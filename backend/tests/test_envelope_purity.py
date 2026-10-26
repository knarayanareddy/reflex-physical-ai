"""THE LAW: the decision path cannot reach the network or a model.

The central claim of this project is that a safety layer which consults the network is not
a safety layer. That claim is only worth making if it is checkable, so this module walks the
import graph of every file in ``app/envelope`` and fails if anything network-capable,
model-capable or non-deterministic appears — directly or as a package.

Two independent checks:

1. **Import graph** (AST): every imported module must be standard library, and must not be
   on the deny list. Relative imports must stay inside ``app.envelope``.
2. **Forbidden tokens** (text): no URL, no client symbol. A docstring may *discuss* the
   network; code may not contain a way to reach it.

The checker is a pure function of ``(filename, source)`` so the test can also prove it
catches a violation, rather than only asserting today's tree is clean.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ENVELOPE_DIR = Path(__file__).resolve().parents[1] / "app" / "envelope"

#: Network, model, process or non-determinism. Nothing here may appear in the decision path.
DENYLIST = frozenset(
    {
        # network / transports
        "socket",
        "ssl",
        "http",
        "urllib",
        "urllib2",
        "ftplib",
        "smtplib",
        "telnetlib",
        "xmlrpc",
        "asyncio",
        "aiohttp",
        "requests",
        "httpx",
        "httpx2",
        "urllib3",
        "websockets",
        "websocket",
        "grpc",
        "boto3",
        "botocore",
        "paramiko",
        "zmq",
        # model / cloud clients
        "openai",
        "anthropic",
        "transformers",
        "torch",
        "onnxruntime",
        "tritonclient",
        "fastapi",
        "starlette",
        "uvicorn",
        "pydantic",
        "jsonschema",
        # process / dynamic loading / non-determinism
        "subprocess",
        "multiprocessing",
        "ctypes",
        "importlib",
        "random",
        "secrets",
        "uuid",
    }
)

#: Allowed standard-library modules whose *non-deterministic* attributes must not be used.
TIME_MUTATORS = frozenset(
    {"time", "time_ns", "monotonic", "perf_counter"}
)  # perf_counter is used for latency only
CLOCK_ATTRIBUTES_NEVER_ALLOWED = frozenset({"now", "today", "utcnow", "fromtimestamp"})
ALLOWED_TIME_ATTRIBUTES = frozenset({"perf_counter", "perf_counter_ns"})

#: Substring scan: a way to reach the network that is not an import.
FORBIDDEN_TOKENS = ("http://", "https://", "urllib", "requests.get", "requests.post", "socket.", "api_key")


def _imported_modules(tree: ast.AST) -> list[tuple[str, int]]:
    """Return ``(module, level)`` for every import in the file."""
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.append((alias.name, 0))
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:  # pragma: no cover - `from . import x`
                continue
            found.append((node.module, node.level or 0))
    return found


def check_source(filename: str, source: str) -> list[str]:
    """Return a list of violations. Pure function, so the test can test the test."""
    problems: list[str] = []
    tree = ast.parse(source, filename=filename)

    for module, level in _imported_modules(tree):
        root = module.split(".")[0]
        if level > 0:
            # Relative import: must resolve inside app.envelope.
            if module not in {"app", "core", "params", "rules"} and not module.startswith("app.envelope"):
                # `from .params import X` parses with level=1, module='params'
                if module.split(".")[0] not in {"core", "params", "rules"}:
                    problems.append(f"{filename}: relative import escapes the package: {'.' * level}{module}")
            continue
        if root == "app":
            if not module.startswith("app.envelope"):
                problems.append(f"{filename}: imports a sibling package: {module}")
            continue
        if root in DENYLIST:
            problems.append(f"{filename}: forbidden import: {module}")
            continue
        if root not in sys.stdlib_module_names:
            problems.append(f"{filename}: third-party import in the decision path: {module}")

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id == "time" and node.attr not in ALLOWED_TIME_ATTRIBUTES:
                problems.append(
                    f"{filename}: time.{node.attr} in the decision path (only perf_counter is allowed)"
                )
            if node.value.id == "datetime" and node.attr in CLOCK_ATTRIBUTES_NEVER_ALLOWED:
                problems.append(f"{filename}: datetime.{node.attr} is a clock read")
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"eval", "exec", "__import__"}
        ):
            problems.append(f"{filename}: {node.func.id}() in the decision path")

    lowered = source.lower()
    for token in FORBIDDEN_TOKENS:
        if token in lowered:
            problems.append(f"{filename}: forbidden token {token!r}")
    return problems


def _envelope_sources() -> list[tuple[str, str]]:
    files = sorted(ENVELOPE_DIR.glob("*.py"))
    assert files, "app/envelope has no python modules"
    return [(path.name, path.read_text(encoding="utf-8")) for path in files]


def test_envelope_package_is_import_clean():
    problems: list[str] = []
    for name, source in _envelope_sources():
        problems.extend(check_source(name, source))
    assert not problems, "the decision path is contaminated:\n  " + "\n  ".join(problems)


def test_envelope_imports_nothing_but_stdlib_and_itself():
    for name, source in _envelope_sources():
        for module, level in _imported_modules(ast.parse(source)):
            if level:
                continue
            root = module.split(".")[0]
            assert root in sys.stdlib_module_names or root == "app", f"{name}: unexpected import {module}"
            if root == "app":
                assert module.startswith("app.envelope"), f"{name}: imports outside the package: {module}"


def test_no_network_or_model_client_in_the_import_graph_transitively():
    """Follow ``app.envelope.*`` imports to closure; only standard library may appear."""
    seen: set[str] = set()
    queue = ["app.envelope"]
    while queue:
        module = queue.pop()
        if module in seen:
            continue
        seen.add(module)
        if not module.startswith("app.envelope"):
            assert module.split(".")[0] in sys.stdlib_module_names, (
                f"transitive import {module} is not stdlib"
            )
            continue
        relative = module.replace("app.envelope", "").strip(".") or "__init__"
        path = ENVELOPE_DIR / f"{relative.split('.')[0]}.py"
        if not path.exists():
            continue
        for imported, level in _imported_modules(ast.parse(path.read_text(encoding="utf-8"))):
            if level:  # pragma: no cover - relative imports of siblings
                queue.append(f"app.envelope.{imported}")
            elif imported.split(".")[0] == "app":
                queue.append(imported)


def test_the_checker_actually_catches_violations():
    """Prove the purity test is not vacuous: feed it code that must be rejected."""
    assert check_source("bad.py", "import httpx\n")
    assert check_source("bad.py", "from openai import OpenAI\n")
    assert check_source("bad.py", "import socket\n")
    assert check_source("bad.py", "from app.tf import ledger\n")
    assert check_source("bad.py", "import time\ntime.time()\n")
    assert check_source("bad.py", "from datetime import datetime\ndatetime.now()\n")
    assert check_source("bad.py", "eval('1+1')\n")
    assert check_source("bad.py", "URL = 'https://api.tokenfactory.nebius.com/v1/'\n")
    assert not check_source("good.py", "import json\nfrom app.envelope.params import Ruleset\n")


def test_decision_path_does_not_import_the_contract_validator():
    """jsonschema transitively reaches urllib; validation belongs at the boundary.

    A docstring may *mention* jsonschema, so this checks the import graph, not the prose.
    """
    for name, source in _envelope_sources():
        for module, _level in _imported_modules(ast.parse(source)):
            assert not module.startswith("app.contracts"), f"{name} must not validate; callers do"
            assert "jsonschema" not in module, f"{name} must not validate; app.contracts does that"


def test_only_perf_counter_is_used_for_timing():
    """``latency_us`` is a measurement, never an input: no wall clock may influence a decision."""
    core = (ENVELOPE_DIR / "core.py").read_text(encoding="utf-8")
    assert "perf_counter_ns" in core
    assert "time.time" not in core
    assert "datetime.now" not in core

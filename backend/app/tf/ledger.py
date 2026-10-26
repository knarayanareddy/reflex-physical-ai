"""Append-only telemetry ledger for Token Factory calls.

This is a *cost and latency* record (one line per model call), not the envelope's veto
ledger. The two artifacts are deliberately separate:

* ``runs/ledger.jsonl``       — telemetry: tokens, latency, cost per model call (this module)
* ``runs/veto-ledger.jsonl``  — one ``EnvelopeDecision`` per envelope evaluation (SPEC C1, Phase B)

Design constraints, learnt the hard way:

* **The path must be explicit.** It used to be derived from ``__file__``, which silently
  resolved into ``site-packages/../runs`` when the package was pip-installed and to
  ``/app/runs`` in the container. It is now ``REFLEX_LEDGER_PATH`` (or ``ledger_path`` in
  settings), falling back to the repository ``runs/`` directory in a source checkout.
* **Writes must be durable and complete.** A single ``write()`` of a line that has already
  been fsync'd cannot leave a half-written record on disk, and an append cannot clobber a
  concurrent writer's line. There is no truncate-then-write path.
* **Every line carries an ``id``** so a re-sent record can be de-duplicated (the
  ledger-durability test in D-T13 depends on this).
"""

from __future__ import annotations

import json
import os
import time
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import REPO_ROOT, settings
from app.storage import append_jsonl, read_jsonl

LEDGER_ENV_VAR = "REFLEX_LEDGER_PATH"
DEFAULT_LEDGER_PATH = REPO_ROOT / "runs" / "ledger.jsonl"
SCHEMA_PATH = REPO_ROOT / "schemas" / "core-schemas.json"


def ledger_path() -> Path:
    """Resolve the ledger destination.

    Precedence: ``REFLEX_LEDGER_PATH`` > ``settings.ledger_path`` > repository default.
    """
    override = os.getenv(LEDGER_ENV_VAR) or settings.ledger_path
    return Path(override).expanduser().resolve() if override else DEFAULT_LEDGER_PATH


@lru_cache(maxsize=1)
def _ledger_validator():
    """Cached JSON-Schema validator for ``$defs/LedgerLine`` (None if unavailable)."""
    try:
        import jsonschema
        from jsonschema import Draft202012Validator
    except ImportError:  # pragma: no cover - jsonschema is a declared dependency
        return None
    if not SCHEMA_PATH.exists():  # installed wheel without the contracts checked out
        return None
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$ref": "#/$defs/LedgerLine",
            "$defs": schema["$defs"],
        }
    )
    assert isinstance(validator, Draft202012Validator) and jsonschema
    return validator


def new_entry_id() -> str:
    """A sortable, collision-resistant record id: ``led_<utc>_<8 hex>``."""
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    return f"led_{stamp}_{uuid.uuid4().hex[:8]}"


def build_entry(
    *,
    kind: str,
    stage: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    cached_tokens: int = 0,
    cost_usd: float = 0.0,
    latency_ms: float = 0.0,
    status: str = "ok",
    notes: str | None = None,
    entry_id: str | None = None,
) -> dict[str, Any]:
    """Build a ``LedgerLine`` without writing it. Useful for tests and dry runs."""
    for name, value in (
        ("prompt_tokens", prompt_tokens),
        ("completion_tokens", completion_tokens),
        ("cached_tokens", cached_tokens),
    ):
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"{name} must be a non-negative integer, got {value!r}")
    if cost_usd < 0:
        raise ValueError(f"cost_usd must be >= 0, got {cost_usd!r}")
    if latency_ms < 0:
        raise ValueError(f"latency_ms must be >= 0, got {latency_ms!r}")

    return {
        "id": entry_id or new_entry_id(),
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "kind": kind,
        "stage": stage,
        "model": model,
        "request": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cached_tokens": cached_tokens,
        },
        "cost_usd": round(float(cost_usd), 6),
        "latency_ms": round(float(latency_ms), 2),
        "status": status,
        "notes": notes,
    }


def validate_entry(entry: dict[str, Any]) -> None:
    """Raise ``jsonschema.ValidationError`` if ``entry`` is not a legal ``LedgerLine``.

    Silently no-ops when the contracts are not present (installed wheel outside a
    checkout); callers in a source tree always get validation.
    """
    validator = _ledger_validator()
    if validator is None:
        return
    validator.validate(entry)


def record_telemetry(
    kind: str,
    stage: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    cached_tokens: int = 0,
    cost_usd: float = 0.0,
    latency_ms: float = 0.0,
    status: str = "ok",
    notes: str | None = None,
    *,
    destination: Path | str | None = None,
    validate: bool = True,
) -> dict[str, Any]:
    """Append one validated telemetry line and return the record that was written."""
    entry = build_entry(
        kind=kind,
        stage=stage,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cached_tokens=cached_tokens,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
        status=status,
        notes=notes,
    )
    if validate:
        validate_entry(entry)

    target = Path(destination).expanduser().resolve() if destination else ledger_path()
    append_jsonl(target, entry)
    return entry


def read_ledger(destination: Path | str | None = None) -> list[dict[str, Any]]:
    """Parse the ledger. Raises on a corrupt line rather than skipping it silently."""
    target = Path(destination).expanduser().resolve() if destination else ledger_path()
    if not target.exists():
        return []
    return read_jsonl(target)

"""JSON-Schema validation of contract objects — the boundary, not the core.

Deliberately outside ``app.envelope``: the envelope must not depend on a library that
transitively reaches ``urllib``/``http``, because its central claim is that the decision
path cannot touch the network. Validation happens here, at the edge of the system, on
the way in (untrusted planner output) and on the way out (the record we are willing to
stand behind).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "schemas" / "core-schemas.json"


class ContractViolation(ValueError):
    """A payload does not satisfy the frozen contract."""

    def __init__(self, defname: str, problems: list[str]) -> None:
        self.defname = defname
        self.problems = problems
        super().__init__(f"{defname}: " + "; ".join(problems[:5]))


@lru_cache(maxsize=1)
def _schema() -> dict[str, Any]:
    if not SCHEMA_PATH.exists():  # installed wheel without the contracts checked out
        raise FileNotFoundError(f"contract file not found: {SCHEMA_PATH}")
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=32)
def _validator(defname: str) -> Draft202012Validator:
    schema = _schema()
    return Draft202012Validator(
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$ref": f"#/$defs/{defname}",
            "$defs": schema["$defs"],
        }
    )


def validate_payload(defname: str, payload: object) -> None:
    """Raise :class:`ContractViolation` if ``payload`` is not a legal ``$defs/<defname>``."""
    errors = sorted(_validator(defname).iter_errors(payload), key=lambda e: list(e.path))
    if not errors:
        return
    problems = []
    for error in errors[:10]:
        location = "/".join(str(part) for part in error.path) or "<root>"
        problems.append(f"{location}: {error.message}")
    raise ContractViolation(defname, problems)


def is_valid(defname: str, payload: object) -> bool:
    try:
        validate_payload(defname, payload)
    except (ContractViolation, jsonschema.exceptions.SchemaError):
        return False
    return True

"""Contract and build provenance.

``envelope_version`` is defined by the contract as *sha256 of (veto-taxonomy.json +
envelope source)*: it ties every decision to the exact rule set that produced it. The
envelope itself does not exist yet (Phase B); this module provides the cheap half —
the taxonomy digest — so ``/v1/info`` can report which rules are live, and so a future
decision record has a single place to get the value from.
"""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TAXONOMY_PATH = REPO_ROOT / "data" / "veto-taxonomy.json"
SCHEMA_PATH = REPO_ROOT / "schemas" / "core-schemas.json"

UNKNOWN = "unknown"


def file_sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


@lru_cache(maxsize=1)
def taxonomy_version() -> str:
    """sha256 of the frozen rule table, or ``"unknown"`` outside a source checkout."""
    return file_sha256(TAXONOMY_PATH) or UNKNOWN


@lru_cache(maxsize=1)
def taxonomy_rule_count() -> int:
    if not TAXONOMY_PATH.exists():
        return 0
    try:
        return len(json.loads(TAXONOMY_PATH.read_text(encoding="utf-8")).get("rules", []))
    except (json.JSONDecodeError, OSError):  # pragma: no cover - defensive
        return 0


@lru_cache(maxsize=1)
def contract_version() -> str:
    """The ``schema_version`` declared in the frozen contracts."""
    if not SCHEMA_PATH.exists():
        return UNKNOWN
    try:
        return str(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")).get("schema_version", UNKNOWN))
    except (json.JSONDecodeError, OSError):  # pragma: no cover - defensive
        return UNKNOWN

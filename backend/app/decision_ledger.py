"""The veto ledger: one ``EnvelopeDecision`` per evaluation, veto or allow.

This is insight #2 as a file. The telemetry ledger (``app/tf/ledger.py``) records what the
models cost; this records what the machine *refused to do*, with the sensor state, the
firing rule, the full rule trace and the intended action preserved.

Every record is validated against ``$defs/EnvelopeDecision`` before it is written. A
decision the contract does not accept is a bug, and a ledger of unvalidated decisions is
not an audit trail.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.config import REPO_ROOT, settings
from app.contracts import validate_payload
from app.storage import append_jsonl, read_jsonl, resolve_path

LEDGER_ENV_VAR = "REFLEX_VETO_LEDGER_PATH"
DEFAULT_VETO_LEDGER = REPO_ROOT / "runs" / "veto-ledger.jsonl"


def veto_ledger_path() -> Path:
    """Resolve the veto-ledger destination: env var > settings > repository default."""
    return resolve_path(
        getattr(settings, "veto_ledger_path", "") or None, LEDGER_ENV_VAR, DEFAULT_VETO_LEDGER
    )


def record_decision(decision: dict[str, Any], destination: Path | str | None = None) -> dict[str, Any]:
    """Validate and append one decision. Returns the record that was written."""
    validate_payload("EnvelopeDecision", decision)
    target = Path(destination).expanduser().resolve() if destination else veto_ledger_path()
    append_jsonl(target, decision)
    return decision


def read_decisions(destination: Path | str | None = None) -> list[dict[str, Any]]:
    target = Path(destination).expanduser().resolve() if destination else veto_ledger_path()
    return read_jsonl(target)

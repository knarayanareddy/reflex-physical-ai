"""Durable JSONL storage: one record per line, append-only, fsync'd.

Shared by the telemetry ledger (``runs/ledger.jsonl``) and the veto ledger
(``runs/veto-ledger.jsonl``) because both are evidence, and evidence that can be
half-written is not evidence.

There is deliberately no truncate/rewrite path here. A ledger is appended to or it is
read; nothing in this module can lose an existing record.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class CorruptLedger(ValueError):
    """A line in the ledger could not be parsed."""


def append_jsonl(target: Path, record: dict[str, Any]) -> None:
    """Append ``record`` as one JSON line and flush it to disk before returning.

    A single write of a newline-terminated line, followed by ``fsync``, means a reader
    sees either the whole record or none of it. ``allow_nan=False`` matters for the
    determinism story: NaN serialises differently across writers and would make a
    replay hash unstable.
    """
    line = json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n"
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "a", encoding="utf-8") as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())


def read_jsonl(target: Path) -> list[dict[str, Any]]:
    """Parse a JSONL file. A corrupt line raises rather than being skipped."""
    if not target.exists():
        return []
    records: list[dict[str, Any]] = []
    with open(target, encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise CorruptLedger(f"{target}:{lineno} is not valid JSON: {exc}") from exc
    return records


def resolve_path(override: str | None, env_var: str, default: Path) -> Path:
    """Resolve a ledger path: explicit argument > environment > repository default."""
    configured = (override or "").strip() or os.getenv(env_var, "").strip()
    return Path(configured).expanduser().resolve() if configured else default

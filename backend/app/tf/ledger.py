import json
import time
from pathlib import Path
from typing import Optional, Dict, Any

LEDGER_PATH = Path(__file__).resolve().parents[3] / "runs" / "ledger.jsonl"

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
    notes: Optional[str] = None
):
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "kind": kind,
        "stage": stage,
        "model": model,
        "request": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cached_tokens": cached_tokens
        },
        "cost_usd": round(cost_usd, 6),
        "latency_ms": round(latency_ms, 2),
        "status": status,
        "notes": notes
    }
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LEDGER_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry

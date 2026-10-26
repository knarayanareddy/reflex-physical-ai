# backend — Reflex

The importable application package. Install or run it from here:

```bash
cd backend
uv run --extra dev pytest -q          # tests
uv run python -m app.main             # serve on :8000
```

Layout:

| Path | Purpose | Status |
|---|---|---|
| `app/config.py` | Settings from environment / `.env` | working |
| `app/main.py` | FastAPI surface: `/health`, `/v1/info` | working, deliberately small |
| `app/version.py` | Contract + taxonomy provenance (`taxonomy_version`) | working |
| `app/tf/ledger.py` | Append-only telemetry ledger (`runs/ledger.jsonl`) | working |
| `app/gate/gate.py` | Evidence-quote checker (**not** the safety envelope) | placeholder |
| `app/envelope/` | Deterministic V1–V10 envelope, purity + determinism tests | **Phase B — not written** |

The repository-wide quickstart, guarantees and limitations live in the root
[`README.md`](../README.md) and [`LIMITATIONS.md`](../LIMITATIONS.md).

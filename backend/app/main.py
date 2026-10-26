"""FastAPI surface.

Scope note, so nobody mistakes this for the product: the deterministic envelope
(V1–V10), the planner and the replay lane are Phase B. This module currently exposes
liveness and provenance only. ``/health`` must never report a capability the process
does not have, and it must never echo a credential.
"""

from __future__ import annotations

from fastapi import FastAPI

from app import version
from app.config import settings

app = FastAPI(
    title="Reflex — Deterministic Edge Safety Envelope & Cloud Replay for Physical AI",
    description=(
        "Cloud VLM proposes robotic actions; a local deterministic envelope holds hard veto "
        "authority over keep-out volumes and force limits. This build exposes provenance and "
        "liveness; the envelope itself is not yet implemented."
    ),
    version="0.1.0",
)


@app.get("/health")
def health_check() -> dict[str, object]:
    """Liveness. Reports capability flags, never credential values."""
    return {
        "status": "ok",
        "environment": settings.environment,
        "capabilities": {
            "nebius_credentials": settings.has_nebius_credentials,
            "tavily_credentials": settings.has_tavily_credentials,
            "envelope_implemented": False,
        },
    }


@app.get("/v1/info")
def get_info() -> dict[str, object]:
    """Provenance: which models are pinned, which rule table is loaded, which contract."""
    return {
        "project": "Reflex — Deterministic Edge Safety Envelope & Cloud Replay for Physical AI",
        "track": "Physical AI",
        "build": {
            "contract_version": version.contract_version(),
            "taxonomy_version": version.taxonomy_version(),
            "taxonomy_rules": version.taxonomy_rule_count(),
            "envelope_implemented": False,
        },
        "models": {
            "ultra": settings.model_ultra,
            "super": settings.model_super,
            "nano": settings.model_nano,
            "vision": settings.model_vision,
        },
    }


if __name__ == "__main__":  # pragma: no cover - exercised by `make demo`
    import uvicorn

    # Only pass an import string when reload is on: reload needs it, and it avoids the
    # old `python -m app.main` bug where the module was imported twice (once as
    # __main__, once as app.main), giving the process two Settings singletons.
    if settings.environment == "development":
        uvicorn.run(
            "app.main:app", host="0.0.0.0", port=8000, reload=True, log_level=settings.log_level.lower()
        )
    else:
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level=settings.log_level.lower())

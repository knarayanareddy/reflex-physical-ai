"""FastAPI surface.

Two layers, deliberately separated:

* the HTTP boundary — validates untrusted input against the frozen contracts and records
  what came back;
* the deterministic envelope — ``app.envelope``, which cannot reach the network and is
  the only thing that decides whether motion happens.

Nothing here widens the envelope: a planner's payload is validated, evaluated and either
refused or clamped. The cloud can propose; it cannot permit.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app import version
from app.config import settings
from app.contracts import ContractViolation, validate_payload
from app.decision_ledger import record_decision, veto_ledger_path
from app.envelope import EnvelopeInputError, ParameterError, Ruleset, envelope_version, evaluate, load_ruleset
from app.replay import compare

app = FastAPI(
    title="Reflex — Deterministic Edge Safety Envelope & Cloud Replay for Physical AI",
    description=(
        "Cloud VLM proposes robotic actions; a local deterministic envelope holds hard veto "
        "authority over keep-out volumes and force limits. The decision path imports no network "
        "client and no model client; it is enforced by tests/test_envelope_purity.py."
    ),
    version="0.2.0",
)


@lru_cache(maxsize=1)
def ruleset() -> Ruleset:
    """Load the taxonomy + calibration once. A broken parameter set fails at first use."""
    return load_ruleset()


class EvaluateRequest(BaseModel):
    """Untrusted input: a sensor snapshot and a proposed action."""

    model_config = ConfigDict(extra="forbid")

    snapshot: dict[str, Any] = Field(description="A $defs/SensorSnapshot")
    proposal: dict[str, Any] = Field(description="A $defs/ActionProposal, from any source")
    requested_mode: Literal["normal", "degraded", "simulation"] = "normal"


class ReplayRequest(BaseModel):
    """A decision that has already been made, to be replayed down both arms."""

    model_config = ConfigDict(extra="forbid")

    decision: dict[str, Any] = Field(description="A $defs/EnvelopeDecision, as returned by /evaluate")


@app.get("/health")
def health_check() -> dict[str, object]:
    """Liveness plus capability. Never echoes a credential."""
    envelope_state = "ok"
    profile: str | None = None
    try:
        active = ruleset()
        profile = active.profile
    except (ParameterError, FileNotFoundError) as exc:  # pragma: no cover - misconfiguration
        envelope_state = f"unavailable: {exc}"

    return {
        "status": "ok",
        "environment": settings.environment,
        "capabilities": {
            "nebius_credentials": settings.has_nebius_credentials,
            "tavily_credentials": settings.has_tavily_credentials,
            "envelope_implemented": True,
            "envelope_state": envelope_state,
        },
        "envelope": {"profile": profile, "calibration_provenance": active.provenance if profile else None}
        if profile
        else None,
    }


@app.get("/v1/info")
def get_info() -> dict[str, object]:
    """Provenance: pinned models, contract version, and exactly which rules are live."""
    return {
        "project": "Reflex — Deterministic Edge Safety Envelope & Cloud Replay for Physical AI",
        "track": "Physical AI",
        "build": {
            "contract_version": version.contract_version(),
            "taxonomy_version": version.taxonomy_version(),
            "taxonomy_rules": version.taxonomy_rule_count(),
            "envelope_implemented": True,
        },
        "models": {
            "ultra": settings.model_ultra,
            "super": settings.model_super,
            "nano": settings.model_nano,
            "vision": settings.model_vision,
        },
    }


@app.get("/v1/envelope/info")
def envelope_info() -> dict[str, object]:
    """The live rule table, the calibration profile and the version that pins them."""
    active = ruleset()
    return {
        "envelope_version": envelope_version(active),
        "profile": active.profile,
        "calibration_provenance": active.provenance,
        "measured": active.is_measured,
        "simulation_badge_required": not active.is_measured,
        "rig": active.rig,
        "rules": [
            {
                "rule_id": rule.rule_id,
                "priority": rule.priority,
                "severity": rule.severity,
                "applies_to_modes": list(rule.applies_to_modes),
                "parameters": {
                    "normal": active.normal.values.get(rule.rule_id, {}),
                    "degraded": active.degraded.values.get(rule.rule_id, {}),
                },
            }
            for rule in active.rules
        ],
        "veto_ledger_path": str(veto_ledger_path()),
    }


@app.post("/v1/envelope/evaluate")
def evaluate_endpoint(request: EvaluateRequest) -> dict[str, Any]:
    """Evaluate one proposal. The response is the decision, already written to the ledger."""
    try:
        validate_payload("SensorSnapshot", request.snapshot)
        validate_payload("ActionProposal", request.proposal)
    except ContractViolation as exc:
        # Rejected before it became a decision: nothing to evaluate, nothing to log.
        raise HTTPException(
            status_code=422, detail={"contract": exc.defname, "problems": exc.problems}
        ) from exc

    try:
        decision = evaluate(ruleset(), request.snapshot, request.proposal, request.requested_mode)
    except (EnvelopeInputError, ParameterError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    record_decision(decision)
    return decision


@app.post("/v1/replay")
def replay_endpoint(request: ReplayRequest) -> dict[str, Any]:
    """Replay one recorded decision down both arms and return the comparison.

    ``envelope_off`` executes the action the planner asked for with no safety layer;
    ``envelope_on`` executes what shipped (nothing, after a veto). Deterministic: the response
    is a function of the decision, the rig and the calibration, and of nothing else — no clock,
    no network, no model. Both arms are validated against ``$defs/ReplayResult`` before they
    leave this process, because a record the contract rejects is not evidence.
    """
    try:
        validate_payload("EnvelopeDecision", request.decision)
    except ContractViolation as exc:
        raise HTTPException(
            status_code=422, detail={"contract": exc.defname, "problems": exc.problems}
        ) from exc

    active = ruleset()
    bounds = active.policy.mapping("V5_WORKSPACE_BOUND", "allowed_volume")
    ceiling = active.params_for(request.decision["parameter_set"]).number(
        "V3_VELOCITY_LIMIT", "max_velocity_mm_s"
    )
    comparison = compare(request.decision, active.rig, bounds, ceiling)
    for arm in ("envelope_off", "envelope_on"):
        try:
            validate_payload("ReplayResult", comparison[arm])
        except ContractViolation as exc:  # pragma: no cover - a bug in app.replay, not in input
            raise HTTPException(
                status_code=500, detail={"contract": exc.defname, "problems": exc.problems}
            ) from exc
    return comparison


if __name__ == "__main__":  # pragma: no cover - exercised by `make demo`
    import uvicorn

    if settings.environment == "development":
        uvicorn.run(
            "app.main:app", host="0.0.0.0", port=8000, reload=True, log_level=settings.log_level.lower()
        )
    else:
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level=settings.log_level.lower())

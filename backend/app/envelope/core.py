"""The deterministic core: evaluate a snapshot + proposal into one EnvelopeDecision.

Contract of this module (the whole point of the project):

* **Pure.** Given the same ``(snapshot, proposal, envelope_version)`` it returns the same
  decision, in any process, on any machine, in any order. No clock feeds a decision; the
  only clock read is ``perf_counter`` for the ``latency_us`` measurement field, which is
  excluded from the determinism claim.
* **No network, no model.** Enforced by ``tests/test_envelope_purity.py``.
* **Fail-safe.** A rule that raises becomes a VETO. Uncertainty stops motion.
* **First veto wins; clamps are superseded.** Rules run in priority order. The first
  stopping result (VETO / SENSOR_MISSING / SENSOR_STALE) in that order names the decision.
  A clamp is recorded but never outranks a veto, because a rejected plan ships nothing.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Mapping
from typing import Any

from app.envelope.params import MODES, Ruleset
from app.envelope.rules import (
    DEGRADE,
    RULES,
    STOPPING_RESULTS,
    Context,
    RuleResult,
    network_degraded,
)

DECISION_ID_PREFIX = "d_"
UNIDENTIFIED_PROPOSAL = "p_unidentified"
UNIDENTIFIED_SNAPSHOT = "s_unidentified"

#: Recorded in the snapshot but never an input to a decision (SPEC §4.2). Excluding it
#: from the hash makes the hash a property of the semantic inputs: a replay that stamps a
#: new monotonic time still reproduces the same hash.
HASH_EXCLUDED_SNAPSHOT_FIELDS = ("ts_mono_ms",)

_ACTION_PROPOSAL_REQUIRED = (
    "proposal_id",
    "plan_id",
    "kind",
    "target_pose",
    "velocity_limit",
    "force_limit",
    "preconditions",
    "expected_end_state",
    "source",
    "issued_at",
    "ttl_ms",
)
_KINDS = {"move_to", "push", "grasp", "release", "home", "wait", "retract"}
_SOURCES = {"cloud_ultra", "cloud_nano", "cloud_gr00t", "cosmos_reason", "edge_local", "hardcoded_sequence"}


class EnvelopeInputError(ValueError):
    """The envelope was handed something it cannot honestly reason about."""


# ----------------------------------------------------------------------------- hashing


def canonical_json(value: Any) -> str:
    """Deterministic JSON: sorted keys, no whitespace, NaN refused.

    ``allow_nan=False`` is deliberate. NaN has no canonical text form and would make a
    replay hash depend on the tool that wrote the file.
    """
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def determinism_hash(snapshot: Mapping[str, Any], proposal: Mapping[str, Any], envelope_version: str) -> str:
    """sha256 of the canonicalised (snapshot, intended_action, envelope_version)."""
    slim_snapshot = {k: v for k, v in snapshot.items() if k not in HASH_EXCLUDED_SNAPSHOT_FIELDS}
    return _sha256(
        canonical_json(
            {"envelope_version": envelope_version, "proposal": proposal, "snapshot": slim_snapshot}
        )
    )


def envelope_version(ruleset: Ruleset) -> str:
    """Pin a decision to the exact rules, values and code that produced it."""
    digest = _sha256(
        canonical_json(
            {
                "calibration": ruleset.calibration_digest,
                "profile": ruleset.profile,
                "provenance": ruleset.provenance,
                "source": ruleset.source_digest,
                "taxonomy": ruleset.taxonomy_digest,
            }
        )
    )
    return f"sha256:{digest}"


# ------------------------------------------------------------------------ mode resolution


def resolve_mode(ruleset: Ruleset, snapshot: Mapping[str, Any], requested_mode: str) -> tuple[str, str]:
    """Return ``(mode, parameter_set)``.

    Mode is resolved *before* rule evaluation because V8's effect is a parameter-set
    switch that every other rule depends on. Rules still run in priority order; V8's trace
    entry reports the transition.

    The debounce window comes from the **normal** set: using the degraded window to decide
    whether to enter degraded mode would be circular.
    """
    if requested_mode not in MODES:
        raise EnvelopeInputError(f"requested_mode {requested_mode!r} is not one of {MODES}")

    window = ruleset.normal.number("V8_NETWORK_DEGRADED", "window_ms")
    cloud_outage = network_degraded(snapshot, window)
    wants_degraded = requested_mode == "degraded" or cloud_outage
    parameter_set = "degraded" if wants_degraded else "normal"

    if not ruleset.is_measured:
        # Unmeasured parameters must never masquerade as a hardware decision.
        return "simulation", parameter_set
    if requested_mode == "simulation":
        return "simulation", parameter_set
    return ("degraded" if wants_degraded else "normal"), parameter_set


# ------------------------------------------------------------------------------ helpers


def _looks_like_action_proposal(proposal: Mapping[str, Any]) -> bool:
    """Cheap structural gate, mirroring $defs/ActionProposal without a schema library."""
    if any(key not in proposal for key in _ACTION_PROPOSAL_REQUIRED):
        return False
    if proposal.get("kind") not in _KINDS or proposal.get("source") not in _SOURCES:
        return False
    velocity = proposal.get("velocity_limit")
    if isinstance(velocity, bool) or not isinstance(velocity, (int, float)) or velocity <= 0:
        return False
    force = proposal.get("force_limit")
    if force is not None and (isinstance(force, bool) or not isinstance(force, (int, float))):
        return False
    if not isinstance(proposal.get("target_pose"), Mapping):
        return False
    if not isinstance(proposal.get("preconditions"), list):
        return False
    if not isinstance(proposal.get("expected_end_state"), Mapping):
        return False
    return isinstance(proposal.get("ttl_ms"), int) and not isinstance(proposal.get("ttl_ms"), bool)


def _safe_id(value: Any, prefix: str, fallback: str) -> str:
    return value if isinstance(value, str) and value.startswith(prefix) else fallback


def _run_rule(rule_id: str, ctx: Context) -> RuleResult:
    rule = RULES.get(rule_id)
    if rule is None:
        # A taxonomy rule with no implementation must never pass silently.
        return RuleResult("VETO", f"rule {rule_id} is declared in the taxonomy but not implemented")
    try:
        return rule(ctx)
    except Exception as exc:
        return RuleResult("VETO", f"rule {rule_id} raised {type(exc).__name__}: {exc}")


# ----------------------------------------------------------------------------- evaluate


def evaluate(
    ruleset: Ruleset,
    snapshot: Mapping[str, Any],
    proposal: Mapping[str, Any],
    requested_mode: str = "normal",
) -> dict[str, Any]:
    """Evaluate one proposal against one snapshot. Returns a contract-shaped decision dict.

    The returned dict has not been schema-validated here: validation needs ``jsonschema``,
    which lives outside the pure core. Callers at the boundary use
    ``app.contracts.validate_payload("EnvelopeDecision", decision)``.
    """
    started = time.perf_counter_ns()

    if not isinstance(snapshot, Mapping) or not isinstance(proposal, Mapping):
        raise EnvelopeInputError("snapshot and proposal must be mappings")
    decided_at = snapshot.get("ts_wall")
    if not isinstance(decided_at, str) or not decided_at:
        raise EnvelopeInputError(
            "snapshot.ts_wall is required: a decision needs a timestamp that is an input, not a clock"
        )

    mode, parameter_set = resolve_mode(ruleset, snapshot, requested_mode)
    params = ruleset.params_for(parameter_set)

    ctx = Context(
        snapshot=snapshot,
        proposal=proposal,
        params=params,
        policy=ruleset.normal,
        parameter_set=parameter_set,
        requested_mode=requested_mode,
        resolved_mode=mode,
    )

    trace: list[dict[str, Any]] = []
    clamps: list[tuple[str, Mapping[str, Any]]] = []
    stop: tuple[str, RuleResult] | None = None

    for rule in ruleset.rules:
        result = _run_rule(rule.rule_id, ctx)
        entry: dict[str, Any] = {
            "rule_id": rule.rule_id,
            "result": result.result,
            "parameter_set_used": parameter_set,
            "detail": result.detail,
        }
        trace.append(entry)

        if result.result == "CLAMP" and result.clamp:
            clamps.append((rule.rule_id, result.clamp))
        elif result.result in STOPPING_RESULTS and stop is None:
            stop = (rule.rule_id, result)
        elif result.result == DEGRADE:
            pass  # the mode change is already reflected in `parameter_set`

    rules_evaluated = [rule.rule_id for rule in ruleset.rules]
    first_veto_index = rules_evaluated.index(stop[0]) if stop else None

    shipped_action: dict[str, Any] | None
    clamp_applied: dict[str, Any] | None = None

    if stop is not None:
        outcome, rule_id = "VETO", stop[0]
        shipped_action = None
    elif clamps:
        outcome, rule_id = "ALLOW_CLAMPED", clamps[0][0]
        merged: dict[str, Any] = {"rule_id": clamps[0][0]}
        for _clamp_rule, clamp in clamps:
            merged.update({k: v for k, v in clamp.items()})
        merged["rule_id"] = clamps[0][0]
        clamp_applied = merged
        shipped_action = _apply_clamp(proposal, merged)
    else:
        outcome, rule_id = "ALLOW", None
        shipped_action = dict(proposal)

    version = envelope_version(ruleset)
    digest = determinism_hash(snapshot, proposal, version)

    structured = _looks_like_action_proposal(proposal)
    relay_was_closed = snapshot.get("relay_state") is True
    hard_stop = stop is not None and ruleset.severity(stop[0]) == "hard_stop"

    decision: dict[str, Any] = {
        # The id is a content address: the same inputs produce the same decision id, so a
        # double-shipped record is detectable rather than duplicated.
        "decision_id": f"{DECISION_ID_PREFIX}{digest[:24]}",
        "proposal_id": _safe_id(proposal.get("proposal_id"), "p_", UNIDENTIFIED_PROPOSAL),
        "snapshot_id": _safe_id(snapshot.get("snapshot_id"), "s_", UNIDENTIFIED_SNAPSHOT),
        "outcome": outcome,
        "rule_id": rule_id,
        "rules_evaluated": rules_evaluated,
        "rule_trace": trace,
        "first_veto_index": first_veto_index,
        "intended_action": dict(proposal) if structured else None,
        "intended_action_raw": None if structured else dict(proposal),
        "shipped_action": shipped_action,
        "clamp_applied": clamp_applied,
        "mode": mode,
        "parameter_set": parameter_set,
        "interlock_relay_opened": bool(hard_stop and relay_was_closed),
        "latency_us": (time.perf_counter_ns() - started) / 1000.0,
        "envelope_version": version,
        "determinism_hash": digest,
        "decided_at": decided_at,
        "device_id": str((snapshot.get("device") or {}).get("device_id") or "unknown-device"),
        "firmware_version": (snapshot.get("device") or {}).get("firmware_version"),
        "buffered_locally": snapshot.get("network", {}).get("cloud_reachable") is False
        if isinstance(snapshot.get("network"), Mapping)
        else False,
        "replayed": False,
    }

    # The raw snapshot travels with EVERY decision, not only vetoes. A record that cannot be
    # re-evaluated without a second file is not an audit trail: the replay lane has to
    # re-derive an ALLOW as readily as a VETO, and a join key that may point at a rotated
    # file is a silent way to lose the evidence. The cost is ledger size; the alternative is
    # a decision that cannot be checked.
    decision["sensor_snapshot_inline"] = dict(snapshot)

    return decision


def _apply_clamp(proposal: Mapping[str, Any], clamp: Mapping[str, Any]) -> dict[str, Any]:
    shipped = {key: value for key, value in proposal.items()}
    velocity = clamp.get("velocity")
    if isinstance(velocity, (list, tuple)) and len(velocity) == 2:
        shipped["velocity_limit"] = velocity[1]
    target = clamp.get("target_pose")
    if isinstance(target, Mapping) and isinstance(target.get("after"), Mapping):
        shipped["target_pose"] = dict(target["after"])
    return shipped

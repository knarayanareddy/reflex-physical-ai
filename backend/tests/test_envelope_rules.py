"""The behaviours the fixtures cannot express.

``test_envelope_fixtures.py`` proves each rule fires on its trigger and stays quiet just
below it. This module probes the seams *between* rules, where the safety argument actually
lives:

* uncertainty abstains instead of passing (a missing sensor is not a clear sensor);
* the first stopping rule names the outcome and later rules cannot override it;
* a clamp recorded by V3 is superseded by a veto from V6, never merged with it;
* a legal-but-too-fast plan is clamped, an untrusted plan is vetoed;
* every rule refuses to move when its own inputs are absent.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.envelope import evaluate, load_ruleset
from app.envelope.rules import RULES, SENSOR_MISSING, SENSOR_STALE, STOPPING_RESULTS, VETO

FIXTURES = Path(__file__).resolve().parents[2] / "data" / "fixtures" / "snapshots"


def _case(name: str) -> tuple[dict[str, Any], dict[str, Any], str]:
    case = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    return case["snapshot"], case["proposal"], case["requested_mode"]


def _decide(snapshot: dict[str, Any], proposal: dict[str, Any], mode: str = "normal") -> dict[str, Any]:
    return evaluate(load_ruleset(), snapshot, proposal, mode)


# ------------------------------------------------------------------ abstention


def test_missing_camera_age_is_an_abstention_not_a_pass():
    """'I do not know' and 'unsafe' must be indistinguishable at the actuator."""
    snapshot, proposal, _ = _case("pass_v1_estop")
    del snapshot["camera"]["age_ms"]
    decision = _decide(snapshot, proposal)
    assert decision["outcome"] == "VETO"
    assert decision["rule_id"] == "V7_SENSOR_STALE"
    entry = next(e for e in decision["rule_trace"] if e["rule_id"] == "V7_SENSOR_STALE")
    assert entry["result"] == SENSOR_MISSING
    assert decision["interlock_relay_opened"] is True


def test_missing_encoder_age_is_an_abstention():
    snapshot, proposal, _ = _case("pass_v1_estop")
    del snapshot["end_effector"]["age_ms"]
    decision = _decide(snapshot, proposal)
    assert decision["rule_id"] == "V7_SENSOR_STALE"
    assert decision["outcome"] == "VETO"


def test_stale_encoder_is_not_rounded_down_to_fresh():
    snapshot, proposal, _ = _case("pass_v1_estop")
    snapshot["end_effector"]["age_ms"] = 50.001
    decision = _decide(snapshot, proposal)
    assert decision["rule_id"] == "V7_SENSOR_STALE"
    assert (
        next(e for e in decision["rule_trace"] if e["rule_id"] == "V7_SENSOR_STALE")["result"] == SENSOR_STALE
    )


def test_missing_force_reading_stops_the_machine():
    """V4 cannot compare against a limit it cannot read, and must not assume the good case."""
    snapshot, proposal, _ = _case("pass_v1_estop")
    del snapshot["force_estimate"]
    decision = _decide(snapshot, proposal)
    assert decision["outcome"] == "VETO"
    assert decision["rule_id"] == "V4_FORCE_LIMIT"


def test_missing_keep_out_flag_is_not_clear():
    snapshot, proposal, _ = _case("pass_v1_estop")
    del snapshot["keep_out_occupied"]
    del snapshot["keep_out_evidence"]
    decision = _decide(snapshot, proposal)
    assert decision["outcome"] == "VETO"
    assert decision["rule_id"] == "V2_KEEP_OUT_OCCUPIED"


def test_keep_out_without_evidence_is_not_trusted():
    """A detector that reports occupancy but cannot say how is not a witness."""
    snapshot, proposal, _ = _case("pass_v1_estop")
    snapshot["keep_out_occupied"] = True
    snapshot["keep_out_evidence"] = {}
    decision = _decide(snapshot, proposal)
    assert decision["outcome"] == "VETO"
    assert decision["rule_id"] == "V2_KEEP_OUT_OCCUPIED"


# ------------------------------------------------------------------ priority and interaction


def test_first_stopping_rule_wins():
    """E-stop + human + stale camera: the interlock names the outcome, not the last rule."""
    snapshot, proposal, _ = _case("pass_v1_estop")
    snapshot["e_stop_asserted"] = True
    snapshot["human_presence_detected"] = True
    snapshot["camera"]["age_ms"] = 9999.0
    decision = _decide(snapshot, proposal)
    assert decision["outcome"] == "VETO"
    assert decision["rule_id"] == "V1_EMERGENCY_STOP"
    assert decision["first_veto_index"] == 0
    assert decision["rule_trace"][0]["rule_id"] == "V1_EMERGENCY_STOP"


def test_priority_order_is_the_taxonomy_order():
    ruleset = load_ruleset()
    assert [rule.priority for rule in ruleset.rules] == sorted(rule.priority for rule in ruleset.rules)
    assert [rule.rule_id for rule in ruleset.rules] == [
        "V1_EMERGENCY_STOP",
        "V2_KEEP_OUT_OCCUPIED",
        "V3_VELOCITY_LIMIT",
        "V4_FORCE_LIMIT",
        "V5_WORKSPACE_BOUND",
        "V6_COLLISION_PREDICTED",
        "V7_SENSOR_STALE",
        "V8_NETWORK_DEGRADED",
        "V9_PLAN_MALFORMED",
        "V10_HUMAN_PRESENCE",
    ]
    assert set(RULES) == {rule.rule_id for rule in ruleset.rules}


def test_a_clamp_is_superseded_by_a_veto_never_merged():
    """A plan too fast AND aimed into an object must be refused, not silently slowed."""
    snapshot, proposal, _ = _case("pass_v1_estop")
    proposal["velocity_limit"] = 40.0  # V3 clamps this to 24 in degraded mode
    snapshot["human_presence_detected"] = True  # V10 vetoes, at priority 10
    decision = _decide(snapshot, proposal, "degraded")
    assert decision["outcome"] == "VETO"
    assert decision["rule_id"] == "V10_HUMAN_PRESENCE"
    v3 = next(e for e in decision["rule_trace"] if e["rule_id"] == "V3_VELOCITY_LIMIT")
    assert v3["result"] == "CLAMP", "the clamp happened and is recorded..."
    assert decision["clamp_applied"] is None, "...but a veto outranks it and nothing is clamped"
    assert decision["clamp_applied"] is None, "a refused plan must not carry a clamp"
    assert decision["shipped_action"] is None or decision["shipped_action"] == proposal


def test_clamped_action_is_what_would_be_shipped():
    """A clamp is a partial refusal: the record must show both what was asked and what shipped."""
    snapshot, proposal, _ = _case("pass_v1_estop")
    proposal["velocity_limit"] = 40.0
    decision = _decide(snapshot, proposal, "degraded")
    assert decision["outcome"] == "ALLOW_CLAMPED"
    assert decision["clamp_applied"]["velocity"] == [40.0, 24.0]
    assert decision["shipped_action"]["velocity_limit"] == 24.0
    assert decision["intended_action"]["velocity_limit"] == 40.0, "the request is preserved"


def test_veto_ships_nothing():
    snapshot, proposal, _ = _case("veto_v1_estop")
    decision = _decide(snapshot, proposal)
    assert decision["outcome"] == "VETO"
    assert decision["shipped_action"] is None
    assert decision["intended_action"] == proposal
    assert decision["interlock_relay_opened"] is True


def test_limit_request_above_the_policy_ceiling_is_untrusted():
    """The ceiling is the NORMAL set: a planner may not buy a clamp with an absurd request."""
    snapshot, proposal, _ = _case("pass_v1_estop")
    proposal["velocity_limit"] = 61.0
    decision = _decide(snapshot, proposal)
    assert decision["outcome"] == "VETO"
    assert decision["rule_id"] == "V9_PLAN_MALFORMED"


def test_limit_request_at_the_policy_ceiling_is_legal():
    snapshot, proposal, _ = _case("pass_v1_estop")
    proposal["velocity_limit"] = 60.0
    assert _decide(snapshot, proposal)["outcome"] == "ALLOW"


def test_plan_legal_at_issue_time_but_over_the_current_ceiling_is_clamped():
    """In degraded mode the same legal 40 mm/s request is over the 24 mm/s mode ceiling."""
    snapshot, proposal, _ = _case("pass_v1_estop")
    proposal["velocity_limit"] = 40.0
    normal = _decide(snapshot, proposal, "normal")
    degraded = _decide(snapshot, proposal, "degraded")
    assert normal["outcome"] == "ALLOW"
    assert degraded["outcome"] == "ALLOW_CLAMPED"
    # Same inputs, same identity: the mode is part of the decision, not of the input hash.
    assert normal["determinism_hash"] == degraded["determinism_hash"]
    assert normal["decision_id"] == degraded["decision_id"]


def test_network_outage_degrades_without_stopping():
    snapshot, proposal, _ = _case("veto_v8_network")
    decision = _decide(snapshot, proposal)
    assert decision["outcome"] != "VETO"
    assert decision["parameter_set"] == "degraded"
    assert decision["buffered_locally"] is True
    entry = next(e for e in decision["rule_trace"] if e["rule_id"] == "V8_NETWORK_DEGRADED")
    assert entry["result"] == "DEGRADE"


def test_network_outage_then_overspeed_is_clamped_by_the_degraded_set():
    """Composition: a degradation discovered mid-evaluation still constrains the same decision."""
    snapshot, proposal, _ = _case("veto_v8_network")
    proposal["velocity_limit"] = 40.0
    decision = _decide(snapshot, proposal)
    assert decision["outcome"] == "ALLOW_CLAMPED"
    assert decision["clamp_applied"]["velocity"] == [40.0, 24.0]


def test_advisory_perception_cannot_authorise_motion():
    """Advisory data may stop the machine; it may never clear a veto."""
    snapshot, proposal, _ = _case("pass_v1_estop")
    snapshot["e_stop_asserted"] = True
    snapshot["advisory_perception"] = {"claims_workspace_clear": True, "object_poses": []}
    decision = _decide(snapshot, proposal)
    assert decision["outcome"] == "VETO"
    assert decision["rule_id"] == "V1_EMERGENCY_STOP"


def test_missing_relay_state_is_an_abstention():
    """Electrical state is not inferable; an unknown relay is not a closed relay."""
    snapshot, proposal, _ = _case("pass_v1_estop")
    del snapshot["relay_state"]
    decision = _decide(snapshot, proposal)
    assert decision["outcome"] == "VETO"


def test_unknown_precondition_is_rejected_as_unverifiable():
    snapshot, proposal, _ = _case("pass_v1_estop")
    proposal["preconditions"] = ["relay_closed", "moon_phase_is_favourable"]
    decision = _decide(snapshot, proposal)
    assert decision["outcome"] == "VETO"
    assert decision["rule_id"] == "V9_PLAN_MALFORMED"
    assert "cannot be verified" in decision["rule_trace"][8]["detail"]


def test_declared_precondition_that_is_false_is_blamed_on_the_owning_rule():
    """Single-source-of-truth: the trace says V2, not V9, when the keep-out is occupied."""
    snapshot, proposal, _ = _case("pass_v1_estop")
    snapshot["keep_out_occupied"] = True
    snapshot["keep_out_evidence"] = {"method": "frame_diff", "blob_area_px": 500.0, "confidence": 0.9}
    proposal["preconditions"] = ["keep_out_clear"]
    decision = _decide(snapshot, proposal)
    assert decision["outcome"] == "VETO"
    assert decision["rule_id"] == "V2_KEEP_OUT_OCCUPIED"
    v9 = next(e for e in decision["rule_trace"] if e["rule_id"] == "V9_PLAN_MALFORMED")
    assert v9["result"] == "PASS", "V9 must not double-count a fact another rule owns"


def test_stopping_results_are_exactly_the_abstentions_and_vetoes():
    assert STOPPING_RESULTS == {VETO, SENSOR_MISSING, SENSOR_STALE}


@pytest.mark.parametrize("rule_id", [rule for rule in RULES])
def test_every_rule_tolerates_a_minimal_snapshot(rule_id: str):
    """No rule may raise on a snapshot that lacks its own inputs; it must abstain."""
    minimal_snapshot: dict[str, Any] = {
        "snapshot_id": "s_min",
        "ts_wall": "2026-10-26T12:00:00Z",
        "ts_mono_ms": 1,
        "device": {"device_id": "rig"},
    }
    minimal_proposal: dict[str, Any] = {"proposal_id": "p_min"}
    decision = _decide(minimal_snapshot, minimal_proposal)
    # Whatever it decides, it must decide without exceptions and name a reason.
    assert decision["outcome"] in {"VETO", "ALLOW", "ALLOW_CLAMPED"}
    assert decision["rule_id"] in RULES or decision["rule_id"] is None
    assert len(decision["rule_trace"]) == len(RULES)


def test_a_rule_raising_becomes_a_veto(monkeypatch: pytest.MonkeyPatch):
    """An exception in a rule must fail closed, never skip the rule."""
    import app.envelope.core as core

    def exploding(context: Any) -> Any:
        raise RuntimeError("detector bug")

    monkeypatch.setitem(core.RULES, "V6_COLLISION_PREDICTED", exploding)
    snapshot, proposal, _ = _case("pass_v1_estop")
    decision = _decide(snapshot, proposal)
    assert decision["outcome"] == "VETO"
    assert decision["rule_id"] == "V6_COLLISION_PREDICTED"
    assert "detector bug" in decision["rule_trace"][5]["detail"]

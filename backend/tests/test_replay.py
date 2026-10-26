"""The replay lane, tested as arithmetic rather than as a story.

A replay that only ever agrees with the envelope is a decoration. These tests pin the
properties that make it evidence:

* the two arms differ **only** in which action is executed;
* a vetoed plan really does not move;
* the counterfactual is the planner's own number, not a softened version of it;
* replay is deterministic (same record -> same trajectory hash) and honest about what a
  2-D swept-volume model cannot see.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.contracts import is_valid
from app.envelope import evaluate, load_ruleset
from app.replay import compare, simulate

FIXTURES = Path(__file__).resolve().parents[2] / "data" / "fixtures" / "snapshots"


@pytest.fixture(scope="module")
def world():
    ruleset = load_ruleset()
    bounds = ruleset.policy.mapping("V5_WORKSPACE_BOUND", "allowed_volume")
    return ruleset, bounds


def _decision(name: str) -> dict[str, Any]:
    case = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    return evaluate(load_ruleset(), case["snapshot"], case["proposal"], case["requested_mode"])


def test_every_replay_record_is_contract_valid(world):
    ruleset, bounds = world
    for path in sorted(FIXTURES.glob("*.json")):
        decision = _decision(path.stem)
        for arm in ("envelope_off", "envelope_on"):
            record = simulate(decision, arm, rig=ruleset.rig, bounds=bounds, max_velocity_mm_s=60.0)
            assert is_valid("ReplayResult", record), (path.stem, arm, record["outcome"])
            assert record["decision_id"] == decision["decision_id"]
            assert record["replay_id"].startswith("rp_")


def test_the_two_arms_differ_only_in_the_action(world):
    """Same scene, same simulator, same seed: only the action changes."""
    ruleset, bounds = world
    decision = _decision("veto_v5_bound")
    off = simulate(decision, "envelope_off", rig=ruleset.rig, bounds=bounds, max_velocity_mm_s=60.0)
    on = simulate(decision, "envelope_on", rig=ruleset.rig, bounds=bounds, max_velocity_mm_s=60.0)

    for key in ("decision_id", "simulator", "sim_version", "ran_at", "seed"):
        assert off[key] == on[key], key
    assert off["outcome"] != on["outcome"], "a clamp that changes nothing proves nothing"


def test_a_vetoed_plan_does_not_move(world):
    ruleset, bounds = world
    decision = _decision("veto_v2_keepout")
    on = simulate(decision, "envelope_on", rig=ruleset.rig, bounds=bounds, max_velocity_mm_s=60.0)
    assert on["outcome"] == "completed"
    assert on["metrics"]["distance_mm"] == 0.0
    assert len(on["trajectory_points"]) == 1, "a stationary arm has a single point"


def test_the_counterfactual_uses_the_planners_own_number(world):
    """arm=off must not inherit the envelope's clamp, or the comparison is rigged."""
    ruleset, bounds = world
    decision = _decision("pass_v3_velocity")  # 60 mm/s requested, legal in normal mode
    off = simulate(decision, "envelope_off", rig=ruleset.rig, bounds=bounds, max_velocity_mm_s=60.0)
    on = simulate(decision, "envelope_on", rig=ruleset.rig, bounds=bounds, max_velocity_mm_s=60.0)
    assert off["metrics"]["duration_ms"] == on["metrics"]["duration_ms"]

    clamped = _decision("veto_v3_velocity")  # same geometry, degraded ceiling of 24 mm/s
    fast = simulate(clamped, "envelope_off", rig=ruleset.rig, bounds=bounds, max_velocity_mm_s=24.0)
    slow = simulate(clamped, "envelope_on", rig=ruleset.rig, bounds=bounds, max_velocity_mm_s=24.0)
    assert fast["metrics"]["duration_ms"] < slow["metrics"]["duration_ms"], (
        "off must be the faster, unclamped arm"
    )


@pytest.mark.parametrize("name", ["veto_v2_keepout", "veto_v5_bound", "veto_v6_collision"])
def test_geometric_counterfactuals_exist_for_the_spatial_rules(world, name):
    """If these stop being prevented, either the envelope changed or the fixture did."""
    ruleset, bounds = world
    comparison = compare(_decision(name), ruleset.rig, bounds, 60.0)
    assert comparison["collision_prevented"] is True
    assert comparison["envelope_off"]["outcome"] in {"collided", "out_of_bounds"}
    assert comparison["envelope_on"]["outcome"] == "completed"


@pytest.mark.parametrize("name", ["veto_v4_force", "veto_v7_stale", "veto_v9_malformed", "veto_v10_human"])
def test_non_spatial_rules_admit_no_geometric_counterfactual(world, name):
    """The report must not pretend the simulator proved something it cannot see."""
    ruleset, bounds = world
    comparison = compare(_decision(name), ruleset.rig, bounds, 60.0)
    assert comparison["collision_prevented"] is False
    assert comparison["geometry_check"] is False


def test_replay_is_deterministic(world):
    ruleset, bounds = world
    decision = _decision("veto_v6_collision")
    first = simulate(decision, "envelope_off", rig=ruleset.rig, bounds=bounds, max_velocity_mm_s=60.0)
    second = simulate(decision, "envelope_off", rig=ruleset.rig, bounds=bounds, max_velocity_mm_s=60.0)
    assert first == second


def test_replay_timestamp_comes_from_the_record(world):
    """No clock is read during replay, so a re-run a year later produces the same bytes."""
    ruleset, bounds = world
    decision = _decision("pass_v1_estop")
    record = simulate(decision, "envelope_off", rig=ruleset.rig, bounds=bounds, max_velocity_mm_s=60.0)
    assert record["ran_at"] == decision["decided_at"]


def test_a_keep_out_volume_is_only_an_obstacle_when_occupied(world):
    """Otherwise every legitimate move inside the cell would replay as a collision."""
    ruleset, bounds = world
    clear = _decision("pass_v1_estop")
    occupied = _decision("veto_v2_keepout")
    assert clear["sensor_snapshot_inline"]["keep_out_occupied"] is False
    assert occupied["sensor_snapshot_inline"]["keep_out_occupied"] is True

    clear_off = simulate(clear, "envelope_off", rig=ruleset.rig, bounds=bounds, max_velocity_mm_s=60.0)
    occupied_off = simulate(occupied, "envelope_off", rig=ruleset.rig, bounds=bounds, max_velocity_mm_s=60.0)
    assert clear_off["outcome"] == "completed"
    assert occupied_off["outcome"] == "collided"


def test_an_untyped_payload_is_still_replayed_as_an_action(world):
    """A malformed plan is still a plan; the counterfactual must not become 'nothing happened'."""
    ruleset, bounds = world
    snapshot = json.loads((FIXTURES / "pass_v1_estop.json").read_text(encoding="utf-8"))["snapshot"]
    decision = evaluate(load_ruleset(), snapshot, {"proposal_id": 7}, "normal")
    assert decision["intended_action"] is None
    assert decision["intended_action_raw"] == {"proposal_id": 7}
    off = simulate(decision, "envelope_off", rig=ruleset.rig, bounds=bounds, max_velocity_mm_s=60.0)
    assert off["outcome"] == "completed"  # no target => no motion, and that is reported honestly


def test_a_collision_under_the_envelope_is_reportable(world):
    """The inverse safety property: replay must be able to tell you the envelope failed."""
    ruleset, bounds = world
    decision = _decision("pass_v1_estop")
    # Force the shipped action to drive into the occupied keep-out volume.
    decision["sensor_snapshot_inline"]["keep_out_occupied"] = True
    decision["shipped_action"] = dict(
        decision["shipped_action"], target_pose={"x": 300.0, "y": 0.0, "z": 40.0}
    )
    record = simulate(decision, "envelope_on", rig=ruleset.rig, bounds=bounds, max_velocity_mm_s=60.0)
    assert record["outcome"] == "collided"
    assert record["collision"]["with"] == "keep_out_volume"
    assert is_valid("ReplayResult", record)


def test_unknown_arm_is_a_programming_error(world):
    ruleset, bounds = world
    with pytest.raises(ValueError, match="unknown arm"):
        simulate(_decision("pass_v1_estop"), "envelope_maybe", rig=ruleset.rig, bounds=bounds)

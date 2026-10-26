#!/usr/bin/env python3
"""Generate the envelope fixture corpus and verify it against the implementation.

Every rule gets **two** fixtures, because a rule that fires on clean input is a false
positive and a rule that never fires is decoration:

* ``veto_vN_*.json`` — the trigger, just past the threshold
* ``pass_vN_*.json`` — the same scenario just *below* the threshold

The files are plain JSON and are committed; this script exists so the twenty cases stay
mutually consistent (one shared baseline, one mutation each) instead of drifting apart.
Running it is deterministic: same bytes in, same bytes out.

The script also evaluates every case through the real envelope and fails if the recorded
``expect`` block disagrees with the implementation — so the fixtures are a specification,
not a snapshot of whatever the code happens to do.

Usage:
    python scripts/make_fixtures.py            # write and verify
    python scripts/make_fixtures.py --check    # verify only, do not write
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "data" / "fixtures" / "snapshots"
sys.path.insert(0, str(REPO / "backend"))

TS_WALL = "2026-10-26T12:00:00Z"

BASE_SNAPSHOT: dict[str, Any] = {
    "snapshot_id": "s_0001",
    "ts_mono_ms": 123456,
    "ts_wall": TS_WALL,
    "camera": {"frame_sha256": "0" * 64, "frame_idx": 42, "age_ms": 33.0, "fps_measured": 30.0},
    "end_effector": {
        "x": 10.0,
        "y": 0.0,
        "z": 40.0,
        "encoder_raw": 1024,
        "age_ms": 5.0,
        "velocity_mm_s": 0.0,
    },
    "limit_switches": {"min": False, "max": False, "age_ms": 5.0},
    "keep_out_occupied": False,
    "keep_out_evidence": {
        "method": "frame_diff",
        "blob_area_px": 0.0,
        "confidence": 0.99,
        "witnesses_agreeing": ["frame_diff"],
    },
    "intruder_present": False,
    "human_presence_detected": False,
    "force_estimate": 2.0,
    "force_estimate_method": "stall_current",
    "relay_state": True,
    "e_stop_asserted": False,
    "network": {"cloud_reachable": True, "last_cloud_ok_ms_ago": 12.0, "rtt_ms_p99": 80.0},
    "device": {
        "device_id": "sim-rig-01",
        "temp_c": 41.0,
        "cpu_pct": 12.0,
        "mem_pct": 30.0,
        "firmware_version": "0.1.0",
    },
}

BASE_PROPOSAL: dict[str, Any] = {
    "proposal_id": "p_0001",
    "plan_id": "plan_0001",
    "kind": "move_to",
    "target_pose": {"x": 200.0, "y": 0.0, "z": 40.0, "frame": "world"},
    "velocity_limit": 40.0,
    "force_limit": 8.0,
    "preconditions": ["relay_closed", "keep_out_clear"],
    "expected_end_state": {"block": "at_target"},
    "source": "cloud_ultra",
    "issued_at": "2026-10-26T11:59:59.900Z",
    "ttl_ms": 500,
    "signature": None,
    "is_noop": False,
}


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


# (case_id, description, expects, requested_mode, {"snapshot": {...}, "proposal": {...}})
CASES: list[tuple[str, str, dict[str, Any], str, dict[str, Any]]] = [
    # ------------------------------------------------------------------ triggers
    (
        "veto_v1_estop",
        "V1: e-stop asserted. The interlock outranks every other rule and there is nothing to compute.",
        {"outcome": "VETO", "rule_id": "V1_EMERGENCY_STOP"},
        "normal",
        {"snapshot": {"e_stop_asserted": True}},
    ),
    (
        "veto_v2_keepout",
        "V2: the intruder block is inside the marked keep-out volume, reported by two agreeing witnesses.",
        {"outcome": "VETO", "rule_id": "V2_KEEP_OUT_OCCUPIED"},
        "normal",
        {
            "snapshot": {
                "keep_out_occupied": True,
                "keep_out_evidence": {
                    "method": "frame_diff",
                    "blob_area_px": 900.0,
                    "confidence": 0.87,
                    "witnesses_agreeing": ["frame_diff", "depth"],
                },
            }
        },
    ),
    (
        "veto_v3_velocity",
        "V3: the operator put the cell in degraded mode, whose velocity ceiling is 24 mm/s. "
        "A 40 mm/s command is clamped, not refused - a partial refusal, recorded with its before/after.",
        {"outcome": "ALLOW_CLAMPED", "rule_id": "V3_VELOCITY_LIMIT", "clamp_velocity": [40.0, 24.0]},
        "degraded",
        {},
    ),
    (
        "veto_v4_force",
        "V4: the stall-current force estimate is above the 12 N limit.",
        {"outcome": "VETO", "rule_id": "V4_FORCE_LIMIT"},
        "normal",
        {"snapshot": {"force_estimate": 20.0}},
    ),
    (
        "veto_v5_bound",
        "V5: the commanded pose is beyond the allowed volume, so the target is clamped to the boundary.",
        {"outcome": "ALLOW_CLAMPED", "rule_id": "V5_WORKSPACE_BOUND", "clamp_x": 375.0},
        "normal",
        {"proposal": {"target_pose": {"x": 500.0}}},
    ),
    (
        "veto_v6_collision",
        "V6: an advisory perception pose sits inside the swept corridor of the commanded move. "
        "Advisory data may stop the machine; it may never restart it.",
        {"outcome": "VETO", "rule_id": "V6_COLLISION_PREDICTED"},
        "normal",
        {
            "snapshot": {
                "advisory_perception": {
                    "scene_description": "block on the rail, second block inside the corridor",
                    "object_poses": [
                        {"id": "intruder_block", "x": 150.0, "y": 0.0, "z": 40.0, "radius_mm": 20.0}
                    ],
                    "anomaly_flags": ["unexpected_object"],
                    "claims_workspace_clear": True,
                    "model": "nvidia/cosmos-reason-2",
                }
            }
        },
    ),
    (
        "veto_v7_stale",
        "V7: the camera frame is 500 ms old, well past the 100 ms freshness window.",
        {"outcome": "VETO", "rule_id": "V7_SENSOR_STALE"},
        "normal",
        {"snapshot": {"camera": {"age_ms": 500.0}}},
    ),
    (
        "veto_v8_network",
        "V8: the cloud has been unreachable for 5 s. Nothing stops; the command is evaluated against the "
        "stricter (degraded) parameter set. mode is 'simulation' because the active calibration profile is "
        "synthetic - that is the honesty rule, not an accident, and it is asserted in "
        "tests/test_network_outage.py that a MEASURED profile reports mode=degraded instead.",
        {"outcome": "ALLOW", "rule_id": None, "mode": "simulation", "parameter_set": "degraded"},
        "normal",
        {
            "snapshot": {"network": {"cloud_reachable": False, "last_cloud_ok_ms_ago": 5000.0}},
            "proposal": {"velocity_limit": 20.0},
        },
    ),
    (
        "veto_v9_malformed",
        "V9: the proposal asks to live for 9 s, beyond the envelope's 5 s TTL ceiling. "
        "A stale proposal describes a world that no longer exists.",
        {"outcome": "VETO", "rule_id": "V9_PLAN_MALFORMED"},
        "normal",
        {"proposal": {"ttl_ms": 9000}},
    ),
    (
        "veto_v10_human",
        "V10: human presence reported in the cell.",
        {"outcome": "VETO", "rule_id": "V10_HUMAN_PRESENCE"},
        "normal",
        {"snapshot": {"human_presence_detected": True}},
    ),
    # ------------------------------------------------------------------ near misses
    (
        "pass_v1_estop",
        "V1 negative: relay closed and e-stop released. Baseline.",
        {"outcome": "ALLOW", "rule_id": None},
        "normal",
        {},
    ),
    (
        "pass_v2_keepout",
        "V2 negative: the keep-out volume is clear and a working detector says so.",
        {"outcome": "ALLOW", "rule_id": None},
        "normal",
        {},
    ),
    (
        "pass_v3_velocity",
        "V3 negative: the command sits exactly ON the 60 mm/s ceiling. The rule must be 'greater than', "
        "not 'greater or equal', or every plan at the limit is silently slowed.",
        {"outcome": "ALLOW", "rule_id": None},
        "normal",
        {"proposal": {"velocity_limit": 60.0}},
    ),
    (
        "pass_v4_force",
        "V4 negative: 11.9 N against a 12 N limit.",
        {"outcome": "ALLOW", "rule_id": None},
        "normal",
        {"snapshot": {"force_estimate": 11.9}},
    ),
    (
        "pass_v5_bound",
        "V5 negative: the target sits exactly on the inset boundary, which is reachable.",
        {"outcome": "ALLOW", "rule_id": None},
        "normal",
        {"proposal": {"target_pose": {"x": 375.0}}},
    ),
    (
        "pass_v6_collision",
        "V6 negative: an object exists but is 200 mm off the rail, far outside the corridor.",
        {"outcome": "ALLOW", "rule_id": None},
        "normal",
        {
            "snapshot": {
                "advisory_perception": {
                    "object_poses": [
                        {"id": "far_block", "x": 150.0, "y": 200.0, "z": 40.0, "radius_mm": 20.0}
                    ],
                    "claims_workspace_clear": True,
                }
            }
        },
    ),
    (
        "pass_v7_stale",
        "V7 negative: 99 ms against a 100 ms window.",
        {"outcome": "ALLOW", "rule_id": None},
        "normal",
        {"snapshot": {"camera": {"age_ms": 99.0}}},
    ),
    (
        "pass_v8_network",
        "V8 negative: the last successful cloud call was 4 s ago but the cloud is reachable now, "
        "so no degradation. Reachability, not staleness of the last call, is the trigger.",
        {"outcome": "ALLOW", "rule_id": None, "mode": "simulation", "parameter_set": "normal"},
        "normal",
        {"snapshot": {"network": {"cloud_reachable": True, "last_cloud_ok_ms_ago": 4000.0}}},
    ),
    (
        "pass_v9_malformed",
        "V9 negative: issued 4 s ago with a 5 s TTL - the oldest still-valid proposal.",
        {"outcome": "ALLOW", "rule_id": None},
        "normal",
        {"proposal": {"issued_at": "2026-10-26T11:59:56.000Z", "ttl_ms": 5000}},
    ),
    (
        "pass_v10_human",
        "V10 negative: no human, no intruder.",
        {"outcome": "ALLOW", "rule_id": None},
        "normal",
        {},
    ),
]


def build_case(case: tuple[str, str, dict[str, Any], str, dict[str, Any]]) -> dict[str, Any]:
    case_id, description, expect, requested_mode, patch = case
    return {
        "case_id": case_id,
        "description": description,
        "requested_mode": requested_mode,
        "expect": expect,
        "snapshot": _deep_merge(BASE_SNAPSHOT, patch.get("snapshot", {})),
        "proposal": _deep_merge(BASE_PROPOSAL, patch.get("proposal", {})),
    }


def verify(cases: list[dict[str, Any]]) -> list[str]:
    """Evaluate every case through the real envelope and compare with its expectation."""
    from app.contracts import validate_payload
    from app.envelope import evaluate, load_ruleset

    problems: list[str] = []
    ruleset = load_ruleset()
    for case in cases:
        case_id = case["case_id"]
        validate_payload("SensorSnapshot", case["snapshot"])
        validate_payload("ActionProposal", case["proposal"])
        decision = evaluate(ruleset, case["snapshot"], case["proposal"], case["requested_mode"])
        validate_payload("EnvelopeDecision", decision)

        expect = case["expect"]
        if decision["outcome"] != expect["outcome"]:
            problems.append(f"{case_id}: expected outcome {expect['outcome']}, got {decision['outcome']}")
        if decision["rule_id"] != expect.get("rule_id"):
            problems.append(f"{case_id}: expected rule {expect.get('rule_id')}, got {decision['rule_id']}")
        if "mode" in expect and decision["mode"] != expect["mode"]:
            problems.append(f"{case_id}: expected mode {expect['mode']}, got {decision['mode']}")
        if "parameter_set" in expect:
            used = {entry.get("parameter_set_used") for entry in decision["rule_trace"]}
            if used != {expect["parameter_set"]}:
                problems.append(
                    f"{case_id}: expected parameter set {expect['parameter_set']}, got {sorted(used)}"
                )
        if "clamp_velocity" in expect:
            applied = (decision.get("clamp_applied") or {}).get("velocity")
            if applied != expect["clamp_velocity"]:
                problems.append(
                    f"{case_id}: expected clamp velocity {expect['clamp_velocity']}, got {applied}"
                )
        if "clamp_x" in expect:
            after = ((decision.get("clamp_applied") or {}).get("target_pose") or {}).get("after") or {}
            if after.get("x") != expect["clamp_x"]:
                problems.append(f"{case_id}: expected clamped x {expect['clamp_x']}, got {after.get('x')}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--check", action="store_true", help="verify without writing")
    args = parser.parse_args(argv)

    cases = [build_case(case) for case in CASES]
    if not args.check:
        OUT.mkdir(parents=True, exist_ok=True)
        for case in cases:
            path = OUT / f"{case['case_id']}.json"
            path.write_text(json.dumps(case, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {len(cases)} fixtures to {OUT.relative_to(REPO)}")

    problems = verify(cases)
    if problems:
        print(f"FAIL - {len(problems)} fixture(s) disagree with the implementation:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    print(f"PASS - {len(cases)} fixtures match the implementation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

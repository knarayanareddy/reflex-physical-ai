"""Shared builders for contract-valid instances.

Every builder returns the *canonical valid* shape; tests then mutate one field to
prove a law is enforced. Keeping the builders next to the contract means a schema
change breaks one file, not twenty tests.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "schemas" / "core-schemas.json"
TAXONOMY_PATH = REPO_ROOT / "data" / "veto-taxonomy.json"

_SCHEMA: dict[str, Any] = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def schema() -> dict[str, Any]:
    return _SCHEMA


def validate(defname: str, instance: object) -> None:
    """Validate ``instance`` against ``$defs/<defname>``; raise on failure."""
    validator = Draft202012Validator(
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$ref": f"#/$defs/{defname}",
            "$defs": _SCHEMA["$defs"],
        }
    )
    validator.validate(instance)


def errors_for(defname: str, instance: object) -> list[jsonschema.ValidationError]:
    validator = Draft202012Validator(
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$ref": f"#/$defs/{defname}",
            "$defs": _SCHEMA["$defs"],
        }
    )
    return sorted(validator.iter_errors(instance), key=lambda e: list(e.path))


# --------------------------------------------------------------------------- builders


def action_proposal(**overrides: Any) -> dict[str, Any]:
    proposal = {
        "proposal_id": "p_0001",
        "plan_id": "plan_0001",
        "kind": "push",
        "target_pose": {"x": 120.0, "y": 0.0, "z": 40.0, "frame": "world"},
        "velocity_limit": 80.0,
        "force_limit": 12.0,
        "preconditions": ["relay_closed", "keep_out_clear"],
        "expected_end_state": {"block": "at_target"},
        "source": "cloud_ultra",
        "issued_at": "2026-10-26T10:00:00Z",
        "ttl_ms": 2000,
        "signature": None,
        "is_noop": False,
    }
    proposal.update(overrides)
    return proposal


def sensor_snapshot(**overrides: Any) -> dict[str, Any]:
    snapshot = {
        "snapshot_id": "s_0001",
        "ts_mono_ms": 1000,
        "ts_wall": "2026-10-26T10:00:00Z",
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
        "keep_out_evidence": None,
        "intruder_present": False,
        "human_presence_detected": False,
        "force_estimate": 0.0,
        "force_estimate_method": "stall_current",
        "relay_state": True,
        "e_stop_asserted": False,
        "network": {"cloud_reachable": True, "last_cloud_ok_ms_ago": 12.0, "rtt_ms_p99": 80.0},
        "device": {
            "device_id": "jetson-orin-nano-01",
            "temp_c": 45.0,
            "cpu_pct": 12.0,
            "mem_pct": 30.0,
            "firmware_version": "0.1.0",
        },
    }
    snapshot.update(overrides)
    return snapshot


def _decision_base(**overrides: Any) -> dict[str, Any]:
    decision = {
        "decision_id": "d_0001",
        "proposal_id": "p_0001",
        "snapshot_id": "s_0001",
        "outcome": "VETO",
        "rule_id": "V2_KEEP_OUT_OCCUPIED",
        "rules_evaluated": ["V1_EMERGENCY_STOP", "V2_KEEP_OUT_OCCUPIED"],
        "rule_trace": [
            {"rule_id": "V1_EMERGENCY_STOP", "result": "PASS", "parameter_set_used": "normal"},
            {
                "rule_id": "V2_KEEP_OUT_OCCUPIED",
                "result": "VETO",
                "parameter_set_used": "normal",
                "detail": "intruder block inside keep-out volume",
            },
        ],
        "first_veto_index": 1,
        "intended_action": action_proposal(),
        "shipped_action": None,
        "clamp_applied": None,
        "mode": "normal",
        "parameter_set": "normal",
        "interlock_relay_opened": True,
        "latency_us": 320.0,
        "envelope_version": "sha256:" + "a" * 64,
        "determinism_hash": "b" * 64,
        "decided_at": "2026-10-26T10:00:00Z",
        "device_id": "jetson-orin-nano-01",
        "buffered_locally": False,
        "replayed": False,
        "sensor_snapshot_inline": sensor_snapshot(
            keep_out_occupied=True,
            keep_out_evidence={"method": "frame_diff", "blob_area_px": 512.0, "confidence": 0.91},
        ),
    }
    decision.update(overrides)
    return decision


def veto_decision(**overrides: Any) -> dict[str, Any]:
    """A canonical VETO: shipped_action is null, rule_id present, relay opened."""
    return _decision_base(**overrides)


def allow_decision(**overrides: Any) -> dict[str, Any]:
    base = dict(
        outcome="ALLOW",
        rule_id=None,
        rules_evaluated=["V1_EMERGENCY_STOP", "V2_KEEP_OUT_OCCUPIED"],
        rule_trace=[
            {"rule_id": "V1_EMERGENCY_STOP", "result": "PASS"},
            {"rule_id": "V2_KEEP_OUT_OCCUPIED", "result": "PASS"},
        ],
        first_veto_index=None,
        shipped_action=action_proposal(),
        clamp_applied=None,
        interlock_relay_opened=False,
    )
    base.update(overrides)
    return _decision_base(**base)


def clamped_decision(**overrides: Any) -> dict[str, Any]:
    base = dict(
        outcome="ALLOW_CLAMPED",
        rule_id="V3_VELOCITY_LIMIT",
        rules_evaluated=["V1_EMERGENCY_STOP", "V2_KEEP_OUT_OCCUPIED", "V3_VELOCITY_LIMIT"],
        rule_trace=[
            {"rule_id": "V1_EMERGENCY_STOP", "result": "PASS"},
            {"rule_id": "V2_KEEP_OUT_OCCUPIED", "result": "PASS"},
            {"rule_id": "V3_VELOCITY_LIMIT", "result": "CLAMP", "detail": "80 -> 32 mm/s"},
        ],
        first_veto_index=None,
        shipped_action=action_proposal(velocity_limit=32.0),
        clamp_applied={"velocity": [80.0, 32.0], "rule_id": "V3_VELOCITY_LIMIT"},
        interlock_relay_opened=False,
    )
    base.update(overrides)
    return _decision_base(**base)


def replay_result(**overrides: Any) -> dict[str, Any]:
    replay = {
        "replay_id": "rp_0001",
        "decision_id": "d_0001",
        "arm": "envelope_off",
        "simulator": "in-house swept-volume 2D",
        "sim_version": "0.1.0",
        "sandbox_image_uuid": None,
        "ran_at": "2026-10-26T10:05:00Z",
        "runner": "local_process",
        "seed": 1337,
        "outcome": "collided",
        "collision": {"with": "intruder_block", "at_t_ms": 412.0, "penetration_mm": 18.5},
        "trajectory_sha256": "c" * 64,
        "trajectory_points": None,
        "still_image_path": None,
        "cost": 0.0,
    }
    replay.update(overrides)
    return replay


def session_run(**overrides: Any) -> dict[str, Any]:
    run = {
        "run_id": "run_0001",
        "mode": "normal",
        "started_at": "2026-10-26T10:00:00Z",
        "ended_at": "2026-10-26T10:10:00Z",
        "device": "jetson-orin-nano-01",
        "hardware_tier": 3,
        "scenario": "repeated_intrusion",
        "counts": {
            "actions_planned": 120,
            "actions_allowed": 96,
            "actions_clamped": 12,
            "actions_vetoed": 12,
            "distinct_rules_exercised": 4,
        },
        "degraded_mode_entered": True,
        "network_outages": 1,
        "decisions_lost_during_outage": 0,
        "collisions_in_shipped": 0,
        "replay": {
            "vetoes_replayed": 12,
            "collisions_envelope_off": 9,
            "collisions_envelope_on": 0,
            "conservative_fraction": 0.25,
        },
        "cost_usd": 0.42,
        "latency": {
            "edge_envelope_us_p50": 210.0,
            "edge_envelope_us_p95": 480.0,
            "description_note": "edge and cloud measured separately",
        },
    }
    run.update(overrides)
    return run


def ledger_line(**overrides: Any) -> dict[str, Any]:
    line = {
        "id": "led_20261026T100000Z_deadbeef",
        "ts": "2026-10-26T10:00:00Z",
        "kind": "chat.completions",
        "stage": "plan",
        "model": "nvidia/Nemotron-3-Ultra-550b-a55b",
        "request": {"prompt_tokens": 1200, "completion_tokens": 300, "cached_tokens": 1024},
        "cost_usd": 0.0031,
        "latency_ms": 1840.5,
        "status": "ok",
        "notes": "synthetic fixture",
    }
    line.update(overrides)
    return line


def taxonomy_rule(rule_id: str = "V2_KEEP_OUT_OCCUPIED") -> dict[str, Any]:
    rules = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))["rules"]
    for rule in rules:
        if rule["rule_id"] == rule_id:
            return copy.deepcopy(rule)
    raise KeyError(rule_id)

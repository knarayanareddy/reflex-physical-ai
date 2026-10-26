"""Two-arm replay: what the veto prevented, reproduced as geometry.

A veto is only convincing if you can show the world it avoided. This module replays one
recorded ``EnvelopeDecision`` twice against the same static scene:

* **envelope_off** — the *intended* action, executed as the planner asked. No clamp, no
  refusal, no safety layer. This is the counterfactual.
* **envelope_on** — the *shipped* action, which is ``None`` when the envelope vetoed. A
  vetoed plan does not move.

Both arms run the same deterministic simulator on the same scene, so the difference between
the two outcomes is attributable to the envelope and nothing else.

Honest scope (also printed by the job): this is a **2D swept-volume** check in the x-y plane
at the end-effector's z. It models position, not contact dynamics, and it cannot model the
force, staleness or trust rules — for those the job reports "no geometric counterfactual"
rather than inventing one. ``docs/SIMULATOR-CHOICE.md`` records why an in-house swept-volume
model was chosen over a physics engine for this claim.

Determinism: no clock, no random numbers, no floating-point accumulation across iterations
beyond a fixed 2 mm sampling step. ``ran_at`` is the *decision's* timestamp, not the wall
clock, so a replay run twice produces byte-identical ``ReplayResult`` records.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping
from typing import Any

SIMULATOR = "in-house swept-volume 2D (x-y at end-effector z), 2 mm sampling"
SIM_VERSION = "0.1.0"
STEP_MM = 2.0
EE_RADIUS_MM = 12.0
DEFAULT_VELOCITY_MM_S = 40.0


def _digest(points: list[tuple[float, float, float]]) -> str:
    """Trajectory identity at 1 um / 0.001 ms resolution."""
    payload = ";".join(f"{x:.3f},{y:.3f},{t:.3f}" for x, y, t in points)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _scene(
    decision: Mapping[str, Any], rig: Mapping[str, Any], bounds: Mapping[str, Any] | None
) -> dict[str, Any]:
    """Build the scene from the recorded snapshot and the rig geometry.

    The keep-out volume is only an obstacle when the snapshot reports it **occupied**. It is
    a place a person may be, not a place the arm may never go — treating it as permanently
    forbidden would make every legitimate plan inside the cell a collision.
    """
    snapshot = decision.get("sensor_snapshot_inline") or {}
    start = snapshot.get("end_effector") or {}
    advisory = snapshot.get("advisory_perception") or {}

    obstacles: list[dict[str, Any]] = []
    for pose in advisory.get("object_poses") or []:
        if not isinstance(pose, Mapping):
            continue
        obstacles.append(
            {
                "name": str(pose.get("id") or "object"),
                "x": float(pose.get("x", 0.0)),
                "y": float(pose.get("y", 0.0)),
                "radius_mm": float(pose.get("radius_mm") or 0.0),
            }
        )

    keep_out = rig.get("keep_out_volume") if snapshot.get("keep_out_occupied") is True else None
    return {
        "start": {"x": float(start.get("x", 0.0)), "y": float(start.get("y", 0.0))},
        "obstacles": obstacles,
        "keep_out": keep_out,
        "bounds": bounds,
    }


def _inside_keep_out(x: float, y: float, keep_out: Mapping[str, Any] | None) -> bool:
    if not isinstance(keep_out, Mapping):
        return False
    x_range = keep_out.get("x") or [math.inf, -math.inf]
    y_range = keep_out.get("y") or [math.inf, -math.inf]
    return x_range[0] <= x <= x_range[1] and y_range[0] <= y <= y_range[1]


def _run_arm(
    action: Mapping[str, Any] | None,
    scene: Mapping[str, Any],
    max_velocity_mm_s: float,
) -> dict[str, Any]:
    """Move the end effector from its recorded pose to the action's target, or not at all."""
    points: list[tuple[float, float, float]] = []
    if action is None:
        # Nothing was shipped: the arm stays where the snapshot found it.
        start = scene["start"]
        points.append((start["x"], start["y"], 0.0))
        return {
            "outcome": "completed",
            "collision": None,
            "points": points,
            "duration_ms": 0.0,
            "distance_mm": 0.0,
            "clearance_mm": None,
            "reason": "the envelope shipped no action; the arm did not move",
        }

    target_pose = action.get("target_pose") or {}
    start = scene["start"]
    target = {"x": float(target_pose.get("x", start["x"])), "y": float(target_pose.get("y", start["y"]))}

    requested = action.get("velocity_limit")
    velocity = (
        float(requested) if isinstance(requested, (int, float)) and requested > 0 else DEFAULT_VELOCITY_MM_S
    )
    velocity = min(velocity, max_velocity_mm_s) if max_velocity_mm_s > 0 else velocity

    dx, dy = target["x"] - start["x"], target["y"] - start["y"]
    distance = math.hypot(dx, dy)
    steps = max(1, math.ceil(distance / STEP_MM))
    points.append((start["x"], start["y"], 0.0))

    clearance = math.inf
    for step in range(1, steps + 1):
        fraction = step / steps
        x = start["x"] + dx * fraction
        y = start["y"] + dy * fraction
        t_ms = (distance * fraction / velocity) * 1000.0 if velocity > 0 else 0.0
        points.append((x, y, t_ms))

        # Keep-out volume: entering it at all is the failure the envelope exists to prevent.
        if _inside_keep_out(x, y, scene.get("keep_out")):
            return {
                "outcome": "collided",
                "collision": {
                    "with": "keep_out_volume",
                    "at_t_ms": round(t_ms, 3),
                    "penetration_mm": None,
                    "contact_point": {"x": round(x, 3), "y": round(y, 3)},
                },
                "points": points,
                "duration_ms": t_ms,
                "distance_mm": distance * fraction,
                "clearance_mm": 0.0,
                "reason": "the intended path enters the keep-out volume",
            }

        # Bounds: leaving the allowed workspace is a failure even without a collision.
        bounds = scene.get("bounds")
        if isinstance(bounds, Mapping):
            if not (bounds["x"][0] <= x <= bounds["x"][1] and bounds["y"][0] <= y <= bounds["y"][1]):
                return {
                    "outcome": "out_of_bounds",
                    "collision": None,
                    "points": points,
                    "duration_ms": t_ms,
                    "distance_mm": distance * fraction,
                    "clearance_mm": None,
                    "reason": "the path leaves the allowed workspace",
                }

        # Obstacles: circle-vs-disc, inflated by the end-effector radius.
        for obstacle in scene["obstacles"]:
            gap = math.hypot(x - obstacle["x"], y - obstacle["y"]) - obstacle["radius_mm"] - EE_RADIUS_MM
            clearance = min(clearance, gap)
            if gap <= 0.0:
                return {
                    "outcome": "collided",
                    "collision": {
                        "with": obstacle["name"],
                        "at_t_ms": round(t_ms, 3),
                        "penetration_mm": round(-gap, 3),
                        "contact_point": {"x": round(x, 3), "y": round(y, 3)},
                    },
                    "points": points,
                    "duration_ms": t_ms,
                    "distance_mm": distance * fraction,
                    "clearance_mm": 0.0,
                    "reason": f"the path intersects {obstacle['name']}",
                }

    final_t = (distance / velocity) * 1000.0 if velocity > 0 else 0.0
    return {
        "outcome": "completed",
        "collision": None,
        "points": points,
        "duration_ms": final_t,
        "distance_mm": distance,
        "clearance_mm": None if clearance is math.inf else clearance,
        "reason": "reached the target without contact",
    }


def simulate(
    decision: Mapping[str, Any],
    arm: str,
    *,
    rig: Mapping[str, Any] | None = None,
    bounds: Mapping[str, Any] | None = None,
    max_velocity_mm_s: float = 0.0,
) -> dict[str, Any]:
    """Replay one recorded decision under one arm. Pure: same record, same result."""
    if arm not in {"envelope_on", "envelope_off"}:
        raise ValueError(f"unknown arm {arm!r}")
    scene = _scene(decision, rig or {}, bounds)

    # The two arms differ in exactly one respect: which action is executed.
    #   envelope_off -> the intended action, as the planner asked for it (untyped payloads
    #                   included, because an unsafe idea does not become safe when malformed)
    #   envelope_on  -> the shipped action; None after a veto, which means "did not move"
    if arm == "envelope_off":
        action = decision.get("intended_action") or decision.get("intended_action_raw")
        ceiling = 0.0  # no envelope, so no ceiling: the planner's number stands
    else:
        action = decision.get("shipped_action")
        ceiling = max_velocity_mm_s  # defence in depth: the mode's ceiling, even if the action drifted
    result = _run_arm(action if isinstance(action, Mapping) else None, scene, ceiling)

    replay_id = "rp_" + hashlib.sha256(f"{decision.get('decision_id')}:{arm}".encode()).hexdigest()[:16]
    return {
        "replay_id": replay_id,
        "decision_id": str(decision.get("decision_id")),
        "arm": arm,
        "simulator": SIMULATOR,
        "sim_version": SIM_VERSION,
        "sandbox_image_uuid": None,
        "sandbox_operation_id": None,
        "sandbox_branch": None,
        # The decision's own timestamp, so replaying twice yields identical bytes.
        "ran_at": decide_time(decision),
        "seed": 0,
        "outcome": result["outcome"],
        "collision": result["collision"],
        "trajectory_sha256": _digest(result["points"]),
        "trajectory_points": [[round(x, 3), round(y, 3), round(t, 3)] for x, y, t in result["points"]],
        "still_image_path": None,
        "metrics": {
            "distance_mm": round(result["distance_mm"], 3),
            "duration_ms": round(result["duration_ms"], 3),
            "clearance_mm": None if result["clearance_mm"] is None else round(result["clearance_mm"], 3),
            "notes": result["reason"],
        },
    }


def decide_time(decision: Mapping[str, Any]) -> str:
    """Replay timestamps come from the record, never from a clock."""
    value = decision.get("decided_at")
    if not isinstance(value, str) or not value:
        raise ValueError("decision has no decided_at; a replay needs a timestamp from its input")
    return value


def compare(
    decision: Mapping[str, Any],
    rig: Mapping[str, Any] | None = None,
    bounds: Mapping[str, Any] | None = None,
    max_velocity_mm_s: float = 0.0,
) -> dict[str, Any]:
    """Both arms plus the one-line verdict the dashboard shows."""
    off = simulate(decision, "envelope_off", rig=rig, bounds=bounds, max_velocity_mm_s=max_velocity_mm_s)
    on = simulate(decision, "envelope_on", rig=rig, bounds=bounds, max_velocity_mm_s=max_velocity_mm_s)
    prevented = off["outcome"] in {"collided", "out_of_bounds"} and on["outcome"] == "completed"
    return {
        "decision_id": decision.get("decision_id"),
        "rule_id": decision.get("rule_id"),
        "outcome": decision.get("outcome"),
        "envelope_off": off,
        "envelope_on": on,
        "collision_prevented": prevented,
        "geometry_check": off["outcome"] != "completed",
    }

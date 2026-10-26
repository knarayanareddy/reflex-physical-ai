#!/usr/bin/env python3
"""D-T20 — a 1,000-action operational session, replayed through both arms.

    python jobs/batch_1000_eval.py                 # the whole thing: session, replays, pack
    python jobs/batch_1000_eval.py --count 50      # a fast smoke run
    python jobs/batch_1000_eval.py --pack out/pack # decide where the sandbox pack lands

What this produces, and what it is worth:

* **1,000 proposed actions**, written to `runs/session/decisions.jsonl`. The session is
  scripted and **SYNTHETIC**: no hardware ran. It is deterministic — a fixed seed and a
  hand-rolled PRNG, so the same command produces the same bytes on any machine, and the
  session hash in the summary names exactly which 1,000 actions were evaluated.
* **every decision**, including the vetoes, recorded through `app.decision_ledger` — the
  same function the API uses, so the records are contract-validated, not just printed.
* **both replay arms per action** (`app.replay.compare`): what the planner asked for with no
  safety layer, and what actually shipped. `envelope_off` is the counterfactual.
* **`runs/headline_statistics.json`** — the numbers the dashboard bar shows.
* **a sandbox pack** (`runs/replay_pack/`) that can be verified with the network disabled.

The session is built from families rather than random noise, because a random walk would
exercise five rules by accident and none of them on purpose. Each family places the world in
a state that makes one rule the *reason* the action was refused or changed:

    nominal            nothing wrong                                   -> ALLOW
    obstacle            an object sits in the swept corridor           -> V6 VETO
    over-ceiling        the plan asks for more than the policy allows   -> V9 VETO
    keep-out traverse   a person stands in the keep-out volume          -> V2 VETO
    joint limit         the target is past the travel limit             -> V5 CLAMP
    human proximity     a human is in the cell                           -> V10 VETO
    force               the force estimate is over the limit            -> V4 VETO
    stale               the camera has stopped delivering               -> V7 VETO
    network             the cloud is unreachable                        -> V8 DEGRADE + V3 CLAMP
    malformed           the plan is untyped, expired or impossible      -> V9 VETO
    e-stop              the operator has hit the button                 -> V1 VETO

Honest scope. This is a 2-D swept-volume model at the recorded end-effector z. It cannot
model contact dynamics, and it cannot model the rules that stop the machine without a spatial
witness (force, staleness, malformed plans, presence without localisation) — those vetoes have
**no geometric counterfactual**, and the summary reports them by rule instead of counting them
as prevented. The generator keeps the motion single-axis, which is what the rig can actually
do; a diagonal move would be a different machine.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

from app.contracts import is_valid  # noqa: E402
from app.decision_ledger import record_decision  # noqa: E402
from app.envelope import envelope_version, evaluate, load_ruleset  # noqa: E402
from app.replay import compare  # noqa: E402
from app.sandbox.replay_pack import build_pack, scene_from_ruleset, verify_pack  # noqa: E402

SCHEMA = "reflex.headline_statistics/1"
DEFAULT_COUNT = 1000
DEFAULT_SEED = 20261026
DEFAULT_OUT = REPO / "runs" / "headline_statistics.json"
DEFAULT_SESSION_DIR = REPO / "runs" / "session"
DEFAULT_PACK_DIR = REPO / "runs" / "replay_pack"

#: The session starts at a fixed instant and advances 100 ms per action (10 Hz). A wall clock
#: here would make the file different on every run and the hash meaningless.
SESSION_START_MS = 1_760_000_000_000

#: `index % 100` -> family. Exact counts, no sampling noise: 1,000 actions is 450 nominal,
#: 120 keep-out traversals, and so on. A test pins the table so it cannot drift silently.
BUCKETS: tuple[tuple[int, str], ...] = (
    (45, "nominal"),
    (50, "obstacle"),
    (55, "over_ceiling"),
    (67, "keep_out"),
    (77, "joint_limit"),
    (85, "human"),
    (90, "force"),
    (94, "stale"),
    (97, "network"),
    (99, "malformed"),
    (100, "e_stop"),
)


class Lcg:
    """A 32-bit linear congruential generator.

    `random.Random` would be fine today, but its sequence is an implementation detail; an
    LCG is six lines of arithmetic that cannot change under a Python upgrade. Reproducibility
    is the point of the session, so the generator is the simplest thing that cannot surprise.
    """

    def __init__(self, seed: int) -> None:
        self.state = seed & 0xFFFFFFFF

    def next(self) -> float:
        self.state = (1664525 * self.state + 1013904223) & 0xFFFFFFFF
        return self.state / 0x1_0000_0000

    def between(self, low: float, high: float) -> float:
        return low + self.next() * (high - low)

    def integer(self, low: int, high: int) -> int:
        return low + int(self.next() * (high - low))


def family_for(index: int) -> str:
    bucket = index % 100
    for boundary, name in BUCKETS:
        if bucket < boundary:
            return name
    return BUCKETS[-1][1]


def _iso(ms: int) -> str:
    from datetime import UTC, datetime, timedelta

    moment = datetime(1970, 1, 1, tzinfo=UTC) + timedelta(milliseconds=ms)
    return moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{moment.microsecond // 1000:03d}Z"


def _snapshot(
    *,
    index: int,
    x: float,
    y: float,
    z: float,
    camera_age_ms: float = 33.0,
    encoder_age_ms: float = 5.0,
    keep_out_occupied: bool = False,
    human: bool = False,
    force_n: float = 2.0,
    relay_closed: bool = True,
    e_stop: bool = False,
    cloud_reachable: bool = True,
    last_cloud_ok_ms_ago: float = 12.0,
    obstacles: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """One contract-valid $defs/SensorSnapshot. Every field the rules read is explicit."""
    ts_ms = SESSION_START_MS + index * 100
    snapshot: dict[str, Any] = {
        "snapshot_id": f"s_{index:06d}",
        "ts_mono_ms": 1_000_000 + index * 100,
        "ts_wall": _iso(ts_ms),
        "camera": {
            "frame_sha256": hashlib.sha256(f"frame-{index}".encode()).hexdigest(),
            "frame_idx": 1000 + index,
            "age_ms": camera_age_ms,
            "fps_measured": 30.0,
        },
        "end_effector": {
            "x": round(x, 3),
            "y": round(y, 3),
            "z": round(z, 3),
            "encoder_raw": 1000 + index,
            "age_ms": encoder_age_ms,
            "velocity_mm_s": 0.0,
        },
        "limit_switches": {"min": False, "max": False, "age_ms": encoder_age_ms},
        "keep_out_occupied": keep_out_occupied,
        "keep_out_evidence": {
            "method": "frame_diff",
            "blob_area_px": 900.0 if keep_out_occupied else 0.0,
            "confidence": 0.91 if keep_out_occupied else 0.99,
            "witnesses_agreeing": ["frame_diff", "depth"] if keep_out_occupied else ["frame_diff"],
        },
        "intruder_present": False,
        "human_presence_detected": human,
        "force_estimate": round(force_n, 3),
        "force_estimate_method": "stall_current",
        "relay_state": relay_closed,
        "e_stop_asserted": e_stop,
        "network": {
            "cloud_reachable": cloud_reachable,
            "last_cloud_ok_ms_ago": last_cloud_ok_ms_ago,
            "rtt_ms_p99": None if not cloud_reachable else 80.0,
        },
        "device": {
            "device_id": "sim-rig-01",
            "temp_c": 41.0,
            "cpu_pct": 12.0,
            "mem_pct": 30.0,
            "firmware_version": "0.1.0",
        },
        "advisory_perception": {
            "scene_description": "synthetic session frame",
            "object_poses": obstacles or [],
            "anomaly_flags": [],
            "claims_workspace_clear": False,
            "model": None,
            "ledger_id": None,
        },
    }
    return snapshot


def _proposal(
    *,
    index: int,
    issued_at: str,
    target: dict[str, float] | None,
    velocity: float,
    force: float = 8.0,
    ttl_ms: int = 500,
    kind: str = "move_to",
) -> dict[str, Any]:
    proposal: dict[str, Any] = {
        "proposal_id": f"p_{index:06d}",
        "plan_id": f"plan_{index // 10:05d}",
        "kind": kind,
        "velocity_limit": round(velocity, 3),
        "force_limit": force,
        "preconditions": [],
        "expected_end_state": {"block": "at_target"},
        "source": "cloud_ultra",
        "issued_at": issued_at,
        "ttl_ms": ttl_ms,
        "signature": None,
        "is_noop": False,
    }
    if target is not None:
        proposal["target_pose"] = {
            "x": round(target["x"], 3),
            "y": round(target["y"], 3),
            "z": round(target["z"], 3),
            "frame": "world",
        }
    return proposal


def _action(index: int, rng: Lcg) -> dict[str, Any]:
    """One proposed action plus the world it was proposed in."""
    family = family_for(index)
    ts_ms = SESSION_START_MS + index * 100
    issued_at = _iso(ts_ms - 50)

    x0 = rng.between(20.0, 130.0)  # always left of the keep-out volume (x >= 150)
    y0 = rng.between(-12.0, 12.0)
    z0 = 40.0
    camera_age = rng.between(20.0, 80.0)
    encoder_age = rng.between(2.0, 20.0)
    force_n = rng.between(1.5, 5.5)

    # Inside the allowed workspace, left of the keep-out: the safe target for every family
    # that is testning a rule other than geometry.
    safe_x = rng.between(30.0, 140.0)
    velocity = rng.between(30.0, 55.0)

    snapshot = _snapshot(
        index=index,
        x=x0,
        y=y0,
        z=z0,
        camera_age_ms=camera_age,
        encoder_age_ms=encoder_age,
        force_n=force_n,
    )
    target: dict[str, float] | None = {"x": safe_x, "y": y0, "z": z0}
    proposal_velocity = velocity
    kind = "move_to"
    ttl_ms = 500

    if family == "obstacle":
        # An object in the swept corridor: V6 must refuse the move.
        mid = (x0 + safe_x) / 2.0
        snapshot["advisory_perception"]["object_poses"] = [
            {
                "id": f"pallet_{index % 17}",
                "x": round(mid, 3),
                "y": round(y0, 3),
                "z": round(z0, 3),
                "radius_mm": round(rng.between(15.0, 35.0), 3),
            }
        ]
    elif family == "over_ceiling":
        # Asking for more than the policy allows is a malformed plan, not a clamp: V9.
        proposal_velocity = rng.between(70.0, 120.0)
    elif family == "keep_out":
        # A person inside the marked volume, and a target beyond it: the intended path would
        # drive straight through. V2 refuses; the replay's OFF arm collides at x = 150.
        snapshot["keep_out_occupied"] = True
        target = {"x": rng.between(170.0, 360.0), "y": y0, "z": z0}
    elif family == "joint_limit":
        corner = (index // 7) % 4
        if corner == 0:
            target = {"x": rng.between(-20.0, 9.0), "y": y0, "z": z0}  # before the rail start
        elif corner == 1:
            target = {"x": rng.between(381.0, 410.0), "y": y0, "z": z0}  # past the rail end
        elif corner == 2:
            # Absolute, not relative to the start pose: `y0 + 26` can land back inside the
            # ±25 mm workspace when y0 is negative, which would make this a legal move and
            # silently stop testing the boundary it was built to test.
            side = 1.0 if index % 2 else -1.0
            target = {"x": safe_x, "y": side * rng.between(26.0, 40.0), "z": z0}
        else:
            target = {"x": safe_x, "y": y0, "z": rng.between(5.0, 14.0)}  # outside z
    elif family == "human":
        snapshot["human_presence_detected"] = True
    elif family == "force":
        snapshot["force_estimate"] = round(rng.between(15.0, 35.0), 3)
    elif family == "stale":
        if index % 2:
            snapshot["camera"]["age_ms"] = rng.between(150.0, 900.0)
        else:
            snapshot["end_effector"]["age_ms"] = rng.between(60.0, 200.0)
            snapshot["limit_switches"]["age_ms"] = snapshot["end_effector"]["age_ms"]
    elif family == "network":
        snapshot["network"] = {
            "cloud_reachable": False,
            "last_cloud_ok_ms_ago": rng.between(5000.0, 20000.0),
            "rtt_ms_p99": None,
        }
        # A fresh camera on purpose: the point of this family is the degraded parameter set,
        # and degraded halves the staleness window to 50 ms. Leaving the age in the 20-80 ms
        # range would make V7 the reason for roughly half the refusals and hide V8 behind it.
        snapshot["camera"]["age_ms"] = round(rng.between(8.0, 30.0), 3)
        snapshot["end_effector"]["age_ms"] = round(rng.between(2.0, 15.0), 3)
        snapshot["limit_switches"]["age_ms"] = snapshot["end_effector"]["age_ms"]
    elif family == "malformed":
        shape = index % 3
        if shape == 0:
            target = None  # no target_pose at all
        elif shape == 1:
            issued_at = _iso(ts_ms - 10_000)  # expired long before it was sent
        else:
            kind = "teleport"  # not in $defs/ActionProposal.kind
    elif family == "e_stop":
        snapshot["e_stop_asserted"] = True
        snapshot["relay_state"] = False

    proposal = _proposal(
        index=index,
        issued_at=issued_at,
        target=target,
        velocity=proposal_velocity,
        ttl_ms=ttl_ms,
        kind=kind,
    )
    return {
        "index": index,
        "family": family,
        "snapshot": snapshot,
        "proposal": proposal,
        "requested_mode": "normal",
    }


def generate_session(count: int = DEFAULT_COUNT, seed: int = DEFAULT_SEED) -> list[dict[str, Any]]:
    """The whole session, before a single decision is made. Pure and deterministic."""
    rng = Lcg(seed)
    return [_action(index, rng) for index in range(count)]


def run_session(
    actions: list[dict[str, Any]],
    *,
    ruleset: Any,
    ledger_path: Path,
    replay_path: Path,
) -> dict[str, Any]:
    """Evaluate and replay every action, writing both logs. Returns the aggregates."""
    from app.replay import simulate

    bounds = ruleset.policy.mapping("V5_WORKSPACE_BOUND", "allowed_volume")
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.unlink(missing_ok=True)
    replay_path.unlink(missing_ok=True)

    outcomes: dict[str, int] = {}
    vetoes_by_rule: dict[str, int] = {}
    family_counts: dict[str, int] = {}
    prevented_total = 0
    prevented_collisions = 0
    prevented_excursions = 0
    prevented_by_rule: dict[str, int] = {}
    no_counterfactual: dict[str, int] = {}
    shipped_collisions = 0
    shipped_excursions = 0
    decision_ids: list[str] = []
    decisions: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []

    with replay_path.open("w", encoding="utf-8") as replay_file:
        for action in actions:
            decision = evaluate(
                ruleset, action["snapshot"], action["proposal"], action["requested_mode"]
            )
            decisions.append(record_decision(decision, ledger_path))
            decision_ids.append(decision["decision_id"])

            family_counts[action["family"]] = family_counts.get(action["family"], 0) + 1
            outcomes[decision["outcome"]] = outcomes.get(decision["outcome"], 0) + 1
            if decision["outcome"] == "VETO":
                rule = decision["rule_id"] or "?"
                vetoes_by_rule[rule] = vetoes_by_rule.get(rule, 0) + 1

            ceiling = ruleset.params_for(decision["parameter_set"]).number(
                "V3_VELOCITY_LIMIT", "max_velocity_mm_s"
            )
            comparison = compare(decision, ruleset.rig, bounds, ceiling)

            off, on = comparison["envelope_off"], comparison["envelope_on"]
            if on["outcome"] == "collided":
                shipped_collisions += 1
            if on["outcome"] == "out_of_bounds":
                shipped_excursions += 1

            if comparison["collision_prevented"]:
                prevented_total += 1
                if off["outcome"] == "collided":
                    prevented_collisions += 1
                else:
                    prevented_excursions += 1
                rule = decision["rule_id"] or "?"
                prevented_by_rule[rule] = prevented_by_rule.get(rule, 0) + 1
            elif decision["outcome"] in {"VETO", "ALLOW_CLAMPED"}:
                # A refusal or a clamp that the 2-D model cannot show a witness for. Counted
                # separately, never folded into "prevented".
                rule = decision["rule_id"] or "?"
                no_counterfactual[rule] = no_counterfactual.get(rule, 0) + 1

            for arm in ("envelope_off", "envelope_on"):
                replay_file.write(json.dumps(comparison[arm], sort_keys=True) + "\n")
                records.append(comparison[arm])

    return {
        "outcomes": outcomes,
        "vetoes_by_rule": vetoes_by_rule,
        "family_counts": family_counts,
        "prevented_total": prevented_total,
        "prevented_collisions": prevented_collisions,
        "prevented_excursions": prevented_excursions,
        "prevented_by_rule": prevented_by_rule,
        "no_counterfactual": no_counterfactual,
        "shipped_collisions": shipped_collisions,
        "shipped_excursions": shipped_excursions,
        "session_sha256": hashlib.sha256("\n".join(decision_ids).encode()).hexdigest(),
        "decision_ids": decision_ids,
        # Consumed by the pack builder; not part of the headline JSON.
        "decisions": decisions,
        "records": records,
    }


def headline_report(
    aggregates: dict[str, Any],
    *,
    ruleset: Any,
    count: int,
    seed: int,
    elapsed_ms: float,
    pack: dict[str, Any] | None,
    pack_verification: dict[str, Any] | None,
) -> dict[str, Any]:
    """The JSON the dashboard bar reads. Every number here is computed above, none asserted."""
    vetoes = aggregates["vetoes_by_rule"]
    total_vetoes = sum(vetoes.values())
    report: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_by": "jobs/batch_1000_eval.py",
        "source": "SYNTHETIC — a scripted session. No hardware ran; no model was called.",
        "session": {
            "seed": seed,
            "actions": count,
            "families": dict(sorted(aggregates["family_counts"].items())),
            "sha256": aggregates["session_sha256"],
            "cadence_hz": 10,
        },
        "headline": {
            "actions_planned": count,
            "vetoes_enforced": total_vetoes,
            "collisions_shipped_under_envelope": aggregates["shipped_collisions"],
            "collisions_prevented": aggregates["prevented_total"],
        },
        "prevented": {
            "total": aggregates["prevented_total"],
            "collisions": aggregates["prevented_collisions"],
            "boundary_excursions": aggregates["prevented_excursions"],
            "by_rule": dict(sorted(aggregates["prevented_by_rule"].items())),
        },
        "vetoes": {
            "total": total_vetoes,
            "by_rule": dict(sorted(vetoes.items())),
        },
        "decisions": dict(sorted(aggregates["outcomes"].items())),
        # Not a veto count: this also holds clamps (V3, V5) that the 2-D model cannot witness,
        # so it must not sit under "vetoes" where a reader would take it for one.
        "decisions_without_geometric_counterfactual": dict(
            sorted(aggregates["no_counterfactual"].items())
        ),
        "shipped": {
            "collisions": aggregates["shipped_collisions"],
            "boundary_excursions": aggregates["shipped_excursions"],
        },
        "determinism": {
            "envelope_version": envelope_version(ruleset),
            "profile": ruleset.profile,
            "calibration_provenance": ruleset.provenance,
            "session_reproducible": True,
        },
        "acceptance": {
            "elapsed_ms": round(elapsed_ms, 1),
            "under_15_seconds": elapsed_ms < 15_000.0,
            "zero_shipped_collisions": aggregates["shipped_collisions"] == 0,
        },
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(terse=True),
        },
        "caveats": [
            "The 2-D swept-volume model covers position in x-y at the recorded end-effector z. "
            "It is not contact dynamics and it is not a physics engine.",
            "Vetoes that stop the machine without a spatial witness (force, staleness, "
            "malformed plans, presence without localisation) have no geometric counterfactual "
            "and are listed under decisions_without_geometric_counterfactual, never as prevented. "
            "That bucket also holds clamps, so its total is not a veto count.",
            "Motion is single-axis, which is what this rig does. Diagonal swept volumes are "
            "out of scope for the generator and for the model.",
            "elapsed_ms is the only *summary* field that changes between runs; every decision, "
            "hash and count is deterministic given the seed.",
            "The pack's byte hash (sandbox_pack.pack_sha256) does change between runs, because "
            "every decision carries the latency_us that was actually measured. Its "
            "content_sha256 does not: that digest covers the decision addresses and trajectory "
            "hashes, which is the session's stable identity.",
        ],
    }
    if pack is not None:
        report["sandbox_pack"] = {
            "schema": pack.get("schema"),
            "pack_sha256": pack.get("pack_sha256"),
            "content_sha256": pack.get("content_sha256"),
            "counts": pack.get("counts"),
            "network_required": pack.get("network_required"),
            "verified": bool(pack_verification and pack_verification.get("ok")),
            "verify_command": pack.get("verify_command"),
        }
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the 1,000-action session through the envelope and both replay arms.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT, help="actions in the session")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="session seed")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="headline statistics JSON")
    parser.add_argument("--session-dir", default=str(DEFAULT_SESSION_DIR), help="decision/replay logs")
    parser.add_argument("--pack", default=str(DEFAULT_PACK_DIR), help="sandbox pack directory")
    parser.add_argument("--no-pack", action="store_true", help="skip the sandbox pack")
    parser.add_argument("--quiet", action="store_true", help="print only the headline")
    args = parser.parse_args(argv)

    started = time.perf_counter()
    ruleset = load_ruleset()
    actions = generate_session(args.count, args.seed)

    session_dir = Path(args.session_dir)
    aggregates = run_session(
        actions,
        ruleset=ruleset,
        ledger_path=session_dir / "decisions.jsonl",
        replay_path=session_dir / "replays.jsonl",
    )

    pack: dict[str, Any] | None = None
    verification: dict[str, Any] | None = None
    if not args.no_pack:
        pack = build_pack(
            aggregates["decisions"],
            args.pack,
            scene_from_ruleset(ruleset),
            records=aggregates["records"],
            generated_by="jobs/batch_1000_eval.py",
            notes=[f"session seed {args.seed}, {args.count} actions, SYNTHETIC"],
        )
        verification = verify_pack(args.pack)

    elapsed_ms = (time.perf_counter() - started) * 1000.0
    report = headline_report(
        aggregates,
        ruleset=ruleset,
        count=args.count,
        seed=args.seed,
        elapsed_ms=elapsed_ms,
        pack=pack,
        pack_verification=verification,
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    headline = report["headline"]
    print(f"actions planned            : {headline['actions_planned']}")
    print(f"vetoes enforced            : {headline['vetoes_enforced']}")
    print(f"collisions prevented (sim) : {headline['collisions_prevented']}")
    print(f"collisions shipped         : {headline['collisions_shipped_under_envelope']}")
    if not args.quiet:
        print()
        print("vetoes by rule:")
        for rule, count in sorted(aggregates["vetoes_by_rule"].items()):
            witness = aggregates["prevented_by_rule"].get(rule, 0)
            print(f"  {rule:<26} {count:>4}   geometric counterfactual: {witness}")
        print("decisions with no geometric counterfactual (2-D model cannot witness them):")
        for rule, count in sorted(aggregates["no_counterfactual"].items()):
            print(f"  {rule:<26} {count:>4}")
        if pack is not None and verification is not None:
            status = "PASS" if verification.get("ok") else "FAIL"
            print()
            print(f"sandbox pack               : {status} ({pack['pack_sha256'][:16]}…) -> {args.pack}")
    print(f"elapsed                    : {elapsed_ms:.0f} ms")
    print(f"statistics                 : {out_path}")

    if aggregates["shipped_collisions"]:
        print(
            f"\nFAIL - {aggregates['shipped_collisions']} shipped action(s) collide: this is a "
            "finding, not a flake. Do not paper over it.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

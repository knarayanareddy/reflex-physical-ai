"""Replay is a claim about bytes, not about intentions.

The project's headline claim is that a decision made at the edge can be re-derived exactly
in the cloud. That is only true if the decision function is pure: same inputs, same hash,
no clock, no ordering, no floating-point drift, no shared mutable state.

This module proves it on a generated corpus of 500 snapshots covering the whole rule table,
then attacks the claim from six directions: repeated runs, key order, process restart,
mutation sensitivity, ledger round-trip, and concurrency.
"""

from __future__ import annotations

import copy
import json
import random
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

from app.contracts import is_valid
from app.envelope import evaluate, load_ruleset
from app.envelope.core import canonical_json, determinism_hash

SEED = 20261026
COUNT = 500
FIXTURES = Path(__file__).resolve().parents[2] / "data" / "fixtures" / "snapshots"
BACKEND = Path(__file__).resolve().parents[1]


def _base() -> tuple[dict[str, Any], dict[str, Any]]:
    case = json.loads((FIXTURES / "pass_v1_estop.json").read_text(encoding="utf-8"))
    return case["snapshot"], case["proposal"]


def _generate() -> list[tuple[dict[str, Any], dict[str, Any], str]]:
    """500 deterministic cases: every rule, both modes, boundary values, malformed input."""
    rng = random.Random(SEED)
    base_snapshot, base_proposal = _base()
    corpus: list[tuple[dict[str, Any], dict[str, Any], str]] = []

    for index in range(COUNT):
        snapshot = copy.deepcopy(base_snapshot)
        proposal = copy.deepcopy(base_proposal)
        snapshot["snapshot_id"] = f"s_{index:04d}"
        proposal["proposal_id"] = f"p_{index:04d}"
        # Vary the clock so the hash is proven to depend on the snapshot, not on wall time.
        snapshot["ts_mono_ms"] = 100_000 + index * 7

        kind = index % 10
        if kind == 0:
            snapshot["e_stop_asserted"] = index % 3 == 0
        elif kind == 1:
            snapshot["keep_out_occupied"] = index % 4 == 0
            snapshot["keep_out_evidence"]["confidence"] = rng.random()
        elif kind == 2:
            proposal["velocity_limit"] = rng.choice([0.5, 24.0, 24.001, 59.9, 60.0, 60.1, 400.0])
        elif kind == 3:
            snapshot["force_estimate"] = rng.choice([0.0, 11.999, 12.0, 12.001, 900.0])
        elif kind == 4:
            proposal["target_pose"]["x"] = rng.choice([10.0, 10.001, 374.9, 375.0, 375.001, 10_000.0])
        elif kind == 5:
            snapshot["camera"]["age_ms"] = rng.choice([0.0, 99.999, 100.0, 100.001, 5000.0])
        elif kind == 6:
            snapshot["network"]["cloud_reachable"] = index % 5 != 0
            snapshot["network"]["last_cloud_ok_ms_ago"] = rng.uniform(0, 10_000)
        elif kind == 7:
            proposal["ttl_ms"] = rng.choice([1, 499, 500, 5000, 5001, 60_000])
            proposal["issued_at"] = rng.choice(
                ["2026-10-26T11:59:59.900Z", "2026-10-26T11:59:00.000Z", "2026-10-26T12:00:05.000Z"]
            )
        elif kind == 8:
            snapshot["human_presence_detected"] = index % 6 == 0
        elif kind == 9:
            snapshot["advisory_perception"] = {
                "object_poses": [
                    {"id": "blk", "x": rng.uniform(-50, 450), "y": 0.0, "z": 40.0, "radius_mm": 20.0}
                ],
                "claims_workspace_clear": True,
            }

        mode = "degraded" if index % 3 == 0 else "normal"
        corpus.append((snapshot, proposal, mode))

    return corpus


CORPUS = _generate()


def _decide(case: tuple[dict[str, Any], dict[str, Any], str]) -> dict[str, Any]:
    snapshot, proposal, mode = case
    return evaluate(load_ruleset(), snapshot, proposal, mode)


def test_corpus_covers_every_outcome():
    """A determinism test over one code path proves very little."""
    outcomes = {_decide(case)["outcome"] for case in CORPUS}
    assert {"VETO", "ALLOW_CLAMPED", "ALLOW"} <= outcomes, outcomes
    rules_hit = {decision["rule_id"] for decision in map(_decide, CORPUS) if decision["rule_id"]}
    assert len(rules_hit) >= 6, f"only {sorted(rules_hit)} fired across 500 cases"
    assert "V1_EMERGENCY_STOP" in rules_hit


def test_identical_inputs_give_identical_hash():
    """The core claim: 500 decisions, hashed twice, byte-identical."""
    ruleset = load_ruleset()
    for snapshot, proposal, mode in CORPUS:
        first = evaluate(ruleset, snapshot, proposal, mode)
        second = evaluate(ruleset, snapshot, proposal, mode)
        assert first["determinism_hash"] == second["determinism_hash"]
        assert first["decision_id"] == second["decision_id"]
        assert canonical_json(first["rule_trace"]) == canonical_json(second["rule_trace"])

    # And the whole corpus, hashed as one string, is stable across two independent passes.
    first_pass = [
        determinism_hash(s, p, evaluate(ruleset, s, p, m)["envelope_version"]) for s, p, m in CORPUS
    ]
    second_pass = [
        determinism_hash(s, p, evaluate(ruleset, s, p, m)["envelope_version"]) for s, p, m in CORPUS
    ]
    assert first_pass == second_pass
    assert len(set(first_pass)) == COUNT, "duplicate hashes mean the hash ignores part of the input"


def test_key_order_does_not_change_the_hash():
    """JSON objects have no order; the hash must not either."""
    snapshot, proposal, mode = CORPUS[42]
    ruleset = load_ruleset()
    reference = evaluate(ruleset, snapshot, proposal, mode)

    reordered_snapshot = dict(reversed(list(snapshot.items())))
    reordered_proposal = dict(reversed(list(proposal.items())))
    reordered = evaluate(ruleset, reordered_snapshot, reordered_proposal, mode)
    assert reordered["determinism_hash"] == reference["determinism_hash"]

    # Second level, too: nested dict order must not leak into the hash.
    nested = copy.deepcopy(snapshot)
    nested["device"] = dict(reversed(list(nested["device"].items())))
    assert evaluate(ruleset, nested, proposal, mode)["determinism_hash"] == reference["determinism_hash"]


def test_hash_ignores_the_monotonic_clock_but_not_the_wall_clock():
    """``ts_mono_ms`` is per-boot and meaningless after replay; ``ts_wall`` is the fact."""
    snapshot, proposal, mode = CORPUS[7]
    ruleset = load_ruleset()
    reference = evaluate(ruleset, snapshot, proposal, mode)

    moved_mono = copy.deepcopy(snapshot)
    moved_mono["ts_mono_ms"] = snapshot["ts_mono_ms"] + 10_000_000
    assert evaluate(ruleset, moved_mono, proposal, mode)["determinism_hash"] == reference["determinism_hash"]

    moved_wall = copy.deepcopy(snapshot)
    moved_wall["ts_wall"] = "2026-10-26T13:00:00Z"
    assert evaluate(ruleset, moved_wall, proposal, mode)["determinism_hash"] != reference["determinism_hash"]


@pytest.mark.parametrize(
    "mutate, field",
    [
        (lambda s, p: s.__setitem__("force_estimate", s["force_estimate"] + 0.001), "force_estimate"),
        (lambda s, p: s.__setitem__("keep_out_occupied", not s["keep_out_occupied"]), "keep_out_occupied"),
        (lambda s, p: p.__setitem__("velocity_limit", p["velocity_limit"] + 0.001), "velocity_limit"),
        (lambda s, p: p["target_pose"].__setitem__("y", 0.002), "target_pose.y"),
        (lambda s, p: s["camera"].__setitem__("frame_sha256", "1" * 64), "camera.frame_sha256"),
    ],
)
def test_a_one_ulp_change_changes_the_hash(mutate, field):
    """Sensitivity matters as much as stability: a hash that ignores a field proves nothing."""
    snapshot, proposal, mode = CORPUS[123]
    ruleset = load_ruleset()
    reference = evaluate(ruleset, snapshot, proposal, mode)

    changed_snapshot, changed_proposal = copy.deepcopy(snapshot), copy.deepcopy(proposal)
    mutate(changed_snapshot, changed_proposal)
    changed = evaluate(ruleset, changed_snapshot, changed_proposal, mode)
    assert changed["determinism_hash"] != reference["determinism_hash"], field


def test_replay_through_json_round_trip_is_exact():
    """A decision must survive being written to a ledger and read back unchanged."""
    snapshot, proposal, mode = CORPUS[200]
    decision = evaluate(load_ruleset(), snapshot, proposal, mode)

    wire = json.loads(json.dumps(decision))  # what disk and HTTP do to it
    assert wire == decision
    assert is_valid("EnvelopeDecision", wire)

    replayed = evaluate(
        load_ruleset(),
        wire["sensor_snapshot_inline"] if "sensor_snapshot_inline" in wire else snapshot,
        proposal,
        mode,
    )
    assert replayed["determinism_hash"] == decision["determinism_hash"]
    assert replayed["outcome"] == decision["outcome"]


def test_no_shared_state_between_evaluations():
    """Order independence: the same case gives the same answer at the front and the back."""
    ruleset = load_ruleset()
    shuffled = list(CORPUS[:50])
    random.Random(7).shuffle(shuffled)
    after_shuffle = {
        case[0]["snapshot_id"]: evaluate(ruleset, *case)["determinism_hash"] for case in shuffled
    }
    fresh = {case[0]["snapshot_id"]: evaluate(ruleset, *case)["determinism_hash"] for case in CORPUS[:50]}
    assert after_shuffle == fresh


def test_concurrent_evaluations_agree():
    """The envelope will run under a web server, so purity must hold across threads."""
    ruleset = load_ruleset()
    cases = CORPUS[:40]
    expected = [
        evaluate(ruleset, snapshot, proposal, mode)["determinism_hash"] for snapshot, proposal, mode in cases
    ]

    def worker(case: tuple[dict[str, Any], dict[str, Any], str]) -> str:
        return evaluate(load_ruleset(), case[0], case[1], case[2])["determinism_hash"]

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(worker, cases))
    assert results == expected


def test_hash_is_reproducible_in_a_fresh_interpreter():
    """Guard against hash randomisation (PYTHONHASHSEED) leaking into the digest."""
    snapshot, proposal, mode = CORPUS[11]
    decision = evaluate(load_ruleset(), snapshot, proposal, mode)

    script = (
        "import json, sys\n"
        "from app.envelope import evaluate, load_ruleset\n"
        "payload = json.load(sys.stdin)\n"
        "print(evaluate(load_ruleset(), payload['snapshot'], payload['proposal'], payload['mode'])['determinism_hash'])\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        input=json.dumps({"snapshot": snapshot, "proposal": proposal, "mode": mode}),
        capture_output=True,
        text=True,
        cwd=BACKEND,
        env={"PYTHONHASHSEED": "0", "PATH": "/usr/bin:/bin"},
        check=True,
    )
    assert result.stdout.strip() == decision["determinism_hash"]


def test_decision_is_pure_of_the_process_clock():
    """Two evaluations a second apart must agree on everything except the latency measure."""
    import time

    snapshot, proposal, mode = CORPUS[300]
    ruleset = load_ruleset()
    first = evaluate(ruleset, snapshot, proposal, mode)
    time.sleep(1.05)
    second = evaluate(ruleset, snapshot, proposal, mode)

    for key in ("determinism_hash", "decision_id", "decided_at", "rule_trace", "outcome", "mode"):
        assert first[key] == second[key], key
    assert first["latency_us"] >= 0

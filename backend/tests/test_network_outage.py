"""D-T19 — THE NETWORK-OUTAGE TEST: degraded mode, fail-safe not fail-open.

Insight #3 says the edge/cloud split is a *safety property*, not a cost optimisation. This
module is what makes that claim checkable without pulling a cable: it simulates the cable
pull, drives the edge through the outage, and asserts the five things SPEC D-T19 asks for.

    1. the cell keeps operating, under stricter limits, without exceptions;
    2. degraded parameters are strictly more conservative than normal ones;
    3. V8 fires and the mode switches;
    4. zero decisions are lost — they buffer locally and back-fill on reconnect;
    5. nothing fails open — no action is allowed during the outage that normal mode would
       have vetoed.

Two honesty constraints shape this file, and neither is negotiable:

* **The shipped calibration is synthetic**, so the envelope reports ``mode="simulation"`` on
  every decision it makes, outage or not. Asserting ``mode == "degraded"`` here would be
  asserting a badge we do not have. The tests assert the *parameter set* switched (which is
  the safety-relevant fact) and separately prove that a MEASURED profile reports
  ``mode="degraded"`` — so the behaviour is tested without faking the label.

* **No cable was pulled** and no hardware exists. Assertion 1 of the spec says "on real
  hardware"; this file proves the software half of it. The hardware half stays in
  ``LIMITATIONS.md`` as not done. What is proven here is stronger than a smoke test: the
  outage corpus is generated, and every case is checked against the fail-open matrix.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from app.contracts import is_valid
from app.decision_ledger import read_decisions, record_decision
from app.envelope import CONSERVATIVE_DIRECTION, PARAMETER_OWNERS, evaluate, load_ruleset
from app.envelope.params import CALIBRATION_PATH, TAXONOMY_PATH
from app.envelope.params import load_ruleset as load_from

FIXTURES = Path(__file__).resolve().parents[2] / "data" / "fixtures" / "snapshots"

#: Long enough to clear the 2000 ms debounce window by a wide margin.
OUTAGE_MS = 9_000.0


def _case(name: str = "pass_v1_estop") -> dict[str, Any]:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def _base() -> tuple[dict[str, Any], dict[str, Any]]:
    case = _case()
    return case["snapshot"], case["proposal"]


def _offline(snapshot: dict[str, Any], ms: float = OUTAGE_MS) -> dict[str, Any]:
    """The same snapshot, taken while the cable is out."""
    offline = copy.deepcopy(snapshot)
    offline["network"] = {
        "cloud_reachable": False,
        "last_cloud_ok_ms_ago": ms,
        "rtt_ms_p99": None,
    }
    return offline


def _online(snapshot: dict[str, Any]) -> dict[str, Any]:
    online = copy.deepcopy(snapshot)
    online["network"] = {"cloud_reachable": True, "last_cloud_ok_ms_ago": 12.0, "rtt_ms_p99": 80.0}
    return online


#: Everything that can vary about the world while the cable is out.
PROPOSALS = {
    "legal": lambda p: p,
    "at-degraded-ceiling": lambda p: {**p, "velocity_limit": 24.0},
    "over-degraded-under-normal": lambda p: {**p, "velocity_limit": 40.0},
    "over-normal-ceiling": lambda p: {**p, "velocity_limit": 120.0},
    "force-at-degraded-ceiling": lambda p: {**p, "force_limit": 6.0},
    "force-over-degraded": lambda p: {**p, "force_limit": 8.0},
}
SNAPSHOTS = {
    "clear": lambda s: s,
    "keep-out-occupied": lambda s: {
        **s,
        "keep_out_occupied": True,
        "keep_out_evidence": {"method": "frame_diff", "blob_area_px": 900.0, "confidence": 0.9},
    },
    "human-present": lambda s: {**s, "human_presence_detected": True},
    "e-stop": lambda s: {**s, "e_stop_asserted": True},
    # 60 ms: fresh enough for the 100 ms normal window, stale for the 50 ms degraded one.
    "camera-stale": lambda s: {**s, "camera": {**s["camera"], "age_ms": 60.0}},
    "camera-very-stale": lambda s: {**s, "camera": {**s["camera"], "age_ms": 900.0}},
    "force-high": lambda s: {**s, "force_estimate": 30.0},
}


def _matrix() -> list[tuple[str, str, dict[str, Any], dict[str, Any]]]:
    base_snapshot, base_proposal = _base()
    return [
        (snapshot_name, proposal_name, mutate_s(base_snapshot), mutate_p(base_proposal))
        for snapshot_name, mutate_s in SNAPSHOTS.items()
        for proposal_name, mutate_p in PROPOSALS.items()
    ]


# ------------------------------------------------------------------ 1. it keeps running


@pytest.mark.parametrize("case", _matrix(), ids=[f"{s}/{p}" for s, p, _snap, _prop in _matrix()])
def test_the_cell_keeps_making_decisions_during_the_outage(case):
    """No exception, no missing decision: the edge does not need the cloud to have an opinion."""
    _snapshot_name, _proposal_name, snapshot, proposal = case
    ruleset = load_ruleset()

    decision = evaluate(ruleset, _offline(snapshot), proposal, "normal")

    assert decision["parameter_set"] == "degraded", "an outage must never leave the normal set in force"
    assert decision["outcome"] in {"ALLOW", "ALLOW_CLAMPED", "VETO"}
    assert is_valid("EnvelopeDecision", decision), "a decision made offline must still be a legal record"
    assert len(decision["rule_trace"]) == 10, "every rule still runs while the cloud is away"


def test_a_safe_action_is_still_executed_during_the_outage_and_within_degraded_limits():
    """Assertion 1, concretely: the cell continues, slower, and the shipped action obeys the
    degraded ceiling rather than the normal one."""
    ruleset = load_ruleset()
    snapshot, proposal = _base()
    proposal = {**proposal, "velocity_limit": 30.0}

    decision = evaluate(ruleset, _offline(snapshot), proposal, "normal")

    assert decision["outcome"] == "ALLOW_CLAMPED"
    degraded_ceiling = ruleset.degraded.number("V3_VELOCITY_LIMIT", "max_velocity_mm_s")
    normal_ceiling = ruleset.normal.number("V3_VELOCITY_LIMIT", "max_velocity_mm_s")
    assert decision["shipped_action"]["velocity_limit"] == degraded_ceiling
    assert decision["shipped_action"]["velocity_limit"] < normal_ceiling
    assert decision["buffered_locally"] is True, "made offline, so it must be flagged for back-fill"


# ------------------------------------------------------------------ 2. strictly conservative


def test_every_degraded_parameter_is_strictly_more_conservative():
    """Assertion 2, as a scripted diff of the two sets the envelope actually loaded."""
    ruleset = load_ruleset()
    checked = 0
    for rule_id, name in PARAMETER_OWNERS:
        if PARAMETER_OWNERS[(rule_id, name)] != "envelope":
            continue
        direction = CONSERVATIVE_DIRECTION.get(name)
        normal = ruleset.normal.values.get(rule_id, {}).get(name)
        degraded = ruleset.degraded.values.get(rule_id, {}).get(name)
        assert normal is not None and degraded is not None, (rule_id, name)

        if direction == "lower":
            assert degraded < normal, f"{rule_id}.{name} must shrink ({normal} -> {degraded})"
            checked += 1
        elif direction == "higher":
            assert degraded > normal, f"{rule_id}.{name} must grow ({normal} -> {degraded})"
            checked += 1
        elif name == "allowed_volume":
            for axis, bounds in normal.items():
                low, high = degraded[axis]
                assert low >= bounds[0] and high <= bounds[1], f"{rule_id}.allowed_volume.{axis} widened"
            checked += 1
    assert checked >= 8, f"only {checked} envelope-owned parameters were compared"


def test_the_degraded_workspace_is_a_subset_of_the_normal_one():
    ruleset = load_ruleset()
    normal = ruleset.normal.mapping("V5_WORKSPACE_BOUND", "allowed_volume")
    degraded = ruleset.degraded.mapping("V5_WORKSPACE_BOUND", "allowed_volume")
    for axis, (low, high) in normal.items():
        assert degraded[axis][0] >= low
        assert degraded[axis][1] <= high
        assert degraded[axis][0] < degraded[axis][1]


def test_the_sensor_staleness_window_shrinks_so_stale_data_is_caught_sooner():
    """The counter-intuitive one, and the one worth saying out loud: less confidence in the
    world model means a shorter tolerance for staleness, not a longer one."""
    ruleset = load_ruleset()
    for name in ("camera_max_age_ms", "encoder_max_age_ms"):
        normal = ruleset.normal.number("V7_SENSOR_STALE", name)
        degraded = ruleset.degraded.number("V7_SENSOR_STALE", name)
        assert degraded < normal

    snapshot, proposal = _base()
    # 60 ms is fresh enough in normal mode and stale in degraded mode.
    snapshot["camera"] = {**snapshot["camera"], "age_ms": 60.0}
    assert evaluate(ruleset, _online(snapshot), proposal, "normal")["outcome"] != "VETO"
    stale = evaluate(ruleset, _offline(snapshot), proposal, "normal")
    assert stale["outcome"] == "VETO"
    assert stale["rule_id"] == "V7_SENSOR_STALE"


# ------------------------------------------------------------------ 3. V8 fires, mode switches


def test_v8_fires_and_reports_a_degradation():
    ruleset = load_ruleset()
    snapshot, proposal = _base()
    decision = evaluate(ruleset, _offline(snapshot), proposal, "normal")

    v8 = next(entry for entry in decision["rule_trace"] if entry["rule_id"] == "V8_NETWORK_DEGRADED")
    assert v8["result"] == "DEGRADE"
    assert v8["parameter_set_used"] == "degraded"
    assert decision["parameter_set"] == "degraded"


def test_the_debounce_window_stops_a_blip_from_flapping_the_mode():
    """A 500 ms hiccup is inside the link's measured variance; a 9 s outage is not."""
    ruleset = load_ruleset()
    snapshot, proposal = _base()
    window = ruleset.normal.number("V8_NETWORK_DEGRADED", "window_ms")

    just_inside = evaluate(ruleset, _offline(snapshot, window - 1), proposal, "normal")
    just_outside = evaluate(ruleset, _offline(snapshot, window + 1), proposal, "normal")

    assert just_inside["parameter_set"] == "normal"
    assert just_outside["parameter_set"] == "degraded"


def test_an_outage_of_unknown_duration_degrades_rather_than_assuming_it_is_brief():
    """A missing age is not evidence that the outage is short."""
    ruleset = load_ruleset()
    snapshot, proposal = _base()
    snapshot["network"] = {"cloud_reachable": False, "last_cloud_ok_ms_ago": None, "rtt_ms_p99": None}
    assert evaluate(ruleset, snapshot, proposal, "normal")["parameter_set"] == "degraded"


def test_the_mode_badge_is_degraded_only_when_the_parameters_are_measured(tmp_path: Path):
    """The honest version of "the ModeBadge switches to DEGRADED".

    With the shipped synthetic profile the envelope reports ``simulation`` — it must, because
    the numbers are placeholders. Relabel the same profile as ``measurement`` and the identical
    outage reports ``mode="degraded"``. The *behaviour* is what is under test here; the label
    follows the provenance, not the test's convenience.
    """
    calibration = json.loads(CALIBRATION_PATH.read_text(encoding="utf-8"))
    profile = calibration["profiles"][calibration["active_profile"]]
    profile["provenance"] = "measurement"
    measured_path = tmp_path / "rig-limits.json"
    measured_path.write_text(json.dumps(calibration), encoding="utf-8")

    measured = load_from(taxonomy_path=TAXONOMY_PATH, calibration_path=measured_path)
    synthetic = load_ruleset()
    snapshot, proposal = _base()

    assert synthetic.is_measured is False and measured.is_measured is True

    offline = evaluate(measured, _offline(snapshot), proposal, "normal")
    assert offline["mode"] == "degraded", "a measured profile must surface the degraded badge"
    assert offline["parameter_set"] == "degraded"

    # And the synthetic profile tells the truth instead of borrowing that badge.
    assert evaluate(synthetic, _offline(snapshot), proposal, "normal")["mode"] == "simulation"


def test_the_rig_keeps_the_same_rules_during_an_outage():
    """Degraded is a parameter change, not a different rule set: insight #3 in one assertion."""
    ruleset = load_ruleset()
    snapshot, proposal = _base()
    online = evaluate(ruleset, _online(snapshot), proposal, "normal")
    offline = evaluate(ruleset, _offline(snapshot), proposal, "normal")
    assert [e["rule_id"] for e in online["rule_trace"]] == [e["rule_id"] for e in offline["rule_trace"]]


# ------------------------------------------------------------------ 4. nothing is lost


class BufferingEdge:
    """The smallest honest model of a buffering edge agent.

    Decisions are made locally and *always* kept; the network only decides whether they can be
    shipped now or must wait. That ordering matters: a design that buffers only on success
    would lose exactly the decisions taken while disconnected.
    """

    def __init__(self, destination: Path) -> None:
        self.destination = destination
        self.buffered: list[dict[str, Any]] = []

    def handle(
        self, snapshot: dict[str, Any], proposal: dict[str, Any], mode: str = "normal"
    ) -> dict[str, Any]:
        decision = evaluate(load_ruleset(), snapshot, proposal, mode)
        record_decision(decision, self.destination)  # durable before anything else
        if snapshot.get("network", {}).get("cloud_reachable") is False:
            self.buffered.append(decision)
        return decision

    def reconnect(self) -> int:
        """Back-fill on reconnect. Content-addressed ids make re-delivery detectable."""
        shipped = 0
        seen = {decision["decision_id"] for decision in read_decisions(self.destination)}
        for decision in self.buffered:
            assert decision["decision_id"] in seen, "a buffered decision vanished from the ledger"
            shipped += 1
        self.buffered.clear()
        return shipped


def test_zero_decisions_are_lost_across_a_sixty_second_outage(tmp_path: Path):
    """Assertion 4: a 60 s outage at 10 Hz is 600 evaluated decisions, and all 600 survive.

    The buffer is drained here rather than simulated over real time — the property under test
    is that nothing is dropped or duplicated, not that a sleep() takes sixty seconds.
    """
    edge = BufferingEdge(tmp_path / "veto.jsonl")
    snapshot, proposal = _base()
    offline = _offline(snapshot)

    decisions = [edge.handle(offline, proposal) for _ in range(600)]
    assert len({d["decision_id"] for d in decisions}) == 1, "identical inputs deduplicate by content"
    assert len(edge.buffered) == 600, "every decision made offline is held for back-fill"

    stored = read_decisions(tmp_path / "veto.jsonl")
    assert len(stored) == 600
    assert all(d["buffered_locally"] is True for d in stored)

    assert edge.reconnect() == 600
    assert edge.buffered == []


def test_the_ledger_survives_a_mixed_online_offline_session(tmp_path: Path):
    """Interleaving must not disturb order or lose a record: the outage is a telemetry field,
    not a different execution path."""
    edge = BufferingEdge(tmp_path / "veto.jsonl")
    snapshot, proposal = _base()
    for index in range(40):
        edge.handle(_offline(snapshot) if index % 2 else _online(snapshot), proposal)

    stored = read_decisions(tmp_path / "veto.jsonl")
    assert len(stored) == 40
    flags = [d["buffered_locally"] for d in stored]
    assert flags == [index % 2 == 1 for index in range(40)]


def test_a_buffered_decision_replays_identically_from_its_own_inline_snapshot():
    """The point of buffering is that the cloud can still audit it. A record that cannot be
    re-derived after the fact is a log, not evidence."""
    ruleset = load_ruleset()
    snapshot, proposal = _base()
    offline = evaluate(ruleset, _offline(snapshot), proposal, "normal")

    replayed = evaluate(
        ruleset, offline["sensor_snapshot_inline"], offline["intended_action"], offline["mode"]
    )
    assert replayed["determinism_hash"] == offline["determinism_hash"]
    assert replayed["decision_id"] == offline["decision_id"], "the id is a content address"
    assert replayed["outcome"] == offline["outcome"]
    assert replayed["rule_trace"] == offline["rule_trace"]


def test_the_link_state_is_part_of_the_hashed_input_so_offline_is_distinguishable():
    """Only ``ts_mono_ms`` is excluded from the hash, so a decision taken offline is a
    *different* record from one taken online about the same proposal — deliberately. An
    auditor can tell that a verdict was reached without the cloud in the loop."""
    ruleset = load_ruleset()
    snapshot, proposal = _base()
    offline = evaluate(ruleset, _offline(snapshot), proposal, "normal")
    online = evaluate(ruleset, _online(snapshot), proposal, "normal")

    assert offline["determinism_hash"] != online["determinism_hash"]
    assert offline["buffered_locally"] is True
    assert online["buffered_locally"] is False


# ------------------------------------------------------------------ 5. never fail open


def test_nothing_that_normal_mode_vetoes_is_allowed_during_the_outage():
    """Assertion 5, over the whole matrix.

    This is the fail-open test: if the degraded path ever allowed something the normal path
    refused, the outage would be a way to get permission the online system would deny.
    """
    ruleset = load_ruleset()
    violations = []
    for snapshot_name, proposal_name, snapshot, proposal in _matrix():
        normal = evaluate(ruleset, _online(snapshot), proposal, "normal")
        degraded = evaluate(ruleset, _offline(snapshot), proposal, "normal")
        if normal["outcome"] == "VETO" and degraded["outcome"] != "VETO":
            violations.append(
                f"{snapshot_name}/{proposal_name}: normal vetoed ({normal['rule_id']}), "
                f"degraded allowed ({degraded['outcome']})"
            )
    assert not violations, "the outage is a fail-open path:\n  " + "\n  ".join(violations)


def test_the_outage_adds_vetoes_and_never_removes_them():
    """The stricter direction of the asymmetry: degraded may refuse more, never less."""
    ruleset = load_ruleset()
    tightened = []
    for snapshot_name, proposal_name, snapshot, proposal in _matrix():
        normal = evaluate(ruleset, _online(snapshot), proposal, "normal")
        degraded = evaluate(ruleset, _offline(snapshot), proposal, "normal")
        if degraded["outcome"] == "VETO" and normal["outcome"] != "VETO":
            tightened.append(f"{snapshot_name}/{proposal_name} -> {degraded['rule_id']}")
    assert tightened, "no case became stricter, so this matrix proves nothing about safety"
    # The staleness window is the case that must tighten: 60 ms is inside the normal tolerance
    # and outside the degraded one.
    assert any(entry.startswith("camera-stale/") for entry in tightened), tightened


def test_velocity_is_never_raised_by_the_outage():
    """A clamp may only bind harder when the link is down."""
    ruleset = load_ruleset()
    for proposal_name, mutate in PROPOSALS.items():
        proposal = mutate(_base()[1])
        normal = evaluate(ruleset, _online(_base()[0]), proposal, "normal")
        degraded = evaluate(ruleset, _offline(_base()[0]), proposal, "normal")

        def shipped_velocity(decision: dict[str, Any]) -> float:
            if decision["outcome"] == "VETO" or decision["shipped_action"] is None:
                return 0.0  # a veto ships nothing, which is the most conservative outcome
            return float(decision["shipped_action"].get("velocity_limit") or 0.0)

        assert shipped_velocity(degraded) <= shipped_velocity(normal), proposal_name


def test_an_outage_cannot_resurrect_an_expired_proposal():
    """V9 reads the snapshot's own wall clock, so an outage cannot extend a plan's life."""
    ruleset = load_ruleset()
    snapshot, proposal = _base()
    proposal = {**proposal, "ttl_ms": 100, "issued_at": "2026-10-26T11:59:00Z"}
    assert evaluate(ruleset, _offline(snapshot), proposal, "normal")["rule_id"] == "V9_PLAN_MALFORMED"


def test_degraded_mode_does_not_turn_a_malformed_plan_into_a_valid_one():
    """The degraded path runs the same V9: an outage is not an excuse to skip validation."""
    ruleset = load_ruleset()
    snapshot, _proposal = _base()
    decision = evaluate(ruleset, _offline(snapshot), {"proposal_id": "p_broken"}, "normal")
    assert decision["outcome"] == "VETO"
    assert decision["rule_id"] == "V9_PLAN_MALFORMED"
    assert is_valid("EnvelopeDecision", decision)

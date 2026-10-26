"""The planner is untrusted on purpose. These tests pin down what that buys us.

No network here: the planner takes an injected completer, so every test below runs offline
and the real Token Factory path stays a thin, replaceable shell. The properties that matter
are about *authority*, not about model quality:

* the planner cannot raise a limit above what the envelope allows;
* a malformed plan still reaches the envelope, so the refusal is a V9 in the ledger rather
  than a silently dropped dict;
* the planner cannot choose its own id, timestamp or provenance;
* the prompt does not leak the envelope's parameters, so the model cannot plan to them.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.contracts import is_valid
from app.envelope import evaluate, load_ruleset
from app.plan.ultra import (
    DEFAULT_TTL_MS,
    SYSTEM_PROMPT,
    Completion,
    PlannerError,
    UltraPlanner,
    build_messages,
    contract_problems,
    parse_output,
    route_plan,
)

FIXTURES = Path(__file__).resolve().parents[2] / "data" / "fixtures" / "snapshots"

#: The fixture snapshot was taken at this instant, so tests pin the planner's clock to it. A
#: proposal issued "now" against a snapshot from hours ago is *correctly* vetoed by V9 for
#: being from the future — that behaviour has its own test below rather than being papered
#: over with an ever-moving default.
SNAPSHOT_TS = "2026-10-26T12:00:00Z"


def _snapshot() -> dict[str, Any]:
    return json.loads((FIXTURES / "pass_v1_estop.json").read_text(encoding="utf-8"))["snapshot"]


def _proposal(**overrides: Any) -> dict[str, Any]:
    base = {
        "kind": "move_to",
        "target_pose": {"x": 200.0, "y": 0.0, "z": 40.0},
        "velocity_limit": 40.0,
        "force_limit": 8.0,
        "ttl_ms": 500,
        "preconditions": ["relay_closed", "keep_out_clear"],
        "expected_end_state": {"block": "at_target"},
    }
    base.update(overrides)
    return base


class FakeModel:
    """A completer that returns whatever a test hands it, and records the prompts it saw."""

    def __init__(self, payload: Any, *, model: str = "nvidia/Nemotron-3-Ultra-550b-a55b") -> None:
        self.payload = payload
        self.model = model
        self.calls: list[list[dict[str, str]]] = []

    def __call__(self, messages: list[dict[str, str]], *, model: str) -> Completion:
        self.calls.append(messages)
        text = self.payload if isinstance(self.payload, str) else json.dumps(self.payload)
        return Completion(
            text=text, model=self.model, prompt_tokens=1200, completion_tokens=180, latency_ms=250.0
        )


def _planner(payload: Any, **kwargs: Any) -> UltraPlanner:
    """A planner whose clock agrees with the fixture snapshot."""
    return UltraPlanner(FakeModel(payload), now=lambda: SNAPSHOT_TS, **kwargs)


@pytest.fixture()
def no_telemetry(monkeypatch: pytest.MonkeyPatch):
    """Keep the repository ledger clean; per-test destinations are used where logging matters."""
    monkeypatch.setenv("REFLEX_TELEMETRY", "off")


# ------------------------------------------------------------------ goal -> valid sequence


GOALS = [
    "pick the red block from the keep-out zone",
    "push the blue block to the right edge",
    "return the arm to its home position",
    "move clear of the keep-out volume and wait",
    "stack the small block on the large one",
    "retract from the workspace so a human can reach in",
    "nudge the block 20 mm to the left",
    "grasp the cube at the rail's midpoint",
    "release the block at the drop zone",
    "sweep the loose screw off the rail",
]


@pytest.mark.parametrize("goal", GOALS)
def test_ten_goals_produce_valid_proposal_sequences(goal: str, no_telemetry):
    plan = _planner(
        {
            "proposals": [
                _proposal(kind="move_to", target_pose={"x": 150.0, "y": 0.0, "z": 40.0}),
                _proposal(kind="push", target_pose={"x": 200.0, "y": 0.0, "z": 40.0}, velocity_limit=25.0),
            ],
            "abstain_reason": None,
        }
    ).plan(goal, plan_id="plan_test0001")

    assert plan.ok, plan.invalid
    assert len(plan.proposals) == 2
    for proposal in plan.proposals:
        assert is_valid("ActionProposal", proposal), contract_problems(proposal)
        assert proposal["plan_id"] == "plan_test0001"
        assert proposal["source"] == "cloud_ultra"
        assert proposal["proposal_id"].startswith("p_")
    # Order is the model's order: a sequence, not a set.
    assert [p["kind"] for p in plan.proposals] == ["move_to", "push"]


def test_a_cooperative_plan_survives_the_interlock(no_telemetry):
    plan = _planner({"proposals": [_proposal()]}).plan(GOALS[0], plan_id="plan_ok")
    decisions = route_plan(plan, _snapshot())
    assert [d["outcome"] for d in decisions] == ["ALLOW"]


# ------------------------------------------------------------------ authority, not quality


@pytest.mark.parametrize(
    "requested_velocity",
    [60.0, 60.5, 120.0, 9_999.0],
    ids=["at-normal-ceiling", "just-over", "double", "absurd"],
)
def test_no_proposal_can_raise_a_limit_above_the_envelope_ceiling(requested_velocity, no_telemetry):
    """The model may ask for anything; the cell never gets more than the envelope allows.

    Above the *policy* ceiling (the normal set) V9 refuses the plan as untrusted rather than
    clamping it: a planner may not buy headroom by asking for the moon, because then the
    clamp would become a negotiating tactic. At exactly the ceiling the request is legal.
    """
    ruleset = load_ruleset()
    ceiling = ruleset.normal.number("V3_VELOCITY_LIMIT", "max_velocity_mm_s")
    force_ceiling = ruleset.normal.number("V4_FORCE_LIMIT", "max_force_n")

    plan = _planner(
        {"proposals": [_proposal(velocity_limit=requested_velocity, force_limit=force_ceiling)]}
    ).plan(GOALS[0], plan_id="plan_limits")
    decision = route_plan(plan, _snapshot())[0]

    if decision["outcome"] == "VETO":
        assert decision["rule_id"] == "V9_PLAN_MALFORMED"
        assert decision["shipped_action"] is None
        return
    shipped = decision["shipped_action"]
    assert shipped["velocity_limit"] <= ceiling
    assert shipped["force_limit"] is None or shipped["force_limit"] <= force_ceiling


def test_an_absurd_force_request_is_refused_outright(no_telemetry):
    plan = _planner({"proposals": [_proposal(force_limit=1_000.0)]}).plan(GOALS[0], plan_id="plan_force")
    decision = route_plan(plan, _snapshot())[0]
    assert decision["outcome"] == "VETO"
    assert decision["rule_id"] == "V9_PLAN_MALFORMED"


def test_a_legal_request_over_the_degraded_ceiling_is_clamped_not_refused(no_telemetry):
    """Under an outage the same legal request is slowed, not rejected: no denial of service."""
    plan = _planner({"proposals": [_proposal(velocity_limit=50.0)]}).plan(GOALS[0], plan_id="plan_clamp")
    snapshot = _snapshot()
    snapshot["network"] = {"cloud_reachable": False, "last_cloud_ok_ms_ago": 9000.0, "rtt_ms_p99": 80.0}

    normal = route_plan(plan, _snapshot())[0]
    degraded = route_plan(plan, snapshot)[0]

    assert normal["outcome"] == "ALLOW"
    assert degraded["outcome"] == "ALLOW_CLAMPED"
    assert degraded["shipped_action"]["velocity_limit"] < normal["shipped_action"]["velocity_limit"]


def test_the_planner_cannot_choose_its_own_identity_or_provenance(no_telemetry):
    """Ids, timestamps and source are system-owned; the model's versions are discarded."""
    hijack = _proposal(
        proposal_id="p_evil",
        plan_id="plan_evil",
        issued_at="2099-01-01T00:00:00Z",
        source="edge_local",
    )
    plan = _planner({"proposals": [hijack]}).plan(GOALS[0], plan_id="plan_real")

    proposal = plan.proposals[0]
    assert proposal["proposal_id"] == "p_real_000"
    assert proposal["plan_id"] == "plan_real"
    assert proposal["issued_at"] == SNAPSHOT_TS
    assert proposal["source"] == "cloud_ultra"
    # And the envelope sees the system's timestamp, not the model's: no 73-year TTL.
    assert route_plan(plan, _snapshot())[0]["outcome"] == "ALLOW"


def test_a_plan_from_the_future_is_vetoed_for_clock_skew(no_telemetry):
    """A cloud clock ahead of the edge is not trusted: V9 rejects a plan issued after the
    snapshot it will be executed against, because it describes a world that has not happened."""
    plan = _planner({"proposals": [_proposal()]}).plan(GOALS[0], plan_id="plan_future")
    stale_snapshot = _snapshot()
    stale_snapshot["ts_wall"] = "2026-10-26T11:00:00Z"  # an hour before the proposal

    decision = route_plan(plan, stale_snapshot)[0]
    assert decision["outcome"] == "VETO"
    assert decision["rule_id"] == "V9_PLAN_MALFORMED"
    assert "future" in decision["rule_trace"][8]["detail"]


def test_the_prompt_does_not_leak_the_envelopes_parameters():
    """If the model knew the limits it would plan to them, and the demo would be circular."""
    ruleset = load_ruleset()
    prompt = SYSTEM_PROMPT + json.dumps(build_messages("move the block"), sort_keys=True)

    for name in (
        "max_velocity_mm_s",
        "max_force_n",
        "allowed_volume",
        "boundary_margin_mm",
        "camera_max_age_ms",
        "encoder_max_age_ms",
        "max_ttl_ms",
        "window_ms",
        "lookahead_ms",
        "swept_volume_inflation_mm",
    ):
        assert name not in prompt, f"{name} leaks into the planner prompt"

    # The numbers themselves must not appear either: a planner that sees "60" can plan to
    # exactly 60. Check every envelope-owned scalar in the active parameter set.
    from app.envelope.params import PARAMETER_OWNERS

    for rule_id, block in ruleset.normal.values.items():
        for name, value in block.items():
            if PARAMETER_OWNERS.get((rule_id, name)) != "envelope":
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            renderings = {str(value), str(float(value)), f"{float(value):.1f}"}
            assert not any(rendering in prompt for rendering in renderings), (rule_id, name, value)


def test_the_prompt_says_the_proposals_are_advisory_and_who_decides():
    lowered = SYSTEM_PROMPT.lower()
    assert "advisory" in lowered
    assert "envelope" in lowered
    assert "veto" in lowered
    # And that it is told not to plan to a number it was not given.
    assert "not told its limits" in lowered


def test_the_scene_is_passed_as_observation_not_as_limits():
    messages = build_messages("move it", {"keep_out_occupied": True, "end_effector": {"x": 10.0}})
    user = json.loads(messages[1]["content"])
    assert user["goal"] == "move it"
    assert user["observed"]["keep_out_occupied"] is True
    assert "max_velocity_mm_s" not in messages[1]["content"]


# ------------------------------------------------------------------ malformed output


#: Shapes that survive normalisation and are genuinely broken.
MALFORMED = {
    "missing target_pose": {k: v for k, v in _proposal().items() if k != "target_pose"},
    "unknown kind": _proposal(kind="teleport"),
    "string velocity": _proposal(velocity_limit="fast"),
    "empty object": {},
    "pose without axes": _proposal(target_pose={"frame": "world"}),
}


@pytest.mark.parametrize("case", sorted(MALFORMED), ids=sorted(MALFORMED))
def test_a_malformed_proposal_is_vetoed_by_v9_and_written_to_the_ledger(case, no_telemetry, tmp_path: Path):
    """The planner reports what it could not type; V9 refuses it; the ledger remembers."""
    plan = _planner({"proposals": [MALFORMED[case]]}).plan(GOALS[0], plan_id="plan_bad")

    assert plan.invalid, "the planner must notice the contract violation"
    index, problems = plan.invalid[0]
    assert index == 0 and problems

    ledger = tmp_path / "veto.jsonl"
    decisions = route_plan(plan, _snapshot(), destination=ledger)

    assert len(decisions) == 1
    decision = decisions[0]
    assert decision["outcome"] == "VETO"
    assert decision["rule_id"] == "V9_PLAN_MALFORMED"
    assert is_valid("EnvelopeDecision", decision), "a refusal must still be a legal record"

    lines = ledger.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["rule_id"] == "V9_PLAN_MALFORMED"
    # The rejected payload travels with the decision: a refusal with no evidence is unauditable.
    assert decision["intended_action_raw"] is not None


def test_missing_optional_fields_are_repaired_not_rejected(no_telemetry):
    """A gap the system can fill safely is filled; a gap it cannot fill is a V9.

    ``ttl_ms`` has a conservative default (a shorter life is always safe) and
    ``expected_end_state`` is advisory, so their absence is repairable. A missing pose is not:
    inventing coordinates would be inventing the thing the machine acts on.
    """
    plan = _planner(
        {"proposals": [{"kind": "move_to", "target_pose": {"x": 100.0, "y": 0.0, "z": 40.0}}]}
    ).plan(GOALS[0], plan_id="plan_repair")
    assert plan.invalid == [], "the repairable gaps must not be reported as contract failures"
    proposal = plan.proposals[0]
    assert proposal["ttl_ms"] == DEFAULT_TTL_MS
    assert proposal["velocity_limit"] > 0
    assert route_plan(plan, _snapshot())[0]["outcome"] == "ALLOW"


def test_a_plan_with_a_bad_proposal_still_keeps_the_good_ones_auditable(no_telemetry):
    """One unparseable step must not erase its neighbours' audit trail."""
    plan = _planner({"proposals": [_proposal(), MALFORMED["unknown kind"], _proposal()]}).plan(
        GOALS[0], plan_id="plan_mixed"
    )
    assert len(plan.invalid) == 1

    decisions = route_plan(plan, _snapshot())
    assert [d["outcome"] for d in decisions] == ["ALLOW", "VETO", "ALLOW"]


def test_non_json_output_is_a_planner_error_not_an_empty_plan():
    """A model outage must not look like 'the model proposed nothing'."""
    planner = UltraPlanner(FakeModel("I cannot help with that."), model="test-model")
    with pytest.raises(PlannerError, match="not JSON"):
        planner.plan(GOALS[0])


def test_json_that_is_not_a_plan_is_a_planner_error():
    with pytest.raises(PlannerError, match="expected an object"):
        parse_output('"just a string"')


def test_markdown_fences_are_tolerated_but_not_trusted():
    """Models wrap JSON in fences. Tolerate the wrapper, keep the strictness."""
    fenced = '```json\n{"proposals": [], "abstain_reason": "needs a depth sensor"}\n```'
    proposals, reason = parse_output(fenced)
    assert proposals == []
    assert reason == "needs a depth sensor"


def test_an_empty_goal_is_rejected_before_the_model_is_called():
    model = FakeModel({"proposals": []})
    with pytest.raises(ValueError, match="goal"):
        UltraPlanner(model).plan("   ")
    assert model.calls == []


# ------------------------------------------------------------------ abstention


def test_the_model_may_abstain_and_the_abstention_is_recorded():
    """Abstention is a result, not an exception: the caller must be able to log it."""
    plan = _planner({"proposals": [], "abstain_reason": "the goal needs a second axis"}).plan(
        GOALS[0], plan_id="plan_abstain"
    )
    assert plan.proposals == []
    assert plan.abstain_reason == "the goal needs a second axis"
    assert plan.ok is False
    assert route_plan(plan, _snapshot()) == []


def test_an_abstention_without_a_reason_still_says_something():
    proposals, reason = parse_output('{"proposals": [], "abstain": true}')
    assert proposals == []
    assert reason == "model abstained without giving a reason"


# ------------------------------------------------------------------ the ledger


def test_every_model_call_writes_telemetry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Protocol DoD: every model call during development is in the ledger, with tokens."""
    monkeypatch.setenv("REFLEX_TELEMETRY", "on")
    ledger = tmp_path / "ledger.jsonl"
    plan = UltraPlanner(
        FakeModel({"proposals": [_proposal()]}), now=lambda: SNAPSHOT_TS, ledger_destination=ledger
    ).plan(GOALS[0], plan_id="plan_logged")

    assert plan.ledger_id
    lines = [json.loads(line) for line in ledger.read_text(encoding="utf-8").strip().splitlines()]
    assert len(lines) == 1
    entry = lines[0]
    assert entry["stage"] == "plan"
    assert entry["kind"] == "chat.completions"
    assert entry["request"]["prompt_tokens"] == 1200
    assert entry["request"]["completion_tokens"] == 180
    assert entry["status"] == "ok"


def test_a_schema_violation_is_recorded_on_the_telemetry_line(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """How often the model produced unusable output is an aggregate worth having."""
    monkeypatch.setenv("REFLEX_TELEMETRY", "on")
    ledger = tmp_path / "ledger.jsonl"
    UltraPlanner(
        FakeModel({"proposals": [MALFORMED["empty object"]]}),
        now=lambda: SNAPSHOT_TS,
        ledger_destination=ledger,
    ).plan(GOALS[0], plan_id="plan_bad_log")
    entry = json.loads(ledger.read_text(encoding="utf-8").strip())
    assert entry["status"] == "schema_violation"


def test_planning_is_deterministic_given_a_fixed_clock(no_telemetry):
    """Re-planning the same goal at the same instant must produce byte-identical proposals."""
    payload = {"proposals": [_proposal()]}
    first = _planner(payload).plan(GOALS[0], plan_id="plan_det")
    second = _planner(payload).plan(GOALS[0], plan_id="plan_det")

    assert first.proposals == second.proposals
    # And the deterministic envelope agrees about them.
    ruleset = load_ruleset()
    assert (
        evaluate(ruleset, _snapshot(), first.proposals[0], "normal")["determinism_hash"]
        == evaluate(ruleset, _snapshot(), second.proposals[0], "normal")["determinism_hash"]
    )

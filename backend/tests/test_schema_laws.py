"""The schema's stated laws, as executable tests.

``schemas/core-schemas.json`` ends with an array called
``integrity_assertions_that_must_fail_validation``. Until now that array was prose:
nothing executed it, which is how a broken VETO branch survived review. Every entry
now has a fixture below, the array is checked for coverage, and the canonical *valid*
shapes are asserted too — a contract that rejects its own central record is worse than
one with no contract at all.
"""

from __future__ import annotations

import copy

import pytest
from jsonschema import ValidationError

from tests.factories import (
    action_proposal,
    allow_decision,
    clamped_decision,
    errors_for,
    ledger_line,
    replay_result,
    schema,
    sensor_snapshot,
    session_run,
    taxonomy_rule,
    validate,
    veto_decision,
)

# --------------------------------------------------------------------- valid shapes


@pytest.mark.parametrize(
    "defname,builder",
    [
        ("ActionProposal", action_proposal),
        ("SensorSnapshot", sensor_snapshot),
        ("EnvelopeDecision", veto_decision),
        ("EnvelopeDecision", allow_decision),
        ("EnvelopeDecision", clamped_decision),
        ("ReplayResult", replay_result),
        ("SessionRun", session_run),
        ("LedgerLine", ledger_line),
        ("Rule", taxonomy_rule),
    ],
)
def test_canonical_instance_is_valid(defname, builder):
    """The reference shape for each definition must validate. This is the regression
    test for the bug where ``shipped_action: null`` on a VETO was unrepresentable."""
    instance = builder()
    problems = errors_for(defname, instance)
    assert not problems, "\n".join(f"{list(e.path)}: {e.message}" for e in problems)


# ------------------------------------------------------ the must-fail assertion list

MUST_FAIL = {
    "veto_with_real_shipped_action": (
        "EnvelopeDecision",
        "EnvelopeDecision with outcome=VETO and a non-null, non-noop shipped_action",
        lambda: veto_decision(shipped_action=action_proposal()),
    ),
    "veto_without_rule_id": (
        "EnvelopeDecision",
        "EnvelopeDecision with outcome=VETO and rule_id=null",
        lambda: veto_decision(rule_id=None),
    ),
    "allow_with_rule_id": (
        "EnvelopeDecision",
        "EnvelopeDecision with outcome=ALLOW and rule_id set",
        lambda: allow_decision(rule_id="V2_KEEP_OUT_OCCUPIED"),
    ),
    "allow_with_clamp": (
        "EnvelopeDecision",
        "EnvelopeDecision with outcome=ALLOW and clamp_applied set",
        lambda: allow_decision(clamp_applied={"velocity": [80.0, 32.0], "rule_id": "V3_VELOCITY_LIMIT"}),
    ),
    "clamped_without_clamp": (
        "EnvelopeDecision",
        "EnvelopeDecision with outcome=ALLOW_CLAMPED and clamp_applied=null",
        lambda: clamped_decision(clamp_applied=None),
    ),
    "clamped_without_before_after": (
        "EnvelopeDecision",
        "EnvelopeDecision with outcome=ALLOW_CLAMPED and a clamp that records no before/after",
        lambda: clamped_decision(clamp_applied={"rule_id": "V3_VELOCITY_LIMIT"}),
    ),
    "proposal_without_ttl": (
        "ActionProposal",
        "ActionProposal with ttl_ms missing or ≤0",
        lambda: {k: v for k, v in action_proposal().items() if k != "ttl_ms"},
    ),
    "proposal_zero_ttl": (
        "ActionProposal",
        "ActionProposal with ttl_ms missing or ≤0",
        lambda: action_proposal(ttl_ms=0),
    ),
    "occupied_without_evidence": (
        "SensorSnapshot",
        "SensorSnapshot with keep_out_occupied=true and keep_out_evidence=null",
        lambda: sensor_snapshot(keep_out_occupied=True, keep_out_evidence=None),
    ),
    "replay_off_without_collision": (
        "ReplayResult",
        "ReplayResult with arm=envelope_off and the collision field omitted entirely",
        lambda: {k: v for k, v in replay_result().items() if k != "collision"},
    ),
    "collided_without_detail": (
        "ReplayResult",
        "ReplayResult with outcome=collided and collision=null",
        lambda: replay_result(outcome="collided", collision=None),
    ),
    "rule_with_one_parameter_set": (
        "Rule",
        "Rule with only one parameter set",
        lambda: {k: v for k, v in taxonomy_rule().items() if k != "parameter_set_degraded"},
    ),
    "decision_without_parameter_set": (
        "EnvelopeDecision",
        "EnvelopeDecision with no parameter_set (an ALLOW is meaningless without the limit set that allowed it)",
        lambda: {k: v for k, v in veto_decision().items() if k != "parameter_set"},
    ),
    "rejection_without_evidence": (
        "EnvelopeDecision",
        "EnvelopeDecision with intended_action=null and intended_action_raw=null",
        lambda: veto_decision(intended_action=None, intended_action_raw=None),
    ),
    "session_with_collision_shipped": (
        "SessionRun",
        "SessionRun with collisions_in_shipped > 0",
        lambda: session_run(collisions_in_shipped=3),
    ),
}


@pytest.mark.parametrize("case", sorted(MUST_FAIL), ids=sorted(MUST_FAIL))
def test_law_is_enforced(case):
    defname, _description, mutate = MUST_FAIL[case]
    with pytest.raises(ValidationError):
        validate(defname, mutate())


def test_every_stated_assertion_has_an_executable_fixture():
    """No assertion may live only in prose. Two entries are exempt by construction:
    the strictness rule (enforced by scripts/validate_taxonomy.py because JSON Schema
    cannot compare two sibling values) — see below."""
    stated = schema()["integrity_assertions_that_must_fail_validation"]
    covered = {description for _defname, description, _mutate in MUST_FAIL.values()}
    enforced_elsewhere = {
        "Rule whose parameter_set_degraded is less conservative than parameter_set_normal "
        "(checked by scripts/diff_parameter_sets.py, not by schema)"
    }
    uncovered = [s for s in stated if s not in covered and s not in enforced_elsewhere]
    assert not uncovered, f"assertions with no executable fixture: {uncovered}"


# --------------------------------------------------------- additional law coverage


def test_veto_may_ship_an_explicit_noop():
    """The schema allows an explicit no-op instead of null: a vetoed actuator still needs
    a well-formed 'do nothing' command to chew on."""
    validate("EnvelopeDecision", veto_decision(shipped_action=action_proposal(is_noop=True)))


def test_veto_may_not_ship_a_non_noop():
    with pytest.raises(ValidationError):
        validate("EnvelopeDecision", veto_decision(shipped_action=action_proposal(is_noop=False)))


def test_allow_clamped_requires_the_clamping_rule():
    with pytest.raises(ValidationError):
        validate("EnvelopeDecision", clamped_decision(clamp_applied={"velocity": [80.0, 32.0]}))


def test_sensor_snapshot_accepts_occupied_with_evidence():
    validate(
        "SensorSnapshot",
        sensor_snapshot(
            keep_out_occupied=True,
            keep_out_evidence={"method": "switch", "witnesses_agreeing": ["switch", "frame_diff"]},
        ),
    )


def test_session_counts_cannot_be_negative():
    with pytest.raises(ValidationError):
        validate(
            "SessionRun",
            session_run(
                counts={
                    "actions_planned": 10,
                    "actions_allowed": -1,
                    "actions_clamped": 0,
                    "actions_vetoed": 0,
                }
            ),
        )


def test_replay_off_clean_run_must_still_state_collision():
    """``collision: null`` is a claim ('nothing was hit'), not an omission."""
    validate("ReplayResult", replay_result(outcome="completed", collision=None))


def test_builders_are_not_shared_mutable_state():
    """Guards the test suite itself: a builder that returned a cached dict would let one
    test's mutation leak into another's fixture and produce false passes."""
    first = veto_decision()
    second = veto_decision()
    first["rules_evaluated"].append("V9_PLAN_MALFORMED")
    assert second["rules_evaluated"] == ["V1_EMERGENCY_STOP", "V2_KEEP_OUT_OCCUPIED"]
    copy.deepcopy(second)["mode"] = "degraded"
    assert second["mode"] == "normal"


def test_a_collision_under_the_envelope_is_representable():
    """The contract must not forbid the finding it exists to look for.

    An earlier draft made ``arm=envelope_on`` unable to report a collision, which would have
    turned "the shipped action still hit something" — the most valuable result the replay
    lane can produce — into a validation crash. Both arms now have to *state* the field;
    neither is allowed to hide behind it.
    """
    validate(
        "ReplayResult",
        replay_result(arm="envelope_on", outcome="collided", collision={"with": "block", "at_t_ms": 12.5}),
    )
    with pytest.raises(ValidationError):
        validate(
            "ReplayResult", {k: v for k, v in replay_result(arm="envelope_on").items() if k != "collision"}
        )

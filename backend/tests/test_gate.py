"""The evidence gate: three verdicts, and the line between the last two.

``app/gate/gate.py`` is NOT the safety envelope. It checks whether a claim is supported by
the text it cites and agrees with the rule's own parameters. Its verdict vocabulary
(PASS / FAIL / UNDETERMINED) is not the contract's ``Outcome`` (ALLOW / ALLOW_CLAMPED /
VETO) and the two are deliberately not interchangeable — a gate verdict is about evidence,
an envelope verdict is about motion.

Three tests here used to be ``xfail(strict=True)``. They are now passing tests, but not all
three assert what the marker claimed, because two of the three markers described behaviour
that would have been *wrong*. The reasoning is in ``docs/DISCREPANCIES.md`` and summarised
in the docstring of each replacement.
"""

from __future__ import annotations

import pytest

from app.gate.gate import (
    FAIL,
    MIN_QUOTE_CHARS,
    PASS,
    ROUTING_HUMAN,
    UNDETERMINED,
    VERDICTS,
    DeterministicGate,
)

SOURCE = "The intruder block is inside the keep-out volume at frame 42."

#: V2's real parameters, taken from the shipped calibration rather than typed by hand, so a
#: change to the profile fails here instead of making the gate silently laxer.
V2 = DeterministicGate.rule_parameters("V2_KEEP_OUT_OCCUPIED")
V3 = DeterministicGate.rule_parameters("V3_VELOCITY_LIMIT")


# ------------------------------------------------------------------ the original behaviour


def test_verbatim_quote_passes():
    result = DeterministicGate.evaluate("V2_KEEP_OUT_OCCUPIED", {}, "intruder block is inside", SOURCE)
    assert result["verdict"] == PASS
    assert result["verified_evidence"] == "intruder block is inside"


def test_missing_quote_is_undetermined():
    result = DeterministicGate.evaluate("V2_KEEP_OUT_OCCUPIED", {}, "", SOURCE)
    assert result["verdict"] == UNDETERMINED
    assert result["reason_code"] == "missing_quote"


def test_quoted_text_absent_from_source_fails():
    result = DeterministicGate.evaluate("V2_KEEP_OUT_OCCUPIED", {}, "the robot is clear", SOURCE)
    assert result["verdict"] == FAIL
    assert result["reason_code"] == "quote_not_in_source"


def test_result_vocabulary_does_not_match_the_contract():
    """Documents the drift the review found: three incompatible state vocabularies.

    The contract's Outcome is ALLOW / ALLOW_CLAMPED / VETO; the gate returns
    PASS / FAIL / UNDETERMINED, so a gate result cannot be stored in an
    EnvelopeDecision without a translation nobody has written.
    """
    outcomes = {"PASS", "FAIL", "UNDETERMINED"}
    contract = {"ALLOW", "ALLOW_CLAMPED", "VETO"}
    assert outcomes.isdisjoint(contract)


# ------------------------------------------------------------------ was xfail #1


def test_gate_must_not_pass_an_assertion_it_never_checked():
    """WAS XFAIL: "the gate ignores `assertion`, so a wildly unsafe claim can pass".

    The claim is now checked against the rule's own declared parameters. ``force_n`` is not
    a V2 parameter — V4 owns ``max_force_n`` — so asserting a 99,999 N force under V2 is a
    category error, and the gate says so instead of passing it through on the strength of an
    unrelated quote.
    """
    result = DeterministicGate.evaluate(
        "V2_KEEP_OUT_OCCUPIED", {"force_n": 99_999}, "intruder block is inside", SOURCE
    )
    assert result["verdict"] == FAIL
    assert result["reason_code"] == "assertion_unknown_parameter"
    assert "max_force_n" not in result["reason"].replace("does not declare", "")


def test_an_assertion_that_contradicts_the_rule_fails():
    """An in-scope parameter with the wrong value is a false claim, not a typo."""
    result = DeterministicGate.evaluate(
        "V3_VELOCITY_LIMIT",
        {"max_velocity_mm_s": V3["max_velocity_mm_s"] * 10},
        "intruder block is inside",
        SOURCE,
    )
    assert result["verdict"] == FAIL
    assert result["reason_code"] == "assertion_contradicts_rule"


def test_an_assertion_that_agrees_with_the_rule_passes():
    result = DeterministicGate.evaluate(
        "V3_VELOCITY_LIMIT",
        {"max_velocity_mm_s": V3["max_velocity_mm_s"]},
        "intruder block is inside",
        SOURCE,
    )
    assert result["verdict"] == PASS


def test_an_assertion_about_a_real_parameter_is_actually_checked():
    """Guard against the check being vacuous: every in-scope parameter must be comparable."""
    assert V2, "V2 declares no parameters, so this test would prove nothing"
    for name, declared in V2.items():
        if isinstance(declared, (int, float)) and not isinstance(declared, bool):
            wrong = DeterministicGate.evaluate(
                "V2_KEEP_OUT_OCCUPIED", {name: declared - 1}, "intruder block is inside", SOURCE
            )
            assert wrong["verdict"] == FAIL, name
            right = DeterministicGate.evaluate(
                "V2_KEEP_OUT_OCCUPIED", {name: declared}, "intruder block is inside", SOURCE
            )
            assert right["verdict"] == PASS, name


def test_true_does_not_equal_one():
    """``True == 1`` in Python; a boolean claim must not satisfy a numeric limit."""
    result = DeterministicGate.evaluate(
        "V9_PLAN_MALFORMED",
        {"max_ttl_ms": True},
        "intruder block is inside",
        SOURCE,
    )
    assert result["verdict"] == FAIL


# ------------------------------------------------------------------ was xfail #2


@pytest.mark.parametrize("quote", [" ", "   ", "\t\n", ".", "...", "-", "a", "ab"])
def test_gate_must_not_accept_a_vacuous_quote(quote):
    """WAS XFAIL: "whitespace/one-character quotes are accepted as grounding".

    A substring match on a single character is not evidence: it succeeds by chance in almost
    any document. Both whitespace-only and shorter-than-meaningful quotes now abstain.
    """
    result = DeterministicGate.evaluate("V1_EMERGENCY_STOP", {}, quote, "some source")
    assert result["verdict"] == UNDETERMINED
    assert result["reason_code"] in {"vacuous_quote", "missing_quote"}


def test_a_quote_exactly_at_the_minimum_length_is_still_judged_on_its_merits():
    """The threshold is a floor, not a bypass: length alone never yields PASS."""
    quote = "xyz"
    assert len(quote) == MIN_QUOTE_CHARS
    result = DeterministicGate.evaluate("V2_KEEP_OUT_OCCUPIED", {}, quote, SOURCE)
    assert result["verdict"] == FAIL, "a long-enough quote that is absent must still fail"


# ------------------------------------------------------------------ was xfail #3


def test_gate_must_not_accept_evidence_it_cannot_verify():
    """WAS XFAIL: "the README promises abstention on unverifiable evidence, code says FAIL".

    The *intent* was right and the *example* was wrong. No document in this repo promises
    that an absent quote becomes an abstention; ``docs/AGENT-DELEGATION-PROTOCOL.md`` §4.2
    says a claim must carry a citation **that resolves**, and the architecture note says the
    gate "rejects any finding whose citations do not resolve". A quote that is absent from a
    source we hold is a citation that failed to resolve: FAIL.

    What genuinely *cannot* be determined is whether the quote appears at all when there is
    no source to search. That is the abstention case, and it is tested here.
    """
    no_source = DeterministicGate.evaluate("V2_KEEP_OUT_OCCUPIED", {}, "not present", None)
    assert no_source["verdict"] == UNDETERMINED
    assert no_source["reason_code"] == "source_unavailable"

    blank_source = DeterministicGate.evaluate("V2_KEEP_OUT_OCCUPIED", {}, "not present", "   \n ")
    assert blank_source["verdict"] == UNDETERMINED

    # And the case the old marker asserted stays a FAIL, on purpose.
    absent = DeterministicGate.evaluate("V2_KEEP_OUT_OCCUPIED", {}, "not present", SOURCE)
    assert absent["verdict"] == FAIL
    assert absent["reason_code"] == "quote_not_in_source"


# ------------------------------------------------------------------ abstention is loud


@pytest.mark.parametrize(
    "args",
    [
        ("V2_KEEP_OUT_OCCUPIED", {}, "", SOURCE),
        ("V2_KEEP_OUT_OCCUPIED", {}, "   ", SOURCE),
        ("V2_KEEP_OUT_OCCUPIED", {}, "not present", None),
        ("V2_KEEP_OUT_OCCUPIED", "not-a-dict", "intruder", SOURCE),
    ],
    ids=["no-quote", "whitespace-quote", "no-source", "unreadable-assertion"],
)
def test_every_abstention_carries_a_reason_code_and_a_route(args):
    """An UNDETERMINED with no next step is a refusal pretending to be a verdict."""
    result = DeterministicGate.evaluate(*args)
    assert result["verdict"] == UNDETERMINED
    assert result["reason_code"]
    assert result["routing"] == ROUTING_HUMAN


def test_a_fail_and_a_pass_carry_no_routing():
    """Only abstention routes to a human: a rejection needs no reviewer to agree with it."""
    failed = DeterministicGate.evaluate("V2_KEEP_OUT_OCCUPIED", {}, "the robot is clear", SOURCE)
    assert "routing" not in failed
    passed = DeterministicGate.evaluate("V2_KEEP_OUT_OCCUPIED", {}, "intruder block is inside", SOURCE)
    assert "routing" not in passed


def test_verdict_vocabulary_is_closed():
    """A gate that can return a fourth state has no contract."""
    assert VERDICTS == {PASS, FAIL, UNDETERMINED}
    for args in [
        ("V2_KEEP_OUT_OCCUPIED", {}, "intruder block is inside", SOURCE),
        ("V2_KEEP_OUT_OCCUPIED", {}, "", SOURCE),
        ("V2_KEEP_OUT_OCCUPIED", {}, "nope", SOURCE),
    ]:
        assert DeterministicGate.evaluate(*args)["verdict"] in VERDICTS


def test_an_unknown_rule_cannot_silently_pass():
    """A rule id the calibration does not know must abstain, not bless the claim."""
    result = DeterministicGate.evaluate(
        "V99_NOT_A_RULE", {"anything": 1}, "some quote here", "some quote here"
    )
    assert result["verdict"] == UNDETERMINED


def test_the_gate_reads_the_shipped_calibration_not_a_second_copy():
    """The gate and the envelope must agree about limits, or a claim can pass the gate and
    be vetoed by the envelope for the same number."""
    from app.envelope import load_ruleset

    ruleset = load_ruleset()
    assert DeterministicGate.rule_parameters("V3_VELOCITY_LIMIT") == dict(
        ruleset.normal.values["V3_VELOCITY_LIMIT"]
    )

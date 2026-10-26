"""Characterisation tests for the current gate, plus the defects it must not hide.

``app/gate/gate.py`` is NOT the safety envelope. It checks whether an evidence quote
appears verbatim in a source document. It never loads the veto taxonomy, never looks at
the assertion it is given, and its verdict vocabulary does not match the contract's
``Outcome`` enum. Two tests below are marked ``xfail(strict=True)``: they describe the
intended behaviour, they fail today, and when Phase B fixes the gate they will start
passing — at which point the strict marker turns that into a test failure and forces
someone to delete the marker rather than leave a stale caveat in the repo.
"""

from __future__ import annotations

import pytest

from app.gate.gate import DeterministicGate

SOURCE = "The intruder block is inside the keep-out volume at frame 42."


def test_verbatim_quote_passes():
    result = DeterministicGate.evaluate("V2_KEEP_OUT_OCCUPIED", {}, "intruder block is inside", SOURCE)
    assert result["verdict"] == "PASS"
    assert result["verified_evidence"] == "intruder block is inside"


def test_missing_quote_is_undetermined():
    result = DeterministicGate.evaluate("V2_KEEP_OUT_OCCUPIED", {}, "", SOURCE)
    assert result["verdict"] == "UNDETERMINED"


def test_quoted_text_absent_from_source_fails():
    result = DeterministicGate.evaluate("V2_KEEP_OUT_OCCUPIED", {}, "the robot is clear", SOURCE)
    assert result["verdict"] == "FAIL"


def test_result_vocabulary_does_not_match_the_contract():
    """Documents the drift the review found: three incompatible state vocabularies.

    The contract's Outcome is ALLOW / ALLOW_CLAMPED / VETO; the gate returns
    PASS / FAIL / UNDETERMINED, so a gate result cannot be stored in an
    EnvelopeDecision without a translation nobody has written.
    """
    outcomes = {"PASS", "FAIL", "UNDETERMINED"}
    contract = {"ALLOW", "ALLOW_CLAMPED", "VETO"}
    assert outcomes.isdisjoint(contract)


@pytest.mark.xfail(
    strict=True, reason="Phase B: the gate ignores `assertion`, so a wildly unsafe claim can pass"
)
def test_gate_must_not_pass_an_assertion_it_never_checked():
    result = DeterministicGate.evaluate(
        "V2_KEEP_OUT_OCCUPIED", {"force_n": 99_999}, "intruder block is inside", SOURCE
    )
    assert result["verdict"] != "PASS"


@pytest.mark.xfail(strict=True, reason="Phase B: whitespace/one-character quotes are accepted as grounding")
def test_gate_must_not_accept_a_vacuous_quote():
    result = DeterministicGate.evaluate("V1_EMERGENCY_STOP", {}, " ", "some source")
    assert result["verdict"] != "PASS"


@pytest.mark.xfail(
    strict=True, reason="Phase B: the README promises abstention on unverifiable evidence, code says FAIL"
)
def test_unverifiable_evidence_should_abstain_not_fail():
    result = DeterministicGate.evaluate("V2_KEEP_OUT_OCCUPIED", {}, "not present", SOURCE)
    assert result["verdict"] == "UNDETERMINED"

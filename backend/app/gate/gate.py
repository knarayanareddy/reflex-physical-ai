"""The deterministic evidence gate.

This is **not** the safety envelope. ``app.envelope`` decides whether a machine moves;
this module decides whether a *claim* is supported by the text it cites. They are different
products of the same discipline: a rule that cannot be checked must not return a verdict.

Three verdicts, and the distinction between the last two is the whole point:

``PASS``
    Every asserted parameter agrees with the rule's own declared parameters, **and** the
    supporting quote appears verbatim in the source.

``FAIL``
    The claim was checked and did not survive. A quote that is absent from the document it
    cites is not "unknown" — it is a false citation, which is exactly what
    ``docs/AGENT-DELEGATION-PROTOCOL.md`` §4.2 calls out ("every claim carries >=1 citation
    object **that resolves**"). Likewise an assertion that names a parameter the rule does
    not govern is a category error, not a gap in our knowledge.

``UNDETERMINED``
    The gate cannot reach a verdict at all: no usable quote, no source text, a source it is
    not allowed to read. ``§4.5`` requires this to be loud, so every abstention carries a
    ``reason_code`` and a ``routing`` instruction — a caller that receives UNDETERMINED must
    escalate to a human, never treat it as permission.

The distinction matters because collapsing it loses information in the dangerous direction:
if fabrication looked like a gap, a model could launder an invented citation into "send for
review"; if a gap looked like fabrication, honest abstention would be reported as misconduct.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

PASS = "PASS"
FAIL = "FAIL"
UNDETERMINED = "UNDETERMINED"

VERDICTS = frozenset({PASS, FAIL, UNDETERMINED})

#: The shortest quote that can count as evidence.
#:
#: A one- or two-character string appears in almost any document by chance, so "verbatim
#: substring" stops meaning anything at that length. Three is not a statistically derived
#: number and does not pretend to be: it is the smallest length at which a human reviewer
#: would accept the match as evidence, and it is a named constant so a future change is a
#: decision rather than a drift.
MIN_QUOTE_CHARS = 3

#: Reason codes. Stable strings, because they are aggregated in the ledger and shown in the UI.
REASON_MISSING_QUOTE = "missing_quote"
REASON_VACUOUS_QUOTE = "vacuous_quote"
REASON_SOURCE_UNAVAILABLE = "source_unavailable"
REASON_QUOTE_NOT_IN_SOURCE = "quote_not_in_source"
REASON_ASSERTION_UNKNOWN_PARAMETER = "assertion_unknown_parameter"
REASON_ASSERTION_CONTRADICTS_RULE = "assertion_contradicts_rule"
REASON_ASSERTION_UNREADABLE = "assertion_unreadable"

#: What the caller must do with an abstention. UNDETERMINED is never permission.
ROUTING_HUMAN = "escalate_to_human_reviewer"
ROUTING_NO_ROUTE = None


def _result(
    rule_id: str,
    verdict: str,
    reason: str,
    *,
    reason_code: str | None = None,
    routing: str | None = ROUTING_NO_ROUTE,
    **extra: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"verdict": verdict, "reason": reason, "rule_id": rule_id}
    if reason_code is not None:
        payload["reason_code"] = reason_code
    if verdict == UNDETERMINED:
        # Enforced structurally: an abstention without a routing instruction is not an
        # abstention, it is a refusal with no next step.
        payload["routing"] = routing or ROUTING_HUMAN
    payload.update(extra)
    return payload


def _is_vacuous(quote: str) -> bool:
    """A quote made only of whitespace or punctuation is not evidence of anything."""
    stripped = quote.strip()
    if len(stripped) < MIN_QUOTE_CHARS:
        return True
    return not any(char.isalnum() for char in stripped)


def _values_agree(asserted: Any, declared: Any) -> bool:
    """Compare an asserted value with the rule's declared one.

    ``bool`` is compared as a bool: in Python ``True == 1``, and a claim of "enabled" must
    not silently equal a limit of 1.
    """
    if isinstance(asserted, bool) or isinstance(declared, bool):
        return isinstance(asserted, bool) and isinstance(declared, bool) and asserted == declared
    if isinstance(asserted, (int, float)) and isinstance(declared, (int, float)):
        return float(asserted) == float(declared)
    if isinstance(asserted, str) and isinstance(declared, str):
        return asserted == declared
    # Anything structured (a volume, a list) must match the declared value exactly.
    return asserted == declared


class DeterministicGate:
    """Check a claim against text and against the rule's own declared parameters."""

    @staticmethod
    def evaluate(
        rule_id: str,
        assertion: dict[str, Any],
        evidence_quote: str,
        raw_source: str | None,
        *,
        parameters: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return a verdict for ``assertion`` under ``rule_id``, supported by ``evidence_quote``.

        ``parameters`` is the rule's own parameter map (name -> declared value). Pass it when
        the caller already holds a ``Ruleset``; otherwise it is loaded from the active
        calibration profile. It is a parameter rather than a module global so that a test can
        exercise a rule with values that are not the shipped ones — and so nothing in this
        module can quietly read a different profile from the one the envelope is using.
        """
        declared = dict(parameters) if parameters is not None else DeterministicGate.rule_parameters(rule_id)

        # 1. The assertion must be a claim this rule is able to make.
        if not isinstance(assertion, Mapping):
            return _result(
                rule_id,
                UNDETERMINED,
                f"assertion is {type(assertion).__name__}, not an object; there is nothing to check",
                reason_code=REASON_ASSERTION_UNREADABLE,
            )

        unknown = sorted(key for key in assertion if key not in declared)
        if unknown and declared:
            # The rule exists and declares its parameters, so "is this a claim about this
            # rule?" is decidable. It is not one.
            return _result(
                rule_id,
                FAIL,
                f"assertion names parameter(s) {unknown} that {rule_id} does not declare "
                f"(it governs {sorted(declared)})",
                reason_code=REASON_ASSERTION_UNKNOWN_PARAMETER,
            )
        if unknown and not declared:
            # No parameters could be loaded for this rule, so we genuinely cannot tell
            # whether the assertion is in scope.
            return _result(
                rule_id,
                UNDETERMINED,
                f"no declared parameters are available for {rule_id}; cannot check {unknown}",
                reason_code=REASON_ASSERTION_UNREADABLE,
            )

        contradiction = sorted(
            f"{key}={value!r} but the rule declares {declared[key]!r}"
            for key, value in assertion.items()
            if not _values_agree(value, declared[key])
        )
        if contradiction:
            return _result(
                rule_id,
                FAIL,
                "assertion contradicts the rule's own parameters: " + "; ".join(contradiction),
                reason_code=REASON_ASSERTION_CONTRADICTS_RULE,
            )

        # 2. There must be a quote, and it must be capable of being evidence.
        if not isinstance(evidence_quote, str) or not evidence_quote.strip():
            return _result(
                rule_id,
                UNDETERMINED,
                "missing supporting evidence quote",
                reason_code=REASON_MISSING_QUOTE,
            )
        if _is_vacuous(evidence_quote):
            return _result(
                rule_id,
                UNDETERMINED,
                f"evidence quote {evidence_quote!r} is vacuous: fewer than {MIN_QUOTE_CHARS} "
                "non-punctuation characters cannot support a claim",
                reason_code=REASON_VACUOUS_QUOTE,
            )

        # 3. There must be a source to check it against.
        if not isinstance(raw_source, str) or not raw_source.strip():
            return _result(
                rule_id,
                UNDETERMINED,
                "no source text was supplied, so the quote cannot be checked",
                reason_code=REASON_SOURCE_UNAVAILABLE,
            )

        # 4. The check itself.
        if evidence_quote not in raw_source:
            return _result(
                rule_id,
                FAIL,
                "evidence quote does not appear verbatim in the source",
                reason_code=REASON_QUOTE_NOT_IN_SOURCE,
            )

        return _result(
            rule_id,
            PASS,
            "quote verified verbatim and assertion agrees with the rule's parameters",
            verified_evidence=evidence_quote,
        )

    @staticmethod
    def rule_parameters(rule_id: str) -> dict[str, Any]:
        """The rule's declared parameters from the active calibration profile.

        Deliberately lazy and degradation-tolerant: if the calibration cannot be loaded the
        gate still runs, and every assertion becomes UNDETERMINED rather than silently
        passing against an empty set of limits.
        """
        try:
            from app.envelope import load_ruleset
        except ImportError:  # pragma: no cover - the package is a hard dependency
            return {}
        try:
            ruleset = load_ruleset()
        except Exception:  # any calibration failure means "cannot check"
            return {}
        return dict(ruleset.normal.values.get(rule_id, {}))

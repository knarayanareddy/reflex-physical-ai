"""The deterministic edge safety envelope.

Import boundary: this package may use the standard library and itself, and nothing else.
``tests/test_envelope_purity.py`` walks the import graph and fails the build if an LLM
client, HTTP client, socket or other network-capable module appears — the claim that the
decision path cannot reach the network must be checkable, not merely asserted.
"""

from app.envelope.core import (
    EnvelopeInputError,
    canonical_json,
    determinism_hash,
    envelope_version,
    evaluate,
    resolve_mode,
)
from app.envelope.params import (
    CONSERVATIVE_DIRECTION,
    PARAMETER_OWNERS,
    ParameterError,
    Params,
    Rule,
    Ruleset,
    envelope_owned_parameters,
    load_ruleset,
)
from app.envelope.rules import (
    CLAMP,
    DEGRADE,
    PASS,
    PRECONDITIONS,
    PROPOSAL_KINDS,
    PROPOSAL_SOURCES,
    RULES,
    SENSOR_MISSING,
    SENSOR_STALE,
    SKIPPED_MODE,
    STOPPING_RESULTS,
    VETO,
    Context,
    RuleResult,
    network_degraded,
)

__all__ = [
    "CLAMP",
    "CONSERVATIVE_DIRECTION",
    "DEGRADE",
    "PARAMETER_OWNERS",
    "PASS",
    "PRECONDITIONS",
    "PROPOSAL_KINDS",
    "PROPOSAL_SOURCES",
    "RULES",
    "SENSOR_MISSING",
    "SENSOR_STALE",
    "SKIPPED_MODE",
    "STOPPING_RESULTS",
    "VETO",
    "Context",
    "EnvelopeInputError",
    "ParameterError",
    "Params",
    "Rule",
    "RuleResult",
    "Ruleset",
    "canonical_json",
    "determinism_hash",
    "envelope_owned_parameters",
    "envelope_version",
    "evaluate",
    "load_ruleset",
    "network_degraded",
    "resolve_mode",
]

"""Cloud planning. Untrusted by construction: nothing here can allow motion.

``app.plan.ultra`` turns a goal into ``ActionProposal``s; ``app.envelope`` decides what
happens to them. The import direction is one-way (plan -> envelope for evaluation, never
envelope -> plan), so the decision path cannot acquire a model client by accident.
"""

from app.plan.ultra import (
    DEFAULT_TTL_MS,
    PROMPT_VERSION,
    Completer,
    Completion,
    Plan,
    PlannerError,
    UltraPlanner,
    build_messages,
    contract_problems,
    openai_completer,
    parse_output,
    route_plan,
)

__all__ = [
    "DEFAULT_TTL_MS",
    "PROMPT_VERSION",
    "Completer",
    "Completion",
    "Plan",
    "PlannerError",
    "UltraPlanner",
    "build_messages",
    "contract_problems",
    "openai_completer",
    "parse_output",
    "route_plan",
]

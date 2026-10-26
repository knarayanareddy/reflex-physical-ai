"""Cloud planning with Nemotron Ultra: a goal in, ordered ``ActionProposal``s out.

The planner is the **untrusted** half of the system. It is allowed to be wrong, creative,
slow and intermittently unavailable; none of that is a safety property, because nothing it
produces moves anything until ``app.envelope`` has evaluated it. This module therefore does
one job: turn a goal into well-formed proposals, and be honest when it cannot.

Three design choices are load-bearing and are recorded in ``docs/DECISIONS.md``:

1. **The planner is not told the envelope's limits.** If the model knew ``max_velocity_mm_s``
   it would plan to that number, and the demonstration would collapse into "the model
   happens to stay inside lines we drew for it". The prompt describes the goal and the scene,
   never a threshold, and a test asserts that no calibration value appears in it.

2. **The model owns intent; the system owns identity and time.** ``proposal_id``,
   ``plan_id``, ``issued_at`` and ``source`` are stamped by code after parsing. A model that
   can choose its own timestamp can outlive its TTL, and one that can choose ``source`` can
   claim to be ``edge_local``. Its prose must never become a date or a provenance.

3. **Every proposal is schema-validated, and an invalid one is still routed.** Dropping a
   malformed proposal in the planner would make a bad plan invisible; instead it goes to the
   envelope, which VETOes it as V9 and writes the rejection to the veto ledger with the raw
   payload attached. The planner reports what it could not type; the envelope owns refusal.

Validation here is advisory bookkeeping (``Plan.invalid``), **not** a verdict. Anything a
caller does with this module that bypasses ``app.envelope`` is a bug in the caller.
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from app.config import settings
from app.contracts import validate_payload
from app.envelope import PRECONDITIONS, PROPOSAL_KINDS

PROMPT_VERSION = "plan.ultra.v1"
STAGE = "plan"

#: The default lifetime of one proposal, in ms. The envelope caps this (V9); the planner does
#: not, because it does not know the cap.
DEFAULT_TTL_MS = 500

#: The default velocity the planner asks for when the model omits one.
DEFAULT_VELOCITY_MM_S = 40.0


class PlannerError(RuntimeError):
    """The planner could not produce proposals at all (no key, transport failure, no JSON)."""


class Completer(Protocol):
    """The one capability the planner needs from the outside world.

    Injected rather than imported so the planner can be tested offline and so a different
    transport never becomes a reason to touch planning logic.
    """

    def __call__(self, messages: list[dict[str, str]], *, model: str) -> Completion: ...


@dataclass(frozen=True)
class Completion:
    """One raw model response, with the accounting needed for the telemetry ledger."""

    text: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0
    latency_ms: float = 0.0


@dataclass
class Plan:
    """The planner's output: proposals plus everything needed to audit them."""

    plan_id: str
    goal: str
    model: str
    issued_at: str
    proposals: list[dict[str, Any]] = field(default_factory=list)
    #: ``(index, problems)`` for every proposal the contract rejected. Not dropped: routed.
    invalid: list[tuple[int, list[str]]] = field(default_factory=list)
    #: Set when the model declined to plan. Empty proposals + a reason is a valid outcome.
    abstain_reason: str | None = None
    ledger_id: str | None = None
    prompt_version: str = PROMPT_VERSION

    @property
    def ok(self) -> bool:
        return bool(self.proposals) and not self.invalid and self.abstain_reason is None


SYSTEM_PROMPT = f"""You are the motion planner for a small robotic cell: a single-axis pusher on a
linear rail, working on a tabletop with a marked keep-out volume around a human workspace.

Answer with ONE JSON object and nothing else (no prose, no markdown fence):

{{"proposals": [ {{"kind": ..., "target_pose": {{"x": ..., "y": ..., "z": ...}},
  "velocity_limit": ..., "force_limit": ..., "ttl_ms": ..., "preconditions": [...],
  "expected_end_state": {{...}}}} ], "abstain_reason": null}}

Rules for the fields you fill in:
- "kind" is one of {sorted(PROPOSAL_KINDS)}.
- "target_pose" is in millimetres, world frame; x is along the rail.
- "velocity_limit" is millimetres per second; "force_limit" is newtons, or null if unknown.
- "ttl_ms" is how long this proposal stays valid, in milliseconds.
- "preconditions" may only contain: {sorted(PRECONDITIONS)}. Use them to say what must be
  true before your move is safe.
- "expected_end_state" is a small object describing what the world should look like after.

Your proposals are ADVISORY. A deterministic safety envelope runs on the edge device and
evaluates every proposal before anything moves. It can veto it outright or lower the limits
you ask for. It holds the authority; you do not. You are deliberately not told its limits,
and asking for them is not useful: plan the motion the goal needs, not the number you think
would be accepted.

Every proposal is re-stamped with a system id, a system timestamp and a system source. Your
"proposal_id", "plan_id", "issued_at" and "source" are discarded if you send them.

If the goal is ambiguous, under-specified, or describes something this one-axis pusher cannot
safely do, return {{"proposals": [], "abstain_reason": "<one sentence saying what you would
need to know>"}}. Abstaining is a correct answer and is preferred to a confident guess."""


def build_messages(goal: str, scene: Mapping[str, Any] | None = None) -> list[dict[str, str]]:
    """The full prompt. Pure, so a test can assert what the model is and is not told."""
    user: dict[str, Any] = {"goal": goal}
    if scene:
        # Only observed state. Never a limit, never a threshold.
        user["observed"] = scene
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(user, sort_keys=True)},
    ]


def _utc_now() -> str:
    """The system's notion of now, in the contract's format (second resolution, UTC)."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _strip_fence(text: str) -> str:
    """Models wrap JSON in markdown fences even when told not to. Tolerate it, don't trust it."""
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    body = stripped[3:]
    if body.startswith("json"):
        body = body[4:]
    end = body.rfind("```")
    return (body[:end] if end != -1 else body).strip()


def parse_output(text: str) -> tuple[list[Any], str | None]:
    """Extract ``(proposals, abstain_reason)`` from a raw model response.

    Raises ``PlannerError`` when there is no JSON at all: that is a transport/shape failure,
    not a plan, and pretending otherwise would turn a model outage into an empty plan.
    """
    try:
        payload = json.loads(_strip_fence(text))
    except json.JSONDecodeError as exc:
        raise PlannerError(f"model output is not JSON: {exc}: {text[:200]!r}") from exc

    if isinstance(payload, list):  # a bare array is a common near-miss
        return payload, None
    if not isinstance(payload, dict):
        raise PlannerError(f"model output is {type(payload).__name__}, expected an object")

    abstain = payload.get("abstain_reason")
    if abstain is not None and not isinstance(abstain, str):
        abstain = str(abstain)
    if abstain is None and payload.get("abstain") is True:
        abstain = "model abstained without giving a reason"

    proposals = payload.get("proposals")
    if proposals is None:
        proposals = []
    if not isinstance(proposals, list):
        raise PlannerError(f"'proposals' is {type(proposals).__name__}, expected a list")
    return proposals, abstain


def _normalise(raw: Any, *, plan_id: str, index: int, issued_at: str) -> dict[str, Any]:
    """Apply system-owned fields to one raw model proposal.

    The model's own ids, timestamp and source are overwritten, never merged: a proposal that
    can choose its own provenance can claim to have come from the edge, and one that can
    choose its own timestamp can outlive its TTL.
    """
    source = raw if isinstance(raw, Mapping) else {}
    proposal: dict[str, Any] = {key: value for key, value in source.items()}

    proposal["proposal_id"] = f"p_{plan_id.removeprefix('plan_')}_{index:03d}"
    proposal["plan_id"] = plan_id
    proposal["issued_at"] = issued_at
    proposal["source"] = "cloud_ultra"

    if not isinstance(proposal.get("kind"), str):
        proposal["kind"] = ""
    pose = proposal.get("target_pose")
    if not isinstance(pose, Mapping):
        proposal["target_pose"] = pose if pose is not None else {}
    if not isinstance(proposal.get("preconditions"), list):
        proposal["preconditions"] = []
    if not isinstance(proposal.get("expected_end_state"), Mapping):
        proposal["expected_end_state"] = {}
    if "velocity_limit" not in proposal:
        proposal["velocity_limit"] = DEFAULT_VELOCITY_MM_S
    if "force_limit" not in proposal:
        proposal["force_limit"] = None
    if "ttl_ms" not in proposal:
        proposal["ttl_ms"] = DEFAULT_TTL_MS
    proposal.setdefault("is_noop", False)
    return proposal


class UltraPlanner:
    """Goal -> proposals, via an injected completer (Nemotron Ultra by default)."""

    def __init__(
        self,
        completer: Completer | None = None,
        *,
        model: str | None = None,
        ledger_destination: Any = None,
        now: Callable[[], str] = _utc_now,
    ) -> None:
        self._completer = completer
        self.model = model or settings.model_ultra
        self._ledger_destination = ledger_destination
        self._now = now

    # ---------------------------------------------------------------- the one entry point

    def plan(self, goal: str, scene: Mapping[str, Any] | None = None, *, plan_id: str | None = None) -> Plan:
        """Propose a sequence of actions for ``goal``.

        Raises ``PlannerError`` on transport/shape failures. A model that declines returns a
        ``Plan`` with an ``abstain_reason`` and no proposals — an abstention is a result, not
        an exception, because the caller must be able to record it.
        """
        if not isinstance(goal, str) or not goal.strip():
            raise ValueError("goal must be a non-empty string")

        completer = self._completer or openai_completer()
        issued_at = self._now()
        plan_id = plan_id or f"plan_{uuid.uuid4().hex[:12]}"

        completion = completer(build_messages(goal, scene), model=self.model)
        raw_proposals, abstain_reason = parse_output(completion.text)

        proposals: list[dict[str, Any]] = []
        invalid: list[tuple[int, list[str]]] = []
        for index, raw in enumerate(raw_proposals):
            proposal = _normalise(raw, plan_id=plan_id, index=index, issued_at=issued_at)
            problems = contract_problems(proposal)
            if problems:
                invalid.append((index, problems))
            proposals.append(proposal)

        ledger_id = self._record(
            completion, goal=goal, plan_id=plan_id, status=ledger_status(invalid, abstain_reason)
        )

        return Plan(
            plan_id=plan_id,
            goal=goal,
            model=completion.model or self.model,
            issued_at=issued_at,
            proposals=proposals,
            invalid=invalid,
            abstain_reason=abstain_reason,
            ledger_id=ledger_id,
        )

    # ------------------------------------------------------------------------- accounting

    def _record(
        self,
        completion: Completion,
        *,
        goal: str,
        plan_id: str,
        status: str,
    ) -> str | None:
        """Every model call is a ledger line. Returns its id, or None if logging is off."""
        if self._ledger_destination is None and not _ledger_enabled():
            return None
        from app.tf.ledger import record_telemetry

        entry = record_telemetry(
            kind="chat.completions",
            stage=STAGE,
            model=completion.model or self.model,
            prompt_tokens=completion.prompt_tokens,
            completion_tokens=completion.completion_tokens,
            cached_tokens=completion.cached_tokens,
            latency_ms=completion.latency_ms,
            status=status,
            notes=f"{PROMPT_VERSION} plan_id={plan_id} goal={goal[:80]!r}",
            destination=self._ledger_destination,
        )
        return str(entry["id"])


def _ledger_enabled() -> bool:
    """Telemetry is on by default; tests opt out with ``REFLEX_TELEMETRY=off``."""
    import os

    return os.getenv("REFLEX_TELEMETRY", "on").strip().lower() not in {"off", "0", "false", "no"}


def contract_problems(proposal: Mapping[str, Any]) -> list[str]:
    """Contract violations for one proposal, as strings. Empty means it is well-formed."""
    try:
        validate_payload("ActionProposal", dict(proposal))
    except Exception as exc:  # ContractViolation, but keep this import-light
        return list(getattr(exc, "problems", [str(exc)]))
    return []


def ledger_status(invalid: Sequence[tuple[int, list[str]]], abstain_reason: str | None) -> str:
    """The ``LedgerLine.status`` for this call.

    ``schema_violation`` is recorded on the *call*, not hidden, so the ledger aggregates can
    show how often the model produced something unusable.
    """
    if abstain_reason is not None:
        return "ok"
    if invalid:
        return "schema_violation"
    return "ok"


# ---------------------------------------------------------------------- the real transport


def openai_completer(
    *,
    base_url: str | None = None,
    api_key: str | None = None,
    timeout: float = 60.0,
) -> Completer:
    """A completer backed by Token Factory's OpenAI-compatible endpoint.

    The key is required at construction time, so a missing credential fails at the call site
    that needs it rather than surfacing as an empty plan three layers deeper.

    TODO_VERIFY(plan-json-mode): ``docs/PLATFORM-CAPABILITIES.md`` lists a JSON/structured-output
    page at ``docs.tokenfactory.nebius.com/ai-models-inference/json``. It is not reachable from
    the build sandbox, so this uses a plain ``chat.completions.create`` and parses the text.
    Confirm whether ``response_format={"type": "json_object"}`` (or a ``json_schema`` variant)
    is supported before relying on it; see reports/D-T11-T26.TASK_REPORT.md.
    """
    from openai import OpenAI

    resolved_key = api_key or settings.require_nebius_credentials()
    client = OpenAI(
        base_url=base_url or settings.nebius_base_url,
        api_key=resolved_key,
        timeout=timeout,
    )

    def complete(messages: list[dict[str, str]], *, model: str) -> Completion:
        started = time.perf_counter()
        try:
            response = client.chat.completions.create(model=model, messages=messages)  # type: ignore[arg-type]
        except Exception as exc:  # re-raised as one typed failure: no raw provider error escapes
            raise PlannerError(f"model call failed: {exc}") from exc
        latency_ms = (time.perf_counter() - started) * 1000.0

        choice = response.choices[0] if response.choices else None
        text = (choice.message.content if choice and choice.message else None) or ""
        usage = getattr(response, "usage", None)
        return Completion(
            text=text,
            model=getattr(response, "model", None) or model,
            prompt_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
            completion_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
            cached_tokens=int(
                getattr(getattr(usage, "prompt_tokens_details", None), "cached_tokens", 0) or 0
            ),
            latency_ms=latency_ms,
        )

    return complete


# ------------------------------------------------------------------- routing to the envelope


def route_plan(
    plan: Plan,
    snapshot: Mapping[str, Any],
    *,
    mode: str = "normal",
    destination: Any = None,
    ruleset: Any = None,
) -> list[dict[str, Any]]:
    """Send every proposal — valid or not — through the envelope and record each decision.

    This is the only path from a plan to motion, and it goes through ``app.envelope``. Invalid
    proposals are routed deliberately: V9 must be the thing that refuses them, in the ledger,
    with the raw payload attached.
    """
    from app.decision_ledger import record_decision
    from app.envelope import evaluate, load_ruleset

    active = ruleset or load_ruleset()
    decisions = []
    for proposal in plan.proposals:
        decision = evaluate(active, snapshot, proposal, mode)
        record_decision(decision, destination)
        decisions.append(decision)
    return decisions

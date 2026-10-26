"""The ten veto rules. Pure functions of (snapshot, proposal, parameters, mode).

Nothing in this module reads a clock, generates randomness, opens a socket or calls a
model. Every result is a deterministic function of its inputs, which is what makes the
``determinism_hash`` meaningful — see ``tests/test_envelope_determinism.py``.

Rule semantics are documented per function. Where the frozen taxonomy is ambiguous, the
resolution is recorded in ``docs/DECISIONS.md`` and asserted by a test.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.envelope.params import AXES, Params

# Result vocabulary. Must stay a subset of $defs/EnvelopeDecision.rule_trace[].result.
PASS = "PASS"
VETO = "VETO"
CLAMP = "CLAMP"
DEGRADE = "DEGRADE"
SKIPPED_MODE = "SKIPPED_MODE"
SENSOR_MISSING = "SENSOR_MISSING"
SENSOR_STALE = "SENSOR_STALE"

#: Results that stop motion. SENSOR_MISSING and SENSOR_STALE are *abstentions*: the
#: envelope could not establish safety, so it refuses to move. At the actuator, "I don't
#: know" and "unsafe" must be the same thing.
STOPPING_RESULTS = frozenset({VETO, SENSOR_MISSING, SENSOR_STALE})


@dataclass(frozen=True)
class RuleResult:
    """One rule's verdict. ``result`` is one of the constants above."""

    result: str
    detail: str
    clamp: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class Context:
    """Everything a rule may read. No clock, no I/O, no global state."""

    snapshot: Mapping[str, Any]
    proposal: Mapping[str, Any]
    params: Params
    policy: Params  # always the normal set: policy ceilings are mode-independent
    parameter_set: str
    requested_mode: str
    resolved_mode: str


# --------------------------------------------------------------- preconditions (V9)


def _relay_closed(snapshot: Mapping[str, Any]) -> bool:
    return snapshot.get("relay_state") is True


def _keep_out_clear(snapshot: Mapping[str, Any]) -> bool:
    return snapshot.get("keep_out_occupied") is False


def _cloud_reachable(snapshot: Mapping[str, Any]) -> bool:
    return bool((snapshot.get("network") or {}).get("cloud_reachable"))


def _e_stop_released(snapshot: Mapping[str, Any]) -> bool:
    return snapshot.get("e_stop_asserted") is not True


def _limit_switches_clear(snapshot: Mapping[str, Any]) -> bool:
    switches = snapshot.get("limit_switches") or {}
    return not switches.get("min") and not switches.get("max")


#: The only precondition strings the envelope can verify. Anything else is rejected
#: rather than assumed: an unverifiable precondition is an unverified plan.
PRECONDITIONS: dict[str, Callable[[Mapping[str, Any]], bool]] = {
    "relay_closed": _relay_closed,
    "keep_out_clear": _keep_out_clear,
    "cloud_reachable": _cloud_reachable,
    "e_stop_released": _e_stop_released,
    "limit_switches_clear": _limit_switches_clear,
}


# ------------------------------------------------------------------------- helpers


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _number(value: object) -> float | None:
    """``value`` as a float, or None when it is not a real number.

    ``bool`` is deliberately excluded: ``True`` must not silently become 1.0 mm/s.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def network_degraded(snapshot: Mapping[str, Any], window_ms: float) -> bool:
    """V8's predicate, in one place: mode resolution and the rule must never disagree."""
    network = snapshot.get("network") or {}
    if network.get("cloud_reachable") is not False:
        return False
    age = _number(network.get("last_cloud_ok_ms_ago"))
    if age is None:
        # Unreachable with an unknown outage duration: assume degraded. Never fail open.
        return True
    return age > float(window_ms)


def _parse_ts(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


# --------------------------------------------------------------------------- rules


def rule_v1_emergency_stop(ctx: Context) -> RuleResult:
    """V1 — e-stop asserted, or the interlock relay already open.

    A binary interlock. It outranks everything and has no parameters.

    The electrical state is read, never inferred: an absent ``relay_state`` is an abstention
    and not a closed relay, because the whole point of an interlock is that its state is
    known. A missing value must never be rounded to the safe-looking one.
    """
    asserted = ctx.snapshot.get("e_stop_asserted")
    relay = ctx.snapshot.get("relay_state")

    if asserted is True:
        return RuleResult(VETO, "e-stop asserted")
    if relay is False:
        return RuleResult(VETO, "interlock relay is open: motion is physically impossible")
    if asserted is not False:
        return RuleResult(SENSOR_MISSING, f"e_stop_asserted is {asserted!r}; interlock state unknown")
    if relay is not True:
        return RuleResult(SENSOR_MISSING, f"relay_state is {relay!r}; cannot confirm the interlock is closed")
    return RuleResult(PASS, "e-stop released and relay closed")


def rule_v2_keep_out_occupied(ctx: Context) -> RuleResult:
    """V2 — something is inside the marked keep-out volume.

    Two independent duties:

    1. If the detector reports occupancy, veto. The parameter set is the *detector's*
       business (blob size, confidence, consecutive frames); the envelope does not
       second-guess a positive.
    2. If the keep-out volume has no working detector, **abstain**. A cell that cannot
       see its primary hazard must not move, so missing evidence is a stop, not a pass.
    """
    occupied = ctx.snapshot.get("keep_out_occupied")
    evidence = ctx.snapshot.get("keep_out_evidence")

    if occupied is True:
        if not isinstance(evidence, Mapping):
            return RuleResult(VETO, "keep-out occupied with no evidence recorded (fail-safe)")
        method = evidence.get("method")
        confidence = evidence.get("confidence")
        witnesses = evidence.get("witnesses_agreeing") or []
        suffix = f", witnesses={list(witnesses)}" if witnesses else ""
        return RuleResult(VETO, f"keep-out occupied (method={method}, confidence={confidence}{suffix})")

    if occupied is not False:
        return RuleResult(SENSOR_MISSING, f"keep_out_occupied is {occupied!r}; occupancy unknown")

    if not isinstance(evidence, Mapping) or evidence.get("method") in (None, "none"):
        return RuleResult(
            SENSOR_MISSING,
            "no working keep-out detector: the envelope cannot prove the volume is clear",
        )

    return RuleResult(PASS, f"keep-out clear per {evidence.get('method')}")


def rule_v3_velocity_limit(ctx: Context) -> RuleResult:
    """V3 — the commanded velocity exceeds this mode's ceiling: clamp, don't stop.

    Clamping is a partial refusal: the action proceeds slower. A value that is not a
    positive number is left for V9 to reject rather than guessed at here.
    """
    limit = ctx.params.number("V3_VELOCITY_LIMIT", "max_velocity_mm_s")
    requested = _number(ctx.proposal.get("velocity_limit"))
    if requested is None or requested <= 0:
        return RuleResult(PASS, f"velocity_limit {requested!r} is not a positive number; V9 decides")

    requested_f = requested
    if requested_f > limit:
        return RuleResult(
            CLAMP,
            f"velocity {requested_f} -> {limit} mm/s ({ctx.parameter_set} ceiling)",
            clamp={"velocity": [requested_f, limit]},
        )
    return RuleResult(PASS, f"velocity {requested_f} <= {limit} mm/s")


def rule_v4_force_limit(ctx: Context) -> RuleResult:
    """V4 — the estimated contact force exceeds the limit.

    The snapshot field is deliberately named ``force_estimate``: derived from stall
    current it is an estimate, and the trace says so. No estimate at all is an
    abstention, because a force limit you cannot check is not a force limit.
    """
    limit = ctx.params.number("V4_FORCE_LIMIT", "max_force_n")
    force = ctx.snapshot.get("force_estimate")
    method = ctx.snapshot.get("force_estimate_method")

    if force is None or method in (None, "none"):
        return RuleResult(
            SENSOR_MISSING,
            f"no force estimate (method={method!r}); the {limit} N limit cannot be verified",
        )
    if not _is_number(force):
        return RuleResult(SENSOR_MISSING, f"force_estimate {force!r} is not numeric")
    if float(force) > limit:
        return RuleResult(VETO, f"force estimate {float(force)} N > {limit} N (method={method})")
    return RuleResult(PASS, f"force estimate {float(force)} N <= {limit} N (method={method})")


def rule_v5_workspace_bound(ctx: Context) -> RuleResult:
    """V5 — the commanded pose leaves the allowed volume: clamp it back to the boundary.

    The margin shrinks the box, so a degraded mode with a larger margin produces a
    strictly smaller reachable volume.
    """
    box = ctx.params.mapping("V5_WORKSPACE_BOUND", "allowed_volume")
    margin = ctx.params.number("V5_WORKSPACE_BOUND", "boundary_margin_mm")
    pose = ctx.proposal.get("target_pose")

    if not isinstance(pose, Mapping):
        return RuleResult(PASS, "target_pose missing; V9 decides")

    clamped: dict[str, float] = {}
    before: dict[str, float] = {}
    for axis in AXES:
        value = _number(pose.get(axis))
        if value is None:
            return RuleResult(PASS, f"target_pose.{axis}={pose.get(axis)!r} is not numeric; V9 decides")
        low, high = (float(b) for b in box[axis])
        low, high = low + margin, high - margin
        if low >= high:
            return RuleResult(
                VETO, f"workspace on {axis} is [{low}, {high}] after a {margin} mm margin: nothing is safe"
            )
        bounded = min(max(value, low), high)
        if bounded != value:
            before[axis] = value
            clamped[axis] = bounded

    if not clamped:
        return RuleResult(PASS, "target pose inside the allowed volume")

    after = {axis: float(pose[axis]) for axis in AXES}
    after.update(clamped)
    after["frame"] = pose.get("frame", "world")
    moved = ", ".join(f"{axis}: {before[axis]} -> {clamped[axis]}" for axis in clamped)
    return RuleResult(
        CLAMP,
        f"target pose clamped to the {margin} mm-inset boundary ({moved})",
        clamp={"target_pose": {"before": {axis: float(pose[axis]) for axis in AXES}, "after": after}},
    )


def rule_v6_collision_predicted(ctx: Context) -> RuleResult:
    """V6 — the swept volume of the commanded move intersects a known object.

    Single-axis geometry: the corridor is the segment from the current end-effector
    position to the commanded target, inflated by ``swept_volume_inflation_mm``, and
    extended by the distance the arm could still travel within ``lookahead_ms`` at its
    measured speed. Obstacles come from *advisory* perception — a model may add evidence
    that stops the machine; it may never remove it (see the model-cannot-clear-a-veto test).
    """
    lookahead = ctx.params.number("V6_COLLISION_PREDICTED", "lookahead_ms")
    inflation = ctx.params.number("V6_COLLISION_PREDICTED", "swept_volume_inflation_mm")

    kind = ctx.proposal.get("kind")
    if kind == "wait":
        return RuleResult(PASS, "no motion commanded (kind=wait)")

    end_effector = ctx.snapshot.get("end_effector") or {}
    target = ctx.proposal.get("target_pose") or {}
    x0f, x1f = _number(end_effector.get("x")), _number(target.get("x"))
    if x0f is None or x1f is None:
        return RuleResult(PASS, "end-effector or target x missing; V7/V9 decide")

    speed = _number(end_effector.get("velocity_mm_s"))
    travel = abs(speed) * lookahead / 1000.0 if speed is not None else 0.0
    direction = 0 if x1f == x0f else (1 if x1f > x0f else -1)
    lo = min(x0f, x1f) - inflation - (travel if direction < 0 else 0.0)
    hi = max(x0f, x1f) + inflation + (travel if direction > 0 else 0.0)

    y0f, z0f = _number(end_effector.get("y", 0.0)), _number(end_effector.get("z", 0.0))
    if y0f is None or z0f is None:
        return RuleResult(PASS, "end-effector y/z unknown; corridor undefined")

    advisory = ctx.snapshot.get("advisory_perception") or {}
    poses = advisory.get("object_poses") or []
    if not isinstance(poses, list):
        return RuleResult(PASS, "advisory object_poses is not a list; ignored")

    ignored = 0
    for index, obstacle in enumerate(poses):
        if not isinstance(obstacle, Mapping):
            ignored += 1
            continue
        ox, oy, oz = _number(obstacle.get("x")), _number(obstacle.get("y")), _number(obstacle.get("z"))
        radius = _number(obstacle.get("radius_mm", 0.0))
        if ox is None or oy is None or oz is None or radius is None:
            ignored += 1
            continue
        radius = abs(radius)
        lateral = inflation + radius
        if abs(oy - y0f) > lateral or abs(oz - z0f) > lateral:
            continue
        if ox + radius < lo or ox - radius > hi:
            continue
        name = obstacle.get("id") or obstacle.get("object_id") or f"object[{index}]"
        return RuleResult(
            VETO,
            f"swept corridor x=[{lo:.1f}, {hi:.1f}] intersects {name!r} at x={ox:.1f} "
            f"(radius {radius:.1f}, inflation {inflation:.1f})",
        )

    suffix = f"; {ignored} advisory pose(s) unusable" if ignored else ""
    return RuleResult(PASS, f"swept corridor x=[{lo:.1f}, {hi:.1f}] clear{suffix}")


def rule_v7_sensor_stale(ctx: Context) -> RuleResult:
    """V7 — a required sensor is missing or older than its freshness window.

    Ages come from the snapshot, so this needs no history and stays deterministic. Both
    windows shrink in degraded mode: less confidence in the world model means a shorter
    tolerance for staleness, not a longer one.
    """
    camera_window = ctx.params.number("V7_SENSOR_STALE", "camera_max_age_ms")
    encoder_window = ctx.params.number("V7_SENSOR_STALE", "encoder_max_age_ms")

    camera = ctx.snapshot.get("camera")
    if not isinstance(camera, Mapping):
        return RuleResult(SENSOR_MISSING, "no camera block in the snapshot")
    camera_age = _number(camera.get("age_ms"))
    if camera_age is None:
        return RuleResult(SENSOR_MISSING, f"camera age {camera.get('age_ms')!r} is not a number")

    end_effector = ctx.snapshot.get("end_effector") or {}
    encoder_age = _number(end_effector.get("age_ms"))
    if encoder_age is None:
        return RuleResult(SENSOR_MISSING, f"encoder age {end_effector.get('age_ms')!r} is not a number")

    stale = []
    if camera_age > camera_window:
        stale.append(f"camera {camera_age} ms > {camera_window} ms")
    if encoder_age > encoder_window:
        stale.append(f"encoder {encoder_age} ms > {encoder_window} ms")
    if stale:
        return RuleResult(SENSOR_STALE, "; ".join(stale))
    return RuleResult(
        PASS,
        f"camera {camera_age} ms <= {camera_window} ms, encoder {encoder_age} ms <= {encoder_window} ms",
    )


def rule_v8_network_degraded(ctx: Context) -> RuleResult:
    """V8 — the cloud is unreachable beyond the debounce window: degrade, never fail open.

    This rule does not stop the machine. It reports the transition; the parameter set was
    already resolved before evaluation (see ``core.resolve_mode``) so that every other rule
    ran with the stricter values.
    """
    window = ctx.params.number("V8_NETWORK_DEGRADED", "window_ms")
    network = ctx.snapshot.get("network") or {}
    reachable = network.get("cloud_reachable")
    age = network.get("last_cloud_ok_ms_ago")

    if reachable is False and network_degraded(ctx.snapshot, window):
        return RuleResult(
            DEGRADE, f"cloud unreachable for {age!r} ms (> {window} ms): stricter parameters in force"
        )
    if reachable is False:
        return RuleResult(PASS, f"cloud unreachable for {age!r} ms, inside the {window} ms debounce window")
    return RuleResult(PASS, "cloud reachable")


def rule_v9_plan_malformed(ctx: Context) -> RuleResult:
    """V9 — the proposal cannot be executed as issued.

    Checks, in order: structural validity, TTL ceiling, expiry against the snapshot's own
    wall clock (never the process clock), limit requests beyond the envelope's policy
    ceiling, and whether every declared precondition is one the envelope can verify.

    Satisfaction of a precondition is deliberately NOT checked here. Each verifiable
    precondition names a fact that another rule owns and reports with its own evidence
    (``relay_closed`` / ``e_stop_released`` -> V1, ``keep_out_clear`` -> V2, ``cloud_reachable``
    -> V8, ``limit_switches_clear`` -> V5). Checking truth in two places would double-count the
    same fact in the trace and would blame "malformed plan" for a well-formed plan that met a
    world it did not expect. It would also make an outage veto every plan that declared
    ``cloud_reachable`` - precisely the fail-open V8 exists to prevent.

    The policy ceiling is the **normal** parameter set on purpose. A planner is entitled to
    ask for up to the normal ceiling; a request beyond that is untrusted and rejected. A
    request that was legal when it was made but exceeds the *current* mode's ceiling is
    clamped by V3 instead — rejecting a legal plan would be a denial of service on the cell.
    """
    proposal = ctx.proposal
    problems: list[str] = []

    velocity = _number(proposal.get("velocity_limit"))
    if velocity is None or velocity <= 0:
        problems.append(f"velocity_limit {proposal.get('velocity_limit')!r} is not a positive number")
    raw_force = proposal.get("force_limit")
    force = _number(raw_force)
    if raw_force is not None and (force is None or force <= 0):
        problems.append(f"force_limit {raw_force!r} is neither null nor a positive number")

    ttl = proposal.get("ttl_ms")
    max_ttl = ctx.params.number("V9_PLAN_MALFORMED", "max_ttl_ms")
    if not isinstance(ttl, int) or isinstance(ttl, bool) or ttl <= 0:
        problems.append(f"ttl_ms {ttl!r} is not a positive integer")
    elif ttl > max_ttl:
        problems.append(f"ttl_ms {ttl} exceeds the {max_ttl} ms ceiling")

    issued = _parse_ts(proposal.get("issued_at"))
    now = _parse_ts(ctx.snapshot.get("ts_wall"))
    if issued is None:
        problems.append("issued_at is missing or not ISO-8601")
    elif now is None:
        problems.append("snapshot ts_wall is missing or not ISO-8601")
    elif isinstance(ttl, int) and not isinstance(ttl, bool) and ttl > 0:
        age_ms = (now - issued).total_seconds() * 1000.0
        if age_ms > ttl:
            problems.append(f"proposal expired {age_ms - ttl:.0f} ms ago (age {age_ms:.0f} ms, ttl {ttl} ms)")
        if age_ms < -1000.0:
            problems.append(f"proposal issued {-age_ms:.0f} ms in the future relative to the snapshot")

    allow_above = ctx.policy.flag("V9_PLAN_MALFORMED", "allow_limit_requests_above_ceiling")
    if not allow_above:
        policy_ceiling = ctx.policy.number("V3_VELOCITY_LIMIT", "max_velocity_mm_s")
        if velocity is not None and velocity > policy_ceiling:
            problems.append(f"velocity_limit {velocity} exceeds the {policy_ceiling} mm/s policy ceiling")
        policy_force = ctx.policy.number("V4_FORCE_LIMIT", "max_force_n")
        if force is not None and force > policy_force:
            problems.append(f"force_limit {force} exceeds the {policy_force} N policy ceiling")

    for precondition in proposal.get("preconditions") or []:
        # An unverifiable precondition is an unverified plan: the planner is asserting a
        # belief about the world that the envelope cannot falsify, so it cannot be trusted.
        if precondition not in PRECONDITIONS:
            problems.append(f"precondition {precondition!r} cannot be verified")

    if problems:
        return RuleResult(VETO, "; ".join(problems))
    return RuleResult(PASS, "structure, ttl, ceiling and verifiable preconditions are valid")


def rule_v10_human_presence(ctx: Context) -> RuleResult:
    """V10 — a person (or an unexpected object) is in the cell.

    Both signals are nullable in the contract, and ``None`` means "the detector did not
    say". For a human-collaborative cell that is an abstention, not a clear.
    """
    human = ctx.snapshot.get("human_presence_detected")
    intruder = ctx.snapshot.get("intruder_present")

    if human is True:
        return RuleResult(VETO, "human presence detected in the cell")
    if intruder is True:
        return RuleResult(VETO, "unexpected object (intruder) present in the cell")
    if human is None and intruder is None:
        return RuleResult(SENSOR_MISSING, "no human-presence signal in the snapshot")
    return RuleResult(PASS, f"no human presence (human={human}, intruder={intruder})")


RULES: dict[str, Callable[[Context], RuleResult]] = {
    "V1_EMERGENCY_STOP": rule_v1_emergency_stop,
    "V2_KEEP_OUT_OCCUPIED": rule_v2_keep_out_occupied,
    "V3_VELOCITY_LIMIT": rule_v3_velocity_limit,
    "V4_FORCE_LIMIT": rule_v4_force_limit,
    "V5_WORKSPACE_BOUND": rule_v5_workspace_bound,
    "V6_COLLISION_PREDICTED": rule_v6_collision_predicted,
    "V7_SENSOR_STALE": rule_v7_sensor_stale,
    "V8_NETWORK_DEGRADED": rule_v8_network_degraded,
    "V9_PLAN_MALFORMED": rule_v9_plan_malformed,
    "V10_HUMAN_PRESENCE": rule_v10_human_presence,
}

"""Parameter resolution: the taxonomy supplies structure, the calibration supplies values.

Why two files:

* ``data/veto-taxonomy.json`` is the frozen **contract**: which rules exist, their
  priority, severity and the shape of their parameters. It deliberately still contains
  ``TODO_MEASURE`` placeholders, because no rig has been measured yet.
* ``data/calibration/rig-limits.json`` is the **measurement store**: numeric values for a
  named rig profile, each with a provenance entry.

The envelope therefore never reads a number out of the taxonomy. It resolves every value
from the active calibration profile and refuses to evaluate if one is missing. That is
what makes "every parameter traces to a measurement" a property of the running system
rather than a claim in a README.

A profile whose provenance is not ``measurement`` forces ``mode="simulation"``: decisions
computed from unmeasured numbers must never be presentable as hardware decisions.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
TAXONOMY_PATH = REPO_ROOT / "data" / "veto-taxonomy.json"
CALIBRATION_PATH = REPO_ROOT / "data" / "calibration" / "rig-limits.json"

MODES = ("normal", "degraded", "simulation")
PARAMETER_SETS = ("normal", "degraded")

# Which stage owns each parameter. The envelope must not silently consume a value that
# belongs to the detector or the driver, or the parameter becomes decoration.
PARAMETER_OWNERS: dict[tuple[str, str], str] = {
    ("V2_KEEP_OUT_OCCUPIED", "detection_min_confidence"): "detector",
    ("V2_KEEP_OUT_OCCUPIED", "detection_method_priority"): "detector",
    ("V2_KEEP_OUT_OCCUPIED", "min_blob_area_px"): "detector",
    ("V2_KEEP_OUT_OCCUPIED", "consecutive_frames_required"): "detector",
    ("V3_VELOCITY_LIMIT", "max_velocity_mm_s"): "envelope",
    ("V3_VELOCITY_LIMIT", "max_accel_mm_s2"): "driver",
    ("V4_FORCE_LIMIT", "max_force_n"): "envelope",
    ("V4_FORCE_LIMIT", "force_estimate_method"): "detector",
    ("V5_WORKSPACE_BOUND", "allowed_volume"): "envelope",
    ("V5_WORKSPACE_BOUND", "boundary_margin_mm"): "envelope",
    ("V6_COLLISION_PREDICTED", "lookahead_ms"): "envelope",
    ("V6_COLLISION_PREDICTED", "swept_volume_inflation_mm"): "envelope",
    ("V7_SENSOR_STALE", "camera_max_age_ms"): "envelope",
    ("V7_SENSOR_STALE", "encoder_max_age_ms"): "envelope",
    ("V8_NETWORK_DEGRADED", "window_ms"): "envelope",
    ("V8_NETWORK_DEGRADED", "allow_multi_step_plans"): "planner",
    ("V8_NETWORK_DEGRADED", "planner_source"): "planner",
    ("V9_PLAN_MALFORMED", "max_ttl_ms"): "envelope",
    ("V9_PLAN_MALFORMED", "allow_limit_requests_above_ceiling"): "envelope",
    ("V10_HUMAN_PRESENCE", "monitor_region"): "detector",
    ("V10_HUMAN_PRESENCE", "detection_method"): "detector",
    ("V10_HUMAN_PRESENCE", "clear_hold_ms"): "detector",
}

# The direction in which a value must move to be MORE conservative in degraded mode.
# Duplicated (narrowly) from scripts/validate_taxonomy.py on purpose: the script polices
# the contract including placeholders, while the envelope must police the values it will
# actually use. A test asserts the two maps agree for envelope-owned parameters.
CONSERVATIVE_DIRECTION: dict[str, str] = {
    "max_velocity_mm_s": "lower",
    "max_force_n": "lower",
    "boundary_margin_mm": "higher",
    "lookahead_ms": "higher",
    "swept_volume_inflation_mm": "higher",
    "camera_max_age_ms": "lower",
    "encoder_max_age_ms": "lower",
    "window_ms": "lower",
    "max_ttl_ms": "lower",
}

AXES = ("x", "y", "z")


class ParameterError(RuntimeError):
    """A parameter required by the envelope is missing, malformed or not conservative."""


@dataclass(frozen=True)
class Rule:
    rule_id: str
    priority: int
    severity: str
    applies_to_modes: tuple[str, ...]


@dataclass(frozen=True)
class Params:
    """Values for one parameter set, bound to a rule set."""

    values: dict[str, dict[str, Any]]
    mode: str  # "normal" | "degraded"

    def number(self, rule_id: str, key: str) -> float:
        value = self.values.get(rule_id, {}).get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ParameterError(
                f"{rule_id}.{key} has no numeric value in the {self.mode} parameter set (got {value!r})"
            )
        return float(value)

    def flag(self, rule_id: str, key: str, default: bool = False) -> bool:
        value = self.values.get(rule_id, {}).get(key, default)
        if not isinstance(value, bool):
            raise ParameterError(f"{rule_id}.{key} must be a boolean (got {value!r})")
        return value

    def mapping(self, rule_id: str, key: str) -> dict[str, Any]:
        value = self.values.get(rule_id, {}).get(key)
        if not isinstance(value, dict):
            raise ParameterError(
                f"{rule_id}.{key} must be an object in the {self.mode} parameter set (got {value!r})"
            )
        return value


class Ruleset:
    """The taxonomy (structure) joined to one calibration profile (values)."""

    def __init__(
        self,
        rules: list[Rule],
        policy: Params,
        normal: Params,
        degraded: Params,
        *,
        profile: str,
        provenance: str,
        rig: dict[str, Any],
        taxonomy_digest: str,
        calibration_digest: str,
        source_digest: str,
    ) -> None:
        self.rules = tuple(sorted(rules, key=lambda r: r.priority))
        self.policy = policy  # always the NORMAL set; see rule V9
        self.normal = normal
        self.degraded = degraded
        self.profile = profile
        self.provenance = provenance
        self.rig = rig
        self.taxonomy_digest = taxonomy_digest
        self.calibration_digest = calibration_digest
        self.source_digest = source_digest

    @property
    def is_measured(self) -> bool:
        return self.provenance == "measurement"

    def params_for(self, parameter_set: str) -> Params:
        if parameter_set == "degraded":
            return self.degraded
        if parameter_set == "normal":
            return self.normal
        raise ParameterError(f"unknown parameter set {parameter_set!r}")

    def severity(self, rule_id: str) -> str:
        for rule in self.rules:
            if rule.rule_id == rule_id:
                return rule.severity
        raise KeyError(rule_id)

    @classmethod
    def load(
        cls,
        taxonomy_path: Path | None = None,
        calibration_path: Path | None = None,
        profile: str | None = None,
    ) -> Ruleset:
        taxonomy_path = taxonomy_path or TAXONOMY_PATH
        calibration_path = calibration_path or CALIBRATION_PATH
        return load_ruleset(taxonomy_path, calibration_path, profile)


# --------------------------------------------------------------------------- loading


def _read_json(path: Path, what: str) -> tuple[dict[str, Any], str]:
    import hashlib

    if not path.exists():
        raise ParameterError(f"{what} not found: {path}")
    raw = path.read_bytes()
    try:
        return json.loads(raw.decode("utf-8")), hashlib.sha256(raw).hexdigest()
    except json.JSONDecodeError as exc:
        raise ParameterError(f"{what} is not valid JSON: {exc}") from exc


def _source_digest() -> str:
    """sha256 over the envelope package source, so a decision pins the code that made it."""
    import hashlib

    digest = hashlib.sha256()
    for path in sorted(Path(__file__).resolve().parent.glob("*.py")):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _check_conservative(rule_id: str, key: str, normal: Any, degraded: Any) -> None:
    direction = CONSERVATIVE_DIRECTION.get(key)
    if direction is None:
        return
    if isinstance(normal, bool) or isinstance(degraded, bool):
        return
    if not isinstance(normal, (int, float)) or not isinstance(degraded, (int, float)):
        raise ParameterError(f"{rule_id}.{key} must be numeric in both sets")
    if direction == "lower" and not degraded < normal:
        raise ParameterError(
            f"{rule_id}.{key}: degraded {degraded} is not lower than normal {normal} — degraded mode must be stricter"
        )
    if direction == "higher" and not degraded > normal:
        raise ParameterError(
            f"{rule_id}.{key}: degraded {degraded} is not higher than normal {normal} — degraded mode must be stricter"
        )


def _check_volume(rule_id: str, volume: Any, key: str) -> None:
    if not isinstance(volume, dict) or set(volume) != set(AXES):
        raise ParameterError(f"{rule_id}.{key} must define exactly the axes {AXES}, got {volume!r}")
    for axis in AXES:
        bounds = volume[axis]
        if not isinstance(bounds, (list, tuple)) or len(bounds) != 2:
            raise ParameterError(f"{rule_id}.{key}.{axis} must be [min, max], got {bounds!r}")
        low, high = bounds
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in (low, high)):
            raise ParameterError(f"{rule_id}.{key}.{axis} bounds must be numbers, got {bounds!r}")
        if low >= high:
            raise ParameterError(f"{rule_id}.{key}.{axis} min {low} must be < max {high}")


def load_ruleset(
    taxonomy_path: Path | None = None,
    calibration_path: Path | None = None,
    profile: str | None = None,
) -> Ruleset:
    taxonomy, taxonomy_digest = _read_json(taxonomy_path or TAXONOMY_PATH, "veto taxonomy")
    calibration, calibration_digest = _read_json(calibration_path or CALIBRATION_PATH, "rig calibration")

    rule_entries = taxonomy.get("rules")
    if not isinstance(rule_entries, list) or not rule_entries:
        raise ParameterError("veto taxonomy has no rules")

    rules: list[Rule] = []
    seen_priorities: set[int] = set()
    for entry in rule_entries:
        try:
            rule = Rule(
                rule_id=str(entry["rule_id"]),
                priority=int(entry["priority"]),
                severity=str(entry["severity"]),
                applies_to_modes=tuple(entry.get("applies_to_modes") or ()),
            )
        except (KeyError, TypeError) as exc:
            raise ParameterError(f"malformed rule entry: {entry!r} ({exc})") from exc
        if rule.priority in seen_priorities:
            raise ParameterError(f"duplicate priority {rule.priority} ({rule.rule_id})")
        seen_priorities.add(rule.priority)
        rules.append(rule)

    profiles = calibration.get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        raise ParameterError("rig calibration defines no profiles")
    profile_name = profile or calibration.get("active_profile")
    if not isinstance(profile_name, str) or profile_name not in profiles:
        raise ParameterError(f"calibration profile {profile_name!r} not found in {sorted(profiles)}")
    active = profiles[profile_name]
    provenance = str(active.get("provenance", "unknown"))
    rig = active.get("rig") or {}

    values = active.get("values")
    if not isinstance(values, dict):
        raise ParameterError(f"profile {profile_name!r} has no 'values' object")

    sets: dict[str, dict[str, dict[str, Any]]] = {}
    for parameter_set in PARAMETER_SETS:
        resolved: dict[str, dict[str, Any]] = {}
        for rule in rules:
            block = values.get(rule.rule_id, {})
            if not isinstance(block, dict):
                raise ParameterError(f"{profile_name}.{rule.rule_id} must be an object")
            resolved[rule.rule_id] = dict(block.get(parameter_set) or {})
        sets[parameter_set] = resolved

    # Every envelope-owned parameter must exist in both sets and be stricter when degraded.
    for rule in rules:
        for key, owner in PARAMETER_OWNERS.items():
            if owner != "envelope" or key[0] != rule.rule_id:
                continue
            _, name = key
            for parameter_set in PARAMETER_SETS:
                if name not in sets[parameter_set][rule.rule_id]:
                    raise ParameterError(
                        f"envelope-owned parameter {rule.rule_id}.{name} missing from the "
                        f"{parameter_set} set of profile {profile_name!r}"
                    )
        volume = sets["normal"][rule.rule_id].get("allowed_volume")
        if volume is not None:
            _check_volume(rule.rule_id, volume, "allowed_volume")
            _check_volume(
                rule.rule_id, sets["degraded"][rule.rule_id].get("allowed_volume"), "allowed_volume"
            )

    for rule in rules:
        for name in CONSERVATIVE_DIRECTION:
            try:
                normal_value = sets["normal"][rule.rule_id][name]
                degraded_value = sets["degraded"][rule.rule_id][name]
            except KeyError:
                continue
            _check_conservative(rule.rule_id, name, normal_value, degraded_value)

    # Degraded workspace must be contained in the normal one.
    for rule in rules:
        normal_volume = sets["normal"][rule.rule_id].get("allowed_volume")
        degraded_volume = sets["degraded"][rule.rule_id].get("allowed_volume")
        if normal_volume and degraded_volume:
            for axis in AXES:
                n_lo, n_hi = normal_volume[axis]
                d_lo, d_hi = degraded_volume[axis]
                if d_lo < n_lo or d_hi > n_hi:
                    raise ParameterError(
                        f"{rule.rule_id}.allowed_volume.{axis}: degraded [{d_lo}, {d_hi}] is wider than "
                        f"normal [{n_lo}, {n_hi}]"
                    )

    return Ruleset(
        rules=rules,
        policy=Params(sets["normal"], "normal"),
        normal=Params(sets["normal"], "normal"),
        degraded=Params(sets["degraded"], "degraded"),
        profile=profile_name,
        provenance=provenance,
        rig=rig,
        taxonomy_digest=taxonomy_digest,
        calibration_digest=calibration_digest,
        source_digest=_source_digest(),
    )


def envelope_owned_parameters() -> dict[str, list[str]]:
    """Envelope-owned parameter names, grouped by rule. Used to prove coverage."""
    grouped: dict[str, list[str]] = {}
    for (rule_id, name), owner in PARAMETER_OWNERS.items():
        if owner == "envelope":
            grouped.setdefault(rule_id, []).append(name)
    return {rule_id: sorted(names) for rule_id, names in grouped.items()}

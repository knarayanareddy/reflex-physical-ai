"""The calibration file is the safety case. These tests are what make it one.

A parameter store is only trustworthy if the loader refuses bad data rather than
interpolating it. Each rejection test builds a *deliberately wrong* calibration file and
asserts that loading fails — a validator that cannot be made to fail is not a validator.

The suite also pins the seam between the two authorities: the frozen taxonomy (structure,
policeable placeholders) and the calibration profile (values the envelope will actually
use). They are separate files with separate jobs, and these tests assert the join is sound.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from app.envelope import EnvelopeInputError, evaluate, load_ruleset
from app.envelope.params import (
    CALIBRATION_PATH,
    CONSERVATIVE_DIRECTION,
    PARAMETER_OWNERS,
    TAXONOMY_PATH,
    ParameterError,
    envelope_owned_parameters,
)

REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / "data" / "fixtures" / "snapshots"


def _calibration() -> dict[str, Any]:
    return json.loads(CALIBRATION_PATH.read_text(encoding="utf-8"))


def _taxonomy() -> dict[str, Any]:
    return json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))


def _profile_name() -> str:
    return _calibration()["active_profile"]


def _write(tmp_path: Path, calibration: dict[str, Any]) -> Path:
    path = tmp_path / "rig-limits.json"
    path.write_text(json.dumps(calibration), encoding="utf-8")
    return path


def _load_with(calibration: dict[str, Any], tmp_path: Path):
    return load_ruleset(taxonomy_path=TAXONOMY_PATH, calibration_path=_write(tmp_path, calibration))


def _mutated(mutate) -> dict[str, Any]:
    calibration = copy.deepcopy(_calibration())
    mutate(calibration["profiles"][calibration["active_profile"]])
    return calibration


# ------------------------------------------------------------------ the shipped profile


def test_active_calibration_profile_loads():
    ruleset = load_ruleset()
    assert ruleset.profile == _profile_name()
    assert len(ruleset.rules) == 10
    assert [rule.priority for rule in ruleset.rules] == list(range(1, 11))


def test_shipped_profile_is_declared_synthetic_and_says_so():
    """Honesty is a test, not a comment: a synthetic profile must not claim measurement."""
    calibration = _calibration()
    profile = calibration["profiles"][calibration["active_profile"]]
    assert profile["provenance"] == "synthetic"
    assert calibration["_meta"]["status"].startswith("SYNTHETIC")
    assert load_ruleset().is_measured is False


def test_every_taxonomy_rule_has_a_parameter_block():
    calibration = _calibration()
    values = calibration["profiles"][calibration["active_profile"]]["values"]
    rule_ids = {rule["rule_id"] for rule in _taxonomy()["rules"]}
    assert set(values) == rule_ids, set(values) ^ rule_ids
    for rule_id, sets in values.items():
        assert set(sets) == {"normal", "degraded"}, rule_id


def test_every_envelope_owned_parameter_has_both_sets():
    """Without this, a rule only fails the first time it fires in production."""
    values = _calibration()["profiles"][_profile_name()]["values"]
    for rule_id, names in envelope_owned_parameters().items():
        for name in names:
            assert name in values[rule_id]["normal"], f"{rule_id}.{name} missing from normal"
            assert name in values[rule_id]["degraded"], f"{rule_id}.{name} missing from degraded"


def test_every_parameter_has_a_declared_owner():
    """An unowned parameter is decoration: nothing enforces it, so it cannot be trusted."""
    declared = {
        (rule["rule_id"], name)
        for rule in _taxonomy()["rules"]
        for name in (rule.get("parameter_set_normal") or {})
    }
    assert declared == set(PARAMETER_OWNERS), declared ^ set(PARAMETER_OWNERS)
    assert set(PARAMETER_OWNERS.values()) <= {"envelope", "detector", "driver", "planner"}
    assert envelope_owned_parameters(), "no parameter is envelope-owned, so the envelope enforces nothing"


def test_owners_and_direction_maps_agree_with_the_taxonomy_validator():
    """Two files police strictness; a test keeps them from drifting apart."""
    import importlib.util
    import sys

    path = REPO / "scripts" / "validate_taxonomy.py"
    spec = importlib.util.spec_from_file_location("vt_for_tests", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["vt_for_tests"] = module
    spec.loader.exec_module(module)

    validated_directions = dict(module.STRICTNESS)

    # 1. Every direction the envelope enforces must match the contract's reading of it.
    for name, direction in CONSERVATIVE_DIRECTION.items():
        assert validated_directions.get(name) == direction, f"{name}: {direction}"

    # 2. Nothing envelope-owned may go unchecked. Numeric parameters are direction-checked;
    #    the remaining two need a dedicated law (containment for the volume, the policy flag
    #    for the ceiling), and both are enforced in load_ruleset / rule_v9.
    enforced_elsewhere = {
        "allowed_volume": "containment",  # load_ruleset: degraded box inside normal box
        "allow_limit_requests_above_ceiling": "policy",  # rule_v9: ceiling = normal set
    }
    for rule_id, names in envelope_owned_parameters().items():
        for name in names:
            assert name in CONSERVATIVE_DIRECTION or name in enforced_elsewhere, (
                f"{rule_id}.{name} is envelope-owned but nothing checks its direction"
            )


def test_param_provenance_covers_every_parameter():
    calibration = _calibration()
    profile = calibration["profiles"][calibration["active_profile"]]
    provenance = profile["parameter_provenance"]
    for rule_id, sets in profile["values"].items():
        for name in sets["normal"]:
            assert f"{rule_id}.{name}" in provenance, f"{rule_id}.{name} has no provenance"


# ------------------------------------------------------------------ load-time refusals


def test_loader_refuses_a_missing_envelope_owned_parameter(tmp_path: Path):
    def drop(profile: dict[str, Any]) -> None:
        del profile["values"]["V4_FORCE_LIMIT"]["degraded"]["max_force_n"]

    with pytest.raises(ParameterError, match=r"V4_FORCE_LIMIT\.max_force_n"):
        _load_with(_mutated(drop), tmp_path)


def test_loader_refuses_degraded_values_that_are_not_stricter(tmp_path: Path):
    def relax(profile: dict[str, Any]) -> None:
        profile["values"]["V7_SENSOR_STALE"]["degraded"]["camera_max_age_ms"] = 500

    with pytest.raises(ParameterError, match=r"must be stricter|not lower"):
        _load_with(_mutated(relax), tmp_path)


def test_loader_refuses_a_wider_degraded_workspace(tmp_path: Path):
    def widen(profile: dict[str, Any]) -> None:
        profile["values"]["V5_WORKSPACE_BOUND"]["degraded"]["allowed_volume"]["x"] = [0.0, 400.0]

    with pytest.raises(ParameterError, match="wider than"):
        _load_with(_mutated(widen), tmp_path)


def test_loader_refuses_a_malformed_volume(tmp_path: Path):
    def break_axis(profile: dict[str, Any]) -> None:
        profile["values"]["V5_WORKSPACE_BOUND"]["normal"]["allowed_volume"]["z"] = [60.0, 20.0]

    with pytest.raises(ParameterError, match=r"min .* must be < max"):
        _load_with(_mutated(break_axis), tmp_path)


def test_loader_refuses_an_unknown_profile(tmp_path: Path):
    with pytest.raises(ParameterError, match="not found"):
        load_ruleset(
            taxonomy_path=TAXONOMY_PATH, calibration_path=_write(tmp_path, _calibration()), profile="ghost"
        )


def test_loader_refuses_a_calibration_with_no_profiles(tmp_path: Path):
    calibration = _calibration()
    calibration["profiles"] = {}
    with pytest.raises(ParameterError, match="no profiles"):
        _load_with(calibration, tmp_path)


def test_loader_refuses_a_duplicate_priority(tmp_path: Path):
    taxonomy = _taxonomy()
    taxonomy["rules"][1]["priority"] = taxonomy["rules"][0]["priority"]
    path = tmp_path / "taxonomy.json"
    path.write_text(json.dumps(taxonomy), encoding="utf-8")
    with pytest.raises(ParameterError, match="duplicate priority"):
        load_ruleset(taxonomy_path=path, calibration_path=CALIBRATION_PATH)


def test_loader_refuses_missing_files(tmp_path: Path):
    with pytest.raises(ParameterError, match="not found"):
        load_ruleset(taxonomy_path=tmp_path / "nope.json", calibration_path=CALIBRATION_PATH)


# ------------------------------------------------------------------ provenance and identity


def test_provenance_decides_the_mode_not_the_request():
    """A synthetic profile can never produce a hardware decision, whatever the caller asks."""
    ruleset = load_ruleset()
    assert not ruleset.is_measured
    case = json.loads((FIXTURES / "pass_v1_estop.json").read_text(encoding="utf-8"))
    for requested in ("normal", "degraded", "simulation"):
        decision = evaluate(ruleset, case["snapshot"], case["proposal"], requested)
        assert decision["mode"] == "simulation", requested


def test_envelope_version_moves_when_a_value_moves(tmp_path: Path):
    """A decision must pin the numbers it was made with."""
    from app.envelope import envelope_version

    reference = envelope_version(load_ruleset())
    assert reference.startswith("sha256:")

    def nudge(profile: dict[str, Any]) -> None:
        profile["values"]["V3_VELOCITY_LIMIT"]["normal"]["max_velocity_mm_s"] = 59.0
        profile["values"]["V3_VELOCITY_LIMIT"]["degraded"]["max_velocity_mm_s"] = 23.0

    assert envelope_version(_load_with(_mutated(nudge), tmp_path)) != reference

    def relabel(profile: dict[str, Any]) -> None:
        profile["provenance"] = "measurement"

    assert envelope_version(_load_with(_mutated(relabel), tmp_path)) != reference


def test_envelope_version_is_stable_across_loads():
    from app.envelope import envelope_version

    assert envelope_version(load_ruleset()) == envelope_version(load_ruleset())


def test_measured_profile_is_trusted_to_say_so(tmp_path: Path):
    """The inverse of the honesty rule: provenance=measurement is what unlocks hardware mode."""

    def measure(profile: dict[str, Any]) -> None:
        profile["provenance"] = "measurement"

    ruleset = _load_with(_mutated(measure), tmp_path)
    assert ruleset.is_measured
    case = json.loads((FIXTURES / "pass_v1_estop.json").read_text(encoding="utf-8"))
    assert evaluate(ruleset, case["snapshot"], case["proposal"], "normal")["mode"] == "normal"


def test_missing_wall_clock_is_an_input_error_not_a_default():
    """The decision timestamp comes from the snapshot. A default would be a fabricated fact."""
    case = json.loads((FIXTURES / "pass_v1_estop.json").read_text(encoding="utf-8"))
    snapshot = copy.deepcopy(case["snapshot"])
    del snapshot["ts_wall"]
    with pytest.raises(EnvelopeInputError, match="ts_wall"):
        evaluate(load_ruleset(), snapshot, case["proposal"], "normal")

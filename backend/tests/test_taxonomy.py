"""The veto taxonomy must be complete, unambiguous, and stricter in degraded mode.

These tests drive ``scripts/validate_taxonomy.py`` as a library so a rule-table
regression is reported by the test runner, not only by a script someone remembers to
run. The script itself stays the CI entry point.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "validate_taxonomy.py"


def _load_script():
    """Import the CLI script as a module.

    ``sys.modules`` must be populated *before* exec_module: with
    ``from __future__ import annotations``, dataclasses resolves string annotations via
    the module registry and raises AttributeError otherwise.
    """
    name = "validate_taxonomy_under_test"
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(name, None)
    return module


@pytest.fixture(scope="module")
def validator():
    assert SCRIPT.exists(), "scripts/validate_taxonomy.py is referenced by the taxonomy; it must exist"
    return _load_script()


def test_structure_is_valid_with_placeholders_allowed(validator, capsys):
    """Structure, priority order and strictness direction must pass today; unresolved
    calibration values are tolerated because D-T06 has not run."""
    exit_code = validator.main(["--allow-placeholders", "--allow-missing-fixtures", "--quiet"])
    assert exit_code == 0, capsys.readouterr().err


def test_placeholders_and_missing_fixtures_are_reported_not_ignored(validator, capsys):
    exit_code = validator.main(["--allow-placeholders", "--allow-missing-fixtures"])
    output = capsys.readouterr().out
    assert exit_code == 0
    # The taxonomy is template v0: it must say so out loud rather than pretend.
    assert "TODO" in output
    assert "unresolved placeholder" in output


def test_strict_mode_fails_while_values_are_unmeasured(validator, capsys):
    """A guard against accidental 'done': until D-T06 measures the rig, --strict must fail."""
    exit_code = validator.main(["--strict", "--quiet"])
    assert exit_code == 1, "strict mode passed even though parameters are still TODO_MEASURE"
    capsys.readouterr()


def test_exactly_ten_rules(validator):
    import json

    rules = json.loads((REPO_ROOT / "data" / "veto-taxonomy.json").read_text(encoding="utf-8"))["rules"]
    assert len(rules) == 10
    assert [r["priority"] for r in rules] == list(range(1, 11))
    assert [r["rule_id"].split("_")[0] for r in rules] == [f"V{i}" for i in range(1, 11)]


def test_every_rule_declares_both_parameter_sets():
    import json

    rules = json.loads((REPO_ROOT / "data" / "veto-taxonomy.json").read_text(encoding="utf-8"))["rules"]
    for rule in rules:
        assert "parameter_set_normal" in rule, rule["rule_id"]
        assert "parameter_set_degraded" in rule, rule["rule_id"]
        if not rule["parameter_set_normal"]:
            assert rule.get("degraded_strictness_exemption"), (
                f"{rule['rule_id']} has an empty normal parameter set with no exemption"
            )


def test_v8_switches_to_degraded_faster_than_normal(validator):
    """The specific bug found in review: window_ms was identical in both modes."""
    import json

    rules = {
        r["rule_id"]: r
        for r in json.loads((REPO_ROOT / "data" / "veto-taxonomy.json").read_text(encoding="utf-8"))["rules"]
    }
    rule = rules["V8_NETWORK_DEGRADED"]
    assert rule["parameter_set_degraded"]["window_ms"] < rule["parameter_set_normal"]["window_ms"]
    assert rule["parameter_set_degraded"]["allow_multi_step_plans"] is False


def test_strictness_direction_is_defined_for_every_parameter(validator):
    """An undeclared parameter would be silently unvalidated. Pair every key in the
    taxonomy with a declared direction."""
    import json

    rules = json.loads((REPO_ROOT / "data" / "veto-taxonomy.json").read_text(encoding="utf-8"))["rules"]
    keys = {key for rule in rules for key in rule["parameter_set_normal"]} | {
        key for rule in rules for key in rule["parameter_set_degraded"]
    }
    undeclared = sorted(keys - set(validator.STRICTNESS))
    assert not undeclared, f"parameters with no declared conservative direction: {undeclared}"

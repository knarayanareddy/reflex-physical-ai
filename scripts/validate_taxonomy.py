#!/usr/bin/env python3
"""Validate the veto taxonomy: structure, totals, and degraded-mode strictness.

Two questions matter here, and both are answerable without any hardware:

1. **Is the rule table complete and unambiguous?** Ten rules, V1..V10, a total
   priority order with no gaps or duplicates, and (per rule) a rationale, a named
   test fixture, a false-positive note and both parameter sets.

2. **Is degraded mode actually stricter than normal mode?** This is insight #3 made
   testable. For every rule we compare each parameter in
   ``parameter_set_degraded`` against ``parameter_set_normal`` and require the
   degraded value to be more conservative. The direction of "more conservative" is
   a property of each parameter, so it is declared explicitly in ``STRICTNESS``
   below rather than guessed.

Placeholder handling: the taxonomy is template v0, so numeric limits are the
literal string ``TODO_MEASURE``. A placeholder is *not* a strictness failure — it is
an unresolved value, reported separately. Pass ``--allow-placeholders`` in CI while
D-T06 calibration is outstanding; pass ``--strict`` to require every value resolved.

Usage:
    python scripts/validate_taxonomy.py --strict
    python scripts/validate_taxonomy.py --allow-placeholders --allow-missing-fixtures

Exit codes: 0 = valid, 1 = invalid.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TAXONOMY = REPO / "data" / "veto-taxonomy.json"

RULE_ID_RE = re.compile(r"^V(?:[1-9]|10)_[A-Z_]+$")
RULE_COUNT = 10

# How to read "more conservative" for each parameter name.
#   lower          -> degraded must be a smaller number
#   higher         -> degraded must be a larger number
#   bool_false     -> degraded must be False (False = safer)
#   bool_true      -> degraded must be True  (True  = safer)
#   categorical    -> a fixed mapping, checked separately
#   equal          -> the value is a capability, not a threshold; must not change
#   unresolved     -> cannot be compared mechanically; reported, never silently ignored
STRICTNESS: dict[str, str] = {
    # V2
    "detection_min_confidence": "lower",
    "detection_method_priority": "equal",
    "min_blob_area_px": "lower",
    "consecutive_frames_required": "lower",
    # V3
    "max_velocity_mm_s": "lower",
    "max_accel_mm_s2": "lower",
    # V4
    "max_force_n": "lower",
    "force_estimate_method": "equal",
    # V5
    "allowed_volume": "unresolved",
    "boundary_margin_mm": "higher",
    # V6
    "lookahead_ms": "higher",
    "swept_volume_inflation_mm": "higher",
    # V7
    "camera_max_age_ms": "lower",
    "encoder_max_age_ms": "lower",
    # V8
    "window_ms": "lower",
    "allow_multi_step_plans": "bool_false",
    "planner_source": "categorical",
    # V9
    "max_ttl_ms": "lower",
    "allow_limit_requests_above_ceiling": "bool_false",
    # V10
    "monitor_region": "unresolved",
    "detection_method": "equal",
    "clear_hold_ms": "higher",
}

# A degraded value that would make the system LESS safe by construction.
FORBIDDEN_DEGRADED = {
    "planner_source": {"cloud_ultra", "cloud_grro", "cloud_gr00t"},
}

# Values that are already as safe as the parameter can be, so "equal" is acceptable.
HARD_BOUNDS: dict[str, float] = {
    "detection_min_confidence": 0.0,  # floor: detect everything
    "consecutive_frames_required": 1.0,  # floor: react immediately
    "min_blob_area_px": 0.0,  # floor: detect the smallest blob
    "window_ms": 0.0,  # floor: switch to degraded immediately
    "max_ttl_ms": 0.0,  # floor: shortest-lived proposals
}

MULTIPLIER_RE = re.compile(r"[×x*]\s*([0-9]*\.?[0-9]+)")


@dataclass
class Finding:
    level: str  # "error" | "warn" | "unresolved"
    where: str
    message: str


def sentence_count(text: str) -> int:
    return len([s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if len(s.split()) >= 3])


def classify(value: object) -> tuple[str, float | None]:
    """Return ('number', x) | ('placeholder', None) | ('placeholder_lower', None) |
    ('placeholder_higher', None) | ('other', None)."""
    if isinstance(value, bool):
        return "other", None
    if isinstance(value, (int, float)):
        return "number", float(value)
    if isinstance(value, str):
        text = value.strip()
        if "TODO" not in text.upper():
            return "other", None
        if MULTIPLIER_RE.search(text):
            return "multiplier", None
        lowered = text.upper()
        if "LOWER" in lowered or "SHRUNK" in lowered or "SHRINK" in lowered:
            return "placeholder_lower", None
        if "HIGHER" in lowered or "INFLAT" in lowered or "GROW" in lowered:
            return "placeholder_higher", None
        return "placeholder", None
    return "other", None


def check_strictness(rule_id: str, normal: dict, degraded: dict, exempt: bool) -> list[Finding]:
    findings: list[Finding] = []
    where = f"{rule_id}.parameter_set_degraded"

    if set(normal) != set(degraded):
        only_n = sorted(set(normal) - set(degraded))
        only_d = sorted(set(degraded) - set(normal))
        findings.append(
            Finding(
                "error",
                where,
                f"parameter names differ from the normal set "
                f"(missing in degraded: {only_n or 'none'}; extra: {only_d or 'none'})",
            )
        )
        return findings

    for key in sorted(normal):
        n, d = normal[key], degraded[key]
        direction = STRICTNESS.get(key)

        if direction is None:
            findings.append(
                Finding(
                    "error",
                    f"{where}.{key}",
                    "unknown parameter - declare its conservative direction in "
                    "scripts/validate_taxonomy.py:STRICTNESS before using it",
                )
            )
            continue

        forbidden = FORBIDDEN_DEGRADED.get(key)
        if forbidden and d in forbidden:
            findings.append(
                Finding("error", f"{where}.{key}", f"degraded value {d!r} is less safe than normal")
            )
            continue

        kind_n, num_n = classify(n)
        kind_d, num_d = classify(d)

        if direction == "unresolved":
            findings.append(
                Finding(
                    "warn",
                    f"{where}.{key}",
                    f"value {d!r} cannot be checked mechanically - assert it in a rule fixture instead",
                )
            )
            continue

        if kind_d == "multiplier" and isinstance(d, str):
            match = MULTIPLIER_RE.search(d)
            assert match is not None
            factor = float(match.group(1))
            if direction == "lower" and factor < 1:
                pass  # conservative direction, value still to be measured
            elif direction == "higher" and factor > 1:
                pass  # conservative direction, value still to be measured
            else:
                findings.append(
                    Finding(
                        "error",
                        f"{where}.{key}",
                        f"multiplier x{factor} goes the WRONG way for a {direction} parameter",
                    )
                )
                continue
            findings.append(
                Finding(
                    "unresolved",
                    f"{where}.{key}",
                    f"placeholder x{factor} is directionally conservative; the base value is still unmeasured",
                )
            )
            continue

        if direction == "categorical":
            findings.append(Finding("warn", f"{where}.{key}", f"declared categorical change: {n!r} -> {d!r}"))
            continue

        if kind_d == "placeholder":
            if direction in ("bool_false", "bool_true", "equal"):
                findings.append(
                    Finding("unresolved", f"{where}.{key}", f"placeholder {d!r} with no direction")
                )
            else:
                findings.append(
                    Finding(
                        "unresolved",
                        f"{where}.{key}",
                        f"placeholder {d!r} does not state whether it is lower or higher than {n!r}",
                    )
                )
            continue

        if kind_d in ("placeholder_lower", "placeholder_higher"):
            implied = "lower" if kind_d == "placeholder_lower" else "higher"
            if direction in ("lower", "higher") and implied != direction:
                findings.append(
                    Finding(
                        "error",
                        f"{where}.{key}",
                        f"{d!r} implies {implied}, but {key} must be {direction} in degraded mode",
                    )
                )
            else:
                findings.append(
                    Finding("unresolved", f"{where}.{key}", f"placeholder {d!r} is directionally consistent")
                )
            continue

        # Numeric comparison.
        if kind_n == "number" and kind_d == "number":
            assert num_n is not None and num_d is not None
            if direction == "lower":
                ok = num_d < num_n or (key in HARD_BOUNDS and num_d == HARD_BOUNDS[key] == num_n)
            elif direction == "higher":
                ok = num_d > num_n
            else:  # equal
                ok = num_d == num_n
            if not ok:
                findings.append(
                    Finding(
                        "error",
                        f"{where}.{key}",
                        f"{num_d} is not more conservative than {num_n} (this parameter must go {direction})",
                    )
                )
            continue

        # A placeholder normal value multiplied into a real degraded value, e.g.
        # "TODO_MEASURE × 0.4": only the multiplier's direction is checkable.
        if kind_n in ("placeholder", "placeholder_lower", "placeholder_higher") and isinstance(d, str):
            match = MULTIPLIER_RE.search(d)
            if match:
                factor = float(match.group(1))
                if direction == "lower" and factor < 1:
                    findings.append(
                        Finding(
                            "unresolved",
                            f"{where}.{key}",
                            f"placeholder x{factor} goes in the conservative direction",
                        )
                    )
                elif direction == "higher" and factor > 1:
                    findings.append(
                        Finding(
                            "unresolved",
                            f"{where}.{key}",
                            f"placeholder x{factor} goes in the conservative direction",
                        )
                    )
                else:
                    findings.append(
                        Finding(
                            "error",
                            f"{where}.{key}",
                            f"placeholder x{factor} goes the WRONG way for a {direction} parameter",
                        )
                    )
                continue
            findings.append(Finding("unresolved", f"{where}.{key}", f"placeholder {d!r}"))
            continue

        # Booleans and categoricals.
        if isinstance(n, bool) or isinstance(d, bool):
            want = False if direction == "bool_false" else True if direction == "bool_true" else None
            if want is None:
                findings.append(
                    Finding("error", f"{where}.{key}", f"boolean {key} must be declared bool_true/bool_false")
                )
            elif d is not want and not (d == want):
                findings.append(Finding("error", f"{where}.{key}", f"{d!r} is not the safe value {want!r}"))
            elif n == d and want is False:
                pass  # already at the safest setting: equal is acceptable
            continue

        if direction == "equal":
            if n != d:
                findings.append(
                    Finding(
                        "error", f"{where}.{key}", f"{key} must not change between modes ({n!r} -> {d!r})"
                    )
                )
            continue

        findings.append(Finding("unresolved", f"{where}.{key}", f"cannot compare {n!r} -> {d!r}"))

    if exempt:
        findings = [f for f in findings if f.level == "error"]
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--strict", action="store_true", help="no allowances: placeholders and missing fixtures fail"
    )
    parser.add_argument(
        "--allow-placeholders", action="store_true", help="TODO_MEASURE values are reported, not failed"
    )
    parser.add_argument(
        "--allow-missing-fixtures", action="store_true", help="named fixtures need not exist yet"
    )
    parser.add_argument("--quiet", action="store_true", help="only print the summary")
    args = parser.parse_args(argv)

    allow_placeholders = args.allow_placeholders and not args.strict
    allow_missing_fixtures = args.allow_missing_fixtures and not args.strict

    taxonomy = json.loads(TAXONOMY.read_text(encoding="utf-8"))
    rules = taxonomy.get("rules", [])
    findings: list[Finding] = []

    def note(level: str, where: str, message: str) -> None:
        findings.append(Finding(level, where, message))

    # ---- Rule set shape -------------------------------------------------------
    if len(rules) != RULE_COUNT:
        note("error", "taxonomy", f"expected {RULE_COUNT} rules, found {len(rules)}")

    ids = [r.get("rule_id", "") for r in rules]
    for rule_id in ids:
        if not RULE_ID_RE.match(rule_id):
            note("error", rule_id or "<missing>", "rule_id must look like V<n>_UPPER_SNAKE")

    if len(set(ids)) != len(ids):
        duplicates = sorted({i for i in ids if ids.count(i) > 1})
        note("error", "taxonomy", f"duplicate rule ids: {duplicates}")

    priorities = [r.get("priority") for r in rules]
    if sorted(p for p in priorities if isinstance(p, int)) != list(range(1, len(rules) + 1)):
        note("error", "taxonomy", f"priorities must be a total order 1..{len(rules)}, found {priorities}")

    modes = set((taxonomy.get("modes") or {}).keys())
    for rule in rules:
        rule_id = rule.get("rule_id", "<missing>")

        rationale = str(rule.get("rationale") or "")
        if sentence_count(rationale) < 2:
            note("error", rule_id, "rationale must be at least two sentences (write it for an auditor)")

        fixture = rule.get("test_fixture") or ""
        if not fixture:
            note("error", rule_id, "no test_fixture named")
        elif not (REPO / fixture).exists() and not allow_missing_fixtures:
            note("error", rule_id, f"named fixture does not exist: {fixture}")
        elif not (REPO / fixture).exists():
            note("unresolved", rule_id, f"fixture not yet created: {fixture}")

        if not str(rule.get("false_positive_risk") or "").strip():
            note("error", rule_id, "missing false_positive_risk note")

        if rule.get("severity") not in {"hard_stop", "clamp", "degrade", "reject"}:
            note("error", rule_id, f"unknown severity {rule.get('severity')!r}")

        rule_modes = set(rule.get("applies_to_modes") or [])
        if not rule_modes:
            note("error", rule_id, "applies_to_modes is empty")
        elif modes and not rule_modes <= modes:
            note("error", rule_id, f"applies_to_modes contains unknown modes: {sorted(rule_modes - modes)}")

        sensors = rule.get("requires_sensors") or []
        staleness = rule.get("sensor_staleness_ms")

        if not isinstance(staleness, int) or isinstance(staleness, bool) or staleness < 0:
            note("error", rule_id, f"sensor_staleness_ms must be a non-negative integer, found {staleness!r}")
        elif staleness == 0 and sensors:
            # A rule that *computes* freshness from ages carried in the snapshot (V7) has
            # no separate freshness window of its own; an extra window would double-count.
            condition = str(rule.get("condition") or "").lower()
            if "age" in condition or "stale" in condition:
                note(
                    "warn",
                    rule_id,
                    "sensor_staleness_ms=0 on a rule that enforces freshness itself - "
                    "age fields come from the snapshot, so no additional window applies",
                )
            else:
                note(
                    "error",
                    rule_id,
                    "sensor_staleness_ms=0 means 'not applicable', but this rule declares sensors - "
                    "give it a real freshness window",
                )
        elif staleness > 0 and not sensors:
            note("error", rule_id, f"declares a {staleness} ms freshness window but no sensors to check")
        elif staleness == 0 and not (rule.get("tuning_note") or rule.get("rationale")):
            note(
                "error",
                rule_id,
                "sensor_staleness_ms=0 needs a note explaining why freshness is not applicable",
            )

        normal = rule.get("parameter_set_normal")
        degraded = rule.get("parameter_set_degraded")
        exemption = rule.get("degraded_strictness_exemption")

        if not isinstance(normal, dict) or not isinstance(degraded, dict):
            note("error", rule_id, "both parameter sets must be objects")
            continue
        if exemption is not None and len(str(exemption).split()) < 8:
            note("error", rule_id, "degraded_strictness_exemption needs a real justification, not a word")
        if not normal and not exemption:
            note("error", rule_id, "parameter_set_normal is empty and no exemption is declared")

        findings.extend(check_strictness(rule_id, normal, degraded, exempt=bool(exemption)))
        if exemption and not args.quiet:
            note("warn", rule_id, "strictness exemption declared - verify it is still justified")

    # ---- Report ---------------------------------------------------------------
    errors = [f for f in findings if f.level == "error"]
    unresolved = [f for f in findings if f.level == "unresolved"]
    warnings = [f for f in findings if f.level == "warn"]

    if not args.quiet:
        for finding in warnings + unresolved + errors:
            prefix = {"error": "ERROR ", "unresolved": "TODO  ", "warn": "WARN  "}[finding.level]
            print(f"{prefix} {finding.where}: {finding.message}")

    if errors or (unresolved and not allow_placeholders):
        print(
            f"\nFAIL - {len(errors)} error(s), {len(unresolved)} unresolved value(s)"
            + ("" if allow_placeholders else " (resolve them or pass --allow-placeholders)"),
            file=sys.stderr,
        )
        return 1

    print(
        f"PASS - {len(rules)} rules, total priority order, "
        f"{len(unresolved)} unresolved placeholder(s), {len(warnings)} warning(s)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Prove that every envelope parameter traces to a measurement.

The taxonomy's integrity warning is explicit: parameter values must be derived from
measurements of your own rig, never copied from a paper or a datasheet. This script is
what turns that sentence into a build step.

It checks three things about the active calibration profile:

1. **Coverage** — every parameter the taxonomy declares has a value in both the normal and
   the degraded set, and every value has a provenance entry.
2. **Direction** — degraded values are strictly more conservative (re-using the taxonomy
   validator's direction map, which is the authoritative one).
3. **Provenance kind** — each entry is either ``measurement`` (with a ``measurement_id``
   that exists in the profile's ``measurements`` map) or ``synthetic``.

Exit codes:
    0  the profile is fully measured
    1  a structural problem (missing value, missing provenance, wrong direction)
    2  structurally sound but still synthetic — i.e. the numbers are placeholders

Exit code 2 exists so that CI can run this and record the debt without either lying (green)
or blocking the build on a measurement that has not happened (red). ``--strict`` turns it
into a failure; that is the flag to use once a rig has been calibrated.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TAXONOMY = REPO / "data" / "veto-taxonomy.json"
CALIBRATION = REPO / "data" / "calibration" / "rig-limits.json"
sys.path.insert(0, str(REPO / "backend"))


def load_rules() -> tuple[dict[str, str], dict[str, float]]:
    """Reuse the taxonomy validator's direction map and hard-bound map — one authority, no drift."""
    import importlib.util

    path = REPO / "scripts" / "validate_taxonomy.py"
    spec = importlib.util.spec_from_file_location("validate_taxonomy_shared", path)
    if spec is None or spec.loader is None:  # pragma: no cover
        raise SystemExit(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["validate_taxonomy_shared"] = module
    spec.loader.exec_module(module)
    return dict(module.STRICTNESS), dict(module.HARD_BOUNDS)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--strict", action="store_true", help="fail if any value is still synthetic")
    parser.add_argument("--profile", help="calibration profile to check (default: active_profile)")
    args = parser.parse_args(argv)

    taxonomy = json.loads(TAXONOMY.read_text(encoding="utf-8"))
    calibration = json.loads(CALIBRATION.read_text(encoding="utf-8"))
    profile_name = args.profile or calibration.get("active_profile")
    profiles = calibration.get("profiles") or {}
    if profile_name not in profiles:
        print(f"FAIL - profile {profile_name!r} not found", file=sys.stderr)
        return 1
    profile = profiles[profile_name]
    values = profile.get("values") or {}
    provenance = profile.get("parameter_provenance") or {}
    measurements = profile.get("measurements") or {}
    directions, hard_bounds = load_rules()

    errors: list[str] = []
    synthetic: list[str] = []
    measured: list[str] = []
    checked = 0

    for rule in taxonomy.get("rules", []):
        rule_id = rule["rule_id"]
        declared = set(rule.get("parameter_set_normal") or {}) | set(rule.get("parameter_set_degraded") or {})
        for parameter in sorted(declared):
            key = f"{rule_id}.{parameter}"
            checked += 1
            entry = values.get(rule_id) or {}
            normal = (entry.get("normal") or {}).get(parameter)
            degraded = (entry.get("degraded") or {}).get(parameter)

            if normal is None or degraded is None:
                errors.append(f"{key}: missing from the {'normal' if normal is None else 'degraded'} set")
                continue

            provenance_entry = provenance.get(key)
            if not provenance_entry:
                errors.append(f"{key}: no provenance entry (add one to {CALIBRATION.name})")
                continue
            kind = provenance_entry.get("kind")
            if kind == "measurement":
                measurement_id = provenance_entry.get("measurement_id")
                if measurement_id not in measurements:
                    errors.append(f"{key}: measurement_id {measurement_id!r} is not in the measurements map")
                else:
                    measured.append(key)
            elif kind == "synthetic":
                synthetic.append(key)
            else:
                errors.append(f"{key}: provenance kind {kind!r} must be 'measurement' or 'synthetic'")

            direction = directions.get(parameter)
            at_hard_bound = normal == degraded and hard_bounds.get(parameter) == normal
            if (
                direction in ("lower", "higher")
                and isinstance(normal, (int, float))
                and isinstance(degraded, (int, float))
                and not at_hard_bound
            ):
                wrong = (direction == "lower" and degraded >= normal) or (
                    direction == "higher" and degraded <= normal
                )
                if wrong:
                    errors.append(
                        f"{key}: degraded {degraded} is not stricter than normal {normal} ({direction})"
                    )

    print(f"profile: {profile_name} (provenance: {profile.get('provenance')})")
    print(
        f"parameters: {checked}  measured: {len(measured)}  synthetic: {len(synthetic)}  errors: {len(errors)}"
    )

    if errors:
        print(f"\nFAIL - {len(errors)} problem(s):", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    if synthetic:
        if args.strict:
            print(f"\nFAIL - {len(synthetic)} parameter(s) are still synthetic:", file=sys.stderr)
            for key in synthetic:
                print(f"  - {key}", file=sys.stderr)
            return 1
        print(f"\nPLACEHOLDER - {len(synthetic)} value(s) are synthetic, not measured.")
        print("  Decisions from this profile are forced to mode=simulation. That is by design.")
        print("  Run with --strict once a rig is calibrated (see _meta.how_to_add_a_measured_profile).")
        return 2

    print(f"\nPASS - every parameter in {profile_name} traces to a measurement")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

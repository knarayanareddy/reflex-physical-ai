#!/usr/bin/env python3
"""Print the normal → degraded parameter diff and fail if any value got *less* safe.

This is insight #3 as a table. Degraded mode is only meaningful if every limit moves in
the conservative direction, so the diff is printed for a human to read and checked by
machine in the same pass.

Source of values: the calibration profile (``data/calibration/rig-limits.json``), because
that is what the envelope actually loads. Run it with ``--taxonomy`` to inspect the
frozen contract's declared values instead.

Usage:
    python scripts/diff_parameter_sets.py
    python scripts/diff_parameter_sets.py --profile measured_rig_v1
    python scripts/diff_parameter_sets.py --taxonomy
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

DIRECTION_SYMBOL = {
    "lower": "v",
    "higher": "^",
    "equal": "=",
    "categorical": "->",
    "bool_false": "!",
    "bool_true": "+",
}


def load_rules() -> tuple[dict[str, str], dict[str, float]]:
    """Direction and hard-bound maps from the taxonomy validator — one authority, no drift."""
    import importlib.util

    path = REPO / "scripts" / "validate_taxonomy.py"
    spec = importlib.util.spec_from_file_location("validate_taxonomy_for_diff", path)
    if spec is None or spec.loader is None:  # pragma: no cover
        raise SystemExit(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["validate_taxonomy_for_diff"] = module
    spec.loader.exec_module(module)
    return dict(module.STRICTNESS), dict(module.HARD_BOUNDS)


def render(value: object) -> str:
    if isinstance(value, dict):
        return "{" + ", ".join(f"{k}: {render(v)}" for k, v in value.items()) + "}"
    return repr(value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--taxonomy", action="store_true", help="read the frozen contract instead of calibration"
    )
    parser.add_argument("--profile", help="calibration profile to inspect (default: active_profile)")
    args = parser.parse_args(argv)

    directions, hard_bounds = load_rules()
    if args.taxonomy:
        source = json.loads(TAXONOMY.read_text(encoding="utf-8"))
        label = "data/veto-taxonomy.json (contract placeholders)"
        blocks = [
            (
                rule["rule_id"],
                rule.get("parameter_set_normal") or {},
                rule.get("parameter_set_degraded") or {},
            )
            for rule in source["rules"]
        ]
    else:
        source = json.loads(CALIBRATION.read_text(encoding="utf-8"))
        profile_name = args.profile or source.get("active_profile")
        profile = (source.get("profiles") or {}).get(profile_name)
        if profile is None:
            print(f"FAIL - profile {profile_name!r} not found", file=sys.stderr)
            return 1
        label = f"data/calibration/rig-limits.json :: {profile_name} (provenance={profile.get('provenance')})"
        blocks = [
            (rule_id, sets.get("normal") or {}, sets.get("degraded") or {})
            for rule_id, sets in (profile.get("values") or {}).items()
        ]

    print(f"source: {label}\n")
    violations: list[str] = []
    for rule_id, normal, degraded in blocks:
        if not normal and not degraded:
            print(f"{rule_id}: (no parameters)")
            continue
        print(rule_id)
        for key in sorted(set(normal) | set(degraded)):
            n, d = normal.get(key, "<missing>"), degraded.get(key, "<missing>")
            direction = directions.get(key, "unresolved")
            symbol = DIRECTION_SYMBOL.get(direction, "?")
            ok = True
            at_hard_bound = n == d and hard_bounds.get(key) == n
            if (
                isinstance(n, (int, float))
                and isinstance(d, (int, float))
                and not isinstance(n, bool)
                and not isinstance(d, bool)
                and not at_hard_bound
            ):
                if direction == "lower":
                    ok = d < n
                elif direction == "higher":
                    ok = d > n
                elif direction == "equal":
                    ok = d == n
            elif direction == "bool_false":
                ok = d is False
            elif direction == "bool_true":
                ok = d is True
            verdict = "ok" if ok else "VIOLATION"
            if not ok:
                violations.append(f"{rule_id}.{key}: {n!r} -> {d!r}")
            print(f"  {symbol} {key:<34} {render(n):<28} -> {render(d):<28} {verdict}")
        print()

    if violations:
        print(
            f"FAIL - {len(violations)} parameter(s) are not more conservative in degraded mode:",
            file=sys.stderr,
        )
        for violation in violations:
            print(f"  - {violation}", file=sys.stderr)
        return 1

    print("PASS - every degraded value is at least as conservative as its normal counterpart")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

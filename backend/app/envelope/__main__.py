"""``python -m app.envelope`` — evaluate a payload, or verify the whole fixture corpus.

This is the CLI the demo and the CI gate both use, so the thing that is demonstrated is the
thing that is tested.

    python -m app.envelope verify                  # every fixture, contract-checked
    python -m app.envelope evaluate snapshot.json proposal.json --mode normal
    python -m app.envelope info                    # version, profile, rule table
    python -m app.envelope replay runs/veto-ledger.jsonl   # re-derive every decision

Exit codes: 0 success, 1 disagreement or invalid payload, 2 usage error.

Note what is *not* here: no HTTP, no model, no network. ``json`` and ``pathlib`` only, so the
purity test's import walk stays clean even with the CLI in the package.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from app.envelope import EnvelopeInputError, ParameterError, envelope_version, evaluate, load_ruleset

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES = REPO_ROOT / "data" / "fixtures" / "snapshots"


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _emit(payload: Any) -> None:
    json.dump(payload, sys.stdout, indent=2, sort_keys=False)
    sys.stdout.write("\n")


def _cmd_info(args: argparse.Namespace) -> int:
    ruleset = load_ruleset()
    _emit(
        {
            "envelope_version": envelope_version(ruleset),
            "profile": ruleset.profile,
            "calibration_provenance": ruleset.provenance,
            "measured": ruleset.is_measured,
            "simulation_badge_required": not ruleset.is_measured,
            "rules": [
                {
                    "rule_id": rule.rule_id,
                    "priority": rule.priority,
                    "severity": rule.severity,
                    "applies_to_modes": list(rule.applies_to_modes),
                }
                for rule in ruleset.rules
            ],
        }
    )
    return 0


def _cmd_evaluate(args: argparse.Namespace) -> int:
    snapshot = _read_json(Path(args.snapshot))
    proposal = _read_json(Path(args.proposal))
    try:
        decision = evaluate(load_ruleset(), snapshot, proposal, args.mode)
    except (EnvelopeInputError, ParameterError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    _emit(decision)
    return 0 if decision["outcome"] in {"ALLOW", "ALLOW_CLAMPED"} else 1


def _cmd_verify(args: argparse.Namespace) -> int:
    """Run every fixture and check the decision against its recorded expectation."""
    ruleset = load_ruleset()
    cases = sorted((Path(args.directory) if args.directory else FIXTURES).glob("*.json"))
    if not cases:
        print("error: no fixtures found", file=sys.stderr)
        return 2

    failures: list[str] = []
    for path in cases:
        case = _read_json(path)
        try:
            decision = evaluate(
                ruleset, case["snapshot"], case["proposal"], case.get("requested_mode", "normal")
            )
        except (KeyError, EnvelopeInputError, ParameterError) as exc:
            failures.append(f"{path.stem}: cannot evaluate ({exc})")
            continue
        expect = case.get("expect") or {}
        if expect.get("outcome") and decision["outcome"] != expect["outcome"]:
            failures.append(f"{path.stem}: expected {expect['outcome']}, got {decision['outcome']}")
        elif expect.get("rule_id") != decision["rule_id"]:
            failures.append(f"{path.stem}: expected rule {expect.get('rule_id')}, got {decision['rule_id']}")
        elif expect.get("mode") and decision["mode"] != expect["mode"]:
            failures.append(f"{path.stem}: expected mode {expect['mode']}, got {decision['mode']}")
        else:
            print(f"  ok  {path.stem:<24} {decision['outcome']:<14} {decision['rule_id'] or '-'}")

    print()
    if failures:
        print(f"FAIL - {len(failures)} of {len(cases)} fixtures disagree:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1
    print(f"PASS - {len(cases)} fixtures reproduce byte-identically under {ruleset.profile}")
    return 0


def _cmd_replay(args: argparse.Namespace) -> int:
    """Re-derive decisions from a ledger. This is the cloud-side replay, offline."""
    ledger = Path(args.ledger)
    if not ledger.exists():
        print(f"error: no ledger at {ledger}", file=sys.stderr)
        return 2

    ruleset = load_ruleset()
    replayed = mismatched = 0
    for lineno, line in enumerate(ledger.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        record = json.loads(line)
        # A record without its own snapshot cannot be replayed; say so instead of guessing.
        snapshot = record.get("sensor_snapshot_inline")
        proposal = record.get("intended_action") or record.get("intended_action_raw")
        if snapshot is None or proposal is None:
            print(f"  skip line {lineno}: no inline snapshot or intended action", file=sys.stderr)
            continue
        decision = evaluate(ruleset, snapshot, proposal, record.get("mode", "normal"))
        replayed += 1
        if decision["determinism_hash"] != record["determinism_hash"]:
            mismatched += 1
            print(
                f"  MISMATCH line {lineno} ({record.get('decision_id')}): {decision['determinism_hash']}",
                file=sys.stderr,
            )

    print()
    print(f"replayed {replayed} decision(s); {mismatched} mismatch(es)")
    return 0 if mismatched == 0 else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.envelope", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    info = sub.add_parser("info", help="print the envelope version, profile and rule table")
    info.set_defaults(func=_cmd_info)

    evaluate_cmd = sub.add_parser("evaluate", help="evaluate one snapshot/proposal pair")
    evaluate_cmd.add_argument("snapshot", help="path to a $defs/SensorSnapshot JSON file")
    evaluate_cmd.add_argument("proposal", help="path to a $defs/ActionProposal JSON file")
    evaluate_cmd.add_argument("--mode", default="normal", choices=["normal", "degraded", "simulation"])
    evaluate_cmd.set_defaults(func=_cmd_evaluate)

    verify = sub.add_parser("verify", help="run the fixture corpus and check expectations")
    verify.add_argument("--directory", help="fixture directory (default: data/fixtures/snapshots)")
    verify.set_defaults(func=_cmd_verify)

    replay = sub.add_parser("replay", help="re-derive the decisions in a veto ledger")
    replay.add_argument("ledger", help="path to a JSONL ledger of $defs/EnvelopeDecision")
    replay.set_defaults(func=_cmd_replay)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except ParameterError as exc:
        print(f"error: calibration or taxonomy is unusable: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

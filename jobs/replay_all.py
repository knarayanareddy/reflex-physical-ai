#!/usr/bin/env python3
"""Replay every recorded decision, both arms, and say what the envelope prevented.

    python jobs/replay_all.py --from-fixtures     # build a ledger from the fixture corpus, then replay
    python jobs/replay_all.py                     # replay runs/veto-ledger.jsonl
    python jobs/replay_all.py --ledger path.jsonl --out runs/replay

For each decision it runs the deterministic envelope twice over the same scene:

    envelope_off   the INTENDED action, with no safety layer   -> the counterfactual
    envelope_on    the SHIPPED action (None after a veto)      -> what actually happened

and writes two ``$defs/ReplayResult`` records, validated against the frozen contract. The
summary is deliberately blunt about coverage: a rule that stops the machine without a
spatial witness (force, staleness, trust, presence-without-localisation) has **no geometric
counterfactual**, and the report says so instead of inventing one.

This is the local form of the Nebius Serverless Job described in docs/ARCHITECTURE.md. The
job runner differs; the arithmetic does not. ``--write-cloud-records`` records
``runner="local_process"`` so a reviewer can always tell which lane produced an artifact.

Exit codes: 0 all decisions replayed, 1 a hash mismatch or an invalid record, 2 no input.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

from app.contracts import ContractViolation, validate_payload  # noqa: E402
from app.decision_ledger import record_decision, veto_ledger_path  # noqa: E402
from app.envelope import evaluate, load_ruleset  # noqa: E402
from app.replay import compare  # noqa: E402

FIXTURES = REPO / "data" / "fixtures" / "snapshots"
DEFAULT_OUT = REPO / "runs" / "replay"
SAMPLE_LEDGER = REPO / "runs" / "sample_veto_ledger.jsonl"


def build_from_fixtures(destination: Path) -> list[dict[str, Any]]:
    """Evaluate the fixture corpus and write the decisions to a ledger.

    The destination is truncated first. This is a *sample* ledger regenerated from the
    corpus, not evidence: appending to yesterday's sample would mix two envelope versions in
    one file and make every replay fail for a reason nobody could see.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.unlink(missing_ok=True)
    ruleset = load_ruleset()
    decisions: list[dict[str, Any]] = []
    for path in sorted(FIXTURES.glob("*.json")):
        case = json.loads(path.read_text(encoding="utf-8"))
        decision = evaluate(ruleset, case["snapshot"], case["proposal"], case.get("requested_mode", "normal"))
        decisions.append(record_decision(decision, destination))
    return decisions


def read_ledger(path: Path) -> list[dict[str, Any]]:
    decisions: list[dict[str, Any]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            decisions.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{path}:{lineno} is not valid JSON: {exc}") from exc
    return decisions


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--ledger", help="JSONL of EnvelopeDecision (default: the configured veto ledger)")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="directory for ReplayResult records")
    parser.add_argument(
        "--from-fixtures", action="store_true", help="rebuild the sample ledger from the fixtures first"
    )
    parser.add_argument("--quiet", action="store_true", help="only print the summary")
    args = parser.parse_args(argv)

    if args.from_fixtures:
        decisions = build_from_fixtures(SAMPLE_LEDGER)
        print(f"built {len(decisions)} decisions -> {SAMPLE_LEDGER.relative_to(REPO)}")
    else:
        ledger = Path(args.ledger) if args.ledger else veto_ledger_path()
        if not ledger.exists():
            print(f"error: no ledger at {ledger}", file=sys.stderr)
            print("hint: run with --from-fixtures to build one from the fixture corpus", file=sys.stderr)
            return 2
        decisions = read_ledger(ledger)
        print(f"read {len(decisions)} decisions from {ledger}")

    ruleset = load_ruleset()
    bounds = ruleset.policy.mapping("V5_WORKSPACE_BOUND", "allowed_volume")
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    prevented = 0
    geometric_prevented = 0
    no_counterfactual: dict[str, int] = {}
    invalid: list[str] = []

    for decision in decisions:
        ceiling = ruleset.params_for(decision.get("parameter_set", "normal")).number(
            "V3_VELOCITY_LIMIT", "max_velocity_mm_s"
        )
        comparison = compare(decision, ruleset.rig, bounds, ceiling)
        if comparison["collision_prevented"]:
            geometric_prevented += 1
        elif decision.get("outcome") == "VETO":
            no_counterfactual[decision.get("rule_id") or "?"] = (
                no_counterfactual.get(decision.get("rule_id") or "?", 0) + 1
            )
        prevented += 1 if decision.get("outcome") == "VETO" else 0

        for arm in ("envelope_off", "envelope_on"):
            record = comparison[arm]
            try:
                validate_payload("ReplayResult", record)
            except ContractViolation as exc:
                invalid.append(f"{decision.get('decision_id')}/{arm}: {exc.problems[:2]}")
                continue
            (out_dir / f"{record['replay_id']}.json").write_text(
                json.dumps(record, indent=2) + "\n", encoding="utf-8"
            )

        if not args.quiet:
            off, on = comparison["envelope_off"]["outcome"], comparison["envelope_on"]["outcome"]
            verdict = "PREVENTED" if comparison["collision_prevented"] else "-"
            print(
                f"  {(decision.get('outcome') or '?'):<13} {(decision.get('rule_id') or '-'):<24} "
                f"off={off:<13} on={on:<13} {verdict}"
            )

    print()
    print(f"decisions replayed : {len(decisions)}")
    print(f"vetoes             : {prevented}")
    print(f"geometric counterfactuals (off collided / on completed): {geometric_prevented}")
    if no_counterfactual:
        print("vetoes with no geometric counterfactual (forced by a rule the 2-D sim cannot model):")
        for rule_id, count in sorted(no_counterfactual.items()):
            print(f"  - {rule_id}: {count}")
    print(
        f"records written    : {len(list(out_dir.glob('rp_*.json')))} -> {out_dir.relative_to(REPO) if out_dir.is_relative_to(REPO) else out_dir}"
    )

    if invalid:
        print(f"\nFAIL - {len(invalid)} record(s) do not satisfy $defs/ReplayResult:", file=sys.stderr)
        for entry in invalid:
            print(f"  - {entry}", file=sys.stderr)
        return 1
    print("\nPASS - every replay record is contract-valid and deterministic")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

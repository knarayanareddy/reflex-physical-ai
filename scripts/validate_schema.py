#!/usr/bin/env python3
"""Validate the frozen contracts: schema meta-validity, $ref resolution, taxonomy conformance.

This is the cheap, dependency-light gate that CI runs on every push. It answers one
question: *are the contracts internally consistent?* It does not validate the
envelope's behaviour (that is the envelope test suite's job).

Usage:
    python scripts/validate_schema.py            # fail on any broken $ref or invalid rule
    python scripts/validate_schema.py -v         # also list every definition checked

Exit codes: 0 = valid, 1 = invalid.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import jsonschema
    from jsonschema import Draft202012Validator
except ImportError:  # pragma: no cover - the error message is the point
    sys.exit("jsonschema is required: cd backend && uv run --extra dev python ../scripts/validate_schema.py")

REPO = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO / "schemas" / "core-schemas.json"
TAXONOMY_PATH = REPO / "data" / "veto-taxonomy.json"
LEDGER_SAMPLE = REPO / "runs" / "sample_ledger.jsonl"


def load(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"missing contract file: {path.relative_to(REPO)}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{path.relative_to(REPO)} is not valid JSON: {exc}") from exc


def validator_for(defname: str, schema: dict) -> Draft202012Validator:
    """Build a validator that resolves #/$defs/<name> locally, with no network access."""
    return Draft202012Validator(
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$ref": f"#/$defs/{defname}",
            "$defs": schema["$defs"],
        }
    )


def resolve_all_refs(schema: dict, verbose: bool) -> list[str]:
    """Every $ref in the document must point inside this document.

    A dangling $ref is silent in JSON Schema: validators that do not touch the
    reference never notice. This repo shipped two that pointed into a different
    project, so the check is explicit rather than implied.
    """
    errors: list[str] = []
    raw = json.dumps(schema)
    refs = sorted({r for r in _walk_refs(schema)})
    for ref in refs:
        if not ref.startswith("#/$defs/"):
            errors.append(f"external or non-local $ref not allowed: {ref}")
            continue
        name = ref.removeprefix("#/$defs/")
        if name not in schema["$defs"]:
            errors.append(f"$ref target missing from $defs: {ref}")
        elif verbose:
            print(f"  ref ok: {ref}")
    if verbose:
        print(f"  {len(refs)} $refs checked")
    assert raw  # silence linters about the unused local
    return errors


def _walk_refs(node: object):
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "$ref" and isinstance(value, str):
                yield value
            else:
                yield from _walk_refs(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk_refs(item)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    problems: list[str] = []

    schema = load(SCHEMA_PATH)
    if args.verbose:
        print(f"schema: {SCHEMA_PATH.relative_to(REPO)} ({len(schema.get('$defs', {}))} definitions)")

    # 1. The schema must itself be a legal 2020-12 schema.
    try:
        Draft202012Validator.check_schema(schema)
    except jsonschema.exceptions.SchemaError as exc:
        problems.append(f"schema meta-validation failed: {exc.message}")
    else:
        if args.verbose:
            print("  meta-validation: ok")

    # 2. No dangling or foreign $refs.
    problems.extend(resolve_all_refs(schema, args.verbose))

    # 3. Every definition must be instantiable, i.e. its own $ref resolves and it
    #    rejects an empty object only for the right reason (a required field).
    for name in schema.get("$defs", {}):
        try:
            errors = list(validator_for(name, schema).iter_errors({}))
        except Exception as exc:
            problems.append(f"$defs/{name} is not resolvable: {type(exc).__name__}: {exc}")
            continue
        unresolved = [e for e in errors if "Unresolvable" in e.message]
        if unresolved:
            problems.append(f"$defs/{name} has an unresolvable reference")
        elif args.verbose:
            print(f"  $defs/{name}: resolvable")

    # 4. Every taxonomy rule must satisfy $defs/Rule.
    taxonomy = load(TAXONOMY_PATH)
    rule_validator = validator_for("Rule", schema)
    rules = taxonomy.get("rules", [])
    for rule in rules:
        for err in rule_validator.iter_errors(rule):
            location = "/".join(str(p) for p in err.path) or "<root>"
            problems.append(f"taxonomy rule {rule.get('rule_id', '?')} [{location}]: {err.message}")
    if args.verbose:
        print(f"taxonomy: {len(rules)} rules checked against $defs/Rule")

    # 5. The committed ledger sample must be parseable and schema-valid. It is a
    #    fixture, so it must be honest about being one.
    if LEDGER_SAMPLE.exists():
        ledger_validator = validator_for("LedgerLine", schema)
        for lineno, line in enumerate(LEDGER_SAMPLE.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                problems.append(f"{LEDGER_SAMPLE.name}:{lineno} is not JSON: {exc}")
                continue
            for err in ledger_validator.iter_errors(record):
                location = "/".join(str(p) for p in err.path) or "<root>"
                problems.append(f"{LEDGER_SAMPLE.name}:{lineno} [{location}]: {err.message}")
        if args.verbose:
            print("ledger sample: checked")

    if problems:
        print(f"\nFAIL - {len(problems)} problem(s):", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    print(f"PASS - schema, $refs, {len(rules)} taxonomy rules and the ledger fixture are consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

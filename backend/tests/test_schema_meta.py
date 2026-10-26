"""The contract file must be a legal, self-contained JSON Schema.

The regression this guards: two ``$ref``s pointed at
``../../A-redflag-eu-product-safety/...`` — a directory that does not exist in this
repo. A dangling ``$ref`` is invisible to a validator that never touches it, so it was
only found by resolution at review time. Now it is a test.
"""

from __future__ import annotations

import json

import pytest
from jsonschema import Draft202012Validator, SchemaError

from tests.factories import REPO_ROOT, SCHEMA_PATH, errors_for, schema, validate

SCHEMA_TEXT = SCHEMA_PATH.read_text(encoding="utf-8")


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


def test_schema_is_valid_json():
    parsed = json.loads(SCHEMA_TEXT)
    assert parsed["$schema"] == "https://json-schema.org/draft/2020-12/schema"


def test_schema_passes_meta_validation():
    try:
        Draft202012Validator.check_schema(schema())
    except SchemaError as exc:  # pragma: no cover - failure path
        pytest.fail(f"schema is not a legal 2020-12 schema: {exc.message}")


def test_no_external_refs():
    external = sorted({r for r in _walk_refs(schema()) if not r.startswith("#/$defs/")})
    assert not external, (
        "every $ref must resolve inside this file; external refs break the frozen-contract "
        f"promise and any consumer without the other repo: {external}"
    )


def test_every_local_ref_resolves():
    missing = sorted(
        {
            r
            for r in _walk_refs(schema())
            if r.startswith("#/$defs/") and r.split("/")[-1] not in schema()["$defs"]
        }
    )
    assert not missing, f"$ref targets missing from $defs: {missing}"


@pytest.mark.parametrize("defname", sorted(schema()["$defs"]))
def test_each_definition_is_instantiable(defname):
    """Resolve and run every definition against an empty instance.

    The point is not the verdict: it is that resolution *happens*. A definition whose
    $ref chain is broken raises here (ResolutionError / AttributeError) instead of
    silently skirting validation for every caller that never touches it.
    """
    errors = errors_for(defname, {})
    # Every error must be a real schema violation, not a reference that failed to resolve.
    for error in errors:
        assert "Unresolvable" not in error.message, f"{defname}: {error.message}"


def test_types_map_targets_exist():
    types = schema().get("types", {})
    for name, node in types.items():
        target = node["$ref"].removeprefix("#/$defs/")
        assert target in schema()["$defs"], f"types.{name} -> unknown {target}"


def test_ledger_sample_fixture_is_honest_and_valid():
    """The committed sample must parse, match $defs/LedgerLine, and admit it is synthetic."""
    sample = REPO_ROOT / "runs" / "sample_ledger.jsonl"
    records = [json.loads(line) for line in sample.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert records, "sample ledger must contain at least one record"
    for record in records:
        validate("LedgerLine", record)
        assert "SYNTHETIC" in (record.get("notes") or "").upper(), (
            "the sample ledger is a fixture, not measured traffic; it must say so"
        )

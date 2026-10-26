"""Telemetry ledger: valid records, durable appends, explicit path, working fixture.

The regression this guards: the ledger path was derived from ``__file__``, so the same
call wrote to ``<repo>/runs`` in a source checkout and to ``site-packages/../runs`` when
installed. For an audit artifact, "where did the record go" cannot depend on how the
package was installed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.tf.ledger import (
    LEDGER_ENV_VAR,
    build_entry,
    ledger_path,
    new_entry_id,
    read_ledger,
    record_telemetry,
    validate_entry,
)
from tests.factories import ledger_line, validate


def test_build_entry_matches_the_contract():
    entry = build_entry(
        kind="chat.completions",
        stage="plan",
        model="nvidia/Nemotron-3-Ultra-550b-a55b",
        prompt_tokens=900,
        completion_tokens=120,
        cached_tokens=800,
        cost_usd=0.00042,
        latency_ms=311.5,
    )
    validate("LedgerLine", entry)


def test_entry_has_a_unique_sortable_id():
    first, second = (
        build_entry(kind="k", stage="s", model="m", prompt_tokens=1, completion_tokens=1),
        build_entry(kind="k", stage="s", model="m", prompt_tokens=1, completion_tokens=1),
    )
    assert first["id"] != second["id"]
    assert first["id"].startswith("led_") and new_entry_id().startswith("led_")


@pytest.mark.parametrize(
    "field,value", [("prompt_tokens", -1), ("completion_tokens", 1.5), ("cached_tokens", True)]
)
def test_rejects_nonsense_token_counts(field, value):
    kwargs = {"prompt_tokens": 1, "completion_tokens": 1, "cached_tokens": 0, field: value}
    with pytest.raises(ValueError):
        build_entry(kind="k", stage="s", model="m", **kwargs)


def test_rejects_negative_cost_and_latency():
    with pytest.raises(ValueError):
        build_entry(kind="k", stage="s", model="m", prompt_tokens=1, completion_tokens=1, cost_usd=-0.1)
    with pytest.raises(ValueError):
        build_entry(kind="k", stage="s", model="m", prompt_tokens=1, completion_tokens=1, latency_ms=-1)


def test_record_telemetry_appends_one_parseable_line(tmp_path):
    destination = tmp_path / "nested" / "ledger.jsonl"
    entry = record_telemetry(
        kind="chat.completions",
        stage="plan",
        model="nvidia/Nemotron-3-nano",
        prompt_tokens=10,
        completion_tokens=2,
        destination=destination,
    )
    raw = destination.read_text(encoding="utf-8")
    assert raw.endswith("\n") and raw.count("\n") == 1
    assert json.loads(raw) == entry
    validate("LedgerLine", entry)


def test_appends_are_additive_never_rewritten(tmp_path):
    destination = tmp_path / "ledger.jsonl"
    first = record_telemetry(
        kind="k", stage="s", model="m", prompt_tokens=1, completion_tokens=1, destination=destination
    )
    second = record_telemetry(
        kind="k", stage="s", model="m", prompt_tokens=2, completion_tokens=2, destination=destination
    )
    records = read_ledger(destination)
    assert [r["id"] for r in records] == [first["id"], second["id"]]


def test_path_is_explicitly_overridable(tmp_path, monkeypatch):
    destination = tmp_path / "custom.jsonl"
    monkeypatch.setenv(LEDGER_ENV_VAR, str(destination))
    assert ledger_path() == destination.resolve()


def test_default_path_lives_in_the_repository_runs_dir(monkeypatch):
    monkeypatch.delenv(LEDGER_ENV_VAR, raising=False)
    monkeypatch.setattr("app.tf.ledger.settings", type("S", (), {"ledger_path": ""})())
    path = ledger_path()
    assert path.name == "ledger.jsonl"
    assert path.parent.name == "runs"
    # ... and it must not resolve into an installed package directory.
    assert "site-packages" not in str(path)


def test_read_ledger_reports_corruption_instead_of_skipping_it(tmp_path):
    destination = tmp_path / "ledger.jsonl"
    destination.write_text('{"id": "led_1"}\nnot json\n', encoding="utf-8")
    with pytest.raises(ValueError, match="not valid JSON"):
        read_ledger(destination)


def test_validation_rejects_a_malformed_entry():
    from jsonschema import ValidationError

    with pytest.raises(ValidationError):
        validate_entry({"id": "x", "ts": "not-a-date", "kind": "k", "stage": "s", "model": "m"})


def test_committed_sample_ledger_parses_and_validates():
    sample = Path(__file__).resolve().parents[2] / "runs" / "sample_ledger.jsonl"
    records = read_ledger(sample)
    assert records
    for record in records:
        validate("LedgerLine", record)


def test_factory_ledger_line_is_contract_valid():
    validate("LedgerLine", ledger_line())


def test_no_stray_newline_escapes_in_fixtures():
    """Guards the generator bug that corrupted three committed fixtures: a literal
    backslash-n written where a newline was meant."""
    sample = Path(__file__).resolve().parents[2] / "runs" / "sample_ledger.jsonl"
    text = sample.read_text(encoding="utf-8")
    assert "\\n" not in text, "sample ledger contains a literal backslash-n"

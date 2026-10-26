"""The veto ledger is the product's evidence; these tests are its chain of custody.

The telemetry ledger records what the models cost. This one records what the machine
refused to do, and it has three obligations that cost models do not:

1. **Nothing unvalidated is written.** A decision that fails the contract never reaches disk.
2. **Nothing is lost.** Append-only, fsync'd, and a corrupt line raises instead of vanishing.
3. **Every record is replayable on its own.** The snapshot travels with the decision, so a
   reader with this file and nothing else can re-derive the outcome.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app import decision_ledger
from app.contracts import ContractViolation
from app.envelope import evaluate, load_ruleset
from app.storage import CorruptLedger, append_jsonl, read_jsonl, resolve_path

FIXTURES = Path(__file__).resolve().parents[2] / "data" / "fixtures" / "snapshots"


def _decision(name: str = "veto_v2_keepout") -> dict:
    case = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    return evaluate(load_ruleset(), case["snapshot"], case["proposal"], case["requested_mode"])


# ------------------------------------------------------------------ storage


def test_append_then_read_round_trips(tmp_path: Path):
    path = tmp_path / "x.jsonl"
    append_jsonl(path, {"a": 1, "b": "ü"})
    append_jsonl(path, {"a": 2})
    assert read_jsonl(path) == [{"a": 1, "b": "ü"}, {"a": 2}]


def test_a_missing_ledger_reads_as_empty(tmp_path: Path):
    assert read_jsonl(tmp_path / "nope.jsonl") == []


def test_a_corrupt_line_raises_instead_of_being_skipped(tmp_path: Path):
    path = tmp_path / "x.jsonl"
    path.write_text('{"ok": true}\nnot json\n', encoding="utf-8")
    with pytest.raises(CorruptLedger, match=r":2 is not valid JSON"):
        read_jsonl(path)


def test_nan_is_refused_because_it_would_break_the_hash(tmp_path: Path):
    with pytest.raises(ValueError):
        append_jsonl(tmp_path / "x.jsonl", {"v": float("nan")})


def test_resolve_path_precedence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    default = tmp_path / "default.jsonl"
    explicit = tmp_path / "explicit.jsonl"

    monkeypatch.delenv("REFLEX_TEST_PATH", raising=False)
    assert resolve_path(None, "REFLEX_TEST_PATH", default) == default

    monkeypatch.setenv("REFLEX_TEST_PATH", str(tmp_path / "env.jsonl"))
    assert resolve_path(None, "REFLEX_TEST_PATH", default) == tmp_path / "env.jsonl"
    assert resolve_path(str(explicit), "REFLEX_TEST_PATH", default) == explicit


# ------------------------------------------------------------------ the veto ledger


def test_record_validates_before_writing(tmp_path: Path):
    path = tmp_path / "veto.jsonl"
    broken = _decision()
    broken["parameter_set"] = "turbo"  # not in the enum
    with pytest.raises(ContractViolation):
        decision_ledger.record_decision(broken, path)
    assert not path.exists(), "an invalid decision must not create the file"


def test_record_and_read_back(tmp_path: Path):
    path = tmp_path / "veto.jsonl"
    decision = _decision()
    decision_ledger.record_decision(decision, path)
    assert decision_ledger.read_decisions(path) == [decision]


def test_every_record_is_replayable_from_itself(tmp_path: Path):
    """The record carries its snapshot, so replay needs no second file."""
    path = tmp_path / "veto.jsonl"
    for fixture in sorted(FIXTURES.glob("*.json"))[:6]:
        decision_ledger.record_decision(_decision(fixture.stem), path)

    ruleset = load_ruleset()
    for record in decision_ledger.read_decisions(path):
        proposal = record["intended_action"] or record["intended_action_raw"]
        replayed = evaluate(ruleset, record["sensor_snapshot_inline"], proposal, record["mode"])
        assert replayed["determinism_hash"] == record["determinism_hash"]
        assert replayed["outcome"] == record["outcome"]


def test_default_path_is_the_repository_ledger(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("REFLEX_VETO_LEDGER_PATH", raising=False)
    monkeypatch.setattr(decision_ledger.settings, "veto_ledger_path", "", raising=False)
    assert decision_ledger.veto_ledger_path().name == "veto-ledger.jsonl"
    assert decision_ledger.veto_ledger_path().parent.name == "runs"


def test_environment_overrides_the_default(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("REFLEX_VETO_LEDGER_PATH", str(tmp_path / "custom.jsonl"))
    monkeypatch.setattr(decision_ledger.settings, "veto_ledger_path", "", raising=False)
    assert decision_ledger.veto_ledger_path() == tmp_path / "custom.jsonl"


def test_the_veto_ledger_and_the_telemetry_ledger_are_different_files():
    """Two kinds of evidence, two files: a cost record is not a safety record."""
    from app.tf import ledger as telemetry

    assert decision_ledger.veto_ledger_path() != telemetry.ledger_path()

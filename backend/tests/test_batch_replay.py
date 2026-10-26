"""D-T20 / D-T21 — the 1,000-action session, the sandbox pack and the replay endpoint.

The batch is the first place in this repository where a *number* is published rather than a
property asserted: "1,000 actions, 0 collisions shipped". Numbers like that are cheap to
manufacture by accident — a generator that never creates a hazard, a replay that quietly skips
the failing arm, a summary that counts a refusal as a prevention because it was easy to count.
So these tests check the measurement, not just the result:

* the session has the shape it claims (1,000 actions, every family present, exact counts);
* every generated snapshot and proposal is contract-valid, so the envelope is not being fed
  garbage and graded on it;
* every decision is contract-valid and every decision is in the ledger;
* the headline arithmetic adds up, and vetoes without a geometric witness are reported as
  such instead of being folded into "prevented";
* the pack re-derives offline, and a pack edited *after* its hashes were recomputed still
  fails — the difference between an integrity check and an actual verification;
* the run is reproducible from the seed, and fast enough to be run in a demo.

The failure paths are exercised on purpose: tampered packs, missing files, extra files, a
non-decision posted to the replay endpoint, a session that would collide if shipped.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import socket
import time
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from app.config import settings
from app.contracts import is_valid, validate_payload
from app.sandbox.replay_pack import (
    DECISIONS,
    MANIFEST,
    REPLAYS,
    _digest,
    _file_table,
    sandbox_plan,
    verify_pack,
)

REPO = Path(__file__).resolve().parents[2]
STATISTICS = REPO / "runs" / "headline_statistics.json"
JOB = REPO / "jobs" / "batch_1000_eval.py"
COUNT = 1000


def _job() -> ModuleType:
    """The batch job is a script, not a package: load it by path, once."""
    spec = importlib.util.spec_from_file_location("batch_1000_eval", JOB)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def job() -> ModuleType:
    return _job()


@pytest.fixture(scope="session")
def batch(job: ModuleType, tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    """Run the real CLI once and hand every test the artifacts it produced."""
    workdir = tmp_path_factory.mktemp("batch")
    out = workdir / "headline_statistics.json"
    started = time.perf_counter()
    exit_code = job.main(
        [
            "--count",
            str(COUNT),
            "--out",
            str(out),
            "--session-dir",
            str(workdir / "session"),
            "--pack",
            str(workdir / "pack"),
            "--quiet",
        ]
    )
    elapsed = time.perf_counter() - started
    assert exit_code == 0, "the batch job reported a failure"
    return {
        "workdir": workdir,
        "report": json.loads(out.read_text(encoding="utf-8")),
        "report_bytes": out.read_bytes(),
        "decisions": [
            json.loads(line)
            for line in (workdir / "session" / "decisions.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ],
        "pack": workdir / "pack",
        "elapsed_s": elapsed,
    }


# --------------------------------------------------------------------- the session


def test_the_session_is_one_thousand_actions_split_across_every_family(batch, job):
    report = batch["report"]
    assert report["session"]["actions"] == COUNT
    families = report["session"]["families"]
    assert sum(families.values()) == COUNT

    # Exact counts, not "approximately": the bucket table is the session's design.
    expected = {}
    for index in range(COUNT):
        name = job.family_for(index)
        expected[name] = expected.get(name, 0) + 1
    assert families == expected
    assert families["nominal"] == 450
    assert families["keep_out"] == 120
    assert families["joint_limit"] == 100
    assert families["human"] == 80


def test_the_session_traverses_the_three_scenarios_the_ticket_names(batch):
    """Keep-out zones, joint-limit boundaries and human proximity: each is ≥8% of the run."""
    families = batch["report"]["session"]["families"]
    assert families["keep_out"] >= 100
    assert families["joint_limit"] >= 100
    assert families["human"] >= 80


def test_the_same_seed_reproduces_the_same_session_byte_for_byte(job):
    first = json.dumps(job.generate_session(50, 20261026), sort_keys=True)
    second = json.dumps(job.generate_session(50, 20261026), sort_keys=True)
    third = json.dumps(job.generate_session(50, 999), sort_keys=True)
    assert first == second, "the generator is not deterministic"
    assert first != third, "the seed does not change the session"


def test_every_snapshot_and_proposal_is_contract_valid_except_the_malformed_family(batch, job):
    """The envelope must be graded on a legal corpus, or "0 collisions" means nothing."""
    valid_proposals = 0
    deliberately_invalid = 0
    for action in job.generate_session(COUNT):
        validate_payload("SensorSnapshot", action["snapshot"])
        try:
            validate_payload("ActionProposal", action["proposal"])
            valid_proposals += 1
        except Exception:
            assert action["family"] == "malformed", (
                f"action {action['index']} ({action['family']}) produced an invalid proposal "
                "without being part of the malformed family"
            )
            deliberately_invalid += 1

    assert valid_proposals + deliberately_invalid == COUNT
    assert deliberately_invalid > 0, "the malformed family stopped being malformed"


def test_every_recorded_decision_is_contract_valid(batch):
    for decision in batch["decisions"]:
        assert is_valid("EnvelopeDecision", decision), decision.get("decision_id")


def test_the_session_hash_names_the_session(batch):
    ids = "\n".join(decision["decision_id"] for decision in batch["decisions"])
    assert batch["report"]["session"]["sha256"] == hashlib.sha256(ids.encode()).hexdigest()


# ----------------------------------------------------------------- the headline claims


def test_zero_collisions_are_shipped_under_the_envelope(batch):
    """The acceptance criterion, checked over all 1,000 actions rather than a sample."""
    report = batch["report"]
    assert report["headline"]["collisions_shipped_under_envelope"] == 0
    assert report["shipped"] == {"collisions": 0, "boundary_excursions": 0}
    assert report["acceptance"]["zero_shipped_collisions"] is True


def test_the_session_runs_well_inside_the_fifteen_second_budget(batch):
    """Measured on the CLI including the pack build and its verification."""
    assert batch["elapsed_s"] < 15.0, f"the batch took {batch['elapsed_s']:.1f}s"


def test_at_least_five_distinct_rules_are_exercised_on_purpose(batch):
    vetoes = batch["report"]["vetoes"]["by_rule"]
    assert len(vetoes) >= 5, vetoes
    # Every one of these is present by construction, not by luck.
    for rule in (
        "V1_EMERGENCY_STOP",
        "V2_KEEP_OUT_OCCUPIED",
        "V4_FORCE_LIMIT",
        "V5_WORKSPACE_BOUND",
        "V6_COLLISION_PREDICTED",
        "V7_SENSOR_STALE",
        "V9_PLAN_MALFORMED",
        "V10_HUMAN_PRESENCE",
    ):
        assert vetoes.get(rule, 0) > 0 or rule in batch["report"]["prevented"]["by_rule"], rule


def test_the_headline_arithmetic_adds_up(batch):
    report = batch["report"]
    headline = report["headline"]
    assert headline["actions_planned"] == COUNT
    assert sum(report["decisions"].values()) == COUNT
    assert headline["vetoes_enforced"] == report["decisions"]["VETO"]
    assert headline["vetoes_enforced"] == sum(report["vetoes"]["by_rule"].values())
    assert headline["collisions_prevented"] == report["prevented"]["total"]
    assert report["prevented"]["total"] == sum(report["prevented"]["by_rule"].values())
    assert report["prevented"]["total"] == (
        report["prevented"]["collisions"] + report["prevented"]["boundary_excursions"]
    )


def test_decisions_without_a_geometric_witness_are_reported_not_counted_as_prevented(batch):
    """The honesty clause: a force veto has no collision to show, so it is not "prevented".

    The bucket is keyed by *decision*, not by veto: V3 and V5 appear in it as clamps. That is why
    it lives at the top level rather than under ``vetoes``, where it read as a veto count a third
    larger than the number of vetoes actually enforced.
    """
    report = batch["report"]
    without = report["decisions_without_geometric_counterfactual"]
    assert without.get("V4_FORCE_LIMIT") == report["vetoes"]["by_rule"]["V4_FORCE_LIMIT"]
    assert without.get("V7_SENSOR_STALE") == report["vetoes"]["by_rule"]["V7_SENSOR_STALE"]
    assert without.get("V10_HUMAN_PRESENCE") == report["vetoes"]["by_rule"]["V10_HUMAN_PRESENCE"]
    assert "V4_FORCE_LIMIT" not in report["prevented"]["by_rule"]

    clamp_rules = {"V3_VELOCITY_LIMIT", "V5_WORKSPACE_BOUND"}
    assert set(without) & clamp_rules, "a clamp without a witness belongs in this bucket"
    witness_free_vetoes = report["vetoes"]["total"] - report["prevented"]["collisions"]
    assert sum(without.values()) > witness_free_vetoes, (
        "the bucket holds more than the witness-free vetoes (it also holds clamps), which is why "
        "its total must never be presented as a veto count"
    )

    witnesses = set(report["prevented"]["by_rule"])
    assert witnesses <= {"V2_KEEP_OUT_OCCUPIED", "V5_WORKSPACE_BOUND", "V6_COLLISION_PREDICTED"}
    assert witnesses == {"V2_KEEP_OUT_OCCUPIED", "V5_WORKSPACE_BOUND", "V6_COLLISION_PREDICTED"}


def test_a_vetoed_keep_out_action_really_does_stop_at_the_volume(batch):
    """Spot-check one decision all the way down: ledger -> both arms -> geometry."""
    decision = next(entry for entry in batch["decisions"] if entry["rule_id"] == "V2_KEEP_OUT_OCCUPIED")
    from app.envelope import load_ruleset
    from app.replay import compare

    ruleset = load_ruleset()
    bounds = ruleset.policy.mapping("V5_WORKSPACE_BOUND", "allowed_volume")
    comparison = compare(decision, ruleset.rig, bounds, 60.0)
    off = comparison["envelope_off"]
    on = comparison["envelope_on"]

    assert off["outcome"] == "collided"
    assert off["collision"]["with"] == "keep_out_volume"
    # Sampled every 2 mm, so the first point inside the volume is at most one step past 150.
    from app.replay import STEP_MM

    assert 150.0 <= off["collision"]["contact_point"]["x"] < 150.0 + 2 * STEP_MM
    assert on["outcome"] == "completed"
    assert len(on["trajectory_points"]) == 1, "a vetoed plan ships no motion at all"
    assert comparison["collision_prevented"] is True


def test_the_committed_statistics_file_matches_a_fresh_run(batch):
    """A committed headline number that no longer reproduces is a lie with a nice font."""
    assert STATISTICS.is_file(), "runs/headline_statistics.json is missing"
    committed = json.loads(STATISTICS.read_text(encoding="utf-8"))
    fresh = batch["report"]

    # `sandbox_pack.pack_sha256` is deliberately volatile (it covers bytes that include a
    # measured latency); `acceptance.elapsed_ms` and the environment obviously are too.
    volatile = {"acceptance", "environment", "sandbox_pack"}
    assert {k: v for k, v in committed.items() if k not in volatile} == {
        k: v for k, v in fresh.items() if k not in volatile
    }
    assert committed["acceptance"]["zero_shipped_collisions"] is True
    assert committed["acceptance"]["under_15_seconds"] is True

    # The pack block is compared on its content digest, not its byte digest: latency_us is a
    # measurement, so the bytes differ while the evidence does not.
    # `verify_command` embeds the pack directory's name, which is a per-run choice.
    for key in ("schema", "counts", "network_required", "verified", "content_sha256"):
        assert committed["sandbox_pack"][key] == fresh["sandbox_pack"][key], key
    assert committed["sandbox_pack"]["verified"] is True
    assert committed["sandbox_pack"]["network_required"] is False


def test_only_the_measured_latency_varies_between_two_identical_decisions():
    """The reason the pack has two digests: latency is measured, everything else is content."""
    from app.envelope import evaluate, load_ruleset

    case = json.loads(
        (REPO / "data" / "fixtures" / "snapshots" / "veto_v2_keepout.json").read_text(encoding="utf-8")
    )
    ruleset = load_ruleset()
    first = evaluate(ruleset, case["snapshot"], case["proposal"], "normal")
    second = evaluate(ruleset, case["snapshot"], case["proposal"], "normal")

    differing = {key for key in first if first[key] != second[key]}
    assert differing == {"latency_us"}, differing
    assert first["decision_id"] == second["decision_id"]
    assert first["determinism_hash"] == second["determinism_hash"]


def test_the_statistics_file_says_it_is_synthetic(batch):
    source = batch["report"]["source"]
    assert source.startswith("SYNTHETIC")
    assert "No hardware ran" in source
    assert any("not contact dynamics" in caveat for caveat in batch["report"]["caveats"])


# ----------------------------------------------------------------------- the pack


def test_the_pack_verifies_with_no_network_at_all(batch, monkeypatch: pytest.MonkeyPatch):
    """The claim a sandbox makes, tested the only way it can be: switch the network off."""

    def refuse(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("pack verification tried to open a socket")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)

    report = verify_pack(batch["pack"])
    assert report["ok"] is True, report["problems"]
    assert report["checked"]["shipped_collisions"] == 0
    assert report["checked"]["decisions"] == COUNT
    assert report["checked"]["replay_records"] == COUNT * 2


def test_the_pack_is_self_contained(batch):
    pack = batch["pack"]
    assert {entry.name for entry in pack.iterdir()} == {MANIFEST, DECISIONS, REPLAYS}
    manifest = json.loads((pack / MANIFEST).read_text(encoding="utf-8"))
    assert manifest["network_required"] is False
    assert manifest["scene"]["rig"] and manifest["scene"]["bounds"]
    assert "velocity_ceiling_mm_s" in manifest["scene"]
    assert manifest["verify_command"].endswith("with the guest network disabled")

    blob = (pack / DECISIONS).read_text(encoding="utf-8") + (pack / REPLAYS).read_text(encoding="utf-8")
    assert "/home/" not in blob and str(REPO) not in blob, "the pack leaks host paths"
    if settings.nebius_api_key:
        assert settings.nebius_api_key not in blob


def test_a_tampered_replay_record_is_rejected(batch, tmp_path: Path):
    """Edit one number; the manifest hash no longer matches."""
    copy = _copy_pack(batch["pack"], tmp_path / "tampered")
    records = [json.loads(line) for line in (copy / REPLAYS).read_text(encoding="utf-8").splitlines()]
    records[0]["outcome"] = "completed"
    (copy / REPLAYS).write_text(
        "".join(json.dumps(r, sort_keys=True) + "\n" for r in records), encoding="utf-8"
    )

    report = verify_pack(copy)
    assert report["ok"] is False
    assert any("does not match the manifest" in problem for problem in report["problems"])


def test_a_pack_edited_after_its_hashes_were_recomputed_still_fails(batch, tmp_path: Path):
    """The important one: an attacker who fixes up the manifest must still be caught.

    A digest proves nobody edited the bytes. Only re-execution proves the numbers follow from
    the inputs — and that is the property this pack is supposed to have.
    """
    copy = _copy_pack(batch["pack"], tmp_path / "forged")
    records = [json.loads(line) for line in (copy / REPLAYS).read_text(encoding="utf-8").splitlines()]
    forged = next(record for record in records if record["arm"] == "envelope_off")
    forged["trajectory_sha256"] = hashlib.sha256(b"nice try").hexdigest()
    (copy / REPLAYS).write_text(
        "".join(json.dumps(r, sort_keys=True) + "\n" for r in records), encoding="utf-8"
    )

    manifest = json.loads((copy / MANIFEST).read_text(encoding="utf-8"))
    manifest["files"] = _file_table(copy)
    manifest["pack_sha256"] = _digest(manifest["files"])
    (copy / MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    report = verify_pack(copy)
    assert report["ok"] is False
    assert any("does not re-derive" in problem for problem in report["problems"]), report["problems"]


def test_a_pack_with_an_extra_file_is_rejected(batch, tmp_path: Path):
    copy = _copy_pack(batch["pack"], tmp_path / "extra")
    (copy / "notes.txt").write_text("trust me\n", encoding="utf-8")
    report = verify_pack(copy)
    assert report["ok"] is False
    assert any("unexpected file" in problem for problem in report["problems"])


def test_a_pack_with_a_missing_file_is_rejected(batch, tmp_path: Path):
    copy = _copy_pack(batch["pack"], tmp_path / "missing")
    (copy / REPLAYS).unlink()
    report = verify_pack(copy)
    assert report["ok"] is False
    assert any("missing" in problem for problem in report["problems"])


def test_a_directory_without_a_manifest_is_not_a_pack(tmp_path: Path):
    report = verify_pack(tmp_path)
    assert report["ok"] is False
    assert report["checked"] == {}


def test_the_sandbox_plan_turns_the_network_off_and_says_what_is_not_wired(
    batch,
):
    plan = sandbox_plan(batch["pack"])
    assert plan["network"] == "disabled"
    commands = [step.get("command", "") for step in plan["steps"]]
    assert any("replay_pack verify" in command for command in commands)
    # The SDK call is not implemented and does not pretend to be.
    assert plan["sdk"]["status"].startswith("TODO_VERIFY")
    assert "signature" in plan["sdk"]["detail"]


def _copy_pack(source: Path, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    for name in (MANIFEST, DECISIONS, REPLAYS):
        (destination / name).write_bytes((source / name).read_bytes())
    return destination


# -------------------------------------------------------------------- the endpoint


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


def _a_veto_decision(client) -> dict[str, Any]:
    case = json.loads(
        (REPO / "data" / "fixtures" / "snapshots" / "veto_v2_keepout.json").read_text(encoding="utf-8")
    )
    response = client.post(
        "/v1/envelope/evaluate",
        json={
            "snapshot": case["snapshot"],
            "proposal": case["proposal"],
            "requested_mode": case["requested_mode"],
        },
    )
    assert response.status_code == 200
    return response.json()


def test_the_replay_endpoint_returns_both_contract_valid_arms(client):
    decision = _a_veto_decision(client)
    response = client.post("/v1/replay", json={"decision": decision})
    assert response.status_code == 200

    body = response.json()
    assert body["collision_prevented"] is True
    for arm in ("envelope_off", "envelope_on"):
        assert is_valid("ReplayResult", body[arm]), body[arm]
        assert body[arm]["decision_id"] == decision["decision_id"]
        assert body[arm]["arm"] == arm
    assert body["envelope_off"]["outcome"] == "collided"
    assert body["envelope_on"]["outcome"] == "completed"


def test_the_replay_endpoint_is_deterministic(client):
    decision = _a_veto_decision(client)
    first = client.post("/v1/replay", json={"decision": decision}).json()
    second = client.post("/v1/replay", json={"decision": decision}).json()
    assert first == second
    assert first["envelope_off"]["trajectory_sha256"] == second["envelope_off"]["trajectory_sha256"]


def test_the_replay_endpoint_can_show_a_clamp_that_prevented_an_excursion(client):
    case = json.loads(
        (REPO / "data" / "fixtures" / "snapshots" / "veto_v5_bound.json").read_text(encoding="utf-8")
    )
    decision = client.post(
        "/v1/envelope/evaluate",
        json={
            "snapshot": case["snapshot"],
            "proposal": case["proposal"],
            "requested_mode": case["requested_mode"],
        },
    ).json()
    body = client.post("/v1/replay", json={"decision": decision}).json()
    assert body["envelope_off"]["outcome"] == "out_of_bounds"
    assert body["envelope_on"]["outcome"] == "completed"
    assert body["collision_prevented"] is True


def test_the_replay_endpoint_rejects_something_that_is_not_a_decision(client):
    response = client.post("/v1/replay", json={"decision": {"decision_id": "d_nope"}})
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["contract"] == "EnvelopeDecision"
    assert detail["problems"]


def test_the_replay_endpoint_rejects_a_made_up_outcome(client):
    decision = _a_veto_decision(client)
    decision["outcome"] = "PROBABLY_FINE"
    response = client.post("/v1/replay", json={"decision": decision})
    assert response.status_code == 422

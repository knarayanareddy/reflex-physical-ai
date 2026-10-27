"""D-T27 — the offline demo, tested as claims rather than as a script.

The demo exists to make five statements on camera. Each one is a test here:

1. the session is 10 seconds at 10 Hz, and the tool tip stops moving when the veto lands;
2. the first refusal is V2 (keep-out), and it opens the interlock;
3. the interlock **latches** — later proposals are refused by a different rule, so asking again does
   not restart the machine;
4. the ledger holds one contract-valid record per frame, including the veto;
5. the counterfactual is real: the envelope-off arm collides with the volume the envelope-on arm
   never reaches.

Two tests deliberately break the world and require the demo to **refuse** to print a green banner:
a session with no intrusion, and a session whose counterfactual never collides. A demo that cannot
fail is not evidence of anything.
"""

from __future__ import annotations

import importlib.util
import json
import socket
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO = Path(__file__).resolve().parents[2]
JOBS = REPO / "jobs"


def _load_demo() -> ModuleType:
    spec = importlib.util.spec_from_file_location("offline_demo", JOBS / "offline_demo.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolves field annotations through sys.modules, so register before executing.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


demo = _load_demo()


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    ledger = tmp_path_factory.mktemp("demo") / "veto-ledger.jsonl"
    result = demo.run_session(ledger_path=ledger)
    result.checks = demo.verify_run(result)
    return result


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


# --------------------------------------------------------------------- the session


def test_the_session_is_ten_seconds_at_ten_hertz(run):
    assert len(run.frames) == 100
    assert run.frames[0].t_s == 0.0
    assert run.frames[-1].t_s == pytest.approx(9.9)
    assert [frame.index for frame in run.frames] == list(range(100))


def test_the_tool_tip_advances_then_freezes_at_the_veto(run):
    xs = [frame.x_mm for frame in run.frames]
    assert xs == sorted(xs), "the tool tip never moves backwards"
    assert xs[run.veto_index] == pytest.approx(70.0), "10 mm start + 15 mm/s for 4.0 s"
    assert all(x == pytest.approx(70.0) for x in xs[run.veto_index :]), "no motion after the veto"


def test_the_keep_out_intrusion_trips_v2_and_opens_the_interlock(run):
    veto = run.veto
    assert veto is not None
    assert veto["outcome"] == "VETO"
    assert veto["rule_id"] == "V2_KEEP_OUT_OCCUPIED"
    assert veto["interlock_relay_opened"] is True
    assert veto["shipped_action"] is None
    assert veto["sensor_snapshot_inline"]["keep_out_occupied"] is True


def test_the_interlock_latches_so_the_next_proposal_is_refused_by_v1(run):
    after = run.decisions[run.veto_index + 1 :]
    assert after, "the demo must keep proposing after the veto, or the latch is untested"
    assert {decision["outcome"] for decision in after} == {"VETO"}
    assert {decision["rule_id"] for decision in after} == {"V1_EMERGENCY_STOP"}
    assert all(decision["shipped_action"] is None for decision in after)
    assert all(decision["interlock_relay_opened"] is False for decision in after), (
        "the relay is already open; only the first veto opens it"
    )


def test_the_session_is_stamped_simulation(run):
    assert {decision["mode"] for decision in run.decisions} == {"simulation"}


# --------------------------------------------------------------------- the ledger


def test_the_ledger_holds_one_valid_record_per_frame(run):
    from app.contracts import validate_payload
    from app.decision_ledger import read_decisions

    records = read_decisions(run.ledger_path)
    assert len(records) == len(run.frames)
    for record in records:
        validate_payload("EnvelopeDecision", record)
    veto_records = [record for record in records if record["outcome"] == "VETO"]
    assert veto_records
    assert veto_records[0]["decision_id"] == run.veto["decision_id"]


def test_the_ledger_line_is_one_json_object_per_line(run):
    text = run.ledger_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    assert len(lines) == len(run.frames)
    for line in lines:
        assert json.loads(line)["decision_id"].startswith("d_")


def test_the_veto_line_carries_its_own_snapshot_and_trace(run):
    """An auditor reading one line must be able to see why the machine stopped."""
    veto = run.veto
    assert veto["sensor_snapshot_inline"]["snapshot_id"] == veto["snapshot_id"]
    trace = veto["rule_trace"]
    assert [entry["rule_id"] for entry in trace][:2] == ["V1_EMERGENCY_STOP", "V2_KEEP_OUT_OCCUPIED"]
    assert trace[1]["result"] == "VETO"
    assert "keep-out occupied" in trace[1]["detail"]


# --------------------------------------------------------------------- the counterfactual


def test_the_counterfactual_collides_where_the_envelope_stops(run):
    replay = run.replays[run.veto["decision_id"]]
    off, on = replay["envelope_off"], replay["envelope_on"]
    assert off["outcome"] == "collided"
    assert off["collision"]["with"] == "keep_out_volume"
    assert off["collision"]["contact_point"]["x"] == pytest.approx(150.0, abs=2.0), (
        "contact is at the keep-out edge (x=150 mm) within the 2 mm sampling step"
    )
    assert on["outcome"] == "completed"
    assert on["metrics"]["distance_mm"] == pytest.approx(0.0)
    assert replay["collision_prevented"] is True


def test_no_decision_in_the_session_collides_under_the_envelope(run):
    assert run.shipped_collisions == 0
    assert run.checks, "verify_run() must have produced its checks"


def test_the_demo_is_deterministic(tmp_path):
    first = demo.run_session(ledger_path=tmp_path / "a.jsonl", replay_every_decision=False)
    second = demo.run_session(ledger_path=tmp_path / "b.jsonl", replay_every_decision=False)
    assert [d["decision_id"] for d in first.decisions] == [d["decision_id"] for d in second.decisions]
    assert [d["determinism_hash"] for d in first.decisions] == [
        d["determinism_hash"] for d in second.decisions
    ]


# --------------------------------------------------------------------- refusing to lie


def test_a_session_that_never_intrudes_is_refused(tmp_path):
    clean = demo.run_session(
        ledger_path=tmp_path / "clean.jsonl", intrusion_at_s=99.0, replay_every_decision=False
    )
    with pytest.raises(demo.DemoError, match="produced no veto"):
        demo.verify_run(clean)


def test_a_session_whose_counterfactual_never_collides_is_refused(tmp_path, monkeypatch):
    """If the envelope-off arm would not have collided, the demo has nothing to show."""
    monkeypatch.setattr(demo, "TARGET_X_MM", 120.0)  # stays short of the keep-out volume at x=150
    run = demo.run_session(ledger_path=tmp_path / "short.jsonl")
    with pytest.raises(demo.DemoError, match="no collision to prevent"):
        demo.verify_run(run)


# --------------------------------------------------------------------- serving


def test_the_check_mode_serves_the_api_and_probes_it(tmp_path):
    """The whole offline path: 10 s session, ledger, uvicorn on a free port, HTTP probe, clean exit."""
    port = _free_port()
    proc = subprocess.run(
        [
            sys.executable,
            str(JOBS / "offline_demo.py"),
            "--check",
            "--no-ui",
            "--api-port",
            str(port),
            "--ledger",
            str(tmp_path / "ledger.jsonl"),
            "--quiet",
        ],
        cwd=REPO / "backend",
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "DEMO PASS" in proc.stdout
    assert "DEMO CHECK PASS" in proc.stdout
    assert "API /v1/envelope/evaluate" in proc.stdout
    assert "same V2_KEEP_OUT_OCCUPIED decision as in-process" in proc.stdout

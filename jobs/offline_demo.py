#!/usr/bin/env python3
"""D-T27 — the 10-second offline demo: a keep-out intrusion, a V2 veto, an open interlock, one ledger line.

    python jobs/offline_demo.py            # the session, the checks, the summary; exit 0 on PASS
    python jobs/offline_demo.py --serve    # ... then serve the API and the dashboard until Ctrl-C
    python jobs/offline_demo.py --check    # ... then probe both servers and exit (CI, no hanging process)

What this is, and what it is not
--------------------------------

A scripted 10-second session at 10 Hz: a tool tip moves from x=10 mm toward a target 190 mm away at
15 mm/s — under the 60 mm/s normal ceiling, inside the workspace, with a fresh camera and a reachable
cloud. At t=4.0 s an intruder appears inside the keep-out volume. Everything else about the world is
unchanged, so the only thing that produced the refusal is the rule that fired:

    t < 4.0 s    ALLOW                     the tool tip advances 1.5 mm per frame
    t = 4.0 s    VETO V2_KEEP_OUT_OCCUPIED  the interlock relay opens; nothing ships
    t > 4.0 s    VETO V1_EMERGENCY_STOP     the relay is open, so every later proposal is refused

The last line is the point of the demo: asking again does not restart the machine. A proposal that
arrives after the veto is refused by a *different* rule, because the machine is no longer in a state
where motion is permissible at all.

Every proposal is evaluated by the real envelope (``app.envelope.evaluate``) and recorded through the
real ledger (``app.decision_ledger.record_decision``), then replayed down both arms
(``app.replay.compare``) so the demo can *show* what the refusal prevented instead of claiming it.
The session is **SYNTHETIC**: no hardware, no camera, no model, no network. ``mode=simulation`` is
stamped on every decision by the calibration profile, and the summary says so out loud.

Honest scope. The replay is a 2-D swept-volume model at the recorded end-effector z. It is not contact
dynamics and it is not a physics engine; "collided" means the swept segment entered the keep-out
volume, which is a proxy for a contact and not a measurement of one. The demo proves the *decision
path* end to end — it does not prove that a machine would have stopped in time, because no machine is
wired up.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

from app.contracts import validate_payload  # noqa: E402
from app.decision_ledger import read_decisions, record_decision  # noqa: E402
from app.envelope import evaluate, load_ruleset  # noqa: E402
from app.replay import compare  # noqa: E402

#: The demo starts at a fixed instant (2026-10-26T12:00:00Z). A wall clock here would make every run
#: produce a different ledger for the same story, and a ledger whose ids move is not a record of
#: anything.
DEMO_START_MS = 1_793_016_000_000

SECONDS = 10.0
HZ = 10.0
START_X_MM = 10.0
SPEED_MM_S = 15.0
TARGET_X_MM = 200.0
INTRUSION_AT_S = 4.0

DEFAULT_LEDGER = REPO / "runs" / "demo-veto-ledger.jsonl"
API_PORT = 8000
UI_PORT = 5173

SYNTHETIC_BANNER = "SYNTHETIC SESSION · mode=simulation · no hardware, no camera, no model, no network"


class DemoError(RuntimeError):
    """The demo did not do what it claims to do. Raised instead of printing a green banner."""


# --------------------------------------------------------------------------- the scripted world


def iso_ms(ms: int) -> str:
    """A fixed-millisecond instant as an ISO-8601 UTC string."""
    moment = datetime(1970, 1, 1, tzinfo=UTC) + timedelta(milliseconds=ms)
    return moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{moment.microsecond // 1000:03d}Z"


@dataclass(frozen=True)
class Frame:
    """One tick of the scripted world."""

    index: int
    t_s: float
    x_mm: float
    keep_out_occupied: bool

    @property
    def ts_ms(self) -> int:
        return DEMO_START_MS + self.index * int(1000 / HZ)


def build_frames(
    *,
    seconds: float = SECONDS,
    hz: float = HZ,
    intrusion_at_s: float = INTRUSION_AT_S,
    start_x_mm: float = START_X_MM,
    speed_mm_s: float = SPEED_MM_S,
) -> list[Frame]:
    """The trajectory, as intended: constant speed until the veto instant, then held.

    After the intrusion the tool tip does not move, because the actuator has no power. The frames
    after the veto are still generated: the cloud planner keeps proposing, and the demo shows what
    the envelope does with those proposals.
    """
    frames: list[Frame] = []
    for index in range(int(seconds * hz)):
        t_s = index / hz
        x_mm = start_x_mm + speed_mm_s * min(t_s, intrusion_at_s)
        frames.append(
            Frame(index=index, t_s=t_s, x_mm=round(x_mm, 3), keep_out_occupied=t_s >= intrusion_at_s)
        )
    return frames


def snapshot_at(frame: Frame, *, relay_open: bool) -> dict[str, Any]:
    """A contract-valid ``$defs/SensorSnapshot`` for one frame.

    Every field is written explicitly. The camera is fresh (33 ms against a 100 ms window), the cloud
    is reachable, the force estimate is 2 N — so no rule other than the one being demonstrated has an
    excuse to fire.
    """
    return {
        "snapshot_id": f"s_{frame.index:06d}",
        "ts_mono_ms": 1_000_000 + frame.index * int(1000 / HZ),
        "ts_wall": iso_ms(frame.ts_ms),
        "camera": {
            "frame_sha256": "0" * 64,
            "frame_idx": 1000 + frame.index,
            "age_ms": 33.0,
            "fps_measured": 30.0,
        },
        "end_effector": {
            "x": frame.x_mm,
            "y": 0.0,
            "z": 40.0,
            "encoder_raw": 1000 + frame.index,
            "age_ms": 5.0,
            "velocity_mm_s": 0.0 if frame.keep_out_occupied else SPEED_MM_S,
        },
        "limit_switches": {"min": False, "max": False, "age_ms": 5.0},
        "keep_out_occupied": frame.keep_out_occupied,
        "keep_out_evidence": {
            "method": "frame_diff",
            "blob_area_px": 900.0 if frame.keep_out_occupied else 0.0,
            "confidence": 0.91 if frame.keep_out_occupied else 0.99,
            "witnesses_agreeing": ["frame_diff", "depth"],
        },
        "intruder_present": frame.keep_out_occupied,
        "human_presence_detected": False,
        "force_estimate": 2.0,
        "force_estimate_method": "stall_current",
        "relay_state": not relay_open,
        "e_stop_asserted": False,
        "network": {"cloud_reachable": True, "last_cloud_ok_ms_ago": 12.0, "rtt_ms_p99": 80.0},
        "device": {
            "device_id": "sim-rig-01",
            "temp_c": 41.0,
            "cpu_pct": 12.0,
            "mem_pct": 30.0,
            "firmware_version": "0.1.0",
        },
    }


def proposal_at(frame: Frame) -> dict[str, Any]:
    """The planner's proposal: one move to the far side of the keep-out volume.

    The planner is *not* told about the intrusion — that is the job of the layer being demonstrated.
    """
    return {
        "proposal_id": f"p_{frame.index:06d}",
        "plan_id": "plan_00001",
        "kind": "move_to",
        "target_pose": {"x": TARGET_X_MM, "y": 0.0, "z": 40.0, "frame": "world"},
        "velocity_limit": SPEED_MM_S,
        "force_limit": 8.0,
        "preconditions": ["relay_closed", "keep_out_clear"],
        "expected_end_state": {"block": "at_target"},
        "source": "cloud_ultra",
        "issued_at": iso_ms(frame.ts_ms - 100),
        "ttl_ms": 500,
        "signature": None,
        "is_noop": False,
    }


# --------------------------------------------------------------------------- the run


@dataclass
class DemoRun:
    """Everything the demo measured, so the checks and the report read the same numbers."""

    frames: list[Frame]
    decisions: list[dict[str, Any]]
    replays: dict[str, dict[str, Any]]
    ledger_path: Path
    elapsed_s: float
    velocity_ceiling_mm_s: float
    checks: list[tuple[str, str]] = field(default_factory=list)

    @property
    def veto_index(self) -> int | None:
        for index, decision in enumerate(self.decisions):
            if decision["outcome"] == "VETO":
                return index
        return None

    @property
    def veto(self) -> dict[str, Any] | None:
        index = self.veto_index
        return None if index is None else self.decisions[index]

    @property
    def shipped_collisions(self) -> int:
        return sum(1 for replay in self.replays.values() if replay["envelope_on"]["outcome"] == "collided")

    @property
    def prevented(self) -> int:
        return sum(1 for replay in self.replays.values() if replay["collision_prevented"])

    def latencies_us(self) -> list[int]:
        return sorted(int(decision["latency_us"]) for decision in self.decisions)


def run_session(
    *,
    ledger_path: Path | str = DEFAULT_LEDGER,
    seconds: float = SECONDS,
    hz: float = HZ,
    intrusion_at_s: float = INTRUSION_AT_S,
    replay_every_decision: bool = True,
) -> DemoRun:
    """Play the session through the real envelope, ledger and replay. Returns the measurements.

    Nothing here decides anything itself: the outcome, the rule, the clamp and the interlock flag come
    back from ``evaluate``; the two arms come back from ``compare``. This function only supplies the
    world and counts what came back.
    """
    ruleset = load_ruleset()
    bounds = ruleset.policy.mapping("V5_WORKSPACE_BOUND", "allowed_volume")
    ceiling = ruleset.params_for("normal").number("V3_VELOCITY_LIMIT", "max_velocity_mm_s")

    ledger = Path(ledger_path).expanduser().resolve()
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text("")  # a demo run is the whole file, not an append to a previous story

    frames = build_frames(seconds=seconds, hz=hz, intrusion_at_s=intrusion_at_s)
    decisions: list[dict[str, Any]] = []
    replays: dict[str, dict[str, Any]] = {}
    relay_open = False
    started = time.perf_counter()

    for frame in frames:
        snapshot = snapshot_at(frame, relay_open=relay_open)
        proposal = proposal_at(frame)
        decision = evaluate(ruleset, snapshot, proposal, "normal")
        validate_payload("EnvelopeDecision", decision)
        record_decision(decision, ledger)
        decisions.append(decision)
        if replay_every_decision:
            replays[decision["decision_id"]] = compare(decision, ruleset.rig, bounds, ceiling)
        # The interlock latches: once the envelope opens the relay, it stays open for the run. Only a
        # human reset (out of scope; no hardware) closes it again.
        relay_open = relay_open or bool(decision["interlock_relay_opened"])

    elapsed = time.perf_counter() - started
    run = DemoRun(
        frames=frames,
        decisions=decisions,
        replays=replays,
        ledger_path=ledger,
        elapsed_s=elapsed,
        velocity_ceiling_mm_s=float(ceiling),
    )
    if not replay_every_decision:
        # A session with no veto is a broken demo, but it is ``verify_run``'s job to say so with the
        # full explanation; this function only replays what exists.
        veto = run.veto
        if veto is not None:
            replays[veto["decision_id"]] = compare(veto, ruleset.rig, bounds, ceiling)
    return run


# --------------------------------------------------------------------------- the claims


def verify_run(run: DemoRun) -> list[tuple[str, str]]:
    """Assert the things the demo exists to show. Raises ``DemoError`` on the first failure.

    A demo that prints a green summary without checking these is a screensaver. Every assertion here
    is on data the envelope produced, not on the script's intent.
    """
    checks: list[tuple[str, str]] = []

    if len(run.decisions) != len(run.frames):
        raise DemoError(f"{len(run.frames)} frames but {len(run.decisions)} decisions")
    checks.append(("every frame evaluated", f"{len(run.decisions)} decisions for {len(run.frames)} frames"))

    veto = run.veto
    index = run.veto_index
    if veto is None or index is None:
        raise DemoError(
            "the session produced no veto. The keep-out intrusion is supposed to trip V2; a demo "
            "that runs clean is either not the demo or a broken envelope."
        )
    if veto["rule_id"] != "V2_KEEP_OUT_OCCUPIED":
        raise DemoError(f"the first refusal was {veto['rule_id']}, expected V2_KEEP_OUT_OCCUPIED")
    checks.append(("first refusal is V2", f"{veto['rule_id']} at {run.frames[index].t_s:.1f} s"))

    if veto["interlock_relay_opened"] is not True:
        raise DemoError("the veto did not open the interlock relay")
    checks.append(("interlock opened", "interlock_relay_opened=true, relay is now open"))

    if veto["shipped_action"] is not None:
        raise DemoError("a VETO shipped an action, which the contract forbids")
    after = run.decisions[index + 1 :]
    if any(decision["outcome"] != "VETO" for decision in after):
        raise DemoError("a proposal after the veto was not refused; the interlock did not latch")
    if any(decision["shipped_action"] is not None for decision in after):
        raise DemoError("a proposal after the veto shipped an action")
    checks.append(("the interlock latches", f"{len(after)} later proposals all refused, none shipped"))

    if run.shipped_collisions:
        raise DemoError(
            f"{run.shipped_collisions} decision(s) replay to a collision under the envelope. "
            "That is a finding, not a demo."
        )
    checks.append(("no collision under the envelope", f"0 of {len(run.replays)} replayed decisions collided"))

    replay = run.replays.get(veto["decision_id"])
    if replay is None:
        raise DemoError("the veto decision was not replayed")
    if replay["envelope_off"]["outcome"] != "collided":
        raise DemoError(
            f"the envelope-off arm ended {replay['envelope_off']['outcome']!r}; "
            "there is no collision to prevent, so this demo shows nothing"
        )
    contact = replay["envelope_off"]["collision"]["contact_point"]
    checks.append(
        (
            "the refusal prevented a collision",
            f"off: collided at ({contact['x']:.1f}, {contact['y']:.1f}) mm · "
            f"on: {replay['envelope_on']['outcome']}",
        )
    )
    return checks


# --------------------------------------------------------------------------- the report


def percentile(values: list[int], fraction: float) -> int:
    """Nearest-rank percentile over a sorted list; 0 for an empty list."""
    if not values:
        return 0
    return values[min(len(values) - 1, int(fraction * len(values)))]


def render_report(run: DemoRun) -> str:
    """The summary a human reads and the video films. Every number comes from ``run``."""
    lines: list[str] = []
    add = lines.append
    index = run.veto_index
    veto = run.veto
    if veto is None or index is None:  # verify_run() has already insisted; this keeps mypy honest
        raise DemoError("render_report() needs a run with a veto")

    add("")
    add("=" * 78)
    add("Reflex — offline demo")
    add(SYNTHETIC_BANNER)
    add(
        f"{SECONDS:.1f} s at {HZ:.0f} Hz · {len(run.frames)} proposals · "
        f"velocity ceiling {run.velocity_ceiling_mm_s:.0f} mm/s · target x={TARGET_X_MM:.0f} mm"
    )
    add("=" * 78)
    add("")
    add("timeline")
    for frame, decision in zip(run.frames, run.decisions, strict=True):
        near = abs(frame.index - index) <= 2
        if frame.index % 10 and not near:
            continue
        marker = "  <-- intruder inside the keep-out volume" if frame.index == index else ""
        add(
            f"  t={frame.t_s:4.1f} s  x={frame.x_mm:6.1f} mm  "
            f"{decision['outcome']:<13} {decision['rule_id'] or '':<22}{marker}"
        )
    add("")
    add("the veto")
    add(f"  rule            : {veto['rule_id']}")
    add(f"  decided_at      : {veto['decided_at']}")
    add(f"  mode            : {veto['mode']}  (parameter set: {veto['parameter_set']})")
    add(f"  intended action : {json.dumps(veto['intended_action'], sort_keys=True)}")
    add(f"  shipped action  : {veto['shipped_action']}")
    add(f"  interlock relay : opened = {veto['interlock_relay_opened']}")
    add(f"  decision id     : {veto['decision_id']}")
    add("")
    travelled = run.frames[index].x_mm - START_X_MM
    held = len(run.frames) - index - 1
    add("motion")
    add(f"  travelled before the veto : {travelled:.1f} mm in {run.frames[index].t_s:.1f} s")
    add(f"  travelled after the veto  : 0.0 mm over {held} frames ({held / HZ:.1f} s)")
    add("")
    add("the ledger line")
    add("  " + json.dumps(veto, sort_keys=True, separators=(",", ":")))
    add("")
    records = read_decisions(run.ledger_path)
    add(f"  file: {run.ledger_path.name} — {len(records)} records, one JSON object per line")
    add("")
    replay = run.replays[veto["decision_id"]]
    off, on = replay["envelope_off"], replay["envelope_on"]
    add("the counterfactual (both arms, same decision)")
    if off["outcome"] == "collided" and off["collision"] is not None:
        contact = off["collision"]["contact_point"]
        add(
            f"  envelope OFF : {off['outcome']} with {off['collision']['with']} at "
            f"t={off['collision']['at_t_ms']:.0f} ms, contact ({contact['x']:.1f}, {contact['y']:.1f}) mm"
        )
    else:
        add(f"  envelope OFF : {off['outcome']}")
    points = len(on["trajectory_points"])
    add(
        f"  envelope ON  : {on['outcome']}, {on['metrics']['distance_mm']:.1f} mm travelled "
        f"({points} trajectory point{'' if points == 1 else 's'})"
    )
    add(f"  prevented    : {replay['collision_prevented']}")
    add("")
    latencies = run.latencies_us()
    add("envelope latency (measured, this run)")
    add(
        f"  p50 {percentile(latencies, 0.50)} µs · p95 {percentile(latencies, 0.95)} µs · "
        f"max {latencies[-1]} µs over {len(latencies)} decisions · wall {run.elapsed_s * 1000:.0f} ms"
    )
    add("")
    add("checks")
    for name, detail in run.checks:
        add(f"  PASS  {name:<34} {detail}")
    add("")
    add(f"DEMO PASS — {len(run.checks)}/{len(run.checks)} checks, 0 collisions shipped")
    return "\n".join(lines)


# --------------------------------------------------------------------------- serving the UI


def http_json(url: str, *, method: str = "GET", payload: dict[str, Any] | None = None) -> tuple[int, str]:
    """One HTTP request against a local server. Returns ``(status, body)``; never raises for 4xx/5xx."""
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        request.add_header("content-type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")


def wait_for(url: str, *, timeout_s: float = 40.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            status, _ = http_json(url)
            if status < 500:
                return
        except (urllib.error.URLError, ConnectionError, OSError):
            pass
        time.sleep(0.2)
    raise DemoError(f"{url} did not answer within {timeout_s:.0f} s")


def port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


@dataclass
class Servers:
    """The API and the dashboard, as child processes the demo starts and stops."""

    api: subprocess.Popen[bytes] | None = None
    ui: subprocess.Popen[bytes] | None = None
    ui_skipped_reason: str | None = None
    api_port: int = API_PORT
    ui_port: int = UI_PORT

    def stop(self) -> None:
        """Stop both children, including anything npm started underneath."""
        for process in (self.ui, self.api):
            if process is None or process.poll() is not None:
                continue
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:  # pragma: no cover - a very stuck child
                with contextlib.suppress(ProcessLookupError, PermissionError):
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)


def start_servers(*, api_port: int = API_PORT, ui_port: int = UI_PORT, with_ui: bool = True) -> Servers:
    """Start uvicorn and (when the dashboard's dependencies are installed) vite.

    On failure the servers started so far are stopped before the error propagates: a demo that leaks a
    listener onto :8000 makes the *next* run fail for an unrelated reason.
    """
    servers = Servers(api_port=api_port, ui_port=ui_port)
    try:
        if not port_is_free(api_port):
            raise DemoError(
                f"port {api_port} is already in use. Stop the other server, or pass --api-port "
                "(the dashboard proxy targets 8000, so moving the API also needs a vite config change)."
            )
        backend = REPO / "backend"
        servers.api = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "0.0.0.0",
                "--port",
                str(api_port),
                "--log-level",
                "warning",
            ],
            cwd=backend,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        wait_for(f"http://127.0.0.1:{api_port}/health")

        if not with_ui:
            return servers
        frontend = REPO / "frontend"
        if not (frontend / "node_modules").is_dir():
            servers.ui_skipped_reason = (
                "frontend/node_modules is absent — run `cd frontend && npm install` once (needs the "
                "registry); after that the demo runs with no network at all"
            )
            return servers
        if not port_is_free(ui_port):
            raise DemoError(f"port {ui_port} is already in use; stop the other dev server or pass --ui-port")
        npm = shutil.which("npm")
        if npm is None:  # pragma: no cover - node is installed wherever the UI is
            servers.ui_skipped_reason = "npm is not installed, so the dashboard cannot be served"
            return servers
        servers.ui = subprocess.Popen(
            [npm, "run", "dev", "--", "--host", "0.0.0.0", "--port", str(ui_port), "--strictPort"],
            cwd=frontend,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        wait_for(f"http://127.0.0.1:{ui_port}/", timeout_s=90.0)
        return servers
    except BaseException:
        servers.stop()
        raise


def probe_servers(run: DemoRun, servers: Servers) -> list[tuple[str, str]]:
    """Prove both servers answer, and that the API reproduces the in-process decision exactly."""
    checks: list[tuple[str, str]] = []
    api = f"http://127.0.0.1:{servers.api_port}"

    status, body = http_json(f"{api}/health")
    if status != 200:
        raise DemoError(f"/health returned {status}: {body[:200]}")
    checks.append(("API /health", f"200 {json.loads(body)['status']}"))

    status, body = http_json(f"{api}/v1/envelope/info")
    if status != 200:
        raise DemoError(f"/v1/envelope/info returned {status}: {body[:200]}")
    info = json.loads(body)
    if info["simulation_badge_required"] is not True:
        raise DemoError("the API did not ask for a simulation badge on a synthetic profile")
    checks.append(("API /v1/envelope/info", f"{len(info['rules'])} rules, profile {info['profile']}"))

    index = run.veto_index
    if index is None:  # pragma: no cover - verify_run() refuses this run first
        raise DemoError("the run has no veto to replay over HTTP")
    frame = run.frames[index]
    status, body = http_json(
        f"{api}/v1/envelope/evaluate",
        method="POST",
        payload={
            "snapshot": snapshot_at(frame, relay_open=False),
            "proposal": proposal_at(frame),
            "requested_mode": "normal",
        },
    )
    if status != 200:
        raise DemoError(f"/v1/envelope/evaluate returned {status}: {body[:300]}")
    over_http = json.loads(body)
    expected = run.decisions[index]
    if over_http["decision_id"] != expected["decision_id"]:
        raise DemoError(
            "the API produced a different decision_id for the same snapshot and proposal "
            f"({over_http['decision_id']} != {expected['decision_id']})"
        )
    checks.append(("API /v1/envelope/evaluate", f"same {over_http['rule_id']} decision as in-process"))

    if servers.ui is None:
        return checks

    ui = f"http://127.0.0.1:{servers.ui_port}"
    status, body = http_json(f"{ui}/")
    if status != 200 or 'id="root"' not in body:
        raise DemoError(f"the dashboard did not serve its entry page (status {status})")
    checks.append(("UI /", "200, mount point present"))

    status, body = http_json(f"{ui}/stats/headline.json")
    if status != 200:
        raise DemoError(f"/stats/headline.json returned {status}: {body[:200]}")
    headline = json.loads(body)["headline"]
    checks.append(
        (
            "UI /stats/headline.json",
            f"200 · {headline['actions_planned']} actions · "
            f"{headline['collisions_shipped_under_envelope']} shipped",
        )
    )
    return checks


# --------------------------------------------------------------------------- CLI


def print_serving(servers: Servers, checks: list[tuple[str, str]]) -> None:
    print()
    print("serving (Ctrl-C to stop)" if servers.ui is not None else "serving the API (Ctrl-C to stop)")
    print(f"  API  http://127.0.0.1:{servers.api_port}/health")
    if servers.ui is not None:
        print(f"  UI   http://127.0.0.1:{servers.ui_port}/")
    elif servers.ui_skipped_reason:
        print(f"  UI   not served: {servers.ui_skipped_reason}")
    for name, detail in checks:
        print(f"  PASS  {name:<26} {detail}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="The 10-second offline Reflex demo.")
    parser.add_argument("--serve", action="store_true", help="serve the API and dashboard until Ctrl-C")
    parser.add_argument("--check", action="store_true", help="serve, probe, then exit (for CI)")
    parser.add_argument("--no-ui", action="store_true", help="skip the dashboard (API only)")
    parser.add_argument("--api-port", type=int, default=API_PORT)
    parser.add_argument("--ui-port", type=int, default=UI_PORT)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER, help="where the demo ledger lands")
    parser.add_argument("--quiet", action="store_true", help="omit the timeline from the summary")
    args = parser.parse_args(argv)

    try:
        run = run_session(ledger_path=args.ledger)
        run.checks = verify_run(run)
    except DemoError as exc:
        print(f"DEMO FAIL — {exc}", file=sys.stderr)
        return 1

    report = render_report(run)
    if args.quiet:
        report = "\n".join(line for line in report.splitlines() if not line.startswith("  t="))
    print(report)

    if not (args.serve or args.check):
        return 0

    try:
        servers = start_servers(api_port=args.api_port, ui_port=args.ui_port, with_ui=not args.no_ui)
        checks = probe_servers(run, servers)
    except DemoError as exc:
        print(f"DEMO FAIL — {exc}", file=sys.stderr)
        return 1
    print_serving(servers, checks)

    if args.check:
        servers.stop()
        print()
        print("DEMO CHECK PASS — session, ledger, API and UI all answered; servers stopped")
        return 0

    # A SIGTERM (a CI timeout, a container stop) must clean up the two children just like Ctrl-C
    # does, or a stopped demo leaves a listener on :8000 and the next run fails for the wrong reason.
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))

    try:
        while True:
            time.sleep(0.5)
            for process in (servers.api, servers.ui):
                if process is not None and process.poll() is not None:
                    raise DemoError(f"a server exited unexpectedly (code {process.returncode})")
    except KeyboardInterrupt:
        print("\nstopping…")
    except DemoError as exc:
        print(f"DEMO FAIL — {exc}", file=sys.stderr)
        return 1
    finally:
        servers.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

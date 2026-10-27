#!/usr/bin/env python3
"""Export the 10-second demo session as a static bundle the dashboard can replay with no backend.

    python jobs/export_static_replay.py                    # -> frontend/public/replay/bundle.json
    python jobs/export_static_replay.py --out /tmp/replay  # somewhere else
    python jobs/export_static_replay.py --check            # validate the invariants, write nothing

Why this exists
---------------

The dashboard's normal mode is a *client*: it asks the API to evaluate a snapshot, and draws the
decision that comes back. On GitHub Pages there is no API — the site is static files. The tempting
shortcut is to make the browser decide, or to hand-write a plausible-looking session. Both would turn
a safety screen into a puppet show: the numbers on screen would no longer be produced by the envelope
that is supposed to be the point of the project.

So this job runs the **real** session (`jobs/offline_demo.py::run_session` — the same function
`make demo` uses), with the **real** envelope (`app.envelope.evaluate`), the **real** ledger
(`app.decision_ledger.record_decision`) and the **real** replay (`app.replay.compare`), and writes
everything those functions returned into one JSON file. The browser then replays a recording. It sends
no request that could be refused, and it computes no outcome, no clamp and no collision: scrubbing the
timeline moves through decisions that were made on this machine, by the code in `backend/app/envelope`.

What is in the bundle
---------------------

* ``info``      — byte-for-byte the body of ``GET /v1/envelope/info`` (same function, called directly),
                  so the Pages build shows the same rule table, profile and rig geometry.
* ``headline``  — ``runs/headline_statistics.json`` if it exists, else ``null``. The UI's existing
                  "no headline statistics" state handles the null; it is never replaced with zeros.
* ``frames``    — the scripted world: t, x, whether the keep-out volume is occupied. 100 rows.
* ``decisions`` — 100 ``$defs/EnvelopeDecision`` payloads, in frame order.
* ``replays``   — one two-arm ``ReplayResult`` comparison per decision id.
* ``checks``    — the six assertions from ``jobs/offline_demo.py::verify_run``, so the Pages build can
                  state the same claims the CLI does, and fails loudly at build time if they do not hold.

Honest scope
------------

The bundle is a recording, not a simulator. It cannot answer a snapshot that is not in it, and the page
says so. ``latency_us`` values are real measurements from the build that produced the file; a
regenerated bundle will differ in those numbers (and in the ledger's own timestamp-free ids) without
anything having changed. The session is SYNTHETIC: no hardware, no camera, no model, no network.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(REPO / "jobs"))

SCHEMA = "reflex.static_replay/1"
DEFAULT_OUT = REPO / "frontend" / "public" / "replay"
DEFAULT_STATS = REPO / "runs" / "headline_statistics.json"
DEFAULT_LEDGER = REPO / "runs" / "demo-veto-ledger.jsonl"


def _load_demo(jobs_dir: Path | None = None):
    """Load ``jobs/offline_demo.py`` by path.

    ``jobs/`` is not a package, and the demo is a script with a ``__main__`` guard. Importing it by
    path keeps one definition of the scripted world: if the demo changes, the bundle changes with it,
    and the two can never disagree about what happened at t=4.0 s.
    """
    path = (jobs_dir or REPO / "jobs") / "offline_demo.py"
    spec = importlib.util.spec_from_file_location("offline_demo_for_export", path)
    if spec is None or spec.loader is None:  # pragma: no cover - a broken checkout, not a code path
        raise SystemExit(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolves annotations through sys.modules: register before executing.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def envelope_info() -> dict[str, Any]:
    """The exact body of ``GET /v1/envelope/info``.

    Called through the FastAPI route function rather than rebuilt here: a second construction of this
    payload would drift from the endpoint the local dashboard reads, and a Pages build that runs a
    different rule table from the one in the repository is worse than no Pages build.
    """
    from app.main import envelope_info as route

    return dict(route())


def build_bundle(
    *,
    demo,
    stats_path: Path | str = DEFAULT_STATS,
    ledger_path: Path | str = DEFAULT_LEDGER,
) -> dict[str, Any]:
    """Run the session and return the bundle. No file is written here, so tests can call it."""
    run = demo.run_session(ledger_path=ledger_path)
    checks = demo.verify_run(run)

    info = envelope_info()
    # The local build reads a path on this machine; it means nothing to a browser. Say what the
    # static page is instead of shipping a path that does not exist on the viewer's disk.
    info["veto_ledger_path"] = "static bundle — no ledger is written from this page"

    stats: dict[str, Any] | None = None
    stats_file = Path(stats_path)
    if stats_file.exists():
        stats = json.loads(stats_file.read_text())
    else:
        print(
            f"  warning: {stats_file} does not exist; the headline bar will render its "
            "'no headline statistics' state (not zeros). Run `make batch` first.",
            file=sys.stderr,
        )

    frames = []
    decisions = []
    replays: dict[str, Any] = {}
    for frame, decision in zip(run.frames, run.decisions, strict=True):
        decisions.append(decision)
        frames.append(
            {
                "index": frame.index,
                "t_s": frame.t_s,
                "x_mm": frame.x_mm,
                "y_mm": 0.0,
                "keep_out_occupied": frame.keep_out_occupied,
                "decision_id": decision["decision_id"],
                "decided_at": decision["decided_at"],
            }
        )
        replay = run.replays.get(decision["decision_id"])
        if replay is not None:
            replays[decision["decision_id"]] = replay

    bundle = {
        "schema": SCHEMA,
        "generated_by": "jobs/export_static_replay.py",
        "source": (
            "jobs/offline_demo.py::run_session — app.envelope.evaluate + app.decision_ledger."
            "record_decision + app.replay.compare. Not a client-side simulation."
        ),
        "session": {
            "seconds": demo.SECONDS,
            "hz": demo.HZ,
            "start_x_mm": demo.START_X_MM,
            "speed_mm_s": demo.SPEED_MM_S,
            "target_x_mm": demo.TARGET_X_MM,
            "intrusion_at_s": demo.INTRUSION_AT_S,
            "frames": len(frames),
            "synthetic": True,
            "hardware": False,
            "model_calls": 0,
        },
        "info": info,
        "headline": stats,
        "frames": frames,
        "decisions": decisions,
        "replays": replays,
        "checks": [{"claim": claim, "evidence": evidence} for claim, evidence in checks],
    }
    return bundle


def validate_bundle(bundle: dict[str, Any], *, demo=None) -> list[tuple[str, str]]:
    """The invariants the Pages build depends on. Raises ``SystemExit`` with the reason on failure.

    These are the same claims ``make demo`` makes, checked against the artifact the browser will
    actually load — a bundle that loses its veto, or ships a collided envelope-on arm, is not
    publishable no matter how well the demo itself ran.
    """
    demo = demo or _load_demo()
    checks: list[tuple[str, str]] = []
    frames = bundle.get("frames") or []
    decisions = bundle.get("decisions") or []
    replays = bundle.get("replays") or {}

    if not frames or len(frames) != len(decisions):
        raise SystemExit(f"bundle has {len(frames)} frames and {len(decisions)} decisions")
    if len(frames) != int(bundle["session"]["frames"]):
        raise SystemExit("session.frames disagrees with the frames array")
    checks.append(("bundle is complete", f"{len(frames)} frames · {len(decisions)} decisions"))

    if len(replays) != len(decisions):
        raise SystemExit(f"{len(replays)} replays for {len(decisions)} decisions")
    checks.append(("every decision has both replay arms", f"{len(replays)} comparisons"))

    vetoes = [index for index, d in enumerate(decisions) if d["outcome"] == "VETO"]
    if not vetoes:
        raise SystemExit("no VETO in the bundle: there is nothing to demonstrate")
    first = vetoes[0]
    veto = decisions[first]
    if veto["rule_id"] != "V2_KEEP_OUT_OCCUPIED":
        raise SystemExit(f"first veto is {veto['rule_id']}, expected V2_KEEP_OUT_OCCUPIED")
    if veto["interlock_relay_opened"] is not True:
        raise SystemExit("the first veto did not open the interlock")
    checks.append(
        (
            "the veto is where the timeline says it is",
            f"frame {first} · t={frames[first]['t_s']:.1f} s · {veto['rule_id']}",
        )
    )

    if frames[first]["x_mm"] != demo.START_X_MM + demo.SPEED_MM_S * demo.INTRUSION_AT_S:
        raise SystemExit(
            f"tool tip is at {frames[first]['x_mm']} mm when the intruder appears, expected "
            f"{demo.START_X_MM + demo.SPEED_MM_S * demo.INTRUSION_AT_S} mm"
        )
    checks.append(
        (
            "the tool tip advances 10 → 70 mm",
            f"{frames[0]['x_mm']:.1f} → {frames[first]['x_mm']:.1f} mm in {demo.INTRUSION_AT_S:.1f} s",
        )
    )

    if any(decision["outcome"] != "VETO" for decision in decisions[first + 1 :]):
        raise SystemExit("a proposal after the veto was not refused; the interlock did not latch")
    if any(decision["shipped_action"] is not None for decision in decisions[first + 1 :]):
        raise SystemExit("a proposal after the veto shipped an action")
    checks.append(("the interlock latches", f"{len(decisions) - first - 1} later proposals refused"))

    collided_on = [
        decision_id
        for decision_id, comparison in replays.items()
        if comparison["envelope_on"]["outcome"] == "collided"
    ]
    if collided_on:
        raise SystemExit(f"{len(collided_on)} envelope-on arms collided; not publishable")
    checks.append(("nothing collided under the envelope", f"0 of {len(replays)} shipped arms collided"))

    comparison = replays[veto["decision_id"]]
    if comparison["envelope_off"]["outcome"] != "collided":
        raise SystemExit("the veto's envelope-off arm did not collide; there is nothing to prevent")
    contact = comparison["envelope_off"]["collision"]["contact_point"]
    if comparison["envelope_on"]["metrics"]["distance_mm"] != 0:
        raise SystemExit(
            f"the veto's envelope-on arm travelled {comparison['envelope_on']['metrics']['distance_mm']} mm"
        )
    checks.append(
        (
            "the refusal prevented a collision",
            f"off: {comparison['envelope_off']['collision']['with']} at "
            f"({contact['x']:.1f}, {contact['y']:.1f}) mm · on: {comparison['envelope_on']['outcome']}",
        )
    )

    return checks


def write_bundle(bundle: dict[str, Any], out_dir: Path) -> Path:
    """Write ``bundle.json`` plus a small ``index.json`` the page fetches first.

    Two files rather than one: ``index.json`` is tiny, so the page can show "loading the recorded
    session" with the real size and check count before the multi-megabyte decision array arrives.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(bundle, indent=None, separators=(",", ":"), sort_keys=True)
    target = out_dir / "bundle.json"
    target.write_text(payload + "\n")
    sha = hashlib.sha256(target.read_bytes()).hexdigest()

    index = {
        "schema": SCHEMA,
        "bundle": "bundle.json",
        "bytes": len(payload) + 1,
        "sha256": sha,
        "frames": len(bundle["frames"]),
        "decisions": len(bundle["decisions"]),
        "replays": len(bundle["replays"]),
        "checks": len(bundle["checks"]),
        "headline": bundle["headline"] is not None,
        "source": bundle["source"],
    }
    (out_dir / "index.json").write_text(json.dumps(index, indent=2) + "\n")
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export the demo session as a static replay bundle.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output directory")
    parser.add_argument("--stats", type=Path, default=DEFAULT_STATS, help="headline statistics to embed")
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER, help="where the session ledger lands")
    parser.add_argument(
        "--check", action="store_true", help="validate only (writes nothing, keeps the ledger)"
    )
    args = parser.parse_args(argv)

    demo = _load_demo()

    if args.check:
        # Validate what is already on disk: this is what CI runs, so a stale bundle fails the build
        # instead of being silently republished.
        target = args.out / "bundle.json"
        if not target.exists():
            print(f"  no bundle at {target}; run without --check to build one", file=sys.stderr)
            return 2
        bundle = json.loads(target.read_text())
        try:
            checks = validate_bundle(bundle, demo=demo)
        except SystemExit as exc:
            print(f"STATIC REPLAY CHECK FAIL — {exc}", file=sys.stderr)
            return 1
        print(f"  loaded {target} ({target.stat().st_size / 1024:.0f} KiB)")
        for claim, evidence in checks:
            print(f"  PASS  {claim:<42} {evidence}")
        print(f"\nSTATIC REPLAY CHECK PASS — {len(checks)} checks on the published bundle")
        return 0

    bundle = build_bundle(demo=demo, stats_path=args.stats, ledger_path=args.ledger)
    checks = validate_bundle(bundle, demo=demo)
    target = write_bundle(bundle, args.out)

    size_mib = target.stat().st_size / (1024 * 1024)
    print(
        f"  session   {len(bundle['frames'])} frames · {len(bundle['decisions'])} decisions · "
        f"{len(bundle['replays'])} two-arm replays"
    )
    print(
        f"  headline  {'embedded from ' + str(args.stats) if bundle['headline'] else 'absent (the bar will say so)'}"
    )
    for claim, evidence in checks:
        print(f"  PASS  {claim:<42} {evidence}")
    print(f"  wrote     {target} ({size_mib:.2f} MiB)")
    print(f"\nSTATIC REPLAY PASS — {len(checks)} checks; the page can replay this with no backend")
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised by `make pages-data`
    raise SystemExit(main())

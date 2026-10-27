#!/usr/bin/env python3
"""Cut the network, and show that the envelope refuses what it allowed a moment ago.

    python scripts/network_cut.py                     # against the API on localhost:8000
    python scripts/network_cut.py --api 127.0.0.1:8010
    python scripts/network_cut.py --dry-run           # print the two request bodies, send nothing

What it does
------------

The demo's own plan — the one from frame 0 of the recorded session — is posted twice to the *running*
API, unchanged except for the network in the snapshot:

    cloud_reachable: true   → the envelope allots the normal parameter set
    cloud_reachable: false  → the cloud has been unreachable for 9 s, so V8 degrades the parameter
    (9 000 ms stale)          set and the tighter TTL ceiling refuses the same plan

This is the claim shot 5 of the demo video makes, and it is a claim about the code, not about the
video: the second request is refused because 3 000 ms exceeds the degraded 2 000 ms ceiling, not
because the script decided anything. The script only builds two requests and prints what came back.

Exit status is 0 only if the first request was allowed under `normal` and the second was refused under
`degraded` — a green run of this script *is* the demonstration. Anything else exits 1 with the
response, so a broken envelope cannot be filmed as a working one.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
BUNDLE = REPO / "frontend" / "dist" / "replay" / "bundle.json"


def build_bodies(bundle_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Two request bodies from the recorded session: the same plan, two networks."""
    bundle = json.loads(bundle_path.read_text())
    decision = bundle["decisions"][0]
    snapshot = decision["sensor_snapshot_inline"]
    proposal = decision["intended_action"]

    plan = dict(proposal)
    plan["proposal_id"] = "p_network_cut"
    # 3 s: legal against the normal 5 s ceiling, illegal against the degraded 2 s one.
    plan["ttl_ms"] = 3000

    healthy = dict(snapshot, snapshot_id="s_cloud_reachable")
    cut = dict(
        snapshot,
        snapshot_id="s_network_cut",
        network={"cloud_reachable": False, "last_cloud_ok_ms_ago": 9000.0, "rtt_ms_p99": None},
    )
    return (
        {"snapshot": healthy, "proposal": plan, "requested_mode": "normal"},
        {"snapshot": cut, "proposal": plan, "requested_mode": "normal"},
    )


def post(api: str, body: dict[str, Any], *, timeout: float = 10.0) -> dict[str, Any]:
    request = urllib.request.Request(
        f"http://{api}/v1/envelope/evaluate",
        data=json.dumps(body).encode(),
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def summary(decision: dict[str, Any]) -> str:
    """One line per decision: the four fields the argument turns on."""
    return (
        f"  {decision['outcome']:<14}parameter_set={decision['parameter_set']:<9}"
        f"mode={decision['mode']:<11}rule={decision['rule_id'] or '—'}  "
        f"interlock={decision['interlock_relay_opened']}"
    )


def off_rules(decision: dict[str, Any]) -> list[dict[str, Any]]:
    return [entry for entry in decision.get("rule_trace", []) if entry.get("result") != "PASS"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cut the network and watch the envelope refuse.")
    parser.add_argument("--api", default="localhost:8000", help="host:port of a running API")
    parser.add_argument("--bundle", type=Path, default=BUNDLE, help="recorded session to take the plan from")
    parser.add_argument("--dry-run", action="store_true", help="print the bodies and exit")
    args = parser.parse_args(argv)

    if not args.bundle.exists():
        print(f"no recorded session at {args.bundle} — run `make pages-data` first", file=sys.stderr)
        return 2

    healthy_body, cut_body = build_bodies(args.bundle)

    if args.dry_run:
        print(json.dumps(healthy_body, indent=2))
        print(json.dumps(cut_body, indent=2))
        return 0

    print(f"POST {args.api}/v1/envelope/evaluate   cloud_reachable=true")
    try:
        healthy = post(args.api, healthy_body)
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"  unreachable: {exc}. Start it with `make serve`.", file=sys.stderr)
        return 2
    print(summary(healthy))
    print()

    print(f"POST {args.api}/v1/envelope/evaluate   cloud_reachable=false (stale 9000 ms)")
    cut = post(args.api, cut_body)
    print(summary(cut))
    for entry in off_rules(cut):
        detail = (entry.get("detail") or "").rstrip(".")
        print(f"  {entry['rule_id']:<22}{entry['result']:<9}{detail}")
    print()

    allowed_healthy = healthy["outcome"] == "ALLOW" and healthy["parameter_set"] == "normal"
    refused_cut = cut["outcome"] == "VETO" and cut["parameter_set"] == "degraded"
    if not (allowed_healthy and refused_cut):
        print(
            "NETWORK CUT FAIL — expected ALLOW/normal on a healthy link and VETO/degraded after the cut; "
            f"got {healthy['outcome']}/{healthy['parameter_set']} then {cut['outcome']}/{cut['parameter_set']}",
            file=sys.stderr,
        )
        return 1

    print(
        "NETWORK CUT PASS — the same plan was allowed under normal parameters and refused under "
        "degraded ones; nothing failed open"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

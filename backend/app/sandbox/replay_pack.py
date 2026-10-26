"""Package the replay ledger into an artifact that can be verified with no network at all.

The claim this module exists to support is the one from ``docs/PLATFORM-CAPABILITIES.md`` §3:
*"Save prepared inputs, verify them without a guest network interface."* A pack that needed the
internet to check would prove nothing, so the pack carries everything verification needs:

    manifest.json     the scene (rig, policy bounds, velocity ceilings), the counts,
                      a sha256 per file, and the pack's own digest
    decisions.jsonl   the recorded EnvelopeDecisions, canonical JSON, one per line
    replays.jsonl     two contract-valid $defs/ReplayResult records per decision

``verify_pack`` then does two independent things:

1. **integrity** — every file hashes to what the manifest says, nothing extra is present, and
   the pack digest recomputes;
2. **re-execution** — it re-runs ``app.replay.simulate`` for every decision and every arm and
   requires the recomputed record to equal the stored one byte for byte.

Step 2 is the one that matters. A digest proves "nobody edited this file"; only re-execution
proves "the number in the file follows from the inputs". A pack whose manifest was regenerated
after a hand-edited replay still fails here.

Honest scope: this packages and verifies. It does **not** call the Token Factory Sandbox API —
no client signature is quoted in the repo's platform notes, and inventing one would produce a
plausible artifact that had never run anywhere. ``sandbox_plan`` emits the exact offline command
to run inside the sandbox and marks the SDK call ``TODO_VERIFY(sandbox-sdk)``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

SCHEMA = "reflex.replay_pack/1"
MANIFEST = "manifest.json"
DECISIONS = "decisions.jsonl"
REPLAYS = "replays.jsonl"
PAYLOAD_FILES = (DECISIONS, REPLAYS)
ARMS = ("envelope_off", "envelope_on")


def _canonical(value: Any) -> str:
    """Stable JSON: sorted keys, no incidental whitespace. The hash depends on this."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_table(pack_dir: Path) -> dict[str, dict[str, Any]]:
    table: dict[str, dict[str, Any]] = {}
    for name in PAYLOAD_FILES:
        path = pack_dir / name
        data = path.read_bytes()
        table[name] = {"sha256": _sha256(data), "bytes": len(data), "lines": data.count(b"\n")}
    return table


def _digest(table: Mapping[str, Any]) -> str:
    """The pack digest: a hash over the sorted (name, sha256, bytes) triples."""
    lines = [f"{name}\0{entry['sha256']}\0{entry['bytes']}" for name, entry in sorted(table.items())]
    return _sha256("\n".join(lines).encode("utf-8"))


def content_digest(decisions: Sequence[Mapping[str, Any]], records: Sequence[Mapping[str, Any]]) -> str:
    """A digest of what the pack *says*, independent of how long each decision took to make.

    ``pack_sha256`` covers the bytes, and those change between runs because ``latency_us`` is
    a measurement. This digest covers the decisions' content addresses and the replays'
    trajectory hashes, so it identifies the session itself. Two packs with the same
    ``content_sha256`` are the same evidence, timing aside.
    """
    parts = [f"{decision.get('decision_id')}:{decision.get('determinism_hash')}" for decision in decisions]
    parts += [f"{record.get('replay_id')}:{record.get('trajectory_sha256')}" for record in records]
    return _sha256("\n".join(parts).encode("utf-8"))


def scene_from_ruleset(ruleset: Any) -> dict[str, Any]:
    """Everything the two arms need, copied out of the ruleset so the pack stands alone."""
    from app.envelope import envelope_version

    return {
        "rig": dict(ruleset.rig),
        "bounds": ruleset.policy.mapping("V5_WORKSPACE_BOUND", "allowed_volume"),
        "velocity_ceiling_mm_s": {
            "normal": ruleset.normal.number("V3_VELOCITY_LIMIT", "max_velocity_mm_s"),
            "degraded": ruleset.degraded.number("V3_VELOCITY_LIMIT", "max_velocity_mm_s"),
        },
        "envelope_version": envelope_version(ruleset),
    }


def build_pack(
    decisions: Sequence[Mapping[str, Any]],
    out_dir: Path | str,
    scene: Mapping[str, Any],
    *,
    records: Iterable[Mapping[str, Any]] | None = None,
    generated_by: str = "app.sandbox.replay_pack",
    notes: Sequence[str] = (),
) -> dict[str, Any]:
    """Write a pack and return its manifest.

    ``records`` lets a caller that has already replayed the session pass the results in rather
    than paying for 2,000 simulations twice. When omitted, they are computed here from
    ``scene`` alone — which is also what ``verify_pack`` does.
    """
    target = Path(out_dir)
    target.mkdir(parents=True, exist_ok=True)

    if records is None:
        records = replay_decisions(decisions, scene)
    replay_records = list(records)

    decisions_text = "".join(_canonical(decision) + "\n" for decision in decisions)
    replays_text = "".join(_canonical(record) + "\n" for record in replay_records)
    (target / DECISIONS).write_text(decisions_text, encoding="utf-8")
    (target / REPLAYS).write_text(replays_text, encoding="utf-8")

    table = _file_table(target)
    manifest: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_by": generated_by,
        "envelope_version": scene.get("envelope_version"),
        "simulator": replay_simulator(),
        "scene": dict(scene),
        "counts": {
            "decisions": len(decisions),
            "replay_records": len(replay_records),
            "arms_per_decision": len(ARMS),
        },
        "files": table,
        "pack_sha256": _digest(table),
        "content_sha256": content_digest(decisions, replay_records),
        "network_required": False,
        "verify_command": (
            f"python -m app.sandbox.replay_pack verify {target.name}   "
            "# from backend/, with the guest network disabled"
        ),
        "notes": [
            *notes,
            "Verification recomputes both arms from decisions.jsonl and the embedded scene; "
            "it reads no clock, no network and no file outside this directory.",
            "The 2-D swept-volume model covers position in x-y at the recorded end-effector z. "
            "Rules that stop the machine without a spatial witness (force, staleness, "
            "malformed plans) have no geometric counterfactual, and are recorded as such.",
        ],
    }
    (target / MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def replay_simulator() -> dict[str, str]:
    from app.replay import SIM_VERSION, SIMULATOR

    return {"name": SIMULATOR, "version": SIM_VERSION}


def replay_decisions(
    decisions: Sequence[Mapping[str, Any]], scene: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """Both arms for every decision, using only what the pack carries."""
    from app.replay import simulate

    records: list[dict[str, Any]] = []
    for decision in decisions:
        parameter_set = decision.get("parameter_set", "normal")
        ceiling = float(scene["velocity_ceiling_mm_s"].get(parameter_set, 0.0))
        for arm in ARMS:
            records.append(
                simulate(
                    decision,
                    arm,
                    rig=scene["rig"],
                    bounds=scene["bounds"],
                    max_velocity_mm_s=ceiling,
                )
            )
    return records


def _read_jsonl(path: Path) -> list[Any]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def verify_pack(pack_dir: Path | str) -> dict[str, Any]:
    """Verify a pack without the network. Returns a report; never raises on a bad pack."""
    from app.contracts import is_valid

    root = Path(pack_dir)
    problems: list[str] = []

    manifest_path = root / MANIFEST
    if not manifest_path.is_file():
        return {"ok": False, "problems": [f"{MANIFEST} is missing from {root}"], "checked": {}}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"ok": False, "problems": [f"{MANIFEST} is not valid JSON: {exc}"], "checked": {}}

    if manifest.get("schema") != SCHEMA:
        problems.append(f"manifest schema {manifest.get('schema')!r} is not {SCHEMA!r}")

    # 1. Integrity: the files, their hashes, and nothing else in the directory.
    listed: dict[str, Any] = manifest.get("files") or {}
    for name in PAYLOAD_FILES:
        path = root / name
        if not path.is_file():
            problems.append(f"{name} is missing")
            continue
        data = path.read_bytes()
        expected = listed.get(name) or {}
        actual: dict[str, Any] = {"sha256": _sha256(data), "bytes": len(data)}
        if expected.get("sha256") != actual["sha256"]:
            problems.append(f"{name}: sha256 {actual['sha256'][:12]}… does not match the manifest")
        if expected.get("bytes") != actual["bytes"]:
            problems.append(f"{name}: {actual['bytes']} bytes, manifest says {expected.get('bytes')}")

    present = {entry.name for entry in root.iterdir() if entry.is_file()}
    unexpected = present - set(PAYLOAD_FILES) - {MANIFEST}
    if unexpected:
        problems.append(f"unexpected file(s) in the pack: {sorted(unexpected)}")

    if listed and manifest.get("pack_sha256") != _digest(listed):
        problems.append("pack_sha256 does not recompute from the manifest's file table")

    if problems:
        # Stop before re-execution: with a broken container, any later result is noise.
        return {"ok": False, "problems": problems, "checked": {"integrity": False}}

    # 2. Re-execution: the stored records must follow from the stored inputs.
    scene = manifest.get("scene") or {}
    for key in ("rig", "bounds", "velocity_ceiling_mm_s"):
        if key not in scene:
            problems.append(f"manifest.scene.{key} is missing; the pack cannot be re-derived")
    if problems:
        return {"ok": False, "problems": problems, "checked": {"integrity": True, "replayed": False}}

    decisions = _read_jsonl(root / DECISIONS)
    stored = _read_jsonl(root / REPLAYS)
    expected_records = replay_decisions(decisions, scene)

    if manifest.get("content_sha256") != content_digest(decisions, stored):
        problems.append("content_sha256 does not match the decisions and replays in the pack")

    if len(stored) != len(expected_records):
        problems.append(f"{len(stored)} replay records stored, {len(expected_records)} expected")
    for index, (stored_record, expected_record) in enumerate(zip(stored, expected_records, strict=False)):
        if stored_record != expected_record:
            decision_id = stored_record.get("decision_id")
            problems.append(
                f"replay record {index} ({decision_id}/{stored_record.get('arm')}) does not "
                "re-derive from the stored decision"
            )
            if len(problems) > 8:
                problems.append("… further mismatches suppressed")
                break
        if not is_valid("ReplayResult", stored_record):
            problems.append(f"replay record {index} is not a valid $defs/ReplayResult")

    shipped_collisions = sum(
        1 for record in stored if record.get("arm") == "envelope_on" and record.get("outcome") == "collided"
    )
    if shipped_collisions:
        problems.append(
            f"{shipped_collisions} shipped action(s) collide under the envelope: "
            "this is the finding that must never pass verification silently"
        )

    counts = manifest.get("counts") or {}
    if counts.get("decisions") != len(decisions):
        problems.append(f"manifest says {counts.get('decisions')} decisions, file has {len(decisions)}")
    if counts.get("replay_records") != len(stored):
        problems.append(f"manifest says {counts.get('replay_records')} records, file has {len(stored)}")

    return {
        "ok": not problems,
        "problems": problems,
        "checked": {
            "integrity": True,
            "replayed": True,
            "decisions": len(decisions),
            "replay_records": len(stored),
            "shipped_collisions": shipped_collisions,
            "pack_sha256": manifest.get("pack_sha256"),
            "content_sha256": manifest.get("content_sha256"),
        },
    }


def sandbox_plan(pack_dir: Path | str, *, image: str = "jobs/Dockerfile") -> dict[str, Any]:
    """The exact steps to verify this pack inside a Token Factory Sandbox, network disabled."""
    name = Path(pack_dir).name
    return {
        "schema": "reflex.sandbox_plan/1",
        "network": "disabled",
        "why": (
            "With the guest network off, a passing verification proves the artifact is "
            "self-consistent and that no result was fetched from the internet."
        ),
        "image": {"source": image, "note": "built from the repository root; see jobs/Dockerfile"},
        "steps": [
            {"step": "prepare", "detail": "build the image once, resolve its immutable UUID"},
            {"step": "inject", "command": f"cp -r {name} /work/{name}"},
            {
                "step": "verify",
                "network": "disabled",
                "command": f"cd /app/backend && python -m app.sandbox.replay_pack verify /work/{name}",
                "expect": '{"ok": true, "checked": {"shipped_collisions": 0}}',
            },
        ],
        "sdk": {
            "status": "TODO_VERIFY(sandbox-sdk)",
            "detail": (
                "docs/PLATFORM-CAPABILITIES.md §3 names the Python SDK modules and the "
                "verify-with-networking-disabled cookbook but quotes no client signature. "
                "This ticket therefore ships the plan and the offline command; wiring the "
                "client is a separate, verifiable step once the SDK is available."
            ),
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build, verify or plan a network-off replay pack.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="package a decisions JSONL into a pack")
    build.add_argument("--ledger", required=True, help="JSONL of EnvelopeDecision")
    build.add_argument("--out", required=True, help="destination directory")
    build.add_argument("--quiet", action="store_true")

    verify = sub.add_parser("verify", help="verify a pack without the network")
    verify.add_argument("pack")
    verify.add_argument("--json", action="store_true", help="print the report as JSON")

    plan = sub.add_parser("sandbox-plan", help="print the network-off sandbox plan")
    plan.add_argument("pack")

    args = parser.parse_args(argv)

    if args.command == "build":
        from app.envelope import load_ruleset

        ledger = Path(args.ledger)
        if not ledger.is_file():
            print(f"error: no ledger at {ledger}", file=sys.stderr)
            return 2
        decisions = _read_jsonl(ledger)
        manifest = build_pack(decisions, args.out, scene_from_ruleset(load_ruleset()))
        if not args.quiet:
            print(f"packed {manifest['counts']['decisions']} decisions -> {Path(args.out)}")
            print(f"pack_sha256: {manifest['pack_sha256']}")
        return 0

    if args.command == "verify":
        report = verify_pack(args.pack)
        if args.json:
            print(json.dumps(report, indent=2))
        elif report["ok"]:
            checked = report["checked"]
            print(
                f"PASS - {checked['decisions']} decisions, {checked['replay_records']} replay "
                f"records re-derived offline; {checked['shipped_collisions']} shipped collisions"
            )
        else:
            print("FAIL - the pack does not verify:", file=sys.stderr)
            for problem in report["problems"]:
                print(f"  - {problem}", file=sys.stderr)
        return 0 if report["ok"] else 1

    print(json.dumps(sandbox_plan(args.pack), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""D-PAGES — the static replay bundle is the real session, and the page cannot invent one.

The GitHub Pages build has no backend, so the dashboard replays a *recording*: `frontend/public/replay/
bundle.json`, produced by `jobs/export_static_replay.py` from `jobs/offline_demo.py::run_session`.

These tests are about the two ways that arrangement could become dishonest, and they are the reason
the bundle is generated rather than written by hand:

1. the artifact drifting from the envelope — a bundle that no longer contains the veto, or that ships
   a collided envelope-on arm, would render as a working demo of a broken envelope;
2. the export quietly replacing the recording with a simulation of its own.

Every assertion below is on the bundle the page will fetch. `--check` (what CI runs) validates the
file on disk; the fixture here builds a fresh one in a temporary directory so the two paths cannot
disagree.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO = Path(__file__).resolve().parents[2]
JOBS = REPO / "jobs"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolves field annotations through sys.modules, so register before executing.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


export = _load("export_static_replay", JOBS / "export_static_replay.py")
demo = _load("offline_demo_for_pages_test", JOBS / "offline_demo.py")


@pytest.fixture(scope="module")
def bundle(tmp_path_factory) -> dict:
    stats = tmp_path_factory.mktemp("pages") / "headline_statistics.json"
    stats.write_text(
        json.dumps(
            {
                "headline": {"actions_planned": 1000, "vetoes_enforced": 420},
                "prevented": {"total": 248},
                "session": {"seed": 1},
            }
        )
    )
    return export.build_bundle(
        demo=demo, stats_path=stats, ledger_path=tmp_path_factory.mktemp("ledger") / "demo.jsonl"
    )


def test_the_bundle_carries_the_whole_session(bundle):
    assert bundle["schema"] == export.SCHEMA
    assert len(bundle["frames"]) == 100
    assert len(bundle["decisions"]) == 100
    assert len(bundle["replays"]) == 100


def test_the_bundle_is_the_envelope_output_not_a_summary(bundle):
    """Every decision must validate against the frozen contract — a summary could not."""
    from app.contracts import validate_payload

    for decision in bundle["decisions"]:
        validate_payload("EnvelopeDecision", decision)
    for comparison in bundle["replays"].values():
        validate_payload("ReplayResult", comparison["envelope_off"])
        validate_payload("ReplayResult", comparison["envelope_on"])


def test_the_rule_table_is_the_endpoints_own_payload(bundle):
    """Built by calling the FastAPI route, so the static page cannot show a different rule table."""
    from app.main import envelope_info

    assert bundle["info"]["rules"] == envelope_info()["rules"]
    assert bundle["info"]["envelope_version"] == envelope_info()["envelope_version"]


def test_the_veto_is_at_4_seconds_and_opens_the_interlock(bundle):
    first = next(index for index, d in enumerate(bundle["decisions"]) if d["outcome"] == "VETO")
    assert (first, bundle["frames"][first]["t_s"]) == (40, 4.0)
    assert bundle["decisions"][first]["rule_id"] == "V2_KEEP_OUT_OCCUPIED"
    assert bundle["decisions"][first]["interlock_relay_opened"] is True
    assert bundle["frames"][first]["x_mm"] == 70.0
    assert bundle["frames"][0]["x_mm"] == 10.0


def test_every_proposal_after_the_veto_is_refused(bundle):
    first = next(index for index, d in enumerate(bundle["decisions"]) if d["outcome"] == "VETO")
    later = bundle["decisions"][first + 1 :]
    assert len(later) == 59
    assert all(decision["outcome"] == "VETO" for decision in later)
    assert all(decision["shipped_action"] is None for decision in later)


def test_nothing_collided_under_the_envelope(bundle):
    shipped = [c for c in bundle["replays"].values() if c["envelope_on"]["outcome"] == "collided"]
    assert shipped == []


def test_the_veto_prevented_a_collision_that_the_unguarded_arm_records(bundle):
    veto = bundle["decisions"][40]
    comparison = bundle["replays"][veto["decision_id"]]
    off, on = comparison["envelope_off"], comparison["envelope_on"]
    assert off["outcome"] == "collided"
    assert off["collision"]["with"] == "keep_out_volume"
    assert off["collision"]["contact_point"] == {"x": 150.0, "y": 0.0}
    assert on["metrics"]["distance_mm"] == 0
    assert comparison["collision_prevented"] is True


def test_the_bundle_states_its_own_provenance(bundle):
    session = bundle["session"]
    assert session["synthetic"] is True
    assert session["hardware"] is False
    assert session["model_calls"] == 0
    assert "offline_demo.py" in bundle["source"]
    assert bundle["generated_by"].endswith("export_static_replay.py")


def test_the_build_checks_travel_with_the_bundle(bundle):
    """The page prints these under the timeline; they are verify_run's six claims, unchanged."""
    assert len(bundle["checks"]) == 6
    claims = [check["claim"] for check in bundle["checks"]]
    assert "the refusal prevented a collision" in claims


def test_absent_statistics_render_as_absent_not_as_zeros(tmp_path):
    """The headline bar must never manufacture '0 collisions shipped' out of a missing file."""
    result = export.build_bundle(
        demo=demo,
        stats_path=tmp_path / "does-not-exist.json",
        ledger_path=tmp_path / "demo.jsonl",
    )
    assert result["headline"] is None


def test_validation_refuses_a_bundle_whose_veto_was_lost(bundle):
    broken = json.loads(json.dumps(bundle))
    for decision in broken["decisions"]:
        if decision["outcome"] == "VETO":
            decision["outcome"] = "ALLOW"
    with pytest.raises(SystemExit, match="no VETO"):
        export.validate_bundle(broken, demo=demo)


def test_validation_refuses_a_bundle_where_the_envelope_shipped_a_collision(bundle):
    broken = json.loads(json.dumps(bundle))
    for comparison in broken["replays"].values():
        comparison["envelope_on"]["outcome"] = "collided"
    with pytest.raises(SystemExit, match="envelope-on arms collided"):
        export.validate_bundle(broken, demo=demo)


def test_validation_refuses_a_bundle_with_a_missing_replay(bundle):
    broken = json.loads(json.dumps(bundle))
    broken["replays"].pop(next(iter(broken["replays"])))
    with pytest.raises(SystemExit, match="replays for"):
        export.validate_bundle(broken, demo=demo)


def test_the_committed_bundle_passes_check_when_present():
    """`make pages-check`: the file CI validates must pass the same invariants.

    Skipped when the bundle has not been generated — it is a build artifact (`.gitignore`), so a
    fresh checkout legitimately has none, and a test that demanded one would turn `make test` red
    for the wrong reason.
    """
    target = export.DEFAULT_OUT / "bundle.json"
    if not target.exists():
        pytest.skip("no generated bundle; run `make pages-data` to create one")
    bundle = json.loads(target.read_text())
    checks = export.validate_bundle(bundle, demo=demo)
    assert len(checks) == 7
    index = json.loads((export.DEFAULT_OUT / "index.json").read_text())
    assert index["frames"] == len(bundle["frames"])
    assert index["bytes"] == target.stat().st_size

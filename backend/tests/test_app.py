"""The application must import and answer HTTP.

This is deliberately the cheapest possible test and it is the one that would have
caught the blocker: ``backend/app/__init__.py`` contained a literal backslash-n instead
of a newline, so *nothing* in the package could be imported — while the entire test
suite stayed green because no test ever imported the app.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import version
from app.config import Settings, settings

FIXTURES = Path(__file__).resolve().parents[2] / "data" / "fixtures" / "snapshots"


def _fixture(name: str):
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def test_package_imports():
    """If this fails, `make demo` and the container entrypoint are broken."""
    import app.main  # noqa: F401 - the import is the assertion


@pytest.fixture(scope="module")
def client():
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


def test_health_is_alive_and_honest(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["environment"] in {"development", "test", "production"}
    # Capabilities are reported as booleans. The envelope is implemented and says which
    # calibration profile it is running, so a reader can tell measured from synthetic.
    assert body["capabilities"]["envelope_implemented"] is True
    assert body["capabilities"]["envelope_state"] == "ok"
    assert isinstance(body["capabilities"]["nebius_credentials"], bool)
    assert body["envelope"]["profile"] == "sim_reference_v0"
    assert body["envelope"]["calibration_provenance"] == "synthetic"


def test_health_never_leaks_a_credential(client):
    body = client.get("/health").text
    for secret in (settings.nebius_api_key, settings.tavily_api_key):
        if secret:
            assert secret not in body


def test_info_reports_pinned_models_and_contract_provenance(client):
    body = client.get("/v1/info").json()
    assert body["track"] == "Physical AI"
    assert body["models"]["ultra"].startswith("nvidia/")
    build = body["build"]
    assert build["contract_version"] != "unknown", "contract schema_version must be readable in a checkout"
    assert build["taxonomy_rules"] == 10
    assert build["envelope_implemented"] is True
    assert len(build["taxonomy_version"]) == 64  # sha256 hex


def test_openapi_is_served(client):
    assert client.get("/openapi.json").status_code == 200


# ------------------------------------------------------------------ configuration


def test_settings_read_a_dotenv_file(tmp_path, monkeypatch):
    """Regression: fields were defined with ``os.getenv()`` and no env_file, so a .env
    file was silently ignored and a missing key defaulted to "mock-key"."""
    env_file = tmp_path / ".env"
    env_file.write_text("ENVIRONMENT=production\nNEBIUS_API_KEY=from-dotenv\n", encoding="utf-8")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)

    configured = Settings(_env_file=env_file)
    assert configured.environment == "production"
    assert configured.has_nebius_credentials is True


def test_settings_never_default_to_a_fake_key(monkeypatch):
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    configured = Settings(_env_file=None)
    assert configured.nebius_api_key == ""
    assert configured.has_nebius_credentials is False
    with pytest.raises(RuntimeError, match="NEBIUS_API_KEY is not set"):
        configured.require_nebius_credentials()


def test_secrets_are_hidden_from_repr():
    configured = Settings(_env_file=None, nebius_api_key="super-secret-value")
    assert "super-secret-value" not in repr(configured)


def test_version_helpers_are_stable():
    assert version.taxonomy_version() == version.taxonomy_version()
    assert version.taxonomy_rule_count() == 10


# ------------------------------------------------------------------ the envelope surface


def test_envelope_info_publishes_the_rule_table(client):
    """The UI must be able to render every rule and the numbers behind it."""
    body = client.get("/v1/envelope/info").json()
    assert body["profile"] == "sim_reference_v0"
    assert body["simulation_badge_required"] is True
    assert [rule["rule_id"] for rule in body["rules"]] == [
        "V1_EMERGENCY_STOP",
        "V2_KEEP_OUT_OCCUPIED",
        "V3_VELOCITY_LIMIT",
        "V4_FORCE_LIMIT",
        "V5_WORKSPACE_BOUND",
        "V6_COLLISION_PREDICTED",
        "V7_SENSOR_STALE",
        "V8_NETWORK_DEGRADED",
        "V9_PLAN_MALFORMED",
        "V10_HUMAN_PRESENCE",
    ]
    by_id = {rule["rule_id"]: rule for rule in body["rules"]}
    # V1 is a binary interlock: it has no parameters, and saying so is more useful than
    # inventing a default for it.
    assert by_id["V1_EMERGENCY_STOP"]["parameters"] == {"normal": {}, "degraded": {}}
    v3 = by_id["V3_VELOCITY_LIMIT"]["parameters"]
    assert v3["degraded"]["max_velocity_mm_s"] < v3["normal"]["max_velocity_mm_s"]
    assert body["envelope_version"].startswith("sha256:")


def test_evaluate_returns_a_valid_decision_and_writes_the_ledger(client, tmp_path):
    from app import decision_ledger

    case = _fixture("veto_v2_keepout")
    ledger = tmp_path / "veto.jsonl"
    original = decision_ledger.veto_ledger_path
    decision_ledger.veto_ledger_path = lambda: ledger  # type: ignore[assignment]
    try:
        response = client.post(
            "/v1/envelope/evaluate",
            json={"snapshot": case["snapshot"], "proposal": case["proposal"], "requested_mode": "normal"},
        )
    finally:
        decision_ledger.veto_ledger_path = original

    assert response.status_code == 200
    decision = response.json()
    assert decision["outcome"] == "VETO"
    assert decision["rule_id"] == "V2_KEEP_OUT_OCCUPIED"
    # Recorded, not merely returned: a decision that is not on disk did not happen.
    assert ledger.exists()
    assert json.loads(ledger.read_text(encoding="utf-8").strip())["decision_id"] == decision["decision_id"]


def test_evaluate_rejects_a_malformed_contract_at_the_boundary(client):
    response = client.post(
        "/v1/envelope/evaluate",
        json={
            "snapshot": {"snapshot_id": "s_1"},
            "proposal": {"proposal_id": "p_1"},
            "requested_mode": "normal",
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"]["contract"] == "SensorSnapshot"


def test_evaluate_rejects_an_unknown_mode(client):
    case = _fixture("pass_v1_estop")
    response = client.post(
        "/v1/envelope/evaluate",
        json={"snapshot": case["snapshot"], "proposal": case["proposal"], "requested_mode": "turbo"},
    )
    assert response.status_code == 422


def test_evaluate_rejects_extra_top_level_fields(client):
    """Unknown keys are a contract violation, not something to ignore."""
    case = _fixture("pass_v1_estop")
    response = client.post(
        "/v1/envelope/evaluate",
        json={"snapshot": case["snapshot"], "proposal": case["proposal"], "force": True},
    )
    assert response.status_code == 422

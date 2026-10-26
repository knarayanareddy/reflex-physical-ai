"""The application must import and answer HTTP.

This is deliberately the cheapest possible test and it is the one that would have
caught the blocker: ``backend/app/__init__.py`` contained a literal backslash-n instead
of a newline, so *nothing* in the package could be imported — while the entire test
suite stayed green because no test ever imported the app.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import version
from app.config import Settings, settings


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
    # Capabilities are reported as booleans; the envelope is not implemented yet and the
    # endpoint must say so rather than imply it is running.
    assert body["capabilities"]["envelope_implemented"] is False
    assert isinstance(body["capabilities"]["nebius_credentials"], bool)


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
    assert build["envelope_implemented"] is False
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

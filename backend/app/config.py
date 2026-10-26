"""Configuration, loaded from the environment and (optionally) a .env file.

Two rules that this module exists to enforce:

1. **No fake credentials.** ``NEBIUS_API_KEY`` used to default to the literal string
   ``"mock-key"``, which made a misconfigured deployment look healthy at ``/health``
   until the first real call. It now defaults to an empty string and is reported as a
   boolean capability, never as a value.
2. **The same settings object in every deployment mode.** Fields are declared once;
   pydantic-settings maps them from ``NEBIUS_API_KEY``-style environment variables and
   from ``backend/.env`` or the repository-root ``.env``, so ``.env.example`` at the
   repo root actually works.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime settings. Every field maps to an environment variable of the same name."""

    model_config = SettingsConfigDict(
        # backend/.env first (most specific), then the repo-root .env.
        env_file=(REPO_ROOT / "backend" / ".env", REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Nebius Token Factory -------------------------------------------------
    # Deliberately empty by default: a missing key must be visible, not masked.
    nebius_api_key: str = Field(default="", repr=False)
    nebius_base_url: str = "https://api.tokenfactory.nebius.com/v1/"

    # --- Optional / bonus track ----------------------------------------------
    tavily_api_key: str = Field(default="", repr=False)

    # --- Pinned model IDs -----------------------------------------------------
    model_ultra: str = "nvidia/Nemotron-3-Ultra-550b-a55b"
    model_super: str = "nvidia/nemotron-3-super-120b-a12b"
    model_nano: str = "nvidia/nemotron-3-nano"
    model_vision: str = "nvidia/cosmos-reason-2"

    # --- Runtime --------------------------------------------------------------
    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    sandbox_network_disabled: bool = True
    mock_external_calls: bool = False

    # Where telemetry is appended. Empty means the repository default
    # (``runs/ledger.jsonl``); set it explicitly in containers.
    ledger_path: str = ""
    # Where envelope decisions are appended (``runs/veto-ledger.jsonl`` by default).
    veto_ledger_path: str = ""

    @property
    def has_nebius_credentials(self) -> bool:
        return bool(self.nebius_api_key.strip())

    @property
    def has_tavily_credentials(self) -> bool:
        return bool(self.tavily_api_key.strip())

    def require_nebius_credentials(self) -> str:
        """Return the API key or raise a message that says what to do about it."""
        if not self.has_nebius_credentials:
            raise RuntimeError(
                "NEBIUS_API_KEY is not set. Copy .env.example to .env and add a Token Factory key, "
                "or run the offline path (make sample) which needs no key."
            )
        return self.nebius_api_key


settings = Settings()

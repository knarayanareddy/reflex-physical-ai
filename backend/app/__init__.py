"""Reflex — deterministic edge safety envelope.

The package is deliberately small: configuration, the HTTP surface, the
deterministic gate and the telemetry ledger. Safety-critical logic must remain
import-pure (no LLM or network clients) — see ``docs/SAFETY-CASE.md`` once the
envelope lands.
"""

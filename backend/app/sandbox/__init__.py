"""Sandbox-side tooling: artifacts that can be verified with the network switched off.

The interesting claim a sandbox makes is not "the code ran somewhere else". It is that the
artifact is **self-contained and self-consistent**: given the bytes, anyone can re-derive the
result without reaching a network, a database or a second file. ``replay_pack`` is the module
that turns the replay lane into that kind of artifact.

The exports are lazy on purpose. Importing this package must not import ``replay_pack``, or
``python -m app.sandbox.replay_pack`` — the command the sandbox plan tells you to run — emits a
``RuntimeWarning`` about the module already being in ``sys.modules``. A verification command
that prints a warning every time is a command people learn to ignore.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.sandbox.replay_pack import (
        DECISIONS,
        MANIFEST,
        REPLAYS,
        SCHEMA,
        build_pack,
        content_digest,
        scene_from_ruleset,
        verify_pack,
    )

__all__ = [
    "DECISIONS",
    "MANIFEST",
    "REPLAYS",
    "SCHEMA",
    "build_pack",
    "content_digest",
    "scene_from_ruleset",
    "verify_pack",
]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from app.sandbox import replay_pack

        return getattr(replay_pack, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

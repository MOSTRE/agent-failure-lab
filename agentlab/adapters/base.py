"""Session adapter protocol and auto-detection."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ..ingestion.normalize import normalize_records
from ..ingestion.schema import Trajectory


class SessionAdapter(Protocol):
    name: str

    def detect(self, path: Path) -> bool: ...
    def parse(self, path: Path) -> Trajectory: ...


def load_trajectory(path: Path) -> Trajectory:
    """Try each adapter in order; fall back to generic JSONL."""
    from .claude import ClaudeAdapter
    from .codex import CodexAdapter
    from .generic import GenericAdapter
    from .opencode import OpenCodeAdapter

    adapters = [ClaudeAdapter(), CodexAdapter(), OpenCodeAdapter(), GenericAdapter()]
    for adapter in adapters:
        try:
            if adapter.detect(path):
                return adapter.parse(path)
        except Exception:
            continue
    # Last resort: generic parse (raises a readable error on failure).
    return GenericAdapter().parse(path)


def supported_formats() -> list[str]:
    return ["generic-jsonl", "claude", "codex", "opencode"]

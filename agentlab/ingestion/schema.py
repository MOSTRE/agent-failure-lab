"""Normalized trajectory schema. Observable behavior only — no chain-of-thought."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

EventKind = Literal[
    "message",
    "tool_call",
    "tool_result",
    "file_read",
    "file_write",
    "shell_command",
    "test_run",
    "git_operation",
    "error",
    "checkpoint",
    "thought_metadata",
]


class TrajectoryEvent(BaseModel):
    index: int = Field(description="1-based sequence number in normalized trajectory")
    kind: str = Field(default="tool_call", description="One of the known event kinds")
    actor: str = Field(default="agent", description="'agent', 'user', 'system', or 'tool'")
    timestamp: str | None = None
    tool: str | None = None
    input: dict[str, Any] = Field(default_factory=dict)
    output: str | None = None
    files_changed: list[str] = Field(default_factory=list)
    files_read: list[str] = Field(default_factory=list)
    exit_code: int | None = None
    duration_ms: int | None = None
    test_passed: bool | None = None
    content: str | None = None
    role: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def text(self) -> str:
        """Best-effort searchable text for this event."""
        parts: list[str] = []
        for v in (self.content, self.output):
            if v:
                parts.append(str(v))
        if self.input:
            parts.append(str(self.input))
        if self.tool:
            parts.append(str(self.tool))
        return "\n".join(parts)


class Trajectory(BaseModel):
    task: str = ""
    events: list[TrajectoryEvent] = Field(default_factory=list)
    source_format: str = "generic-jsonl"
    session_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def tool_calls(self) -> list[TrajectoryEvent]:
        return [e for e in self.events if e.kind in ("tool_call", "shell_command", "file_write", "file_read", "test_run")]

    @property
    def test_runs(self) -> list[TrajectoryEvent]:
        return [e for e in self.events if e.kind == "test_run" or _looks_like_test(e)]

    @property
    def files_touched(self) -> list[str]:
        seen: list[str] = []
        for e in self.events:
            for f in e.files_changed:
                if f not in seen:
                    seen.append(f)
        return seen

    def window(self, start: int, end: int) -> list[TrajectoryEvent]:
        return [e for e in self.events if start <= e.index <= end]


def _looks_like_test(e: TrajectoryEvent) -> bool:
    blob = ((e.tool or "") + " " + str(e.input) + " " + (e.output or "")).lower()
    return any(k in blob for k in ("pytest", "npm test", "jest ", "go test", "cargo test", "vitest"))

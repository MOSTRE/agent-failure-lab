"""Normalize raw JSONL records into TrajectoryEvents.

The generic JSONL contract (documented in docs/benchmark-format.md and
docs/getting-started.md) accepts one JSON object per line with a `type` field:

    {"type": "message", "role": "user", "content": "Fix the auth timeout"}
    {"type": "tool_call", "tool": "read_file", "input": {"path": "src/auth.py"}}
    {"type": "tool_result", "output": "...", "exit_code": 0}
    {"type": "test_run", "input": {"command": "pytest"}, "output": "...", "exit_code": 1}
    {"type": "file_write", "input": {"path": "src/auth.py"}}
    {"type": "shell_command", "input": {"command": "pytest tests/auth"}}
    {"type": "error", "output": "Traceback ..."}
    {"type": "checkpoint", "content": "claimed success"}

Unknown fields are preserved in `metadata` so adapters can evolve
without breaking stored sessions.
"""
from __future__ import annotations

from typing import Any

from .schema import Trajectory, TrajectoryEvent

_KIND_ALIASES = {
    "message": "message",
    "user": "message",
    "assistant": "message",
    "tool_call": "tool_call",
    "toolcall": "tool_call",
    "tool_result": "tool_result",
    "toolresult": "tool_result",
    "file_read": "file_read",
    "read": "file_read",
    "file_write": "file_write",
    "write": "file_write",
    "edit": "file_write",
    "shell": "shell_command",
    "shell_command": "shell_command",
    "bash": "shell_command",
    "command": "shell_command",
    "test": "test_run",
    "test_run": "test_run",
    "tests": "test_run",
    "git": "git_operation",
    "git_operation": "git_operation",
    "error": "error",
    "checkpoint": "checkpoint",
    "thought_metadata": "thought_metadata",
}


def normalize_record(record: dict[str, Any], index: int) -> TrajectoryEvent:
    raw_type = str(record.get("type", record.get("kind", "tool_call"))).lower()
    kind = _KIND_ALIASES.get(raw_type, "tool_call")
    tool = record.get("tool") or record.get("name")
    inp = record.get("input") or {}
    if isinstance(inp, str):
        inp = {"command": inp}
    if not isinstance(inp, dict):
        inp = {"value": inp}

    # Some producers put the command at top level.
    for key in ("command", "path", "file"):
        if key in record and key not in inp:
            inp[key] = record[key]

    output = record.get("output", record.get("result", record.get("observation")))
    if output is not None and not isinstance(output, str):
        output = str(output)

    files_changed = _as_str_list(record.get("files_changed", inp.get("files_changed", [])))
    files_read = _as_str_list(record.get("files_read", inp.get("files_read", [])))
    # Single path shortcuts.
    path = inp.get("path") or inp.get("file")
    if path and kind in ("file_write", "file_read"):
        target = files_changed if kind == "file_write" else files_read
        if str(path) not in target:
            target.append(str(path))
    if kind == "tool_call" and tool in ("write_file", "edit_file", "apply_patch", "write"):
        p = inp.get("path") or inp.get("file")
        if p and str(p) not in files_changed:
            files_changed.append(str(p))
    if kind == "tool_call" and tool in ("read_file", "read"):
        p = inp.get("path") or inp.get("file")
        if p and str(p) not in files_read:
            files_read.append(str(p))

    exit_code = record.get("exit_code", inp.get("exit_code"))
    test_passed = record.get("test_passed", inp.get("test_passed"))
    if test_passed is None and kind == "test_run":
        if exit_code is not None:
            test_passed = exit_code == 0
        elif output:
            test_passed = _guess_test_outcome(str(output))

    known = {
        "type", "kind", "tool", "name", "input", "output", "result", "observation",
        "files_changed", "files_read", "exit_code", "duration_ms", "timestamp",
        "time", "actor", "role", "content", "text", "test_passed", "command",
        "path", "file",
    }
    metadata = {k: v for k, v in record.items() if k not in known}
    # Keep symbols / repo context if the session embeds it.
    for extra in ("known_symbols", "repo_files", "task", "session_id"):
        if extra in record and extra not in metadata:
            metadata[extra] = record[extra]

    return TrajectoryEvent(
        index=index,
        kind=kind,
        actor=str(record.get("actor", record.get("role", "agent") if kind != "message" else record.get("role", "user"))),
        timestamp=record.get("timestamp", record.get("time")),
        tool=str(tool) if tool else None,
        input=dict(inp),
        output=output,
        files_changed=files_changed,
        files_read=files_read,
        exit_code=exit_code if isinstance(exit_code, int) else None,
        duration_ms=record.get("duration_ms"),
        test_passed=test_passed,
        content=record.get("content", record.get("text")),
        role=record.get("role"),
        metadata=metadata,
    )


def normalize_records(records: list[dict[str, Any]], task: str = "", source_format: str = "generic-jsonl") -> Trajectory:
    events = [normalize_record(r, i + 1) for i, r in enumerate(records)]
    if not task:
        task = _infer_task(events)
    meta: dict[str, Any] = {}
    # Hoist session-level metadata (known symbols help the hallucinated-API detector).
    for e in events:
        for key in ("known_symbols", "repo_files", "session_id"):
            src = e.metadata.get(key)
            if src and key not in meta:
                meta[key] = src
    session_id = meta.pop("session_id", None) if isinstance(meta.get("session_id"), str) else None
    return Trajectory(task=task, events=events, source_format=source_format, session_id=session_id, metadata=meta)


def _infer_task(events: list[TrajectoryEvent]) -> str:
    for e in events:
        if e.kind == "message" and (e.role == "user" or e.actor == "user") and e.content:
            return e.content.strip()[:500]
    for e in events:
        if e.content:
            return e.content.strip()[:500]
    return ""


def _as_str_list(v: Any) -> list[str]:
    if v is None:
        return []
    if isinstance(v, str):
        return [v]
    try:
        return [str(x) for x in list(v)]
    except TypeError:
        return [str(v)]


def _guess_test_outcome(output: str) -> bool | None:
    low = output.lower()
    fail_markers = ["failed", "failure", "error", "traceback", "assertionerror", "✗", "✘"]
    pass_markers = ["passed", "ok", "✓", "✔"]
    has_fail = any(m in low for m in fail_markers)
    has_pass = any(m in low for m in pass_markers)
    if has_fail and not has_pass:
        return False
    if has_pass and not has_fail:
        return True
    return None

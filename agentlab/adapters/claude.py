"""Claude-style session adapter.

Claude Code / Anthropic export shapes vary by version, so this adapter is
deliberately tolerant: it detects records that look like Anthropic message
logs (``role``/``content`` blocks with ``tool_use`` / ``tool_result``) and
normalizes them into the shared trajectory model.

It never claims to support a private format — anything it cannot map falls
through to the generic record normalizer.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..ingestion.normalize import normalize_record, normalize_records
from ..ingestion.schema import Trajectory


class ClaudeAdapter:
    name = "claude"

    def detect(self, path: Path) -> bool:
        try:
            sample = path.read_text(encoding="utf-8", errors="replace")[:20000].lower()
        except OSError:
            return False
        markers = ("tool_use", "tool_result", "anthropic", "claude")
        generic_hint = '"type"' in sample and '"tool_call"' in sample
        if generic_hint:
            return False
        return any(m in sample for m in markers)

    def parse(self, path: Path) -> Trajectory:
        records = _read_records(path)
        normalized_inputs: list[dict[str, Any]] = []
        for rec in records:
            normalized_inputs.extend(_to_generic(rec))
        if not normalized_inputs:
            normalized_inputs = records
        traj = normalize_records(normalized_inputs, source_format=self.name)
        # Preserve explicitly stated task.
        task = _find_task(records)
        if task:
            traj.task = task
        return traj


def _read_records(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    out: list[dict[str, Any]] = []
    if not text:
        return out
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
        if isinstance(data, dict):
            for key in ("events", "messages", "turns", "transcript", "history"):
                if isinstance(data.get(key), list):
                    return [x for x in data[key] if isinstance(x, dict)]
            return [data]
    except json.JSONDecodeError:
        pass
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def _to_generic(rec: dict[str, Any]) -> list[dict[str, Any]]:
    """Map one Claude-ish record to one or more generic records."""
    rtype = str(rec.get("type", "")).lower()
    role = rec.get("role", rec.get("actor"))
    content = rec.get("content")

    # Assistant message with content blocks: [{"type": "text", ...}, {"type": "tool_use", ...}]
    if isinstance(content, list):
        mapped: list[dict[str, Any]] = []
        text_parts = []
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = str(block.get("type", "")).lower()
            if btype == "tool_use":
                mapped.append({
                    "type": "tool_call",
                    "tool": block.get("name", "tool"),
                    "input": block.get("input", {}),
                    "metadata": {"tool_use_id": block.get("id")},
                })
            elif btype == "tool_result":
                c = block.get("content", block.get("output", ""))
                if isinstance(c, list):
                    c = " ".join(str(x.get("text", x)) if isinstance(x, dict) else str(x) for x in c)
                mapped.append({
                    "type": "tool_result",
                    "output": c,
                    "metadata": {"tool_use_id": block.get("tool_use_id")},
                })
            elif btype == "text":
                text_parts.append(str(block.get("text", "")))
        if text_parts:
            mapped.insert(0, {"type": "message", "role": role or "assistant", "content": "\n".join(text_parts)})
        return mapped or [rec]

    if rtype in ("tool_use", "function_call"):
        return [{"type": "tool_call", "tool": rec.get("name", rec.get("tool", "tool")),
                 "input": rec.get("input", rec.get("arguments", {}))}]
    if rtype in ("tool_result", "function_result", "toolresult"):
        return [{"type": "tool_result", "output": rec.get("output", rec.get("content", rec.get("result"))),
                 "exit_code": rec.get("exit_code")}]
    if "tool_use_id" in rec and ("output" in rec or "content" in rec):
        return [{"type": "tool_result", "output": rec.get("output", rec.get("content"))}]
    if role in ("user", "assistant", "system") and isinstance(content, str):
        return [{"type": "message", "role": role, "content": content}]
    return [rec]


def _find_task(records: list[dict[str, Any]]) -> str:
    for rec in records:
        if rec.get("role") == "user" and isinstance(rec.get("content"), str):
            text = rec["content"].strip()
            if text:
                return text[:500]
        if isinstance(rec.get("task"), str) and rec["task"].strip():
            return rec["task"].strip()[:500]
    return ""

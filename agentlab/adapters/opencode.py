"""OpenCode-style session adapter.

OpenCode stores sessions as JSON (parts with `type: text | tool | ...`).
This adapter maps those parts onto the generic contract. Unknown part
types are kept as generic tool_call/tool_result records so no data is lost.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..ingestion.normalize import normalize_records
from ..ingestion.schema import Trajectory


class OpenCodeAdapter:
    name = "opencode"

    def detect(self, path: Path) -> bool:
        try:
            sample = path.read_text(encoding="utf-8", errors="replace")[:20000].lower()
        except OSError:
            return False
        if '"tool_call"' in sample:
            return False
        return "opencode" in sample or ('"parts"' in sample and '"tool"' in sample) or '"sessionid"' in sample.replace(" ", "")

    def parse(self, path: Path) -> Trajectory:
        records = _read_any(path)
        generic: list[dict[str, Any]] = []
        for rec in records:
            generic.extend(_to_generic(rec))
        traj = normalize_records(generic or records, source_format=self.name)
        task = _find_task(records)
        if task:
            traj.task = task
        return traj


def _read_any(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return []
    try:
        data = json.loads(text)
        if isinstance(data, list):
            flat: list[dict[str, Any]] = []
            for x in data:
                if isinstance(x, dict):
                    flat.extend(_unwrap(x))
            return flat
        if isinstance(data, dict):
            for key in ("parts", "events", "messages", "turns"):
                if isinstance(data.get(key), list):
                    flat = []
                    for x in data[key]:
                        if isinstance(x, dict):
                            flat.extend(_unwrap(x))
                    return flat
            return _unwrap(data)
    except json.JSONDecodeError:
        pass
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            out.extend(_unwrap(obj))
    return out


def _unwrap(rec: dict[str, Any]) -> list[dict[str, Any]]:
    # OpenCode nests: {"part": {...}} or {"message": {...}, "parts": [...]}
    if isinstance(rec.get("part"), dict):
        return _unwrap(rec["part"])
    if isinstance(rec.get("parts"), list):
        flat: list[dict[str, Any]] = []
        for p in rec["parts"]:
            if isinstance(p, dict):
                flat.extend(_unwrap(p))
        header_role = rec.get("role")
        return flat or [rec]
    return [rec]


def _to_generic(rec: dict[str, Any]) -> list[dict[str, Any]]:
    ptype = str(rec.get("type", "")).lower()
    if ptype == "text":
        text = rec.get("text", rec.get("content", rec.get("data", "")))
        if isinstance(text, str) and text.strip():
            return [{"type": "message", "role": rec.get("role", "assistant"), "content": text}]
        return [rec]
    if ptype in ("tool", "tool_use", "tool-call"):
        state = rec.get("state", {})
        output = ""
        if isinstance(state, dict):
            output = state.get("output", state.get("result", ""))
        return [{
            "type": "tool_call",
            "tool": rec.get("tool", rec.get("name", "tool")),
            "input": rec.get("input", rec.get("args", rec.get("parameters", {}))),
            "output": output or None,
        }]
    if ptype in ("tool_result", "result"):
        return [{"type": "tool_result", "output": rec.get("output", rec.get("content", rec.get("text"))),
                 "exit_code": rec.get("exit_code")}]
    if ptype in ("step_start", "step_finish", "snapshot"):
        return [{"type": "checkpoint", "content": rec.get("summary", ptype)}]
    if ptype == "error":
        return [{"type": "error", "output": rec.get("error", rec.get("message", "error"))}]
    if "tool" in rec and "input" in rec:
        return [{"type": "tool_call", "tool": rec.get("tool"), "input": rec.get("input", {})}]
    return [rec]


def _find_task(records: list[dict[str, Any]]) -> str:
    for rec in records:
        if rec.get("role") == "user" and isinstance(rec.get("text"), str) and rec["text"].strip():
            return rec["text"].strip()[:500]
        if rec.get("role") == "user" and isinstance(rec.get("content"), str) and rec["content"].strip():
            return rec["content"].strip()[:500]
    return ""

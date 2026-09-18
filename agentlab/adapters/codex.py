"""Codex-style session adapter.

Handles Codex CLI session logs (JSONL `response_item` / `function_call`
records and the newer `thread`-shaped exports). Like the other provider
adapters this is best-effort: anything unrecognized passes through to the
generic normalizer unchanged.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..ingestion.normalize import normalize_records
from ..ingestion.schema import Trajectory


class CodexAdapter:
    name = "codex"

    def detect(self, path: Path) -> bool:
        try:
            sample = path.read_text(encoding="utf-8", errors="replace")[:20000].lower()
        except OSError:
            return False
        if '"tool_call"' in sample and '"type"' in sample:
            return False
        return any(m in sample for m in ("response_item", "function_call", "codex", "reasoning_item"))

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
            return [x for x in data if isinstance(x, dict)]
        if isinstance(data, dict):
            for key in ("events", "items", "responses", "turns", "history", "thread"):
                if isinstance(data.get(key), list):
                    return [x for x in data[key] if isinstance(x, dict)]
            return [data]
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
            # Codex nests payloads under record / payload keys.
            if isinstance(obj.get("record"), dict):
                obj = obj["record"]
            out.append(obj)
    return out


def _to_generic(rec: dict[str, Any]) -> list[dict[str, Any]]:
    rtype = str(rec.get("type", "")).lower()
    if rtype in ("function_call", "custom_tool_call", "local_shell_call", "response_item"):
        payload = rec.get("payload", rec)
        if isinstance(payload, dict) and payload is not rec:
            return _to_generic({**payload, "type": payload.get("type", rtype)})
        name = rec.get("name", rec.get("tool", rec.get("command_name", "shell")))
        args = rec.get("arguments", rec.get("input", rec.get("command", {})))
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {"command": args}
        if not isinstance(args, dict):
            args = {"value": args}
        kind = "tool_call"
        low = str(name).lower() + " " + str(args).lower()
        if any(k in low for k in ("pytest", "jest", "npm test", "go test", "cargo test")):
            kind = "test_run"
        return [{"type": kind, "tool": str(name), "input": args}]
    if rtype in ("function_call_output", "function_result"):
        return [{"type": "tool_result", "output": rec.get("output", rec.get("result")),
                 "exit_code": rec.get("exit_code")}]
    if rtype == "message" and isinstance(rec.get("content"), str):
        return [{"type": "message", "role": rec.get("role", "user"), "content": rec["content"]}]
    if rtype == "message" and isinstance(rec.get("content"), list):
        texts = [b.get("text", "") if isinstance(b, dict) else str(b) for b in rec["content"]]
        return [{"type": "message", "role": rec.get("role", "user"), "content": " ".join(texts)}]
    return [rec]


def _find_task(records: list[dict[str, Any]]) -> str:
    for rec in records:
        if rec.get("role") == "user" and isinstance(rec.get("content"), str) and rec["content"].strip():
            return rec["content"].strip()[:500]
        # Codex "instructions" field often holds the task.
        if isinstance(rec.get("instructions"), str) and rec["instructions"].strip():
            return rec["instructions"].strip()[:500]
    return ""

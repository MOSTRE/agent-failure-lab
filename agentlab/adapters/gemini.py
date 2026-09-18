"""Gemini session support (partial).

The public Gemini CLI session format is not stable enough to hard-code, so
this module documents that fact and provides a tolerant fallback: anything
that is valid JSON/JSONL is normalized through the generic path, and records
that carry Gemini-ish markers (`functionCall`, `functionResponse`,
`groundingMetadata`) are mapped onto tool_call / tool_result.

If you export a Gemini session and it parses as generic JSONL, it works.
If Google stabilizes a format, add a strict parser here behind detection.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..ingestion.normalize import normalize_records
from ..ingestion.schema import Trajectory
from .codex import _read_any  # reuse the tolerant JSON/JSONL reader


class GeminiAdapter:
    name = "gemini"

    def detect(self, path: Path) -> bool:
        try:
            sample = path.read_text(encoding="utf-8", errors="replace")[:20000]
        except OSError:
            return False
        low = sample.lower()
        if '"tool_call"' in low:
            return False
        return "functioncall" in low.replace(" ", "") or "gemini" in low

    def parse(self, path: Path) -> Trajectory:
        records = _read_any(path)
        generic: list[dict[str, Any]] = []
        for rec in records:
            generic.extend(_to_generic(rec))
        return normalize_records(generic or records, source_format=self.name)


def _to_generic(rec: dict[str, Any]) -> list[dict[str, Any]]:
    # Gemini REST shape: {"content": {"parts": [{"functionCall": {...}}]}}
    content = rec.get("content")
    if isinstance(content, dict) and isinstance(content.get("parts"), list):
        mapped: list[dict[str, Any]] = []
        for part in content["parts"]:
            if not isinstance(part, dict):
                continue
            if "functionCall" in part:
                fc = part["functionCall"]
                mapped.append({"type": "tool_call", "tool": fc.get("name", "tool"),
                               "input": fc.get("args", {})})
            elif "functionResponse" in part:
                fr = part["functionResponse"]
                mapped.append({"type": "tool_result", "output": str(fr.get("response", ""))})
            elif "text" in part:
                mapped.append({"type": "message", "role": rec.get("role", "assistant"),
                               "content": str(part["text"])})
        if mapped:
            return mapped
    # camelCase single-part records.
    if "functionCall" in rec:
        fc = rec["functionCall"]
        return [{"type": "tool_call", "tool": fc.get("name", "tool"), "input": fc.get("args", {})}]
    if "functionResponse" in rec:
        return [{"type": "tool_result", "output": str(rec["functionResponse"])}]
    return [rec]

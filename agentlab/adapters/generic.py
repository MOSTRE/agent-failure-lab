"""Generic JSONL adapter — the stable contract of the project.

Accepts either newline-delimited JSON (one object per line) or a
whole-file JSON array / {"events": [...]} object. Every record goes
through ingestion.normalize so all adapters share one code path.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..ingestion.normalize import normalize_records
from ..ingestion.reader import read_json_maybe, read_jsonl
from ..ingestion.schema import Trajectory


class GenericAdapter:
    name = "generic-jsonl"

    def detect(self, path: Path) -> bool:
        return path.suffix.lower() in (".jsonl", ".json", ".ndjson", ".log")

    def parse(self, path: Path) -> Trajectory:
        text = path.read_text(encoding="utf-8", errors="replace")
        stripped = text.strip()
        records: list[dict] = []
        if path.suffix.lower() == ".json" and stripped.startswith(("[", "{")):
            # Heuristic: whole-file JSON vs JSONL with .json extension.
            first_line = stripped.splitlines()[0] if stripped else ""
            try:
                maybe_whole = json.loads(stripped)
                if isinstance(maybe_whole, (list, dict)) and not (
                    isinstance(maybe_whole, dict) and "type" in maybe_whole
                ):
                    if isinstance(maybe_whole, list):
                        records = [x for x in maybe_whole if isinstance(x, dict)]
                    elif isinstance(maybe_whole, dict):
                        for key in ("events", "messages", "turns", "history", "records"):
                            if isinstance(maybe_whole.get(key), list):
                                records = [x for x in maybe_whole[key] if isinstance(x, dict)]
                                break
                        else:
                            records = [maybe_whole]
                    task = ""
                    if isinstance(maybe_whole, dict) and isinstance(maybe_whole.get("task"), str):
                        task = maybe_whole["task"]
                    return normalize_records(records, task=task, source_format=self.name)
            except json.JSONDecodeError:
                pass
            void = first_line  # silence linters about unused
        # Default: streaming JSONL (tolerates one bad line without losing the session).
        try:
            records, _warnings = read_jsonl(path)
        except ValueError:
            records = read_json_maybe(path)
        task = ""
        return normalize_records(records, task=task, source_format=self.name)

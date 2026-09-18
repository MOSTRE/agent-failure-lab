"""Streaming JSONL reader with helpful errors."""
from __future__ import annotations

import json
from pathlib import Path


class SessionReadError(ValueError):
    pass


def read_jsonl(path: Path) -> tuple[list[dict], list[str]]:
    """Return (records, warnings). Recovers events before a malformed line."""
    records: list[dict] = []
    warnings: list[str] = []
    with path.open("r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                obj = json.loads(stripped)
            except json.JSONDecodeError as exc:
                warnings.append(
                    f"Line {lineno} could not be parsed ({exc.msg}). "
                    f"The previous {len(records)} events were recovered."
                )
                continue
            if isinstance(obj, dict):
                records.append(obj)
            else:
                warnings.append(f"Line {lineno} is not a JSON object and was skipped.")
    if not records:
        raise SessionReadError(
            f"{path} contains no parseable session events. "
            "Expected one JSON object per line (generic JSONL)."
        )
    return records, warnings


def read_json_maybe(path: Path) -> list[dict]:
    """Read a whole-file JSON session (single object or array) into records."""
    text = path.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SessionReadError(f"{path} is not valid JSON: {exc}") from exc
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        # Common shapes: {"events": [...]}, {"messages": [...]}, {"turns": [...]}
        for key in ("events", "messages", "turns", "history", "records"):
            if isinstance(data.get(key), list):
                items = data[key]
                return [x for x in items if isinstance(x, dict)]
        return [data]
    raise SessionReadError(f"{path} has an unrecognized JSON shape.")

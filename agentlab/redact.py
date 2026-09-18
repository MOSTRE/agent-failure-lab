"""Secret redaction for sessions and reports. Conservative: false positives beat leaks."""
from __future__ import annotations

import json
import re
from pathlib import Path

PATTERNS = [
    ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----")),
    ("api key", re.compile(r"\b(sk-[A-Za-z0-9_-]{8,}|xox[bpas]-[A-Za-z0-9-]{8,}|ghp_[A-Za-z0-9]{8,}|gho_[A-Za-z0-9]{8,}|AKIA[0-9A-Z]{16})\b")),
    ("bearer token", re.compile(r"\b[Bb]earer\s+[A-Za-z0-9\-._~+/=]{10,}")),
    ("password", re.compile(r"(?i)(password|passwd|pwd)\s*[:=]\s*['\"]?([^\s'\",;]+)['\"]?")),
    ("generic secret", re.compile(r"(?i)(api[_-]?key|secret|token)\s*[:=]\s*['\"]?([A-Za-z0-9\-._~+/=]{12,})['\"]?")),
    ("env assignment", re.compile(r"\b(OPENAI_API_KEY|ANTHROPIC_API_KEY|AWS_SECRET_ACCESS_KEY|GITHUB_TOKEN)=([^\s]+)")),
]

REDACTED = "[REDACTED]"


def redact_text(text: str) -> tuple[str, int]:
    count = 0
    for _name, rx in PATTERNS:
        text, n = rx.subn(REDACTED, text)
        count += n
    return text, count


def redact_file(path: Path, in_place: bool = False, output: Path | None = None) -> tuple[Path, int]:
    text = path.read_text(encoding="utf-8", errors="replace")
    total = 0
    lines = []
    for line in text.splitlines():
        # Try to keep JSONL valid: redact inside string values.
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                dumped = json.dumps(obj)
                red, n = redact_text(dumped)
                total += n
                lines.append(red)
                continue
        except json.JSONDecodeError:
            pass
        red, n = redact_text(line)
        total += n
        lines.append(red)
    out_text = "\n".join(lines) + "\n"
    if in_place:
        path.write_text(out_text, encoding="utf-8")
        return path, total
    dest = output or path.with_name(path.stem + ".redacted" + path.suffix)
    dest.write_text(out_text, encoding="utf-8")
    return dest, total


def scan_text(text: str) -> list[str]:
    hits = []
    for name, rx in PATTERNS:
        if rx.search(text):
            hits.append(name)
    return hits

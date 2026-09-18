"""Create a reproducible benchmark directory from a diagnosed session."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from ..diagnosis.analyzer import Diagnosis
from ..ingestion.schema import Trajectory
from .models import Benchmark, BenchmarkMeta, Verification


def slugify(text: str, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "benchmark").lower()).strip("-")
    return (slug or "benchmark")[:max_len].strip("-") or "benchmark"


def generate(
    trajectory: Trajectory,
    diagnosis: Diagnosis,
    source_path: Path | None = None,
    output_dir: Path = Path("benchmarks"),
    name: str | None = None,
) -> Path:
    category = diagnosis.category
    base = name or f"{category.replace('_', '-')}-{diagnosis.critical_step or 'x'}"
    # Avoid collisions: short task slug + critical step.
    task_slug = slugify(trajectory.task, 24)
    if task_slug != "benchmark" and task_slug not in base:
        base = f"{base}-{task_slug}"[:60]
    dest = output_dir / base
    counter = 2
    while dest.exists():
        dest = output_dir / f"{base}-{counter}"
        counter += 1
    dest.mkdir(parents=True)

    verification_cmd = _infer_verification(trajectory)
    bench = Benchmark(
        name=dest.name,
        description=f"{category} reproduced from agent session"
        + (f" (critical step {diagnosis.critical_step})" if diagnosis.critical_step else ""),
        task=trajectory.task or "(no task recorded in session)",
        category=category,
        base_commit=(trajectory.metadata.get("base_commit", "") or ""),
        verification=Verification(command=verification_cmd),
        metadata=BenchmarkMeta(
            difficulty=_difficulty(trajectory),
            tags=[category, trajectory.source_format],
            source_session=str(source_path) if source_path else None,
        ),
    )
    (dest / "benchmark.yaml").write_text(bench.to_yaml(), encoding="utf-8")
    (dest / "task.txt").write_text(bench.task + "\n", encoding="utf-8")
    (dest / "base-commit.txt").write_text((bench.base_commit or "unknown") + "\n", encoding="utf-8")
    (dest / "metadata.json").write_text(json.dumps({
        "name": bench.name,
        "category": bench.category,
        "critical_step": diagnosis.critical_step,
        "confidence": diagnosis.confidence,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_format": trajectory.source_format,
        "events": len(trajectory.events),
    }, indent=2) + "\n", encoding="utf-8")
    (dest / "README.md").write_text(_readme(bench, diagnosis), encoding="utf-8")
    (dest / "expected").mkdir(exist_ok=True)
    (dest / "expected" / "notes.md").write_text(
        "Describe the expected end state here (files, behavior, test outcome).\n", encoding="utf-8")
    verifier_dir = dest / "verifier"
    verifier_dir.mkdir(exist_ok=True)
    (verifier_dir / "run.sh").write_text(f"#!/bin/sh\nset -e\n{verification_cmd}\n", encoding="utf-8")
    evidence_dir = dest / "evidence"
    evidence_dir.mkdir(exist_ok=True)
    (evidence_dir / "diagnosis.json").write_text(
        json.dumps(diagnosis.to_dict(), indent=2) + "\n", encoding="utf-8")
    return dest


def _infer_verification(trajectory: Trajectory) -> str:
    for e in trajectory.events:
        if e.kind == "test_run":
            cmd = e.input.get("command") or e.input.get("cmd")
            if cmd:
                return str(cmd)
    # Guess from tool calls mentioning test runners.
    for e in trajectory.events:
        blob = str(e.input)
        for runner in ("pytest", "npm test", "npx jest", "go test ./...", "cargo test"):
            if runner in blob:
                return runner
    return "pytest -q"


def _difficulty(trajectory: Trajectory) -> str:
    n = len(trajectory.events)
    if n < 15:
        return "easy"
    if n < 60:
        return "medium"
    return "hard"


def _readme(bench: Benchmark, diagnosis: Diagnosis) -> str:
    return f"""# {bench.name}

{bench.description}

- Category: `{bench.category}`
- Critical step in source session: {diagnosis.critical_step or "n/a"}
- Diagnosis confidence: {diagnosis.confidence}

## Task

{bench.task}

## Verify

```bash
{bench.verification.command}
```

## Layout

- `benchmark.yaml` — stable machine-readable spec
- `task.txt` — the task given to the agent
- `verifier/run.sh` — runs the verification command
- `expected/` — describe the expected end state
- `evidence/diagnosis.json` — the original failure diagnosis
"""

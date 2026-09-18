"""Benchmark runner: isolated workspace, agent attempt, verification, report."""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from .models import Benchmark
from .verifier import VerificationResult, verify


@dataclass
class RunResult:
    benchmark: str
    agent: str
    passed: bool | None
    exit_code: int | None
    duration_ms: int
    verification_command: str | None
    output_tail: str
    workdir: str
    timestamp: str


def run_benchmark(
    benchmark: Benchmark,
    benchmark_dir: Path,
    agent: str = "manual",
    workdir: Path | None = None,
    keep_workdir: bool = False,
    timeout_seconds: int | None = None,
) -> tuple[RunResult, Path]:
    """Run verification for a benchmark in an isolated copy.

    Full agent execution (driving Claude/Codex/CLIs) is an explicit,
    opt-in extension point: by default the runner prepares the workspace,
    runs the benchmark's verification command, and records the result.
    When `--agent` names a CLI available on PATH and `--execute` is passed
    by future versions, that hook lives in `_maybe_drive_agent`.
    """
    started = time.time()
    tmp = Path(tempfile.mkdtemp(prefix="agentlab-")) if workdir is None else workdir
    if workdir is not None:
        tmp.mkdir(parents=True, exist_ok=True)

    # Isolated workspace: copy benchmark dir (never touch the user's tree).
    workspace = tmp / "workspace"
    if workspace.exists():
        shutil.rmtree(workspace)
    shutil.copytree(benchmark_dir, workspace)

    _maybe_checkout_base(workspace, benchmark.base_commit)
    _maybe_drive_agent(workspace, benchmark, agent)

    timeout = timeout_seconds or benchmark.verification.timeout_seconds
    vr: VerificationResult = verify(benchmark.verification.command, cwd=workspace, timeout_seconds=timeout)

    result = RunResult(
        benchmark=benchmark.name,
        agent=agent,
        passed=vr.passed,
        exit_code=vr.exit_code,
        duration_ms=int((time.time() - started) * 1000),
        verification_command=vr.command,
        output_tail=vr.output[-4000:],
        workdir=str(workspace),
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
    )
    runs_dir = benchmark_dir / "runs"
    runs_dir.mkdir(exist_ok=True)
    artifact = runs_dir / f"run-{result.timestamp.replace(':', '-')}-{agent}.json"
    artifact.write_text(json.dumps(asdict(result), indent=2), encoding="utf-8")

    if workdir is None and not keep_workdir:
        shutil.rmtree(tmp, ignore_errors=True)
        result.workdir = "<cleaned>"
    return result, artifact


def _maybe_checkout_base(workspace: Path, base_commit: str) -> None:
    if not base_commit or base_commit == "unknown":
        return
    # Only attempt when the workspace itself is a git repo; never touch the parent.
    if not (workspace / ".git").exists():
        return
    try:
        subprocess.run(["git", "checkout", "--quiet", base_commit],
                       cwd=str(workspace), capture_output=True, timeout=30)
    except Exception:
        pass


def _maybe_drive_agent(workspace: Path, benchmark: Benchmark, agent: str) -> None:
    """Extension point for live agent execution.

    Deliberately conservative: the runner must never invent agent output.
    Currently it records the intent and leaves execution to the operator
    (or a future --execute flag with explicit sandboxing).
    """
    marker = workspace / "runs" / f".agent-{agent}.txt"
    try:
        marker.parent.mkdir(exist_ok=True)
        marker.write_text(
            f"agent={agent}\ntask={benchmark.task[:200]}\n"
            "note=live agent execution is manual in v0.1; verification ran locally.\n",
            encoding="utf-8",
        )
    except OSError:
        pass

"""Run a verification command and interpret the result."""
from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class VerificationResult:
    passed: bool | None  # None == unverified (no command)
    exit_code: int | None
    output: str
    duration_ms: int
    command: str | None


def verify(command: str | None, cwd: Path, timeout_seconds: int = 120) -> VerificationResult:
    if not command or not command.strip():
        return VerificationResult(passed=None, exit_code=None, output="",
                                  duration_ms=0, command=None)
    start = time.time()
    try:
        proc = subprocess.run(
            command, shell=True, cwd=str(cwd), capture_output=True, text=True,
            timeout=timeout_seconds,
        )
        out = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
        return VerificationResult(
            passed=proc.returncode == 0,
            exit_code=proc.returncode,
            output=out[-8000:],
            duration_ms=int((time.time() - start) * 1000),
            command=command,
        )
    except subprocess.TimeoutExpired as exc:
        out = ((exc.stdout or b"").decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or ""))
        return VerificationResult(passed=False, exit_code=None,
                                  output=f"TIMEOUT after {timeout_seconds}s\n{out}"[-8000:],
                                  duration_ms=timeout_seconds * 1000, command=command)
    except FileNotFoundError as exc:
        return VerificationResult(passed=None, exit_code=None, output=f"Could not run command: {exc}",
                                  duration_ms=int((time.time() - start) * 1000), command=command)

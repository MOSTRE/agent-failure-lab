"""Score a run against its benchmark (pass/fail/unverified + notes)."""
from __future__ import annotations

from ..benchmark.runner import RunResult


def score_run(result: RunResult) -> dict:
    if result.passed is None:
        verdict = "UNVERIFIED"
    elif result.passed:
        verdict = "PASS"
    else:
        verdict = "FAIL"
    return {
        "benchmark": result.benchmark,
        "agent": result.agent,
        "verdict": verdict,
        "exit_code": result.exit_code,
        "duration_ms": result.duration_ms,
    }

"""Aggregate metrics for runs and battle comparisons."""
from __future__ import annotations

from ..ingestion.schema import Trajectory


def trajectory_metrics(trajectory: Trajectory) -> dict:
    tool_calls = len(trajectory.tool_calls)
    test_runs = [e for e in trajectory.events if e.kind == "test_run"]
    passed = sum(1 for e in test_runs if e.test_passed)
    failed = sum(1 for e in test_runs if e.test_passed is False)
    durations = [e.duration_ms or 0 for e in trajectory.events if e.duration_ms]
    tokens = trajectory.metadata.get("tokens")
    return {
        "events": len(trajectory.events),
        "tool_calls": tool_calls,
        "files_changed": len(trajectory.files_touched),
        "test_runs": len(test_runs),
        "tests_passed": passed,
        "tests_failed": failed,
        "duration_ms": sum(durations) if durations else None,
        "tokens": tokens if isinstance(tokens, int) else None,
    }

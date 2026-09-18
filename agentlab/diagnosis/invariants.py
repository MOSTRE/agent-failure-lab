"""Cheap invariant checks over a trajectory.

These are deliberately simple predicates (not ML). The analyzer combines
their outputs with per-category detectors.
"""
from __future__ import annotations

import re

from ..ingestion.schema import Trajectory, TrajectoryEvent

_SUCCESS_CLAIM = re.compile(r"\b(done|fixed|complete|completed|resolved|all tests? pass|success)\b", re.I)
_FAIL_WORD = re.compile(r"\b(fail|failed|failure|error|traceback|assert|not found|undefined|no such)\b", re.I)
_DESTRUCTIVE = re.compile(
    r"(rm\s+-rf|DROP\s+TABLE|DELETE\s+FROM\s+\w+\s*;?\s*$|--force|git\s+push\s+.*--force|"
    r"git\s+reset\s+--hard|mkfs|:\(\)\s*\{)",
    re.I,
)


def success_claims(trajectory: Trajectory) -> list[TrajectoryEvent]:
    return [e for e in trajectory.events if e.content and _SUCCESS_CLAIM.search(e.content)]


def failing_tests(trajectory: Trajectory) -> list[TrajectoryEvent]:
    out = []
    for e in trajectory.events:
        if e.kind == "test_run" and e.test_passed is False:
            out.append(e)
        elif e.kind == "tool_result" and e.exit_code not in (None, 0) and _looks_testy(e):
            out.append(e)
    return out


def _looks_testy(e: TrajectoryEvent) -> bool:
    blob = ((e.tool or "") + " " + (e.output or "")).lower()
    return any(k in blob for k in ("pytest", "jest", "test", "assert", "fail"))


def destructive_events(trajectory: Trajectory) -> list[TrajectoryEvent]:
    out = []
    for e in trajectory.events:
        blob = str(e.input) + "\n" + (e.output or "") + "\n" + (e.content or "")
        if _DESTRUCTIVE.search(blob):
            out.append(e)
    return out


def has_verification(trajectory: Trajectory) -> bool:
    return any(e.kind == "test_run" for e in trajectory.events)


def verification_passed(trajectory: Trajectory) -> bool | None:
    runs = [e for e in trajectory.events if e.kind == "test_run" and e.test_passed is not None]
    if not runs:
        return None
    return all(e.test_passed for e in runs)

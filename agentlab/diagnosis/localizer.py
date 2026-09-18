"""Critical-step localization.

The goal is the *earliest* meaningful action that caused the failure
cascade — not the final error. Each event gets an explainable score from
simple signals (first contradiction, first bad tool result, first failing
test, ...). The highest-scoring event wins; ties break toward the earlier
step because the first contradiction usually matters more than the final error.

Returns (critical_index, scores, reasons).
"""
from __future__ import annotations

import re

from ..ingestion.schema import Trajectory

_ERROR_WORDS = re.compile(r"\b(error|failed|failure|traceback|not found|undefined|no such|invalid|attributeerror|typeerror|referenceerror)\b", re.I)
_SYMBOL_CALL = re.compile(r"([A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)+)\s*\(")


def score_events(
    trajectory: Trajectory,
    hint_indices: list[int] | None = None,
    known_symbols: set[str] | None = None,
) -> tuple[int, dict[int, float], dict[int, str]]:
    scores: dict[int, float] = {}
    reasons: dict[int, str] = {}
    hint_set = set(hint_indices or [])
    events = trajectory.events
    if not events:
        return 0, {}, {}

    first_error_idx = _first_match(events, lambda e: bool(e.output and _ERROR_WORDS.search(e.output)))
    first_fail_idx = _first_match(events, lambda e: e.kind == "test_run" and e.test_passed is False)
    first_destructive_idx = _first_match(events, _is_destructive)

    for pos, e in enumerate(events):
        s = 0.0
        why: list[str] = []
        blob = ((e.tool or "") + " " + str(e.input) + " " + (e.output or "") + " " + (e.content or ""))

        if e.index in hint_set:
            s += 3.0
            why.append("flagged by failure detector")
        if e.kind in ("file_write", "tool_call", "shell_command") and e.output and _ERROR_WORDS.search(e.output):
            s += 2.0
            why.append("first invalid tool result" if e.index == first_error_idx else "invalid tool result")
        if e.kind == "test_run" and e.test_passed is False:
            s += 2.0
            why.append("first failing test" if e.index == first_fail_idx else "failing test")
        if _is_destructive(e):
            s += 2.5
            why.append("irreversible/destructive action")
        if e.kind == "file_write" and e.files_changed:
            s += 0.5
            why.append("modifies files")
        # Unknown dotted symbol that never appears elsewhere -> suspicious.
        for sym in _SYMBOL_CALL.findall(blob):
            if known_symbols and sym not in known_symbols and _symbol_is_rare(trajectory, sym, e.index):
                s += 2.2
                why.append(f"references unknown symbol {sym}")
                break
        # Edit-then-failure adjacency: an edit right before the first failure is suspect.
        if first_fail_idx and e.index < first_fail_idx <= e.index + 2 and e.kind in ("file_write", "tool_call"):
            s += 1.0
            why.append("immediately precedes first failure")
        # Early steps get a small bonus so ties resolve toward the origin of the cascade.
        s += max(0.0, 0.5 - pos * 0.02)

        # Downstream weight: mistakes with many later events score higher.
        later = len(events) - pos - 1
        if why:
            s += min(1.5, later * 0.08)

        scores[e.index] = round(s, 3)
        reasons[e.index] = "; ".join(why) if why else "no suspicious signal"

    critical = max(scores, key=lambda i: (scores[i], -i))
    # If nothing scored above background noise, there is no meaningful critical step.
    if all(v < 1.0 for v in scores.values()):
        return 0, scores, reasons
    return critical, scores, reasons


def downstream_impact(trajectory: Trajectory, critical: int) -> int:
    if not critical:
        return 0
    return sum(1 for e in trajectory.events if e.index > critical)


def recovery_opportunity(trajectory: Trajectory, critical: int) -> int | None:
    """First later step where the agent could plausibly have recovered.

    Heuristic: the first failing test, error result, or user/tool message
    after the critical step. Returns None when nothing looks like feedback.
    """
    if not critical:
        return None
    for e in trajectory.events:
        if e.index <= critical:
            continue
        if e.kind == "test_run" and e.test_passed is False:
            return e.index
        if e.kind in ("tool_result", "error") and e.output and _ERROR_WORDs(e.output):
            return e.index
        if e.kind == "message" and e.actor in ("user", "tool"):
            return e.index
    return None


def _ERROR_WORDs(output: str) -> bool:
    return bool(_ERROR_WORDS.search(output))


def _first_match(events, pred) -> int | None:
    for e in events:
        try:
            if pred(e):
                return e.index
        except Exception:
            continue
    return None


def _is_destructive(e) -> bool:
    import re as _re

    blob = str(e.input) + "\n" + (e.output or "")
    return bool(_re.search(r"(rm\s+-rf|DROP\s+TABLE|DELETE\s+FROM| --force|reset\s+--hard)", blob, _re.I))


def _symbol_is_rare(trajectory: Trajectory, sym: str, at: int) -> bool:
    count = 0
    for e in trajectory.events:
        if e.index == at:
            continue
        if sym in ((e.output or "") + str(e.input) + (e.content or "")):
            count += 1
    return count == 0

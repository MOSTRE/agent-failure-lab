"""Evidence collection: short, quotable snippets backing a diagnosis."""
from __future__ import annotations

from ..ingestion.schema import Trajectory, TrajectoryEvent


def snippet(event: TrajectoryEvent, max_len: int = 220) -> str:
    text = event.content or event.output or str(event.input) or event.kind
    text = " ".join(str(text).split())
    if len(text) > max_len:
        return text[: max_len - 1] + "…"
    return text


def describe(event: TrajectoryEvent) -> str:
    where = f"step {event.index}"
    what = event.tool or event.kind
    detail = snippet(event)
    return f"{where} [{what}]: {detail}"


def collect(trajectory: Trajectory, indices: list[int]) -> list[str]:
    by_index = {e.index: e for e in trajectory.events}
    out = []
    for i in indices:
        e = by_index.get(i)
        if e is not None:
            out.append(describe(e))
    return out

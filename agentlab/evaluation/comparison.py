"""Side-by-side comparison for `agentlab battle`."""
from __future__ import annotations

from ..benchmark.runner import RunResult
from .scoring import score_run


def compare(results: list[RunResult]) -> dict:
    rows = []
    for r in results:
        s = score_run(r)
        rows.append({
            "agent": r.agent,
            "verdict": s["verdict"],
            "time_ms": r.duration_ms,
            "exit_code": r.exit_code,
            "tool_calls": "N/A",
            "tokens": "N/A",
            "cost": "N/A",
        })
    winners = [row["agent"] for row in rows if row["verdict"] == "PASS"]
    return {"rows": rows, "winners": winners}

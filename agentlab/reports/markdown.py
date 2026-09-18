"""Markdown failure report."""
from __future__ import annotations

from ..diagnosis.analyzer import Diagnosis
from ..diagnosis.taxonomy import label
from ..ingestion.schema import Trajectory


def render(trajectory: Trajectory, diagnosis: Diagnosis, session: str = "") -> str:
    lines = [
        f"# Agent Failure Autopsy",
        "",
        f"**Task:** {trajectory.task or '(no task recorded)'}" if trajectory.task else "**Task:** (no task recorded)",
        "",
        f"**Result:** {'PASSED' if diagnosis.success else 'FAILED' if diagnosis.success is False else 'UNVERIFIED'}",
        f"**Failure:** `{diagnosis.category}` - {label(diagnosis.category)}",
        f"**Severity:** {diagnosis.severity} · **Confidence:** {diagnosis.confidence:.2f}",
        f"**Critical step:** {diagnosis.critical_step or 'n/a'}",
        f"**Downstream impact:** {diagnosis.downstream_impact} later actions",
        f"**Recovery opportunity:** step {diagnosis.recovery_opportunity}" if diagnosis.recovery_opportunity else "**Recovery opportunity:** none found",
        "",
        "## Explanation",
        "",
        diagnosis.explanation,
        "",
        "## Evidence",
        "",
    ]
    if diagnosis.evidence:
        lines += [f"- {e}" for e in diagnosis.evidence]
    else:
        lines.append("- (no direct evidence snippets)")
    lines += [
        "",
        "## Timeline (abridged)",
        "",
        "| Step | Kind | Tool | Detail |",
        "| --- | --- | --- | --- |",
    ]
    for e in trajectory.events[:80]:
        detail = (e.content or e.output or str(e.input))[:100].replace("\n", " ").replace("|", "\\|")
        lines.append(f"| {e.index} | {e.kind} | {e.tool or '-'} | {detail} |")
    if len(trajectory.events) > 80:
        lines.append(f"| … | | | {len(trajectory.events) - 80} more events |")
    lines += ["", "## Files touched", ""]
    if trajectory.files_touched:
        lines += [f"- `{f}`" for f in trajectory.files_touched]
    else:
        lines.append("- (none)")
    lines += [
        "",
        "## Signals by category",
        "",
        "| Category | Score |",
        "| --- | --- |",
    ]
    for cat, score in sorted(diagnosis.scores.items(), key=lambda kv: -kv[1]):
        lines.append(f"| `{cat}` | {score:.2f} |")
    lines += [
        "",
        "> Generated locally by Agent Failure Lab. No data left this machine.",
    ]
    if session:
        lines.insert(1, f"**Session:** `{session}`")
    return "\n".join(lines) + "\n"

"""Single-file HTML forensic report (no external assets, no network)."""
from __future__ import annotations

import html

from ..diagnosis.analyzer import Diagnosis
from ..diagnosis.taxonomy import label
from ..ingestion.schema import Trajectory


def render(trajectory: Trajectory, diagnosis: Diagnosis, session: str = "") -> str:
    esc = html.escape
    verdict = "PASSED ✅" if diagnosis.success else "FAILED ❌" if diagnosis.success is False else "UNVERIFIED ❓"
    rows = []
    for e in trajectory.events:
        detail = esc(((e.content or e.output or str(e.input))[:600]))
        cls = "critical" if e.index == diagnosis.critical_step else ""
        rec = " ← recovery point" if e.index == diagnosis.recovery_opportunity else ""
        rows.append(
            f'<tr class="{cls}"><td>{e.index}</td><td>{esc(e.kind)}</td>'
            f'<td>{esc(e.tool or "—")}</td><td>{detail}{rec}</td></tr>'
        )
    evidence = "".join(f"<li>{esc(x)}</li>" for x in diagnosis.evidence) or "<li>(none)</li>"
    files = "".join(f"<li><code>{esc(f)}</code></li>" for f in trajectory.files_touched) or "<li>(none)</li>"
    scores = "".join(
        f"<tr><td><code>{esc(k)}</code></td><td>{v:.2f}</td></tr>"
        for k, v in sorted(diagnosis.scores.items(), key=lambda kv: -kv[1])
    )
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Agent Failure Autopsy — {esc(diagnosis.category)}</title>
<style>
body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;max-width:960px;margin:2rem auto;padding:0 1rem;color:#1c2333;background:#fbfcfe}}
.card{{background:#fff;border:1px solid #e3e8f2;border-radius:12px;padding:1.2rem 1.4rem;margin-bottom:1rem;box-shadow:0 1px 2px rgba(20,30,60,.05)}}
.badge{{display:inline-block;padding:.2rem .6rem;border-radius:999px;background:#101828;color:#fff;font-size:.8rem}}
.badge.fail{{background:#b42318}}.badge.pass{{background:#027a48}}.badge.unv{{background:#475467}}
table{{width:100%;border-collapse:collapse;font-size:.9rem}}th,td{{text-align:left;padding:.4rem .5rem;border-bottom:1px solid #edf0f6;vertical-align:top}}
tr.critical td{{background:#fff7e6;font-weight:600}}
code{{background:#f2f4f9;padding:.1rem .35rem;border-radius:6px}}
h1{{font-size:1.5rem}}h2{{font-size:1.1rem;margin-top:0}}
.muted{{color:#667085}}
</style></head><body>
<div class="card"><div class="muted">AGENT FAILURE LAB · FORENSIC REPORT</div>
<h1>Agent Failure Autopsy</h1>
<p><span class="badge {'pass' if diagnosis.success else 'fail' if diagnosis.success is False else 'unv'}">{verdict}</span>
<span class="badge">{esc(label(diagnosis.category))}</span></p>
<p><strong>Task:</strong> {esc(trajectory.task or '(no task recorded)')}</p>
<p class="muted">Session: {esc(session)} · Source: {esc(trajectory.source_format)} · Events: {len(trajectory.events)}</p>
<p>{esc(diagnosis.explanation)}</p>
<table>
<tr><th>Critical step</th><td>{diagnosis.critical_step or 'n/a'}</td></tr>
<tr><th>Confidence</th><td>{diagnosis.confidence:.2f} ({esc(diagnosis.severity)})</td></tr>
<tr><th>Downstream impact</th><td>{diagnosis.downstream_impact} later actions</td></tr>
<tr><th>Recovery opportunity</th><td>{diagnosis.recovery_opportunity or 'none found'}</td></tr>
</table></div>
<div class="card"><h2>Evidence</h2><ul>{evidence}</ul></div>
<div class="card"><h2>Timeline</h2><table><tr><th>#</th><th>Kind</th><th>Tool</th><th>Detail</th></tr>{''.join(rows)}</table></div>
<div class="card"><h2>Files touched</h2><ul>{files}</ul><h2>Signals by category</h2><table>{scores}</table></div>
<p class="muted">Generated locally by Agent Failure Lab. No data left this machine.</p>
</body></html>
"""

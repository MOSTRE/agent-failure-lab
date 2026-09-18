"""Local SVG share card — no API, no network."""
from __future__ import annotations

import xml.sax.saxutils as sax

from ..diagnosis.analyzer import Diagnosis
from ..diagnosis.taxonomy import label


def render_svg(diagnosis: Diagnosis, agent: str = "agent", stats: str = "") -> str:
    cat = sax.escape(label(diagnosis.category).upper())
    step = diagnosis.critical_step or "—"
    ag = sax.escape(agent)
    stats_esc = sax.escape(stats)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="640" height="320" role="img">
<rect width="640" height="320" rx="16" fill="#0b1020"/>
<rect x="24" y="24" width="592" height="272" rx="12" fill="none" stroke="#2b3b5c" stroke-width="2"/>
<text x="48" y="66" font-family="monospace" font-size="18" fill="#8ea2c8">AGENT FAILURE LAB</text>
<text x="48" y="104" font-family="monospace" font-size="22" fill="#ffffff">{ag} · FAILED AT STEP {step}</text>
<text x="48" y="152" font-family="monospace" font-size="34" font-weight="bold" fill="#ffb224">{cat}</text>
<text x="48" y="190" font-family="monospace" font-size="16" fill="#c6d3ea">{stats_esc}</text>
<text x="48" y="228" font-family="monospace" font-size="16" fill="#7ee2a8">{"Recovery opportunity found" if diagnosis.recovery_opportunity else "No recovery point"}</text>
<text x="48" y="268" font-family="monospace" font-size="14" fill="#5b6b8c">every failure should become a test</text>
</svg>
"""

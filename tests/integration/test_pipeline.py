"""End to end: JSONL -> trajectory -> diagnosis -> benchmark -> report."""
from pathlib import Path

from agentlab.adapters.base import load_trajectory
from agentlab.benchmark import generator as gen
from agentlab.benchmark.models import Benchmark
from agentlab.diagnosis.analyzer import analyze
from agentlab.reports import html as html_report
from agentlab.reports import markdown as md_report

DEMO = Path(__file__).resolve().parent.parent.parent / "examples" / "sessions" / "demo.jsonl"


def test_full_pipeline(tmp_path):
    traj = load_trajectory(DEMO)
    assert len(traj.events) == 21

    diag = analyze(traj)
    assert diag.category == "hallucinated_api"

    dest = gen.generate(traj, diag, source_path=DEMO, output_dir=tmp_path / "benchmarks")
    bench = Benchmark.load(dest)
    assert bench.name == dest.name

    md = md_report.render(traj, diag)
    html = html_report.render(traj, diag)
    assert "hallucinated_api" in md and "hallucinated_api" in html

    (tmp_path / "report.md").write_text(md, encoding="utf-8")
    (tmp_path / "report.html").write_text(html, encoding="utf-8")


def test_malformed_input_still_diagnoses():
    traj = load_trajectory(
        Path(__file__).resolve().parent.parent / "fixtures" / "malformed.jsonl"
    )
    assert len(traj.events) == 3  # bad line skipped, everything else recovered
    diag = analyze(traj)
    assert diag.category  # any best-guess category, honestly scored

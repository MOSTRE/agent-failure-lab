"""Reports, share card, redaction, taxonomy, evaluation."""
from pathlib import Path

from agentlab.adapters.base import load_trajectory
from agentlab.diagnosis.analyzer import analyze
from agentlab.diagnosis.taxonomy import CATEGORIES
from agentlab.evaluation.comparison import compare
from agentlab.evaluation.metrics import trajectory_metrics
from agentlab.evaluation.scoring import score_run
from agentlab.benchmark.runner import RunResult
from agentlab.redact import redact_file, redact_text
from agentlab.reports import html as html_report
from agentlab.reports import markdown as md_report
from agentlab.reports.share_card import render_svg

DEMO = Path(__file__).resolve().parent.parent.parent / "examples" / "sessions" / "demo.jsonl"


def _diag():
    return analyze(load_trajectory(DEMO))


def test_taxonomy_covers_spec_categories():
    for cat in ("hallucinated_api", "wrong_file", "ignored_existing_code",
                "ignored_test_failure", "missing_test_execution", "scope_creep",
                "requirement_misread", "destructive_change", "stale_context",
                "infinite_repair_loop", "partial_success", "premature_completion"):
        assert cat in CATEGORIES


def test_markdown_report_has_sections():
    traj = load_trajectory(DEMO)
    text = md_report.render(traj, _diag(), session="demo.jsonl")
    for section in ("## Evidence", "## Timeline", "## Files touched", "hallucinated_api"):
        assert section in text


def test_html_report_is_standalone():
    traj = load_trajectory(DEMO)
    text = html_report.render(traj, _diag())
    assert "<html" in text and "Critical step" in text
    assert "http" not in text.replace("lang=\"en\"", ""), "no external assets allowed"


def test_share_card_svg():
    svg = render_svg(_diag(), agent="claude", stats="43 tool calls")
    assert svg.startswith("<svg") and "HALLUCINATED" in svg


def test_redaction_catches_common_secrets(tmp_path):
    text, n = redact_text("key = 'sk-abcdefgh12345678' and password: hunter2-hunter2")
    assert n >= 1 and "sk-abcdefgh" not in text
    p = tmp_path / "s.jsonl"
    p.write_text('{"type": "message", "content": "token=abcdefgh1234567890"}\n', encoding="utf-8")
    dest, count = redact_file(p)
    assert dest.exists() and count >= 1


def test_metrics_and_scoring():
    traj = load_trajectory(DEMO)
    m = trajectory_metrics(traj)
    assert m["tool_calls"] == 11 and m["tests_failed"] == 4
    r = RunResult("b", "claude", True, 0, 12, "pytest -q", "ok", "w", "t")
    assert score_run(r)["verdict"] == "PASS"
    assert compare([r])["winners"] == ["claude"]
    r2 = RunResult("b", "codex", None, None, 5, None, "", "w", "t")
    assert score_run(r2)["verdict"] == "UNVERIFIED"

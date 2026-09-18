"""CLI smoke tests through Typer's test runner."""
from pathlib import Path

from typer.testing import CliRunner

from agentlab.cli import app

runner = CliRunner()
DEMO = str(Path(__file__).resolve().parent.parent.parent / "examples" / "sessions" / "demo.jsonl")


def test_analyze_terminal():
    result = runner.invoke(app, ["analyze", DEMO])
    assert result.exit_code == 0, result.output
    assert "HALLUCINATED_API" in result.output


def test_analyze_json_and_inspect():
    result = runner.invoke(app, ["diagnose", DEMO, "--format", "json"])
    assert result.exit_code == 0, result.output
    assert '"hallucinated_api"' in result.output
    result = runner.invoke(app, ["inspect", DEMO])
    assert result.exit_code == 0


def test_promote_and_benchmark_commands(tmp_path):
    out = tmp_path / "benchmarks"
    result = runner.invoke(app, ["promote", DEMO, "--output", str(out)])
    assert result.exit_code == 0, result.output
    created = list(out.iterdir())
    assert len(created) == 1
    result = runner.invoke(app, ["benchmark", "list", "--dir", str(out)])
    assert result.exit_code == 0
    name = created[0].name
    result = runner.invoke(app, ["benchmark", "show", name, "--dir", str(out)])
    assert result.exit_code == 0 and "hallucinated_api" in result.output


def test_doctor_and_missing_file():
    assert runner.invoke(app, ["doctor"]).exit_code == 0
    assert runner.invoke(app, ["analyze", "nope.jsonl"]).exit_code == 2

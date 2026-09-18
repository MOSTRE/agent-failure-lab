"""Suite resolution, running, and rendering."""
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from agentlab.benchmark import suite as suitemod
from agentlab.benchmark.models import Benchmark
from agentlab.cli import app

runner = CliRunner()


def _bench(tmp_path: Path, name: str, ok: bool = True) -> Path:
    d = tmp_path / name
    d.mkdir()
    cmd = f'"{sys.executable}" -c "pass"' if ok else f'"{sys.executable}" -c "import sys; sys.exit(1)"'
    (d / "benchmark.yaml").write_text(
        f"version: 1\nname: {name}\ndescription: t\ntask: |\n  do it\n"
        f"category: premature_completion\nbase_commit: unknown\n"
        f"verification:\n  command: '{cmd}'\n  timeout_seconds: 30\n",
        encoding="utf-8",
    )
    return d


def _suite_file(tmp_path: Path, names: list[str]) -> Path:
    p = tmp_path / "core.yaml"
    p.write_text("version: 1\nname: core\nbenchmarks:\n" + "".join(f"  - {n}\n" for n in names),
                 encoding="utf-8")
    return p


def test_resolve_from_benchmarks_dir(tmp_path):
    _bench(tmp_path, "a", ok=True)
    _bench(tmp_path, "b", ok=False)
    name, entries = suitemod.resolve_suite(tmp_path, tmp_path)
    assert len(entries) == 2


def test_resolve_from_suite_file(tmp_path):
    _bench(tmp_path, "a", ok=True)
    suite = _suite_file(tmp_path, ["a"])
    name, entries = suitemod.resolve_suite(suite, tmp_path)
    assert name == "core" and len(entries) == 1


def test_resolve_missing_entry_errors(tmp_path):
    suite = _suite_file(tmp_path, ["nope"])
    with pytest.raises(FileNotFoundError):
        suitemod.resolve_suite(suite, tmp_path)


def test_run_all_counts_and_exit(tmp_path):
    _bench(tmp_path, "good", ok=True)
    _bench(tmp_path, "bad", ok=False)
    suite = _suite_file(tmp_path, ["good", "bad"])
    _name, entries = suitemod.resolve_suite(suite, tmp_path)
    summary = suitemod.run_all(entries, "core")
    assert len(summary.passed) == 1 and len(summary.failed) == 1
    assert summary.failed[0].name == "bad"
    text = suitemod.render_text(summary)
    assert "1 passed" in text and "1 regressions" in text and "Exit code: 1" in text
    md = suitemod.render_markdown(summary)
    assert "| `bad` |" in md and "FAIL" in md


def test_cli_run_suite_terminal_and_github(tmp_path):
    _bench(tmp_path, "good", ok=True)
    result = runner.invoke(app, ["run-suite", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "1 passed" in result.output
    _bench(tmp_path, "bad", ok=False)
    result = runner.invoke(app, ["run-suite", str(tmp_path), "--format", "github"])
    assert result.exit_code == 1, result.output
    assert "regressions" in result.output and "::error::" in result.output


def test_cli_run_suite_missing_target():
    result = runner.invoke(app, ["run-suite", "does-not-exist"])
    assert result.exit_code == 2


def test_repo_agentlab_example_resolves():
    root = Path(__file__).resolve().parent.parent.parent
    agentlab_dir = root / ".agentlab"
    assert (agentlab_dir / "config.yaml").exists()
    name, entries = suitemod.resolve_suite(agentlab_dir, root / "benchmarks")
    assert entries, "example suite must resolve at least one benchmark"
    summary = suitemod.run_all(entries, name)
    assert not summary.failed, "example suite must stay green"

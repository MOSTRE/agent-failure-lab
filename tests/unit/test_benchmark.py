"""Benchmark generation / loading / verification."""
import sys
from pathlib import Path

from agentlab.adapters.base import load_trajectory
from agentlab.benchmark import generator as gen
from agentlab.benchmark.models import Benchmark
from agentlab.benchmark.registry import discover, load_by_name
from agentlab.benchmark.runner import run_benchmark
from agentlab.benchmark.verifier import verify
from agentlab.diagnosis.analyzer import analyze

DEMO = Path(__file__).resolve().parent.parent.parent / "examples" / "sessions" / "demo.jsonl"
BENCHMARKS = Path(__file__).resolve().parent.parent.parent / "benchmarks"


def test_generate_creates_layout(tmp_path):
    traj = load_trajectory(DEMO)
    diag = analyze(traj)
    dest = gen.generate(traj, diag, source_path=DEMO, output_dir=tmp_path)
    for name in ("benchmark.yaml", "task.txt", "metadata.json", "base-commit.txt", "README.md"):
        assert (dest / name).exists(), name
    assert (dest / "verifier" / "run.sh").exists()
    assert (dest / "evidence" / "diagnosis.json").exists()
    loaded = Benchmark.load(dest)
    assert loaded.category == "hallucinated_api"
    assert "authentication timeout" in loaded.task


def test_all_fixture_benchmarks_load():
    found = discover(BENCHMARKS)
    assert len(found) == 20, f"expected 20 curated benchmarks, found {len(found)}"
    for name, path in found:
        b = Benchmark.load(path)
        assert b.task and b.category and b.verification.command, name


def test_verifier_pass_fail_unverified(tmp_path):
    ok = verify(f'"{sys.executable}" -c "import sys; sys.exit(0)"', cwd=tmp_path)
    assert ok.passed is True
    bad = verify(f'"{sys.executable}" -c "import sys; sys.exit(1)"', cwd=tmp_path)
    assert bad.passed is False
    assert bad.exit_code == 1
    none = verify("", cwd=tmp_path)
    assert none.passed is None


def test_runner_records_artifact(tmp_path):
    b, bdir = load_by_name(BENCHMARKS, "hallucinated-api/auth-timeout-001")
    result, artifact = run_benchmark(b, bdir, agent="test-agent")
    assert artifact.exists()
    assert result.benchmark == "auth-timeout-001"
    # Curated fixtures have no repo attached, so verification fails honestly.
    assert result.passed is False


def test_runner_passes_with_trivial_verification(tmp_path):
    bdir = tmp_path / "tiny"
    bdir.mkdir()
    (bdir / "benchmark.yaml").write_text(
        "version: 1\nname: tiny\ndescription: t\ntask: |\n  do it\ncategory: premature_completion\n"
        f"base_commit: unknown\nverification:\n  command: '\"{sys.executable}\" -c \"pass\"'\n  timeout_seconds: 30\n",
        encoding="utf-8",
    )
    b = Benchmark.load(bdir)
    result, _artifact = run_benchmark(b, bdir, agent="test-agent")
    assert result.passed is True

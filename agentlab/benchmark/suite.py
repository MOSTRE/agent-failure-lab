"""Benchmark suites: run a set of historical failures as regression tests.

A suite is either a directory of benchmarks, a suite YAML file listing
benchmark names, or an `.agentlab/` directory with a `config.yaml` that
points at suite files. Every run executes the benchmark's *verification
command* locally — it does not drive external agents, and the `--agent`
flag is only the label recorded with the result.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .models import Benchmark
from .registry import discover, load_by_name
from .runner import RunResult, run_benchmark


@dataclass
class SuiteOutcome:
    name: str
    category: str
    agent: str
    verdict: str  # PASS | FAIL | UNVERIFIED
    duration_ms: int
    detail: str = ""


@dataclass
class SuiteSummary:
    suite: str
    outcomes: list[SuiteOutcome] = field(default_factory=list)

    @property
    def passed(self) -> list[SuiteOutcome]:
        return [o for o in self.outcomes if o.verdict == "PASS"]

    @property
    def failed(self) -> list[SuiteOutcome]:
        return [o for o in self.outcomes if o.verdict == "FAIL"]

    @property
    def unverified(self) -> list[SuiteOutcome]:
        return [o for o in self.outcomes if o.verdict == "UNVERIFIED"]


def resolve_suite(target: Path, benchmarks_dir: Path) -> tuple[str, list[tuple[Benchmark, Path]]]:
    """Return (suite_name, [(benchmark, dir)]). Raises FileNotFoundError with guidance."""
    if not target.exists():
        raise FileNotFoundError(
            f"Suite '{target}' does not exist. Pass a benchmarks directory, "
            "a suite YAML file, or an .agentlab/ directory."
        )
    if target.is_file():
        return _from_suite_file(target, benchmarks_dir)
    config = target / "config.yaml"
    if config.exists():
        return _from_config(target, config)
    if (target / "benchmark.yaml").exists():
        return target.name, [(Benchmark.load(target), target)]
    found = discover(target)
    if not found:
        raise FileNotFoundError(
            f"No benchmarks found under {target}/. "
            "See .agentlab/ for an example suite layout."
        )
    entries = []
    for _name, path in found:
        entries.append((Benchmark.load(path), path))
    return target.name or "suite", entries


def _from_suite_file(path: Path, benchmarks_dir: Path) -> tuple[str, list[tuple[Benchmark, Path]]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    names = data.get("benchmarks", [])
    if not isinstance(names, list) or not names:
        raise ValueError(f"Suite file {path} needs a non-empty `benchmarks:` list.")
    entries = [_resolve_entry(str(n), benchmarks_dir, path.parent) for n in names]
    return str(data.get("name", path.stem)), entries


def _from_config(root: Path, config: Path) -> tuple[str, list[tuple[Benchmark, Path]]]:
    data = yaml.safe_load(config.read_text(encoding="utf-8")) or {}
    benchmarks_dir = Path(str(data.get("benchmarks_dir", "benchmarks")))
    if not benchmarks_dir.is_absolute():
        benchmarks_dir = root.parent / benchmarks_dir if (root.name == ".agentlab") else root / benchmarks_dir
    suites = data.get("suites", {})
    if not suites:
        # No named suites: treat benchmarks_dir as the suite.
        return _discover_all(root, benchmarks_dir)
    entries: list[tuple[Benchmark, Path]] = []
    names: list[str] = []
    for suite_name, suite_file in suites.items():
        suite_path = root / str(suite_file)
        _name, suite_entries = _from_suite_file(suite_path, benchmarks_dir)
        names.append(str(suite_name))
        entries.extend(suite_entries)
    return "+".join(names), entries


def _discover_all(root: Path, benchmarks_dir: Path) -> tuple[str, list[tuple[Benchmark, Path]]]:
    if not benchmarks_dir.exists():
        raise FileNotFoundError(
            f"benchmarks_dir {benchmarks_dir} does not exist (from {root / 'config.yaml'})."
        )
    found = discover(benchmarks_dir)
    return root.name, [(Benchmark.load(p), p) for _, p in found]


def _resolve_entry(entry: str, benchmarks_dir: Path, relative_to: Path) -> tuple[Benchmark, Path]:
    direct = Path(entry)
    if direct.is_dir() and (direct / "benchmark.yaml").exists():
        return Benchmark.load(direct), direct
    via_root = relative_to / entry
    if via_root.is_dir() and (via_root / "benchmark.yaml").exists():
        return Benchmark.load(via_root), via_root
    try:
        return load_by_name(benchmarks_dir, entry)
    except FileNotFoundError:
        pass
    raise FileNotFoundError(
        f"Suite entry '{entry}' matches no benchmark under {benchmarks_dir}/ "
        f"and is not a directory. Try `agentlab benchmark list --dir {benchmarks_dir}`."
    )


def run_all(
    entries: list[tuple[Benchmark, Path]],
    suite_name: str,
    agent: str = "manual",
) -> SuiteSummary:
    summary = SuiteSummary(suite=suite_name)
    for benchmark, bdir in entries:
        result, _artifact = run_benchmark(benchmark, bdir, agent=agent)
        summary.outcomes.append(_to_outcome(benchmark, result, agent))
    return summary


def _to_outcome(benchmark: Benchmark, result: RunResult, agent: str) -> SuiteOutcome:
    verdict = "PASS" if result.passed else "FAIL" if result.passed is False else "UNVERIFIED"
    detail = ""
    if verdict == "FAIL":
        detail = (result.output_tail or "").strip().splitlines()[-1][:160] if result.output_tail else ""
    return SuiteOutcome(
        name=benchmark.name, category=benchmark.category, agent=agent,
        verdict=verdict, duration_ms=result.duration_ms, detail=detail,
    )


def render_text(summary: SuiteSummary) -> str:
    """Plain ASCII summary — safe for CI logs on any platform."""
    lines = [
        "Agent Failure Lab",
        "",
        f"{len(summary.outcomes)} historical failures tested",
        "",
        f"[PASS] {len(summary.passed)} passed" if summary.passed else "[PASS] 0 passed",
        f"[FAIL] {len(summary.failed)} regressions" if summary.failed else "[FAIL] 0 regressions",
    ]
    if summary.unverified:
        lines.append(f"[----] {len(summary.unverified)} unverified (no verification command)")
    lines.append("")
    for o in summary.failed:
        lines.append(f"{o.name}")
        lines.append(f"{o.category.upper()}")
        if o.detail:
            lines.append(f"  {o.detail}")
        lines.append("")
    for o in summary.unverified:
        lines.append(f"{o.name} (UNVERIFIED)")
    lines.append(f"Exit code: {1 if summary.failed else 0}")
    return "\n".join(lines).rstrip() + "\n"


def render_markdown(summary: SuiteSummary) -> str:
    """Markdown table for step summaries and PR comments."""
    lines = [
        "## Agent Failure Lab",
        "",
        f"{len(summary.outcomes)} historical failures tested — "
        f"{len(summary.passed)} passed, {len(summary.failed)} regressions"
        + (f", {len(summary.unverified)} unverified" if summary.unverified else ""),
        "",
        "| Benchmark | Category | Verdict | Time |",
        "| --- | --- | --- | --- |",
    ]
    for o in summary.outcomes:
        mark = "PASS" if o.verdict == "PASS" else "FAIL" if o.verdict == "FAIL" else "UNVERIFIED"
        lines.append(f"| `{o.name}` | `{o.category}` | **{mark}** | {o.duration_ms}ms |")
    return "\n".join(lines) + "\n"


def write_github_annotations(summary: SuiteSummary) -> str:
    """Workflow commands: red annotations for regressions, groups for context."""
    lines = [f"::group::Agent Failure Lab — {summary.suite}"]
    for o in summary.outcomes:
        if o.verdict == "FAIL":
            msg = f"{o.name} regressed ({o.category})".replace("\n", " ")
            lines.append(f"::error::{msg}")
    lines.append("::endgroup::")
    return "\n".join(lines) + "\n"


def append_step_summary(markdown: str) -> Path | None:
    """Append to $GITHUB_STEP_SUMMARY when running inside Actions."""
    dest = os.environ.get("GITHUB_STEP_SUMMARY")
    if not dest:
        return None
    path = Path(dest)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(markdown + "\n")
    return path

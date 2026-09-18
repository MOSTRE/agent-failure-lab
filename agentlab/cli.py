"""Agent Failure Lab CLI: failure -> diagnosis -> benchmark -> regression test."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from contextlib import nullcontext
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from . import __version__
from .adapters.base import load_trajectory, supported_formats
from .benchmark import generator as gen
from .benchmark import registry
from .benchmark import runner as runmod
from .benchmark import suite as suitemod
from .benchmark.models import Benchmark
from .diagnosis.analyzer import analyze as analyze_trajectory
from .diagnosis.taxonomy import CATEGORIES, label
from .evaluation import comparison as cmp
from .evaluation import scoring
from .evaluation.metrics import trajectory_metrics
from .ingestion.reader import SessionReadError
from .ingestion.schema import Trajectory
from .redact import redact_file, scan_text
from .reports import html as html_report
from .reports import markdown as md_report
from .reports import share_card

app = typer.Typer(help="Every AI agent failure should become a test.", no_args_is_help=True)
benchmark_app = typer.Typer(help="Inspect local benchmarks.", no_args_is_help=True)
app.add_typer(benchmark_app, name="benchmark")
console = Console()
err_console = Console(stderr=True)

BENCHMARKS_DIR = Path("benchmarks")


def _load_session(path: Path) -> Trajectory:
    if not path.exists():
        err_console.print(f"Error: {path} does not exist.")
        raise typer.Exit(2)
    try:
        return load_trajectory(path)
    except SessionReadError as exc:
        err_console.print(f"Error: {exc}")
        raise typer.Exit(2)
    except Exception as exc:  # pragma: no cover - defensive
        err_console.print(f"Error: {path} is not a recognized session.\n\nSupported formats:\n" +
                          "\n".join(f"  {f}" for f in supported_formats()) +
                          f"\n\nTry:\n  agentlab inspect {path}\n\n({exc})")
        raise typer.Exit(2)


def _warn_secrets(traj: Trajectory) -> None:
    blob = (traj.task or "") + "\n" + "\n".join(e.text() for e in traj.events[:50])
    hits = scan_text(blob)
    if hits:
        err_console.print(
            f"[yellow]Warning: session may contain secrets ({', '.join(hits)}). "
            "Run `agentlab redact` before sharing reports.[/yellow]"
        )


def _autopsy_panel(traj: Trajectory, diag, session: str) -> Panel:
    verdict = "PASSED" if diag.success else "FAILED" if diag.success is False else "UNVERIFIED"
    m = trajectory_metrics(traj)
    tokens = f"{m['tokens']:,}" if m["tokens"] else "N/A"
    dur = _fmt_ms(m["duration_ms"]) if m["duration_ms"] else _session_duration(traj)
    lines = [
        f"[bold]Task:[/bold] {traj.task or '(no task recorded)'}",
        "",
        f"[bold]Result:[/bold] {verdict}",
        "",
        f"[bold]Critical step:[/bold] #{diag.critical_step}" if diag.critical_step else "[bold]Critical step:[/bold] n/a",
        "",
        f"[bold]Failure:[/bold] {diag.category.upper()} - {label(diag.category)}",
        "",
        (traj.task and diag.explanation) or diag.explanation,
        "",
        f"[dim]Downstream impact: {diag.downstream_impact} later actions   "
        f"Recovery opportunity: step {diag.recovery_opportunity or '-'}   "
        f"Files touched: {len(traj.files_touched)}   "
        f"Tool calls: {m['tool_calls']}   Tokens: {tokens}   Duration: {dur}[/dim]",
    ]
    return Panel("\n".join(lines), title="AGENT FAILURE AUTOPSY", border_style="red")


def _fmt_ms(ms: int | None) -> str:
    if not ms:
        return "N/A"
    s = ms // 1000
    if s < 60:
        return f"{s}s"
    return f"{s // 60}m {s % 60:02d}s"


def _session_duration(traj: Trajectory) -> str:
    durs = [e.duration_ms or 0 for e in traj.events if e.duration_ms]
    if durs:
        return _fmt_ms(sum(durs))
    return "N/A"


@app.command("analyze")
def analyze_cmd(
    session: Path = typer.Argument(..., help="Session file (.jsonl / .json)"),
    format: str = typer.Option("terminal", "--format", "-f", help="terminal | markdown | html | json"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Write report to file"),
    show_scores: bool = typer.Option(False, "--show-scores", help="Show all category scores"),
):
    """Analyze a failed agent session and print the autopsy."""
    _run_analysis(session, format, output, show_scores)


@app.command("diagnose")
def diagnose_cmd(
    session: Path = typer.Argument(..., help="Session file (.jsonl / .json)"),
    format: str = typer.Option("terminal", "--format", "-f", help="terminal | markdown | html | json"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Write report to file"),
    show_scores: bool = typer.Option(False, "--show-scores", help="Show all category scores"),
):
    """Diagnose a session (same engine as `analyze`)."""
    _run_analysis(session, format, output, show_scores)


def _run_analysis(session: Path, format: str, output: Optional[Path], show_scores: bool) -> None:
    traj = _load_session(session)
    _warn_secrets(traj)
    diag = analyze_trajectory(traj)
    fmt = format.lower()
    if fmt == "json":
        text = json.dumps(diag.to_dict(), indent=2)
        if output:
            output.write_text(text, encoding="utf-8")
        else:
            console.print(text)
    elif fmt == "markdown":
        text = md_report.render(traj, diag, session=str(session))
        if output:
            output.write_text(text, encoding="utf-8")
            console.print(f"Wrote Markdown report to {output}")
        else:
            console.print(text)
    elif fmt == "html":
        text = html_report.render(traj, diag, session=str(session))
        dest = output or Path("report.html")
        dest.write_text(text, encoding="utf-8")
        console.print(f"Wrote HTML report to {dest}")
    else:
        console.print(_autopsy_panel(traj, diag, str(session)))
        if show_scores:
            table = Table(title="Signals by category")
            table.add_column("Category")
            table.add_column("Score", justify="right")
            for cat, score in sorted(diag.scores.items(), key=lambda kv: -kv[1]):
                table.add_row(cat, f"{score:.2f}")
            console.print(table)
        if diag.evidence:
            console.print("\n[bold]Evidence:[/bold]")
            for e in diag.evidence[:6]:
                console.print(f"  - {e}")


@app.command("inspect")
def inspect_cmd(session: Path = typer.Argument(..., help="Session file to inspect")):
    """Show session structure without diagnosing (format, counts, files)."""
    traj = _load_session(session)
    table = Table(title=f"Session: {session}")
    table.add_column("Field")
    table.add_column("Value")
    m = trajectory_metrics(traj)
    table.add_row("Format", traj.source_format)
    table.add_row("Task", (traj.task or "(none)")[:80])
    table.add_row("Events", str(len(traj.events)))
    table.add_row("Tool calls", str(m["tool_calls"]))
    table.add_row("Test runs", str(m["test_runs"]))
    table.add_row("Files touched", ", ".join(traj.files_touched[:10]) or "(none)")
    kinds: dict[str, int] = {}
    for e in traj.events:
        kinds[e.kind] = kinds.get(e.kind, 0) + 1
    table.add_row("Kinds", ", ".join(f"{k}={v}" for k, v in sorted(kinds.items())))
    console.print(table)


@app.command("promote")
def promote_cmd(
    session: Path = typer.Argument(..., help="Session file to promote to a benchmark"),
    output: Path = typer.Option(BENCHMARKS_DIR, "--output", "-o", help="Benchmarks directory"),
    name: Optional[str] = typer.Option(None, "--name", help="Benchmark name (default: derived)"),
):
    """Turn a failed session into a reproducible benchmark."""
    traj = _load_session(session)
    diag = analyze_trajectory(traj)
    dest = gen.generate(traj, diag, source_path=session, output_dir=output, name=name)
    console.print(f"[green]Created benchmark:[/green] {dest}")
    console.print(f"  category: {diag.category}  critical step: {diag.critical_step or 'n/a'}")
    console.print(f"Next: agentlab run {dest}")


@benchmark_app.command("list")
def benchmark_list(benchmarks_dir: Path = typer.Option(BENCHMARKS_DIR, "--dir", help="Benchmarks root")):
    """List local benchmarks."""
    found = registry.discover(benchmarks_dir)
    if not found:
        console.print(f"No benchmarks found under {benchmarks_dir}/")
        raise typer.Exit(0)
    table = Table(title=f"Benchmarks ({len(found)})")
    table.add_column("Name")
    table.add_column("Category")
    table.add_column("Task")
    for name, path in found:
        try:
            b = Benchmark.load(path)
            table.add_row(name, b.category, (b.task or "")[:60])
        except Exception as exc:
            table.add_row(name, "ERROR", str(exc)[:60])
    console.print(table)


@benchmark_app.command("show")
def benchmark_show(
    name: str = typer.Argument(..., help="Benchmark name or path"),
    benchmarks_dir: Path = typer.Option(BENCHMARKS_DIR, "--dir", help="Benchmarks root"),
):
    """Show a benchmark spec."""
    target = Path(name)
    if target.is_dir() and (target / "benchmark.yaml").exists():
        b = Benchmark.load(target)
    else:
        b, target = registry.load_by_name(benchmarks_dir, name)
    console.print(f"[bold]{b.name}[/bold] - {b.description}")
    console.print(f"Category: {b.category}")
    console.print(f"Task: {b.task}")
    console.print(f"Verify: {b.verification.command} (timeout {b.verification.timeout_seconds}s)")
    console.print(f"Path: {target}")


@app.command("run")
def run_cmd(
    benchmark: str = typer.Argument(..., help="Benchmark name or path"),
    agent: str = typer.Option("manual", "--agent", "-a", help="Agent label for this run"),
    benchmarks_dir: Path = typer.Option(BENCHMARKS_DIR, "--dir", help="Benchmarks root"),
    keep_workdir: bool = typer.Option(False, "--keep-workdir", help="Keep isolated workspace for debugging"),
):
    """Run a benchmark's verification in an isolated workspace."""
    target = Path(benchmark)
    if target.is_dir():
        b = Benchmark.load(target)
        bdir = target
    else:
        b, bdir = registry.load_by_name(benchmarks_dir, benchmark)
    if not b.verification.command:
        console.print("[yellow]Benchmark has no verification command. Result will be UNVERIFIED.[/yellow]")
    with console.status("Running verification…"):
        result, artifact = runmod.run_benchmark(b, bdir, agent=agent, keep_workdir=keep_workdir)
    s = scoring.score_run(result)
    color = "green" if s["verdict"] == "PASS" else "red" if s["verdict"] == "FAIL" else "yellow"
    console.print(f"[{color}]{s['verdict']}[/{color}] {b.name} (agent={agent}) in {result.duration_ms}ms")
    if result.output_tail:
        console.print(Panel(result.output_tail[-2000:], title="verification output"))
    console.print(f"Artifacts: {artifact}")


@app.command("battle")
def battle_cmd(
    benchmark: str = typer.Argument(..., help="Benchmark name or path"),
    agents: str = typer.Option("manual", "--agents", help="Comma-separated agent labels"),
    benchmarks_dir: Path = typer.Option(BENCHMARKS_DIR, "--dir", help="Benchmarks root"),
):
    """Compare agents on one benchmark (verification-level, no invented metrics)."""
    target = Path(benchmark)
    if target.is_dir():
        b = Benchmark.load(target)
        bdir = target
    else:
        b, bdir = registry.load_by_name(benchmarks_dir, benchmark)
    labels = [a.strip() for a in agents.split(",") if a.strip()] or ["manual"]
    results = []
    for agent in labels:
        with console.status(f"Running {agent}…"):
            result, _artifact = runmod.run_benchmark(b, bdir, agent=agent)
        results.append(result)
    cmp_result = cmp.compare(results)
    table = Table(title=f"Battle: {b.name}")
    for col in ("agent", "verdict", "time_ms", "exit_code", "tool_calls", "tokens", "cost"):
        table.add_column(col)
    for row in cmp_result["rows"]:
        table.add_row(*(str(row[c]) for c in ("agent", "verdict", "time_ms", "exit_code", "tool_calls", "tokens", "cost")))
    console.print(table)
    if cmp_result["winners"]:
        console.print(f"[green]Winner(s): {', '.join(cmp_result['winners'])}[/green]")
    else:
        console.print("[yellow]No agent passed.[/yellow]")


@app.command("run-suite")
def run_suite_cmd(
    suite: Optional[Path] = typer.Argument(None, help="Suite file, .agentlab/ dir, or benchmarks dir (default: .agentlab or benchmarks)"),
    benchmarks_dir: Path = typer.Option(BENCHMARKS_DIR, "--dir", help="Benchmarks root for suite name lookups"),
    agent: str = typer.Option("manual", "--agent", "-a", help="Agent label recorded with each result"),
    format: str = typer.Option("terminal", "--format", "-f", help="terminal | github"),
    summary_out: Optional[Path] = typer.Option(None, "--summary-out", help="Write Markdown summary table to file (for PR comments)"),
):
    """Run a whole suite of historical failures. Exit 1 on any regression."""
    target = suite
    if target is None:
        target = Path(".agentlab") if Path(".agentlab").exists() else BENCHMARKS_DIR
    try:
        suite_name, entries = suitemod.resolve_suite(target, benchmarks_dir)
    except (FileNotFoundError, ValueError) as exc:
        err_console.print(f"Error: {exc}")
        raise typer.Exit(2)
    if format.lower() == "github":
        print(f"::group::Agent Failure Lab — running {len(entries)} benchmarks")
    with console.status(f"Running {len(entries)} benchmarks…") if format.lower() != "github" else nullcontext():
        summary = suitemod.run_all(entries, suite_name, agent=agent)
    text = suitemod.render_text(summary)
    if format.lower() == "github":
        print(f"::endgroup::")
        print(text)
        print(suitemod.write_github_annotations(summary))
        md = suitemod.render_markdown(summary)
        print(md)
        suitemod.append_step_summary(md)
        if summary_out:
            summary_out.write_text(md, encoding="utf-8")
    else:
        table = Table(title=f"Suite: {suite_name} ({len(summary.outcomes)} benchmarks)")
        table.add_column("Benchmark")
        table.add_column("Category")
        table.add_column("Verdict")
        table.add_column("Time", justify="right")
        for o in summary.outcomes:
            color = "green" if o.verdict == "PASS" else "red" if o.verdict == "FAIL" else "yellow"
            table.add_row(o.name, o.category, f"[{color}]{o.verdict}[/{color}]", f"{o.duration_ms}ms")
        console.print(table)
        console.print(f"[bold]{len(summary.passed)} passed, {len(summary.failed)} regressions"
                      + (f", {len(summary.unverified)} unverified" if summary.unverified else "") + "[/bold]")
        if summary_out:
            summary_out.write_text(suitemod.render_markdown(summary), encoding="utf-8")
            console.print(f"Wrote summary to {summary_out}")
    raise typer.Exit(1 if summary.failed else 0)


@app.command("report")
def report_cmd(
    target: Path = typer.Argument(..., help="Session file or run-result JSON"),
    format: str = typer.Option("terminal", "--format", "-f", help="terminal | markdown | html"),
    output: Optional[Path] = typer.Option(None, "--output", "-o"),
):
    """Render a report from a session (or pretty-print a run result)."""
    if target.suffix == ".json" and target.exists():
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict) and "benchmark" in data and "verdict" not in data and "agent" in data and "events" not in data:
            # Looks like a run result.
            verdict = "PASS" if data.get("passed") else "FAIL" if data.get("passed") is False else "UNVERIFIED"
            console.print(f"[bold]{data.get('benchmark')}[/bold] agent={data.get('agent')} verdict={verdict}")
            if data.get("output_tail"):
                console.print(Panel(str(data["output_tail"])[-2000:], title="verification output"))
            return
    traj = _load_session(target)
    diag = analyze_trajectory(traj)
    fmt = format.lower()
    if fmt == "markdown":
        text = md_report.render(traj, diag, session=str(target))
        if output:
            output.write_text(text, encoding="utf-8")
            console.print(f"Wrote {output}")
        else:
            console.print(text)
    elif fmt == "html":
        dest = output or Path("report.html")
        dest.write_text(html_report.render(traj, diag, session=str(target)), encoding="utf-8")
        console.print(f"Wrote HTML report to {dest}")
    else:
        console.print(_autopsy_panel(traj, diag, str(target)))


@app.command("export")
def export_cmd(
    target: Path = typer.Argument(..., help="Run-result JSON or session to export"),
    format: str = typer.Option("markdown", "--format", "-f", help="markdown | html | svg | json"),
    output: Optional[Path] = typer.Option(None, "--output", "-o"),
):
    """Export a run or diagnosis (including SVG share card)."""
    fmt = format.lower()
    if target.exists() and target.suffix == ".json":
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict) and "category" in data and fmt == "svg":
            from .diagnosis.analyzer import Diagnosis as D

            d = D.model_validate(data)
            svg = share_card.render_svg(d, agent=str(target.stem))
            dest = output or Path("share-card.svg")
            dest.write_text(svg, encoding="utf-8")
            console.print(f"Wrote {dest}")
            return
    traj = _load_session(target)
    diag = analyze_trajectory(traj)
    if fmt == "svg":
        m = trajectory_metrics(traj)
        stats = f"{m['tool_calls']} tool calls · {len(traj.files_touched)} files"
        dest = output or Path("share-card.svg")
        dest.write_text(share_card.render_svg(diag, agent=traj.source_format, stats=stats), encoding="utf-8")
        console.print(f"Wrote {dest}")
    elif fmt == "html":
        dest = output or Path("report.html")
        dest.write_text(html_report.render(traj, diag, session=str(target)), encoding="utf-8")
        console.print(f"Wrote {dest}")
    elif fmt == "json":
        dest = output or Path("diagnosis.json")
        dest.write_text(json.dumps(diag.to_dict(), indent=2), encoding="utf-8")
        console.print(f"Wrote {dest}")
    else:
        dest = output or Path("report.md")
        dest.write_text(md_report.render(traj, diag, session=str(target)), encoding="utf-8")
        console.print(f"Wrote {dest}")


@app.command("redact")
def redact_cmd(
    session: Path = typer.Argument(..., help="Session file to redact"),
    in_place: bool = typer.Option(False, "--in-place", help="Overwrite the original file"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output path"),
):
    """Redact likely secrets from a session file (conservative)."""
    dest, count = redact_file(session, in_place=in_place, output=output)
    console.print(f"Redacted {count} potential secret(s) -> {dest}")


@app.command("doctor")
def doctor_cmd():
    """Check local environment: Python, git, docker, agent CLIs, repo status."""
    console.print("[bold]Agent Failure Lab Doctor[/bold]\n")
    ok_all = True

    def row(name: str, ok: bool, detail: str = ""):
        mark = "[green]ok[/green]" if ok else "[red]--[/red]"
        console.print(f"{mark} {name}" + (f" - {detail}" if detail else ""))

    row("Python " + sys.version.split()[0], sys.version_info >= (3, 10))
    git = shutil.which("git")
    git_ver = ""
    if git:
        try:
            git_ver = subprocess.run(["git", "--version"], capture_output=True, text=True, timeout=10).stdout.strip()
        except Exception:
            git_ver = "git found"
    row("Git", bool(git), git_ver or "not found")
    try:
        r = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=10)
        row("Repository detected", r.returncode == 0, r.stdout.strip() if r.returncode == 0 else "not a git repo (ok)")
    except Exception:
        row("Repository detected", False, "git unavailable")
    docker = shutil.which("docker")
    row("Docker (optional)", bool(docker), "available" if docker else "not found - sandboxing will be skipped")
    for cli_name in ("claude", "codex", "opencode", "gemini"):
        found = shutil.which(cli_name)
        row(f"{cli_name.capitalize()} CLI", bool(found), "found" if found else "not found - battle labels still work")
    try:
        import typer as _t, pydantic as _p, yaml as _y, rich as _r  # noqa: F401

        row("Python dependencies", True, "typer, pydantic, yaml, rich")
    except ImportError as exc:
        row("Python dependencies", False, str(exc))
        ok_all = False
    console.print()
    if ok_all:
        console.print("Everything required for local analysis is available.")
    else:
        console.print("[yellow]Some optional pieces are missing - local analysis still works.[/yellow]")


@app.command("version")
def version_cmd():
    """Print the installed version."""
    console.print(f"agent-failure-lab {__version__}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()

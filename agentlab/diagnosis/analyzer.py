"""Deterministic diagnosis engine.

No LLM, no network, no chain-of-thought recovery. Every detector looks at
observable behavior only: tool calls, outputs, files, tests, timestamps.
Confidence scores are honest: strong evidence -> high confidence, single
heuristic -> low confidence.
"""
from __future__ import annotations

import difflib
import re
from typing import Any

from pydantic import BaseModel, Field

from ..ingestion.schema import Trajectory, TrajectoryEvent
from . import evidence as ev
from . import invariants as inv
from . import localizer
from .taxonomy import severity_for

_PATH_RE = re.compile(r"[\w\-./]+\.(?:py|ts|tsx|js|jsx|go|rs|java|rb|php|css|html|json|yaml|yml|toml|md)")
_SYMBOL_RE = re.compile(r"([A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)+)\s*\(")
_ATTR_ERR = re.compile(
    r"(AttributeError|TypeError|ReferenceError|NameError|has no attribute|is not a function|"
    r"undefined|no such (?:method|function|attribute)|ModuleNotFound|ImportError|"
    r"cannot find|not found)",
    re.I,
)
_SUCCESS_CLAIM = re.compile(r"\b(done|fixed|complete|completed|resolved|all .*pass|success|looks good|ready)\b", re.I)
_DEP_FILES = {"package.json", "package-lock.json", "requirements.txt", "pyproject.toml",
              "Cargo.toml", "Cargo.lock", "go.mod", "go.sum", "Gemfile", "pom.xml"}


class Diagnosis(BaseModel):
    category: str
    severity: str
    confidence: float = Field(ge=0.0, le=1.0)
    critical_step: int = 0
    evidence: list[str] = Field(default_factory=list)
    downstream_impact: int = 0
    recovery_opportunity: int | None = None
    explanation: str = ""
    scores: dict[str, float] = Field(default_factory=dict)
    success: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


def analyze(trajectory: Trajectory) -> Diagnosis:
    detectors = [
        ("destructive_change", _detect_destructive),
        ("hallucinated_api", _detect_hallucinated_api),
        ("infinite_repair_loop", _detect_repair_loop),
        ("ignored_test_failure", _detect_ignored_failure),
        ("premature_completion", _detect_premature),
        ("missing_test_execution", _detect_missing_tests),
        ("wrong_file", _detect_wrong_file),
        ("scope_creep", _detect_scope_creep),
        ("partial_success", _detect_partial),
        ("stale_context", _detect_stale),
        ("ignored_existing_code", _detect_ignored_code),
        ("requirement_misread", _detect_misread),
    ]
    results: dict[str, tuple[float, list[int], list[int], str]] = {}
    for name, fn in detectors:
        try:
            results[name] = fn(trajectory)
        except Exception:
            results[name] = (0.0, [], [], "")

    category = max(results, key=lambda k: results[k][0])
    confidence, hints, evidence_idx, explanation = results[category]
    # Nothing fired convincingly: report the best guess honestly.
    if confidence < 0.35:
        confidence = min(confidence, 0.4)

    known = set(trajectory.metadata.get("known_symbols", []) or [])
    critical, _scores, _reasons = localizer.score_events(trajectory, hints or evidence_idx, known or None)
    # If detectors gave no hint, keep critical only when the localizer is confident.
    if not hints and not evidence_idx and critical:
        pass

    downstream = localizer.downstream_impact(trajectory, critical)
    recovery = localizer.recovery_opportunity(trajectory, critical)
    evidence = ev.collect(trajectory, evidence_idx[:6])
    if critical and all(f"step {critical}" not in e for e in evidence):
        by_index = {e.index: e for e in trajectory.events}
        if critical in by_index:
            evidence = [ev.describe(by_index[critical])] + evidence

    verdict = _verdict(trajectory)
    return Diagnosis(
        category=category,
        severity=severity_for(category),
        confidence=round(float(confidence), 2),
        critical_step=critical,
        evidence=evidence,
        downstream_impact=downstream,
        recovery_opportunity=recovery,
        explanation=explanation or "Best-guess diagnosis from observable signals.",
        scores={k: round(v[0], 2) for k, v in results.items()},
        success=verdict,
    )


def _verdict(trajectory: Trajectory) -> bool | None:
    vp = inv.verification_passed(trajectory)
    if vp is True:
        # A passing suite with a later success claim is a pass; without any
        # failure signal we still call it a pass (verification is ground truth).
        return True
    if vp is False:
        return False
    if inv.destructive_events(trajectory):
        return False
    if inv.failing_tests(trajectory):
        return False
    # Error outputs with no recovery look like failures.
    for e in trajectory.events:
        if e.kind in ("error",) and e.output:
            return False
    return None


# ---- detectors: each returns (confidence, hint_indices, evidence_indices, explanation) ----

def _detect_hallucinated_api(t: Trajectory):
    known = set(t.metadata.get("known_symbols", []) or [])
    hints: list[int] = []
    evidence_idx: list[int] = []
    best_sym = ""
    for e in t.events:
        blob = str(e.input) + "\n" + (e.content or "")
        for sym in _SYMBOL_RE.findall(blob):
            suspect = False
            if known and sym not in known:
                # Is there a close valid symbol? That is the classic tell.
                close = difflib.get_close_matches(sym, list(known), n=1, cutoff=0.6)
                suspect = True
                if close:
                    best_sym = f"{sym} (did you mean {close[0]}?)"
                else:
                    best_sym = sym
            elif not known and _error_mentions(t, sym):
                suspect = True
                best_sym = sym
            if suspect:
                hints.append(e.index)
                evidence_idx.append(e.index)
                # Link the confirming error.
                err = _first_error_mentioning(t, sym, after=e.index)
                if err is not None and err not in evidence_idx:
                    evidence_idx.append(err)
                break
    if not hints:
        return 0.0, [], [], ""
    has_confirming_error = len(evidence_idx) > len(hints)
    if known:
        conf = 0.9 if has_confirming_error else 0.72
    else:
        conf = 0.66 if has_confirming_error else 0.45
    sym_txt = best_sym or "an unknown symbol"
    return conf, hints, sorted(evidence_idx), (
        f"Agent called {sym_txt} which has no matching symbol in the available context, "
        "and the subsequent tool output confirms the mismatch."
    )


def _error_mentions(t: Trajectory, sym: str) -> bool:
    base = sym.split(".")[-1].lower()
    for e in t.events:
        out = (e.output or "")
        if out and base in out.lower() and _ATTR_ERR.search(out):
            return True
    return False


def _first_error_mentioning(t: Trajectory, sym: str, after: int) -> int | None:
    base = sym.split(".")[-1].lower()
    for e in t.events:
        if e.index <= after:
            continue
        out = (e.output or "")
        if out and base in out.lower() and _ATTR_ERR.search(out):
            return e.index
    return None


def _task_paths(task: str) -> set[str]:
    return set(m.group(0) for m in _PATH_RE.finditer(task or ""))


def _detect_wrong_file(t: Trajectory):
    touched = t.files_touched
    if not touched:
        return 0.0, [], [], ""
    task_files = _task_paths(t.task)
    # Also consider files the agent actually read as in-scope context.
    read_files: set[str] = set()
    for e in t.events:
        read_files.update(e.files_read)
    scope = set(task_files) | read_files
    if not scope:
        # No stated scope: only fire when edits spray across many directories.
        dirs = {f.split("/")[0] for f in touched}
        if len(touched) >= 4 and len(dirs) >= 3:
            return 0.5, [e.index for e in t.events if e.files_changed][:2], \
                [e.index for e in t.events if e.files_changed][:3], \
                "Task names no files but the agent edited files across unrelated directories."
        return 0.0, [], [], ""
    overlap = [f for f in touched if f in scope or any(s in f or f in s for s in scope)]
    if overlap:
        return 0.0, [], [], ""
    idx = [e.index for e in t.events if e.files_changed]
    return 0.78, idx[:1], idx[:4], (
        f"Task scope mentions {sorted(task_files) or 'files the agent read'} but edits landed in "
        f"{touched}, with no overlap."
    )


def _detect_ignored_failure(t: Trajectory):
    failing = inv.failing_tests(t)
    if not failing:
        return 0.0, [], [], ""
    first = failing[0]
    failing_names = _failing_names(first)
    later = [e for e in t.events if e.index > first.index]
    if not later:
        return 0.3, [first.index], [first.index], "Test failed at the end of the session."
    # Did the agent revisit the failure (same test name, or any test re-run)?
    revisited = any(
        (e.kind == "test_run")
        and (not failing_names or any(n.lower() in str(e.input).lower() for n in failing_names))
        for e in later
    )
    unrelated_edits = [e for e in later if e.kind == "file_write" or e.files_changed]
    if revisited:
        return 0.25, [first.index], [first.index], "Test failed but the agent re-ran tests."
    if unrelated_edits:
        return 0.85, [first.index], [first.index] + [e.index for e in unrelated_edits[:3]], (
            "A test failed and the agent kept editing other code without addressing "
            "the failing assertion."
        )
    return 0.55, [first.index], [first.index], "Test failed and was never addressed."


def _failing_names(e: TrajectoryEvent) -> list[str]:
    blob = str(e.input) + " " + (e.output or "")
    names = re.findall(r"(test[\w_:.-]+|[\w_]+\.py::[\w_:.-]+)", blob)
    return list(dict.fromkeys(names))[:5]


def _detect_missing_tests(t: Trajectory):
    writes = [e for e in t.events if e.kind == "file_write" or e.files_changed]
    if not writes:
        return 0.0, [], [], ""
    if any(e.kind == "test_run" for e in t.events):
        return 0.1, [], [], ""
    if inv.success_claims(t):
        # Claimed success without tests belongs more to premature_completion;
        # keep this signal weaker so the claim detector owns it.
        return 0.65, [writes[0].index], [e.index for e in writes[:3]], (
            "Agent modified code and claimed success without running any tests."
        )
    return 0.6, [writes[0].index], [e.index for e in writes[:3]], (
        "Agent modified code but never ran tests or verification."
    )


def _detect_scope_creep(t: Trajectory):
    touched = t.files_touched
    if len(touched) < 4:
        return 0.0, [], [], ""
    dep_touched = [f for f in touched for d in _DEP_FILES if f.endswith(d)]
    loc_signals = 0
    for e in t.events:
        blob = str(e.input) + (e.output or "")
        m = re.search(r"(\d+)\s+insertions?", blob)
        if m and int(m.group(1)) > 200:
            loc_signals += 1
    task_len = len((t.task or "").split())
    # Short task + many files = classic creep. Long tasks legitimately touch more.
    threshold = 4 if task_len < 40 else 8
    if len(touched) >= threshold or (dep_touched and len(touched) >= 3):
        idx = [e.index for e in t.events if e.files_changed]
        extra = f", including dependency files {dep_touched}," if dep_touched else ""
        return 0.75, idx[:2], idx[:5], (
            f"Task is ~{task_len} words but the agent touched {len(touched)} files{extra} "
            "with no evidence the task required it."
        )
    return 0.3, [], [], ""


def _detect_misread(t: Trajectory):
    task = (t.task or "").lower()
    if not task:
        return 0.0, [], [], ""
    constraints = []
    for phrase in ("only", "do not", "don't", "never", "just", "without", "exclusively"):
        if phrase in task:
            constraints.append(phrase)
    task_files = _task_paths(t.task)
    read_files: set[str] = set()
    for e in t.events:
        read_files.update(e.files_read)
    writes = [e for e in t.events if e.files_changed]
    # Agent never even reads the file the task is about.
    if task_files and writes and not (set(t.files_touched) & task_files) and not (read_files & task_files):
        idx = [e.index for e in writes]
        return 0.62, idx[:1], idx[:3], (
            f"Task is about {sorted(task_files)} but the agent never read or edited them."
        )
    return 0.0, [], [], ""


def _detect_destructive(t: Trajectory):
    hits = inv.destructive_events(t)
    if not hits:
        return 0.0, [], [], ""
    return 0.92, [hits[0].index], [e.index for e in hits[:4]], (
        "Session contains a destructive operation (data deletion, forced overwrite, "
        "or dropped safety check)."
    )


def _detect_stale(t: Trajectory):
    # read ... git_operation ... write(same file) with a wide gap.
    reads: dict[str, int] = {}
    for e in t.events:
        for f in e.files_read:
            reads.setdefault(f, e.index)
    git_at = [e.index for e in t.events if e.kind == "git_operation" or _is_git_command(e)]
    hints, evidence_idx = [], []
    for e in t.events:
        for f in e.files_changed:
            if f in reads and e.index - reads[f] >= 3:
                if any(g for g in git_at if reads[f] < g < e.index):
                    hints.append(e.index)
                    evidence_idx += [reads[f], e.index]
    if hints:
        return 0.68, hints[:1], sorted(set(evidence_idx))[:4], (
            "Agent wrote a file it read much earlier, after intervening git operations — "
            "classic stale-context edit."
        )
    # Conflict-style errors also suggest staleness.
    for e in t.events:
        out = (e.output or "").lower()
        if "conflict" in out or "stale" in out or "already changed" in out:
            return 0.55, [e.index], [e.index], "Tool output reports a conflict/stale state."
    return 0.0, [], [], ""


def _is_git_command(e: TrajectoryEvent) -> bool:
    blob = str(e.input).lower()
    return "git " in blob or "git pull" in blob or "git fetch" in blob


def _detect_repair_loop(t: Trajectory):
    failing = [e for e in t.events if e.kind == "test_run" and e.test_passed is False]
    if len(failing) < 3:
        # Also catch edit -> same error 3x without formal test_run records.
        err_runs = [e for e in t.events if e.kind in ("tool_result", "error") and e.output and "fail" in e.output.lower()]
        if len(err_runs) < 3:
            return 0.0, [], [], ""
        sig = _sig(err_runs[0])
        same = [e for e in err_runs if _sig(e) == sig or not sig]
        if len(same) < 3:
            return 0.0, [], [], ""
        return 0.8, [same[0].index], [e.index for e in same[:5]], (
            "Agent repeats the same failing action 3+ times without changing approach."
        )
    # Group consecutive failures by signature; a group of 3+ is a loop.
    groups: list[list[TrajectoryEvent]] = [[failing[0]]]
    for f in failing[1:]:
        if _sig(f) == _sig(groups[-1][-1]):
            groups[-1].append(f)
        else:
            groups.append([f])
    biggest = max(groups, key=len)
    if len(biggest) >= 3:
        edits_between = [e.index for e in t.events
                         if biggest[0].index < e.index < biggest[-1].index and e.kind == "file_write"]
        return 0.88, [biggest[0].index], [e.index for e in biggest[:4]], (
            f"Same test fails {len(biggest)} times with edits in between and no progress."
        )
    if len(failing) >= 3:
        return 0.55, [failing[0].index], [e.index for e in failing[:4]], (
            "Tests fail repeatedly without convergence."
        )
    return 0.0, [], [], ""


def _sig(e: TrajectoryEvent) -> str:
    blob = str(e.input) + " " + (e.output or "")[:300]
    names = _failing_names(e)
    if names:
        return names[0].lower()
    # Fall back: first AssertionError / Error line.
    for line in (e.output or "").splitlines():
        if "error" in line.lower() or "assert" in line.lower():
            return line.strip().lower()[:120]
    return blob.lower()[:120]


def _detect_partial(t: Trajectory):
    runs = [e for e in t.events if e.kind == "test_run" and e.test_passed is not None]
    if runs and any(e.test_passed for e in runs) and any(not e.test_passed for e in runs):
        idx = [e.index for e in runs]
        return 0.7, idx[:1], idx[:5], "Some verification passes while other checks still fail."
    # Multi-part tasks ("fix A and B") where only one file area is touched.
    parts = re.split(r"\band\b|,|;|\+", t.task or "")
    parts = [p.strip() for p in parts if len(p.strip().split()) >= 3]
    if len(parts) >= 2 and t.files_touched:
        return 0.4, [], [], ""
    return 0.0, [], [], ""


def _detect_premature(t: Trajectory):
    claims = [e for e in t.events if e.content and _SUCCESS_CLAIM.search(e.content)]
    if not claims:
        return 0.0, [], [], ""
    vp = inv.verification_passed(t)
    if vp is False:
        idx = [e.index for e in inv.failing_tests(t)[:2]] + [claims[0].index]
        return 0.88, [claims[0].index], sorted(idx), (
            "Agent claims success while verification is failing."
        )
    if vp is None and not inv.has_verification(t):
        return 0.78, [claims[0].index], [claims[0].index], (
            "Agent claims success without running any verification."
        )
    return 0.15, [], [], ""


def _detect_ignored_code(t: Trajectory):
    # Output mentions an existing helper, then the agent writes a duplicate.
    hints: list[int] = []
    evidence_idx: list[int] = []
    for e in t.events:
        blob = ((e.output or "") + " " + (e.content or "")).lower()
        if any(p in blob for p in ("already exists", "already implemented", "existing function", "you can use", "reuse")):
            for later in t.events:
                if later.index > e.index and later.kind == "file_write":
                    hints.append(later.index)
                    evidence_idx += [e.index, later.index]
                    break
            break
    if hints:
        return 0.6, hints, sorted(set(evidence_idx)), (
            "Session output points at existing code, but the agent implements its own version."
        )
    return 0.0, [], [], ""

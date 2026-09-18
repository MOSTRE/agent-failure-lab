"""Failure taxonomy: the shared vocabulary for diagnoses.

Each category documents what it means, what signals the detectors look for,
and where false positives come from. The full prose lives in
docs/failure-taxonomy.md; this module is the machine-readable mirror.
"""
from __future__ import annotations


CATEGORIES: dict[str, dict[str, str]] = {
    "hallucinated_api": {
        "label": "Hallucinated API",
        "description": "Agent calls a function, method, or endpoint that does not exist in the repo.",
        "signals": "unknown symbol + nearby valid symbol + execution/test failure",
        "false_positives": "dynamically generated symbols, unvendored dependencies",
    },
    "wrong_file": {
        "label": "Wrong File",
        "description": "Agent edits files outside the scope implied by the task.",
        "signals": "task mentions file X, edits happen in unrelated file Y",
        "false_positives": "refactors that legitimately touch shared modules",
    },
    "ignored_existing_code": {
        "label": "Ignored Existing Code",
        "description": "Agent reimplements something the repo already provides.",
        "signals": "existing helper present + duplicate implementation added",
        "false_positives": "intentional replacement of a buggy helper",
    },
    "ignored_test_failure": {
        "label": "Ignored Test Failure",
        "description": "Tests fail and the agent moves on without addressing the failure.",
        "signals": "failing test_run followed by unrelated edits, failure never revisited",
        "false_positives": "flaky tests the agent correctly re-ran later",
    },
    "missing_test_execution": {
        "label": "Missing Test Execution",
        "description": "Agent changes code but never runs relevant tests or verification.",
        "signals": "file_write events with no subsequent test_run",
        "false_positives": "tasks that are docs-only or explicitly test-free",
    },
    "scope_creep": {
        "label": "Scope Creep",
        "description": "Agent changes far more than the task asked for.",
        "signals": "many files touched, dependency changes, unrelated modifications",
        "false_positives": "tasks that genuinely require cross-cutting changes",
    },
    "requirement_misread": {
        "label": "Requirement Misread",
        "description": "Agent builds the wrong behavior despite clear task wording.",
        "signals": "task keywords contradicted by implementation, premature narrowing",
        "false_positives": "ambiguous tasks where either reading is defensible",
    },
    "destructive_change": {
        "label": "Destructive Change",
        "description": "Agent deletes data, drops tables, force-pushes, or removes safety checks.",
        "signals": "rm -rf, DROP TABLE, --force, deleted guards",
        "false_positives": "explicitly requested destructive migrations",
    },
    "stale_context": {
        "label": "Stale Context",
        "description": "Agent acts on outdated file contents after the repo moved on.",
        "signals": "read long before write, intervening git_operation, conflicting edit",
        "false_positives": "idempotent re-application of the same edit",
    },
    "infinite_repair_loop": {
        "label": "Infinite Repair Loop",
        "description": "Agent repeats edit -> failing test cycles without progress.",
        "signals": "same test failing 3+ times with near-identical edits",
        "false_positives": "legitimate iterative debugging that converges",
    },
    "partial_success": {
        "label": "Partial Success",
        "description": "Agent fixes part of the task but leaves sub-requirements undone.",
        "signals": "some checks pass, others never addressed, work stops mid-task",
        "false_positives": "tasks the user explicitly descoped mid-session",
    },
    "premature_completion": {
        "label": "Premature Completion",
        "description": "Agent claims success without verification, or while tests fail.",
        "signals": "'done/fixed' message with missing or failing verification",
        "false_positives": "verification run outside the recorded session",
    },
}

SEVERITY = {
    "hallucinated_api": "high",
    "wrong_file": "medium",
    "ignored_existing_code": "medium",
    "ignored_test_failure": "high",
    "missing_test_execution": "medium",
    "scope_creep": "medium",
    "requirement_misread": "high",
    "destructive_change": "critical",
    "stale_context": "medium",
    "infinite_repair_loop": "high",
    "partial_success": "medium",
    "premature_completion": "high",
}


def label(category: str) -> str:
    return CATEGORIES.get(category, {}).get("label", category)


def severity_for(category: str) -> str:
    return SEVERITY.get(category, "medium")

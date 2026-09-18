# Failure taxonomy

Every diagnosis reports a `category`, `severity`, `confidence` (0–1),
`critical_step`, `evidence`, `downstream_impact`, and `recovery_opportunity`.
Confidence is honest: strong corroborating evidence scores high, a single
heuristic scores low. When nothing fires convincingly, the best guess is
returned with low confidence rather than false certainty.

## hallucinated_api (high)

Agent calls a function/method/endpoint that does not exist.

- Signals: unknown dotted symbol in agent input; `AttributeError` /
  "not a function" / "no such method" output mentioning it; a close valid
  symbol nearby (`invalidateUser` vs `deleteUser`).
- Example: `benchmarks/hallucinated-api/auth-timeout-001`.
- Limitations: without repo context (`known_symbols`) the detector relies
  on error text alone and confidence drops. Dynamically generated symbols
  can false-positive.

## wrong_file (medium)

Edits land outside the task's scope.

- Signals: task names file X (or the agent read X), edits happen in
  unrelated file Y with zero overlap.
- Limitations: legitimate cross-cutting refactors look identical; the
  detector cannot tell intent.

## ignored_existing_code (medium)

Agent reimplements something the repo already provides.

- Signals: output mentions an existing helper ("already exists", "you can
  use …") followed by a fresh implementation.
- Limitations: weakest detector — it needs the hint in tool output, and an
  intentional replacement of a buggy helper looks the same.

## ignored_test_failure (high)

A test fails and the agent moves on to unrelated code.

- Signals: failing `test_run`, later file edits, no re-run of the failing
  test.
- False positives: flaky tests the agent correctly judged irrelevant
  (mitigated: any re-run of the failing test clears the signal).

## missing_test_execution (medium)

Code changed, nothing ever verified it.

- Signals: `file_write` events with no subsequent `test_run`; stronger
  with a success claim.
- False positives: docs-only tasks. When a success claim exists, most of
  the weight goes to `premature_completion` instead.

## scope_creep (medium)

Far more changed than the task asked for.

- Signals: 4+ files touched for a short task, dependency files
  (`package.json`, `requirements.txt`, …) modified.
- Limitations: tasks that genuinely require cross-cutting changes will
  trip this; check the task length vs. files touched.

## requirement_misread (high)

Agent builds the wrong behavior.

- Signals: task names files the agent never reads or edits despite
  writing code elsewhere.
- Limitations: ambiguous tasks where either reading is defensible —
  confidence stays low by design.

## destructive_change (critical)

Data deletion, forced overwrites, dropped guards.

- Signals: `rm -rf`, `DROP TABLE`, `--force` push, `reset --hard`.
- False positives: explicitly requested destructive migrations. Always
  review before acting on this one.

## stale_context (medium)

Agent edits from outdated file contents.

- Signals: read … git operation … write to the same file with a wide gap,
  or conflict/stale tool output.
- Limitations: needs the git operation (or conflict text) in the session;
  otherwise it stays silent.

## infinite_repair_loop (high)

Edit → same failing test, 3+ times, no progress.

- Signals: grouped failing-test signatures with edits between them.
- False positives: iterative debugging that converges (group never
  reaches 3 identical failures, so it does not fire).

## partial_success (medium)

Part of the task fixed, rest abandoned.

- Signals: mixed test outcomes (some pass, some fail) with work stopped.
- Limitations: user-descoped tasks look the same; the detector reports
  the state, not the intent.

## premature_completion (high)

"Done" without proof.

- Signals: success-claim message while verification is failing — or with
  no verification at all.
- False positives: verification run outside the recorded session. If your
  harness verifies externally, ignore this category.

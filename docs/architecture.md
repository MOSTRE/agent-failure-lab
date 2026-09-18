# Architecture

```
Adapters
   |
   v
Normalized Trajectory
   |
   v
Diagnosis Engine --+--> Failure Model (category, critical step, evidence)
   |                |
   v                v
Benchmark Generator  Reports (terminal / markdown / HTML / SVG)
   |
   v
Runner --> Verifier --> Evaluation (metrics, scoring, battle comparison)
```

## Adapters (`agentlab/adapters/`)

Provider logs are messy and versioned. Each adapter does one job: detect a
file's shape and map it onto the generic JSONL contract. All mapping funnels
through `agentlab/ingestion/normalize.py`, so there is exactly one place
where a raw record becomes a `TrajectoryEvent`. Unknown fields survive in
`metadata` instead of being dropped.

## Normalized trajectory (`agentlab/ingestion/`)

The `Trajectory` is the only data structure the rest of the system sees:
a task string plus an ordered list of observable events (tool calls,
outputs, files, tests, git ops, errors, timestamps). The analyzer never
sees model chain-of-thought — only what the agent *did*.

## Diagnosis engine (`agentlab/diagnosis/`)

Deterministic detectors, one per failure category. Each returns a
confidence in [0, 1] plus the event indices behind it. `analyzer.py` picks
the winner; `localizer.py` then finds the earliest event that explains the
cascade, using explainable signals (first contradiction, first bad tool
result, unknown-symbol reference, edit-before-failure adjacency, downstream
weight). `enhance.py` is an optional hook for LLM-written explanations —
it can reword, never re-score.

## Benchmarks (`agentlab/benchmark/`)

`generator.py` snapshots a diagnosis into a `benchmark.yaml` directory
(task, category, verification command, evidence). `runner.py` copies the
benchmark into an isolated temp workspace, optionally checks out the base
commit, runs verification, and writes a run artifact. It never touches the
user's working tree.

## Evaluation (`agentlab/evaluation/`)

`metrics.py` counts what can be counted (tool calls, files, test outcomes).
`scoring.py` maps a run to PASS / FAIL / UNVERIFIED. `comparison.py`
renders battle tables. Token and cost columns are `N/A` unless the provider
actually reported them — the tool never invents numbers.

## Storage (`agentlab/storage/`)

A tiny SQLite database under `~/.agentlab/` keeps run and diagnosis
*metadata* (names, verdicts, timestamps). Session bodies are never stored
there.

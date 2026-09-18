# Agent Failure Lab

### Turn AI agent failures into regression tests.

AI agents fail.

Don't delete the session.

Analyze the failure.
Find the critical step.
Turn it into a benchmark.
Run it again.

```
Agent Session
     ↓
Diagnosis
     ↓
Critical Failure
     ↓
Benchmark
     ↓
Regression Test
```

## Why this exists

Coding agents fail in repeatable ways: invented APIs, edits to the wrong
file, ignored test failures, runaway scope, repair loops, premature "done".
Teams throw these sessions away. Agent Failure Lab keeps them — each one
becomes aita diagnosed case and then a runnable benchmark, so the same
failure can be tested against future agents and future versions of your
code.

## 30-second demo

```bash
git clone https://github.com/MOSTRE/agent-failure-lab
cd agent-failure-lab
pip install -e .
agentlab analyze examples/sessions/demo.jsonl
```

Real output:

```
┌─────────────────────────── AGENT FAILURE AUTOPSY ───────────────────────────┐
│ Task: Fix authentication timeout in api/users.ts                            │
│                                                                             │
│ Result: FAILED                                                              │
│                                                                             │
│ Critical step: #12                                                          │
│                                                                             │
│ Failure: HALLUCINATED_API - Hallucinated API                                │
│                                                                             │
│ Agent called redis.invalidateUser (did you mean redis.deleteUser?) which    │
│ has no matching symbol in the available context, and the subsequent tool    │
│ output confirms the mismatch.                                               │
│                                                                             │
│ Downstream impact: 9 later actions   Recovery opportunity: step 13   Files  │
│ touched: 2   Tool calls: 11   Tokens: N/A   Duration: N/A                   │
└─────────────────────────────────────────────────────────────────────────────┘

Evidence:
  - step 12 : {'path': 'lib/redis.ts', 'diff': 'call redis.invalidateUser(userId)'}
  - step 13 : AttributeError: 'Redis' object has no attribute 'invalidateUser'.
Did you mean: 'deleteUser'?
```

Then turn it into a benchmark and re-run it:

```bash
agentlab promote examples/sessions/demo.jsonl --output benchmarks/
agentlab benchmark list
agentlab run examples/custom-benchmark
agentlab run-suite .agentlab
```

```
1 passed, 0 regressions
```

## Installation

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate | macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
agentlab doctor
```

Requirements: Python 3.10+. Git, Docker, and agent CLIs are optional —
local analysis works without any of them.

## Quick start

```bash
agentlab analyze session.jsonl                          # terminal autopsy
agentlab analyze session.jsonl --format html -o out.html
agentlab inspect session.jsonl                          # structure, no diagnosis
agentlab diagnose session.jsonl --format json           # machine-readable
agentlab promote session.jsonl --output benchmarks/     # make it a benchmark
agentlab benchmark list
agentlab benchmark show hallucinated-api/auth-timeout-001
agentlab run <benchmark>                                # verify in isolation
agentlab battle <benchmark> --agents claude,codex       # compare labels
agentlab run-suite .agentlab                            # regression suite (exit 1 on FAIL)
agentlab redact session.jsonl -o session.redacted.jsonl # scrub secrets
```

Every command documents itself: `agentlab <command> --help`.

## How it works

Adapters normalize provider logs into one trajectory format (observable
behavior only — never model chain-of-thought). Deterministic detectors
score twelve failure categories with honest confidence, the localizer
finds the earliest event that explains the cascade, and the generator
snapshots the case into a `benchmark.yaml` directory with task, verifier,
and evidence. The runner executes verification in an isolated copy and
never touches your working tree. Details: `docs/architecture.md`.

## Failure taxonomy

`hallucinated_api`, `wrong_file`, `ignored_existing_code`,
`ignored_test_failure`, `missing_test_execution`, `scope_creep`,
`requirement_misread`, `destructive_change`, `stale_context`,
`infinite_repair_loop`, `partial_success`, `premature_completion`.

Each diagnosis carries severity, confidence, critical step, evidence,
downstream impact, and recovery opportunity. Signals, examples, and known
false positives: `docs/failure-taxonomy.md`.

## Benchmark format

```yaml
version: 1
name: hallucinated-api-001
task: |
  Fix the authentication timeout.
category: hallucinated_api
base_commit: abc123
verification:
  command: pytest tests/auth -q
  timeout_seconds: 120
```

20 curated benchmarks ship under `benchmarks/`. Full spec:
`docs/benchmark-format.md`. Copy `.agentlab/` into your own repo to gate
PRs on your suite.

## Supported session formats

Generic JSONL works out of the box and is the stable contract (one object
per line: `message`, `tool_call`, `tool_result`, `test_run`, …).
Claude, Codex, and OpenCode shapes are auto-detected; Gemini support is
partial because its public session format is still unstable — generic
JSONL is the fallback there. Capture and compatibility notes:
`docs/adapters.md`.

## GitHub Action

Run your suite on every pull request with the local action (no
marketplace needed — pin the tag):

```yaml
- uses: MOSTRE/agent-failure-lab/.github/actions/agentlab@v0.1.0
  with:
    suite: .agentlab
```

It installs the pinned checkout, runs `run-suite --format github`,
annotates regressions, appends a Markdown table to the job summary, and
can post it as a PR comment. Options and PR-comment setup:
`.github/actions/agentlab/README.md`.

## Privacy

Local by default. Nothing is uploaded, there is no telemetry, and the
SQLite store under `~/.agentlab/` keeps run metadata only — never session
bodies. Sessions can contain secrets, so scrub before sharing
(`agentlab redact …`). See `SECURITY.md`.

## Development

```bash
pip install -e ".[dev]"
pytest
```

## Contributing

Contributors welcome — especially new failure detectors, adapters, and
benchmarks. Conventions and PR checklist: `CONTRIBUTING.md`.

## Roadmap

- Flaky-test-aware detectors and multi-agent sessions
- Live agent execution sandbox (`run --execute` with Docker isolation)
- Web viewer for shared reports
- Community benchmark registry with deduplication

## License

MIT — see `LICENSE`.

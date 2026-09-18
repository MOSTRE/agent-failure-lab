# Agent Failure Lab action

Runs your `.agentlab` benchmark suite as regression tests. Fails the step
when any benchmark verification fails, annotates regressions with
`::error::`, appends a Markdown table to the job summary, and optionally
posts it as a PR comment.

## Use it in your repository

Copy `.agentlab/` from this repository, list your benchmarks in
`.agentlab/suites/core.yaml`, then add a workflow:

```yaml
name: Agent regression

on:
  pull_request:

permissions:
  contents: read
  pull-requests: write  # only needed for pr-comment: 'true'

jobs:
  agent-regression:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: MOSTRE/agent-failure-lab/.github/actions/agentlab@v0.1.0
        with:
          suite: .agentlab
```

With inputs:

```yaml
      - uses: MOSTRE/agent-failure-lab/.github/actions/agentlab@v0.1.0
        with:
          suite: .agentlab
          benchmarks-dir: benchmarks
          agent: manual
          pr-comment: 'true'
```

Notes:

- The action installs Agent Failure Lab from its own pinned checkout, so
  no marketplace publication is needed — pin `@v0.1.0` (or a commit SHA).
- Each benchmark runs its `verification.command` in an isolated copy.
  No external agents are executed; `agent` is just the recorded label.
- The step exits non-zero on any FAIL, so it gates the PR. Benchmarks
  without a verification command report UNVERIFIED and do not fail.
- The Markdown table lands in `$GITHUB_STEP_SUMMARY` automatically and in
  `agentlab-summary.md` for upload or `pr-comment`.

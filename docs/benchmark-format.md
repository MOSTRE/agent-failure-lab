# Benchmark format (v1)

A benchmark is a directory. The only required file is `benchmark.yaml`;
everything else is convention that `agentlab promote` creates for you.

```
benchmarks/auth-timeout-017/
├── benchmark.yaml    # stable machine-readable spec (required)
├── README.md         # human summary
├── metadata.json     # provenance: source session, diagnosis, timestamps
├── base-commit.txt   # git revision to reproduce from ("unknown" if none)
├── task.txt          # the task text given to the agent
├── expected/         # describe the expected end state
├── verifier/         # run.sh executes the verification command
└── evidence/         # diagnosis.json and anything backing the benchmark
```

## benchmark.yaml

```yaml
version: 1
name: hallucinated-api-001
description: Agent invents invalid Redis API
task: |
  Fix the authentication timeout in the API.
category: hallucinated_api
base_commit: abc123
verification:
  command: pytest tests/auth -q
  timeout_seconds: 120
  expected_exit_code: 0
metadata:
  difficulty: medium
  tags:
    - python
    - redis
    - authentication
```

Field notes:

- `category` is one of the taxonomy names in `docs/failure-taxonomy.md`.
- `base_commit: unknown` means "no recorded revision" — the runner then
  skips checkout instead of failing.
- An empty `verification.command` is allowed; runs are recorded as
  `UNVERIFIED` rather than erroring out.
- Keep `task` self-contained: an agent that never saw the original session
  must be able to attempt the benchmark from `task.txt` + the base commit.

## Size guidance

Do not vendor huge transcripts into every benchmark. Reference the source
session in `metadata.json` (`source_session`) and keep `evidence/` to the
diagnosis plus short excerpts. Benchmarks should stay small enough for a
contributor to read in a few minutes.

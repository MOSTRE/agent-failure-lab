# Contributing to Agent Failure Lab

Thanks for helping turn agent failures into tests. Small, focused pull
requests beat big ones.

## Local setup

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate | macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
agentlab doctor
pytest
```

## What to work on

- **New failure detector** — add a `_detect_*` function in
  `agentlab/diagnosis/analyzer.py`, wire it into `analyze()`, document it
  in `docs/failure-taxonomy.md` (including limitations and false
  positives), and add a fixture + parametrized case in
  `tests/unit/test_analyzer.py`.
- **New adapter** — follow `docs/adapters.md`: `detect` + `parse` via
  `ingestion/normalize.py`, register in `adapters/base.py`, add a fixture
  and tests. When the provider format is undocumented, map what you can
  and fall back to generic — never fabricate a format.
- **New benchmark** — copy `examples/custom-benchmark/`, keep it small,
  make sure `benchmark.yaml` validates (`agentlab benchmark show <dir>`),
  place it under `benchmarks/<category>/`.

## Coding style

- Simple functions over frameworks. No new abstraction layers without a
  real reason.
- Comments explain decisions, not syntax.
- Type hints where they clarify; minimal dependencies (every new one
  needs justification in the PR).
- Terminal output must stay ASCII-safe (Windows consoles) — emoji and
  wide glyphs belong in HTML/SVG reports only.

## Pull request expectations

- `pytest` passes; new behavior has tests, including at least one
  malformed-input case where relevant.
- Detectors report honest confidence — no fake certainty.
- No invented metrics, no telemetry, no network calls in the core path.
- Update the relevant `docs/` page and `CHANGELOG.md`.

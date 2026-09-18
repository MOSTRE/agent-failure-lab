# Changelog

## 0.1.1

- Fix the bundled GitHub Action's install path (it resolved one directory
  level short of the repository root, so the action step failed before
  running any benchmark)

## 0.1.0 — Initial public release

- Analyze agent trajectories (`analyze`, `diagnose`, `inspect`)
- Diagnose common failure modes across a 12-category taxonomy
- Localize likely critical failure steps with explainable scoring
- Promote failures into reproducible `benchmark.yaml` benchmarks
- Run benchmark verification in isolated workspaces (`run`, `battle`)
- Run whole suites as regression tests with CI-friendly output (`run-suite`)
- Local GitHub Action (`.github/actions/agentlab`) + `.agentlab/` suite example
- Generate Markdown, HTML, JSON, and SVG share-card reports
- Local secret redaction (`redact`) and environment diagnostics (`doctor`)
- Generic JSONL plus Claude, Codex, and OpenCode adapters (Gemini partial)
- 20 curated benchmarks; offline-first operation, no telemetry

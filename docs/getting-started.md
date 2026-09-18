# Getting started

Agent Failure Lab turns failed AI-agent sessions into reproducible benchmarks.
The whole workflow runs locally — no API keys, no uploads.

## Install

```bash
git clone https://github.com/your-org/agent-failure-lab
cd agent-failure-lab
python -m venv .venv
# Windows: .venv\Scripts\activate | macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
```

Check the setup:

```bash
agentlab doctor
```

## The 5-minute demo

A failed session is already checked in at `examples/sessions/demo.jsonl`.
In it, an agent tries to fix an auth timeout and invents
`redis.invalidateUser()` — a method that does not exist
(the repo only has `redis.deleteUser()`).

**1. Analyze it:**

```bash
agentlab analyze examples/sessions/demo.jsonl
```

You get the autopsy: failure category (`hallucinated_api`), the critical
step (#12), the confirming error (#13), downstream impact, and a recovery
point.

**2. Promote it to a benchmark:**

```bash
agentlab promote examples/sessions/demo.jsonl --output benchmarks/
agentlab benchmark list
```

**3. Inspect and run it:**

```bash
agentlab benchmark show hallucinated-api/auth-timeout-001
agentlab run examples/custom-benchmark
agentlab battle examples/custom-benchmark --agents claude,codex
```

**4. Render reports:**

```bash
agentlab analyze examples/sessions/demo.jsonl --format markdown --output report.md
agentlab analyze examples/sessions/demo.jsonl --format html --output report.html
agentlab export examples/sessions/demo.jsonl --format svg --output share-card.svg
```

Ready-made reports live in `examples/reports/`.

## Bring your own session

Export your agent session as generic JSONL (one object per line) and point
`agentlab` at it:

```json
{"type": "message", "role": "user", "content": "Fix the auth timeout"}
{"type": "tool_call", "tool": "read_file", "input": {"path": "src/auth.py"}}
{"type": "tool_result", "output": "..."}
{"type": "test_run", "input": {"command": "pytest -q"}, "output": "1 failed", "exit_code": 1}
```

The full contract is documented in `docs/benchmark-format.md`, and
provider-shaped logs (Claude, Codex, OpenCode, partial Gemini) are
auto-detected — see `docs/adapters.md`.

Before sharing anything, scrub secrets:

```bash
agentlab redact session.jsonl --output session.redacted.jsonl
```

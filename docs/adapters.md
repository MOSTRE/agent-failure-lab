# Adapters

All adapters normalize into the same `Trajectory`. Detection order is
claude → codex → opencode → generic; the first adapter whose `detect()`
matches wins, and anything unrecognized falls through to generic JSONL.

## generic-jsonl (stable contract)

One JSON object per line, or a whole-file JSON array / `{"events": [...]}`.
Record fields (all optional except the payload):

| Field | Meaning |
|---|---|
| `type` | `message`, `tool_call`, `tool_result`, `file_read`, `file_write`, `shell_command`, `test_run`, `git_operation`, `error`, `checkpoint` |
| `role` / `actor` | `user`, `assistant`, `agent`, `tool`, `system` |
| `tool` | tool name for `tool_call` |
| `input` | arguments object (`command`, `path`, `diff`, …) |
| `output` | tool/test output text |
| `content` | message text |
| `files_changed` / `files_read` | file lists (also inferred from `path`) |
| `exit_code`, `duration_ms`, `test_passed` | execution facts |
| `known_symbols`, `repo_files` | optional repo context (improves `hallucinated_api` detection) |

Aliases are accepted (`edit` → `file_write`, `bash` → `shell_command`,
`test` → `test_run`, …). Unknown fields are preserved in `metadata`.

Example session:

```json
{"type": "message", "role": "user", "content": "Fix the auth timeout"}
{"type": "tool_call", "tool": "read_file", "input": {"path": "src/auth.py"}}
{"type": "tool_result", "output": "def get_user(...): ..."}
{"type": "test_run", "input": {"command": "pytest -q"}, "output": "1 failed", "exit_code": 1}
```

Malformed lines do not kill the session: the reader reports
`Line 182 could not be parsed. The previous 181 events were recovered.`

## claude

Tolerant parser for Anthropic-style logs: `role`/`content` blocks with
`tool_use` / `tool_result` parts, `function_call` records, and plain
message lists. Anything it cannot map passes through to the generic
normalizer unchanged.

## codex

Handles Codex CLI shapes: `response_item` / `function_call` /
`function_call_output` records, `payload`-nested items, and
`instructions`-carried tasks. Test-runner commands in arguments are
promoted to `test_run` events.

## opencode

Maps OpenCode session parts (`text`, `tool`, `tool_result`, `error`,
`step_start`/`step_finish`) onto generic records.

## gemini (partial)

The public Gemini CLI session format is not stable enough to hard-code.
`agentlab/adapters/gemini.py` maps `functionCall` / `functionResponse`
parts and otherwise relies on the generic contract. If you export a Gemini
session as JSON/JSONL, it works; if Google stabilizes a format, a strict
parser belongs behind `GeminiAdapter.detect()`.

## Capturing sessions from real tools

No provider offers a stable "export session for Agent Failure Lab" button,
so capture is manual today. What works reliably:

- **Any tool:** write the generic JSONL yourself as the session unfolds
  (task message first, then tool calls, results, and test outcomes). The
  demo at `examples/sessions/demo.jsonl` shows the shape. This is the
  only path guaranteed to keep working across provider updates.
- **Claude Code:** transcripts live under `~/.claude/` as JSONL in current
  versions, but the schema is version-dependent — check with
  `agentlab inspect <file>` and fall back to generic JSONL if detection
  misses. Anything unmapped is preserved, never dropped.
- **Codex CLI:** session logs vary by release (`response_item` /
  `function_call` shapes). Same advice: inspect first, generic fallback
  second.
- **OpenCode:** session JSON with `parts` maps best; single-file exports
  parse directly.
- **Gemini:** export whatever JSON/JSONL the CLI gives you. Only
  `functionCall` / `functionResponse` parts are interpreted so far; the
  rest flows through the generic normalizer. Compatibility here is
  explicitly partial and may change with upstream releases.

Whichever path you take, run `agentlab redact` before the file leaves
your machine.

## Adding an adapter

1. Create `agentlab/adapters/<name>.py` with a class exposing
   `detect(path) -> bool` and `parse(path) -> Trajectory`.
2. Reuse `agentlab/ingestion/normalize.py` — do not build events by hand.
3. Register it in `agentlab/adapters/base.py` (`load_trajectory` order).
4. Add a fixture under `tests/fixtures/` and a test in
   `tests/unit/test_adapters.py`.
5. Document the shape (or its instability) here.

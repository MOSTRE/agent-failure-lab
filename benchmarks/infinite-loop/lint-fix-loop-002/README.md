# lint-fix-loop-002

Agent cycles the same two edits while the same lint error persists.

## Task

Make `ruff check` pass on src/worker.py.

## Verify

```bash
ruff check src/worker.py
```

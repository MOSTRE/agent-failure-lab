## What changed

## How to verify

- [ ] `pytest` passes
- [ ] `agentlab analyze examples/sessions/demo.jsonl` still diagnoses `hallucinated_api`
- [ ] Docs updated (`docs/`, `CHANGELOG.md` if user-facing)

## Checklist

- [ ] No secrets in sessions/fixtures (ran `agentlab redact` where relevant)
- [ ] No invented metrics; confidence scores honest
- [ ] Terminal output stays ASCII-safe

# api-redesign-003

Agent redesigns the middleware chain across 11 files.

## Task

Add a missing `Retry-After` header to the 429 response.

## Verify

```bash
pytest tests/test_rate_limit.py -q
```

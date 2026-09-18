# two-bugs-001

Agent fixes login, leaves logout broken, stops.

## Task

Fix both the login redirect and the logout 500 in src/auth.

## Verify

```bash
pytest tests/test_auth_flow.py -q
```

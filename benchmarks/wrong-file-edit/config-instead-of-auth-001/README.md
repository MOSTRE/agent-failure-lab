# config-instead-of-auth-001

Agent edits src/billing/invoice.ts instead of the login module.

## Task

Fix the login redirect in src/auth/login.ts so users land on /dashboard.

## Verify

```bash
pytest tests/test_login.py -q
```

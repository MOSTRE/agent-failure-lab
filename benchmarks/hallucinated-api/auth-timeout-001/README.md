# auth-timeout-001

Agent invents redis.invalidateUser(); the repo only provides redis.deleteUser().

## Task

Fix the authentication timeout in api/users.ts. Sessions expire but the lookup hangs for 60s.

## Verify

```bash
pytest tests/auth -q
```

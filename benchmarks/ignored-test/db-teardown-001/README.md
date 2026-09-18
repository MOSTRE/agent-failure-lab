# db-teardown-001

Agent sees teardown failure, then refactors unrelated checkout code without addressing it.

## Task

Fix flaky orders test by isolating DB state in tests/test_orders.py.

## Verify

```bash
pytest tests/test_orders.py -q
```

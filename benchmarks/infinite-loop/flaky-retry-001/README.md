# flaky-retry-001

Agent repeats edit -> same failing signature check 5 times.

## Task

Fix the payment webhook handler rejecting valid signatures.

## Verify

```bash
pytest tests/test_webhook.py -q
```

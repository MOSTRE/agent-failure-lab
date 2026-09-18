# pagination-filter-002

Agent fixes pagination; the filter still returns everything.

## Task

Fix pagination AND the status filter on /orders.

## Verify

```bash
pytest tests/test_orders_page.py -q
```

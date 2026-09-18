# pagination-cursor-002

Agent calls db.fetchPageAfter() which does not exist; the helper is db.fetchPage().

## Task

Fix cursor pagination in api/list.ts; the second page repeats the first page.

## Verify

```bash
pytest tests/test_pagination.py -q
```

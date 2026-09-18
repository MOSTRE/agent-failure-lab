# migration-instead-of-model-003

Agent edits an old alembic migration instead of the model.

## Task

Fix User.email validation in app/models/user.py.

## Verify

```bash
pytest tests/test_user_model.py -q
```

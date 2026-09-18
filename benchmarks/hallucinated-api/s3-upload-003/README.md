# s3-upload-003

Agent calls storage.putObjectAcl() with a wrong signature; correct call is storage.put_object().

## Task

Fix image uploads timing out against object storage.

## Verify

```bash
pytest tests/test_upload.py -q
```

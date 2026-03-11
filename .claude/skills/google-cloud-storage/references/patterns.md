# GCS Patterns Reference

## Contents
- Upload Patterns
- Download Patterns
- Signed URLs
- Configuration and Initialization
- Testing Without GCS

---

## Upload Patterns

### Standard Upload via StorageService

`upload_file(content, path, content_type)` is **synchronous**. Tries GCS; falls back to local on any exception. The stream position is reset before local fallback.

```python
from app.services.storage_service import storage_service

# DO — synchronous, no await
stored_path = storage_service.upload_file(
    content=csv_bytes,
    path="rrc-data/oil_proration.csv",
    content_type="text/csv"
)
```

```python
# DON'T — upload_file is NOT async
stored_path = await storage_service.upload_file(...)  # AttributeError: can't await
```

### Upload via Domain Helper (Preferred for User Files)

`UploadStorage.save_upload()` handles timestamp prefix and path construction. Use this for user-submitted files, not raw `upload_file()`.

```python
from app.services.storage_service import upload_storage
from fastapi import UploadFile

@router.post("/extract/upload")
async def upload_pdf(file: UploadFile, user_id: str):
    content = await file.read()  # FastAPI async — not storage

    # Synchronous storage call
    stored_path = upload_storage.save_upload(
        content=content,
        filename=file.filename,
        tool="extract",
        user_id=user_id
    )
    # → "uploads/extract/{user_id}/{timestamp}_{filename}"
    return {"file_path": stored_path}
```

### Upload from External Source (RRC Pattern)

Download from external API → store → cache in memory → sync to Firestore. See `rrc_data_service.py`.

```python
from app.services.storage_service import rrc_storage
import io, pandas as pd

# Store raw CSV bytes
rrc_storage.save_oil_data(csv_response.content)

# Load back for processing
oil_bytes = rrc_storage.get_oil_data()
if oil_bytes:
    df = pd.read_csv(io.BytesIO(oil_bytes))
```

### WARNING: Never Bypass StorageService

**The Problem:**

```python
# BAD — direct GCS access with no fallback
from google.cloud import storage as gcs
client = gcs.Client()
bucket = client.bucket("table-rock-tools-storage")
bucket.blob("uploads/doc.pdf").upload_from_string(pdf_bytes)
```

**Why This Breaks:**
1. Fails immediately in local dev (no credentials = exception)
2. Hardcodes bucket name — breaks if config changes
3. No fallback logging or error recovery
4. Bypasses `_init_client()` lazy initialization guard

**The Fix:** Always use `storage_service.upload_file()` or a domain helper.

---

## Download Patterns

### Download Returns None on Miss

`download_file()` returns `None` if the file doesn't exist in GCS or locally. It does NOT raise an exception.

```python
# DO — check for None
content = storage_service.download_file("rrc-data/oil_proration.csv")
if content is None:
    raise HTTPException(status_code=503, detail="RRC data not available")

df = pd.read_csv(io.BytesIO(content))
```

```python
# DON'T — don't assume download succeeds
df = pd.read_csv(io.BytesIO(storage_service.download_file("missing.csv")))
# TypeError: a bytes-like object is required, not 'NoneType'
```

### Check Existence Before Conditional Logic

```python
# Use file_exists() when you need conditional branching without consuming the file
if storage_service.file_exists("rrc-data/oil_proration.csv"):
    status = "available"
else:
    status = "missing — trigger download"
```

### GCS Download Falls Back to Local

If a file is in GCS but GCS fails, download checks local as fallback. This means a file saved locally during a GCS outage will still be found.

```python
# From storage_service.py:106
def download_file(self, path: str) -> bytes | None:
    if self.is_gcs_enabled:
        result = self._download_from_gcs(path)
        if result is not None:
            return result
        # GCS returned None — check local too
    return self._download_from_local(path)
```

---

## Signed URLs

`get_signed_url()` requires active GCS credentials. Returns `None` in local dev or when credentials are missing.

```python
# DO — always handle None
signed_url = storage_service.get_signed_url("exports/report.pdf", expiration_minutes=30)

if signed_url:
    return RedirectResponse(url=signed_url)
else:
    content = storage_service.download_file("exports/report.pdf")
    return Response(content=content, media_type="application/pdf")
```

```python
# DON'T — frontend gets {"download_url": null}, button silently breaks
return {"download_url": storage_service.get_signed_url(path)}
```

**Why this fails in production:** On Cloud Run, GCS credentials are available via Workload Identity — signed URLs work. But Cloud Run's service account needs the `roles/storage.objectViewer` role and the bucket must allow signed URL generation.

---

## Configuration and Initialization

### config.use_gcs ≠ GCS Available

```python
# From config.py
@property
def use_gcs(self) -> bool:
    return bool(self.gcs_bucket_name)
    # True when GCS_BUCKET_NAME is set — which is ALWAYS by default
```

`config.use_gcs` is `True` by default even without credentials. Actual availability requires:
1. `google-cloud-storage` package installed
2. Valid credentials (`GOOGLE_APPLICATION_CREDENTIALS` or ADC)
3. Network access to GCS
4. Bucket exists and service account has permissions

`_init_client()` catches all init failures and sets `_client = None`, enabling local fallback.

### Local Dev — No Setup Required

```bash
# Don't set GOOGLE_APPLICATION_CREDENTIALS
# StorageService auto-falls back to backend/data/
make dev
# uploads/ → backend/data/uploads/
# rrc-data/ → backend/data/rrc-data/
```

### GCS in Local Dev (Optional)

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/serviceaccount.json"
export GCS_BUCKET_NAME="table-rock-tools-storage"
export GCS_PROJECT_ID="tablerockenergy"
make dev
```

---

## Testing Without GCS

### Mock StorageService (Unit Tests)

```python
from unittest.mock import MagicMock, patch

def test_upload_handler():
    mock_storage = MagicMock()
    mock_storage.upload_file.return_value = "uploads/extract/test.pdf"

    with patch("app.api.extract.upload_storage", mock_storage):
        # Test handler logic without real storage
        ...
    mock_storage.upload_file.assert_called_once()
```

### Override data_dir (Integration Tests)

```python
import tempfile
from pathlib import Path
from app.services.storage_service import StorageService

def test_local_roundtrip():
    with tempfile.TemporaryDirectory() as tmpdir:
        svc = StorageService()
        svc._initialized = True  # Skip GCS init
        svc._client = None       # Force local mode

        # Override settings.data_dir indirectly via monkeypatch if needed
        content = b"test csv content"
        svc.upload_file(content, "test/data.csv", "text/csv")
        result = svc.download_file("test/data.csv")
        assert result == content
```

For async test patterns, see the **pytest** skill.

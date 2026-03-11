# GCS Types Reference

## Contents
- StorageService Methods
- Domain Helper Classes
- Config Properties
- Return Types Summary

---

## StorageService Methods

All methods are **synchronous**. The GCS Python client is synchronous; so is the local filesystem fallback. Import the module-level instance:

```python
from app.services.storage_service import storage_service
```

### upload_file

```python
def upload_file(
    self,
    content: bytes | BinaryIO,
    path: str,
    content_type: str = "application/octet-stream",
) -> str
```

- `content`: Raw bytes or a file-like object (must be seekable — seek is called if GCS fails and falls back to local)
- `path`: Full storage path, e.g., `"uploads/extract/doc.pdf"` or `"rrc-data/oil_proration.csv"`
- `content_type`: GCS metadata MIME type
- Returns: GCS URI (`"gs://bucket/path"`) on success; local path string on fallback

### download_file

```python
def download_file(self, path: str) -> bytes | None
```

Returns `None` if not found in GCS **or** locally. NEVER raises on a missing file.

```python
# DO — check for None
content = storage_service.download_file("rrc-data/oil_proration.csv")
if content is None:
    raise HTTPException(503, "RRC data unavailable")
```

### file_exists

```python
def file_exists(self, path: str) -> bool
```

Checks GCS first, then local. Never raises.

### get_file_info

```python
def get_file_info(self, path: str) -> dict | None
```

Returns `{"size": int, "modified": str (ISO 8601), "content_type": str}` or `None`.
When using local fallback, `content_type` is always `"application/octet-stream"`.

### delete_file

```python
def delete_file(self, path: str) -> bool
```

Idempotent — returns `True` even if the file was already absent.

### list_files

```python
def list_files(self, prefix: str) -> list[str]
```

Returns blob names (GCS) or relative paths from `settings.data_dir` (local). Returns `[]` on error.

### get_signed_url

```python
def get_signed_url(self, path: str, expiration_minutes: int = 60) -> str | None
```

Returns `None` when GCS is unavailable. GCS-only — there is no local equivalent.

### is_gcs_enabled (property)

```python
@property
def is_gcs_enabled(self) -> bool
```

Triggers lazy `_init_client()` on first call. Returns `True` only if GCS client actually initialized successfully.

---

## Domain Helper Classes

Thin wrappers over `StorageService` with pre-configured paths. All methods are synchronous.

### RRCDataStorage (`rrc_storage`)

```python
from app.services.storage_service import rrc_storage

rrc_storage.oil_path   # "rrc-data/oil_proration.csv"
rrc_storage.gas_path   # "rrc-data/gas_proration.csv"

rrc_storage.save_oil_data(content: bytes) -> str
rrc_storage.save_gas_data(content: bytes) -> str
rrc_storage.get_oil_data() -> bytes | None
rrc_storage.get_gas_data() -> bytes | None
rrc_storage.get_status() -> dict
```

`get_status()` shape:
```python
{
    "oil_available": bool,
    "gas_available": bool,
    "oil_size": int,           # 0 if not found
    "gas_size": int,
    "oil_modified": str | None,  # ISO datetime
    "gas_modified": str | None,
    "storage_type": "gcs" | "local"
}
```

### UploadStorage (`upload_storage`)

```python
from app.services.storage_service import upload_storage

upload_storage.save_upload(
    content: bytes | BinaryIO,
    filename: str,          # Original filename — spaces → underscores
    tool: str,              # "extract" | "title" | "proration" | "revenue"
    user_id: str | None,    # Optional
) -> str
# Path: "uploads/{tool}/{user_id}/{timestamp}_{filename}"
#    or "uploads/{tool}/{timestamp}_{filename}" (no user_id)
```

Content-type is inferred from extension: pdf, csv, xlsx, xls, png, jpg, jpeg.

### ProfileStorage (`profile_storage`)

```python
from app.services.storage_service import profile_storage

profile_storage.save_profile_image(content: bytes, user_id: str, filename: str) -> str
profile_storage.get_profile_image_url(user_id: str) -> str | None
# Returns "/api/admin/profile-image/{user_id}" (API proxy, NOT a GCS signed URL)

profile_storage.get_profile_image_path(user_id: str) -> Path | None
# Local path only — used to stream file from disk in the API proxy endpoint

profile_storage.delete_profile_image(user_id: str) -> bool
```

`get_profile_image_url()` always returns an API proxy URL to avoid signed URL generation overhead and Cloud Run IAM complexity.

---

## Config Properties

From `backend/app/core/config.py`:

```python
settings.gcs_bucket_name      # Optional[str], default "table-rock-tools-storage"
settings.gcs_project_id       # Optional[str], default "tablerockenergy"
settings.gcs_rrc_data_folder  # str, default "rrc-data"
settings.gcs_uploads_folder   # str, default "uploads"
settings.gcs_profiles_folder  # str, default "profiles"
settings.data_dir             # Path — local fallback root: backend/data/

settings.use_gcs  # @property: bool(gcs_bucket_name) — True by default!
```

### WARNING: use_gcs Is Not a Runtime Availability Check

```python
settings.use_gcs       # True (gcs_bucket_name is always set by default)
storage_service.is_gcs_enabled  # False in local dev without credentials
```

Never gate logic on `settings.use_gcs`. Check the actual return value instead:

```python
# DON'T
if settings.use_gcs:
    return storage_service.get_signed_url(path)  # Still may be None

# DO
url = storage_service.get_signed_url(path)
if url:
    return url
return f"/api/files/download?path={path}"
```

---

## Return Types Summary

| Method | Success Type | Missing / Failure |
|--------|-------------|-------------------|
| `upload_file()` | `str` path | Raises on unrecoverable error |
| `download_file()` | `bytes` | `None` |
| `file_exists()` | `True` | `False` |
| `get_file_info()` | `dict` | `None` |
| `delete_file()` | `True` | `False` on error |
| `list_files()` | `list[str]` | `[]` |
| `get_signed_url()` | `str` URL | `None` |
| `rrc_storage.get_oil_data()` | `bytes` | `None` |
| `rrc_storage.get_status()` | `dict` | Always returns dict |

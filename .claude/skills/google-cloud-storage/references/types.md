# GCS Types Reference

## Contents
- StorageService Methods
- Configuration Properties
- GCS Client Objects
- Return Types and Error Cases

---

## StorageService Methods

### upload_file

**Signature:**
```python
async def upload_file(
    self,
    file_content: bytes,
    filename: str,
    subfolder: str = ""
) -> str
```

**Parameters:**
- `file_content: bytes` - Raw file bytes (PDF, CSV, Excel, etc.)
- `filename: str` - Original filename (preserved for debugging)
- `subfolder: str` - Logical folder within bucket/data directory (e.g., `"uploads/extract"`)

**Returns:**
- `str` - Relative path to the stored file: `"{subfolder}/{filename}"`
- Example: `"uploads/extract/exhibit_a.pdf"`

**Behavior:**
1. Tries GCS upload if `config.use_gcs` and `self.bucket` is not None
2. Falls back to local filesystem (`backend/data/{subfolder}/{filename}`)
3. Creates parent directories as needed
4. Logs which backend was used (info level)

**Exceptions:**
- Generally doesn't raise exceptions (fallback handles GCS failures)
- May raise filesystem errors if local disk is full or permissions are wrong (rare)

---

### download_file

**Signature:**
```python
async def download_file(self, file_path: str) -> bytes
```

**Parameters:**
- `file_path: str` - Relative path from upload (e.g., `"rrc-data/oil_proration.csv"`)

**Returns:**
- `bytes` - Raw file content

**Behavior:**
1. Tries GCS download if `config.use_gcs` and `self.bucket` is not None
2. Falls back to local filesystem
3. Checks `blob.exists()` before downloading from GCS

**Exceptions:**
- `FileNotFoundError` - File not found in GCS or local storage
- **You must handle this exception**

**Example:**
```python
try:
    content = await storage.download_file("uploads/missing.pdf")
except FileNotFoundError:
    raise HTTPException(status_code=404, detail="File not found")
```

---

### file_exists

**Signature:**
```python
async def file_exists(self, file_path: str) -> bool
```

**Parameters:**
- `file_path: str` - Relative path to check

**Returns:**
- `bool` - `True` if file exists in GCS or local storage, `False` otherwise

**Behavior:**
1. Checks GCS first via `blob.exists()`
2. Falls back to local filesystem check
3. Never raises exceptions

**Use case:** Conditional logic, avoiding exceptions for control flow

```python
if await storage.file_exists("rrc-data/oil_proration.csv"):
    # File exists, safe to download
    content = await storage.download_file("rrc-data/oil_proration.csv")
else:
    # File missing, trigger download
    await trigger_rrc_sync()
```

---

### get_signed_url

**Signature:**
```python
def get_signed_url(
    self,
    file_path: str,
    expiration_minutes: int = 60
) -> str | None
```

**Parameters:**
- `file_path: str` - Relative path to file
- `expiration_minutes: int` - How long the URL remains valid (default: 60)

**Returns:**
- `str` - HTTPS signed URL with expiration token
- `None` - GCS is unavailable or file doesn't exist

**Behavior:**
1. **Only works with GCS** (no local filesystem equivalent)
2. Returns `None` if `self.bucket` is `None` or blob doesn't exist
3. Generates a time-limited URL that bypasses authentication

**Critical: Always handle None case**

```python
# DO
signed_url = storage.get_signed_url("exports/report.pdf", expiration_minutes=30)

if signed_url:
    return {"download_url": signed_url}
else:
    # Provide local fallback API route
    return {"download_url": f"/api/files/download?path=exports/report.pdf"}
```

```python
# DON'T
signed_url = storage.get_signed_url("exports/report.pdf")
return {"download_url": signed_url}  # BAD - May be None
```

**Why this matters:**
In local dev (no GCS credentials), `get_signed_url()` **always returns None**. The frontend will receive `{"download_url": null}` and download buttons will silently fail.

---

## Configuration Properties

### Settings (Pydantic BaseSettings)

From `backend/app/core/config.py`:

```python
class Settings(BaseSettings):
    # GCS bucket configuration
    gcs_bucket_name: str = "table-rock-tools-storage"
    gcs_project_id: str = "tablerockenergy"
    
    @property
    def use_gcs(self) -> bool:
        """Returns True if GCS bucket name is configured.
        
        WARNING: This does NOT guarantee GCS is actually available at runtime.
        GCS availability depends on valid credentials, network, and permissions.
        """
        return bool(self.gcs_bucket_name)
    
    class Config:
        env_file = ".env"
        case_sensitive = False
```

**Key Properties:**

| Property | Type | Default | Purpose |
|----------|------|---------|---------|
| `gcs_bucket_name` | `str` | `"table-rock-tools-storage"` | Target GCS bucket |
| `gcs_project_id` | `str` | `"tablerockenergy"` | GCP project ID |
| `use_gcs` | `bool` (property) | `True` (when bucket name set) | Signals intent to use GCS |

**WARNING: use_gcs is NOT an availability flag**

```python
# DON'T - This is a common mistake
if config.use_gcs:
    # BAD - Assumes GCS is available, but it may not be
    url = storage.get_signed_url(path)
    return url  # May be None!
```

**The Fix:**
```python
# DO - Check actual return values, not config flags
url = storage.get_signed_url(path)

if url is not None:
    # GCS is actually available
    return url
else:
    # GCS unavailable, use local fallback
    return f"/api/files/{path}"
```

---

## GCS Client Objects

### google.cloud.storage.Client

**From:** `google-cloud-storage` Python package

**Initialization:**
```python
from google.cloud import storage as gcs

# Automatically uses GOOGLE_APPLICATION_CREDENTIALS env var
client = gcs.Client(project="tablerockenergy")
```

**Project setup:**
- Production (Cloud Run): Credentials via Workload Identity (automatic)
- Local dev: Set `GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json`

---

### google.cloud.storage.Bucket

**Access:**
```python
bucket = client.bucket("table-rock-tools-storage")

# Check bucket exists
if bucket.exists():
    print("Bucket is accessible")
```

**Common operations:**
```python
# List blobs (files) in bucket
blobs = list(bucket.list_blobs(prefix="uploads/"))

# Get single blob reference
blob = bucket.blob("uploads/file.pdf")
```

---

### google.cloud.storage.Blob

**Upload:**
```python
blob = bucket.blob("uploads/document.pdf")

# From bytes
blob.upload_from_string(pdf_bytes)

# From file-like object
with open("local.pdf", "rb") as f:
    blob.upload_from_file(f)
```

**Download:**
```python
blob = bucket.blob("uploads/document.pdf")

# To bytes
content = blob.download_as_bytes()

# To file
blob.download_to_filename("/tmp/downloaded.pdf")
```

**Existence check:**
```python
blob = bucket.blob("uploads/document.pdf")

if blob.exists():
    content = blob.download_as_bytes()
else:
    raise FileNotFoundError("Blob not found")
```

**Signed URL generation:**
```python
from datetime import timedelta

blob = bucket.blob("uploads/document.pdf")

# Generate URL valid for 1 hour
url = blob.generate_signed_url(
    version="v4",
    expiration=timedelta(minutes=60),
    method="GET"
)
# Returns: "https://storage.googleapis.com/bucket/uploads/document.pdf?X-Goog-Algorithm=..."
```

---

## Return Types and Error Cases

### Upload Return Values

```python
file_path = await storage.upload_file(
    file_content=b"content",
    filename="test.pdf",
    subfolder="uploads"
)
# Type: str
# Value: "uploads/test.pdf"
```

**Guarantee:** Always returns a string path, never `None`, never raises exceptions (under normal circumstances).

---

### Download Return Values and Errors

```python
# Success case
content = await storage.download_file("uploads/test.pdf")
# Type: bytes
# Value: b"%PDF-1.4\n..."

# Error case
try:
    content = await storage.download_file("missing.pdf")
except FileNotFoundError as e:
    # File not in GCS or local storage
    logger.error(f"File not found: {e}")
    raise HTTPException(status_code=404, detail="File not found")
```

**Exceptions you must handle:**
- `FileNotFoundError` - File doesn't exist in either backend

---

### Signed URL Return Values

```python
# Success case (GCS available)
url = storage.get_signed_url("uploads/test.pdf", expiration_minutes=30)
# Type: str
# Value: "https://storage.googleapis.com/table-rock-tools-storage/uploads/test.pdf?X-Goog-Signature=..."

# Failure case (GCS unavailable or blob doesn't exist)
url = storage.get_signed_url("uploads/test.pdf")
# Type: None
# Value: None
```

**Type annotation:** `str | None` (union type, requires Python 3.10+)

**Critical pattern:**
```python
signed_url = storage.get_signed_url(path)

if signed_url is not None:
    # Use GCS signed URL
    return RedirectResponse(url=signed_url)
else:
    # Fallback to local file serving
    content = await storage.download_file(path)
    return Response(content=content, media_type="application/pdf")
```

---

### File Existence Return Values

```python
exists = await storage.file_exists("uploads/test.pdf")
# Type: bool
# Value: True or False

# Never raises exceptions
```

**Use cases:**
1. **Conditional downloads** - Avoid `FileNotFoundError` exceptions
2. **Scheduled task validation** - Check if RRC data download succeeded
3. **Cache invalidation** - Check if file needs re-upload

```python
# Pattern: Check before download
if await storage.file_exists("rrc-data/oil_proration.csv"):
    content = await storage.download_file("rrc-data/oil_proration.csv")
else:
    logger.warning("RRC data missing, triggering download")
    await sync_rrc_data()
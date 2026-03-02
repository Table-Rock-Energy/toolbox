# GCS Patterns Reference

## Contents
- Upload Patterns
- Download Patterns
- Error Handling and Fallback
- Configuration and Initialization
- Testing Without GCS

---

## Upload Patterns

### Standard File Upload

Use `upload_file()` for all file uploads. It handles GCS → local fallback transparently.

```python
from app.services.storage_service import StorageService

storage = StorageService()

# DO - Let the service handle fallback
file_path = await storage.upload_file(
    file_content=pdf_bytes,
    filename="document.pdf",
    subfolder="uploads/extract"
)
# Returns: "uploads/extract/document.pdf" (works with or without GCS)
```

```python
# DON'T - Never bypass StorageService to write directly to GCS
from google.cloud import storage as gcs

# BAD - No fallback, breaks in local dev
client = gcs.Client()
bucket = client.bucket("table-rock-tools-storage")
blob = bucket.blob("uploads/document.pdf")
blob.upload_from_string(pdf_bytes)
```

**Why DON'T breaks:**
1. No fallback when GCS is unavailable (local dev fails)
2. Bypasses logging and error tracking
3. Hardcoded bucket name violates config abstraction
4. No path normalization or validation

### Upload from UploadFile (FastAPI)

```python
from fastapi import UploadFile

@router.post("/extract/upload")
async def upload_pdf(file: UploadFile):
    # Read entire file into memory (acceptable for <50MB files)
    content = await file.read()
    
    # DO - Use original filename, let service handle uniqueness if needed
    stored_path = await storage.upload_file(
        file_content=content,
        filename=file.filename,  # Preserves original name
        subfolder="extract/uploads"
    )
    
    return {"file_path": stored_path}
```

```python
# DON'T - Don't generate unique filenames unless required
import uuid

# BAD - Loses original filename, makes debugging harder
unique_name = f"{uuid.uuid4()}.pdf"
stored_path = await storage.upload_file(
    file_content=content,
    filename=unique_name,  # User loses context
    subfolder="extract/uploads"
)
```

**Why DON'T breaks:**
Preserving the original filename makes debugging and support easier. The current implementation doesn't handle filename collisions (overwrites), but this is acceptable for our use case where:
- Files are user-scoped (different users can upload same filename)
- Firestore tracks metadata with job IDs
- Collision is rare in practice

If you need uniqueness in the future, add a timestamp prefix: `f"{int(time.time())}_{file.filename}"`.

### Upload from External API

**Pattern:** Download from external source (RRC website) → upload to storage

```python
# From backend/app/services/proration/rrc_data_service.py:127
async def sync_rrc_data(well_type: str):
    # Step 1: Download from external source
    csv_content = download_rrc_csv_from_website(well_type)
    
    # Step 2: Upload to storage (GCS or local)
    file_path = await storage.upload_file(
        file_content=csv_content.encode('utf-8'),
        filename=f"{well_type.lower()}_proration.csv",
        subfolder="rrc-data"
    )
    
    # Step 3: Parse and cache in memory
    df = pd.read_csv(io.StringIO(csv_content))
    cache[well_type] = df
    
    # Step 4: Sync to Firestore for persistence
    await sync_to_firestore(df, well_type)
```

**Key insight:** Storage is the first persistence layer (durable backup), then in-memory cache for performance, then Firestore for querying.

---

## Download Patterns

### Download Existing File

Use `download_file()` to retrieve files. It checks GCS first, then local filesystem.

```python
# DO - Let service check both locations
try:
    file_content = await storage.download_file("rrc-data/oil_proration.csv")
    df = pd.read_csv(io.BytesIO(file_content))
except FileNotFoundError:
    logger.error("RRC data not found in GCS or local storage")
    raise HTTPException(status_code=404, detail="RRC data not available")
```

```python
# DON'T - Never assume file exists without checking
# BAD - Will raise FileNotFoundError in local dev
file_content = await storage.download_file("missing.csv")  # Crash
df = pd.read_csv(io.BytesIO(file_content))
```

**Why DON'T breaks:**
`download_file()` raises `FileNotFoundError` if the file doesn't exist in either GCS or local storage. Always wrap in try/except.

### Check File Existence Before Download

```python
# DO - Check first for conditional logic
if await storage.file_exists("rrc-data/oil_proration.csv"):
    file_content = await storage.download_file("rrc-data/oil_proration.csv")
    # Process file
else:
    logger.warning("Oil proration data not found, triggering download")
    await trigger_rrc_download()
```

**When to use:** Conditional logic, avoiding exceptions for control flow, or checking if scheduled tasks ran successfully.

### Signed URL for Direct Download

```python
# DO - Always handle None case
signed_url = storage.get_signed_url("exports/report.pdf", expiration_minutes=30)

if signed_url:
    # GCS is available, use signed URL
    return {"download_url": signed_url}
else:
    # GCS unavailable, serve from local filesystem via API
    local_url = f"/api/files/download?path=exports/report.pdf"
    return {"download_url": local_url}
```

```python
# DON'T - Never assume signed URL is not None
# BAD - Frontend gets None URL, download button breaks
signed_url = storage.get_signed_url("exports/report.pdf")
return {"download_url": signed_url}  # May be None!
```

**Why DON'T breaks:**
`get_signed_url()` returns `None` when GCS is unavailable. The frontend will receive `{"download_url": null}` and the download button will fail silently.

**Fix pattern:** Always check for `None` and provide a local API endpoint as fallback.

---

## Error Handling and Fallback

### Upload Fallback Logic

The `upload_file()` method automatically falls back to local storage on GCS failure.

```python
# From backend/app/services/storage_service.py:60
async def upload_file(self, file_content: bytes, filename: str, subfolder: str = "") -> str:
    try:
        # Try GCS first if configured
        if self.config.use_gcs and self.bucket:
            blob = self.bucket.blob(full_path)
            blob.upload_from_string(file_content)
            logger.info(f"Uploaded to GCS: {full_path}")
            return full_path
    except Exception as e:
        logger.warning(f"GCS upload failed: {e}, falling back to local storage")
    
    # Fallback: local filesystem
    local_path = self.data_dir / full_path
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_bytes(file_content)
    logger.info(f"Uploaded to local storage: {full_path}")
    return full_path
```

**Key insights:**
1. **Silent fallback** - Callers don't need to know which backend was used
2. **Same return value** - Path is identical regardless of backend
3. **Logging differentiates** - Check logs to see which backend was used

### Download Fallback Logic

```python
# From backend/app/services/storage_service.py:90
async def download_file(self, file_path: str) -> bytes:
    # Try GCS first
    if self.config.use_gcs and self.bucket:
        try:
            blob = self.bucket.blob(file_path)
            if blob.exists():
                return blob.download_as_bytes()
        except Exception as e:
            logger.warning(f"GCS download failed: {e}, trying local storage")
    
    # Fallback: local filesystem
    local_path = self.data_dir / file_path
    if not local_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    return local_path.read_bytes()
```

**Key insight:** GCS errors are logged as warnings, not errors. This is intentional—local dev without GCS is a valid use case.

### WARNING: Don't Rely on config.use_gcs Alone

```python
# DON'T - Config flag doesn't guarantee GCS availability
if config.use_gcs:
    # BAD - GCS client may still be None at runtime
    signed_url = storage.get_signed_url(path)
    return signed_url  # May be None even when config.use_gcs == True
```

**The Problem:**
`config.use_gcs` returns `True` when `GCS_BUCKET_NAME` is set (which is always by default: `"table-rock-tools-storage"`). But GCS availability depends on:
1. `GOOGLE_APPLICATION_CREDENTIALS` environment variable
2. Valid service account key
3. Network connectivity
4. Bucket permissions

**The Fix:**
```python
# DO - Always check the return value, not the config
signed_url = storage.get_signed_url(path)

if signed_url is not None:
    # GCS is actually available
    return {"url": signed_url}
else:
    # GCS unavailable, use local fallback
    return {"url": f"/api/files/{path}"}
```

---

## Configuration and Initialization

### Environment Variables

From `backend/app/core/config.py`:

```python
class Settings(BaseSettings):
    # GCS Configuration
    gcs_bucket_name: str = "table-rock-tools-storage"  # Default always set
    gcs_project_id: str = "tablerockenergy"
    
    @property
    def use_gcs(self) -> bool:
        """Returns True if GCS bucket name is configured (not a guarantee of availability)."""
        return bool(self.gcs_bucket_name)
```

**Production (Cloud Run):**
- `GOOGLE_APPLICATION_CREDENTIALS` automatically available via Workload Identity
- No manual service account key needed

**Local Development:**
```bash
# Option 1: Use GCS with service account key
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/key.json"
export GCS_BUCKET_NAME="table-rock-tools-storage"
export GCS_PROJECT_ID="tablerockenergy"

# Option 2: Local-only mode (no GCS)
# Just don't set GOOGLE_APPLICATION_CREDENTIALS
# Storage will automatically fall back to backend/data/
```

### StorageService Initialization

```python
# From backend/app/services/storage_service.py:20
class StorageService:
    def __init__(self):
        self.config = get_settings()
        self.data_dir = Path(__file__).parent.parent / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize GCS client (may be None)
        self.client = None
        self.bucket = None
        
        if self.config.use_gcs:
            try:
                from google.cloud import storage as gcs
                self.client = gcs.Client(project=self.config.gcs_project_id)
                self.bucket = self.client.bucket(self.config.gcs_bucket_name)
            except Exception as e:
                logger.warning(f"GCS initialization failed: {e}, using local storage only")
```

**Key insights:**
1. **Lazy GCS import** - Only imports `google.cloud.storage` if `use_gcs` is `True`
2. **Graceful failure** - GCS init errors are warnings, not exceptions
3. **Local directory always created** - `backend/data/` is always available as fallback

---

## Testing Without GCS

### Local Development Setup

```bash
# No GCS environment variables needed
cd toolbox
make install
make dev
```

All file operations will automatically use `backend/data/`:
- Uploads → `backend/data/uploads/`
- RRC data → `backend/data/rrc-data/`
- Exports → `backend/data/exports/`

### Simulating GCS in Tests

```python
# Option 1: Mock the StorageService
from unittest.mock import MagicMock, AsyncMock

async def test_upload_flow():
    storage = MagicMock()
    storage.upload_file = AsyncMock(return_value="uploads/test.pdf")
    
    result = await upload_handler(file_content, storage)
    assert result["file_path"] == "uploads/test.pdf"
```

```python
# Option 2: Use local storage with temp directory
import tempfile
from pathlib import Path

def test_local_storage():
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = StorageService()
        storage.data_dir = Path(tmpdir)  # Override data directory
        
        file_path = await storage.upload_file(
            file_content=b"test content",
            filename="test.txt",
            subfolder="uploads"
        )
        
        assert (Path(tmpdir) / file_path).exists()
```

For testing patterns, see the **pytest** skill.
# GCS Modules Reference

## Contents
- StorageService Architecture
- Global Instances
- Integration with FastAPI Routes
- RRC Data Pipeline
- Local Directory Structure

---

## StorageService Architecture

**Path:** `backend/app/services/storage_service.py`

### Lazy Initialization

GCS client is initialized on first use via `_init_client()`, guarded by `_initialized` flag. This means GCS init failures are silent at startup — the service just operates in local-only mode.

```python
class StorageService:
    def __init__(self):
        self._client: Optional[storage.Client] = None
        self._bucket: Optional[storage.Bucket] = None
        self._initialized = False

    def _init_client(self) -> bool:
        if self._initialized:
            return self._client is not None
        self._initialized = True

        if not GCS_AVAILABLE:  # package not installed
            return False
        if not settings.use_gcs:  # no bucket name configured
            return False

        try:
            self._client = storage.Client(project=settings.gcs_project_id)
            self._bucket = self._client.bucket(settings.gcs_bucket_name)
            # Creates bucket if it doesn't exist
            if not self._bucket.exists():
                self._bucket = self._client.create_bucket(...)
            return True
        except Exception as e:
            logger.error(f"Failed to initialize GCS: {e}")
            self._client = None
            self._bucket = None
            return False
```

**Key design points:**
1. `_initialized` flag prevents repeated init attempts on every operation
2. `GCS_AVAILABLE` module-level flag handles missing `google-cloud-storage` package
3. Bucket creation on first init (sets up GCS automatically for new environments)
4. All exceptions caught and converted to local-fallback mode

---

## Global Instances

Prefer using these module-level singletons over creating new `StorageService()` instances. They're initialized once at import time.

```python
from app.services.storage_service import (
    storage_service,    # Base StorageService
    rrc_storage,        # RRCDataStorage — wraps rrc-data/ paths
    upload_storage,     # UploadStorage — handles user file uploads
    profile_storage,    # ProfileStorage — profile image management
)
```

Each domain helper wraps `storage_service` with pre-configured paths:

```python
# Bottom of storage_service.py
storage_service = StorageService()
rrc_storage = RRCDataStorage(storage_service)
upload_storage = UploadStorage(storage_service)
profile_storage = ProfileStorage(storage_service)
```

---

## Integration with FastAPI Routes

### User File Upload Pattern

```python
# backend/app/api/extract.py
from fastapi import UploadFile
from app.services.storage_service import upload_storage

@router.post("/upload")
async def upload_pdf(file: UploadFile, user_email: str):
    content = await file.read()  # FastAPI async — not storage

    # Synchronous — returns path regardless of GCS availability
    stored_path = upload_storage.save_upload(
        content=content,
        filename=file.filename,
        tool="extract",
        user_id=user_email
    )

    # Process file...
    text = extract_text(content)
    return {"file_path": stored_path, "parties": parse_parties(text)}
```

### Export Download with Signed URL Fallback

```python
# Pattern used in proration and revenue export endpoints
from fastapi.responses import RedirectResponse, Response
from app.services.storage_service import storage_service

@router.get("/export/download")
async def download_export(path: str):
    signed_url = storage_service.get_signed_url(path, expiration_minutes=15)

    if signed_url:
        # Redirect client to GCS directly (preferred — offloads bandwidth)
        return RedirectResponse(url=signed_url)

    # Fallback: stream through FastAPI
    content = storage_service.download_file(path)
    if content is None:
        raise HTTPException(404, "Export file not found")

    from pathlib import Path
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={Path(path).name}"}
    )
```

---

## RRC Data Pipeline

Storage is the first persistence layer in the RRC pipeline: raw CSV → GCS/local → pandas cache → Firestore.

### Download → Store → Cache (from `rrc_data_service.py`)

```python
from app.services.storage_service import rrc_storage
import io, pandas as pd

def sync_rrc_data_oil(csv_bytes: bytes):
    # 1. Store raw CSV (GCS or local fallback)
    rrc_storage.save_oil_data(csv_bytes)

    # 2. Cache in memory for fast lookups
    df = pd.read_csv(io.BytesIO(csv_bytes))
    _oil_cache = df

    # 3. Sync to Firestore (background thread, sync client)
    # See rrc_background.py for background thread pattern
```

### Load on Startup

```python
def load_rrc_cache():
    """Load RRC data from storage into memory on startup."""
    oil_bytes = rrc_storage.get_oil_data()
    gas_bytes = rrc_storage.get_gas_data()

    if oil_bytes:
        _cache["oil"] = pd.read_csv(io.BytesIO(oil_bytes))
        logger.info(f"Loaded {len(_cache['oil'])} oil records")
    else:
        logger.warning("No oil RRC data found — trigger download via /rrc/download")
```

### Status Check

```python
from app.services.storage_service import rrc_storage

@router.get("/rrc/status")
async def get_rrc_status():
    return rrc_storage.get_status()
    # {"oil_available": True, "storage_type": "gcs", "oil_modified": "2024-01-15T..."}
```

For scheduling patterns, see the **apscheduler** skill. For pandas patterns, see the **pandas** skill.

---

## Local Directory Structure

Local filesystem mirrors GCS bucket layout exactly. The path passed to `upload_file(path=...)` is used unchanged in both backends.

```
backend/data/               # settings.data_dir
├── uploads/                # settings.gcs_uploads_folder
│   ├── extract/            # OCC Exhibit A PDFs
│   ├── title/              # Title opinion Excel/CSV
│   ├── proration/          # Mineral holder CSVs
│   └── revenue/            # Revenue statement PDFs
├── rrc-data/               # settings.gcs_rrc_data_folder
│   ├── oil_proration.csv
│   └── gas_proration.csv
└── profiles/               # settings.gcs_profiles_folder
    └── {user_id}/avatar.jpg
```

Subdirectories are created automatically on first upload (`mkdir(parents=True, exist_ok=True)`).

### What's in .gitignore

RRC CSVs and the `rrc-data/` directory are gitignored (see recent commit `fcf4266`):

```
# .gitignore
backend/data/rrc-data/
```

User uploads and generated exports should also be gitignored. The `allowed_users.json` auth file is **not** ignored — it's committed to the repo.

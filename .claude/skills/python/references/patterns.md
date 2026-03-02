# Python Patterns Reference

## Contents
- Service Module Pattern
- Async/Await Best Practices
- Error Handling & Logging
- Configuration Management
- Import Strategies
- Storage Fallback Pattern

---

## Service Module Pattern

All services follow `{domain}_service.py` naming with lazy initialization for expensive clients.

### DO: Lazy Firebase/GCS Initialization

```python
# backend/app/services/firestore_service.py
from __future__ import annotations
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from google.cloud.firestore import Client

logger = logging.getLogger(__name__)
_firestore_client: Client | None = None

def _get_firestore() -> Client:
    """Lazy init to avoid crashes when credentials missing."""
    global _firestore_client
    if _firestore_client is None:
        from google.cloud import firestore
        _firestore_client = firestore.Client()
    return _firestore_client

async def save_job(job_id: str, data: dict) -> None:
    db = _get_firestore()  # Only initializes on first call
    db.collection("jobs").document(job_id).set(data)
```

**Why:** Firebase/GCS clients crash on import if credentials are missing. Lazy init allows local dev without GCP setup.

### DON'T: Initialize Clients at Module Level

```python
# BAD - Crashes immediately if GOOGLE_APPLICATION_CREDENTIALS not set
from google.cloud import firestore

firestore_client = firestore.Client()  # FAILS at import time

async def save_job(job_id: str, data: dict) -> None:
    firestore_client.collection("jobs").document(job_id).set(data)
```

**Why This Breaks:** Module-level initialization runs on import, before you can catch errors. Lazy init defers until first use.

---

## Async/Await Best Practices

### DO: Async All the Way Down

```python
# backend/app/api/proration.py
from fastapi import APIRouter, UploadFile
from app.services.proration.csv_processor import process_csv

router = APIRouter()

@router.post("/upload")
async def upload_csv(file: UploadFile):
    content = await file.read()  # Async read
    result = await process_csv(content)  # Async processing
    return result
```

**Why:** FastAPI runs async handlers in the event loop. Blocking calls (sync I/O) stall the entire server.

### DON'T: Blocking I/O in Async Context

```python
# BAD - Blocks event loop, kills throughput
@router.post("/upload")
async def upload_csv(file: UploadFile):
    content = file.read()  # SYNC READ - blocks all requests
    with open("data/temp.csv", "w") as f:  # SYNC WRITE
        f.write(content.decode())
    return {"status": "done"}
```

**Why This Breaks:** Synchronous I/O blocks the event loop. A 2-second file write freezes all other requests for 2 seconds.

**The Fix:** Use `await file.read()` and `aiofiles` for async file I/O, or run sync code in `asyncio.to_thread()`.

---

## Error Handling & Logging

### DO: HTTPException with Context

```python
# backend/app/api/extract.py
from fastapi import HTTPException
import logging

logger = logging.getLogger(__name__)

@router.post("/upload")
async def extract_pdf(file: UploadFile):
    try:
        if not file.filename.endswith(".pdf"):
            raise HTTPException(status_code=400, detail="PDF files only")
        
        content = await file.read()
        result = await parse_pdf(content)
        return result
    
    except ValueError as e:
        logger.error(f"Parsing failed for {file.filename}: {e}")
        raise HTTPException(status_code=422, detail=f"Invalid PDF: {e}")
    
    except Exception as e:
        logger.exception(f"Unexpected error processing {file.filename}")
        raise HTTPException(status_code=500, detail="Processing failed")
```

**Why:** HTTPException maps to proper HTTP status codes. `logger.exception()` includes stack traces for debugging.

### WARNING: Bare Except Clauses

**The Problem:**

```python
# BAD - Catches KeyboardInterrupt, SystemExit, EVERYTHING
try:
    result = await parse_pdf(content)
except:  # DANGEROUS
    return {"error": "unknown"}
```

**Why This Breaks:**
1. Catches `KeyboardInterrupt` (Ctrl+C) - can't stop the server
2. Catches `SystemExit` - breaks pytest, docker stop
3. Hides bugs - you never see the real error

**The Fix:**

```python
# GOOD - Catch specific exceptions
try:
    result = await parse_pdf(content)
except (ValueError, PDFSyntaxError) as e:
    logger.error(f"PDF parsing failed: {e}")
    raise HTTPException(status_code=422, detail=str(e))
except Exception as e:
    logger.exception("Unexpected PDF error")
    raise HTTPException(status_code=500, detail="Processing failed")
```

---

## Configuration Management

### DO: Pydantic Settings with @property

```python
# backend/app/core/config.py
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    gcs_bucket_name: str = "table-rock-tools-storage"
    gcs_project_id: str = "tablerockenergy"
    firestore_enabled: bool = True
    database_enabled: bool = False
    
    @property
    def use_gcs(self) -> bool:
        """GCS enabled if bucket name is set."""
        return bool(self.gcs_bucket_name)
    
    class Config:
        env_file = ".env"
        case_sensitive = False

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
```

**Why:** `@property` allows computed config values. `@lru_cache` prevents re-reading env vars on every access.

### DON'T: Direct os.getenv() Everywhere

```python
# BAD - No validation, scattered config, type unsafe
import os

def upload_file(path: str):
    bucket_name = os.getenv("GCS_BUCKET_NAME")  # Might be None
    project_id = os.getenv("GCS_PROJECT_ID", "default")  # String default
    if bucket_name:  # Runtime check instead of type safety
        # Upload to GCS
```

**Why This Breaks:** No central config, no validation, no type safety. Pydantic Settings validates on startup.

---

## Import Strategies

### DO: TYPE_CHECKING for Type Hints

```python
# backend/app/services/storage_service.py
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from google.cloud.storage import Bucket
    from google.cloud.firestore import Client

def upload_to_bucket(bucket: Bucket, path: str) -> None:
    """Type hints work, but imports only run during type checking."""
    bucket.blob(path).upload_from_filename(path)
```

**Why:** `TYPE_CHECKING` is `False` at runtime, so imports don't execute. Avoids circular dependencies and import-time crashes.

### DON'T: Top-Level Imports for Lazy-Loaded Clients

```python
# BAD - Imports run immediately, crash if credentials missing
from google.cloud import firestore
from google.cloud.storage import Client as StorageClient

# These crash at import time if GOOGLE_APPLICATION_CREDENTIALS not set
db = firestore.Client()
storage_client = StorageClient()
```

**Why This Breaks:** Imports execute on `import` statement, before you can handle errors. Use lazy initialization instead.

---

## Storage Fallback Pattern

### DO: GCS with Local Filesystem Fallback

```python
# backend/app/services/storage_service.py
from pathlib import Path
from app.core.config import settings

async def download_file(file_path: str) -> bytes:
    """Try GCS first, fallback to local."""
    if settings.use_gcs:
        try:
            bucket = _get_gcs_bucket()
            blob = bucket.blob(file_path)
            return blob.download_as_bytes()
        except Exception as e:
            logger.warning(f"GCS download failed, trying local: {e}")
    
    # Local fallback
    local_path = Path(f"data/{file_path}")
    if not local_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    return local_path.read_bytes()
```

**Why:** Allows local dev without GCP credentials. Production uses GCS, local dev uses `data/` directory.

### WARNING: Returning None for Missing Files

**The Problem:**

```python
# BAD - Caller has to handle None, easy to forget
def get_signed_url(file_path: str) -> str | None:
    if not settings.use_gcs:
        return None  # Caller must check for None
    return bucket.blob(file_path).generate_signed_url(...)
```

**Why This Breaks:** Every caller must remember to check for `None`. Easy to miss, causes `NoneType` errors.

**The Fix:**

```python
# GOOD - Always return a usable URL
def get_file_url(file_path: str) -> str:
    if settings.use_gcs:
        try:
            return bucket.blob(file_path).generate_signed_url(...)
        except Exception as e:
            logger.warning(f"GCS URL failed: {e}")
    
    # Local fallback URL
    return f"/files/{file_path}"
```

**When You Might Be Tempted:** Returning `None` seems simpler, but it pushes error handling to every caller. Provide a fallback instead.
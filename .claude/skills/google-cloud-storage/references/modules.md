# GCS Modules Reference

## Contents
- StorageService Architecture
- Integration with FastAPI Routes
- Integration with Firestore
- RRC Data Pipeline Integration
- Local Data Directory Structure

---

## StorageService Architecture

### Module Location

**Path:** `backend/app/services/storage_service.py`

**Imports:**
```python
from __future__ import annotations
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from app.core.config import get_settings

if TYPE_CHECKING:
    from google.cloud.storage import Bucket, Client

logger = logging.getLogger(__name__)
```

**Key architectural decisions:**
1. **Lazy GCS import** - Only imports `google.cloud.storage` if `config.use_gcs` is `True`
2. **TYPE_CHECKING imports** - Type hints for GCS objects without runtime import
3. **Pathlib for local paths** - `Path` objects for filesystem operations
4. **Singleton pattern** - Single instance via dependency injection

---

### Class Structure

```python
class StorageService:
    """Manages file storage with GCS primary and local filesystem fallback.
    
    All methods transparently fall back to local storage when GCS is unavailable.
    Callers don't need to check GCS availability—it's handled automatically.
    """
    
    def __init__(self):
        self.config = get_settings()
        self.data_dir = Path(__file__).parent.parent / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.client: Client | None = None
        self.bucket: Bucket | None = None
        
        if self.config.use_gcs:
            self._init_gcs()
    
    def _init_gcs(self):
        """Initialize GCS client. Logs warning on failure, doesn't raise."""
        try:
            from google.cloud import storage as gcs
            self.client = gcs.Client(project=self.config.gcs_project_id)
            self.bucket = self.client.bucket(self.config.gcs_bucket_name)
            logger.info(f"GCS initialized: {self.config.gcs_bucket_name}")
        except Exception as e:
            logger.warning(f"GCS initialization failed: {e}, using local storage only")
            self.client = None
            self.bucket = None
```

**Design patterns:**
- **Fail-safe initialization** - GCS errors don't crash the service
- **Explicit None types** - `client` and `bucket` can be `None`
- **Logging for observability** - Info on success, warning on failure

---

### Dependency Injection

StorageService is injected into route handlers as a singleton.

**Dependency pattern:**
```python
# backend/app/services/storage_service.py
_storage_service: StorageService | None = None

def get_storage_service() -> StorageService:
    """Get or create singleton StorageService instance."""
    global _storage_service
    if _storage_service is None:
        _storage_service = StorageService()
    return _storage_service
```

**Usage in routes:**
```python
from fastapi import Depends
from app.services.storage_service import get_storage_service, StorageService

@router.post("/upload")
async def upload_file(
    file: UploadFile,
    storage: StorageService = Depends(get_storage_service)
):
    content = await file.read()
    file_path = await storage.upload_file(
        file_content=content,
        filename=file.filename,
        subfolder="uploads"
    )
    return {"file_path": file_path}
```

**Why singleton pattern:**
1. GCS client is expensive to initialize (network connection, auth)
2. Bucket object can be reused across requests
3. Local data directory only needs one mkdir check

For dependency injection patterns, see the **fastapi** skill.

---

## Integration with FastAPI Routes

### Extract Tool Upload

**File:** `backend/app/api/extract.py`

```python
from fastapi import APIRouter, UploadFile, HTTPException, Depends
from app.services.storage_service import get_storage_service, StorageService
from app.services.extract.pdf_extractor import extract_text_from_pdf
from app.services.extract.party_parser import parse_parties

router = APIRouter()

@router.post("/extract/upload")
async def upload_exhibit_a(
    file: UploadFile,
    storage: StorageService = Depends(get_storage_service)
):
    # Validate file type
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files allowed")
    
    # Read and store
    content = await file.read()
    stored_path = await storage.upload_file(
        file_content=content,
        filename=file.filename,
        subfolder="extract/uploads"
    )
    
    # Extract and parse
    text = extract_text_from_pdf(content)
    parties = parse_parties(text)
    
    return {
        "file_path": stored_path,
        "party_count": len(parties),
        "parties": parties
    }
```

**Integration points:**
1. `storage.upload_file()` - Persist uploaded PDF
2. File validation before upload (reduces storage waste)
3. Path returned to client for future reference

---

### Proration RRC Data Download

**File:** `backend/app/api/proration.py`

```python
from app.services.proration.rrc_data_service import download_and_sync_rrc_data

@router.post("/proration/rrc/download")
async def trigger_rrc_download():
    """Manually trigger RRC data download and sync to storage + Firestore."""
    try:
        result = await download_and_sync_rrc_data()
        return {
            "status": "success",
            "oil_count": result["oil_count"],
            "gas_count": result["gas_count"],
            "timestamp": result["timestamp"]
        }
    except Exception as e:
        logger.error(f"RRC download failed: {e}")
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")
```

**Under the hood** (`backend/app/services/proration/rrc_data_service.py`):
```python
from app.services.storage_service import get_storage_service

async def download_and_sync_rrc_data():
    storage = get_storage_service()
    
    # Download from RRC website (requires custom SSL adapter)
    oil_csv = download_rrc_csv("OIL")
    gas_csv = download_rrc_csv("GAS")
    
    # Upload to storage (GCS or local)
    await storage.upload_file(
        file_content=oil_csv.encode('utf-8'),
        filename="oil_proration.csv",
        subfolder="rrc-data"
    )
    await storage.upload_file(
        file_content=gas_csv.encode('utf-8'),
        filename="gas_proration.csv",
        subfolder="rrc-data"
    )
    
    # Parse and cache in memory
    oil_df = pd.read_csv(io.StringIO(oil_csv))
    gas_df = pd.read_csv(io.StringIO(gas_csv))
    
    # Sync to Firestore
    await sync_to_firestore(oil_df, "OIL")
    await sync_to_firestore(gas_df, "GAS")
    
    return {
        "oil_count": len(oil_df),
        "gas_count": len(gas_df),
        "timestamp": datetime.utcnow().isoformat()
    }
```

**Storage role:** First persistence layer before in-memory cache and Firestore sync.

---

### Export Download Endpoint

**Pattern:** Serve files with GCS signed URLs or local fallback

```python
@router.get("/proration/export/download")
async def download_proration_export(
    file_path: str,
    storage: StorageService = Depends(get_storage_service)
):
    # Try signed URL first (GCS only)
    signed_url = storage.get_signed_url(file_path, expiration_minutes=15)
    
    if signed_url:
        return RedirectResponse(url=signed_url)
    
    # Fallback: serve from local filesystem
    try:
        content = await storage.download_file(file_path)
        return Response(
            content=content,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={Path(file_path).name}"}
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Export file not found")
```

**Integration points:**
1. `get_signed_url()` - Preferred (offloads download to GCS)
2. `download_file()` - Fallback (streams through FastAPI)
3. `FileNotFoundError` handling

---

## Integration with Firestore

### File Metadata Tracking

**Pattern:** Store file paths in Firestore for job tracking

```python
from app.services.firestore_service import get_firestore_client

async def create_extract_job(user_email: str, file_path: str, parties: list):
    db = get_firestore_client()
    
    job_data = {
        "user_email": user_email,
        "file_path": file_path,  # Path from storage.upload_file()
        "party_count": len(parties),
        "created_at": datetime.utcnow(),
        "tool": "extract",
        "status": "completed"
    }
    
    doc_ref = db.collection("jobs").document()
    doc_ref.set(job_data)
    
    return doc_ref.id
```

**Why store file_path in Firestore:**
1. **Job history** - Users can see which files they uploaded
2. **Re-download** - Retrieve file later via `storage.download_file(file_path)`
3. **Cleanup** - Identify old files for deletion (if implemented)

For Firestore patterns, see the **firestore** skill.

---

### RRC Data Sync to Firestore

**File:** `backend/app/services/proration/rrc_data_service.py`

```python
async def sync_to_firestore(df: pd.DataFrame, well_type: str):
    """Sync RRC CSV data to Firestore for persistence and querying."""
    db = get_firestore_client()
    collection_name = f"rrc_data_{well_type.lower()}"
    
    # Firestore batch limit: 500 operations
    batch = db.batch()
    batch_count = 0
    
    for idx, row in df.iterrows():
        doc_ref = db.collection(collection_name).document(str(row["lease_number"]))
        doc_data = row.to_dict()
        batch.set(doc_ref, doc_data)
        
        batch_count += 1
        if batch_count >= 500:
            await batch.commit()
            batch = db.batch()
            batch_count = 0
    
    # Commit remaining
    if batch_count > 0:
        await batch.commit()
    
    logger.info(f"Synced {len(df)} {well_type} records to Firestore")
```

**Integration flow:**
1. Download RRC CSV → `storage.upload_file()` (durable backup)
2. Parse CSV → pandas DataFrame (in-memory cache)
3. Sync DataFrame → Firestore (queryable persistence)

**Storage role:** Durable backup of raw CSV. Firestore stores parsed records for querying.

---

## RRC Data Pipeline Integration

### Scheduled Download (APScheduler)

**File:** `backend/app/main.py`

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.services.proration.rrc_data_service import download_and_sync_rrc_data

scheduler = AsyncIOScheduler()

@app.on_event("startup")
async def startup_event():
    # Schedule monthly RRC data download
    scheduler.add_job(
        download_and_sync_rrc_data,
        trigger="cron",
        day=1,  # 1st of month
        hour=2,  # 2 AM
        minute=0,
        id="rrc_monthly_sync"
    )
    scheduler.start()
    logger.info("RRC data sync scheduled: 1st of month at 2 AM")
```

**Storage integration:**
- RRC data downloaded as CSV string
- `storage.upload_file()` saves to `rrc-data/oil_proration.csv` and `rrc-data/gas_proration.csv`
- Local dev: saves to `backend/data/rrc-data/`
- Production: saves to GCS bucket

For scheduling patterns, see the **apscheduler** skill.

---

### CSV Processor (In-Memory Cache)

**File:** `backend/app/services/proration/csv_processor.py`

```python
from app.services.storage_service import get_storage_service
import pandas as pd
import io

# In-memory cache
_rrc_cache: dict[str, pd.DataFrame] = {}

async def load_rrc_data_into_cache():
    """Load RRC CSV from storage into memory for fast lookups."""
    storage = get_storage_service()
    
    # Download from storage (GCS or local)
    oil_content = await storage.download_file("rrc-data/oil_proration.csv")
    gas_content = await storage.download_file("rrc-data/gas_proration.csv")
    
    # Parse into DataFrames
    _rrc_cache["OIL"] = pd.read_csv(io.BytesIO(oil_content))
    _rrc_cache["GAS"] = pd.read_csv(io.BytesIO(gas_content))
    
    logger.info(f"RRC data loaded: {len(_rrc_cache['OIL'])} oil, {len(_rrc_cache['GAS'])} gas")

def lookup_lease(lease_number: str, well_type: str) -> dict | None:
    """Fast in-memory lookup of RRC data."""
    df = _rrc_cache.get(well_type)
    if df is None:
        return None
    
    match = df[df["lease_number"] == lease_number]
    if match.empty:
        return None
    
    return match.iloc[0].to_dict()
```

**Storage integration:**
1. Download CSV via `storage.download_file()`
2. Cache in memory as pandas DataFrame
3. Fast lookups during proration calculations (no storage or DB queries)

For pandas patterns, see the **pandas** skill.

---

## Local Data Directory Structure

### Directory Layout

```
backend/data/
├── uploads/           # User-uploaded files
│   ├── extract/       # OCC Exhibit A PDFs
│   ├── title/         # Title opinion Excel/CSV
│   ├── proration/     # Mineral holder CSVs
│   └── revenue/       # Revenue statement PDFs
├── rrc-data/          # RRC proration CSVs
│   ├── oil_proration.csv
│   └── gas_proration.csv
├── exports/           # Generated exports
│   ├── proration_reports/
│   └── revenue_m1_uploads/
└── allowed_users.json # Auth allowlist
```

**Creation:**
All directories are created automatically by `StorageService.__init__()` or on first upload.

```python
self.data_dir = Path(__file__).parent.parent / "data"
self.data_dir.mkdir(parents=True, exist_ok=True)

# Subdirectories created on upload
local_path = self.data_dir / full_path  # e.g., data/uploads/extract/file.pdf
local_path.parent.mkdir(parents=True, exist_ok=True)
```

---

### Mirroring GCS Structure

Local filesystem mirrors GCS bucket structure exactly:

| GCS Path | Local Path | Purpose |
|----------|------------|---------|
| `uploads/extract/file.pdf` | `backend/data/uploads/extract/file.pdf` | Extract PDFs |
| `rrc-data/oil_proration.csv` | `backend/data/rrc-data/oil_proration.csv` | RRC oil data |
| `exports/report.pdf` | `backend/data/exports/report.pdf` | Generated exports |

**Why mirror:** File paths are identical regardless of backend. Code doesn't need to know which backend is active.

---

### .gitignore Patterns

```
# backend/.gitignore
data/uploads/
data/exports/
data/rrc-data/*.csv

# Keep directory structure
!data/uploads/.gitkeep
!data/exports/.gitkeep
!data/rrc-data/.gitkeep

# Allow allowlist file
!data/allowed_users.json
```

**Rationale:**
- Don't commit user uploads or generated files
- Keep directory structure for local dev
- Commit `allowed_users.json` (auth config, not sensitive data)
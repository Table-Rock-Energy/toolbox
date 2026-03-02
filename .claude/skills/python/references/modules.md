# Python Modules Reference

## Contents
- Project Structure
- Module Organization
- Import Patterns
- Dependency Injection
- Service Layer Pattern
- Tool-Per-Module Architecture

---

## Project Structure

```
backend/app/
├── main.py                     # FastAPI app, routers, startup/shutdown
├── api/                        # Route handlers (one per tool)
│   ├── extract.py              # /api/extract/* endpoints
│   ├── title.py
│   ├── proration.py
│   ├── revenue.py
│   ├── admin.py
│   └── history.py
├── models/                     # Pydantic models (one per tool)
│   ├── extract.py              # PartyEntry, ExtractionResult
│   ├── title.py
│   ├── proration.py
│   ├── revenue.py
│   └── db_models.py            # SQLAlchemy ORM (optional)
├── services/                   # Business logic
│   ├── extract/                # PDF extraction (6 files)
│   ├── title/                  # Excel processing
│   ├── proration/              # RRC data + calculations (8 files)
│   ├── revenue/                # Revenue parsing
│   ├── storage_service.py      # GCS + local fallback
│   ├── firestore_service.py    # Firestore CRUD
│   └── db_service.py           # PostgreSQL (optional)
├── core/                       # App config
│   ├── config.py               # Pydantic Settings
│   ├── auth.py                 # Firebase token verification
│   └── database.py             # SQLAlchemy engine
└── utils/                      # Shared helpers
    ├── patterns.py             # Regex, US states
    └── helpers.py              # Date parsing, UID generation
```

---

## Module Organization

### DO: Tool-Per-Module Pattern

```python
# backend/app/api/proration.py
from fastapi import APIRouter, HTTPException, UploadFile
from app.models.proration import MineralHolderRow, RRCQueryResult
from app.services.proration.csv_processor import process_mineral_holders
from app.services.proration.rrc_data_service import download_rrc_data

router = APIRouter(prefix="/proration", tags=["Proration"])

@router.post("/upload")
async def upload_csv(file: UploadFile):
    # Route logic only - delegate to service layer
    content = await file.read()
    result = await process_mineral_holders(content)
    return result

@router.post("/rrc/download")
async def trigger_rrc_download():
    status = await download_rrc_data()
    return status
```

**Why:** One router per tool, routes delegate to service layer. Keeps route handlers thin and testable.

### DON'T: Business Logic in Route Handlers

```python
# BAD - Route handler doing too much
@router.post("/upload")
async def upload_csv(file: UploadFile):
    content = await file.read()
    df = pd.read_csv(io.BytesIO(content))
    
    # 50 lines of CSV processing here...
    for _, row in df.iterrows():
        # RRC lookup logic...
        # NRA calculation...
        # Validation...
    
    return {"status": "done"}
```

**Why This Breaks:** Untestable (requires HTTP request), violates SRP, can't reuse logic.

**The Fix:** Extract to `services/proration/csv_processor.py` and import.

---

## Import Patterns

### DO: Lazy Imports for Heavy Dependencies

```python
# backend/app/services/firestore_service.py
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from google.cloud.firestore import Client

_firestore_client: Client | None = None

def _get_firestore() -> Client:
    """Lazy init to avoid crashes when credentials missing."""
    global _firestore_client
    if _firestore_client is None:
        from google.cloud import firestore  # Import only when needed
        _firestore_client = firestore.Client()
    return _firestore_client
```

**Why:** Firebase/GCS imports fail if credentials missing. Lazy init allows local dev without GCP.

### WARNING: Circular Dependencies

**The Problem:**

```python
# backend/app/services/proration/csv_processor.py
from app.services.proration.rrc_data_service import get_rrc_data

# backend/app/services/proration/rrc_data_service.py
from app.services.proration.csv_processor import process_csv

# ImportError: cannot import name 'get_rrc_data'
```

**Why This Breaks:** Module A imports B, B imports A. Python can't resolve the circular dependency.

**The Fix:**

1. **Restructure:** Move shared code to a third module
2. **Lazy import:** Import inside function instead of top-level
3. **Dependency injection:** Pass dependencies as function arguments

```python
# GOOD - Dependency injection
# backend/app/services/proration/csv_processor.py
def process_csv(content: bytes, rrc_lookup_fn):
    # Uses passed-in function instead of importing
    rrc_data = rrc_lookup_fn(lease_number)

# backend/app/api/proration.py
from app.services.proration.csv_processor import process_csv
from app.services.proration.rrc_data_service import get_rrc_data

result = process_csv(content, rrc_lookup_fn=get_rrc_data)
```

---

## Dependency Injection

### DO: Pass Dependencies as Arguments

```python
# backend/app/services/extract/pdf_parser.py
async def parse_pdf(
    content: bytes,
    storage_service=None,
    firestore_service=None
):
    storage = storage_service or get_default_storage()
    db = firestore_service or get_default_firestore()
    
    # Parse PDF...
    await storage.upload_file("parsed.json", result)
    await db.save_job(job_id, metadata)
```

**Why:** Testable with mock dependencies. No global state.

### DON'T: Direct Imports of Stateful Services

```python
# BAD - Hardcoded dependencies, hard to test
from app.services.storage_service import upload_file
from app.services.firestore_service import save_job

async def parse_pdf(content: bytes):
    # Can't test without real GCS/Firestore
    await upload_file("parsed.json", result)
    await save_job(job_id, metadata)
```

**Why This Breaks:** Tests require real GCS/Firestore or complex mocking. Dependency injection allows passing fakes.

---

## Service Layer Pattern

### DO: {domain}_service.py Naming

```
services/
├── storage_service.py          # GCS + local filesystem
├── firestore_service.py        # Firestore CRUD
├── extract/
│   ├── pdf_parser.py           # PDF text extraction
│   ├── party_parser.py         # Party name parsing
│   └── export_service.py       # CSV/Excel export
├── proration/
│   ├── rrc_data_service.py     # RRC download
│   ├── csv_processor.py        # CSV parsing + lookup
│   ├── calculation_service.py  # NRA calculations
│   └── export_service.py       # Excel/PDF export
```

**Why:** Consistent naming (`{domain}_service.py`, `{type}_parser.py`, `export_service.py`) makes code discoverable.

### DON'T: Generic Names Like utils.py or helpers.py for Business Logic

```python
# BAD - Vague naming
services/
├── utils.py                    # What utils? Storage? Parsing?
├── helpers.py                  # Too generic
└── proration_stuff.py          # Unprofessional
```

**Why This Breaks:** Generic names become dumping grounds for unrelated code. Use specific names.

---

## Tool-Per-Module Architecture

Each tool (Extract, Title, Proration, Revenue) has:

1. **API route:** `api/{tool}.py` - HTTP endpoints
2. **Pydantic models:** `models/{tool}.py` - Request/response types
3. **Service layer:** `services/{tool}/` - Business logic

### Example: Proration Module

```python
# backend/app/api/proration.py
from fastapi import APIRouter
from app.models.proration import MineralHolderRow, ProrationResult
from app.services.proration.csv_processor import process_csv

router = APIRouter(prefix="/proration")

@router.post("/upload")
async def upload(file: UploadFile) -> ProrationResult:
    content = await file.read()
    return await process_csv(content)
```

```python
# backend/app/models/proration.py
from pydantic import BaseModel, Field

class MineralHolderRow(BaseModel):
    name: str = Field(..., description="Mineral holder name")
    nra: float = Field(..., description="Net revenue acres")

class ProrationResult(BaseModel):
    rows: list[MineralHolderRow]
    total_nra: float
```

```python
# backend/app/services/proration/csv_processor.py
import pandas as pd
from app.models.proration import ProrationResult

async def process_csv(content: bytes) -> ProrationResult:
    df = pd.read_csv(io.BytesIO(content))
    # Processing logic...
    return ProrationResult(rows=rows, total_nra=total)
```

**Why:** Clear separation of concerns. Routes handle HTTP, models handle validation, services handle business logic.
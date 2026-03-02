---
name: python
description: |
  Writes Python services, async/await patterns, and module organization for FastAPI backend with Firestore, GCS, and pandas-based document processing.
  Use when: Creating new services, refactoring business logic, adding async operations, working with Pydantic models, or organizing modules in the backend.
allowed-tools: Read, Edit, Write, Glob, Grep, Bash
---

# Python Skill

This backend uses **FastAPI with async/await** patterns, **Pydantic** for validation, **pandas** for CSV/Excel processing, and **Firestore** for persistence. All services follow a strict pattern: `{domain}_service.py` with lazy initialization for Firebase/GCS clients. Use `python3` command (not `python`) and snake_case naming everywhere.

## Quick Start

### Service Module Pattern

```python
# backend/app/services/{domain}_service.py
from __future__ import annotations
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from google.cloud.firestore import Client

logger = logging.getLogger(__name__)
_firestore_client: Client | None = None

def _get_firestore() -> Client:
    """Lazy init to avoid errors when GCS not available."""
    global _firestore_client
    if _firestore_client is None:
        from google.cloud import firestore
        _firestore_client = firestore.Client()
    return _firestore_client

async def process_data(data: list[dict]) -> dict:
    """Process data with proper error handling."""
    try:
        # Business logic here
        return {"status": "success", "count": len(data)}
    except Exception as e:
        logger.error(f"Processing failed: {e}")
        raise
```

### Async Route Handler

```python
# backend/app/api/extract.py
from fastapi import APIRouter, HTTPException, UploadFile
from app.models.extract import ExtractionResult
from app.services.extract.pdf_parser import parse_pdf

router = APIRouter()

@router.post("/upload", response_model=ExtractionResult)
async def upload_pdf(file: UploadFile):
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="PDF files only")
    
    try:
        content = await file.read()
        result = await parse_pdf(content)
        return result
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

### Pydantic Model with Field Descriptors

```python
# backend/app/models/proration.py
from pydantic import BaseModel, Field
from enum import Enum

class WellType(str, Enum):
    OIL = "Oil"
    GAS = "Gas"
    BOTH = "Both"

class MineralHolderRow(BaseModel):
    name: str = Field(..., description="Mineral holder full name")
    nra: float = Field(..., description="Net revenue acres")
    well_type: WellType = Field(default=WellType.OIL, description="Oil or Gas")
    lease_number: str | None = Field(None, description="RRC lease number")
```

## Key Concepts

| Concept | Usage | Example |
|---------|-------|---------|
| Async everywhere | All routes and DB ops | `async def upload_file()` |
| Lazy initialization | Firebase/GCS clients | `_get_firestore()` cached global |
| TYPE_CHECKING imports | Type hints without runtime overhead | `if TYPE_CHECKING: from google.cloud.firestore import Client` |
| Pydantic Settings | Env var management | `class Settings(BaseSettings)` with `@property` |
| snake_case | All Python code | `def process_csv()`, `total_count` |
| SCREAMING_SNAKE | Constants | `USERS_COLLECTION`, `M1_COLUMNS` |

## Common Patterns

### Storage Fallback Pattern

**When:** Working with GCS that may be unavailable in local dev

```python
# backend/app/services/storage_service.py
from app.core.config import settings

async def upload_file(file_path: str, content: bytes) -> str | None:
    """Upload to GCS, fallback to local on failure."""
    if settings.use_gcs:
        try:
            blob = bucket.blob(file_path)
            blob.upload_from_string(content)
            return blob.public_url
        except Exception as e:
            logger.warning(f"GCS upload failed, using local: {e}")
    
    # Local fallback
    local_path = f"data/{file_path}"
    Path(local_path).parent.mkdir(parents=True, exist_ok=True)
    Path(local_path).write_bytes(content)
    return f"/files/{file_path}"  # Local URL
```

### Firestore Batch Operations

**When:** Syncing large datasets (500 doc limit per batch)

```python
async def sync_to_firestore(records: list[dict]) -> int:
    """Batch write with 500-doc commit limit."""
    db = _get_firestore()
    batch = db.batch()
    count = 0
    
    for i, record in enumerate(records, 1):
        doc_ref = db.collection("rrc_data").document(record["id"])
        batch.set(doc_ref, record)
        count += 1
        
        if i % 500 == 0:  # Firestore limit
            batch.commit()
            batch = db.batch()
    
    if count % 500 != 0:
        batch.commit()
    
    return count
```

## See Also

- [patterns](references/patterns.md) - Service patterns, async/await, error handling
- [types](references/types.md) - Pydantic models, enums, type hints
- [modules](references/modules.md) - Project structure, imports, lazy init
- [errors](references/errors.md) - HTTPException, logging, fallback strategies

## Related Skills

- **fastapi** - Route handlers, dependency injection, middleware
- **pydantic** - Model validation, Settings, Field descriptors
- **firestore** - Firestore CRUD, batch operations, queries
- **google-cloud-storage** - GCS upload/download, signed URLs
- **pandas** - DataFrame operations, CSV processing, in-memory caching
- **pytest** - Async testing, httpx client, fixtures
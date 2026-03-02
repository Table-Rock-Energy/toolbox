# Database Reference

## Contents
- Firestore Async Client
- Batch Operations
- RRC Data Upsert Pattern
- Job Tracking
- Query Patterns

## Firestore Async Client

### Lazy Client Initialization

```python
# toolbox/backend/app/services/firestore_service.py
from google.cloud.firestore_v1 import AsyncClient

_db: Optional[AsyncClient] = None

def get_firestore_client() -> AsyncClient:
    """Get or create Firestore async client."""
    global _db
    if _db is None:
        _db = firestore.AsyncClient(
            project=settings.gcs_project_id,
            database="tablerocktools"
        )
    return _db
```

**WHY:** Defers client initialization until first use, avoids startup crashes if credentials unavailable.

### Collection Constants

```python
# Collection names
USERS_COLLECTION = "users"
JOBS_COLLECTION = "jobs"
EXTRACT_ENTRIES_COLLECTION = "extract_entries"
TITLE_ENTRIES_COLLECTION = "title_entries"
PRORATION_ROWS_COLLECTION = "proration_rows"
REVENUE_STATEMENTS_COLLECTION = "revenue_statements"
RRC_OIL_COLLECTION = "rrc_oil_proration"
RRC_GAS_COLLECTION = "rrc_gas_proration"
RRC_SYNC_COLLECTION = "rrc_data_syncs"
AUDIT_LOGS_COLLECTION = "audit_logs"
```

**WHY:** Centralized collection names prevent typos, easy to refactor.

## Batch Operations

### Firestore 500-Document Limit

```python
# toolbox/backend/app/services/firestore_service.py
async def save_extract_entries(job_id: str, entries: list[dict]) -> int:
    """Save extract entries for a job."""
    db = get_firestore_client()
    batch = db.batch()
    count = 0
    
    for entry_data in entries:
        doc_ref = db.collection(EXTRACT_ENTRIES_COLLECTION).document()
        entry_data["job_id"] = job_id
        entry_data["created_at"] = datetime.utcnow()
        batch.set(doc_ref, entry_data)
        count += 1
        
        # Firestore batch limit is 500
        if count % 500 == 0:
            await batch.commit()
            batch = db.batch()
    
    # Commit remaining
    if count % 500 != 0:
        await batch.commit()
    
    logger.info(f"Saved {count} entries for job {job_id}")
    return count
```

**WHY:** Firestore hard limit of 500 operations per batch. Must commit and create new batch every 500 docs.

### DO: Batch Related Operations

```python
# GOOD - Batch entry saves for performance
async def save_proration_rows(job_id: str, rows: list[dict]) -> int:
    db = get_firestore_client()
    batch = db.batch()
    count = 0
    
    for row_data in rows:
        doc_ref = db.collection(PRORATION_ROWS_COLLECTION).document()
        row_data["job_id"] = job_id
        row_data["created_at"] = datetime.utcnow()
        batch.set(doc_ref, row_data)
        count += 1
        
        if count % 500 == 0:
            await batch.commit()
            batch = db.batch()
    
    if count % 500 != 0:
        await batch.commit()
    
    return count
```

**WHY:** Single batch write (500 docs) is ~50x faster than 500 individual writes. Critical for RRC data sync (40k+ rows).

### DON'T: Individual Writes in Loops

```python
# BAD - Slow, expensive (one write per doc)
async def save_entries(job_id: str, entries: list[dict]):
    db = get_firestore_client()
    for entry in entries:
        doc_ref = db.collection(EXTRACT_ENTRIES_COLLECTION).document()
        await doc_ref.set(entry)  # WRONG - individual write
```

**WHY THIS BREAKS:** 1000 entries = 1000 individual writes = ~30 seconds. Batching: ~1 second. Also hits rate limits.

## RRC Data Upsert Pattern

### Detecting Changes for Updates

```python
# toolbox/backend/app/services/firestore_service.py
async def upsert_rrc_oil_record(
    district: str,
    lease_number: str,
    operator_name: Optional[str] = None,
    unit_acres: Optional[float] = None,
    raw_data: Optional[dict] = None
) -> tuple[dict, bool, bool]:
    """
    Insert or update RRC oil proration record.
    Returns: (record, is_new, is_updated)
    """
    db = get_firestore_client()
    doc_id = f"{district}-{lease_number}"
    doc_ref = db.collection(RRC_OIL_COLLECTION).document(doc_id)
    doc = await doc_ref.get()
    
    record_data = {
        "district": district,
        "lease_number": lease_number,
        "operator_name": operator_name,
        "unit_acres": unit_acres,
        "raw_data": raw_data,
        "updated_at": datetime.utcnow()
    }
    
    if doc.exists:
        existing = doc.to_dict()
        # Check if data changed
        changed = (
            existing.get("unit_acres") != unit_acres or
            existing.get("operator_name") != operator_name
        )
        if changed:
            await doc_ref.update(record_data)
            return record_data, False, True  # Updated
        return existing, False, False  # Unchanged
    else:
        record_data["created_at"] = datetime.utcnow()
        await doc_ref.set(record_data)
        return record_data, True, False  # New
```

**WHY:** Monthly RRC sync should only update changed records. Tracking new/updated/unchanged counts helps monitor data drift.

### DO: Use Composite Document IDs

```python
# GOOD - Unique, deterministic doc ID
doc_id = f"{district}-{lease_number}"
doc_ref = db.collection(RRC_OIL_COLLECTION).document(doc_id)
```

**WHY:** Predictable IDs enable upserts (idempotent), prevent duplicate records.

### DON'T: Auto-Generate IDs for Updatable Data

```python
# BAD - Creates duplicate records on re-sync
doc_ref = db.collection(RRC_OIL_COLLECTION).document()  # WRONG - random ID
await doc_ref.set(record_data)
```

**WHY THIS BREAKS:** Next sync creates new docs instead of updating existing. 12 months = 12 duplicate copies of 40k records.

## Job Tracking

### Job Lifecycle Pattern

```python
# toolbox/backend/app/services/firestore_service.py
async def create_job(
    tool: str,
    source_filename: str,
    user_id: Optional[str] = None,
    options: Optional[dict] = None
) -> dict:
    """Create a new processing job."""
    db = get_firestore_client()
    job_id = str(uuid4())
    
    job_data = {
        "id": job_id,
        "user_id": user_id,
        "tool": tool,
        "status": "pending",
        "source_filename": source_filename,
        "options": options or {},
        "total_count": 0,
        "success_count": 0,
        "error_count": 0,
        "created_at": datetime.utcnow(),
        "completed_at": None
    }
    
    await db.collection(JOBS_COLLECTION).document(job_id).set(job_data)
    return job_data

async def update_job_status(
    job_id: str,
    status: str,
    total_count: int = 0,
    success_count: int = 0,
    error_count: int = 0,
    error_message: Optional[str] = None
) -> Optional[dict]:
    """Update job status and counts."""
    db = get_firestore_client()
    job_ref = db.collection(JOBS_COLLECTION).document(job_id)
    
    update_data = {
        "status": status,
        "total_count": total_count,
        "success_count": success_count,
        "error_count": error_count,
        "error_message": error_message,
        "updated_at": datetime.utcnow()
    }
    
    if status in ("completed", "failed"):
        update_data["completed_at"] = datetime.utcnow()
    
    await job_ref.update(update_data)
    return (await job_ref.get()).to_dict()
```

**WHY:** Persistent job tracking for async operations, enables history/audit trail, useful for debugging.

## Query Patterns

### Filtered and Ordered Queries

```python
# toolbox/backend/app/services/firestore_service.py
async def get_user_jobs(
    user_id: str,
    tool: Optional[str] = None,
    limit: int = 50
) -> list[dict]:
    """Get jobs for a user, optionally filtered by tool."""
    db = get_firestore_client()
    query = db.collection(JOBS_COLLECTION).where("user_id", "==", user_id)
    
    if tool:
        query = query.where("tool", "==", tool)
    
    query = query.order_by("created_at", direction=firestore.Query.DESCENDING).limit(limit)
    docs = await query.get()
    return [doc.to_dict() for doc in docs]
```

**WHY:** Firestore queries are eventually consistent, ordering ensures latest jobs appear first.

### DO: Use Compound Queries with Indexes

```python
# GOOD - Filter + order requires composite index
query = db.collection(JOBS_COLLECTION).where("user_id", "==", user_id)
query = query.where("tool", "==", tool)
query = query.order_by("created_at", direction=firestore.Query.DESCENDING)
```

**WHY:** Firestore automatically creates single-field indexes. Multi-field queries require composite index (created automatically on first use).

### DON'T: Fetch All Then Filter in Python

```python
# BAD - Loads all docs into memory, slow
all_jobs = await db.collection(JOBS_COLLECTION).get()
user_jobs = [doc.to_dict() for doc in all_jobs if doc.to_dict().get("user_id") == user_id]
```

**WHY THIS BREAKS:** Reads all documents (expensive), doesn't scale past 1k docs, wastes bandwidth/memory.

### Counting Documents

```python
# toolbox/backend/app/services/firestore_service.py
async def get_rrc_data_status() -> dict:
    db = get_firestore_client()
    
    # Count using aggregation query (efficient)
    oil_count_query = db.collection(RRC_OIL_COLLECTION).count()
    oil_count_result = await oil_count_query.get()
    oil_rows = oil_count_result[0][0].value if oil_count_result else 0
    
    return {"oil_rows": oil_rows}
```

**WHY:** `.count()` is a server-side aggregation, doesn't transfer documents. Much faster than `.get()` + `len()`.
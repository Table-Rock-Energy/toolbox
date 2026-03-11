# Firestore Patterns Reference

## Contents
- Lazy Async Client Initialization
- Batch Writes with 500-Doc Limit
- Deterministic Document IDs for Idempotent Upserts
- Batch Reads with `get_all`
- Count Aggregation Queries
- Composite Index Fallback
- Background Thread: Sync Client Only

---

## Lazy Async Client Initialization

**Why:** Importing Firebase at module level crashes when `GOOGLE_APPLICATION_CREDENTIALS` is not set (local dev, CI). The module-level `_db` singleton avoids re-initializing per request.

```python
# backend/app/services/firestore_service.py
from __future__ import annotations
from typing import Optional
from google.cloud import firestore
from google.cloud.firestore_v1 import AsyncClient
from app.core.config import settings

_db: Optional[AsyncClient] = None

def get_firestore_client() -> AsyncClient:
    global _db
    if _db is None:
        _db = firestore.AsyncClient(
            project=settings.gcs_project_id,
            database="tablerocktools",  # Named database, not default
        )
    return _db
```

**DO:** Import `google.cloud.firestore` at the top of the service file (it's the library, not a side-effectful init). The actual client object is what must be created lazily.

**DON'T:**
```python
# BAD - creates client at import time, crashes without credentials
from google.cloud import firestore
db = firestore.AsyncClient()  # Module-level client
```

---

## Batch Writes with 500-Doc Limit

**Why:** Firestore enforces a hard limit of 500 operations per batch. Exceeding it raises a `google.api_core.exceptions.InvalidArgument` error. The remainder check (`count % 500 != 0`) is critical — without it, the last partial batch is silently dropped.

```python
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
            batch = db.batch()  # MUST create a new batch after commit

    if count % 500 != 0:  # Commit the remainder
        await batch.commit()

    return count
```

**DO:** Reset the batch with `batch = db.batch()` after each commit.

**DON'T:**
```python
# BAD - no batching, crashes on >500 items
batch = db.batch()
for item in ten_thousand_items:
    batch.set(ref, item)
await batch.commit()  # Raises InvalidArgument
```

### Batch Delete Pattern

Same 500-limit applies to deletes. Used in `delete_job()`:

```python
batch = db.batch()
count = 0
for doc in docs:
    batch.delete(doc.reference)
    count += 1
    if count % 500 == 0:
        await batch.commit()
        batch = db.batch()
if count % 500 != 0:
    await batch.commit()
```

---

## Deterministic Document IDs for Idempotent Upserts

**Why:** Auto-generated IDs cause duplicates when the same PDF is re-uploaded. Deterministic IDs derived from natural keys make re-uploads idempotent — the second write overwrites the first.

```python
# backend/app/services/firestore_service.py - save_revenue_statement()
import hashlib

key_parts = [
    statement_data.get("check_number") or "",
    statement_data.get("owner_number") or "",
    statement_data.get("owner_name") or "",
    statement_data.get("filename") or "",
]
composite = "|".join(str(p).lower() for p in key_parts)
statement_id = hashlib.sha256(composite.encode()).hexdigest()[:20]

# Preserve created_at if overwriting an existing doc
existing = await db.collection(REVENUE_STATEMENTS_COLLECTION).document(statement_id).get()
created_at = existing.to_dict().get("created_at", datetime.utcnow()) if existing.exists else datetime.utcnow()
```

**For simpler cases** (RRC records), use a composite key directly:

```python
# district + lease_number makes a globally unique RRC identifier
doc_id = f"{district}-{lease_number}"
doc_ref = db.collection(RRC_OIL_COLLECTION).document(doc_id)
```

**DO:** Preserve `created_at` when overwriting — only update `updated_at`.

**DON'T:**
```python
# BAD - generates new ID on every call, creates duplicates
doc_ref = db.collection("revenue_statements").document()  # Auto-ID
await doc_ref.set(statement_doc)
```

---

## Batch Reads with `get_all`

**Why:** Fetching N documents one-by-one is N round trips. `get_all()` fetches up to 100 refs in a single RPC. Used for county status lookups.

```python
# backend/app/services/firestore_service.py - get_counties_status()
async def get_counties_status(keys: list[str]) -> dict[str, dict]:
    db = get_firestore_client()
    result: dict[str, dict] = {}

    # Firestore get_all supports up to 100 refs at a time
    for i in range(0, len(keys), 100):
        batch_keys = keys[i:i + 100]
        refs = [
            db.collection(RRC_COUNTY_STATUS_COLLECTION).document(k)
            for k in batch_keys
        ]
        docs = db.get_all(refs)
        async for doc in docs:
            if doc.exists:
                result[doc.id] = doc.to_dict()

    return result
```

**Note:** `db.get_all()` returns an async generator — use `async for`, not `await`.

---

## Count Aggregation Queries

**Why:** `len(await collection.get())` downloads all documents to count them. The `.count()` aggregation runs server-side and returns only the number.

```python
# backend/app/services/firestore_service.py - get_rrc_data_status()
oil_count_query = db.collection(RRC_OIL_COLLECTION).count()
oil_count_result = await oil_count_query.get()
oil_rows = oil_count_result[0][0].value if oil_count_result else 0
```

**DO:** Use `.count()` for status/health checks.

**DON'T:**
```python
# BAD - downloads every document just to count
all_docs = await db.collection(RRC_OIL_COLLECTION).get()
count = len(all_docs)  # Wastes bandwidth, slow on large collections
```

---

## Composite Index Fallback

**Why:** Firestore requires composite indexes for queries that filter on one field and order by another. Indexes don't exist until explicitly created in the GCP console. Missing indexes throw an exception with a URL to create the index.

```python
async def get_recent_jobs(tool: str | None = None, limit: int = 20) -> list[dict]:
    db = get_firestore_client()
    query = db.collection(JOBS_COLLECTION)
    if tool:
        query = query.where("tool", "==", tool)

    try:
        query = query.order_by("created_at", direction=firestore.Query.DESCENDING).limit(limit)
        docs = await query.get()
    except Exception:
        # Composite index missing — fall back to client-side sort
        logger.warning("Firestore composite index missing for get_recent_jobs")
        base_query = db.collection(JOBS_COLLECTION)
        if tool:
            base_query = base_query.where("tool", "==", tool)
        docs = await base_query.limit(limit).get()
        docs = sorted(docs, key=lambda d: d.to_dict().get("created_at", ""), reverse=True)

    return [doc.to_dict() for doc in docs]
```

**When to create the index:** The exception message includes a direct URL to create the missing index in the GCP console. Do that for production; the fallback is a safety net.

---

## Background Thread: Sync Client Only

**Why:** Background threads (used in `rrc_background.py` for APScheduler jobs) run outside the asyncio event loop. `AsyncClient` requires an active event loop — calling it from a background thread raises `RuntimeError: no running event loop`.

```python
# backend/app/services/rrc_background.py
# CORRECT: synchronous client for background thread
from google.cloud import firestore as sync_firestore

def _get_sync_client():
    return sync_firestore.Client(
        project=settings.gcs_project_id,
        database="tablerocktools",
    )

def run_rrc_sync_job(job_id: str):
    """Called from APScheduler background thread — must use sync client."""
    db = _get_sync_client()
    # Use db.collection(...).document(...).set(...) — no await
    db.collection("rrc_sync_jobs").document(job_id).update({"status": "running"})
```

**DO:** Use `firestore.Client()` (sync) in background threads, `firestore.AsyncClient()` in async route handlers.

**DON'T:**
```python
# BAD - AsyncClient in a background thread
async def background_task():  # NOT called with await from a thread
    db = firestore.AsyncClient()  # RuntimeError in APScheduler job
    await db.collection("jobs").document(job_id).update(...)
```

See the **apscheduler** skill for the full background task pattern.

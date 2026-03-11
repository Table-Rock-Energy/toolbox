# Firestore Workflows Reference

## Contents
- Job Lifecycle (Create → Update → Query)
- RRC Data Sync to Firestore
- County Status Tracking
- Adding a New Collection

---

## Job Lifecycle (Create → Update → Query)

**Goal:** Track a processing job from creation through completion with status updates.

### Workflow Steps

```
Copy this checklist and track progress:
- [ ] Step 1: Call create_job() at start of upload handler
- [ ] Step 2: Run processing logic
- [ ] Step 3: Call update_job_status() with final counts
- [ ] Step 4: Save tool-specific entries (save_extract_entries, etc.)
- [ ] Step 5: Frontend polls or queries job history
```

### Step 1: Create job

```python
# backend/app/api/extract.py
from app.services import firestore_service as fs

@router.post("/upload")
async def upload_extract(file: UploadFile, user=Depends(get_current_user)):
    job = await fs.create_job(
        tool="extract",
        source_filename=file.filename,
        user_id=user["uid"],
        user_name=user.get("name"),
        source_file_size=file.size,
    )
    job_id = job["id"]
    # job_id is a UUID string — store for subsequent updates
```

### Step 2-3: Update on completion

```python
    try:
        entries = await run_extraction(file_content)
        await fs.update_job_status(
            job_id=job_id,
            status="completed",
            total_count=len(entries),
            success_count=len(entries),
            error_count=0,
        )
        await fs.save_extract_entries(job_id, [e.model_dump() for e in entries])
    except Exception as e:
        await fs.update_job_status(
            job_id=job_id,
            status="failed",
            error_message=str(e),
        )
        raise HTTPException(status_code=500, detail=str(e))
```

### Step 4: Query job history

```python
# backend/app/api/history.py
@router.get("/jobs")
async def get_jobs(tool: str | None = None, user=Depends(get_current_user)):
    jobs = await fs.get_user_jobs(user_id=user["uid"], tool=tool)
    return {"jobs": jobs}
```

### Validation

```bash
# Trigger upload, then check job was created
curl -X POST http://localhost:8000/api/extract/upload -F "file=@test.pdf" -H "Authorization: Bearer TOKEN"

# Verify job appears in history
curl http://localhost:8000/api/history/jobs -H "Authorization: Bearer TOKEN"
# Response should include job with status "completed" or "failed"
```

**Iterate until pass:**
1. Create job → verify document exists in Firestore `jobs` collection
2. Complete processing → verify status updated to `completed`
3. Query history → verify job appears with correct counts
4. If job stuck at `pending`, check error handling in upload handler

---

## RRC Data Sync to Firestore

**Goal:** Sync thousands of RRC lease records to Firestore with batching and sync status tracking.

### Workflow Steps

```
Copy this checklist and track progress:
- [ ] Step 1: Start sync — call start_rrc_sync()
- [ ] Step 2: Iterate records, call upsert_rrc_oil_record() per record (batched by caller)
- [ ] Step 3: Track new/updated/unchanged counts
- [ ] Step 4: Complete sync — call complete_rrc_sync()
- [ ] Step 5: Verify status via get_rrc_data_status()
```

### Step 1-2: Upsert with change detection

```python
# backend/app/services/rrc_background.py
from app.services import firestore_service as fs

async def sync_oil_records(records: list[dict]) -> dict:
    sync_id = await fs.start_rrc_sync("oil")
    new_count = updated_count = unchanged_count = 0

    for record in records:
        _, is_new, is_updated = await fs.upsert_rrc_oil_record(
            district=record["district"],
            lease_number=record["lease_number"],
            operator_name=record.get("operator_name"),
            lease_name=record.get("lease_name"),
            unit_acres=float(record.get("unit_acres") or 0),
            allowable=float(record.get("allowable") or 0),
            raw_data=record,
        )
        if is_new:
            new_count += 1
        elif is_updated:
            updated_count += 1
        else:
            unchanged_count += 1

    await fs.complete_rrc_sync(
        sync_id=sync_id,
        total_records=len(records),
        new_records=new_count,
        updated_records=updated_count,
        unchanged_records=unchanged_count,
        success=True,
    )
    return {"new": new_count, "updated": updated_count, "unchanged": unchanged_count}
```

Note: `upsert_rrc_oil_record` does individual `get` + conditional `set`/`update` per record (not batched). For large syncs, batch the initial write using the batch pattern from `patterns.md` and skip change detection.

### Step 5: Check sync status

```python
# Callable from /api/proration/rrc/status
status = await fs.get_rrc_data_status()
# Returns: {oil_rows: int, gas_rows: int, last_sync: {...}, oil_available: bool}
```

### Validation

```bash
# Trigger sync
curl -X POST http://localhost:8000/api/proration/rrc/download -H "Authorization: Bearer TOKEN"

# Poll job status
curl http://localhost:8000/api/proration/rrc/download/{job_id}/status

# Check data status
curl http://localhost:8000/api/proration/rrc/status
# oil_rows and gas_rows should be > 0
```

See the **apscheduler** skill for how the monthly scheduled sync is wired up.

---

## County Status Tracking

**Goal:** Track which counties have been downloaded and when, to avoid redundant re-downloads.

### Staleness Check

```python
# backend/app/services/firestore_service.py
async def get_stale_counties(keys: list[str]) -> list[str]:
    statuses = await get_counties_status(keys)  # Batch read via get_all()
    first_of_month = datetime.now(timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    stale = []
    for key in keys:
        status = statuses.get(key)
        if not status or status.get("status") == "failed":
            stale.append(key)
            continue
        if status.get("oil_record_count", 0) == 0:
            stale.append(key)
            continue
        last_dl = status.get("last_downloaded_at")
        if not last_dl or last_dl < first_of_month:
            stale.append(key)
    return stale
```

### Update after download

```python
await fs.update_county_status(
    key="08-003",  # district-county_code format
    data={
        "status": "success",
        "last_downloaded_at": datetime.now(timezone.utc),
        "oil_record_count": len(records),
    }
)
# merge=True ensures this patches the document, not replaces it
```

**DO:** Use `merge=True` (set in `update_county_status`) so partial updates don't wipe existing fields.

**DON'T:**
```python
# BAD - replaces entire document, loses other fields
await doc_ref.set({"status": "success"})  # No merge=True
```

---

## Adding a New Collection

**Goal:** Add a new Firestore collection for a new tool or feature.

### Checklist

```
Copy this checklist and track progress:
- [ ] Step 1: Add a constant to firestore_service.py
- [ ] Step 2: Add save_{entity}() function with batch write
- [ ] Step 3: Add get_{entity}() function with job_id filter
- [ ] Step 4: Call save in the tool's API handler after processing
- [ ] Step 5: Add delete logic to delete_job() map
```

### Step 1-3: Collection constant + CRUD

```python
# backend/app/services/firestore_service.py

# Step 1: Add constant
MY_TOOL_ENTRIES_COLLECTION = "my_tool_entries"

# Step 2: Save with batch write
async def save_my_tool_entries(job_id: str, entries: list[dict]) -> int:
    db = get_firestore_client()
    batch = db.batch()
    count = 0
    for entry in entries:
        doc_ref = db.collection(MY_TOOL_ENTRIES_COLLECTION).document()
        entry["job_id"] = job_id
        entry["created_at"] = datetime.utcnow()
        batch.set(doc_ref, entry)
        count += 1
        if count % 500 == 0:
            await batch.commit()
            batch = db.batch()
    if count % 500 != 0:
        await batch.commit()
    return count

# Step 3: Get by job
async def get_my_tool_entries(job_id: str) -> list[dict]:
    db = get_firestore_client()
    docs = await db.collection(MY_TOOL_ENTRIES_COLLECTION).where("job_id", "==", job_id).get()
    return [doc.to_dict() for doc in docs]
```

### Step 5: Wire into delete_job()

```python
# backend/app/services/firestore_service.py - delete_job()
entries_collection = {
    "extract": EXTRACT_ENTRIES_COLLECTION,
    "title": TITLE_ENTRIES_COLLECTION,
    "proration": PRORATION_ROWS_COLLECTION,
    "revenue": REVENUE_STATEMENTS_COLLECTION,
    "my_tool": MY_TOOL_ENTRIES_COLLECTION,  # Add here
}.get(tool)
```

### Validation

```bash
# Run a job for the new tool, then verify entries in Firestore
curl -X POST http://localhost:8000/api/my-tool/upload -F "file=@test.csv" -H "Authorization: Bearer TOKEN"

# Verify entries saved (check GCP Firestore console or via API)
curl http://localhost:8000/api/history/jobs -H "Authorization: Bearer TOKEN"
# job should show total_count > 0 and status "completed"
```

**Iterate until pass:**
1. Upload file → verify job created in `jobs` collection
2. Processing completes → verify entries in new collection with correct `job_id`
3. Delete job → verify entries also deleted
4. If entries not deleted, check `delete_job()` map includes new tool name

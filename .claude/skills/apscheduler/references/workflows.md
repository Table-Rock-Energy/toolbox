# APScheduler Workflows Reference

## Contents
- Adding a New Background Job (Current Pattern)
- Debugging Failed Jobs
- Testing Background Jobs Locally
- Adding a New APScheduler Job (Non-Cloud-Run)
- Job State Machine

---

## Adding a New Background Job (Current Pattern)

The existing `rrc_background.py` pattern is the template for all background work in this project. Follow these steps to add a new long-running job.

### Workflow Checklist

Copy this checklist and track progress:
- [ ] Step 1: Create background worker function in a `*_background.py` service file
- [ ] Step 2: Create Firestore job tracking functions (create, update, add_step)
- [ ] Step 3: Add API endpoint to trigger the job
- [ ] Step 4: Add API endpoint to poll job status
- [ ] Step 5: Test by calling the trigger endpoint locally
- [ ] Step 6: Verify Firestore job document is created and updated
- [ ] Step 7: Test error case (confirm `status: "failed"` is written)

### Step 1: Background Worker

```python
# backend/app/services/my_background.py
import asyncio
import logging
import threading
from datetime import datetime
from typing import Optional
from google.cloud import firestore
from app.core.config import settings

logger = logging.getLogger(__name__)
JOBS_COLLECTION = "my_jobs"

_sync_client: Optional[firestore.Client] = None

def _get_sync_client() -> firestore.Client:
    global _sync_client
    if _sync_client is None:
        _sync_client = firestore.Client(
            project=settings.gcs_project_id,
            database="tablerocktools",
        )
    return _sync_client

def create_job() -> str:
    db = _get_sync_client()
    job_id = f"job-{datetime.utcnow().strftime('%Y-%m-%dT%H-%M-%S')}"
    db.collection(JOBS_COLLECTION).document(job_id).set({
        "id": job_id,
        "status": "running",
        "started_at": datetime.utcnow(),
        "completed_at": None,
        "error": None,
    })
    return job_id

def _run_job(job_id: str) -> None:
    """The actual work. Runs in a background thread."""
    db = _get_sync_client()
    ref = db.collection(JOBS_COLLECTION).document(job_id)
    try:
        # Sync operations work directly
        do_sync_work()

        # Async operations: bridge with asyncio.run()
        result = asyncio.run(do_async_work())

        ref.update({"status": "complete", "completed_at": datetime.utcnow()})
    except Exception as e:
        logger.exception(f"Job {job_id} failed: {e}")
        try:
            ref.update({
                "status": "failed",
                "error": str(e),
                "completed_at": datetime.utcnow(),
            })
        except Exception:
            pass  # Best-effort status update

def start_background_job() -> str:
    job_id = create_job()
    thread = threading.Thread(
        target=_run_job, args=(job_id,), daemon=True, name=f"job-{job_id}"
    )
    thread.start()
    return job_id
```

### Step 2: API Endpoints

```python
# backend/app/api/my_tool.py
from app.services.my_background import start_background_job, get_job_status

@router.post("/run")
async def trigger_job():
    """Start background job. Returns job_id for polling."""
    job_id = start_background_job()
    return {"job_id": job_id, "status": "started"}

@router.get("/run/{job_id}/status")
async def poll_job_status(job_id: str):
    """Poll job status. Frontend polls until status is 'complete' or 'failed'."""
    from app.services.firestore_service import get_firestore_client
    db = get_firestore_client()
    doc = await db.collection("my_jobs").document(job_id).get()
    if not doc.exists:
        raise HTTPException(404, "Job not found")
    return doc.to_dict()
```

---

## Debugging Failed Jobs

### Check Firestore Job Document First

When a job fails, the `status: "failed"` and `error` fields in Firestore are the first place to look:

```python
# In a Python shell or test:
from google.cloud import firestore
db = firestore.Client(project="tablerockenergy", database="tablerocktools")
doc = db.collection("rrc_sync_jobs").document("rrc-sync-2026-03-01T02-00-00").get()
print(doc.to_dict())
# {"status": "failed", "error": "SSL error: ...", "steps": [...]}
```

### Common Failure Modes

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| `status` stuck at `"downloading_oil"` | Thread crashed before updating Firestore | Check Cloud Run logs for the thread exception |
| `"RuntimeError: no running event loop"` | Used async Firestore client in thread | Use `_get_sync_firestore_client()` |
| `"RuntimeError: This event loop is already running"` | Called `asyncio.run()` from within an async context | Only call `asyncio.run()` from sync thread functions |
| Job never starts | Thread creation failed | Check available memory in Cloud Run instance |
| RRC SSL error | RRC website SSL config | Verify `RRCSSLAdapter` is configured in `rrc_data_service.py` |

### Cloud Run Logs

```bash
# Filter for background job output
gcloud logging read \
  "resource.type=cloud_run_revision AND \
   resource.labels.service_name=table-rock-tools AND \
   textPayload=~'rrc-sync'" \
  --limit 50 --format="value(textPayload)"
```

### Iterate-Until-Pass

1. Check Firestore `rrc_sync_jobs` for `error` field
2. Fix root cause in code
3. Restart backend: `make dev-backend`
4. Manually trigger: `POST /api/proration/rrc/download`
5. Poll status: `GET /api/proration/rrc/download/{job_id}/status`
6. If still failing, go to step 1

---

## Testing Background Jobs Locally

### Direct Function Call (Fastest)

Bypass the thread entirely — call the worker function directly:

```python
# In backend/ directory:
python3 -c "
from app.services.rrc_background import _run_rrc_download, create_rrc_sync_job
job_id = create_rrc_sync_job()
print(f'Job: {job_id}')
_run_rrc_download(job_id)  # Runs synchronously in the shell
print('Done')
"
```

### Via API (With Thread)

```bash
# Trigger download
curl -X POST http://localhost:8000/api/proration/rrc/download

# Poll status (replace JOB_ID)
curl http://localhost:8000/api/proration/rrc/download/rrc-sync-2026-03-01T02-00-00/status
```

### Verify Firestore Job Document

```bash
# Check job was created and completed in Firestore
# Use Firebase Console or the Admin SDK
python3 -c "
from google.cloud import firestore
db = firestore.Client(database='tablerocktools')
jobs = db.collection('rrc_sync_jobs').order_by('started_at', direction=firestore.Query.DESCENDING).limit(3).get()
for j in jobs:
    d = j.to_dict()
    print(d['id'], d['status'], d.get('error'))
"
```

---

## Adding a New APScheduler Job (Non-Cloud-Run)

Only use APScheduler if deploying to an always-on environment (VM, Kubernetes, Docker with restart policy):

```python
# backend/app/main.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from app.services.my_service import my_async_job

scheduler = AsyncIOScheduler(timezone="America/Chicago")

@app.on_event("startup")
async def startup_event():
    if settings.environment != "production":  # Avoid on Cloud Run
        scheduler.add_job(
            my_async_job,
            trigger=CronTrigger(day=1, hour=2, minute=0),
            id="my_job",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        scheduler.start()
        logger.info("APScheduler started")

@app.on_event("shutdown")
async def shutdown_event():
    if scheduler.running:
        scheduler.shutdown(wait=False)
```

---

## Job State Machine

The RRC job progresses through states. New jobs should follow this same pattern:

```
created
    │
    ▼
downloading_oil ──→ failed (oil download failed)
    │
    ▼
downloading_gas ──→ failed (gas download failed)
    │
    ▼
syncing_oil ──────→ failed (Firestore oil sync failed)
    │
    ▼
syncing_gas ──────→ failed (Firestore gas sync failed)
    │
    ▼
complete
```

**Rule:** Each step updates `status` in Firestore before starting and writes `error` + `completed_at` on failure. Never skip writing terminal state — a job stuck in a non-terminal state will confuse the frontend polling.

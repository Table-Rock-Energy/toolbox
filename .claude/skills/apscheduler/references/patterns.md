# APScheduler Patterns Reference

## Contents
- Current Architecture (Why APScheduler Was Removed)
- threading.Thread Pattern (Current Approach)
- Sync Firestore Client in Background Threads
- Async-in-Thread Pattern
- Firestore Job Status Tracking
- APScheduler Patterns (Non-Cloud-Run Only)
- Anti-Patterns

---

## Current Architecture: Why APScheduler Was Removed

Cloud Run scales to **0 instances** when idle. An in-process APScheduler dies when the instance shuts down — the cron trigger fires on no running process.

**The comment in `backend/app/main.py` (line 138):**
```python
# NOTE: RRC monthly download is triggered externally via GitHub Actions cron
# (see .github/workflows/rrc-download.yml). APScheduler was removed because
# Cloud Run scales to 0 instances, killing in-process schedulers.
```

**Current architecture:**
```
GitHub Actions cron (monthly)
         │
         ▼
POST /api/proration/rrc/download  ← also manually triggerable
         │
         ▼
threading.Thread(_run_rrc_download)  [backend/app/services/rrc_background.py]
         │
         ▼
Firestore rrc_sync_jobs (status polling)
         │
         ▼
GET /rrc/download/{job_id}/status  ← frontend polls this
```

---

## threading.Thread Pattern (Current Approach)

From `backend/app/services/rrc_background.py`:

```python
def start_rrc_background_download() -> str:
    """Returns job_id immediately; download runs in background thread."""
    job_id = create_rrc_sync_job()  # Creates Firestore doc first

    thread = threading.Thread(
        target=_run_rrc_download,
        args=(job_id,),
        daemon=True,                    # Critical: dies with process, no zombie threads
        name=f"rrc-download-{job_id}", # Named for /proc debugging
    )
    thread.start()
    return job_id  # API returns immediately, client polls for status
```

**Always use `daemon=True`.** Without it, background threads block Cloud Run container shutdown, causing health check timeouts and failed deployments.

---

## Sync Firestore Client in Background Threads

Background threads run **outside the asyncio event loop**. The async Firestore client from `firestore_service.py` cannot be used — it raises `RuntimeError: no running event loop`.

```python
# GOOD: Separate synchronous Firestore client for background thread
from google.cloud import firestore

_sync_firestore_client: Optional[firestore.Client] = None

def _get_sync_firestore_client() -> firestore.Client:
    """Lazy singleton — separate from the async client in API endpoints."""
    global _sync_firestore_client
    if _sync_firestore_client is None:
        _sync_firestore_client = firestore.Client(
            project=settings.gcs_project_id,
            database="tablerocktools",
        )
    return _sync_firestore_client
```

```python
# BAD: Using the async client from firestore_service in a thread
from app.services.firestore_service import get_firestore_client

def background_fn():
    db = get_firestore_client()  # Returns AsyncClient
    db.collection("jobs").document(job_id).update(...)  # Crashes: no event loop
```

See the **firestore** skill for async client patterns used in API endpoints.

---

## Async-in-Thread Pattern

When a background thread needs to call an async function (like `sync_to_database`), use `asyncio.run()`:

```python
def _run_rrc_download(job_id: str) -> None:
    """Sync function running in a thread."""
    try:
        # Sync download works normally
        oil_success, msg, count = rrc_data_service.download_oil_data()

        # Async Firestore sync: bridge with asyncio.run()
        oil_sync_result = asyncio.run(rrc_data_service.sync_to_database("oil"))
    except Exception as e:
        logger.exception(f"Unexpected error in job {job_id}: {e}")
        try:
            update_rrc_sync_job(job_id, {
                "status": "failed",
                "error": str(e),
                "completed_at": datetime.utcnow(),
            })
        except Exception as update_err:
            logger.error(f"Failed to update job status: {update_err}")
```

**Always wrap `asyncio.run()` in try/except.** If the async call raises, you still need to update Firestore status — don't let the error propagate silently.

---

## Firestore Job Status Tracking

The `rrc_sync_jobs` Firestore collection tracks long-running background jobs:

```python
def create_rrc_sync_job() -> str:
    db = _get_sync_firestore_client()
    job_id = f"rrc-sync-{datetime.utcnow().strftime('%Y-%m-%dT%H-%M-%S')}"
    job_data = {
        "id": job_id,
        "status": "downloading_oil",   # State machine: downloading_oil → downloading_gas → syncing_oil → syncing_gas → complete/failed
        "started_at": datetime.utcnow(),
        "completed_at": None,
        "oil_rows": 0,
        "gas_rows": 0,
        "error": None,
        "steps": [],                   # Append-only step log
    }
    db.collection("rrc_sync_jobs").document(job_id).set(job_data)
    return job_id
```

**Terminal states** are `"complete"` and `"failed"`. Polling stops when either is reached.

---

## APScheduler Patterns (Non-Cloud-Run Only)

Use APScheduler only when the deployment **does not scale to 0** (always-on VMs, Docker with restart policy):

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# AsyncIOScheduler: shares the event loop, supports async def jobs
# BackgroundScheduler: NEVER use in FastAPI — blocks the event loop
scheduler = AsyncIOScheduler(timezone="America/Chicago")  # Texas time for RRC

@app.on_event("startup")
async def startup_event():
    scheduler.add_job(
        my_async_job,
        trigger=CronTrigger(day=1, hour=2, minute=0),
        id="monthly_job",
        replace_existing=True,   # Safe on app restart (dev reload creates duplicates otherwise)
        misfire_grace_time=3600, # Run up to 1h late if instance was briefly down
    )
    scheduler.start()

@app.on_event("shutdown")
async def shutdown_event():
    scheduler.shutdown(wait=False)  # Don't block shutdown waiting for running jobs
```

**Trigger types:**
- `CronTrigger(day=1, hour=2)` — specific calendar date/time ("1st of month at 2 AM")
- `IntervalTrigger(days=7)` — fixed period ("every 7 days")

---

## Anti-Patterns

### WARNING: APScheduler on Cloud Run

**The Problem:**
```python
# BAD: In-process scheduler on a scale-to-zero deployment
scheduler = AsyncIOScheduler()
scheduler.add_job(monthly_job, CronTrigger(day=1, hour=2))
scheduler.start()
```

**Why This Breaks:**
1. Cloud Run scales to 0 at night — exactly when monthly jobs are scheduled
2. The trigger fires but no instance is running to execute it
3. `misfire_grace_time` doesn't help because the process doesn't exist
4. Job silently never runs — no error logged anywhere

**The Fix:** External cron (GitHub Actions) + POST endpoint.

---

### WARNING: Async Firestore in Background Thread

```python
# BAD: async client in threading.Thread
from app.services.firestore_service import get_firestore_client

def worker(job_id):
    db = get_firestore_client()              # AsyncClient
    db.collection("jobs").document(job_id).update({...})  # RuntimeError: no running event loop
```

**The Fix:** Use a separate synchronous `firestore.Client` (see Sync Firestore Client section above).

---

### WARNING: Missing daemon=True

```python
# BAD: Non-daemon thread blocks process shutdown
thread = threading.Thread(target=long_running_job)
thread.start()
# Cloud Run sends SIGTERM → process waits for thread → health check fails → forced kill
```

```python
# GOOD: Daemon thread exits with the process
thread = threading.Thread(target=long_running_job, daemon=True)
thread.start()
```

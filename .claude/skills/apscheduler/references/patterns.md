# APScheduler Patterns Reference

## Contents
- Scheduler Initialization
- Cron Triggers vs Interval Triggers
- Job Idempotency
- Timezone Handling
- Logging and Monitoring
- Anti-Patterns

---

## Scheduler Initialization

### AsyncIOScheduler for FastAPI

**ALWAYS use AsyncIOScheduler** when running inside a FastAPI/asyncio application. BackgroundScheduler will block the event loop.

```python
# GOOD - Non-blocking async scheduler
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

@app.on_event("startup")
async def startup_event():
    scheduler.start()
```

```python
# BAD - Blocks the event loop, freezes API requests
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()  # Wrong for async apps
```

**Why This Breaks:**
1. BackgroundScheduler runs in a separate thread pool, not the asyncio event loop
2. Async jobs (`async def`) won't execute correctly
3. Database connections/async clients may fail with thread safety errors

---

## Cron Triggers vs Interval Triggers

### Monthly Schedule (1st of Month)

```python
# GOOD - Cron trigger for specific date/time
from apscheduler.triggers.cron import CronTrigger

scheduler.add_job(
    download_rrc_data_job,
    trigger=CronTrigger(day=1, hour=2, minute=0),  # 1st of month at 2 AM
    id="rrc_data_download",
    replace_existing=True,
)
```

### Every N Days (Interval)

```python
# GOOD - Interval trigger for periodic execution
from apscheduler.triggers.interval import IntervalTrigger

scheduler.add_job(
    cleanup_old_files,
    trigger=IntervalTrigger(days=7),  # Every 7 days
    id="file_cleanup",
)
```

**Decision Tree:**
- **Cron**: Specific calendar date/time (e.g., "1st of month", "every Monday at 9 AM")
- **Interval**: Fixed time periods (e.g., "every 6 hours", "every 30 minutes")

---

## Job Idempotency

### WARNING: Non-Idempotent Downloads

**The Problem:**

```python
# BAD - Re-running fails or duplicates data
async def download_rrc_data_job():
    # Download overwrites file - OK
    await download_csv_from_rrc()
    
    # Sync to Firestore - NOT IDEMPOTENT if it appends
    await sync_to_firestore()  # Duplicates data if run twice
```

**Why This Breaks:**
1. Job fails mid-execution → partial state in database
2. Manual re-trigger after failure → duplicate records
3. Clock drift or scheduler restart → job runs twice

**The Fix:**

```python
# GOOD - Idempotent with transaction-style sync
async def download_rrc_data_job():
    # Always overwrites file (idempotent)
    await download_csv_from_rrc()
    
    # Clear old data before sync (idempotent)
    await clear_rrc_collection()
    await sync_to_firestore()
    
    # Or use upsert with unique keys
    await upsert_rrc_data_by_lease_number()
```

**Current Implementation:**
The RRC data service uses `sync_to_database()` which **batches upserts** by lease number. Safe to re-run.

---

## Timezone Handling

### WARNING: Naive Datetimes

**The Problem:**

```python
# BAD - Defaults to server local timezone (undefined on Cloud Run)
scheduler.add_job(
    job_func,
    trigger=CronTrigger(hour=2),  # 2 AM in what timezone?
)
```

**Why This Breaks:**
1. Cloud Run containers may run in UTC or undefined timezone
2. Daylight Saving Time transitions can skip/duplicate job runs
3. Moving servers changes job execution time

**The Fix:**

```python
# GOOD - Explicit timezone
from apscheduler.triggers.cron import CronTrigger
from pytz import timezone

central = timezone('America/Chicago')

scheduler.add_job(
    download_rrc_data_job,
    trigger=CronTrigger(day=1, hour=2, minute=0, timezone=central),
    id="rrc_data_download",
)
```

**For This Codebase:**
RRC data is Texas-based. Use `America/Chicago` (Central Time) for consistency with business hours.

---

## Logging and Monitoring

### Job Success/Failure Tracking

```python
# GOOD - Comprehensive logging
async def download_rrc_data_job():
    logger.info("Starting scheduled RRC data download")
    start_time = time.time()
    
    try:
        result = await download_and_sync_rrc_data()
        duration = time.time() - start_time
        logger.info(f"RRC download completed in {duration:.2f}s: {result}")
        
        # Optional: Store success status in Firestore
        await update_job_status("rrc_data_download", "success", result)
        
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"RRC download failed after {duration:.2f}s: {e}", exc_info=True)
        
        # Optional: Store failure for monitoring
        await update_job_status("rrc_data_download", "failed", str(e))
        raise  # Re-raise to mark job as failed
```

### Scheduler Event Listeners

```python
# GOOD - Monitor all job executions
def job_listener(event):
    if event.exception:
        logger.error(f"Job {event.job_id} failed: {event.exception}")
    else:
        logger.info(f"Job {event.job_id} succeeded")

scheduler.add_listener(
    job_listener,
    EVENT_JOB_EXECUTED | EVENT_JOB_ERROR
)
```

---

## Anti-Patterns

### 1. Blocking I/O in Async Jobs

```python
# BAD - Blocks event loop
async def download_job():
    response = requests.get(url)  # Synchronous HTTP call
    data = response.json()
```

```python
# GOOD - Use async HTTP client
import httpx

async def download_job():
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        data = response.json()
```

**Exception:** The RRC service uses `requests` with a custom SSL adapter because RRC's outdated SSL config doesn't work with `httpx`. This is acceptable since the job runs in background.

### 2. Missing replace_existing

```python
# BAD - Creates duplicate jobs on app restart
scheduler.add_job(
    job_func,
    trigger=CronTrigger(hour=2),
    id="daily_job",
)
```

```python
# GOOD - Replaces existing job with same ID
scheduler.add_job(
    job_func,
    trigger=CronTrigger(hour=2),
    id="daily_job",
    replace_existing=True,  # Safe on restart
)
```

**Why This Breaks:**
FastAPI dev mode uses auto-reload. Each reload creates a new scheduler instance. Without `replace_existing=True`, jobs accumulate and run multiple times.

### 3. Long-Running Jobs Without Timeouts

```python
# BAD - Job may hang indefinitely
async def sync_job():
    await slow_external_api()  # No timeout
```

```python
# GOOD - Enforce timeout
import asyncio

async def sync_job():
    try:
        await asyncio.wait_for(slow_external_api(), timeout=300)
    except asyncio.TimeoutError:
        logger.error("Job exceeded 5-minute timeout")
        raise
```

**For Cloud Run:**
Maximum job duration must be **< 600s** (Cloud Run request timeout). Add timeouts to prevent jobs from blocking container shutdown.
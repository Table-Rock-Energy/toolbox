# APScheduler Workflows Reference

## Contents
- Adding a New Scheduled Job
- Debugging Failed Jobs
- Testing Scheduled Jobs Locally
- Monitoring in Production
- Handling Job Failures

---

## Adding a New Scheduled Job

### Workflow Checklist

Copy this checklist and track progress:
- [ ] 1. Create async job function in appropriate service file
- [ ] 2. Add logging (start, success, failure)
- [ ] 3. Ensure idempotency (safe to re-run)
- [ ] 4. Add job to scheduler in `main.py` startup
- [ ] 5. Test job manually via API endpoint
- [ ] 6. Verify logs in local dev
- [ ] 7. Deploy and monitor first production run

### Step 1: Create Job Function

```python
# toolbox/backend/app/services/export_cleanup_service.py
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

async def cleanup_old_exports_job():
    """Delete export files older than 30 days."""
    logger.info("Starting export cleanup job")
    
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=30)
        deleted_count = await delete_exports_before(cutoff_date)
        
        logger.info(f"Export cleanup completed: {deleted_count} files deleted")
        return {"deleted_count": deleted_count, "cutoff_date": cutoff_date.isoformat()}
        
    except Exception as e:
        logger.error(f"Export cleanup failed: {e}", exc_info=True)
        raise
```

**Requirements:**
1. **Async function** (`async def`)
2. **Logger** with module name
3. **Try/except** with logging
4. **Return value** (for monitoring/debugging)

### Step 2: Register Job in Scheduler

```python
# toolbox/backend/app/main.py
from apscheduler.triggers.cron import CronTrigger
from app.services.export_cleanup_service import cleanup_old_exports_job

@app.on_event("startup")
async def startup_event():
    # Existing RRC job
    scheduler.add_job(
        download_rrc_data_job,
        trigger=CronTrigger(day=1, hour=2, minute=0),
        id="rrc_data_download",
        replace_existing=True,
    )
    
    # NEW: Daily cleanup at 3 AM
    scheduler.add_job(
        cleanup_old_exports_job,
        trigger=CronTrigger(hour=3, minute=0),
        id="export_cleanup",
        replace_existing=True,
    )
    
    scheduler.start()
    logger.info("APScheduler started with 2 jobs")
```

### Step 3: Add Manual Trigger Endpoint (Optional)

```python
# toolbox/backend/app/api/admin.py
from app.services.export_cleanup_service import cleanup_old_exports_job

@router.post("/cleanup/trigger")
async def trigger_cleanup():
    """Manually trigger export cleanup (also runs daily at 3 AM)."""
    result = await cleanup_old_exports_job()
    return {"status": "success", "result": result}
```

**Why This Helps:**
1. Test job logic without waiting for schedule
2. Manually trigger cleanup after incidents
3. Validate job works before deploying schedule

---

## Debugging Failed Jobs

### Check Logs for Job Execution

```bash
# Local dev - check console output
# Look for:
# - "Starting scheduled RRC data download"
# - "RRC data download completed" or "RRC data download failed"

# Production (Cloud Run) - check logs
gcloud logging read "resource.type=cloud_run_revision AND \
  resource.labels.service_name=table-rock-tools AND \
  textPayload=~'RRC data download'" \
  --limit 50 --format json
```

### Common Failure Modes

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| Job not running | Scheduler not started | Check `startup_event()` logs |
| Job runs twice | Missing `replace_existing=True` | Add flag to `add_job()` |
| Job times out | Cloud Run 600s limit | Optimize job or increase timeout |
| RRC SSL error | Outdated RRC website SSL | Verify `RRCSSLAdapter` is used |
| Database error | Firestore/GCS unavailable | Add retry logic with exponential backoff |

### Manual Job Invocation for Testing

```python
# In a python3 REPL or test script
import asyncio
from app.services.proration.rrc_data_service import download_rrc_data_job

# Run job directly
asyncio.run(download_rrc_data_job())
```

### Iterate-Until-Pass Pattern

1. Identify failure from logs
2. Fix issue in job function
3. Restart backend: `make dev-backend`
4. Manually trigger job via API: `POST /api/admin/cleanup/trigger`
5. If job fails, check logs and repeat step 1
6. Only proceed when job succeeds

---

## Testing Scheduled Jobs Locally

### WARNING: Don't Wait for Schedule

**The Problem:**

```python
# BAD - Waiting for monthly job to test
scheduler.add_job(
    download_rrc_data_job,
    trigger=CronTrigger(day=1, hour=2),  # Must wait until next month
    id="rrc_data_download",
)
```

**The Fix:**

```python
# GOOD - Temporary interval trigger for testing
from apscheduler.triggers.interval import IntervalTrigger

scheduler.add_job(
    download_rrc_data_job,
    # In production: CronTrigger(day=1, hour=2)
    trigger=IntervalTrigger(minutes=5),  # Every 5 min for testing
    id="rrc_data_download",
    replace_existing=True,
)
```

### Environment-Based Scheduling

```python
# GOOD - Different schedules for dev/prod
from app.core.config import settings

if settings.environment == "production":
    trigger = CronTrigger(day=1, hour=2, minute=0)
else:
    # Dev: every 10 minutes for faster testing
    trigger = IntervalTrigger(minutes=10)

scheduler.add_job(
    download_rrc_data_job,
    trigger=trigger,
    id="rrc_data_download",
    replace_existing=True,
)
```

---

## Monitoring in Production

### Job Status Endpoint

```python
# toolbox/backend/app/api/admin.py
@router.get("/scheduler/jobs")
async def get_scheduled_jobs():
    """List all scheduled jobs and their next run times."""
    jobs = scheduler.get_jobs()
    return {
        "jobs": [
            {
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
            }
            for job in jobs
        ]
    }
```

**Expected Output:**

```json
{
  "jobs": [
    {
      "id": "rrc_data_download",
      "name": "download_rrc_data_job",
      "next_run": "2026-03-01T02:00:00",
      "trigger": "cron[day='1', hour='2', minute='0']"
    }
  ]
}
```

### Store Job Results in Firestore

```python
# GOOD - Persistent job history
from app.services.firestore_service import firestore_service

async def download_rrc_data_job():
    job_id = "rrc_data_download"
    start_time = datetime.utcnow()
    
    try:
        result = await download_and_sync_rrc_data()
        
        await firestore_service.create_document("job_history", {
            "job_id": job_id,
            "status": "success",
            "started_at": start_time,
            "completed_at": datetime.utcnow(),
            "result": result,
        })
        
    except Exception as e:
        await firestore_service.create_document("job_history", {
            "job_id": job_id,
            "status": "failed",
            "started_at": start_time,
            "completed_at": datetime.utcnow(),
            "error": str(e),
        })
        raise
```

---

## Handling Job Failures

### Retry Logic with Exponential Backoff

```python
# GOOD - Retry transient failures
import asyncio

async def download_with_retry(max_retries=3):
    for attempt in range(max_retries):
        try:
            return await download_csv_from_rrc()
        except (httpx.TimeoutError, ConnectionError) as e:
            if attempt == max_retries - 1:
                raise
            
            wait_time = 2 ** attempt  # 1s, 2s, 4s
            logger.warning(f"Download failed (attempt {attempt + 1}/{max_retries}), "
                          f"retrying in {wait_time}s: {e}")
            await asyncio.sleep(wait_time)
```

### Partial Success Handling

```python
# GOOD - Download both oil and gas, even if one fails
async def download_rrc_data_job():
    results = {"oil": None, "gas": None}
    errors = []
    
    try:
        results["oil"] = await download_oil_proration()
    except Exception as e:
        logger.error(f"Oil download failed: {e}")
        errors.append(f"oil: {e}")
    
    try:
        results["gas"] = await download_gas_proration()
    except Exception as e:
        logger.error(f"Gas download failed: {e}")
        errors.append(f"gas: {e}")
    
    if errors:
        raise Exception(f"Partial failure: {'; '.join(errors)}")
    
    return results
```

### Dead Letter Queue Pattern (Future Enhancement)

```python
# GOOD - For production-grade reliability
async def download_rrc_data_job():
    try:
        await download_and_sync_rrc_data()
    except Exception as e:
        # Push to dead letter queue for manual review
        await firestore_service.create_document("failed_jobs", {
            "job_id": "rrc_data_download",
            "error": str(e),
            "traceback": traceback.format_exc(),
            "timestamp": datetime.utcnow(),
        })
        
        # Optional: Send alert (email, Slack, etc.)
        await send_alert(f"RRC download failed: {e}")
        raise
```

**When You Might Be Tempted:**
If jobs fail intermittently and you need visibility into failure patterns, implement a dead letter queue to track failures for later investigation.
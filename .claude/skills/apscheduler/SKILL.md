---
name: apscheduler
description: |
  Schedules monthly RRC data downloads via APScheduler background tasks.
  Use when: implementing scheduled tasks, automating periodic jobs, managing background workers in FastAPI applications
allowed-tools: Read, Edit, Write, Glob, Grep, Bash
---

# APScheduler Skill

APScheduler manages background scheduled tasks in the Table Rock Tools backend. Currently runs a **monthly RRC data download** on the 1st of each month at 2 AM, fetching oil/gas proration data from the Texas Railroad Commission website.

## Quick Start

### Monthly RRC Data Download

```python
# toolbox/backend/app/main.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

scheduler = AsyncIOScheduler()

@app.on_event("startup")
async def startup_event():
    # Schedule monthly RRC download (1st of month at 2 AM)
    scheduler.add_job(
        download_rrc_data_job,
        trigger=CronTrigger(day=1, hour=2, minute=0),
        id="rrc_data_download",
        replace_existing=True,
    )
    scheduler.start()

@app.on_event("shutdown")
async def shutdown_event():
    scheduler.shutdown()
```

### Async Job Function

```python
# toolbox/backend/app/services/proration/rrc_data_service.py
async def download_rrc_data_job():
    """Background job for scheduled RRC data download."""
    logger.info("Starting scheduled RRC data download...")
    try:
        result = await download_and_sync_rrc_data()
        logger.info(f"RRC data download completed: {result}")
    except Exception as e:
        logger.error(f"RRC data download failed: {e}", exc_info=True)
```

## Key Concepts

| Concept | Usage | Example |
|---------|-------|---------|
| AsyncIOScheduler | FastAPI/asyncio integration | `scheduler = AsyncIOScheduler()` |
| CronTrigger | Cron-style scheduling | `CronTrigger(day=1, hour=2, minute=0)` |
| Job ID | Unique identifier for jobs | `id="rrc_data_download"` |
| replace_existing | Prevent duplicate jobs on restart | `replace_existing=True` |

## Common Patterns

### Startup/Shutdown Lifecycle

**When:** Integrating scheduler with FastAPI application lifecycle

```python
@app.on_event("startup")
async def startup_event():
    scheduler.add_job(...)
    scheduler.start()
    logger.info("APScheduler started")

@app.on_event("shutdown")
async def shutdown_event():
    scheduler.shutdown(wait=False)
    logger.info("APScheduler shutdown")
```

### Error Handling in Jobs

**When:** Preventing job failures from crashing the scheduler

```python
async def resilient_job():
    try:
        await risky_operation()
    except Exception as e:
        logger.error(f"Job failed: {e}", exc_info=True)
        # Scheduler continues running
```

### Manual Job Trigger

**When:** Providing an API endpoint to trigger scheduled jobs on-demand

```python
# toolbox/backend/app/api/proration.py
@router.post("/rrc/download")
async def trigger_rrc_download():
    """Manually trigger RRC data download (also runs monthly automatically)."""
    result = await download_and_sync_rrc_data()
    return {"status": "success", "result": result}
```

## Integration with This Codebase

APScheduler runs **inside the FastAPI Uvicorn process** (not a separate worker). Jobs execute asynchronously using the same event loop. For production, ensure:

1. **Cloud Run timeout** (600s) exceeds job duration
2. **Logging** captures job success/failure for monitoring
3. **Idempotency** in download logic (safe to re-run if job fails mid-execution)

## See Also

- [patterns](references/patterns.md) - Job configuration, timezone handling, idempotency
- [workflows](references/workflows.md) - Adding new scheduled tasks, debugging failed jobs

## Related Skills

- **fastapi** - Integrating scheduler with FastAPI lifecycle
- **python** - Async/await patterns for background jobs
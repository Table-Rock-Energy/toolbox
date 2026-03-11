# Product Analytics Reference

## Contents
- Current Analytics Infrastructure
- Job History as Proxy Analytics
- What to Measure per Tool
- Funnel Definition
- WARNING: Missing Instrumentation

---

## Current Analytics Infrastructure

Table Rock Tools has **no dedicated analytics library** (no Mixpanel, Amplitude, or GA4). The only usage data comes from Firestore job records written by the backend on each tool invocation.

Job records are stored in Firestore with this shape (from `backend/app/api/history.py`):
```python
# Firestore document in jobs collection
{
  "id": "...",
  "tool": "extract",           # Tool name
  "source_filename": "...",    # Uploaded file name
  "user_email": "...",         # Who ran it
  "user_id": "...",            # Firebase UID
  "created_at": "...",         # ISO timestamp
  "status": "completed",       # completed | failed
  "total_count": 42,           # Rows extracted
  "success_count": 38,
  "error_count": 4,
}
```

This is fetched by `GET /api/history/jobs` and rendered on the Dashboard.

---

## Job History as Proxy Analytics

Use `GET /api/history/jobs` for all usage analysis:

```bash
# Check adoption distribution across tools
curl http://localhost:8000/api/history/jobs?limit=1000 | \
  python3 -c "import json,sys; jobs=json.load(sys.stdin)['jobs']; \
  [print(j['tool']) for j in jobs]" | sort | uniq -c | sort -rn
```

```python
# Backend: Aggregate tool usage stats for admin view
# backend/app/api/history.py
@router.get("/stats")
async def get_usage_stats():
    jobs = await firestore_service.get_jobs(limit=1000)
    by_tool = {}
    for job in jobs:
        tool = job.get("tool")
        by_tool[tool] = by_tool.get(tool, {"count": 0, "errors": 0})
        by_tool[tool]["count"] += 1
        if job.get("status") == "failed":
            by_tool[tool]["errors"] += 1
    return by_tool
```

---

## What to Measure per Tool

**Extract**
- Upload-to-result success rate
- Flagged party rate (high = low PDF quality)
- Export rate (did they download after processing?)

**Title**
- Row count per job (signals file complexity)
- Duplicate detection rate
- Entity detection accuracy (requires user feedback)

**Proration**
- RRC lookup hit rate (`found_count` / `total_count`)
- Fetch-missing invocations (proxy for RRC data staleness)
- Export format distribution (Excel vs PDF)

**Revenue**
- Parser format distribution (EnergyLink vs Enverus vs Energy Transfer)
- Gemini fallback invocation rate (high = format mismatch growing)
- M1 export success rate

**GHL Prep**
- Flagged row rate
- Send-to-GHL completion rate (did prep lead to send?)

---

## Funnel Definition

Each tool has a 4-step funnel. All drop-offs are currently invisible:

```
Step 1: Tool opened (navigate to /extract)
Step 2: File uploaded (POST /api/extract/upload called)
Step 3: Results reviewed (time on page after results load)
Step 4: Export triggered (POST /api/extract/export/csv called)
```

**GOOD - Log funnel events to Firestore:**
```python
# backend/app/api/extract.py — after successful processing
await firestore_service.log_event({
    "event": "extract_upload_complete",
    "user_id": current_user["uid"],
    "row_count": len(result.entries),
    "flagged_count": result.flagged_count,
})
```

```python
# On export endpoint
await firestore_service.log_event({
    "event": "extract_export",
    "user_id": current_user["uid"],
    "format": "csv",
})
```

---

## WARNING: Missing Instrumentation

**No frontend events.** There's no tracking of which steps users reach, where they stop, or how long they spend reviewing results. The only signal is a completed job — there's no way to distinguish "processed and immediately left" from "processed and spent 20 minutes reviewing."

**No error rate tracking.** `error_count` on job records captures extraction errors, but API-level failures (400, 500 responses) aren't aggregated anywhere.

**No session duration.** Time spent per tool is completely unknown.

To add structured event tracking, see the **instrumenting-product-metrics** skill.
To use Firestore for event storage, see the **firestore** skill.

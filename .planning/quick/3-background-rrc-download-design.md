# Background RRC Download with Firestore Job Tracking

## Problem

RRC oil CSV download takes 5-15+ minutes and times out. Currently the endpoint blocks synchronously, causing failures. Users want to start the download, leave the page (or close the browser), and come back to find data ready.

## Approach

Firestore Job + Background Thread + Polling (Approach A).

## Design

### 1. Firestore Job Document (`rrc_sync_jobs` collection)

```json
{
  "id": "rrc-sync-2026-03-04T...",
  "status": "downloading_oil | downloading_gas | syncing_oil | syncing_gas | complete | failed",
  "started_at": "ISO timestamp",
  "completed_at": "ISO timestamp | null",
  "oil_rows": 0,
  "gas_rows": 0,
  "error": "null | error message",
  "steps": [
    { "step": "downloading_oil", "started_at": "...", "completed_at": "...", "message": "Downloaded 45,000 rows" },
    { "step": "downloading_gas", "started_at": "...", "completed_at": "...", "message": "Downloaded 138,985 rows" },
    { "step": "syncing_oil", "started_at": "...", "completed_at": "...", "message": "Synced 45,000 records" },
    { "step": "syncing_gas", "started_at": "...", "completed_at": "...", "message": "Synced 138,985 records" }
  ]
}
```

### 2. Backend API Changes (backend/app/api/proration.py)

**Modify:** `POST /api/proration/rrc/download`
- Keep existing monthly guard (returns immediately if already synced this month)
- Instead of blocking, create Firestore job doc and spawn `threading.Thread`
- Return immediately: `{ job_id, status: "downloading_oil" }`

**Add:** `GET /api/proration/rrc/download/{job_id}/status`
- Return current job doc from Firestore
- Frontend polls every 3-5 seconds

**Add:** `GET /api/proration/rrc/download/active`
- Return most recent job that is active OR completed within last 5 minutes
- Used on page load to detect running jobs

### 3. Background Worker (in rrc_data_service.py or new file)

Use `threading.Thread` (not asyncio — download methods are synchronous `requests` calls).

Sequence:
1. Update job status → `downloading_oil` → call `download_oil_data()` → update with row count
2. Update job status → `downloading_gas` → call `download_gas_data()` → update with row count
3. Update job status → `syncing_oil` → sync oil to Firestore → update
4. Update job status → `syncing_gas` → sync gas to Firestore → update
5. Update job status → `complete` with final stats

On failure: update job → `failed` with error. Partial success tracked (e.g., gas OK, oil failed).

**Important:** The thread needs its own Firestore client for synchronous writes (can't use async from thread). Use `google.cloud.firestore.Client` directly, not the async wrappers.

### 4. Firestore Helper Functions (backend/app/services/firestore_service.py)

Add synchronous Firestore helpers for the background thread:
- `create_rrc_sync_job() -> str` — create job doc, return ID
- `update_rrc_sync_job(job_id, updates)` — update status/steps
- `get_rrc_sync_job(job_id) -> dict` — read job (async, for API)
- `get_active_rrc_sync_job() -> dict | None` — find active/recent job (async, for API)

### 5. Frontend Changes (frontend/src/pages/Proration.tsx)

- On page load: call `GET /rrc/download/active` to check for running jobs
- If active job found → start polling `GET /rrc/download/{job_id}/status` every 3s
- "Sync RRC Data" button → `POST /rrc/download` → get job_id → start polling
- Show step-by-step progress in the existing RRC status card area:
  - Spinner + current step label ("Downloading oil data...", "Syncing gas data...")
  - When complete: refresh RRC status, show success message
  - When failed: show error with retry button
- Disable "Sync" button while job is active

### 6. Cloud Run Timeout

The download now runs in a background thread, but the thread still lives on the Cloud Run instance. The instance needs to stay alive. Current Cloud Run config has `min-instances: 0`, meaning the instance could scale down.

Options:
- The polling requests from the frontend keep the instance alive (every 3-5s)
- If concerned, set `min-instances: 1` during sync (costs ~$10/month)
- For now, rely on polling to keep instance warm — simplest approach

### Files to Create/Modify

| File | Action | What |
|------|--------|------|
| `backend/app/services/rrc_background.py` | CREATE | Background worker thread + Firestore job management |
| `backend/app/api/proration.py` | MODIFY | Change download endpoint to async, add status/active endpoints |
| `backend/app/services/firestore_service.py` | MODIFY | Add sync Firestore helpers for rrc_sync_jobs |
| `frontend/src/pages/Proration.tsx` | MODIFY | Add polling, progress display, active job detection |
| `.github/workflows/deploy.yml` | MODIFY | Increase Cloud Run timeout to 1200s |

### Testing

- Start download → verify immediate response with job_id
- Poll status → verify steps update in sequence
- Navigate away → come back → verify active job detected
- Close browser → reopen → verify completed job shown
- Force timeout in oil download → verify partial failure tracked

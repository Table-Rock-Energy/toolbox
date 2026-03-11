---
phase: quick-4
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/app/services/rrc_background.py
  - backend/app/services/firestore_service.py
  - backend/app/api/proration.py
  - backend/app/models/proration.py
  - frontend/src/pages/Proration.tsx
autonomous: true
requirements: [QUICK-4]
must_haves:
  truths:
    - "RRC download starts immediately and returns a job_id without blocking"
    - "User sees step-by-step progress (downloading oil, downloading gas, syncing oil, syncing gas, complete)"
    - "User can navigate away and return to see active/completed job progress"
    - "Failed downloads show error with ability to retry"
    - "Sync button is disabled while a job is active"
  artifacts:
    - path: "backend/app/services/rrc_background.py"
      provides: "Background worker thread + Firestore job CRUD"
    - path: "backend/app/api/proration.py"
      provides: "Async download endpoint + status/active polling endpoints"
    - path: "frontend/src/pages/Proration.tsx"
      provides: "Polling UI with step progress display"
  key_links:
    - from: "frontend/src/pages/Proration.tsx"
      to: "/api/proration/rrc/download"
      via: "POST returns job_id, then polls status"
      pattern: "rrc/download.*job_id"
    - from: "backend/app/services/rrc_background.py"
      to: "rrc_sync_jobs collection"
      via: "Sync Firestore Client writes from background thread"
      pattern: "firestore\\.Client"
    - from: "backend/app/api/proration.py"
      to: "backend/app/services/rrc_background.py"
      via: "start_rrc_background_download"
      pattern: "start_rrc_background_download"
---

<objective>
Implement background RRC data download with Firestore job tracking and frontend polling progress display.

Purpose: RRC oil CSV download takes 5-15+ minutes and times out. This converts the blocking download to a background thread with Firestore-persisted job status so users can start the download, leave, and come back to find data ready.

Output: Non-blocking RRC download with real-time step progress in the Proration UI.
</objective>

<execution_context>
@.planning/quick/3-background-rrc-download-design.md
</execution_context>

<context>
@backend/app/services/proration/rrc_data_service.py (existing download methods: download_oil_data, download_gas_data, download_all_data, sync_to_database)
@backend/app/api/proration.py (existing download endpoint to modify)
@backend/app/services/firestore_service.py (existing Firestore helpers, add sync helpers for rrc_sync_jobs)
@backend/app/models/proration.py (RRCDownloadResponse model to extend)
@frontend/src/pages/Proration.tsx (existing RRC status banner and download handler)

<interfaces>
From backend/app/services/proration/rrc_data_service.py:
```python
class RRCDataService:
    def download_oil_data(self) -> tuple[bool, str, int]:  # (success, message, row_count)
    def download_gas_data(self) -> tuple[bool, str, int]:
    def download_all_data(self) -> tuple[bool, str, dict]:  # dict has oil_rows, gas_rows
    async def sync_to_database(self, data_type: str) -> dict:  # {"success": bool, "message": str}

rrc_data_service = RRCDataService()  # singleton
```

From backend/app/services/firestore_service.py:
```python
def get_firestore_client() -> AsyncClient:  # lazy init async client
RRC_SYNC_COLLECTION = "rrc_data_syncs"
```

From backend/app/models/proration.py:
```python
class RRCDownloadResponse(BaseModel):
    success: bool
    message: str
    oil_rows: int = 0
    gas_rows: int = 0
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Backend -- Background worker + Firestore job helpers + API endpoints</name>
  <files>
    backend/app/services/rrc_background.py
    backend/app/services/firestore_service.py
    backend/app/api/proration.py
    backend/app/models/proration.py
  </files>
  <action>
**1. CREATE `backend/app/services/rrc_background.py`** -- Background worker + sync Firestore job management.

This module uses `threading.Thread` because the RRC download methods are synchronous `requests` calls. The thread needs its own **synchronous** Firestore client (`google.cloud.firestore.Client`, NOT the async one) since it runs outside the asyncio event loop.

Constants:
- `RRC_SYNC_JOBS_COLLECTION = "rrc_sync_jobs"`

Functions (all synchronous, for use in background thread):
- `_get_sync_firestore_client() -> firestore.Client` -- Lazy-init a synchronous `google.cloud.firestore.Client` (separate from the async one in firestore_service.py). Use `settings.gcs_project_id` and database `"tablerocktools"`.
- `create_rrc_sync_job() -> str` -- Create job doc in `rrc_sync_jobs` with fields per design doc (id as `rrc-sync-{ISO timestamp}`, status `"downloading_oil"`, started_at, completed_at=None, oil_rows=0, gas_rows=0, error=None, steps=[]). Return job ID.
- `update_rrc_sync_job(job_id: str, updates: dict)` -- Merge updates into job doc.
- `add_step(job_id: str, step_name: str, message: str | None = None)` -- Append a step dict `{step, started_at, completed_at, message}` to the steps array. When `message` is provided, it means the step completed (set `completed_at`). When `message` is None, it means the step just started (no `completed_at`).
- `_run_rrc_download(job_id: str)` -- The actual worker function that runs in the thread:
  1. Update status `"downloading_oil"`, add_step started
  2. Call `rrc_data_service.download_oil_data()` -> (success, message, row_count)
  3. If success: update oil_rows, complete the step with message. If fail: set status `"failed"`, set error, return.
  4. Update status `"downloading_gas"`, add_step started
  5. Call `rrc_data_service.download_gas_data()` -> same pattern
  6. Update status `"syncing_oil"`, add_step started
  7. Run sync_to_database for oil -- **Important**: `sync_to_database` is async. From the background thread, use `asyncio.run()` to call it: `asyncio.run(rrc_data_service.sync_to_database("oil"))`.
  8. Complete step, update status `"syncing_gas"`, add_step started
  9. Run sync_to_database for gas similarly
  10. Update status `"complete"`, set completed_at
  11. Wrap entire function in try/except -- on any exception, set status `"failed"` with error message.
- `start_rrc_background_download() -> str` -- Create job, spawn `threading.Thread(target=_run_rrc_download, args=(job_id,), daemon=True)`, start it, return job_id.

Functions (async, for use in API endpoints):
- `get_rrc_sync_job(job_id: str) -> dict | None` -- Use the **async** Firestore client from `firestore_service.get_firestore_client()` to read job doc.
- `get_active_rrc_sync_job() -> dict | None` -- Query `rrc_sync_jobs` for jobs where status is NOT `"complete"` and NOT `"failed"`, OR status is `"complete"` and `completed_at` is within the last 5 minutes. Return most recent. Use async client. For the "completed within 5 minutes" check, query for status `"complete"` with `completed_at` >= `datetime.utcnow() - timedelta(minutes=5)`, then also query for any non-terminal status. Return the most recent of either.

**2. MODIFY `backend/app/services/firestore_service.py`** -- No changes needed. The sync Firestore client lives in rrc_background.py to keep concerns separate.

**3. MODIFY `backend/app/models/proration.py`** -- Add a new response model:
```python
class RRCBackgroundDownloadResponse(BaseModel):
    """Response from starting a background RRC download."""
    job_id: str = Field(..., description="Background job ID for polling")
    status: str = Field(..., description="Initial job status")
    message: str = Field("Download started", description="Status message")
```

**4. MODIFY `backend/app/api/proration.py`** -- Change download endpoint and add 2 new endpoints:

- `POST /rrc/download` -- Keep the existing monthly guard logic (lines 63-80 that check last sync and return early). After the guard, instead of blocking on `rrc_data_service.download_all_data()`, call `start_rrc_background_download()` and return `RRCBackgroundDownloadResponse(job_id=job_id, status="downloading_oil")`. Change return type to `RRCBackgroundDownloadResponse | RRCDownloadResponse` (use `Union` or just return dict). Import `start_rrc_background_download` from `app.services.rrc_background`.

- `GET /rrc/download/{job_id}/status` -- New endpoint. Call `get_rrc_sync_job(job_id)`. Return the job dict. If not found, raise HTTPException 404.

- `GET /rrc/download/active` -- New endpoint. Call `get_active_rrc_sync_job()`. Return the job dict, or `{"job": null}` if none found.

Keep the existing `/rrc/download/oil`, `/rrc/download/gas`, and `/rrc/sync` endpoints unchanged (they are standalone utilities).
  </action>
  <verify>
    <automated>cd /Users/ventinco/Documents/Projects/Table Rock TX/Tools/toolbox && python3 -c "from app.services.rrc_background import start_rrc_background_download, get_rrc_sync_job, get_active_rrc_sync_job; from app.models.proration import RRCBackgroundDownloadResponse; print('All imports OK')"</automated>
  </verify>
  <done>
    - POST /rrc/download returns immediately with job_id instead of blocking
    - GET /rrc/download/{job_id}/status returns job progress from Firestore
    - GET /rrc/download/active returns most recent active or recently completed job
    - Background thread runs download + sync sequence with step tracking
    - Monthly guard still prevents redundant downloads
  </done>
</task>

<task type="auto">
  <name>Task 2: Frontend -- Polling progress display and active job detection</name>
  <files>frontend/src/pages/Proration.tsx</files>
  <action>
Modify `Proration.tsx` to replace the blocking download UX with polling-based progress.

**New interface:**
```typescript
interface RRCSyncJob {
  id: string
  status: 'downloading_oil' | 'downloading_gas' | 'syncing_oil' | 'syncing_gas' | 'complete' | 'failed'
  started_at: string
  completed_at: string | null
  oil_rows: number
  gas_rows: number
  error: string | null
  steps: Array<{
    step: string
    started_at: string
    completed_at: string | null
    message: string | null
  }>
}
```

**New state variables** (add near existing RRC state around line 142):
```typescript
const [rrcSyncJob, setRrcSyncJob] = useState<RRCSyncJob | null>(null)
const rrcPollRef = useRef<ReturnType<typeof setInterval> | null>(null)
```

**On page load -- check for active job** (add a new useEffect):
- Call `GET ${API_BASE}/proration/rrc/download/active`
- If response has a job (not null), set `rrcSyncJob` and start polling if status is not terminal (complete/failed)
- If status is `complete` and within 5 min, show the completed state briefly

**Polling logic** (new helper functions):
- `startPolling(jobId: string)` -- Set interval at 3 seconds calling `GET ${API_BASE}/proration/rrc/download/${jobId}/status`. On each response:
  - Update `rrcSyncJob` state
  - If status is `complete`: stop polling, call `checkRRCStatus()` to refresh data counts, set `rrcMessage` with success info, clear `isDownloadingRRC`
  - If status is `failed`: stop polling, set `error` with the job's error message, clear `isDownloadingRRC`
- `stopPolling()` -- Clear the interval ref
- Clean up polling on unmount via useEffect return

**Modify `handleDownloadRRC`:**
- Keep the fetch to `POST ${API_BASE}/proration/rrc/download`
- Check response: if it has `job_id` field (background response), set `rrcSyncJob` with initial state and call `startPolling(job_id)`. Keep `isDownloadingRRC` true.
- If it has `success` and `message` but no `job_id` (monthly guard early return), handle as before (show message, not downloading).

**Modify RRC status banner UI** (the section starting around line 578):
When `isDownloadingRRC` is true and `rrcSyncJob` is set, replace the simple "Syncing..." button text with a progress display inside the banner:

In the action-needed banner (yellow/orange), replace the button area with progress when downloading:
```
- Show current step label with spinner:
  - "downloading_oil" -> "Downloading oil data..."
  - "downloading_gas" -> "Downloading gas data..."
  - "syncing_oil" -> "Syncing oil to database..."
  - "syncing_gas" -> "Syncing gas to database..."
- Show completed steps with checkmarks and their messages (e.g., "Downloaded 45,000 rows")
- Show elapsed time from started_at
```

Also show progress in the compact green banner area (line 585) when a job is active -- override the green banner to show progress instead.

When job completes, transition back to the green "data loaded" banner with updated counts.

When job fails, show error in red with a "Retry" button that calls handleDownloadRRC again.

**Disable the "Sync RRC Data" / "Download & Build" button** while `rrcSyncJob` has a non-terminal status.

**Step label helper:**
```typescript
const STEP_LABELS: Record<string, string> = {
  downloading_oil: 'Downloading oil data...',
  downloading_gas: 'Downloading gas data...',
  syncing_oil: 'Syncing oil to database...',
  syncing_gas: 'Syncing gas to database...',
}
```

Use Tailwind classes consistent with existing patterns: `animate-spin` for spinners, `text-tre-teal` for active states, green for completed steps, red for failures.
  </action>
  <verify>
    <automated>cd /Users/ventinco/Documents/Projects/Table Rock TX/Tools/toolbox/frontend && npx tsc --noEmit 2>&1 | head -30</automated>
  </verify>
  <done>
    - Page load detects active RRC download jobs and resumes polling
    - "Sync RRC Data" button starts background download and shows step-by-step progress
    - Completed steps show checkmarks with row count messages
    - Active step shows spinner with label
    - Failed jobs show error with retry capability
    - Button is disabled during active downloads
    - Navigating away and back resumes progress display
  </done>
</task>

</tasks>

<verification>
1. Backend imports verify: `python3 -c "from app.services.rrc_background import start_rrc_background_download"`
2. Frontend TypeScript compiles: `cd frontend && npx tsc --noEmit`
3. Manual: Start dev servers (`make dev`), go to Proration page, click "Sync RRC Data", verify:
   - Immediate response (no blocking)
   - Step progress updates every 3 seconds
   - Navigate away and back -- progress resumes
   - On complete, RRC status refreshes with new counts
</verification>

<success_criteria>
- RRC download no longer blocks the HTTP response (returns in < 1 second)
- Background thread runs the 4-step download+sync sequence
- Frontend polls and displays real-time step progress
- Active jobs are detected on page load
- Failed jobs display error with retry option
- Monthly guard still prevents redundant downloads
- TypeScript compiles without errors
</success_criteria>

<output>
After completion, create `.planning/quick/4-implement-background-rrc-download/4-SUMMARY.md`
</output>

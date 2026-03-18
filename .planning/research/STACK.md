# Technology Stack

**Project:** Table Rock Tools v1.6 - Pipeline Fixes & Unified Enrichment
**Researched:** 2026-03-18

## Verdict: No New Dependencies Required

Every capability needed for v1.6 is achievable with the existing stack. The features are architectural changes (combining existing pipeline steps, adding auth guards, fixing data flow), not new technology integrations.

## What Already Exists (DO NOT ADD)

| Technology | Already In | Used For |
|------------|-----------|----------|
| sse-starlette 2.0+ | requirements.txt | SSE streaming (GHL bulk send progress) |
| React 19 useState/useCallback | package.json | Local state management |
| FastAPI Depends(require_auth) | main.py | Router-level auth enforcement |
| FastAPI Depends(require_admin) | auth.py | Admin-only endpoint protection |
| Pydantic BaseModel | pipeline.py | ProposedChange, PipelineRequest, PipelineResponse |
| usePreviewState hook | hooks/ | Entry state, edits, exclusions |
| useSSEProgress hook | hooks/ | SSE event consumption with reconnect |
| EnrichmentToolbar | components/ | 3-button enrichment UI (being replaced) |
| pipeline.py endpoints | api/ | /cleanup, /validate, /enrich returning PipelineResponse |

## Changes Per Feature

### 1. Unified Enrichment Modal

**Backend: New combined pipeline endpoint**

No new deps. Combine the three existing pipeline steps (`/cleanup`, `/validate`, `/enrich`) into a single SSE-streaming endpoint.

| What | How | Uses |
|------|-----|------|
| `POST /api/pipeline/run-all` | New endpoint, streams SSE events as each step completes | `sse-starlette` (already installed) |
| Step progress events | `EventSourceResponse` with `step`, `progress`, `total`, `changes_so_far` fields | `sse-starlette` + `asyncio` |
| Per-step proposed changes | Stream `ProposedChange` batches after each step finishes | Existing `PipelineResponse` model |
| ETA calculation | Track elapsed time per step, extrapolate remaining | Python `time.monotonic()` (stdlib) |

**Frontend: Modal component + progress hook**

No new deps. Build with existing React primitives.

| What | How | Uses |
|------|-----|------|
| `EnrichmentModal.tsx` | Modal overlay with 3-step progress bar | Existing `Modal.tsx` pattern |
| Step indicator | Three labeled stages (Clean Up -> Validate -> Enrich) with active/complete/pending states | Tailwind CSS classes |
| Progress bar with ETA | `width` percentage + "~Xs remaining" text | `useState` + `Date.now()` arithmetic |
| Live preview updates | Apply `ProposedChange` batches to `usePreviewState.updateEntries()` as they stream in | Existing `usePreviewState` hook |
| Change highlighting | CSS transition on cells that received proposed changes, fade after 3s | Tailwind `transition-colors` + `setTimeout` |
| SSE consumption | Adapt `useSSEProgress` pattern for pipeline events (or inline EventSource in modal) | Native `EventSource` API |

**Key design decision:** Use SSE (not polling) because `sse-starlette` is already proven in the GHL flow and keeps the pattern consistent. The `/run-all` endpoint yields events as each step completes, so the frontend can update the preview table incrementally.

**Why NOT WebSockets:** SSE is simpler, unidirectional (server->client only, which is all we need), already works through the Vite proxy, and matches the GHL pattern. No reason to introduce `websockets` or `socket.io`.

### 2. RRC Fetch-Missing Fixes

**No new deps.** All fixes are logic changes in existing code.

| Fix | File | Change |
|-----|------|--------|
| Compound lease splitting | `api/proration.py` | Split "12345/12346" into separate lookups before Firestore query |
| Direct data use | `api/proration.py` | When RRC query returns data, apply it to the row immediately instead of requiring a second lookup |
| Per-row status feedback | `models/proration.py` | `fetch_status` field already exists on row model; ensure it's set to "found"/"not_found"/"error" for every row |

**Existing tools used:** `pandas` for DataFrame operations, `beautifulsoup4` for HTML scraping, `requests` for RRC HTTP calls.

### 3. Admin/History Auth Hardening

**No new deps.** Pure routing configuration changes.

| Fix | File | Change |
|-----|------|--------|
| Admin router auth | `main.py` | Add `dependencies=[Depends(require_auth)]` to admin router include. Currently missing -- all admin GET endpoints (settings, users list, options, preferences, profile images) are unprotected. |
| Admin read endpoints need auth | `api/admin.py` | GET `/users`, `/settings/*`, `/preferences/*`, `/options` currently have no auth dependency. Router-level auth from main.py fixes all of them. |
| `check_user` exception | `api/admin.py` | The `/users/{email}/check` endpoint must remain unauthenticated (used during login flow). Move it to a separate mini-router or add explicit auth skip. |
| History user-scoping | `api/history.py` | Add `user: dict = Depends(require_auth)` to `get_jobs()`, filter by `user["email"]` unless user is admin. History router already has router-level auth via main.py. |
| History delete needs admin | `api/history.py` | Add `Depends(require_admin)` to `delete_job()` -- currently any authenticated user can delete any job. |

**Existing tools used:** `require_auth`, `require_admin` from `app.core.auth`, `Depends` from FastAPI.

### 4. GHL smart_list_name Cleanup

**No new deps.** Field removal across models and API.

| Fix | File | Change |
|-----|------|--------|
| Remove from model | `models/ghl.py` | Delete `smart_list_name` field |
| Remove from API client | `api/ghl.py` | Remove references in send/bulk endpoints |
| Remove from frontend | `utils/api.ts` + `GhlSendModal.tsx` | Remove field from request types and UI |

## What NOT to Add

| Temptation | Why Not |
|------------|---------|
| `zustand` or `jotai` for state | `usePreviewState` hook handles everything; adding a state library for one modal is overkill |
| `react-query` / `tanstack-query` | Pipeline is a one-shot operation, not cached data fetching; `useEffect` + `EventSource` is sufficient |
| `framer-motion` for change highlighting | CSS `transition-colors` with Tailwind does the job; 45KB bundle addition not justified |
| `socket.io` / `ws` for WebSockets | SSE already works, is simpler, and matches existing GHL pattern |
| `celery` / `dramatiq` for background tasks | Pipeline steps run sequentially in <30s total; no need for a task queue |
| New progress tracking library | `Date.now()` arithmetic for ETA is ~5 lines of code |
| `redis` for step state | Steps run in a single SSE stream; no distributed state needed |

## SSE Event Schema for Unified Pipeline

```typescript
// Frontend types (no library needed)
interface PipelineSSEEvent {
  type: 'step_start' | 'step_progress' | 'step_complete' | 'pipeline_complete' | 'error'
  step?: 'cleanup' | 'validate' | 'enrich'
  step_index?: number           // 0, 1, 2
  entries_processed?: number
  entries_total?: number
  proposed_changes?: ProposedChange[]  // Batch of changes from completed step
  elapsed_ms?: number
  estimated_remaining_ms?: number
  error?: string
}
```

```python
# Backend (uses existing sse-starlette)
from sse_starlette.sse import EventSourceResponse

async def pipeline_run_all(request: PipelineRequest):
    async def event_generator():
        for step_index, step_fn in enumerate([cleanup, validate, enrich]):
            yield {"event": "step_start", "data": json.dumps({...})}
            result = await step_fn(request)
            yield {"event": "step_complete", "data": json.dumps({...})}
        yield {"event": "pipeline_complete", "data": json.dumps({...})}

    return EventSourceResponse(event_generator())
```

## Installation

No changes to `package.json` or `requirements.txt` needed.

```bash
# Nothing to install -- all deps already present
make install  # if starting fresh
```

## Confidence Assessment

| Claim | Confidence | Basis |
|-------|------------|-------|
| sse-starlette supports this pattern | HIGH | Already working in GHL bulk send; same EventSourceResponse pattern |
| No new frontend deps needed | HIGH | Existing React 19 primitives + Tailwind cover modal, progress, highlighting |
| Admin router lacks auth | HIGH | Verified in main.py line 80: no `dependencies=` on admin router include |
| History lacks user-scoping | HIGH | Verified in history.py: no user filter on `get_jobs()` query |
| CSS transitions sufficient for highlighting | MEDIUM | Standard pattern, but may need testing for table row re-renders |
| Pipeline runs under 30s | MEDIUM | Depends on entry count and external API latency (Google Maps, PDL) |

## Sources

- Codebase: `main.py` line 80 -- admin router has no auth dependencies
- Codebase: `history.py` -- no user filtering on job queries
- Codebase: `pipeline.py` -- existing /cleanup, /validate, /enrich endpoints
- Codebase: `useSSEProgress.ts` -- proven SSE consumption pattern
- Codebase: `usePreviewState.ts` -- `updateEntries()` supports live replacement
- Codebase: `requirements.txt` -- `sse-starlette>=2.0` already installed
- Codebase: `package.json` -- no additional frontend deps needed

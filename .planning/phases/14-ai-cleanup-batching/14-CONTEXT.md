# Phase 14: AI Cleanup Batching - Context

**Gathered:** 2026-03-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Configurable batch sizes, concurrent batch execution, auto-retry of failed batches, and backend disconnect detection for AI cleanup operations. Builds on Phase 13's batch engine foundation — this phase makes it tunable, concurrent, resilient, and server-aware of client disconnects.

Requirements: BATCH-03, BATCH-04, RESIL-02, RESIL-04

</domain>

<decisions>
## Implementation Decisions

### Batch Size Configuration
- Single global batch size (all tools use same value) — no per-tool override needed
- Config lives under existing Google Cloud section in admin UI as "AI Cleanup" subsection with batch size control
- Stored in `batch_config` key in existing app_settings.json — same encrypt/persist flow as other settings
- Frontend fetches batch size from `/api/admin/settings` response; falls back to 25 if not configured

### Concurrency & Retry Strategy
- 2 concurrent batches (respects Gemini free-tier 10 RPM while leaving headroom) — configurable alongside batch size
- Retry failed batches once at end of step (collect failures, re-run after all batches complete) — avoids mid-stream complexity
- `max_retries` stored in same `batch_config` in app_settings (default: 1)
- After retry exhausted, return partial results with count of still-failed entries — same skip-and-continue as Phase 13

### Backend Disconnect Detection
- Check `request.is_disconnected()` in `/api/pipeline/cleanup` endpoint between internal Gemini batches
- Add `request: Request` parameter to pipeline endpoints — FastAPI injects automatically
- On disconnect: log warning + return early with partial results (no error response since client is gone)
- Granularity: check before each internal Gemini batch call

### Claude's Discretion
- Concurrency implementation details (asyncio.Semaphore vs Promise.allSettled on frontend)
- Whether concurrency is frontend-side (parallel fetch calls) or backend-side (parallel Gemini calls) or both
- Retry batch collection data structure and re-dispatch mechanism
- Admin UI layout for batch config controls (slider vs number input)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `OperationContext.tsx` — Batch engine with BATCH_SIZE=25, progressive apply, skip-and-continue. Needs concurrency + retry additions
- `gemini_provider.py` — `cleanup_entries()` already batches internally with BATCH_SIZE and BATCH_DELAY_SECONDS
- `gemini_service.py` — Rate limiting infrastructure (_check_rate_limit, _record_request, MAX_RPM=10, BATCH_SIZE=25, BATCH_DELAY_SECONDS=6)
- `admin.py` — app_settings load/save/encrypt/persist flow, `_apply_settings_to_runtime()` for runtime config injection
- `AdminSettings.tsx` — Google Cloud settings card with API key, model, budget controls — extend with batch config

### Established Patterns
- app_settings.json → Firestore sync with encryption for sensitive fields
- Frontend fetches settings via admin API, applies locally
- Backend batches Gemini calls in asyncio.to_thread with BATCH_DELAY_SECONDS between calls
- OperationContext uses local variable threading (not React state) to avoid stale closures in async loops

### Integration Points
- `OperationContext.tsx` line 6: `const BATCH_SIZE = 25` — replace with dynamic value from settings
- `gemini_service.py` line 27: `BATCH_SIZE = 25` — make configurable via runtime settings
- `pipeline.py` endpoints: Add `request: Request` parameter for disconnect detection
- `AdminSettings.tsx`: Add batch config controls to Google Cloud section

</code_context>

<specifics>
## Specific Ideas

No specific requirements — decisions align with recommended approaches throughout. The existing batch engine needs concurrency (parallel fetches), retry (end-of-step re-run), and the backend needs disconnect awareness.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 14-ai-cleanup-batching*
*Context gathered: 2026-03-19*

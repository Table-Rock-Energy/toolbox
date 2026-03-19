# Domain Pitfalls: Batch Processing & Resilience (v1.7)

**Domain:** Adding batch processing, streaming, operation persistence, and cancellation to existing FastAPI + React app
**Researched:** 2026-03-19
**Context:** Table Rock Tools -- current pain points are AI cleanup timeouts on 200+ entries, sequential Firestore lookups in proration, navigation destroying state, no backend abort propagation, and blocking multi-PDF Gemini calls in revenue upload

## Critical Pitfalls

Mistakes that cause rewrites or major issues.

### Pitfall 1: Client-Side Batching Without Backend Awareness

**What goes wrong:** Frontend splits 200 entries into 8 batches of 25 and fires them sequentially at `/pipeline/cleanup`. Backend has no concept of these being related. If user cancels after batch 3, backend still processes batch 4 (already in-flight). Rate limiter in `gemini_service.py` (10 RPM, 250 RPD) gets confused because each batch looks independent.

**Why it happens:** Easiest implementation is to loop `fetch()` calls on the client. It works for small datasets but breaks at scale because the backend and frontend have no shared concept of a "job."

**Consequences:** Wasted Gemini quota on cancelled work. Rate limit state (`_rpm_timestamps`, `_daily_count`) drifts. No way to resume a partially-complete batch set after a page refresh.

**Prevention:** Two viable approaches, pick one:
- **Option A (simpler):** Keep client-side orchestration but add `AbortSignal` propagation to backend via a cancellation token. Backend checks token before each Gemini call. Already have `abortControllerRef` in `useEnrichmentPipeline.ts` -- extend it to pass a job ID that backend respects.
- **Option B (more resilient):** Backend accepts full entry set, manages batching internally, streams progress via SSE. More work but survives page navigation. Use the existing `sse_starlette.EventSourceResponse` pattern from `ghl.py`.

**Detection:** Users report "Cancel didn't stop it" or Gemini budget burns faster than expected after cancellations.

**Phase relevance:** Must decide architecture (A vs B) in Phase 1 before any batch work begins. Everything else builds on this choice.

### Pitfall 2: SSE Connection Lifecycle Mismanagement

**What goes wrong:** EventSource connections are opened but never properly closed. Component unmounts, user navigates away, or browser tab goes to sleep -- the SSE endpoint keeps streaming into void. On Cloud Run (1Gi memory, 0-10 instances), orphaned SSE handlers pin instances alive, preventing scale-to-zero.

**Why it happens:** Existing `useSSEProgress.ts` handles this for GHL send (one job at a time), but batch processing may need multiple concurrent SSE streams or long-running single streams. The cleanup logic doesn't generalize.

**Consequences:** Cloud Run instances stay alive billing compute. Memory leaks from accumulating event generators. Firestore reads continue for jobs nobody is watching.

**Prevention:**
- Server-side: Use `request.is_disconnected()` check in FastAPI's async generator (Starlette exposes this). Poll it every iteration of the batch loop.
- Client-side: Always close EventSource in `useEffect` cleanup. Use a single generalized SSE hook, not per-feature copies.
- Cloud Run: Set `--session-affinity` if SSE reconnects need to hit the same instance. Without it, reconnects may hit a different instance that has no state for that job.

**Detection:** Cloud Run showing minimum 1 instance even with zero traffic. Memory growth in instance metrics.

### Pitfall 3: Navigation Destroys In-Flight Operations

**What goes wrong:** User starts AI cleanup on Extract page (200 entries, ~2 minutes), navigates to Proration, comes back -- all progress and results are gone. React component unmounted, state evaporated.

**Why it happens:** All tool state lives in component-local `useState`. There's no global store, no persistence layer, no background job tracking for pipeline operations. The `useEnrichmentPipeline` hook's entire state tree dies on unmount.

**Consequences:** Users learn to never navigate during operations. They stare at progress bars instead of multitasking. Lost work on accidental navigation (back button, link click).

**Prevention:**
- Store operation state outside components: either a React Context at the app level, or `zustand`/`jotai` store (but project constraint says "no Redux/Zustand" -- Context is the sanctioned path).
- Minimum viable: Store `{jobId, tool, status, partialResults}` in a global context. When component remounts, check for active job and reconnect SSE.
- Better: Backend-managed jobs (like existing RRC background download pattern in `rrc_background.py`) with Firestore persistence and polling.

**Detection:** User complaints about lost work. "I clicked Proration and my Extract cleanup results disappeared."

**Phase relevance:** This is the "operation persistence" feature. Must be designed before implementing any streaming/batch work, because the state shape dictates everything.

### Pitfall 4: Partial Results Lost on Failure

**What goes wrong:** Batch 6 of 8 fails (Gemini rate limit, network blip). Frontend `catch` block in `runAllSteps` discards all results from batches 1-5, shows error. User retries entire 200-entry set.

**Why it happens:** Current `runAllSteps` in `useEnrichmentPipeline.ts` does handle step-level partial failure (continues to next step), but within a step, a single failed API call loses all proposed changes from that call because `response.data?.success` is the only path to applying changes.

**Consequences:** Wasted Gemini budget re-processing entries that already succeeded. User frustration.

**Prevention:**
- Accumulate results across batches in a local array OUTSIDE the try/catch.
- On batch failure: log which entries failed, continue with next batch (or stop, but keep results so far).
- Return partial results to UI even on overall failure: `PipelineResponse` should have a `partial` flag.
- Backend: Return `success=True` with a `warnings` field when some sub-operations fail, rather than throwing.

**Detection:** Users report having to re-run cleanup multiple times to get full coverage.

## Moderate Pitfalls

### Pitfall 5: Proration Cache-First Lookup Ordering Bug

**What goes wrong:** Current proration checks Firestore before in-memory cache for each row (sequential). Fix seems obvious: check cache first, batch the misses. But the cache may be stale (data was updated in Firestore by background RRC sync) and cache-first silently returns old data.

**Prevention:**
- On startup, pre-warm cache from Firestore (or GCS CSV).
- Cache invalidation: When `start_rrc_background_download` completes, invalidate the in-memory cache. The existing `rrc_data_service` already loads CSVs into pandas DataFrames -- use those as primary cache, Firestore as persistence.
- Batch Firestore reads with `asyncio.gather()` for cache misses, but cap concurrency to avoid Firestore quota issues.

### Pitfall 6: AbortController Doesn't Abort Server Work

**What goes wrong:** Frontend `AbortController.abort()` cancels the `fetch()` request. Backend never knows. The Gemini API call continues to completion, burning quota and compute.

**Prevention:**
- FastAPI can detect client disconnect via `await request.is_disconnected()` in async endpoints.
- For streaming endpoints, the async generator naturally stops when the client disconnects (Starlette handles this).
- For non-streaming batch endpoints: check `request.is_disconnected()` between batches. Requires passing `Request` object into service layer or using a cancellation token pattern.
- Gemini calls themselves cannot be cancelled mid-request. Granularity is per-batch, not per-token.

### Pitfall 7: SSE Auth Token in Query String

**What goes wrong:** Existing GHL SSE passes auth token as query parameter (`?token=...`). This works but tokens appear in server access logs, browser history, and potentially proxy logs. Extending this pattern to more SSE endpoints multiplies the exposure surface.

**Prevention:**
- Accept that EventSource API doesn't support custom headers (this is a browser limitation, not fixable).
- Mitigation: Use short-lived, purpose-scoped tokens for SSE connections (not the full Firebase ID token). Generate a one-time SSE token on job creation, valid only for that job ID.
- Or: Use `fetch()` with `ReadableStream` instead of `EventSource` -- supports headers but loses automatic reconnection. For batch progress (finite duration), reconnection matters less.

### Pitfall 8: Streaming Response + Cloud Run Request Timeout

**What goes wrong:** Cloud Run has a 600s (10 min) request timeout configured for this service. An SSE stream for a 500-entry AI cleanup might take longer if rate-limited at 10 RPM. The connection dies mid-stream.

**Prevention:**
- Calculate worst-case: 500 entries / 25 per batch = 20 batches. At 6s delay between batches + processing time, ~3-4 minutes. Should fit.
- But: If Gemini rate limit backs off, delays grow. Build in timeout awareness -- if approaching 500s, flush partial results and close stream gracefully.
- Alternative: Client-side orchestration (Option A from Pitfall 1) avoids this because each batch is a separate short-lived request.

### Pitfall 9: Revenue Multi-PDF Upload Blocks UI

**What goes wrong:** Revenue upload accepts multiple PDFs. Currently processes sequentially, blocking the entire request. Adding per-PDF progress streaming is good, but if Gemini fallback parser is used, each PDF adds 10-30s of Gemini latency.

**Prevention:**
- Process PDFs concurrently with `asyncio.gather()` but cap concurrency (semaphore of 3) to avoid Gemini rate limit.
- Stream per-PDF completion events, not per-entry. Users care about "3/7 PDFs done" not "processing line 42."
- If a PDF fails, continue with others and report partial results.

### Pitfall 10: Race Condition in Global Operation State

**What goes wrong:** User starts cleanup on Extract, navigates to Title, starts cleanup there. Two operations writing to the same global context. Results interleave or overwrite.

**Prevention:**
- Key operation state by tool name: `operations: { extract: {...}, title: {...} }`.
- Only allow one active operation per tool (disable Enrich button if that tool has an active operation).
- Allow concurrent operations across different tools (user can process Extract and Title simultaneously).

## Minor Pitfalls

### Pitfall 11: ETA Calculation Jitter

**What goes wrong:** ETA shows "2 minutes remaining" then jumps to "5 minutes" because Gemini response times are variable. Users lose trust in the progress indicator.

**Prevention:**
- Use exponential moving average for per-batch timing, not instantaneous rate.
- Don't show ETA until at least 2 batches complete (need baseline).
- Show "X of Y batches" alongside ETA -- concrete progress even if time estimate is wrong.

### Pitfall 12: Firestore Batch Read Size Limits

**What goes wrong:** `asyncio.gather()` for Firestore reads fires 200 concurrent `get()` calls. Firestore client may throttle or error with too many concurrent operations.

**Prevention:**
- Use Firestore `get_all()` (batch read) for up to 100 document references at once -- single RPC, much faster than individual gets.
- For larger sets, chunk into groups of 100 and `asyncio.gather()` the chunks.
- Existing code already batches writes at 500 (`firestore_service.py`) -- apply same discipline to reads.

### Pitfall 13: Memory Pressure from Pre-Warming Cache

**What goes wrong:** Pre-warming proration cache loads full RRC CSV into pandas DataFrame at startup. On Cloud Run cold start with 1Gi memory, this competes with other startup tasks.

**Prevention:**
- Load cache lazily on first proration request, not on app startup.
- Or: Load in background task after startup completes (don't block readiness probe).
- Monitor: The existing oil + gas CSVs are ~50-100MB in pandas. Should fit in 1Gi with room, but verify.

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Batch architecture decision | Pitfall 1: Client vs server orchestration | Decide in Phase 1, document as Key Decision |
| AI cleanup batching | Pitfall 4: Partial results lost | Accumulate results outside try/catch, return partial on failure |
| SSE streaming | Pitfall 2: Connection lifecycle | Use `request.is_disconnected()`, generalize SSE hook |
| SSE streaming | Pitfall 8: Cloud Run timeout | Calculate worst-case timing, graceful timeout handling |
| Cancel/abort | Pitfall 6: Server doesn't know about abort | Check `request.is_disconnected()` between batches |
| Operation persistence | Pitfall 3: Navigation destroys state | Global context or backend job tracking before any streaming work |
| Operation persistence | Pitfall 10: Multi-tool race condition | Key state by tool, one active operation per tool |
| Proration optimization | Pitfall 5: Stale cache | Invalidate on RRC sync completion, pre-warm lazily |
| Proration optimization | Pitfall 12: Firestore batch read limits | Use `get_all()` in chunks of 100 |
| Revenue streaming | Pitfall 9: Multi-PDF blocking | Concurrent with semaphore, per-PDF progress events |
| Progress UI | Pitfall 11: ETA jitter | Exponential moving average, show batch count alongside |

## Sources

- Codebase analysis: `useEnrichmentPipeline.ts`, `useSSEProgress.ts`, `pipeline.py`, `gemini_service.py`, `ghl.py`, `rrc_background.py`
- FastAPI `request.is_disconnected()`: Starlette ASGI disconnect detection (HIGH confidence, documented feature)
- Cloud Run SSE behavior: Cloud Run request timeout applies to streaming responses (HIGH confidence, GCP docs)
- EventSource header limitation: Browser API spec, no custom headers supported (HIGH confidence)
- Firestore `get_all()` batch reads: Firestore Python SDK supports multi-document reads (HIGH confidence)

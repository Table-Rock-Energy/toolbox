# Feature Landscape

**Domain:** Batch processing, streaming responses, operation persistence, and request cancellation for internal document-processing web app
**Researched:** 2026-03-19
**Milestone:** v1.7 Batch Processing & Resilience

## Table Stakes

Features users expect when long-running operations exist. Missing = lost work, timeouts, confusion.

| Feature | Why Expected | Complexity | Dependencies | Notes |
|---------|--------------|------------|--------------|-------|
| Batch progress with ETA | AI cleanup runs 25-entry batches with 6s delays; 200 entries = 48s+ with no feedback | Low | Existing `useEnrichmentPipeline` already has step indicators | Move batch loop to client, emit per-batch progress |
| Partial results on failure | Gemini rate limit or network error after batch 5/8 should keep those 5 batches of suggestions | Low | Existing `gemini_service.py` already returns partial on rate limit | Extend pattern to network errors; return accumulated results + error |
| Cancel in-flight operation | User starts 200-entry AI cleanup, realizes wrong data, has no way to stop | Med | `AbortController` already wired in `useEnrichmentPipeline` | Need backend cancellation propagation via `request.is_disconnected()` |
| Per-PDF progress for Revenue | Multi-PDF upload shows nothing until all PDFs finish; 10 PDFs = long wait | Med | Revenue endpoints already exist; need SSE or streaming JSON | Stream per-PDF results as they complete |
| Operation survives navigation | User starts enrichment, clicks Proration tab, comes back, results gone | Med | React Context above Router; no new deps | `OperationContext` provider wrapping `<Outlet />` in MainLayout |
| Proration batch Firestore reads | Per-row sequential Firestore lookups are O(n) round trips; 200 rows = 200 reads | Low | `firestore_service.get_in_batches` already exists with 100-doc chunking | Wire proration to use batch reads instead of per-row |

## Differentiators

Features that improve the experience beyond baseline expectations. Not blocking but high-value.

| Feature | Value Proposition | Complexity | Dependencies | Notes |
|---------|-------------------|------------|--------------|-------|
| Client-side batch orchestration | Client controls batch size/timing; can pause, resume, adjust; server stays stateless | Med | Requires new `useBatchProcessor` hook | Client sends batch N, waits for response, sends batch N+1; server processes one batch per request |
| Streaming batch responses (NDJSON) | Each batch result streams back as it completes rather than waiting for all | Med | FastAPI `StreamingResponse` already used for GHL SSE | Use NDJSON (`application/x-ndjson`) for non-SSE streaming; simpler than SSE for request/response |
| Proration cache pre-warming on startup | First proration query is slow because Firestore data isn't cached; pre-warm on app start | Low | FastAPI `lifespan` event | Load hot county data into memory on startup; ~5s for typical dataset |
| Global undo across navigation | Enrichment changes persist in context; undo works even after navigating away and back | Low | Depends on operation persistence context | Store `originalValues` map in context alongside results |
| Batch retry for failed items only | After partial failure, retry button re-sends only failed entries | Med | Requires tracking failed entry indices | UI shows "3/8 batches failed - Retry failed?" button |

## Anti-Features

Features to explicitly NOT build for v1.7.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| WebSocket connections | Overkill for unidirectional progress; adds connection management complexity; SSE already proven in codebase | Use SSE for server-push, NDJSON for streaming request/response |
| Server-side operation persistence (Firestore jobs) | Small internal team, operations complete in seconds-to-minutes, not hours; adds write cost and cleanup complexity | Client-side React Context persistence; operations re-run if browser closes |
| Celery/Redis task queue | No Redis in stack, single Cloud Run instance, operations are CPU-light (waiting on Gemini API); massive infra overhead for this use case | Direct async processing with `asyncio.to_thread` for blocking calls (already working) |
| Optimistic UI updates | Data accuracy is the core value; showing unverified results as "done" undermines trust | Show progress, then show verified results |
| Automatic retry with backoff | Gemini rate limits are real constraints, not transient errors; auto-retry burns budget and confuses users | Show failure clearly, let user decide to retry |
| IndexedDB/localStorage for operation state | Serialization complexity, storage limits, stale data on app updates; React Context is sufficient for in-session persistence | React Context with optional sessionStorage for crash recovery |
| Background Service Worker processing | Adds massive complexity; operations need auth tokens that expire; not supported well in all deployment contexts | Keep processing in main thread with async patterns |

## Feature Dependencies

```
Batch progress with ETA
  --> Client-side batch orchestration (orchestration enables progress)
  --> Partial results on failure (batch-level tracking enables partial returns)

Cancel in-flight operation
  --> Client-side batch orchestration (cancel between batches, not mid-batch)
  --> Backend disconnect detection (stop processing after current batch)

Operation survives navigation
  --> Global undo across navigation (undo requires persistent state)

Per-PDF progress for Revenue
  --> Streaming batch responses (same NDJSON pattern)

Proration batch Firestore reads
  (independent -- no dependencies, can ship first)

Proration cache pre-warming
  (independent -- no dependencies, can ship first)
```

## MVP Recommendation

**Ship first (low complexity, independent):**
1. Proration batch Firestore reads -- immediate perf win, `get_in_batches` already exists
2. Proration cache pre-warming -- startup hook, small code change
3. Partial results on failure -- extend existing Gemini pattern to all error types

**Ship second (table stakes, interdependent):**
4. Client-side batch orchestration hook (`useBatchProcessor`) -- foundation for progress + cancel
5. Batch progress with ETA -- uses the orchestration hook
6. Cancel in-flight operation -- abort between batches + backend disconnect check

**Ship third (UX polish):**
7. Operation persistence context -- wraps Router, stores results
8. Per-PDF Revenue progress -- streaming NDJSON response
9. Global undo across navigation -- extends operation context

**Defer:**
- Batch retry for failed items only: Nice-to-have, adds state complexity; manual re-run is acceptable for small team
- Streaming batch responses (NDJSON): Only needed if single-batch response times are still too slow after client orchestration

## Implementation Patterns

### Client-Side Batch Orchestration

The proven pattern for this stack: client sends batches sequentially, server processes one batch per request. This keeps the server stateless and gives the client full control over pacing, cancellation, and progress.

```
Client                          Server
  |-- POST /api/ai/cleanup ------>|  (batch 1: entries 0-24)
  |<-- 200 {suggestions: [...]} --|
  |  update progress (1/8)        |
  |-- POST /api/ai/cleanup ------>|  (batch 2: entries 25-49)
  |<-- 200 {suggestions: [...]} --|
  |  update progress (2/8)        |
  ...
```

Advantages: AbortController cancels between batches naturally. Partial results are automatic (completed batches are already in client state). No server-side job tracking needed. ETA calculated from observed batch duration.

### Backend Disconnect Detection

For streaming responses (Revenue per-PDF, any future SSE), FastAPI's `StreamingResponse` auto-raises `asyncio.CancelledError` on client disconnect. For regular endpoints during long processing, check `await request.is_disconnected()` between batches.

### Operation Persistence Context

React Context provider placed above the Router in MainLayout. Stores: tool name, operation type, status, results, original values (for undo). Cleared on explicit user action, not on navigation. Pattern already proven with `AuthContext`.

### Partial Results Response Shape

```json
{
  "success": true,
  "suggestions": [],
  "entries_reviewed": 125,
  "total_entries": 200,
  "batches_completed": 5,
  "batches_total": 8,
  "error_message": "Rate limited after 5 batches. Partial results returned.",
  "partial": true
}
```

Already ~80% implemented in `gemini_service.py` for rate limit case. Extend to catch `Exception` in batch loop and return accumulated results.

## Existing Code to Leverage

| Component/Pattern | Current State | v1.7 Role |
|-------------------|---------------|-----------|
| `useEnrichmentPipeline` | Runs steps sequentially with AbortController | Refactor: move batch loop to client, add per-batch progress callback |
| `useSSEProgress` | GHL-specific SSE hook with reconnect | Generalize for Revenue per-PDF progress |
| `gemini_service.py` batch loop | 25-entry batches with 6s delays, partial on rate limit | Move batching to client; server processes single batch per request |
| `firestore_service.get_in_batches` | 100-doc chunked reads, already async | Wire into proration lookup path |
| `rrc_county_download_service` | asyncio.gather with semaphore throttling | Pattern for concurrent Firestore reads |
| `StreamingResponse` in ghl.py | SSE for bulk send progress | Reuse for Revenue per-PDF streaming |
| `AuthContext` in MainLayout | Context above Router, persists across navigation | Template for `OperationContext` |

## Sources

- [FastAPI SSE Tutorial](https://fastapi.tiangolo.com/tutorial/server-sent-events/)
- [FastAPI Client Disconnect Detection](https://github.com/fastapi/fastapi/discussions/7572)
- [Stop Burning CPU on Dead FastAPI Streams](https://jasoncameron.dev/posts/fastapi-cancel-on-disconnect)
- [AbortController MDN](https://developer.mozilla.org/en-US/docs/Web/API/AbortController)
- [Partial Success Response Patterns](https://techdocs.akamai.com/test-ctr/reference/partial-success-responses)
- [React State Management 2025](https://www.developerway.com/posts/react-state-management-2025)
- [Bulk API Design Patterns](https://www.mscharhag.com/api-design/bulk-and-batch-operations)

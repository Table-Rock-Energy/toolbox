# Technology Stack: v1.7 Batch Processing & Resilience

**Project:** Table Rock Tools
**Researched:** 2026-03-19
**Scope:** New capabilities only -- batch orchestration, streaming, cancellation, operation persistence

## Executive Decision

**No new dependencies required.** The existing stack has every primitive needed. This milestone is about patterns, not packages.

## Existing Stack Already Covers v1.7

| Capability Needed | Already Have | Where Used |
|-------------------|-------------|------------|
| SSE streaming | `sse-starlette>=2.0` | GHL bulk send progress (`api/ghl.py`) |
| NDJSON streaming | `StreamingResponse` (FastAPI built-in) | Enrichment pipeline (`api/extract.py`, `api/title.py`) |
| Request cancellation (frontend) | `AbortController` | `useEnrichmentPipeline.ts`, `api.ts` timeout |
| Request cancellation (backend) | Firestore flag polling | GHL `cancel_job()` in `bulk_send_service.py` |
| Background jobs | `threading` + Firestore job docs | `rrc_background.py` with sync Firestore client |
| Job status tracking | Firestore collections | `rrc_sync_jobs` collection with polling endpoint |
| Async concurrency | `asyncio.gather`, `asyncio.Semaphore` | `rrc_county_download_service.py` (semaphore-throttled) |
| Progress events | Custom event protocol | Both SSE (GHL) and NDJSON (enrichment) patterns |

## What NOT to Add

| Temptation | Why Skip | Do This Instead |
|------------|---------|-----------------|
| Celery / Dramatiq / ARQ | Overkill for 1-10 users. Requires Redis/RabbitMQ. Cloud Run cold starts kill workers. | Client-side batch orchestration with NDJSON streaming |
| Redis | No shared state needed. Firestore persists jobs. 1Gi memory limit. | Firestore for persistence, in-memory dict for active state |
| WebSockets | `EventSource` is simpler, auto-reconnects, works through proxies. Already proven in GHL. | SSE via `sse-starlette` (already installed) |
| zustand / jotai | One global store for operation state is not worth a dep. | Module-level store with `useSyncExternalStore` |
| react-query / SWR | Data fetching is simple POST-and-display, not cache-invalidation-heavy. | Keep existing `ApiClient` + `useEffect` pattern |
| Server-side batch queue | Cloud Run scales to 0 -- no persistent process to poll. | Client drives batches, server processes one batch per request |
| framer-motion | CSS `transition-colors` handles cell highlighting. 45KB not justified. | Tailwind transitions |

## Implementation Patterns (Zero New Deps)

### Backend: Batch Streaming with Cancellation

Use `request.is_disconnected()` -- built into Starlette. When the client aborts the `fetch()`, the server detects disconnection and stops processing. No Firestore flag needed for streaming endpoints.

```python
async def process_batch_stream(request: Request, entries: list[dict]) -> AsyncGenerator[str, None]:
    for i in range(0, len(entries), BATCH_SIZE):
        if await request.is_disconnected():
            yield json.dumps({"type": "cancelled", "processed": i}) + "\n"
            return
        batch = entries[i:i + BATCH_SIZE]
        results = await process_batch(batch)
        yield json.dumps({"type": "progress", "processed": i + len(batch), "results": results}) + "\n"
```

**Confidence:** HIGH -- `request.is_disconnected()` is core Starlette API.

### Backend: Parallel Firestore Reads

Replace sequential lookups with `asyncio.gather`:

```python
# Before: sequential
for lease_id in lease_ids:
    doc = await firestore_service.get_document("rrc_data", lease_id)

# After: parallel
docs = await asyncio.gather(*[
    firestore_service.get_document("rrc_data", lid) for lid in lease_ids
])
```

**Confidence:** HIGH -- `asyncio.gather` is stdlib, Firestore async client supports concurrent reads.

### Backend: Proration Cache Pre-warming

Call existing RRC data load at startup instead of on first request:

```python
@app.on_event("startup")
async def startup():
    asyncio.create_task(warm_rrc_cache())

async def warm_rrc_cache():
    from app.services.proration.rrc_data_service import rrc_data_service
    await asyncio.to_thread(rrc_data_service.load_data)
```

**Confidence:** HIGH -- `asyncio.to_thread` is stdlib, startup hooks already used in `main.py`.

### Frontend: NDJSON Stream Consumption

Same pattern as existing enrichment pipeline. `ReadableStream` API reads chunked NDJSON:

```typescript
const reader = response.body!.getReader()
const decoder = new TextDecoder()
let buffer = ''
while (true) {
  const { done, value } = await reader.read()
  if (done) break
  buffer += decoder.decode(value, { stream: true })
  const lines = buffer.split('\n')
  buffer = lines.pop()!
  for (const line of lines) {
    if (line.trim()) onEvent(JSON.parse(line))
  }
}
```

**Confidence:** HIGH -- already proven in the enrichment hook.

### Frontend: Operation Persistence Across Navigation

Module-level singleton outside React tree. Survives route changes, cleared on explicit action.

```typescript
// operationStore.ts
const activeOperations = new Map<string, OperationState>()
const listeners = new Set<() => void>()

export function getOperation(id: string): OperationState | undefined { ... }
export function setOperation(id: string, state: OperationState): void { ... }
export function subscribe(listener: () => void): () => void { ... }

// In components: useSyncExternalStore(subscribe, () => getOperation(id))
```

`useSyncExternalStore` is the correct React 19 API for binding external mutable state to components. No Context provider needed, no re-render cascade, no new dependency.

**Confidence:** HIGH -- `useSyncExternalStore` is stable React API since React 18.

## Architecture Decision: Client-Driven vs Server-Driven Batching

**Decision: Client-driven batching for AI cleanup. Server-driven streaming for everything else.**

| Feature | Who Drives | Why |
|---------|-----------|-----|
| AI cleanup (Gemini) | Client | Gemini has per-request token limits. Client controls batch size, retries failed batches, accumulates partial results. |
| Revenue per-PDF progress | Server | Server knows the PDFs. Stream progress events between each PDF. |
| Proration Firestore lookups | Server | Server knows the lease IDs. `asyncio.gather` for parallel reads. |
| Enrichment pipeline | Server | Already server-driven via NDJSON streaming. No change needed. |

**Rationale:** Cloud Run's 600s request timeout means server streams are viable (RRC downloads already push this). Client-driven batching for AI cleanup means natural cancel points between batches and automatic partial results on failure.

## Streaming Protocol Choice: NDJSON vs SSE

**Decision: NDJSON for batch processing. SSE stays for GHL send only.**

| Protocol | Use For | Why |
|----------|---------|-----|
| NDJSON (`StreamingResponse`) | AI cleanup batches, revenue per-PDF, enrichment | Simpler. No event type negotiation. Works with `fetch()` + `ReadableStream`. Already used for enrichment. |
| SSE (`EventSourceResponse`) | GHL bulk send | Already built and working. `EventSource` API handles reconnection automatically for long-running sends. |

Don't convert GHL to NDJSON (working code, different access pattern with query-param auth). Don't use SSE for new batch endpoints (NDJSON is simpler when you control the fetch lifecycle).

## Version Pinning

No changes to `requirements.txt` or `package.json`. Current versions sufficient:

| Package | Current Pin | Needed Capability |
|---------|-------------|-------------------|
| `fastapi>=0.109.0` | `Request.is_disconnected()`, `StreamingResponse` | Batch cancellation, NDJSON streaming |
| `sse-starlette>=2.0` | `EventSourceResponse` | GHL send (unchanged) |
| `google-cloud-firestore>=2.14.0` | Async client, batch operations | Parallel reads, job persistence |
| `react>=19.2.0` | `useSyncExternalStore`, hooks | Operation persistence store |
| `anyio>=4.0` | Cancellation scopes | Already installed |

## Installation

```bash
# Nothing to install -- all deps already present
make install  # only if starting fresh
```

## Confidence Assessment

| Claim | Confidence | Basis |
|-------|------------|-------|
| No new backend deps needed | HIGH | All patterns use FastAPI/Starlette built-ins + asyncio stdlib |
| No new frontend deps needed | HIGH | React 19 primitives + Web APIs cover all patterns |
| `request.is_disconnected()` works for cancellation | HIGH | Core Starlette API, documented |
| `useSyncExternalStore` for operation persistence | HIGH | Stable React API since v18, well-documented |
| NDJSON streaming pattern works | HIGH | Already proven in enrichment pipeline |
| Client-driven batching is correct for AI cleanup | HIGH | Matches Gemini token limits + partial result needs |
| Cloud Run 600s timeout sufficient | MEDIUM | Most operations complete in <60s; revenue multi-PDF could push limits with large uploads |

## Sources

- Codebase: `api/ghl.py` -- SSE with `EventSourceResponse`, cancellation via Firestore flag
- Codebase: `api/extract.py` lines 333-336 -- NDJSON `StreamingResponse` for enrichment
- Codebase: `hooks/useEnrichmentPipeline.ts` -- `AbortController` pattern, NDJSON consumption
- Codebase: `hooks/useSSEProgress.ts` -- SSE consumption with reconnect
- Codebase: `services/rrc_background.py` -- background thread + Firestore job tracking
- Codebase: `services/proration/rrc_county_download_service.py` -- `asyncio.Semaphore` throttling
- Codebase: `requirements.txt` -- `sse-starlette>=2.0`, `anyio>=4.0` already installed
- Codebase: `utils/api.ts` -- `AbortController` for request timeouts

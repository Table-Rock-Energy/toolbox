# Architecture: v1.7 Batch Processing & Resilience

**Domain:** Batch processing, streaming responses, operation persistence for existing FastAPI + React SPA
**Researched:** 2026-03-19
**Confidence:** HIGH -- builds on existing patterns already proven in the codebase

## Current Architecture Inventory

Before adding anything, here is what already exists and can be reused:

| Pattern | Where It Exists | Status |
|---------|----------------|--------|
| SSE streaming | GHL bulk send (`useSSEProgress` + `EventSourceResponse`) | Production, proven |
| NDJSON streaming | Extract enrichment (`StreamingResponse` + `application/x-ndjson`) | Production, proven |
| Background jobs (thread) | RRC download (`rrc_background.py` + `threading.Thread`) | Production, proven |
| Background jobs (asyncio) | GHL bulk send (`asyncio.create_task`) | Production, proven |
| Firestore job tracking | RRC sync jobs + GHL send jobs | Production, proven |
| Abort/cancel | GHL send (`/send/{job_id}/cancel` + Firestore flag) | Production, proven |
| Client-side abort | `useEnrichmentPipeline` (`AbortController`) | Production, proven |
| Sequential step pipeline | `useEnrichmentPipeline.runAllSteps()` | Production, proven |
| Local variable threading | `runAllSteps` uses local `currentEntries` not React state | Production, proven |

**Key insight:** Every pattern needed for v1.7 already exists somewhere in the codebase. The work is composing them into a unified approach, not inventing new patterns.

## Recommended Architecture

### Component Boundaries

| Component | Responsibility | New/Modified | Communicates With |
|-----------|---------------|--------------|-------------------|
| `useOperationStore` (hook) | Global operation state that survives navigation | **NEW** | All tool pages, MainLayout |
| `useBatchPipeline` (hook) | Client-side batch orchestration with ETA | **NEW** | `pipelineApi`, `useOperationStore` |
| `OperationStatusBar` (component) | Persistent banner showing active/completed ops | **NEW** | `useOperationStore` |
| `pipelineApi` (extended) | Streaming batch endpoints | **MODIFIED** | Backend pipeline router |
| `pipeline.py` (extended) | SSE/NDJSON batch streaming endpoints | **MODIFIED** | LLM provider, validation, enrichment |
| `useEnrichmentPipeline` (refactored) | Delegates batch logic to `useBatchPipeline` | **MODIFIED** | `useBatchPipeline` |
| `revenue.py` (extended) | Per-PDF progress streaming | **MODIFIED** | Revenue parsers |
| `proration.py` (extended) | Cache-first + batch Firestore reads | **MODIFIED** | Firestore, RRC data service |

### Data Flow: Batch Pipeline (AI Cleanup Example)

```
User clicks "Enrich" on Extract page (200 entries)
  |
  v
useBatchPipeline splits into 8 batches of 25
  |
  v
For each batch:
  POST /pipeline/cleanup (existing endpoint, 25 entries per call)
    |
    v
  Backend processes 25 entries via Gemini
    |
    v
  Client receives batch result
    |-- Remaps entry_index to global offset (batch_start + local_index)
    |-- Merges changes into local accumulator (not React state per batch)
    |-- Updates progress in useOperationStore
    |-- Pushes accumulated entries to React state (visible update)
    v
  Next batch (or done)
    |
    v
  useOperationStore.complete() -- results persist across navigation
```

### Data Flow: Revenue Multi-PDF Progress

```
User uploads 5 PDFs
  |
  v
POST /revenue/upload-stream (SSE)
  |
  v
Backend processes sequentially:
  |-- yields SSE: {type: "pdf_start", index: 0, filename: "jan.pdf"}
  |-- yields SSE: {type: "pdf_complete", index: 0, rows: 14}
  |-- yields SSE: {type: "pdf_start", index: 1, filename: "feb.pdf"}
  |-- ...
  |-- yields SSE: {type: "complete", total_rows: 67, statements: [...]}
  v
Client shows per-PDF progress bar
```

### Data Flow: Operation Persistence

```
User starts enrichment on Extract (200 entries)
  |
  v
useOperationStore registers operation:
  {id: "extract-enrich-1710...", tool: "extract", type: "enrich",
   status: "running", progress: {current: 0, total: 200}}
  |
  v
User navigates to Revenue page
  |-- OperationStatusBar shows: "Extract: Enriching 45/200..."
  |-- useBatchPipeline continues (not interrupted)
  v
User navigates back to Extract
  |-- useOperationStore.getResults("extract-enrich-1710...")
  |-- Results applied to preview state
```

## Patterns to Follow

### Pattern 1: Client-Side Batch Orchestration

**What:** The client splits entries into batches and calls the backend per-batch. The backend does NOT manage batch state.

**Why:** Matches the existing `runAllSteps` pattern. Client already manages local variable threading, abort, and step sequencing. Adding batching is a natural extension. Server-side batch management would require new Firestore collections, polling, and duplicate the job tracking already done client-side.

**When:** AI cleanup (Gemini has per-request token limits), address validation (Google Maps rate limits), contact enrichment (PDL rate limits).

**Example:**
```typescript
// useBatchPipeline.ts
const BATCH_SIZE = 25

async function processBatches(
  entries: Record<string, unknown>[],
  apiMethod: (tool: string, entries: Record<string, unknown>[]) => Promise<ApiResponse<PipelineResponse>>,
  tool: string,
  onProgress: (processed: number, total: number) => void,
  signal: AbortSignal
): Promise<ProposedChange[]> {
  const allChanges: ProposedChange[] = []
  const total = entries.length

  for (let i = 0; i < total; i += BATCH_SIZE) {
    if (signal.aborted) break

    const batch = entries.slice(i, i + BATCH_SIZE)
    const response = await apiMethod(tool, batch)

    if (response.data?.success) {
      // Remap entry_index to global index
      const remapped = response.data.proposed_changes.map(c => ({
        ...c,
        entry_index: c.entry_index + i
      }))
      allChanges.push(...remapped)
    }

    onProgress(Math.min(i + BATCH_SIZE, total), total)
  }

  return allChanges
}
```

### Pattern 2: SSE for Long Operations (Backend-Driven Progress)

**What:** For operations where the backend controls pacing (revenue PDF processing, Gemini calls), use SSE to stream progress events.

**Why:** Already proven with GHL bulk send. `sse-starlette` is already a dependency. `useSSEProgress` hook exists. EventSource reconnects automatically.

**When:** Revenue multi-PDF upload, any single endpoint taking >5 seconds.

**Example (backend):**
```python
@router.post("/upload-stream")
async def upload_pdfs_stream(request: Request, files: list[UploadFile] = File(...)):
    async def event_generator():
        for i, file in enumerate(files):
            yield {"event": "pdf_start", "data": json.dumps({
                "index": i, "filename": file.filename, "total": len(files)
            })}

            # Process PDF...
            rows = await process_pdf(file)

            yield {"event": "pdf_complete", "data": json.dumps({
                "index": i, "rows": len(rows)
            })}

        yield {"event": "complete", "data": json.dumps({...final_result...})}

    return EventSourceResponse(event_generator())
```

### Pattern 3: Operation Store (React Context, Not Zustand)

**What:** A React Context that holds active and recently completed operations. Lives at the `MainLayout` level so it survives route changes.

**Why:** No new dependencies (constraint: no new deps). The app already uses Context for auth. Operations are few (max 1-2 concurrent). No need for Redux/Zustand complexity.

**When:** Any operation that should survive navigation.

**Key design:** The store holds references to in-progress promises and their results. When a tool page mounts, it checks the store for pending/completed operations matching its tool name.

```typescript
// contexts/OperationContext.tsx
interface Operation {
  id: string
  tool: string
  type: 'enrich' | 'upload' | 'export'
  status: 'running' | 'completed' | 'failed' | 'cancelled'
  progress: { current: number; total: number }
  result?: unknown  // Tool-specific result data
  startedAt: number
  completedAt?: number
}

interface OperationContextValue {
  operations: Map<string, Operation>
  register: (op: Omit<Operation, 'status' | 'startedAt'>) => string
  updateProgress: (id: string, current: number, total: number) => void
  complete: (id: string, result: unknown) => void
  fail: (id: string, error: string) => void
  cancel: (id: string) => void
  getActiveForTool: (tool: string) => Operation | undefined
  getCompletedForTool: (tool: string) => Operation | undefined
  dismiss: (id: string) => void
}
```

### Pattern 4: Partial Results on Failure

**What:** When a batch fails mid-stream, return all successfully processed batches plus the error.

**Why:** With 200 entries and Gemini processing, losing 7 completed batches because batch 8 fails is unacceptable.

**When:** Any batched operation.

**Implementation:** Already natural with client-side batching. The `allChanges` accumulator in `useBatchPipeline` holds all successful results. On error, the hook transitions to `completed_partial` status and makes accumulated changes available.

```typescript
// In useBatchPipeline
} catch (err) {
  // Partial failure: keep what we have
  return {
    changes: allChanges,  // All successful batches
    status: 'completed_partial',
    error: `Failed at batch ${batchIndex + 1}: ${err.message}`,
    processedCount: i,
    totalCount: total,
  }
}
```

### Pattern 5: Proration Cache-First with Batch Reads

**What:** Proration RRC lookups check in-memory pandas cache first, then batch-read from Firestore for misses, then individual HTML scraping as last resort.

**Why:** Current flow does sequential Firestore reads per missing row. `asyncio.gather` can parallelize these. Cache pre-warming on startup eliminates cold-start penalty.

**When:** Proration upload processing.

```python
# Tiered lookup strategy
async def lookup_rrc_data(rows: list[MineralHolderRow]) -> list[RRCResult]:
    # 1. Check pandas in-memory cache (instant, covers ~95% of cases)
    cached, misses = rrc_data_service.batch_lookup(rows)

    # 2. Batch Firestore reads for misses (parallel)
    if misses:
        tasks = [firestore_lookup(row) for row in misses]
        db_results = await asyncio.gather(*tasks, return_exceptions=True)
        # Merge successes, collect remaining misses

    # 3. Individual HTML scraping for remaining misses (existing pattern)
    # Already implemented in fetch_individual_leases
```

## Anti-Patterns to Avoid

### Anti-Pattern 1: Server-Side Batch Job Management for Pipeline

**What:** Creating Firestore job documents and polling for AI cleanup/validation/enrichment batches.
**Why bad:** Duplicates the client-side orchestration that already works. Adds complexity, Firestore cost, and a second state management path. The existing `runAllSteps` local-variable-threading pattern is simpler and proven.
**Instead:** Client-side batching with direct HTTP calls. Server stays stateless per request.

### Anti-Pattern 2: WebSocket for Progress

**What:** Using WebSocket instead of SSE for streaming progress.
**Why bad:** SSE is already proven in the codebase. WebSocket requires bidirectional protocol, connection management, and has worse reconnection semantics. The data flow is unidirectional (server to client).
**Instead:** SSE via `sse-starlette` (already a dependency).

### Anti-Pattern 3: Global State Library (Redux, Zustand, Jotai)

**What:** Adding a state management library for operation persistence.
**Why bad:** Violates "no new dependencies" constraint. The app has one user at a time (small internal team). Operation count is trivially small. React Context handles this fine.
**Instead:** `OperationContext` at `MainLayout` level.

### Anti-Pattern 4: Streaming Individual Entry Results

**What:** SSE streaming per-entry results from backend during AI cleanup.
**Why bad:** Gemini processes entries in a single prompt (the whole batch at once). There is no per-entry progress to stream. The latency is in the LLM call, not iteration.
**Instead:** Batch-level progress (batch 3 of 8 complete).

### Anti-Pattern 5: Persisting Operation State to Firestore

**What:** Writing in-progress pipeline operations to Firestore.
**Why bad:** These operations are ephemeral (seconds to minutes), user-specific, and the results are already held in React state. Firestore persistence is for durable data (jobs, RRC data, connections). Adding operation state creates cleanup burden and read/write costs for transient data.
**Instead:** In-memory React Context. If the browser tab closes, the operation is lost -- acceptable for an internal tool with one user.

## Integration Points: New vs Modified

### New Files

| File | Purpose |
|------|---------|
| `frontend/src/contexts/OperationContext.tsx` | Global operation state provider |
| `frontend/src/hooks/useBatchPipeline.ts` | Client-side batch orchestration with ETA |
| `frontend/src/components/OperationStatusBar.tsx` | Persistent banner in MainLayout showing active ops |

### Modified Files

| File | Change |
|------|--------|
| `frontend/src/hooks/useEnrichmentPipeline.ts` | Delegate batch splitting to `useBatchPipeline`, consume `useOperationStore` |
| `frontend/src/components/EnrichmentModal.tsx` | Show batch-level progress (batch N of M), not just step-level |
| `frontend/src/layouts/MainLayout.tsx` | Wrap with `OperationProvider`, render `OperationStatusBar` |
| `frontend/src/App.tsx` | Add `OperationProvider` inside `AuthProvider` |
| `frontend/src/utils/api.ts` | Add timeout extension for batch calls (existing 300s may need per-batch adjustment) |
| `backend/app/api/pipeline.py` | No change needed if client-side batching; optionally add batch_size hint param |
| `backend/app/api/revenue.py` | Add `/upload-stream` SSE endpoint alongside existing `/upload` |
| `backend/app/api/proration.py` | Add `asyncio.gather` for batch Firestore reads |
| `backend/app/services/proration/rrc_data_service.py` | Add `batch_lookup()` method, startup pre-warming |
| `backend/app/main.py` | Add startup hook for RRC cache pre-warming |

### Unchanged Files

| File | Why No Change |
|------|---------------|
| `frontend/src/contexts/AuthContext.tsx` | Auth is orthogonal to operations |
| `backend/app/services/rrc_background.py` | RRC background download pattern stays as-is |
| `backend/app/api/ghl.py` | GHL already has its own SSE pattern, no changes needed |
| `frontend/src/hooks/useSSEProgress.ts` | GHL-specific, new SSE consumption can use a generic variant or inline EventSource |

## Suggested Build Order

Based on dependency analysis:

```
Phase 1: Foundation (no UI changes needed)
  |-- OperationContext.tsx          -- no deps, just a provider
  |-- useBatchPipeline.ts          -- depends on pipelineApi (existing)
  |-- Proration cache pre-warming  -- backend only, no frontend

Phase 2: Pipeline Batching (core feature)
  |-- useEnrichmentPipeline refactor to use useBatchPipeline
  |-- EnrichmentModal batch progress UI
  |-- Backend pipeline batch support (if needed beyond client-side splitting)

Phase 3: Operation Persistence (requires Phase 1)
  |-- OperationStatusBar.tsx
  |-- MainLayout integration
  |-- Tool pages consume operation results on mount

Phase 4: Revenue Streaming (independent of Phases 2-3)
  |-- Backend /upload-stream SSE endpoint
  |-- Revenue page SSE progress UI

Phase 5: Proration Optimization (independent)
  |-- asyncio.gather for batch Firestore reads
  |-- batch_lookup() in rrc_data_service
```

**Phase ordering rationale:**
- Phase 1 first because OperationContext and useBatchPipeline are consumed by everything else
- Phase 2 before Phase 3 because batching delivers value without persistence; persistence without batching delivers nothing
- Phase 4 is independent -- revenue streaming has no dependency on the enrichment pipeline
- Phase 5 is independent -- proration optimization is purely backend

## Abort/Cancel Propagation

Three levels of abort already exist in the codebase. v1.7 needs to connect them:

1. **Client-side AbortController** (exists in `useEnrichmentPipeline`): Stops batch iteration
2. **fetch AbortSignal** (exists in `ApiClient`): Cancels in-flight HTTP request
3. **SSE disconnect detection** (exists in GHL SSE): `request.is_disconnected()`

**New connection needed:** When `useBatchPipeline.abort()` is called:
1. Set AbortController signal (stops next batch from starting)
2. Abort current fetch via signal (cancels in-flight request)
3. Backend detects disconnection and stops processing (or discards result)
4. Accumulated partial results remain available in the hook

No Firestore cancellation flag needed (unlike GHL jobs) because pipeline operations are direct HTTP requests, not background tasks.

## Scalability Considerations

| Concern | Current (10-50 entries) | Target (200-500 entries) | Limit (1000+ entries) |
|---------|------------------------|--------------------------|----------------------|
| AI cleanup | Single request, 30s | 8-20 batches, ~2min | Consider backend queue |
| Address validation | Sequential, slow | Batch with concurrency limit | Google Maps quota |
| Enrichment | Sequential | Batch with PDL rate limit | Cost concern, not technical |
| Revenue PDFs | Synchronous, blocks | SSE per-PDF | Memory (1Gi Cloud Run) |
| Proration lookup | Sequential Firestore | asyncio.gather parallel | Firestore read quota |
| Operation store | N/A | 1-2 concurrent ops | React re-render cost (trivial) |

## Sources

- Codebase analysis: `frontend/src/hooks/useSSEProgress.ts`, `backend/app/api/ghl.py` (SSE pattern)
- Codebase analysis: `frontend/src/hooks/useEnrichmentPipeline.ts` (pipeline orchestration)
- Codebase analysis: `backend/app/services/rrc_background.py` (background job pattern)
- Codebase analysis: `backend/app/api/pipeline.py` (current pipeline endpoints)
- Codebase analysis: `backend/app/api/extract.py` (NDJSON streaming)
- FastAPI SSE: sse-starlette already in requirements.txt

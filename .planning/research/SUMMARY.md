# Project Research Summary

**Project:** Table Rock Tools — v1.7 Batch Processing & Resilience
**Domain:** Batch orchestration, streaming progress, operation persistence, and request cancellation for internal document-processing SPA
**Researched:** 2026-03-19
**Confidence:** HIGH

## Executive Summary

v1.7 is a resilience milestone, not a feature milestone. The existing stack already contains every primitive needed: SSE via `sse-starlette`, NDJSON streaming via `StreamingResponse`, background jobs via `threading` + Firestore, abort via `AbortController` + `request.is_disconnected()`, and parallel reads via `asyncio.gather`. No new dependencies are required. The work is composing these proven patterns into a unified approach across the AI cleanup, Revenue multi-PDF, and Proration lookup flows.

The critical architectural decision is where batch orchestration lives. Research strongly recommends client-side orchestration for AI cleanup (Gemini has per-request token limits, client controls pacing and retries) and server-side streaming for Revenue per-PDF progress (backend controls the PDFs, SSE per-PDF is natural). This hybrid matches the existing codebase patterns precisely: `useEnrichmentPipeline` already does client-side step orchestration; `ghl.py` already does server-side SSE streaming. v1.7 extends both patterns rather than introducing a third.

The primary risk is state architecture: if operation state is not moved out of component-local `useState` before batch work begins, navigation will destroy in-progress results. The mitigation is `OperationContext` at the `MainLayout` level — a React Context that survives route changes, following the exact same pattern as `AuthContext`. This must be designed first because the state shape dictates everything else.

## Key Findings

### Recommended Stack

No changes to `requirements.txt` or `package.json`. All patterns use FastAPI/Starlette built-ins, asyncio stdlib, and stable React 19 APIs. See [STACK.md](STACK.md) for full analysis.

**Core technologies leveraged:**
- `request.is_disconnected()` (Starlette built-in) — backend cancellation detection without Firestore flags
- `asyncio.gather` (stdlib) — parallel Firestore reads replacing sequential per-row lookups
- `useSyncExternalStore` (React 19 built-in) — binding module-level operation store to components without Context re-renders
- `StreamingResponse` + NDJSON (FastAPI built-in) — batch streaming, already proven in enrichment pipeline
- `EventSourceResponse` (sse-starlette, already installed) — Revenue per-PDF SSE progress

**What to reject:** Celery, Redis, WebSockets, Zustand/Jotai, react-query, server-side batch queues, Framer Motion. Each adds a dependency or architecture layer that the existing stack renders unnecessary.

### Expected Features

See [FEATURES.md](FEATURES.md) for full table with complexity and dependency analysis.

**Must have (table stakes):**
- Batch progress with ETA — 200-entry AI cleanup has no feedback without it
- Partial results on failure — losing 5 completed batches on batch 6 failure is unacceptable
- Cancel in-flight operation — user cannot stop an incorrectly-started 200-entry cleanup
- Per-PDF progress for Revenue — multi-PDF upload blocks with no feedback
- Operation survives navigation — state loss on tab switch destroys trust
- Proration batch Firestore reads — O(n) sequential reads at 200 rows is unacceptable latency

**Should have (differentiators):**
- Client-side batch orchestration hook (`useBatchPipeline`) — foundation for all progress/cancel features
- Proration cache pre-warming on startup — eliminates cold-start penalty
- Global undo across navigation — extends operation persistence context
- Batch retry for failed items only — retry only failed entries after partial failure

**Defer:**
- Per-entry streaming within a batch — Gemini processes whole batch at once, no per-entry granularity available
- Server-side batch job persistence to Firestore — ephemeral operations, React Context is sufficient

### Architecture Approach

The recommended architecture adds three new files (`OperationContext.tsx`, `useBatchPipeline.ts`, `OperationStatusBar.tsx`) and modifies six existing files. Server stays stateless per request. Client drives AI cleanup batches. Backend drives Revenue streaming. See [ARCHITECTURE.md](ARCHITECTURE.md) for full component boundary diagram and data flow.

**Major components:**
1. `OperationContext.tsx` — global operation state at `MainLayout` level, survives navigation, keyed by tool name
2. `useBatchPipeline.ts` — client-side batch loop with `AbortController`, ETA calculation, partial result accumulation
3. `OperationStatusBar.tsx` — persistent banner in `MainLayout` showing active/completed ops across route changes
4. `revenue.py` `/upload-stream` endpoint — SSE per-PDF progress alongside existing `/upload`
5. `proration.py` batch Firestore reads — `asyncio.gather` replacing sequential per-row lookups
6. `rrc_data_service.py` startup pre-warming — `asyncio.to_thread` in FastAPI lifespan hook

### Critical Pitfalls

See [PITFALLS-V1.7.md](PITFALLS-V1.7.md) for full pitfall catalog with detection and prevention details.

1. **Batch architecture decided too late** — must choose client-side vs server-side orchestration in Phase 1 before any batch work. Research recommends client-side for AI cleanup, server-side SSE for Revenue. Changing mid-implementation requires rewriting state management.
2. **Navigation destroys in-progress operations** — all tool state in component-local `useState` dies on unmount. `OperationContext` must be in place before batch UI is built, otherwise results are lost on any navigation event.
3. **Partial results discarded on batch failure** — current `runAllSteps` error handling loses all completed batches. Results accumulator must live outside the `try/catch` block, returning `{partial: true, batches_completed: N}` on failure.
4. **AbortController doesn't abort server** — frontend `abort()` cancels the `fetch()` but backend Gemini call continues burning quota. Backend must check `await request.is_disconnected()` between batches, or use client-side orchestration so each request is short-lived.
5. **SSE connection lifecycle** — orphaned SSE handlers pin Cloud Run instances alive preventing scale-to-zero. Server must poll `request.is_disconnected()` every iteration. Client must close EventSource in `useEffect` cleanup.

## Implications for Roadmap

Based on research, the ARCHITECTURE.md phase ordering is the correct build sequence. Dependencies are hard: operation context must precede batch UI, batch pipeline must precede progress/cancel features, Revenue streaming is independent.

### Phase 1: Foundation — Operation Context + Batch Pipeline

**Rationale:** Everything else depends on these two pieces. `OperationContext` defines the state shape that all tool pages will consume. `useBatchPipeline` is the engine that all client-driven batch features will use. Building either without the other creates throwaway code. Proration pre-warming is included here as an independent backend-only quick win.
**Delivers:** Global operation state that survives navigation; client-side batch orchestration with abort and partial results; proration cache pre-warming
**Addresses:** Operation survives navigation, partial results on failure, proration cold-start latency
**Avoids:** Pitfall 1 (architecture decision made upfront), Pitfall 3 (navigation destroys state), Pitfall 4 (partial results lost)

### Phase 2: AI Cleanup Batching — Pipeline Refactor

**Rationale:** Phase 1 foundations enable this. `useEnrichmentPipeline` delegates batch splitting to `useBatchPipeline`. Adds batch progress UI to `EnrichmentModal`. This is the highest-value user-facing change: 200-entry AI cleanup goes from opaque blocking to transparent batch-by-batch progress with cancel.
**Delivers:** Batch progress with ETA, cancel in-flight, partial results on failure — all for AI cleanup flow
**Uses:** `useBatchPipeline`, `OperationContext`, `AbortController` + `request.is_disconnected()`
**Implements:** Client-side batch orchestration pattern
**Avoids:** Pitfall 4 (partial results), Pitfall 6 (abort doesn't stop server), Pitfall 11 (ETA jitter — use moving average, show batch count alongside)

### Phase 3: Operation Persistence UI

**Rationale:** Context is in place (Phase 1), batch operations are running (Phase 2). Now surface the context to users. `OperationStatusBar` in `MainLayout` shows active/completed operations across navigation. Tool pages check context on mount for pending results.
**Delivers:** Persistent operation banner, results survive navigation, undo across tab switches
**Implements:** `OperationStatusBar.tsx`, `MainLayout` integration, per-tool mount-time context check
**Avoids:** Pitfall 10 (multi-tool race condition — key state by tool name, one active operation per tool)

### Phase 4: Revenue Multi-PDF Streaming

**Rationale:** Independent of Phases 2-3 (different tool, different pattern). SSE per-PDF progress follows the established GHL bulk send pattern exactly. Add `/upload-stream` endpoint alongside existing `/upload` for zero regression risk.
**Delivers:** Per-PDF progress during multi-PDF Revenue upload; partial results if one PDF fails; concurrent PDF processing with semaphore
**Uses:** `EventSourceResponse` (sse-starlette), generalized SSE hook pattern
**Avoids:** Pitfall 2 (SSE lifecycle), Pitfall 8 (Cloud Run 600s timeout — worst case ~210s for 7 PDFs), Pitfall 9 (blocking UI)

### Phase 5: Proration Optimization

**Rationale:** Independent of all other phases (backend-only, no new UI). Batch reads replace sequential reads in the existing proration upload path.
**Delivers:** Faster proration upload (O(n) → O(n/100) Firestore round trips)
**Implements:** `asyncio.gather` with chunked `get_all()`, `batch_lookup()` in `rrc_data_service`
**Avoids:** Pitfall 5 (stale cache — invalidate on RRC sync completion), Pitfall 12 (Firestore batch size — chunk at 100), Pitfall 13 (memory pressure — load lazily in background after startup)

### Phase Ordering Rationale

- Phase 1 is prerequisite: `OperationContext` state shape must be final before any tool page consumes it; `useBatchPipeline` API must be stable before `useEnrichmentPipeline` refactors against it.
- Phase 2 before Phase 3: Batch operations must exist before a status bar has anything to show. Context without operations is overhead with no value.
- Phases 4 and 5 are independent: Revenue streaming has no dependency on the enrichment pipeline; proration optimization is purely backend. Both can be parallelized with Phases 2-3 if bandwidth allows.
- The architecture decision in Pitfall 1 is embedded in Phase 1 as a Key Decision. Documenting it before Phase 2 begins prevents mid-implementation pivots.

### Research Flags

All phases use well-documented patterns — no phase requires `/gsd:research-phase`:
- **Phase 1:** `OperationContext`, `useBatchPipeline`, `asyncio.to_thread` startup are all established and verified against the existing codebase.
- **Phase 2:** `useEnrichmentPipeline` refactor is mechanical — same hook, moved batch loop to client. No new APIs.
- **Phase 3:** `MainLayout` integration follows `AuthContext` pattern exactly.
- **Phase 4:** SSE pattern is production-proven in GHL send. `revenue.py` `/upload-stream` follows identical structure.
- **Phase 5:** `asyncio.gather`, Firestore `get_all()`, and startup hooks are documented stdlib/SDK features.

Areas requiring care during implementation (upfront design, not formal research):
- **Phase 2:** `AbortController` integration needs verification that existing `ApiClient` fetch wrapper can propagate the signal. Verify before building the cancel UI.
- **Phase 4:** SSE token in query string (Pitfall 7) extends to new endpoints. Decide at Phase 4 kickoff whether to use short-lived job-scoped tokens or accept the existing pattern.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All patterns verified against existing codebase files; no new deps means no version compatibility unknowns |
| Features | HIGH | Derived from concrete user-reported pain points (timeouts, state loss, no cancel), not speculative |
| Architecture | HIGH | Every component boundary references existing files and proven patterns; build order driven by hard dependencies |
| Pitfalls | HIGH | All critical pitfalls sourced from actual codebase analysis (`useEnrichmentPipeline.ts`, `gemini_service.py`, `ghl.py`) not speculation |

**Overall confidence:** HIGH

### Gaps to Address

- **Cloud Run 600s timeout with large Gemini batch sets:** Research calculates 500 entries at ~3-4 minutes under normal conditions. If Gemini adds exponential backoff on rate limits, this could approach the limit. Track batch start time in `useBatchPipeline` and abort with graceful partial results if approaching 540s. Validate during Phase 2 with actual Gemini timing data.
- **RRC CSV size in memory:** Research estimates 50-100MB for oil + gas DataFrames combined. Pre-warming at startup is safe but should be verified with production data volume before enabling the startup hook. Validate during Phase 5.
- **SSE token exposure (Pitfall 7):** GHL SSE passes Firebase ID token as query param. Short-lived job-scoped tokens are the right fix but add complexity. Flag for Phase 4 implementation decision.

## Sources

### Primary (HIGH confidence — direct codebase inspection)
- `frontend/src/hooks/useEnrichmentPipeline.ts` — pipeline orchestration, AbortController, partial results pattern
- `frontend/src/hooks/useSSEProgress.ts` — SSE consumption with reconnect
- `backend/app/api/ghl.py` — SSE with EventSourceResponse, cancellation via Firestore flag
- `backend/app/api/extract.py` — NDJSON StreamingResponse for enrichment
- `backend/app/services/rrc_background.py` — background thread + Firestore job tracking
- `backend/app/services/proration/rrc_county_download_service.py` — asyncio.Semaphore throttling
- `backend/app/services/firestore_service.py` — get_in_batches, batch write limits
- `requirements.txt` — `sse-starlette>=2.0`, `anyio>=4.0` confirmed installed; no new deps needed
- `utils/api.ts` — AbortController for request timeouts

### Secondary (MEDIUM confidence)
- FastAPI SSE Tutorial — server-sent events integration
- FastAPI Client Disconnect Discussion (GitHub) — `is_disconnected()` behavior
- React State Management 2025 (developerway.com) — Context vs external store tradeoffs
- Bulk API Design Patterns (mscharhag.com) — partial success response shapes
- Partial Success Response Patterns (Akamai) — `partial: true` response shape

### Tertiary (LOW confidence)
- Cloud Run SSE timeout behavior under sustained Gemini rate limiting — inferred from 600s config + GHL SSE production behavior; not directly tested with batch streaming

---
*Research completed: 2026-03-19*
*Ready for roadmap: yes*

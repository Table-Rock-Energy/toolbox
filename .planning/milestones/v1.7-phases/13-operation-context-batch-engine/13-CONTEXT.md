# Phase 13: Operation Context & Batch Engine - Context

**Gathered:** 2026-03-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Global operation state that survives React Router navigation, plus client-side batch orchestration for AI cleanup. Operations have a place to live at the MainLayout level, and batch processing shows per-batch progress with ETA. Retry logic, concurrency tuning, and admin-configurable batch sizes are Phase 14. Status bar UI is Phase 15.

Requirements: PERSIST-01, BATCH-01, BATCH-02, RESIL-01, RESIL-03

</domain>

<decisions>
## Implementation Decisions

### Operation Context Architecture
- **Wrap and lift pattern**: OperationContext wraps useEnrichmentPipeline at MainLayout level, above `<Outlet />`
- Tool pages consume context via `useOperationContext()` instead of calling the enrichment hook directly
- **Full enrichment state in context**: entries snapshot, step statuses, enrichment changes, completed steps, ETA — all live in context. Tool pages are pure consumers/renderers
- **One operation at a time**: Only one enrichment operation runs globally. Starting a new one while another is active requires cancel confirmation
- **Auto-restore on return**: When tool page mounts and completed results exist for that tool in OperationContext, automatically apply them to preview state. No recovery banner or user action needed

### Client-Side Batch Orchestration
- **Client slices entries into 25-entry batches** and sends separate requests per batch to existing pipeline endpoints
- Existing `/api/pipeline/cleanup` (and validate/enrich) endpoints accept any array size — no backend changes for batching
- Backend still batches internally for Gemini (transparent to client) but receives only 25 entries per request
- **Progressive auto-apply**: Each batch's results apply immediately to the preview table as they complete. User sees rows updating live
- **ETA in EnrichmentModal**: Extend existing modal to show batch-level progress within each step — "Clean Up: Batch 3 of 8 — ~45s remaining". ETA recalculates after each batch completes

### Navigate-Away Behavior
- **Silent continue, no warning**: Operation keeps running in OperationContext when user navigates between tool pages. No modal, toast, or confirmation dialog
- **AbortController on beforeunload only**: Cancel in-flight fetches when browser tab/window closes. React Router navigation within the app does NOT cancel operations (OperationContext persists above page components)
- **Modal auto-close on navigation**: EnrichmentModal closes when user navigates away. When user returns to the tool page, if operation is still running the modal reopens automatically. If completed, results auto-restore without modal

### Partial Failure Recovery
- **Skip failed batches, continue rest**: If batch 3 of 8 fails (Gemini error, network issue), mark it as failed and continue with batches 4-8. Entries from failed batch remain unchanged in preview
- **Error count in modal**: EnrichmentModal shows "Clean Up: 7/8 batches — 25 entries skipped (1 batch failed)". No per-entry failure markers in the data table
- **No retry in Phase 13**: Retry logic is Phase 14 scope (RESIL-04). This phase focuses on the engine foundation
- **Full undo**: Global undo reverts the entire pre-pipeline snapshot, including all successful batches. No selective per-batch undo

### Claude's Discretion
- OperationContext provider implementation details (React Context shape, memoization strategy)
- How useEnrichmentPipeline refactors internally to support batch slicing
- AbortController wiring for beforeunload event
- How auto-restore detects "this tool's results" in the context (tool name key)
- EnrichmentModal batch progress sub-component layout

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & Roadmap
- `.planning/REQUIREMENTS.md` — PERSIST-01, BATCH-01, BATCH-02, RESIL-01, RESIL-03 requirement definitions
- `.planning/ROADMAP.md` §Phase 13 — Success criteria (5 items) and dependency chain

### Prior Phase Context
- `.planning/phases/08-enrichment-pipeline-features/08-CONTEXT.md` — Enrichment pipeline decisions: auto-apply high-confidence, propose-review-apply workflow, edit conflict resolution

### Out of Scope Boundary
- `.planning/REQUIREMENTS.md` §Out of Scope — Server-side job queue, Zustand/Redux, WebSocket streaming explicitly excluded

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `useEnrichmentPipeline.ts` (frontend/src/hooks/useEnrichmentPipeline.ts): Core hook with runAllSteps, abortPipeline, step statuses, ETA, AbortController, progressive apply. This gets lifted into OperationContext
- `EnrichmentModal.tsx` (frontend/src/components/EnrichmentModal.tsx): Progress modal with step indicators, ETA calculation, completion summary. Extend with batch-level progress
- `AuthContext.tsx` (frontend/src/contexts/AuthContext.tsx): Only existing React Context — pattern reference for OperationContext provider/consumer setup

### Established Patterns
- React Context at provider level with `useContext` hook consumer (AuthContext pattern)
- Local variable threading through async steps (runAllSteps uses currentEntries, not React state — avoids stale closure)
- AbortController ref pattern already in useEnrichmentPipeline
- BATCH_SIZE=25 defined in `backend/app/services/gemini_service.py` — client should match this

### Integration Points
- `MainLayout.tsx` (frontend/src/layouts/MainLayout.tsx): OperationProvider wraps the `<Outlet />` here
- Tool pages (Extract.tsx, Title.tsx, Proration.tsx, Revenue.tsx): Replace direct useEnrichmentPipeline calls with useOperationContext
- `pipelineApi` in `frontend/src/utils/api.ts`: Existing API client methods (cleanup, validate, enrich) — called per-batch by the new engine
- `EnrichmentModal`: Already rendered in tool pages, may need to move to MainLayout or remain in tool pages with context-driven props

</code_context>

<specifics>
## Specific Ideas

No specific requirements — decisions align with recommended approaches throughout. The existing useEnrichmentPipeline hook already implements most of the logic; this phase primarily lifts it to a higher level and adds batch slicing.

</specifics>

<deferred>
## Deferred Ideas

- Configurable batch size per tool via admin settings — Phase 14 (BATCH-03)
- Concurrent batch requests — Phase 14 (BATCH-04)
- Auto-retry failed batches — Phase 14 (RESIL-04)
- Backend disconnect detection (request.is_disconnected) — Phase 14 (RESIL-02)
- Status bar in MainLayout header — Phase 15 (PERSIST-02)
- Result recovery UI after navigation — Phase 15 (PERSIST-03)

</deferred>

---

*Phase: 13-operation-context-batch-engine*
*Context gathered: 2026-03-19*

# Phase 13: Operation Context & Batch Engine - Research

**Researched:** 2026-03-19
**Domain:** React Context state lifting, client-side batch orchestration, AbortController lifecycle
**Confidence:** HIGH

## Summary

This phase is a pure frontend refactor with no backend changes. The existing `useEnrichmentPipeline` hook already contains all the pipeline logic (runAllSteps, abortPipeline, step statuses, ETA, AbortController, progressive apply). The work is: (1) lift that hook's state into a new `OperationContext` at the `MainLayout` level so operations survive React Router navigation, (2) add client-side batch slicing (25-entry chunks) to `runAllSteps` so progress shows "Batch N of M", and (3) wire AbortController to `beforeunload` only (not navigation).

Four tool pages (Extract, Title, Proration, Revenue) currently call `useEnrichmentPipeline` directly and render `EnrichmentModal` locally. All four must be refactored to consume `useOperationContext()` instead. The `EnrichmentModal` stays in tool pages but receives context-driven props. No new libraries needed -- React Context, AbortController, and Array.prototype.slice are sufficient.

**Primary recommendation:** Create `OperationContext` as a provider wrapping `<Outlet />` in MainLayout, with the batch-aware pipeline logic inside. Tool pages become thin consumers.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Wrap and lift pattern**: OperationContext wraps useEnrichmentPipeline at MainLayout level, above `<Outlet />`
- Tool pages consume context via `useOperationContext()` instead of calling the enrichment hook directly
- **Full enrichment state in context**: entries snapshot, step statuses, enrichment changes, completed steps, ETA -- all live in context. Tool pages are pure consumers/renderers
- **One operation at a time**: Only one enrichment operation runs globally. Starting a new one while another is active requires cancel confirmation
- **Auto-restore on return**: When tool page mounts and completed results exist for that tool in OperationContext, automatically apply them to preview state. No recovery banner or user action needed
- **Client slices entries into 25-entry batches** and sends separate requests per batch to existing pipeline endpoints
- Existing `/api/pipeline/cleanup` (and validate/enrich) endpoints accept any array size -- no backend changes for batching
- Backend still batches internally for Gemini (transparent to client) but receives only 25 entries per request
- **Progressive auto-apply**: Each batch's results apply immediately to the preview table as they complete. User sees rows updating live
- **ETA in EnrichmentModal**: Extend existing modal to show batch-level progress within each step -- "Clean Up: Batch 3 of 8 -- ~45s remaining". ETA recalculates after each batch completes
- **Silent continue, no warning**: Operation keeps running in OperationContext when user navigates between tool pages. No modal, toast, or confirmation dialog
- **AbortController on beforeunload only**: Cancel in-flight fetches when browser tab/window closes. React Router navigation within the app does NOT cancel operations
- **Modal auto-close on navigation**: EnrichmentModal closes when user navigates away. When user returns, if operation is still running the modal reopens automatically. If completed, results auto-restore without modal
- **Skip failed batches, continue rest**: If batch 3 of 8 fails, mark it as failed and continue with batches 4-8. Entries from failed batch remain unchanged
- **Error count in modal**: Shows "Clean Up: 7/8 batches -- 25 entries skipped (1 batch failed)". No per-entry failure markers
- **No retry in Phase 13**: Retry logic is Phase 14 scope
- **Full undo**: Global undo reverts entire pre-pipeline snapshot. No selective per-batch undo

### Claude's Discretion
- OperationContext provider implementation details (React Context shape, memoization strategy)
- How useEnrichmentPipeline refactors internally to support batch slicing
- AbortController wiring for beforeunload event
- How auto-restore detects "this tool's results" in the context (tool name key)
- EnrichmentModal batch progress sub-component layout

### Deferred Ideas (OUT OF SCOPE)
- Configurable batch size per tool via admin settings -- Phase 14 (BATCH-03)
- Concurrent batch requests -- Phase 14 (BATCH-04)
- Auto-retry failed batches -- Phase 14 (RESIL-04)
- Backend disconnect detection (request.is_disconnected) -- Phase 14 (RESIL-02)
- Status bar in MainLayout header -- Phase 15 (PERSIST-02)
- Result recovery UI after navigation -- Phase 15 (PERSIST-03)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PERSIST-01 | Active operations continue when user navigates between pages | OperationContext at MainLayout level persists above `<Outlet />` -- page unmounts don't affect context state |
| BATCH-01 | User sees AI cleanup process entries in batches of 25 with per-batch progress | Client-side batch slicing in runAllSteps, EnrichmentModal shows "Batch N of M" per step |
| BATCH-02 | User sees ETA for remaining batches based on first-batch timing | Existing ETA calculation in EnrichmentModal refactored from per-step to per-batch granularity |
| RESIL-01 | All fetch requests use AbortController and cancel on component unmount | AbortController on `beforeunload` event; in-app navigation does NOT cancel (context persists) |
| RESIL-03 | User receives partial results when a batch fails (successful batches preserved) | Skip-and-continue batch logic; progressive auto-apply ensures completed batches already in preview state |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| React | 19.x | Context API, hooks, state management | Already in project |
| React Router | 7.x | `<Outlet />` nested routing enables context persistence | Already in project |

### Supporting
No new libraries needed. All functionality uses built-in browser APIs and existing React patterns.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| React Context | Zustand/Redux | Explicitly out of scope per REQUIREMENTS.md |
| AbortController | axios CancelToken | AbortController already used in ApiClient, native API |
| Client-side batching | Server-side streaming | SSE reserved for Revenue (Phase 16), client batching matches existing pattern |

## Architecture Patterns

### Recommended Project Structure
```
frontend/src/
├── contexts/
│   ├── AuthContext.tsx          # Existing auth context (pattern reference)
│   └── OperationContext.tsx     # NEW: Global operation state provider
├── hooks/
│   ├── useEnrichmentPipeline.ts # REFACTORED: Add batch slicing to runAllSteps
│   ├── usePreviewState.ts       # UNCHANGED: Tool pages still use this
│   └── ...
├── components/
│   └── EnrichmentModal.tsx      # EXTENDED: Batch-level progress display
├── layouts/
│   └── MainLayout.tsx           # MODIFIED: Wrap <Outlet /> with OperationProvider
└── pages/
    ├── Extract.tsx              # REFACTORED: useOperationContext() consumer
    ├── Title.tsx                # REFACTORED: useOperationContext() consumer
    ├── Proration.tsx            # REFACTORED: useOperationContext() consumer
    └── Revenue.tsx              # REFACTORED: useOperationContext() consumer
```

### Pattern 1: OperationContext Provider Shape

**What:** A React Context that holds global pipeline state keyed by tool name, wrapping `<Outlet />` in MainLayout.

**When to use:** Whenever state must survive React Router page transitions.

**Recommended shape:**
```typescript
interface OperationState {
  tool: string
  status: PipelineStatus           // 'idle' | 'running' | 'completed' | 'error'
  stepStatuses: StepStatus[]
  batchProgress: BatchProgress | null
  enrichmentChanges: Map<string, EnrichmentCellChange>
  completedSteps: Set<PipelineStep>
  entriesSnapshot: Record<string, unknown>[] | null  // Pre-pipeline for undo
  resultEntries: Record<string, unknown>[] | null     // Final results for auto-restore
  errorMessage: string | null
}

interface BatchProgress {
  currentBatch: number
  totalBatches: number
  failedBatches: number
  skippedEntries: number
  currentStep: PipelineStep
  batchTimings: number[]  // ms per completed batch, for ETA
}

interface OperationContextType {
  operation: OperationState | null
  startOperation: (opts: StartOperationOpts) => void
  abortOperation: () => void
  undoOperation: () => void
  clearOperation: () => void
  getResultsForTool: (tool: string) => Record<string, unknown>[] | null
}
```

**Key design decisions:**
- `operation` is singular (one-at-a-time constraint)
- `tool` field identifies which tool page owns this operation
- `resultEntries` stores final results so returning tool page can auto-restore
- `batchProgress` is separate from `stepStatuses` for clarity

### Pattern 2: Client-Side Batch Slicing

**What:** Split entries array into 25-entry chunks, send each as a separate API request, apply results progressively.

**When to use:** Inside `runAllSteps` for each pipeline step.

```typescript
const BATCH_SIZE = 25  // Matches backend gemini_service.py BATCH_SIZE

async function runStepBatched(
  step: PipelineStep,
  entries: Record<string, unknown>[],
  signal: AbortSignal
): Promise<void> {
  const totalBatches = Math.ceil(entries.length / BATCH_SIZE)
  const batchTimings: number[] = []
  let failedBatches = 0

  for (let i = 0; i < totalBatches; i++) {
    if (signal.aborted) break

    const start = i * BATCH_SIZE
    const batch = entries.slice(start, start + BATCH_SIZE)
    const batchStart = Date.now()

    try {
      const response = await apiMethod(tool, batch, undefined, sourceData)
      const elapsed = Date.now() - batchStart
      batchTimings.push(elapsed)

      // Apply changes to entries (mutate local copy, push to state)
      applyBatchResults(response.data.proposed_changes, entries, start)

      // Update progress: triggers re-render in EnrichmentModal
      updateBatchProgress({ currentBatch: i + 1, totalBatches, batchTimings, failedBatches })
    } catch {
      failedBatches++
      updateBatchProgress({ currentBatch: i + 1, totalBatches, batchTimings, failedBatches })
      // Skip and continue (RESIL-03)
      continue
    }
  }
}
```

**Critical detail:** When applying batch results, entry indices in the response are relative to the batch (0-24), not the full array. The client must offset by `batchStartIndex` when mapping changes back.

### Pattern 3: Auto-Restore on Tool Page Mount

**What:** When tool page mounts, check OperationContext for completed results matching that tool.

```typescript
// Inside tool page component
const { operation, getResultsForTool } = useOperationContext()

useEffect(() => {
  const results = getResultsForTool(toolName)
  if (results) {
    preview.updateEntries(results as T[])
  }
}, []) // Run once on mount
```

**When to use:** Every tool page that consumes OperationContext.

### Pattern 4: beforeunload AbortController

**What:** Wire AbortController to window `beforeunload` to cancel in-flight fetches on tab close/refresh.

```typescript
// Inside OperationContext provider
useEffect(() => {
  const handleBeforeUnload = () => {
    abortControllerRef.current?.abort()
  }
  window.addEventListener('beforeunload', handleBeforeUnload)
  return () => window.removeEventListener('beforeunload', handleBeforeUnload)
}, [])
```

**Note:** Do NOT wire to React Router navigation events. The whole point of OperationContext is that operations survive navigation.

### Anti-Patterns to Avoid
- **Passing AbortSignal through props from tool pages:** The AbortController lives in OperationContext, not in tool pages. Tool pages do not control cancellation on unmount.
- **Storing entries in both OperationContext and usePreviewState:** OperationContext holds the canonical result entries. Tool pages read from context and feed into usePreviewState on mount. Do not duplicate.
- **Using React state for batch iteration tracking:** The batch loop runs in a single async function. Use local variables for the loop counter and timing array; only push summary to React state for rendering.
- **Canceling operations on `useEffect` cleanup in tool pages:** This defeats PERSIST-01. Only `beforeunload` cancels.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| State management across routes | Custom pub/sub or global store | React Context above `<Outlet />` | Project explicitly excludes Zustand/Redux; Context is the established pattern (AuthContext) |
| Fetch cancellation | Custom token system | AbortController (native) | Already used in ApiClient and useEnrichmentPipeline |
| Batch progress ETA | Moving average, weighted prediction | Simple arithmetic mean of completed batch timings | Good enough for 5-20 batches; complexity not justified |
| Entry index remapping | Complex index tracking | Offset arithmetic: `batchIndex * BATCH_SIZE + responseIndex` | Deterministic, no state needed |

## Common Pitfalls

### Pitfall 1: Stale Closure in Batch Loop
**What goes wrong:** Using React state inside the batch `for` loop reads stale values because state updates are batched and don't reflect mid-loop.
**Why it happens:** React state updates are asynchronous. Reading `entries` from useState inside a loop always gets the initial value.
**How to avoid:** Use local variable threading (already the pattern in existing `runAllSteps`). Mutate a local `currentEntries` array, push snapshots to React state only for rendering.
**Warning signs:** Tests pass for 1 batch but changes from batch 1 are overwritten when batch 2 completes.

### Pitfall 2: Entry Index Mismatch in Batch Results
**What goes wrong:** Backend returns `entry_index: 3` meaning "3rd entry in this batch", but client applies it to index 3 of the full array.
**Why it happens:** Each batch request sends a slice of 25 entries. Backend indices are zero-based relative to that slice.
**How to avoid:** Offset: `const globalIndex = batchStartIndex + change.entry_index`. Always compute `batchStartIndex = batchNumber * BATCH_SIZE`.
**Warning signs:** Changes apply to wrong rows; first batch works correctly, subsequent batches corrupt data.

### Pitfall 3: Context Re-Render Storm
**What goes wrong:** Every batch progress update triggers re-render of all context consumers (all tool pages, MainLayout).
**Why it happens:** React Context re-renders all consumers when context value changes, regardless of which field changed.
**How to avoid:** (a) Memoize context value with `useMemo`. (b) Only the active tool page and EnrichmentModal need batch progress -- other pages should not subscribe to operation details. (c) Consider splitting into two contexts: `OperationStateContext` (changes frequently) and `OperationActionsContext` (stable functions). Or use `useRef` for progress and force-update only the modal.
**Warning signs:** Noticeable jank when navigating during an operation; React DevTools shows unnecessary re-renders.

### Pitfall 4: Race Condition on New Operation Start
**What goes wrong:** User starts operation on Extract, navigates to Title, starts another operation before the first completes.
**Why it happens:** Two concurrent operations writing to the same context state.
**How to avoid:** Enforce one-at-a-time constraint. `startOperation` checks if `operation.status === 'running'` and shows cancel confirmation before proceeding. Abort the existing operation before starting a new one.
**Warning signs:** Data from Extract operation appears in Title results.

### Pitfall 5: Memory Leak from beforeunload Listener
**What goes wrong:** Multiple `beforeunload` listeners accumulate if OperationContext provider remounts.
**Why it happens:** Provider remounts on auth state changes without proper cleanup.
**How to avoid:** Use `useEffect` cleanup function to remove the listener. This is standard but easy to forget.
**Warning signs:** Console warnings about memory leaks; multiple abort calls on page unload.

### Pitfall 6: EnrichmentModal State Desync After Navigation
**What goes wrong:** Modal shows stale batch progress after returning to tool page.
**Why it happens:** Modal re-renders from context state which was updated while the page was unmounted. The modal's `isOpen` state is local to the page, so it needs to re-derive from context.
**How to avoid:** Modal `isOpen` should derive from context: open if `operation.status === 'running' && operation.tool === currentTool`. On mount, if operation is running for this tool, modal auto-opens.
**Warning signs:** User returns to tool page and sees no modal despite operation still running.

## Code Examples

### OperationContext Provider (recommended structure)
```typescript
// frontend/src/contexts/OperationContext.tsx
import { createContext, useContext, useCallback, useState, useRef, useEffect, useMemo } from 'react'
import type { ReactNode } from 'react'
import { pipelineApi } from '../utils/api'
import type { PipelineStatus, StepStatus, PipelineStep, EnrichmentCellChange } from '../hooks/useEnrichmentPipeline'

const BATCH_SIZE = 25

interface BatchProgress {
  currentBatch: number
  totalBatches: number
  failedBatches: number
  skippedEntries: number
  currentStep: PipelineStep
  batchTimings: number[]
}

interface OperationState {
  tool: string
  status: PipelineStatus
  stepStatuses: StepStatus[]
  batchProgress: BatchProgress | null
  enrichmentChanges: Map<string, EnrichmentCellChange>
  completedSteps: Set<PipelineStep>
  entriesSnapshot: Record<string, unknown>[] | null
  resultEntries: Record<string, unknown>[] | null
  errorMessage: string | null
}

// Split context to avoid re-render storms
const OperationStateContext = createContext<OperationState | null>(null)
const OperationActionsContext = createContext<OperationActions | null>(null)

// ... provider implementation
```

### Batch ETA Calculation
```typescript
function calculateBatchEta(batchTimings: number[], remainingBatches: number): string | null {
  if (batchTimings.length === 0 || remainingBatches <= 0) return null
  const avgMs = batchTimings.reduce((a, b) => a + b, 0) / batchTimings.length
  const remainingMs = remainingBatches * avgMs
  const remainingSec = Math.max(0, Math.ceil(remainingMs / 1000))
  if (remainingSec === 0) return null
  if (remainingSec >= 60) return `~${Math.ceil(remainingSec / 60)} min remaining`
  return `~${remainingSec}s remaining`
}
```

### Tool Page Consumer Pattern
```typescript
// Inside Extract.tsx (or any tool page)
const { operation, startOperation, undoOperation } = useOperationContext()

// Auto-restore results on mount
useEffect(() => {
  if (operation?.tool === 'extract' && operation.status === 'completed' && operation.resultEntries) {
    preview.updateEntries(operation.resultEntries as PartyEntry[])
  }
}, []) // Intentionally run once on mount

// Derive modal state from context
const showEnrichModal = operation?.tool === 'extract' && operation.status === 'running'
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Pipeline state per tool page | Global OperationContext | Phase 13 | Operations survive navigation |
| Send all entries in one request | Client-side 25-entry batches | Phase 13 | Per-batch progress + partial failure resilience |
| ETA per pipeline step | ETA per batch within step | Phase 13 | More granular progress for large datasets |
| AbortController on component unmount | AbortController on beforeunload only | Phase 13 | Operations continue during in-app navigation |

## Open Questions

1. **Should OperationContext split into State + Actions contexts?**
   - What we know: Single context causes all consumers to re-render on every batch progress update. Split context (stable actions + volatile state) is a known optimization.
   - What's unclear: Whether the performance impact is noticeable with 4 tool pages as consumers.
   - Recommendation: Start with split context (it's minimal extra code). If unnecessary, easy to merge later. Harder to split later when perf issues arise.

2. **How should auto-restore interact with usePreviewState's source reset?**
   - What we know: `usePreviewState` resets `overrideEntries` when `sourceEntries` reference changes (line 43-50 of usePreviewState.ts). Auto-restore calls `updateEntries` which sets `overrideEntries`.
   - What's unclear: If the tool page re-derives `sourceEntries` from job data on mount, the `useEffect` in usePreviewState might reset the auto-restored entries.
   - Recommendation: Auto-restore must run AFTER the initial sourceEntries effect. Use a ref flag or `setTimeout(0)` to ensure restore runs after the reset cycle. Or check if operation results exist before feeding sourceEntries.

3. **EnrichmentModal rendering location**
   - What we know: Currently rendered inside each tool page with local `isOpen` state. Context decisions say modal auto-closes on navigation and auto-reopens on return.
   - What's unclear: Whether modal should move to MainLayout (single instance) or stay in tool pages (4 instances, driven by context).
   - Recommendation: Keep in tool pages. Each tool page already renders it with tool-specific props. Moving to MainLayout would require the modal to know about all tool types. Tool pages simply derive `isOpen` from context state.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | No frontend test framework configured |
| Config file | None |
| Quick run command | N/A |
| Full suite command | N/A |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PERSIST-01 | Operation continues after navigation | manual | Navigate away during operation, verify progress continues | N/A |
| BATCH-01 | Batches of 25 with per-batch progress | manual | Upload 100+ entries, run cleanup, verify "Batch N of M" | N/A |
| BATCH-02 | ETA updates after each batch | manual | Observe ETA recalculation in EnrichmentModal | N/A |
| RESIL-01 | AbortController on beforeunload | manual | Open DevTools Network, close tab during operation, verify requests canceled | N/A |
| RESIL-03 | Partial results preserved on batch failure | manual | Simulate network error mid-batch (DevTools throttle), verify prior batches applied | N/A |

### Sampling Rate
- **Per task commit:** Manual smoke test -- trigger enrichment, verify modal shows batch progress
- **Per wave merge:** Full manual walkthrough of all 5 success criteria
- **Phase gate:** All 5 success criteria verified manually before `/gsd:verify-work`

### Wave 0 Gaps
- No frontend test framework exists (explicitly out of scope per REQUIREMENTS.md "Out of Scope" table)
- All validation is manual for this phase
- Backend tests (pytest) are unaffected -- no backend changes in this phase

## Sources

### Primary (HIGH confidence)
- `frontend/src/hooks/useEnrichmentPipeline.ts` -- Current pipeline implementation (489 lines)
- `frontend/src/contexts/AuthContext.tsx` -- Existing Context pattern (223 lines)
- `frontend/src/layouts/MainLayout.tsx` -- Current layout with `<Outlet />` (79 lines)
- `frontend/src/components/EnrichmentModal.tsx` -- Current modal (195 lines)
- `frontend/src/hooks/usePreviewState.ts` -- Preview state management (151 lines)
- `frontend/src/App.tsx` -- Router structure showing MainLayout wrapping tool routes (77 lines)
- `frontend/src/utils/api.ts` -- ApiClient with AbortController, pipelineApi methods
- `backend/app/services/gemini_service.py` -- BATCH_SIZE=25 constant

### Secondary (MEDIUM confidence)
- React 19 Context API documentation -- createContext, useContext, Provider pattern
- AbortController MDN documentation -- signal, abort(), beforeunload integration

### Tertiary (LOW confidence)
- None -- all findings derived from codebase inspection

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new libraries, all existing project dependencies
- Architecture: HIGH -- pattern directly follows existing AuthContext + useEnrichmentPipeline code
- Pitfalls: HIGH -- derived from reading actual implementation, especially stale closure and index offset issues

**Research date:** 2026-03-19
**Valid until:** 2026-04-19 (stable -- no external dependency changes)

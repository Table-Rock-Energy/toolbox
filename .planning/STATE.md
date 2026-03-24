---
gsd_state_version: 1.0
milestone: v1.8
milestone_name: Preview System Overhaul
status: defining_requirements
stopped_at: null
last_updated: "2026-03-24"
progress:
  total_phases: 0
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-24)

**Core value:** The tools must reliably process uploaded documents and return accurate, exportable results.
**Current focus:** Defining requirements for v1.8

## Current Position

Phase: Not started (defining requirements)
Plan: —
Status: Defining requirements
Last activity: 2026-03-24 — Milestone v1.8 started

## Accumulated Context

### Decisions

- v1.6: Per-endpoint Depends() for admin auth, not router-level (avoids check_user deadlock)
- v1.6: Enrichment modal uses sequential await, not SSE (steps are 2-15s each)
- v1.6: runAllSteps() uses local variable threading, not React state (avoids stale closure)
- v1.7: Client-side batch orchestration for AI cleanup, server-side SSE for Revenue (research recommendation)
- v1.7: OperationContext at MainLayout level (survives navigation, keyed by tool name)
- v1.7: useBatchPipeline hook as shared engine for all batch operations
- [Phase 13]: Split context pattern (OperationStateContext + OperationActionsContext) to prevent re-render storms
- [Phase 14]: asyncio.Semaphore for batch concurrency control (simpler than TaskGroup)
- [Phase 14]: Sync disconnect_check callable with fire-and-forget async polling for disconnect detection
- [Phase 17]: Cache uses atomic dict replacement on invalidate (new empty dict, not .clear())

### Pending Todos

None.

### Blockers/Concerns

- [v1.6]: EnrichmentToolbar component still exported from barrel (unused, cleanup candidate)

## Session Continuity

Last session: 2026-03-24
Stopped at: Milestone v1.8 started, defining requirements
Resume file: None

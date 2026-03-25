---
phase: 09-tool-specific-ai-prompts
plan: 02
subsystem: ui, api
tags: [react, typescript, enrichment-pipeline, ecf, confidence-badge, proposed-changes]

# Dependency graph
requires:
  - phase: 09-01
    provides: Backend pipeline prompts, PipelineRequest.source_data model, ExtractionResult.original_csv_entries
provides:
  - Frontend PipelineRequest.source_data passthrough to backend
  - ECF tool routing (tool='ecf') in Extract.tsx
  - ProposedChangesPanel confidence badges in group headers
  - ProposedChangesPanel confidence-based group sorting
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Conditional tool routing based on format hint (formatHint === 'ECF' ? 'ecf' : 'extract')"
    - "sourceData passthrough only for cleanup step (cross-file comparison)"
    - "Confidence aggregation in group headers using CONFIDENCE_ORDER map"

key-files:
  created: []
  modified:
    - frontend/src/utils/api.ts
    - frontend/src/hooks/useEnrichmentPipeline.ts
    - frontend/src/pages/Extract.tsx
    - frontend/src/components/ProposedChangesPanel.tsx
    - backend/app/api/extract.py

key-decisions:
  - "source_data passed only for cleanup step, not validate or enrich"
  - "Confidence badge shows highest confidence across all changes in a group"
  - "Groups sorted by highest confidence (high first) using CONFIDENCE_ORDER map"

patterns-established:
  - "Conditional tool routing: formatHint-driven tool selection for pipeline API calls"
  - "sourceData optional param threaded through hook -> api client -> backend"

requirements-completed: [ENRICH-11]

# Metrics
duration: 8min
completed: 2026-03-17
---

# Phase 9 Plan 2: Frontend ECF Plumbing Summary

**Frontend ECF source_data passthrough with confidence badges and sorting in ProposedChangesPanel**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-17T00:00:00Z
- **Completed:** 2026-03-17T00:08:00Z
- **Tasks:** 3 (2 auto + 1 checkpoint)
- **Files modified:** 5

## Accomplishments
- Wired ECF source_data flow from Extract.tsx through useEnrichmentPipeline to pipelineApi to backend
- Extract.tsx now routes to tool='ecf' when formatHint is ECF, passing original CSV entries as sourceData
- ProposedChangesPanel displays colored confidence badges (green/yellow/red) in group header rows
- Groups sorted by highest confidence so high-confidence suggestions surface first
- Backend extract upload returns original_csv_entries for ECF format

## Task Commits

Each task was committed atomically:

1. **Task 1: Frontend plumbing -- PipelineRequest.source_data, pipelineApi, useEnrichmentPipeline.sourceData, Extract.tsx ECF routing, backend extract upload original_csv_entries** - `4d32f54` (feat)
2. **Task 2: ProposedChangesPanel confidence badge in group header + sort by confidence** - `90357ef` (feat)
3. **Task 3: Visual verification checkpoint** - approved (no commit needed)

## Files Created/Modified
- `frontend/src/utils/api.ts` - Added source_data to PipelineRequest interface and pipelineApi methods
- `frontend/src/hooks/useEnrichmentPipeline.ts` - Added sourceData option, passes to cleanup step only
- `frontend/src/pages/Extract.tsx` - ECF tool routing, originalCsvEntries state, sourceData passthrough
- `frontend/src/components/ProposedChangesPanel.tsx` - Confidence badge in group header, confidence-based sorting
- `backend/app/api/extract.py` - Returns original_csv_entries in ECF upload response

## Decisions Made
- source_data passed only for cleanup step (cross-file comparison is part of cleanup, not validate/enrich)
- Confidence badge shows the highest confidence level across all changes in a group
- Groups sorted by highest confidence (high first) using numeric CONFIDENCE_ORDER map

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- This is the final plan in phase 9 and the final phase of v1.5
- All enrichment pipeline features are complete
- ECF uploads now have full AI-assisted cleanup with cross-file comparison
- ProposedChangesPanel provides clear confidence signals for user review

## Self-Check: PASSED

All commits verified (4d32f54, 90357ef). All modified files confirmed on disk. SUMMARY.md created.

---
*Phase: 09-tool-specific-ai-prompts*
*Completed: 2026-03-17*

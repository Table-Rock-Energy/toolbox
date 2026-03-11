---
phase: 04-frontend-integration
plan: 01
subsystem: ui
tags: [react, typescript, ecf, file-upload, formdata]

# Dependency graph
requires: []
provides:
  - ECF format option in Extract page format dropdown
  - Conditional CSV/Excel FileUpload for Convey 640 files
  - Dual-file FormData upload (PDF + optional CSV)
  - CaseMetadata and merge_warnings type contracts on ExtractionResult
affects: [04-frontend-integration]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Conditional secondary FileUpload based on format selection"
    - "useEffect cleanup for format-dependent file state"

key-files:
  created: []
  modified:
    - frontend/src/pages/Extract.tsx

key-decisions:
  - "ECF option added to both collapsed and expanded panel dropdowns for consistency"
  - "CSV file cleared via useEffect on formatHint change rather than inline handler"

patterns-established:
  - "Dual-file upload via FormData.append for optional secondary files"

requirements-completed: [FE-01]

# Metrics
duration: 2min
completed: 2026-03-11
---

# Phase 4 Plan 1: ECF Format Selection and Dual-File Upload Summary

**ECF format option in Extract dropdown with conditional Convey 640 CSV upload and CaseMetadata type contracts**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-11T19:26:33Z
- **Completed:** 2026-03-11T19:28:40Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments
- ECF Filing (Convey 640) option added to both format dropdowns in Extract page
- Conditional second FileUpload for CSV/Excel appears only when ECF format is selected
- Upload handler sends csv_file in FormData alongside PDF when ECF + CSV provided
- CaseMetadata interface and merge_warnings field prepared for backend response handling

## Task Commits

Each task was committed atomically:

1. **Task 1: Add ECF format option and conditional CSV upload** - `85f5734` (feat)
2. **Task 2: Add CaseMetadata interface to ExtractionResult** - `0768061` (feat)

## Files Created/Modified
- `frontend/src/pages/Extract.tsx` - Added ECF format option, conditional CSV FileUpload, csvFile state, FormData csv_file append, CaseMetadata interface, merge_warnings field

## Decisions Made
- ECF option added to both collapsed and expanded panel dropdowns for UI consistency
- CSV file state cleared via useEffect on formatHint change to prevent stale file references
- CaseMetadata fields kept optional to maintain backward compatibility with non-ECF uploads

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Frontend input side complete, ready for Plan 02 (result display with case metadata and merge warnings)
- Backend ECF parsing (Phases 1-3) will populate the new CaseMetadata and merge_warnings fields

---
*Phase: 04-frontend-integration*
*Completed: 2026-03-11*

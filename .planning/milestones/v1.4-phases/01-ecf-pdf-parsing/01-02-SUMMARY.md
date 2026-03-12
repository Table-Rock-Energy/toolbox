---
phase: 01-ecf-pdf-parsing
plan: 02
subsystem: api
tags: [fastapi, export, routing, ecf, exhibit-a, filtering]

# Dependency graph
requires:
  - phase: 01-ecf-pdf-parsing plan 01
    provides: "ECF parser module (parse_ecf_filing), CaseMetadata model, ExhibitFormat.ECF enum"
provides:
  - "ECF format routing in /api/extract/upload?format_hint=ECF endpoint"
  - "ExtractionResult includes case_metadata for ECF uploads"
  - "Export filtering excludes address-less entries from address_unknown/curative_unknown sections"
affects: [02-csv-processing, 03-merge, 04-frontend-integration]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Lazy import of ecf_parser in upload route (same pattern as other parsers)"
    - "Export filtering based on section_type: non-ECF entries always pass through"

key-files:
  created: []
  modified:
    - backend/app/api/extract.py
    - backend/app/services/extract/export_service.py
    - backend/tests/test_ecf_parser.py

key-decisions:
  - "ECF parser skips post-processing name parse loop since it handles parse_name internally"
  - "Export filtering uses section_type presence as guard -- only activates when entries have section_type set"

patterns-established:
  - "Export filtering: check section_type presence before filtering, preserving backward compatibility"

requirements-completed: [ECF-01, ECF-05]

# Metrics
duration: 7min
completed: 2026-03-12
---

# Phase 01 Plan 02: API Wiring Summary

**ECF format routing in upload endpoint with case_metadata in response and address-less entry filtering in exports**

## Performance

- **Duration:** 7 min
- **Started:** 2026-03-12T11:36:04Z
- **Completed:** 2026-03-12T11:43:49Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Upload endpoint routes format_hint=ECF to parse_ecf_filing and returns entries with case_metadata
- Exports exclude entries from address_unknown/curative_unknown sections that have no address
- 10 new integration tests covering upload routing and export filtering edge cases (65 total ECF tests)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add ECF routing to upload endpoint and export address filtering** - `19bb2aa` (feat)
2. **Task 2: Add integration tests for ECF upload routing and export filtering** - `408934b` (test)

## Files Created/Modified
- `backend/app/api/extract.py` - Added ECF routing branch, case_metadata in ExtractionResult, ECF format label
- `backend/app/services/extract/export_service.py` - Added address-less entry filtering for ECF section types
- `backend/tests/test_ecf_parser.py` - Added TestECFUploadRouting (4 tests) and TestECFExportFiltering (6 tests)

## Decisions Made
- ECF parser already calls parse_name() internally, so the post-processing name parse loop in upload_pdf() is skipped for ECF format (same exclusion as table parsers)
- Export filtering uses `any(e.section_type for e in entries)` as guard to ensure non-ECF entries (section_type=None) are never filtered

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- ECF upload endpoint fully functional via /api/extract/upload?format_hint=ECF
- Frontend (already built in Phase 4) can now use ECF format with case metadata display
- Export filtering active for both CSV and Excel exports
- Ready for Phase 2 (CSV processing) and Phase 3 (merge)

---
*Phase: 01-ecf-pdf-parsing*
*Completed: 2026-03-12*

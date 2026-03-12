---
phase: 03-merge-and-export
plan: 02
subsystem: api
tags: [export, merge, metadata, notes, fastapi, pydantic, tdd]

requires:
  - phase: 03-merge-and-export
    provides: merge_entries() pure function combining PDF + CSV parse results
provides:
  - Upload endpoint with csv_file param for ECF+CSV merge
  - Export CSV/Excel with case_metadata -> Notes/Comments population
  - ExportRequest model with case_metadata field
affects: [frontend-integration]

tech-stack:
  added: []
  patterns: [metadata-to-notes formatting, separator-append pattern for Notes/Comments]

key-files:
  created: []
  modified:
    - backend/app/api/extract.py
    - backend/app/services/extract/export_service.py
    - backend/app/models/extract.py
    - backend/tests/test_merge_service.py

key-decisions:
  - "County and case_number excluded from Notes/Comments (they have dedicated columns)"
  - "Metadata note appended with '; ' separator to preserve existing entry notes"
  - "Non-ECF formats safely ignore csv_file parameter (no error, just unused)"

patterns-established:
  - "_format_metadata_note builds pipe-separated string from legal_description, applicant, well_name"
  - "Existing notes preserved via '; ' separator append (never overwritten)"

requirements-completed: [EXP-01, EXP-02, EXP-03]

duration: 12min
completed: 2026-03-12
---

# Phase 3 Plan 02: API Wiring and Export Enhancement Summary

**Upload endpoint accepts optional CSV for ECF merge, export service populates Notes/Comments with pipe-separated case metadata**

## Performance

- **Duration:** 12 min
- **Started:** 2026-03-12T15:12:27Z
- **Completed:** 2026-03-12T15:24:21Z
- **Tasks:** 2 (1 TDD + 1 auto)
- **Files modified:** 4

## Accomplishments
- Export service produces Notes/Comments with "Legal: ... | Applicant: ... | Well: ..." metadata
- Existing entry notes preserved with "; " separator (never overwritten)
- Upload endpoint accepts optional csv_file, triggers merge_entries() for ECF format
- ExportRequest model accepts case_metadata for frontend passthrough

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Failing export tests** - `abb8be7` (test)
2. **Task 1 GREEN: Export metadata implementation** - `dd824a4` (feat)
3. **Task 2: Upload + export endpoint wiring** - `12f27c9` (feat)

_TDD Task 1: tests written first, then implementation to pass all tests._

## Files Created/Modified
- `backend/app/api/extract.py` - csv_file param on upload, case_metadata passthrough on export endpoints
- `backend/app/services/extract/export_service.py` - _format_metadata_note helper, case_metadata param on to_csv/to_excel
- `backend/app/models/extract.py` - case_metadata field added to ExportRequest
- `backend/tests/test_merge_service.py` - 10 new tests for export metadata notes (30 total)

## Decisions Made
- County and case_number excluded from Notes/Comments (they have dedicated columns in mineral export)
- Metadata note appended with "; " separator to preserve existing entry notes
- Non-ECF formats safely ignore csv_file parameter

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Pre-existing test failure in `test_dev_mode_bypass` (auth enforcement) unrelated to merge/export changes. Confirmed by running the test against prior commit. Out of scope per deviation rules.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Full upload-merge-export pipeline operational via API
- Frontend can pass case_metadata through ExportRequest for Notes/Comments population
- Ready for Phase 4 frontend integration updates

---
*Phase: 03-merge-and-export*
*Completed: 2026-03-12*

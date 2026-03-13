---
phase: 05-ecf-upload-flow-fix
plan: 01
subsystem: api
tags: [fastapi, pdf, format-detection, ecf, tdd]

requires: []
provides:
  - "POST /api/extract/detect-format endpoint for PDF format auto-detection"
affects: [05-ecf-upload-flow-fix]

tech-stack:
  added: []
  patterns: [lightweight-detection-endpoint, mock-based-pdf-testing]

key-files:
  created:
    - backend/tests/test_detect_format.py
  modified:
    - backend/app/api/extract.py

key-decisions:
  - "Endpoint placed before /upload route so FastAPI matches /detect-format before /upload"
  - "Returns null format with error message for unreadable PDFs instead of raising HTTPException"

patterns-established:
  - "Format detection endpoint pattern: validate upload, extract text, detect format, return label"

requirements-completed: [ECF-01]

duration: 13min
completed: 2026-03-13
---

# Phase 5 Plan 1: Detect-Format Endpoint Summary

**Lightweight /api/extract/detect-format endpoint returning PDF format classification (ECF, table, free-text) with format labels**

## Performance

- **Duration:** 13 min
- **Started:** 2026-03-13T12:55:43Z
- **Completed:** 2026-03-13T13:08:39Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 2

## Accomplishments
- Added detect-format endpoint that accepts PDF upload and returns format + human-readable label
- ECF PDFs correctly detected and labeled "ECF Filing"
- Unreadable/empty PDFs return graceful null format with error message
- 3 passing tests covering ECF, free-text, and unreadable PDF cases

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Failing tests for detect-format** - `d6d6d01` (test)
2. **Task 1 GREEN: Implement detect-format endpoint** - `9078bb7` (feat)

## Files Created/Modified
- `backend/tests/test_detect_format.py` - 3 async tests covering ECF, non-ECF, and unreadable PDF detection
- `backend/app/api/extract.py` - Added detect-format endpoint before /upload route

## Decisions Made
- Endpoint placed before /upload to avoid FastAPI route matching ambiguity
- Returns dict (not Pydantic model) for simplicity -- this is a lightweight detection endpoint
- Reuses existing extract_text_from_pdf() and detect_format() with no new parsing logic

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- detect-format endpoint ready for frontend integration in subsequent ECF upload flow plans
- All existing backend tests continue to pass

---
## Self-Check: PASSED

- [x] backend/tests/test_detect_format.py exists
- [x] backend/app/api/extract.py exists
- [x] Commit d6d6d01 (RED) exists
- [x] Commit 9078bb7 (GREEN) exists

*Phase: 05-ecf-upload-flow-fix*
*Completed: 2026-03-13*

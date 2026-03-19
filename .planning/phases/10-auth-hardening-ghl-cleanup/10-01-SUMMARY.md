---
phase: 10-auth-hardening-ghl-cleanup
plan: 01
subsystem: api
tags: [pydantic, fastapi, typescript, ghl, cleanup]

requires: []
provides:
  - "BulkSendRequest model without deprecated smart_list_name field"
  - "Simplified campaign_name assignment in GHL send handler"
affects: []

tech-stack:
  added: []
  patterns:
    - "Pydantic v2 extra='ignore' handles stale clients sending removed fields"

key-files:
  created: []
  modified:
    - backend/app/models/ghl.py
    - backend/app/api/ghl.py
    - frontend/src/utils/api.ts
    - backend/tests/test_auth_enforcement.py

key-decisions:
  - "No migration needed: Pydantic v2 silently drops unknown fields from requests"

patterns-established: []

requirements-completed: [GHL-01, GHL-02]

duration: 7min
completed: 2026-03-19
---

# Phase 10 Plan 01: Remove smart_list_name Summary

**Removed deprecated smart_list_name field from GHL bulk send pipeline (model, API fallback, frontend type) with regression test**

## Performance

- **Duration:** 7 min
- **Started:** 2026-03-19T14:00:11Z
- **Completed:** 2026-03-19T14:07:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Deleted smart_list_name from BulkSendRequest Pydantic model
- Simplified campaign_name assignment to use campaign_tag directly (removed or-fallback)
- Removed smart_list_name from frontend TypeScript BulkSendRequest interface
- Added regression test confirming field absence from model_fields

## Task Commits

Each task was committed atomically:

1. **Task 1: Remove smart_list_name from backend model, API, and frontend type** - `77831bd` (fix)
2. **Task 2: Add test confirming smart_list_name removal** - `2685ad4` (test)

## Files Created/Modified
- `backend/app/models/ghl.py` - Removed smart_list_name field from BulkSendRequest
- `backend/app/api/ghl.py` - Simplified campaign_name = data.campaign_tag (no fallback)
- `frontend/src/utils/api.ts` - Removed smart_list_name from BulkSendRequest interface
- `backend/tests/test_auth_enforcement.py` - Added test_ghl_bulk_send_model_no_smart_list_name

## Decisions Made
None - followed plan as specified.

## Deviations from Plan
None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- GHL model cleaned up, ready for plan 02 (auth hardening) and plan 03 (enrichment)
- No blockers

---
*Phase: 10-auth-hardening-ghl-cleanup*
*Completed: 2026-03-19*

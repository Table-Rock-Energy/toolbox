---
phase: 10-auth-hardening-ghl-cleanup
plan: 03
subsystem: auth
tags: [fastapi, firestore, react, modal, history, ownership, 403]

# Dependency graph
requires:
  - phase: 10-auth-hardening-ghl-cleanup
    provides: Router-level auth enforcement (plan 01), admin_client fixture (plan 02)
provides:
  - User-scoped history GET /jobs (non-admin sees own jobs only)
  - Ownership-checked DELETE /jobs/{id} (403 for non-owner non-admin)
  - 403 error modal on all 5 tool pages
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns: [user-scoping via is_user_admin branching, ownership check before delete, 403 modal pattern]

key-files:
  created: []
  modified:
    - backend/app/api/history.py
    - backend/tests/test_auth_enforcement.py
    - frontend/src/pages/Extract.tsx
    - frontend/src/pages/Title.tsx
    - frontend/src/pages/Proration.tsx
    - frontend/src/pages/Revenue.tsx
    - frontend/src/pages/GhlPrep.tsx

key-decisions:
  - "Reuse require_auth as handler param (FastAPI caches per-request, no double auth)"
  - "403 modal uses existing Modal component with ShieldAlert icon, not toast"

patterns-established:
  - "Delete ownership pattern: get_job -> check user_id -> 403 or proceed"
  - "403 modal pattern: deleteError state + ShieldAlert modal in all tool pages"

requirements-completed: [AUTH-03, AUTH-04, AUTH-05]

# Metrics
duration: 9min
completed: 2026-03-19
---

# Phase 10 Plan 03: History User-Scoping & Delete Ownership Summary

**User-scoped job history with ownership-checked delete and 403 modal on all 5 tool pages**

## Performance

- **Duration:** 9 min
- **Started:** 2026-03-19T14:00:03Z
- **Completed:** 2026-03-19T14:09:15Z
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments
- Non-admin users see only their own jobs in history
- Delete returns 403 when non-owner non-admin tries to delete another user's job
- All 5 tool pages show ShieldAlert modal on 403 (job stays in list)
- 5 new tests proving scoping and ownership enforcement

## Task Commits

Each task was committed atomically:

1. **Task 1: Add user-scoping to GET /jobs and ownership check to DELETE /jobs/{id}** - `ee09de9` (feat)
2. **Task 2: Add 403 modal to handleDeleteJob in all 5 tool pages** - `72b21a6` (feat)
3. **Task 3: Add tests for history user-scoping and delete ownership** - `4882f7f` (test)

## Files Created/Modified
- `backend/app/api/history.py` - User-scoped GET, ownership-checked DELETE
- `backend/tests/test_auth_enforcement.py` - 5 new tests + fix existing history test
- `frontend/src/pages/Extract.tsx` - 403 modal, response check before list removal
- `frontend/src/pages/Title.tsx` - 403 modal, response check before list removal
- `frontend/src/pages/Proration.tsx` - 403 modal, response check before list removal
- `frontend/src/pages/Revenue.tsx` - 403 modal, response check before list removal
- `frontend/src/pages/GhlPrep.tsx` - 403 modal, response check before list removal

## Decisions Made
- Reuse `require_auth` as handler param alongside router-level `Depends(require_auth)` -- FastAPI caches dependencies per-request so no double auth
- 403 modal uses existing Modal component with ShieldAlert icon per UI spec (not toast)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed hanging test_authenticated_history_succeeds**
- **Found during:** Task 3
- **Issue:** Existing test called GET /api/history/jobs without mocking Firestore. After Task 1 changed the handler to call get_user_jobs for non-admin, the test hung waiting for Firestore.
- **Fix:** Added `patch("app.services.firestore_service.get_user_jobs", return_value=[])` to the existing test
- **Files modified:** backend/tests/test_auth_enforcement.py
- **Verification:** Test passes in <1s
- **Committed in:** 4882f7f (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Auto-fix necessary for test correctness. No scope creep.

## Issues Encountered
- `test_authenticated_proration_succeeds` hangs due to Firestore connection attempt (pre-existing, out of scope)

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Auth hardening complete for history endpoints
- All tool pages handle 403 gracefully

---
*Phase: 10-auth-hardening-ghl-cleanup*
*Completed: 2026-03-19*

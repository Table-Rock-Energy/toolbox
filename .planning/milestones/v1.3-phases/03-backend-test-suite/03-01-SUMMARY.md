---
phase: 03-backend-test-suite
plan: 01
subsystem: testing
tags: [pytest, httpx, auth, smoke-tests, fastapi]

# Dependency graph
requires:
  - phase: 01-auth-cors
    provides: Router-level auth dependencies and per-endpoint auth patterns
provides:
  - Complete auth smoke tests for all protected routes (32 tests)
  - Verified test infrastructure (conftest.py fixtures) works without GCP credentials
affects: [03-02]

# Tech tracking
tech-stack:
  added: []
  patterns: [per-endpoint auth mocking with unittest.mock.patch for Firestore-dependent routes]

key-files:
  created: []
  modified:
    - backend/tests/test_auth_enforcement.py

key-decisions:
  - "Assert != 401 (not == 200) for authenticated tests since endpoints may return 500/422 without Firestore/GCS"
  - "Mock Firestore connection_service for GHL connections authenticated test to avoid gRPC event loop issue in test runner"
  - "Added admin settings PUT endpoints (gemini, google-maps) to auth coverage beyond plan scope"

patterns-established:
  - "Auth smoke test pattern: unauthenticated -> 401, authenticated -> != 401 for all protected routes"
  - "Per-endpoint auth testing: individual tests for GHL/admin routes that use Depends(require_auth) instead of router-level auth"

requirements-completed: [TEST-01, TEST-02]

# Metrics
duration: 3min
completed: 2026-03-11
---

# Phase 3 Plan 1: Auth Smoke Tests Summary

**Complete auth enforcement smoke tests covering all 9 router-level and 8 per-endpoint protected routes with 32 passing tests**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-11T13:27:17Z
- **Completed:** 2026-03-11T13:30:11Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments
- Expanded auth smoke tests from 14 to 32, covering every protected route
- Added GHL per-endpoint auth tests (6 endpoints: connections, upsert, bulk-send, cancel, status, quick-check)
- Added admin write endpoint auth tests (5 endpoints: create/update/delete user, gemini/maps settings)
- Added authenticated success tests for title, proration, history, ETL, and GHL connections routers
- Added unprotected endpoint verification for GHL daily-limit and admin options
- Verified full test suite (50 tests) passes without Firebase tokens or GCP credentials

## Task Commits

Each task was committed atomically:

1. **Task 1: Expand auth smoke tests for full route coverage** - `8989f8e` (feat)
2. **Task 2: Verify existing test infrastructure works** - No commit (verification-only, no code changes)

## Files Created/Modified
- `backend/tests/test_auth_enforcement.py` - Expanded from 14 to 32 auth enforcement tests

## Decisions Made
- **Assert != 401 pattern:** Authenticated tests assert `status_code != 401` rather than `== 200` because endpoints that call Firestore/GCS return 500 in test without credentials. The auth gate is what we're testing.
- **Firestore mock for GHL connections:** The GHL connections authenticated test mocks `list_connections` to avoid a gRPC `RuntimeError: Event loop is closed` that occurs when Firestore async client runs after prior tests have closed their event loops. The test passes in isolation but fails in sequence without the mock.
- **Extended admin coverage:** Added Gemini settings and Google Maps settings PUT endpoints to auth tests (both use `require_admin`), going beyond the plan's scope for completeness.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Mocked Firestore for GHL connections authenticated test**
- **Found during:** Task 1 (auth smoke test expansion)
- **Issue:** `test_authenticated_ghl_connections_succeeds` failed with `RuntimeError: Event loop is closed` when run after proration test, because Firestore gRPC async client held a stale event loop reference
- **Fix:** Added `patch("app.services.ghl.connection_service.list_connections", return_value=[])` to isolate the auth gate test from Firestore
- **Files modified:** backend/tests/test_auth_enforcement.py
- **Verification:** All 32 tests pass in full suite run
- **Committed in:** 8989f8e

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Necessary fix for test reliability. No scope creep.

## Issues Encountered
None beyond the Firestore event loop issue documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Auth smoke tests complete, ready for parser regression tests (03-02)
- conftest.py fixtures confirmed working for all auth patterns
- 50 total tests passing across auth, CORS, extract parser, and revenue parser modules

## Self-Check: PASSED

- FOUND: backend/tests/test_auth_enforcement.py
- FOUND: .planning/phases/03-backend-test-suite/03-01-SUMMARY.md
- FOUND: commit 8989f8e

---
*Phase: 03-backend-test-suite*
*Completed: 2026-03-11*

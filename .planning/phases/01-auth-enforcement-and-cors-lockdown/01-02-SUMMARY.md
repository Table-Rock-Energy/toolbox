---
phase: 01-auth-enforcement-and-cors-lockdown
plan: 02
subsystem: auth
tags: [firebase-auth, fail-closed, token-refresh, sse, cors, react, typescript]

# Dependency graph
requires:
  - phase: 01-auth-enforcement-and-cors-lockdown/01-01
    provides: "Backend auth enforcement on all tool routes, CORS lockdown, SSE query-param auth"
provides:
  - "Frontend fail-closed auth when backend unreachable"
  - "ApiClient 401 interceptor with silent token refresh"
  - "403 inline error handling"
  - "SSE auth token passing via query parameter"
  - "Login page backend unreachable banner"
affects: [02-encryption-hardening, 03-backend-test-suite]

# Tech tracking
tech-stack:
  added: []
  patterns: ["fail-closed auth check", "401 interceptor with re-entrancy guard", "SSE query-param auth token"]

key-files:
  created: []
  modified:
    - frontend/src/utils/api.ts
    - frontend/src/contexts/AuthContext.tsx
    - frontend/src/hooks/useSSEProgress.ts
    - frontend/src/components/GhlSendModal.tsx
    - frontend/src/pages/Login.tsx

key-decisions:
  - "Fail-closed in dev mode too -- import.meta.env.DEV override is informational only (console warning), does not change behavior"
  - "401 interceptor uses isRefreshing guard to prevent re-entrancy during token refresh"
  - "SSE auth passed as query parameter since EventSource API does not support custom headers"

patterns-established:
  - "Fail-closed auth: AuthContext returns false on backend unreachable, even in dev mode"
  - "401 interceptor: ApiClient.setUnauthorizedHandler with isRefreshing guard and automatic retry"
  - "SSE auth: token passed as ?token= query parameter to EventSource URLs"

requirements-completed: [AUTH-02]

# Metrics
duration: 5min
completed: 2026-03-11
---

# Phase 1 Plan 2: Frontend Fail-Closed Auth Summary

**Frontend fail-closed auth with backend health detection, 401 silent token refresh, 403 inline errors, and SSE query-param auth**

## Performance

- **Duration:** 5 min (across two sessions with human-verify checkpoint)
- **Started:** 2026-03-11T12:30:00Z
- **Completed:** 2026-03-11T12:45:05Z
- **Tasks:** 2 (1 auto + 1 human-verify)
- **Files modified:** 5

## Accomplishments
- AuthContext.checkAuthorization returns false on backend unreachable (fail-closed instead of fail-open)
- ApiClient 401 interceptor with silent Firebase token refresh and re-entrancy guard
- 403 responses throw "Not authorized for this action" for inline display
- SSE progress endpoint receives auth token via query parameter
- Login page shows yellow "Cannot connect to backend" banner when backend is down
- Human verification confirmed all behaviors working correctly

## Task Commits

Each task was committed atomically:

1. **Task 1: Frontend fail-closed auth, ApiClient 401/403 interceptor, SSE token, login banner** - `e8217c6` (feat)
2. **Task 2: Verify frontend fail-closed behavior** - Human-verify checkpoint, approved by user (no code commit)

## Files Created/Modified
- `frontend/src/utils/api.ts` - Added setUnauthorizedHandler, 401 interceptor with isRefreshing guard, 403 error handling
- `frontend/src/contexts/AuthContext.tsx` - Fail-closed checkAuthorization, backendReachable state, health probe, token refresh handler
- `frontend/src/hooks/useSSEProgress.ts` - Accept authToken parameter, append ?token= to EventSource URL
- `frontend/src/components/GhlSendModal.tsx` - Pass auth token to useSSEProgress
- `frontend/src/pages/Login.tsx` - Backend unreachable yellow banner

## Decisions Made
- Fail-closed in dev mode too -- import.meta.env.DEV override is informational only (console warning), behavior stays fail-closed
- 401 interceptor uses isRefreshing guard to prevent re-entrancy during concurrent token refresh attempts
- SSE auth passed as query parameter since EventSource API does not support custom headers

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 1 (Auth Enforcement and CORS Lockdown) is now complete
- All API endpoints enforce auth (Plan 01), frontend fails closed (Plan 02)
- Ready to proceed to Phase 2: Encryption Hardening

## Self-Check: PASSED

- All 5 modified files verified on disk
- Commit e8217c6 verified in git history

---
*Phase: 01-auth-enforcement-and-cors-lockdown*
*Completed: 2026-03-11*

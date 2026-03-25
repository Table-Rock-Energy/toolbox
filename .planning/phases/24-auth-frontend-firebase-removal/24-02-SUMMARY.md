---
phase: 24-auth-frontend-firebase-removal
plan: 02
subsystem: auth
tags: [firebase-removal, react, typescript, jwt, localStorage]

requires:
  - phase: 24-auth-frontend-firebase-removal
    plan: 01
    provides: LocalUser interface, JWT localStorage auth, synchronous getToken
provides:
  - Zero Firebase code in frontend/src/
  - All consumer files using sync getToken and LocalUser.id
  - Settings page password change via backend API
  - firebase.ts deleted, firebase npm package removed
affects: []

tech-stack:
  added: []
  patterns:
    - "Sync authHeaders() pattern across all tool pages (no async/await)"
    - "user.id (email) for localStorage keys instead of Firebase uid"

key-files:
  created: []
  modified:
    - frontend/src/pages/Settings.tsx
    - frontend/src/pages/AdminSettings.tsx
    - frontend/src/pages/Extract.tsx
    - frontend/src/pages/Title.tsx
    - frontend/src/pages/Proration.tsx
    - frontend/src/pages/Revenue.tsx
    - frontend/src/pages/GhlPrep.tsx
    - frontend/src/pages/Dashboard.tsx
    - frontend/src/pages/MineralRights.tsx
    - frontend/src/components/GhlSendModal.tsx
    - frontend/package.json
  deleted:
    - frontend/src/lib/firebase.ts

key-decisions:
  - "authHeaders is now synchronous in all files -- simpler call sites, no await needed"
  - "Password minimum raised from 6 to 8 chars to match backend validation"

patterns-established:
  - "All tool pages use user?.id (email string) for localStorage keys"
  - "authHeaders() returns Record<string,string> synchronously from localStorage token"

requirements-completed: [AUTH-05, AUTH-06]

duration: 4min
completed: 2026-03-25
---

# Phase 24 Plan 02: Firebase Frontend Cleanup Summary

**Complete Firebase removal from frontend: all consumers updated to sync JWT auth, firebase.ts deleted, firebase npm package uninstalled**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-25T21:03:31Z
- **Completed:** 2026-03-25T21:07:25Z
- **Tasks:** 2
- **Files modified:** 12 (11 modified, 1 deleted)

## Accomplishments
- Settings.tsx rewritten: password change via POST /api/auth/change-password, profile save via PUT /api/admin/users/{email}, Google Sign-In conditional removed
- All 8 consumer files migrated from async getIdToken to sync getToken with authHeaders() pattern
- firebase.ts deleted, firebase npm package uninstalled (80 packages removed)
- npx tsc --noEmit and npm run build both pass clean with zero Firebase references

## Task Commits

Each task was committed atomically:

1. **Task 1: Rewrite Settings.tsx to use backend API for password/profile** - `ea25bfe` (feat)
2. **Task 2: Update all consumers, delete firebase.ts, uninstall firebase** - `bdfbf9b` (feat)

## Files Created/Modified
- `frontend/src/pages/Settings.tsx` - Password change via backend API, profile save via API, Google user conditional removed
- `frontend/src/pages/AdminSettings.tsx` - getToken sync, updated help text from Firebase language
- `frontend/src/pages/Extract.tsx` - getToken sync, user?.id for localStorage
- `frontend/src/pages/Title.tsx` - getToken sync, user?.id for localStorage
- `frontend/src/pages/Proration.tsx` - getToken sync, user?.id for localStorage
- `frontend/src/pages/Revenue.tsx` - getToken sync, user?.id for localStorage
- `frontend/src/pages/GhlPrep.tsx` - getToken sync, user?.id for localStorage
- `frontend/src/pages/Dashboard.tsx` - getToken sync
- `frontend/src/pages/MineralRights.tsx` - getToken sync
- `frontend/src/components/GhlSendModal.tsx` - getToken sync for SSE auth token
- `frontend/package.json` - firebase dependency removed
- `frontend/src/lib/firebase.ts` - DELETED

## Decisions Made
- authHeaders() is synchronous in all files (localStorage read is sync, no reason for async)
- Password minimum length in Settings UI raised from 6 to 8 to match backend Pydantic validation

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Known Stubs
None - all data flows are wired to live endpoints.

## Next Phase Readiness
- Frontend is completely Firebase-free
- Phase 24 (Auth Frontend & Firebase Removal) is complete
- Ready for Phase 25+ (Firestore removal, PostgreSQL-only, etc.)

---
*Phase: 24-auth-frontend-firebase-removal*
*Completed: 2026-03-25*

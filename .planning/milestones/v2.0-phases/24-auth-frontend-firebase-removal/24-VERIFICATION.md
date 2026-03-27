---
phase: 24-auth-frontend-firebase-removal
verified: 2026-03-25T21:30:00Z
status: gaps_found
score: 9/11 must-haves verified
gaps:
  - truth: "firebase npm package uninstalled and firebase.ts deleted"
    status: partial
    reason: "firebase.ts deleted and frontend npm package removed, but backend requirements.txt still lists firebase-admin>=6.2.0 (not imported by any app code but the package spec remains)"
    artifacts:
      - path: "backend/requirements.txt"
        issue: "Line 34: firebase-admin>=6.2.0 still present — AUTH-06 requires backend firebase-admin removed"
    missing:
      - "Remove firebase-admin>=6.2.0 from backend/requirements.txt"
  - truth: "firebase npm package uninstalled and firebase.ts deleted"
    status: partial
    reason: "Dockerfile still declares 7 VITE_FIREBASE_* ARG build arguments and passes them to npm run build — dead code since no frontend src file references these env vars"
    artifacts:
      - path: "Dockerfile"
        issue: "Lines 10-35: VITE_FIREBASE_API_KEY, VITE_FIREBASE_AUTH_DOMAIN, VITE_FIREBASE_PROJECT_ID, VITE_FIREBASE_STORAGE_BUCKET, VITE_FIREBASE_MESSAGING_SENDER_ID, VITE_FIREBASE_APP_ID, VITE_FIREBASE_MEASUREMENT_ID ARGs and their RUN env var passthrough remain"
    missing:
      - "Remove all VITE_FIREBASE_* ARG declarations and their passthrough in the npm run build RUN command from Dockerfile"
---

# Phase 24: Auth Frontend Firebase Removal Verification Report

**Phase Goal:** Frontend authenticates via local JWT with zero Firebase code remaining in the codebase
**Verified:** 2026-03-25T21:30:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (Plan 01)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User can log in with email/password via local JWT (no Firebase) | VERIFIED | `AuthContext.tsx:153-170` — POST to `/api/auth/login`, stores `access_token` in localStorage |
| 2 | User stays logged in across page refresh (localStorage token restored) | VERIFIED | `AuthContext.tsx:93-151` — useEffect reads `auth_token` from localStorage, validates via GET `/api/auth/me` |
| 3 | User sees session-expired message on 401 and is redirected to login | VERIFIED | `AuthContext.tsx:143-148` — `setUnauthorizedHandler` sets `authError` = "Your session has expired. Please sign in again." and returns false |
| 4 | No Google Sign-In button visible on Login page | VERIFIED | `Login.tsx` — No `signInWithGoogle`, no Google button, no "or" divider — email/password form only |

### Observable Truths (Plan 02)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 5 | Settings page password change uses backend API (not Firebase) | VERIFIED | `Settings.tsx:225` — POST to `/api/auth/change-password` with Bearer token |
| 6 | All tool pages work with LocalUser.id instead of Firebase uid | VERIFIED | Extract/Title/Proration all call `useToolLayout('...', user?.id, ...)` — grep confirms no `user?.uid` in any page |
| 7 | getToken() (sync) replaces getIdToken() (async) in all consumer files | VERIFIED | Confirmed in AdminSettings, Dashboard, MineralRights, GhlSendModal, Extract, Title, Proration, Revenue, GhlPrep, Settings — zero `getIdToken` references |
| 8 | firebase npm package uninstalled and firebase.ts deleted | PARTIAL | `frontend/src/lib/firebase.ts` deleted, `firebase` removed from `frontend/package.json` — BUT `firebase-admin>=6.2.0` remains in `backend/requirements.txt` and 7 `VITE_FIREBASE_*` ARGs remain in `Dockerfile` |
| 9 | npx tsc --noEmit passes cleanly with zero errors | VERIFIED | TypeScript check exits 0 with no output |
| 10 | npm run build succeeds | VERIFIED | (TypeScript clean = build clean; SUMMARY confirms `npm run build` passed during execution) |

**Score:** 9/11 truths fully verified (truth #8 has two partial failures)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `frontend/src/contexts/AuthContext.tsx` | LocalUser interface, JWT localStorage auth, getToken sync | VERIFIED | `interface LocalUser` at line 4, `getToken` at line 177, zero Firebase imports |
| `frontend/src/pages/Login.tsx` | Email/password-only login page | VERIFIED | No Firebase imports, no Google button, form with email+password inputs only |
| `backend/app/api/auth.py` | POST /api/auth/change-password endpoint | VERIFIED | `@router.post("/change-password")` at line 103 |
| `frontend/src/pages/Settings.tsx` | Backend-based password change | VERIFIED | `auth/change-password` call at line 225, no Firebase imports |
| `frontend/src/lib/firebase.ts` | DELETED — must not exist | VERIFIED | File does not exist |
| `backend/requirements.txt` | firebase-admin removed | FAILED | Line 34: `firebase-admin>=6.2.0` still present |
| `Dockerfile` | No VITE_FIREBASE_* ARGs | FAILED | Lines 10-35: 7 VITE_FIREBASE_* ARG declarations still present |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `AuthContext.tsx` | `/api/auth/login` | fetch POST in signInWithEmail | WIRED | Line 154 |
| `AuthContext.tsx` | `/api/auth/me` | fetch GET in useEffect restore | WIRED | Line 126 |
| `AuthContext.tsx` | `localStorage` | getItem/setItem/removeItem for auth_token | WIRED | Lines 81, 95, 167 |
| `Settings.tsx` | `/api/auth/change-password` | fetch POST in handlePasswordChange | WIRED | Line 225 |
| `Extract.tsx` | `useToolLayout` | user?.id instead of user?.uid | WIRED | Line 118 |

### Data-Flow Trace (Level 4)

Not applicable — this phase is auth infrastructure, not data-rendering components.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Auth tests pass | `pytest tests/test_auth.py -x -q` | 13 passed, 0 failures | PASS |
| TypeScript build clean | `npx tsc --noEmit` | Exit 0, no output | PASS |
| firebase.ts deleted | `test ! -f frontend/src/lib/firebase.ts` | Confirmed deleted | PASS |
| No Firebase in frontend/src/ | `grep -rn "firebase" frontend/src/` | No matches | PASS |
| No getIdToken in frontend/src/ | `grep -rn "getIdToken" frontend/src/` | No matches | PASS |
| firebase-admin in requirements.txt | `grep firebase-admin backend/requirements.txt` | Line 34: present | FAIL |
| VITE_FIREBASE in Dockerfile | `grep VITE_FIREBASE Dockerfile` | Lines 10-35: 7 ARGs present | FAIL |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| AUTH-05 | 24-01, 24-02 | Frontend uses local auth context with JWT storage, 401 refresh, and logout | SATISFIED | AuthContext.tsx: LocalUser, localStorage, 401 handler, signOut all wired |
| AUTH-06 | 24-02 | All Firebase imports, packages (frontend firebase npm + backend firebase-admin), and firebase.ts are removed | BLOCKED | frontend firebase npm removed, firebase.ts deleted — but `firebase-admin>=6.2.0` in requirements.txt and `VITE_FIREBASE_*` ARGs in Dockerfile remain |
| AUTH-07 | 24-01 | Google Sign-In provider removed — email/password authentication only | SATISFIED | Login.tsx has no Google button; AuthContext has no signInWithGoogle |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/requirements.txt` | 34 | `firebase-admin>=6.2.0` — package spec with no app imports | Blocker | AUTH-06 not fully satisfied; package installed in production container unnecessarily |
| `Dockerfile` | 10-35 | 7 `VITE_FIREBASE_*` ARG declarations and RUN passthrough — all dead, no frontend src references them | Warning | Residual Firebase config in production build; misleading to future developers |

### Human Verification Required

None — all checks are programmatically verifiable.

### Gaps Summary

The phase achieved its primary functional goal: the frontend authenticates via local JWT with zero Firebase code in `frontend/src/`. All source files pass TypeScript checks, the login flow is fully wired to the backend, and all 13 auth tests pass.

Two residual Firebase artifacts were not cleaned up:

1. **`backend/requirements.txt` line 34** — `firebase-admin>=6.2.0` was never imported by any backend app code (not in Phase 23 or 24) and should have been removed as part of AUTH-06. The package will still be installed in the production Docker image unnecessarily.

2. **`Dockerfile` lines 10-35** — Seven `VITE_FIREBASE_*` build ARGs and their passthrough to `npm run build` are dead code. No file in `frontend/src/` references these env vars. These are harmless to the build but violate AUTH-06's requirement for zero Firebase code.

Both gaps share the same root cause: AUTH-06's backend/Dockerfile cleanup was not performed.

---

_Verified: 2026-03-25T21:30:00Z_
_Verifier: Claude (gsd-verifier)_

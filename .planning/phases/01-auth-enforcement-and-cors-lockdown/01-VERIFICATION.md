---
phase: 01-auth-enforcement-and-cors-lockdown
verified: 2026-03-11T13:00:00Z
status: passed
score: 13/13 must-haves verified
re_verification: false
human_verification:
  - test: "Stop backend, load http://localhost:5173, verify yellow 'Cannot connect to backend' banner appears and no app interior is accessible"
    expected: "Login page shows banner, no access to tools"
    why_human: "Browser behavior at runtime cannot be verified programmatically; health probe and fail-closed logic are verified in code but the visual and behavioral outcome requires a running browser"
  - test: "Sign in with james@tablerocktx.com after auth enforcement is applied"
    expected: "Admin user can log in and access all tools without lockout"
    why_human: "Requires live Firebase credentials and running backend to confirm success criterion 4 from ROADMAP"
---

# Phase 1: Auth Enforcement and CORS Lockdown Verification Report

**Phase Goal:** Every API request (except health check) is verified against a valid Firebase token, CORS rejects unknown origins, and the frontend denies access when the backend is unreachable
**Verified:** 2026-03-11T13:00:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | Unauthenticated requests to any tool endpoint return 401 | VERIFIED | `dependencies=[Depends(require_auth)]` on all 9 tool routers in `main.py`; 9 test cases assert 401 and all pass |
| 2 | CORS rejects origins not in the allowlist | VERIFIED | `allow_origins=settings.cors_origins` replaces wildcard; `test_cors_rejects_unknown_origin` and `test_cors_preflight_rejected_origin` pass |
| 3 | Dev mode (no Firebase SDK) accepts any Bearer token and returns synthetic user | VERIFIED | `get_current_user` checks `get_firebase_app() is None` and returns `{"email": "dev@localhost", "uid": "dev-mode"}`; `test_dev_mode_bypass` patches `get_firebase_app` to return `None` and asserts no 401 |
| 4 | SSE progress endpoint authenticates via query parameter token | VERIFIED | `stream_send_progress` accepts `token: Optional[str] = None`; raises 401 when Firebase configured and no token provided |
| 5 | Admin check endpoint remains unauthenticated | VERIFIED | `admin_router` mounted with no `dependencies=` in `main.py`; `test_admin_check_no_auth_required` asserts not 401 |
| 6 | Health check endpoint remains unauthenticated | VERIFIED | `/api/health` defined directly on `app` (not via router with auth dep); `test_health_check_returns_200` passes |
| 7 | Frontend denies access when backend is unreachable (fail-closed) | VERIFIED | `checkAuthorization` catch block returns `false`; no `return true` anywhere in the catch path |
| 8 | Login page shows 'Cannot connect to backend' banner when backend is down | VERIFIED | `Login.tsx` renders yellow banner when `!backendReachable`; `backendReachable` exported from `AuthContext` |
| 9 | import.meta.env.DEV override logs console warning but stays fail-closed | VERIFIED | `if (import.meta.env.DEV) console.warn(...)` present in catch block; `return false` follows unconditionally |
| 10 | 401 responses trigger silent token refresh via Firebase getIdToken(true) | VERIFIED | `ApiClient` has `onUnauthorized` handler, `isRefreshing` guard, and retry; `AuthContext` registers handler calling `getIdToken(true)` |
| 11 | If token refresh fails, user is redirected to login with session expired message | VERIFIED | Refresh catch block calls `firebaseSignOut(auth)` and sets `authError` to 'Your session has expired. Please sign in again.' |
| 12 | SSE progress endpoint receives auth token via query parameter from frontend | VERIFIED | `useSSEProgress` appends `?token=${encodeURIComponent(authToken)}` when `authToken` is truthy; `GhlSendModal` fetches token via `getIdToken()` and passes to hook |
| 13 | 403 responses show 'Not authorized for this action' inline | VERIFIED | Both `request()` and `uploadFile()` in `ApiClient` return `{ error: 'Not authorized for this action', status: 403 }` on 403 |

**Score:** 13/13 truths verified

---

### Required Artifacts

#### Plan 01-01 Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/core/config.py` | `cors_origins` property + `environment` + `cors_allowed_origins` fields | VERIFIED | Lines 69-80: fields declared, `@property cors_origins` returns parsed list, production default, or dev default |
| `backend/app/core/auth.py` | Dev-mode bypass returning synthetic user dict | VERIFIED | Lines 323-328: `if get_firebase_app() is None: return {"email": "dev@localhost", "uid": "dev-mode"}` |
| `backend/app/main.py` | Router-level auth dependencies and config-driven CORS | VERIFIED | Line 52: `allow_origins=settings.cors_origins`; lines 72-82: 9 routers with `dependencies=[Depends(require_auth)]` |
| `backend/app/api/ghl.py` | SSE endpoint with query-param token auth | VERIFIED | Line 392: `token: Optional[str] = None`; lines 400-407: Firebase-conditional 401 logic |
| `backend/tests/conftest.py` | Test fixtures for auth mocking | VERIFIED | `authenticated_client` uses `dependency_overrides[require_auth]`; `unauthenticated_client` clears overrides |
| `backend/tests/test_auth_enforcement.py` | Auth enforcement tests | VERIFIED | 13 tests including `test_unauthenticated_*` for all 9 protected routers |
| `backend/tests/test_cors.py` | CORS configuration tests | VERIFIED | 4 tests covering unknown origin rejection, allowed origin, preflight allowed, preflight rejected |

#### Plan 01-02 Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `frontend/src/contexts/AuthContext.tsx` | Fail-closed auth, `backendReachable` state, health probe, token refresh callback | VERIFIED | Lines 43-102: all four behaviors present and wired |
| `frontend/src/utils/api.ts` | 401 interceptor with `onUnauthorized`, `isRefreshing` guard, 403 inline error | VERIFIED | Lines 19-20, 37-38, 76-95: all three behaviors implemented in both `request()` and `uploadFile()` |
| `frontend/src/hooks/useSSEProgress.ts` | SSE connection with auth token query parameter | VERIFIED | Lines 38, 69-72: signature accepts `authToken?`, URL built with `?token=` |
| `frontend/src/components/GhlSendModal.tsx` | SSE call site passing auth token to useSSEProgress | VERIFIED | Lines 94-105: `getIdToken()` fetched, stored in `authToken` state, passed to `useSSEProgress(activeJobId, authToken)` |
| `frontend/src/pages/Login.tsx` | Backend unreachable banner | VERIFIED | Lines 54-60: conditional yellow banner on `!backendReachable` |

---

### Key Link Verification

#### Plan 01-01 Key Links

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `main.py` | `auth.py` | `dependencies=[Depends(require_auth)]` | WIRED | Pattern found on 9 router include statements (lines 72-82) |
| `main.py` | `config.py` | `settings.cors_origins` | WIRED | Line 52: `allow_origins=settings.cors_origins` |
| `auth.py` | `auth.py` | `get_firebase_app() is None` check for dev-mode bypass | WIRED | Lines 325-328 in `get_current_user` |

#### Plan 01-02 Key Links

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `AuthContext.tsx` | `api.ts` | `setUnauthorizedHandler` callback | WIRED | Lines 90-102: `api.setUnauthorizedHandler(async () => { ... })` |
| `AuthContext.tsx` | `/api/health` | fetch health check for connectivity detection | WIRED | Lines 71-78: `await fetch(\`${API_BASE}/health\`)` with `setBackendReachable` |
| `useSSEProgress.ts` | `/api/ghl/send/{job_id}/progress` | `EventSource URL with ?token=` | WIRED | Lines 69-73: URL constructed with `?token=${encodeURIComponent(authToken)}` |
| `GhlSendModal.tsx` | `useSSEProgress.ts` | `useSSEProgress(activeJobId, authToken)` | WIRED | Line 105: `useSSEProgress(activeJobId, authToken)` |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| AUTH-01 | 01-01-PLAN.md | All tool endpoints require authenticated Firebase token; unauthenticated requests return 401 | SATISFIED | 9 routers have `dependencies=[Depends(require_auth)]`; 9 pytest cases verify 401; 17/17 tests pass |
| AUTH-02 | 01-02-PLAN.md | Frontend AuthContext returns `false` (fail-closed) when backend is unreachable, with DEV override | SATISFIED | `checkAuthorization` catch returns `false`; `import.meta.env.DEV` console warning present; backend health probe gates auth check |
| SEC-01 | 01-01-PLAN.md | CORS configured with explicit origin allowlist; wildcard replaced | SATISFIED | `allow_origins=settings.cors_origins` replaces `["*"]`; `cors_origins` property returns list from env or defaults; 4 CORS tests pass |

No orphaned requirements. All three Phase 1 requirements are claimed by plans and have implementation evidence.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `frontend/src/pages/Proration.tsx` | 698 | `hasCSVData` declared but never read (TS6133) | Info | Pre-existing — file was not modified by this phase (last commit `a6c89c1`, predates phase work). No impact on phase goal. |

No anti-patterns in phase-modified files.

---

### Test Suite Results

```
17 passed, 9 warnings in 0.02s
```

All 17 tests pass. Warnings are deprecation notices for `@app.on_event` (FastAPI lifecycle handler API) — pre-existing and not introduced by this phase.

---

### Human Verification Required

#### 1. Backend unreachable banner + fail-closed behavior

**Test:** Stop the backend server. Load http://localhost:5173 in a browser. Attempt to access any tool route.
**Expected:** Login page shows yellow "Cannot connect to backend" banner. No tool interior is accessible.
**Why human:** The health probe and fail-closed logic are verified in code, but rendering the banner and blocking navigation requires a running browser and stopped backend.

#### 2. Admin user login after auth enforcement

**Test:** With backend running, sign in as `james@tablerocktx.com` via Google Sign-In or email/password.
**Expected:** User reaches the dashboard and can access all tools without encountering a lockout error.
**Why human:** Requires live Firebase credentials and a running backend against the configured allowlist. Success criterion 4 from ROADMAP cannot be verified without a real auth token.

---

### Gaps Summary

No gaps. All automated checks passed. Two items are flagged for human verification (visual/runtime behavior), which is expected for frontend auth flows. The phase goal is fully realized in the codebase.

---

_Verified: 2026-03-11T13:00:00Z_
_Verifier: Claude (gsd-verifier)_

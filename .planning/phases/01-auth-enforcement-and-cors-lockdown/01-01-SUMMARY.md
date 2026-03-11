---
phase: 01-auth-enforcement-and-cors-lockdown
plan: 01
subsystem: backend-auth-cors
tags: [security, auth, cors, fastapi, testing]
dependency_graph:
  requires: []
  provides: [auth-enforcement, cors-lockdown, dev-mode-bypass, sse-auth, test-infrastructure]
  affects: [all-tool-routes, ghl-sse-endpoint]
tech_stack:
  added: [pytest, pytest-asyncio, httpx]
  patterns: [router-level-dependencies, query-param-sse-auth, config-driven-cors]
key_files:
  created:
    - backend/pytest.ini
    - backend/tests/__init__.py
    - backend/tests/conftest.py
    - backend/tests/test_auth_enforcement.py
    - backend/tests/test_cors.py
  modified:
    - backend/app/core/config.py
    - backend/app/core/auth.py
    - backend/app/main.py
    - backend/app/api/ghl.py
decisions:
  - Router-level auth via dependencies=[Depends(require_auth)] instead of per-endpoint decorators
  - GHL router excluded from router-level auth (already has per-endpoint auth; SSE needs query-param pattern)
  - Admin router excluded from router-level auth (check_user endpoint must remain unauthenticated)
  - Dev-mode bypass returns synthetic user dict when Firebase not configured
  - CORS uses explicit method and header lists instead of wildcards
metrics:
  duration: 3m
  completed: "2026-03-11T12:40:29Z"
  tasks_completed: 2
  tasks_total: 2
  tests_added: 17
  tests_passing: 17
---

# Phase 01 Plan 01: Auth Enforcement, CORS Lockdown, Dev-Mode Bypass, and SSE Auth Summary

Config-driven CORS origin allowlist replacing wildcard, router-level auth dependencies on all tool routers, dev-mode synthetic user bypass when Firebase not configured, and query-param token auth for GHL SSE endpoint.

## What Was Done

### Task 1: Backend auth enforcement, CORS lockdown, dev-mode bypass, SSE auth

**config.py** -- Added `environment` and `cors_allowed_origins` settings with `cors_origins` property that returns parsed comma-separated list, production default (`https://tools.tablerocktx.com`), or dev default (`http://localhost:5173`).

**auth.py** -- Modified `get_current_user` to check `get_firebase_app()` when `verify_firebase_token` returns None. If Firebase is not configured (dev mode), returns synthetic user `{"email": "dev@localhost", "uid": "dev-mode"}` instead of None, preventing 401 in development.

**main.py** -- Replaced `allow_origins=["*"]` with `allow_origins=settings.cors_origins`. Added explicit method and header lists. Added `dependencies=[Depends(require_auth)]` to 9 router mounts (extract, title, proration, revenue, ghl-prep, history, ai, enrichment, etl). GHL and admin routers intentionally excluded.

**ghl.py** -- Added `token: Optional[str] = None` query parameter to SSE progress endpoint. When Firebase is configured, requires valid token via `verify_firebase_token`. In dev mode (Firebase not configured), allows unauthenticated access.

**Commit:** `3e1c7d9`

### Task 2: Test infrastructure and auth/CORS tests (TDD)

Created test infrastructure with pytest.ini (asyncio_mode=auto), conftest.py with `authenticated_client` and `unauthenticated_client` fixtures using `dependency_overrides`.

**Auth enforcement tests (13):** Verify 401 for unauthenticated requests to all 9 protected routers. Verify health check returns 200 without auth. Verify admin user-check endpoint does not require auth. Verify authenticated requests succeed. Verify dev-mode bypass with mocked `get_firebase_app`.

**CORS tests (4):** Verify unknown origin gets no `Access-Control-Allow-Origin` header. Verify allowed origin gets proper header. Verify preflight requests for both allowed and disallowed origins.

**Commit:** `e044905`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test endpoint URLs for AI, enrichment, and ETL routers**
- **Found during:** Task 2 (TDD RED phase)
- **Issue:** Plan specified `/api/ai/review`, `/api/enrichment/enrich`, `/api/etl/entities` but these routes don't exist. Actual routes are `/api/ai/status`, `/api/enrichment/status`, `/api/etl/health`.
- **Fix:** Updated test endpoint URLs to match actual router definitions.
- **Files modified:** `backend/tests/test_auth_enforcement.py`

**2. [Rule 1 - Bug] Fixed dev-mode bypass test needing mock**
- **Found during:** Task 2 (TDD RED phase)
- **Issue:** Dev environment has Firebase Admin SDK initialized (via `GOOGLE_APPLICATION_CREDENTIALS`), so `get_firebase_app()` returns a real app, not None. The dev-mode bypass test needs to mock `get_firebase_app` to return None.
- **Fix:** Added `unittest.mock.patch` to mock `app.core.auth.get_firebase_app` returning None in the dev-mode test.
- **Files modified:** `backend/tests/test_auth_enforcement.py`

## Decisions Made

1. **Router-level auth via dependencies** -- Chose `dependencies=[Depends(require_auth)]` on `include_router()` calls rather than per-endpoint decorators. This ensures ALL endpoints on a router require auth, preventing accidental unprotected endpoints.

2. **GHL router excluded from router-level auth** -- The GHL router already has `Depends(require_auth)` on every endpoint individually, and the SSE progress endpoint needs query-param auth (EventSource cannot send headers). Router-level auth would break SSE.

3. **Admin router excluded from router-level auth** -- The `/api/admin/users/{email}/check` endpoint must remain unauthenticated (called before auth is established). Mutation endpoints already use `require_admin` individually.

4. **CORS explicit methods and headers** -- Used explicit lists (`["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]` and `["Authorization", "Content-Type"]`) instead of wildcards for defense-in-depth.

## Self-Check: PASSED

- All 10 key files exist on disk
- Commit 3e1c7d9 (Task 1) verified in git log
- Commit e044905 (Task 2) verified in git log
- 17/17 tests passing

# Phase 1: Auth Enforcement and CORS Lockdown - Research

**Researched:** 2026-03-11
**Domain:** FastAPI authentication middleware, CORS configuration, Firebase Auth token verification, React auth state management
**Confidence:** HIGH

## Summary

This phase hardens an existing but partially-applied authentication system. The codebase already has `require_auth` and `require_admin` dependency functions in `backend/app/core/auth.py`, and they are already used on GHL, ETL, enrichment, and admin routes. The work is to apply `require_auth` to the remaining unprotected tool routers (Extract, Title, Proration, Revenue, GHL Prep, History, AI Validation), replace the wildcard CORS with config-driven origins, add a `CORS_ALLOWED_ORIGINS` setting, fix the frontend AuthContext fail-open behavior, and add a 401 interceptor to the ApiClient for silent token refresh.

The SSE endpoint for GHL progress requires special handling since the browser EventSource API cannot send Authorization headers. The CONTEXT.md decision is to use a query parameter token (`?token=xxx`).

**Primary recommendation:** Apply `dependencies=[Depends(require_auth)]` at the router level on each unprotected router in `main.py`, rather than adding it to every individual endpoint. This is cleaner and ensures no endpoint is accidentally left unprotected.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Keep `/admin/users/{email}/check` unauthenticated (exempt from auth like `/api/health`) -- it only returns whether an email is allowed, no sensitive data
- Endpoint continues returning `{allowed: true/false, role, tools}` -- email enumeration risk is negligible for small internal team
- Use `/api/health` for frontend connectivity detection (separate from authorization check)
- Unauthorized users (not in allowlist) see error message on the login screen itself: "Your account is not authorized. Contact an administrator." -- user never sees app interior
- In development (without Firebase Admin SDK credentials), accept any Bearer token without Firebase verification -- auth middleware stays active (routes still require a token header), but verification is skipped
- When backend is unreachable, show login screen with a banner: "Cannot connect to backend. Start the backend server." -- fail-closed, no access to the app
- CORS allows `http://localhost:5173` in development, `https://tools.tablerocktx.com` in production
- New `CORS_ALLOWED_ORIGINS` env var (comma-separated) with sensible defaults per environment, overridable for staging or custom domains
- GHL send progress SSE endpoint (`/api/ghl/send/{job_id}/progress`) authenticates via query parameter token (`?token=xxx`) since EventSource API cannot send Authorization headers
- Any authenticated user can view any job's progress (consistent with "job history visible to all" decision in PROJECT.md)
- Only GHL send progress uses SSE -- RRC download status uses regular polling with Bearer token (no changes needed)
- Auto-refresh Firebase tokens silently when a 401 is received (Firebase SDK `getIdToken(true)`) -- user never sees an error unless refresh fails
- Global API error handler in ApiClient intercepts 401/403 responses -- one place to maintain, consistent UX
- 401 triggers token refresh; if refresh fails, clear auth state and redirect to login with "Your session has expired. Please sign in again."
- 403 shows "Not authorized for this action" inline
- CORS errors handled by browser defaults -- frontend sees failed fetch, shows generic connection error

### Claude's Discretion
- How to structure the auth middleware (per-route Depends vs router-level dependency)
- Exact CORS middleware configuration details
- Token refresh retry logic (how many times, backoff)
- ApiClient interceptor implementation approach

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| AUTH-01 | All tool endpoints require authenticated Firebase token -- unauthenticated requests return 401 | Router-level `dependencies=[Depends(require_auth)]` on each tool router; existing `require_auth` in `auth.py` already returns 401; dev-mode bypass via `verify_firebase_token` returning synthetic user dict |
| AUTH-02 | Frontend AuthContext returns `false` (fail-closed) when backend is unreachable, with `import.meta.env.DEV` override for local development | Change `checkAuthorization` catch block from `return true` to `return false`; add health check probe; show banner when backend unreachable |
| SEC-01 | CORS configured with explicit origin allowlist from environment config | Add `cors_allowed_origins` and `environment` to Pydantic Settings; replace `allow_origins=["*"]` in `main.py` with config-driven list |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.x (installed) | API framework with dependency injection | Already in use; `Depends()` is the idiomatic auth pattern |
| firebase-admin | >=6.2.0 (installed) | Server-side Firebase ID token verification | Already in use in `auth.py` |
| starlette CORSMiddleware | (bundled with FastAPI) | CORS configuration | Already in use in `main.py`; just needs config change |
| Firebase JS SDK | 12.x (installed) | Client-side auth + `getIdToken(true)` for forced refresh | Already in use in AuthContext |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic-settings | (installed) | Environment-based configuration | Add `cors_allowed_origins` and `environment` fields |
| sse-starlette | >=2.0 (installed) | SSE streaming | Already used for GHL progress; needs query-param auth |

No new dependencies are needed. Everything required is already installed.

## Architecture Patterns

### Recommended Auth Application Strategy

**Use router-level dependencies, not per-endpoint.** FastAPI `include_router` accepts a `dependencies` parameter that applies to all endpoints in that router.

```python
# In main.py - apply auth to all tool routers at mount time
from app.core.auth import require_auth
from fastapi import Depends

app.include_router(
    extract_router,
    prefix="/api/extract",
    tags=["extract"],
    dependencies=[Depends(require_auth)],
)
```

**Why this approach:**
- Single place to manage auth for each router
- No risk of forgetting to add `Depends(require_auth)` to a new endpoint
- Existing per-endpoint `Depends(require_auth)` on GHL routes will still work (double-dependency is harmless -- FastAPI deduplicates)
- Admin routes already use per-endpoint `Depends(require_admin)` which chains on `require_auth` -- adding router-level `require_auth` is redundant but harmless

**Exempt endpoints** (no auth):
- `/api/health` -- global health check (defined directly on `app`, not on a router)
- `/api/admin/users/{email}/check` -- authorization check called before auth is established (per user decision)
- Per-tool `/health` endpoints (e.g., `/api/extract/health`) -- these are sub-health-checks

**Problem: admin check endpoint exemption.** The `check_user` endpoint at `/api/admin/users/{email}/check` lives on the admin router, which also has `require_admin` on all mutation endpoints. Since we want the admin router to require auth generally but exempt this one endpoint, we have two options:

1. **Move `check_user` to a separate public router** mounted without auth dependencies
2. **Keep admin router without router-level auth** (it already has per-endpoint `require_admin` on mutations)

**Recommendation: Option 2.** The admin router already applies `require_admin` to every mutation endpoint individually. Adding router-level `require_auth` would break the `check_user` endpoint. Keep the admin router as-is -- its mutation endpoints are already protected by `require_admin` which chains through `require_auth`.

### Dev-Mode Auth Bypass

The `verify_firebase_token` function (line 290 of `auth.py`) already returns `None` when Firebase Admin SDK is not configured. The problem is that `get_current_user` (line 308) treats `None` from verification as "no user" rather than "dev mode bypass."

**Fix:** When Firebase is not configured AND a Bearer token is present, return a synthetic user dict instead of `None`:

```python
async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[dict]:
    if credentials is None:
        return None

    token = credentials.credentials
    decoded = await verify_firebase_token(token)

    if decoded is None:
        # Firebase not configured -- dev mode bypass
        # Still require a token header, but skip verification
        app = get_firebase_app()
        if app is None:
            logger.warning("Dev mode: accepting token without Firebase verification")
            return {"email": "dev@localhost", "uid": "dev-mode"}
        # Firebase IS configured but token is invalid
        return None

    email = decoded.get("email")
    if email and not is_user_allowed(email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not authorized to access this application"
        )
    return decoded
```

### CORS Configuration

```python
# In config.py
environment: str = "development"
cors_allowed_origins: str = ""  # Comma-separated, empty means use defaults

@property
def cors_origins(self) -> list[str]:
    """Get CORS allowed origins based on environment."""
    if self.cors_allowed_origins:
        return [o.strip() for o in self.cors_allowed_origins.split(",")]
    if self.environment == "production":
        return ["https://tools.tablerocktx.com"]
    return ["http://localhost:5173"]
```

```python
# In main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
```

**Key detail:** Do NOT use `allow_origins=["*"]` with `allow_credentials=True` in production. Browsers reject this combination per the CORS spec. The current code has this bug -- it works only because Vite proxies `/api` in dev (so CORS never fires) and production serves from the same origin (static files served by FastAPI).

### SSE Query Parameter Auth

```python
@router.get("/send/{job_id}/progress")
async def stream_send_progress(job_id: str, request: Request, token: Optional[str] = None):
    """Stream SSE progress events. Auth via query param ?token=xxx."""
    if token:
        decoded = await verify_firebase_token(token)
        if decoded is None and get_firebase_app() is not None:
            raise HTTPException(status_code=401, detail="Invalid token")
    # If no token and Firebase not configured, allow (dev mode)
    elif get_firebase_app() is not None:
        raise HTTPException(status_code=401, detail="Token required")
    # ... rest of SSE logic
```

Frontend change in `useSSEProgress.ts`:
```typescript
const connectEventSource = (authToken: string | null) => {
    let url = `/api/ghl/send/${jobId}/progress`
    if (authToken) {
        url += `?token=${encodeURIComponent(authToken)}`
    }
    const eventSource = new EventSource(url)
    // ...
}
```

### ApiClient 401 Interceptor

Add token refresh logic to the `request` method in `ApiClient`:

```typescript
// In ApiClient.request(), after getting response:
if (response.status === 401 && this.onUnauthorized) {
    const retried = await this.onUnauthorized()
    if (retried) {
        // Retry the original request with new token
        return this.request<T>(endpoint, options)
    }
}
```

The `onUnauthorized` callback is set by AuthContext after initialization, providing access to Firebase's `getIdToken(true)` for forced refresh. This avoids a circular dependency between ApiClient and AuthContext.

### Frontend Fail-Closed Pattern

```typescript
// In AuthContext.tsx checkAuthorization:
const checkAuthorization = async (email: string) => {
    try {
        const response = await fetch(`${API_BASE}/admin/users/${encodeURIComponent(email)}/check`)
        if (response.ok) {
            const data = await response.json()
            return data
        }
        return false
    } catch (error) {
        console.error('Error checking authorization:', error)
        // CHANGE: Fail closed -- deny access when backend is unreachable
        if (import.meta.env.DEV) {
            // Dev override: still fail closed but set a flag for the banner
            return false
        }
        return false
    }
}
```

A separate health check call (`/api/health`) determines whether the backend is reachable and drives the banner message ("Cannot connect to backend" vs "Not authorized").

### Anti-Patterns to Avoid
- **Per-endpoint auth on every route:** Leads to forgotten endpoints. Use router-level `dependencies` instead.
- **Wildcard CORS with credentials:** Browsers reject `allow_origins=["*"]` with `allow_credentials=True`. Always use explicit origins.
- **Storing tokens in localStorage:** Firebase SDK already handles token persistence and refresh. Do not cache tokens separately.
- **Checking `import.meta.env.DEV` for auth bypass on the backend:** Dev mode detection belongs on the backend (Firebase SDK availability), not passed from frontend.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Token verification | Custom JWT parsing | `firebase_admin.auth.verify_id_token()` | Handles key rotation, expiry, issuer validation |
| Token refresh | Manual refresh timer | Firebase JS SDK `getIdToken(true)` | Handles refresh token exchange, caching, error states |
| CORS handling | Custom middleware | Starlette `CORSMiddleware` | Handles preflight, vary headers, credential rules per spec |
| Dev mode detection | Environment flags from frontend | `get_firebase_app() is None` check | Natural -- if Firebase Admin SDK is not configured, you're in dev |

## Common Pitfalls

### Pitfall 1: Admin Lockout
**What goes wrong:** Applying auth to `check_user` endpoint breaks the login flow because the frontend calls it before the user has auth context.
**Why it happens:** `check_user` at `/api/admin/users/{email}/check` is on the admin router. Router-level auth would lock it.
**How to avoid:** Do NOT add router-level auth to the admin router. Its mutation endpoints already use `require_admin` individually.
**Warning signs:** Login page shows "Cannot connect" or spinner forever after deploying auth changes.

### Pitfall 2: SSE Endpoint Breaks
**What goes wrong:** Adding router-level auth to the GHL router breaks the SSE progress endpoint because EventSource cannot send Authorization headers.
**Why it happens:** `stream_send_progress` is on the GHL router which would get `require_auth` applied.
**How to avoid:** Either (a) move SSE endpoint to a separate router without auth and add query-param auth manually, or (b) keep GHL router without router-level auth since all its endpoints already have per-endpoint `Depends(require_auth)`, then add query-param auth to the SSE endpoint.
**Warning signs:** SSE progress stops working after auth deployment; 401 errors in browser console for EventSource.

### Pitfall 3: Dev Mode Returns None Instead of User Dict
**What goes wrong:** `require_auth` receives `None` from `get_current_user` in dev mode and raises 401, making local development impossible.
**Why it happens:** Current `get_current_user` returns `None` when Firebase is not configured, which `require_auth` interprets as "unauthenticated."
**How to avoid:** Return a synthetic user dict `{"email": "dev@localhost", "uid": "dev-mode"}` when Firebase is not configured but a Bearer token is present.
**Warning signs:** All API calls return 401 in local development after deploying auth changes.

### Pitfall 4: CORS Blocks Production After Deployment
**What goes wrong:** Production requests fail with CORS errors after switching from wildcard to explicit origins.
**Why it happens:** Missing the production origin in the allowlist, or using HTTP instead of HTTPS.
**How to avoid:** Ensure `https://tools.tablerocktx.com` is in the production origins list. Add `ENVIRONMENT=production` to Cloud Run env vars. Verify with `curl -H "Origin: https://tools.tablerocktx.com" -I https://tools.tablerocktx.com/api/health`.
**Warning signs:** Browser console shows "No 'Access-Control-Allow-Origin' header" errors.

### Pitfall 5: Token Refresh Infinite Loop
**What goes wrong:** 401 interceptor retries the request, gets another 401 (token is actually invalid, not just expired), retries again infinitely.
**Why it happens:** No retry limit or flag to prevent re-entrancy.
**How to avoid:** Add a `_isRefreshing` flag and a retry counter (max 1 retry). If the refreshed token still gets 401, clear auth and redirect to login.
**Warning signs:** Rapid-fire requests in network tab, browser freezes.

### Pitfall 6: Per-Tool Health Endpoints Get Locked
**What goes wrong:** Router-level auth on tool routers locks the per-tool health endpoints (e.g., `/api/extract/health`).
**Why it happens:** Per-tool health checks are defined on the tool routers.
**How to avoid:** Either remove per-tool health endpoints (the global `/api/health` is sufficient) or accept that they require auth (they are not used by external monitoring).
**Warning signs:** Per-tool health checks return 401. Impact is minimal since only the global `/api/health` is used for monitoring.

## Code Examples

### Router-Level Auth Application (main.py changes)

```python
# Source: FastAPI docs - https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-in-path-operation-decorators/
from fastapi import Depends
from app.core.auth import require_auth

# Tool routers - all require auth
app.include_router(extract_router, prefix="/api/extract", tags=["extract"], dependencies=[Depends(require_auth)])
app.include_router(title_router, prefix="/api/title", tags=["title"], dependencies=[Depends(require_auth)])
app.include_router(proration_router, prefix="/api/proration", tags=["proration"], dependencies=[Depends(require_auth)])
app.include_router(revenue_router, prefix="/api/revenue", tags=["revenue"], dependencies=[Depends(require_auth)])
app.include_router(ghl_prep_router, prefix="/api/ghl-prep", tags=["ghl-prep"], dependencies=[Depends(require_auth)])
app.include_router(history_router, prefix="/api/history", tags=["history"], dependencies=[Depends(require_auth)])
app.include_router(ai_router, prefix="/api/ai", tags=["ai"], dependencies=[Depends(require_auth)])
app.include_router(enrichment_router, prefix="/api/enrichment", tags=["enrichment"], dependencies=[Depends(require_auth)])
app.include_router(etl_router, prefix="/api/etl", tags=["etl"], dependencies=[Depends(require_auth)])

# GHL router - already has per-endpoint auth, keep as-is for SSE endpoint flexibility
app.include_router(ghl_router, prefix="/api/ghl", tags=["ghl"])

# Admin router - keep as-is, check_user must be unauthenticated
app.include_router(admin_router, prefix="/api/admin", tags=["admin"])
```

### Pydantic Settings Addition (config.py)

```python
# Add to Settings class
environment: str = "development"
cors_allowed_origins: str = ""

@property
def cors_origins(self) -> list[str]:
    if self.cors_allowed_origins:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]
    if self.environment == "production":
        return ["https://tools.tablerocktx.com"]
    return ["http://localhost:5173"]
```

### ApiClient Interceptor Pattern (api.ts)

```typescript
class ApiClient {
    private onUnauthorized: (() => Promise<boolean>) | null = null
    private isRefreshing = false

    setUnauthorizedHandler(handler: () => Promise<boolean>) {
        this.onUnauthorized = handler
    }

    private async request<T>(endpoint: string, options: ApiRequestOptions = {}): Promise<ApiResponse<T>> {
        // ... existing fetch logic ...

        if (!response.ok) {
            if (response.status === 401 && this.onUnauthorized && !this.isRefreshing) {
                this.isRefreshing = true
                try {
                    const refreshed = await this.onUnauthorized()
                    if (refreshed) {
                        this.isRefreshing = false
                        return this.request<T>(endpoint, options)
                    }
                } finally {
                    this.isRefreshing = false
                }
            }
            // ... existing error handling ...
        }
    }
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `allow_origins=["*"]` CORS | Explicit origin allowlist | This phase | Fixes CORS spec violation with credentials |
| No backend auth enforcement | Router-level `require_auth` | This phase | All tool endpoints return 401 without valid token |
| Frontend fail-open on backend down | Fail-closed with dev override | This phase | No access to app interior without backend |

**Not changing:**
- Firebase Auth integration (already works)
- `require_auth` / `require_admin` dependency functions (already correct)
- Frontend `ProtectedRoute` wrapper (already redirects to login)

## Open Questions

1. **Per-tool health endpoints**
   - What we know: Each tool router has its own `/health` endpoint. Router-level auth will lock them.
   - What's unclear: Whether anything monitors these per-tool health endpoints.
   - Recommendation: Accept that they require auth. The global `/api/health` (on the app, not a router) is exempt and sufficient for monitoring. If per-tool health checks are needed without auth, they can be moved later.

2. **ENVIRONMENT env var in Cloud Run**
   - What we know: The `ENVIRONMENT` env var is referenced in CLAUDE.md docs but is NOT currently in the Pydantic Settings class.
   - What's unclear: Whether Cloud Run already has `ENVIRONMENT=production` set.
   - Recommendation: Add `environment` to Settings, default to `"development"`. Verify Cloud Run has it set or add it to the deploy workflow.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >=7.4.0 + pytest-asyncio >=0.23.0 |
| Config file | None -- needs pytest.ini or pyproject.toml section (Wave 0) |
| Quick run command | `cd backend && python3 -m pytest tests/ -x -q` |
| Full suite command | `cd backend && python3 -m pytest tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AUTH-01 | Unauthenticated requests to tool endpoints return 401 | integration | `cd backend && python3 -m pytest tests/test_auth_enforcement.py -x` | No -- Wave 0 |
| AUTH-01 | Authenticated requests to tool endpoints succeed (not 401) | integration | `cd backend && python3 -m pytest tests/test_auth_enforcement.py -x` | No -- Wave 0 |
| AUTH-01 | Dev mode (no Firebase) accepts any Bearer token | unit | `cd backend && python3 -m pytest tests/test_auth_enforcement.py::test_dev_mode_bypass -x` | No -- Wave 0 |
| AUTH-02 | Frontend fail-closed when backend unreachable | manual-only | Manual: stop backend, verify login screen with banner | N/A |
| SEC-01 | CORS rejects unknown origins | integration | `cd backend && python3 -m pytest tests/test_cors.py -x` | No -- Wave 0 |
| SEC-01 | CORS allows configured origins | integration | `cd backend && python3 -m pytest tests/test_cors.py -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `cd backend && python3 -m pytest tests/ -x -q`
- **Per wave merge:** `cd backend && python3 -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/__init__.py` -- package init
- [ ] `backend/tests/conftest.py` -- shared fixtures: test client with auth override, mock Firebase user
- [ ] `backend/tests/test_auth_enforcement.py` -- covers AUTH-01
- [ ] `backend/tests/test_cors.py` -- covers SEC-01
- [ ] `backend/pytest.ini` -- pytest configuration (asyncio mode, test paths)
- [ ] Framework install: Already installed (`pytest>=7.4.0`, `pytest-asyncio>=0.23.0`, `httpx>=0.26.0` in requirements.txt)

**Test fixture pattern for auth mocking:**
```python
# conftest.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.auth import require_auth

@pytest.fixture
def mock_user():
    return {"email": "test@example.com", "uid": "test-uid"}

@pytest.fixture
def authenticated_client(mock_user):
    """Client with auth bypassed."""
    app.dependency_overrides[require_auth] = lambda: mock_user
    yield AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    app.dependency_overrides.clear()

@pytest.fixture
def unauthenticated_client():
    """Client with no auth override (should get 401)."""
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
```

## Sources

### Primary (HIGH confidence)
- **Codebase inspection** -- `backend/app/core/auth.py` (lines 290-368): existing `require_auth`, `require_admin`, `verify_firebase_token`, `get_current_user` functions
- **Codebase inspection** -- `backend/app/main.py` (lines 48-81): current CORS config and router mounts
- **Codebase inspection** -- `frontend/src/contexts/AuthContext.tsx` (lines 44-57): current fail-open `checkAuthorization`
- **Codebase inspection** -- `frontend/src/utils/api.ts`: current ApiClient without 401 interceptor
- **Codebase inspection** -- `backend/app/api/ghl.py` (lines 391-489): SSE endpoint without auth
- **FastAPI docs** -- router-level dependencies via `include_router(dependencies=[...])` is documented standard pattern

### Secondary (MEDIUM confidence)
- **Starlette CORS docs** -- `allow_origins` with `allow_credentials=True` requires explicit origins, not `"*"`
- **Firebase JS SDK docs** -- `getIdToken(true)` forces token refresh from Firebase servers

### Tertiary (LOW confidence)
- None -- all findings verified against codebase

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already installed and in use
- Architecture: HIGH -- patterns verified against existing codebase code
- Pitfalls: HIGH -- identified from direct code inspection of current implementation gaps

**Research date:** 2026-03-11
**Valid until:** 2026-04-11 (stable domain, no moving targets)

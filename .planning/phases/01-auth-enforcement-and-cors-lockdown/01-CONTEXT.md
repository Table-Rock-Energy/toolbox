# Phase 1: Auth Enforcement and CORS Lockdown - Context

**Gathered:** 2026-03-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Every API request (except health check and user authorization check) requires a valid Firebase token. CORS rejects unknown origins. Frontend fails closed when backend is unreachable, with development-mode override. Admin user (james@tablerocktx.com) retains full access after enforcement.

</domain>

<decisions>
## Implementation Decisions

### Login flow
- Keep `/admin/users/{email}/check` unauthenticated (exempt from auth like `/api/health`) -- it only returns whether an email is allowed, no sensitive data
- Endpoint continues returning `{allowed: true/false, role, tools}` -- email enumeration risk is negligible for small internal team
- Use `/api/health` for frontend connectivity detection (separate from authorization check)
- Unauthorized users (not in allowlist) see error message on the login screen itself: "Your account is not authorized. Contact an administrator." -- user never sees app interior

### Dev mode behavior
- In development (without Firebase Admin SDK credentials), accept any Bearer token without Firebase verification -- auth middleware stays active (routes still require a token header), but verification is skipped
- When backend is unreachable, show login screen with a banner: "Cannot connect to backend. Start the backend server." -- fail-closed, no access to the app
- CORS allows `http://localhost:5173` in development, `https://tools.tablerocktx.com` in production
- New `CORS_ALLOWED_ORIGINS` env var (comma-separated) with sensible defaults per environment, overridable for staging or custom domains

### SSE progress auth
- GHL send progress SSE endpoint (`/api/ghl/send/{job_id}/progress`) authenticates via query parameter token (`?token=xxx`) since EventSource API cannot send Authorization headers
- Any authenticated user can view any job's progress (consistent with "job history visible to all" decision in PROJECT.md)
- Only GHL send progress uses SSE -- RRC download status uses regular polling with Bearer token (no changes needed)

### Error experience
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

</decisions>

<specifics>
## Specific Ideas

No specific requirements -- open to standard approaches.

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `require_auth` dependency in `backend/app/core/auth.py` (line 339): Already implements 401 response for missing/invalid tokens -- just needs to be applied to routes
- `require_admin` dependency in `backend/app/core/auth.py` (line 355): Chains on `require_auth`, checks admin role -- already used on admin routes
- `verify_firebase_token` in `backend/app/core/auth.py` (line 290): Returns `None` when Firebase isn't configured -- natural dev-mode bypass point
- `ApiClient` class in `frontend/src/utils/api.ts`: Has `setAuthToken`/`clearAuthToken` -- extend with 401 interceptor for token refresh
- `HTTPBearer(auto_error=False)` security scheme already configured (line 31)

### Established Patterns
- Admin routes already use `Depends(require_admin)` -- same pattern extends to tool routes with `Depends(require_auth)`
- GHL routes already use `Depends(require_auth)` -- proves the pattern works end-to-end
- Frontend AuthContext already sends tokens via `api.setAuthToken(token)` after Firebase sign-in
- Pydantic Settings in `config.py` for environment-based configuration -- add `cors_allowed_origins` here

### Integration Points
- `main.py` line 49-55: CORSMiddleware currently uses `allow_origins=["*"]` -- replace with config-driven origins
- `main.py` line 71-81: Router includes where auth dependencies would be applied
- `frontend/src/contexts/AuthContext.tsx` line 46-57: `checkAuthorization` function -- currently fail-open, needs fail-closed logic
- `frontend/src/contexts/AuthContext.tsx` line 55: `return true` on backend unreachable -- change to `return false`

</code_context>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope.

</deferred>

---

*Phase: 01-auth-enforcement-and-cors-lockdown*
*Context gathered: 2026-03-11*

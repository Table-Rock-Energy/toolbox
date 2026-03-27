# Phase 23: Auth Backend - Context

**Gathered:** 2026-03-25
**Status:** Ready for planning
**Mode:** Auto-generated (infrastructure phase — discuss skipped)

<domain>
## Phase Boundary

Implement JWT-based authentication against PostgreSQL. Add /api/auth/login and /api/auth/me endpoints returning JWT tokens. Replace Firebase token verification in require_auth/require_admin with JWT decode. Create CLI seed script for initial admin user (james@tablerocktx.com). App must fail fast if JWT_SECRET_KEY missing in production.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — pure infrastructure phase. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

Key research findings to incorporate:
- PyJWT >= 2.12.0 for JWT (NOT python-jose — abandoned)
- pwdlib[bcrypt] >= 0.2.0 for password hashing (NOT passlib — broken with bcrypt 5.0+)
- Keep existing Depends() chain: get_current_user → require_auth → require_admin — just change internals
- JWT claims: sub (email), role, exp — same shape returned as current Firebase decoded token
- 24-hour JWT expiry (from STATE.md decisions)
- CRON_SECRET bypass preserved for scheduled jobs
- User model already has password_hash, role, scope, tools columns from Phase 22

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/core/auth.py` — Firebase token verification, require_auth, require_admin, get_current_user
- `backend/app/models/db_models.py` — User model with password_hash, role, scope, tools, added_by columns (Phase 22)
- `backend/app/core/config.py` — Settings model for env vars
- `backend/app/core/database.py` — async engine, session factory

### Established Patterns
- FastAPI Depends() chain for auth: get_current_user → require_auth → require_admin
- HTTPBearer security scheme extracts token
- AllowedUser Pydantic model has role, scope, tools fields
- CRON_SECRET bypass checks header before token verification

### Integration Points
- auth.py verify_firebase_token → replace with jwt.decode
- auth.py is_user_allowed → replace with DB query on users table
- All 9 tool routers use include_router(dependencies=[Depends(require_auth)])
- SSE endpoints use query-param token auth (must work with JWT too)
- GHL/admin routers have custom auth (check_user must stay unauthenticated)

</code_context>

<specifics>
## Specific Ideas

No specific requirements — infrastructure phase. Refer to ROADMAP phase description and success criteria.

</specifics>

<deferred>
## Deferred Ideas

None — infrastructure phase.

</deferred>

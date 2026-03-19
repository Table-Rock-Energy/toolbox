# Phase 10: Auth Hardening & GHL Cleanup - Context

**Gathered:** 2026-03-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Secure admin and history endpoints with proper authentication and authorization. Remove the deprecated GHL `smart_list_name` field. No new capabilities -- this is purely hardening and cleanup of existing endpoints.

</domain>

<decisions>
## Implementation Decisions

### Admin endpoint auth
- All admin GET endpoints (`/options`, `/users`, `/settings/gemini`, `/settings/google-cloud`, `/settings/google-maps`) require `require_admin` dependency
- Per-endpoint `Depends(require_admin)` on each handler, NOT router-level dependency (avoids breaking `check_user` which must remain unauthenticated)
- `check_user` (`GET /users/{email}/check`) remains unauthenticated -- used during login flow
- Preferences endpoints (`GET/PUT /preferences/{email}`) require `require_auth` (any authenticated user)
- Profile image endpoints (`POST /upload-profile-image`, `GET /profile-image/{user_id}`) -- Claude's discretion on auth level

### History user-scoping
- `GET /jobs` auto-detects admin vs non-admin from the authenticated user
- Non-admin users see only jobs where `user_id` matches their email
- Admin users see all jobs (no query param needed -- auto-detected from auth)
- Jobs with missing `user_id` (legacy) are visible only to admins
- Scope key is email matching (`user_id` field in Firestore stores email)

### Delete ownership
- `DELETE /jobs/{job_id}` checks job ownership before deletion
- Non-owner gets 403 with clear message ("You can only delete your own jobs")
- Frontend shows a modal notification when a user tries to delete someone else's job
- Admin users can delete any job (admin override)

### GHL smart_list_name removal
- Single-pass removal (frontend type + backend model + API fallback in one commit)
- No UI component ever rendered or collected `smart_list_name` -- only the TypeScript type definition exists
- Remove from: `BulkSendRequest` model, `ghl.py` fallback logic, `api.ts` type
- `campaign_name` assignment becomes simply `data.campaign_tag` (required field, always present)

### Claude's Discretion
- Auth level for profile image endpoints
- Error message wording for 403 responses
- Whether to add tests for the new auth checks (recommended)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Auth endpoints
- `backend/app/api/admin.py` -- All admin endpoints, current auth state (GETs are open)
- `backend/app/api/history.py` -- History endpoints, no user-scoping currently
- `backend/app/core/auth.py` -- `require_admin`, `require_auth`, `is_user_admin` helpers
- `backend/app/main.py` lines 78-83 -- Router mounting with/without auth dependencies

### GHL cleanup
- `backend/app/models/ghl.py` lines 102-118 -- `BulkSendRequest` with deprecated `smart_list_name`
- `backend/app/api/ghl.py` line 343 -- Fallback: `campaign_name = data.smart_list_name or data.campaign_tag`
- `frontend/src/utils/api.ts` line 457 -- TypeScript type with `smart_list_name`

### Requirements
- `.planning/REQUIREMENTS.md` -- AUTH-01 through AUTH-05, GHL-01, GHL-02

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `require_admin` dependency: Already used on admin write endpoints (POST/PUT/DELETE users, PUT settings). Just add to GET handlers.
- `require_auth` dependency: Already applied at router level for history. Need to extract user email from the dependency return value for scoping.
- `is_user_admin()` function in `auth.py`: Can be called inside handlers to branch admin vs non-admin behavior.

### Established Patterns
- Admin write endpoints already use `user: dict = Depends(require_admin)` pattern -- follow same for GETs
- History router already has `Depends(require_auth)` at router level -- user-scoping adds filtering inside the handler
- The `user` dict from `require_auth` contains the verified token payload including `email`

### Integration Points
- `firestore_service.get_recent_jobs()` needs to accept an optional `user_id` filter parameter
- Frontend history/dashboard components may need to handle 403 responses on delete
- Frontend AdminSettings page already gates on admin status -- no frontend changes needed for admin auth

</code_context>

<specifics>
## Specific Ideas

- Frontend should show a modal (not just a toast) when delete is denied -- user specifically requested this
- The 403 message should be user-friendly, not technical

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 10-auth-hardening-ghl-cleanup*
*Context gathered: 2026-03-18*

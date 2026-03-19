# Phase 10: Auth Hardening & GHL Cleanup - Research

**Researched:** 2026-03-18
**Domain:** FastAPI auth dependencies, Firestore query scoping, Pydantic model cleanup
**Confidence:** HIGH

## Summary

This phase involves three distinct workstreams: (1) adding `require_admin` to admin GET endpoints, (2) scoping history queries by user and enforcing delete ownership, and (3) removing the deprecated `smart_list_name` field. All three are straightforward modifications to existing code using established patterns already in the codebase.

The auth infrastructure (`require_admin`, `require_auth`, `is_user_admin`) is fully built and battle-tested on admin write endpoints. The history service already has `get_user_jobs()` in Firestore. The GHL cleanup is a field deletion across 3 files. No new libraries, no new patterns -- just applying existing patterns to currently-unprotected endpoints.

**Primary recommendation:** Follow existing `Depends(require_admin)` pattern on each admin GET handler. Use the existing `get_user_jobs()` Firestore function for history scoping. Remove `smart_list_name` from all three locations in a single pass.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- All admin GET endpoints (`/options`, `/users`, `/settings/gemini`, `/settings/google-cloud`, `/settings/google-maps`) require `require_admin` dependency
- Per-endpoint `Depends(require_admin)` on each handler, NOT router-level dependency (avoids breaking `check_user` which must remain unauthenticated)
- `check_user` (`GET /users/{email}/check`) remains unauthenticated -- used during login flow
- Preferences endpoints (`GET/PUT /preferences/{email}`) require `require_auth` (any authenticated user)
- `GET /jobs` auto-detects admin vs non-admin from the authenticated user
- Non-admin users see only jobs where `user_id` matches their email
- Admin users see all jobs (no query param needed -- auto-detected from auth)
- Jobs with missing `user_id` (legacy) are visible only to admins
- Scope key is email matching (`user_id` field in Firestore stores email)
- `DELETE /jobs/{job_id}` checks job ownership before deletion
- Non-owner gets 403 with clear message ("You can only delete your own jobs")
- Frontend shows a modal notification when a user tries to delete someone else's job
- Admin users can delete any job (admin override)
- Single-pass removal for smart_list_name (frontend type + backend model + API fallback in one commit)
- No UI component ever rendered or collected `smart_list_name` -- only the TypeScript type definition exists
- Remove from: `BulkSendRequest` model, `ghl.py` fallback logic, `api.ts` type
- `campaign_name` assignment becomes simply `data.campaign_tag` (required field, always present)

### Claude's Discretion
- Auth level for profile image endpoints
- Error message wording for 403 responses
- Whether to add tests for the new auth checks (recommended)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| AUTH-01 | Admin GET endpoints require `require_admin` authentication | Existing `require_admin` dependency; add `user: dict = Depends(require_admin)` to 5 GET handlers in `admin.py` |
| AUTH-02 | `check_user` endpoint remains unauthenticated for login flow | Already unauthenticated (no Depends); just verify tests assert this |
| AUTH-03 | History GET /jobs returns only jobs belonging to authenticated user | `get_user_jobs()` already exists in `firestore_service.py`; extract email from `require_auth` return dict |
| AUTH-04 | Admin users can view all users' jobs in history | Use `is_user_admin(email)` to branch between `get_recent_jobs()` (all) and `get_user_jobs()` (scoped) |
| AUTH-05 | History DELETE /jobs/{id} restricted to job owner or admin | Fetch job via `get_job()`, compare `user_id` field to authenticated email, admin bypasses |
| GHL-01 | `smart_list_name` field removed from backend model and API | Delete field from `BulkSendRequest` in `models/ghl.py`, simplify line 343 in `api/ghl.py` |
| GHL-02 | `smart_list_name` references removed from frontend types and API client | Delete from `api.ts` line 457 |
</phase_requirements>

## Architecture Patterns

### Pattern 1: Per-Endpoint Admin Auth (Existing)

Admin write endpoints already use this exact pattern. Apply to GET endpoints.

**Current state (admin.py):**
```python
# WRITE endpoints -- already protected:
@router.post("/users", response_model=UserResponse)
async def add_user(request: AddUserRequest, user: dict = Depends(require_admin)):
    ...

# GET endpoints -- currently OPEN (the bug):
@router.get("/options", response_model=OptionsResponse)
async def get_options():
    ...
```

**Target state:**
```python
@router.get("/options", response_model=OptionsResponse)
async def get_options(user: dict = Depends(require_admin)):
    ...

@router.get("/users", response_model=AllowlistResponse)
async def list_allowed_users(user: dict = Depends(require_admin)):
    ...
```

**Endpoints to add `require_admin`:**
1. `GET /options` (line 280)
2. `GET /users` (line 290)
3. `GET /settings/gemini` (line 411)
4. `GET /settings/google-cloud` (line 475)
5. `GET /settings/google-maps` (line 535)

**Endpoints to add `require_auth`:**
1. `GET /preferences/{email}` (line 699)
2. `PUT /preferences/{email}` (line 719)

**Endpoints that MUST remain unauthenticated:**
1. `GET /users/{email}/check` (line 393) -- login flow dependency

### Pattern 2: User-Scoped History Queries

The history router already has router-level `require_auth` (main.py line 81). The `user` dict from `require_auth` contains `{"email": "...", "uid": "..."}`.

**Current flow (history.py):**
```python
@router.get("/jobs")
async def get_jobs(tool, limit):
    jobs = await db.get_recent_jobs(tool=tool, limit=limit)  # returns ALL jobs
    return {"jobs": jobs}
```

**Target flow:**
```python
@router.get("/jobs")
async def get_jobs(tool, limit, user: dict = Depends(require_auth)):
    email = user.get("email", "")
    if is_user_admin(email):
        jobs = await db.get_recent_jobs(tool=tool, limit=limit)
    else:
        jobs = await db.get_user_jobs(user_id=email, tool=tool, limit=limit)
    return {"jobs": jobs}
```

Key detail: `require_auth` is already applied at the router level in `main.py`, but the handler doesn't extract the user. Adding `user: dict = Depends(require_auth)` to the handler signature does NOT double-authenticate -- FastAPI's dependency injection caches per-request.

### Pattern 3: Delete Ownership Check

```python
@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str, user: dict = Depends(require_auth)):
    job = await db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    email = user.get("email", "")
    job_owner = job.get("user_id", "")

    if job_owner != email and not is_user_admin(email):
        raise HTTPException(
            status_code=403,
            detail="You can only delete your own jobs"
        )

    deleted = await db.delete_job(job_id)
    ...
```

### Pattern 4: Frontend 403 Handling with Modal

The tool pages (Extract, Title, Proration, Revenue, GhlPrep) all have `handleDeleteJob` functions that fire-and-forget the DELETE request. They need to check the response status and show a modal on 403.

Current pattern (all pages):
```typescript
try {
  await fetch(`${API_BASE}/history/jobs/${job.job_id}`, {
    method: 'DELETE',
    headers: await authHeaders(),
  })
} catch { /* best-effort */ }
setJobs((prev) => prev.filter((j) => j.id !== job.id))
```

Target: Check response status, show modal on 403, only remove from local state on success.

### Pattern 5: Profile Image Auth (Claude's Discretion)

**Recommendation:** `require_auth` (any authenticated user) for both profile image endpoints.

Rationale: Profile images are user-specific but not sensitive admin data. Any authenticated user should be able to upload their own image and view any user's image (for avatars in job history, etc.). No need for admin restriction.

```python
@router.post("/upload-profile-image")
async def upload_profile_image(
    file: ..., user_id: ..., user: dict = Depends(require_auth)
):
    ...

@router.get("/profile-image/{user_id}")
async def get_profile_image(user_id: str, user: dict = Depends(require_auth)):
    ...
```

### Anti-Patterns to Avoid
- **Router-level `require_admin` on admin router:** Would break `check_user` endpoint used during login
- **Query param for admin/user mode in history:** Use auto-detection from token, not client-controlled params
- **Removing smart_list_name from backend before frontend:** Cached frontends would get 422 errors (though CONTEXT says single-pass is fine since no UI sends this field)

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Auth dependency | Custom middleware | `Depends(require_admin)` / `Depends(require_auth)` | Already built, tested, handles 401/403 correctly |
| User job filtering | Manual Firestore queries | `firestore_service.get_user_jobs()` | Already exists with index fallback handling |
| Admin detection | Custom role check | `is_user_admin(email)` from `core/auth.py` | Already handles primary admin fallback |

## Common Pitfalls

### Pitfall 1: Router-Level vs Per-Endpoint Auth Conflict
**What goes wrong:** Adding `require_admin` at router level on the admin router breaks `check_user`.
**Why it happens:** `check_user` is on the same router but must remain unauthenticated for login flow.
**How to avoid:** Per-endpoint `Depends(require_admin)` on each GET handler. CONTEXT explicitly locks this decision.
**Warning signs:** Login flow fails after deploy.

### Pitfall 2: Double Auth on History Endpoints
**What goes wrong:** History router already has `Depends(require_auth)` at router level (main.py line 81). Adding it again per-endpoint seems redundant.
**Why it happens:** Confusion about FastAPI dependency scoping.
**How to avoid:** This is fine -- FastAPI caches dependency results per-request. Adding `user: dict = Depends(require_auth)` to the handler gives access to the user dict without re-authenticating.

### Pitfall 3: Legacy Jobs Without user_id
**What goes wrong:** Old Firestore jobs may not have a `user_id` field. Non-admin user query returns no results for these.
**Why it happens:** `user_id` was added after initial job creation.
**How to avoid:** Per CONTEXT decision, legacy jobs (missing `user_id`) are visible only to admins. The `get_user_jobs()` query naturally excludes them since it filters on `user_id == email`.

### Pitfall 4: Frontend Optimistic Delete on 403
**What goes wrong:** Current code removes the job from local state regardless of API response.
**Why it happens:** Fire-and-forget pattern doesn't check response status.
**How to avoid:** Check `response.ok` before removing from local state. On 403, show a modal. On other errors, optionally show a toast.

### Pitfall 5: GhlSendModal Variable Naming
**What goes wrong:** `GhlSendModal.tsx` uses `smartListName` as a local state variable name, which looks like a reference to the deprecated field.
**Why it happens:** Historical naming -- the variable holds the `campaign_tag` value.
**How to avoid:** The CONTEXT says to remove `smart_list_name` from the TypeScript type in `api.ts`. The `smartListName` state variable in `GhlSendModal.tsx` is a separate concern -- it maps to `campaign_tag` in the request. Renaming this variable is optional cleanup (not required by GHL-01/GHL-02), but recommended for clarity.

### Pitfall 6: Pydantic Extra Fields
**What goes wrong:** Removing `smart_list_name` from the model could cause 422 if a client still sends it.
**Why it happens:** Pydantic v2 default behavior depends on model config. If `extra='forbid'`, unknown fields cause validation errors.
**How to avoid:** Verified: `BulkSendRequest` has NO `ConfigDict` or `model_config` set. Pydantic v2 defaults to `extra='ignore'`, meaning unknown fields are silently dropped. Safe to remove the field -- any old client sending it will have the field ignored, not rejected.

## Code Examples

### Admin GET Auth Addition (5 endpoints)
```python
# admin.py -- add require_admin to each GET handler signature

@router.get("/options", response_model=OptionsResponse)
async def get_options(user: dict = Depends(require_admin)):
    # body unchanged
    ...

@router.get("/users", response_model=AllowlistResponse)
async def list_allowed_users(user: dict = Depends(require_admin)):
    # body unchanged
    ...

# Same pattern for GET /settings/gemini, /settings/google-cloud, /settings/google-maps
```

### History User-Scoping
```python
# history.py
from app.core.auth import require_auth, is_user_admin

@router.get("/jobs")
async def get_jobs(
    tool: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    user: dict = Depends(require_auth),
):
    email = user.get("email", "")
    from app.services import firestore_service as db

    if is_user_admin(email):
        jobs = await db.get_recent_jobs(tool=tool, limit=limit)
    else:
        jobs = await db.get_user_jobs(user_id=email, tool=tool, limit=limit)

    # ... rest of handler (serialize, resolve names)
```

### Delete Ownership Check
```python
@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str, user: dict = Depends(require_auth)):
    from app.services import firestore_service as db

    job = await db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    email = user.get("email", "")
    job_owner = job.get("user_id", "")

    if job_owner != email and not is_user_admin(email):
        raise HTTPException(status_code=403, detail="You can only delete your own jobs")

    deleted = await db.delete_job(job_id)
    return {"success": True, "message": f"Job {job_id} deleted"}
```

### GHL smart_list_name Removal
```python
# models/ghl.py -- delete lines 113-117 (the smart_list_name field)
# Before:
class BulkSendRequest(BaseModel):
    connection_id: str = Field(...)
    contacts: list[BulkContactData] = Field(...)
    campaign_tag: str = Field(...)
    manual_sms: bool = Field(False)
    assigned_to_list: Optional[list[str]] = Field(None)
    smart_list_name: Optional[str] = Field(None, deprecated=True)  # DELETE THIS

# api/ghl.py line 343 -- simplify:
# Before: campaign_name = data.smart_list_name or data.campaign_tag
# After:  campaign_name = data.campaign_tag
```

```typescript
// frontend/src/utils/api.ts -- delete line 457
// Before:
interface BulkSendRequest {
  connection_id: string
  contacts: BulkContactData[]
  campaign_tag: string
  manual_sms: boolean
  assigned_to_list?: string[]
  smart_list_name?: string  // DELETE THIS
}
```

### Frontend 403 Modal Handling
```typescript
const handleDeleteJob = async (e: React.MouseEvent, job: Job) => {
  e.stopPropagation()
  if (!job.job_id) {
    setJobs((prev) => prev.filter((j) => j.id !== job.id))
    return
  }
  try {
    const response = await fetch(`${API_BASE}/history/jobs/${job.job_id}`, {
      method: 'DELETE',
      headers: await authHeaders(),
    })
    if (response.status === 403) {
      // Show modal with user-friendly message
      setDeleteError("You can only delete your own jobs")
      return
    }
    if (!response.ok) return
    setJobs((prev) => prev.filter((j) => j.id !== job.id))
    if (activeJob?.id === job.id) setActiveJob(null)
  } catch { /* network error, best-effort */ }
}
```

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 7.x + pytest-asyncio |
| Config file | `backend/pytest.ini` |
| Quick run command | `cd /Users/yojimbo/Documents/dev/toolbox/backend && python3 -m pytest tests/test_auth_enforcement.py -x -q` |
| Full suite command | `cd /Users/yojimbo/Documents/dev/toolbox/backend && python3 -m pytest -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AUTH-01 | Admin GET endpoints return 401 without auth | unit | `python3 -m pytest tests/test_auth_enforcement.py -x -q -k "admin_options or admin_users or admin_settings"` | Partially -- existing tests assert NO auth required (must be updated) |
| AUTH-02 | check_user remains unauthenticated | unit | `python3 -m pytest tests/test_auth_enforcement.py -x -q -k "admin_check_no_auth"` | Yes |
| AUTH-03 | Non-admin sees only own jobs | unit | `python3 -m pytest tests/test_auth_enforcement.py -x -q -k "history_scoped"` | No -- Wave 0 |
| AUTH-04 | Admin sees all jobs | unit | `python3 -m pytest tests/test_auth_enforcement.py -x -q -k "history_admin"` | No -- Wave 0 |
| AUTH-05 | Delete restricted to owner or admin | unit | `python3 -m pytest tests/test_auth_enforcement.py -x -q -k "delete_ownership"` | No -- Wave 0 |
| GHL-01 | smart_list_name removed from backend | unit | `python3 -m pytest tests/test_auth_enforcement.py -x -q -k "ghl_no_smart_list"` | No -- Wave 0 |
| GHL-02 | smart_list_name removed from frontend | manual-only | Grep search: `grep -r "smart_list_name" frontend/src/` returns 0 results | N/A |

### Sampling Rate
- **Per task commit:** `cd /Users/yojimbo/Documents/dev/toolbox/backend && python3 -m pytest tests/test_auth_enforcement.py -x -q`
- **Per wave merge:** `cd /Users/yojimbo/Documents/dev/toolbox/backend && python3 -m pytest -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] Update existing `test_admin_options_no_auth_required` -- flip assertion: now MUST return 401 without auth
- [ ] Update existing `test_admin_check_no_auth_required` -- keep as-is (still unauthenticated)
- [ ] Add tests for admin GET settings endpoints returning 401 without auth
- [ ] Add tests for admin GET endpoints returning 403 for non-admin authenticated users
- [ ] Add `admin_client` fixture to `conftest.py` (mock user with admin role)
- [ ] Add tests for history user-scoping (requires mocking `firestore_service.get_user_jobs`)
- [ ] Add tests for delete ownership (requires mocking `firestore_service.get_job`)

## Open Questions

1. **Profile image auth level**
   - What we know: Currently unauthenticated. CONTEXT leaves this to Claude's discretion.
   - Recommendation: `require_auth` (any authenticated user). Profile images are not sensitive admin data.

2. **GhlSendModal `smartListName` variable rename**
   - What we know: The state variable `smartListName` maps to `campaign_tag` in the request. Not a `smart_list_name` API reference.
   - Recommendation: Rename to `campaignTag` for clarity, but this is optional cleanup beyond GHL-01/GHL-02 scope.

## Sources

### Primary (HIGH confidence)
- `backend/app/core/auth.py` -- `require_admin`, `require_auth`, `is_user_admin` implementations verified
- `backend/app/api/admin.py` -- All 5 unprotected GET endpoints confirmed at lines 280, 290, 411, 475, 535
- `backend/app/api/history.py` -- Current handler lacks user parameter, `get_recent_jobs` returns all
- `backend/app/services/firestore_service.py` -- `get_user_jobs()` at line 210, `get_job()` at line 165, `delete_job()` at line 172
- `backend/app/models/ghl.py` -- `smart_list_name` field at line 113, no `model_config` (extra fields ignored by default)
- `backend/app/api/ghl.py` -- Fallback logic at line 343 confirmed
- `frontend/src/utils/api.ts` -- `smart_list_name` type at line 457
- `backend/app/main.py` -- Router mounting with auth dependencies at lines 73-86

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - no new libraries, all patterns already exist in codebase
- Architecture: HIGH - direct code inspection of all affected files
- Pitfalls: HIGH - verified Pydantic extra field behavior, identified legacy job edge case

**Research date:** 2026-03-18
**Valid until:** 2026-04-18 (stable -- internal codebase patterns, no external dependencies)

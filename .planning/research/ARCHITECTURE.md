# Architecture Patterns

**Domain:** v1.6 Integration -- Unified Enrichment Modal, RRC Fixes, Auth Hardening, GHL Cleanup
**Researched:** 2026-03-18
**Confidence:** HIGH (based on direct codebase analysis of all integration points)

## Current Architecture Snapshot

```
Frontend                          Backend
--------                          -------
EnrichmentToolbar (3 buttons)     POST /api/pipeline/cleanup
  -> useEnrichmentPipeline()      POST /api/pipeline/validate
     -> sequential await per step POST /api/pipeline/enrich
  -> usePreviewState()            (each returns PipelineResponse with ProposedChange[])
     -> updateEntries()
     -> editField()

Proration page                    POST /api/proration/rrc/fetch-missing
  -> fetch, replace rows            -> Firestore lookup -> individual RRC scrape
                                    -> BackgroundTasks for county download

Admin router (NO router-level auth)
  GET /users (no auth)            GET /settings/* (no auth)
  GET /users/{email}/check (no auth -- intentional for login flow)
  POST/PUT/DELETE /users (require_admin)

History router (router-level require_auth)
  GET /jobs (no user scoping)     GET /jobs/{id} (no ownership check)
  DELETE /jobs/{id} (no ownership check)
```

---

## Recommended Architecture Changes

### 1. Unified Enrichment Modal

**Pattern: Sequential Await with Progress Callback -- NOT SSE**

SSE is overkill. The existing `useEnrichmentPipeline` hook already does sequential `await` calls. The modal wraps the same 3 calls with a step-progress UI. Each step takes 2-15 seconds; SSE adds complexity (query-param auth, reconnection, event parsing) for 3 discrete status updates.

**New components:**

| Component | Type | Replaces/Modifies |
|-----------|------|-------------------|
| `EnrichmentModal.tsx` | NEW | Replaces `EnrichmentToolbar.tsx` (3 buttons) |
| `useEnrichmentPipeline.ts` | MODIFIED | Add `runAllSteps()` method for chained execution |
| Tool pages (Extract, Title, Proration, Revenue) | MODIFIED | Replace toolbar with single button + modal |

**Modal state machine:**

```
idle -> running:cleanup -> running:validate -> running:enrich -> review -> applied
             |                  |                  |
             v                  v                  v
       (auto-apply high     (auto-apply         (all changes
        confidence,          authoritative,       to review)
        update preview)      update preview)
```

**Key design decisions:**

1. **Auto-apply per step, accumulate review changes.** Don't wait until all 3 steps finish. Apply high-confidence cleanup results immediately, then start validation on the already-cleaned data. Validation runs on better input.

2. **Pass cleaned entries to subsequent steps.** Currently `runStep()` uses `previewEntries` at call time. After step 1 calls `updateEntries()`, React state updates, but the next `runStep` may see stale closure data. Solution: `runAllSteps()` maintains a local `currentEntries` variable that chains through steps without depending on React state timing.

```typescript
async function runAllSteps() {
  let currentEntries = [...previewEntries]

  // Step 1: Cleanup
  const cleanResult = await pipelineApi.cleanup(tool, currentEntries)
  currentEntries = applyHighConfidence(currentEntries, cleanResult.proposed_changes)
  updateEntries(currentEntries)  // live preview update
  accumulateForReview(cleanResult.proposed_changes.filter(c => c.confidence !== 'high'))

  // Step 2: Validate (uses cleaned data)
  const valResult = await pipelineApi.validate(tool, currentEntries)
  currentEntries = applyAuthoritative(currentEntries, valResult.proposed_changes)
  updateEntries(currentEntries)  // live preview update
  accumulateForReview(valResult.proposed_changes.filter(c => !c.authoritative))

  // Step 3: Enrich (uses validated data)
  const enrichResult = await pipelineApi.enrich(tool, currentEntries)
  accumulateForReview(enrichResult.proposed_changes)  // all to review, no auto-apply
}
```

3. **Progress model:** 3 discrete steps, not a continuous bar. Show step name + spinner for current, checkmark for completed, gray for pending. Include entry count per step (e.g., "Validated 42/42 addresses").

4. **Skip unavailable steps.** If Gemini is not configured, skip cleanup and move to validate. If Maps is not configured, skip validate. The modal adapts to what's enabled, running only available steps.

5. **Cumulative highlight keys.** Current `recentlyAppliedKeys` resets per step. The modal accumulates across all steps, clearing only when the modal closes.

**Data flow for live preview updates:**

```
User clicks "Enrich All" button -> modal opens

Modal Step 1 (cleanup):
  POST /api/pipeline/cleanup with currentEntries
  -> auto-apply high-confidence to currentEntries
  -> updateEntries(currentEntries) -> table re-renders live
  -> accumulate medium/low for final review

Modal Step 2 (validate):
  POST /api/pipeline/validate with currentEntries (cleaned)
  -> auto-apply authoritative address corrections
  -> updateEntries(currentEntries) -> table re-renders live
  -> accumulate partial-confidence for review

Modal Step 3 (enrich):
  POST /api/pipeline/enrich with currentEntries (validated)
  -> all enrichment changes go to review (never auto-apply contact data)

Modal Review:
  -> show accumulated medium/low changes from all 3 steps
  -> user checks/unchecks, clicks Apply
  -> single batch apply to previewEntries
  -> modal closes
```

### 2. RRC Fetch-Missing: Compound Lease Splitting

**Where:** `backend/app/api/proration.py` in `fetch_missing_rrc_data()`, plus new utility

**Current problem:** A row with `rrc_lease = "08-41100"` does a single lookup. But some properties have compound leases like `"08-41100 / 08-41200"` that need splitting into separate lookups and combining results.

**New file:** `backend/app/services/proration/lease_parser.py`

```python
def split_compound_lease(rrc_lease: str) -> list[tuple[str, str]]:
    """Split compound lease strings into individual (district, lease) pairs.

    Handles: "08-41100 / 08-41200", "08-41100/08-41200", "08-41100, 08-41200"
    Returns: [("08", "41100"), ("08", "41200")]
    """
    parts = re.split(r'[/,]', rrc_lease)
    results = []
    for part in parts:
        part = part.strip()
        if '-' in part:
            d, l = part.split('-', 1)
            results.append((d.strip().zfill(2), l.strip()))
    return results
```

**Integration point:** In `fetch_missing_rrc_data()`, replace the single `district/lease_number` parse with:

```python
lease_pairs = split_compound_lease(row.rrc_lease) if row.rrc_lease else []
if len(lease_pairs) <= 1:
    # existing single-lease path
else:
    # compound: lookup each, sum acres
    total_acres = 0
    found_count = 0
    for d, l in lease_pairs:
        rrc_info = await lookup_rrc_acres(d, l)
        if rrc_info:
            total_acres += float(rrc_info.get("acres", 0))
            found_count += 1
    if found_count == len(lease_pairs):
        row.rrc_acres = total_acres
        row.fetch_status = "split_found"
    elif found_count > 0:
        row.rrc_acres = total_acres
        row.fetch_status = "split_partial"
    else:
        # add all to missing_leases for individual scrape
```

**Per-row status values (existing + new):**

| Status | Meaning |
|--------|---------|
| `found` | Direct match (existing) |
| `not_found` | No match after all attempts (existing) |
| `split_found` | Compound lease split, all parts matched (NEW) |
| `split_partial` | Compound lease split, some parts matched (NEW) |

**Acres aggregation:** Sum acres from all matched parts. NRA calculation uses total lease acres, so summing is correct for compound leases on the same property.

### 3. Admin Auth Hardening

**Current state:** Admin router has NO router-level auth. Intentional for `check_user` (login flow) and profile images. But `GET /users`, `GET /settings/*`, `GET /preferences/*` are all unauthenticated -- leaks config.

**Approach: Per-endpoint Depends, not router-level.**

Cannot use router-level `dependencies=[Depends(require_auth)]` because `check_user` must stay unauthenticated. Add `Depends` to individual endpoints.

| Endpoint | Current Auth | Target Auth | Rationale |
|----------|-------------|-------------|-----------|
| `GET /options` | None | `require_auth` | Options harmless but should require login |
| `GET /users` | None | **`require_admin`** | User list is sensitive (emails, roles) |
| `POST /users` | `require_admin` | `require_admin` | Already correct |
| `PUT /users/{email}` | `require_admin` | `require_admin` | Already correct |
| `DELETE /users/{email}` | `require_admin` | `require_admin` | Already correct |
| `GET /users/{email}/check` | None | **None** | Must stay unauthenticated (login flow) |
| `GET /settings/gemini` | None | `require_auth` | Config read should require login |
| `PUT /settings/gemini` | `require_admin` | `require_admin` | Already correct |
| `GET /settings/google-cloud` | None | `require_auth` | Config read should require login |
| `PUT /settings/google-cloud` | `require_admin` | `require_admin` | Already correct |
| `GET /settings/google-maps` | None | `require_auth` | Config read should require login |
| `PUT /settings/google-maps` | `require_admin` | `require_admin` | Already correct |
| `GET /preferences/{email}` | None | `require_auth` | User data |
| `PUT /preferences/{email}` | None | `require_auth` | User data |
| `POST /upload-profile-image` | None | `require_auth` | Write operation |
| `GET /profile-image/{user_id}` | None | **None** | Images can stay public (served to `<img>` tags) |

**Implementation:** Add `user: dict = Depends(require_auth)` or `Depends(require_admin)` to each function signature. No architectural changes, just decorator additions.

### 4. History Auth: User-Scoped Queries

**Current state:** `GET /api/history/jobs` has router-level `require_auth` but returns ALL jobs. Any authenticated user can see all users' jobs.

**Critical FastAPI subtlety:** Router-level `dependencies=[Depends(require_auth)]` enforces the check but does NOT inject the user dict into route handlers. Each handler that needs user context must declare its own `user: dict = Depends(require_auth)` parameter. The dependency runs twice (router-level + handler-level) but Firebase token verification is cheap.

**Implementation:**

```python
@router.get("/jobs")
async def get_jobs(
    tool: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    user: dict = Depends(require_auth),  # ADD: gives us user email
):
    from app.core.auth import is_user_admin
    show_all = is_user_admin(user.get("email", ""))
    user_filter = None if show_all else user.get("email")
    jobs = await db.get_recent_jobs(tool=tool, limit=limit, user_id=user_filter)
```

**Firestore query change** in `firestore_service.py`:

```python
async def get_recent_jobs(tool=None, limit=50, user_id=None):
    query = db.collection("jobs").order_by("created_at", direction=firestore.Query.DESCENDING)
    if tool:
        query = query.where("tool", "==", tool)
    if user_id:
        query = query.where("user_id", "==", user_id)  # ADD
    query = query.limit(limit)
```

**Also scope:** `DELETE /jobs/{job_id}` and `GET /jobs/{job_id}` -- verify job's `user_id` matches requester (or requester is admin).

### 5. GHL smart_list_name Cleanup

**Current state:** `BulkSendRequest.smart_list_name` is deprecated but still used:

```python
# backend/app/api/ghl.py line 343
campaign_name = data.smart_list_name or data.campaign_tag
```

**Changes:**

1. Remove `smart_list_name` from `BulkSendRequest` model in `models/ghl.py`
2. Change line 343 to `campaign_name = data.campaign_tag`
3. Remove `smart_list_name` from frontend `api.ts` if referenced
4. Historical Firestore docs with `smart_list_name` don't need migration

---

## Component Boundaries

| Component | Responsibility | Communicates With | Change Type |
|-----------|---------------|-------------------|-------------|
| `EnrichmentModal.tsx` | Orchestrates 3-step pipeline, shows progress + review | `useEnrichmentPipeline`, `usePreviewState` | NEW |
| `useEnrichmentPipeline.ts` | Runs pipeline steps, manages proposed changes | `pipelineApi`, receives `updateEntries` callback | MODIFIED (add `runAllSteps`) |
| `usePreviewState.ts` | Single source of truth for table data | Tool pages, enrichment hooks | UNCHANGED |
| `EnrichmentToolbar.tsx` | 3 separate buttons | -- | REMOVE |
| `ProposedChangesSummary.tsx` | Shows change review UI | Moved inside `EnrichmentModal` | RELOCATED |
| `lease_parser.py` | Compound lease string parsing | `fetch_missing_rrc_data` | NEW |
| `fetch_missing_rrc_data()` | RRC lookup with compound lease support | `lease_parser`, Firestore | MODIFIED |
| Admin endpoints | Per-endpoint auth decorators | `require_auth`, `require_admin` | MODIFIED |
| History endpoints | User-scoped job queries | `firestore_service`, `require_auth` | MODIFIED |
| `BulkSendRequest` model | GHL bulk send request shape | `ghl.py` endpoint | MODIFIED (remove field) |

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: SSE for Short-Lived Sequential Operations
**What:** Using Server-Sent Events for the enrichment modal progress.
**Why bad:** Each pipeline step is a single HTTP request taking 2-15 seconds. SSE adds complexity (reconnection, query-param auth, event parsing) for 3 discrete status updates. The GHL bulk send uses SSE because it processes hundreds of contacts over minutes -- that is the right use case.
**Instead:** Sequential await with state updates after each step.

### Anti-Pattern 2: Running Pipeline Steps in Parallel
**What:** `Promise.all([cleanup, validate, enrich])` to speed up enrichment.
**Why bad:** Steps are intentionally sequential. Cleanup fixes name casing before address validation, which fixes addresses before contact enrichment. Parallel means enrichment searches for uncleaned names at uncorrected addresses.
**Instead:** Sequential with inter-step data passthrough via local variable (not React state).

### Anti-Pattern 3: New Unified Pipeline Backend Endpoint
**What:** Creating `POST /api/pipeline/run-all` that runs all 3 steps server-side.
**Why bad:** Loses the ability to update the preview table between steps. The modal's value is showing live progress. A single endpoint is a black box until completion.
**Instead:** Keep 3 separate endpoints, orchestrate from frontend modal.

### Anti-Pattern 4: Router-Level Auth on Admin Router
**What:** Adding `dependencies=[Depends(require_auth)]` to the admin router include.
**Why bad:** Breaks `check_user` endpoint which must remain unauthenticated (login flow checks allowlist before user has auth context in the app).
**Instead:** Per-endpoint `Depends()` on each handler that needs auth.

### Anti-Pattern 5: Relying on Router-Level Depends for User Context
**What:** Assuming the `user` dict from router-level `dependencies=[Depends(require_auth)]` is available in route handlers.
**Why bad:** Router-level dependencies enforce the check but do NOT inject into handler parameters. The handler gets no `user` variable.
**Instead:** Declare `user: dict = Depends(require_auth)` in each handler that needs user context. The duplicate call is cheap.

---

## Suggested Build Order

Based on dependency analysis and risk:

| Order | Task | Effort | Dependencies | Type |
|-------|------|--------|-------------|------|
| 1 | GHL `smart_list_name` removal | 0.5h | None | Backend + frontend |
| 2 | Admin auth hardening (per-endpoint Depends) | 1h | None | Backend only |
| 3 | History user-scoping + ownership checks | 1h | Pattern from #2 | Backend only |
| 4 | RRC compound lease splitting | 2h | None | Backend + minor frontend |
| 5 | Unified enrichment modal | 4h | Stable pipeline API | Frontend (largest change) |

**Rationale:**
- Steps 1-3 are backend-only, low-risk, independently shippable
- Step 4 is backend with minor frontend (display new `fetch_status` values)
- Step 5 is the largest frontend change; benefits from stable backend; touches 4 tool pages
- Steps 1-4 can be done in any order; step 5 should go last

---

## Sources

- `backend/app/api/pipeline.py` -- Pipeline endpoint implementation (3 endpoints, PipelineResponse format)
- `backend/app/api/admin.py` -- Admin auth patterns (mix of authenticated and unauthenticated)
- `backend/app/api/history.py` -- History endpoint (no user scoping, no ownership checks)
- `backend/app/api/ghl.py` -- SSE pattern reference (Firestore polling, query-param auth), `smart_list_name` usage
- `backend/app/api/proration.py` -- `fetch_missing_rrc_data()` implementation
- `backend/app/models/proration.py` -- `MineralHolderRow.fetch_status` field
- `backend/app/models/pipeline.py` -- `PipelineRequest/Response/ProposedChange` models
- `backend/app/main.py` -- Router auth dependency patterns (lines 72-86)
- `frontend/src/hooks/useEnrichmentPipeline.ts` -- Pipeline orchestration (sequential runStep)
- `frontend/src/hooks/usePreviewState.ts` -- Preview state management (updateEntries preserves edits)
- `frontend/src/components/EnrichmentToolbar.tsx` -- Current 3-button toolbar (to be replaced)

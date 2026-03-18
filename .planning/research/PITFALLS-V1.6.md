# Domain Pitfalls: v1.6 Pipeline Fixes & Unified Enrichment

**Domain:** Adding unified enrichment modal, RRC fetch-missing fixes, admin/history auth hardening, GHL legacy cleanup to existing app
**Researched:** 2026-03-18
**Confidence:** HIGH (based on codebase inspection, not external research)

## Critical Pitfalls

### Pitfall 1: Unified Enrichment Modal Race Condition on Double-Click

**What goes wrong:** User clicks the unified "Enrich" button, modal opens, pipeline starts. User clicks again (impatient) or closes/reopens modal. Two pipeline runs execute concurrently against the same preview state. Both apply changes, causing duplicate mutations, corrupted entries, or lost edits.

**Why it happens:** The current `useEnrichmentPipeline` hook tracks `isProcessing` via `activeAction !== null`, but there is no server-side idempotency guard. The pipeline API endpoints (`/api/pipeline/*`) are stateless -- they process whatever entries are sent. If two requests overlap, both return proposed changes against the same snapshot, and applying both corrupts state. The existing 3-button UI has the same vulnerability (noted in STATE.md as a known concern), but a modal makes it worse because the "run all steps sequentially" flow is longer-running.

**Consequences:** Duplicate proposed changes applied. Preview entries mutated twice (e.g., address validated then overwritten by second validation run). Undo state becomes inconsistent -- undoing one run partially reverts the other.

**Prevention:**
- Add a `pipelineRunId` (UUID) to the modal. On open, generate new ID. On close, abort any in-flight requests for that ID.
- Use `AbortController` in the fetch calls so closing the modal cancels pending API requests.
- Server-side: consider a short-lived lock per job/tool (optional -- client-side guard is sufficient for single-user tool).
- Disable the trigger button entirely while modal is open and processing. Not just `isProcessing` check -- the button that opens the modal should be disabled too.

**Detection:** Two sets of proposed changes appearing in rapid succession. Console errors about state updates on unmounted components.

**Phase to address:** Unified enrichment modal phase -- must be built into modal from the start.

---

### Pitfall 2: check_user Endpoint Breaks When Admin Router Gets Auth

**What goes wrong:** Adding `require_auth` to the admin router's `GET /users/{email}/check` endpoint causes a login deadlock. The frontend's `AuthContext.tsx` calls `check_user` immediately after Firebase sign-in to verify the user is in the allowlist. But `require_auth` needs a valid, verified token -- which the frontend doesn't consider "complete" until `check_user` returns `allowed: true`. Result: infinite 401 loop, no one can log in.

**Why it happens:** The admin router is currently mounted WITHOUT router-level auth (`main.py` line 80: `app.include_router(admin_router, prefix="/api/admin", tags=["admin"])`). This was a deliberate decision (documented in PROJECT.md key decisions). The `check_user` endpoint is intentionally unauthenticated because it's part of the login flow itself. Adding blanket auth to the admin router breaks this specific endpoint.

**Consequences:** Complete login failure for all users. No one can access the app. Production outage.

**Prevention:**
- Add auth per-endpoint on admin routes, NOT at the router level via `dependencies=[Depends(require_auth)]`.
- `check_user` must remain unauthenticated (or use a weaker auth that accepts any valid Firebase token without checking the allowlist).
- The GET settings endpoints (`/settings/gemini`, `/settings/google-maps`, etc.) are the ones that need `require_admin` added. Add `Depends(require_admin)` to each GET handler individually.
- Test the login flow end-to-end after any auth changes: sign out, sign in, verify check_user still works.

**Detection:** 401 responses from `/api/admin/users/{email}/check` in browser devtools during login. App stuck on login screen.

**Phase to address:** Auth hardening phase -- first thing to test after any admin auth change.

---

### Pitfall 3: History User-Scoping Breaks Admin Dashboard

**What goes wrong:** Adding `user_id` filtering to `/api/history/jobs` so users only see their own jobs inadvertently hides all jobs from the admin. The admin needs to see everyone's jobs for oversight. If the filter is applied unconditionally, the dashboard's "Recent Jobs" section shows nothing for admin when other users uploaded files.

**Why it happens:** The history router already has router-level auth (`main.py` line 81: `dependencies=[Depends(require_auth)]`), but the `get_jobs` endpoint doesn't receive the authenticated user. Adding a `user_id` filter requires injecting the current user and deciding when to apply the filter. Naive implementation: always filter by `user_id`. Correct implementation: filter by `user_id` unless user is admin.

**Consequences:** Admin sees empty job history. Dashboard appears broken. Admin loses ability to review other users' work.

**Prevention:**
- Add `user: dict = Depends(require_auth)` to the `get_jobs` handler (this requires making `require_auth` return user data, which it already does).
- Check `is_user_admin(user["email"])`. If admin, return all jobs (existing behavior). If non-admin, filter by `user_id == user["email"]`.
- Add a `?all=true` query param that only admins can use (explicit opt-in for admin view).
- Also scope `delete_job` -- non-admin should only delete their own jobs.

**Detection:** Admin dashboard showing 0 jobs after the change. Non-admin seeing other users' jobs (if filter was accidentally omitted).

**Phase to address:** History user-scoping phase -- must include admin bypass logic.

---

### Pitfall 4: Compound Lease Splitting Produces Wrong District-Lease Pairs

**What goes wrong:** The existing `split_lease_number` splits on `/` and `,`, but the current implementation treats each split result as a full compound value. For input like `"12345/12346"` (no district prefix), it splits into `["12345", "12346"]` which are then treated as lease numbers without district context. For `"02-12345/12346"`, it splits into `["02-12345", "12346"]` -- the second part loses its district prefix, causing lookup against wrong district or no district.

**Why it happens:** Real-world compound leases come in multiple formats:
- `"02-12345/02-12346"` -- each part has district (handled correctly)
- `"02-12345/12346"` -- second part inherits district from first (NOT handled)
- `"12345/12346"` -- no district on either (district comes from the row's `district` field)
- `"02-12345, 02-12346"` -- comma with spaces

The current `split_lease_number` just splits on delimiters. It does not propagate the district from the first part to subsequent parts. The main lookup loop at line 378 only uses `row.district` and `row.lease_number` -- it never calls `split_lease_number` on the rrc_lease field.

**Consequences:** Compound lease rows remain "not_found" even when individual leases exist in Firestore. The `split_lease_number` function exists but is never integrated into the fetch-missing loop.

**Prevention:**
- After splitting, check if each part contains a district prefix (has `-`). If not, inherit the district from the first part or from `row.district`.
- Actually call `split_lease_number` in the fetch-missing loop when `rrc_lease` contains `/` or `,`.
- For split leases, look up each sub-lease and pick the result with the highest `acres` value (or aggregate if that's the domain logic).
- Set `fetch_status = "split_lookup"` to distinguish from single-lease matches.
- Test with real compound lease data from uploaded CSVs.

**Detection:** Rows with `/` or `,` in rrc_lease still showing "not_found" after fetch-missing runs. The `split_lease_number` function having zero callers outside tests.

**Phase to address:** RRC fetch-missing phase -- must integrate split logic into the lookup loop.

---

### Pitfall 5: Removing smart_list_name Breaks In-Flight Firestore Jobs

**What goes wrong:** Existing GHL send jobs stored in Firestore reference `smart_list_name` in their campaign metadata. If the field is removed from `BulkSendRequest` model and the fallback logic at `ghl.py` line 343 (`campaign_name = data.smart_list_name or data.campaign_tag`), any code that reads old job records and expects `smart_list_name` will break. Additionally, the frontend `api.ts` line 457 still defines `smart_list_name` -- if the backend model removes it, in-flight requests from old cached frontends will get 422 validation errors.

**Why it happens:** The field is marked `deprecated=True` in the Pydantic model but is still actively used in the fallback expression on line 343. Old jobs in Firestore have `campaign_name` values that came from `smart_list_name`. Removing the field from the model means old API clients (cached frontend builds) send a field the backend no longer accepts.

**Consequences:** Pydantic strict validation rejects requests with unknown `smart_list_name` field (422 error). Users with cached frontends get "Unprocessable Entity" errors on GHL send. History/job display may break if it reads campaign metadata that referenced the old field name.

**Prevention:**
- Remove `smart_list_name` from the frontend `api.ts` FIRST (stop sending it).
- Keep `smart_list_name` in the backend `BulkSendRequest` model for one release cycle with `deprecated=True` and `exclude=True` or just ignore it. Pydantic v2 by default ignores extra fields unless `model_config = ConfigDict(extra='forbid')` -- check the model config.
- Simplify the fallback: change line 343 to just `campaign_name = data.campaign_tag` (campaign_tag is already required).
- Do NOT touch existing Firestore documents -- they store `campaign_name` (the resolved value), not `smart_list_name`.
- Deploy backend with the field still accepted but unused, then deploy frontend without it, then remove from backend.

**Detection:** 422 errors in production after backend deploy but before frontend cache clears. GHL send button failing with validation errors.

**Phase to address:** GHL cleanup phase -- two-step removal (frontend first, then backend).

---

## Moderate Pitfalls

### Pitfall 6: Streaming Preview Updates Cause Render Thrashing

**What goes wrong:** The unified enrichment modal runs cleanup -> validate -> enrich sequentially. If each step updates the preview table in real-time (entry by entry or batch by batch), React re-renders the entire table on each update. With 50+ rows, this causes visible jank, input lag, and potentially dropped frames. Users see the table "flickering" during enrichment.

**Why it happens:** The current `useEnrichmentPipeline` hook calls `updateEntries` (which sets state) after each step completes. If the modal streams intermediate results (e.g., address validation results as they come back), each partial update triggers a full table re-render. React 19's concurrent features don't help if state updates are synchronous.

**Prevention:**
- Batch state updates: collect all proposed changes from a step before calling `updateEntries` once.
- Use `React.startTransition` for preview updates so they don't block the progress bar animation.
- Don't update the preview table mid-step. Show progress in the modal, update table only when each step completes.
- Consider virtualized rendering (react-window) if table exceeds 100 rows -- but this is likely premature for current data volumes.

**Phase to address:** Unified enrichment modal phase.

---

### Pitfall 7: Admin Settings GET Endpoints Leak API Keys

**What goes wrong:** `GET /settings/gemini` and similar settings read endpoints are currently unauthenticated (no `Depends(require_auth)` or `Depends(require_admin)`). Any authenticated user (or if someone finds the endpoint, any visitor) can read the app's AI configuration, enabled features, and whether API keys are configured. While the keys are masked (`has_key: true/false`), the configuration exposure is still a security issue.

**Why it happens:** The admin router was intentionally excluded from router-level auth (see Pitfall 2). The GET settings handlers were added without per-endpoint auth, likely assuming the router would eventually get auth. The PUT handlers correctly use `Depends(require_admin)`, but the GET handlers have no auth at all.

**Prevention:**
- Add `Depends(require_auth)` (not `require_admin`) to settings GET endpoints. Any authenticated user should be able to read feature flags (needed for UI rendering). Only admin can write.
- Or add `Depends(require_admin)` if settings should be admin-only reads. Check which frontend pages call these endpoints and whether non-admin users need the data.

**Phase to address:** Auth hardening phase.

---

### Pitfall 8: Enrichment Modal State Persists Across Tool Pages

**What goes wrong:** If the enrichment modal is implemented as a shared component and the user navigates away (e.g., from Extract to Title) while enrichment is running, the in-flight API calls continue. When the user returns or opens the modal on a different tool, stale results from the previous tool's enrichment may appear, or the state may be corrupted.

**Why it happens:** React state in hooks persists within a component's lifecycle. If the modal is a shared component mounted in `MainLayout`, it doesn't unmount on page navigation (React Router renders via `<Outlet />`). The `useEnrichmentPipeline` hook is per-page (each tool page has its own instance), but if the modal component is shared, its internal state may not reset.

**Prevention:**
- Keep the modal component per-page (each tool page renders its own modal instance). This ensures unmounting on navigation cleans up state.
- Use `AbortController` cleanup in `useEffect` return to cancel in-flight requests on unmount.
- If using a shared modal, key it by tool name (`<EnrichmentModal key={tool} .../>`) to force remount on tool change.

**Phase to address:** Unified enrichment modal phase.

---

### Pitfall 9: RRC Rate Limiting on Compound Lease Expansion

**What goes wrong:** A compound lease like `"02-12345/02-12346/02-12347"` expands to 3 individual lookups. If a CSV has 20 rows with compound leases averaging 2-3 sub-leases each, the 25-query cap (`MAX_INDIVIDUAL_QUERIES`) is hit quickly. Worse, the expansion happens inside the cap -- meaning some rows never get looked up because the budget was consumed by expanded sub-leases from earlier rows.

**Why it happens:** The cap at line 429 (`if len(unique_leases) > MAX_INDIVIDUAL_QUERIES`) applies after deduplication but before expansion. If compound leases are split inside the lookup loop, each split produces additional queries that weren't counted toward the cap.

**Prevention:**
- Split compound leases BEFORE the cap check, not inside the lookup loop.
- Count expanded leases toward the budget: `unique_leases` should contain the expanded set.
- Consider raising `MAX_INDIVIDUAL_QUERIES` modestly (25 -> 50) since individual HTML queries are lightweight compared to county downloads.
- Prioritize rows by: single-lease rows first (guaranteed 1 query each), then compound rows.

**Phase to address:** RRC fetch-missing phase.

---

## Minor Pitfalls

### Pitfall 10: GHL Field Removal Without Frontend Type Sync

**What goes wrong:** Backend removes `smart_list_name` from the Pydantic model but the frontend TypeScript type in `api.ts` still defines it as optional. TypeScript doesn't error because it's optional. Code that references `smart_list_name` continues to compile but sends a field the backend ignores (or rejects).

**Prevention:**
- Search the entire frontend for `smart_list_name` references. Remove from type definitions, form state, and any UI labels.
- Check `GhlSendModal.tsx` for any reference to SmartList or smart_list_name in form fields or labels.

**Phase to address:** GHL cleanup phase.

---

### Pitfall 11: History Delete Endpoint Missing User Authorization

**What goes wrong:** `DELETE /api/history/jobs/{job_id}` deletes any job by ID. After adding user-scoping to the GET endpoint, the DELETE endpoint still allows any authenticated user to delete any job. A non-admin user could delete another user's jobs.

**Prevention:**
- Add ownership check to `delete_job`: load the job, compare `user_id` with the authenticated user's email.
- Allow admin to delete any job (admin bypass).

**Phase to address:** History user-scoping phase.

---

### Pitfall 12: Enrichment Pipeline Timeout on Large Datasets

**What goes wrong:** Running cleanup -> validate -> enrich sequentially in a modal. Each step calls an API endpoint that processes all entries. For 100+ entries with external API calls (address validation, contact enrichment), the total pipeline duration exceeds the frontend fetch timeout or the user's patience. The modal shows a spinning progress bar for 5+ minutes.

**Prevention:**
- Show per-step progress (e.g., "Step 2/3: Validating addresses... 45/100").
- Add ETA calculation based on per-entry processing speed (measure first few entries, extrapolate).
- Allow cancellation mid-pipeline (AbortController + backend support for early termination).
- Consider making each step independently completable -- if validation times out, show partial results and let user retry.

**Phase to address:** Unified enrichment modal phase.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Unified enrichment modal | Race condition on re-trigger (Pitfall 1) | AbortController + pipelineRunId, disable button during processing |
| Unified enrichment modal | Render thrashing from streaming updates (Pitfall 6) | Batch state updates per-step, not per-entry |
| Unified enrichment modal | Cross-page state leakage (Pitfall 8) | Per-page modal instance or key by tool name |
| Unified enrichment modal | Pipeline timeout (Pitfall 12) | Per-step progress, ETA, cancellation support |
| Admin auth hardening | check_user login deadlock (Pitfall 2) | Per-endpoint auth, NOT router-level. check_user stays unauthenticated |
| Admin auth hardening | Settings endpoints leaking config (Pitfall 7) | Add require_auth to GET settings endpoints individually |
| History user-scoping | Admin loses visibility (Pitfall 3) | Admin bypass: skip user_id filter for admin role |
| History user-scoping | Delete without ownership check (Pitfall 11) | Add user_id check to delete_job, admin bypass |
| RRC fetch-missing | split_lease_number never called (Pitfall 4) | Integrate into fetch-missing loop, test with compound lease CSV |
| RRC fetch-missing | Rate limit budget consumed by expansion (Pitfall 9) | Expand before cap check, count expanded leases |
| GHL cleanup | In-flight 422 from cached frontend (Pitfall 5) | Two-step removal: frontend first, backend second |
| GHL cleanup | TypeScript type not updated (Pitfall 10) | Search and remove all frontend references |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Admin router auth | Adding `dependencies=[Depends(require_auth)]` to `include_router` | Add per-endpoint `Depends()` to each handler, skip check_user |
| History filtering | `db.get_recent_jobs(user_id=user_email)` without admin check | Check admin role first, pass `user_id=None` for admin |
| Enrichment modal | Sharing modal component across pages via layout | Each page renders its own modal instance, cleans up on unmount |
| GHL field removal | Removing backend field first | Remove from frontend first, keep backend field deprecated for 1 release |
| Compound lease split | Splitting inside the per-row loop after cap check | Split all leases first, deduplicate, then apply cap |
| Pipeline state | Updating preview entries per-change during pipeline | Collect all changes per step, apply once when step completes |

## "Looks Done But Isn't" Checklist

- [ ] **check_user still works:** After admin auth changes, test full login flow (sign out -> sign in -> verify dashboard loads)
- [ ] **Admin sees all jobs:** After history scoping, verify admin dashboard shows jobs from all users
- [ ] **Non-admin sees only own jobs:** After history scoping, verify non-admin sees only their uploads
- [ ] **split_lease_number is called:** Verify the function is actually invoked in the fetch-missing loop, not just defined
- [ ] **Compound lease district propagation:** Test "02-12345/12346" -- second part should use district "02"
- [ ] **Modal cleanup on close:** Close the modal mid-pipeline, verify no console errors or orphaned API calls
- [ ] **smart_list_name removed from frontend:** Search for "smart_list" in all .tsx and .ts files, zero results
- [ ] **Settings GET endpoints require auth:** Unauthenticated request to `/api/admin/settings/gemini` returns 401
- [ ] **Pipeline abort works:** Start enrichment, close modal, verify no state corruption in preview table
- [ ] **Delete job ownership:** Non-admin user cannot delete another user's job (returns 403)

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| check_user deadlock (Pitfall 2) | LOW | Revert admin router auth change, redeploy. 5 minute fix. |
| Admin can't see jobs (Pitfall 3) | LOW | Add admin bypass to query, redeploy. |
| Race condition corrupted preview (Pitfall 1) | MEDIUM | User refreshes page, re-uploads file. No persistent data loss since preview is in-memory. |
| 422 from cached frontend (Pitfall 5) | LOW | Keep backend field for backwards compat. Hard refresh clears frontend cache. |
| Compound leases still not found (Pitfall 4) | LOW | Fix integration in fetch-missing loop, users re-run "Fetch Missing". |
| Settings data leaked (Pitfall 7) | LOW | Add auth, redeploy. No API keys exposed (only has_key boolean). |

---
*Pitfalls research for: v1.6 Pipeline Fixes & Unified Enrichment*
*Researched: 2026-03-18*

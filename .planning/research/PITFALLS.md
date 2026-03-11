# Domain Pitfalls

**Domain:** Security hardening of a production FastAPI + React internal toolbox
**Researched:** 2026-03-11
**Confidence:** HIGH (based on direct codebase analysis + established patterns for retroactive auth hardening)

## Critical Pitfalls

Mistakes that cause outages, security regressions, or require rewrites.

---

### Pitfall 1: Locking Out the Only Admin During Auth Rollout

**What goes wrong:** Adding `Depends(require_auth)` to all routes simultaneously breaks the `/api/admin/users/{email}/check` endpoint that the frontend's `AuthContext.tsx` calls *before* the user is fully authenticated. The frontend calls `checkAuthorization()` at line 46 without an auth token (it's a pre-auth check). If that endpoint now requires auth, the frontend enters a dead loop: can't check authorization without a token, can't get authorized without passing the check.

**Why it happens:** The current auth flow is: Firebase sign-in -> frontend calls `/admin/users/{email}/check` (unauthenticated) -> if allowed, proceed. This is a chicken-and-egg dependency that breaks when you blanket-apply auth.

**Consequences:** All users locked out of the application, including the admin who would need to fix it. Production outage with no self-service recovery path.

**Prevention:**
1. Map the exact auth flow before touching any routes: Firebase sign-in -> token acquisition -> authorization check -> app access.
2. Move the allowlist check INTO `get_current_user` / `require_auth` itself (the dependency already has the email from the decoded token at line 329 of `auth.py`). This eliminates the need for the unauthenticated `/check` endpoint entirely.
3. If keeping `/check` as a separate endpoint, explicitly exclude it from auth requirements or redesign it to accept a Bearer token.
4. Deploy auth changes behind a feature flag or environment variable so you can roll back without a code deploy.

**Detection:** Test the full sign-in flow in a staging environment before deploying. Specifically test: fresh browser -> Google sign-in -> app loads. If the app shows "not authorized" or hangs on loading, this pitfall has been hit.

**Phase:** Must be addressed in the FIRST phase, before any other auth work begins.

---

### Pitfall 2: Frontend `return true` on Backend Failure Negates All Backend Auth

**What goes wrong:** `AuthContext.tsx` line 54-55: when the backend is unreachable or returns an error, `checkAuthorization` returns `true`. This means if the backend is slow, temporarily down, or returns a 401/403 after auth is added, the frontend silently grants access. Any backend auth hardening is undermined by the frontend's fail-open behavior.

**Why it happens:** Added as a dev convenience ("if backend is unavailable, allow access") but shipped to production. It's easy to forget this exists because it only triggers during error conditions.

**Consequences:** Users who should be rejected (removed from allowlist, unauthorized) can access the frontend and make API calls if the backend check fails for any reason. Combined with the current `allow_origins=["*"]` CORS, this is exploitable.

**Prevention:**
1. Change the catch block to `return false` (fail-closed).
2. Add a clear "Backend unavailable" error state in the UI instead of silently granting access.
3. For local development, use `import.meta.env.DEV` to conditionally allow the fail-open behavior.

**Detection:** Search for `return true` in catch blocks within auth-related frontend code. Test by stopping the backend and verifying the frontend shows an error, not the app.

**Phase:** Must be fixed in the same deployment as backend auth hardening. Fixing backend without fixing frontend creates a false sense of security.

---

### Pitfall 3: CORS `allow_origins=["*"]` with `allow_credentials=True` Is Invalid Per Spec

**What goes wrong:** The current CORS config (`main.py` line 50-55) sets `allow_origins=["*"]` with `allow_credentials=True`. Per the CORS specification, browsers MUST reject responses with `Access-Control-Allow-Origin: *` when credentials are included. Some browsers enforce this strictly, others don't. When you tighten CORS to specific origins, you may break the frontend if the origin doesn't exactly match (e.g., trailing slash, www vs non-www, http vs https).

**Why it happens:** The wildcard was set during development and never updated. The comment on line 51 literally says "In production, specify allowed origins" but nobody did.

**Consequences:**
- If tightened incorrectly, every API call from the frontend fails with CORS errors. Users see a blank/broken app.
- Common mistake: setting `allow_origins=["https://tools.tablerocktx.com"]` but forgetting `http://localhost:5173` for development, breaking local dev.

**Prevention:**
1. Use an environment variable for allowed origins: `CORS_ORIGINS=https://tools.tablerocktx.com` in production, `http://localhost:5173,http://localhost:8000` in development.
2. Parse the env var as a comma-separated list in `config.py`.
3. Test CORS changes from the actual production domain, not just local dev (use the browser network tab to verify `Access-Control-Allow-Origin` header).
4. Keep `allow_credentials=True` only when origins are explicitly listed (not `*`).

**Detection:** After deploying CORS changes, check the browser console for `CORS policy` errors. Test from both production URL and local dev.

**Phase:** CORS lockdown should be deployed together with auth hardening, not separately.

---

### Pitfall 4: Firestore Revenue Subcollection Migration Loses Production Data

**What goes wrong:** Moving revenue `rows` from an embedded array in the revenue statement document to a subcollection requires a data migration. If the migration script reads old docs and writes to the new subcollection but the app is simultaneously serving requests, you get: (a) new uploads writing to the old format that the migration already "completed," (b) reads failing because code expects subcollection but data is still in the old format, or (c) partial migrations where some documents are migrated and others aren't.

**Why it happens:** Firestore has no schema migrations, no transactions across collections, and no way to atomically move data from a field to a subcollection. The app must handle both old and new formats during the transition.

**Consequences:** Revenue data appears missing or incomplete. Users re-upload PDFs, creating duplicates. Worst case: data loss if old documents are modified/deleted before migration completes.

**Prevention:**
1. Write the new code to READ from both formats (check for subcollection first, fall back to embedded `rows` field). Deploy this read-path change first.
2. Write a one-time migration script that copies `rows` to subcollections WITHOUT deleting the embedded array.
3. After migration is verified complete, deploy code that WRITES to subcollections.
4. Only after confirming all documents are migrated AND no code reads the old format, remove the embedded `rows` field in a cleanup pass.
5. Never delete old data until the new format is proven in production for at least a week.

**Detection:** Monitor Firestore reads/writes during migration. If revenue statement reads return 0 rows but the document exists, the migration has a gap.

**Phase:** This should be its own discrete phase, NOT bundled with auth changes. Too many moving parts at once.

---

### Pitfall 5: Requiring ENCRYPTION_KEY at Startup Breaks Existing Deployments

**What goes wrong:** The plan says "Require ENCRYPTION_KEY at startup -- fail fast if missing." But the current production deployment may not have this env var set (the encryption module currently falls back to plaintext). Adding a hard startup requirement means the next deploy crashes immediately if the Cloud Run service doesn't have the secret configured.

**Why it happens:** Environment variable requirements are invisible until they cause a failure. Cloud Run deploys are triggered by `git push`, so a missing env var won't be caught until the container tries to start.

**Consequences:** Production outage. The new container fails to start, Cloud Run keeps the old revision running (if available), but if the old revision is already replaced or the service scales to 0 and back, the app is down.

**Prevention:**
1. Add `ENCRYPTION_KEY` to the Cloud Run service configuration BEFORE deploying the code that requires it. Use `gcloud run services update table-rock-tools --update-secrets=ENCRYPTION_KEY=encryption-key:latest` or `--update-env-vars`.
2. Generate the Fernet key and store it in GCP Secret Manager first.
3. In the startup check, log a CRITICAL warning instead of crashing on the first deploy. Add a hard requirement only after confirming the key is present in production.
4. Handle the migration of existing plaintext values: on first startup with the key, re-encrypt all plaintext values in Firestore.

**Detection:** Before deploying, run `gcloud run services describe table-rock-tools --format='value(spec.template.spec.containers[0].env)'` to verify the env var exists.

**Phase:** Environment setup must happen BEFORE the code deploy. Add this as a pre-deployment checklist item.

---

### Pitfall 6: Allowlist Dual-Storage Race Condition During Auth Hardening

**What goes wrong:** The allowlist lives in both `data/allowed_users.json` (local file) and Firestore. `save_allowlist()` writes to the local file synchronously, then fires-and-forgets a Firestore write (`loop.create_task` at line 71 of `auth.py`). If the Firestore write fails silently (which it will, since failures are caught and logged as warnings at line 83), the local file and Firestore diverge. On the next container restart, `init_allowlist_from_firestore()` overwrites the local file with stale Firestore data, reverting any changes made since the last successful Firestore sync.

**Why it happens:** Cloud Run containers are ephemeral. The local JSON file is lost on every deploy or scale-to-zero. Firestore is the actual source of truth, but writes to it are fire-and-forget with silent failure handling.

**Consequences:** Admin adds a user, user can access the app, then on next deploy the user is removed because the Firestore write failed and the local file was rebuilt from stale Firestore data. In a security hardening context, this means users you REMOVED might reappear.

**Prevention:**
1. Make Firestore writes synchronous (await them) in the allowlist save path. If Firestore write fails, surface the error to the admin.
2. Eliminate the local JSON file as a cache. Read directly from Firestore. Use in-memory caching with a TTL instead.
3. At minimum, change the fire-and-forget `create_task` to an awaited call in the admin API endpoints (which are already async).

**Detection:** After adding/removing a user, check Firestore directly (`gcloud firestore documents get`) to confirm the write landed.

**Phase:** Fix before or during auth hardening. A diverged allowlist undermines the entire auth model.

---

## Moderate Pitfalls

---

### Pitfall 7: Testing External Dependencies Without Mocks Causes Flaky Tests

**What goes wrong:** Writing tests for auth-protected routes that actually hit Firebase Admin SDK, Firestore, and GCS creates tests that fail when credentials aren't available (CI environment), when Firestore has unexpected data, or when Firebase token verification times out.

**Prevention:**
1. Mock `verify_firebase_token` to return a known decoded token dict. Mock `is_user_allowed` to return `True`/`False`.
2. Use `app.dependency_overrides` in FastAPI tests to replace `require_auth` and `require_admin` with test fixtures that return predictable user dicts.
3. For Firestore, mock at the service level (`firestore_service.py` functions), not at the Firestore client level.
4. For RRC scraping tests, save HTML fixtures in `test-data/` and mock the HTTP requests.
5. Create a `conftest.py` with reusable fixtures: `authenticated_client`, `admin_client`, `unauthenticated_client`.

**Detection:** If tests pass locally but fail in CI, or pass on first run but fail on second, external dependencies are leaking.

**Phase:** Set up test infrastructure (mocks, fixtures, conftest.py) as the FIRST testing task, before writing any individual tests.

---

### Pitfall 8: Replacing x-user-email Headers Breaks Job Attribution

**What goes wrong:** The current system uses spoofable `x-user-email` and `x-user-name` headers for job attribution (stored in Firestore `jobs` collection as `user_id` and `user_name`). Switching to token-based identity changes the user identifier format -- Firebase tokens provide a `uid` (like `abc123def`) instead of an email. Existing jobs in Firestore have email-based `user_id` values. After the switch, job history queries (`get_user_jobs` filtering by `user_id`) stop matching old jobs.

**Prevention:**
1. Store BOTH `user_id` (Firebase UID) and `user_email` on new jobs.
2. Query job history by email (which is in the decoded token) rather than UID, for backwards compatibility.
3. Do NOT backfill old jobs -- just ensure the query works for both old (email-based) and new (UID-based) records.

**Detection:** After deploying, check if the Dashboard's "recent jobs" shows historical jobs for existing users.

**Phase:** Address during the auth enforcement phase, when adding `Depends(require_auth)` to tool routes.

---

### Pitfall 9: Composite Firestore Indexes Not Deployed Before Code That Needs Them

**What goes wrong:** The codebase already has fallback code for missing composite indexes (lines 225-232 in `firestore_service.py` -- catches exceptions and falls back to client-side sorting). If new queries are added during restructuring that require composite indexes, and those indexes aren't created before the code deploys, queries will either fail or silently fall back to unordered/incomplete results.

**Prevention:**
1. Define all required indexes in a `firestore.indexes.json` file.
2. Deploy indexes with `gcloud firestore indexes composite create` BEFORE deploying the code that uses them.
3. Firestore indexes can take 5-20 minutes to build. Verify they're ACTIVE before deploying.
4. Keep the client-side sort fallback but log it at WARNING level so you know when it's being used.

**Detection:** Search backend logs for "composite index missing" or "falling back to client-side sort" after deploying.

**Phase:** Index deployment must be a pre-step before any Firestore restructuring code deploys.

---

### Pitfall 10: Admin Settings Stored in Plaintext While Encryption Migration Is In-Flight

**What goes wrong:** The plan includes both "encrypt admin/app settings before Firestore persistence" and "require ENCRYPTION_KEY at startup." If these are deployed in the wrong order, you get a window where: (a) the app reads encrypted values but doesn't have the key (returns garbled data), or (b) the app writes encrypted values, then on restart falls back to plaintext reads because the key env var wasn't persisted correctly.

**Prevention:**
1. Deploy in this exact order: (a) add ENCRYPTION_KEY to Cloud Run env, (b) deploy code that CAN encrypt but doesn't require it, (c) run a one-time migration to encrypt existing plaintext values, (d) deploy code that requires encryption.
2. The `decrypt_value` function already handles the `enc:` prefix gracefully (line 66 of `encryption.py`). Leverage this: encrypted values have the prefix, plaintext values don't. The code can handle both.
3. Never deploy encryption-required code before the key is confirmed present AND existing data is migrated.

**Detection:** After enabling encryption, read back a known value from Firestore and verify it decrypts correctly.

**Phase:** Encryption changes should be a standalone step, deployed after ENCRYPTION_KEY is in the environment but before auth hardening.

---

## Minor Pitfalls

---

### Pitfall 11: `auto_error=False` on HTTPBearer Silently Passes Unauthenticated Requests

**What goes wrong:** In `auth.py` line 31: `security = HTTPBearer(auto_error=False)`. This means if no `Authorization` header is present, FastAPI does NOT return 401 automatically -- it passes `None` to `get_current_user`. The current `get_current_user` returns `None` for unauthenticated users (line 318). Only `require_auth` raises 401. If a developer adds `Depends(get_current_user)` instead of `Depends(require_auth)` to a new route, it silently allows unauthenticated access.

**Prevention:** When adding auth to routes, always use `Depends(require_auth)`, never `Depends(get_current_user)` for protected routes. Add a code review checklist item for this. Consider renaming `get_current_user` to `get_optional_user` to make the distinction obvious.

**Detection:** Grep for `Depends(get_current_user)` in route files. Any occurrence that isn't explicitly optional auth is a bug.

**Phase:** Verify during the auth enforcement phase.

---

### Pitfall 12: SSE Progress Streams May Not Send Auth Tokens

**What goes wrong:** The GoHighLevel bulk send uses Server-Sent Events (`/api/ghl/send/{job_id}/progress`) for real-time progress. SSE connections via `EventSource` in the browser do NOT support custom headers (no `Authorization` header). If this endpoint gets `Depends(require_auth)`, SSE connections will fail with 401.

**Prevention:**
1. For SSE endpoints, use a query parameter token approach: `/api/ghl/send/{job_id}/progress?token=<firebase-id-token>`.
2. Create a `require_auth_or_token_param` dependency that checks both the header and a query param.
3. Alternatively, use `fetch()` with `ReadableStream` instead of `EventSource` on the frontend (supports headers but more complex).

**Detection:** After adding auth to GHL routes, test the bulk send feature end-to-end and verify the progress bar updates.

**Phase:** Address when adding auth to GHL routes specifically.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Auth enforcement on all routes | Pitfall 1 (admin lockout) + Pitfall 2 (frontend fail-open) | Fix frontend auth context FIRST, then restructure the auth check flow, then add `Depends(require_auth)` to routes |
| CORS lockdown | Pitfall 3 (origin mismatch) | Add env var for origins, test from production domain, keep dev origins |
| ENCRYPTION_KEY requirement | Pitfall 5 (startup crash) + Pitfall 10 (migration ordering) | Set env var in Cloud Run BEFORE deploying code. Deploy encryption as standalone step |
| Firestore revenue restructuring | Pitfall 4 (data loss during migration) | Read-both-formats code first, then migration script, then write-new-format code |
| Allowlist hardening | Pitfall 6 (dual-storage divergence) | Make Firestore writes synchronous, eliminate local file dependency |
| Header replacement (x-user-email) | Pitfall 8 (job history breaks) | Store both UID and email, query by email for backwards compat |
| Test suite creation | Pitfall 7 (flaky external deps) | Build mock infrastructure first, use `dependency_overrides` |
| Firestore indexes | Pitfall 9 (indexes not ready) | Deploy indexes 20+ minutes before code that needs them |
| SSE endpoints | Pitfall 12 (EventSource can't send headers) | Use query param token for SSE auth |

## Recommended Phase Ordering (Risk-Based)

Based on these pitfalls, the safest order is:

1. **Pre-deploy infrastructure** (Pitfalls 5, 9): Set ENCRYPTION_KEY in Cloud Run, deploy Firestore indexes
2. **Frontend auth fix** (Pitfall 2): Change `return true` to `return false` in catch block
3. **Auth flow restructuring** (Pitfalls 1, 6, 11): Move allowlist check into `require_auth`, fix dual-storage, rename `get_current_user`
4. **Backend auth enforcement** (Pitfalls 8, 12): Add `Depends(require_auth)` to all routes, handle SSE + header migration
5. **CORS lockdown** (Pitfall 3): Environment-based origin allowlist
6. **Encryption hardening** (Pitfall 10): Encrypt existing plaintext values, then require key
7. **Firestore restructuring** (Pitfalls 4, 9): Revenue subcollection migration with dual-read support
8. **Test suite** (Pitfall 7): Mock infrastructure first, then auth smoke tests, then parsing regression tests

---

## Sources

- Direct codebase analysis of `backend/app/core/auth.py`, `backend/app/main.py`, `frontend/src/contexts/AuthContext.tsx`, `backend/app/services/shared/encryption.py`, `backend/app/services/firestore_service.py` (HIGH confidence)
- CORS specification behavior with credentials: established web standard (HIGH confidence)
- Firestore migration patterns and batch limits: established GCP patterns (HIGH confidence)
- FastAPI `dependency_overrides` for testing: established FastAPI pattern (HIGH confidence)
- EventSource header limitation: browser API specification (HIGH confidence)

---

*Pitfalls audit: 2026-03-11*

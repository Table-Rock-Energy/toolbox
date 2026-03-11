# Feature Landscape

**Domain:** Security hardening, testing, and data optimization for an internal FastAPI + React toolbox
**Researched:** 2026-03-11

## Table Stakes

Features that are non-negotiable for an internal tool exposed to the public internet via Cloud Run with `--allow-unauthenticated`. Missing any of these is an active security incident, not just a gap.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Auth on all tool endpoints | App is publicly accessible on the internet; unauthenticated endpoints = data exposure | Low | `require_auth` dependency exists, just not applied to Extract, Title, Proration, Revenue, GHL Prep, History, ETL routes. Mechanical find-and-add. |
| Admin-only on admin endpoints | User management, settings, API key config must not be accessible to regular users | Low | `require_admin` already used on some admin routes (add/update/remove user, Gemini settings). Need to audit for gaps (e.g., `GET /admin/users`, app settings reads, profile uploads). |
| Replace spoofable identity headers | `x-user-email` / `x-user-name` headers can be forged by any HTTP client; user identity must come from verified Firebase token | Medium | Requires changing how routes get user identity -- use `user["email"]` from the decoded token instead of reading request headers. Frontend already sends Bearer tokens. |
| CORS origin allowlist | `allow_origins=["*"]` with `allow_credentials=True` is spec-invalid per CORS specification (verified via FastAPI docs); browsers must reject credential-bearing requests with wildcard origin | Low | Set explicit origins: `https://tools.tablerocktx.com` for production, `http://localhost:5173` for development. Read from config/env var. |
| Require ENCRYPTION_KEY at startup | Current code silently falls back to plaintext storage when key is missing; GHL API keys end up unencrypted in Firestore | Low | Add startup validation in `main.py`. Fail fast with clear error message. Only enforce in production (allow dev without it). |
| Encrypt admin/app settings in Firestore | Settings containing API keys (Gemini, Google Maps, PDL, SearchBug) stored as plaintext in Firestore `app_config` collection | Medium | Apply `encrypt_value`/`decrypt_value` from existing `shared/encryption.py` to sensitive fields before Firestore writes. Need to identify which fields are sensitive. |
| Profile image upload ownership check | Any authenticated user can upload a profile image for any other user by passing a different `user_id` | Low | Verify `user_id` in upload matches authenticated user's UID, unless caller is admin. |
| Frontend fail-closed auth | `AuthContext.tsx` returns `true` when backend is unreachable, bypassing all server-side auth | Low | Change catch block to `return false`. Use `import.meta.env.DEV` for dev convenience. |
| Backend test suite: auth smoke tests | Zero tests exist. No way to verify auth actually blocks unauthenticated requests after changes. | Medium | Need pytest + httpx fixtures with mocked Firebase auth. Test that protected routes return 401 without token and 200 with valid token. |

## Differentiators

Features that improve robustness and operational quality but are not immediate security risks.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Firestore revenue subcollection restructure | Revenue statements embed all rows in a single document. Large statements risk hitting Firestore's 1MB document limit, causing silent data loss. | Medium | Move `rows` array to a subcollection (`revenue_statements/{id}/rows`). Requires dual-read migration pattern for existing data. |
| ETL entity detail batch retrieval | Entity detail page makes N+1 Firestore fetches (one per relationship). Slow for entities with many relationships. | Low | Replace loop of `get()` calls with `get_all()` batch retrieval. Straightforward optimization. |
| Firestore composite indexes | Client-side sorting fallback masks missing server-side indexes. Queries fetch all documents then sort in Python, wasting bandwidth and memory. | Low | Define required composite indexes in `firestore.indexes.json`. Deploy with `gcloud firestore indexes`. Remove client-side sorting fallback code. |
| Parsing pipeline regression tests | Revenue and Extract parsers are the core value. No regression tests means parser changes can silently break output accuracy. | High | Need representative test fixtures (sanitized PDFs or extracted text snapshots), expected output assertions. Most valuable tests in the whole codebase but require curating test data. |
| Audit logging for admin actions | Admin can add/remove users, change API keys, modify settings with no record of who did what or when. | Low | `AUDIT_LOGS_COLLECTION` already defined in Firestore service but unused. Write audit entries on admin mutations. |

## Anti-Features

Features to explicitly NOT build for this milestone.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Per-user data isolation / multi-tenancy | Team is ~5 people. PROJECT.md explicitly states "small team, transparency preferred over isolation." Adding row-level security adds complexity with no user benefit. | Keep shared visibility. Auth ensures only team members see data. |
| Rate limiting | Important eventually but a separate concern. Small internal team is not going to DDoS themselves. RRC fetch-missing already has its own built-in caps. | Defer to next milestone as stated in PROJECT.md out-of-scope. |
| Frontend test suite | Backend is where security and parsing accuracy live. Frontend tests have lower ROI until the backend is solid. | Defer per PROJECT.md. Focus backend test budget on auth and parsers. |
| OAuth scopes / granular permissions | Role/scope/tools fields exist in allowlist but are not enforced anywhere. Building a full RBAC system is over-engineering for 5 users. | Enforce admin vs. non-admin only. The role field exists if needed later. |
| Global auth middleware via BaseHTTPMiddleware | Runs on every request including static files, health checks. Cannot return values to endpoint functions. Breaks FastAPI's dependency injection model. | Use per-endpoint `Depends()` instead (FastAPI recommended pattern). |
| Structured logging / request tracing | Valuable for debugging but not a security fix. | Defer to next milestone per PROJECT.md. |
| JWT-based session tokens (replacing Firebase) | Firebase Auth works and is already integrated. Replacing it adds zero security benefit for massive effort. | Keep Firebase Auth. Just enforce verification. |
| API key rotation system | Fernet key is static. Rotation is good practice but premature for this team size. | Document the rotation procedure. Do not build automated rotation. |

## Feature Dependencies

```
CORS lockdown (independent, no deps)
  |
Auth on all endpoints --> Replace spoofable headers (headers depend on auth being required first)
  |                    --> Profile upload ownership (depends on auth being enforced)
  |
Require ENCRYPTION_KEY --> Encrypt admin settings (encryption must work before encrypting data)

Frontend fail-closed --> Must deploy WITH backend auth changes (not before, not after)

Auth smoke tests --> depend on auth enforcement being implemented (test what you build)

Revenue subcollection restructure (independent)
ETL batch retrieval (independent)
Firestore composite indexes (independent)
Parsing regression tests (independent, but best done after auth tests establish test infrastructure)
```

## MVP Recommendation

**Phase 1 -- Security fundamentals (do first, all table stakes):**
1. CORS origin allowlist (5 min fix, highest risk-to-effort ratio)
2. Frontend fail-closed auth (must ship with backend auth changes)
3. Auth on all tool endpoints (mechanical, low risk)
4. Admin-only audit of admin endpoints (verify coverage)
5. Replace spoofable identity headers with token-based identity
6. Require ENCRYPTION_KEY at startup (fail fast)
7. Encrypt sensitive admin settings in Firestore
8. Profile image upload ownership check

**Phase 2 -- Verification (prove Phase 1 works):**
1. Backend test infrastructure (pytest + httpx + auth mocking fixtures)
2. Auth smoke tests for every protected route
3. Basic parsing regression tests (at least one per parser)

**Phase 3 -- Data optimization (after security is locked down):**
1. Revenue subcollection restructure + dual-read migration
2. ETL batch retrieval fix
3. Firestore composite indexes

**Defer:** Audit logging, rate limiting, structured logging, frontend tests. All valuable but not this milestone.

## Sources

- Codebase analysis: `backend/app/core/auth.py`, `backend/app/main.py`, `backend/app/api/*.py`, `backend/app/services/shared/encryption.py`
- FastAPI CORS docs (verified via WebFetch): wildcard + credentials is spec-invalid
- FastAPI dependency injection docs (verified via WebFetch): router-level dependencies are recommended for auth
- PROJECT.md: explicit scope decisions on what to include/defer

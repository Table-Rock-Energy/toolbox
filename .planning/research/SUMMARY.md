# Research Summary: v2.0 On-Prem Migration

**Project:** Table Rock Tools
**Synthesized:** 2026-03-25
**Milestone:** v2.0 Full On-Prem Migration
**Research Confidence:** HIGH — all 4 research areas based on direct codebase analysis + authoritative documentation

---

## Executive Summary

Table Rock Tools v2.0 is a cloud-to-on-prem infrastructure migration, not a feature build. The app itself (Extract, Title, Proration, Revenue, GHL Prep) remains unchanged. The goal is to replace four Google Cloud dependencies — Firebase Auth, Firestore, GCS, and Gemini — with self-hosted equivalents: local JWT auth, PostgreSQL, local filesystem storage, and LM Studio for AI. The migration is unusually low-risk for its scope because most of the target infrastructure already exists in the codebase: SQLAlchemy models cover 10 of 13 tables, the async database engine is already configured, local filesystem storage already has a working fallback, and the OpenAI SDK is the natural client for LM Studio's OpenAI-compatible API.

The recommended sequencing is database first, auth second, AI and storage last. Auth depends on the users table with a `password_hash` column, which means PostgreSQL must be promoted to primary before JWT endpoints can be built. Every API endpoint depends on auth, so auth must be complete before testing anything end-to-end. AI and storage are independent and can be addressed last. The migration should execute as a hard cutover — dual database operation (Firestore + PostgreSQL simultaneously) is explicitly an anti-pattern here, adding complexity without benefit for a small internal team.

The most significant risks are not in the new code but in the migration data: Firestore's nested documents (revenue rows inside statement documents) must be explicitly decomposed into relational rows, 5+ SQLAlchemy models are missing and must be created before schema generation, and the RRC background worker requires a separate synchronous session factory because it runs outside the asyncio event loop. Addressing these in order during the database phase prevents all downstream failures.

---

## Key Findings

### From STACK.md — Technology Decisions

- **PyJWT** (>=2.12.0) replaces python-jose — python-jose is abandoned (last release 2021), FastAPI officially dropped it in PR #11589
- **pwdlib[bcrypt]** (>=0.2.0) replaces passlib — passlib is broken with bcrypt>=5.0 and Python>=3.13+, pwdlib is from the FastAPI-Users author
- **openai SDK** (>=1.60.0) is the right client for LM Studio — LM Studio exposes a 100% OpenAI-compatible `/v1/chat/completions` endpoint; set `base_url="http://localhost:1234/v1"` and `api_key="not-needed"`, zero new prompt logic needed
- **Alembic** (already in requirements.txt) becomes mandatory — the existing `create_all()` approach cannot handle schema evolution once PostgreSQL is the sole database
- **No new frontend dependencies** — JWT auth is fetch + localStorage, Firebase SDK removal saves ~600KB from the bundle
- **SQLAlchemy + asyncpg already exist in requirements.txt** — the migration activates existing code, not greenfield work

### From FEATURES.md — Feature Scope

**Table Stakes (must have for working app):**

- Local email/password login with `/api/auth/login` and `/api/auth/refresh` endpoints
- JWT Bearer token verification middleware replacing Firebase verification — zero changes to route handlers due to existing `Depends()` pattern
- PostgreSQL as sole database with all 13 Firestore collections ported (10 models exist, 3 need creation)
- Alembic initial migration generated from completed `db_models.py`
- CLI seed script for initial admin user (`create_admin.py`)
- Silent local filesystem storage (no GCS warning logs when `GCS_BUCKET_NAME` is unset)
- LM Studio OpenAI-compatible provider implementing existing `LLMProvider` protocol

**Differentiators (valuable, low complexity):**

- Password change UI in AdminSettings (eliminates CLI dependency for password resets)
- Health endpoint reporting PostgreSQL + AI provider connectivity status
- Alembic auto-migration on startup (`alembic upgrade head` in FastAPI lifespan)

**Anti-features (explicitly excluded):**

- Google Sign-In / OAuth — removed entirely
- Self-registration — admin-created accounts only
- Refresh token rotation / token blacklist — 24-hour access tokens + DB deactivation is sufficient
- Alembic downgrade support — forward-only migrations
- Firebase-to-PostgreSQL live sync — one-time cutover script only

**Deferred to production cutover:**

- DB-04: Firestore-to-PostgreSQL data migration script (only needed once when moving prod data)

### From ARCHITECTURE.md — Structural Decisions

- **Hard cutover, not dual-DB** — no period of simultaneous Firestore + PostgreSQL operation
- **Dependency injection pattern preserved** — `get_current_user` → `require_auth` → `require_admin` chain stays identical, only internals of `get_current_user` change (JWT decode vs Firebase verify), zero route handler changes required
- **`firestore_service.py` → `db_service.py`** — identical function signatures; callers change only the import path
- **JWT token storage** — access token in localStorage (internal tool behind VPN, no CSRF risk, survives page refresh), 24-hour expiry, no refresh token complexity
- **3 missing SQLAlchemy models** needed before schema generation: `AppConfig` (key/JSONB), `UserPreference` (user_id FK/JSONB), `RRCCountyStatus`
- **4 new columns on `User` model**: `password_hash`, `role`, `scope`, `tools`
- **RRC background worker** needs a separate sync `Session` factory — strip `+asyncpg` from the DATABASE_URL, use `sessionmaker` not `async_sessionmaker`
- **OpenAI provider** implements existing `LLMProvider` protocol — factory in `llm/__init__.py` routes based on `AI_PROVIDER` env var

### From PITFALLS.md — Critical Risk Areas

**Critical (cause rewrites or data loss):**

1. **Nested Firestore docs flattened incorrectly** — Revenue rows are nested inside statement documents; must explicitly decompose with FK resolution (create parent row first to get PK, then insert child rows); add count-verification after migration
2. **Async session lifecycle leaks** — Use `Depends(get_db)` generator pattern with explicit commit/rollback; set pool settings (`pool_size=5, max_overflow=10, pool_pre_ping=True`); separate sync session factory for the RRC background worker
3. **JWT token shape vs Firebase User shape** — Frontend components reference `displayName`, `photoURL`, `getIdToken()` which don't exist on a plain JWT payload; define `LocalUser` interface; run `npx tsc --noEmit` after auth migration to catch all references
4. **RRC background worker event loop isolation** — Cannot use async sessions in a daemon thread; must use sync `Session` with `postgresql://` URL (strip `+asyncpg`)
5. **LM Studio JSON response parsing** — No schema-enforced JSON output; implement multi-layer fallback: direct parse → strip markdown fences → regex extract first `{...}` block → graceful empty return
6. **Allowlist + config data silently lost** — 5+ Firestore collections lack SQLAlchemy models (`rrc_county_status`, `app_config`, `user_preferences`, `ghl_connections`, `entities`); GHL encrypted tokens must be migrated as-is (ENCRYPTION_KEY stays constant)

**Moderate:**

- JWT secret must be a persisted env var (not auto-generated at startup) or all tokens invalidate on container restart
- Bcrypt 12 rounds in production, 4 in test fixtures
- Firestore timestamps are sometimes timezone-naive — normalize all to `datetime.now(timezone.utc)` before PostgreSQL insert; replace all `datetime.utcnow()` calls (deprecated in Python 3.12+)
- Docker named volume required for `/app/data` — files are lost on container restart without it
- LM Studio timeout must be set to 120s+ (local models can take 60-90s for large batch prompts)
- Test suite mocks `firestore_service` imports — update tests per-phase as services are ported

**Integration risks:**

- Firebase UIDs (strings like `"abc123def456"`) vs new user identifiers — use email as the stable `user_id` in FK columns to avoid orphaned job records
- JWT expiry mid-pipeline — 24-hour tokens mitigate this; add `/api/auth/refresh` endpoint and wire up frontend 401 handler
- Existing job records may contain `gs://` storage paths — audit `save_upload()` call sites before writing migration script

---

## Implications for Roadmap

### Suggested Phase Structure

**Phase 1 — Database Foundation**

Rationale: Auth depends on the users table with `password_hash`; everything depends on auth. PostgreSQL must be primary before any other work begins. Session patterns must be established before any service is ported.

- Complete 5+ missing SQLAlchemy models (`AppConfig`, `UserPreference`, `RRCCountyStatus`, `GhlConnection`, `Entity`)
- Add `password_hash`, `role`, `scope`, `tools` columns to `User` model
- Initialize Alembic with async template, generate initial migration from complete `db_models.py`
- Flip config defaults: `DATABASE_ENABLED=true`, `FIRESTORE_ENABLED=false`
- Port all `firestore_service.py` functions to `db_service.py` with identical function signatures
- Establish `Depends(get_db)` session generator pattern with explicit pool settings
- Create separate sync session factory for `rrc_background.py`
- Deliverable: App runs entirely on PostgreSQL; all tools functional; Firestore disabled
- Pitfalls: #1 (nested docs), #2 (session leaks), #4 (background worker), #6 (missing models)

**Phase 2 — Auth Swap**

Rationale: Every API endpoint depends on auth. Must be complete and tested before end-to-end validation of any tool.

- Backend: `/api/auth/login` with bcrypt verify + JWT encode, `/api/auth/refresh`, `/api/auth/me`
- Replace `verify_firebase_token()` with `jwt.decode()` in `auth.py` — keep `Depends()` chain identical
- CLI seed script `create_admin.py` for initial admin user
- Frontend: rewrite `AuthContext.tsx` with `LocalUser` interface; JWT stored in localStorage
- Update `Login.tsx` to call `/api/auth/login` instead of Firebase `signInWithEmailAndPassword`
- Remove Firebase SDK (`npm uninstall firebase`), delete `firebase.ts`
- Wire `api.ts` 401 handler to `/api/auth/refresh` instead of `auth.currentUser.getIdToken(true)`
- Deliverable: Firebase credentials no longer required to run the app
- Pitfalls: #3 (token shape mismatch), #7 (JWT secret persistence), #8 (bcrypt rounds), #14 (dead Firebase bundle), Integration #1 (user ID format)

**Phase 3 — AI Provider + Storage Cleanup**

Rationale: Both are independent of database and auth; app already degrades gracefully without AI; local storage fallback already works. Combine into one phase.

- Implement `OpenAICompatibleProvider` in `services/llm/openai_provider.py` with multi-layer JSON fallback parser
- Wire into factory in `llm/__init__.py` with `AI_PROVIDER` env var routing (`gemini` | `lm_studio` | `none`)
- Add `AI_PROVIDER`, `LLM_API_BASE`, `LLM_MODEL`, `LLM_API_KEY` to `config.py`
- Change `gcs_bucket_name` and `gcs_project_id` defaults to `None`; suppress GCS log warnings when unconfigured
- Verify Docker named volume for `/app/data` in `docker-compose.yml`
- Deliverable: App runs fully on-prem with no Google Cloud dependencies
- Pitfalls: #5 (JSON parsing), #10 (Docker volume), #11 (LM Studio timeout), #15 (token counting)

**Phase 4 — Data Migration (Cutover Only)**

Rationale: One-time script run only when moving production data. Deferred until production cutover is scheduled.

- Write `scripts/migrate_firestore_to_postgres.py` with per-collection handlers
- Handle revenue statement nested rows explicitly (create parent FK first, then child rows)
- Normalize all Firestore timestamps to UTC-aware before insert
- Audit and rewrite `gs://` storage paths if found in job records
- Verify migrated counts vs Firestore document counts per collection
- Migrate `ghl_connections` with encrypted tokens as-is (`ENCRYPTION_KEY` stays constant)
- Deliverable: Production data preserved in PostgreSQL; Firestore can be decommissioned
- Pitfalls: #1 (nested docs), #6 (config/allowlist data), #9 (timestamps), Integration #3 (storage paths)

### Research Flags

- **Phase 1** — Well-documented SQLAlchemy patterns; no additional research phase needed. Follow the existing `db_models.py` and `database.py` patterns.
- **Phase 2** — FastAPI JWT tutorial is the definitive reference; no additional research phase needed.
- **Phase 3** — LM Studio JSON compliance varies by model. Consider a short spike with the specific model being deployed before writing the provider. Flag for `/gsd:research-phase` if the local model is undecided.
- **Phase 4** — Firestore collection structure must be inspected against actual production data before writing the migration script. Run against staging first.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | PyJWT, pwdlib, openai SDK choices based on official FastAPI docs and active maintenance status; no ambiguity |
| Features | HIGH | All features are direct ports of existing functionality; scope bounded by explicit anti-features list |
| Architecture | HIGH | Most target patterns already exist in the codebase; `Depends()` chain preservation eliminates route handler changes |
| Pitfalls | HIGH | Based on direct codebase analysis with specific line and file references; not hypothetical |

**Gaps requiring attention before execution:**

- The actual count of Firestore collections may exceed 13. ETL `entity_registry.py` and `relationship_tracker.py` may write additional collections not surfaced in `firestore_service.py`. Audit before writing the migration script.
- LM Studio model JSON compliance is model-dependent. The multi-layer fallback parser handles this defensively, but the specific local model should be tested before enabling AI features in production.
- CORS allowed origins for the on-prem deployment URL are not yet defined. Must be set in the Docker env file before deployment.

---

## Recommended MVP Sequence (Ordered)

1. Complete SQLAlchemy models (missing 5+ tables, 4 User columns)
2. Alembic init + initial migration
3. Port `firestore_service.py` → `db_service.py` (same function signatures)
4. Establish session patterns (`Depends(get_db)` generator + sync factory for background worker)
5. JWT login/refresh/me endpoints + bcrypt password hashing
6. Replace Firebase verification middleware with JWT decode (keep Depends chain)
7. CLI admin seed script
8. Frontend `AuthContext.tsx` rewrite + `Login.tsx` update
9. Remove Firebase SDK (`npm uninstall firebase`)
10. OpenAI-compatible LM Studio provider with JSON fallback parser
11. Config default changes (`gcs_bucket_name=None`, `FIRESTORE_ENABLED=false`)
12. Docker named volume verification
13. (Cutover only) Firestore-to-PostgreSQL migration script

---

## Sources

Aggregated from all 4 research files:

- [FastAPI JWT Tutorial (official)](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)
- [FastAPI PR #11589: Replace python-jose with PyJWT](https://github.com/fastapi/fastapi/pull/11589)
- [FastAPI Discussion #11345: Abandon python-jose](https://github.com/fastapi/fastapi/discussions/11345)
- [FastAPI Discussion #11773: passlib unmaintained](https://github.com/fastapi/fastapi/discussions/11773)
- [LM Studio OpenAI Compatibility Docs](https://lmstudio.ai/docs/developer/openai-compat)
- [LM Studio API Server Docs](https://lmstudio.ai/docs/developer/core/server)
- [Alembic Async Cookbook](https://alembic.sqlalchemy.org/en/latest/cookbook.html)
- [PyJWT PyPI](https://pypi.org/project/PyJWT/) — v2.12.1
- [OpenAI Python SDK PyPI](https://pypi.org/project/openai/) — v2.29.0
- [pwdlib PyPI](https://pypi.org/project/pwdlib/)
- Codebase: `backend/app/core/auth.py`, `backend/app/core/database.py`
- Codebase: `backend/app/models/db_models.py` — 10 of 13 tables confirmed
- Codebase: `backend/app/services/firestore_service.py` — 13 collections, ~40 functions
- Codebase: `backend/app/services/storage_service.py` — local fallback pattern
- Codebase: `backend/app/services/rrc_background.py` — threading + asyncio.run() pattern
- Codebase: `backend/app/services/gemini_service.py` — current AI integration structure
- Codebase: `frontend/src/contexts/AuthContext.tsx` — Firebase User type dependencies
- Codebase: `frontend/src/utils/api.ts` — setAuthToken/clearAuthToken/setUnauthorizedHandler
- Codebase: `backend/app/services/llm/` — LLMProvider protocol + factory

# Feature Landscape

**Domain:** On-prem migration of existing cloud-hosted FastAPI + React app (Firebase Auth -> local JWT, Firestore -> PostgreSQL, Gemini -> LM Studio, GCS -> local filesystem)
**Researched:** 2026-03-25
**Milestone:** v2.0 Full On-Prem Migration

## Table Stakes

Features users expect from the migration. Missing = broken app or degraded experience.

### AUTH: Local JWT Authentication

| Feature | Why Expected | Complexity | Existing Code Dependency |
|---------|--------------|------------|--------------------------|
| Email + password login form | Current app has email/password login via Firebase | Low | `Login.tsx`, `AuthContext.tsx` -- replace Firebase calls with `/api/auth/login` |
| JWT access token in Authorization header | Every API call already sends `Bearer <token>` | Low | `api.ts` `setAuthToken()` already handles this -- no change needed |
| Backend token verification middleware | Current `require_auth` / `require_admin` dependencies | Med | `auth.py` -- replace `verify_firebase_token()` with `jose.jwt.decode()` |
| Token expiry + automatic refresh | Firebase auto-refreshes tokens; users expect seamless sessions | Med | `AuthContext.tsx` has `setUnauthorizedHandler` that retries on 401 -- reuse pattern with `/api/auth/refresh` |
| Logout (clear token) | Current `signOut` clears Firebase state | Low | Frontend already calls `api.clearAuthToken()` -- just skip Firebase signOut |
| Admin-only user creation | Current allowlist model -- admin adds users, no self-registration | Low | `admin.py` already has user CRUD -- add password hashing |
| CLI script to seed initial admin user | No Firebase console available on-prem | Low | New `create_admin.py` script -- runs once at deploy |
| Allowlist check preserved | Current `is_user_allowed()` checks email against list | Low | Merge allowlist into PostgreSQL `users` table -- `is_active` column replaces allowlist |
| Role/scope/tools permissions preserved | AllowedUser model has role, scope, tools fields | Low | Already in `auth.py` -- move to `users` table columns |
| Cron secret bypass preserved | `CRON_SECRET` token for scheduled jobs | Low | Keep as-is in new JWT verification -- check cron secret before JWT decode |

**Login flow behavior (user-facing):**
1. User enters email + password on Login page
2. Frontend POSTs to `/api/auth/login` -- receives `{ access_token, refresh_token, user }`
3. Frontend stores access token in memory (AuthContext state), refresh token in localStorage
4. On 401, frontend calls `/api/auth/refresh` with refresh token to get new access token
5. On refresh failure, redirect to login with "session expired" message

**Token expiry expectations:**
- Access token: 30-60 minute expiry (short-lived, stored in memory only)
- Refresh token: 7-30 day expiry (long-lived, stored in localStorage)
- Silent refresh: user never sees expiry unless inactive for days
- The existing `setUnauthorizedHandler` in `api.ts` already implements retry-on-401 -- just swap Firebase `getIdToken(true)` for `/api/auth/refresh` call

**Session management:**
- Stateless JWT -- no server-side session storage needed
- Deactivating a user in DB blocks them on next token verification (allowlist check)
- No token blacklist needed -- short access token expiry handles logout lag
- Multiple tabs/windows share the same token via AuthContext (already works this way)

### DB: PostgreSQL as Only Database

| Feature | Why Expected | Complexity | Existing Code Dependency |
|---------|--------------|------------|--------------------------|
| All Firestore collections in PostgreSQL | App persists jobs, entries, RRC data, config, preferences | High | `firestore_service.py` has 13 collections, ~40 functions -- each needs PostgreSQL equivalent |
| Schema creation on first run | Firestore auto-creates collections; PostgreSQL needs DDL | Low | `database.py` already has `init_db()` using `Base.metadata.create_all` |
| Alembic migrations for schema versioning | Production DB needs safe schema changes over time | Med | `alembic>=1.13.0` in requirements.txt, no alembic.ini yet -- needs async template init |
| One-time Firestore-to-PostgreSQL data migration | Existing production data must transfer | Med | New script -- read all Firestore collections, insert into PostgreSQL tables |
| Batch insert performance | Firestore batches at 500 docs; PostgreSQL needs similar throughput | Low | SQLAlchemy `session.add_all()` + `commit()` handles bulk inserts natively |
| Job history with user scoping | Non-admin sees own jobs; admin sees all | Low | Already in `firestore_service.py` `get_user_jobs()` -- port query logic to SQLAlchemy |
| App config storage | Currently in `app_config` Firestore collection (GHL keys, settings) | Low | New `app_config` table: `key VARCHAR PRIMARY KEY, data JSONB, updated_at TIMESTAMP` |
| User preferences storage | Currently in `user_preferences` Firestore collection | Low | New `user_preferences` table: `user_id FK, data JSONB` |
| RRC data lookup performance | Currently pandas in-memory cache from CSV + Firestore | Med | Keep pandas in-memory cache -- load from PostgreSQL on startup instead of Firestore |

**Firestore collection to PostgreSQL table mapping:**

| Firestore Collection | PostgreSQL Table | SQLAlchemy Model Status |
|---------------------|------------------|------------------------|
| `users` | `users` | EXISTS -- needs `password_hash`, `role`, `scope`, `tools` columns |
| `jobs` | `jobs` | EXISTS -- ready |
| `extract_entries` | `extract_entries` | EXISTS -- ready |
| `title_entries` | `title_entries` | EXISTS -- ready |
| `proration_rows` | `proration_rows` | EXISTS -- ready |
| `revenue_statements` | `revenue_statements` + `revenue_rows` | EXISTS -- ready |
| `rrc_oil_proration` | `rrc_oil_proration` | EXISTS -- ready |
| `rrc_gas_proration` | `rrc_gas_proration` | EXISTS -- ready |
| `rrc_data_syncs` | `rrc_data_syncs` | EXISTS -- ready |
| `rrc_county_status` | `rrc_county_status` | MISSING -- new model needed |
| `audit_logs` | `audit_logs` | EXISTS -- ready |
| `app_config` | `app_config` | MISSING -- new model needed (key/JSONB) |
| `user_preferences` | `user_preferences` | MISSING -- new model needed (user_id FK/JSONB) |

10 of 13 tables already have SQLAlchemy models. 3 need new models. Users table needs 4 new columns.

**Migration approach:**
- Alembic async template with `env.py` reading `database.py` engine
- Initial migration auto-generates from `db_models.py`
- Add missing tables as new models before initial migration generation
- Forward-only migrations (no downgrade support)
- `alembic upgrade head` in app startup hook for automatic migration application

### AI: LM Studio Provider via OpenAI-Compatible API

| Feature | Why Expected | Complexity | Existing Code Dependency |
|---------|--------------|------------|--------------------------|
| OpenAI-compatible chat completions | LM Studio serves at `http://localhost:1234/v1/chat/completions` | Med | New `openai_provider.py` implementing existing `LLMProvider` protocol |
| No API key required | LM Studio needs no authentication | Low | Pass `api_key="lm-studio"` (dummy value) to OpenAI client |
| Model selection via config | User picks which local model to use | Low | New env vars: `AI_PROVIDER`, `LLM_API_BASE`, `LLM_MODEL` |
| Provider routing in factory | `get_llm_provider()` returns correct provider based on config | Low | `llm/__init__.py` factory already exists -- add OpenAI branch |
| JSON response parsing without structured output | LM Studio models may not support `response_mime_type` | Med | Parse JSON from text response (regex `{...}` extraction) instead of Gemini's native JSON mode |
| Timeout handling for local inference | Local models can be 30s+ for large batches | Low | OpenAI client `timeout` parameter -- set 120s default |
| Rate limiting skipped for local | No API rate limits for self-hosted inference | Low | Skip `_check_rate_limit()` when provider is LM Studio |
| Existing Gemini preserved as dual option | Gemini still works if API key provided | Low | Keep `gemini_service.py` and `GeminiProvider` -- factory selects based on config |
| Batch processing compatibility | Pipeline sends 25-entry batches through `cleanup_entries()` | Low | `LLMProvider` protocol unchanged -- new provider implements same interface |

**LM Studio specifics:**
- Default endpoint: `http://localhost:1234/v1`
- Supports: `/v1/chat/completions`, `/v1/models`, `/v1/completions`, `/v1/embeddings`
- No API key needed -- pass any string (convention: `"lm-studio"`)
- JSON mode: Some models support `response_format: {"type": "json_object"}` but model-dependent. Safer to prompt for JSON and parse from text.
- Tool/function calling: Supported for fine-tuned models only. Do not depend on it.
- Model names: Listed via `GET /v1/models` -- user configures via `LLM_MODEL` env var

**Provider switching behavior:**
- `AI_PROVIDER=gemini` (default): Uses existing `GeminiProvider`, requires `GEMINI_API_KEY`
- `AI_PROVIDER=lm_studio` or `AI_PROVIDER=openai_compatible`: Uses new `OpenAICompatibleProvider`, requires `LLM_API_BASE`
- Factory in `llm/__init__.py` reads `settings.ai_provider` and returns correct provider
- Budget/rate-limit tracking only applies to Gemini (pay-per-token); LM Studio has no cost tracking

**Response parsing difference:**
- Gemini: `response_mime_type="application/json"` + `response_json_schema=SCHEMA` -- guaranteed JSON
- LM Studio: Prompt instructs "return JSON", response may include markdown fencing or preamble text -- need robust extraction (`json.loads()` on first `{...}` block found in response text)

### STOR: Local Filesystem Storage (No GCS Warnings)

| Feature | Why Expected | Complexity | Existing Code Dependency |
|---------|--------------|------------|--------------------------|
| Silent local-only operation | No "GCS not available" warnings in logs | Low | `storage_service.py` -- change `logger.info()` to `logger.debug()` when `gcs_bucket_name` is empty |
| Default to no GCS | `gcs_bucket_name` should default to `None` | Low | `config.py` line 32 -- change from `"table-rock-tools-storage"` to `None` |
| All storage paths work locally | RRC data, uploads, profiles all use local filesystem | Low | Already works -- `StorageService` falls back to local. Just need clean defaults. |
| No GCS Python package required | `google-cloud-storage` import fully optional | Low | Already handled -- `try/except ImportError` in `storage_service.py` |

**What "no GCS warnings" means in practice:**
- `GCS_BUCKET_NAME` unset/empty: `use_gcs` returns `False`
- `StorageService._init_client()` skips GCS init entirely -- no log messages at all
- All operations go straight to local filesystem via `data/` directory
- `get_signed_url()` returns `None` (already handled -- profile images use `/api/admin/profile-image/` proxy)
- RRC CSV data: `data/rrc-data/`
- User uploads: `data/uploads/`
- Profile images: `data/profiles/`

**Config default changes needed:**
- `gcs_bucket_name`: `"table-rock-tools-storage"` -> `None`
- `gcs_project_id`: `"tablerockenergy"` -> `None`
- `firestore_enabled`: `True` -> `False`
- `database_enabled`: `False` -> `True`

## Differentiators

Features that improve the on-prem experience beyond "it works." Not expected, but valuable.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Password change UI in Settings | Admin resets passwords without CLI | Low | New form in AdminSettings, calls `PUT /api/admin/users/{email}/password` |
| Health endpoint includes DB + AI status | Dashboard shows system health at a glance | Low | Extend `/api/health` to report PostgreSQL and AI provider connectivity |
| Docker Compose with PostgreSQL + app | One `docker-compose up` to run everything | Low | Existing `docker-compose.yml` already has PostgreSQL service |
| Alembic auto-migration on startup | App checks for pending migrations and applies | Med | `alembic upgrade head` in FastAPI lifespan -- prevents manual migration steps |
| AI provider status in admin settings | Shows active provider, model name, connectivity | Low | Extend existing admin settings page |
| Graceful AI unavailability | Enrichment pipeline works without AI (skip cleanup step) | Low | Already handled -- `get_llm_provider()` returns `None` when unavailable |

## Anti-Features

Features to explicitly NOT build during this migration.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Google Sign-In (OAuth) | No Google Cloud dependency on-prem | Email + password only. Remove `googleProvider` entirely. |
| Self-registration | Internal tool -- admin controls access | Admin creates accounts via admin settings page or CLI |
| Session storage in Redis | Adds infrastructure for small team | Stateless JWT tokens -- no session store needed |
| Token blacklist/revocation | Complex for small user base | Short access token expiry (30 min). Admin deactivates user in DB. |
| Alembic downgrade support | Rollbacks risky in production | PostgreSQL backup before migrations. Forward-only. |
| Multi-tenant database | Single team, single instance | One database, shared by all users |
| Local model fine-tuning | Out of scope for document processing | Use pre-trained models from LM Studio model library |
| Firebase-to-PostgreSQL live sync | One-time migration only | Run migration script once during cutover |
| GCS-to-local file sync | One-time copy only | `gsutil cp -r gs://bucket/path ./data/` once |
| Password complexity rules | Small internal team, admin-created accounts | Minimum 8 characters, no complexity regex |
| MFA/2FA | Overkill for internal tool behind VPN/LAN | Defer indefinitely |

## Feature Dependencies

```
AUTH-04 (seed admin) -> AUTH-01 (users table with password_hash)
AUTH-01 (users table) -> DB-02 (extend SQLAlchemy models)
AUTH-02 (login endpoint) -> AUTH-01 (users table)
AUTH-03 (JWT middleware) -> AUTH-02 (login returns JWT)
AUTH-05 (frontend auth context) -> AUTH-02 + AUTH-03 (backend endpoints exist)
AUTH-06 (remove Firebase) -> AUTH-05 (new auth context works)

DB-02 (extend models) -> DB-01 (PostgreSQL is primary)
DB-03 (schema creation) -> DB-02 (models complete)
DB-04 (data migration) -> DB-03 (schema exists in production)
DB-05 (port all services) -> DB-02 (models available)

AI-02 (provider routing) -> AI-01 (OpenAI provider exists)
AI-03 (env vars) -> AI-02 (factory reads config)

STOR-01 -> independent (config default change only)
```

## MVP Recommendation

**Phase 1 -- Database foundation:**
1. DB-02: Extend SQLAlchemy models (add 3 missing tables + auth columns to `users`)
2. DB-03: Alembic init + initial migration
3. DB-01: Flip defaults (`DATABASE_ENABLED=true`, `FIRESTORE_ENABLED=false`)
4. DB-05: Port `firestore_service.py` functions to `db_service.py` using SQLAlchemy

**Phase 2 -- Auth swap:**
1. AUTH-01 + AUTH-02: Login/refresh endpoints with bcrypt + python-jose
2. AUTH-03: Replace Firebase verification middleware with JWT decode
3. AUTH-04: CLI admin seed script
4. AUTH-05: Frontend AuthContext rewrite (remove Firebase SDK)
5. AUTH-06: Remove all Firebase imports and packages

**Phase 3 -- AI + Storage cleanup:**
1. AI-01: OpenAI-compatible provider implementing `LLMProvider` protocol
2. AI-02 + AI-03: Factory routing with new env vars
3. STOR-01: Default config changes + log level cleanup

**Defer to production cutover:** DB-04 (Firestore migration script) -- only needed once when moving prod data.

**Rationale:** Database first because auth needs the users table with `password_hash`. Auth second because every endpoint depends on it. AI + Storage last because they're independent and the app already degrades gracefully without them.

## Sources

- [FastAPI OAuth2 JWT Tutorial](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/) -- official docs for password hashing + JWT
- [LM Studio OpenAI Compatibility Endpoints](https://lmstudio.ai/docs/developer/openai-compat) -- `/v1/chat/completions`, no API key needed
- [LM Studio API Server](https://lmstudio.ai/docs/developer/core/server) -- default port 1234, model listing
- Codebase: `backend/app/core/auth.py` -- Firebase auth (13 Firestore-touching functions to replace)
- Codebase: `backend/app/services/llm/protocol.py` -- `LLMProvider` protocol (2 methods: `cleanup_entries`, `is_available`)
- Codebase: `backend/app/services/llm/__init__.py` -- provider factory (add OpenAI branch)
- Codebase: `backend/app/models/db_models.py` -- 10 of 13 SQLAlchemy models already exist
- Codebase: `backend/app/services/firestore_service.py` -- 13 collections, ~40 functions to port
- Codebase: `backend/app/services/storage_service.py` -- local fallback already functional
- Codebase: `frontend/src/contexts/AuthContext.tsx` -- 401 retry pattern reusable for JWT refresh
- Codebase: `frontend/src/utils/api.ts` -- `setAuthToken`/`clearAuthToken`/`setUnauthorizedHandler` already abstracted

# Architecture Patterns: v2.0 On-Prem Migration

**Domain:** Cloud-to-on-prem migration (Firebase/Firestore/GCS/Gemini removal)
**Researched:** 2026-03-25
**Confidence:** HIGH -- all components examined in source, patterns well-understood

## Current Architecture (What Exists)

```
Frontend (React 19)                Backend (FastAPI)                  Cloud Services
+-----------------------+     +----------------------------+     +------------------+
| firebase.ts           |     | core/auth.py               |     | Firebase Auth    |
| AuthContext.tsx        |---->|   verify_firebase_token()  |---->| (token verify)   |
| Login.tsx             |     |   get_firebase_app()       |     +------------------+
| Settings.tsx          |     |   allowlist mgmt (JSON)    |
| AdminSettings.tsx     |     +----------------------------+     +------------------+
+-----------------------+     | firestore_service.py       |---->| Firestore        |
                              |   1003 lines, 15 colls     |     | (15 collections) |
                              +----------------------------+     +------------------+
                              | storage_service.py         |
                              |   GCS + local fallback     |---->| GCS Bucket       |
                              +----------------------------+     +------------------+
                              | gemini_service.py          |
                              | llm/gemini_provider.py     |---->| Gemini API       |
                              +----------------------------+     +------------------+
```

## Target Architecture

```
Frontend (React 19)                Backend (FastAPI)                  Local Services
+-----------------------+     +----------------------------+     +------------------+
| AuthContext.tsx        |     | core/auth.py               |     | PostgreSQL 16    |
|   (JWT-based)         |---->|   verify_jwt_token()       |     | (all data)       |
| Login.tsx             |     |   bcrypt passwords         |     +------------------+
|   (direct POST)       |     |   users table via SQLAlch  |
+-----------------------+     +----------------------------+     +------------------+
                              | db_service.py              |     | Local filesystem |
                              |   SQLAlchemy async CRUD    |---->| (data/ dir)      |
                              +----------------------------+     +------------------+
                              | storage_service.py         |
                              |   Local-only (simplified)  |     +------------------+
                              +----------------------------+     | LM Studio        |
                              | llm/__init__.py            |---->| (OpenAI compat)  |
                              | llm/openai_provider.py     |     +------------------+
                              +----------------------------+
```

## Component Boundaries

| Component | Responsibility | Change Type | Communicates With |
|-----------|---------------|-------------|-------------------|
| `core/auth.py` | JWT creation, verification, user CRUD, role checks | **REWRITE** | PostgreSQL users table |
| `core/config.py` | App settings, env vars | **MODIFY** | All services |
| `core/database.py` | SQLAlchemy engine, sessions | **KEEP** (already exists) | PostgreSQL |
| `models/db_models.py` | ORM models for all tables | **EXTEND** | database.py |
| `services/firestore_service.py` | Firestore CRUD for 15 collections | **DELETE** | -- |
| `services/db_service.py` | SQLAlchemy CRUD matching firestore_service API | **NEW** | PostgreSQL |
| `services/storage_service.py` | File storage abstraction | **SIMPLIFY** | Local filesystem only |
| `services/gemini_service.py` | Gemini AI validation | **KEEP** | Gemini API (optional) |
| `services/llm/__init__.py` | Provider factory | **MODIFY** | LLM providers |
| `services/llm/openai_provider.py` | OpenAI-compatible LLM calls | **NEW** | LM Studio |
| `services/llm/protocol.py` | LLMProvider interface | **KEEP** | -- |
| `services/rrc_background.py` | Background RRC downloads | **MODIFY** | Sync SQLAlchemy session |
| `main.py` | App startup, router mounting | **MODIFY** | auth, config, DB |
| `api/admin.py` | User management, app settings | **MODIFY** | db_service |
| Frontend `AuthContext.tsx` | Auth state, login/logout | **REWRITE** | Backend JWT endpoints |
| Frontend `firebase.ts` | Firebase init | **DELETE** | -- |
| Frontend `Login.tsx` | Login form | **MODIFY** | AuthContext |

## Data Flow Changes

### Auth Flow: Before vs After

**Before (Firebase):**
```
User clicks "Sign In with Google"
  -> Firebase SDK popup -> Google OAuth
  -> Firebase returns ID token
  -> Frontend stores token, sends in Authorization header
  -> Backend verify_firebase_token() calls firebase_admin.auth.verify_id_token()
  -> Backend checks email against JSON allowlist
  -> 200 OK or 403 Forbidden
```

**After (JWT):**
```
User enters email + password on Login page
  -> Frontend POST /api/auth/login { email, password }
  -> Backend bcrypt.checkpw(password, stored_hash)
  -> Backend creates JWT with { sub: user_id, email, role, exp }
  -> Returns { access_token, token_type, user: { email, role, ... } }
  -> Frontend stores token in memory + localStorage
  -> Frontend sends Authorization: Bearer <jwt> on all requests
  -> Backend verify_jwt_token() decodes JWT, checks exp
  -> 200 OK or 401 Unauthorized
```

**New auth endpoints:**
```
POST /api/auth/login        -> { access_token, user }
GET  /api/auth/me           -> { user } (from JWT)
POST /api/auth/refresh      -> { access_token } (optional, for long sessions)
```

**JWT dependency chain (replaces require_auth):**
```python
# New auth.py pattern
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=["HS256"])
    user = await db_service.get_user_by_email(payload["email"])
    if not user or not user["is_active"]:
        raise HTTPException(401)
    return user

async def require_auth(user: dict = Depends(get_current_user)) -> dict:
    return user  # Same signature as current, all router deps unchanged

async def require_admin(user: dict = Depends(require_auth)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(403)
    return user
```

**Key insight:** `require_auth` and `require_admin` keep the exact same signatures. Every `Depends(require_auth)` in `main.py` and route handlers works unchanged. The only thing that changes is the internal implementation (JWT decode instead of Firebase verify).

### Database Flow: Firestore to PostgreSQL

**Firestore collections mapped to PostgreSQL tables:**

| Firestore Collection | PostgreSQL Table | Existing ORM Model? | Notes |
|---------------------|-----------------|---------------------|-------|
| `users` | `users` | YES (User) | Add `password_hash`, `role`, `scope`, `tools` columns |
| `jobs` | `jobs` | YES (Job) | Add `user_name` column |
| `extract_entries` | `extract_entries` | YES (ExtractEntry) | As-is |
| `title_entries` | `title_entries` | YES (TitleEntry) | As-is |
| `proration_rows` | `proration_rows` | YES (ProrationRow) | As-is |
| `revenue_statements` | `revenue_statements` | YES (RevenueStatement) | As-is |
| `revenue_rows` | `revenue_rows` | YES (RevenueRow) | As-is |
| `rrc_oil_proration` | `rrc_oil_proration` | YES (RRCOilProration) | Add unique constraint on (district, lease_number) |
| `rrc_gas_proration` | `rrc_gas_proration` | YES (RRCGasProration) | Add unique constraint on (district, lease_number) |
| `rrc_data_syncs` | `rrc_data_syncs` | YES (RRCDataSync) | As-is |
| `rrc_county_status` | `rrc_county_status` | NO | **NEW model** |
| `rrc_metadata` | `rrc_metadata` | NO | **NEW model** (key-value for counts) |
| `rrc_sync_jobs` | `rrc_sync_jobs` | NO | **NEW model** (background job tracking) |
| `audit_logs` | `audit_logs` | YES (AuditLog) | As-is |
| `app_config` | `app_config` | NO | **NEW model** (key-value config store) |
| `user_preferences` | `user_preferences` | NO | **NEW model** |

**New ORM models needed (5):**
1. `RRCCountyStatus` -- district, county_code, status, oil_record_count, last_downloaded_at
2. `RRCMetadata` -- key (primary), oil_rows, gas_rows, last_sync_at, new_records, updated_records
3. `RRCSyncJob` -- id, status, data_type, progress, error_message, timestamps
4. `AppConfig` -- key (primary), value (JSONB), updated_at
5. `UserPreference` -- user_email (primary), preferences (JSONB), updated_at

**Existing User model changes:**
```python
class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(128), primary_key=True)  # UUID, not Firebase UID
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))  # NEW: bcrypt hash
    role: Mapped[str] = mapped_column(String(20), default="user")  # NEW: admin/user/viewer
    scope: Mapped[str] = mapped_column(String(20), default="all")  # NEW
    tools: Mapped[list] = mapped_column(JSONB, default=list)  # NEW
    first_name: Mapped[Optional[str]] = mapped_column(String(100))  # NEW
    last_name: Mapped[Optional[str]] = mapped_column(String(100))  # NEW
    # ... display_name, photo_url, is_admin, is_active, timestamps unchanged
```

### db_service.py API Surface

`db_service.py` must expose the exact same function signatures as `firestore_service.py` to minimize caller changes. The 30+ import sites throughout the codebase (`from app.services.firestore_service import X`) become `from app.services.db_service import X`.

**Strategy:** Create `db_service.py` with matching function names. Then find-and-replace all `firestore_service` imports to `db_service`. Callers do not change.

**Critical functions to implement (grouped):**

```
# User ops
get_or_create_user(uid, email, ...) -> dict

# Job ops
create_job(tool, filename, ...) -> dict
update_job_status(job_id, status, ...) -> dict | None
get_job(job_id) -> dict | None
delete_job(job_id) -> bool
get_user_jobs(user_id, tool, limit) -> list[dict]
get_recent_jobs(tool, limit) -> list[dict]

# Entry ops (per tool)
save_extract_entries(job_id, entries) -> int
get_extract_entries(job_id) -> list[dict]
save_title_entries(job_id, entries) -> int
get_title_entries(job_id) -> list[dict]
save_proration_rows(job_id, rows) -> int
get_proration_rows(job_id) -> list[dict]
save_revenue_statement(job_id, data) -> dict
get_revenue_statements(job_id) -> list[dict]

# RRC ops
upsert_rrc_oil_record(...) -> tuple[dict, bool, bool]
upsert_rrc_gas_record(...) -> tuple[dict, bool, bool]
lookup_rrc_acres(district, lease) -> dict | None
lookup_rrc_by_lease_number(lease) -> dict | None
get_rrc_cached_status() -> dict | None
update_rrc_metadata_counts(...) -> None
get_rrc_data_status() -> dict
start_rrc_sync(data_type) -> str
complete_rrc_sync(...) -> None

# County status ops
get_counties_status(keys) -> dict
update_county_status(key, data) -> None
get_all_tracked_county_keys() -> list[str]
get_stale_counties(keys) -> list[str]

# Config/prefs
get_config_doc(doc_id) -> dict | None
set_config_doc(doc_id, data) -> None
get_user_preferences(email) -> dict | None
set_user_preferences(email, prefs) -> None

# Audit
create_audit_log(...) -> dict
```

### Storage Flow: GCS to Local-Only

**Current:** `StorageService` tries GCS first, falls back to local `data/` directory.
**Target:** Local filesystem only. Remove all GCS code.

**What changes:**
- Remove `_init_client()`, all `_*_gcs()` methods, `get_signed_url()`
- `is_gcs_enabled` always returns `False`
- Keep `_*_local()` methods as the primary (and only) implementation
- `upload_file()`, `download_file()`, etc. call local methods directly
- Remove `GCS_AVAILABLE` import guard
- `RRCDataStorage`, `UploadStorage`, `ProfileStorage` work unchanged (they call `self.storage.*` which routes to local)

**Config change:** Set `gcs_bucket_name` default to `None` so `use_gcs` returns `False`. No GCS warnings when unconfigured.

### AI Flow: Gemini to OpenAI-Compatible

**Current LLM abstraction (already exists):**
```
llm/__init__.py   -> get_llm_provider() -> GeminiProvider
llm/protocol.py   -> LLMProvider protocol (cleanup_entries, is_available)
llm/gemini_provider.py -> Uses google.genai Client
```

**Target:**
```
llm/__init__.py   -> get_llm_provider() -> routes based on AI_PROVIDER env var
llm/protocol.py   -> LLMProvider protocol (unchanged)
llm/gemini_provider.py -> Kept for backward compat
llm/openai_provider.py -> NEW: uses openai.AsyncOpenAI client
```

**New provider pattern:**
```python
# llm/openai_provider.py
from openai import AsyncOpenAI

class OpenAIProvider:
    def __init__(self):
        self.client = AsyncOpenAI(
            base_url=settings.llm_api_base,  # "http://localhost:1234/v1"
            api_key=settings.llm_api_key or "lm-studio",
        )
        self.model = settings.llm_model  # "qwen2.5-coder-32b"

    def is_available(self) -> bool:
        return bool(settings.llm_api_base)

    async def cleanup_entries(self, tool, entries, ...) -> list[ProposedChange]:
        # Same prompt templates from llm/prompts.py
        # Uses client.chat.completions.create() with JSON response_format
        ...
```

**Updated factory:**
```python
# llm/__init__.py
def get_llm_provider() -> LLMProvider | None:
    provider_name = settings.ai_provider  # "gemini" | "openai" | "lmstudio"

    if provider_name in ("openai", "lmstudio"):
        from app.services.llm.openai_provider import OpenAIProvider
        provider = OpenAIProvider()
        return provider if provider.is_available() else None

    # Default: Gemini (backward compatible)
    from app.services.llm.gemini_provider import GeminiProvider
    provider = GeminiProvider()
    return provider if provider.is_available() else None
```

**gemini_service.py stays:** The old `gemini_service.py` is called directly by `api/ai_validation.py` for the `/api/ai/review` endpoint, separate from the pipeline LLM abstraction. It can stay as a legacy path or be refactored later.

**New config vars:**
```python
# config.py additions
ai_provider: str = "gemini"         # "gemini" | "openai" | "lmstudio"
llm_api_base: Optional[str] = None  # "http://localhost:1234/v1"
llm_api_key: Optional[str] = None   # API key (LM Studio ignores)
llm_model: Optional[str] = None     # "qwen2.5-coder-32b"
jwt_secret_key: Optional[str] = None # Required for JWT auth
```

## Patterns to Follow

### Pattern 1: Same-Signature Service Replacement
**What:** `db_service.py` exposes identical function signatures to `firestore_service.py`.
**Why:** 30+ import sites. Changing signatures means touching every caller.
**How:** Build function-by-function matching firestore_service, then bulk-rename imports.

```python
# firestore_service.py (current)
async def create_job(tool: str, source_filename: str, ...) -> dict:
    db = get_firestore_client()
    ...

# db_service.py (new, same signature)
async def create_job(tool: str, source_filename: str, ...) -> dict:
    async with get_db_session() as session:
        job = Job(tool=tool, source_filename=source_filename, ...)
        session.add(job)
        await session.flush()
        return _job_to_dict(job)
```

### Pattern 2: Auth Dependency Preservation
**What:** Keep `require_auth` and `require_admin` with identical signatures.
**Why:** 12 router `dependencies=[Depends(require_auth)]` in main.py. Must not change.
**How:** Only change the internal implementation (JWT decode instead of Firebase verify).

### Pattern 3: Provider Factory for AI
**What:** `get_llm_provider()` routes to the correct provider based on config.
**Why:** Already exists for Gemini. Adding OpenAI is one more branch.
**How:** Add `ai_provider` setting, add `openai_provider.py`, update factory.

### Pattern 4: Background Thread DB Access
**What:** `rrc_background.py` needs synchronous DB access (runs outside asyncio).
**Why:** Background thread cannot use async SQLAlchemy sessions.
**How:** Create synchronous SQLAlchemy session factory for background threads.

```python
# database.py addition
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Sync URL: replace +asyncpg with psycopg2
_sync_url = settings.database_url.replace("+asyncpg", "+psycopg2")
sync_engine = create_engine(_sync_url, pool_pre_ping=True)
SyncSession = sessionmaker(sync_engine)

def get_sync_db() -> Session:
    return SyncSession()
```

### Pattern 5: Dict Return Convention
**What:** All db_service functions return `dict`, not ORM objects.
**Why:** Callers expect `dict` (from Firestore's `.to_dict()`). Changing to ORM objects breaks `user["email"]` access patterns everywhere.
**How:** Each function converts ORM model to dict before returning via helper functions.

```python
def _user_to_dict(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "is_admin": user.role == "admin",
        "is_active": user.is_active,
        "role": user.role,
        "scope": user.scope,
        "tools": user.tools or [],
        "first_name": user.first_name,
        "last_name": user.last_name,
        "created_at": user.created_at,
        "last_login_at": user.last_login_at,
    }
```

## Anti-Patterns to Avoid

### Anti-Pattern 1: Gradual Migration with Feature Flags
**What:** Running both Firestore and PostgreSQL simultaneously with `if settings.use_firestore` checks.
**Why bad:** Doubles code paths, doubles bugs, never gets cleaned up. Both databases drift.
**Instead:** Hard cutover. Build PostgreSQL path, run migration script, delete Firestore code.

### Anti-Pattern 2: Changing Auth Dependency Signatures
**What:** Changing `require_auth` to return an ORM `User` object instead of `dict`.
**Why bad:** Every route handler unpacks `user["email"]`, `user.get("uid")`. Changing return type means touching 20+ handlers.
**Instead:** Keep returning `dict` with the same keys.

### Anti-Pattern 3: Keeping GCS Import Guards
**What:** Leaving `try: from google.cloud import storage` in storage_service.py.
**Why bad:** Dead code. On-prem will never have GCS credentials.
**Instead:** Remove all GCS code entirely.

### Anti-Pattern 4: Rewriting gemini_service.py
**What:** Replacing the 535-line gemini_service.py with an OpenAI version.
**Why bad:** It works, has rate limiting, has retry logic. Pipeline already uses LLM abstraction.
**Instead:** Keep it as-is. Add openai_provider.py via the existing LLM protocol.

### Anti-Pattern 5: SQLAlchemy Session Per Function
**What:** Creating a new session inside each db_service function.
**Why bad:** No transaction grouping, excessive connection usage.
**Instead:** Use a session factory that each function calls, but allow callers to pass sessions for transaction grouping when needed (e.g., `delete_job` which deletes entries + job in one transaction).

## File-Level Impact Analysis

### NEW Files (6)
| File | Purpose | Lines (est) |
|------|---------|-------------|
| `backend/app/services/db_service.py` | SQLAlchemy CRUD replacing firestore_service | ~600 |
| `backend/app/services/llm/openai_provider.py` | OpenAI-compatible LLM provider | ~150 |
| `backend/app/api/auth_routes.py` | `/api/auth/login`, `/api/auth/me` endpoints | ~80 |
| `backend/scripts/create_admin.py` | CLI script to create initial admin user | ~40 |
| `backend/scripts/migrate_firestore.py` | One-time Firestore-to-PostgreSQL migration | ~200 |
| `backend/scripts/create_tables.py` | Schema creation script | ~30 |

### REWRITE Files (2)
| File | What Changes | Risk |
|------|-------------|------|
| `backend/app/core/auth.py` | Remove Firebase SDK, add JWT creation/verification, bcrypt. Keep `require_auth`/`require_admin` signatures. Remove JSON allowlist (users in DB). | HIGH |
| `frontend/src/contexts/AuthContext.tsx` | Remove Firebase `onAuthStateChanged`, add JWT login via fetch, localStorage token. Remove Google Sign-In. | HIGH |

### MODIFY Files (12)
| File | What Changes | Risk |
|------|-------------|------|
| `backend/app/core/config.py` | Add `jwt_secret_key`, `ai_provider`, `llm_*` vars. Remove `gcs_bucket_name` default. Flip `database_enabled` to True, `firestore_enabled` to False. | LOW |
| `backend/app/core/database.py` | Add sync engine + sync session factory for background threads. | LOW |
| `backend/app/models/db_models.py` | Extend User model, add 5 new models, add unique constraints. | MEDIUM |
| `backend/app/main.py` | Remove Firestore init calls, add DB init, add auth router. | LOW |
| `backend/app/services/storage_service.py` | Remove all GCS code (~200 lines). Keep local-only ops. | LOW |
| `backend/app/services/llm/__init__.py` | Route to openai_provider based on `ai_provider` setting. | LOW |
| `backend/app/services/rrc_background.py` | Replace sync Firestore client with sync SQLAlchemy session. | MEDIUM |
| `backend/app/api/admin.py` | Replace Firestore config calls with db_service. Add password endpoints. | MEDIUM |
| `frontend/src/pages/Login.tsx` | Remove Google Sign-In button, use direct POST. | LOW |
| `frontend/src/pages/Settings.tsx` | Remove Firebase password references. | LOW |
| `frontend/src/pages/AdminSettings.tsx` | Remove Firebase user creation calls. | LOW |
| `frontend/src/utils/api.ts` | Token refresh via `/api/auth/refresh` instead of Firebase `getIdToken(true)`. | LOW |

### DELETE Files (2)
| File | Why |
|------|-----|
| `frontend/src/lib/firebase.ts` | No more Firebase SDK |
| `backend/app/services/firestore_service.py` | Replaced by db_service.py |

### BULK RENAME (30+ import sites in 15 files)
All `from app.services.firestore_service import X` become `from app.services.db_service import X`. Mechanical find-and-replace.

**Files with firestore imports (15):**
- `backend/app/core/auth.py`
- `backend/app/core/ingestion.py`
- `backend/app/api/admin.py`
- `backend/app/api/enrichment.py`
- `backend/app/api/ghl.py`
- `backend/app/api/proration.py`
- `backend/app/services/ghl/bulk_send_service.py`
- `backend/app/services/ghl/connection_service.py`
- `backend/app/services/rrc_background.py`
- `backend/app/services/proration/rrc_county_download_service.py`
- `backend/app/services/proration/rrc_data_service.py`
- `backend/app/services/proration/csv_processor.py`
- `backend/app/services/etl/entity_registry.py`

### NPM Packages to Remove
- `firebase` (frontend)
- All `VITE_FIREBASE_*` env vars

### Python Packages to Remove
- `firebase-admin`
- `google-cloud-firestore`
- `google-cloud-storage`

### Python Packages to Add
- `python-jose[cryptography]` (JWT)
- `bcrypt` (password hashing)
- `openai` (LM Studio client)
- `psycopg2-binary` (sync PostgreSQL driver for background threads)

## Test Impact

### Current Test Structure (18 test files)
Tests use `conftest.py` fixtures that override `require_auth` with a mock user dict:
```python
app.dependency_overrides[require_auth] = lambda: {"email": "test@example.com", "uid": "test-uid"}
```

This pattern is **unaffected** because `require_auth` keeps the same signature and return type.

### Tests That Need Changes
| Test | Change Needed |
|------|--------------|
| `test_auth_enforcement.py` | Update if it tests Firebase-specific behavior |
| `test_proration_cache.py` | Update firestore imports if present |
| `test_fetch_missing.py` | Update firestore imports if present |
| `test_pipeline.py` | Update firestore imports if present |

### Tests Completely Unaffected
All parser tests (10+ files): `test_extract_parser.py`, `test_ecf_parser.py`, `test_convey640_parser.py`, `test_revenue_parser.py`, `test_detect_format.py`, `test_merge_service.py`, `test_post_process.py`, `test_prompts.py`, `test_llm_protocol.py`. These test pure parsing/prompt logic with no auth or DB dependencies.

### New Tests Needed
| Test | Purpose |
|------|---------|
| `test_jwt_auth.py` | JWT creation, verification, expiration, invalid tokens |
| `test_db_service.py` | CRUD operations against test PostgreSQL |
| `test_openai_provider.py` | OpenAI provider with mocked responses |

## Suggested Build Order

Build order follows dependency chain. Auth is needed before DB migration (user table has auth fields). DB is needed before storage cleanup. AI is independent.

### Phase 1: Auth (JWT + PostgreSQL users)
**Dependencies:** None
**Why first:** Every other component needs auth working. Migration script needs user table.

1. Extend `User` model in `db_models.py`
2. Add `jwt_secret_key` to `config.py`
3. Rewrite `core/auth.py` (JWT verify, bcrypt, same require_auth/require_admin signatures)
4. Create `api/auth_routes.py` (login, me)
5. Create `scripts/create_admin.py`
6. Update `main.py` (add auth router, remove Firestore allowlist init)
7. Enable `database_enabled: True` in config, run schema creation
8. Rewrite `AuthContext.tsx` (JWT, localStorage)
9. Update `Login.tsx` (remove Google Sign-In)
10. Delete `firebase.ts`, remove Firebase npm packages
11. Update `Settings.tsx`, `AdminSettings.tsx`, `api.ts`

### Phase 2: Database Migration (Firestore to PostgreSQL)
**Dependencies:** Phase 1 (users table exists)
**Why second:** All data operations depend on this.

1. Add 5 new ORM models + unique constraints to `db_models.py`
2. Build `db_service.py` matching all firestore_service function signatures
3. Bulk-rename imports: `firestore_service` -> `db_service` (30+ sites, 15 files)
4. Update `rrc_background.py` (sync SQLAlchemy session)
5. Add sync session factory to `database.py`
6. Remove Firestore startup init calls from `main.py`
7. Create `scripts/migrate_firestore.py` (one-time migration)
8. Delete `firestore_service.py`

### Phase 3: Storage Simplification
**Dependencies:** Phase 2
**Why third:** Quick cleanup after DB migration removes GCS refs.

1. Strip all GCS code from `storage_service.py`
2. Set `gcs_bucket_name` default to `None`
3. Remove `google-cloud-storage`, `google-cloud-firestore`, `firebase-admin` from requirements.txt

### Phase 4: AI Provider
**Dependencies:** None (independent)
**Why last:** Lowest priority. Existing Gemini still works. LM Studio is optional.

1. Add `ai_provider`, `llm_api_base`, `llm_model`, `llm_api_key` to config
2. Create `llm/openai_provider.py` implementing LLMProvider protocol
3. Update `llm/__init__.py` factory
4. Add `openai` to requirements.txt

## Docker/Deployment Changes

On-prem `docker-compose.yml` needs:
```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: toolbox
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: <secret>
    volumes:
      - pgdata:/var/lib/postgresql/data

  backend:
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:<secret>@db:5432/toolbox
      DATABASE_ENABLED: "true"
      FIRESTORE_ENABLED: "false"
      GCS_BUCKET_NAME: ""
      JWT_SECRET_KEY: <generated>
      AI_PROVIDER: lmstudio  # optional
      LLM_API_BASE: http://host.docker.internal:1234/v1  # optional
```

## Sources

- Codebase: `backend/app/core/auth.py` (373 lines -- Firebase token verification, allowlist management)
- Codebase: `backend/app/services/firestore_service.py` (1003 lines -- 15 Firestore collections, all CRUD operations)
- Codebase: `backend/app/services/storage_service.py` (484 lines -- GCS + local fallback)
- Codebase: `backend/app/services/gemini_service.py` (535 lines -- Gemini API with rate limiting)
- Codebase: `backend/app/services/llm/protocol.py` (existing LLMProvider protocol)
- Codebase: `backend/app/services/llm/__init__.py` (existing provider factory)
- Codebase: `backend/app/models/db_models.py` (existing SQLAlchemy models for 10 tables)
- Codebase: `backend/app/core/database.py` (existing async engine and session factory)
- Codebase: `backend/app/services/rrc_background.py` (sync Firestore client pattern for background threads)
- Codebase: `backend/tests/conftest.py` (auth mock pattern via dependency override)
- Codebase: `frontend/src/contexts/AuthContext.tsx` (Firebase auth state management)
- Codebase: `frontend/src/lib/firebase.ts` (Firebase SDK initialization)
- Codebase: grep results -- 30+ firestore_service imports across 15 backend files
- Codebase: grep results -- 4 frontend files importing Firebase

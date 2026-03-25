# Technology Stack: v2.0 On-Prem Migration

**Project:** Table Rock Tools
**Researched:** 2026-03-25
**Scope:** NEW infrastructure only (JWT auth, PostgreSQL-only, local storage, LM Studio AI)

## Recommended Stack Changes

### Authentication (Firebase Auth -> Local JWT)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| PyJWT | >=2.12.0 | JWT token creation/verification | FastAPI official docs switched from python-jose to PyJWT. python-jose is abandoned (no release in 3+ years). PyJWT is actively maintained, simpler API, HS256 is sufficient for internal app. |
| pwdlib[bcrypt] | >=0.2.0 | Password hashing | FastAPI official docs switched from passlib to pwdlib. passlib is unmaintained and broken with bcrypt>=5.0 and Python>=3.13. pwdlib is from the FastAPI-Users author, supports bcrypt natively. Use `[bcrypt]` extra, not `[argon2]` -- bcrypt is simpler to deploy (no system deps) and sufficient for small internal team. |

**NOT python-jose:** Abandoned, last release 2021. FastAPI PR #11589 formally replaced it.
**NOT passlib:** Unmaintained since 2020, broken with bcrypt 5.0+, incompatible with Python 3.13+.
**NOT argon2:** Requires system-level `argon2-cffi` build dependencies. Bcrypt is universally available and sufficient for <20 users.

### Database (Firestore -> PostgreSQL-only)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| SQLAlchemy[asyncio] | >=2.0.0 | ORM + async database access | Already in requirements.txt and used in `database.py` + `db_models.py`. Models exist for all entity types. Just needs to become the primary path. |
| asyncpg | >=0.29.0 | Async PostgreSQL driver | Already in requirements.txt. Used by SQLAlchemy async engine. |
| Alembic | >=1.18.0 | Schema migrations | Already in requirements.txt. Required now because PostgreSQL becomes the sole database -- schema changes need proper migration tracking. Use `alembic init --template async` for async engine compat. |
| psycopg2-binary | >=2.9.0 | Sync PostgreSQL driver (Alembic) | Already in requirements.txt. Alembic migrations run synchronously even with async engine. Needed for `env.py` offline mode. |

**Key finding:** The existing codebase already has full SQLAlchemy models in `db_models.py` covering Users, Jobs, ExtractEntry, TitleEntry, ProrationRow, RevenueStatement, RevenueRow, RRC data, and AuditLog. The `database.py` module has async engine, session factory, and `init_db()`. This is not a greenfield migration -- it is activating and extending code that already exists.

**Missing models to add:**
- `AppConfig` -- replaces Firestore `app_config` collection (allowlist, settings)
- `UserPreference` -- replaces Firestore `user_preferences` collection
- `RRCCountyStatus` -- replaces Firestore `rrc_county_status` collection
- `password_hash` column on existing `User` model
- `role`, `scope`, `tools` columns on existing `User` model (currently in JSON allowlist)

**Alembic vs create_all:** Use Alembic. The existing `init_db()` uses `Base.metadata.create_all` which is fine for initial setup but cannot handle schema evolution. With PostgreSQL as sole DB, Alembic is mandatory for adding columns, indexes, etc. without data loss.

### AI Provider (Gemini -> LM Studio via OpenAI SDK)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| openai | >=1.60.0 | OpenAI-compatible API client | LM Studio exposes `/v1/chat/completions` endpoint that is 100% OpenAI SDK compatible. Set `base_url="http://localhost:1234/v1"` and `api_key="not-needed"`. Zero code changes to prompt logic, just client initialization. |

**NOT google-genai for LM Studio:** LM Studio does not speak Gemini protocol. The OpenAI-compatible endpoint is the standard for local LLMs.
**NOT litellm:** Adds unnecessary abstraction. The openai SDK already handles routing to any OpenAI-compatible endpoint via `base_url`.
**NOT lmstudio SDK:** Exists but is less mature. OpenAI SDK is battle-tested and lets you switch between LM Studio, Ollama, vLLM, or actual OpenAI with zero code changes.

**Integration pattern:**
```python
# Current Gemini code in gemini_service.py:
from google import genai
client = genai.Client(api_key=settings.gemini_api_key)
response = client.models.generate_content(model=..., contents=..., config=...)

# New OpenAI-compatible code:
from openai import OpenAI
client = OpenAI(base_url=settings.llm_api_base, api_key=settings.llm_api_key or "not-needed")
response = client.chat.completions.create(model=settings.llm_model, messages=[...], response_format={"type": "json_object"})
```

**LM Studio JSON mode:** LM Studio supports `response_format: {"type": "json_object"}` which replaces Gemini's `response_mime_type="application/json"` + `response_json_schema`. The schema enforcement is less strict -- validation moves to the application layer (Pydantic parsing of response).

### Storage (GCS -> Local Filesystem)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| (none new) | - | Local filesystem storage | `StorageService` already has local fallback. Change: make local the default when `GCS_BUCKET_NAME` is empty/unset, suppress GCS warnings. No new dependencies needed. |

**What changes:** Default `gcs_bucket_name` from `"table-rock-tools-storage"` to `None` in config.py. When `None`, `use_gcs` returns `False` and all storage silently uses `data_dir`. Remove log warnings about GCS unavailability.

### Frontend Auth (Firebase SDK -> fetch-based JWT)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| (none new) | - | JWT auth via fetch API | Remove `firebase` npm package (12.9.0). Replace `AuthContext.tsx` with local auth context that stores JWT in localStorage, sends as Bearer token. Login page calls `POST /api/auth/login` instead of Firebase `signInWithEmailAndPassword`. No new npm dependencies needed. |

**What gets removed from frontend:**
- `firebase` npm package (~600KB gzipped)
- `frontend/src/lib/firebase.ts`
- All `firebase/auth` imports in `AuthContext.tsx`
- Google Sign-In provider (replaced by email/password only)
- Firebase config env vars (`VITE_FIREBASE_*`)

## New Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `JWT_SECRET_KEY` | Yes (production) | auto-generated in dev | HMAC secret for JWT signing. Generate with `openssl rand -hex 32`. |
| `JWT_ALGORITHM` | No | `HS256` | JWT signing algorithm |
| `JWT_EXPIRE_MINUTES` | No | `1440` (24h) | Token expiry. 24h is fine for internal tool with small team. |
| `AI_PROVIDER` | No | `none` | `gemini`, `openai`, or `none`. Controls which AI backend is used. |
| `LLM_API_BASE` | No | `http://localhost:1234/v1` | Base URL for OpenAI-compatible API (LM Studio default). |
| `LLM_MODEL` | No | `local-model` | Model name to request from LM Studio. |
| `LLM_API_KEY` | No | `not-needed` | API key for LLM provider. LM Studio ignores this. |
| `DATABASE_URL` | Yes | `postgresql+asyncpg://postgres:postgres@localhost:5432/toolbox` | Already exists. Becomes mandatory. |
| `DATABASE_ENABLED` | Removed | - | No longer needed. PostgreSQL is always on. |
| `FIRESTORE_ENABLED` | Removed | - | Firestore removed entirely. |
| `GCS_BUCKET_NAME` | No | `None` | Default changes to None (was `table-rock-tools-storage`). |

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| JWT | PyJWT | python-jose | Abandoned, no releases since 2021, FastAPI dropped it |
| JWT | PyJWT | Authlib | Heavier, full OAuth2 framework -- overkill for internal JWT |
| Password hashing | pwdlib[bcrypt] | passlib[bcrypt] | Unmaintained, broken with bcrypt>=5.0, Python>=3.13 incompatible |
| Password hashing | pwdlib[bcrypt] | bcrypt (direct) | No verify/hash helpers, pwdlib wraps it cleanly |
| Password hashing | pwdlib[bcrypt] | pwdlib[argon2] | argon2 needs system deps (libargon2), bcrypt is simpler |
| AI client | openai SDK | litellm | Unnecessary abstraction layer, openai SDK handles base_url natively |
| AI client | openai SDK | httpx (raw) | Reinventing the wheel, openai SDK handles retries/streaming/types |
| AI client | openai SDK | lmstudio-python | Less mature, smaller ecosystem, openai SDK is universal |
| Migrations | Alembic | create_all | Can't evolve schema without data loss |
| Migrations | Alembic | manual SQL | Error-prone, no rollback tracking |

## Installation

```bash
# New backend dependencies (add to requirements.txt)
pip install PyJWT>=2.12.0
pip install "pwdlib[bcrypt]>=0.2.0"
pip install "openai>=1.60.0"

# Already in requirements.txt (no changes needed)
# sqlalchemy[asyncio]>=2.0.0
# asyncpg>=0.29.0
# psycopg2-binary>=2.9.0
# alembic>=1.13.0

# Frontend: REMOVE firebase
cd frontend && npm uninstall firebase
```

## Dependencies to REMOVE

```bash
# Backend (requirements.txt)
# REMOVE these lines:
# google-cloud-storage>=2.14.0
# google-cloud-firestore>=2.14.0
# firebase-admin>=6.2.0
# google-genai>=1.0.0   (keep if dual-provider support desired)

# Frontend (package.json)
# REMOVE:
# "firebase": "^12.9.0"
```

## Confidence Assessment

| Decision | Confidence | Basis |
|----------|------------|-------|
| PyJWT over python-jose | HIGH | FastAPI official docs PR #11589, python-jose abandoned |
| pwdlib over passlib | HIGH | FastAPI official docs, passlib broken with bcrypt 5.0+ |
| openai SDK for LM Studio | HIGH | LM Studio official docs confirm full OpenAI API compat |
| Alembic for migrations | HIGH | Already in requirements.txt, standard SQLAlchemy practice |
| No new frontend deps | HIGH | JWT auth is just fetch + localStorage, no library needed |
| bcrypt over argon2 | MEDIUM | Both work, bcrypt avoids system deps, argon2 is theoretically stronger but irrelevant for <20 users |

## Sources

- [FastAPI JWT Tutorial (official)](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/) -- PyJWT + pwdlib
- [FastAPI PR #11589: Replace python-jose with PyJWT](https://github.com/fastapi/fastapi/pull/11589)
- [FastAPI Discussion #11345: Abandon python-jose](https://github.com/fastapi/fastapi/discussions/11345)
- [FastAPI Discussion #11773: passlib unmaintained](https://github.com/fastapi/fastapi/discussions/11773)
- [LM Studio OpenAI Compatibility Docs](https://lmstudio.ai/docs/developer/openai-compat)
- [PyJWT PyPI](https://pypi.org/project/PyJWT/) -- v2.12.1
- [OpenAI Python SDK PyPI](https://pypi.org/project/openai/) -- v2.29.0
- [pwdlib PyPI](https://pypi.org/project/pwdlib/)
- [Alembic Documentation](https://alembic.sqlalchemy.org/en/latest/) -- v1.18.4

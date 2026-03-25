# Architecture: v2.0 On-Prem Migration

**Domain:** Cloud-to-on-prem infrastructure migration for FastAPI + React SPA
**Researched:** 2026-03-25
**Confidence:** HIGH -- most target patterns already exist in the codebase

## Current Architecture (Cloud)

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   React SPA  │────>│  FastAPI API  │────>│  Firestore   │
│  (Vite:5173) │     │  (Uvicorn)   │     │  (primary DB)│
└──────┬───────┘     └──────┬───────┘     └──────────────┘
       │                    │
  Firebase Auth      ┌──────┴───────┐
  (Google Sign-In)   │  GCS Bucket  │
                     │  + Gemini AI │
                     └──────────────┘
```

## Target Architecture (On-Prem)

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   React SPA  │────>│  FastAPI API  │────>│  PostgreSQL  │
│  (Vite:5173) │     │  (Uvicorn)   │     │  (sole DB)   │
└──────┬───────┘     └──────┬───────┘     └──────────────┘
       │                    │
  JWT Auth (local)   ┌──────┴───────┐
  (email/password)   │  Local FS    │
                     │  + LM Studio │
                     └──────────────┘
```

## Component Boundaries

| Component | Current | Target | Change Scope |
|-----------|---------|--------|-------------|
| `auth.py` | Firebase Admin SDK token verification | PyJWT `jwt.decode()` + bcrypt password verification | Replace ~3 functions, keep dependency injection pattern |
| `firestore_service.py` | ~40 async functions across 13 collections | `db_service.py` using SQLAlchemy async sessions | New file, port all function signatures |
| `gemini_service.py` | google-genai `Client.models.generate_content()` | OpenAI SDK `client.chat.completions.create()` | Rewrite client init + API calls, keep prompt logic |
| `storage_service.py` | GCS primary, local fallback | Local primary, GCS optional | Config default change only |
| `config.py` | Firebase/Firestore/GCS defaults on | PostgreSQL/local defaults on | Change 4 default values, add JWT + AI config |
| `AuthContext.tsx` | Firebase SDK `onAuthStateChanged` | fetch-based JWT with localStorage | Full rewrite of auth provider |
| `firebase.ts` | Firebase app + auth init | Deleted | Remove file entirely |
| `Login.tsx` | Firebase `signInWithEmailAndPassword` | `POST /api/auth/login` | Replace auth calls, keep UI structure |

## Auth Architecture

### Backend Auth Flow

```
POST /api/auth/login {email, password}
  │
  ├─ Query users table by email
  ├─ Verify password with pwdlib.verify()
  ├─ Create JWT: jwt.encode({sub: email, role: role, exp: ...}, SECRET_KEY)
  └─ Return {access_token, user: {email, role, first_name, last_name}}

GET /api/extract/upload (Authorization: Bearer <jwt>)
  │
  ├─ HTTPBearer extracts token (existing pattern)
  ├─ jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
  ├─ Check user exists + is_active in DB
  └─ Return user dict to route handler (same shape as current Firebase decoded token)
```

### Key Design Decision: Keep Dependency Injection Pattern

The current auth uses FastAPI's `Depends()` chain:
```python
# Current (keep this pattern, just change internals)
async def get_current_user(credentials = Depends(security)) -> Optional[dict]
async def require_auth(user = Depends(get_current_user)) -> dict
async def require_admin(user = Depends(require_auth)) -> dict
```

Every route handler and router-level dependency already uses `require_auth` or `require_admin`. The migration changes what happens INSIDE `get_current_user` (JWT decode instead of Firebase verify) but the external interface stays identical. This means **zero changes to route handlers**.

### JWT Token Claims

```python
{
    "sub": "james@tablerocktx.com",  # email as subject
    "role": "admin",                  # admin | user | viewer
    "exp": 1711449600,               # expiry timestamp
    "iat": 1711363200                # issued at
}
```

No refresh tokens. 24-hour expiry. Small internal team re-logs in daily. Avoids refresh token complexity (rotation, storage, revocation).

### Frontend Auth Flow

```
Login page: POST /api/auth/login -> receive {access_token, user}
  │
  ├─ Store token in AuthContext state (not localStorage for access token)
  ├─ ApiClient.setAuthToken(token)  (existing method, no change)
  └─ Navigate to Dashboard

On page load: check localStorage for "was_logged_in" flag
  │
  ├─ If flag exists: GET /api/auth/me with stored token
  │    ├─ 200: restore session
  │    └─ 401: clear flag, show login
  └─ If no flag: show login
```

Actually, for simplicity: store JWT in localStorage directly. This is an internal tool behind a VPN/LAN, not a public-facing app. The token is already sent as Bearer header (no CSRF risk). localStorage survives page refreshes.

## Database Architecture

### Service Layer Pattern

Replace `firestore_service.py` with `db_service.py` using identical function signatures:

```python
# firestore_service.py (current)
async def create_job(user_id, tool, filename, ...) -> str:
    doc_ref = db.collection("jobs").document()
    await doc_ref.set({...})
    return doc_ref.id

# db_service.py (target)
async def create_job(user_id, tool, filename, ...) -> str:
    async with async_session_maker() as session:
        job = Job(user_id=user_id, tool=tool, source_filename=filename, ...)
        session.add(job)
        await session.commit()
        return str(job.id)
```

The function signatures stay the same so callers (route handlers) need minimal changes -- just change the import path.

### Alembic Setup

```
backend/
├── alembic/
│   ├── env.py          # Async engine configuration
│   ├── script.py.mako  # Migration template
│   └── versions/       # Migration files
├── alembic.ini         # Database URL reference
```

**env.py key pattern for async:**
```python
from app.core.database import engine
from app.models.db_models import Base  # Import all models

def run_migrations_online():
    connectable = engine  # async engine
    # Use run_sync pattern for Alembic's synchronous migration functions
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
```

### Missing PostgreSQL Models

```python
# Add to db_models.py

class AppConfig(Base):
    __tablename__ = "app_config"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    data: Mapped[dict] = mapped_column(JSONB, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class UserPreference(Base):
    __tablename__ = "user_preferences"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), ForeignKey("users.id"), unique=True)
    data: Mapped[dict] = mapped_column(JSONB, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class RRCCountyStatus(Base):
    __tablename__ = "rrc_county_status"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    county_code: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    county_name: Mapped[str] = mapped_column(String(100))
    well_type: Mapped[str] = mapped_column(String(10))
    last_downloaded: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    record_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="pending")
```

**User model additions:**
```python
class User(Base):
    # ... existing columns ...
    password_hash: Mapped[Optional[str]] = mapped_column(String(255))  # bcrypt hash
    role: Mapped[str] = mapped_column(String(20), default="user")      # admin|user|viewer
    scope: Mapped[str] = mapped_column(String(20), default="all")      # all|land|revenue|operations
    tools: Mapped[list] = mapped_column(JSONB, default=list)           # ["extract","title",...]
```

## AI Provider Architecture

### Provider Abstraction

The codebase already has an `LLMProvider` protocol in `services/llm/`. Add an OpenAI-compatible provider:

```python
# services/llm/openai_provider.py
from openai import OpenAI

class OpenAICompatibleProvider:
    def __init__(self, base_url: str, api_key: str, model: str):
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model = model

    async def cleanup_entries(self, tool: str, entries: list[dict]) -> list[dict]:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": TOOL_PROMPTS[tool]},
                {"role": "user", "content": json.dumps(entries)},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        return json.loads(response.choices[0].message.content)

    def is_available(self) -> bool:
        try:
            self.client.models.list()
            return True
        except Exception:
            return False
```

### Provider Factory

```python
# services/llm/__init__.py
def get_llm_provider() -> Optional[LLMProvider]:
    if settings.ai_provider == "gemini" and settings.use_gemini:
        return GeminiProvider(...)
    elif settings.ai_provider in ("openai", "lm_studio"):
        return OpenAICompatibleProvider(
            base_url=settings.llm_api_base,
            api_key=settings.llm_api_key or "not-needed",
            model=settings.llm_model,
        )
    return None
```

## Anti-Patterns to Avoid

### Anti-Pattern 1: Dual Database Period
**What:** Running Firestore and PostgreSQL simultaneously during migration.
**Why bad:** Two sources of truth, data drift, doubled complexity. Every service needs conditional logic.
**Instead:** Hard cutover. Port all services to PostgreSQL first (with tests), then flip the switch. One database at a time.

### Anti-Pattern 2: Abstracting Storage Behind an Interface
**What:** Creating a `StorageBackend` ABC with `GCSBackend` and `LocalBackend` implementations.
**Why bad:** Over-engineering. The local fallback already works in `StorageService`. The migration is just changing the default.
**Instead:** Keep `StorageService` as-is. Change config defaults so local is the default path.

### Anti-Pattern 3: Token Refresh Complexity
**What:** Implementing refresh tokens, token rotation, blacklists.
**Why bad:** This is a <20 user internal tool. The complexity of refresh token management (rotation, replay detection, storage) is not justified.
**Instead:** 24-hour access tokens. User re-logs in daily. If a user is deactivated, they're blocked on next API call (allowlist check).

### Anti-Pattern 4: Migrating Firestore Data Structure 1:1
**What:** Creating PostgreSQL tables that mirror Firestore's document/subcollection nesting.
**Why bad:** Firestore's schemaless nested documents don't map cleanly to relational tables. Forcing it creates inefficient schemas.
**Instead:** The existing SQLAlchemy models are already properly relational. Use them as the target schema, not Firestore's structure.

## Sources

- Codebase: `backend/app/core/auth.py` -- current Firebase auth dependency chain
- Codebase: `backend/app/core/database.py` -- existing async SQLAlchemy setup
- Codebase: `backend/app/models/db_models.py` -- existing models (10 of 13 tables)
- Codebase: `backend/app/services/firestore_service.py` -- 13 collections to port
- Codebase: `backend/app/services/gemini_service.py` -- current AI integration
- Codebase: `backend/app/services/storage_service.py` -- local fallback pattern
- [FastAPI JWT Tutorial](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)
- [LM Studio OpenAI Compat](https://lmstudio.ai/docs/developer/openai-compat)
- [Alembic Async Cookbook](https://alembic.sqlalchemy.org/en/latest/cookbook.html)

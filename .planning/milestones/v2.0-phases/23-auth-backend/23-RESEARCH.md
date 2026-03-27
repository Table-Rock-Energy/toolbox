# Phase 23: Auth Backend - Research

**Researched:** 2026-03-25
**Domain:** JWT authentication, password hashing, FastAPI security middleware
**Confidence:** HIGH

## Summary

Phase 23 replaces Firebase token verification with JWT-based auth against PostgreSQL. The User model already has `password_hash`, `role`, `scope`, `tools` columns from Phase 22. The `get_db()` session dependency and async session factory already exist in `database.py`. PyJWT 2.11.0 is already installed (transitive dep of firebase-admin). pwdlib 0.3.0 + bcrypt 5.0.0 need to be installed.

The existing Depends() chain (`get_current_user` -> `require_auth` -> `require_admin`) stays intact -- only the internals of `get_current_user` change from Firebase token decode to `jwt.decode()`, and `is_user_allowed` changes from JSON allowlist to DB query. The SSE endpoint in `ghl.py` uses query-param token auth which must also switch to JWT decode. The test conftest.py uses `app.dependency_overrides[require_auth]` which will continue working unchanged.

**Primary recommendation:** Rewrite `auth.py` internals (verify function + user lookup), add `/api/auth/login` and `/api/auth/me` endpoints in a new `auth` router, add JWT settings to `config.py`, create `scripts/create_admin.py` CLI seed script. Do NOT change the Depends() chain or router wiring.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
All implementation choices are at Claude's discretion -- pure infrastructure phase. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

Key research findings to incorporate:
- PyJWT >= 2.12.0 for JWT (NOT python-jose -- abandoned)
- pwdlib[bcrypt] >= 0.2.0 for password hashing (NOT passlib -- broken with bcrypt 5.0+)
- Keep existing Depends() chain: get_current_user -> require_auth -> require_admin -- just change internals
- JWT claims: sub (email), role, exp -- same shape returned as current Firebase decoded token
- 24-hour JWT expiry (from STATE.md decisions)
- CRON_SECRET bypass preserved for scheduled jobs
- User model already has password_hash, role, scope, tools columns from Phase 22

### Claude's Discretion
All implementation choices.

### Deferred Ideas (OUT OF SCOPE)
None -- infrastructure phase.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AUTH-01 | User can log in with email and password against local PostgreSQL users table | PyJWT + pwdlib verified; User model has password_hash; get_db() session exists |
| AUTH-02 | Backend provides /api/auth/login returning JWT access token and /api/auth/me returning user profile | FastAPI official JWT pattern verified; new auth router needed |
| AUTH-03 | Backend verifies JWT tokens in require_auth/require_admin dependencies (replacing Firebase) | jwt.decode() replaces verify_firebase_token(); Depends() chain unchanged |
| AUTH-04 | Admin can create initial admin user via CLI seed script (james@tablerocktx.com) | pwdlib for hashing; async session for DB insert; standalone script |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PyJWT | 2.11.0 (installed) | JWT encode/decode | FastAPI official docs; already installed as firebase-admin dep |
| pwdlib[bcrypt] | 0.3.0 (install needed) | Password hashing | FastAPI official docs replaced passlib; works with bcrypt 5.0+ and Python 3.13 |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| bcrypt | 5.0.0 | Backend for pwdlib | Auto-installed via pwdlib[bcrypt] extra |
| SQLAlchemy[asyncio] | (already installed) | User DB queries | get_db() session dependency already in database.py |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pwdlib | passlib | passlib is unmaintained, broken with bcrypt>=5.0 |
| PyJWT | python-jose | python-jose abandoned since 2021 |
| HTTPBearer | OAuth2PasswordBearer | HTTPBearer already in use; switching to OAuth2PasswordBearer changes Swagger UI behavior but is optional |

**Installation:**
```bash
pip install "pwdlib[bcrypt]>=0.2.0"
# PyJWT already installed (2.11.0 via firebase-admin)
```

## Architecture Patterns

### New Files
```
backend/
├── app/
│   ├── api/
│   │   └── auth.py              # NEW: /api/auth/login, /api/auth/me endpoints
│   ├── core/
│   │   ├── auth.py              # MODIFY: replace Firebase internals with JWT
│   │   ├── config.py            # MODIFY: add JWT_SECRET_KEY, JWT_ALGORITHM, JWT_EXPIRE_MINUTES
│   │   └── security.py          # NEW: password hashing + JWT token helpers
├── scripts/
│   └── create_admin.py          # NEW: CLI seed script
```

### Pattern 1: JWT Token Creation and Verification
**What:** Centralized token helpers in `core/security.py`, separate from route-level auth in `core/auth.py`.
**When to use:** Every login and every authenticated request.
**Example:**
```python
# core/security.py
# Source: FastAPI official JWT tutorial
from datetime import datetime, timedelta, timezone
from pwdlib import PasswordHash
import jwt
from jwt.exceptions import InvalidTokenError
from app.core.config import settings

password_hash = PasswordHash.recommended()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return password_hash.hash(password)

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.jwt_expire_minutes))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
```

### Pattern 2: Replace verify_firebase_token with JWT decode
**What:** `get_current_user` calls `jwt.decode()` instead of Firebase Admin SDK.
**When to use:** Every request through the Depends() chain.
**Example:**
```python
# core/auth.py -- modified get_current_user
async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[dict]:
    if credentials is None:
        return None

    token = credentials.credentials

    # CRON_SECRET bypass preserved
    if settings.cron_secret and token == settings.cron_secret:
        return {"email": "cron@tablerocktx.com", "uid": "cron", "cron": True}

    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        email = payload.get("sub")
        if email is None:
            return None
    except InvalidTokenError:
        return None

    # DB lookup replaces allowlist check
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.email == email, User.is_active == True))
        user = result.scalar_one_or_none()
    if user is None:
        return None

    return {
        "email": user.email,
        "uid": user.id,
        "role": user.role,
        "scope": user.scope,
        "tools": user.tools or [],
        "first_name": user.display_name,  # or split display_name
    }
```

### Pattern 3: Login Endpoint
**What:** POST /api/auth/login accepts email+password, returns JWT.
**Example:**
```python
# api/auth.py
from pydantic import BaseModel, EmailStr

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserProfile

class UserProfile(BaseModel):
    email: str
    role: str
    scope: str
    tools: list[str]
    first_name: str | None = None
    last_name: str | None = None
    is_admin: bool = False

@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await db.execute(select(User).where(User.email == request.email.lower()))
    user = user.scalar_one_or_none()
    if user is None or not user.password_hash or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")
    # Update last_login_at
    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()
    access_token = create_access_token(data={"sub": user.email, "role": user.role})
    return LoginResponse(
        access_token=access_token,
        user=UserProfile(email=user.email, role=user.role, scope=user.scope,
                         tools=user.tools or [], is_admin=user.is_admin)
    )
```

### Pattern 4: SSE Query-Param Token Auth Migration
**What:** The GHL SSE endpoint (`/api/ghl/send/{job_id}/progress`) authenticates via `?token=` query param because EventSource cannot send headers.
**Current code:** Calls `verify_firebase_token(token)`.
**New code:** Call `jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])`.
**Location:** `backend/app/api/ghl.py` lines 398-406.

### Pattern 5: Fail-Fast Startup Check
**What:** App refuses to start in production if JWT_SECRET_KEY is missing.
**Where:** `main.py` lifespan or startup event.
**Example:**
```python
# In main.py startup
if settings.environment == "production" and not settings.jwt_secret_key:
    raise RuntimeError("JWT_SECRET_KEY must be set in production")
```

### Pattern 6: CLI Seed Script
**What:** Standalone script to create admin user with bcrypt-hashed password.
**Example:**
```python
# scripts/create_admin.py
import asyncio
import sys
from getpass import getpass

async def main():
    from app.core.database import async_session_maker
    from app.core.security import get_password_hash
    from app.models.db_models import User

    password = getpass("Enter admin password: ")
    if len(password) < 8:
        print("Password must be at least 8 characters"); sys.exit(1)

    async with async_session_maker() as session:
        existing = await session.execute(select(User).where(User.email == "james@tablerocktx.com"))
        if existing.scalar_one_or_none():
            print("Admin user already exists"); sys.exit(0)
        user = User(email="james@tablerocktx.com", password_hash=get_password_hash(password),
                     role="admin", is_admin=True, is_active=True, display_name="James")
        session.add(user); await session.commit()
        print("Admin user created")

if __name__ == "__main__":
    asyncio.run(main())
```

### Anti-Patterns to Avoid
- **Do NOT change the Depends() chain:** `require_auth` and `require_admin` signatures stay identical. Only internals change.
- **Do NOT remove allowlist functions yet:** `admin.py` imports `get_full_allowlist`, `add_allowed_user`, etc. These will be replaced in a later phase (DB-05). For now, the auth verification path uses DB, but admin CRUD still touches the JSON allowlist. This is intentional dual-write during migration.
- **Do NOT add refresh tokens:** Out of scope per STATE.md. 24-hour access token is sufficient for small internal team.
- **Do NOT use OAuth2PasswordBearer:** The codebase uses `HTTPBearer(auto_error=False)` which allows unauthenticated pass-through to `get_current_user`. Switching to `OAuth2PasswordBearer` changes this behavior and would require updating the entire Depends() chain.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Password hashing | Custom bcrypt wrapper | pwdlib `PasswordHash.recommended()` | Handles cost factor, encoding, timing-safe comparison |
| JWT creation | Manual base64 + HMAC | PyJWT `jwt.encode()` | Handles expiry claims, algorithm selection, standard compliance |
| JWT verification | Manual token parsing | PyJWT `jwt.decode()` | Validates signature, expiry, algorithm; raises typed exceptions |
| Timing-safe comparison | `==` for password check | pwdlib's `verify()` | Prevents timing attacks |

## Common Pitfalls

### Pitfall 1: JWT Token Shape Must Match Existing Code Expectations
**What goes wrong:** The `get_current_user` return dict is consumed by all route handlers as `user: dict`. Currently it contains Firebase fields like `uid`, `email`, and sometimes `name`. If the JWT version returns different keys, downstream code breaks silently.
**Why it happens:** Firebase `verify_id_token` returns `{"email": ..., "uid": ..., "name": ..., ...}`. JWT decode returns `{"sub": ..., "role": ..., "exp": ...}`.
**How to avoid:** The `get_current_user` function must transform JWT payload into the SAME dict shape: `{"email": str, "uid": str, "role": str, "scope": str, "tools": list}`. The `email` and `uid` keys are the critical ones -- used by route handlers, history scoping, and audit logging.
**Warning signs:** Tests pass (they mock `require_auth`) but production breaks on user-specific queries.

### Pitfall 2: check_user Endpoint Must Stay Unauthenticated
**What goes wrong:** `/api/admin/users/{email}/check` is intentionally unauthenticated (used by login flow to check if user exists). Adding auth breaks the login UI.
**Current code:** No `Depends(require_auth)` on `check_user`.
**How to avoid:** Do NOT add auth to this endpoint. The test `test_admin_check_no_auth_required` verifies this.

### Pitfall 3: get_current_user DB Query Creates Session Without get_db Dependency
**What goes wrong:** `get_current_user` runs on EVERY request. If it opens its own DB session (outside the `get_db` dependency), it doubles session usage per request.
**How to avoid:** Either inject `get_db` as a sub-dependency of `get_current_user`, or use `async_session_maker()` directly with proper cleanup. The FastAPI Depends system supports nested dependencies -- `get_current_user` can depend on `get_db`.
**Recommended:** Use `async_session_maker()` context manager directly inside `get_current_user` since it's a lightweight SELECT. Adding `get_db` as a Depends would change the function signature and require updating all downstream code.

### Pitfall 4: JWT_SECRET_KEY Auto-Generation in Dev
**What goes wrong:** If dev mode auto-generates a random secret on every startup, tokens from previous sessions are invalidated, breaking developer experience.
**How to avoid:** Use a stable default for development: `jwt_secret_key: str = "dev-secret-change-in-production"`. Only fail-fast in production. Document that this default is insecure.

### Pitfall 5: admin.py add_user Still Calls set_user_password (Firebase)
**What goes wrong:** `admin.py` `add_user` endpoint calls `set_user_password()` which uses Firebase Admin SDK. After JWT migration, this will fail.
**How to avoid:** Replace `set_user_password()` with a DB-based password hash set. When admin creates a user with a password, hash it with pwdlib and set `user.password_hash` in PostgreSQL. This is a necessary change in this phase.

### Pitfall 6: is_user_admin Hardcoded Fallback
**What goes wrong:** `is_user_admin()` has a hardcoded fallback: `email.lower() == "james@tablerocktx.com"`. After JWT migration, if the admin user doesn't exist in DB yet (before seed script runs), this fallback keeps working. But after full migration, this hardcode should be removed.
**How to avoid:** Keep the fallback for now. It provides a safety net during migration. Remove it in a cleanup phase after DB is fully operational.

## Code Examples

### Config Settings Addition
```python
# core/config.py -- add to Settings class
# JWT settings (local auth)
jwt_secret_key: str = "dev-only-change-in-production"
jwt_algorithm: str = "HS256"
jwt_expire_minutes: int = 1440  # 24 hours
```

### Password Hashing (pwdlib)
```python
# Source: FastAPI official JWT tutorial + PyPI pwdlib docs
from pwdlib import PasswordHash

password_hash = PasswordHash.recommended()

# Hash a password
hashed = password_hash.hash("my-password")
# Returns: "$2b$12$..." (bcrypt hash string)

# Verify a password
is_valid = password_hash.verify("my-password", hashed)
# Returns: True/False
```

### JWT Encode/Decode (PyJWT)
```python
# Source: FastAPI official JWT tutorial + PyJWT docs
import jwt
from jwt.exceptions import InvalidTokenError

# Encode
token = jwt.encode(
    {"sub": "user@example.com", "role": "admin", "exp": expire_datetime},
    "secret-key",
    algorithm="HS256"
)

# Decode (raises InvalidTokenError on bad/expired token)
payload = jwt.decode(token, "secret-key", algorithms=["HS256"])
email = payload["sub"]
```

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 7.x + pytest-asyncio |
| Config file | `backend/pytest.ini` |
| Quick run command | `cd backend && python3 -m pytest tests/ -x -q` |
| Full suite command | `cd backend && python3 -m pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AUTH-01 | Login with valid email/password returns 200 + token | integration | `pytest tests/test_auth.py::test_login_success -x` | Wave 0 |
| AUTH-01 | Login with wrong password returns 401 | integration | `pytest tests/test_auth.py::test_login_wrong_password -x` | Wave 0 |
| AUTH-01 | Login with non-existent email returns 401 | integration | `pytest tests/test_auth.py::test_login_unknown_email -x` | Wave 0 |
| AUTH-02 | GET /api/auth/me with valid token returns profile | integration | `pytest tests/test_auth.py::test_me_returns_profile -x` | Wave 0 |
| AUTH-02 | GET /api/auth/me without token returns 401 | integration | `pytest tests/test_auth.py::test_me_no_token_401 -x` | Wave 0 |
| AUTH-03 | Protected endpoint with valid JWT passes auth | integration | `pytest tests/test_auth_enforcement.py::test_authenticated_extract_succeeds -x` | Existing (already passes with mock) |
| AUTH-03 | Protected endpoint without JWT returns 401 | integration | `pytest tests/test_auth_enforcement.py::test_unauthenticated_extract_returns_401 -x` | Existing |
| AUTH-04 | Seed script creates admin user | unit | `pytest tests/test_auth.py::test_seed_admin -x` | Wave 0 |
| AUTH-03 | Fail-fast if JWT_SECRET_KEY missing in prod | unit | `pytest tests/test_auth.py::test_jwt_secret_required_in_prod -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `cd backend && python3 -m pytest tests/test_auth.py tests/test_auth_enforcement.py -x -q`
- **Per wave merge:** `cd backend && python3 -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_auth.py` -- covers AUTH-01, AUTH-02, AUTH-04 (new file)
- [ ] Test DB fixture -- either mock DB session or use test PostgreSQL
- [ ] Update `conftest.py` mock_user to include `role`, `scope`, `tools` keys (existing tests expect these from downstream handlers)

## Key Implementation Details

### Files to Modify
1. **`core/config.py`** -- Add `jwt_secret_key`, `jwt_algorithm`, `jwt_expire_minutes` settings
2. **`core/auth.py`** -- Replace `verify_firebase_token` with `jwt.decode`; replace `is_user_allowed` with DB query; keep Depends() chain; remove Firebase SDK imports; keep allowlist CRUD functions (still used by admin.py)
3. **`api/ghl.py`** lines 398-406 -- Replace Firebase token verification with JWT decode in SSE endpoint
4. **`main.py`** -- Add auth router, add JWT fail-fast startup check
5. **`api/admin.py`** -- Replace `set_user_password` Firebase call with DB password_hash update via pwdlib

### Files to Create
1. **`core/security.py`** -- `verify_password()`, `get_password_hash()`, `create_access_token()`
2. **`api/auth.py`** -- Login and /me endpoints with new auth router
3. **`scripts/create_admin.py`** -- CLI seed script
4. **`tests/test_auth.py`** -- Auth endpoint tests

### Files NOT to Change
- `conftest.py` fixtures can stay as-is (dependency_overrides pattern works with JWT auth)
- Tool routers (`extract.py`, `title.py`, etc.) -- no changes needed
- `database.py` -- already has `get_db()` and `async_session_maker`

### Return Dict Shape Contract
The `get_current_user` function MUST return dicts with these keys (used by downstream handlers):
```python
{
    "email": str,       # Used by history scoping, audit logging, admin checks
    "uid": str,         # Used by job user_id assignment
    "role": str,        # Used by require_admin (via is_user_admin)
    "scope": str,       # Available for future scope checks
    "tools": list[str], # Available for future tool-level access control
    "cron": bool,       # Only present for CRON_SECRET bypass
}
```

### is_user_admin Transition
Currently `is_user_admin` reads from JSON allowlist. After this phase, `get_current_user` returns `role` from DB. `require_admin` should check `user.get("role") == "admin" or user.get("email") == "james@tablerocktx.com"` (fallback preserved). The `is_user_admin` function in auth.py can be simplified to check the dict returned by `get_current_user` rather than re-reading the allowlist.

## Sources

### Primary (HIGH confidence)
- FastAPI official JWT tutorial: https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/ -- verified PyJWT + pwdlib patterns
- PyJWT 2.11.0 installed locally -- `pip3 show PyJWT` confirmed
- pwdlib 0.3.0 available -- `pip3 install --dry-run` confirmed
- Direct codebase analysis of `auth.py`, `config.py`, `database.py`, `db_models.py`, `admin.py`, `conftest.py`, `ghl.py`

### Secondary (MEDIUM confidence)
- STACK.md research findings on library choices (verified against FastAPI docs)
- PITFALLS.md Pitfall 3 (JWT token shape) -- verified by reading actual code

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- PyJWT already installed, pwdlib verified, FastAPI official patterns confirmed
- Architecture: HIGH -- existing Depends() chain, User model, session factory all analyzed directly
- Pitfalls: HIGH -- derived from direct code analysis of auth.py, admin.py, ghl.py, conftest.py

**Research date:** 2026-03-25
**Valid until:** 2026-04-25 (stable libraries, internal app)

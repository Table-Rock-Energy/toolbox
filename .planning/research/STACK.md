# Technology Stack

**Project:** Table Rock Tools - Security Hardening
**Researched:** 2026-03-11

## Recommended Stack

This is a security hardening milestone for an existing production app. The stack is fixed (React 19 + FastAPI + Firestore + Firebase Auth). Recommendations below are for **new libraries to add** and **patterns to adopt** within the existing stack, not stack replacements.

### Authentication & Authorization (No New Libraries)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| FastAPI `Depends()` | (built-in) | Router-level auth dependencies | Already exists in `core/auth.py` as `require_auth` and `require_admin`. Apply at router level via `APIRouter(dependencies=[Depends(require_auth)])` instead of per-endpoint. Verified: FastAPI docs confirm router-level dependencies execute before endpoint dependencies. |
| Firebase Admin SDK | >=6.2.0 (already installed) | Server-side token verification | Already in use. No changes needed to the verification logic itself -- just need to apply it consistently. |

**Confidence:** HIGH -- verified against FastAPI official documentation.

**Pattern: Router-Level Dependencies**

Apply `require_auth` at the `APIRouter()` level for tool routers, not per-endpoint. This is the FastAPI-recommended approach for applying auth to groups of related endpoints.

```python
# Before (current -- no auth on tool routers)
router = APIRouter()

@router.post("/upload")
async def upload(file: UploadFile):
    ...

# After (auth applied to all routes in this router)
router = APIRouter(dependencies=[Depends(require_auth)])

@router.post("/upload")
async def upload(file: UploadFile):
    ...
```

For admin routes, use `APIRouter(dependencies=[Depends(require_admin)])`.

The `/api/health` endpoint lives on `app` directly (not a router), so it remains unauthenticated. The `/api/admin/users/{email}/check` endpoint needs special handling -- see PITFALLS.md.

### CORS Configuration (No New Libraries)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `CORSMiddleware` | (built-in Starlette) | CORS headers | Already in use, but misconfigured. |

**Confidence:** HIGH -- verified against FastAPI official CORS documentation.

**Critical Finding:** The current config has `allow_origins=["*"]` with `allow_credentials=True`. Per the CORS spec and confirmed in FastAPI docs: "None of `allow_origins`, `allow_methods` and `allow_headers` can be set to `['*']` if `allow_credentials` is set to `True`." This is not just insecure -- it is spec-invalid and browsers will reject credential-bearing requests.

**Recommended Configuration:**

```python
# Add to Settings in config.py
cors_origins: list[str] = ["https://tools.tablerocktx.com"]
environment: str = "development"

# In main.py
origins = settings.cors_origins
if settings.environment == "development":
    origins = ["http://localhost:5173", "http://localhost:8000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
```

### Encryption (No New Libraries)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `cryptography` (Fernet) | >=42.0.0 (already installed) | Symmetric encryption for API keys in Firestore | Already in use via `shared/encryption.py`. Pattern is sound (Fernet with `enc:` prefix for migration). |

**Confidence:** HIGH -- Fernet is the standard symmetric encryption choice for Python. Already implemented correctly.

**Required Change:** Fail at startup if `ENCRYPTION_KEY` is not set in production. The current fallback-to-plaintext pattern silently stores secrets unencrypted.

```python
# In Settings class or startup hook
@app.on_event("startup")  # or lifespan
async def startup_event():
    if settings.environment == "production" and not settings.encryption_key:
        raise RuntimeError(
            "ENCRYPTION_KEY is required in production. "
            "Generate one with: python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
        )
```

### Firestore Subcollections (No New Libraries)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `google-cloud-firestore` | >=2.14.0 (already installed) | Subcollection pattern for revenue rows | Revenue statements currently embed all rows in a single document. Firestore has a 1MB document size limit. Move rows to a subcollection: `revenue_statements/{id}/rows/{row_id}`. |

**Confidence:** HIGH -- subcollections are a core Firestore feature. This is the standard pattern for unbounded lists.

**Pattern:**

```python
# Before: single document with embedded rows array
doc_ref = db.collection("revenue_statements").document(stmt_id)
await doc_ref.set({"rows": [...hundreds of rows...], "metadata": {...}})

# After: metadata in parent doc, rows in subcollection
doc_ref = db.collection("revenue_statements").document(stmt_id)
await doc_ref.set({"metadata": {...}, "row_count": len(rows)})

# Batch write rows to subcollection (commit every 500 -- Firestore limit)
batch = db.batch()
rows_ref = doc_ref.collection("rows")
for i, row in enumerate(rows):
    batch.set(rows_ref.document(), row)
    if (i + 1) % 500 == 0:
        await batch.commit()
        batch = db.batch()
if i % 500 != 499:
    await batch.commit()
```

### Testing (Existing Libraries, New Patterns)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| `pytest` | >=7.4.0 (already installed) | Test runner | Standard Python test framework. Already a dependency. |
| `pytest-asyncio` | >=0.23.0 (already installed) | Async test support | Required for testing async FastAPI endpoints. Already a dependency. |
| `httpx` | >=0.26.0 (already installed) | Test HTTP client | FastAPI's `TestClient` is built on httpx. Already a dependency. |

**Confidence:** HIGH -- verified against FastAPI official testing documentation.

**Auth Mocking Pattern (verified from FastAPI docs):**

Use `app.dependency_overrides` to mock auth dependencies in tests. This is the FastAPI-recommended approach -- no additional mocking libraries needed.

```python
# conftest.py
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.auth import require_auth, require_admin

MOCK_USER = {"uid": "test-uid", "email": "test@tablerocktx.com"}
MOCK_ADMIN = {"uid": "admin-uid", "email": "james@tablerocktx.com"}

def mock_require_auth():
    return MOCK_USER

def mock_require_admin():
    return MOCK_ADMIN

@pytest.fixture
def client():
    """Test client with auth mocked to return a regular user."""
    app.dependency_overrides[require_auth] = mock_require_auth
    with TestClient(app) as c:
        yield c
    app.dependency_overrides = {}

@pytest.fixture
def admin_client():
    """Test client with auth mocked to return an admin user."""
    app.dependency_overrides[require_auth] = mock_require_auth
    app.dependency_overrides[require_admin] = mock_require_admin
    with TestClient(app) as c:
        yield c
    app.dependency_overrides = {}

@pytest.fixture
def unauthed_client():
    """Test client with NO auth override -- tests 401 responses."""
    # Don't override -- let the real require_auth run and reject
    with TestClient(app) as c:
        yield c
```

**Note:** Test functions use normal `def` (not `async def`) with `TestClient`. The `TestClient` handles async internally. Only use `async def` tests with `@pytest.mark.asyncio` when testing service-layer functions directly.

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Auth middleware | Router-level `Depends()` | Global middleware via `BaseHTTPMiddleware` | Middleware runs on every request including static files and health checks. Router dependencies are scoped to specific routes and integrate with FastAPI's dependency injection (return values, error handling). |
| Auth middleware | Router-level `Depends()` | Per-endpoint `Depends(require_auth)` on each function | Works but error-prone -- easy to forget on new endpoints. Router-level ensures all endpoints in a tool router are protected by default. |
| CORS | Explicit origin list from config | `allow_origin_regex` | Regex is harder to audit and easier to misconfigure. An explicit list is clearer for a single-domain internal app. |
| Secret management | Fernet encryption + startup validation | Google Secret Manager | Overkill for this use case. The app only encrypts GHL API keys in Firestore. Fernet with a single env var is simpler and already implemented. Secret Manager is better when you have many secrets or need rotation. |
| Secret management | Fernet (existing) | `python-jose` / JWT-based encryption | Wrong tool. JWTs are for tokens, not at-rest encryption. Fernet is purpose-built for symmetric encrypt/decrypt. |
| Testing | `TestClient` + `dependency_overrides` | `unittest.mock.patch` on Firebase | Fragile -- patches internal implementation. `dependency_overrides` is FastAPI's official mechanism and survives refactors. |
| Testing | `pytest` + `httpx` sync TestClient | `pytest-asyncio` + `httpx.AsyncClient` | Adds complexity. FastAPI docs recommend sync TestClient for API tests. Reserve async tests for service-layer unit tests only. |
| Firestore structure | Subcollections for revenue rows | Separate top-level collection with foreign key | Subcollections co-locate related data, simplify security rules, and allow deleting a statement to cascade-delete its rows. Top-level collections require manual cleanup. |

## No New Dependencies Required

This milestone requires zero new pip or npm packages. Everything needed is already installed:

- `fastapi` (router dependencies, CORS middleware)
- `cryptography` (Fernet encryption)
- `google-cloud-firestore` (subcollections)
- `pytest` + `pytest-asyncio` + `httpx` (testing)
- `firebase-admin` (token verification)

## Configuration Changes Required

Add to `Settings` class in `backend/app/core/config.py`:

```python
# CORS
cors_origins: list[str] = ["https://tools.tablerocktx.com"]
environment: str = "development"
```

Add `ENVIRONMENT` and `CORS_ORIGINS` env vars to Cloud Run deployment config.

## Sources

- FastAPI Router Dependencies: https://fastapi.tiangolo.com/tutorial/bigger-applications/ (verified via WebFetch)
- FastAPI CORS: https://fastapi.tiangolo.com/tutorial/cors/ (verified via WebFetch -- confirms wildcard + credentials is invalid)
- FastAPI Testing: https://fastapi.tiangolo.com/tutorial/testing/ (verified via WebFetch)
- FastAPI Dependency Overrides: https://fastapi.tiangolo.com/advanced/testing-dependencies/ (verified via WebFetch)
- Existing codebase: `backend/app/core/auth.py`, `backend/app/main.py`, `backend/app/services/shared/encryption.py`

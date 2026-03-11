# Architecture Patterns

**Domain:** Security hardening, Firestore restructuring, and test infrastructure for an existing FastAPI + React + Firestore internal toolbox
**Researched:** 2026-03-11

## Recommended Architecture

The existing tool-per-module monolith is well-structured. Security hardening layers on top of it without restructuring -- the key is applying existing auth dependencies (`require_auth`, `require_admin`) consistently, tightening CORS at the middleware level, and restructuring one Firestore collection. No new services or layers are needed.

### Component Boundaries

| Component | Responsibility | Communicates With | Changes Needed |
|-----------|---------------|-------------------|----------------|
| **CORS Middleware** (`main.py`) | Origin validation | Inbound HTTP requests | Replace `allow_origins=["*"]` with config-driven allowlist |
| **Auth Dependencies** (`core/auth.py`) | Token verification + allowlist check | All API routers, Firestore (allowlist) | No code changes -- already correct. Just needs to be wired into unprotected routers |
| **Tool Routers** (`api/*.py`) | HTTP handling per tool | Service layer, auth dependencies | Add `Depends(require_auth)` to all unprotected endpoints |
| **Admin Router** (`api/admin.py`) | User management, settings, profile images | Auth dependencies, Firestore | Add `Depends(require_admin)` to unprotected admin endpoints (GET users, settings, profile, preferences) |
| **Firestore Service** (`services/firestore_service.py`) | All Firestore CRUD | Google Firestore | Restructure `revenue_statements` to use subcollection for rows; add encryption for config docs |
| **Config** (`core/config.py`) | Environment + settings | All layers | Add `cors_origins`, `encryption_key` as required field |
| **Encryption** (`services/shared/encryption.py`) | Fernet encrypt/decrypt | Admin settings persistence | Require `ENCRYPTION_KEY` at startup; encrypt sensitive config before Firestore write |
| **Test Suite** (`tests/`) | Verification | All backend components via httpx `TestClient` | New directory; test auth enforcement, parsing pipelines |

### Data Flow

**Current auth flow (working but inconsistently applied):**
```
Browser -> ApiClient (injects Firebase ID token)
       -> FastAPI middleware (CORS - currently allows *)
       -> Router endpoint
       -> [MISSING on most routes] Depends(require_auth) -> verify_firebase_token()
       -> Service layer processes request
       -> Firestore/GCS persistence
       -> Response
```

**Target auth flow (after hardening):**
```
Browser -> ApiClient (injects Firebase ID token)
       -> FastAPI CORS middleware (explicit origin allowlist)
       -> Router endpoint with Depends(require_auth) on ALL tool routes
       -> verify_firebase_token() -> allowlist check -> decoded user dict
       -> Service layer processes request (user identity from token, not headers)
       -> Firestore/GCS persistence
       -> Response
```

**Revenue Firestore restructuring data flow:**
```
Current:  revenue_statements/{id} = { ...metadata, rows: [{...}, {...}, ...] }
          (rows embedded in document -- hits 1MB limit on large statements)

Target:   revenue_statements/{id} = { ...metadata, total_rows: N }
          revenue_statements/{id}/rows/{row_id} = { ...row_data }
          (rows in subcollection -- no document size limit, cheaper reads when only metadata needed)
```

## Patterns to Follow

### Pattern 1: Router-Level Auth via Dependencies (existing pattern)
**What:** FastAPI's `Depends()` for auth enforcement at the router or endpoint level.
**When:** Every endpoint except `/api/health`.
**Why this approach:** The `require_auth` and `require_admin` dependencies already exist and work. The GHL router already uses this pattern on all its endpoints. Just replicate across other routers.

Two strategies, use the simpler one:

**Option A -- Per-endpoint (current GHL pattern, recommended):**
```python
@router.post("/upload")
async def upload(file: UploadFile, user: dict = Depends(require_auth)):
    # user is verified, contains email, uid, etc.
```

**Option B -- Router-level default dependency:**
```python
router = APIRouter(dependencies=[Depends(require_auth)])
```

Use Option A because it makes auth explicit at each endpoint, and some routers mix auth levels (e.g., ETL has both `require_auth` and `require_admin` endpoints). Router-level dependencies would still need per-endpoint overrides.

### Pattern 2: Config-Driven CORS
**What:** Move CORS origins from hardcoded `["*"]` to `Settings` with environment-aware defaults.
**When:** Startup, in `main.py`.

```python
# config.py
cors_origins: list[str] = ["http://localhost:5173"]  # dev default

# In production, set CORS_ORIGINS=https://tools.tablerocktx.com

# main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
```

### Pattern 3: Firestore Subcollection Migration (Revenue Rows)
**What:** Move `rows` array out of parent document into a subcollection.
**When:** During `save_revenue_statement` and `get_revenue_statements`.

Key constraint: This must be backwards-compatible. Read functions should handle both old (embedded rows) and new (subcollection) formats during migration.

```python
# Write path (new): save rows to subcollection
async def save_revenue_statement(job_id: str, statement_data: dict) -> dict:
    rows = statement_data.pop("rows", [])
    # Save parent doc WITHOUT rows
    await doc_ref.set(statement_doc)
    # Save rows to subcollection
    batch = db.batch()
    for i, row in enumerate(rows):
        row_ref = doc_ref.collection("rows").document(str(i))
        batch.set(row_ref, row)
        # ... commit every 500

# Read path (backwards-compatible):
async def get_revenue_statements(job_id: str) -> list[dict]:
    for doc in docs:
        data = doc.to_dict()
        if "rows" not in data or not data["rows"]:
            # New format: fetch from subcollection
            row_docs = await doc.reference.collection("rows").get()
            data["rows"] = [r.to_dict() for r in row_docs]
```

### Pattern 4: Startup Validation for Required Secrets
**What:** Fail fast if `ENCRYPTION_KEY` is missing.
**When:** App startup in `main.py` or via Pydantic validator.

```python
# config.py -- make encryption_key required in production
@property
def require_encryption(self) -> bool:
    return self.environment == "production" or bool(self.encryption_key)

# main.py startup
if not settings.encryption_key:
    if settings.environment == "production":
        raise RuntimeError("ENCRYPTION_KEY is required in production")
    logger.warning("ENCRYPTION_KEY not set -- sensitive data will not be encrypted")
```

### Pattern 5: Test Infrastructure with httpx AsyncClient
**What:** pytest + httpx for testing FastAPI endpoints with auth mocking.
**When:** All backend tests.

```python
# conftest.py
@pytest.fixture
def app():
    from app.main import app
    return app

@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

@pytest.fixture
def auth_headers():
    """Mock auth headers. Override require_auth dependency in tests."""
    return {"Authorization": "Bearer test-token"}

@pytest.fixture(autouse=True)
def override_auth(app):
    """Replace require_auth with a mock that returns a test user."""
    async def mock_require_auth():
        return {"uid": "test-uid", "email": "test@tablerocktx.com"}
    app.dependency_overrides[require_auth] = mock_require_auth
    yield
    app.dependency_overrides.clear()
```

## Anti-Patterns to Avoid

### Anti-Pattern 1: Global Auth Middleware Instead of Dependencies
**What:** Adding a middleware that checks auth on every request and filtering by path prefix.
**Why bad:** FastAPI's dependency injection is the idiomatic approach. Middleware-based auth requires path matching regex, is harder to test, doesn't integrate with OpenAPI docs, and can't vary auth level per endpoint.
**Instead:** Use `Depends(require_auth)` per endpoint or `dependencies=[...]` per router.

### Anti-Pattern 2: Migrating All Firestore Documents at Once
**What:** Running a one-time migration script to move all revenue rows to subcollections.
**Why bad:** Risk of data loss, downtime, and partial migration failures. Revenue data may span many documents.
**Instead:** Dual-read pattern (check for embedded rows, fall back to subcollection). New writes always use subcollection. Optionally run a background migration later, but it is not required for correctness.

### Anti-Pattern 3: Trusting x-user-email Headers for Identity
**What:** Reading user identity from request headers set by the frontend.
**Why bad:** These headers are trivially spoofable. Any HTTP client can set `x-user-email: admin@company.com`.
**Instead:** Extract user identity exclusively from the verified Firebase token (already available in the `user` dict returned by `require_auth`).

### Anti-Pattern 4: Testing Against Live Firestore
**What:** Running tests that read/write to the real Firestore database.
**Why bad:** Flaky tests, test pollution, cost, and risk of corrupting production data.
**Instead:** Mock Firestore calls in unit tests. For integration tests, use Firestore emulator or mock the `get_firestore_client()` function.

## Suggested Build Order

Build order is constrained by dependencies between components. The critical path is:

```
Phase 1: Auth enforcement (no dependencies, highest security impact)
  |- Add require_auth to all unprotected tool routers
  |- Add require_admin to unprotected admin endpoints
  |- Replace x-user-email header usage with token-derived identity
  |- Lock down CORS origins in config

Phase 2: Encryption + config hardening (depends on auth being solid)
  |- Require ENCRYPTION_KEY at startup
  |- Encrypt sensitive app_config docs before Firestore write
  |- Encrypt admin/app settings

Phase 3: Firestore restructuring (independent of auth, but lower priority)
  |- Revenue rows subcollection migration (dual-read pattern)
  |- Fix ETL N+1 with batch retrieval
  |- Define composite indexes (remove client-side sort fallbacks)

Phase 4: Test infrastructure (should verify phases 1-3)
  |- Set up pytest + httpx + conftest with auth mocking
  |- Auth enforcement smoke tests (verify 401 without token on every route)
  |- Parsing pipeline regression tests (Extract, Revenue parsers)
```

**Phase ordering rationale:**
- Auth enforcement first because it is the highest-severity security gap and has zero dependencies on other changes.
- CORS lockdown ships with auth because both are `main.py` / config changes.
- Encryption second because it depends on the auth model being stable (encrypted config is read during auth flows).
- Firestore restructuring third because it is a data modeling concern independent of security, and the dual-read pattern means no migration downtime.
- Tests last because they should verify the hardened system, not the pre-hardened one. Also, auth mocking fixtures need to know the final auth dependency structure.

## Unprotected Endpoints Inventory

Routers with NO auth on any endpoint (all routes exposed):
- **extract.py** -- upload, export, parse-entries, enrich (7 endpoints)
- **title.py** -- upload, export, preview, enrich, validate (7 endpoints)
- **proration.py** -- all RRC + upload + export (14 endpoints)
- **revenue.py** -- upload, export, summary, validate, debug (7 endpoints)
- **ghl_prep.py** -- upload, export (4 endpoints)
- **history.py** -- jobs list, delete, detail, entries (5 endpoints)
- **ai_validation.py** -- status, validate (2 endpoints)

Routers with PARTIAL auth:
- **admin.py** -- POST/PUT/DELETE users + settings use `require_admin`, but GET users, GET settings, profile image upload/get, preferences have NO auth (8 unprotected of 12)
- **enrichment.py** -- config update uses `require_admin`, but status/get-config/lookup have no auth (3 unprotected of 5)
- **etl.py** -- entity corrections + relationships use `require_admin`, but health/status/search/detail/relationships-get/ownership have no auth (6 unprotected of 8)

Router with FULL auth:
- **ghl.py** -- all endpoints use `require_auth` (correct)

**Total: ~63 unprotected endpoints need `require_auth` or `require_admin` added.**

## Scalability Considerations

| Concern | Current (small team) | At scale | Notes |
|---------|---------------------|----------|-------|
| Auth verification | Firebase token verify per request | Same -- Firebase handles scale | Token caching possible but unnecessary at current scale |
| Revenue doc size | Rows embedded in document | Hits 1MB Firestore limit | Subcollection migration fixes this |
| Firestore indexes | Client-side sort fallback | Slower queries, higher read costs | Define composite indexes to eliminate fallbacks |
| Test suite | None | Regressions go undetected | Start with smoke tests + parser regression tests |

## Sources

- Existing codebase analysis: `backend/app/core/auth.py`, `backend/app/main.py`, `backend/app/services/firestore_service.py`, all files in `backend/app/api/`
- FastAPI dependency injection: established pattern already used in `ghl.py` router
- Firestore subcollection pattern: standard Firestore data modeling for unbounded arrays
- Firestore 1MB document size limit: Firestore documented constraint

---

*Architecture analysis: 2026-03-11*

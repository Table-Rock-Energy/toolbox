# Phase 3: Backend Test Suite - Research

**Researched:** 2026-03-11
**Domain:** pytest + httpx async testing for FastAPI backend
**Confidence:** HIGH

## Summary

Phase 3 builds on an existing, working test foundation. The project already has 17 passing tests across two modules (`test_auth_enforcement.py` and `test_cors.py`) with a fully functional `conftest.py` providing `authenticated_client`, `unauthenticated_client`, and `mock_user` fixtures using `app.dependency_overrides[require_auth]`. The pytest config uses `asyncio_mode = auto` and all dependencies (pytest 7.4+, pytest-asyncio 0.23+, httpx 0.26+) are already in `requirements.txt`.

The remaining work is: (1) expand auth smoke tests to cover ALL protected routes (currently 9 of ~40+ endpoints tested), including the GHL/admin routers which use per-endpoint `Depends(require_auth)` instead of router-level auth, (2) add parser regression tests for the Extract `parse_exhibit_a()` and Revenue `parse_energylink_statement()` functions using inline text fixtures, and (3) ensure everything runs in CI without GCP credentials by mocking Firestore calls in upload-path tests.

**Primary recommendation:** Use the existing conftest.py pattern unchanged. Add parser unit tests that call service functions directly (not through HTTP endpoints) to avoid needing file upload mocking and Firestore mocking. Auth smoke tests should hit lightweight endpoints (health checks, GET routes) per router to verify 401/non-401 status.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| TEST-01 | pytest + httpx test infrastructure with Firebase auth mocking via `app.dependency_overrides[require_auth]` pattern, reusable test client fixture | Already implemented in `backend/tests/conftest.py` -- existing fixtures work correctly. Verify and document, no new code needed for infrastructure. |
| TEST-02 | Auth smoke tests verify every protected route returns 401 without token and 200/appropriate status with valid token | Existing `test_auth_enforcement.py` covers 9 routes. Need to add GHL per-endpoint auth routes (`/api/ghl/connections`, `/api/ghl/contacts/upsert`, etc.) and admin protected routes (`/api/admin/users` POST/PUT/DELETE). Also verify authenticated requests succeed for each router. |
| TEST-03 | Parsing regression tests with representative test fixtures for at least one revenue parser and one extract parser, asserting expected output structure | Call `parse_exhibit_a()` and `parse_energylink_statement()` directly with inline text strings. No PDF files needed -- both parsers accept `str` input. Assert on `PartyEntry` and `RevenueStatement` model structure. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | >=7.4.0 | Test runner | Already installed, configured in `pytest.ini` |
| pytest-asyncio | >=0.23.0 | Async test support | Already installed, `asyncio_mode = auto` configured |
| httpx | >=0.26.0 | Async HTTP test client | Already installed, used in `conftest.py` via `ASGITransport` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| unittest.mock | stdlib | Patching Firestore/Firebase | When testing upload endpoints that call `persist_job_result` |

### Alternatives Considered
None -- the stack is already established and working. No changes needed.

**Installation:**
```bash
# Already in requirements.txt -- no new packages needed
```

## Architecture Patterns

### Current Test Structure (keep as-is)
```
backend/
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Shared fixtures (auth mock, clients)
│   ├── test_auth_enforcement.py # AUTH-01 smoke tests (expand for TEST-02)
│   ├── test_cors.py             # SEC-01 CORS tests (complete)
│   ├── test_extract_parser.py   # NEW: Extract parser regression (TEST-03)
│   └── test_revenue_parser.py   # NEW: Revenue parser regression (TEST-03)
├── pytest.ini                   # asyncio_mode = auto, testpaths = tests
```

### Pattern 1: Auth Smoke Test (existing, proven)
**What:** Hit one endpoint per router, verify 401 without auth, non-401 with auth
**When to use:** For every protected router/endpoint
**Example:**
```python
# Source: backend/tests/test_auth_enforcement.py (existing pattern)
@pytest.mark.asyncio
async def test_unauthenticated_ghl_connections_returns_401(unauthenticated_client):
    response = await unauthenticated_client.get("/api/ghl/connections")
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_authenticated_ghl_connections_succeeds(authenticated_client):
    response = await authenticated_client.get("/api/ghl/connections")
    assert response.status_code != 401
```

### Pattern 2: Parser Unit Test (direct function call)
**What:** Call parser functions directly with inline text, assert output model structure
**When to use:** For parser regression tests (TEST-03)
**Example:**
```python
# Direct parser call -- no HTTP, no file upload, no Firestore mocking needed
from app.services.extract.parser import parse_exhibit_a
from app.models.extract import PartyEntry, EntityType

def test_parse_exhibit_a_basic_entry():
    text = """1. JOHN DOE
123 Main Street
Midland, TX 79701"""
    entries = parse_exhibit_a(text)
    assert len(entries) >= 1
    entry = entries[0]
    assert isinstance(entry, PartyEntry)
    assert entry.entry_number == "1"
    assert entry.primary_name  # Non-empty
    assert entry.entity_type == EntityType.INDIVIDUAL
```

### Pattern 3: Authenticated Client Fixture (existing)
**What:** `app.dependency_overrides[require_auth]` returns mock user dict
**When to use:** All authenticated endpoint tests
**Example:**
```python
# Source: backend/tests/conftest.py (existing, working)
@pytest_asyncio.fixture
async def authenticated_client(mock_user):
    async def _override_auth():
        return mock_user
    app.dependency_overrides[require_auth] = _override_auth
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client
    app.dependency_overrides.clear()
```

### Anti-Patterns to Avoid
- **Do NOT upload real PDF files for parser tests:** Both `parse_exhibit_a(text)` and `parse_energylink_statement(text, filename)` accept plain strings. Testing through the HTTP upload endpoint requires mocking PDF extraction, Firestore persistence, and file validation -- unnecessary complexity.
- **Do NOT mock individual Firestore calls for auth smoke tests:** Use lightweight GET endpoints (health checks, status endpoints) that don't trigger Firestore writes. The authenticated client's `dependency_overrides` handles all auth.
- **Do NOT add new conftest.py fixtures unless necessary:** The existing `authenticated_client`, `unauthenticated_client`, and `mock_user` fixtures cover all TEST-01 and TEST-02 needs.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Auth mocking | Custom middleware mock | `app.dependency_overrides[require_auth]` | Already working in conftest.py, FastAPI's official pattern |
| HTTP test client | requests + threading | `httpx.AsyncClient(transport=ASGITransport(app=app))` | In-process, no port binding, already set up |
| Test fixtures for parsers | PDF file fixtures | Inline text strings | Parsers accept `str`, not bytes; avoids binary test data |
| Firestore mocking for parser tests | Mock Firestore client | Call parser functions directly (not via HTTP) | Parsers are pure functions, no side effects |

## Common Pitfalls

### Pitfall 1: Testing parsers through HTTP endpoints
**What goes wrong:** Upload endpoint involves file validation, PDF text extraction, Firestore job persistence, format detection -- all need mocking.
**Why it happens:** Instinct to test "end to end" through the API.
**How to avoid:** Call `parse_exhibit_a(text)` and `parse_energylink_statement(text, filename)` directly. They are pure functions that accept strings and return Pydantic models.
**Warning signs:** Test needs 5+ mocks to set up.

### Pitfall 2: GHL/Admin auth is per-endpoint, not router-level
**What goes wrong:** Assuming GHL and admin routes are unprotected because `main.py` doesn't add `dependencies=[Depends(require_auth)]` to their `include_router()` calls.
**Why it happens:** GHL uses per-endpoint `Depends(require_auth)` because the SSE progress endpoint needs query-param token auth. Admin uses `Depends(require_admin)` on write endpoints and leaves read/check endpoints open.
**How to avoid:** Check each GHL/admin endpoint individually. Some GHL endpoints (`/daily-limit`, `/send/{job_id}/progress`) do NOT require auth. Admin endpoints: `/users/{email}/check`, `/options`, `/settings/*` GET, `/profile-image/{user_id}` do NOT require auth.
**Warning signs:** 401 test fails on an endpoint that's intentionally unauthenticated.

### Pitfall 3: Authenticated test returns 500 instead of 200
**What goes wrong:** Authenticated smoke test expects non-401 but gets 500 because the endpoint tries to call Firestore/GCS.
**Why it happens:** Some endpoints (like POST upload) trigger side effects even with auth mocked.
**How to avoid:** For auth smoke tests, assert `response.status_code != 401` (not `== 200`). Use GET endpoints where possible. The existing tests already follow this pattern correctly.
**Warning signs:** Test asserts `== 200` on an endpoint that requires a request body or calls external services.

### Pitfall 4: CI fails on import of firebase_admin or google-cloud
**What goes wrong:** Importing `app.main` triggers Firebase/GCS initialization code.
**Why it happens:** Lazy initialization with fallback -- the app gracefully handles missing credentials.
**How to avoid:** The existing tests already work without GCP credentials (17 pass currently). The app logs warnings but does not fail. No special CI environment setup needed.
**Warning signs:** `ImportError` or credential errors during test collection.

## Code Examples

### Extract Parser -- Inline Text Fixture
```python
# Verified: parse_exhibit_a accepts str, returns list[PartyEntry]
# Source: backend/app/services/extract/parser.py line 37

EXHIBIT_A_SAMPLE = """1. JOHN SMITH DOE
123 Main Street
Midland, TX 79701

2. ACME ENERGY, LLC
456 Oak Avenue, Suite 200
Dallas, TX 75201

3. THE DOE FAMILY TRUST
c/o Jane Doe, Trustee
789 Elm Drive
Houston, TX 77002

U1. UNKNOWN HEIRS OF JAMES DOE
ADDRESS UNKNOWN"""

def test_parse_exhibit_a_multiple_entries():
    from app.services.extract.parser import parse_exhibit_a
    entries = parse_exhibit_a(EXHIBIT_A_SAMPLE)
    assert len(entries) >= 3  # At least the named entries
    # Verify structure
    for entry in entries:
        assert entry.entry_number
        assert entry.primary_name
        assert entry.entity_type  # Always has a value (default: INDIVIDUAL)
```

### Revenue Parser -- Inline Text Fixture
```python
# Verified: parse_energylink_statement accepts (str, str), returns RevenueStatement
# Source: backend/app/services/revenue/energylink_parser.py line 10

ENERGYLINK_SAMPLE = """Check Date: 2/24/2025
Check Number: 005468
Owner Code: TAB001
Owner Name: TABLE ROCK ENERGY, LLC

0012345678
SMITH WELL #1
DAWSON, TX

Dec 2024
101
RI
0.000
1500.000
65.50
98250.00
0.00125000
1.875
122.81"""

def test_parse_energylink_statement():
    from app.services.revenue.energylink_parser import parse_energylink_statement
    from app.models.revenue import StatementFormat
    stmt = parse_energylink_statement(ENERGYLINK_SAMPLE, "test.pdf")
    assert stmt.format == StatementFormat.ENERGYLINK
    assert stmt.check_number == "005468"
    assert stmt.owner_name == "TABLE ROCK ENERGY, LLC"
    assert len(stmt.rows) >= 1
    row = stmt.rows[0]
    assert row.property_number == "0012345678"
    assert row.product_code == "101"
    assert row.interest_type == "RI"
```

### Complete Auth Coverage Map

Routers with **router-level** auth (all endpoints protected via `dependencies=[Depends(require_auth)]` in main.py):
- `/api/extract/*` -- test via GET `/api/extract/health`
- `/api/title/*` -- test via GET `/api/title/health`
- `/api/proration/*` -- test via GET `/api/proration/rrc/status`
- `/api/revenue/*` -- test via POST `/api/revenue/upload`
- `/api/ghl-prep/*` -- test via POST `/api/ghl-prep/upload`
- `/api/history/*` -- test via GET `/api/history/jobs`
- `/api/ai/*` -- test via GET `/api/ai/status`
- `/api/enrichment/*` -- test via GET `/api/enrichment/status`
- `/api/etl/*` -- test via GET `/api/etl/health`

Routers with **per-endpoint** auth (need individual testing):
- `/api/ghl/connections` GET -- `Depends(require_auth)` -- test 401/non-401
- `/api/ghl/contacts/upsert` POST -- `Depends(require_auth)` -- test 401
- `/api/ghl/contacts/bulk-send` POST -- `Depends(require_auth)` -- test 401
- `/api/ghl/send/{job_id}/cancel` POST -- `Depends(require_auth)` -- test 401
- `/api/ghl/send/{job_id}/status` GET -- `Depends(require_auth)` -- test 401
- `/api/ghl/connections/{id}/quick-check` POST -- `Depends(require_auth)` -- test 401
- `/api/admin/users` POST -- `Depends(require_admin)` -- test 401
- `/api/admin/users/{email}` PUT/DELETE -- `Depends(require_admin)` -- test 401

Endpoints intentionally **NOT protected** (verify they remain accessible):
- `/api/health` -- global health check
- `/api/admin/users/{email}/check` -- user check (pre-login)
- `/api/admin/options` -- dropdown options
- `/api/admin/settings/*` GET -- read-only settings
- `/api/ghl/daily-limit` -- public rate limit info
- `/api/ghl/send/{job_id}/progress` -- SSE with query-param token (custom auth)

### CI Workflow Addition
```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.13'
      - run: pip install -r backend/requirements.txt
      - run: cd backend && python -m pytest -v
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `@pytest.fixture` for async | `@pytest_asyncio.fixture` | pytest-asyncio 0.23+ | Required for async fixtures with `asyncio_mode=auto` |
| `httpx.AsyncClient(app=app)` | `AsyncClient(transport=ASGITransport(app=app))` | httpx 0.26+ | `app` param deprecated, use `transport` |
| `on_event("startup")` | lifespan context manager | FastAPI 0.109+ | Deprecation warnings appear but functionality works |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-asyncio 1.3.0 (installed) |
| Config file | `backend/pytest.ini` (asyncio_mode = auto) |
| Quick run command | `cd backend && python -m pytest -v` |
| Full suite command | `cd backend && python -m pytest -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TEST-01 | Auth mocking infrastructure works | unit | `cd backend && python -m pytest tests/conftest.py -v` | Yes -- `conftest.py` |
| TEST-02 | Every protected route returns 401 w/o token | smoke | `cd backend && python -m pytest tests/test_auth_enforcement.py -v` | Yes -- needs expansion |
| TEST-03a | Extract parser regression | unit | `cd backend && python -m pytest tests/test_extract_parser.py -v` | No -- Wave 0 |
| TEST-03b | Revenue parser regression | unit | `cd backend && python -m pytest tests/test_revenue_parser.py -v` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `cd backend && python -m pytest -v -x`
- **Per wave merge:** `cd backend && python -m pytest -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_extract_parser.py` -- covers TEST-03a (extract parser regression)
- [ ] `tests/test_revenue_parser.py` -- covers TEST-03b (revenue parser regression)
- [ ] `.github/workflows/test.yml` -- CI test workflow (TEST success criteria #4)

## Open Questions

1. **GHL SSE progress endpoint auth**
   - What we know: `/api/ghl/send/{job_id}/progress` uses query-param token (`?token=...`) instead of Bearer header because EventSource API doesn't support custom headers. It has custom auth logic inside the handler.
   - What's unclear: Whether a smoke test should verify the query-param auth path or just document it as intentionally different.
   - Recommendation: Add a comment in the auth test file documenting this endpoint's auth pattern. Testing it would require understanding the custom token verification logic, which is out of scope for a smoke test.

2. **Test data for parser regression tests**
   - What we know: Both parsers accept plain text strings. Inline fixtures are sufficient.
   - What's unclear: Whether the sample text will produce deterministic output (parsers use regex, edge cases may vary).
   - Recommendation: Use simple, unambiguous text samples. Assert on structural properties (field presence, type, count) rather than exact string values. Run the parsers manually first to establish baseline expected values.

## Sources

### Primary (HIGH confidence)
- `backend/tests/conftest.py` -- existing fixture implementation (verified working)
- `backend/tests/test_auth_enforcement.py` -- existing auth test pattern (17 tests pass)
- `backend/app/main.py` -- router-level auth configuration (lines 72-82)
- `backend/app/core/auth.py` -- `require_auth` dependency definition (line 343-356)
- `backend/app/services/extract/parser.py` -- `parse_exhibit_a(text: str)` signature (line 37)
- `backend/app/services/revenue/energylink_parser.py` -- `parse_energylink_statement(text: str, filename: str)` signature (line 10)
- `backend/app/api/ghl.py` -- per-endpoint auth decorators (verified via grep)
- `backend/app/api/admin.py` -- per-endpoint admin auth (verified via grep)

### Secondary (MEDIUM confidence)
- `.claude/skills/pytest/references/mocking.md` -- project-specific mocking patterns
- `.claude/skills/pytest/references/fixtures.md` -- project-specific fixture patterns

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- already installed and working, 17 tests pass
- Architecture: HIGH -- existing pattern is proven, just needs expansion
- Pitfalls: HIGH -- identified from reading actual code and existing test patterns

**Research date:** 2026-03-11
**Valid until:** 2026-04-11 (stable, no version changes expected)

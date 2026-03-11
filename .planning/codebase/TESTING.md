# Testing Patterns

**Analysis Date:** 2026-03-10

## Test Framework

**Runner:**
- pytest >= 7.4.0 (backend only)
- pytest-asyncio >= 0.23.0 (async test support)
- Config: No `pytest.ini`, `conftest.py`, or `pyproject.toml` test config found
- Config location: Test settings would go in `backend/pytest.ini` or `backend/pyproject.toml`

**Assertion Library:**
- pytest built-in assertions (no test files exist yet to verify patterns)

**HTTP Testing:**
- httpx >= 0.26.0 (for async FastAPI test client)

**Run Commands:**
```bash
make test                # Run all tests (currently backend only)
make test-backend        # Run pytest with verbose output: cd backend && pytest -v
```

## Test File Organization

**Location:**
- No test files currently exist in the codebase
- No `tests/` directory, no `test_*.py` files, no `conftest.py`
- Test dependencies (pytest, pytest-asyncio, httpx) are listed in `backend/requirements.txt`

**Expected Pattern (from CLAUDE.md and dependencies):**
- Backend tests should go in `backend/tests/` directory
- Test files named `test_{module}.py`
- Use `conftest.py` for shared fixtures

**Recommended Structure:**
```
backend/
├── tests/
│   ├── conftest.py           # Shared fixtures (test client, mock services)
│   ├── test_extract.py       # Extract API endpoint tests
│   ├── test_title.py         # Title API endpoint tests
│   ├── test_proration.py     # Proration API endpoint tests
│   ├── test_revenue.py       # Revenue API endpoint tests
│   ├── test_ghl_prep.py      # GHL Prep API endpoint tests
│   └── services/
│       ├── test_parser.py    # Unit tests for parsing logic
│       └── test_helpers.py   # Unit tests for utility functions
```

**Frontend Testing:**
- No test framework configured (no jest, vitest, or testing-library in `package.json`)
- No frontend test files exist
- ESLint is the only quality check for frontend code

## Test Structure

**No existing tests to reference.** Based on the stack (FastAPI + pytest-asyncio + httpx), the recommended pattern is:

**Suite Organization:**
```python
"""Tests for extract API endpoints."""

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest.fixture
async def client():
    """Create async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Test extract health endpoint."""
    response = await client.get("/api/extract/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_upload_pdf(client: AsyncClient):
    """Test PDF upload and extraction."""
    with open("test-data/extract/sample.pdf", "rb") as f:
        response = await client.post(
            "/api/extract/upload",
            files={"file": ("test.pdf", f, "application/pdf")},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["result"]["success"] is True
```

## Mocking

**Framework:** No mocking framework explicitly listed; use pytest built-in `monkeypatch` or `unittest.mock`

**What Would Need Mocking:**
- Firestore client (`backend/app/services/firestore_service.py`) -- lazy init via `get_firestore_client()`
- GCS storage (`backend/app/services/storage_service.py`) -- lazy init via `_init_client()`
- Firebase Admin SDK (`backend/app/core/auth.py`) -- lazy init via `get_firebase_app()`
- Gemini AI service (`backend/app/services/gemini_service.py`)
- External HTTP requests (RRC downloads in `backend/app/services/proration/rrc_data_service.py`)

**Recommended Mocking Pattern:**
```python
from unittest.mock import AsyncMock, patch


@pytest.fixture
def mock_firestore():
    """Mock Firestore to avoid real database calls."""
    with patch("app.services.firestore_service.get_firestore_client") as mock:
        mock.return_value = AsyncMock()
        yield mock


@pytest.fixture
def mock_storage():
    """Mock GCS storage to use local filesystem."""
    with patch("app.services.storage_service.StorageService._init_client") as mock:
        mock.return_value = False  # Force local fallback
        yield mock
```

**What NOT to Mock:**
- PDF parsing logic (test with real PDF fixtures in `test-data/extract/`)
- CSV processing (test with real CSV fixtures in `test-data/proration/`)
- Pydantic model validation (test directly)
- Utility functions in `backend/app/utils/helpers.py` and `backend/app/utils/patterns.py`

## Fixtures and Factories

**Test Data:**
- `test-data/` directory exists at project root (gitignored)
- Subdirectories per tool: `test-data/extract/`, `test-data/title/`, `test-data/proration/`, `test-data/revenue/`, `test-data/ghl/`
- Test fixtures must be copied locally; they are not committed to the repository

**Recommended Fixture Pattern:**
```python
import pytest
from pathlib import Path

TEST_DATA_DIR = Path(__file__).parent.parent.parent / "test-data"


@pytest.fixture
def sample_pdf() -> bytes:
    """Load a sample OCC Exhibit A PDF for testing."""
    pdf_path = TEST_DATA_DIR / "extract" / "sample.pdf"
    if not pdf_path.exists():
        pytest.skip("Test data not available")
    return pdf_path.read_bytes()


@pytest.fixture
def sample_csv() -> bytes:
    """Load a sample mineral holders CSV for testing."""
    csv_path = TEST_DATA_DIR / "proration" / "sample.csv"
    if not csv_path.exists():
        pytest.skip("Test data not available")
    return csv_path.read_bytes()
```

## Coverage

**Requirements:** None enforced. No coverage configuration exists.

**Recommended Setup:**
```bash
# Add to requirements.txt
pytest-cov>=4.1.0

# Run with coverage
cd backend && pytest --cov=app --cov-report=html -v
```

## Test Types

**Unit Tests:**
- Priority targets for unit testing:
  - `backend/app/utils/helpers.py` -- pure functions (parse_date, parse_decimal, clean_text, generate_uid)
  - `backend/app/utils/patterns.py` -- regex patterns and detect_entity_type()
  - `backend/app/services/extract/parser.py` -- exhibit A text parsing
  - `backend/app/services/extract/name_parser.py` -- name parsing
  - `backend/app/services/proration/csv_processor.py` -- CSV processing
  - `backend/app/services/proration/legal_description_parser.py` -- legal description parsing
  - `backend/app/models/*.py` -- Pydantic model validation

**Integration Tests:**
- API endpoint tests using httpx AsyncClient against FastAPI app
  - Upload endpoints (file handling + processing pipeline)
  - Export endpoints (data transformation + file response)
  - Health check endpoints
- Require mocking external services (Firestore, GCS, Firebase)

**E2E Tests:**
- Not used. No Playwright, Cypress, or similar configured.

## Common Patterns

**Async Testing (recommended):**
```python
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")
        assert response.status_code == 200
```

**Error Testing (recommended):**
```python
@pytest.mark.asyncio
async def test_upload_invalid_file(client: AsyncClient):
    """Test that uploading a non-PDF file returns 400."""
    response = await client.post(
        "/api/extract/upload",
        files={"file": ("test.txt", b"not a pdf", "text/plain")},
    )
    assert response.status_code == 400
    assert "Invalid file type" in response.json()["detail"]
```

**Utility Function Testing (recommended):**
```python
from app.utils.helpers import parse_date, parse_decimal, generate_uid
from datetime import date
from decimal import Decimal


def test_parse_date_mdy():
    assert parse_date("2/24/2025") == date(2025, 2, 24)


def test_parse_date_month_year():
    assert parse_date("Dec 2024") == date(2024, 12, 1)


def test_parse_date_invalid():
    assert parse_date("not a date") is None


def test_parse_decimal_negative():
    assert parse_decimal("(123.45)") == Decimal("-123.45")


def test_generate_uid():
    assert generate_uid("CHK001", "PROP001", 1) == "CHK001-PROP001-0001"
```

## Current State Summary

| Area | Status |
|------|--------|
| Backend test framework | Installed (pytest, pytest-asyncio, httpx) but no tests written |
| Backend test files | None exist |
| Backend conftest.py | Does not exist |
| Frontend test framework | Not installed |
| Frontend test files | None exist |
| Coverage tooling | Not configured |
| CI test step | `make test` runs `cd backend && pytest -v` (would pass vacuously with 0 tests) |
| Test data fixtures | `test-data/` directory exists (gitignored), contains sample files per tool |

---

*Testing analysis: 2026-03-10*

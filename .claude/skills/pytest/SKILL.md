---
name: pytest
description: |
  Runs backend tests with async support and API testing via httpx.
  Use when: writing tests for FastAPI endpoints, testing async services, validating Pydantic models, or ensuring backend business logic correctness.
allowed-tools: Read, Edit, Write, Glob, Grep, Bash, mcp__plugin_context7_context7__resolve-library-id, mcp__plugin_context7_context7__query-docs
---

# Pytest Skill

This project uses pytest with `pytest-asyncio` for async test support and `httpx` for FastAPI endpoint testing. Tests live in `toolbox/backend/` and cover API routes, service layer logic, Pydantic validation, and Firestore/GCS integration with mocking.

## Quick Start

### Running Tests

```bash
# Run all tests from toolbox/
make test

# Or run directly with verbose output
cd toolbox/backend && pytest -v

# Run specific test file
pytest toolbox/backend/tests/test_extract.py -v

# Run tests matching pattern
pytest -k "test_upload" -v
```

### Basic Test Structure

```python
# tests/test_extract.py
import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_upload_valid_pdf():
    """Test PDF upload endpoint returns 200 and party entries."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        with open("tests/fixtures/exhibit_a.pdf", "rb") as f:
            response = await client.post(
                "/api/extract/upload",
                files={"file": ("test.pdf", f, "application/pdf")}
            )
    
    assert response.status_code == 200
    data = response.json()
    assert "parties" in data
    assert len(data["parties"]) > 0
```

## Key Concepts

| Concept | Usage | Example |
|---------|-------|---------|
| `@pytest.mark.asyncio` | Mark async test functions | `@pytest.mark.asyncio async def test_api():` |
| `AsyncClient` (httpx) | Test FastAPI endpoints | `async with AsyncClient(app=app, base_url="http://test")` |
| `pytest.fixture` | Reusable test setup | `@pytest.fixture def mock_gcs():` |
| `monkeypatch` | Mock functions/env vars | `monkeypatch.setenv("GCS_BUCKET_NAME", "test")` |
| `pytest -k` | Run tests by name pattern | `pytest -k "upload"` |

## Common Patterns

### Testing FastAPI Endpoints

**When:** Validating API routes with file uploads, JSON payloads, or authentication

```python
@pytest.mark.asyncio
async def test_proration_upload(mock_firestore, mock_gcs):
    """Test mineral holders CSV upload with mocked storage."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        csv_content = b"Name,Interest\nJohn Doe,0.125"
        response = await client.post(
            "/api/proration/upload",
            files={"file": ("holders.csv", csv_content, "text/csv")}
        )
    
    assert response.status_code == 200
    result = response.json()
    assert result["total_count"] == 1
    assert result["rows"][0]["name"] == "John Doe"
```

### Mocking External Services

**When:** Testing service layer without GCS, Firestore, or Firebase dependencies

```python
@pytest.fixture
def mock_storage(monkeypatch):
    """Mock StorageService to use local filesystem only."""
    monkeypatch.setenv("GCS_BUCKET_NAME", "")
    # Forces storage_service to use local fallback
    from app.services.storage_service import StorageService
    service = StorageService()
    assert not service.use_gcs
    return service
```

### Testing Async Services

**When:** Validating business logic in service layer (RRC download, CSV processing)

```python
@pytest.mark.asyncio
async def test_rrc_data_download(tmp_path, monkeypatch):
    """Test RRC CSV download saves to local storage."""
    monkeypatch.setenv("GCS_BUCKET_NAME", "")
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    
    from app.services.proration.rrc_data_service import download_rrc_data
    result = await download_rrc_data(data_dir)
    
    assert result["status"] == "success"
    assert (data_dir / "rrc-data" / "oil_proration.csv").exists()
```

## See Also

- [unit](references/unit.md) - Unit testing service layer and utilities
- [integration](references/integration.md) - API integration tests with httpx
- [mocking](references/mocking.md) - Mocking GCS, Firestore, and external APIs
- [fixtures](references/fixtures.md) - Reusable test fixtures and setup

## Related Skills

- **python** - For async patterns, type hints, and Pydantic usage
- **fastapi** - Understanding endpoint structure and dependency injection
- **pydantic** - Validating model serialization in tests
- **google-cloud-storage** - Understanding GCS mocking strategies
- **firestore** - Mocking Firestore batch operations
- **pandas** - Testing CSV processing and DataFrame transformations

## Documentation Resources

> Fetch latest pytest documentation with Context7.

**How to use Context7:**
1. Use `mcp__plugin_context7_context7__resolve-library-id` to search for "pytest"
2. **Prefer website documentation** (IDs starting with `/websites/`) over source code repositories when available
3. Query with `mcp__plugin_context7_context7__query-docs` using the resolved library ID

**Library ID:** Resolve using `mcp__plugin_context7_context7__resolve-library-id` with query "pytest documentation"

**Recommended Queries:**
- "pytest async testing with asyncio"
- "pytest fixtures and dependency injection"
- "pytest mocking with monkeypatch"
- "pytest parametrize multiple test cases"
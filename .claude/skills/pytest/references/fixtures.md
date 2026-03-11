# Fixtures Reference

## Contents
- Shared Fixtures (conftest.py)
- File Fixtures (Test Data)
- Service Mocks
- Fixture Scope and Cleanup
- Anti-Patterns

---

## Shared Fixtures (conftest.py)

Place reusable fixtures in `conftest.py` to share across test modules.

### Project-Wide conftest.py

```python
# toolbox/backend/conftest.py
import pytest
from pathlib import Path

@pytest.fixture(scope="session")
def fixtures_dir():
    """Return path to test fixtures directory."""
    return Path(__file__).parent / "tests" / "fixtures"

@pytest.fixture
def tmp_data_dir(tmp_path, monkeypatch):
    """Create temporary data directory for tests."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    return data_dir

@pytest.fixture
def mock_env_development(monkeypatch):
    """Set environment to development mode."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("DATABASE_ENABLED", "false")
    monkeypatch.setenv("FIRESTORE_ENABLED", "false")
    monkeypatch.setenv("GCS_BUCKET_NAME", "")
```

### Storage Mock Fixture

```python
@pytest.fixture
def mock_storage(monkeypatch):
    """Mock StorageService to use local filesystem only.

    StorageService checks settings.use_gcs at init time.
    Setting GCS_BUCKET_NAME="" disables it; is_gcs_enabled returns False.
    """
    monkeypatch.setenv("GCS_BUCKET_NAME", "")
    monkeypatch.setenv("GCS_PROJECT_ID", "")

    from app.services.storage_service import StorageService
    service = StorageService()
    assert not service.is_gcs_enabled
    return service
```

### Firestore Mock Fixture

```python
@pytest.fixture
def mock_firestore(monkeypatch):
    """Mock Firestore client to prevent real database writes.

    firestore_service uses get_firestore_client() — patch that function.
    """
    from unittest.mock import MagicMock, AsyncMock

    mock_client = MagicMock()
    mock_collection = MagicMock()
    mock_client.collection.return_value = mock_collection

    # Mock document add
    mock_doc_ref = MagicMock()
    mock_doc_ref.id = "test-job-12345"
    mock_collection.add = AsyncMock(return_value=(None, mock_doc_ref))

    # Mock document get
    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {"job_id": "test-job-12345", "status": "completed"}
    mock_collection.document.return_value.get = AsyncMock(return_value=mock_doc)

    # Mock batch operations
    mock_batch = MagicMock()
    mock_batch.commit = AsyncMock()
    mock_client.batch.return_value = mock_batch

    monkeypatch.setattr("app.services.firestore_service.get_firestore_client", lambda: mock_client)
    return mock_client
```

---

## File Fixtures (Test Data)

Store test PDFs, CSVs, and Excel files in `tests/fixtures/`.

### Creating Test Files Programmatically

```python
# conftest.py
import pytest
import pandas as pd

@pytest.fixture
def sample_mineral_holders_csv(tmp_path):
    """Create sample mineral holders CSV for testing."""
    csv_path = tmp_path / "mineral_holders.csv"
    df = pd.DataFrame({
        "Name": ["John Doe", "Jane Smith", "ACME Trust"],
        "Interest": [0.125, 0.0625, 0.25],
        "Legal Description": ["Section 1 Block A", "Section 2 Block B", "Section 3 Block C"],
        "County": ["Midland", "Ector", "Midland"]
    })
    df.to_csv(csv_path, index=False)
    return csv_path

@pytest.fixture
def sample_title_excel(tmp_path):
    """Create sample title opinion Excel for testing."""
    excel_path = tmp_path / "title_opinion.xlsx"
    df = pd.DataFrame({
        "Owner Name": ["John Doe", "Jane Doe"],
        "Owner Interest": ["12.5%", "6.25%"],
        "Legal Description": ["Sec 1", "Sec 2"],
        "Vesting Deed": ["Warranty Deed", "Mineral Deed"]
    })
    df.to_excel(excel_path, index=False, sheet_name="Owners")
    return excel_path
```

### Using Committed Test Files

```python
# tests/api/test_extract.py
import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_extract_real_pdf_fixture(fixtures_dir, mock_storage):
    """Test extraction with committed PDF fixture."""
    pdf_path = fixtures_dir / "exhibit_a_sample.pdf"
    assert pdf_path.exists(), "Missing test fixture: exhibit_a_sample.pdf"
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        with open(pdf_path, "rb") as f:
            response = await client.post(
                "/api/extract/upload",
                files={"file": ("exhibit_a.pdf", f, "application/pdf")}
            )
    
    assert response.status_code == 200
    result = response.json()
    assert result["total_count"] > 0
```

---

## RRC Data Mock Fixture

### In-Memory RRC DataFrame

```python
@pytest.fixture
def mock_rrc_data(monkeypatch):
    """Mock in-memory RRC data for proration lookups."""
    import pandas as pd
    
    # Create sample RRC data
    rrc_df = pd.DataFrame({
        "Lease Number": ["12345", "67890", "11111"],
        "Operator": ["Test Operator A", "Test Operator B", "Test Operator C"],
        "County": ["Midland", "Ector", "Midland"],
        "Field": ["Spraberry", "Permian", "Spraberry"],
        "Proration_Factor": [0.85, 0.92, 0.88]
    })
    
    # Mock the CSV processor to return this data
    from app.services.proration.csv_processor import CSVProcessor
    original_load = CSVProcessor.load_rrc_data
    
    def mock_load_rrc_data(self, well_type):
        self._rrc_cache[well_type] = rrc_df
        return rrc_df
    
    monkeypatch.setattr(CSVProcessor, "load_rrc_data", mock_load_rrc_data)
    return rrc_df
```

---

## Fixture Scope and Cleanup

### Session-Scoped Fixtures

```python
@pytest.fixture(scope="session")
def app_config():
    """Load application config once per test session."""
    from app.core.config import Settings
    return Settings(
        environment="test",
        database_enabled=False,
        firestore_enabled=False,
        gcs_bucket_name=""
    )
```

### Function-Scoped with Auto Cleanup

```python
@pytest.fixture
def temp_upload_dir(tmp_path):
    """Create temporary upload directory, cleaned up after test."""
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    yield upload_dir
    # tmp_path automatically cleaned up by pytest
```

### Cleanup After Async Fixtures

```python
@pytest.fixture
async def async_client_with_auth(mock_firebase_auth):
    """Create AsyncClient with mocked auth headers."""
    from httpx import AsyncClient
    from app.main import app
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        client.headers["Authorization"] = "Bearer mock-token"
        yield client
    # AsyncClient automatically closed after yield
```

---

## Anti-Patterns

### WARNING: Using Mutable Default Fixtures

**The Problem:**

```python
# BAD - Mutable fixture shared across tests
@pytest.fixture
def shared_data():
    return {"parties": []}  # Same dict reused across tests!

def test_one(shared_data):
    shared_data["parties"].append("John Doe")
    assert len(shared_data["parties"]) == 1

def test_two(shared_data):
    # Fails! shared_data["parties"] already has "John Doe" from test_one
    assert len(shared_data["parties"]) == 0
```

**Why This Breaks:**
1. Tests interfere with each other
2. Test order matters (fragile)
3. Passing tests become failing when run with other tests

**The Fix:**

```python
# GOOD - Return new instance each time
@pytest.fixture
def fresh_data():
    return {"parties": []}  # New dict for each test

# BETTER - Use function scope explicitly
@pytest.fixture(scope="function")
def isolated_data():
    return {"parties": []}
```

**When You Might Be Tempted:**
When thinking "I'll just reset it"—fixtures should be isolated by default.

---

### WARNING: Not Using tmp_path for File Operations

**The Problem:**

```python
# BAD - Writes to real filesystem
@pytest.fixture
def test_csv():
    csv_path = Path("test_data.csv")
    csv_path.write_text("Name,Interest\nTest,0.125")
    return csv_path
    # File left on filesystem after test!
```

**Why This Breaks:**
1. Pollutes filesystem with test data
2. Tests fail if file already exists
3. No automatic cleanup
4. CI/CD artifacts accumulate

**The Fix:**

```python
# GOOD - Use tmp_path for automatic cleanup
@pytest.fixture
def test_csv(tmp_path):
    csv_path = tmp_path / "test_data.csv"
    csv_path.write_text("Name,Interest\nTest,0.125")
    return csv_path
    # tmp_path automatically deleted after test
```

**When You Might Be Tempted:**
When quickly prototyping a test—always use `tmp_path` for file fixtures.

---

### WARNING: Over-Using session Scope

**The Problem:**

```python
# BAD - Session-scoped mutable state
@pytest.fixture(scope="session")
def shared_mock_firestore(monkeypatch):
    # monkeypatch doesn't work with session scope!
    monkeypatch.setattr(...)  # Raises error
```

**Why This Breaks:**
1. `monkeypatch` is function-scoped, can't be used in session fixtures
2. Session-scoped mocks can leak state across tests
3. Hard to debug test interactions

**The Fix:**

```python
# GOOD - Use function scope for mocks
@pytest.fixture(scope="function")
def mock_firestore(monkeypatch):
    """Function-scoped Firestore mock, isolated per test."""
    monkeypatch.setattr("app.services.firestore_service._get_client", lambda: mock_client)
    return mock_client
```

**When You Might Be Tempted:**
When optimizing test speed—session scope is for read-only resources (config, fixture files), not mocks.
# Mocking Reference

## Contents
- Mocking GCS (Google Cloud Storage)
- Mocking Firestore
- Mocking Firebase Auth
- Mocking External APIs (RRC)
- Anti-Patterns

---

## Mocking GCS (Google Cloud Storage)

The `StorageService` has built-in local fallback. Mock by disabling GCS via environment variables.

### Basic GCS Mock Fixture

```python
# conftest.py
import pytest

@pytest.fixture
def mock_storage(monkeypatch, tmp_path):
    """Mock StorageService to use local filesystem only."""
    monkeypatch.setenv("GCS_BUCKET_NAME", "")  # Disables GCS
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    
    from app.services.storage_service import StorageService
    service = StorageService()
    assert not service.use_gcs  # Verify GCS is disabled
    return service
```

### Testing File Upload/Download

```python
@pytest.mark.asyncio
async def test_storage_upload_download(mock_storage, tmp_path):
    """Test file upload and download with mocked storage."""
    file_content = b"test pdf content"
    file_path = "uploads/test.pdf"
    
    # Upload
    result_url = await mock_storage.upload_file(file_path, file_content)
    assert result_url.startswith("file://")
    assert (tmp_path / file_path).exists()
    
    # Download
    downloaded = await mock_storage.download_file(file_path)
    assert downloaded == file_content
```

### Mocking Signed URLs

```python
@pytest.mark.asyncio
async def test_get_signed_url_local_fallback(mock_storage):
    """Test get_signed_url returns local URL when GCS disabled."""
    file_path = "test.pdf"
    await mock_storage.upload_file(file_path, b"data")
    
    url = mock_storage.get_signed_url(file_path)
    # GCS disabled, returns None (caller provides local fallback)
    assert url is None
```

---

## Mocking Firestore

Firestore operations should be mocked to avoid real database writes. Use `monkeypatch` or `unittest.mock`.

### Basic Firestore Mock Fixture

```python
# conftest.py
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def mock_firestore(monkeypatch):
    """Mock Firestore client to prevent real database operations."""
    mock_client = MagicMock()
    mock_collection = MagicMock()
    mock_client.collection.return_value = mock_collection
    
    # Mock add operation
    mock_doc_ref = MagicMock()
    mock_doc_ref.id = "test-job-id-12345"
    mock_collection.add = AsyncMock(return_value=(None, mock_doc_ref))
    
    # Mock get operation
    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {
        "job_id": "test-job-id-12345",
        "tool": "extract",
        "status": "completed",
        "created_at": "2025-02-09T10:00:00Z"
    }
    mock_collection.document.return_value.get = AsyncMock(return_value=mock_doc)
    
    # Patch firestore client initialization
    monkeypatch.setattr("app.services.firestore_service._get_client", lambda: mock_client)
    return mock_client
```

### Mocking Batch Operations

```python
@pytest.fixture
def mock_firestore_batch(monkeypatch):
    """Mock Firestore batch writes for RRC data sync."""
    mock_client = MagicMock()
    mock_batch = MagicMock()
    mock_client.batch.return_value = mock_batch
    mock_batch.commit = AsyncMock()
    
    monkeypatch.setattr("app.services.firestore_service._get_client", lambda: mock_client)
    return mock_batch

@pytest.mark.asyncio
async def test_rrc_sync_to_firestore(mock_firestore_batch):
    """Test RRC data sync batches 500 docs per commit."""
    from app.services.proration.rrc_data_service import sync_to_database
    
    # Create 1200 test records (should batch into 3 commits)
    import pandas as pd
    df = pd.DataFrame({"lease_number": range(1200), "operator": ["Test"] * 1200})
    
    await sync_to_database(df, "oil")
    
    # Verify batch.commit() called 3 times (500 + 500 + 200)
    assert mock_firestore_batch.commit.call_count == 3
```

---

## Mocking Firebase Auth

Mock token verification to bypass authentication in tests.

### Auth Mock Fixture

```python
# conftest.py
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def mock_firebase_auth(monkeypatch):
    """Mock Firebase Auth token verification."""
    mock_decoded_token = {
        "uid": "test-user-uid",
        "email": "test@tablerocktx.com",
        "email_verified": True
    }
    
    mock_verify = AsyncMock(return_value=mock_decoded_token)
    monkeypatch.setattr("app.core.auth.verify_token", mock_verify)
    
    # Mock allowlist check
    monkeypatch.setattr("app.core.auth.is_user_allowed", lambda email: True)
    
    return mock_decoded_token
```

### Testing Protected Endpoints

```python
@pytest.mark.asyncio
async def test_protected_endpoint_requires_auth():
    """Test protected endpoint rejects requests without auth header."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/admin/users")
    
    assert response.status_code == 401
    assert "Authorization" in response.json()["detail"]

@pytest.mark.asyncio
async def test_protected_endpoint_with_valid_token(mock_firebase_auth):
    """Test protected endpoint allows valid Firebase token."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get(
            "/api/admin/users",
            headers={"Authorization": "Bearer valid-token"}
        )
    
    assert response.status_code == 200
```

---

## Mocking External APIs (RRC)

Mock RRC website downloads to avoid network calls and SSL issues.

### RRC Download Mock

```python
@pytest.fixture
def mock_rrc_download(monkeypatch):
    """Mock RRC CSV download to return test data."""
    from unittest.mock import MagicMock
    import requests
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b"Lease Number,Operator\n12345,Test Operator\n67890,Another Operator"
    
    def mock_get(*args, **kwargs):
        return mock_response
    
    monkeypatch.setattr(requests, "get", mock_get)
    return mock_response

@pytest.mark.asyncio
async def test_rrc_download_oil_data(mock_rrc_download, tmp_path):
    """Test RRC oil data download uses mocked response."""
    from app.services.proration.rrc_data_service import download_oil_proration
    
    result = await download_oil_proration(tmp_path)
    
    assert result["status"] == "success"
    assert result["record_count"] == 2
    csv_path = tmp_path / "rrc-data" / "oil_proration.csv"
    assert csv_path.exists()
```

---

## Anti-Patterns

### WARNING: Partial Mocking That Leaks Real Calls

**The Problem:**

```python
# BAD - Mocks upload but not download, causes mixed behavior
@pytest.fixture
def partial_mock_storage(monkeypatch):
    from unittest.mock import AsyncMock
    monkeypatch.setattr("app.services.storage_service.StorageService.upload_file", AsyncMock())
    # Forgot to mock download_file—it still hits real GCS!
```

**Why This Breaks:**
1. Some operations use real GCS, others don't
2. Non-deterministic test failures
3. Hard to debug mixed real/mock behavior

**The Fix:**

```python
# GOOD - Mock entire service or use local fallback
@pytest.fixture
def mock_storage(monkeypatch, tmp_path):
    """Disable GCS entirely for consistent local-only behavior."""
    monkeypatch.setenv("GCS_BUCKET_NAME", "")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from app.services.storage_service import StorageService
    return StorageService()  # All methods use local fallback
```

**When You Might Be Tempted:**
When debugging one method and forgetting others—always mock the entire service boundary.

---

### WARNING: Not Verifying Mock Call Counts

**The Problem:**

```python
# BAD - Mocks Firestore but doesn't verify it was called
@pytest.mark.asyncio
async def test_job_saved_to_firestore(mock_firestore):
    async with AsyncClient(app=app, base_url="http://test") as client:
        await client.post("/api/extract/upload", files=...)
    # Test passes but doesn't verify Firestore.add() was called!
```

**Why This Breaks:**
1. Code might skip Firestore save due to bug
2. Test passes falsely (mock exists but unused)
3. Doesn't catch regression when persistence removed

**The Fix:**

```python
# GOOD - Verify mock interactions
@pytest.mark.asyncio
async def test_job_saved_to_firestore(mock_firestore):
    """Test extract upload saves job to Firestore."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/extract/upload",
            files={"file": ("test.pdf", pdf_bytes, "application/pdf")}
        )
    
    assert response.status_code == 200
    
    # Verify Firestore.collection().add() was called
    mock_firestore.collection.assert_called_with("jobs")
    mock_collection = mock_firestore.collection.return_value
    mock_collection.add.assert_called_once()
    
    # Verify saved data structure
    call_args = mock_collection.add.call_args
    saved_data = call_args[0][0]
    assert saved_data["tool"] == "extract"
    assert "job_id" in saved_data
```

**When You Might Be Tempted:**
When trusting that the endpoint "probably" saves to Firestore—always verify critical side effects.
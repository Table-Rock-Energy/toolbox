# Integration Testing Reference

## Contents
- FastAPI Endpoint Testing
- File Upload Testing
- Multi-Tool Workflows
- Database Integration Tests
- Anti-Patterns

---

## FastAPI Endpoint Testing with httpx

Integration tests validate API endpoints end-to-end with mocked external services (GCS, Firestore, Firebase Auth).

### Basic Endpoint Test

```python
# tests/api/test_health.py
import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_health_endpoint():
    """Test health check returns 200 and service info."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "environment" in data
```

### File Upload Endpoint

```python
# tests/api/test_extract.py
import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_extract_upload_pdf(mock_storage, mock_firestore):
    """Test OCC Exhibit A PDF upload extracts parties."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        with open("tests/fixtures/exhibit_a_sample.pdf", "rb") as f:
            response = await client.post(
                "/api/extract/upload",
                files={"file": ("exhibit_a.pdf", f, "application/pdf")}
            )
    
    assert response.status_code == 200
    result = response.json()
    assert result["total_count"] > 0
    assert "parties" in result
    assert result["parties"][0]["name"]
    assert result["parties"][0]["entity_type"]

@pytest.mark.asyncio
async def test_extract_upload_invalid_file_type():
    """Test extract endpoint rejects non-PDF files."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/extract/upload",
            files={"file": ("test.txt", b"not a pdf", "text/plain")}
        )
    
    assert response.status_code == 400
    assert "PDF" in response.json()["detail"]
```

---

## Testing CSV/Excel Uploads

### Proration Tool Upload

```python
# tests/api/test_proration.py
import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_proration_upload_valid_csv(mock_storage, mock_rrc_data):
    """Test mineral holders CSV upload with RRC data lookup."""
    csv_content = b"""Name,Interest,Legal Description,County
John Doe,0.125,Section 1 Block A,Midland
Jane Smith,0.0625,Section 2 Block B,Ector"""
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/proration/upload",
            files={"file": ("holders.csv", csv_content, "text/csv")}
        )
    
    assert response.status_code == 200
    result = response.json()
    assert result["total_count"] == 2
    assert result["rows"][0]["name"] == "John Doe"
    assert "nra_decimal" in result["rows"][0]  # Calculated field

@pytest.mark.asyncio
async def test_proration_upload_missing_columns():
    """Test proration endpoint rejects CSV with missing required columns."""
    csv_content = b"Name,Interest\nJohn Doe,0.125"  # Missing Legal Description
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/proration/upload",
            files={"file": ("invalid.csv", csv_content, "text/csv")}
        )
    
    assert response.status_code == 400
    assert "Legal Description" in response.json()["detail"]
```

---

## Export Endpoint Testing

### Testing CSV/Excel/PDF Exports

```python
# tests/api/test_export.py
import pytest
from httpx import AsyncClient
from app.main import app
import pandas as pd
from io import BytesIO

@pytest.mark.asyncio
async def test_export_csv(mock_storage):
    """Test CSV export returns downloadable file."""
    # First upload data
    async with AsyncClient(app=app, base_url="http://test") as client:
        csv_content = b"Name,Interest\nJohn Doe,0.125"
        upload_response = await client.post(
            "/api/proration/upload",
            files={"file": ("holders.csv", csv_content, "text/csv")}
        )
        job_id = upload_response.json()["job_id"]
        
        # Export to CSV
        export_response = await client.post(
            "/api/proration/export/csv",
            json={"job_id": job_id}
        )
    
    assert export_response.status_code == 200
    assert export_response.headers["content-type"] == "text/csv"
    
    # Validate exported CSV content
    df = pd.read_csv(BytesIO(export_response.content))
    assert len(df) == 1
    assert df.iloc[0]["Name"] == "John Doe"

@pytest.mark.asyncio
async def test_export_excel_has_multiple_sheets():
    """Test Excel export includes all required sheets."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # ... upload and process data ...
        response = await client.post(
            "/api/proration/export/excel",
            json={"job_id": "test-job-id"}
        )
    
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    
    # Validate Excel structure
    excel_file = BytesIO(response.content)
    df_dict = pd.read_excel(excel_file, sheet_name=None)
    assert "Summary" in df_dict
    assert "Details" in df_dict
```

---

## Multi-Tool Workflow Testing

### Testing Job History Retrieval

```python
# tests/api/test_history.py
import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_history_get_recent_jobs(mock_firestore):
    """Test history endpoint returns recent jobs for all tools."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/history/jobs?limit=10")
    
    assert response.status_code == 200
    jobs = response.json()["jobs"]
    assert len(jobs) <= 10
    assert all("tool" in job for job in jobs)
    assert all("created_at" in job for job in jobs)

@pytest.mark.asyncio
async def test_history_filter_by_tool():
    """Test history endpoint filters by tool type."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/history/jobs?tool=extract&limit=5")
    
    assert response.status_code == 200
    jobs = response.json()["jobs"]
    assert all(job["tool"] == "extract" for job in jobs)
```

---

## Anti-Patterns

### WARNING: Not Mocking External Services in Integration Tests

**The Problem:**

```python
# BAD - Integration test hits real Firestore/GCS
@pytest.mark.asyncio
async def test_proration_upload():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/api/proration/upload", ...)
    # This writes to real Firestore if credentials exist!
```

**Why This Breaks:**
1. Creates test data in production database
2. Fails in CI/CD without credentials
3. Slow due to network latency
4. Non-deterministic (depends on external state)

**The Fix:**

```python
# GOOD - Mock external services via fixtures
@pytest.mark.asyncio
async def test_proration_upload(mock_firestore, mock_storage):
    """Test proration upload with mocked Firestore and GCS."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/proration/upload",
            files={"file": ("test.csv", csv_content, "text/csv")}
        )
    
    assert response.status_code == 200
    # Firestore writes happen to mock, not real DB
```

See the **mocking** reference for fixture implementations.

**When You Might Be Tempted:**
When testing "end-to-end" and thinking you need real services—integration tests should mock external boundaries.

---

### WARNING: Not Cleaning Up Test Files

**The Problem:**

```python
# BAD - Leaves test files in local storage
@pytest.mark.asyncio
async def test_upload_creates_file():
    async with AsyncClient(app=app, base_url="http://test") as client:
        await client.post("/api/extract/upload", files={"file": ...})
    # File saved to backend/data/ but never cleaned up
```

**Why This Breaks:**
1. Pollutes local filesystem with test data
2. Tests interfere with each other (file already exists errors)
3. Fills disk over time

**The Fix:**

```python
# GOOD - Use tmp_path fixture for isolated storage
@pytest.mark.asyncio
async def test_upload_creates_file(tmp_path, monkeypatch):
    """Test file upload saves to temporary directory."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("GCS_BUCKET_NAME", "")  # Use local only
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/extract/upload",
            files={"file": ("test.pdf", pdf_bytes, "application/pdf")}
        )
    
    assert response.status_code == 200
    # tmp_path automatically cleaned up after test
```

**When You Might Be Tempted:**
When focusing on happy path and forgetting about test isolation—always use `tmp_path` for file storage tests.
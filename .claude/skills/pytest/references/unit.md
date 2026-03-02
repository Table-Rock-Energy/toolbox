# Unit Testing Reference

## Contents
- Service Layer Testing
- Pydantic Model Validation
- Utility Function Testing
- Error Handling Tests
- Anti-Patterns

---

## Service Layer Testing

Unit tests for service layer logic should mock external dependencies (GCS, Firestore, RRC API) and focus on business logic correctness.

### Testing CSV Processors

```python
# tests/services/test_csv_processor.py
import pytest
import pandas as pd
from app.services.proration.csv_processor import CSVProcessor

def test_process_mineral_holders_valid_csv(tmp_path):
    """Test processing valid mineral holders CSV."""
    csv_path = tmp_path / "holders.csv"
    csv_path.write_text("Name,Interest,Legal Description\nJohn Doe,0.125,Section 1")
    
    processor = CSVProcessor()
    result = processor.process_file(str(csv_path))
    
    assert result.total_count == 1
    assert result.rows[0].name == "John Doe"
    assert result.rows[0].interest == 0.125
```

### Testing Pydantic Model Serialization

```python
# tests/models/test_extract.py
from app.models.extract import PartyEntry, EntityType

def test_party_entry_serialization():
    """Test PartyEntry serializes to dict correctly."""
    entry = PartyEntry(
        name="ACME Trust",
        entity_type=EntityType.TRUST,
        address="123 Main St",
        city="Austin",
        state="TX",
        zip_code="78701"
    )
    
    data = entry.model_dump()
    assert data["name"] == "ACME Trust"
    assert data["entity_type"] == "Trust"  # Enum serializes to string
    assert data["state"] == "TX"

def test_party_entry_validation_fails_invalid_state():
    """Test PartyEntry rejects invalid state code."""
    with pytest.raises(ValueError, match="Invalid state"):
        PartyEntry(
            name="Test",
            entity_type=EntityType.INDIVIDUAL,
            state="XX"  # Invalid state code
        )
```

### Testing Utility Functions

```python
# tests/utils/test_helpers.py
from app.utils.helpers import parse_date, parse_decimal, generate_uid

def test_parse_date_valid_formats():
    """Test date parser handles multiple formats."""
    assert parse_date("2025-01-15") == "2025-01-15"
    assert parse_date("01/15/2025") == "2025-01-15"
    assert parse_date("January 15, 2025") == "2025-01-15"

def test_parse_decimal_handles_percentages():
    """Test decimal parser converts percentages."""
    assert parse_decimal("12.5%") == 0.125
    assert parse_decimal("0.125") == 0.125
    assert parse_decimal("invalid") is None

def test_generate_uid_unique():
    """Test UID generator creates unique IDs."""
    uid1 = generate_uid()
    uid2 = generate_uid()
    assert uid1 != uid2
    assert len(uid1) == 12  # Assuming 12-char UIDs
```

---

## Mocking External Dependencies

### WARNING: Never Test Against Live GCS/Firestore

**The Problem:**

```python
# BAD - Tests fail without GCS credentials
@pytest.mark.asyncio
async def test_upload_file():
    from app.services.storage_service import StorageService
    service = StorageService()  # Uses real GCS if credentials exist
    await service.upload_file("test.pdf", b"data")
```

**Why This Breaks:**
1. Tests require production credentials in CI/CD
2. Creates actual files in production buckets
3. Fails in local dev without credentials
4. Slow due to network calls

**The Fix:**

```python
# GOOD - Mock GCS by disabling it via env var
@pytest.mark.asyncio
async def test_upload_file(monkeypatch, tmp_path):
    """Test file upload uses local fallback."""
    monkeypatch.setenv("GCS_BUCKET_NAME", "")  # Disables GCS
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    
    from app.services.storage_service import StorageService
    service = StorageService()
    
    result = await service.upload_file("test.pdf", b"data")
    assert result.startswith("file://")
    assert (tmp_path / "test.pdf").exists()
```

**When You Might Be Tempted:**
When testing storage service and thinking "it works on my machine with credentials"—always mock for portable tests.

---

## Testing Error Handling

### Service Layer Errors

```python
# tests/services/test_extract_service.py
import pytest
from fastapi import HTTPException
from app.services.extract.pdf_extractor import extract_parties_from_pdf

@pytest.mark.asyncio
async def test_extract_parties_invalid_pdf():
    """Test PDF extractor raises error for invalid files."""
    with pytest.raises(HTTPException) as exc_info:
        await extract_parties_from_pdf(b"not a pdf")
    
    assert exc_info.value.status_code == 400
    assert "Invalid PDF" in exc_info.value.detail

@pytest.mark.asyncio
async def test_extract_parties_empty_pdf(tmp_path):
    """Test PDF extractor handles empty PDFs gracefully."""
    # Create minimal valid but empty PDF
    empty_pdf = tmp_path / "empty.pdf"
    empty_pdf.write_bytes(b"%PDF-1.4\n%%EOF")
    
    result = await extract_parties_from_pdf(empty_pdf.read_bytes())
    assert result.total_count == 0
    assert result.parties == []
```

### Pydantic Validation Errors

```python
# tests/models/test_revenue.py
from pydantic import ValidationError
from app.models.revenue import M1UploadRow

def test_m1_upload_row_validation_fails_missing_required():
    """Test M1UploadRow rejects missing required fields."""
    with pytest.raises(ValidationError) as exc_info:
        M1UploadRow(
            well_name="Test Well"
            # Missing required fields: api_number, production_date, etc.
        )
    
    errors = exc_info.value.errors()
    assert any(e["loc"] == ("api_number",) for e in errors)
    assert any(e["loc"] == ("production_date",) for e in errors)
```

---

## Anti-Patterns

### WARNING: Testing Implementation Details Instead of Behavior

**The Problem:**

```python
# BAD - Test knows too much about internal implementation
def test_csv_processor_uses_pandas():
    """Test CSV processor uses pandas DataFrame internally."""
    processor = CSVProcessor()
    df = processor._internal_dataframe  # Accessing private attribute
    assert isinstance(df, pd.DataFrame)
```

**Why This Breaks:**
1. Brittle—breaks when refactoring internal implementation
2. Doesn't validate actual behavior users care about
3. Couples tests to implementation instead of interface

**The Fix:**

```python
# GOOD - Test observable behavior
def test_csv_processor_returns_correct_row_count(tmp_path):
    """Test CSV processor returns correct number of rows."""
    csv_path = tmp_path / "test.csv"
    csv_path.write_text("Name,Interest\nA,0.1\nB,0.2\nC,0.3")
    
    processor = CSVProcessor()
    result = processor.process_file(str(csv_path))
    assert result.total_count == 3  # Public behavior
```

**When You Might Be Tempted:**
When debugging and wanting to verify internal state—use logging instead of testing internals.

---

### WARNING: Not Using pytest.raises for Expected Errors

**The Problem:**

```python
# BAD - Manually catching exceptions
def test_invalid_entity_type():
    try:
        PartyEntry(name="Test", entity_type="InvalidType")
        raised = False
    except ValidationError:
        raised = True
    assert raised
```

**Why This Breaks:**
1. Verbose and hard to read
2. Doesn't verify exception message
3. Passes if wrong exception type raised

**The Fix:**

```python
# GOOD - Use pytest.raises context manager
def test_invalid_entity_type():
    """Test PartyEntry rejects invalid entity type."""
    with pytest.raises(ValidationError, match="entity_type"):
        PartyEntry(name="Test", entity_type="InvalidType")
```

**When You Might Be Tempted:**
When coming from unittest background—pytest.raises is clearer and validates exception details.
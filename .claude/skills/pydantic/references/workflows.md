# Pydantic Workflows Reference

## Contents
- Creating API Models
- Configuring Settings
- Validation Testing
- Model Serialization

---

## Creating API Models

### Workflow: Add New API Endpoint Model

**Scenario:** Adding a new FastAPI endpoint that returns structured data.

**Steps:**

1. **Define the response model in `backend/app/models/`**

```python
# backend/app/models/extract.py
from pydantic import BaseModel, Field

class ExtractionResult(BaseModel):
    """OCC Exhibit A extraction response."""
    entries: list[PartyEntry] = Field(default_factory=list, description="Extracted parties")
    total_count: int = Field(..., description="Total parties found")
    pdf_filename: str = Field(..., description="Source PDF name")
    processing_time_ms: float = Field(..., description="Processing duration")
```

2. **Use in FastAPI route handler**

```python
# backend/app/api/extract.py
from fastapi import APIRouter, UploadFile
from app.models.extract import ExtractionResult

router = APIRouter(prefix="/api/extract")

@router.post("/upload", response_model=ExtractionResult)
async def upload_pdf(file: UploadFile) -> ExtractionResult:
    """Process OCC Exhibit A PDF and extract parties."""
    entries = await extract_service.process_pdf(file)
    return ExtractionResult(
        entries=entries,
        total_count=len(entries),
        pdf_filename=file.filename,
        processing_time_ms=elapsed_ms
    )
```

3. **Validate OpenAPI docs at `/docs`**

Navigate to `http://localhost:8000/docs` and verify:
- [ ] Endpoint appears with correct path
- [ ] Response schema shows all fields with descriptions
- [ ] Example values are reasonable

4. **Test serialization**

```python
# Verify model serializes correctly
result = ExtractionResult(entries=[], total_count=0, pdf_filename="test.pdf", processing_time_ms=123.4)
assert result.model_dump() == {
    "entries": [],
    "total_count": 0,
    "pdf_filename": "test.pdf",
    "processing_time_ms": 123.4
}
```

---

## Configuring Settings

### Workflow: Add New Environment Variable

**Scenario:** Need to configure a new external service with environment variables.

**Steps:**

1. **Add field to Settings class**

```python
# backend/app/core/config.py
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    # ... existing fields ...

    rrc_api_timeout: int = Field(default=30, description="RRC download timeout in seconds")
    rrc_retry_count: int = Field(default=3, description="RRC download retry attempts")

    @property
    def rrc_enabled(self) -> bool:
        """RRC downloads enabled if timeout > 0."""
        return self.rrc_api_timeout > 0
```

2. **Document in CLAUDE.md environment table**

Add to the Environment Variables section:

```markdown
| `RRC_API_TIMEOUT` | No | `30` | RRC download timeout in seconds |
| `RRC_RETRY_COUNT` | No | `3` | RRC download retry attempts |
```

3. **Add to Dockerfile ENV defaults (if needed for production)**

```dockerfile
# Only if production default differs from code default
ENV RRC_API_TIMEOUT=60
ENV RRC_RETRY_COUNT=5
```

4. **Use in service layer**

```python
# backend/app/services/proration/rrc_data_service.py
from app.core.config import get_settings

settings = get_settings()

async def download_rrc_data():
    if not settings.rrc_enabled:
        logger.warning("RRC downloads disabled (timeout = 0)")
        return None
    
    response = await httpx.get(
        RRC_URL,
        timeout=settings.rrc_api_timeout,
        # ...
    )
```

**Validation Checklist:**
- [ ] Settings field has type hint and description
- [ ] Default value is production-safe
- [ ] Computed `@property` methods use new field correctly
- [ ] CLAUDE.md documents the environment variable
- [ ] Service layer uses `get_settings()` not hardcoded values

---

## Validation Testing

### Workflow: Test Pydantic Validation Logic

**Scenario:** Ensure custom validators reject invalid data before it reaches the database.

**Steps:**

1. **Write validation test cases**

```python
# backend/tests/test_models.py
import pytest
from pydantic import ValidationError
from app.models.proration import MineralHolderRow

def test_decimal_interest_range_valid():
    """Valid decimal interest between 0.0 and 1.0."""
    row = MineralHolderRow(
        lease_number="12345",
        decimal_interest=0.125,
        holder_name="Test Owner"
    )
    assert row.decimal_interest == 0.125

def test_decimal_interest_too_high():
    """Reject decimal interest > 1.0."""
    with pytest.raises(ValidationError) as exc:
        MineralHolderRow(
            lease_number="12345",
            decimal_interest=1.5,
            holder_name="Test Owner"
        )
    assert "must be 0.0-1.0" in str(exc.value)

def test_decimal_interest_negative():
    """Reject negative decimal interest."""
    with pytest.raises(ValidationError) as exc:
        MineralHolderRow(
            lease_number="12345",
            decimal_interest=-0.1,
            holder_name="Test Owner"
        )
    assert "must be 0.0-1.0" in str(exc.value)
```

2. **Run validation tests**

```bash
cd toolbox/backend
pytest tests/test_models.py -v
```

3. **If validation fails, iterate:**
   - Fix validator logic in model
   - Rerun tests
   - Only proceed when all tests pass

**Iterate-Until-Pass Pattern:**
1. Write test for invalid data
2. Run `pytest tests/test_models.py::test_name -v`
3. If test fails, fix validator logic
4. Repeat step 2 until test passes
5. Write next test case

---

## Model Serialization

### Workflow: Export Models to JSON/CSV

**Scenario:** Export Pydantic models to client-friendly formats (JSON, CSV).

**Steps:**

1. **JSON serialization (for API responses)**

```python
# Automatic via FastAPI response_model
@router.get("/jobs", response_model=list[JobRecord])
async def get_jobs() -> list[JobRecord]:
    """Returns JSON automatically via FastAPI."""
    jobs = await firestore_service.get_recent_jobs()
    return jobs  # FastAPI serializes to JSON

# Manual JSON serialization
job_json = job_record.model_dump_json(indent=2)
```

2. **CSV export (for Excel compatibility)**

```python
# backend/app/services/extract/export_service.py
import csv
from io import StringIO
from app.models.extract import PartyEntry

def export_to_csv(entries: list[PartyEntry]) -> str:
    """Convert PartyEntry models to CSV string."""
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=["name", "address", "entity_type", "page_number"])
    writer.writeheader()
    
    for entry in entries:
        # Use model_dump() to get dict representation
        writer.writerow(entry.model_dump(include={"name", "address", "entity_type", "page_number"}))
    
    return output.getvalue()
```

3. **Excel export (via pandas)**

```python
import pandas as pd
from app.models.title import OwnerEntry

def export_to_excel(entries: list[OwnerEntry]) -> bytes:
    """Convert OwnerEntry models to Excel bytes."""
    # Convert Pydantic models to list of dicts
    data = [entry.model_dump() for entry in entries]
    
    # Create DataFrame
    df = pd.DataFrame(data)
    
    # Export to Excel bytes
    output = BytesIO()
    df.to_excel(output, index=False, engine="openpyxl")
    return output.getvalue()
```

**Export Validation Checklist:**
- [ ] JSON: Use `model_dump_json()` for string or let FastAPI handle it
- [ ] CSV: Use `model_dump(include={...})` to control fields
- [ ] Excel: Convert to dict list, then DataFrame
- [ ] All exports preserve field order from model definition

---

## Copy-Paste Checklists

### New API Model Checklist

Copy this when creating new API endpoint models:

```markdown
- [ ] Model defined in `backend/app/models/{tool}.py`
- [ ] All fields have `Field(..., description="...")`
- [ ] Optional fields use `Field(default=..., description="...")`
- [ ] Enums use `str, Enum` pattern
- [ ] Custom validators use `@field_validator` or `@model_validator`
- [ ] Route handler uses `response_model=YourModel`
- [ ] OpenAPI docs verified at `/docs`
- [ ] Serialization tested with `model_dump()`
```

### Settings Configuration Checklist

Copy this when adding environment variables:

```markdown
- [ ] Field added to `Settings` class in `backend/app/core/config.py`
- [ ] Type hint and description provided
- [ ] Default value is production-safe
- [ ] Computed `@property` methods updated if needed
- [ ] Environment variable documented in CLAUDE.md
- [ ] Service layer uses `get_settings()` not hardcoded values
- [ ] Dockerfile ENV updated if production default differs
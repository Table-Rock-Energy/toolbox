# Python Errors Reference

## Contents
- HTTPException Patterns
- Logging Strategies
- Validation Errors
- Storage Fallbacks
- Common Python Errors
- Testing Error Paths

---

## HTTPException Patterns

### DO: Specific Status Codes with Context

```python
# backend/app/api/extract.py
from fastapi import HTTPException, UploadFile
import logging

logger = logging.getLogger(__name__)

@router.post("/upload")
async def upload_pdf(file: UploadFile):
    # Validation errors: 400 Bad Request
    if not file.filename.endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="PDF files only. Received: " + file.filename
        )
    
    try:
        content = await file.read()
        result = await parse_pdf(content)
        return result
    
    # Parsing errors: 422 Unprocessable Entity
    except ValueError as e:
        logger.error(f"PDF parsing failed for {file.filename}: {e}")
        raise HTTPException(
            status_code=422,
            detail=f"Invalid PDF structure: {e}"
        )
    
    # Unexpected errors: 500 Internal Server Error
    except Exception as e:
        logger.exception(f"Unexpected error processing {file.filename}")
        raise HTTPException(
            status_code=500,
            detail="Processing failed. Please contact support."
        )
```

**Why:** Clear status codes help clients handle errors. `logger.exception()` includes stack traces for debugging.

### DON'T: Generic 500 Errors for All Failures

```python
# BAD - Client can't distinguish validation vs server errors
@router.post("/upload")
async def upload_pdf(file: UploadFile):
    try:
        result = await parse_pdf(await file.read())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

**Why This Breaks:** Client sees 500 for user errors (wrong file type). Use 400/422 for client errors, 500 for server errors.

---

## Logging Strategies

### DO: Structured Logging with Context

```python
# backend/app/services/proration/rrc_data_service.py
import logging

logger = logging.getLogger(__name__)

async def download_rrc_data(well_type: str) -> dict:
    logger.info(f"Starting RRC download for {well_type}")
    
    try:
        response = await fetch_rrc_csv(well_type)
        logger.info(f"Downloaded {len(response)} bytes for {well_type}")
        return {"status": "success", "size": len(response)}
    
    except requests.RequestException as e:
        logger.error(f"RRC download failed for {well_type}: {e}")
        raise
    
    except Exception as e:
        logger.exception(f"Unexpected RRC download error for {well_type}")
        raise
```

**Why:** `logger = logging.getLogger(__name__)` includes module name in logs. Context (well_type) aids debugging.

### WARNING: Logging Sensitive Data

**The Problem:**

```python
# BAD - Logs user credentials, API keys
logger.info(f"User login: {email}, password: {password}")
logger.debug(f"API request: {api_key}")
```

**Why This Breaks:** Logs may be stored/transmitted insecurely. Credentials leak to log aggregators.

**The Fix:**

```python
# GOOD - Redact sensitive fields
logger.info(f"User login: {email}")  # No password
logger.debug(f"API request: {api_key[:8]}...")  # Partial key only
```

---

## Validation Errors

### DO: Pydantic Validation with Clear Messages

```python
# backend/app/models/proration.py
from pydantic import BaseModel, Field, field_validator

class MineralHolderRow(BaseModel):
    name: str = Field(..., min_length=1, description="Mineral holder name")
    nra: float = Field(..., gt=0, description="Net revenue acres (must be positive)")
    
    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Name cannot be empty or whitespace")
        return v.strip()
```

**Why:** Pydantic returns structured error JSON with field names and messages. Clients can display field-specific errors.

### DON'T: Manual Validation with Generic Errors

```python
# BAD - Unclear error, no field context
@router.post("/upload")
async def upload(data: dict):
    if not data.get("name"):
        raise HTTPException(400, "Invalid data")
    if data.get("nra", 0) <= 0:
        raise HTTPException(400, "Invalid data")
```

**Why This Breaks:** Client sees "Invalid data" twice, doesn't know which field failed. Use Pydantic models.

---

## Storage Fallbacks

### DO: Graceful Degradation with Logging

```python
# backend/app/services/storage_service.py
from app.core.config import settings

async def upload_file(file_path: str, content: bytes) -> str:
    """Upload to GCS, fallback to local on failure."""
    if settings.use_gcs:
        try:
            bucket = _get_gcs_bucket()
            blob = bucket.blob(file_path)
            blob.upload_from_string(content)
            logger.info(f"Uploaded to GCS: {file_path}")
            return blob.public_url
        
        except Exception as e:
            logger.warning(f"GCS upload failed for {file_path}, using local: {e}")
    
    # Local fallback
    local_path = Path(f"data/{file_path}")
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_bytes(content)
    logger.info(f"Saved to local: {local_path}")
    return f"/files/{file_path}"
```

**Why:** Warns in logs when GCS fails, but doesn't crash. Local dev works without GCP credentials.

### WARNING: Silent Fallbacks Without Logging

**The Problem:**

```python
# BAD - Fails silently, no visibility
def upload_file(file_path: str, content: bytes) -> str:
    try:
        return upload_to_gcs(file_path, content)
    except:
        return upload_to_local(file_path, content)
```

**Why This Breaks:** Production failures go unnoticed. You think GCS is working, but it's silently falling back.

**The Fix:** Always log warnings when fallback paths execute.

---

## Common Python Errors

### WARNING: Mutable Default Arguments

**The Problem:**

```python
# BAD - Shared list across calls
def add_error(message: str, errors: list[str] = []):
    errors.append(message)
    return errors

result1 = add_error("error 1")  # ["error 1"]
result2 = add_error("error 2")  # ["error 1", "error 2"]  # BUG!
```

**Why This Breaks:** Default `[]` is created once at function definition. All calls share the same list.

**The Fix:**

```python
# GOOD - New list per call
def add_error(message: str, errors: list[str] | None = None) -> list[str]:
    if errors is None:
        errors = []
    errors.append(message)
    return errors
```

### WARNING: Using 'is' for Value Comparison

**The Problem:**

```python
# BAD - Compares object identity, not value
if user_input is "admin":  # ALWAYS FALSE for non-interned strings
    grant_access()
```

**Why This Breaks:** `is` checks identity (same object in memory), not equality. Works for small ints/None, fails for strings/floats.

**The Fix:**

```python
# GOOD - Use == for value comparison
if user_input == "admin":
    grant_access()

# 'is' only for None/True/False
if value is None:
    # ...
```

---

## Testing Error Paths

### DO: Test Both Success and Failure Cases

```python
# backend/tests/test_extract.py
import pytest
from fastapi import HTTPException
from app.services.extract.pdf_parser import parse_pdf

@pytest.mark.asyncio
async def test_parse_valid_pdf():
    content = load_sample_pdf("valid.pdf")
    result = await parse_pdf(content)
    assert len(result.parties) > 0

@pytest.mark.asyncio
async def test_parse_invalid_pdf():
    content = b"Not a PDF"
    with pytest.raises(ValueError, match="Invalid PDF"):
        await parse_pdf(content)

@pytest.mark.asyncio
async def test_parse_corrupted_pdf():
    content = load_sample_pdf("corrupted.pdf")
    with pytest.raises(HTTPException) as exc_info:
        await parse_pdf(content)
    assert exc_info.value.status_code == 422
```

**Why:** Tests verify error handling works as expected. `pytest.raises` checks exception type and message.

See the **pytest** skill for async testing patterns.
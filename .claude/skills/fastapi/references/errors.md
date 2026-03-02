# Errors Reference

## Contents
- HTTPException Patterns
- Structured Error Responses
- Exception Chaining
- Logging Best Practices
- Global Exception Handlers

## HTTPException Patterns

### When to Use 400 vs 500

```python
# toolbox/backend/app/api/extract.py
@router.post("/upload")
async def upload_pdf(file: UploadFile):
    # 400: Client error (bad input)
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a PDF file.")
    
    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty file uploaded")
    
    try:
        # Process file
        result = extract_text_from_pdf(file_bytes)
        return result
    except Exception as e:
        # 500: Server error (unexpected)
        logger.exception(f"Error processing PDF: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing PDF: {str(e)}") from e
```

**WHY:**
- **400 Bad Request:** Client sent invalid data (wrong file type, empty file, invalid JSON). Client should fix input.
- **500 Internal Server Error:** Server failed unexpectedly (PDF library crash, out of memory). Client can't fix, retry might help.

### DO: Use Specific, Actionable Error Messages

```python
# GOOD - User knows exactly what's wrong and how to fix
if not file.filename.lower().endswith(".pdf"):
    raise HTTPException(
        status_code=400,
        detail="Invalid file type. Please upload a PDF file."
    )

if len(file_bytes) == 0:
    raise HTTPException(status_code=400, detail="Empty file uploaded")
```

### DON'T: Use Generic Error Messages

```python
# BAD - User has no idea what went wrong
if not valid:
    raise HTTPException(status_code=400, detail="Invalid input")  # WRONG - what's invalid?
```

**WHY THIS BREAKS:** User sees "Invalid input", doesn't know if it's the file type, size, format, or something else. Leads to support requests.

## Structured Error Responses

### Success=False Pattern for Expected Failures

```python
# toolbox/backend/app/api/extract.py
@router.post("/upload", response_model=UploadResponse)
async def upload_pdf(file: UploadFile) -> UploadResponse:
    file_bytes = await file.read()
    full_text = extract_text_from_pdf(file_bytes)
    
    # Expected failure: PDF is scanned/image-based
    if not full_text or len(full_text.strip()) < 50:
        return UploadResponse(
            message="Could not extract text from PDF",
            result=ExtractionResult(
                success=False,
                error_message="PDF appears to be empty or unreadable. The document may be scanned/image-based.",
                source_filename=file.filename
            )
        )
    
    entries = parse_exhibit_a(full_text)
    
    # Expected failure: No party entries found
    if not entries:
        return UploadResponse(
            message="No party entries found",
            result=ExtractionResult(
                success=False,
                error_message="Could not find numbered party entries (e.g., '1. Name, Address') in the document.",
                source_filename=file.filename
            )
        )
    
    # Success
    return UploadResponse(
        message=f"Successfully extracted {len(entries)} entries",
        result=ExtractionResult(success=True, entries=entries, total_count=len(entries))
    )
```

**WHY:** Expected failures (empty PDF, no matches) should return 200 with `success=False` and descriptive error. Frontend shows helpful message in UI instead of generic error toast.

**CRITICAL:** Only raise HTTPException for **unexpected** failures (crashes, invalid input). Use `success=False` for **expected** domain failures (no results, partial processing).

### DO: Distinguish Expected vs Unexpected Failures

```python
# GOOD - Expected failures return 200 with success=false
if not entries:
    return ProcessingResult(
        success=False,
        error_message="No entries found in uploaded file."
    )

# GOOD - Unexpected failures raise 500
try:
    result = process_file(file_bytes)
except Exception as e:
    logger.exception(f"Processing failed: {e}")
    raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}") from e
```

### DON'T: Raise HTTPException for Expected Domain Failures

```python
# BAD - Expected failure raised as 400 error
if not entries:
    raise HTTPException(status_code=400, detail="No entries found")  # WRONG - expected outcome
```

**WHY THIS BREAKS:** Frontend sees 400 error, shows generic error toast, user loses file context. Should return structured response with `success=false`.

## Exception Chaining

### Preserving Stack Traces with `from e`

```python
# toolbox/backend/app/api/extract.py
@router.post("/export/csv")
async def export_csv(request: ExportRequest) -> Response:
    try:
        csv_bytes = to_csv(request.entries)
        return Response(content=csv_bytes, media_type="text/csv")
    except Exception as e:
        logger.exception(f"Error generating CSV: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error generating CSV: {str(e)}"
        ) from e  # IMPORTANT: Preserves original stack trace
```

**WHY:** `raise ... from e` preserves original exception stack trace. Logs show **where** the error originated (e.g., pandas CSV writer line 342), not just the HTTP handler.

### DO: Log Before Re-Raising

```python
# GOOD - Log original exception, then raise HTTP error
try:
    result = process_data(input)
except Exception as e:
    logger.exception(f"Processing failed: {e}")  # Logs full stack trace
    raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}") from e
```

**WHY:** `logger.exception()` captures full stack trace. HTTPException only shows message to client (no internal details).

### DON'T: Swallow Exceptions

```python
# BAD - Exception disappears
try:
    result = process_data(input)
except Exception as e:
    pass  # WRONG - silent failure, impossible to debug

# BAD - Exception logged but not raised
try:
    result = process_data(input)
except Exception as e:
    logger.error(f"Error: {e}")
    return {"success": True}  # WRONG - lying to client
```

**WHY THIS BREAKS:** Errors disappear, users see "success" but data is corrupted/missing. Debugging requires time-travel.

## Logging Best Practices

### Module-Level Loggers

```python
# toolbox/backend/app/api/extract.py
import logging

logger = logging.getLogger(__name__)  # GOOD - __name__ = "app.api.extract"

@router.post("/upload")
async def upload_pdf(file: UploadFile):
    logger.info(f"Processing PDF: {file.filename}")
    # ...
    logger.info(f"Extracted {len(entries)} entries from {file.filename}")
```

**WHY:** Log messages show module name (`app.api.extract`), easy to filter logs by component.

### Log Levels

```python
# INFO: Normal operations, progress tracking
logger.info(f"Processing PDF: {file.filename}")
logger.info(f"Extracted {len(entries)} entries")

# WARNING: Recoverable issues, degraded functionality
logger.warning(f"GCS upload failed, falling back to local storage: {e}")
logger.warning(f"Firebase Admin SDK not initialized - running without server-side auth")

# ERROR: Unexpected failures, request failures
logger.error(f"Failed to initialize GCS: {e}")
logger.error(f"Token verification failed: {e}")

# EXCEPTION: Error with full stack trace (only in except blocks)
logger.exception(f"Error processing PDF: {e}")  # Includes stack trace
```

**WHY:** `logger.exception()` includes stack trace (only use in `except` blocks). `logger.error()` for known errors without stack traces.

### DO: Include Context in Log Messages

```python
# GOOD - Includes filename, entry count
logger.info(f"Extracted {len(entries)} entries ({flagged_count} flagged) from {file.filename}")

# GOOD - Includes operation details
logger.warning(f"GCS upload failed for {path}, falling back to local: {e}")
```

### DON'T: Log Sensitive Data

```python
# BAD - Logs user tokens, passwords
logger.info(f"User logged in with token: {token}")  # WRONG - security risk

# BAD - Logs full request body with PII
logger.info(f"Request: {request.json()}")  # WRONG - may contain SSN, addresses
```

**WHY THIS BREAKS:** Logs persist in monitoring systems (Stackdriver, CloudWatch), accessible to ops team. Never log credentials, tokens, PII.

## Global Exception Handlers

### Catch-All for Unhandled Errors

```python
# toolbox/backend/app/main.py
@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle 500 errors."""
    logger.exception(f"Internal server error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

@app.exception_handler(404)
async def not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle 404 errors."""
    return JSONResponse(
        status_code=404,
        content={"detail": "Resource not found"}
    )
```

**WHY:** Global handlers ensure consistent error format, log all unhandled exceptions, prevent stack trace leaks to clients.

### DO: Return Generic Messages to Clients

```python
# GOOD - Hides internal details
return JSONResponse(
    status_code=500,
    content={"detail": "Internal server error"}
)
```

**WHY:** Internal error messages might expose implementation details (file paths, library versions) useful for attackers.

### DON'T: Return Stack Traces to Clients

```python
# BAD - Exposes internal implementation
return JSONResponse(
    status_code=500,
    content={"detail": str(exc), "traceback": traceback.format_exc()}  # WRONG - security risk
)
```

**WHY THIS BREAKS:** Stack traces leak internal file paths, library versions, code structure. Use for debugging logs only.
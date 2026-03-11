# Routes Reference

## Contents
- Router Organization
- File Upload Endpoints
- Export Endpoints
- Health Check Pattern
- Form Data with JSON Options
- Async Response Patterns

## Router Organization

### Tool-per-Router Pattern

```python
# toolbox/backend/app/main.py
from app.api.extract import router as extract_router
from app.api.title import router as title_router
from app.api.proration import router as proration_router

app.include_router(extract_router, prefix="/api/extract", tags=["extract"])
app.include_router(title_router, prefix="/api/title", tags=["title"])
app.include_router(proration_router, prefix="/api/proration", tags=["proration"])
```

**WHY:** Isolates tool logic, makes routes easy to find, enables parallel development without merge conflicts.

### DO: Use Consistent Router Structure

```python
# toolbox/backend/app/api/extract.py
router = APIRouter()

@router.get("/health")
async def health_check() -> dict:
    return {"status": "healthy", "service": "extract"}

@router.post("/upload", response_model=UploadResponse)
async def upload_pdf(file: UploadFile = File(...)) -> UploadResponse:
    ...

@router.post("/export/csv")
async def export_csv(request: ExportRequest) -> Response:
    ...
```

**WHY:** Every tool has same endpoint structure (`/health`, `/upload`, `/export/*`), easier to maintain.

### DON'T: Mix Tool Logic in Routes

```python
# BAD - Route handling business logic
@router.post("/upload")
async def upload_pdf(file: UploadFile):
    file_bytes = await file.read()
    
    # WRONG: PDF extraction logic in route
    import fitz
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    
    # WRONG: Parsing logic in route
    entries = []
    for line in text.split("\n"):
        if re.match(r"^\d+\.", line):
            entries.append(parse_line(line))
    
    return {"entries": entries}
```

**WHY THIS BREAKS:**
1. Routes become untestable without mocking file uploads
2. Business logic scattered across multiple route files
3. Can't reuse extraction logic (e.g., for debugging endpoints)

**THE FIX:**

```python
# GOOD - Delegate to service layer
from app.services.extract.pdf_extractor import extract_text_from_pdf
from app.services.extract.parser import parse_exhibit_a

@router.post("/upload", response_model=UploadResponse)
async def upload_pdf(file: UploadFile) -> UploadResponse:
    file_bytes = await file.read()
    
    # Service layer handles extraction
    full_text = extract_text_from_pdf(file_bytes)
    entries = parse_exhibit_a(full_text)
    
    return UploadResponse(
        message=f"Extracted {len(entries)} entries",
        result=ExtractionResult(success=True, entries=entries)
    )
```

## File Upload Endpoints

### Shared Upload Validation Helper

Use `validate_upload()` from `core/ingestion.py` — never reimplement this per-router:

```python
# backend/app/api/extract.py
from app.core.ingestion import validate_upload

@router.post("/upload", response_model=UploadResponse)
async def upload_pdf(
    file: Annotated[UploadFile, File(description="PDF file containing Exhibit A")],
    request: Request,
) -> UploadResponse:
    # One-liner handles: filename check, extension, size limit (50MB), empty file
    file_bytes = await validate_upload(file, allowed_extensions=[".pdf"])

    full_text = extract_text_from_pdf(file_bytes)
    if not full_text or len(full_text.strip()) < 50:
        return UploadResponse(
            message="Could not extract text from PDF",
            result=ExtractionResult(
                success=False,
                error_message="PDF appears to be empty or unreadable. The document may be scanned/image-based.",
            ),
        )
```

`validate_upload` raises `HTTPException(400)` for: missing filename, wrong extension, empty file, size > 50MB. It soft-checks content-type (logs warning, doesn't reject — browsers lie).

**WHY:** All validation logic is in one place. Adding a new allowed extension is `[".pdf", ".PDF"]` not touching 5 files.

### DO: Return Structured Errors for User Feedback

```python
# GOOD - Specific, actionable error messages
if not full_text or len(full_text.strip()) < 50:
    return UploadResponse(
        message="Could not extract text from PDF",
        result=ExtractionResult(
            success=False,
            error_message="PDF appears to be empty or unreadable. The document may be scanned/image-based.",
            source_filename=file.filename
        )
    )

if not entries:
    return UploadResponse(
        message="No party entries found",
        result=ExtractionResult(
            success=False,
            error_message="Could not find numbered party entries (e.g., '1. Name, Address') in the document."
        )
    )
```

**WHY:** Users need to know **why** processing failed and **what** to do about it. Generic "processing failed" is useless.

### DON'T: Raise HTTPException for Expected Failures

```python
# BAD - Expected failures should return success=False, not 400/500
if not entries:
    raise HTTPException(status_code=400, detail="No entries found")  # WRONG
```

**WHY THIS BREAKS:** Frontend sees 400 error, shows generic error toast, user loses context. Expected failures (empty PDF, no matches) should return 200 with `success=False` and descriptive error messages.

## Export Endpoints

### Shared Export Response Helper

Use `file_response()` from `core/ingestion.py` — it infers MIME type from extension automatically:

```python
# backend/app/api/extract.py
from app.core.ingestion import file_response

@router.post("/export/csv")
async def export_csv(request: ExportRequest):
    if not request.entries:
        raise HTTPException(status_code=400, detail="No entries provided for export")
    try:
        csv_bytes = to_csv(request.entries)
        filename = f"{request.filename or 'exhibit_a_export'}.csv"
        return file_response(csv_bytes, filename)  # Infers text/csv from .csv extension
    except Exception as e:
        logger.exception("Error generating CSV: %s", e)
        raise HTTPException(status_code=500, detail=f"Error generating CSV: {e!s}") from e

@router.post("/export/excel")
async def export_excel(request: ExportRequest):
    if not request.entries:
        raise HTTPException(status_code=400, detail="No entries provided for export")
    excel_bytes = to_excel(request.entries)
    return file_response(excel_bytes, "export.xlsx")  # Infers application/vnd.openxmlformats...
```

Supported extensions and MIME types in `file_response`: `.csv` → `text/csv`, `.xlsx` → Excel MIME, `.pdf` → `application/pdf`, `.json` → `application/json`. Unknown extensions fall back to `application/octet-stream`.

**WHY:** `Content-Disposition: attachment` triggers browser download; `filename` sets the save name. Centralizing this prevents subtle MIME type bugs.

### DO: Use Correct MIME Types

```python
# GOOD - Proper MIME types for each format
CSV = "text/csv"
EXCEL = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
PDF = "application/pdf"
```

### DON'T: Return Export Data as JSON

```python
# BAD - Forces frontend to construct blob
@router.post("/export/csv")
async def export_csv(request: ExportRequest):
    csv_content = to_csv(request.entries)
    return {"content": csv_content.decode("utf-8"), "filename": "export.csv"}  # WRONG
```

**WHY THIS BREAKS:** JSON escapes special characters, breaks UTF-8 encoding, requires frontend blob construction. Return raw bytes with proper headers.

## Health Check Pattern

### Nested Health Checks

```python
# toolbox/backend/app/main.py
@app.get("/api/health")
async def health_check() -> dict:
    return {
        "status": "healthy",
        "service": "table-rock-toolbox",
        "version": settings.version,
        "tools": ["extract", "title", "proration", "revenue"]
    }

# toolbox/backend/app/api/extract.py
@router.get("/health")
async def health_check() -> dict:
    return {"status": "healthy", "service": "extract"}
```

**WHY:** Global health check for load balancers/monitoring, per-tool health checks for debugging specific tools.

## Form Data with JSON Options

### Combining File Upload with JSON Config

```python
# toolbox/backend/app/api/proration.py
@router.post("/upload", response_model=UploadResponse)
async def upload_csv(
    file: Annotated[UploadFile, File(description="CSV file")],
    options_json: Annotated[Optional[str], Form(description="Processing options as JSON")] = None
) -> UploadResponse:
    # Read file
    file_bytes = await file.read()
    
    # Parse options from JSON string
    if options_json:
        try:
            options_dict = json.loads(options_json)
            # Handle empty string as None
            if options_dict.get("well_type_override") == "":
                options_dict["well_type_override"] = None
            options = ProcessingOptions(**options_dict)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Invalid options JSON: {e}, using defaults")
            options = ProcessingOptions()
    else:
        options = ProcessingOptions()
    
    result = await process_csv(file_bytes, file.filename, options)
```

**WHY:** Can't use Pydantic model directly in multipart/form-data requests. JSON string in form field lets you send complex config with file upload.

### DO: Validate and Provide Defaults

```python
# GOOD - Gracefully handle invalid JSON, provide defaults
try:
    options = ProcessingOptions(**json.loads(options_json))
except (json.JSONDecodeError, ValueError):
    logger.warning("Invalid options, using defaults")
    options = ProcessingOptions()
```

### DON'T: Let Invalid JSON Crash the Endpoint

```python
# BAD - Unhandled JSON parsing errors
options_dict = json.loads(options_json)  # Crashes on invalid JSON
options = ProcessingOptions(**options_dict)
```

## Async Response Patterns

### Fire-and-Forget Background Tasks

```python
# toolbox/backend/app/api/proration.py
@router.post("/rrc/download", response_model=RRCDownloadResponse)
async def download_rrc_data() -> RRCDownloadResponse:
    success, message, stats = rrc_data_service.download_all_data()
    
    # Fire-and-forget database sync
    if success:
        async def _background_sync():
            try:
                sync_result = await rrc_data_service.sync_to_database("both")
                if sync_result.get("success"):
                    logger.info(f"Background sync complete: {sync_result['message']}")
                else:
                    logger.warning(f"Background sync failed: {sync_result.get('message')}")
            except Exception as e:
                logger.warning(f"Background sync failed (non-critical): {e}")
        
        asyncio.create_task(_background_sync())
    
    return RRCDownloadResponse(success=success, message=message, oil_rows=stats.get("oil_rows", 0))
```

**WHY:** CSV download returns immediately, DB sync (30+ seconds for 40k rows) runs in background. User doesn't wait.

**WARNING:** Background tasks must handle exceptions internally or they crash silently. Always wrap in try/except with logging.
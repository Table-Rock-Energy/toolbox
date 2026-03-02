---
name: fastapi
description: |
  Builds async FastAPI routes, Pydantic validation, and error handling for Table Rock Tools backend.
  Use when: building API endpoints, processing file uploads, validating requests, handling responses, managing async operations, configuring middleware, implementing authentication, or structuring backend services.
allowed-tools: Read, Edit, Write, Glob, Grep, Bash, mcp__plugin_context7_context7__resolve-library-id, mcp__plugin_context7_context7__query-docs
---

# FastAPI Skill

FastAPI backend for Table Rock Tools with tool-per-module architecture. Each tool (Extract, Title, Proration, Revenue) has dedicated routes, Pydantic models, and service layers. GCS/Firestore integration with local fallbacks, Firebase auth with JSON allowlist, APScheduler for cron jobs, async-first patterns.

## Quick Start

### Basic Route Structure

```python
from fastapi import APIRouter, File, HTTPException, UploadFile
from app.models.extract import UploadResponse, ExtractionResult

router = APIRouter()

@router.post("/upload", response_model=UploadResponse)
async def upload_pdf(file: UploadFile = File(...)) -> UploadResponse:
    # Validate file
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Invalid file type")
    
    # Process
    file_bytes = await file.read()
    result = process_pdf(file_bytes)
    
    return UploadResponse(message="Success", result=result)
```

### Pydantic Response Models

```python
from pydantic import BaseModel, Field

class ExtractionResult(BaseModel):
    success: bool = Field(..., description="Whether extraction succeeded")
    entries: list[PartyEntry] = Field(default_factory=list)
    total_count: int = Field(0, description="Total entries extracted")
    error_message: Optional[str] = None
```

### File Export Pattern

```python
@router.post("/export/csv")
async def export_csv(request: ExportRequest) -> Response:
    if not request.entries:
        raise HTTPException(status_code=400, detail="No entries provided")
    
    csv_bytes = to_csv(request.entries)
    filename = f"{request.filename or 'export'}.csv"
    
    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
```

## Key Concepts

| Concept | Usage | Example |
|---------|-------|---------|
| Router prefixing | Tool namespacing | `app.include_router(extract_router, prefix="/api/extract")` |
| Async routes | All handlers | `async def upload_pdf(...)` |
| Pydantic Settings | Config management | `class Settings(BaseSettings)` with `@property` |
| Lazy initialization | Firebase/GCS clients | Import only when needed to avoid startup errors |
| Fire-and-forget tasks | Background jobs | `asyncio.create_task(_background_sync())` |
| Startup/shutdown hooks | Scheduler, DB init | `@app.on_event("startup")` |

## Common Patterns

### File Upload with Validation

**When:** Processing user-uploaded files (PDF, CSV, Excel)

```python
async def upload_csv(file: UploadFile) -> UploadResponse:
    # Validate filename
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Invalid file type")
    
    # Validate content type
    if file.content_type and "csv" not in file.content_type.lower():
        if file.content_type not in ["text/csv", "application/csv"]:
            raise HTTPException(status_code=400, detail="Invalid content type")
    
    # Read and validate size
    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty file uploaded")
    
    # Process in service layer
    result = await process_csv(file_bytes, file.filename)
    return UploadResponse(message="Success", result=result)
```

### Lazy Client Initialization

**When:** Working with GCS, Firestore, Firebase Admin SDK

```python
_client: Optional[storage.Client] = None
_initialized = False

def _init_client(self) -> bool:
    if self._initialized:
        return self._client is not None
    
    self._initialized = True
    
    if not GCS_AVAILABLE:
        return False
    
    try:
        self._client = storage.Client(project=settings.gcs_project_id)
        return True
    except Exception as e:
        logger.error(f"Failed to initialize: {e}")
        self._client = None
        return False
```

### Background Task Pattern

**When:** Long-running operations that shouldn't block the response

```python
@router.post("/rrc/download")
async def download_rrc_data() -> RRCDownloadResponse:
    success, message, stats = rrc_data_service.download_all_data()
    
    # Fire-and-forget DB sync
    if success:
        async def _background_sync():
            try:
                await rrc_data_service.sync_to_database("both")
            except Exception as e:
                logger.warning(f"Background sync failed: {e}")
        
        asyncio.create_task(_background_sync())
    
    return RRCDownloadResponse(success=success, message=message)
```

## See Also

- [routes](references/routes.md) - Router setup, endpoint patterns, file handling
- [services](references/services.md) - Service layer architecture, storage fallbacks
- [database](references/database.md) - Firestore operations, batch writes, RRC data
- [auth](references/auth.md) - Firebase token verification, allowlist management
- [errors](references/errors.md) - HTTPException patterns, error logging, validation

## Related Skills

- **python** - Core language patterns, async/await, type hints
- **pydantic** - Model validation, settings management, Field descriptors
- **google-cloud-storage** - GCS client usage, signed URLs, fallback patterns
- **firestore** - Async client, batch operations, queries
- **firebase** - Admin SDK, token verification
- **apscheduler** - Cron job scheduling, async tasks

## Documentation Resources

> Fetch latest FastAPI documentation with Context7.

**How to use Context7:**
1. Use `mcp__plugin_context7_context7__resolve-library-id` to search for "fastapi"
2. **Prefer website documentation** (IDs starting with `/websites/`) over source code
3. Query with `mcp__plugin_context7_context7__query-docs` using the resolved library ID

**Library ID:** `/fastapi/fastapi` or `/websites/fastapi.tiangolo.com` _(resolve using mcp__plugin_context7_context7__resolve-library-id, prefer /websites/)_

**Recommended Queries:**
- "fastapi async route handlers best practices"
- "fastapi file upload validation patterns"
- "fastapi dependency injection with settings"
- "fastapi background tasks and lifecycle events"
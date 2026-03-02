---
name: google-cloud-storage
description: |
  Manages GCS file uploads/downloads with transparent local filesystem fallback for Table Rock TX Tools.
  Use when: implementing file storage, handling uploads, configuring storage backends, debugging GCS failures, or setting up local development without GCS credentials.
allowed-tools: Read, Edit, Write, Glob, Grep, Bash, mcp__plugin_context7_context7__resolve-library-id, mcp__plugin_context7_context7__query-docs
---

# Google Cloud Storage Skill

This project uses GCS as the primary storage backend with **transparent fallback** to local filesystem. The `StorageService` (`backend/app/services/storage_service.py`) abstracts storage operations so the rest of the codebase never needs to check GCS availability. All uploads, downloads, and file existence checks automatically fall back to `backend/data/` when GCS is unavailable (local dev without credentials).

**Critical architectural decision:** `config.use_gcs` returns `True` when `GCS_BUCKET_NAME` is set (always by default), but actual GCS availability is determined at **runtime**. This means you cannot rely on the config flag alone—always handle `None` returns from signed URLs and provide local fallbacks.

## Quick Start

### Upload with Automatic Fallback

```python
from app.services.storage_service import StorageService

storage = StorageService()

# Try GCS first, fall back to local on failure
file_path = await storage.upload_file(
    file_content=pdf_bytes,
    filename="exhibit_a.pdf",
    subfolder="uploads"
)
# Returns: "uploads/exhibit_a.pdf" (works regardless of GCS availability)
```

### Download with Dual-Location Check

```python
# Checks GCS first, then local filesystem
file_content = await storage.download_file("uploads/exhibit_a.pdf")

# Check existence across both storage backends
exists = await storage.file_exists("rrc-data/oil_proration.csv")
```

### Signed URLs with Local Fallback

```python
# WARNING: Returns None when GCS is unavailable
signed_url = storage.get_signed_url("uploads/exhibit_a.pdf", expiration_minutes=60)

if signed_url is None:
    # ALWAYS provide a local fallback route
    local_url = f"/api/files/download?path=uploads/exhibit_a.pdf"
    return {"download_url": local_url}
```

## Key Concepts

| Concept | Usage | Example |
|---------|-------|---------|
| Transparent Fallback | All operations try GCS → local automatically | `upload_file()` returns path regardless of backend |
| Runtime Availability | GCS availability determined at operation time, not config time | `config.use_gcs` may be `True` but GCS still fails |
| Signed URL None-Safety | `get_signed_url()` returns `None` when GCS unavailable | Always check `if url is None:` before using |
| Subfolder Organization | Files organized by tool/purpose | `uploads/`, `rrc-data/`, `exports/` |
| Local Storage Root | `backend/data/` is the local filesystem fallback | Created automatically if missing |

## Common Patterns

### File Upload in API Route

**When:** Processing user uploads (PDFs, CSVs, Excel)

```python
from fastapi import UploadFile
from app.services.storage_service import StorageService

storage = StorageService()

@router.post("/upload")
async def upload_document(file: UploadFile):
    content = await file.read()
    
    # Automatically falls back to local if GCS unavailable
    stored_path = await storage.upload_file(
        file_content=content,
        filename=file.filename,
        subfolder="extract/uploads"
    )
    
    return {"file_path": stored_path}
```

### RRC Data Download and Storage

**When:** Monthly RRC data sync (see `backend/app/services/proration/rrc_data_service.py:127`)

```python
# Download CSV from RRC website
csv_data = download_rrc_csv(well_type)

# Save to storage (GCS or local)
file_path = await storage.upload_file(
    file_content=csv_data.encode('utf-8'),
    filename=f"{well_type.lower()}_proration.csv",
    subfolder="rrc-data"
)
# Returns: "rrc-data/oil_proration.csv"
```

### Export File Download Endpoint

**When:** Providing download links for generated exports

```python
@router.get("/download")
async def download_export(path: str):
    # Get signed URL (may be None)
    signed_url = storage.get_signed_url(path, expiration_minutes=15)
    
    if signed_url:
        return RedirectResponse(url=signed_url)
    else:
        # Fallback: serve from local filesystem
        file_content = await storage.download_file(path)
        return Response(content=file_content, media_type="application/pdf")
```

## See Also

- [patterns](references/patterns.md) - Upload/download patterns, error handling, GCS setup
- [types](references/types.md) - StorageService methods, config properties
- [modules](references/modules.md) - Storage service architecture, integration points
- [errors](references/errors.md) - GCS failures, credential errors, fallback scenarios

## Related Skills

- **python** - Async/await patterns, type hints, exception handling
- **fastapi** - File upload handling, dependency injection, response types
- **pydantic** - Settings management for GCS configuration
- **firestore** - Metadata persistence for uploaded files

## Documentation Resources

> Fetch latest Google Cloud Storage Python client documentation with Context7.

**How to use Context7:**
1. Use `mcp__plugin_context7_context7__resolve-library-id` to search for "google-cloud-storage python"
2. **Prefer website documentation** (IDs starting with `/websites/`) over source code repositories when available
3. Query with `mcp__plugin_context7_context7__query-docs` using the resolved library ID

**Library ID:** `/google-cloud/python-storage` _(resolve using mcp__plugin_context7_context7__resolve-library-id, prefer /websites/ when available)_

**Recommended Queries:**
- "google-cloud-storage python client upload blob"
- "google-cloud-storage python signed urls"
- "google-cloud-storage python bucket configuration"
"""Generic ingestion engine for file upload, validation, persistence, and export.

Provides reusable building blocks so new tools can be added with minimal
boilerplate.  Each tool still owns its own processing logic, models, and
export column definitions -- this module handles the repetitive scaffolding
around those.

Usage example (in a new tool's API router):

    from app.core.ingestion import validate_upload, persist_job_result, file_response

    @router.post("/upload")
    async def upload(file: UploadFile):
        file_bytes = await validate_upload(file, allowed_extensions=[".pdf"])
        result = my_tool_specific_processing(file_bytes, file.filename)
        result.job_id = await persist_job_result(
            tool="my_tool",
            filename=file.filename,
            file_size=len(file_bytes),
            entries=[e.model_dump() for e in result.entries],
            total=len(result.entries),
            success=len(result.entries),
            errors=0,
        )
        return UploadResponse(message="Done", result=result)

    @router.post("/export/csv")
    async def export_csv(request: ExportRequest):
        csv_bytes = my_to_csv(request.entries)
        return file_response(csv_bytes, "export.csv", "text/csv")
"""

from __future__ import annotations

import logging
from typing import Optional, Sequence

from fastapi import HTTPException, UploadFile
from fastapi.responses import Response

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# File validation
# ---------------------------------------------------------------------------

CONTENT_TYPE_MAP: dict[str, list[str]] = {
    ".pdf": ["application/pdf"],
    ".csv": ["text/csv", "application/csv", "text/plain"],
    ".xlsx": [
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ],
    ".xls": ["application/vnd.ms-excel"],
}


async def validate_upload(
    file: UploadFile,
    *,
    allowed_extensions: Sequence[str],
    max_size_bytes: int = 50 * 1024 * 1024,
) -> bytes:
    """Validate an uploaded file and return its bytes.

    Checks:
    - filename is present
    - extension is in *allowed_extensions*
    - content-type is plausible (if set by the client)
    - file is not empty
    - file does not exceed *max_size_bytes*

    Raises ``HTTPException(400)`` on any validation failure.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    filename_lower = file.filename.lower()
    ext_match = any(filename_lower.endswith(ext) for ext in allowed_extensions)
    if not ext_match:
        exts = ", ".join(allowed_extensions)
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {exts}",
        )

    # Soft content-type check (browsers may send wrong types)
    if file.content_type:
        allowed_ct: list[str] = []
        for ext in allowed_extensions:
            allowed_ct.extend(CONTENT_TYPE_MAP.get(ext, []))
        if allowed_ct and not any(ct in file.content_type.lower() for ct in allowed_ct):
            # Only warn -- don't reject since content-type is unreliable
            logger.debug(
                "Unexpected content-type %s for %s", file.content_type, file.filename
            )

    file_bytes = await file.read()

    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty file uploaded")

    if len(file_bytes) > max_size_bytes:
        max_mb = max_size_bytes / (1024 * 1024)
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds maximum size of {max_mb:.0f} MB",
        )

    return file_bytes


# ---------------------------------------------------------------------------
# Firestore job persistence (fire-and-forget)
# ---------------------------------------------------------------------------

async def persist_job_result(
    *,
    tool: str,
    filename: str,
    file_size: Optional[int] = None,
    entries: list[dict],
    total: int,
    success: int,
    errors: int,
    collection: Optional[str] = None,
    user_id: Optional[str] = None,
    user_name: Optional[str] = None,
    job_id: Optional[str] = None,
) -> Optional[str]:
    """Persist processing results to Firestore.

    Returns the job ID on success, ``None`` if Firestore is unavailable.
    This is intentionally fire-and-forget -- a Firestore failure never
    causes the upload to fail for the user.
    """
    try:
        from app.services.firestore_service import (
            create_job,
            update_job_status,
        )

        job = await create_job(
            tool=tool,
            source_filename=filename,
            source_file_size=file_size,
            user_id=user_id,
            user_name=user_name,
            job_id=job_id,
        )
        job_id = job["id"]

        # Save entries to the tool-specific collection
        if entries:
            await _save_entries(tool, job_id, entries, collection)

        await update_job_status(
            job_id,
            status="completed",
            total_count=total,
            success_count=success,
            error_count=errors,
        )

        return job_id
    except Exception as exc:
        logger.warning("Firestore persistence failed (non-critical): %s", exc)
        return None


async def _save_entries(
    tool: str,
    job_id: str,
    entries: list[dict],
    collection: Optional[str] = None,
) -> None:
    """Route to the correct Firestore save function for a tool."""
    from app.services.firestore_service import (
        save_extract_entries,
        save_title_entries,
        save_proration_rows,
        save_revenue_statement,
    )

    save_map = {
        "extract": save_extract_entries,
        "title": save_title_entries,
        "proration": save_proration_rows,
    }

    saver = save_map.get(tool)
    if saver:
        await saver(job_id, entries)
    elif tool == "revenue":
        # Revenue saves each statement individually
        for entry in entries:
            await save_revenue_statement(job_id, entry)
    elif tool == "ghl_prep":
        # GHL Prep entries are transformations, not persistent entities
        # Job metadata is sufficient - skip entry saving
        pass


# ---------------------------------------------------------------------------
# Export response helpers
# ---------------------------------------------------------------------------

MEDIA_TYPES = {
    "csv": "text/csv",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "xls": "application/vnd.ms-excel",
    "pdf": "application/pdf",
    "json": "application/json",
}


def file_response(
    content: bytes,
    filename: str,
    media_type: Optional[str] = None,
    extra_headers: Optional[dict[str, str]] = None,
) -> Response:
    """Build a ``Response`` for a downloadable file export.

    If *media_type* is ``None`` it is inferred from the filename extension.
    Optional *extra_headers* are merged into the response headers.
    """
    if media_type is None:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        media_type = MEDIA_TYPES.get(ext, "application/octet-stream")

    response_headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    if extra_headers:
        response_headers.update(extra_headers)

    return Response(
        content=content,
        media_type=media_type,
        headers=response_headers,
    )

"""API routes for Title Processing Tool."""

from __future__ import annotations

import logging
import re
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from app.models.title import (
    ExportRequest,
    FilterOptions,
    OwnerEntry,
    ProcessingResult,
    UploadResponse,
)
from app.services.title.csv_processor import process_csv
from app.services.title.excel_processor import process_excel
from app.services.title.export_service import generate_filename, to_csv, to_excel, to_mineral_excel

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health_check() -> dict:
    """Health check endpoint for title tool."""
    return {"status": "healthy", "service": "title"}


@router.post("/upload", response_model=UploadResponse)
async def upload_file(
    file: Annotated[UploadFile, File(description="Excel or CSV file to process")],
) -> UploadResponse:
    """
    Upload an Excel or CSV file and extract owner entries.

    Args:
        file: Excel (.xlsx, .xls) or CSV file upload

    Returns:
        UploadResponse with processing results
    """
    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    filename_lower = file.filename.lower()
    is_excel = filename_lower.endswith((".xlsx", ".xls"))
    is_csv = filename_lower.endswith(".csv")

    if not is_excel and not is_csv:
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Please upload an Excel (.xlsx, .xls) or CSV file.",
        )

    try:
        # Read file bytes
        file_bytes = await file.read()

        if len(file_bytes) == 0:
            raise HTTPException(status_code=400, detail="Empty file uploaded")

        # Process based on file type
        logger.info(f"Processing file: {file.filename}")

        if is_excel:
            entries = process_excel(file_bytes, file.filename)
        else:
            entries = process_csv(file_bytes, file.filename)

        if not entries:
            return UploadResponse(
                message="No owner entries found",
                result=ProcessingResult(
                    success=False,
                    error_message="Could not find any owner entries in the file. "
                    "Please check the file format.",
                    source_filename=file.filename,
                ),
            )

        # Calculate statistics
        duplicate_count = sum(1 for e in entries if e.duplicate_flag)
        no_address_count = sum(1 for e in entries if not e.has_address)
        sections = list(set(e.legal_description for e in entries))

        logger.info(
            f"Extracted {len(entries)} entries ({duplicate_count} duplicates, "
            f"{no_address_count} without address) from {file.filename}"
        )

        result = ProcessingResult(
            success=True,
            entries=entries,
            total_count=len(entries),
            duplicate_count=duplicate_count,
            no_address_count=no_address_count,
            sections=sorted(sections),
            source_filename=file.filename,
        )

        # Persist to Firestore (non-blocking, failure doesn't break upload)
        try:
            from app.services.firestore_service import (
                create_job,
                save_title_entries,
                update_job_status,
            )

            job = await create_job(
                tool="title",
                source_filename=file.filename,
                source_file_size=len(file_bytes),
            )
            job_id = job["id"]
            result.job_id = job_id

            await save_title_entries(
                job_id, [e.model_dump() for e in entries]
            )
            await update_job_status(
                job_id,
                status="completed",
                total_count=len(entries),
                success_count=len(entries),
                error_count=duplicate_count,
            )
        except Exception as fs_err:
            logger.warning(f"Firestore persistence failed (non-critical): {fs_err}")

        return UploadResponse(
            message=f"Successfully processed {len(entries)} entries",
            result=result,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error processing file: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing file: {str(e)}",
        ) from e


@router.post("/preview")
async def preview_export(
    request: ExportRequest,
) -> list[OwnerEntry]:
    """
    Preview filtered results before export.

    Args:
        request: Export request with entries and filter options

    Returns:
        Filtered list of owner entries
    """
    from app.services.title.export_service import apply_filters

    if not request.entries:
        return []

    return apply_filters(request.entries, request.filters)


@router.post("/export/csv")
async def export_csv(request: ExportRequest) -> Response:
    """
    Export owner entries to CSV format.

    Args:
        request: Export request with entries and filter options

    Returns:
        CSV file download
    """
    if not request.entries:
        raise HTTPException(status_code=400, detail="No entries provided for export")

    try:
        csv_bytes = to_csv(request.entries, request.filters)
        filename = generate_filename(request.filename or "title_export", "csv")

        return Response(
            content=csv_bytes,
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )

    except Exception as e:
        logger.exception(f"Error generating CSV: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error generating CSV: {str(e)}",
        ) from e


@router.post("/export/excel")
async def export_excel(request: ExportRequest) -> Response:
    """
    Export owner entries to Excel format.

    Args:
        request: Export request with entries and filter options

    Supports format_type parameter:
        - 'standard': Default title export format
        - 'mineral': CRM-compatible mineral format

    Returns:
        Excel file download
    """
    if not request.entries:
        raise HTTPException(status_code=400, detail="No entries provided for export")

    try:
        # Check if mineral format is requested
        if request.format_type == "mineral":
            excel_bytes = to_mineral_excel(request.entries, request.filters)
            filename = generate_filename(
                (request.filename or "title_export") + "_mineral", "xlsx"
            )
        else:
            excel_bytes = to_excel(request.entries, request.filters)
            filename = generate_filename(request.filename or "title_export", "xlsx")

        return Response(
            content=excel_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )

    except Exception as e:
        logger.exception(f"Error generating Excel: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error generating Excel: {str(e)}",
        ) from e


class EnrichRequest(BaseModel):
    """Request to enrich title entries."""
    entries: list[dict]


@router.post("/enrich")
async def enrich_entries(request: EnrichRequest):
    """Enrich title entries with address validation, name cleaning, and splitting.

    Returns a streaming response with newline-delimited JSON progress events.
    """
    if not request.entries:
        raise HTTPException(status_code=400, detail="No entries provided")

    from app.services.enrichment_service import enrich_entries as run_enrichment

    return StreamingResponse(
        run_enrichment("title", request.entries),
        media_type="application/x-ndjson",
    )


@router.post("/validate")
async def validate_entries(entries: list[OwnerEntry]) -> dict:
    """
    Validate entries against the output schema.

    Args:
        entries: List of owner entries to validate

    Returns:
        Validation results with any issues found
    """
    issues: list[dict] = []

    for i, entry in enumerate(entries):
        entry_issues = []

        # Check required fields
        if not entry.full_name:
            entry_issues.append("Missing full name")

        if not entry.legal_description:
            entry_issues.append("Missing legal description")

        # Check state format
        if entry.state and len(entry.state) != 2:
            entry_issues.append(f"Invalid state format: {entry.state}")

        # Check ZIP format
        if entry.zip_code:
            if not re.match(r"^\d{5}(-\d{4})?$", entry.zip_code):
                entry_issues.append(f"Invalid ZIP format: {entry.zip_code}")

        if entry_issues:
            issues.append({
                "index": i,
                "name": entry.full_name,
                "issues": entry_issues,
            })

    return {
        "valid": len(issues) == 0,
        "total_entries": len(entries),
        "issues_count": len(issues),
        "issues": issues,
    }

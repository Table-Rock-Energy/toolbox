"""API routes for Title Processing Tool."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Annotated, Optional
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.ingestion import file_response, persist_job_result, validate_upload
from app.models.title import (
    ExportRequest,
    OwnerEntry,
    ProcessingResult,
    UploadResponse,
)
from app.services.title.csv_processor import process_csv
from app.services.title.excel_processor import process_excel
from app.services.title.export_service import (
    apply_filters,
    generate_filename,
    to_csv,
    to_excel,
    to_mineral_csv,
    to_mineral_excel,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health_check() -> dict:
    """Health check endpoint for title tool."""
    return {"status": "healthy", "service": "title"}


@router.post("/upload", response_model=UploadResponse)
async def upload_file(
    file: Annotated[UploadFile, File(description="Excel or CSV file to process")],
    request: Request,
) -> UploadResponse:
    """Upload an Excel or CSV file and extract owner entries."""
    file_bytes = await validate_upload(
        file, allowed_extensions=[".xlsx", ".xls", ".csv"]
    )

    try:
        logger.info("Processing file: %s", file.filename)

        filename_lower = file.filename.lower()
        is_excel = filename_lower.endswith((".xlsx", ".xls"))

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

        duplicate_count = sum(1 for e in entries if e.duplicate_flag)
        no_address_count = sum(1 for e in entries if not e.has_address)
        sections = sorted(set(e.legal_description for e in entries))

        logger.info(
            "Extracted %d entries (%d duplicates, %d without address) from %s",
            len(entries), duplicate_count, no_address_count, file.filename,
        )

        # Generate job_id locally so we can return it immediately
        job_id = str(uuid4())

        result = ProcessingResult(
            success=True,
            entries=entries,
            total_count=len(entries),
            duplicate_count=duplicate_count,
            no_address_count=no_address_count,
            sections=sections,
            source_filename=file.filename,
            job_id=job_id,
        )

        # Extract user info from headers
        user_email = request.headers.get("x-user-email") or None
        user_name = request.headers.get("x-user-name") or None

        # Fire-and-forget: persist to Firestore in background
        entry_dicts = [e.model_dump() for e in entries]
        asyncio.create_task(_persist_in_background(
            job_id=job_id,
            filename=file.filename,
            file_size=len(file_bytes),
            entries=entry_dicts,
            total=len(entries),
            success=len(entries),
            errors=duplicate_count,
            user_id=user_email,
            user_name=user_name,
        ))

        return UploadResponse(
            message=f"Successfully processed {len(entries)} entries",
            result=result,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error processing file: %s", e)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing file: {e!s}",
        ) from e


async def _persist_in_background(
    *,
    job_id: str,
    filename: str,
    file_size: int,
    entries: list[dict],
    total: int,
    success: int,
    errors: int,
    user_id: Optional[str] = None,
    user_name: Optional[str] = None,
) -> None:
    """Background task for Firestore persistence."""
    try:
        await persist_job_result(
            tool="title",
            filename=filename,
            file_size=file_size,
            entries=entries,
            total=total,
            success=success,
            errors=errors,
            user_id=user_id,
            user_name=user_name,
            job_id=job_id,
        )
    except Exception as e:
        logger.warning("Background persistence failed: %s", e)

    # ETL pipeline disabled - will be replaced with Supabase


@router.post("/preview")
async def preview_export(request: ExportRequest) -> list[OwnerEntry]:
    """Preview filtered results before export."""
    if not request.entries:
        return []
    return apply_filters(request.entries, request.filters)


@router.post("/export/csv")
async def export_csv(request: ExportRequest):
    """Export owner entries to CSV format."""
    if not request.entries:
        raise HTTPException(status_code=400, detail="No entries provided for export")

    try:
        if request.format_type == "mineral":
            csv_bytes = to_mineral_csv(
                request.entries,
                request.filters,
                county=request.county or "",
                campaign_name=request.campaign_name or "",
            )
            filename = generate_filename(
                (request.filename or "title_export") + "_mineral", "csv"
            )
        else:
            csv_bytes = to_csv(request.entries, request.filters)
            filename = generate_filename(request.filename or "title_export", "csv")
        return file_response(csv_bytes, filename)
    except Exception as e:
        logger.exception("Error generating CSV: %s", e)
        raise HTTPException(status_code=500, detail=f"Error generating CSV: {e!s}") from e


@router.post("/export/excel")
async def export_excel(request: ExportRequest):
    """Export owner entries to Excel format."""
    if not request.entries:
        raise HTTPException(status_code=400, detail="No entries provided for export")

    try:
        if request.format_type == "mineral":
            excel_bytes = to_mineral_excel(
                request.entries,
                request.filters,
                county=request.county or "",
                campaign_name=request.campaign_name or "",
            )
            filename = generate_filename(
                (request.filename or "title_export") + "_mineral", "xlsx"
            )
        else:
            excel_bytes = to_excel(request.entries, request.filters)
            filename = generate_filename(request.filename or "title_export", "xlsx")

        return file_response(excel_bytes, filename)
    except Exception as e:
        logger.exception("Error generating Excel: %s", e)
        raise HTTPException(status_code=500, detail=f"Error generating Excel: {e!s}") from e


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

    from app.services.data_enrichment_pipeline import enrich_entries as run_enrichment

    return StreamingResponse(
        run_enrichment("title", request.entries),
        media_type="application/x-ndjson",
    )


@router.post("/validate")
async def validate_entries(entries: list[OwnerEntry]) -> dict:
    """Validate entries against the output schema."""
    issues: list[dict] = []

    for i, entry in enumerate(entries):
        entry_issues = []

        if not entry.full_name:
            entry_issues.append("Missing full name")

        if not entry.legal_description:
            entry_issues.append("Missing legal description")

        if entry.state and len(entry.state) != 2:
            entry_issues.append(f"Invalid state format: {entry.state}")

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

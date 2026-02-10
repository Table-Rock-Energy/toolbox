"""API routes for OCC Exhibit A PDF extraction (extract tool)."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.ingestion import file_response, persist_job_result, validate_upload
from app.models.extract import (
    ExportRequest,
    ExtractionResult,
    PartyEntry,
    UploadResponse,
)
from app.services.extract.export_service import to_csv, to_excel
from app.services.extract.name_parser import parse_name
from app.services.extract.parser import parse_exhibit_a
from app.services.extract.pdf_extractor import extract_party_list, extract_text_from_pdf

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health_check() -> dict:
    """Health check endpoint for extract tool."""
    return {"status": "healthy", "service": "extract"}


@router.post("/upload", response_model=UploadResponse)
async def upload_pdf(
    file: Annotated[UploadFile, File(description="PDF file containing Exhibit A")],
) -> UploadResponse:
    """Upload a PDF file and extract party entries from Exhibit A."""
    file_bytes = await validate_upload(file, allowed_extensions=[".pdf"])

    try:
        # Extract text from PDF
        logger.info("Processing PDF: %s", file.filename)
        full_text = extract_text_from_pdf(file_bytes)

        if not full_text or len(full_text.strip()) < 50:
            return UploadResponse(
                message="Could not extract text from PDF",
                result=ExtractionResult(
                    success=False,
                    error_message="PDF appears to be empty or unreadable. "
                    "The document may be scanned/image-based.",
                    source_filename=file.filename,
                ),
            )

        # Extract party list section (or full text if no section found)
        party_text = extract_party_list(full_text)
        entries = parse_exhibit_a(party_text)

        if not entries:
            return UploadResponse(
                message="No party entries found",
                result=ExtractionResult(
                    success=False,
                    error_message="Could not find numbered party entries "
                    "(e.g., '1. Name, Address') in the document.",
                    source_filename=file.filename,
                ),
            )

        # Populate parsed name fields for individuals
        for entry in entries:
            parsed = parse_name(entry.primary_name, entry.entity_type.value)
            if parsed.is_person:
                entry.first_name = parsed.first_name or None
                entry.middle_name = parsed.middle_name or None
                entry.last_name = parsed.last_name or None
                entry.suffix = parsed.suffix or None

        flagged_count = sum(1 for e in entries if e.flagged)

        logger.info(
            "Extracted %d entries (%d flagged) from %s",
            len(entries), flagged_count, file.filename,
        )

        result = ExtractionResult(
            success=True,
            entries=entries,
            total_count=len(entries),
            flagged_count=flagged_count,
            source_filename=file.filename,
        )

        # Persist to Firestore (non-blocking)
        job_id = await persist_job_result(
            tool="extract",
            filename=file.filename,
            file_size=len(file_bytes),
            entries=[e.model_dump() for e in entries],
            total=len(entries),
            success=len(entries),
            errors=flagged_count,
        )
        if job_id:
            result.job_id = job_id

        # Feed ETL pipeline (non-blocking, failure doesn't break upload)
        try:
            from app.services.etl.pipeline import process_extract_entries
            await process_extract_entries(
                job_id=result.job_id or "",
                source_filename=file.filename,
                entries=[e.model_dump() for e in entries],
            )
        except Exception as etl_err:
            logger.warning(f"ETL pipeline failed (non-critical): {etl_err}")

        return UploadResponse(
            message=f"Successfully extracted {len(entries)} entries",
            result=result,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error processing PDF: %s", e)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing PDF: {e!s}",
        ) from e


@router.post("/export/csv")
async def export_csv(request: ExportRequest):
    """Export party entries to CSV format."""
    if not request.entries:
        raise HTTPException(status_code=400, detail="No entries provided for export")

    try:
        csv_bytes = to_csv(request.entries)
        filename = f"{request.filename or 'exhibit_a_export'}.csv"
        return file_response(csv_bytes, filename)
    except Exception as e:
        logger.exception("Error generating CSV: %s", e)
        raise HTTPException(status_code=500, detail=f"Error generating CSV: {e!s}") from e


@router.post("/export/excel")
async def export_excel(request: ExportRequest):
    """Export party entries to Excel format."""
    if not request.entries:
        raise HTTPException(status_code=400, detail="No entries provided for export")

    try:
        excel_bytes = to_excel(request.entries)
        filename = f"{request.filename or 'exhibit_a_export'}.xlsx"
        return file_response(excel_bytes, filename)
    except Exception as e:
        logger.exception("Error generating Excel: %s", e)
        raise HTTPException(status_code=500, detail=f"Error generating Excel: {e!s}") from e


class EnrichRequest(BaseModel):
    """Request to enrich extracted entries."""
    entries: list[dict]


@router.post("/enrich")
async def enrich_entries(request: EnrichRequest):
    """Enrich extracted party entries with address validation, name cleaning, and splitting.

    Returns a streaming response with newline-delimited JSON progress events.
    """
    if not request.entries:
        raise HTTPException(status_code=400, detail="No entries provided")

    from app.services.data_enrichment_pipeline import enrich_entries as run_enrichment

    return StreamingResponse(
        run_enrichment("extract", request.entries),
        media_type="application/x-ndjson",
    )


@router.post("/parse-entries", response_model=list[PartyEntry])
async def parse_entries(text: str) -> list[PartyEntry]:
    """Parse raw Exhibit A text into party entries."""
    if not text or len(text.strip()) < 10:
        raise HTTPException(status_code=400, detail="Text is too short to parse")

    try:
        entries = parse_exhibit_a(text)
        return entries
    except Exception as e:
        logger.exception("Error parsing text: %s", e)
        raise HTTPException(status_code=500, detail=f"Error parsing text: {e!s}") from e

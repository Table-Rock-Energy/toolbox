"""API routes for OCC Exhibit A PDF extraction (extract tool)."""

from __future__ import annotations

import logging
from typing import Annotated, Optional

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
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
from app.services.extract.format_detector import (
    ExhibitFormat,
    compute_quality_score,
    detect_format,
)
from app.services.extract.name_parser import parse_name
from app.services.extract.parser import parse_exhibit_a
from app.services.extract.pdf_extractor import extract_party_list, extract_text_from_pdf
from app.services.extract.table_parser import parse_table_pdf

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health_check() -> dict:
    """Health check endpoint for extract tool."""
    return {"status": "healthy", "service": "extract"}


@router.post("/upload", response_model=UploadResponse)
async def upload_pdf(
    file: Annotated[UploadFile, File(description="PDF file containing Exhibit A")],
    request: Request,
    format_hint: Optional[str] = Query(
        None, description="Manual format hint (e.g., TABLE_ATTENTION, FREE_TEXT_LIST)"
    ),
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

        # Detect format (or use manual hint)
        fmt = ExhibitFormat.FREE_TEXT_NUMBERED
        if format_hint:
            try:
                fmt = ExhibitFormat(format_hint)
                logger.info("Using manual format hint: %s", fmt.value)
            except ValueError:
                logger.warning("Invalid format_hint '%s', auto-detecting", format_hint)
                fmt = detect_format(full_text, file_bytes)
        else:
            fmt = detect_format(full_text, file_bytes)

        # Route to correct parser based on format
        if fmt in (ExhibitFormat.TABLE_ATTENTION, ExhibitFormat.TABLE_SPLIT_ADDR):
            entries = parse_table_pdf(file_bytes, fmt)
        elif fmt == ExhibitFormat.FREE_TEXT_LIST:
            # Re-extract with 2-column layout for Coterra-style
            two_col_text = extract_text_from_pdf(file_bytes, num_columns=2)
            party_text = extract_party_list(two_col_text)
            entries = parse_exhibit_a(party_text)
        else:
            # Default FREE_TEXT_NUMBERED flow
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
                    format_detected=fmt.value,
                ),
            )

        # Populate parsed name fields for individuals (for non-table formats;
        # table parsers already do this inline)
        if fmt not in (ExhibitFormat.TABLE_ATTENTION, ExhibitFormat.TABLE_SPLIT_ADDR):
            for entry in entries:
                parsed = parse_name(entry.primary_name, entry.entity_type.value)
                if parsed.is_person:
                    entry.first_name = parsed.first_name or None
                    entry.middle_name = parsed.middle_name or None
                    entry.last_name = parsed.last_name or None
                    entry.suffix = parsed.suffix or None

        flagged_count = sum(1 for e in entries if e.flagged)

        # Compute quality score
        quality = compute_quality_score(entries)
        format_warning = None
        if quality < 0.5:
            format_warning = (
                "Low parsing confidence. Try selecting a different format manually."
            )

        logger.info(
            "Extracted %d entries (%d flagged, quality=%.2f, format=%s) from %s",
            len(entries), flagged_count, quality, fmt.value, file.filename,
        )

        result = ExtractionResult(
            success=True,
            entries=entries,
            total_count=len(entries),
            flagged_count=flagged_count,
            source_filename=file.filename,
            format_detected=fmt.value,
            quality_score=quality,
            format_warning=format_warning,
        )

        # Persist to Firestore (non-blocking)
        user_email = request.headers.get("x-user-email") or None
        user_name = request.headers.get("x-user-name") or None
        job_id = await persist_job_result(
            tool="extract",
            filename=file.filename,
            file_size=len(file_bytes),
            entries=[e.model_dump() for e in entries],
            total=len(entries),
            success=len(entries),
            errors=flagged_count,
            user_id=user_email,
            user_name=user_name,
        )
        if job_id:
            result.job_id = job_id

        # ETL pipeline disabled - will be replaced with Supabase

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
        csv_bytes = to_csv(
            request.entries,
            county=request.county or "",
            campaign_name=request.campaign_name or "",
        )
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
        excel_bytes = to_excel(
            request.entries,
            county=request.county or "",
            campaign_name=request.campaign_name or "",
        )
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

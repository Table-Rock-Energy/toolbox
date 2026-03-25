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


@router.post("/detect-format")
async def detect_format_endpoint(
    file: Annotated[UploadFile, File(description="PDF to detect format")],
    request: Request,
) -> dict:
    """Detect the format of an uploaded PDF without full extraction."""
    file_bytes = await validate_upload(file, allowed_extensions=[".pdf"])
    full_text = extract_text_from_pdf(file_bytes)
    if not full_text or len(full_text.strip()) < 50:
        return {"format": None, "error": "Could not extract text"}
    fmt = detect_format(full_text, file_bytes)
    format_labels = {
        ExhibitFormat.TABLE_ATTENTION: "Table with Attention Column",
        ExhibitFormat.TABLE_SPLIT_ADDR: "Table with Split Address",
        ExhibitFormat.FREE_TEXT_LIST: "Two-Column Numbered List",
        ExhibitFormat.FREE_TEXT_NUMBERED: "Free Text (Default)",
        ExhibitFormat.ECF: "ECF Filing",
        ExhibitFormat.UNKNOWN: "Unknown",
    }
    return {"format": fmt.value, "format_label": format_labels.get(fmt, fmt.value)}


@router.post("/upload", response_model=UploadResponse)
async def upload_pdf(
    file: Annotated[UploadFile, File(description="PDF file containing Exhibit A")],
    request: Request,
    format_hint: Optional[str] = Query(
        None, description="Manual format hint (e.g., TABLE_ATTENTION, FREE_TEXT_LIST)"
    ),
    csv_file: Optional[UploadFile] = File(
        None, description="Optional Convey 640 CSV/Excel file for merge"
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
        case_metadata = None
        merge_warnings = None
        original_csv_entries = None
        if fmt in (ExhibitFormat.TABLE_ATTENTION, ExhibitFormat.TABLE_SPLIT_ADDR):
            entries = parse_table_pdf(file_bytes, fmt)
            # Fallback: if table parser found nothing, try free-text parser
            if not entries:
                logger.warning(
                    "Table parser (%s) returned 0 entries, falling back to free-text",
                    fmt.value,
                )
                party_text = extract_party_list(full_text)
                entries = parse_exhibit_a(party_text)
                if entries:
                    fmt = ExhibitFormat.FREE_TEXT_NUMBERED
                    logger.info(
                        "Free-text fallback found %d entries", len(entries)
                    )
        elif fmt == ExhibitFormat.ECF:
            from app.services.extract.ecf_parser import parse_ecf_filing

            ecf_result = parse_ecf_filing(full_text)
            entries = ecf_result.entries
            case_metadata = ecf_result.metadata

            # Merge with optional CSV file
            merge_warnings = None
            original_csv_entries = None
            if csv_file:
                csv_bytes = await csv_file.read()
                from app.services.extract.convey640_parser import parse_convey640
                from app.services.extract.merge_service import merge_entries

                csv_result = parse_convey640(csv_bytes, csv_file.filename or "upload.csv")
                # Capture original CSV entries before merge for cross-file comparison
                original_csv_entries = [e.model_dump() for e in csv_result.entries] if csv_result.entries else None
                merge_result = merge_entries(ecf_result, csv_result)
                entries = merge_result.entries
                case_metadata = merge_result.metadata
                merge_warnings = merge_result.warnings or None
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
            format_label = {
                ExhibitFormat.TABLE_ATTENTION: "table with Attention column (Devon-style)",
                ExhibitFormat.TABLE_SPLIT_ADDR: "table with split address columns (Mewbourne-style)",
                ExhibitFormat.FREE_TEXT_LIST: "two-column numbered list (Coterra-style)",
                ExhibitFormat.FREE_TEXT_NUMBERED: "numbered list (e.g., '1. Name, Address')",
                ExhibitFormat.ECF: "ECF multiunit horizontal well filing",
            }.get(fmt, fmt.value)
            return UploadResponse(
                message="No party entries found",
                result=ExtractionResult(
                    success=False,
                    error_message=f"Detected format as {format_label} but could not "
                    "extract any entries. Try selecting a different format manually.",
                    source_filename=file.filename,
                    format_detected=fmt.value,
                ),
            )

        # Populate parsed name fields for individuals (for non-table formats;
        # table parsers and ECF parser already do this inline)
        if fmt not in (
            ExhibitFormat.TABLE_ATTENTION,
            ExhibitFormat.TABLE_SPLIT_ADDR,
            ExhibitFormat.ECF,
        ):
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

        # Post-process: programmatic fixes + AI verification
        pp_result = None
        try:
            from app.services.data_enrichment_pipeline import auto_enrich

            entry_dicts = [e.model_dump() for e in entries]
            pp_result = await auto_enrich("extract", entry_dicts)
            entries = [PartyEntry(**d) for d in entry_dicts]
            flagged_count = sum(1 for e in entries if e.flagged)
        except Exception as e:
            logger.warning("Post-processing failed, returning raw results: %s", e)

        result = ExtractionResult(
            success=True,
            entries=entries,
            total_count=len(entries),
            flagged_count=flagged_count,
            source_filename=file.filename,
            format_detected=fmt.value,
            quality_score=quality,
            format_warning=format_warning,
            case_metadata=case_metadata,
            merge_warnings=merge_warnings,
            original_csv_entries=original_csv_entries if fmt == ExhibitFormat.ECF else None,
            post_process=pp_result,
        )

        # Persist to database (non-blocking)
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
            case_metadata=request.case_metadata,
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
            case_metadata=request.case_metadata,
        )
        filename = f"{request.filename or 'exhibit_a_export'}.xlsx"
        return file_response(excel_bytes, filename)
    except Exception as e:
        logger.exception("Error generating Excel: %s", e)
        raise HTTPException(status_code=500, detail=f"Error generating Excel: {e!s}") from e


@router.get("/pipeline-status")
async def pipeline_status():
    """Return which data pipeline features are enabled."""
    from app.core.config import settings

    return {
        "google_maps_enabled": settings.use_google_maps,
        "ai_enabled": settings.use_ai,
    }


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

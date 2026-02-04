"""API routes for OCC Exhibit A PDF extraction (extract tool)."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response

from app.models.extract import (
    ExportRequest,
    ExtractionResult,
    PartyEntry,
    UploadResponse,
)
from app.services.extract.export_service import to_csv, to_excel
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
    """
    Upload a PDF file and extract party entries from Exhibit A.

    Args:
        file: PDF file upload

    Returns:
        UploadResponse with extraction results
    """
    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Please upload a PDF file.",
        )

    # Validate content type
    if file.content_type and "pdf" not in file.content_type.lower():
        raise HTTPException(
            status_code=400,
            detail="Invalid content type. Please upload a PDF file.",
        )

    try:
        # Read file bytes
        file_bytes = await file.read()

        if len(file_bytes) == 0:
            raise HTTPException(status_code=400, detail="Empty file uploaded")

        # Extract text from PDF
        logger.info(f"Processing PDF: {file.filename}")
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

        # Parse entries from the extracted text
        entries = parse_exhibit_a(party_text)

        if not entries:
            return UploadResponse(
                message="No party entries found",
                result=ExtractionResult(
                    success=False,
                    error_message="Could not find numbered party entries (e.g., '1. Name, Address') in the document.",
                    source_filename=file.filename,
                ),
            )

        # Count flagged entries
        flagged_count = sum(1 for e in entries if e.flagged)

        logger.info(
            f"Extracted {len(entries)} entries ({flagged_count} flagged) "
            f"from {file.filename}"
        )

        return UploadResponse(
            message=f"Successfully extracted {len(entries)} entries",
            result=ExtractionResult(
                success=True,
                entries=entries,
                total_count=len(entries),
                flagged_count=flagged_count,
                source_filename=file.filename,
            ),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error processing PDF: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing PDF: {str(e)}",
        ) from e


@router.post("/export/csv")
async def export_csv(request: ExportRequest) -> Response:
    """
    Export party entries to CSV format.

    Args:
        request: ExportRequest with entries to export

    Returns:
        CSV file download
    """
    if not request.entries:
        raise HTTPException(status_code=400, detail="No entries provided for export")

    try:
        csv_bytes = to_csv(request.entries)
        filename = f"{request.filename or 'exhibit_a_export'}.csv"

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
    Export party entries to Excel format.

    Args:
        request: ExportRequest with entries to export

    Returns:
        Excel file download
    """
    if not request.entries:
        raise HTTPException(status_code=400, detail="No entries provided for export")

    try:
        excel_bytes = to_excel(request.entries)
        filename = f"{request.filename or 'exhibit_a_export'}.xlsx"

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


@router.post("/parse-entries", response_model=list[PartyEntry])
async def parse_entries(text: str) -> list[PartyEntry]:
    """
    Parse raw Exhibit A text into party entries.

    This endpoint is useful for debugging or when text has been
    extracted by other means.

    Args:
        text: Raw Exhibit A text

    Returns:
        List of parsed PartyEntry objects
    """
    if not text or len(text.strip()) < 10:
        raise HTTPException(status_code=400, detail="Text is too short to parse")

    try:
        entries = parse_exhibit_a(text)
        return entries

    except Exception as e:
        logger.exception(f"Error parsing text: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error parsing text: {str(e)}",
        ) from e

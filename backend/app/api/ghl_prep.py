"""API routes for GHL Prep Tool."""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated, Optional
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from app.core.ingestion import file_response, persist_job_result, validate_upload
from app.models.ghl_prep import ExportRequest, TransformResult, UploadResponse
from app.services.ghl_prep.export_service import generate_filename, to_csv
from app.services.ghl_prep.transform_service import transform_csv

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health_check() -> dict:
    """Health check endpoint for GHL Prep tool."""
    return {"status": "healthy", "service": "ghl-prep"}


@router.post("/upload", response_model=UploadResponse)
async def upload_file(
    file: Annotated[UploadFile, File(description="Mineral export CSV file to process")],
    request: Request,
) -> UploadResponse:
    """Upload a Mineral export CSV and transform it for GoHighLevel import."""
    file_bytes = await validate_upload(file, allowed_extensions=[".csv"])

    try:
        logger.info("Processing GHL Prep file: %s", file.filename)

        # Transform the CSV
        result = transform_csv(file_bytes, file.filename)

        if not result.success:
            return UploadResponse(
                message="Transformation failed",
                result=result,
            )

        # Generate job_id locally so we can return it immediately
        job_id = str(uuid4())
        result.job_id = job_id

        # Extract user info from headers
        user_email = request.headers.get("x-user-email") or None
        user_name = request.headers.get("x-user-name") or None

        # Fire-and-forget: persist to Firestore in background
        asyncio.create_task(
            _persist_in_background(
                job_id=job_id,
                filename=file.filename,
                file_size=len(file_bytes),
                rows=result.rows,
                total=result.total_count,
                success=result.total_count,
                errors=len(result.warnings),
                user_id=user_email,
                user_name=user_name,
            )
        )

        logger.info(
            "Transformed %d rows from %s (job_id=%s)",
            result.total_count,
            file.filename,
            job_id,
        )

        return UploadResponse(
            message=f"Successfully transformed {result.total_count} rows",
            result=result,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error processing GHL Prep file: %s", e)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing file: {e!s}",
        ) from e


async def _persist_in_background(
    *,
    job_id: str,
    filename: str,
    file_size: int,
    rows: list[dict],
    total: int,
    success: int,
    errors: int,
    user_id: Optional[str] = None,
    user_name: Optional[str] = None,
) -> None:
    """Background task for Firestore persistence."""
    try:
        # For GHL Prep, we don't need to save individual entries (they're transformations, not entities)
        # Just persist the job metadata
        await persist_job_result(
            tool="ghl_prep",
            filename=filename,
            file_size=file_size,
            entries=[],  # Empty entries list - job metadata is sufficient
            total=total,
            success=success,
            errors=errors,
            user_id=user_id,
            user_name=user_name,
            job_id=job_id,
        )
    except Exception as e:
        logger.warning("Background persistence failed (non-critical): %s", e)


@router.post("/export/csv")
async def export_csv(request: ExportRequest):
    """Export transformed GHL Prep data to CSV format."""
    if not request.rows:
        raise HTTPException(status_code=400, detail="No rows provided for export")

    try:
        csv_bytes = to_csv(request.rows)
        filename = generate_filename(request.filename or "mineral_export")

        logger.info("Exporting %d rows to %s", len(request.rows), filename)

        return file_response(csv_bytes, filename)
    except Exception as e:
        logger.exception("Error generating CSV export: %s", e)
        raise HTTPException(
            status_code=500, detail=f"Error generating CSV: {e!s}"
        ) from e

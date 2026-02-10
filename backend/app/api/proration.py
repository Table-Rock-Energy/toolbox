"""API routes for Proration tool."""

from __future__ import annotations

import json
import logging
from typing import Annotated, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.core.ingestion import file_response, persist_job_result, validate_upload
from app.models.proration import (
    ExportRequest,
    ProcessingOptions,
    RRCDownloadResponse,
    UploadResponse,
)
from app.services.proration.csv_processor import process_csv
from app.services.proration.export_service import to_csv, to_excel, to_pdf
from app.services.proration.rrc_data_service import rrc_data_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health_check() -> dict:
    """Health check endpoint for proration tool."""
    return {"status": "healthy", "service": "proration"}


@router.get("/rrc/status")
async def get_rrc_status() -> dict:
    """Get status of RRC proration data from CSV files and database."""
    status = rrc_data_service.get_data_status()

    try:
        from app.services.firestore_service import get_rrc_data_status
        db_status = await get_rrc_data_status()
        status["db_oil_rows"] = db_status.get("oil_rows", 0)
        status["db_gas_rows"] = db_status.get("gas_rows", 0)
        status["last_sync"] = db_status.get("last_sync")
        status["db_available"] = db_status.get("oil_rows", 0) > 0 or db_status.get("gas_rows", 0) > 0
    except Exception as e:
        logger.debug("Could not get database status: %s", e)
        status["db_oil_rows"] = 0
        status["db_gas_rows"] = 0
        status["last_sync"] = None
        status["db_available"] = False

    return status


@router.post("/rrc/download", response_model=RRCDownloadResponse)
async def download_rrc_data() -> RRCDownloadResponse:
    """Download latest RRC proration data (oil and gas)."""
    logger.info("Starting RRC data download...")

    success, message, stats = rrc_data_service.download_all_data()

    sync_message = ""
    if success:
        try:
            sync_result = await rrc_data_service.sync_to_database("both")
            if sync_result.get("success"):
                sync_message = f" | DB sync: {sync_result['message']}"
                logger.info("DB sync complete: %s", sync_result["message"])
            else:
                sync_message = " | DB sync failed (CSV data still available)"
                logger.warning("DB sync failed: %s", sync_result.get("message"))
        except Exception as e:
            sync_message = " | DB sync failed (CSV data still available)"
            logger.warning("DB sync failed (non-critical): %s", e)

    return RRCDownloadResponse(
        success=success,
        message=message + sync_message,
        oil_rows=stats.get("oil_rows", 0),
        gas_rows=stats.get("gas_rows", 0),
    )


@router.post("/rrc/download/oil", response_model=RRCDownloadResponse)
async def download_oil_data() -> RRCDownloadResponse:
    """Download only oil proration data."""
    success, message, row_count = rrc_data_service.download_oil_data()
    return RRCDownloadResponse(
        success=success,
        message=message,
        oil_rows=row_count,
        gas_rows=0,
    )


@router.post("/rrc/download/gas", response_model=RRCDownloadResponse)
async def download_gas_data() -> RRCDownloadResponse:
    """Download only gas proration data."""
    success, message, row_count = rrc_data_service.download_gas_data()
    return RRCDownloadResponse(
        success=success,
        message=message,
        oil_rows=0,
        gas_rows=row_count,
    )


@router.post("/rrc/sync")
async def sync_rrc_to_database() -> dict:
    """Manually sync existing CSV data to the database."""
    try:
        result = await rrc_data_service.sync_to_database("both")
        return result
    except Exception as e:
        logger.exception("Database sync failed: %s", e)
        raise HTTPException(
            status_code=500,
            detail=f"Database sync failed: {e!s}",
        ) from e


@router.post("/upload", response_model=UploadResponse)
async def upload_csv(
    file: Annotated[UploadFile, File(description="CSV file from mineralholders.com")],
    options_json: Annotated[Optional[str], Form(description="Processing options as JSON")] = None,
) -> UploadResponse:
    """Upload a CSV file and process mineral holder data."""
    file_bytes = await validate_upload(file, allowed_extensions=[".csv"])

    try:
        # Parse options from JSON
        if options_json:
            try:
                options_dict = json.loads(options_json)
                if options_dict.get("well_type_override") == "":
                    options_dict["well_type_override"] = None
                options_dict["query_rrc"] = False
                options = ProcessingOptions(**options_dict)
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning("Invalid options JSON: %s, using defaults", e)
                options = ProcessingOptions(query_rrc=False)
        else:
            options = ProcessingOptions(query_rrc=False)

        logger.info("Processing CSV: %s", file.filename)
        result = await process_csv(file_bytes, file.filename, options)

        if not result.success:
            return UploadResponse(message="Processing failed", result=result)

        logger.info(
            "Processed %d rows (%d matched, %d failed) from %s",
            result.processed_rows, result.matched_rows, result.failed_rows,
            file.filename,
        )

        # Persist to Firestore (non-blocking)
        job_id = await persist_job_result(
            tool="proration",
            filename=file.filename,
            file_size=len(file_bytes),
            entries=[r.model_dump() for r in result.rows],
            total=result.total_rows,
            success=result.matched_rows,
            errors=result.failed_rows,
        )
        if job_id:
            result.job_id = job_id

        return UploadResponse(
            message=(
                f"Successfully processed {result.processed_rows} rows "
                f"({result.matched_rows} matched with RRC data)"
            ),
            result=result,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error processing CSV: %s", e)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing CSV: {e!s}",
        ) from e


@router.post("/export/csv")
async def export_csv(request: ExportRequest):
    """Export mineral holder rows to CSV format."""
    if not request.rows:
        raise HTTPException(status_code=400, detail="No rows provided for export")

    try:
        csv_bytes = to_csv(request.rows)
        filename = f"{request.filename or 'proration_export'}.csv"
        return file_response(csv_bytes, filename)
    except Exception as e:
        logger.exception("Error generating CSV: %s", e)
        raise HTTPException(status_code=500, detail=f"Error generating CSV: {e!s}") from e


@router.post("/export/excel")
async def export_excel(request: ExportRequest):
    """Export mineral holder rows to Excel format."""
    if not request.rows:
        raise HTTPException(status_code=400, detail="No rows provided for export")

    try:
        excel_bytes = to_excel(request.rows)
        filename = f"{request.filename or 'proration_export'}.xlsx"
        return file_response(excel_bytes, filename)
    except Exception as e:
        logger.exception("Error generating Excel: %s", e)
        raise HTTPException(status_code=500, detail=f"Error generating Excel: {e!s}") from e


@router.post("/export/pdf")
async def export_pdf(request: ExportRequest):
    """Export mineral holder rows to PDF format."""
    if not request.rows:
        raise HTTPException(status_code=400, detail="No rows provided for export")

    try:
        pdf_bytes = to_pdf(request.rows)
        filename = f"{request.filename or 'proration_export'}.pdf"
        return file_response(pdf_bytes, filename)
    except Exception as e:
        logger.exception("Error generating PDF: %s", e)
        raise HTTPException(status_code=500, detail=f"Error generating PDF: {e!s}") from e

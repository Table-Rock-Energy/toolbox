"""API routes for Proration tool."""

from __future__ import annotations

import json
import logging
from typing import Annotated, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from app.models.proration import (
    ExportRequest,
    ProcessingOptions,
    ProcessingResult,
    RRCDataStatus,
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

    # Try to get database status too
    try:
        from app.services.firestore_service import get_rrc_data_status
        db_status = await get_rrc_data_status()
        status["db_oil_rows"] = db_status.get("oil_rows", 0)
        status["db_gas_rows"] = db_status.get("gas_rows", 0)
        status["last_sync"] = db_status.get("last_sync")
        status["db_available"] = db_status.get("oil_rows", 0) > 0 or db_status.get("gas_rows", 0) > 0
    except Exception as e:
        logger.debug(f"Could not get database status: {e}")
        status["db_oil_rows"] = 0
        status["db_gas_rows"] = 0
        status["last_sync"] = None
        status["db_available"] = False

    return status


@router.post("/rrc/download", response_model=RRCDownloadResponse)
async def download_rrc_data() -> RRCDownloadResponse:
    """
    Download latest RRC proration data (oil and gas).

    This downloads the full proration schedules from the Texas Railroad Commission.
    The download may take 1-2 minutes depending on connection speed.
    After download, data is synced to the database for persistent storage.
    """
    logger.info("Starting RRC data download...")

    success, message, stats = rrc_data_service.download_all_data()

    # Sync to database inline so Firestore is populated before we return
    sync_message = ""
    if success:
        try:
            sync_result = await rrc_data_service.sync_to_database("both")
            if sync_result.get("success"):
                sync_message = f" | DB sync: {sync_result['message']}"
                logger.info(f"DB sync complete: {sync_result['message']}")
            else:
                sync_message = " | DB sync failed (CSV data still available)"
                logger.warning(f"DB sync failed: {sync_result.get('message')}")
        except Exception as e:
            sync_message = " | DB sync failed (CSV data still available)"
            logger.warning(f"DB sync failed (non-critical): {e}")

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
    """
    Manually sync existing CSV data to the database.

    Use this if CSV data was downloaded but the database sync failed or was skipped.
    """
    try:
        result = await rrc_data_service.sync_to_database("both")
        return result
    except Exception as e:
        logger.exception(f"Database sync failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Database sync failed: {str(e)}",
        ) from e


@router.post("/upload", response_model=UploadResponse)
async def upload_csv(
    file: Annotated[UploadFile, File(description="CSV file from mineralholders.com")],
    options_json: Annotated[Optional[str], Form(description="Processing options as JSON")] = None,
) -> UploadResponse:
    """
    Upload a CSV file and process mineral holder data.

    Args:
        file: CSV file upload
        options_json: Processing options as JSON string (filters, RRC query settings, etc.)

    Returns:
        UploadResponse with processing results
    """
    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Please upload a CSV file.",
        )

    # Validate content type
    if file.content_type and "csv" not in file.content_type.lower():
        if file.content_type not in ["text/csv", "application/csv", "text/plain"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid content type. Please upload a CSV file.",
            )

    try:
        # Read file bytes
        file_bytes = await file.read()

        if len(file_bytes) == 0:
            raise HTTPException(status_code=400, detail="Empty file uploaded")

        # Parse options from JSON
        if options_json:
            try:
                options_dict = json.loads(options_json)
                # Convert empty string well_type_override to None
                if options_dict.get("well_type_override") == "":
                    options_dict["well_type_override"] = None
                # Disable RRC query by default (we use local data now)
                options_dict["query_rrc"] = False
                options = ProcessingOptions(**options_dict)
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"Invalid options JSON: {e}, using defaults")
                options = ProcessingOptions(query_rrc=False)
        else:
            options = ProcessingOptions(query_rrc=False)

        # Process CSV
        logger.info(f"Processing CSV: {file.filename}")
        result = await process_csv(file_bytes, file.filename, options)

        if not result.success:
            return UploadResponse(
                message="Processing failed",
                result=result,
            )

        logger.info(
            f"Processed {result.processed_rows} rows "
            f"({result.matched_rows} matched, {result.failed_rows} failed) from {file.filename}"
        )

        # Persist to Firestore (non-blocking, failure doesn't break upload)
        try:
            from app.services.firestore_service import (
                create_job,
                save_proration_rows,
                update_job_status,
            )

            job = await create_job(
                tool="proration",
                source_filename=file.filename,
                source_file_size=len(file_bytes),
            )
            job_id = job["id"]
            result.job_id = job_id

            await save_proration_rows(
                job_id, [r.model_dump() for r in result.rows]
            )
            await update_job_status(
                job_id,
                status="completed",
                total_count=result.total_rows,
                success_count=result.matched_rows,
                error_count=result.failed_rows,
            )
        except Exception as fs_err:
            logger.warning(f"Firestore persistence failed (non-critical): {fs_err}")

        return UploadResponse(
            message=f"Successfully processed {result.processed_rows} rows ({result.matched_rows} matched with RRC data)",
            result=result,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error processing CSV: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing CSV: {str(e)}",
        ) from e


@router.post("/export/csv")
async def export_csv(request: ExportRequest) -> Response:
    """Export mineral holder rows to CSV format."""
    if not request.rows:
        raise HTTPException(status_code=400, detail="No rows provided for export")

    try:
        csv_bytes = to_csv(request.rows)
        filename = f"{request.filename or 'proration_export'}.csv"

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
    Export mineral holder rows to Excel format.

    Args:
        request: ExportRequest with rows to export

    Returns:
        Excel file download
    """
    if not request.rows:
        raise HTTPException(status_code=400, detail="No rows provided for export")

    try:
        excel_bytes = to_excel(request.rows)
        filename = f"{request.filename or 'proration_export'}.xlsx"

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


@router.post("/export/pdf")
async def export_pdf(request: ExportRequest) -> Response:
    """
    Export mineral holder rows to PDF format.

    Args:
        request: ExportRequest with rows to export

    Returns:
        PDF file download
    """
    if not request.rows:
        raise HTTPException(status_code=400, detail="No rows provided for export")

    try:
        pdf_bytes = to_pdf(request.rows)
        filename = f"{request.filename or 'proration_export'}.pdf"

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )

    except Exception as e:
        logger.exception(f"Error generating PDF: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error generating PDF: {str(e)}",
        ) from e

"""API routes for Proration tool."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Annotated, Optional, Union

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Request, UploadFile

from app.core.ingestion import file_response, persist_job_result, validate_upload
from app.models.proration import (
    ExportRequest,
    FetchMissingRequest,
    FetchMissingResult,
    ProcessingOptions,
    RRCBackgroundDownloadResponse,
    RRCDownloadResponse,
    UploadResponse,
)
from app.services.proration.csv_processor import extract_needed_counties, process_csv
from app.services.proration.export_service import to_csv, to_excel, to_pdf
from app.services.proration.rrc_county_download_service import (
    ensure_counties_fresh,
    fetch_individual_leases,
)
from app.services.proration.rrc_data_service import rrc_data_service
from app.services.rrc_background import (
    get_active_rrc_sync_job,
    get_rrc_sync_job,
    start_rrc_background_download,
)

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


@router.post("/rrc/download")
async def download_rrc_data(force: bool = False) -> Union[RRCBackgroundDownloadResponse, RRCDownloadResponse]:
    """Download latest RRC proration data (oil and gas) in the background.

    Skips download if data was already synced this month unless force=True.
    Returns immediately with a job_id for polling progress.
    """
    # Guard: only download once per month
    if not force:
        try:
            from app.services.firestore_service import get_rrc_data_status
            db_status = await get_rrc_data_status()
            last_sync = db_status.get("last_sync", {})
            completed_at = last_sync.get("completed_at") if last_sync else None
            if completed_at:
                last_dt = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
                first_of_month = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                if last_dt >= first_of_month:
                    total = (db_status.get("oil_rows", 0) + db_status.get("gas_rows", 0))
                    logger.info("RRC data already current (synced %s). Skipping download.", completed_at)
                    return RRCDownloadResponse(
                        success=True,
                        message=f"Already up to date ({total:,} records synced {completed_at[:10]})",
                        oil_rows=db_status.get("oil_rows", 0),
                        gas_rows=db_status.get("gas_rows", 0),
                    )
        except Exception as e:
            logger.debug("Could not check last sync for guard: %s", e)

    logger.info("Starting background RRC data download...")

    # Start background download and return immediately with job_id
    job_id = start_rrc_background_download()

    return RRCBackgroundDownloadResponse(
        job_id=job_id,
        status="downloading_oil",
        message="Download started in background",
    )


@router.get("/rrc/download/{job_id}/status")
async def get_rrc_download_status(job_id: str) -> dict:
    """Get status of a background RRC download job.

    Used for polling progress from the frontend.
    """
    job = await get_rrc_sync_job(job_id)

    if job is None:
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} not found",
        )

    return job


@router.get("/rrc/download/active")
async def get_active_rrc_download() -> dict:
    """Get the most recent active or recently completed RRC download job.

    Returns the job if found, or {"job": null} if none.
    Used on page load to detect running jobs.
    """
    try:
        job = await get_active_rrc_sync_job()
    except Exception as e:
        logger.debug("Could not check active RRC job (missing index?): %s", e)
        return {"job": None}

    if job is None:
        return {"job": None}

    return job


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


@router.post("/rrc/refresh-counties")
async def refresh_tracked_counties() -> dict:
    """Re-download RRC data for all previously tracked counties.

    Intended to be called weekly (Friday evenings) via GitHub Actions cron.
    Only downloads counties that are stale (not refreshed this month).
    """
    try:
        from app.services.firestore_service import get_all_tracked_county_keys, get_stale_counties
        from app.services.proration.rrc_county_codes import TEXAS_COUNTY_CODES

        all_keys = await get_all_tracked_county_keys()
        if not all_keys:
            return {"message": "No tracked counties", "refreshed": 0, "total": 0}

        stale_keys = await get_stale_counties(all_keys)
        if not stale_keys:
            return {"message": "All counties are fresh", "refreshed": 0, "total": len(all_keys)}

        # Build reverse lookup: "district-county_code" -> county_name
        key_to_name = {}
        for name, (code, district) in TEXAS_COUNTY_CODES.items():
            key_to_name[f"{district}-{code}"] = name

        # Build county dicts for download
        counties_to_download = []
        for key in stale_keys:
            parts = key.split("-", 1)
            if len(parts) != 2:
                continue
            district, county_code = parts
            county_name = key_to_name.get(key, f"{district}-{county_code}")
            counties_to_download.append({
                "county_name": county_name,
                "county_code": county_code,
                "district": district,
            })

        logger.info("refresh-counties: %d stale of %d tracked, downloading", len(counties_to_download), len(all_keys))
        dl_results = await ensure_counties_fresh(counties_to_download)

        downloaded = sum(1 for r in dl_results if r["status"] == "downloaded")
        failed = sum(1 for r in dl_results if r["status"] == "failed")
        total_records = sum(r.get("records_downloaded", 0) for r in dl_results)

        return {
            "message": f"Refreshed {downloaded} counties ({total_records} records)",
            "refreshed": downloaded,
            "failed": failed,
            "total": len(all_keys),
            "details": dl_results,
        }
    except Exception as e:
        logger.exception("County refresh failed: %s", e)
        raise HTTPException(status_code=500, detail=f"County refresh failed: {e!s}") from e


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
    request: Request,
    background_tasks: BackgroundTasks,
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

        # Schedule county download in background (don't block upload)
        try:
            needed_counties = extract_needed_counties(file_bytes)
            if needed_counties:
                logger.info("Scheduling background county download for %d counties", len(needed_counties))
                background_tasks.add_task(_background_county_download, needed_counties)
        except Exception as e:
            logger.warning("County extraction failed: %s", e)

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
        user_email = request.headers.get("x-user-email") or None
        user_name = request.headers.get("x-user-name") or None
        job_id = await persist_job_result(
            tool="proration",
            filename=file.filename,
            file_size=len(file_bytes),
            entries=[r.model_dump() for r in result.rows],
            total=result.total_rows,
            success=result.matched_rows,
            errors=result.failed_rows,
            user_id=user_email,
            user_name=user_name,
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


@router.post("/rrc/fetch-missing", response_model=FetchMissingResult)
async def fetch_missing_rrc_data(request: FetchMissingRequest, background_tasks: BackgroundTasks) -> FetchMissingResult:
    """Fetch RRC data for rows that are missing it.

    1. Groups unmatched rows by county
    2. Downloads county data from RRC on-demand
    3. Re-looks up each row in Firestore after download
    """
    import re

    from app.models.proration import WellType
    from app.services.proration.rrc_county_codes import lookup_county

    if not request.rows:
        raise HTTPException(status_code=400, detail="No rows provided")

    try:
        from app.services.firestore_service import (
            lookup_rrc_acres,
            lookup_rrc_by_lease_number,
        )
    except ImportError:
        return FetchMissingResult(
            updated_rows=list(request.rows),
            matched_count=0,
            still_missing_count=len(request.rows),
        )

    logger.info("fetch-missing: %d rows received", len(request.rows))

    # Step 1: Parse district/lease from each row and check Firestore first
    updated_rows = []
    matched = 0
    missing_leases: list[tuple[int, str, str, str]] = []  # (row_index, district, lease_number, county_code)

    for i, row in enumerate(request.rows):
        district = row.district
        lease_number = row.lease_number

        # Try to parse from rrc_lease if not already set
        if not district or not lease_number:
            if row.rrc_lease and "-" in row.rrc_lease:
                parts = row.rrc_lease.split("-", 1)
                district = district or parts[0].strip()
                lease_number = lease_number or parts[1].strip()
            elif row.raw_rrc:
                numbers = re.findall(r"\d+", str(row.raw_rrc))
                if len(numbers) >= 2:
                    district = district or numbers[0].zfill(2)
                    lease_number = lease_number or numbers[1]

        # Resolve county code for narrower RRC searches
        county_code = ""
        if row.county:
            county_result = lookup_county(row.county)
            if county_result:
                county_code = county_result[0]

        rrc_info = None

        if district and lease_number:
            logger.info("fetch-missing: Firestore lookup district=%s lease=%s", district, lease_number)
            rrc_info = await lookup_rrc_acres(district, lease_number)

        if rrc_info is None and lease_number:
            rrc_info = await lookup_rrc_by_lease_number(lease_number)

        if rrc_info:
            logger.info("fetch-missing: MATCHED district=%s lease=%s -> acres=%s", district, lease_number, rrc_info.get("acres"))
            _apply_rrc_info(row, rrc_info, WellType)
            matched += 1
        elif district and lease_number:
            missing_leases.append((i, district, lease_number, county_code))

        updated_rows.append(row)

    # Step 2: Individual RRC queries for missing leases (fast with county codes)
    # County downloads happen in background after response is sent
    MAX_INDIVIDUAL_QUERIES = 25
    county_download_infos = []

    if missing_leases:
        unique_leases = list({(d, ln, cc) for _, d, ln, cc in missing_leases})
        logger.info("fetch-missing: %d rows not in Firestore (%d unique leases)", len(missing_leases), len(unique_leases))

        if len(unique_leases) > MAX_INDIVIDUAL_QUERIES:
            logger.info(
                "fetch-missing: capping individual queries from %d to %d",
                len(unique_leases), MAX_INDIVIDUAL_QUERIES,
            )
            unique_leases = unique_leases[:MAX_INDIVIDUAL_QUERIES]
        logger.info(
            "fetch-missing: querying RRC for %d individual leases",
            len(unique_leases),
        )
        try:
            individual_results = await fetch_individual_leases(unique_leases)
        except Exception as e:
            logger.warning("Individual lease fetch failed: %s", e)
            individual_results = {}

        if individual_results:
            for row_idx, district, lease_number, _cc in missing_leases:
                row = updated_rows[row_idx]
                rrc_info = await lookup_rrc_acres(district, lease_number)
                if rrc_info is None:
                    rrc_info = await lookup_rrc_by_lease_number(lease_number)
                if rrc_info:
                    _apply_rrc_info(row, rrc_info, WellType)
                    matched += 1

    # Mark rows that are still missing after full fetch attempt
    RRC_SEARCH_URL = "https://webapps2.rrc.texas.gov/EWA/oilProQueryAction.do"
    for row in updated_rows:
        if not row.rrc_acres and row.notes and "Not found" in row.notes:
            district = row.district or ""
            lease = row.lease_number or ""
            row.notes = f"Not found in RRC|{RRC_SEARCH_URL}?district={district}&lease={lease}"

    logger.info("fetch-missing: matched %d of %d rows", matched, len(request.rows))

    # Background: download full county data so future lookups hit Firestore directly
    if missing_leases or matched > 0:
        county_set: set[str] = set()
        for row in request.rows:
            if row.county:
                county_set.add(row.county.strip().upper().replace(" COUNTY", ""))
        bg_counties = []
        for name in county_set:
            result = lookup_county(name)
            if result:
                county_code, district_code, canonical = result
                bg_counties.append({
                    "county_name": canonical,
                    "county_code": county_code,
                    "district": district_code,
                })
        if bg_counties:
            background_tasks.add_task(_background_county_download, bg_counties)

    return FetchMissingResult(
        updated_rows=updated_rows,
        matched_count=matched,
        still_missing_count=len(request.rows) - matched,
        counties_downloaded=county_download_infos,
    )


async def _background_county_download(counties: list[dict]) -> None:
    """Download full county RRC data in the background to backfill Firestore."""
    logger.info("Background county download starting for %d counties: %s",
                len(counties), [c["county_name"] for c in counties])
    try:
        results = await ensure_counties_fresh(counties)
        downloaded = sum(1 for r in results if r["status"] == "downloaded")
        fresh = sum(1 for r in results if r["status"] == "fresh")
        failed = sum(1 for r in results if r["status"] == "failed")
        logger.info("Background county download complete: %d downloaded, %d fresh, %d failed",
                    downloaded, fresh, failed)
    except Exception as e:
        logger.warning("Background county download failed: %s", e)


def _apply_rrc_info(row, rrc_info: dict, WellType) -> None:
    """Apply RRC lookup results to a row."""
    row.rrc_acres = rrc_info.get("acres")
    well_type_str = rrc_info.get("type", "")
    if well_type_str == "oil":
        row.well_type = WellType.OIL
    elif well_type_str == "gas":
        row.well_type = WellType.GAS
    elif well_type_str == "both":
        row.well_type = WellType.BOTH

    # Recalculate est_nra if we now have acres
    if row.rrc_acres and row.interest:
        row.est_nra = round(row.rrc_acres * row.interest, 6)
        if row.estimated_monthly_revenue and row.est_nra > 0:
            row.dollars_per_nra = round(
                row.estimated_monthly_revenue / row.est_nra, 2
            )

    row.notes = None  # Clear "Not found" note


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
        sheet_name = (request.filename or "MH").replace("_proration_export", "").replace("_export", "")
        excel_bytes = to_excel(request.rows, sheet_name=sheet_name)
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

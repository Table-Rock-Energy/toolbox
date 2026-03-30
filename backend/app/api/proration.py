"""API routes for Proration tool."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Annotated, Optional, Union

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

from app.core.ingestion import file_response, persist_job_result, validate_upload
from app.models.proration import (
    ExportRequest,
    FetchMissingRequest,
    MineralHolderRow,
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
from app.services.storage_service import rrc_storage
from app.services.rrc_background import (
    get_active_rrc_sync_job,
    get_rrc_sync_job,
    start_rrc_background_download,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def split_lease_number(rrc_lease: str) -> list[str]:
    """Split compound lease numbers separated by / or , into individual leases."""
    import re

    if not rrc_lease:
        return []
    parts = re.split(r"[/,]", rrc_lease)
    return [p.strip() for p in parts if p.strip()]


def split_compound_lease(rrc_lease: str, fallback_district: str = "") -> list[tuple[str, str]]:
    """Split compound lease and resolve district for each part.

    District inheritance: first part's district propagates to subsequent
    parts that lack one. Falls back to fallback_district if no part has one.

    Returns list of (district, lease_number) tuples.
    Returns empty list for single/non-compound leases.
    """
    import re

    if not rrc_lease:
        return []
    raw_parts = re.split(r"[/,]", rrc_lease)
    parts = [p.strip() for p in raw_parts if p.strip()]
    if len(parts) <= 1:
        return []

    resolved: list[tuple[str, str]] = []
    inherited_district = fallback_district
    for part in parts:
        if "-" in part:
            d, ln = part.split("-", 1)
            inherited_district = d.strip()
            resolved.append((inherited_district, ln.strip()))
        else:
            resolved.append((inherited_district, part))
    return resolved


@router.get("/health")
async def health_check() -> dict:
    """Health check endpoint for proration tool."""
    return {"status": "healthy", "service": "proration"}


@router.get("/rrc/status")
async def get_rrc_status() -> dict:
    """Get status of RRC proration data from CSV files and database."""
    status = rrc_data_service.get_data_status()

    try:
        from app.core.database import async_session_maker
        from app.services import db_service

        async with async_session_maker() as session:
            # Try O(1) cached read first
            db_status = await db_service.get_rrc_cached_status(session)
            if db_status is None:
                # Cache miss — fall back to expensive queries
                db_status = await db_service.get_rrc_data_status(session)

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
            from app.core.database import async_session_maker
            from app.services import db_service
            async with async_session_maker() as session:
                db_status = await db_service.get_rrc_data_status(session)
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
        from app.core.database import async_session_maker
        from app.services import db_service
        from app.services.proration.rrc_county_codes import TEXAS_COUNTY_CODES

        async with async_session_maker() as session:
            all_keys = await db_service.get_all_tracked_county_keys(session)
            if not all_keys:
                return {"message": "No tracked counties", "refreshed": 0, "total": 0}

            stale_keys = await db_service.get_stale_counties(session, all_keys)
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
    """Manually sync existing CSV data to the database (row-by-row upsert)."""
    try:
        result = await rrc_data_service.sync_to_database("both")
        return result
    except Exception as e:
        logger.exception("Database sync failed: %s", e)
        raise HTTPException(
            status_code=500,
            detail=f"Database sync failed: {e!s}",
        ) from e


@router.post("/rrc/import-csv")
async def import_csv_to_database() -> dict:
    """Bulk-import existing RRC CSV files from disk into PostgreSQL.

    Uses INSERT ON CONFLICT for fast batch upserts (~220K records).
    After import, invalidates and re-prewarms the in-memory cache.
    """
    from datetime import timezone

    from app.core.database import async_session_maker
    from app.services import db_service
    from app.services.proration.rrc_cache import invalidate_cache, prewarm_rrc_cache
    from app.services.proration.rrc_data_service import _csv_bytes_to_upsert_rows

    oil_count = 0
    gas_count = 0
    errors = []

    # Import oil CSV
    try:
        oil_bytes = rrc_storage.get_oil_data()
        if oil_bytes:
            oil_rows = _csv_bytes_to_upsert_rows(oil_bytes)
            if oil_rows:
                async with async_session_maker() as session:
                    oil_count, _ = await db_service.bulk_upsert_rrc_oil(session, oil_rows)
                    await session.commit()
                logger.info("Imported %d oil records to PostgreSQL", oil_count)
        else:
            errors.append("Oil CSV not found on disk")
    except Exception as e:
        logger.exception("Oil CSV import failed: %s", e)
        errors.append(f"Oil import error: {e!s}")

    # Import gas CSV
    try:
        gas_bytes = rrc_storage.get_gas_data()
        if gas_bytes:
            gas_rows = _csv_bytes_to_upsert_rows(gas_bytes)
            if gas_rows:
                async with async_session_maker() as session:
                    gas_count, _ = await db_service.bulk_upsert_rrc_gas(session, gas_rows)
                    await session.commit()
                logger.info("Imported %d gas records to PostgreSQL", gas_count)
        else:
            errors.append("Gas CSV not found on disk")
    except Exception as e:
        logger.exception("Gas CSV import failed: %s", e)
        errors.append(f"Gas import error: {e!s}")

    # Record sync entry
    try:
        now = datetime.now(timezone.utc)
        async with async_session_maker() as session:
            sync = await db_service.start_rrc_sync(session, "both")
            await db_service.complete_rrc_sync(
                session,
                sync_id=sync.id,
                total_records=oil_count + gas_count,
                new_records=oil_count + gas_count,
                updated_records=0,
                unchanged_records=0,
                success=not errors,
                error_message="; ".join(errors) if errors else None,
            )
            # Update metadata cache
            await db_service.update_rrc_metadata_counts(
                session,
                oil_rows=oil_count,
                gas_rows=gas_count,
                last_sync_at=now,
                new_records=oil_count + gas_count,
            )
            await session.commit()
    except Exception as e:
        logger.warning("Could not record sync entry: %s", e)

    # Invalidate and re-prewarm cache from database
    invalidate_cache()
    rrc_data_service._combined_lookup = None
    rrc_data_service._oil_lookup = None
    rrc_data_service._gas_lookup = None
    try:
        await prewarm_rrc_cache()
    except Exception as e:
        logger.warning("Cache re-prewarm failed: %s", e)

    total = oil_count + gas_count
    return {
        "success": not errors,
        "message": f"Imported {total:,} records ({oil_count:,} oil, {gas_count:,} gas)",
        "oil_records": oil_count,
        "gas_records": gas_count,
        "total_records": total,
        "errors": errors or None,
    }


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

        # Post-process: programmatic fixes (name casing) + AI verification
        try:
            from app.services.data_enrichment_pipeline import auto_enrich

            row_dicts = [r.model_dump() for r in result.rows]
            pp_result = await auto_enrich("proration", row_dicts)
            result.rows = [MineralHolderRow(**d) for d in row_dicts]
            result.post_process = pp_result
        except Exception as e:
            logger.warning("Post-processing failed, returning raw results: %s", e)

        logger.info(
            "Processed %d rows (%d matched, %d failed) from %s",
            result.processed_rows, result.matched_rows, result.failed_rows,
            file.filename,
        )

        # Persist to database (non-blocking)
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


@router.post("/rrc/fetch-missing")
async def fetch_missing_rrc_data(request: FetchMissingRequest, background_tasks: BackgroundTasks):
    """Fetch RRC data for rows that are missing it.

    Streams NDJSON progress events:
    - {"event":"started","total":<n>}
    - {"event":"progress","phase":"db_lookup"|"rrc_query","checked":<n>,"total":<n>,"matched":<n>}
    - {"event":"complete","matched_count":<n>,"still_missing_count":<n>,"updated_rows":[...]}
    """
    import re

    from app.models.proration import WellType
    from app.services.proration.rrc_county_codes import lookup_county

    if not request.rows:
        raise HTTPException(status_code=400, detail="No rows provided")

    from app.core.database import async_session_maker
    from app.services import db_service

    async def lookup_rrc_acres(district: str, lease_number: str):
        async with async_session_maker() as session:
            return await db_service.lookup_rrc_acres(session, district, lease_number)

    async def lookup_rrc_by_lease_number(lease_number: str):
        async with async_session_maker() as session:
            return await db_service.lookup_rrc_by_lease_number(session, lease_number)

    async def _stream():
        total = len(request.rows)
        yield json.dumps({"event": "started", "total": total}) + "\n"

        try:
            # Step 1: Parse district/lease from each row and check database first
            updated_rows = []
            matched = 0
            missing_leases: list[tuple[int, str, str, str]] = []

            for i, row in enumerate(request.rows):
                district = row.district
                lease_number = row.lease_number

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

                county_code = ""
                if row.county:
                    county_result = lookup_county(row.county)
                    if county_result:
                        county_code = county_result[0]

                is_compound = False
                sub_parts: list[tuple[str, str]] = []
                if row.rrc_lease and ("/" in row.rrc_lease or "," in row.rrc_lease):
                    sub_parts = split_compound_lease(row.rrc_lease, district or "")
                    is_compound = bool(sub_parts)

                if is_compound:
                    for sub_d, sub_ln in sub_parts:
                        missing_leases.append((len(updated_rows), sub_d, sub_ln, county_code))
                    updated_rows.append(row)
                    if (i + 1) % 5 == 0:
                        yield json.dumps({"event": "progress", "phase": "db_lookup", "checked": i + 1, "total": total, "matched": matched}) + "\n"
                    continue

                rrc_info = None
                # Try district+lease first (fast doc lookup), then lease-only fallback (collection scan)
                if district and lease_number:
                    rrc_info = await lookup_rrc_acres(district, lease_number)
                if rrc_info is None and lease_number:
                    rrc_info = await lookup_rrc_by_lease_number(lease_number)

                if rrc_info:
                    _apply_rrc_info(row, rrc_info, WellType)
                    row.fetch_status = "found"
                    matched += 1
                elif district and lease_number:
                    missing_leases.append((len(updated_rows), district, lease_number, county_code))

                updated_rows.append(row)

                if (i + 1) % 5 == 0:
                    yield json.dumps({"event": "progress", "phase": "db_lookup", "checked": i + 1, "total": total, "matched": matched}) + "\n"

            # Final db_lookup progress
            yield json.dumps({"event": "progress", "phase": "db_lookup", "checked": total, "total": total, "matched": matched}) + "\n"

            # Step 2: Individual RRC queries for missing leases
            if missing_leases:
                unique_leases = list({(d, ln, cc) for _, d, ln, cc in missing_leases})
                logger.info("fetch-missing: querying RRC for %d individual leases", len(unique_leases))

                yield json.dumps({"event": "progress", "phase": "rrc_query", "checked": 0, "total": len(unique_leases), "matched": matched}) + "\n"

                try:
                    individual_results = await fetch_individual_leases(unique_leases)
                except Exception as e:
                    logger.warning("Individual lease fetch failed: %s", e)
                    individual_results = {}

                yield json.dumps({"event": "progress", "phase": "rrc_query", "checked": len(unique_leases), "total": len(unique_leases), "matched": matched}) + "\n"

                from collections import defaultdict
                row_lease_map: dict[int, list[tuple[str, str, str]]] = defaultdict(list)
                for row_idx, d, ln, cc in missing_leases:
                    row_lease_map[row_idx].append((d, ln, cc))

                for row_idx, lease_parts in row_lease_map.items():
                    row = updated_rows[row_idx]
                    if len(lease_parts) == 1:
                        d, ln, _cc = lease_parts[0]
                        rrc_info = individual_results.get((d, ln))
                        if rrc_info:
                            _apply_rrc_info(row, rrc_info, WellType)
                            row.fetch_status = "found"
                            matched += 1
                        else:
                            row.fetch_status = "not_found"
                    else:
                        sub_results = []
                        first_found_info = None
                        for d, ln, _cc in lease_parts:
                            rrc_info = individual_results.get((d, ln))
                            if rrc_info:
                                sub_results.append({"district": d, "lease_number": ln, "status": "found", "acres": rrc_info.get("acres")})
                                if first_found_info is None:
                                    first_found_info = rrc_info
                            else:
                                sub_results.append({"district": d, "lease_number": ln, "status": "not_found", "acres": None})
                        row.sub_lease_results = sub_results
                        if first_found_info:
                            _apply_rrc_info(row, first_found_info, WellType)
                            row.fetch_status = "split_lookup"
                            matched += 1
                        else:
                            row.fetch_status = "not_found"

                # Background persist
                if individual_results:
                    background_tasks.add_task(_background_persist_individual, individual_results)

            # Mark rows still missing
            RRC_SEARCH_URL = "https://webapps2.rrc.texas.gov/EWA/oilProQueryAction.do"
            for row in updated_rows:
                if not row.rrc_acres and row.notes and "Not found" in row.notes:
                    d = row.district or ""
                    ln = row.lease_number or ""
                    row.notes = f"Not found in RRC|{RRC_SEARCH_URL}?district={d}&lease={ln}"

            logger.info("fetch-missing: matched %d of %d rows", matched, total)

            # Background county download
            county_set: set[str] = set()
            for row in request.rows:
                if row.county:
                    county_set.add(row.county.strip().upper().replace(" COUNTY", ""))
            bg_counties = []
            for name in county_set:
                result = lookup_county(name)
                if result:
                    county_code, district_code, canonical = result
                    bg_counties.append({"county_name": canonical, "county_code": county_code, "district": district_code})
            if bg_counties:
                background_tasks.add_task(_background_county_download, bg_counties)

            # Serialize updated rows via Pydantic
            serialized_rows = [r.model_dump() for r in updated_rows]

            yield json.dumps({
                "event": "complete",
                "matched_count": matched,
                "still_missing_count": total - matched,
                "updated_rows": serialized_rows,
            }) + "\n"

        except Exception as e:
            logger.exception("fetch-missing stream error: %s", e)
            yield json.dumps({
                "event": "error",
                "message": f"RRC lookup failed: {e!s}",
            }) + "\n"

    return StreamingResponse(_stream(), media_type="application/x-ndjson")


async def _background_persist_individual(results: dict[tuple[str, str], dict]) -> None:
    """Persist individually-fetched RRC data to database for cache."""
    try:
        from app.core.database import async_session_maker
        from app.services import db_service

        async with async_session_maker() as session:
            for (district, lease_number), info in results.items():
                await db_service.upsert_rrc_oil_record(
                    session,
                    district=district,
                    lease_number=lease_number,
                    operator_name=info.get("operator"),
                    lease_name=info.get("lease_name"),
                    field_name=None,
                    county=None,
                    unit_acres=info.get("acres"),
                )
            await session.commit()
        logger.info("Background persist: saved %d individual RRC results to database", len(results))
    except Exception as e:
        logger.warning("Background persist failed: %s", e)


async def _background_county_download(counties: list[dict]) -> None:
    """Download full county RRC data in the background to backfill database."""
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

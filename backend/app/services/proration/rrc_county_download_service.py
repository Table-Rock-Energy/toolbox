"""On-demand county-level RRC oil data downloads.

Downloads oil proration data per-county from RRC, chunked by well type,
to work around RRC record limits on bulk district downloads.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from io import BytesIO

import pandas as pd

from app.services.proration.rrc_county_codes import WELL_TYPE_CODES
from app.services.proration.rrc_data_service import (
    OIL_SEARCH_URL,
    create_rrc_session,
    rrc_data_service,
)

logger = logging.getLogger(__name__)

# Timeouts
SEARCH_TIMEOUT = 60
CSV_TIMEOUT = 120
MAX_RETRIES = 2
RETRY_BACKOFFS = [30, 60]
COUNTY_BUDGET_SECONDS = 300  # 5 min per county
TOTAL_BUDGET_SECONDS = 300  # 5 min total for all counties in one upload


async def ensure_counties_fresh(
    counties: list[dict],
) -> list[dict]:
    """Check freshness and download stale counties.

    Args:
        counties: List of dicts with county_name, county_code, district

    Returns:
        List of dicts with county_name, status, records_downloaded, duration_seconds
    """
    if not counties:
        return []

    try:
        from app.services.firestore_service import get_stale_counties
    except ImportError:
        logger.warning("Firestore not available, skipping county freshness check")
        return [
            {"county_name": c["county_name"], "status": "skipped", "records_downloaded": 0}
            for c in counties
        ]

    # Build keys and check staleness
    county_map = {}
    keys = []
    for c in counties:
        key = f"{c['district']}-{c['county_code']}"
        keys.append(key)
        county_map[key] = c

    stale_keys = await get_stale_counties(keys)
    stale_set = set(stale_keys)

    results = []
    total_start = time.monotonic()

    for key in keys:
        county = county_map[key]
        if key not in stale_set:
            results.append({
                "county_name": county["county_name"],
                "status": "fresh",
                "records_downloaded": 0,
                "duration_seconds": 0.0,
            })
            continue

        # Check total budget
        elapsed = time.monotonic() - total_start
        if elapsed > TOTAL_BUDGET_SECONDS:
            logger.warning(
                "Total county download budget exceeded (%.0fs), skipping %s",
                elapsed, county["county_name"],
            )
            results.append({
                "county_name": county["county_name"],
                "status": "skipped",
                "records_downloaded": 0,
                "duration_seconds": 0.0,
            })
            continue

        # Download this county
        county_start = time.monotonic()
        success, message, record_count = await _download_county_oil(
            district=county["district"],
            county_code=county["county_code"],
            county_name=county["county_name"],
        )
        duration = time.monotonic() - county_start

        status = "downloaded" if success else "failed"
        results.append({
            "county_name": county["county_name"],
            "status": status,
            "records_downloaded": record_count,
            "duration_seconds": round(duration, 1),
        })

        # Update freshness tracking
        try:
            from app.services.firestore_service import update_county_status
            await update_county_status(key, {
                "county_code": county["county_code"],
                "county_name": county["county_name"],
                "district": county["district"],
                "last_downloaded_at": datetime.utcnow() if success else None,
                "oil_record_count": record_count,
                "status": "success" if success else "failed",
                "error": None if success else message,
            })
        except Exception as e:
            logger.warning("Failed to update county status for %s: %s", key, e)

    # Invalidate in-memory cache so lookups pick up new data
    downloaded_any = any(r["status"] == "downloaded" for r in results)
    if downloaded_any:
        rrc_data_service._combined_lookup = None

    downloaded_count = sum(1 for r in results if r["status"] == "downloaded")
    fresh_count = sum(1 for r in results if r["status"] == "fresh")
    failed_count = sum(1 for r in results if r["status"] == "failed")
    logger.info(
        "County download summary: %d fresh, %d downloaded, %d failed",
        fresh_count, downloaded_count, failed_count,
    )

    return results


async def _download_county_oil(
    district: str,
    county_code: str,
    county_name: str,
) -> tuple[bool, str, int]:
    """Download oil proration data for one county, chunked by well type.

    Returns:
        (success, message, total_records)
    """
    logger.info("Downloading oil data for %s County (district=%s, code=%s)", county_name, district, county_code)

    session = create_rrc_session()
    all_dfs: list[pd.DataFrame] = []
    well_types_downloaded: list[str] = []

    for well_type in WELL_TYPE_CODES:
        success, content = _download_well_type_chunk(session, district, county_code, well_type)
        if not success or content is None:
            continue

        try:
            df = pd.read_csv(BytesIO(content), skiprows=2, low_memory=False)
            if len(df) > 0:
                all_dfs.append(df)
                well_types_downloaded.append(well_type)
                logger.debug(
                    "  %s/%s well_type=%s: %d rows",
                    county_name, county_code, well_type, len(df),
                )
        except Exception as e:
            logger.warning(
                "Failed to parse CSV for %s well_type=%s: %s",
                county_name, well_type, e,
            )

    if not all_dfs:
        logger.info("No oil data found for %s County", county_name)
        return True, "No records found", 0

    combined = pd.concat(all_dfs, ignore_index=True)
    total_records = len(combined)
    logger.info("Downloaded %d oil records for %s County", total_records, county_name)

    # Upsert to Firestore
    upserted = await _upsert_county_records(combined)

    return True, f"Downloaded {total_records} records, upserted {upserted}", total_records


def _download_well_type_chunk(
    session,
    district: str,
    county_code: str,
    well_type: str,
) -> tuple[bool, bytes | None]:
    """Download one well-type chunk from RRC.

    Returns:
        (success, csv_bytes_or_none)
    """
    for attempt in range(MAX_RETRIES + 1):
        try:
            # Step 1: Search POST
            search_data = {
                "methodToCall": "search",
                "searchArgs.districtCodeArg": district,
                "searchArgs.countyCodeArg": county_code,
                "searchArgs.wellTypeArg": well_type,
            }
            resp = session.post(OIL_SEARCH_URL, data=search_data, timeout=SEARCH_TIMEOUT)
            resp.raise_for_status()

            # Check if search returned results (HTML page with results)
            if "No records found" in resp.text or "0 records" in resp.text.lower():
                return True, None

            # Step 2: CSV download POST
            csv_data = {
                "methodToCall": "generateOilProrationReportCsv",
            }
            resp = session.post(OIL_SEARCH_URL, data=csv_data, timeout=CSV_TIMEOUT)
            resp.raise_for_status()

            # Verify we got CSV not HTML
            content_start = resp.content[:500].decode("utf-8", errors="ignore")
            if "<html" in content_start.lower() or "<!doctype" in content_start.lower():
                logger.debug(
                    "RRC returned HTML for district=%s county=%s well_type=%s (attempt %d)",
                    district, county_code, well_type, attempt + 1,
                )
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_BACKOFFS[attempt])
                    # Create fresh session for retry
                    session = create_rrc_session()
                    continue
                return False, None

            return True, resp.content

        except Exception as e:
            logger.warning(
                "Error downloading district=%s county=%s well_type=%s (attempt %d): %s",
                district, county_code, well_type, attempt + 1, e,
            )
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFFS[attempt])
                session = create_rrc_session()
                continue
            return False, None

    return False, None


async def _upsert_county_records(df: pd.DataFrame) -> int:
    """Upsert county oil records to Firestore."""
    try:
        from app.services.firestore_service import upsert_rrc_oil_record
    except ImportError:
        logger.warning("Firestore not available, skipping upsert")
        return 0

    count = 0
    for _, row in df.iterrows():
        try:
            district = str(row.get("District", "")).strip()
            if district and district[0].isdigit():
                district = district.zfill(2) if len(district) == 1 else district

            lease_number = str(row.get("Lease No.", "")).strip()
            if not district or not lease_number:
                continue

            acres = float(row["Acres"]) if pd.notna(row.get("Acres")) else None

            await upsert_rrc_oil_record(
                district=district,
                lease_number=lease_number,
                operator_name=str(row.get("Operator Name", "")) if pd.notna(row.get("Operator Name")) else None,
                lease_name=str(row.get("Lease Name", "")) if pd.notna(row.get("Lease Name")) else None,
                field_name=str(row.get("Field Name", "")) if pd.notna(row.get("Field Name")) else None,
                county=str(row.get("County", "")) if pd.notna(row.get("County")) else None,
                unit_acres=acres,
            )
            count += 1
        except Exception as e:
            if count < 5:
                logger.warning("Error upserting record: %s", e)

    return count

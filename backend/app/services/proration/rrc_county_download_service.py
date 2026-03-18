"""On-demand county-level RRC oil data downloads.

Downloads oil proration data per-county from RRC, chunked by well type,
to work around RRC record limits on bulk district downloads.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from io import BytesIO

import pandas as pd

from app.services.proration.rrc_county_codes import WELL_TYPE_CODES
from app.services.proration.rrc_data_service import (
    OIL_SEARCH_URL,
    create_rrc_session,
    rrc_data_service,
)

logger = logging.getLogger(__name__)

# Timeouts — kept short so we fail fast and fall back to individual queries
SEARCH_TIMEOUT = 30
CSV_TIMEOUT = 120
MAX_RETRIES = 1
RETRY_BACKOFFS = [10]
COUNTY_BUDGET_SECONDS = 180  # 3 min per county before giving up
TOTAL_BUDGET_SECONDS = 300   # 5 min total for all counties


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
                "last_downloaded_at": datetime.now(timezone.utc) if success else None,
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
    _trace("=== Downloading %s County (district=%s, code=%s) ===", county_name, district, county_code)

    session = create_rrc_session()
    _warm_rrc_session(session)
    _human_delay(1.5, 3.0)

    all_dfs: list[pd.DataFrame] = []
    well_types_downloaded: list[str] = []
    county_start = time.monotonic()

    for well_type in WELL_TYPE_CODES:
        # Bail if county budget exceeded (RRC is unresponsive)
        elapsed = time.monotonic() - county_start
        if elapsed > COUNTY_BUDGET_SECONDS:
            _trace("%s County: budget exceeded (%.0fs), stopping well type iteration", county_name, elapsed)
            break

        _trace("--- %s County: trying well_type=%s (%.0fs elapsed) ---", county_name, well_type, elapsed)
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
            _trace(
                "SEARCH: district=%s county=%s well_type=%s (attempt %d/%d, timeout=%ds)",
                district, county_code, well_type, attempt + 1, MAX_RETRIES + 1, SEARCH_TIMEOUT,
            )
            t0 = time.monotonic()
            resp = session.post(OIL_SEARCH_URL, data=search_data, timeout=SEARCH_TIMEOUT)
            elapsed = time.monotonic() - t0
            _trace(
                "SEARCH response: status=%d, %.1fs, size=%d bytes",
                resp.status_code, elapsed, len(resp.content),
            )
            resp.raise_for_status()

            # Save search HTML for debugging (first attempt only)
            if attempt == 0:
                try:
                    debug_path = f"/tmp/rrc_search_{district}_{county_code}_{well_type}.html"
                    with open(debug_path, "w") as f:
                        f.write(resp.text)
                    _trace("Saved search HTML to %s", debug_path)
                except Exception:
                    pass

            # Check if search returned results (HTML page with results)
            if "No records found" in resp.text or "No results found" in resp.text or "0 records" in resp.text.lower():
                _trace("SEARCH: no records found for well_type=%s", well_type)
                return True, None

            # Step 2: CSV download POST
            csv_data = {
                "methodToCall": "generateOilProrationReportCsv",
            }
            _trace("CSV download: well_type=%s (timeout=%ds)", well_type, CSV_TIMEOUT)
            t0 = time.monotonic()
            resp = session.post(OIL_SEARCH_URL, data=csv_data, timeout=CSV_TIMEOUT)
            elapsed = time.monotonic() - t0
            _trace(
                "CSV response: status=%d, %.1fs, size=%d bytes",
                resp.status_code, elapsed, len(resp.content),
            )
            resp.raise_for_status()

            # Verify we got CSV not HTML
            content_start = resp.content[:500].decode("utf-8", errors="ignore")
            if "<html" in content_start.lower() or "<!doctype" in content_start.lower():
                _trace(
                    "CSV got HTML instead! district=%s county=%s well_type=%s (attempt %d)",
                    district, county_code, well_type, attempt + 1,
                )
                if attempt < MAX_RETRIES:
                    _trace("Retrying in %ds...", RETRY_BACKOFFS[attempt])
                    time.sleep(RETRY_BACKOFFS[attempt])
                    session = create_rrc_session()
                    continue
                return False, None

            _trace("CSV success: well_type=%s, %d bytes", well_type, len(resp.content))
            return True, resp.content

        except Exception as e:
            elapsed = time.monotonic() - t0 if 't0' in dir() else 0
            _trace(
                "ERROR: district=%s county=%s well_type=%s (attempt %d, %.1fs): %s: %s",
                district, county_code, well_type, attempt + 1, elapsed,
                type(e).__name__, e,
            )
            if attempt < MAX_RETRIES:
                _trace("Retrying in %ds...", RETRY_BACKOFFS[attempt])
                time.sleep(RETRY_BACKOFFS[attempt])
                session = create_rrc_session()
                continue
            return False, None

    return False, None


def _trace(msg: str, *args) -> None:
    """Print trace messages that always show in terminal output."""
    formatted = msg % args if args else msg
    print(f"[RRC-TRACE] {formatted}", flush=True)
    logger.info(formatted)


def _warm_rrc_session(session) -> bool:
    """Visit the RRC query page first to establish cookies/session, like a human would.

    Returns True if the page loaded successfully.
    """
    try:
        _trace("Warming session: GET %s ...", OIL_SEARCH_URL)
        resp = session.get(OIL_SEARCH_URL, timeout=30)
        resp.raise_for_status()
        _trace("Session warmed: status=%d, cookies=%d", resp.status_code, len(session.cookies))
        return True
    except Exception as e:
        _trace("Session warm FAILED: %s", e)
        return False


def _human_delay(min_seconds: float = 1.5, max_seconds: float = 4.0) -> None:
    """Random delay between requests to simulate human browsing."""
    import random
    delay = random.uniform(min_seconds, max_seconds)
    time.sleep(delay)


def _parse_rrc_html(html: str) -> list[dict]:
    """Parse RRC oil proration search results from HTML response.

    Extracts lease data directly from HTML instead of downloading CSV,
    which is much faster and avoids CSV generation timeouts on RRC's server.

    Returns list of dicts with keys: district, lease_number, lease_name,
    operator_name, field_name, acres, well_type_label.
    """
    import re

    records: list[dict] = []

    # Find lease detail links which mark the start of each data row.
    # Pattern: leaseDetailAction.do?...&distCode=XX&leaseNo=YYYYY&...
    # After the lease link, the subsequent <td> cells contain the row data.
    lease_pattern = re.compile(
        r'leaseDetailAction\.do\?searchType=distLease[^"]*distCode=(\w+)[^"]*leaseNo=(\d+)',
    )

    # Split HTML by lease detail links (distLease type, which appears once per row)
    parts = lease_pattern.split(html)
    # parts[0] = before first match, then groups of (district, lease_no, trailing_html)

    if len(parts) < 4:
        return records

    for i in range(1, len(parts) - 2, 3):
        dist = parts[i].strip().zfill(2)
        lease_no = parts[i + 1].strip()
        trailing = parts[i + 2]

        # Extract the <td> values that follow this lease link
        # The order after the lease link cell is:
        #   lease_name, well_no, field_no, field_name, schedule,
        #   operator_no, operator_name, (empty/county), potential, gas_oil_ratio, acres, ...
        td_pattern = re.compile(r'<td[^>]*>(.*?)</td>', re.DOTALL)
        tds = td_pattern.findall(trailing)

        # Clean HTML tags from td contents
        def clean(val: str) -> str:
            return re.sub(r'<[^>]+>', '', val).strip()

        td_vals = [clean(td) for td in tds]

        if len(td_vals) < 12:
            continue

        # Extract fields from the td sequence
        # td[0] = Links dropdown (skip), td[1] = lease_name, td[2] = well_no,
        # td[3] = field_no, td[4] = field_name, td[5] = schedule,
        # td[6] = operator_no, td[7] = operator_name, td[8] = unit_no,
        # td[9] = potential, td[10] = gas_oil_ratio, td[11] = acres,
        # td[12] = daily_allowable, td[13] = well_type
        lease_name = td_vals[1] if len(td_vals) > 1 and td_vals[1] else None
        field_name = td_vals[4] if len(td_vals) > 4 else None
        operator_name = td_vals[7] if len(td_vals) > 7 else None
        acres_str = td_vals[11] if len(td_vals) > 11 else None
        well_type_label = td_vals[13] if len(td_vals) > 13 else None

        acres = None
        if acres_str:
            try:
                acres = float(acres_str)
            except (ValueError, TypeError):
                pass

        # Deduplicate: keep the first record per lease (or the one with highest acres)
        records.append({
            "district": dist,
            "lease_number": lease_no,
            "lease_name": lease_name,
            "operator_name": operator_name,
            "field_name": field_name,
            "acres": acres,
            "well_type_label": well_type_label,
        })

    # Deduplicate by lease: keep record with max acres
    best: dict[tuple[str, str], dict] = {}
    for rec in records:
        key = (rec["district"], rec["lease_number"])
        existing = best.get(key)
        if existing is None or (rec["acres"] or 0) > (existing["acres"] or 0):
            best[key] = rec

    return list(best.values())


MAX_CONCURRENT_RRC = 8


async def fetch_individual_leases(
    leases: list[tuple[str, str, str]],
) -> dict[tuple[str, str], dict]:
    """Fetch individual leases from RRC with semaphore-throttled concurrency.

    Each concurrent worker creates its own requests.Session (thread-safe since
    each is independent). Semaphore limits to MAX_CONCURRENT_RRC concurrent.

    Args:
        leases: List of (district, lease_number, county_code) tuples.
                county_code can be empty string if unknown.

    Returns:
        Dict mapping (district, lease_number) -> RRC record data
    """
    import asyncio

    if not leases:
        return {}

    try:
        from app.services.firestore_service import upsert_rrc_oil_record
    except ImportError:
        logger.warning("Firestore not available for individual lease fetch")
        return {}

    sem = asyncio.Semaphore(MAX_CONCURRENT_RRC)
    results: dict[tuple[str, str], dict] = {}
    individual_timeout = 60

    async def fetch_one(district: str, lease_number: str, county_code: str) -> None:
        async with sem:
            session = create_rrc_session()
            try:
                _warm_rrc_session(session)
                _human_delay(1.0, 2.0)

                search_data = {
                    "methodToCall": "search",
                    "searchArgs.districtCodeArg": district,
                    "searchArgs.leaseNumberArg": lease_number,
                }
                if county_code:
                    search_data["searchArgs.countyCodeArg"] = county_code

                _trace("Individual search: district=%s lease=%s county=%s", district, lease_number, county_code or "none")
                loop = asyncio.get_event_loop()
                resp = await loop.run_in_executor(
                    None,
                    lambda: session.post(OIL_SEARCH_URL, data=search_data, timeout=individual_timeout),
                )
                resp.raise_for_status()

                if "No records found" in resp.text or "No results found" in resp.text or "0 records" in resp.text.lower():
                    _trace("No RRC data for %s-%s", district, lease_number)
                    return

                parsed = _parse_rrc_html(resp.text)
                if not parsed:
                    return

                for rec in parsed:
                    d = rec["district"]
                    ln = rec["lease_number"]
                    acres = rec["acres"]
                    await upsert_rrc_oil_record(
                        district=d, lease_number=ln,
                        operator_name=rec.get("operator_name"),
                        lease_name=rec.get("lease_name"),
                        field_name=rec.get("field_name"),
                        county=None, unit_acres=acres,
                    )
                    results[(d, ln)] = {
                        "acres": acres, "type": "oil",
                        "operator": rec.get("operator_name"),
                        "lease_name": rec.get("lease_name"),
                    }
            except Exception as e:
                logger.warning("Individual RRC fetch failed for %s-%s: %s", district, lease_number, e)

    tasks = [fetch_one(d, ln, cc) for d, ln, cc in leases]
    await asyncio.gather(*tasks, return_exceptions=True)
    logger.info("Individual lease fetch: %d of %d leases found", len(results), len(leases))
    return results


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

"""CSV processing service for mineral holder data."""

from __future__ import annotations

import asyncio
import io
import logging
import re
from typing import TYPE_CHECKING, Optional

import pandas as pd

from app.models.proration import (
    FilterOptions,
    MineralHolderRow,
    ProcessingOptions,
    ProcessingResult,
    WellType,
)
from app.services.proration.calculation_service import calculate_metrics
from app.services.proration.legal_description_parser import parse_legal_description
from app.services.proration.rrc_cache import get_from_cache, update_cache
from app.services.proration.rrc_county_codes import lookup_county
from app.services.proration.rrc_data_service import rrc_data_service

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Whether to use database for RRC lookups
_use_database = True


async def _lookup_from_database(
    district: str, lease_number: str
) -> Optional[dict]:
    """Look up RRC data from PostgreSQL database."""
    try:
        from app.core.database import async_session_maker
        from app.services import db_service
        async with async_session_maker() as session:
            return await db_service.lookup_rrc_acres(session, district, lease_number)
    except Exception as e:
        logger.debug(f"Database lookup failed: {e}")
        return None


async def _lookup_by_lease_from_database(lease_number: str) -> Optional[dict]:
    """Look up RRC data by lease number only from PostgreSQL."""
    try:
        from app.core.database import async_session_maker
        from app.services import db_service
        async with async_session_maker() as session:
            return await db_service.lookup_rrc_by_lease_number(session, lease_number)
    except Exception as e:
        logger.debug(f"Database lease lookup failed: {e}")
        return None


def parse_currency(value) -> float | None:
    """Parse a currency string like '$10.49' to float."""
    if pd.isna(value) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    # Remove $ and commas, then convert
    try:
        return float(str(value).replace('$', '').replace(',', '').strip())
    except (ValueError, TypeError):
        return None


# Required columns for CSV validation
REQUIRED_COLUMNS = [
    "County",
    "Owner",
    "Interest",
    "Interest Type",
    "Appraisal Value",
    "Legal Description",
    "Property",
    "Operator",
    "Raw RRC",
    "RRC Lease #",
    "New Record",
    "Estimated Monthly Revenue",
]


async def process_csv(
    file_bytes: bytes,
    filename: str,
    options: ProcessingOptions,
) -> ProcessingResult:
    """
    Process a CSV file and return processed rows.

    Args:
        file_bytes: CSV file content as bytes
        filename: Original filename
        options: Processing options

    Returns:
        ProcessingResult with processed rows
    """
    try:
        # Read CSV into pandas DataFrame
        df = pd.read_csv(io.BytesIO(file_bytes))

        # Validate required columns
        missing_columns = [col for col in REQUIRED_COLUMNS if col not in df.columns]
        if missing_columns:
            return ProcessingResult(
                success=False,
                error_message=f"Missing required columns: {', '.join(missing_columns)}",
                source_filename=filename,
            )

        total_rows = len(df)

        # Apply filters
        df_filtered = apply_filters(df, options.filters)
        filtered_rows = len(df_filtered)

        # Convert to MineralHolderRow objects using 3-phase approach:
        # Phase 1: Parse rows, check cache, collect misses
        # Phase 2: Batch database reads for all cache misses (PERF-03)
        # Phase 3: Build MineralHolderRow objects using cached results
        rows: list[MineralHolderRow] = []
        failed_count = 0
        matched_count = 0

        # Phase 1: Parse all rows, check in-memory cache, collect misses
        parsed_rows: list[dict] = []
        cache_misses: set[tuple[str, str]] = set()  # (district, lease_number)
        lease_only_misses: set[str] = set()  # lease_number only

        for idx, row_data in df_filtered.iterrows():
            try:
                rrc_lease_str = row_data.get("RRC Lease #") or row_data.get("Raw RRC", "")
                district, lease_number = rrc_data_service.parse_rrc_lease(rrc_lease_str)

                block, section, abstract = parse_legal_description(
                    row_data.get("Legal Description", "")
                )
                well_type = determine_well_type(row_data, options.well_type_override)

                # Determine lookup path and check cache
                lookup_type = None  # "district", "lease_only", or None
                lease_only = None

                if district and lease_number:
                    cached = get_from_cache(district, lease_number)
                    if cached is None and _use_database:
                        cache_misses.add((district, lease_number))
                    lookup_type = "district"
                elif lease_number or rrc_lease_str:
                    lease_only = lease_number
                    if not lease_only and rrc_lease_str:
                        numbers = re.findall(r'\d+', str(rrc_lease_str))
                        if numbers:
                            lease_only = numbers[0]
                    if lease_only:
                        # For lease-only, cache key uses empty district
                        cached = get_from_cache("", lease_only)
                        if cached is None and _use_database:
                            lease_only_misses.add(lease_only)
                        lookup_type = "lease_only"

                parsed_rows.append({
                    "idx": idx,
                    "row_data": row_data,
                    "district": district,
                    "lease_number": lease_number,
                    "lease_only": lease_only,
                    "block": block,
                    "section": section,
                    "abstract": abstract,
                    "well_type": well_type,
                    "rrc_lease_str": rrc_lease_str,
                    "lookup_type": lookup_type,
                })
            except Exception as e:
                logger.exception(f"Error parsing row {idx}: {e}")
                failed_count += 1

        # Phase 2: Batch database reads for all cache misses (PERF-03)
        if cache_misses and _use_database:
            sem = asyncio.Semaphore(25)

            async def bounded_lookup(d: str, ln: str) -> tuple[tuple[str, str], dict | None]:
                async with sem:
                    return (d, ln), await _lookup_from_database(d, ln)

            results = await asyncio.gather(
                *[bounded_lookup(d, ln) for d, ln in cache_misses],
                return_exceptions=True,
            )

            for result in results:
                if not isinstance(result, Exception):
                    key, info = result
                    update_cache(key, info)

        if lease_only_misses and _use_database:
            sem = asyncio.Semaphore(25)

            async def bounded_lease_lookup(ln: str) -> tuple[str, dict | None]:
                async with sem:
                    return ln, await _lookup_by_lease_from_database(ln)

            lease_results = await asyncio.gather(
                *[bounded_lease_lookup(ln) for ln in lease_only_misses],
                return_exceptions=True,
            )

            for result in lease_results:
                if not isinstance(result, Exception):
                    ln, info = result
                    update_cache(("", ln), info)

        # Phase 3: Build MineralHolderRow objects using cache
        for parsed in parsed_rows:
            try:
                idx = parsed["idx"]
                row_data = parsed["row_data"]
                district = parsed["district"]
                lease_number = parsed["lease_number"]
                lease_only = parsed["lease_only"]
                block = parsed["block"]
                section = parsed["section"]
                abstract = parsed["abstract"]
                well_type = parsed["well_type"]
                rrc_lease_str = parsed["rrc_lease_str"]
                lookup_type = parsed["lookup_type"]

                rrc_acres = None
                rrc_info = None
                notes = None

                if lookup_type == "district":
                    # Check cache (now populated from Phase 2)
                    rrc_info = get_from_cache(district, lease_number)

                    # Fall back to in-memory CSV lookup
                    if rrc_info is None:
                        rrc_info = rrc_data_service.lookup_acres(district, lease_number)

                    if rrc_info:
                        rrc_acres = rrc_info.get("acres")
                        well_type_str = rrc_info.get("type", "")
                        if well_type_str == "oil":
                            well_type = WellType.OIL
                        elif well_type_str == "gas":
                            well_type = WellType.GAS
                        elif well_type_str == "both":
                            well_type = WellType.BOTH
                        row_count = rrc_info.get("row_count", 1)
                        if row_count > 1:
                            notes = f"Combined {row_count} RRC entries"
                        matched_count += 1
                    else:
                        notes = "Not found in RRC data"
                elif lookup_type == "lease_only" and lease_only:
                    # Check cache (now populated from Phase 2)
                    rrc_info = get_from_cache("", lease_only)

                    # Fall back to in-memory CSV
                    if rrc_info is None:
                        rrc_info = rrc_data_service.lookup_by_lease_number(lease_only)

                    if rrc_info:
                        rrc_acres = rrc_info.get("acres")
                        well_type_str = rrc_info.get("type", "")
                        if well_type_str == "oil":
                            well_type = WellType.OIL
                        elif well_type_str == "gas":
                            well_type = WellType.GAS
                        elif well_type_str == "both":
                            well_type = WellType.BOTH
                        districts_found = rrc_info.get("districts_found", 1)
                        if districts_found > 1:
                            notes = f"Found in {districts_found} districts, acres summed"
                        matched_count += 1
                    else:
                        notes = "Not found in RRC data"
                elif lookup_type == "lease_only":
                    notes = "No valid RRC Lease #"
                else:
                    notes = "No valid RRC Lease #"

                # Create MineralHolderRow
                mineral_row = MineralHolderRow(
                    county=str(row_data.get("County", "")).replace(" County", ""),
                    state=row_data.get("State") if pd.notna(row_data.get("State")) else None,
                    year=int(row_data.get("Year")) if pd.notna(row_data.get("Year")) else None,
                    interest_key=str(row_data.get("Interest Key", ""))
                    if pd.notna(row_data.get("Interest Key"))
                    else None,
                    owner_id=str(row_data.get("Owner ID", ""))
                    if pd.notna(row_data.get("Owner ID"))
                    else None,
                    owner=str(row_data.get("Owner", "")),
                    interest=float(row_data.get("Interest", 0))
                    if pd.notna(row_data.get("Interest"))
                    else 0.0,
                    interest_type=str(row_data.get("Interest Type", ""))
                    if pd.notna(row_data.get("Interest Type"))
                    else None,
                    appraisal_value=float(row_data.get("Appraisal Value", 0))
                    if pd.notna(row_data.get("Appraisal Value"))
                    else None,
                    legal_description=str(row_data.get("Legal Description", ""))
                    if pd.notna(row_data.get("Legal Description"))
                    else None,
                    property_id=str(row_data.get("Property ID", ""))
                    if pd.notna(row_data.get("Property ID"))
                    else None,
                    property=str(row_data.get("Property", ""))
                    if pd.notna(row_data.get("Property"))
                    else None,
                    operator=str(row_data.get("Operator", ""))
                    if pd.notna(row_data.get("Operator"))
                    else None,
                    raw_rrc=str(row_data.get("Raw RRC", ""))
                    if pd.notna(row_data.get("Raw RRC"))
                    else None,
                    rrc_lease=str(row_data.get("RRC Lease #", ""))
                    if pd.notna(row_data.get("RRC Lease #"))
                    else None,
                    new_record=str(row_data.get("New Record", ""))
                    if pd.notna(row_data.get("New Record"))
                    else None,
                    estimated_monthly_revenue=parse_currency(row_data.get("Estimated Monthly Revenue")),
                    estimated_net_bbl=float(row_data.get("Estimated Net BBL", 0))
                    if pd.notna(row_data.get("Estimated Net BBL"))
                    else None,
                    estimated_net_mcf=float(row_data.get("Estimated Net MCF", 0))
                    if pd.notna(row_data.get("Estimated Net MCF"))
                    else None,
                    district=district,
                    lease_number=lease_number,
                    block=block,
                    section=section,
                    abstract=abstract,
                    rrc_acres=rrc_acres,
                    well_type=well_type,
                    notes=notes,
                )

                # Calculate metrics (Est NRA, $/NRA)
                calculate_metrics(mineral_row)

                rows.append(mineral_row)

            except Exception as e:
                logger.exception(f"Error processing row {parsed['idx']}: {e}")
                failed_count += 1
                continue

        return ProcessingResult(
            success=True,
            total_rows=total_rows,
            filtered_rows=filtered_rows,
            processed_rows=len(rows),
            failed_rows=failed_count,
            matched_rows=matched_count,
            rows=rows,
            source_filename=filename,
        )

    except Exception as e:
        logger.exception(f"Error processing CSV: {e}")
        return ProcessingResult(
            success=False,
            error_message=f"Error processing CSV: {str(e)}",
            source_filename=filename,
        )


def apply_filters(df: pd.DataFrame, filters: FilterOptions) -> pd.DataFrame:
    """
    Apply filtering options to DataFrame.

    Args:
        df: Input DataFrame
        filters: Filter options

    Returns:
        Filtered DataFrame
    """
    df_filtered = df.copy()

    # Filter by New Record
    if filters.new_record_only:
        df_filtered = df_filtered[df_filtered.get("New Record", "") == "Y"]

    # Filter by minimum appraisal value
    if filters.min_appraisal_value > 0:
        df_filtered = df_filtered[
            pd.to_numeric(df_filtered.get("Appraisal Value", 0), errors="coerce")
            >= filters.min_appraisal_value
        ]

    # Filter by counties
    if filters.counties:
        df_filtered = df_filtered[df_filtered.get("County", "").isin(filters.counties)]

    # Filter by owners
    if filters.owners:
        df_filtered = df_filtered[df_filtered.get("Owner", "").isin(filters.owners)]

    # Deduplicate
    if filters.deduplicate:
        # Try Property ID first, then RRC Lease #
        if "Property ID" in df_filtered.columns:
            df_filtered = df_filtered.drop_duplicates(subset=["Property ID"], keep="first")
        elif "RRC Lease #" in df_filtered.columns:
            df_filtered = df_filtered.drop_duplicates(subset=["RRC Lease #"], keep="first")

    return df_filtered


def determine_well_type(
    row_data: pd.Series,
    override: WellType | None = None,
) -> WellType:
    """
    Determine well type from row data.

    Args:
        row_data: Row data from DataFrame
        override: Manual override for well type

    Returns:
        WellType enum value
    """
    if override:
        return override

    # Check Estimated Net BBL and MCF
    estimated_bbl = row_data.get("Estimated Net BBL", 0)
    estimated_mcf = row_data.get("Estimated Net MCF", 0)

    if pd.notna(estimated_bbl) and float(estimated_bbl) > 0:
        if pd.notna(estimated_mcf) and float(estimated_mcf) > 0:
            return WellType.BOTH
        return WellType.OIL

    if pd.notna(estimated_mcf) and float(estimated_mcf) > 0:
        return WellType.GAS

    return WellType.UNKNOWN


def extract_needed_counties(file_bytes: bytes) -> list[dict]:
    """Extract unique counties from an uploaded CSV for on-demand RRC download.

    Args:
        file_bytes: CSV file content

    Returns:
        List of dicts with county_name, county_code, district for counties
        found in both the CSV and the RRC county code mapping.
    """
    try:
        df = pd.read_csv(io.BytesIO(file_bytes))
    except Exception as e:
        logger.warning("Could not pre-parse CSV for county extraction: %s", e)
        return []

    if "County" not in df.columns:
        return []

    seen: set[str] = set()
    counties: list[dict] = []

    for raw in df["County"].dropna().unique():
        name = str(raw).strip().upper().replace(" COUNTY", "")
        if name in seen or not name:
            continue
        seen.add(name)

        result = lookup_county(name)
        if result:
            county_code, district, canonical = result
            counties.append({
                "county_name": canonical,
                "county_code": county_code,
                "district": district,
            })
        else:
            logger.debug("County '%s' not found in RRC mapping", name)

    logger.info("Extracted %d counties from CSV: %s", len(counties), [c["county_name"] for c in counties])
    return counties

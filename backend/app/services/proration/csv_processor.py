"""CSV processing service for mineral holder data."""

from __future__ import annotations

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
from app.services.proration.rrc_data_service import rrc_data_service

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger(__name__)

# Whether to use Firestore master database for RRC lookups
_use_firestore = True


async def _lookup_from_firestore(
    district: str, lease_number: str
) -> Optional[dict]:
    """Look up RRC data from Firestore master database."""
    try:
        from app.services.firestore_service import lookup_rrc_acres
        return await lookup_rrc_acres(district, lease_number)
    except Exception as e:
        logger.debug(f"Firestore lookup failed: {e}")
        return None


async def _lookup_by_lease_from_firestore(lease_number: str) -> Optional[dict]:
    """Look up RRC data by lease number only from Firestore."""
    try:
        from app.services.firestore_service import lookup_rrc_by_lease_number
        return await lookup_rrc_by_lease_number(lease_number)
    except Exception as e:
        logger.debug(f"Firestore lease lookup failed: {e}")
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

        # Convert to MineralHolderRow objects
        rows: list[MineralHolderRow] = []
        failed_count = 0
        matched_count = 0

        for idx, row_data in df_filtered.iterrows():
            try:
                # Parse RRC lease number using the new service
                rrc_lease_str = row_data.get("RRC Lease #") or row_data.get("Raw RRC", "")
                district, lease_number = rrc_data_service.parse_rrc_lease(rrc_lease_str)

                # Parse legal description
                block, section, abstract = parse_legal_description(
                    row_data.get("Legal Description", "")
                )

                # Determine well type from RRC lookup or estimates
                well_type = determine_well_type(row_data, options.well_type_override)

                # Look up acres from RRC master database (Firestore),
                # falling back to in-memory CSV if Firestore unavailable
                rrc_acres = None
                rrc_info = None
                notes = None

                if district and lease_number:
                    # Try Firestore master database first
                    if _use_firestore:
                        rrc_info = await _lookup_from_firestore(district, lease_number)

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
                elif lease_number or rrc_lease_str:
                    # No district parsed - try looking up by lease number only
                    lease_only = lease_number
                    if not lease_only and rrc_lease_str:
                        numbers = re.findall(r'\d+', str(rrc_lease_str))
                        if numbers:
                            lease_only = numbers[0]

                    if lease_only:
                        # Try Firestore first
                        if _use_firestore:
                            rrc_info = await _lookup_by_lease_from_firestore(lease_only)

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
                    else:
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
                logger.exception(f"Error processing row {idx}: {e}")
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

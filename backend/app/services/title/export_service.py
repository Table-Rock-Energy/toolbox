"""Export service for generating CSV and Excel files."""

from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Optional

import pandas as pd

from app.models.title import EXPORT_COLUMNS, FilterOptions, OwnerEntry


def apply_filters(
    entries: list[OwnerEntry], filters: Optional[FilterOptions]
) -> list[OwnerEntry]:
    """
    Apply filter options to entries.

    Args:
        entries: List of owner entries
        filters: Filter options

    Returns:
        Filtered list of entries
    """
    if not filters:
        return entries

    result = entries.copy()

    # Filter out entries without addresses
    if filters.hide_no_address:
        result = [e for e in result if e.has_address]

    # Hide duplicates (keep first occurrence)
    if filters.hide_duplicates:
        seen_names: set[str] = set()
        unique_entries = []
        for entry in result:
            norm_name = entry.full_name.upper().strip()
            if norm_name not in seen_names:
                seen_names.add(norm_name)
                unique_entries.append(entry)
        result = unique_entries

    # Filter by legal descriptions
    if filters.sections:
        sections_upper = {s.upper() for s in filters.sections}
        result = [e for e in result if e.legal_description.upper() in sections_upper]

    return result


def entries_to_dataframe(entries: list[OwnerEntry]) -> pd.DataFrame:
    """
    Convert owner entries to a pandas DataFrame.

    Args:
        entries: List of owner entries

    Returns:
        DataFrame with export columns
    """
    rows = []
    for entry in entries:
        rows.append({
            "Full Name": entry.full_name,
            "First Name": entry.first_name or "",
            "Last Name": entry.last_name or "",
            "Entity Type": entry.entity_type.value,
            "Address": entry.address or "",
            "City": entry.city or "",
            "State": entry.state or "",
            "Zip": entry.zip_code or "",
            "Legal Description": entry.legal_description,
            "Notes": entry.notes or "",
            "Duplicate Flag": "TRUE" if entry.duplicate_flag else "",
            "Has Address": "TRUE" if entry.has_address else "",
        })

    return pd.DataFrame(rows, columns=EXPORT_COLUMNS)


def to_csv(
    entries: list[OwnerEntry], filters: Optional[FilterOptions] = None
) -> bytes:
    """
    Export owner entries to CSV format.

    Args:
        entries: List of owner entries
        filters: Optional filter options

    Returns:
        CSV file contents as bytes (UTF-8 with BOM)
    """
    # Apply filters
    filtered_entries = apply_filters(entries, filters)

    # Create CSV content with UTF-8 BOM for Excel compatibility
    output = io.StringIO()

    # Write BOM for Excel
    output.write("\ufeff")

    writer = csv.DictWriter(output, fieldnames=EXPORT_COLUMNS)
    writer.writeheader()

    for entry in filtered_entries:
        writer.writerow({
            "Full Name": entry.full_name,
            "First Name": entry.first_name or "",
            "Last Name": entry.last_name or "",
            "Entity Type": entry.entity_type.value,
            "Address": entry.address or "",
            "City": entry.city or "",
            "State": entry.state or "",
            "Zip": entry.zip_code or "",
            "Legal Description": entry.legal_description,
            "Notes": entry.notes or "",
            "Duplicate Flag": "TRUE" if entry.duplicate_flag else "",
            "Has Address": "TRUE" if entry.has_address else "",
        })

    csv_content = output.getvalue()
    output.close()

    return csv_content.encode("utf-8")


def to_excel(
    entries: list[OwnerEntry], filters: Optional[FilterOptions] = None
) -> bytes:
    """
    Export owner entries to Excel format.

    Args:
        entries: List of owner entries
        filters: Optional filter options

    Returns:
        Excel file contents as bytes
    """
    # Apply filters
    filtered_entries = apply_filters(entries, filters)

    # Convert to DataFrame
    df = entries_to_dataframe(filtered_entries)

    # Write to Excel
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Owners")

        # Auto-adjust column widths
        worksheet = writer.sheets["Owners"]
        for i, col in enumerate(EXPORT_COLUMNS):
            # Set width based on column header length + padding
            width = max(len(col), 12) + 2
            worksheet.column_dimensions[chr(65 + i)].width = width

    output.seek(0)
    return output.getvalue()


def generate_filename(base_name: str, extension: str) -> str:
    """
    Generate export filename with timestamp.

    Args:
        base_name: Base filename
        extension: File extension (csv or xlsx)

    Returns:
        Filename with timestamp
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{base_name}_{timestamp}.{extension}"

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


# CRM contact import column names for mineral format
MINERAL_EXPORT_COLUMNS = [
    "Contact Id",
    "Full Name",
    "First Name",
    "Last Name",
    "Middle Name",
    "County",
    "Suffix",
    "Age",
    "Relative Names",
    "Primary Address 1",
    "Primary Address 2",
    "Primary Address City",
    "Primary Address State",
    "Primary Address Zip",
    "Primary Address Country",
    "Secondary Address 1",
    "Secondary Address 2",
    "Secondary Address City",
    "Secondary Address State",
    "Secondary Address Zip",
    "Secondary Address Country",
    "Owner Type",
    "Global Owner",
    "Primary Email",
    "Email 2",
    "Email 3",
    "Primary Home Phone",
    "Home Phone 2",
    "Home Phone 3",
    "Primary Mobile Phone",
    "Mobile Phone 2",
    "Mobile Phone 3",
    "Primary Work Phone",
    "Work Phone 2",
    "Work Phone 3",
    "Company Name",
    "Job Title",
    "Industry Type",
    "LinkedIn Profile",
    "Facebook Profile",
    "Twitter Profile",
    "Lead Source",
    "Stage",
    "Territory",
    "Campaign Name",
    "Status",
    "Website",
    "Contact Owner",
    "Notes/Comments",
    "Tags",
    "Mineral Holders Link",
    "Mineral Holders Property Count (2025)",
    "Mineral Holders Property Count (2024)",
    "Link to Summary",
    "Link to OneDrive Folder",
]


def entries_to_mineral_dataframe(entries: list[OwnerEntry]) -> pd.DataFrame:
    """
    Convert owner entries to a pandas DataFrame in CRM mineral format.

    Args:
        entries: List of owner entries

    Returns:
        DataFrame with CRM contact import column format
    """
    rows = []
    for entry in entries:
        row = {col: "" for col in MINERAL_EXPORT_COLUMNS}

        # Map our extracted data to CRM fields
        row["Full Name"] = entry.full_name
        row["First Name"] = entry.first_name or ""
        row["Last Name"] = entry.last_name or ""
        row["Primary Address 1"] = entry.address or ""
        row["Primary Address City"] = entry.city or ""
        row["Primary Address State"] = entry.state or ""
        row["Primary Address Zip"] = entry.zip_code or ""
        row["Owner Type"] = entry.entity_type.value
        row["Notes/Comments"] = entry.notes or ""
        row["Territory"] = entry.legal_description

        # Set company name for non-individual entities
        if entry.entity_type.value != "INDIVIDUAL":
            row["Company Name"] = entry.full_name

        rows.append(row)

    return pd.DataFrame(rows, columns=MINERAL_EXPORT_COLUMNS)


def to_mineral_excel(
    entries: list[OwnerEntry], filters: Optional[FilterOptions] = None
) -> bytes:
    """
    Export owner entries to Excel format in CRM mineral format.

    Args:
        entries: List of owner entries
        filters: Optional filter options

    Returns:
        Excel file contents as bytes
    """
    # Apply filters
    filtered_entries = apply_filters(entries, filters)

    # Convert to DataFrame
    df = entries_to_mineral_dataframe(filtered_entries)

    # Write to Excel
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Contacts")

        # Auto-adjust column widths
        worksheet = writer.sheets["Contacts"]
        for i, col in enumerate(df.columns):
            # Get column letter (handles AA, AB, etc.)
            col_letter = _get_column_letter(i + 1)
            max_length = max(
                df[col].astype(str).map(len).max() if len(df) > 0 else 0,
                len(col),
            )
            # Limit max width and add padding
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[col_letter].width = adjusted_width

    output.seek(0)
    return output.getvalue()


def _get_column_letter(col_idx: int) -> str:
    """
    Convert a column index (1-based) to Excel column letter.

    Args:
        col_idx: Column index (1-based)

    Returns:
        Excel column letter (A, B, ..., Z, AA, AB, ...)
    """
    result = ""
    while col_idx > 0:
        col_idx, remainder = divmod(col_idx - 1, 26)
        result = chr(65 + remainder) + result
    return result

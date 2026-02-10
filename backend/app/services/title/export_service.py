"""Export service for generating CSV and Excel files from title entries."""

from __future__ import annotations

import csv
import io
from typing import Optional

import pandas as pd

from app.models.title import EXPORT_COLUMNS, FilterOptions, OwnerEntry
from app.services.shared.export_utils import (
    dataframe_to_excel_bytes,
    generate_export_filename,
)

# Re-export for callers that import generate_filename from here
generate_filename = generate_export_filename


def apply_filters(
    entries: list[OwnerEntry], filters: Optional[FilterOptions]
) -> list[OwnerEntry]:
    """Apply filter options to entries."""
    if not filters:
        return entries

    result = entries.copy()

    if filters.hide_no_address:
        result = [e for e in result if e.has_address]

    if filters.hide_duplicates:
        seen_names: set[str] = set()
        unique_entries = []
        for entry in result:
            norm_name = entry.full_name.upper().strip()
            if norm_name not in seen_names:
                seen_names.add(norm_name)
                unique_entries.append(entry)
        result = unique_entries

    if filters.sections:
        sections_upper = {s.upper() for s in filters.sections}
        result = [e for e in result if e.legal_description.upper() in sections_upper]

    return result


def entries_to_dataframe(entries: list[OwnerEntry]) -> pd.DataFrame:
    """Convert owner entries to a pandas DataFrame."""
    rows = []
    for entry in entries:
        rows.append({
            "Full Name": entry.full_name,
            "First Name": entry.first_name or "",
            "Middle Name": entry.middle_name or "",
            "Last Name": entry.last_name or "",
            "Entity Type": entry.entity_type.value,
            "Address": entry.address or "",
            "Address Line 2": entry.address_line_2 or "",
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
    """Export owner entries to CSV format."""
    filtered_entries = apply_filters(entries, filters)

    output = io.StringIO()
    output.write("\ufeff")

    writer = csv.DictWriter(output, fieldnames=EXPORT_COLUMNS)
    writer.writeheader()

    for entry in filtered_entries:
        writer.writerow({
            "Full Name": entry.full_name,
            "First Name": entry.first_name or "",
            "Middle Name": entry.middle_name or "",
            "Last Name": entry.last_name or "",
            "Entity Type": entry.entity_type.value,
            "Address": entry.address or "",
            "Address Line 2": entry.address_line_2 or "",
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
    """Export owner entries to Excel format."""
    filtered_entries = apply_filters(entries, filters)
    df = entries_to_dataframe(filtered_entries)
    return dataframe_to_excel_bytes(df, sheet_name="Owners")


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
    """Convert owner entries to a pandas DataFrame in CRM mineral format."""
    rows = []
    for entry in entries:
        row = {col: "" for col in MINERAL_EXPORT_COLUMNS}

        row["Full Name"] = entry.full_name
        row["First Name"] = entry.first_name or ""
        row["Middle Name"] = entry.middle_name or ""
        row["Last Name"] = entry.last_name or ""
        row["Primary Address 1"] = entry.address or ""
        row["Primary Address 2"] = entry.address_line_2 or ""
        row["Primary Address City"] = entry.city or ""
        row["Primary Address State"] = entry.state or ""
        row["Primary Address Zip"] = entry.zip_code or ""
        row["Owner Type"] = entry.entity_type.value
        row["Notes/Comments"] = entry.notes or ""
        row["Territory"] = entry.legal_description

        if entry.entity_type.value != "INDIVIDUAL":
            row["Company Name"] = entry.full_name

        rows.append(row)

    return pd.DataFrame(rows, columns=MINERAL_EXPORT_COLUMNS)


def to_mineral_csv(
    entries: list[OwnerEntry], filters: Optional[FilterOptions] = None
) -> bytes:
    """Export owner entries to CSV format in CRM mineral format."""
    filtered_entries = apply_filters(entries, filters)
    df = entries_to_mineral_dataframe(filtered_entries)
    return dataframe_to_csv_bytes(df)


def to_mineral_excel(
    entries: list[OwnerEntry], filters: Optional[FilterOptions] = None
) -> bytes:
    """Export owner entries to Excel format in CRM mineral format."""
    filtered_entries = apply_filters(entries, filters)
    df = entries_to_mineral_dataframe(filtered_entries)
    return dataframe_to_excel_bytes(df, sheet_name="Contacts")

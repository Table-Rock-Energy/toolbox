"""Export service for generating CSV and Excel files from extracted entries."""

from __future__ import annotations

import io
from typing import Any

import pandas as pd

from app.models.extract import PartyEntry
from app.services.extract.name_parser import (
    parse_name,
    is_business_name,
    split_multiple_names,
    clean_name_for_export,
)


def to_csv(entries: list[PartyEntry]) -> bytes:
    """
    Convert party entries to CSV format.

    Args:
        entries: List of PartyEntry objects

    Returns:
        CSV file as bytes
    """
    df = _entries_to_dataframe(entries)

    # Write to bytes buffer
    buffer = io.BytesIO()
    df.to_csv(buffer, index=False, encoding="utf-8-sig")  # UTF-8 with BOM for Excel
    buffer.seek(0)

    return buffer.getvalue()


def to_excel(entries: list[PartyEntry]) -> bytes:
    """
    Convert party entries to Excel format.

    Args:
        entries: List of PartyEntry objects

    Returns:
        Excel file as bytes
    """
    df = _entries_to_dataframe(entries)

    # Write to bytes buffer
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Contacts")

        # Auto-adjust column widths
        worksheet = writer.sheets["Contacts"]
        for idx, col in enumerate(df.columns):
            max_length = max(
                df[col].astype(str).map(len).max(),
                len(col),
            )
            # Limit max width and add padding
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[
                _get_column_letter(idx + 1)
            ].width = adjusted_width

    buffer.seek(0)
    return buffer.getvalue()


def _entries_to_dataframe(entries: list[PartyEntry]) -> pd.DataFrame:
    """
    Convert party entries to a pandas DataFrame in CRM contact format.

    Args:
        entries: List of PartyEntry objects

    Returns:
        DataFrame with CRM contact import column format
    """
    # CRM contact import column names
    columns = [
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

    # Convert entries to dictionaries matching CRM format
    data: list[dict[str, Any]] = []
    for entry in entries:
        # Clean the name (remove notes/annotations)
        cleaned_name = clean_name_for_export(entry.primary_name)

        # Check if this is actually a business name even if marked as Individual
        entity_type = entry.entity_type.value
        if entity_type == "Individual" and is_business_name(cleaned_name):
            entity_type = "Business"

        # Split multiple names if present (e.g., "John & Jane Smith")
        names_to_export = split_multiple_names(cleaned_name)

        for name in names_to_export:
            row: dict[str, Any] = {col: "" for col in columns}

            # Map our extracted data to CRM fields
            row["Full Name"] = name
            row["Primary Address 1"] = entry.mailing_address or ""
            row["Primary Address City"] = entry.city or ""
            row["Primary Address State"] = entry.state or ""
            row["Primary Address Zip"] = entry.zip_code or ""
            row["Owner Type"] = entity_type
            row["Notes/Comments"] = entry.notes or ""

            # Parse name into first/middle/last for Individuals only
            # Re-check if this specific name is a person (after splitting)
            if entity_type == "Individual" and not is_business_name(name):
                parsed = parse_name(name, "Individual")
                if parsed.is_person:
                    row["First Name"] = parsed.first_name
                    row["Middle Name"] = parsed.middle_name
                    row["Last Name"] = parsed.last_name
                    row["Suffix"] = parsed.suffix

            data.append(row)

    df = pd.DataFrame(data, columns=columns)
    return df


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

"""Export service for generating CSV and Excel files from extracted entries."""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.models.extract import PartyEntry
from app.services.extract.name_parser import (
    clean_name_for_export,
    is_business_name,
    parse_name,
    split_multiple_names,
)
from app.services.shared.export_utils import (
    MINERAL_EXPORT_COLUMNS,
    dataframe_to_csv_bytes,
    dataframe_to_excel_bytes,
)

# Alias for backward compatibility
COLUMNS = MINERAL_EXPORT_COLUMNS


def to_csv(
    entries: list[PartyEntry],
    *,
    county: str = "",
    campaign_name: str = "",
) -> bytes:
    """Convert party entries to CSV format."""
    df = _entries_to_dataframe(entries, county=county, campaign_name=campaign_name)
    return dataframe_to_csv_bytes(df)


def to_excel(
    entries: list[PartyEntry],
    *,
    county: str = "",
    campaign_name: str = "",
) -> bytes:
    """Convert party entries to Excel format."""
    df = _entries_to_dataframe(entries, county=county, campaign_name=campaign_name)
    return dataframe_to_excel_bytes(df, sheet_name="Contacts")


def _entries_to_dataframe(
    entries: list[PartyEntry],
    *,
    county: str = "",
    campaign_name: str = "",
) -> pd.DataFrame:
    """Convert party entries to a pandas DataFrame in CRM contact format."""
    data: list[dict[str, Any]] = []
    for entry in entries:
        cleaned_name = clean_name_for_export(entry.primary_name)

        entity_type = entry.entity_type.value
        if entity_type == "Individual" and is_business_name(cleaned_name):
            entity_type = "Business"

        names_to_export = split_multiple_names(cleaned_name)

        for name in names_to_export:
            row: dict[str, Any] = {col: "" for col in COLUMNS}

            row["Full Name"] = name
            row["Primary Address 1"] = entry.mailing_address or ""
            row["Primary Address 2"] = entry.mailing_address_2 or ""
            row["Primary Address City"] = entry.city or ""
            row["Primary Address State"] = entry.state or ""
            row["Primary Address Zip"] = entry.zip_code or ""
            row["Owner Type"] = entity_type
            row["Notes/Comments"] = entry.notes or ""
            row["County"] = county
            row["Campaign Name"] = campaign_name

            if entity_type == "Individual" and not is_business_name(name):
                parsed = parse_name(name, "Individual")
                if parsed.is_person:
                    row["First Name"] = parsed.first_name
                    row["Middle Name"] = parsed.middle_name
                    row["Last Name"] = parsed.last_name
                    row["Suffix"] = parsed.suffix

            data.append(row)

    return pd.DataFrame(data, columns=COLUMNS)

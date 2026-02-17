"""Excel processing service for reading and parsing multi-sheet Excel files."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from io import BytesIO
from typing import Optional

import pandas as pd

from app.models.title import EntityType, OwnerEntry
from app.services.title.ownership_report_parser import (
    is_ownership_report,
    process_ownership_report,
)
from app.services.title.address_parser import (
    extract_address_annotations,
    parse_address_with_notes,
    split_address_lines,
)
from app.services.title.entity_detector import detect_entity_type
from app.services.title.name_parser import clean_name, parse_name, is_valid_name
from app.services.title.text_parser import parse_text_entry, split_cell_entries


def _merge_notes(*note_sources: str | list | None) -> str | None:
    """Merge multiple note sources into a single notes string."""
    all_notes = []
    for source in note_sources:
        if source is None:
            continue
        if isinstance(source, list):
            all_notes.extend([n for n in source if n])
        elif isinstance(source, str) and source.strip():
            all_notes.append(source.strip())
    return "; ".join(all_notes) if all_notes else None


def _is_unknown_address(value: str | None) -> bool:
    """Check if address value is unknown/placeholder."""
    if not value:
        return True
    return value.strip().lower() in ("address unknown", "unknown", "n/a", "none", "")


logger = logging.getLogger(__name__)


@dataclass
class ExcelProcessingResult:
    """Result of processing an Excel file."""

    entries: list[OwnerEntry]
    county: Optional[str] = None


def process_excel(file_bytes: bytes, filename: str) -> ExcelProcessingResult:
    """
    Process an Excel file with multiple sheets.

    Each sheet represents a legal description (e.g., "2-6N-4W").
    Handles various formats:
    - Single-column with newline-delimited data
    - Multi-column (Name | Address | City State Zip)
    - With or without headers

    Args:
        file_bytes: Excel file contents as bytes
        filename: Original filename for logging

    Returns:
        ExcelProcessingResult with entries and optional county
    """
    entries: list[OwnerEntry] = []

    try:
        # Read Excel file
        excel_file = pd.ExcelFile(BytesIO(file_bytes))

        # Check for ownership report format first
        if is_ownership_report(excel_file):
            logger.info("Detected ownership report format for %s", filename)
            or_entries, county = process_ownership_report(file_bytes, filename)
            return ExcelProcessingResult(entries=or_entries, county=county)
        sheet_names = excel_file.sheet_names

        logger.info(f"Processing {len(sheet_names)} sheets from {filename}")

        for sheet_name in sheet_names:
            # Extract legal description from sheet name
            legal_description = _extract_legal_description(sheet_name)

            # Read sheet
            df = pd.read_excel(excel_file, sheet_name=sheet_name, header=None)

            if df.empty:
                logger.warning(f"Sheet '{sheet_name}' is empty, skipping")
                continue

            # Detect sheet format and process accordingly
            sheet_entries = _process_sheet(df, legal_description, sheet_name)
            entries.extend(sheet_entries)

            logger.info(
                f"Extracted {len(sheet_entries)} entries from sheet '{sheet_name}'"
            )

    except Exception as e:
        logger.exception(f"Error processing Excel file: {e}")
        raise

    # Flag duplicates
    entries = _flag_duplicates(entries)

    return ExcelProcessingResult(entries=entries)


def _extract_legal_description(sheet_name: str) -> str:
    """
    Extract legal description from sheet name.

    Expected formats:
    - "2-6N-4W" -> "2-6N-4W"
    - "Section 2-6N-4W" -> "2-6N-4W"
    - "Sheet1" -> "Sheet1" (use as-is if no pattern)

    Args:
        sheet_name: Raw sheet name

    Returns:
        Cleaned legal description string
    """
    # Pattern for Section-Township-Range (e.g., "2-6N-4W")
    pattern = re.compile(r"(\d+)-?(\d+[NS])-?(\d+[EW])", re.IGNORECASE)
    match = pattern.search(sheet_name)

    if match:
        section = match.group(1)
        township = match.group(2).upper()
        range_val = match.group(3).upper()
        return f"{section}-{township}-{range_val}"

    # Return original name if no pattern found
    return sheet_name.strip()


def _process_sheet(
    df: pd.DataFrame, legal_description: str, sheet_name: str
) -> list[OwnerEntry]:
    """
    Process a single sheet and extract owner entries.

    Detects format (single-column vs multi-column) and processes accordingly.

    Args:
        df: Pandas DataFrame from sheet
        legal_description: Legal description for all entries
        sheet_name: Sheet name for logging

    Returns:
        List of OwnerEntry objects
    """
    entries: list[OwnerEntry] = []

    # Detect format based on column count and data patterns
    num_cols = len(df.columns)
    has_headers = _detect_headers(df)

    if has_headers:
        # Re-read with first row as header
        df.columns = df.iloc[0]
        df = df.iloc[1:].reset_index(drop=True)

    if num_cols == 1:
        # Single column format - entries may be newline-delimited
        entries = _process_single_column(df, legal_description)
    elif num_cols >= 3:
        # Multi-column format - try to map columns
        entries = _process_multi_column(df, legal_description)
    else:
        # Two columns - could be name|address
        entries = _process_two_column(df, legal_description)

    return entries


def _detect_headers(df: pd.DataFrame) -> bool:
    """
    Detect if the first row contains headers.

    Args:
        df: DataFrame to analyze

    Returns:
        True if first row appears to be headers
    """
    if df.empty:
        return False

    first_row = df.iloc[0]

    # Common header keywords
    header_keywords = [
        "name", "owner", "address", "city", "state", "zip",
        "contact", "mailing", "street", "full name",
        "entity type", "county", "legal description", "campaign", "notes",
    ]

    # Check if any cell in first row contains header keywords
    for cell in first_row:
        if pd.isna(cell):
            continue
        cell_str = str(cell).lower().strip()
        for keyword in header_keywords:
            if keyword in cell_str:
                return True

    return False


def _process_single_column(
    df: pd.DataFrame, legal_description: str
) -> list[OwnerEntry]:
    """
    Process single-column format where data is newline-delimited.

    Args:
        df: Single-column DataFrame
        legal_description: Legal description for entries

    Returns:
        List of OwnerEntry objects
    """
    entries: list[OwnerEntry] = []

    for _, row in df.iterrows():
        cell_value = row.iloc[0]
        if pd.isna(cell_value):
            continue

        cell_text = str(cell_value).strip()
        if not cell_text:
            continue

        # Split cell into individual entries if needed
        raw_entries = split_cell_entries(cell_text)

        for raw_entry in raw_entries:
            entry = _create_entry_from_text(raw_entry, legal_description)
            if entry:
                entries.append(entry)

    return entries


def _process_multi_column(
    df: pd.DataFrame, legal_description: str
) -> list[OwnerEntry]:
    """
    Process multi-column format (Name | Address | City | State | Zip).

    Args:
        df: Multi-column DataFrame
        legal_description: Legal description for entries

    Returns:
        List of OwnerEntry objects
    """
    entries: list[OwnerEntry] = []

    # Try to identify columns
    col_mapping = _identify_columns(df)

    # Check if the "name" column is actually a dedicated full name column
    # vs a first_name/last_name column being used as fallback
    has_full_name_col = "name" in col_mapping and col_mapping["name"] not in (
        col_mapping.get("first_name"), col_mapping.get("last_name")
    )
    has_separate_name_cols = "first_name" in col_mapping or "last_name" in col_mapping

    for _, row in df.iterrows():
        name_col = col_mapping.get("name", 0)
        raw_name = row.iloc[name_col] if name_col < len(row) else None

        # If no dedicated full name column, reconstruct from first/last parts
        if not has_full_name_col and has_separate_name_cols:
            raw_first = _get_cell_value(row, col_mapping.get("first_name"))
            raw_last = _get_cell_value(row, col_mapping.get("last_name"))
            parts = [p for p in [raw_first, raw_last] if p]
            if parts:
                raw_name = " ".join(parts)

        if pd.isna(raw_name) if not isinstance(raw_name, str) else not raw_name or not str(raw_name).strip():
            continue

        # Extract annotations from name
        cleaned_name, name_notes = extract_address_annotations(str(raw_name).strip())
        full_name = clean_name(cleaned_name)

        # Skip if not a valid name (e.g., legal descriptions, junk data)
        if not is_valid_name(full_name):
            continue

        # Get address components and extract annotations
        raw_address = _get_cell_value(row, col_mapping.get("address"))
        address_notes: list[str] = []
        address = None
        address_line_2 = None

        # Treat "Address Unknown" as no address
        if _is_unknown_address(raw_address):
            raw_address = None

        if raw_address:
            cleaned_addr, addr_notes = extract_address_annotations(raw_address)
            address = cleaned_addr
            address_notes.extend(addr_notes)

        city = _get_cell_value(row, col_mapping.get("city"))
        state = _get_cell_value(row, col_mapping.get("state"))
        zip_code = _get_cell_value(row, col_mapping.get("zip"))

        # Treat unknown city as no city
        if _is_unknown_address(city):
            city = None

        # If we have a combined city/state/zip column, parse it
        if city and not state and not zip_code:
            parsed = parse_address_with_notes(city)
            if parsed.state:
                city = parsed.city
                state = parsed.state
                zip_code = parsed.zip_code
                address_notes.extend(parsed.notes)

        # Split address into line 1 and line 2
        if address:
            address, address_line_2 = split_address_lines(address)

        # Read entity type from file if present, otherwise auto-detect
        file_entity_type_str = _get_cell_value(row, col_mapping.get("entity_type"))
        if file_entity_type_str:
            parsed_et = _parse_entity_type_value(file_entity_type_str)
            entity_type = parsed_et if parsed_et else detect_entity_type(full_name)
        else:
            entity_type = detect_entity_type(full_name)

        # Parse name for individuals
        first_name, middle_name, last_name = parse_name(full_name, entity_type)

        # Read legal description from column if present, prefer over sheet name
        file_legal = _get_cell_value(row, col_mapping.get("legal_description"))
        effective_legal = file_legal or legal_description

        # Read notes from column and merge with extracted annotations
        file_notes = _get_cell_value(row, col_mapping.get("notes"))

        # Read county and campaign_name from columns
        file_county = _get_cell_value(row, col_mapping.get("county"))
        file_campaign = _get_cell_value(row, col_mapping.get("campaign_name"))

        # Determine if has address
        has_address = bool(address or city or state or zip_code)

        # Merge notes
        all_notes = _merge_notes(file_notes, name_notes, address_notes)

        entry = OwnerEntry(
            full_name=full_name,
            first_name=first_name,
            middle_name=middle_name,
            last_name=last_name,
            entity_type=entity_type,
            address=address,
            address_line_2=address_line_2,
            city=city,
            state=state.upper() if state else None,
            zip_code=zip_code,
            legal_description=effective_legal,
            notes=all_notes,
            campaign_name=file_campaign,
            county=file_county,
            duplicate_flag=False,
            has_address=has_address,
        )
        entries.append(entry)

    return entries


def _process_two_column(
    df: pd.DataFrame, legal_description: str
) -> list[OwnerEntry]:
    """
    Process two-column format (Name | Full Address or Name | Notes).

    Args:
        df: Two-column DataFrame
        legal_description: Legal description for entries

    Returns:
        List of OwnerEntry objects
    """
    entries: list[OwnerEntry] = []

    for _, row in df.iterrows():
        raw_name = row.iloc[0]
        raw_second = row.iloc[1] if len(row) > 1 else None

        if pd.isna(raw_name) or not str(raw_name).strip():
            continue

        # Extract annotations from name
        cleaned_name, name_notes = extract_address_annotations(str(raw_name).strip())
        full_name = clean_name(cleaned_name)

        # Skip if not a valid name (e.g., legal descriptions, junk data)
        if not is_valid_name(full_name):
            continue

        # Detect entity type
        entity_type = detect_entity_type(full_name)

        # Parse name for individuals
        first_name, middle_name, last_name = parse_name(full_name, entity_type)

        # Try to parse second column as address
        address = None
        address_line_2 = None
        city = None
        state = None
        zip_code = None
        address_notes: list[str] = []
        other_notes = None

        if raw_second and not pd.isna(raw_second):
            second_text = str(raw_second).strip()
            # Treat "Address Unknown" as no address
            if _is_unknown_address(second_text):
                second_text = None
            elif re.search(r"\d", second_text):
                # Check if it looks like an address (has numbers or ZIP)
                parsed = parse_address_with_notes(second_text)
                address = parsed.street
                city = parsed.city
                state = parsed.state
                zip_code = parsed.zip_code
                address_notes = parsed.notes
            else:
                # Treat as notes
                other_notes = second_text

        # Split address into line 1 and line 2
        if address:
            address, address_line_2 = split_address_lines(address)

        has_address = bool(address or city or state or zip_code)

        # Merge notes
        all_notes = _merge_notes(name_notes, address_notes, other_notes)

        entry = OwnerEntry(
            full_name=full_name,
            first_name=first_name,
            middle_name=middle_name,
            last_name=last_name,
            entity_type=entity_type,
            address=address,
            address_line_2=address_line_2,
            city=city,
            state=state,
            zip_code=zip_code,
            legal_description=legal_description,
            notes=all_notes,
            duplicate_flag=False,
            has_address=has_address,
        )
        entries.append(entry)

    return entries


def _is_campaign_name_column(name: str) -> bool:
    """Check if a column name is a campaign name column (handles misspellings)."""
    normalized = name.replace("_", " ").replace("-", " ").lower().strip()
    known = {"campaign name", "campain name", "campaignname", "campainname", "campaign"}
    if normalized in known:
        return True
    return normalized.startswith("camp") and "name" in normalized


def _parse_entity_type_value(value: str) -> EntityType | None:
    """Try to parse an entity type string into an EntityType enum value."""
    normalized = value.strip().upper()
    for et in EntityType:
        if et.value == normalized:
            return et
    return None


def _identify_columns(df: pd.DataFrame) -> dict[str, int]:
    """
    Identify column meanings based on header names or data patterns.

    Args:
        df: DataFrame to analyze

    Returns:
        Dictionary mapping column type to column index
    """
    mapping: dict[str, int] = {}

    # If columns have names, use them
    col_names = [str(c).lower().strip() for c in df.columns]

    # Track whether any header was detected by name (not just positional)
    has_named_headers = False

    for i, name in enumerate(col_names):
        if name in ("full name", "full_name"):
            mapping["name"] = i
            has_named_headers = True
        elif name in ("first name", "first_name"):
            mapping["first_name"] = i
            has_named_headers = True
        elif name in ("last name", "last_name"):
            mapping["last_name"] = i
            has_named_headers = True
        elif _is_campaign_name_column(name):
            mapping["campaign_name"] = i
            has_named_headers = True
        elif "name" in name or "owner" in name:
            # Generic name/owner column - only set if no specific match yet
            if "name" not in mapping:
                mapping["name"] = i
                has_named_headers = True
        elif "address" in name or "street" in name or "mailing" in name:
            mapping["address"] = i
            has_named_headers = True
        elif "city" in name:
            mapping["city"] = i
            has_named_headers = True
        elif "state" in name:
            mapping["state"] = i
            has_named_headers = True
        elif "zip" in name or "postal" in name:
            mapping["zip"] = i
            has_named_headers = True
        elif name in ("entity type", "entity_type", "type"):
            mapping["entity_type"] = i
            has_named_headers = True
        elif name == "county":
            mapping["county"] = i
            has_named_headers = True
        elif name in ("legal description", "legal_description", "legal", "section"):
            mapping["legal_description"] = i
            has_named_headers = True
        elif name in ("notes", "comments", "remarks"):
            mapping["notes"] = i
            has_named_headers = True

    # If no "full name" column but we have first+last, use first_name as the
    # name column (full_name will be reconstructed in _process_multi_column)
    if "name" not in mapping:
        if "first_name" in mapping:
            mapping["name"] = mapping["first_name"]
        elif "last_name" in mapping:
            mapping["name"] = mapping["last_name"]

    # Default positional mappings only when no headers were detected by name
    if not has_named_headers:
        if "name" not in mapping:
            mapping["name"] = 0
        if "address" not in mapping and len(df.columns) > 1:
            mapping["address"] = 1
        if "city" not in mapping and len(df.columns) > 2:
            mapping["city"] = 2
        if "state" not in mapping and len(df.columns) > 3:
            mapping["state"] = 3
        if "zip" not in mapping and len(df.columns) > 4:
            mapping["zip"] = 4
    else:
        # Even with named headers, ensure we have a name column
        if "name" not in mapping:
            mapping["name"] = 0

    return mapping


def _get_cell_value(row: pd.Series, col_idx: Optional[int]) -> Optional[str]:
    """Get cell value as string or None."""
    if col_idx is None or col_idx >= len(row):
        return None
    value = row.iloc[col_idx]
    if pd.isna(value):
        return None
    return str(value).strip() or None


def _create_entry_from_text(raw_text: str, legal_description: str) -> Optional[OwnerEntry]:
    """
    Create an OwnerEntry from raw text.

    Args:
        raw_text: Raw text entry (may be multi-line)
        legal_description: Legal description for the entry

    Returns:
        OwnerEntry or None if invalid
    """
    parsed = parse_text_entry(raw_text)

    if not parsed.name:
        return None

    # Extract annotations from the name too (c/o, trust dates, etc.)
    cleaned_name, name_notes = extract_address_annotations(parsed.name)
    full_name = clean_name(cleaned_name)
    if not full_name:
        return None

    # Validate that it's actually a name, not a legal description or junk
    if not is_valid_name(full_name):
        return None

    # Detect entity type
    entity_type = detect_entity_type(full_name)

    # Parse name for individuals
    first_name, middle_name, last_name = parse_name(full_name, entity_type)

    # Parse address with annotation extraction
    address = None
    address_line_2 = None
    city = None
    state = None
    zip_code = None
    address_notes: list[str] = []

    if parsed.address_text:
        # Treat "Address Unknown" as no address
        if _is_unknown_address(parsed.address_text):
            pass
        else:
            addr = parse_address_with_notes(parsed.address_text)
            address = addr.street
            city = addr.city
            state = addr.state
            zip_code = addr.zip_code
            address_notes = addr.notes

    # Split address into line 1 and line 2
    if address:
        address, address_line_2 = split_address_lines(address)

    has_address = bool(address or city or state or zip_code)

    # Merge all notes: from text parser, from name, from address
    all_notes = _merge_notes(parsed.notes, name_notes, address_notes)

    return OwnerEntry(
        full_name=full_name,
        first_name=first_name,
        middle_name=middle_name,
        last_name=last_name,
        entity_type=entity_type,
        address=address,
        address_line_2=address_line_2,
        city=city,
        state=state,
        zip_code=zip_code,
        legal_description=legal_description,
        notes=all_notes,
        duplicate_flag=False,
        has_address=has_address,
    )


def _flag_duplicates(entries: list[OwnerEntry]) -> list[OwnerEntry]:
    """
    Flag duplicate entries based on name matching.

    An entry is flagged as duplicate if the same name appears multiple times
    with different address information.

    Args:
        entries: List of entries to check

    Returns:
        List with duplicate_flag set appropriately
    """
    # Group by normalized name
    name_groups: dict[str, list[int]] = {}

    for i, entry in enumerate(entries):
        # Normalize name for comparison
        norm_name = entry.full_name.upper().strip()
        if norm_name not in name_groups:
            name_groups[norm_name] = []
        name_groups[norm_name].append(i)

    # Flag duplicates
    for indices in name_groups.values():
        if len(indices) > 1:
            # Mark all as duplicates
            for idx in indices:
                entries[idx].duplicate_flag = True

    return entries

"""CSV processing service for reading and parsing CSV files."""

from __future__ import annotations

import logging
import re
from io import StringIO
from typing import Optional

import pandas as pd

from app.models.title import EntityType, OwnerEntry
from app.services.title.address_parser import (
    extract_address_annotations,
    parse_address_with_notes,
)
from app.services.title.entity_detector import detect_entity_type
from app.services.title.name_parser import clean_name, parse_name


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


logger = logging.getLogger(__name__)


def process_csv(file_bytes: bytes, filename: str) -> list[OwnerEntry]:
    """
    Process a CSV file containing owner information.

    Args:
        file_bytes: CSV file contents as bytes
        filename: Original filename for logging

    Returns:
        List of OwnerEntry objects
    """
    entries: list[OwnerEntry] = []

    try:
        # Decode bytes to string, handling BOM
        content = file_bytes.decode("utf-8-sig")

        # Try to detect delimiter
        sample = content[:2000]
        delimiter = _detect_delimiter(sample)

        # Read CSV
        df = pd.read_csv(
            StringIO(content),
            delimiter=delimiter,
            dtype=str,
            keep_default_na=False,
        )

        if df.empty:
            logger.warning(f"CSV file '{filename}' is empty")
            return entries

        logger.info(f"Processing CSV with {len(df)} rows and {len(df.columns)} columns")

        # Identify column mapping
        col_mapping = _identify_columns(df)

        # Extract legal description from filename if not in data
        default_legal_description = _extract_legal_from_filename(filename)

        for _, row in df.iterrows():
            entry = _process_row(row, col_mapping, default_legal_description)
            if entry:
                entries.append(entry)

        # Flag duplicates
        entries = _flag_duplicates(entries)

        logger.info(f"Extracted {len(entries)} entries from {filename}")

    except Exception as e:
        logger.exception(f"Error processing CSV file: {e}")
        raise

    return entries


def _detect_delimiter(sample: str) -> str:
    """Detect CSV delimiter from sample content."""
    # Count occurrences of common delimiters
    delimiters = [",", "\t", ";", "|"]
    counts = {d: sample.count(d) for d in delimiters}

    # Return delimiter with highest count (default to comma)
    max_delim = max(counts, key=counts.get)
    return max_delim if counts[max_delim] > 0 else ","


def _identify_columns(df: pd.DataFrame) -> dict[str, Optional[int]]:
    """
    Identify column meanings based on header names.

    Args:
        df: DataFrame to analyze

    Returns:
        Dictionary mapping column type to column index
    """
    mapping: dict[str, Optional[int]] = {
        "name": None,
        "first_name": None,
        "last_name": None,
        "address": None,
        "city": None,
        "state": None,
        "zip": None,
        "legal_description": None,
        "notes": None,
    }

    col_names = [str(c).lower().strip() for c in df.columns]

    for i, name in enumerate(col_names):
        if name in ["full name", "full_name", "name", "owner", "owner name"]:
            mapping["name"] = i
        elif name in ["first name", "first_name", "first"]:
            mapping["first_name"] = i
        elif name in ["last name", "last_name", "last"]:
            mapping["last_name"] = i
        elif name in ["address", "street", "mailing address", "street address"]:
            mapping["address"] = i
        elif name == "city":
            mapping["city"] = i
        elif name == "state":
            mapping["state"] = i
        elif name in ["zip", "zip code", "zipcode", "postal", "postal code"]:
            mapping["zip"] = i
        elif name in ["legal description", "legal_description", "section", "legal"]:
            mapping["legal_description"] = i
        elif name in ["notes", "comments", "remarks"]:
            mapping["notes"] = i

    # If no name column found, try first column
    if mapping["name"] is None and mapping["first_name"] is None:
        mapping["name"] = 0

    return mapping


def _extract_legal_from_filename(filename: str) -> str:
    """Extract legal description from filename if present."""
    # Pattern for Section-Township-Range
    pattern = re.compile(r"(\d+)-?(\d+[NS])-?(\d+[EW])", re.IGNORECASE)
    match = pattern.search(filename)

    if match:
        section = match.group(1)
        township = match.group(2).upper()
        range_val = match.group(3).upper()
        return f"{section}-{township}-{range_val}"

    # Return generic default
    return "Unknown"


def _get_value(row: pd.Series, col_idx: Optional[int]) -> Optional[str]:
    """Get cell value as string or None."""
    if col_idx is None:
        return None
    try:
        value = row.iloc[col_idx]
        if pd.isna(value) or str(value).strip() == "":
            return None
        return str(value).strip()
    except (IndexError, KeyError):
        return None


def _process_row(
    row: pd.Series,
    col_mapping: dict[str, Optional[int]],
    default_legal: str,
) -> Optional[OwnerEntry]:
    """
    Process a single CSV row into an OwnerEntry.

    Args:
        row: DataFrame row
        col_mapping: Column index mapping
        default_legal: Default legal description

    Returns:
        OwnerEntry or None if invalid
    """
    # Get name
    raw_name = _get_value(row, col_mapping["name"])

    # If no full name, try to construct from first/last
    if not raw_name:
        first = _get_value(row, col_mapping["first_name"])
        last = _get_value(row, col_mapping["last_name"])
        if first and last:
            raw_name = f"{first} {last}"
        elif last:
            raw_name = last
        elif first:
            raw_name = first

    if not raw_name:
        return None

    # Extract annotations from name
    cleaned_name, name_notes = extract_address_annotations(raw_name)
    full_name = clean_name(cleaned_name)

    # Detect entity type
    entity_type = detect_entity_type(full_name)

    # Get or parse first/last names
    first_name = _get_value(row, col_mapping["first_name"])
    last_name = _get_value(row, col_mapping["last_name"])

    if not first_name and not last_name:
        first_name, last_name = parse_name(full_name, entity_type)

    # Get address components with annotation extraction
    raw_address = _get_value(row, col_mapping["address"])
    address = None
    city = _get_value(row, col_mapping["city"])
    state = _get_value(row, col_mapping["state"])
    zip_code = _get_value(row, col_mapping["zip"])
    address_notes: list[str] = []

    if raw_address:
        # Extract annotations from address
        cleaned_addr, addr_notes = extract_address_annotations(raw_address)
        address_notes.extend(addr_notes)

        # If we have address but no city/state/zip, try to parse
        if not city and not state and not zip_code:
            parsed = parse_address_with_notes(cleaned_addr)
            if parsed.city or parsed.state:
                city = parsed.city
                state = parsed.state
                zip_code = parsed.zip_code
                address = parsed.street
                address_notes.extend(parsed.notes)
            else:
                address = cleaned_addr
        else:
            address = cleaned_addr

    # Get legal description
    legal_description = _get_value(row, col_mapping["legal_description"])
    if not legal_description:
        legal_description = default_legal

    # Get existing notes column
    existing_notes = _get_value(row, col_mapping["notes"])

    # Merge all notes
    all_notes = _merge_notes(existing_notes, name_notes, address_notes)

    # Normalize state
    if state:
        state = state.upper()[:2]

    has_address = bool(address or city or state or zip_code)

    return OwnerEntry(
        full_name=full_name,
        first_name=first_name,
        last_name=last_name,
        entity_type=entity_type,
        address=address,
        city=city,
        state=state,
        zip_code=zip_code,
        legal_description=legal_description,
        notes=all_notes,
        duplicate_flag=False,
        has_address=has_address,
    )


def _flag_duplicates(entries: list[OwnerEntry]) -> list[OwnerEntry]:
    """Flag duplicate entries based on name matching."""
    name_groups: dict[str, list[int]] = {}

    for i, entry in enumerate(entries):
        norm_name = entry.full_name.upper().strip()
        if norm_name not in name_groups:
            name_groups[norm_name] = []
        name_groups[norm_name].append(i)

    for indices in name_groups.values():
        if len(indices) > 1:
            for idx in indices:
                entries[idx].duplicate_flag = True

    return entries

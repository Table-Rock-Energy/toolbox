"""Parser for Ownership Report Excel files (Blaine/Canadian county format).

These files have a distinct structure:
- Multi-sheet workbooks (one sheet per tract)
- Metadata rows at top (county, section/township/range, acreage)
- "MINERAL OWNER" header row anchoring column positions
- Owner data in multi-line cells (name + address in col A)
- Interest, Net Acres, and optionally Leasehold columns
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from io import BytesIO
from typing import Optional

import pandas as pd

from app.models.title import OwnerEntry
from app.services.title.address_parser import (
    extract_address_annotations,
    parse_address_with_notes,
    split_address_lines,
)
from app.services.title.entity_detector import detect_entity_type
from app.services.title.name_parser import clean_name, is_valid_name, parse_name

logger = logging.getLogger(__name__)


@dataclass
class SheetMetadata:
    """Metadata extracted from the top rows of an ownership report sheet."""

    legal_description: str = ""
    tract_description: str = ""
    county: Optional[str] = None
    total_acreage: Optional[float] = None
    header_row: int = -1
    col_interest: Optional[int] = None
    col_net_acres: Optional[int] = None
    col_leasehold: Optional[int] = None


def is_ownership_report(excel_file: pd.ExcelFile) -> bool:
    """Check if an Excel file is an ownership report format.

    Scans the first 30 rows of the first sheet for "OWNERSHIP REPORT" text.
    """
    if not excel_file.sheet_names:
        return False

    try:
        df = pd.read_excel(excel_file, sheet_name=excel_file.sheet_names[0], header=None)
        for i in range(min(30, len(df))):
            for j in range(min(3, len(df.columns))):
                val = df.iloc[i, j]
                if pd.notna(val) and "OWNERSHIP REPORT" in str(val).upper():
                    return True
    except Exception:
        return False

    return False


def extract_filename_metadata(filename: str) -> tuple[Optional[str], Optional[str]]:
    """Extract county and legal description from filename.

    Patterns:
        "Blaine_8-15N-13W OR.xlsx" -> ("Blaine", "8-15N-13W")
        "Canadian_18-11N-5W Ownership Report.xlsx" -> ("Canadian", "18-11N-5W")
    """
    if not filename:
        return None, None

    # Strip extension
    base = re.sub(r"\.\w+$", "", filename)

    # Try pattern: County_Section-Township-Range
    match = re.match(
        r"([A-Za-z]+)[_\s]+(\d+)-?(\d+[NS])-?(\d+[EW])",
        base,
        re.IGNORECASE,
    )
    if match:
        county = match.group(1).title()
        legal = f"{match.group(2)}-{match.group(3).upper()}-{match.group(4).upper()}"
        return county, legal

    return None, None


def _extract_sheet_metadata(
    df: pd.DataFrame,
    filename_county: Optional[str],
    filename_legal: Optional[str],
) -> Optional[SheetMetadata]:
    """Extract metadata from sheet header rows and find the MINERAL OWNER anchor."""
    meta = SheetMetadata()

    # Scan rows for metadata and MINERAL OWNER header
    scan_limit = min(30, len(df))
    for i in range(scan_limit):
        val0 = str(df.iloc[i, 0]) if pd.notna(df.iloc[i, 0]) else ""

        # County detection: "Blaine County, OK" or "Canadian County, OK"
        county_match = re.match(r"([A-Za-z]+)\s+County,?\s*(?:OK|Oklahoma)", val0, re.IGNORECASE)
        if county_match:
            meta.county = county_match.group(1).title()

        # Section/Township/Range from content
        str_match = re.search(
            r"Section\s+(\d+),?\s*Township\s+(\d+)\s+(North|South),?\s*Range\s+(\d+)\s+(West|East)",
            val0,
            re.IGNORECASE,
        )
        if not str_match:
            # Check col 1 too
            val1 = str(df.iloc[i, 1]) if len(df.columns) > 1 and pd.notna(df.iloc[i, 1]) else ""
            str_match = re.search(
                r"Section\s+(\d+),?\s*Township\s+(\d+)\s+(North|South),?\s*Range\s+(\d+)\s+(West|East)",
                val1,
                re.IGNORECASE,
            )
        if str_match:
            section = str_match.group(1)
            township = str_match.group(2) + ("N" if "north" in str_match.group(3).lower() else "S")
            range_val = str_match.group(4) + ("W" if "west" in str_match.group(5).lower() else "E")
            meta.legal_description = f"{section}-{township}-{range_val}"

        # Tract description
        tract_match = re.match(r"TRACT\s*#?\s*\d+\s*:\s*", val0, re.IGNORECASE)
        if tract_match:
            # Get tract description from col 1
            val1 = str(df.iloc[i, 1]) if len(df.columns) > 1 and pd.notna(df.iloc[i, 1]) else ""
            meta.tract_description = val1.strip()

        # Acreage
        if "CONTAINING" in val0.upper():
            for j in range(1, min(4, len(df.columns))):
                acreage_val = df.iloc[i, j]
                if pd.notna(acreage_val):
                    try:
                        meta.total_acreage = float(acreage_val)
                        break
                    except (ValueError, TypeError):
                        pass

        # MINERAL OWNER header row (anchor)
        if "MINERAL OWNER" in val0.upper():
            meta.header_row = i
            # Detect column positions from this row
            for j in range(1, len(df.columns)):
                cell = str(df.iloc[i, j]).upper().strip() if pd.notna(df.iloc[i, j]) else ""
                if "INTEREST" in cell and meta.col_interest is None:
                    meta.col_interest = j
                elif "NET ACRES" in cell or "NET" in cell:
                    meta.col_net_acres = j
                elif "LEASEHOLD" in cell:
                    meta.col_leasehold = j
            break

    # Fall back to filename metadata
    if not meta.county and filename_county:
        meta.county = filename_county
    if not meta.legal_description and filename_legal:
        meta.legal_description = filename_legal

    if meta.header_row < 0:
        return None

    return meta


def _parse_owner_cell(cell_text: str) -> tuple[str, Optional[str], Optional[str], list[str]]:
    """Parse a multi-line owner cell into name, address, and notes.

    Returns:
        (name, address_text, address_text_2, notes_list)
    """
    lines = cell_text.split("\n")
    name = ""
    address_lines: list[str] = []
    notes: list[str] = []

    # State pattern for city/state/zip
    csz_pattern = re.compile(
        r"[A-Za-z\s]+,\s*[A-Z]{2}\s+\d{5}",
    )
    street_pattern = re.compile(
        r"^\d+\s|^P\.?\s*O\.?\s*Box|^PO\s+Box",
        re.IGNORECASE,
    )

    for i, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line:
            continue

        if i == 0:
            name = line
            continue

        line_upper = line.upper()

        # Note indicators
        if line_upper.startswith("NOTE") or line_upper.startswith("SEE NOTE"):
            notes.append(line)
            continue

        # Apparent Successor text
        if "APPARENT SUCCESSOR" in line_upper:
            notes.append(line)
            continue

        # Remaindermen should not reach here (handled separately)

        # Address detection
        if street_pattern.search(line) or csz_pattern.search(line):
            address_lines.append(line)
        elif address_lines:
            # If we already have address lines and this doesn't look like
            # an address, treat as note
            notes.append(line)
        else:
            # Could be a c/o line or other note before address
            if re.match(r"^c/?o\s", line, re.IGNORECASE):
                address_lines.append(line)
            else:
                notes.append(line)

    address_text = ", ".join(address_lines) if address_lines else None

    return name, address_text, None, notes


def _parse_remaindermen_cell(
    cell_text: str,
    life_estate_name: str,
    legal_description: str,
    meta: SheetMetadata,
) -> list[OwnerEntry]:
    """Parse a Remaindermen cell into multiple OwnerEntry objects.

    Format:
        Remaindermen:
        Name 1
        Address 1
        City, ST ZIP
        Name 2
        Address 2
        City, ST ZIP
        ...
    """
    entries: list[OwnerEntry] = []
    lines = cell_text.split("\n")

    # Skip the "Remaindermen:" header
    data_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.lower().startswith("remaindermen"):
            continue
        data_lines.append(stripped)

    # Group lines into entries: name, then address lines until next name
    csz_pattern = re.compile(r"[A-Za-z\s]+,\s*[A-Z]{2}\s+\d{5}")

    current_name = ""
    current_addr_lines: list[str] = []
    base_note = f"Remainderman of {life_estate_name}"

    def flush_entry():
        nonlocal current_name, current_addr_lines
        if not current_name:
            return
        addr_text = ", ".join(current_addr_lines) if current_addr_lines else None
        entry = _build_owner_entry(
            current_name,
            addr_text,
            legal_description,
            meta,
            extra_notes=[base_note],
        )
        if entry:
            entries.append(entry)
        current_name = ""
        current_addr_lines = []

    street_pattern = re.compile(
        r"^\d+\s|^P\.?\s*O\.?\s*Box|^PO\s+Box",
        re.IGNORECASE,
    )

    for line in data_lines:
        # If this is an address line, add to current
        if street_pattern.search(line) or csz_pattern.search(line):
            current_addr_lines.append(line)
        elif re.match(r"^c/?o\s", line, re.IGNORECASE):
            current_addr_lines.append(line)
        else:
            # If city/state/zip was the last line, the previous entry is complete
            if current_addr_lines and csz_pattern.search(current_addr_lines[-1]):
                flush_entry()
            elif current_name:
                # Previous name had no address, flush it
                flush_entry()
            current_name = line

    # Flush last entry
    flush_entry()

    return entries


def _build_owner_entry(
    raw_name: str,
    address_text: Optional[str],
    legal_description: str,
    meta: SheetMetadata,
    interest: Optional[float] = None,
    net_acres: Optional[float] = None,
    leasehold: Optional[str] = None,
    extra_notes: Optional[list[str]] = None,
) -> Optional[OwnerEntry]:
    """Build an OwnerEntry from parsed components."""
    # Clean and validate name
    cleaned_name, name_notes = extract_address_annotations(raw_name)
    full_name = clean_name(cleaned_name)
    if not full_name or not is_valid_name(full_name):
        return None

    entity_type = detect_entity_type(full_name)
    first_name, middle_name, last_name = parse_name(full_name, entity_type)

    address = None
    address_line_2 = None
    city = None
    state = None
    zip_code = None
    address_notes: list[str] = []

    if address_text:
        parsed_addr = parse_address_with_notes(address_text)
        address = parsed_addr.street
        city = parsed_addr.city
        state = parsed_addr.state
        zip_code = parsed_addr.zip_code
        address_notes = parsed_addr.notes

    if address:
        address, address_line_2 = split_address_lines(address)

    has_address = bool(address or city or state or zip_code)

    # Merge all notes
    all_notes_parts: list[str] = []
    if name_notes:
        all_notes_parts.extend(name_notes)
    if address_notes:
        all_notes_parts.extend(address_notes)
    if extra_notes:
        all_notes_parts.extend(extra_notes)
    all_notes = "; ".join(n for n in all_notes_parts if n) or None

    # Build legal description with tract info
    full_legal = legal_description
    if meta.tract_description:
        full_legal = f"{legal_description} ({meta.tract_description})"

    return OwnerEntry(
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
        legal_description=full_legal,
        notes=all_notes,
        duplicate_flag=False,
        has_address=has_address,
        interest=interest,
        net_acres=net_acres,
        leasehold=leasehold,
    )


def _is_page_break_row(val0: str) -> bool:
    """Check if a row is a page break (repeated header or page number)."""
    upper = val0.upper().strip()
    if "MINERAL OWNER" in upper:
        return True
    if re.match(r"Page\s+\d+\s+of\s+\d+", val0, re.IGNORECASE):
        return True
    # Repeated section reference like "18-11N-5W Canadian Co. - Tract 1"
    if re.match(r"\d+-\d+[NS]-\d+[EW]\s+", val0, re.IGNORECASE):
        return True
    return False


def _is_skip_row(val0: str) -> bool:
    """Check if a row should be skipped (metadata, notes, footer)."""
    upper = val0.upper().strip()
    skip_prefixes = [
        "RECORDS EXAMINED",
        "LAST EXAMINED",
        "UNRELEASED MORTGAGES",
        "NOTE ",
        "NOTE:",
        "I CERTIFY",
        "SURFACE OWNER",
    ]
    return any(upper.startswith(p) for p in skip_prefixes)


def _get_float_value(df: pd.DataFrame, row_idx: int, col_idx: Optional[int]) -> Optional[float]:
    """Safely get a float value from a DataFrame cell."""
    if col_idx is None or col_idx >= len(df.columns):
        return None
    val = df.iloc[row_idx, col_idx]
    if pd.isna(val):
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _get_str_value(df: pd.DataFrame, row_idx: int, col_idx: Optional[int]) -> Optional[str]:
    """Safely get a string value from a DataFrame cell."""
    if col_idx is None or col_idx >= len(df.columns):
        return None
    val = df.iloc[row_idx, col_idx]
    if pd.isna(val):
        return None
    text = str(val).strip()
    return text if text else None


def process_ownership_report(
    file_bytes: bytes, filename: str
) -> tuple[list[OwnerEntry], Optional[str]]:
    """Process an Ownership Report Excel file.

    Returns:
        (entries, county) - list of parsed entries and detected county name
    """
    from app.services.title.excel_processor import _flag_duplicates

    entries: list[OwnerEntry] = []
    detected_county: Optional[str] = None
    filename_county, filename_legal = extract_filename_metadata(filename)

    excel_file = pd.ExcelFile(BytesIO(file_bytes))
    logger.info("Processing ownership report with %d sheets from %s", len(excel_file.sheet_names), filename)

    for sheet_name in excel_file.sheet_names:
        df = pd.read_excel(excel_file, sheet_name=sheet_name, header=None)
        if df.empty:
            logger.warning("Sheet '%s' is empty, skipping", sheet_name)
            continue

        meta = _extract_sheet_metadata(df, filename_county, filename_legal)
        if meta is None:
            logger.warning("Sheet '%s' has no MINERAL OWNER header, skipping", sheet_name)
            continue

        if meta.county and not detected_county:
            detected_county = meta.county

        logger.info(
            "Sheet '%s': legal=%s, county=%s, header_row=%d, interest_col=%s, net_acres_col=%s, leasehold_col=%s",
            sheet_name, meta.legal_description, meta.county, meta.header_row,
            meta.col_interest, meta.col_net_acres, meta.col_leasehold,
        )

        # Process data rows starting after the header
        # Data starts 2 rows after header (header + 1 blank row)
        i = meta.header_row + 2
        while i < len(df):
            val0 = df.iloc[i, 0]

            # Skip empty rows
            if pd.isna(val0):
                # Check for totals row (empty col A but numeric values)
                interest_val = _get_float_value(df, i, meta.col_interest)
                if interest_val is not None:
                    # This is a totals row - skip it
                    i += 1
                    continue
                i += 1
                continue

            cell_text = str(val0).strip()
            if not cell_text:
                i += 1
                continue

            # Skip page breaks, repeated headers, and metadata rows
            if _is_page_break_row(cell_text) or _is_skip_row(cell_text):
                i += 1
                continue

            # Get interest/net_acres/leasehold values
            interest = _get_float_value(df, i, meta.col_interest)
            net_acres = _get_float_value(df, i, meta.col_net_acres)
            leasehold = _get_str_value(df, i, meta.col_leasehold)

            # Clean up leasehold (remove trailing newlines)
            if leasehold:
                leasehold = re.sub(r"\s+", " ", leasehold).strip()

            # Check for Remaindermen cell
            if cell_text.upper().startswith("REMAINDERMEN"):
                # Look at the previous entry for the life estate owner name
                life_estate_name = entries[-1].full_name if entries else "Unknown"
                remainder_entries = _parse_remaindermen_cell(
                    cell_text, life_estate_name, meta.legal_description, meta
                )
                entries.extend(remainder_entries)
                i += 1
                continue

            # Parse normal owner cell
            name, address_text, _, cell_notes = _parse_owner_cell(cell_text)
            if not name:
                i += 1
                continue

            entry = _build_owner_entry(
                raw_name=name,
                address_text=address_text,
                legal_description=meta.legal_description,
                meta=meta,
                interest=interest,
                net_acres=net_acres,
                leasehold=leasehold,
                extra_notes=cell_notes if cell_notes else None,
            )
            if entry:
                entries.append(entry)

            i += 1

        logger.info("Extracted %d entries from sheet '%s'", len(entries), sheet_name)

    # Flag duplicates
    entries = _flag_duplicates(entries)

    # Fall back to filename county
    if not detected_county and filename_county:
        detected_county = filename_county

    logger.info(
        "Ownership report complete: %d total entries, county=%s",
        len(entries), detected_county,
    )

    return entries, detected_county

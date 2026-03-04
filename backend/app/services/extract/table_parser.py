"""Table-based parser for Exhibit A PDFs.

Handles TABLE_ATTENTION (Devon-style) and TABLE_SPLIT_ADDR (Mewbourne-style)
formats using pdfplumber table extraction.
"""

from __future__ import annotations

import io
import logging
import re

import pdfplumber

from app.models.extract import EntityType, PartyEntry
from app.services.extract.address_parser import parse_address
from app.services.extract.format_detector import ExhibitFormat
from app.utils.patterns import detect_entity_type

logger = logging.getLogger(__name__)

# Header keywords used to detect and skip header rows
_HEADER_KEYWORDS = {
    "name", "attention", "attn", "address", "city", "state", "zip",
    "no", "no.", "number", "#", "mailing", "respondent",
}


def parse_table_pdf(
    file_bytes: bytes, fmt: ExhibitFormat
) -> list[PartyEntry]:
    """Parse a table-layout Exhibit A PDF into PartyEntry objects.

    Args:
        file_bytes: Raw PDF bytes.
        fmt: The detected format (TABLE_ATTENTION or TABLE_SPLIT_ADDR).

    Returns:
        List of parsed PartyEntry objects.
    """
    entries: list[PartyEntry] = []
    entry_counter = 0
    in_curative = False

    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page_num, page in enumerate(pdf.pages):
                tables = page.extract_tables()
                if not tables:
                    logger.debug(
                        "No tables on page %d, skipping", page_num + 1
                    )
                    continue

                for table in tables:
                    if not table:
                        continue

                    for row in table:
                        if not row or not any(
                            cell and str(cell).strip() for cell in row
                        ):
                            continue

                        # Skip header rows
                        if _is_header_row(row):
                            continue

                        # Check for "Curative Parties" section marker
                        row_text = " ".join(
                            str(c) for c in row if c
                        ).strip()
                        if re.search(
                            r"curative\s+parties", row_text, re.IGNORECASE
                        ):
                            in_curative = True
                            continue

                        entry_counter += 1

                        if fmt == ExhibitFormat.TABLE_ATTENTION:
                            entry = _parse_attention_row(
                                row, entry_counter, in_curative
                            )
                        elif fmt == ExhibitFormat.TABLE_SPLIT_ADDR:
                            entry = _parse_split_addr_row(
                                row, entry_counter, in_curative
                            )
                        else:
                            continue

                        if entry:
                            entries.append(entry)

    except Exception as e:
        logger.exception("Table parsing failed: %s", e)

    logger.info(
        "Table parser extracted %d entries (format=%s)", len(entries), fmt.value
    )
    return entries


def _is_header_row(row: list) -> bool:
    """Detect if a row is a table header rather than data."""
    if not row:
        return False

    cells_text = [
        str(c).strip().lower() for c in row if c and str(c).strip()
    ]
    if not cells_text:
        return True  # empty row

    # If most cells match header keywords, it's a header
    matches = sum(
        1 for t in cells_text if t.rstrip(".") in _HEADER_KEYWORDS
    )
    return matches >= 2


def _parse_attention_row(
    row: list, counter: int, in_curative: bool
) -> PartyEntry | None:
    """Parse a TABLE_ATTENTION row: [Name, Attention, Address1, Address2].

    The Attention column is mapped to notes as 'c/o {attention}'.
    Address2 typically contains 'City, State ZIP'.
    """
    # Normalize cells
    cells = [_clean_cell(c) for c in row]

    # Pad to at least 4 columns
    while len(cells) < 4:
        cells.append("")

    name = cells[0]
    attention = cells[1]
    address1 = cells[2]
    address2 = cells[3]

    if not name:
        return None

    # Build notes from attention
    notes = f"c/o {attention}" if attention else None

    # Build address string for parsing
    address_str = ""
    if address1 and address2:
        address_str = f"{address1}, {address2}"
    elif address1:
        address_str = address1
    elif address2:
        address_str = address2

    addr = parse_address(address_str) if address_str else {
        "street": None, "street2": None, "city": None,
        "state": None, "zip": None,
    }

    entity_type_str = detect_entity_type(name)
    entity_type = EntityType(entity_type_str)

    # Name parsing for individuals
    from app.services.extract.name_parser import parse_name

    parsed = parse_name(name, entity_type.value)

    entry = PartyEntry(
        entry_number=str(counter),
        primary_name=name,
        entity_type=entity_type,
        mailing_address=addr.get("street"),
        mailing_address_2=addr.get("street2"),
        city=addr.get("city"),
        state=addr.get("state"),
        zip_code=addr.get("zip"),
        first_name=parsed.first_name if parsed.is_person else None,
        middle_name=parsed.middle_name if parsed.is_person else None,
        last_name=parsed.last_name if parsed.is_person else None,
        suffix=parsed.suffix if parsed.is_person else None,
        notes=notes,
        flagged=in_curative,
        flag_reason="Curative party" if in_curative else None,
    )
    return entry


def _parse_split_addr_row(
    row: list, counter: int, in_curative: bool
) -> PartyEntry | None:
    """Parse a TABLE_SPLIT_ADDR row: [No., Name, Addr1, Addr2, City, State, Zip].

    Fields map directly to PartyEntry.
    """
    cells = [_clean_cell(c) for c in row]

    # Pad to 7 columns
    while len(cells) < 7:
        cells.append("")

    entry_number = cells[0] or str(counter)
    name = cells[1]
    address1 = cells[2]
    address2 = cells[3]
    city = cells[4]
    state = cells[5]
    zip_code = cells[6]

    if not name:
        return None

    # Clean entry number (remove trailing period)
    entry_number = entry_number.rstrip(".")

    entity_type_str = detect_entity_type(name)
    entity_type = EntityType(entity_type_str)

    from app.services.extract.name_parser import parse_name

    parsed = parse_name(name, entity_type.value)

    entry = PartyEntry(
        entry_number=entry_number,
        primary_name=name,
        entity_type=entity_type,
        mailing_address=address1 or None,
        mailing_address_2=address2 or None,
        city=city or None,
        state=state.upper()[:2] if state else None,
        zip_code=zip_code or None,
        first_name=parsed.first_name if parsed.is_person else None,
        middle_name=parsed.middle_name if parsed.is_person else None,
        last_name=parsed.last_name if parsed.is_person else None,
        suffix=parsed.suffix if parsed.is_person else None,
        notes="Curative party" if in_curative else None,
        flagged=in_curative,
        flag_reason="Curative party" if in_curative else None,
    )
    return entry


def _clean_cell(cell) -> str:
    """Clean a table cell value to a trimmed string."""
    if cell is None:
        return ""
    text = str(cell).strip()
    # Collapse internal whitespace
    text = re.sub(r"\s+", " ", text)
    return text

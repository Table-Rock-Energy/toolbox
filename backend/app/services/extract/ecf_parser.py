"""ECF filing parser for OCC multiunit horizontal well applications.

Parses ECF Exhibit A respondent lists into structured entries with names,
addresses, entity types, section tags, and case metadata from raw PDF text.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from app.models.extract import CaseMetadata, EntityType, PartyEntry
from app.services.extract.name_parser import parse_name
from app.services.shared.address_parser import parse_address
from app.utils.patterns import detect_entity_type

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@dataclass
class ECFParseResult:
    """Result of parsing an ECF filing."""

    entries: list[PartyEntry] = field(default_factory=list)
    metadata: CaseMetadata = field(default_factory=CaseMetadata)


def parse_ecf_filing(text: str) -> ECFParseResult:
    """Parse an ECF PDF's full text into entries and metadata.

    Args:
        text: Full extracted text from the ECF PDF.

    Returns:
        ECFParseResult with entries and metadata.
    """
    metadata = _extract_metadata(text)
    exhibit_text = _extract_exhibit_a_section(text)
    cleaned = _strip_page_headers(exhibit_text, metadata)
    sections = _split_into_sections(cleaned)

    entries: list[PartyEntry] = []
    for section_type, section_text in sections:
        entries.extend(_parse_section_entries(section_text, section_type))

    logger.info("Parsed %d ECF entries across %d sections", len(entries), len(sections))
    return ECFParseResult(entries=entries, metadata=metadata)


# ---------------------------------------------------------------------------
# ECF-specific patterns
# ---------------------------------------------------------------------------

DECEASED_PATTERN = re.compile(r",?\s*(?:possibly\s+)?deceased\b", re.IGNORECASE)
NOW_NAME_PATTERN = re.compile(r"\s+now\s+(\w+)\s*$", re.IGNORECASE)
HEIRS_DEVISEES_PATTERN = re.compile(
    r"Heirs\s+and\s+Devisees\s+of\b", re.IGNORECASE
)
CO_LINE_PATTERN = re.compile(r"^c/o\s+(.+)$", re.IGNORECASE | re.MULTILINE)

# Entry number: digit(s) + dot + space + uppercase letter
# This distinguishes from street addresses like "12801 N Central"
ENTRY_NUMBER_RE = re.compile(r"^(\d+)\.\s+([A-Z].*)", re.MULTILINE)

# Page header/footer patterns
PAGE_HEADER_PATTERN = re.compile(
    r"^MULTIUNIT HORIZONTAL WELL.*$", re.MULTILINE
)
PAGE_FOOTER_PATTERN = re.compile(
    r"^CASE\s+CD\s+CD\d+.*?PAGE\s+\d+\s+OF\s+\d+\s*$", re.MULTILINE
)
EXHIBIT_A_HEADER = re.compile(
    r'^EXHIBIT\s+["\u201c]?A["\u201d]?\s*$', re.MULTILINE
)
PAGE_NUMBER_PATTERN = re.compile(r"^\d{1,2}\s*$", re.MULTILINE)

# Section headers (order: longest/most-specific first)
SECTION_HEADERS = [
    ("CURATIVE RESPONDENTS WITH ADDRESS UNKNOWN:", "curative_unknown"),
    ("RESPONDENTS WITH ADDRESS UNKNOWN:", "address_unknown"),
    ("CURATIVE RESPONDENTS:", "curative"),
    ("FOR INFORMATIONAL PURPOSES ONLY:", "informational"),
]

# Address line detection
ADDRESS_START_RE = re.compile(
    r"^\d+\s+\w|^P\.?\s*O\.?\s*Box\b", re.IGNORECASE
)
CITY_STATE_ZIP_RE = re.compile(
    r"^[A-Z][a-z].*\s+[A-Z]{2}\s+\d{5}", re.MULTILINE
)


# ---------------------------------------------------------------------------
# Metadata extraction
# ---------------------------------------------------------------------------


def _extract_metadata(text: str) -> CaseMetadata:
    """Extract case metadata from the first page of the ECF PDF."""
    county = None
    county_match = re.search(r"(\w+)\s+COUNTY,\s+OKLAHOMA", text)
    if county_match:
        county = county_match.group(1).strip()

    # Case number: "CAUSE NO. CD\n2026-000909-T" (may span two lines)
    case_number = None
    # Try single-line first
    case_match = re.search(
        r"CAUSE\s+NO\.?\s+CD\s+(\d{4}-\d+-[A-Z])", text
    )
    if case_match:
        case_number = f"CD {case_match.group(1)}"
    else:
        # Try two-line: "CAUSE NO. CD\n2026-000909-T"
        case_match = re.search(
            r"CAUSE\s+NO\.?\s+CD\s*\n\s*(\d{4}-\d+-[A-Z])", text
        )
        if case_match:
            case_number = f"CD {case_match.group(1)}"

    applicant = None
    app_match = re.search(r"APPLICANT:\s+(.+?)(?:\n|$)", text)
    if app_match:
        applicant = app_match.group(1).strip()

    legal_description = None
    legal_match = re.search(
        r"(SECTION\(S\)\s+.+?RANGE\s+\d+\s+\w+)", text
    )
    if legal_match:
        legal_description = legal_match.group(1).strip()

    well_name = None
    well_match = re.search(r"\(the\s+(.+?)\s+well\)", text, re.IGNORECASE)
    if well_match:
        well_name = well_match.group(1).strip()

    return CaseMetadata(
        county=county,
        legal_description=legal_description,
        applicant=applicant,
        case_number=case_number,
        well_name=well_name,
    )


# ---------------------------------------------------------------------------
# Text preprocessing
# ---------------------------------------------------------------------------


def _extract_exhibit_a_section(text: str) -> str:
    """Extract only the Exhibit A respondent list portion."""
    # Find standalone EXHIBIT "A" header on its own line (not inline references
    # like 'set out on Exhibit "A", attached hereto')
    exhibit_match = re.search(
        r'^EXHIBIT\s+["\u201c]?A["\u201d]?\s*$', text, re.IGNORECASE | re.MULTILINE
    )
    if not exhibit_match:
        # Fallback: any EXHIBIT "A" that is followed by numbered entries
        exhibit_match = re.search(
            r'EXHIBIT\s+["\u201c]?A["\u201d]?', text, re.IGNORECASE
        )
    if exhibit_match:
        text = text[exhibit_match.end():]

    # Look for "RESPONDENTS" header right after
    resp_match = re.search(r"RESPONDENTS\s*\n", text)
    if resp_match:
        text = text[resp_match.end():]

    # Trim at Exhibit B if present
    exhibit_b = re.search(
        r'EXHIBIT\s+["\u201c]?B["\u201d]?', text, re.IGNORECASE
    )
    if exhibit_b:
        text = text[:exhibit_b.start()]

    return text.strip()


def _strip_page_headers(text: str, metadata: CaseMetadata | None = None) -> str:
    """Remove repeated page headers and footers."""
    text = PAGE_HEADER_PATTERN.sub("", text)
    text = PAGE_FOOTER_PATTERN.sub("", text)
    text = EXHIBIT_A_HEADER.sub("", text)

    # Strip county/section summary lines that repeat on each page
    text = re.sub(
        r"^SECTION\(S\)\s+.*?(?:COUNTY|OKLAHOMA).*$", "", text, flags=re.MULTILINE
    )

    # Strip applicant name lines that repeat (if metadata available)
    if metadata and metadata.applicant:
        escaped = re.escape(metadata.applicant)
        text = re.sub(
            rf"^{escaped}\s*$", "", text, flags=re.MULTILINE
        )

    # Strip "RESPONDENTS" header that may repeat
    text = re.sub(r"^RESPONDENTS\s*$", "", text, flags=re.MULTILINE)

    # Strip standalone page numbers
    text = PAGE_NUMBER_PATTERN.sub("", text)

    # Collapse excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


# ---------------------------------------------------------------------------
# Section splitting
# ---------------------------------------------------------------------------


def _split_into_sections(text: str) -> list[tuple[str, str]]:
    """Split text by section headers into (section_type, section_text) tuples."""
    sections: list[tuple[str, str]] = []

    # Find all section header positions
    header_positions: list[tuple[int, str]] = []
    for header_text, section_type in SECTION_HEADERS:
        pos = text.find(header_text)
        if pos >= 0:
            header_positions.append((pos, section_type))

    if not header_positions:
        # No section headers found -- everything is "regular"
        return [("regular", text)]

    # Sort by position
    header_positions.sort(key=lambda x: x[0])

    # Text before first header is "regular"
    first_pos = header_positions[0][0]
    regular_text = text[:first_pos].strip()
    if regular_text:
        sections.append(("regular", regular_text))

    # Each header to the next header (or end)
    for i, (pos, section_type) in enumerate(header_positions):
        # Find the header text to skip past it
        for header_text, st in SECTION_HEADERS:
            if st == section_type:
                start = pos + len(header_text)
                break
        else:
            start = pos

        if i + 1 < len(header_positions):
            end = header_positions[i + 1][0]
        else:
            end = len(text)

        section_text = text[start:end].strip()
        if section_text:
            sections.append((section_type, section_text))

    return sections


# ---------------------------------------------------------------------------
# Entry parsing
# ---------------------------------------------------------------------------


def _parse_section_entries(text: str, section_type: str) -> list[PartyEntry]:
    """Split section text into entry blocks and parse each."""
    if not text.strip():
        return []

    # Split on entry number pattern: newline + digit(s) + dot + space + uppercase
    # Use lookahead so the match is included in the next block
    blocks = re.split(r"\n(?=\d+\.\s+[A-Z])", text)

    entries: list[PartyEntry] = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue

        # Verify this block starts with an entry number
        match = re.match(r"^(\d+)\.\s+(.+)", block, re.DOTALL)
        if not match:
            continue

        entry = _parse_entry_block(block, section_type)
        if entry:
            entries.append(entry)

    return entries


def _parse_entry_block(block: str, section_type: str) -> PartyEntry | None:
    """Parse a single ECF entry block into a PartyEntry."""
    lines = [line.strip() for line in block.strip().split("\n") if line.strip()]
    if not lines:
        return None

    # Extract entry number from first line
    first_match = re.match(r"^(\d+)\.\s+(.+)", lines[0])
    if not first_match:
        return None

    entry_number = first_match.group(1)
    first_line_rest = first_match.group(2)

    # Rebuild lines with the first line's content after the number
    content_lines = [first_line_rest] + lines[1:]

    # Separate name lines from address lines and detect c/o
    name_lines: list[str] = []
    address_lines: list[str] = []
    notes_parts: list[str] = []
    in_address = False
    is_address_unknown = section_type in ("address_unknown", "curative_unknown")

    for line in content_lines:
        # Check for c/o line
        co_match = re.match(r"^c/o\s+(.+)$", line, re.IGNORECASE)
        if co_match:
            notes_parts.append(f"c/o {co_match.group(1)}")
            continue

        if not in_address and not is_address_unknown:
            # Check if this line starts an address
            if ADDRESS_START_RE.match(line):
                in_address = True
                address_lines.append(line)
            elif re.match(r"^[A-Z][a-z].*\s+[A-Z]{2}\s+\d{5}", line):
                # City/state/ZIP line
                in_address = True
                address_lines.append(line)
            else:
                name_lines.append(line)
        else:
            if not is_address_unknown:
                address_lines.append(line)
            else:
                name_lines.append(line)

    # Join name lines into full name text
    full_name = " ".join(name_lines).strip()
    if not full_name:
        return None

    # Classify entity type (ECF-specific)
    entity_type, extra_notes = _classify_ecf_entity(full_name)
    notes_parts.extend(extra_notes)

    # Handle "now [name]" pattern BEFORE cleaning name
    now_match = NOW_NAME_PATTERN.search(full_name)
    if now_match:
        married_name = now_match.group(1)
        # Get the name parts before "now"
        name_before_now = full_name[:now_match.start()].strip()
        name_parts = name_before_now.split()
        if len(name_parts) >= 2:
            maiden_last = name_parts[-1]
            notes_parts.append(f"f/k/a {maiden_last}")
            # Replace last name with married name
            full_name = " ".join(name_parts[:-1]) + " " + married_name
        else:
            full_name = name_before_now + " " + married_name

    # Strip deceased/heirs annotations from name for clean parsing
    clean_name = DECEASED_PATTERN.sub("", full_name).strip()
    clean_name = HEIRS_DEVISEES_PATTERN.sub("", clean_name).strip()
    clean_name = clean_name.strip(",").strip()

    # Parse name components for individuals
    parsed = parse_name(clean_name, entity_type.value)

    # Parse address
    address_text = "\n".join(address_lines) if address_lines else ""
    addr = parse_address(address_text) if address_text else {}

    # Combine notes
    notes = "; ".join(notes_parts) if notes_parts else None

    # Flagging
    flagged = False
    flag_reason = None
    if len(clean_name) < 3:
        flagged = True
        flag_reason = "Name too short"
    elif (
        section_type in ("regular", "curative")
        and not address_lines
        and not is_address_unknown
    ):
        flagged = True
        flag_reason = "Expected address missing"

    return PartyEntry(
        entry_number=entry_number,
        primary_name=clean_name,
        entity_type=entity_type,
        mailing_address=addr.get("street"),
        mailing_address_2=addr.get("street2"),
        city=addr.get("city"),
        state=addr.get("state"),
        zip_code=addr.get("zip"),
        first_name=parsed.first_name or None,
        middle_name=parsed.middle_name or None,
        last_name=parsed.last_name or None,
        suffix=parsed.suffix or None,
        notes=notes,
        flagged=flagged,
        flag_reason=flag_reason,
        section_type=section_type,
    )


# ---------------------------------------------------------------------------
# Entity classification
# ---------------------------------------------------------------------------


def _classify_ecf_entity(text: str) -> tuple[EntityType, list[str]]:
    """Detect entity type with ECF-specific deceased/heirs handling.

    Returns:
        Tuple of (entity_type, extra_notes_list).
    """
    notes: list[str] = []

    # Check for deceased (case-insensitive, with or without comma)
    if DECEASED_PATTERN.search(text):
        if re.search(r"possibly\s+deceased", text, re.IGNORECASE):
            notes.append("possibly deceased")
        else:
            notes.append("deceased")
        return EntityType.ESTATE, notes

    # Check for "Heirs and Devisees of"
    if HEIRS_DEVISEES_PATTERN.search(text):
        return EntityType.ESTATE, notes

    # Fall back to existing detection
    detected = detect_entity_type(text)
    return EntityType(detected), notes

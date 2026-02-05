"""Parser service for extracting party entries from Exhibit A text."""

from __future__ import annotations

import logging
import re
from typing import Optional

from app.models.extract import EntityType, PartyEntry
from app.services.extract.address_parser import parse_address
from app.utils.patterns import (
    ADDRESS_UNKNOWN_PATTERN,
    AKA_PATTERN,
    CO_PATTERN,
    CORP_PATTERN,
    ESTATE_PATTERN,
    FBO_PATTERN,
    FKA_PATTERN,
    GOVERNMENT_PATTERN,
    HEIR_OF_PATTERN,
    INC_PATTERN,
    INDIVIDUALLY_PATTERN,
    LLC_PATTERN,
    LP_PATTERN,
    PARTNERSHIP_PATTERN,
    TRUST_DATE_PATTERN,
    TRUST_PATTERN,
    TRUSTEE_PATTERN,
    UNKNOWN_HEIRS_PATTERN,
    US_STATES,
    clean_text,
)

logger = logging.getLogger(__name__)


def parse_exhibit_a(text: str) -> list[PartyEntry]:
    """
    Parse Exhibit A text into a list of party entries.

    Args:
        text: Raw text from Exhibit A section

    Returns:
        List of parsed PartyEntry objects
    """
    entries = []

    # Split text into individual entries using entry number pattern
    raw_entries = _split_into_entries(text)

    for raw_entry in raw_entries:
        try:
            entry = _parse_single_entry(raw_entry)
            if entry:
                entries.append(entry)
        except Exception as e:
            logger.warning(f"Failed to parse entry: {raw_entry[:50]}... Error: {e}")
            # Create a flagged entry for failed parses
            entries.append(
                PartyEntry(
                    entry_number="?",
                    primary_name=raw_entry[:100] if raw_entry else "Unknown",
                    flagged=True,
                    flag_reason=f"Parse error: {str(e)}",
                )
            )

    return entries


def _split_into_entries(text: str) -> list[str]:
    """
    Split the Exhibit A text into individual entry strings.

    Args:
        text: Full Exhibit A text

    Returns:
        List of raw entry strings
    """
    # Pattern to match entry numbers: "1.", "2.", "U 1.", "U1.", etc.
    entry_pattern = re.compile(
        r"(?:^|\n)\s*(U\s*\d+\.|\d+\.)\s+",
        re.MULTILINE,
    )

    # Find all entry start positions
    matches = list(entry_pattern.finditer(text))

    if not matches:
        logger.warning("No entry numbers found in text")
        return []

    entries = []
    for i, match in enumerate(matches):
        start = match.start()
        # End at the start of the next entry, or end of text
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)

        entry_text = text[start:end].strip()
        if entry_text:
            entries.append(entry_text)

    return entries


def _parse_single_entry(raw_text: str) -> Optional[PartyEntry]:
    """
    Parse a single entry string into a PartyEntry object.

    Args:
        raw_text: Raw text for a single entry

    Returns:
        PartyEntry object or None if parsing fails
    """
    if not raw_text or len(raw_text.strip()) < 3:
        return None

    raw_text = clean_text(raw_text)

    # Extract entry number
    entry_number = _extract_entry_number(raw_text)
    if not entry_number:
        return None

    # Remove entry number from text
    text_without_number = _remove_entry_number(raw_text)

    # Check for ADDRESS UNKNOWN
    is_address_unknown = bool(ADDRESS_UNKNOWN_PATTERN.search(text_without_number))

    # Extract notes (a/k/a, f/k/a, c/o, trustee info, etc.)
    notes_list, text_cleaned = _extract_notes(text_without_number)

    # Separate name from address
    name_text, address_text = _separate_name_and_address(
        text_cleaned, is_address_unknown
    )

    # Clean up the name
    primary_name = _clean_name(name_text)

    # Detect entity type
    entity_type = _detect_entity_type(text_without_number)

    # Parse address
    address_parts = {"street": None, "street2": None, "city": None, "state": None, "zip": None}
    if address_text and not is_address_unknown:
        address_parts = parse_address(address_text)

    # Build notes string
    notes = "; ".join(notes_list) if notes_list else None

    # Determine if entry should be flagged
    flagged, flag_reason = _check_flagging(
        primary_name, address_parts, is_address_unknown
    )

    return PartyEntry(
        entry_number=entry_number,
        primary_name=primary_name,
        entity_type=entity_type,
        mailing_address=address_parts["street"],
        mailing_address_2=address_parts["street2"],
        city=address_parts["city"],
        state=address_parts["state"],
        zip_code=address_parts["zip"],
        notes=notes,
        flagged=flagged,
        flag_reason=flag_reason,
    )


def _extract_entry_number(text: str) -> Optional[str]:
    """Extract the entry number from entry text."""
    # Match patterns like "1.", "U 1.", "U1."
    match = re.match(r"^\s*(U\s*)?(\d+)\.", text)
    if match:
        prefix = "U" if match.group(1) else ""
        number = match.group(2)
        return f"{prefix}{number}"
    return None


def _remove_entry_number(text: str) -> str:
    """Remove the entry number prefix from text."""
    return re.sub(r"^\s*(U\s*)?\d+\.\s*", "", text).strip()


def _extract_notes(text: str) -> tuple[list[str], str]:
    """
    Extract notes (a/k/a, f/k/a, c/o, trustee info, etc.) from text.

    Returns:
        Tuple of (list of notes, cleaned text with notes removed)
    """
    notes = []
    cleaned = text

    # Extract a/k/a names
    aka_matches = AKA_PATTERN.findall(cleaned)
    for aka in aka_matches:
        notes.append(f"a/k/a {aka.strip()}")
    cleaned = AKA_PATTERN.sub(" ", cleaned)

    # Extract f/k/a names
    fka_matches = FKA_PATTERN.findall(cleaned)
    for fka in fka_matches:
        notes.append(f"f/k/a {fka.strip()}")
    cleaned = FKA_PATTERN.sub(" ", cleaned)

    # Extract c/o (but preserve for address parsing)
    co_matches = CO_PATTERN.findall(cleaned)
    for co in co_matches:
        notes.append(f"c/o {co.strip()}")
    # Don't remove c/o from text as it's part of address

    # Extract trust dates
    trust_date_matches = TRUST_DATE_PATTERN.findall(cleaned)
    for date in trust_date_matches:
        notes.append(f"Trust dated {date.strip()}")

    # Extract trustee info
    trustee_match = TRUSTEE_PATTERN.search(cleaned)
    if trustee_match:
        trustee_text = trustee_match.group(1).strip()
        if trustee_text and "trustee" in trustee_text.lower():
            notes.append(trustee_text)

    # Extract "Individually and as..." patterns
    indiv_matches = INDIVIDUALLY_PATTERN.findall(cleaned)
    for indiv in indiv_matches:
        notes.append(indiv.strip().lstrip(",").strip())

    # Extract "heir of" patterns
    heir_matches = HEIR_OF_PATTERN.findall(cleaned)
    for heir in heir_matches:
        notes.append(heir.strip().lstrip(",").strip())

    # Extract FBO patterns
    fbo_matches = FBO_PATTERN.findall(cleaned)
    for fbo in fbo_matches:
        notes.append(f"FBO {fbo.strip()}")

    # Clean up multiple spaces (but preserve newlines for line-based parsing)
    cleaned = re.sub(r"[^\S\n]+", " ", cleaned)  # Collapse spaces/tabs but not newlines
    cleaned = re.sub(r" *\n *", "\n", cleaned)  # Clean spaces around newlines
    cleaned = cleaned.strip()

    return notes, cleaned


def _separate_name_and_address(text: str, is_address_unknown: bool) -> tuple[str, str]:
    """
    Separate the name portion from the address portion.

    Handles multi-line format where entries have structure:
    - Name on first line(s)
    - Street address line(s)
    - City, State ZIP line

    Args:
        text: Entry text with entry number removed
        is_address_unknown: Whether this is an ADDRESS UNKNOWN entry

    Returns:
        Tuple of (name_text, address_text)
    """
    if is_address_unknown:
        # Remove ADDRESS UNKNOWN and return just the name
        name = ADDRESS_UNKNOWN_PATTERN.sub("", text).strip()
        return name, ""

    # Split into lines and process
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    if not lines:
        return text, ""

    # Patterns for address line detection
    street_pattern = re.compile(
        r"^(\d+\s+|P\.?O\.?\s*Box|c/o\s+)",
        re.IGNORECASE,
    )
    city_state_zip_pattern = re.compile(
        r",?\s*[A-Z]{2}\s+\d{5}",
        re.IGNORECASE,
    )

    # Find where address starts by looking at each line
    address_start_idx = None
    for i, line in enumerate(lines):
        # Check if line looks like a street address
        if street_pattern.match(line):
            address_start_idx = i
            break
        # Check if line contains city, state, ZIP (indicates we're in address)
        if city_state_zip_pattern.search(line):
            # This line has city/state/zip, address might have started earlier
            # Look back for street address
            for j in range(i - 1, -1, -1):
                if street_pattern.match(lines[j]):
                    address_start_idx = j
                    break
            if address_start_idx is None:
                address_start_idx = i
            break

    if address_start_idx is not None:
        name_lines = lines[:address_start_idx]
        address_lines = lines[address_start_idx:]
        name = " ".join(name_lines).strip()
        address = ", ".join(address_lines).strip()
        return name, address

    # Fallback: try the old single-line approach
    flat_text = " ".join(lines)

    # Look for address markers
    address_start_pattern = re.compile(
        r"(?:^|\s)(\d+\s+[A-Za-z]|P\.?O\.?\s*Box|c/o\s+)",
        re.IGNORECASE,
    )

    match = address_start_pattern.search(flat_text)
    if match:
        before = flat_text[: match.start()].strip()
        after = flat_text[match.start() :].strip()
        if len(before) > 5:
            return before, after

    # Try to find a ZIP code and work backwards
    zip_pattern = re.compile(r"\b\d{5}(?:-\d{4})?\b")
    zip_match = zip_pattern.search(flat_text)

    if zip_match:
        text_before_zip = flat_text[: zip_match.start()]
        state_pattern = re.compile(r",?\s*([A-Z]{2})\s*$")
        state_match = state_pattern.search(text_before_zip)

        if state_match:
            text_before_state = text_before_zip[: state_match.start()]

            for i, char in enumerate(text_before_state):
                if char.isdigit():
                    potential_start = text_before_state[i:]
                    if re.match(r"\d+\s+\w", potential_start):
                        name = text_before_state[:i].strip().rstrip(",").strip()
                        address = flat_text[i:].strip()
                        if len(name) > 3:
                            return name, address
                    break

            po_match = re.search(r"P\.?O\.?\s*Box", text_before_state, re.IGNORECASE)
            if po_match:
                name = text_before_state[: po_match.start()].strip().rstrip(",").strip()
                address = flat_text[po_match.start() :].strip()
                return name, address

    # Fallback: split by comma
    parts = flat_text.split(",")
    if len(parts) >= 3:
        name = ", ".join(parts[:-3]).strip() if len(parts) > 3 else parts[0].strip()
        address = ", ".join(parts[-3:]).strip() if len(parts) > 3 else ", ".join(parts[1:])
        return name, address

    return flat_text, ""


def _clean_name(name: str) -> str:
    """Clean up the extracted name."""
    # Remove leading/trailing punctuation and whitespace
    name = name.strip().strip(",").strip()

    # Remove double spaces
    name = re.sub(r"\s+", " ", name)

    # Remove common artifacts
    name = re.sub(r"\s*,\s*$", "", name)

    # Remove "c/o" prefix if it starts with that (it's part of address)
    if name.lower().startswith("c/o "):
        # Find the actual name after c/o
        co_match = re.match(r"c/o\s+[^,]+,?\s*(.+)", name, re.IGNORECASE)
        if co_match:
            name = co_match.group(1).strip()

    return name


def _detect_entity_type(text: str) -> EntityType:
    """
    Detect the entity type based on keywords in text.

    Order matters - first match wins.
    """
    # Check patterns in order of specificity
    if UNKNOWN_HEIRS_PATTERN.search(text):
        return EntityType.UNKNOWN_HEIRS

    if ESTATE_PATTERN.search(text):
        return EntityType.ESTATE

    if TRUST_PATTERN.search(text):
        return EntityType.TRUST

    if LLC_PATTERN.search(text):
        return EntityType.LLC

    if INC_PATTERN.search(text) or CORP_PATTERN.search(text):
        return EntityType.CORPORATION

    if LP_PATTERN.search(text):
        # Make sure it's not "Partners" without being a limited partnership
        if not re.search(r"\bPartners\b", text) or PARTNERSHIP_PATTERN.search(text):
            return EntityType.PARTNERSHIP

    if PARTNERSHIP_PATTERN.search(text):
        return EntityType.PARTNERSHIP

    if GOVERNMENT_PATTERN.search(text):
        return EntityType.GOVERNMENT

    return EntityType.INDIVIDUAL


def _check_flagging(
    name: str, address: dict, is_address_unknown: bool
) -> tuple[bool, Optional[str]]:
    """
    Check if an entry should be flagged for review.

    Returns:
        Tuple of (flagged: bool, reason: str or None)
    """
    reasons = []

    # Check for missing address when not ADDRESS UNKNOWN
    if not is_address_unknown:
        if not address.get("street") and not address.get("city"):
            reasons.append("No address found")

    # Check for invalid state
    if address.get("state"):
        if address["state"].upper() not in US_STATES:
            reasons.append(f"Invalid state: {address['state']}")

    # Check for invalid ZIP
    if address.get("zip"):
        if not re.match(r"^\d{5}(-\d{4})?$", address["zip"]):
            reasons.append(f"Invalid ZIP format: {address['zip']}")

    # Check for very short name
    if len(name) < 10:
        reasons.append("Name unusually short")

    # Check if name contains address-like fragments
    if re.search(r"\b\d{5}\b", name):  # ZIP code in name
        reasons.append("Name may contain address fragments")

    if reasons:
        return True, "; ".join(reasons)

    return False, None

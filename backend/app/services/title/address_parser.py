"""Address parsing service for extracting structured address components."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from app.utils.patterns import (
    APT_SUITE_PATTERN,
    PO_BOX_PATTERN,
    US_STATES,
    normalize_state,
    validate_zip,
)


@dataclass
class AddressWithNotes:
    """Parsed address with extracted notes/annotations."""

    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    notes: list[str] = field(default_factory=list)


# Patterns for extracting annotations from addresses
# Note: Order matters - more specific patterns should come first
ANNOTATION_PATTERNS = [
    # c/o (care of) - extract the name/entity after c/o up to comma or number
    (re.compile(r"\bc/?o\s+([^,\n\d]+?)(?=\s*(?:,|\d|$))", re.IGNORECASE), "c/o"),
    # Note references - Note (6), Note (7), etc.
    (re.compile(r"\bNote\s*\((\d+)\)", re.IGNORECASE), "Note"),
    # FD references - FD: 11-13
    (re.compile(r"\bFD:\s*([^\n,]+)", re.IGNORECASE), "FD"),
    # QCMD references - QCMD: 821-822
    (re.compile(r"\bQCMD:\s*([^\n,]+)", re.IGNORECASE), "QCMD"),
    # Lease references - Lease 23, Lease 22
    (re.compile(r"-?\s*Lease\s+(\d+(?:\s*[-&]\s*\d+)?)", re.IGNORECASE), "Lease"),
    # Relationship annotations - daugh., son, step daughter (but not "son of")
    (re.compile(r",?\s*-?\s*\b(daugh(?:ter)?\.?)\b", re.IGNORECASE), "relationship"),
    (re.compile(r",?\s*\b(son)\b(?!\s+of)", re.IGNORECASE), "relationship"),
    (re.compile(r",?\s*\b(step\s*(?:daughter|son|mother|father)?)\b", re.IGNORECASE), "relationship"),
    # Just "step" alone at end of name (e.g., "John Smith, step")
    (re.compile(r",\s*(step)\s*$", re.IGNORECASE), "relationship"),
    # Established/created dates for trusts - Established June 15, 2006
    (re.compile(r"\bEstablished\s+([A-Z][a-z]+\s+\d{1,2},?\s+\d{4})", re.IGNORECASE), "established"),
    # BENEFICIARY marker
    (re.compile(r"\bBENEFICIARY\b", re.IGNORECASE), "marker"),
    # Possible Apparent Heirs marker
    (re.compile(r"\bPossible\s+Apparent\s+Heirs:?\s*", re.IGNORECASE), "marker"),
]

# Patterns to extract as notes but NOT remove from text
# (these provide context but shouldn't change the name/address)
ANNOTATION_EXTRACT_ONLY = [
    # Trust date patterns - dated March 28, 1997 or dated 04/12/1997
    (re.compile(r"\b(?:dated|dtd\.?)\s+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", re.IGNORECASE), "dated"),
    (re.compile(r"\b(?:dated|dtd\.?)\s+([A-Z][a-z]+\s+\d{1,2},?\s+\d{4})", re.IGNORECASE), "dated"),
    # U/T/A (Under Trust Agreement) - just note it, don't remove
    (re.compile(r"\bU/?T/?A\b", re.IGNORECASE), "U/T/A"),
]


def extract_address_annotations(text: str) -> tuple[str, list[str]]:
    """
    Extract annotations from address text and return cleaned text with notes.

    Extracts:
    - c/o (care of) references
    - Trust dates (dated, U/T/A, established)
    - Note references (Note (6))
    - FD and QCMD references
    - Lease references
    - Relationship annotations (daugh., son, step daughter)

    Args:
        text: Raw address/text that may contain annotations

    Returns:
        Tuple of (cleaned_text, list_of_notes)
    """
    if not text:
        return text, []

    notes = []
    cleaned = text

    # First, extract annotations that should be removed from text
    for pattern, note_type in ANNOTATION_PATTERNS:
        matches = pattern.findall(cleaned)
        for match in matches:
            if note_type == "c/o":
                notes.append(f"c/o {match.strip()}")
            elif note_type == "Note":
                notes.append(f"Note ({match})")
            elif note_type == "FD":
                notes.append(f"FD: {match.strip()}")
            elif note_type == "QCMD":
                notes.append(f"QCMD: {match.strip()}")
            elif note_type == "Lease":
                notes.append(f"Lease {match.strip()}")
            elif note_type == "relationship":
                notes.append(match.strip())
            elif note_type == "established":
                notes.append(f"established {match.strip()}")
            elif note_type == "marker":
                # Don't add markers to notes, just remove them
                pass

        # Remove the matched pattern from the cleaned text
        cleaned = pattern.sub("", cleaned)

    # Then, extract annotations that should NOT be removed (just noted)
    for pattern, note_type in ANNOTATION_EXTRACT_ONLY:
        matches = pattern.findall(cleaned)
        for match in matches:
            if note_type == "dated":
                notes.append(f"dated {match.strip()}")
            elif note_type == "U/T/A":
                notes.append("U/T/A")
        # Do NOT remove these patterns from the text

    # Clean up the result
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r",\s*,", ",", cleaned)
    cleaned = re.sub(r"^\s*,\s*", "", cleaned)
    cleaned = re.sub(r"\s*,\s*$", "", cleaned)
    cleaned = cleaned.strip()

    return cleaned, notes


def parse_address_with_notes(address_text: str) -> AddressWithNotes:
    """
    Parse an address string, extracting annotations to notes.

    Args:
        address_text: Raw address text (may contain annotations)

    Returns:
        AddressWithNotes with address components and extracted notes
    """
    if not address_text or not address_text.strip():
        return AddressWithNotes()

    # First extract annotations
    cleaned_text, notes = extract_address_annotations(address_text)

    # Then parse the cleaned address
    parsed = parse_address(cleaned_text)

    return AddressWithNotes(
        street=parsed["street"],
        city=parsed["city"],
        state=parsed["state"],
        zip_code=parsed["zip"],
        notes=notes,
    )


def parse_address(address_text: str) -> dict[str, Optional[str]]:
    """
    Parse an address string into structured components.

    Handles:
    - Standard formats: "123 Main St, City, ST 12345"
    - Multi-line addresses
    - PO Box addresses
    - Apartment/suite/unit numbers
    - ZIP and ZIP+4 formats

    Args:
        address_text: Raw address text (may be multi-line)

    Returns:
        Dictionary with keys: street, city, state, zip
    """
    result: dict[str, Optional[str]] = {
        "street": None,
        "city": None,
        "state": None,
        "zip": None,
    }

    if not address_text or not address_text.strip():
        return result

    # Normalize the address text
    text = _normalize_address_text(address_text)

    # Try to extract ZIP code first (most reliable anchor)
    zip_match = _extract_zip(text)
    if zip_match:
        result["zip"] = zip_match["zip"]
        text_before_zip = zip_match["text_before"]

        # Extract state (should be right before ZIP)
        state_result = _extract_state(text_before_zip)
        if state_result:
            result["state"] = state_result["state"]
            text_before_state = state_result["text_before"]

            # Extract city and street from remaining text
            city_street = _extract_city_and_street(text_before_state)
            result["city"] = city_street["city"]
            result["street"] = city_street["street"]
        else:
            # No state found, try to parse city and street anyway
            city_street = _extract_city_and_street(text_before_zip)
            result["city"] = city_street["city"]
            result["street"] = city_street["street"]
    else:
        # No ZIP found, try alternative parsing
        result = _parse_without_zip(text)

    # Clean up results
    result = _clean_result(result)

    return result


def _normalize_address_text(text: str) -> str:
    """Normalize address text by handling line breaks and extra whitespace."""
    # Replace various line breaks and multiple spaces
    text = re.sub(r"[\r\n]+", ", ", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r",\s*,", ",", text)
    text = text.strip()
    return text


def _extract_zip(text: str) -> Optional[dict]:
    """Extract ZIP code and return it with the text before it."""
    # Find ZIP code at END of address (most reliable)
    end_zip_pattern = re.compile(r"\b(\d{5})(?:-(\d{4}))?\s*$")
    match = end_zip_pattern.search(text)

    if not match:
        # Try to find ZIP preceded by a state abbreviation
        state_zip_pattern = re.compile(
            r"[,\s]+[A-Z]{2}[.,]?\s+(\d{5})(?:-(\d{4}))?(?:\s*$|[,\s])"
        )
        match = state_zip_pattern.search(text.upper())
        if match:
            # Find the actual position in original text
            zip_val = match.group(1)
            # Search for this ZIP in original text
            actual_pattern = re.compile(r"\b(" + zip_val + r")(?:-(\d{4}))?\b")
            all_matches = list(actual_pattern.finditer(text))
            if all_matches:
                match = all_matches[-1]  # Use the last occurrence

    if match:
        zip5 = match.group(1)
        zip4 = match.group(2) if len(match.groups()) > 1 else None
        zip_code = f"{zip5}-{zip4}" if zip4 else zip5

        return {
            "zip": zip_code,
            "text_before": text[: match.start()].strip().rstrip(",").strip(),
        }
    return None


def _extract_state(text: str) -> Optional[dict]:
    """Extract state abbreviation from the end of text."""
    text = text.strip().rstrip(",").strip()

    # Pattern: ends with 2-letter state code
    state_pattern = re.compile(r"[,\s]+([A-Za-z]{2})\.?\s*$")
    match = state_pattern.search(text)

    if match:
        potential_state = match.group(1).upper()
        if potential_state in US_STATES:
            return {
                "state": potential_state,
                "text_before": text[: match.start()].strip(),
            }

    # Try without comma/space requirement
    if len(text) >= 2:
        last_two = text[-2:].upper()
        if last_two in US_STATES:
            # Make sure it's not part of a word
            if len(text) == 2 or not text[-3].isalpha():
                return {
                    "state": last_two,
                    "text_before": text[:-2].strip().rstrip(",").strip(),
                }

    return None


def _extract_city_and_street(text: str) -> dict[str, Optional[str]]:
    """Extract city and street from remaining address text."""
    result: dict[str, Optional[str]] = {"city": None, "street": None}

    if not text:
        return result

    text = text.strip().rstrip(",").strip()

    # Split by comma
    parts = [p.strip() for p in text.split(",") if p.strip()]

    if len(parts) >= 2:
        # Last part is likely city, rest is street
        result["city"] = parts[-1]
        result["street"] = ", ".join(parts[:-1])
    elif len(parts) == 1:
        # Try to separate city from street by looking for patterns
        single_part = parts[0]

        # Check if it looks like just a city (no numbers at start)
        if not re.match(r"^\d", single_part) and not PO_BOX_PATTERN.match(single_part):
            # Likely just a city name
            result["city"] = single_part
        else:
            # Likely a street address, city might be missing
            result["street"] = single_part

    return result


def _parse_without_zip(text: str) -> dict[str, Optional[str]]:
    """Parse address when no ZIP code is found."""
    result: dict[str, Optional[str]] = {
        "street": None,
        "city": None,
        "state": None,
        "zip": None,
    }

    # Split by comma and analyze parts
    parts = [p.strip() for p in text.split(",") if p.strip()]

    if not parts:
        return result

    # Look for state abbreviation in any part
    for i, part in enumerate(parts):
        words = part.split()
        for j, word in enumerate(words):
            clean_word = word.strip(".,").upper()
            if clean_word in US_STATES:
                result["state"] = clean_word
                # City might be before state in same part
                if j > 0:
                    result["city"] = " ".join(words[:j])
                elif i > 0:
                    result["city"] = parts[i - 1]
                # Street is everything before city
                if i > 1:
                    result["street"] = ", ".join(parts[: i - 1])
                elif i == 1 and result["city"] is None:
                    result["street"] = parts[0]
                return result

    # No state found, make best guess
    if len(parts) >= 2:
        result["street"] = ", ".join(parts[:-1])
        result["city"] = parts[-1]
    else:
        result["street"] = parts[0]

    return result


def _clean_result(result: dict[str, Optional[str]]) -> dict[str, Optional[str]]:
    """Clean up parsed address components."""
    for key in result:
        if result[key]:
            # Strip whitespace and trailing punctuation
            value = result[key].strip().rstrip(".,").strip()
            # Remove multiple spaces
            value = re.sub(r"\s+", " ", value)
            result[key] = value if value else None

    # Validate state
    if result["state"]:
        normalized = normalize_state(result["state"])
        result["state"] = normalized

    # Validate ZIP
    if result["zip"] and not validate_zip(result["zip"]):
        # Try to fix common issues
        zip_clean = re.sub(r"[^\d-]", "", result["zip"])
        if validate_zip(zip_clean):
            result["zip"] = zip_clean

    return result


def format_full_address(
    street: Optional[str],
    city: Optional[str],
    state: Optional[str],
    zip_code: Optional[str],
) -> str:
    """Format address components into a single-line address string."""
    parts = []

    if street:
        parts.append(street)
    if city:
        parts.append(city)
    if state and zip_code:
        parts.append(f"{state} {zip_code}")
    elif state:
        parts.append(state)
    elif zip_code:
        parts.append(zip_code)

    return ", ".join(parts)


def is_po_box(street: Optional[str]) -> bool:
    """Check if the street address is a PO Box."""
    if not street:
        return False
    return bool(PO_BOX_PATTERN.search(street))


def has_apartment(street: Optional[str]) -> bool:
    """Check if the street address contains an apartment/suite/unit."""
    if not street:
        return False
    return bool(APT_SUITE_PATTERN.search(street))

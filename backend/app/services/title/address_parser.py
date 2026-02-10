"""Address parsing service for title documents.

Core address parsing is delegated to the shared address parser.
This module adds title-specific annotation extraction on top of
the shared logic (c/o, trust dates, notes, lease references, etc.).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from app.services.shared.address_parser import (
    format_full_address,
    has_apartment,
    is_po_box,
    parse_address,
    split_address_lines,
)

__all__ = [
    "AddressWithNotes",
    "extract_address_annotations",
    "format_full_address",
    "has_apartment",
    "is_po_box",
    "parse_address",
    "parse_address_with_notes",
    "split_address_lines",
]


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
    (re.compile(r"\bc/?o\s+([^,\n\d]+?)(?=\s*(?:,|\d|$))", re.IGNORECASE), "c/o"),
    (re.compile(r"\bNote\s*\((\d+)\)", re.IGNORECASE), "Note"),
    (re.compile(r"\bFD:\s*([^\n,]+)", re.IGNORECASE), "FD"),
    (re.compile(r"\bQCMD:\s*([^\n,]+)", re.IGNORECASE), "QCMD"),
    (re.compile(r"-?\s*Lease\s+(\d+(?:\s*[-&]\s*\d+)?)", re.IGNORECASE), "Lease"),
    (re.compile(r",?\s*\b(step\s*(?:daughter|son|mother|father))\b", re.IGNORECASE), "relationship"),
    (re.compile(r",?\s*-?\s*\b(daugh(?:ter)?\.?)", re.IGNORECASE), "relationship"),
    (re.compile(r",?\s*\b(son)\b(?!\s+of)", re.IGNORECASE), "relationship"),
    (re.compile(r",\s*(step)\s*$", re.IGNORECASE), "relationship"),
    (re.compile(r",?\s*\bnow\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)", re.IGNORECASE), "now"),
    (re.compile(r",?\s*\bformerly\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)", re.IGNORECASE), "formerly"),
    (re.compile(r"\bEstablished\s+([A-Z][a-z]+\s+\d{1,2},?\s+\d{4})", re.IGNORECASE), "established"),
    (re.compile(r"\bBENEFICIARY\b", re.IGNORECASE), "marker"),
    (re.compile(r"\bPossible\s+Apparent\s+Heirs:?\s*", re.IGNORECASE), "marker"),
]

# Patterns to extract as notes but NOT remove from text
ANNOTATION_EXTRACT_ONLY = [
    (re.compile(r"\b(?:dated|dtd\.?)\s+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", re.IGNORECASE), "dated"),
    (re.compile(r"\b(?:dated|dtd\.?)\s+([A-Z][a-z]+\s+\d{1,2},?\s+\d{4})", re.IGNORECASE), "dated"),
    (re.compile(r"\bU/?T/?A\b", re.IGNORECASE), "U/T/A"),
]

_NOTE_FORMATTERS = {
    "c/o": lambda m: f"c/o {m.strip()}",
    "Note": lambda m: f"Note ({m})",
    "FD": lambda m: f"FD: {m.strip()}",
    "QCMD": lambda m: f"QCMD: {m.strip()}",
    "Lease": lambda m: f"Lease {m.strip()}",
    "relationship": lambda m: m.strip(),
    "now": lambda m: f"now {m.strip()}",
    "formerly": lambda m: f"formerly {m.strip()}",
    "established": lambda m: f"established {m.strip()}",
}

_EXTRACT_ONLY_FORMATTERS = {
    "dated": lambda m: f"dated {m.strip()}",
    "U/T/A": lambda _m: "U/T/A",
}


def extract_address_annotations(text: str) -> tuple[str, list[str]]:
    """Extract annotations from address text and return cleaned text with notes."""
    if not text:
        return text, []

    notes: list[str] = []
    cleaned = text

    for pattern, note_type in ANNOTATION_PATTERNS:
        matches = pattern.findall(cleaned)
        formatter = _NOTE_FORMATTERS.get(note_type)
        if formatter:
            for match in matches:
                notes.append(formatter(match))
        cleaned = pattern.sub("", cleaned)

    for pattern, note_type in ANNOTATION_EXTRACT_ONLY:
        matches = pattern.findall(cleaned)
        formatter = _EXTRACT_ONLY_FORMATTERS.get(note_type)
        if formatter:
            for match in matches:
                notes.append(formatter(match))

    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r",\s*,", ",", cleaned)
    cleaned = re.sub(r"^\s*,\s*", "", cleaned)
    cleaned = re.sub(r"\s*,\s*$", "", cleaned)
    cleaned = cleaned.strip()

    return cleaned, notes


def parse_address_with_notes(address_text: str) -> AddressWithNotes:
    """Parse an address string, extracting annotations to notes."""
    if not address_text or not address_text.strip():
        return AddressWithNotes()

    cleaned_text, notes = extract_address_annotations(address_text)
    parsed = parse_address(cleaned_text)

    return AddressWithNotes(
        street=parsed["street"],
        city=parsed["city"],
        state=parsed["state"],
        zip_code=parsed["zip"],
        notes=notes,
    )

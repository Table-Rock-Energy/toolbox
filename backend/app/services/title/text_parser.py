"""Text parsing service for extracting owner information from raw text entries."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from app.utils.patterns import (
    AKA_PATTERN,
    CO_PATTERN,
    FD_PATTERN,
    FKA_PATTERN,
    LEASE_PATTERN,
    NOTE_PATTERN,
    clean_text,
)


@dataclass
class ParsedEntry:
    """Parsed text entry components."""

    name: str
    address_text: Optional[str]
    notes: Optional[str]


def parse_text_entry(raw_text: str) -> ParsedEntry:
    """
    Parse a raw text entry into name, address, and notes components.

    Handles newline-delimited entries like:
        JOHN SMITH
        123 MAIN ST
        OKLAHOMA CITY, OK 73156

    Or single-line entries like:
        JOHN SMITH, 123 MAIN ST, OKLAHOMA CITY, OK 73156

    Args:
        raw_text: Raw text entry (may be multi-line)

    Returns:
        ParsedEntry with name, address_text, and notes
    """
    if not raw_text or not raw_text.strip():
        return ParsedEntry("", None, None)

    # Clean OCR artifacts
    text = clean_text(raw_text)

    # Extract notes first (FD:, Note:, etc.)
    notes = _extract_notes(text)

    # Remove notes from text
    text = _remove_notes(text)

    # Split into lines
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    if not lines:
        return ParsedEntry("", None, notes)

    if len(lines) == 1:
        # Single line - try to split by comma
        return _parse_single_line(lines[0], notes)

    # Multiple lines - first line is usually name
    name = _extract_name(lines[0])
    address_lines = lines[1:]

    # Join address lines
    address_text = ", ".join(address_lines) if address_lines else None

    return ParsedEntry(name, address_text, notes)


def _extract_notes(text: str) -> Optional[str]:
    """Extract notes from text (FD:, Note:, a/k/a, f/k/a, c/o, Lease refs)."""
    notes_parts = []

    # Extract FD: notes
    fd_matches = FD_PATTERN.findall(text)
    for match in fd_matches:
        notes_parts.append(f"FD: {match.strip()}")

    # Extract Note: notes
    note_matches = NOTE_PATTERN.findall(text)
    for match in note_matches:
        notes_parts.append(f"Note: {match.strip()}")

    # Extract a/k/a
    aka_matches = AKA_PATTERN.findall(text)
    for match in aka_matches:
        notes_parts.append(f"a/k/a {match.strip()}")

    # Extract f/k/a
    fka_matches = FKA_PATTERN.findall(text)
    for match in fka_matches:
        notes_parts.append(f"f/k/a {match.strip()}")

    # Extract c/o
    co_matches = CO_PATTERN.findall(text)
    for match in co_matches:
        notes_parts.append(f"c/o {match.strip()}")

    # Extract lease/reference numbers
    lease_matches = LEASE_PATTERN.findall(text)
    for match in lease_matches:
        notes_parts.append(f"Ref: {match.strip()}")

    return "; ".join(notes_parts) if notes_parts else None


def _remove_notes(text: str) -> str:
    """Remove note patterns from text while preserving line structure."""
    # Remove FD: lines
    text = FD_PATTERN.sub("", text)

    # Remove Note: content
    text = NOTE_PATTERN.sub("", text)

    # Remove a/k/a and everything after on the same logical unit
    text = re.sub(r"\s+a/?k/?a\s+[^\n,]+", "", text, flags=re.IGNORECASE)

    # Remove f/k/a
    text = re.sub(r"\s+f/?k/?a\s+[^\n,]+", "", text, flags=re.IGNORECASE)

    # Remove c/o (but keep address that follows)
    text = re.sub(r"\s+c/?o\s+[^,\n]+,?", "", text, flags=re.IGNORECASE)

    # Remove lease references
    text = LEASE_PATTERN.sub("", text)

    # Clean up extra horizontal whitespace (preserve newlines)
    text = re.sub(r"[^\S\n]+", " ", text)
    text = re.sub(r",\s*,", ",", text)
    # Clean up empty lines
    text = re.sub(r"\n\s*\n", "\n", text)
    text = text.strip()

    return text


def _extract_name(line: str) -> str:
    """Extract name from the first line, removing any trailing address indicators."""
    name = line.strip()

    # Remove any trailing numbers that look like addresses
    name = re.sub(r",?\s+\d+\s+[A-Z].*$", "", name, flags=re.IGNORECASE)

    # Remove PO Box patterns from name
    name = re.sub(r",?\s+P\.?O\.?\s*Box.*$", "", name, flags=re.IGNORECASE)

    # Clean up
    name = name.strip().rstrip(",").strip()

    return name


def _parse_single_line(line: str, notes: Optional[str]) -> ParsedEntry:
    """Parse a single line entry that may contain name and address."""
    # Look for patterns that indicate address starts
    # Common patterns: after comma + number, after comma + PO Box

    # Try to find where address starts
    address_start_patterns = [
        # Street number after comma
        re.compile(r",\s+(\d+\s+[A-Z].*)$", re.IGNORECASE),
        # PO Box after comma
        re.compile(r",\s+(P\.?O\.?\s*Box.*)$", re.IGNORECASE),
    ]

    for pattern in address_start_patterns:
        match = pattern.search(line)
        if match:
            name = line[: match.start()].strip()
            address_text = match.group(1).strip()
            return ParsedEntry(name, address_text, notes)

    # If no address pattern found, check if it looks like just a name
    # Names typically don't have 5+ digit numbers (ZIP codes)
    if not re.search(r"\d{5}", line):
        return ParsedEntry(line.strip(), None, notes)

    # Has ZIP-like number, try comma split
    parts = line.split(",")
    if len(parts) >= 2:
        name = parts[0].strip()
        address_text = ", ".join(parts[1:]).strip()
        return ParsedEntry(name, address_text, notes)

    # Can't determine, return as name only
    return ParsedEntry(line.strip(), None, notes)


def split_cell_entries(cell_value: str) -> list[str]:
    """
    Split a cell that may contain multiple entries separated by newlines.

    Some Excel cells have multiple owners packed into one cell with newlines.

    Args:
        cell_value: Raw cell value

    Returns:
        List of individual entry strings
    """
    if not cell_value:
        return []

    # Split by double newlines (entry separator)
    entries = re.split(r"\n\s*\n", cell_value)

    # Clean each entry
    entries = [e.strip() for e in entries if e.strip()]

    return entries

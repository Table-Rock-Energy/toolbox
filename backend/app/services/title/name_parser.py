"""Name parsing service for title tool."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from app.models.title import EntityType
from app.utils.patterns import NAME_SUFFIXES


@dataclass
class ParsedName:
    """Parsed name components."""

    first_name: str
    middle_name: str
    last_name: str
    suffix: str


def parse_individual_name(name: str) -> ParsedName:
    """
    Parse an individual's name into first, middle, and last name components.

    Args:
        name: Full name string

    Returns:
        ParsedName with components
    """
    if not name or not name.strip():
        return ParsedName("", "", "", "")

    # Clean up the name first
    name = name.strip()

    # Remove trailing dashes and clean punctuation
    name = re.sub(r"\s*-\s*$", "", name)
    name = re.sub(r"^-\s*", "", name)

    # Remove W/H and JTWROS markers
    name = re.sub(r"^W/?H\s+", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s+W/?H$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s+JTWROS\b", "", name, flags=re.IGNORECASE)

    # Remove common prefixes (Mr., Mrs., etc.)
    name = re.sub(r"^(?:Mr\.?|Mrs\.?|Ms\.?|Dr\.?|Miss)\s+", "", name, flags=re.IGNORECASE)

    # Handle joint owners ("John Smith and Jane Smith") - take first person
    if " and " in name.lower():
        name = re.split(r"\s+and\s+", name, flags=re.IGNORECASE)[0].strip()

    # Also handle "&" for joint owners
    if " & " in name:
        name = name.split(" & ")[0].strip()

    # Extract and remove suffix
    suffix = ""
    words = name.split()
    if words:
        last_word_upper = words[-1].upper().rstrip(".,")
        if last_word_upper in NAME_SUFFIXES or last_word_upper.rstrip(".") in NAME_SUFFIXES:
            suffix = words[-1]
            words = words[:-1]
            name = " ".join(words)

    # Check for "Last, First Middle" format
    if "," in name:
        parts = name.split(",", 1)
        if len(parts) == 2:
            last_name = parts[0].strip()
            rest = parts[1].strip()
            rest_parts = rest.split()
            if rest_parts:
                first_name = rest_parts[0]
                middle_name = " ".join(rest_parts[1:]) if len(rest_parts) > 1 else ""
                return ParsedName(first_name, middle_name, last_name, suffix)

    # Standard "First Middle Last" format
    words = name.split()

    if len(words) == 0:
        return ParsedName("", "", "", "")

    if len(words) == 1:
        # Just one name - for ownership records, assume it's a LAST name
        return ParsedName("", "", words[0], suffix)

    if len(words) == 2:
        # Two words: First Last
        return ParsedName(words[0], "", words[1], suffix)

    # Three or more words: First Middle(s) Last
    first_name = words[0]
    last_name = words[-1]
    middle_parts = words[1:-1]
    middle_name = " ".join(middle_parts)

    return ParsedName(first_name, middle_name, last_name, suffix)


def parse_name(name: str, entity_type: EntityType) -> tuple[Optional[str], Optional[str]]:
    """
    Parse a name based on entity type.

    Only parses first/last for INDIVIDUAL entities.

    Args:
        name: Full name string
        entity_type: The detected entity type

    Returns:
        Tuple of (first_name, last_name) - both None for non-individuals
    """
    if entity_type != EntityType.INDIVIDUAL:
        return None, None

    parsed = parse_individual_name(name)

    # Combine middle name with first name if present
    first_name = parsed.first_name
    if parsed.middle_name:
        first_name = f"{parsed.first_name} {parsed.middle_name}"

    # Add suffix to last name if present
    last_name = parsed.last_name
    if parsed.suffix:
        last_name = f"{parsed.last_name} {parsed.suffix}"

    return first_name or None, last_name or None


def clean_name(name: str) -> str:
    """
    Clean a name by removing annotations and extra whitespace.

    Args:
        name: Name that may contain annotations

    Returns:
        Cleaned name
    """
    if not name:
        return name

    cleaned = name

    # Remove a/k/a and everything after
    cleaned = re.sub(r"\s+a/?k/?a\s+.*$", "", cleaned, flags=re.IGNORECASE)

    # Remove f/k/a and everything after
    cleaned = re.sub(r"\s+f/?k/?a\s+.*$", "", cleaned, flags=re.IGNORECASE)

    # Remove c/o and everything after (at end of name)
    cleaned = re.sub(r"\s+c/?o\s+.*$", "", cleaned, flags=re.IGNORECASE)

    # Remove Trustee designations at end
    cleaned = re.sub(
        r",?\s+(?:as\s+)?(?:Successor\s+)?Trustee(?:s)?(?:\s+of\s+.*)?$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    # Remove W/H (wife/husband) marker at start or end
    cleaned = re.sub(r"^W/?H\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+W/?H$", "", cleaned, flags=re.IGNORECASE)

    # Remove JTWROS (joint tenants with right of survivorship) marker
    cleaned = re.sub(r"\s+JTWROS\b", "", cleaned, flags=re.IGNORECASE)

    # Clean up trailing dashes (often leftover from relationship markers)
    cleaned = re.sub(r"\s*-\s*$", "", cleaned)
    cleaned = re.sub(r"^-\s*", "", cleaned)

    # Clean up extra whitespace and trailing punctuation
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = cleaned.rstrip(",-").strip()

    return cleaned

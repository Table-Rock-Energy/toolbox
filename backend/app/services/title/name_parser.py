"""Name parsing service for title tool."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from app.models.title import EntityType
from app.utils.patterns import LEGAL_DESCRIPTION_PATTERN, NAME_SUFFIXES


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


def parse_name(name: str, entity_type: EntityType) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Parse a name based on entity type.

    Only parses first/last/middle for INDIVIDUAL entities.

    Args:
        name: Full name string
        entity_type: The detected entity type

    Returns:
        Tuple of (first_name, middle_name, last_name) - all None for non-individuals
    """
    if entity_type != EntityType.INDIVIDUAL:
        return None, None, None

    parsed = parse_individual_name(name)

    first_name = parsed.first_name or None
    middle_name = parsed.middle_name or None

    # Add suffix to last name if present
    last_name = parsed.last_name
    if parsed.suffix:
        last_name = f"{parsed.last_name} {parsed.suffix}"

    return first_name, middle_name, last_name or None


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

    # Strip "as Guardian of ..." before general comma handling
    cleaned = re.sub(r",\s+as\s+Guardian\s+(?:of|for)\s+.*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r",\s+incompetent\b.*$", "", cleaned, flags=re.IGNORECASE)

    # Strip "now [Name]" (married name change) before comma parsing
    cleaned = re.sub(r",?\s+now\s+\w+(?:\s+\w+)?$", "", cleaned, flags=re.IGNORECASE)

    # Strip "formerly [Name]"
    cleaned = re.sub(r",?\s+formerly\s+\w+(?:\s+\w+)?$", "", cleaned, flags=re.IGNORECASE)

    # Strip "record owner"
    cleaned = re.sub(r",?\s+record\s+owner\b.*$", "", cleaned, flags=re.IGNORECASE)

    # Strip "a widow" / "widow"
    cleaned = re.sub(r",?\s+(?:a\s+)?widow\b", "", cleaned, flags=re.IGNORECASE)

    # Strip parenthetical spouse markers like "(Mae Henslee/wife)"
    cleaned = re.sub(r"\s*\([^)]*?/(?:wife|husband|hus)\)", "", cleaned, flags=re.IGNORECASE)

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

    # Remove HWJT (husband wife joint tenants) and variants
    cleaned = re.sub(r",?\s+HWJT\b", "", cleaned, flags=re.IGNORECASE)

    # Remove JTRS (joint tenants with rights of survivorship)
    cleaned = re.sub(r",?\s+JTRS\b", "", cleaned, flags=re.IGNORECASE)

    # Remove "both apparently deceased" and similar death annotations
    cleaned = re.sub(r",?\s+both\s+(?:apparently\s+)?deceased\b.*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r",?\s+(?:apparently\s+)?deceased\b", "", cleaned, flags=re.IGNORECASE)

    # Remove LKA: (Last Known Address) and everything after
    cleaned = re.sub(r",?\s+LKA\s*:.*$", "", cleaned, flags=re.IGNORECASE)

    # Remove "n/k/a" (now known as) and everything after
    cleaned = re.sub(r"\s+n/?k/?a\s+.*$", "", cleaned, flags=re.IGNORECASE)

    # Clean up trailing dashes (often leftover from relationship markers)
    cleaned = re.sub(r"\s*-\s*$", "", cleaned)
    cleaned = re.sub(r"^-\s*", "", cleaned)

    # Clean up extra whitespace and trailing punctuation
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = cleaned.rstrip(",-").strip()

    return cleaned


# Patterns that should be extracted from names into notes
_LEGAL_ANNOTATION_PATTERNS = [
    (re.compile(r",?\s+(HWJT)\b", re.IGNORECASE), "HWJT"),
    (re.compile(r",?\s+(JTRS)\b", re.IGNORECASE), "JTRS"),
    (re.compile(r",?\s+(JTWROS)\b", re.IGNORECASE), "JTWROS"),
    (re.compile(r",?\s+(both\s+(?:apparently\s+)?deceased\b.*?)(?:,|$)", re.IGNORECASE), None),
    (re.compile(r",?\s+((?:apparently\s+)?deceased)\b", re.IGNORECASE), None),
    (re.compile(r",?\s+(LKA\s*:.*)$", re.IGNORECASE), None),
]


def extract_legal_annotations(name: str) -> tuple[str, list[str]]:
    """Extract legal annotations from name, returning (cleaned_name, annotations).

    Annotations like HWJT, JTRS, LKA:, deceased are stripped from the name
    and returned as a list for merging into the notes field.
    """
    if not name:
        return name, []

    annotations: list[str] = []
    cleaned = name

    for pattern, label in _LEGAL_ANNOTATION_PATTERNS:
        match = pattern.search(cleaned)
        if match:
            annotations.append(label or match.group(1).strip())
            cleaned = pattern.sub("", cleaned)

    cleaned = re.sub(r"\s+", " ", cleaned).strip().rstrip(",-").strip()
    return cleaned, annotations


def is_valid_name(name: str) -> bool:
    """
    Check if a string is a valid name (not a legal description or junk data).

    Args:
        name: String to validate

    Returns:
        True if it looks like a valid name
    """
    if not name or not name.strip():
        return False

    cleaned = name.strip()

    # Check if it looks like a legal description (e.g., "2-6N-4W")
    if LEGAL_DESCRIPTION_PATTERN.match(cleaned):
        return False

    # Check if it's just numbers/dashes
    if re.match(r"^[\d\s\-]+$", cleaned):
        return False

    # Check if it starts with common non-name indicators
    non_name_prefixes = [
        "apparent successors",
        "unknown heirs",
        "and assigns",
        "successors and",
    ]
    cleaned_lower = cleaned.lower()
    for prefix in non_name_prefixes:
        if cleaned_lower.startswith(prefix):
            return False

    # Must have at least one letter
    if not re.search(r"[a-zA-Z]", cleaned):
        return False

    return True

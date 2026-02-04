"""Name parsing service for splitting names into first/middle/last components."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ParsedName:
    """Parsed name components."""
    first_name: str
    middle_name: str
    last_name: str
    suffix: str
    is_person: bool  # True if detected as a person's name


# Common name suffixes
SUFFIXES = {
    "JR", "JR.", "SR", "SR.", "II", "III", "IV", "V",
    "MD", "M.D.", "PHD", "PH.D.", "ESQ", "ESQ.",
}

# Business indicators - if name contains these, it's likely a business
BUSINESS_INDICATORS = [
    r"\bLLC\b",
    r"\bL\.L\.C\.\b",
    r"\bINC\b",
    r"\bINC\.\b",
    r"\bCORP\b",
    r"\bCORP\.\b",
    r"\bCORPORATION\b",
    r"\bCOMPANY\b",
    r"\bCO\.\b",
    r"\bLTD\b",
    r"\bLTD\.\b",
    r"\bLIMITED\b",
    r"\bLP\b",
    r"\bL\.P\.\b",
    r"\bLLP\b",
    r"\bL\.L\.P\.\b",
    r"\bPARTNERSHIP\b",
    r"\bPARTNERS\b",
    r"\bTRUST\b",
    r"\bTRUSTEE\b",
    r"\bESTATE\b",
    r"\bFOUNDATION\b",
    r"\bASSOCIATION\b",
    r"\bSOCIETY\b",
    r"\bCHURCH\b",
    r"\bMINISTRIES\b",
    r"\bUNIVERSITY\b",
    r"\bCOLLEGE\b",
    r"\bSCHOOL\b",
    r"\bHOSPITAL\b",
    r"\bCLINIC\b",
    r"\bGROUP\b",
    r"\bHOLDINGS\b",
    r"\bENTERPRISES\b",
    r"\bVENTURES\b",
    r"\bINVESTMENTS\b",
    r"\bPROPERTIES\b",
    r"\bREALTY\b",
    r"\bRESOURCES\b",
    r"\bENERGY\b",
    r"\bOIL\b",
    r"\bGAS\b",
    r"\bPETROLEUM\b",
    r"\bMINERALS\b",
    r"\bROYALTY\b",
    r"\bBUREAU\b",
    r"\bDEPARTMENT\b",
    r"\bCOMMISSION\b",
    r"\bCOUNTY\b",
    r"\bSTATE OF\b",
    r"\bCITY OF\b",
    r"\bUNKNOWN HEIRS\b",
    r"\bHEIRS AND ASSIGNS\b",
    r"\bHEIRS OF\b",
    r"\bSUCCESSORS\b",
    r"\bRED CROSS\b",
    r"\bGP\b",  # General Partner
    r"\bCAPITAL\b",
    r"\bFUND\b",
    r"\bBANK\b",
    r"\bSERVICES\b",
    r"\bSOLUTIONS\b",
    r"\bSYSTEMS\b",
    r"\bTECHNOLOGIES\b",
    r"\bINDUSTRIES\b",
    r"\bPRODUCTION\b",
    r"\bPRODUCTIONS\b",
    r"\bCONSULTING\b",
    r"\bMANAGEMENT\b",
    r"\bDEVELOPMENT\b",
]

# Compile business indicator patterns
BUSINESS_PATTERNS = [re.compile(p, re.IGNORECASE) for p in BUSINESS_INDICATORS]

# Common first name prefixes that indicate a person
PERSON_PREFIXES = {"MR", "MR.", "MRS", "MRS.", "MS", "MS.", "DR", "DR.", "MISS"}

# Pattern for middle initial (single letter, possibly with period)
MIDDLE_INITIAL_PATTERN = re.compile(r"^[A-Z]\.?$", re.IGNORECASE)


def is_business_name(name: str) -> bool:
    """
    Check if a name appears to be a business/organization rather than a person.

    Args:
        name: The name to check

    Returns:
        True if the name appears to be a business
    """
    if not name:
        return False

    # Check for business indicators
    for pattern in BUSINESS_PATTERNS:
        if pattern.search(name):
            return True

    # Note: We do NOT flag "&" or "and" names as businesses here
    # Those will be split into separate person names by split_multiple_names()

    # Check for all-caps acronym-style names (likely business)
    # But exclude short names that might be initials
    words = name.split()
    if len(words) == 1 and len(name) > 4 and name.isupper():
        return True

    return False


def parse_person_name(name: str) -> ParsedName:
    """
    Parse a person's name into first, middle, and last name components.

    Handles formats like:
    - "John Smith"
    - "John A. Smith"
    - "John Adam Smith"
    - "John A Smith Jr."
    - "Smith, John A."

    Args:
        name: Full name string

    Returns:
        ParsedName with components
    """
    if not name or not name.strip():
        return ParsedName("", "", "", "", False)

    # Check if it's a business name
    if is_business_name(name):
        return ParsedName("", "", "", "", False)

    # Clean up the name
    name = name.strip()

    # Remove common prefixes (Mr., Mrs., etc.)
    name_upper = name.upper()
    for prefix in PERSON_PREFIXES:
        if name_upper.startswith(prefix + " "):
            name = name[len(prefix):].strip()
            break

    # Extract and remove suffix
    suffix = ""
    words = name.split()
    if words:
        last_word_upper = words[-1].upper().rstrip(".,")
        if last_word_upper in SUFFIXES or last_word_upper.rstrip(".") in SUFFIXES:
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
                return ParsedName(first_name, middle_name, last_name, suffix, True)

    # Standard "First Middle Last" format
    words = name.split()

    if len(words) == 0:
        return ParsedName("", "", "", "", False)

    if len(words) == 1:
        # Just one name - assume it's a first name or could be last name
        # For safety, put it in first name
        return ParsedName(words[0], "", "", suffix, True)

    if len(words) == 2:
        # Two words: First Last
        return ParsedName(words[0], "", words[1], suffix, True)

    # Three or more words
    first_name = words[0]
    last_name = words[-1]
    middle_parts = words[1:-1]

    # Join middle parts
    middle_name = " ".join(middle_parts)

    return ParsedName(first_name, middle_name, last_name, suffix, True)


def parse_name(name: str, entity_type: str) -> ParsedName:
    """
    Parse a name, only splitting if it's an Individual.

    Args:
        name: Full name string
        entity_type: The entity type (Individual, LLC, Corporation, etc.)

    Returns:
        ParsedName with components (empty for non-individuals)
    """
    # Only parse names for Individuals
    if entity_type != "Individual":
        return ParsedName("", "", "", "", False)

    return parse_person_name(name)


def split_multiple_names(name: str) -> list[str]:
    """
    Split a name containing multiple people into separate names.

    Handles formats like:
    - "John Smith & Jane Smith"
    - "John and Jane Smith"
    - "Carl Leon Webb & Elizabeth Jean Webb"

    Does NOT split on:
    - "heirs and assigns"
    - "heirs and devisees"
    - "successors and assigns"
    - Other legal phrases

    Args:
        name: Name string that may contain multiple people

    Returns:
        List of individual names
    """
    if not name:
        return [name]

    # Phrases that should NOT be split (legal terms, not multiple people)
    no_split_phrases = [
        r"heirs\s+and\s+assigns",
        r"heirs\s+and\s+devisees",
        r"successors\s+and\s+assigns",
        r"executors\s+and\s+administrators",
        r"husband\s+and\s+wife",
        r"oil\s+and\s+gas",
        r"individually\s+and\s+as",
        r"unknown\s+heirs\s+and",
    ]

    # Check if name contains any no-split phrases
    name_lower = name.lower()
    for phrase in no_split_phrases:
        if re.search(phrase, name_lower):
            # This name contains a legal phrase, don't split it
            return [name]

    # Check for " & " separator
    if " & " in name:
        parts = name.split(" & ")
        return _expand_shared_surname(parts)

    # Check for " and " separator (case insensitive) - only split if it looks like two names
    if " and " in name_lower:
        # Find the "and" position case-insensitively
        pos = name_lower.find(" and ")
        part1 = name[:pos].strip()
        part2 = name[pos + 5:].strip()

        # Only split if both parts look like names (have at least one word)
        # and the second part starts with a capital letter (likely a name)
        if part1 and part2 and len(part2) > 0:
            # Check if part2 starts with a capital letter (likely a name)
            if part2[0].isupper():
                parts = [part1, part2]
                return _expand_shared_surname(parts)

    return [name]


def _expand_shared_surname(parts: list[str]) -> list[str]:
    """
    Expand names that share a surname.

    E.g., ["Carl Leon Webb", "Elizabeth Jean Webb"] stays as is
    E.g., ["John", "Jane Smith"] becomes ["John Smith", "Jane Smith"]

    Args:
        parts: List of name parts

    Returns:
        List of complete names
    """
    if len(parts) < 2:
        return parts

    parts = [p.strip() for p in parts if p.strip()]
    if len(parts) < 2:
        return parts

    # Get the last part's words
    last_part_words = parts[-1].split()
    if len(last_part_words) < 2:
        return parts

    # Assume the last word of the last part is the shared surname
    shared_surname = last_part_words[-1]

    result = []
    for i, part in enumerate(parts):
        words = part.split()
        # If this part doesn't end with the shared surname and has fewer words,
        # it might need the surname added
        if i < len(parts) - 1:  # Not the last part
            if len(words) == 1 or (len(words) < len(last_part_words) and words[-1] != shared_surname):
                # Add shared surname
                result.append(f"{part} {shared_surname}")
            else:
                result.append(part)
        else:
            result.append(part)

    return result


def clean_name_for_export(name: str) -> str:
    """
    Clean a name by removing notes/annotations that should be in the notes field.

    Removes:
    - a/k/a and anything after
    - f/k/a and anything after
    - c/o and anything after (if at start or middle of name)
    - Trustee designations
    - "by [name]" patterns
    - "Individually and as" patterns
    - "his/her unknown heirs" patterns
    - "Deceased" annotations

    Args:
        name: Name that may contain annotations

    Returns:
        Cleaned name
    """
    if not name:
        return name

    cleaned = name

    # Remove a/k/a and everything after (do early)
    cleaned = re.sub(r'\s+a/?k/?a\s+.*$', '', cleaned, flags=re.IGNORECASE)

    # Remove f/k/a and everything after (do early)
    cleaned = re.sub(r'\s+f/?k/?a\s+.*$', '', cleaned, flags=re.IGNORECASE)

    # Remove ", by [name]" patterns (e.g., "John Smith, Individually and by Jane Smith, Trustee")
    # Do this BEFORE removing "Individually" patterns
    cleaned = re.sub(r',?\s+by\s+[^,]+(?:,\s*(?:Trustee|as\s+\w+))?', '', cleaned, flags=re.IGNORECASE)

    # Remove Trustee designations at end
    cleaned = re.sub(r',?\s+(?:as\s+)?(?:Successor\s+)?Trustee(?:s)?(?:\s+of\s+.*)?$', '', cleaned, flags=re.IGNORECASE)

    # Now remove "Individually and as..." patterns
    cleaned = re.sub(r',?\s*Individually\s+and\s+as\s+.*$', '', cleaned, flags=re.IGNORECASE)

    # Remove "Individually and" at end (without "as")
    cleaned = re.sub(r',?\s*Individually\s+and\s*$', '', cleaned, flags=re.IGNORECASE)

    # Remove ", Individually" at end
    cleaned = re.sub(r',?\s*Individually\s*$', '', cleaned, flags=re.IGNORECASE)

    # Remove "his/her/their unknown heirs and assigns" patterns
    cleaned = re.sub(r',?\s+(?:his|her|their)\s+unknown\s+heirs.*$', '', cleaned, flags=re.IGNORECASE)

    # Remove "unknown heirs and assigns" at end
    cleaned = re.sub(r',?\s+unknown\s+heirs.*$', '', cleaned, flags=re.IGNORECASE)

    # Remove ", Deceased" annotation but keep the name
    cleaned = re.sub(r',?\s+Deceased\s*$', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r',?\s+Deceased,', ',', cleaned, flags=re.IGNORECASE)

    # Clean up extra whitespace and trailing punctuation
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    cleaned = cleaned.rstrip(',').strip()

    return cleaned

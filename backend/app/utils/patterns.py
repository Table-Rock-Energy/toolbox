"""Compiled regex patterns for parsing documents across all tools."""

from __future__ import annotations

import re

# State abbreviations - all US states and territories
US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "DC", "PR", "VI", "GU", "AS", "MP",
}

# ZIP code patterns
ZIP_PATTERN = re.compile(r"\b(\d{5})(?:-(\d{4}))?\b")
ZIP_FULL_PATTERN = re.compile(r"\b\d{5}(?:-\d{4})?\b")

# PO Box pattern
PO_BOX_PATTERN = re.compile(
    r"P\.?\s*O\.?\s*Box\s+(\d+)",
    re.IGNORECASE,
)

# Apartment/Suite pattern
APT_SUITE_PATTERN = re.compile(
    r"(?:Apt\.?|Suite|Ste\.?|Unit|#)\s*(\d+[A-Za-z]?|[A-Za-z])",
    re.IGNORECASE,
)

# Name annotation patterns
AKA_PATTERN = re.compile(
    r"\ba/?k/?a\b\s*:?\s*([^,\n]+)",
    re.IGNORECASE,
)

FKA_PATTERN = re.compile(
    r"\bf/?k/?a\b\s*:?\s*([^,\n]+)",
    re.IGNORECASE,
)

CO_PATTERN = re.compile(
    r"\bc/?o\b\s*:?\s*([^,\n]+)",
    re.IGNORECASE,
)

# Common name suffixes
NAME_SUFFIXES = {
    "JR", "JR.", "SR", "SR.", "II", "III", "IV", "V",
    "MD", "M.D.", "PHD", "PH.D.", "ESQ", "ESQ.",
}

# OCR artifact cleaning patterns
OCR_ARTIFACTS = [
    (re.compile(r"[^\S\n]+"), " "),  # Multiple spaces/tabs to single space
    (re.compile(r"\n{3,}"), "\n\n"),  # Collapse 3+ newlines to 2
    (re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]"), ""),  # Control characters
    (re.compile(r"[\u201c\u201d\u201f]"), '"'),  # Smart quotes
    (re.compile(r"[\u2018\u2019\u201b]"), "'"),  # Smart apostrophes
    (re.compile(r"\u2013"), "-"),  # En dash
    (re.compile(r"\u2014"), "-"),  # Em dash
]


def clean_text(text: str) -> str:
    """Clean common OCR artifacts from text while preserving line structure."""
    for pattern, replacement in OCR_ARTIFACTS:
        text = pattern.sub(replacement, text)
    return text.strip()


def normalize_state(state: str) -> str | None:
    """Normalize and validate a state abbreviation."""
    state_upper = state.upper().strip()
    if state_upper in US_STATES:
        return state_upper
    return None


def validate_zip(zip_code: str) -> bool:
    """Validate ZIP code format."""
    return bool(ZIP_FULL_PATTERN.fullmatch(zip_code.strip()))


# Entity type detection patterns for title tool
ESTATE_PATTERNS = [
    re.compile(r"\bESTATE\s+OF\b", re.IGNORECASE),
    re.compile(r"\bESTATE\b", re.IGNORECASE),
    re.compile(r"\bHEIRS\s+OF\b", re.IGNORECASE),
    re.compile(r"\bHEIRS\s+AND\s+ASSIGNS\b", re.IGNORECASE),
    re.compile(r"\bUNKNOWN\s+HEIRS\b", re.IGNORECASE),
    re.compile(r",\s*DECEASED\b", re.IGNORECASE),
]

TRUST_PATTERNS = [
    re.compile(r"\bTRUST\b", re.IGNORECASE),
    re.compile(r"\bTRUSTEE\b", re.IGNORECASE),
    re.compile(r"\bU/?T/?A\b", re.IGNORECASE),  # Under Trust Agreement
    re.compile(r"\bU/?D\b(?=\s|$)", re.IGNORECASE),  # Under Declaration
    re.compile(r"\bREVOCABLE\s+LIVING\b", re.IGNORECASE),
    re.compile(r"\bLIVING\s+TRUST\b", re.IGNORECASE),
    re.compile(r"\bFAMILY\s+TRUST\b", re.IGNORECASE),
]

CORPORATION_PATTERNS = [
    re.compile(r"\bINC\.?\b", re.IGNORECASE),
    re.compile(r"\bINCORPORATED\b", re.IGNORECASE),
    re.compile(r"\bCORP\.?\b", re.IGNORECASE),
    re.compile(r"\bCORPORATION\b", re.IGNORECASE),
    re.compile(r"\bL\.?L\.?C\.?\b", re.IGNORECASE),
    re.compile(r"\bL\.?P\.?\b(?!\s*\d)", re.IGNORECASE),
    re.compile(r"\bL\.?L\.?P\.?\b", re.IGNORECASE),
    re.compile(r"\bLTD\.?\b", re.IGNORECASE),
    re.compile(r"\bLIMITED\b", re.IGNORECASE),
    re.compile(r"\bPARTNERSHIP\b", re.IGNORECASE),
    re.compile(r"\bPARTNERS\b", re.IGNORECASE),
    re.compile(r"\bCOMPANY\b", re.IGNORECASE),
    re.compile(r"\bCO\.\b", re.IGNORECASE),
]

FOUNDATION_PATTERNS = [
    re.compile(r"\bFOUNDATION\b", re.IGNORECASE),
]

UNIVERSITY_PATTERNS = [
    re.compile(r"\bUNIVERSITY\b", re.IGNORECASE),
    re.compile(r"\bCOLLEGE\b", re.IGNORECASE),
]

CHURCH_PATTERNS = [
    re.compile(r"\bCHURCH\b", re.IGNORECASE),
    re.compile(r"\bDIOCESE\b", re.IGNORECASE),
    re.compile(r"\bPARISH\b", re.IGNORECASE),
    re.compile(r"\bMINISTRIES\b", re.IGNORECASE),
]

MINERAL_CO_PATTERNS = [
    re.compile(r"\bMINERALS?\b", re.IGNORECASE),
    re.compile(r"\bROYALT(?:Y|IES)\b", re.IGNORECASE),
    re.compile(r"\bOIL\s*(?:&|AND)\s*GAS\b", re.IGNORECASE),
    re.compile(r"\bPETROLEUM\b", re.IGNORECASE),
    re.compile(r"\bENERGY\b", re.IGNORECASE),
    re.compile(r"\bRESOURCES\b", re.IGNORECASE),
]

# Extract tool specific patterns
ENTRY_NUMBER_PATTERN = re.compile(
    r"^(U\s*)?(\d+)\.\s*",
    re.MULTILINE,
)

ENTRY_SPLIT_PATTERN = re.compile(
    r"(?=(?:^|\n)(?:U\s*)?\d+\.\s+)",
    re.MULTILINE,
)

TRUSTEE_PATTERN = re.compile(
    r",?\s*((?:as\s+)?(?:Successor\s+)?Trustee(?:s)?(?:\s+of)?)",
    re.IGNORECASE,
)

TRUST_DATE_PATTERN = re.compile(
    r"(?:dated|dtd\.?|dt\.?)\s+([A-Z][a-z]+\s+\d{1,2},?\s+\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
    re.IGNORECASE,
)

ADDRESS_UNKNOWN_PATTERN = re.compile(
    r"ADDRESS\s+UNKNOWN",
    re.IGNORECASE,
)

INDIVIDUALLY_PATTERN = re.compile(
    r"(,?\s*Individually\s+and\s+as\s+[^,]+)",
    re.IGNORECASE,
)

HEIR_OF_PATTERN = re.compile(
    r"(,?\s*[Hh]eir\s+of\s+[^,\d]+)",
    re.IGNORECASE,
)

FBO_PATTERN = re.compile(
    r"\bFBO\s+([^,\n]+)",
    re.IGNORECASE,
)

EXHIBIT_A_START_PATTERN = re.compile(
    r"(?:^|\n)\s*Exhibit\s*[\"']?A[\"']?\s*\n\s*(?=\d+\.\s)",
    re.IGNORECASE | re.MULTILINE,
)

EXHIBIT_END_PATTERN = re.compile(
    r"Exhibit\s*[\"']?[B-Z][\"']?",
    re.IGNORECASE,
)

LLC_PATTERN = re.compile(r"\bL\.?L\.?C\.?\b", re.IGNORECASE)
INC_PATTERN = re.compile(r"\b(?:Inc\.?|Incorporated)\b", re.IGNORECASE)
CORP_PATTERN = re.compile(r"\b(?:Corp\.?|Corporation)\b", re.IGNORECASE)
LP_PATTERN = re.compile(r"\bL\.?P\.?\b(?!\s*\d)", re.IGNORECASE)
PARTNERSHIP_PATTERN = re.compile(r"\bPartnership\b", re.IGNORECASE)
TRUST_PATTERN = re.compile(r"\b(?:Trust|Trustee)\b", re.IGNORECASE)
ESTATE_PATTERN = re.compile(r"\b(?:Estate\s+of|,\s*Deceased)\b", re.IGNORECASE)
UNKNOWN_HEIRS_PATTERN = re.compile(
    r"\b(?:Unknown\s+Heirs|heirs\s+and\s+assigns)\b",
    re.IGNORECASE,
)
GOVERNMENT_PATTERN = re.compile(
    r"\b(?:Bureau|County|Commission|Board\s+of|State\s+of|United\s+States)\b",
    re.IGNORECASE,
)

# Title tool specific patterns
FD_PATTERN = re.compile(
    r"\bFD:\s*([^\n]+)",
    re.IGNORECASE,
)

NOTE_PATTERN = re.compile(
    r"\bNote\s*(?:\(?\d+\)?)?:?\s*([^\n]+)",
    re.IGNORECASE,
)

LEASE_PATTERN = re.compile(
    r"\b(?:Lease|QCMD|Ref\.?)[\s#:]*([A-Za-z0-9-]+)",
    re.IGNORECASE,
)

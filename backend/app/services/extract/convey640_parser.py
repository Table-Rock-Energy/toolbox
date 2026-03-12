"""Convey 640 CSV/Excel parser for OCC respondent lists.

Parses Convey 640 export files (CSV or Excel) into the same PartyEntry +
CaseMetadata types used by the ECF PDF parser.  This allows Phase 3 merge
to consume both PDF and CSV results with identical types.

Pipeline order for each name:
  1. Strip leading entry number
  2. Extract CLO/ELO care-of patterns
  3. Extract standard C/O patterns
  4. Extract A/K/A aliases
  5. Extract NEE maiden name
  6. Extract NOW married name
  7. Strip DECEASED marker
  8. Detect entity type
  9. For individuals: split joint names on &
  10. For trusts: extract grantor as primary name
  11. Parse individual names (first/middle/last/suffix)
"""

from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass, field

import pandas as pd

from app.models.extract import CaseMetadata, EntityType, PartyEntry
from app.services.extract.name_parser import parse_name
from app.utils.patterns import detect_entity_type

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@dataclass
class Convey640ParseResult:
    """Result of parsing a Convey 640 CSV/Excel file."""

    entries: list[PartyEntry] = field(default_factory=list)
    metadata: CaseMetadata = field(default_factory=CaseMetadata)


def parse_convey640(file_bytes: bytes, filename: str) -> Convey640ParseResult:
    """Parse a Convey 640 CSV or Excel file.

    Args:
        file_bytes: Raw file content.
        filename: Original filename (used to detect CSV vs Excel).

    Returns:
        Convey640ParseResult with entries and metadata.

    Raises:
        ValueError: If schema is invalid or file has no data rows.
    """
    df = _read_file(file_bytes, filename)
    _validate_schema(df)

    if df.empty:
        raise ValueError("File contains no data rows")

    metadata = _extract_metadata(df)
    entries: list[PartyEntry] = []

    for idx, row in df.iterrows():
        entry = _parse_row(row, int(idx) + 1)
        if entry:
            entries.append(entry)

    logger.info("Parsed %d Convey 640 entries from %s", len(entries), filename)
    return Convey640ParseResult(entries=entries, metadata=metadata)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EXPECTED_COLUMNS = {
    "county", "str", "applicant", "classification", "case_no",
    "curative", "_date", "name", "address", "city", "state", "postal_code",
}

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Entry number: digits + optional period + required whitespace
ENTRY_NUMBER_RE = re.compile(r"^(\d+)\.?\s+")

# CLO/ELO care-of (Convey 640 specific notation)
CLO_ELO_RE = re.compile(r"\s+(?:CLO|ELO)\s+(.+)$", re.IGNORECASE)

# Standard C/O pattern
CO_RE = re.compile(r"\s+C/O\s+(.+)$", re.IGNORECASE)

# A/K/A alias
AKA_RE = re.compile(r"\s+A/K/A\s+(.+)$", re.IGNORECASE)

# NEE maiden name
NEE_RE = re.compile(r"\s+NEE\s+(\S+.*)$", re.IGNORECASE)

# NOW married name -- captures the new name at the end
NOW_RE = re.compile(r"\s+NOW\s+(\S+.*)$", re.IGNORECASE)

# DECEASED / POSSIBLY DECEASED marker
DECEASED_RE = re.compile(r"\s*\b(?:POSSIBLY\s+)?DECEASED\b\s*", re.IGNORECASE)

# Trust grantor extraction -- text before trust keyword
TRUST_KEYWORD_RE = re.compile(
    r"\b(?:REVOCABLE\s+TRUST|LIVING\s+TRUST|FAMILY\s+TRUST|TRUST\s+DATED|"
    r"TRUST\s+AGREEMENT|TRUST)\b",
    re.IGNORECASE,
)

# "AS TRUSTEE OF" pattern -- trustee is the grantor
AS_TRUSTEE_RE = re.compile(
    r"^(.+?)\s+AS\s+(?:SUCCESSOR\s+)?TRUSTEE\s+OF\s+(?:THE\s+)?(.+)$",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# File reading and validation
# ---------------------------------------------------------------------------


def _read_file(file_bytes: bytes, filename: str) -> pd.DataFrame:
    """Read CSV or Excel bytes into a DataFrame with dtype=str."""
    buf = io.BytesIO(file_bytes)
    if filename.lower().endswith((".xlsx", ".xls")):
        df = pd.read_excel(buf, dtype=str)
    else:
        df = pd.read_csv(buf, dtype=str, keep_default_na=False)

    # Normalize column names to lowercase, stripped
    df.columns = df.columns.str.strip().str.lower()
    return df


def _validate_schema(df: pd.DataFrame) -> None:
    """Validate DataFrame has the expected 12 Convey 640 columns."""
    actual = set(df.columns)
    missing = EXPECTED_COLUMNS - actual
    if missing:
        raise ValueError(
            f"Missing expected columns: {sorted(missing)}. "
            f"Found columns: {sorted(actual)}"
        )


# ---------------------------------------------------------------------------
# Metadata extraction
# ---------------------------------------------------------------------------


def _extract_metadata(df: pd.DataFrame) -> CaseMetadata:
    """Extract case metadata from the first row."""
    row = df.iloc[0]
    return CaseMetadata(
        county=_clean_str(row.get("county")) or None,
        legal_description=_clean_str(row.get("str")) or None,
        applicant=_clean_str(row.get("applicant")) or None,
        case_number=_normalize_case_number(str(row.get("case_no", ""))),
    )


def _normalize_case_number(raw: str) -> str | None:
    """Convert '2026000909' or '2026000909.0' to 'CD 2026-000909-T'."""
    raw = raw.strip()
    if not raw or raw.lower() in ("nan", "none", ""):
        return None
    # Remove .0 suffix from float-like strings
    if "." in raw:
        raw = raw.split(".")[0]
    if len(raw) == 10 and raw.isdigit():
        return f"CD {raw[:4]}-{raw[4:]}-T"
    return raw


# ---------------------------------------------------------------------------
# Postal code normalization
# ---------------------------------------------------------------------------


def _normalize_postal_code(val: str) -> tuple[str, bool]:
    """Convert postal_code string to 5-digit zero-padded.

    Returns:
        Tuple of (normalized_zip, should_flag).
    """
    if not val or val.lower() in ("nan", "none", ""):
        return "", False
    # Remove .0 suffix
    if "." in val:
        val = val.split(".")[0]
    val = val.strip()
    if not val or not val.isdigit():
        return "", False
    if len(val) > 5:
        # Data error -- truncate to 5, flag the entry
        return val[:5], True
    return val.zfill(5), False


# ---------------------------------------------------------------------------
# Name normalization pipeline
# ---------------------------------------------------------------------------


def _strip_entry_number(name: str) -> tuple[str | None, str]:
    """Strip leading entry number from name.

    Returns (entry_number_or_none, cleaned_name).
    """
    match = ENTRY_NUMBER_RE.match(name)
    if match:
        return match.group(1), name[match.end():]
    return None, name


def _extract_care_of(name: str) -> tuple[str, str | None]:
    """Extract CLO/ELO and C/O care-of from name.

    Returns (cleaned_name, care_of_name_or_none).
    """
    # Check CLO/ELO first
    match = CLO_ELO_RE.search(name)
    if match:
        return name[:match.start()].strip(), match.group(1).strip()
    # Check standard C/O
    match = CO_RE.search(name)
    if match:
        return name[:match.start()].strip(), match.group(1).strip()
    return name, None


def _extract_aka(name: str) -> tuple[str, str | None]:
    """Extract A/K/A alias from name.

    Returns (cleaned_name, alias_or_none).
    """
    match = AKA_RE.search(name)
    if match:
        return name[:match.start()].strip(), match.group(1).strip()
    return name, None


def _extract_nee(name: str) -> tuple[str, str | None]:
    """Extract NEE maiden name from name.

    Returns (cleaned_name, maiden_name_or_none).
    """
    match = NEE_RE.search(name)
    if match:
        return name[:match.start()].strip(), match.group(1).strip()
    return name, None


def _extract_now_name(name: str) -> tuple[str, str | None]:
    """Extract NOW married name from name.

    If present, the married name becomes primary and the maiden last name
    goes to notes.

    Returns (new_primary_name, maiden_last_name_or_none).
    """
    match = NOW_RE.search(name)
    if match:
        married_name = match.group(1).strip()
        before_now = name[:match.start()].strip()
        parts = before_now.split()
        if len(parts) >= 2:
            maiden_last = parts[-1]
            new_name = " ".join(parts[:-1]) + " " + married_name
            return new_name, maiden_last
        return before_now + " " + married_name, None
    return name, None


def _strip_deceased(name: str) -> tuple[str, bool]:
    """Strip DECEASED / POSSIBLY DECEASED marker from name.

    Returns (cleaned_name, is_deceased).
    """
    if DECEASED_RE.search(name):
        cleaned = DECEASED_RE.sub("", name).strip()
        return cleaned, True
    return name, False


def _extract_trust_grantor(name: str) -> tuple[str, str | None]:
    """Extract grantor name from a trust name.

    For "JUDI K SMITH AS TRUSTEE OF THE JUDI K SMITH TRUST",
    extracts "JUDI K SMITH" as the contactable person.

    For "INA NADINE TAYLOR REVOCABLE TRUST DATED ...",
    extracts "INA NADINE TAYLOR" as the grantor.

    Returns (grantor_name, trust_details_or_none).
    """
    # Check for "AS TRUSTEE OF" pattern first
    as_trustee_match = AS_TRUSTEE_RE.match(name)
    if as_trustee_match:
        grantor = as_trustee_match.group(1).strip()
        trust_detail = as_trustee_match.group(2).strip()
        return grantor, f"trustee of {trust_detail}"

    # Find trust keyword and use text before it as grantor
    keyword_match = TRUST_KEYWORD_RE.search(name)
    if keyword_match:
        grantor = name[:keyword_match.start()].strip()
        trust_detail = name[keyword_match.start():].strip()
        if grantor:
            return grantor, trust_detail.lower()

    return name, None


# ---------------------------------------------------------------------------
# Row parsing
# ---------------------------------------------------------------------------


def _parse_row(row: pd.Series, row_index: int) -> PartyEntry | None:
    """Parse a single DataFrame row into a PartyEntry."""
    raw_name = str(row.get("name", "")).strip()
    if not raw_name or raw_name.lower() in ("nan", "none"):
        return None

    notes_parts: list[str] = []
    flagged = False
    flag_reason = None

    # 1. Strip entry number
    entry_number, name = _strip_entry_number(raw_name)
    if entry_number is None:
        entry_number = str(row_index)

    # 2. Extract care-of (CLO/ELO and C/O)
    name, care_of = _extract_care_of(name)
    if care_of:
        notes_parts.append(f"c/o {care_of}")

    # 3. Extract A/K/A
    name, aka = _extract_aka(name)
    if aka:
        notes_parts.append(f"a/k/a {aka}")

    # 4. Extract NEE maiden name
    name, nee = _extract_nee(name)
    if nee:
        notes_parts.append(f"f/k/a {nee}")

    # 5. Extract NOW married name
    name, maiden_last = _extract_now_name(name)
    if maiden_last:
        notes_parts.append(f"f/k/a {maiden_last}")

    # 6. Strip DECEASED
    name, is_deceased = _strip_deceased(name)
    if is_deceased:
        notes_parts.append("deceased")

    # 7. Detect entity type
    entity_type_str = detect_entity_type(name)
    entity_type = EntityType(entity_type_str)

    # Override to ESTATE if deceased
    if is_deceased:
        entity_type = EntityType.ESTATE

    # 8. For trusts: extract grantor name
    if entity_type == EntityType.TRUST:
        name, trust_detail = _extract_trust_grantor(name)
        if trust_detail:
            notes_parts.append(trust_detail)

    # 9. For individuals: split joint names on &
    if entity_type == EntityType.INDIVIDUAL and " & " in name:
        parts = name.split(" & ", 1)
        name = parts[0].strip()
        if len(parts) > 1:
            notes_parts.append(parts[1].strip())

    # Clean up name
    name = name.strip()

    # 10. Parse name for individuals
    parsed = parse_name(name, entity_type.value)

    # Postal code
    postal_raw = str(row.get("postal_code", "")).strip()
    zip_code, zip_flagged = _normalize_postal_code(postal_raw)
    if zip_flagged:
        flagged = True
        flag_reason = "Postal code has more than 5 digits"

    # Section type from curative column
    curative_val = str(row.get("curative", "0")).strip()
    section_type = "curative" if curative_val == "1" else "regular"

    # Address fields
    address = _clean_str(row.get("address"))
    city = _clean_str(row.get("city"))
    state = _clean_str(row.get("state"))

    notes = "; ".join(notes_parts) if notes_parts else None

    return PartyEntry(
        entry_number=entry_number,
        primary_name=name,
        entity_type=entity_type,
        mailing_address=address or None,
        city=city or None,
        state=state or None,
        zip_code=zip_code,
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
# Utilities
# ---------------------------------------------------------------------------


def _clean_str(val: object) -> str:
    """Convert a value to a cleaned string, handling NaN/None."""
    if val is None:
        return ""
    s = str(val).strip()
    if s.lower() in ("nan", "none"):
        return ""
    return s

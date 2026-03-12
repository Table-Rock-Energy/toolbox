"""Format detection for Exhibit A PDFs.

Identifies the layout format of OCC Exhibit A documents so the correct
parser strategy can be applied.
"""

from __future__ import annotations

import io
import logging
import re
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.extract import PartyEntry

logger = logging.getLogger(__name__)


class ExhibitFormat(str, Enum):
    """Supported Exhibit A PDF layout formats."""

    FREE_TEXT_NUMBERED = "FREE_TEXT_NUMBERED"
    TABLE_ATTENTION = "TABLE_ATTENTION"
    TABLE_SPLIT_ADDR = "TABLE_SPLIT_ADDR"
    FREE_TEXT_LIST = "FREE_TEXT_LIST"
    ECF = "ECF"
    UNKNOWN = "UNKNOWN"


# Detection patterns
_ATTENTION_HEADER = re.compile(
    r"\b(attention|attn)\b", re.IGNORECASE
)
_NAME_HEADER = re.compile(r"\bname\b", re.IGNORECASE)
_ADDRESS_HEADER = re.compile(r"\baddress\b", re.IGNORECASE)

_CITY_STATE_ZIP_HEADERS = re.compile(
    r"\bcity\b.*\bstate\b.*\bzip\b", re.IGNORECASE
)
_CURATIVE_PARTIES = re.compile(
    r"curative\s+parties", re.IGNORECASE
)

_RESPONDENTS_UNKNOWN = re.compile(
    r"RESPONDENTS\s+WITH\s+ADDRESS\s+UNKNOWN", re.IGNORECASE
)

# Two-column numbered list: look for numbers like "1." appearing with
# wide horizontal spacing (suggesting two columns on same line)
_TWO_COL_NUMBERED = re.compile(
    r"^\s*\d+\.\s+.{20,}\s{4,}\d+\.\s+", re.MULTILINE
)

# ECF filing: multiunit horizontal well application with Exhibit A respondent list
_ECF_MULTIUNIT = re.compile(
    r"MULTIUNIT\s+HORIZONTAL\s+WELL", re.IGNORECASE
)
_ECF_CAUSE_CD = re.compile(
    r"CAUSE\s+(?:NO\.?\s+)?CD\s+\d{4}-\d+", re.IGNORECASE
)


def detect_format(
    text: str, file_bytes: bytes | None = None
) -> ExhibitFormat:
    """Auto-detect the Exhibit A PDF format from extracted text.

    Args:
        text: Full extracted text from the PDF.
        file_bytes: Raw PDF bytes (optional). Used for pdfplumber table
            detection when text heuristics are ambiguous.

    Returns:
        The detected ExhibitFormat.
    """
    # Check for TABLE_ATTENTION (Devon-style)
    has_attention = bool(_ATTENTION_HEADER.search(text))
    has_name = bool(_NAME_HEADER.search(text))
    has_address = bool(_ADDRESS_HEADER.search(text))

    if has_attention and has_name and has_address:
        logger.info("Format detected: TABLE_ATTENTION (attention column header)")
        return ExhibitFormat.TABLE_ATTENTION

    # Check for TABLE_SPLIT_ADDR (Mewbourne-style)
    if _CITY_STATE_ZIP_HEADERS.search(text) or _CURATIVE_PARTIES.search(text):
        logger.info("Format detected: TABLE_SPLIT_ADDR (split city/state/zip headers)")
        return ExhibitFormat.TABLE_SPLIT_ADDR

    # Check for ECF filing (multiunit horizontal well application)
    if _ECF_MULTIUNIT.search(text) and _ECF_CAUSE_CD.search(text):
        logger.info("Format detected: ECF (multiunit horizontal well filing)")
        return ExhibitFormat.ECF

    # Check for FREE_TEXT_LIST (Coterra-style two-column numbered list)
    if _TWO_COL_NUMBERED.search(text) or _RESPONDENTS_UNKNOWN.search(text):
        logger.info("Format detected: FREE_TEXT_LIST (two-column numbered list)")
        return ExhibitFormat.FREE_TEXT_LIST

    # Use pdfplumber table detection as secondary signal
    if file_bytes:
        fmt = _detect_via_tables(file_bytes)
        if fmt != ExhibitFormat.UNKNOWN:
            return fmt

    # Default to existing free-text parser
    logger.info("Format detected: FREE_TEXT_NUMBERED (default)")
    return ExhibitFormat.FREE_TEXT_NUMBERED


def _detect_via_tables(file_bytes: bytes) -> ExhibitFormat:
    """Use pdfplumber to detect tables and infer format from column count."""
    try:
        import pdfplumber

        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            # Check first few pages for tables
            for page in pdf.pages[:3]:
                tables = page.extract_tables()
                if not tables:
                    continue
                for table in tables:
                    if not table or len(table) < 2:
                        continue
                    # Use first non-empty row to determine column count
                    for row in table:
                        if row and any(cell for cell in row if cell):
                            col_count = len(row)
                            header_text = " ".join(
                                str(c) for c in row if c
                            ).lower()
                            if col_count >= 6 and (
                                "city" in header_text
                                or "state" in header_text
                                or "zip" in header_text
                            ):
                                logger.info(
                                    "Format detected via table: TABLE_SPLIT_ADDR (%d cols)",
                                    col_count,
                                )
                                return ExhibitFormat.TABLE_SPLIT_ADDR
                            if col_count >= 4 and (
                                "attention" in header_text
                                or "attn" in header_text
                            ):
                                logger.info(
                                    "Format detected via table: TABLE_ATTENTION (%d cols)",
                                    col_count,
                                )
                                return ExhibitFormat.TABLE_ATTENTION
                            break
    except Exception as e:
        logger.warning("pdfplumber table detection failed: %s", e)

    return ExhibitFormat.UNKNOWN


def compute_quality_score(
    entries: list[PartyEntry],
    total_expected: int | None = None,
) -> float:
    """Score parsing quality from 0.0 (poor) to 1.0 (excellent).

    Criteria:
      - Ratio of non-flagged entries
      - Ratio of entries with a valid address (street or city)
      - Ratio of entries with a plausible name (>5 chars, no garbled text)
      - If total_expected is known, ratio of parsed vs expected count

    Args:
        entries: Parsed party entries.
        total_expected: Expected entry count (optional).

    Returns:
        Quality score between 0.0 and 1.0.
    """
    if not entries:
        return 0.0

    n = len(entries)

    # 1. Non-flagged ratio
    non_flagged = sum(1 for e in entries if not e.flagged)
    flag_ratio = non_flagged / n

    # 2. Address ratio (has at least street or city)
    has_addr = sum(
        1
        for e in entries
        if (e.mailing_address or e.city)
        and not e.entry_number.startswith("U")
    )
    # Exclude unknown-address entries from denominator
    addr_denom = sum(1 for e in entries if not e.entry_number.startswith("U"))
    addr_ratio = (has_addr / addr_denom) if addr_denom > 0 else 1.0

    # 3. Name quality ratio
    good_names = sum(1 for e in entries if _is_valid_name(e.primary_name))
    name_ratio = good_names / n

    # 4. Count ratio (if expected count known)
    count_ratio = 1.0
    if total_expected and total_expected > 0:
        count_ratio = min(n / total_expected, 1.0)

    # Weighted average
    score = (
        0.25 * flag_ratio
        + 0.30 * addr_ratio
        + 0.30 * name_ratio
        + 0.15 * count_ratio
    )
    return round(min(max(score, 0.0), 1.0), 2)


def _is_valid_name(name: str) -> bool:
    """Check if a name looks plausible (not garbled)."""
    if not name or len(name) < 3:
        return False

    # Garbled: high ratio of non-ASCII / non-printable
    ascii_chars = sum(1 for c in name if c.isascii() and c.isprintable())
    if len(name) > 0 and ascii_chars / len(name) < 0.8:
        return False

    # Mostly numbers/symbols
    alpha_chars = sum(1 for c in name if c.isalpha())
    if len(name) > 3 and alpha_chars / len(name) < 0.4:
        return False

    return True

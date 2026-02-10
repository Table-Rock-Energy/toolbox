"""Shared address parsing service used by Extract and Title tools.

This module contains the core address-parsing logic that was previously
duplicated across ``services/extract/address_parser.py`` and
``services/title/address_parser.py``.  Both tool-specific modules now
import from here.

The title tool extends the shared parser with annotation extraction
(``parse_address_with_notes``, ``extract_address_annotations``).
"""

from __future__ import annotations

import re
from typing import Optional

from app.utils.patterns import (
    APT_SUITE_PATTERN,
    PO_BOX_PATTERN,
    US_STATES,
    normalize_state,
    validate_zip,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_address(address_text: str) -> dict[str, Optional[str]]:
    """Parse an address string into structured components.

    Handles:
    - Standard formats: ``"123 Main St, City, ST 12345"``
    - Multi-line addresses
    - PO Box addresses
    - Apartment/suite/unit numbers (split to street2)
    - ZIP and ZIP+4 formats

    Returns a dict with keys: ``street``, ``street2``, ``city``,
    ``state``, ``zip``.
    """
    result: dict[str, Optional[str]] = {
        "street": None,
        "street2": None,
        "city": None,
        "state": None,
        "zip": None,
    }

    if not address_text or not address_text.strip():
        return result

    text = _normalize_address_text(address_text)

    zip_match = _extract_zip(text)
    if zip_match:
        result["zip"] = zip_match["zip"]
        text_before_zip = zip_match["text_before"]

        state_result = _extract_state(text_before_zip)
        if state_result:
            result["state"] = state_result["state"]
            text_before_state = state_result["text_before"]
            city_street = _extract_city_and_street(text_before_state)
        else:
            city_street = _extract_city_and_street(text_before_zip)

        result["city"] = city_street["city"]
        result["street"] = city_street["street"]
    else:
        result = _parse_without_zip(text)

    result = _clean_result(result)
    return result


def format_full_address(
    street: Optional[str],
    city: Optional[str],
    state: Optional[str],
    zip_code: Optional[str],
) -> str:
    """Format address components into a single-line address string."""
    parts: list[str] = []
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


def split_address_lines(street: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """Split street into line 1 and line 2 (apt/suite/unit/#)."""
    if not street:
        return None, None

    match = re.search(
        r"[,\s]+(?:Apt\.?|Suite|Ste\.?|Unit|#)\s*\S+.*$",
        street,
        re.IGNORECASE,
    )
    if match:
        line1 = street[: match.start()].rstrip(", ")
        line2 = street[match.start() :].lstrip(", ")
        return line1 or None, line2 or None

    return street, None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _normalize_address_text(text: str) -> str:
    """Normalize address text by handling line breaks and extra whitespace."""
    text = re.sub(r"[\r\n]+", ", ", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r",\s*,", ",", text)
    return text.strip()


def _extract_zip(text: str) -> Optional[dict]:
    """Extract ZIP code and return it with the text before it."""
    end_zip_pattern = re.compile(r"\b(\d{5})(?:-(\d{4}))?\s*$")
    match = end_zip_pattern.search(text)

    if not match:
        state_zip_pattern = re.compile(
            r"[,\s]+[A-Z]{2}[.,]?\s+(\d{5})(?:-(\d{4}))?(?:\s*$|[,\s])"
        )
        match = state_zip_pattern.search(text.upper())
        if match:
            zip_val = match.group(1)
            actual_pattern = re.compile(r"\b(" + zip_val + r")(?:-(\d{4}))?\b")
            all_matches = list(actual_pattern.finditer(text))
            if all_matches:
                match = all_matches[-1]

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

    state_pattern = re.compile(r"[,\s]+([A-Za-z]{2})\.?\s*$")
    match = state_pattern.search(text)

    if match:
        potential_state = match.group(1).upper()
        if potential_state in US_STATES:
            return {
                "state": potential_state,
                "text_before": text[: match.start()].strip(),
            }

    if len(text) >= 2:
        last_two = text[-2:].upper()
        if last_two in US_STATES:
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
    parts = [p.strip() for p in text.split(",") if p.strip()]

    if len(parts) >= 2:
        result["city"] = parts[-1]
        result["street"] = ", ".join(parts[:-1])
    elif len(parts) == 1:
        single_part = parts[0]
        if not re.match(r"^\d", single_part) and not PO_BOX_PATTERN.match(
            single_part
        ):
            result["city"] = single_part
        else:
            result["street"] = single_part

    return result


def _parse_without_zip(text: str) -> dict[str, Optional[str]]:
    """Parse address when no ZIP code is found."""
    result: dict[str, Optional[str]] = {
        "street": None,
        "street2": None,
        "city": None,
        "state": None,
        "zip": None,
    }

    parts = [p.strip() for p in text.split(",") if p.strip()]
    if not parts:
        return result

    for i, part in enumerate(parts):
        words = part.split()
        for j, word in enumerate(words):
            clean_word = word.strip(".,").upper()
            if clean_word in US_STATES:
                result["state"] = clean_word
                if j > 0:
                    result["city"] = " ".join(words[:j])
                elif i > 0:
                    result["city"] = parts[i - 1]
                if i > 1:
                    result["street"] = ", ".join(parts[: i - 1])
                elif i == 1 and result["city"] is None:
                    result["street"] = parts[0]
                return result

    if len(parts) >= 2:
        result["street"] = ", ".join(parts[:-1])
        result["city"] = parts[-1]
    else:
        result["street"] = parts[0]

    return result


def _split_apt_unit(street: str) -> tuple[str, Optional[str]]:
    """Split apartment/suite/unit from street address."""
    if not street:
        return street, None

    apt_pattern = re.compile(
        r"[,\s]+(?P<apt>(?:Apt\.?|Apartment|Suite|Ste\.?|Unit|#)\s*[A-Za-z0-9-]+)\s*$",
        re.IGNORECASE,
    )
    match = apt_pattern.search(street)
    if match:
        apt_part = match.group("apt").strip()
        street_part = street[: match.start()].strip().rstrip(",").strip()
        return street_part, apt_part

    inline_pattern = re.compile(
        r"^(?P<street>.+?)\s+(?P<apt>(?:Apt\.?|Apartment|Suite|Ste\.?|Unit|#)\s*[A-Za-z0-9-]+)$",
        re.IGNORECASE,
    )
    match = inline_pattern.match(street)
    if match:
        return match.group("street").strip(), match.group("apt").strip()

    return street, None


def _clean_result(result: dict[str, Optional[str]]) -> dict[str, Optional[str]]:
    """Clean up parsed address components."""
    for key in result:
        if result[key]:
            value = result[key].strip().rstrip(".,)").strip()
            value = re.sub(r"\s+", " ", value)
            if value and not re.search(r"[a-zA-Z0-9]", value):
                value = None
            result[key] = value if value else None

    # Split apt/suite/unit from street address into street2
    if result.get("street") and not result.get("street2"):
        street, street2 = _split_apt_unit(result["street"])
        result["street"] = street
        result["street2"] = street2

    if result["state"]:
        normalized = normalize_state(result["state"])
        result["state"] = normalized

    if result["zip"] and not validate_zip(result["zip"]):
        zip_clean = re.sub(r"[^\d-]", "", result["zip"])
        if validate_zip(zip_clean):
            result["zip"] = zip_clean

    return result

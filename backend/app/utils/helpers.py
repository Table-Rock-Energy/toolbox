"""Utility functions for the toolbox backend."""

import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Optional


def parse_date(date_str: str) -> Optional[date]:
    """Parse date from various formats."""
    if not date_str:
        return None

    date_str = date_str.strip()

    # Format: "Dec 2024" or "Sep 2024"
    month_year_pattern = r"^([A-Za-z]{3})\s+(\d{4})$"
    match = re.match(month_year_pattern, date_str)
    if match:
        month_str, year_str = match.groups()
        months = {
            "jan": 1, "feb": 2, "mar": 3, "apr": 4,
            "may": 5, "jun": 6, "jul": 7, "aug": 8,
            "sep": 9, "oct": 10, "nov": 11, "dec": 12
        }
        month = months.get(month_str.lower())
        if month:
            return date(int(year_str), month, 1)

    # Format: "2/24/2025" or "02/24/2025"
    mdy_pattern = r"^(\d{1,2})/(\d{1,2})/(\d{4})$"
    match = re.match(mdy_pattern, date_str)
    if match:
        month, day, year = match.groups()
        return date(int(year), int(month), int(day))

    # Format: "01/16/2026"
    mdy_pattern2 = r"^(\d{2})/(\d{2})/(\d{4})$"
    match = re.match(mdy_pattern2, date_str)
    if match:
        month, day, year = match.groups()
        return date(int(year), int(month), int(day))

    # Format: "MM/YY"
    mmyy_pattern = r"^(\d{1,2})/(\d{2})$"
    match = re.match(mmyy_pattern, date_str)
    if match:
        month, year = match.groups()
        full_year = 2000 + int(year) if int(year) < 50 else 1900 + int(year)
        return date(full_year, int(month), 1)

    return None


def parse_decimal(value_str: str) -> Optional[Decimal]:
    """Parse decimal from string, handling parentheses for negatives."""
    if not value_str:
        return None

    value_str = str(value_str).strip()

    # Handle parentheses for negative values: (123.45) -> -123.45
    if value_str.startswith("(") and value_str.endswith(")"):
        value_str = "-" + value_str[1:-1]

    # Remove commas
    value_str = value_str.replace(",", "")

    # Remove any currency symbols
    value_str = value_str.replace("$", "")

    try:
        return Decimal(value_str)
    except InvalidOperation:
        return None


def clean_text(text: str) -> str:
    """Clean extracted text by normalizing whitespace."""
    if not text:
        return ""
    # Replace multiple spaces with single space
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_property_number(text: str) -> Optional[str]:
    """Extract property number from property header line."""
    if not text:
        return None

    # Pattern: starts with digits, may contain letters
    match = re.match(r"^(\d+[A-Za-z0-9]*)", text.strip())
    if match:
        return match.group(1)
    return None


def extract_property_name(text: str) -> Optional[str]:
    """Extract property name from property header line."""
    if not text:
        return None

    # Remove property number from start
    text = re.sub(r"^\d+[A-Za-z0-9]*\s+", "", text.strip())

    # Remove state abbreviation from end (e.g., "DAWSON, TX")
    # Keep the county/location but remove ", TX" or similar
    return text.strip()


def generate_uid(check_number: str, property_number: str, line_number: int) -> str:
    """Generate a unique identifier for a revenue row."""
    check_part = check_number or "NOCHECK"
    prop_part = property_number or "NOPROP"
    return f"{check_part}-{prop_part}-{line_number:04d}"


def map_product_code(code: str) -> str:
    """Map product code to standard description."""
    product_map = {
        "101": "Oil",
        "201": "Gas",
        "400": "NGL",
        "O": "Oil",
        "G": "Gas",
    }
    return product_map.get(code, code)


def map_interest_type(code: str) -> str:
    """Map interest type code to description."""
    interest_map = {
        "RI": "Royalty",
        "WI": "Working Interest",
        "OR": "Override Royalty Interest",
        "MI": "Unleased Royalty Interest",
        "PP": "Production Payment",
    }
    return interest_map.get(code, code)


def map_tax_type(code: str) -> str:
    """Map tax code to description."""
    tax_map = {
        "SV": "Severance",
        "SC01": "Colorado Severance Tax",
        "SMT1": "Montana Mineral Royalty Backup WH",
        "SOK1": "Oklahoma Non-Resident Royalty WH",
        "SOK2": "Oklahoma Non-Resident Alien WH",
        "SND1": "North Dakota State WH",
        "SNM1": "New Mexico State NRT1 WH",
    }
    return tax_map.get(code, code)


def is_tax_row(int_code: str, ded_code: str) -> bool:
    """Determine if a row is a tax row based on codes."""
    return int_code == "SV" or ded_code == "SV"


def is_deduction_row(int_code: str, ded_code: str) -> bool:
    """Determine if a row is a deduction row based on codes."""
    return ded_code == "10" or (ded_code and ded_code not in ["SV", "RI"])

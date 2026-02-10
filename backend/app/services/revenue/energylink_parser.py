"""Parser for EnergyLink format revenue statements."""

import re
from typing import Optional

from app.models.revenue import RevenueRow, RevenueStatement, StatementFormat
from app.utils.helpers import parse_date, parse_decimal


def parse_energylink_statement(text: str, filename: str) -> RevenueStatement:
    """
    Parse an EnergyLink format revenue statement.

    Format characteristics:
    - Multi-page with header on each page
    - Check Date, Check Number, Owner Code, Owner Name in header
    - Property sections with property number and name
    - Line items: Sale Date, Prd, Int, Ded, BTU, Volume, Price, Value, Interest, Volume, Value
    """
    statement = RevenueStatement(
        filename=filename,
        format=StatementFormat.ENERGYLINK,
        rows=[],
        errors=[]
    )

    try:
        # Extract header information
        header_info = extract_header_info(text)
        statement.check_date = header_info.get("check_date")
        statement.check_number = header_info.get("check_number")
        statement.check_amount = header_info.get("check_amount")
        statement.owner_number = header_info.get("owner_code")
        statement.owner_name = header_info.get("owner_name")
        statement.payor = header_info.get("payor")
        statement.operator_name = header_info.get("payor")

        # Parse property sections and line items
        rows = parse_line_items(text)
        statement.rows = rows

    except Exception as e:
        statement.errors.append(f"Parsing error: {str(e)}")

    return statement


def extract_header_info(text: str) -> dict:
    """Extract header information from the statement."""
    info = {}

    # Check Date: 2/24/2025
    check_date_match = re.search(r"Check\s+Date:\s*(\d{1,2}/\d{1,2}/\d{4})", text, re.IGNORECASE)
    if check_date_match:
        info["check_date"] = parse_date(check_date_match.group(1))

    # Check Number: 005468
    check_num_match = re.search(r"Check\s+Number:\s*(\d+)", text, re.IGNORECASE)
    if check_num_match:
        info["check_number"] = check_num_match.group(1)

    # Owner Code: TAB001
    owner_code_match = re.search(r"Owner\s+Code:\s*([A-Za-z0-9]+)", text, re.IGNORECASE)
    if owner_code_match:
        info["owner_code"] = owner_code_match.group(1)

    # Owner Name: TABLE ROCK ENERGY, LLC
    owner_name_match = re.search(r"Owner\s+Name:\s*(.+?)(?:\n|$)", text, re.IGNORECASE)
    if owner_name_match:
        info["owner_name"] = owner_name_match.group(1).strip()

    # Extract payor from company name block
    payor_patterns = [
        r"(Hibernia\s+Resources[^,\n]*(?:,\s*LLC)?)",
        r"(Magnolia\s+Oil\s*&?\s*Gas[^,\n]*(?:,\s*LLC)?)",
        r"(Oxyrock\s+Operating[^,\n]*(?:,\s*LLC)?)",
        r"(Petro-Hunt[^,\n]*(?:,\s*LLC)?)",
    ]

    for pattern in payor_patterns:
        payor_match = re.search(pattern, text, re.IGNORECASE)
        if payor_match:
            info["payor"] = payor_match.group(1).strip()
            break

    # Extract check amount from footer
    net_value_match = re.search(r"Net\s+Value\s+([\d,]+\.?\d*)", text, re.IGNORECASE)
    if net_value_match:
        info["check_amount"] = parse_decimal(net_value_match.group(1))

    return info


def parse_line_items(text: str) -> list[RevenueRow]:
    """Parse line items from the statement text using token-based approach."""
    rows = []
    lines = text.split("\n")
    tokens = [line.strip() for line in lines if line.strip()]

    current_property_number = None
    current_property_name = None

    i = 0
    while i < len(tokens):
        token = tokens[i]

        # Check for property header (10-digit number)
        if re.match(r"^\d{10}$", token):
            current_property_number = token
            # Next token should be property name
            if i + 1 < len(tokens):
                current_property_name = tokens[i + 1]
                i += 2
                # Skip location line (e.g., "DAWSON, TX")
                if i < len(tokens) and re.match(r"^[A-Z]+,\s*[A-Z]{2}$", tokens[i]):
                    i += 1
            continue

        # Check for date pattern (e.g., "Dec 2024", "Sep 2024")
        if re.match(r"^[A-Za-z]{3}\s+\d{4}$", token):
            row = parse_row_from_tokens(tokens, i, current_property_number, current_property_name)
            if row:
                rows.append(row["row"])
                i = row["next_index"]
            else:
                i += 1
            continue

        # Skip other tokens
        i += 1

    return rows


def parse_row_from_tokens(
    tokens: list[str],
    start_index: int,
    property_number: Optional[str],
    property_name: Optional[str]
) -> Optional[dict]:
    """Parse a single row from tokens starting at the given index."""
    try:
        i = start_index

        # Date (e.g., "Dec 2024")
        if i >= len(tokens):
            return None
        sales_date = parse_date(tokens[i])
        i += 1

        # Product code (101, 201, 400)
        if i >= len(tokens):
            return None
        product_code = tokens[i]
        if not re.match(r"^\d{3}$", product_code):
            return None
        i += 1

        # Interest type or Tax/Deduct code (RI, SV, 10)
        if i >= len(tokens):
            return None
        code = tokens[i]
        i += 1

        interest_type = None
        tax_type = None
        deduct_code = None
        is_revenue_line = False
        is_tax_line = False
        is_deduct_line = False

        if code == "RI":
            interest_type = "RI"
            is_revenue_line = True
        elif code == "SV":
            tax_type = "SV"
            is_tax_line = True
        elif code == "10":
            deduct_code = "10"
            is_deduct_line = True
        else:
            # Unknown code, skip
            return None

        # For revenue lines (RI): BTU, Volume, Price, Value, Interest, OwnerVolume, OwnerValue
        # For tax/deduct lines (SV, 10): Value, Interest, OwnerValue
        _ = None  # BTU placeholder (parsed but not used)
        volume = None
        price = None
        property_value = None
        interest = None
        owner_volume = None
        owner_value = None

        if is_revenue_line:
            # BTU (e.g., "0.000") - skip, not used in M1 format
            if i < len(tokens):
                _ = parse_decimal(tokens[i])  # BTU - unused
                i += 1

            # Volume
            if i < len(tokens):
                volume = parse_decimal(tokens[i])
                i += 1

            # Price
            if i < len(tokens):
                price = parse_decimal(tokens[i])
                i += 1

            # Property Value
            if i < len(tokens):
                property_value = parse_decimal(tokens[i])
                i += 1

            # Interest decimal
            if i < len(tokens):
                interest = parse_decimal(tokens[i])
                i += 1

            # Owner Volume
            if i < len(tokens):
                owner_volume = parse_decimal(tokens[i])
                i += 1

            # Owner Value
            if i < len(tokens):
                owner_value = parse_decimal(tokens[i])
                i += 1

        else:
            # Tax or deduction line - fewer fields
            # Value (in parentheses for negative)
            if i < len(tokens):
                property_value = parse_decimal(tokens[i])
                i += 1

            # Interest decimal
            if i < len(tokens):
                interest = parse_decimal(tokens[i])
                i += 1

            # Owner Value (in parentheses for negative)
            if i < len(tokens):
                owner_value = parse_decimal(tokens[i])
                i += 1

        row = RevenueRow(
            property_name=property_name,
            property_number=property_number,
            sales_date=sales_date,
            product_code=product_code,
            decimal_interest=interest,
            interest_type=interest_type,
            avg_price=price,
            property_gross_volume=volume,
            property_gross_revenue=property_value,
            owner_volume=owner_volume,
            owner_value=owner_value if is_revenue_line else None,
            owner_tax_amount=owner_value if is_tax_line else None,
            tax_type=tax_type,
            owner_deduct_amount=owner_value if is_deduct_line else None,
            deduct_code=deduct_code,
        )

        return {"row": row, "next_index": i}

    except Exception:
        return None

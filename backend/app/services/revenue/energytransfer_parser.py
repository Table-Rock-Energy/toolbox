"""Parser for Energy Transfer format revenue statements."""

import re
from decimal import Decimal
from typing import Optional

from app.models.revenue import RevenueRow, RevenueStatement, StatementFormat
from app.utils.helpers import parse_date, parse_decimal


def parse_energy_transfer_statement(text: str, filename: str) -> RevenueStatement:
    """
    Parse an Energy Transfer format revenue statement.

    Format characteristics:
    - Simple 1-2 page tabular format
    - Property-level summaries (not transaction-level)
    - Header: Owner No, Name, Payment Date, Payment Number
    - Columns: County, State, Property, Property No., Sales Date, Product,
               Volume, Avg Price, Property Gross Value, State Tax, Gross Deducts,
               Property Net Value, Owner Interest, IT, Owner Gross Value, State Tax,
               Adj Code, Adj Value, Owner Net Value
    """
    statement = RevenueStatement(
        filename=filename,
        format=StatementFormat.ENERGY_TRANSFER,
        rows=[],
        errors=[]
    )

    try:
        # Extract header information
        header_info = extract_header_info(text)
        statement.check_date = header_info.get("payment_date")
        statement.check_number = header_info.get("payment_number")
        statement.owner_number = header_info.get("owner_number")
        statement.owner_name = header_info.get("owner_name")
        statement.payor = "Energy Transfer Crude Marketing, LLC"
        statement.operator_name = "Energy Transfer Crude Marketing, LLC"

        # Parse property rows
        rows = parse_table_rows(text)
        statement.rows = rows

        # Extract totals for check amount
        totals = extract_totals(text)
        if totals.get("net_value"):
            statement.check_amount = totals["net_value"]

    except Exception as e:
        statement.errors.append(f"Parsing error: {str(e)}")

    return statement


def extract_header_info(text: str) -> dict:
    """Extract header information from Energy Transfer statement."""
    info = {}

    # Owner No: 1000388295
    owner_no_match = re.search(r"Owner\s+No:?\s*(\d+)", text, re.IGNORECASE)
    if owner_no_match:
        info["owner_number"] = owner_no_match.group(1)

    # Name: TABLE ROCK ENERGY LLC
    name_match = re.search(r"Name:\s*(.+?)(?:\n|Owner|$)", text, re.IGNORECASE)
    if name_match:
        info["owner_name"] = name_match.group(1).strip()

    # Payment Date: 01/16/2026
    payment_date_match = re.search(r"Payment\s+Date:\s*(\d{1,2}/\d{1,2}/\d{4})", text, re.IGNORECASE)
    if payment_date_match:
        info["payment_date"] = parse_date(payment_date_match.group(1))

    # Payment Number: E000000310015
    payment_num_match = re.search(r"Payment\s+Number:\s*([A-Za-z0-9]+)", text, re.IGNORECASE)
    if payment_num_match:
        info["payment_number"] = payment_num_match.group(1)

    return info


def parse_table_rows(text: str) -> list[RevenueRow]:
    """Parse property rows from the statement."""
    rows = []
    lines = text.split("\n")

    # State/County tracking
    current_county = None
    current_state = None

    # Pattern to identify data rows
    # Format varies but typically: Property Name, Property No., Date, Product, Volume, Price, etc.

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Skip header lines and codes section
        if any(skip in line.lower() for skip in [
            "county", "state", "property", "sales date", "product", "volume",
            "adjustment codes", "withholding", "interest types", "totals",
            "energy transfer crude marketing", "p.o. box", "houston",
            "page", "owner no", "payment"
        ]):
            # Check if this is a state/county header
            state_match = re.match(r"^([A-Z]{2})$", line)
            if state_match:
                current_state = state_match.group(1)
            continue

        # Try to parse as a data row
        row = parse_data_line(line, current_county, current_state)
        if row:
            rows.append(row)

    return rows


def parse_data_line(line: str, county: Optional[str], state: Optional[str]) -> Optional[RevenueRow]:
    """Parse a single data line into a RevenueRow."""
    # Energy Transfer format example:
    # ECHOLS 1    056711-00001    12/25    O    180.54    55.97    10,105.15    465.97    0.00    9,639.18    0.00078125 RI    7.89    0.36    7.53

    # Split by whitespace but be careful with property names that have spaces
    parts = line.split()

    if len(parts) < 10:
        return None

    try:
        # Try to identify the structure
        # Look for property number pattern (digits-digits)
        prop_num_idx = None
        for i, part in enumerate(parts):
            if re.match(r"^\d+-\d+$", part) or re.match(r"^\d{6,}-\d+$", part):
                prop_num_idx = i
                break

        if prop_num_idx is None:
            return None

        # Property name is everything before the property number
        property_name = " ".join(parts[:prop_num_idx])
        property_number = parts[prop_num_idx]

        # Remaining parts after property number
        remaining = parts[prop_num_idx + 1:]

        if len(remaining) < 8:
            return None

        # Parse date (MM/YY format)
        sales_date_str = remaining[0]
        sales_date = parse_date(sales_date_str)

        # Product code (O = Oil, G = Gas)
        product_code = remaining[1]

        # Volume
        volume = parse_decimal(remaining[2])

        # Average price
        avg_price = parse_decimal(remaining[3])

        # Property gross value
        property_gross_value = parse_decimal(remaining[4])

        # State tax (property-level, not owner-level - parsed but not used directly)
        _ = parse_decimal(remaining[5])  # state_tax at property level

        # Gross deducts (property-level)
        _ = parse_decimal(remaining[6])  # gross_deducts at property level

        # Property net value (property-level)
        _ = parse_decimal(remaining[7])  # property_net_value - using owner values instead

        # Owner interest and type
        owner_interest = None
        interest_type = None
        owner_gross = None
        owner_tax = None
        adj_code = None
        adj_value = None
        owner_net = None

        if len(remaining) > 8:
            owner_interest = parse_decimal(remaining[8])

        if len(remaining) > 9:
            interest_type = remaining[9]

        if len(remaining) > 10:
            owner_gross = parse_decimal(remaining[10])

        if len(remaining) > 11:
            owner_tax = parse_decimal(remaining[11])

        if len(remaining) > 12:
            adj_code = remaining[12] if not remaining[12].replace(".", "").replace("-", "").isdigit() else None

        if len(remaining) > 13:
            adj_value = parse_decimal(remaining[13])

        if len(remaining) > 14:
            owner_net = parse_decimal(remaining[14])
        elif len(remaining) > 13 and adj_code is None:
            owner_net = parse_decimal(remaining[13])

        # Map product code
        product_desc = {
            "O": "Oil",
            "G": "Gas",
        }.get(product_code, product_code)

        row = RevenueRow(
            property_name=property_name,
            property_number=property_number,
            sales_date=sales_date,
            product_code=product_code,
            product_description=product_desc,
            decimal_interest=owner_interest,
            interest_type=interest_type,
            avg_price=avg_price,
            property_gross_volume=volume,
            property_gross_revenue=property_gross_value,
            owner_volume=volume * owner_interest if volume and owner_interest else None,
            owner_value=owner_gross,
            owner_tax_amount=owner_tax,
            tax_type="State Tax" if owner_tax and owner_tax != Decimal("0") else None,
            owner_deduct_amount=adj_value,
            deduct_code=adj_code,
            owner_net_revenue=owner_net,
        )

        return row
    except Exception:
        return None


def extract_totals(text: str) -> dict:
    """Extract totals from the statement footer."""
    totals = {}

    # Look for "Totals" line
    totals_match = re.search(
        r"Totals\s+([\d,.]+)\s+([\d,.]+)\s+([\d,.]+)\s+([\d,.]+)",
        text,
        re.IGNORECASE
    )

    if totals_match:
        totals["gross_value"] = parse_decimal(totals_match.group(1))
        totals["tax"] = parse_decimal(totals_match.group(2))
        totals["deductions"] = parse_decimal(totals_match.group(3))
        totals["net_value"] = parse_decimal(totals_match.group(4))

    return totals

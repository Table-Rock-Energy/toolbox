"""Parser for Enverus/EnergyLink web-generated PDF revenue statements.

Handles tabular layouts from Magnolia, Oxyrock, and Petro-Hunt operators
using positional text extraction via PyMuPDF dict mode.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from app.models.revenue import RevenueRow, RevenueStatement, StatementFormat
from app.services.revenue.enverus_layout import EnverusColumnLayout, detect_layout
from app.services.revenue.pdf_extractor import TextSpan, extract_spans_by_page
from app.utils.helpers import map_product_code, parse_date, parse_decimal

logger = logging.getLogger(__name__)

# Y-tolerance for grouping spans into the same logical row
ROW_Y_TOLERANCE = 3.0


def parse_enverus_statement(pdf_bytes: bytes, filename: str) -> RevenueStatement:
    """Parse an Enverus web-generated revenue statement from raw PDF bytes.

    Uses positional extraction: extracts text spans with (x, y) coordinates,
    auto-detects column layout from page 1 headers, then reads data rows
    by assigning spans to columns based on x-position.
    """
    statement = RevenueStatement(
        filename=filename,
        format=StatementFormat.ENVERUS,
        rows=[],
        errors=[],
    )

    try:
        pages = extract_spans_by_page(pdf_bytes)
        if not pages:
            statement.errors.append("No text spans extracted from PDF")
            return statement

        # Detect column layout from page 0
        page0_spans = pages.get(0, [])
        layout = detect_layout(page0_spans)
        if layout is None:
            statement.errors.append("Could not detect column layout from headers")
            return statement

        logger.debug(f"Detected columns: {list(layout.columns.keys())}")

        # Extract header info from page 0
        header = _extract_header(page0_spans, layout)
        statement.check_date = header.get("check_date")
        statement.check_number = header.get("check_number")
        statement.check_amount = header.get("check_amount")
        statement.owner_number = header.get("owner_code")
        statement.owner_name = header.get("owner_name")
        statement.payor = header.get("operator_name")
        statement.operator_name = header.get("operator_name")

        # Parse data rows from all pages, carrying property context across pages
        page_ctx: dict[str, Optional[str]] = {}
        for page_num in sorted(pages.keys()):
            page_spans = pages[page_num]
            rows, page_ctx = _parse_page_rows(page_spans, layout, page_ctx)
            statement.rows.extend(rows)

    except Exception as e:
        statement.errors.append(f"Parsing error: {e!s}")
        logger.exception(f"Failed to parse Enverus statement: {filename}")

    return statement


def _extract_header(spans: list[TextSpan], layout: EnverusColumnLayout) -> dict:
    """Extract header fields (owner, operator, check info) from page 0 spans.

    Enverus headers have a 3-column layout:
    - Left (x≈24): "Owner" label, then owner code, name, address below
    - Middle (x≈282): "Operator" label, then operator code, name below
    - Right (x≈546): Check Number, Check Amount, Check Date with values to right
    """
    info: dict = {}

    # Only consider spans in the header area (above y=170, before copyright notice)
    header_spans = [s for s in spans if s.y0 < 170]
    sorted_spans = sorted(header_spans, key=lambda s: (s.y0, s.x0))

    # Extract check info: label on left, value on right (same y)
    for span in sorted_spans:
        text = span.text.strip()
        text_lower = text.lower()

        if text_lower in ("check number", "check number:"):
            val = _find_value_right_of(span, sorted_spans)
            if val:
                info["check_number"] = val.strip()

        elif text_lower in ("check date", "check date:"):
            val = _find_value_right_of(span, sorted_spans)
            if val:
                info["check_date"] = parse_date(val.strip())

        elif text_lower in ("check amount", "check amount:"):
            val = _find_value_right_of(span, sorted_spans)
            if val:
                amt = parse_decimal(val.strip())
                if amt is not None:
                    info["check_amount"] = float(amt)

    # Extract owner/operator from vertical layout below their labels
    # Find "Owner" and "Operator" section labels
    owner_label_y: Optional[float] = None
    operator_label_y: Optional[float] = None
    owner_x_range = (0, 200)  # Owner section is leftmost
    operator_x_range = (200, 500)  # Operator section is middle

    for span in sorted_spans:
        text = span.text.strip()
        if text == "Owner" and span.x0 < 100:
            owner_label_y = span.y0
        elif text == "Operator" and 200 < span.x0 < 500:
            operator_label_y = span.y0

    # Owner info: spans below "Owner" label in the left column
    if owner_label_y is not None:
        owner_spans = [
            s for s in sorted_spans
            if s.y0 > owner_label_y + 5
            and owner_x_range[0] <= s.x0 <= owner_x_range[1]
        ]
        owner_spans.sort(key=lambda s: s.y0)
        if owner_spans:
            # First span below is owner code
            info["owner_code"] = owner_spans[0].text.strip()
            # Second span is owner name (if it's text, not an address)
            if len(owner_spans) > 1:
                name = owner_spans[1].text.strip()
                # Verify it looks like a name (not a number or address starting with digits)
                if name and not re.match(r"^\d", name):
                    info["owner_name"] = name

    # Operator info: spans below "Operator" label in the middle column
    if operator_label_y is not None:
        op_spans = [
            s for s in sorted_spans
            if s.y0 > operator_label_y + 5
            and operator_x_range[0] <= s.x0 <= operator_x_range[1]
        ]
        op_spans.sort(key=lambda s: s.y0)
        if op_spans:
            # First span below is operator code, skip it
            # Find the first span that looks like a company name
            for s in op_spans:
                text = s.text.strip()
                if text and not re.match(r"^\d", text) and len(text) > 5:
                    info["operator_name"] = text
                    break

    # Fallback: extract operator from known patterns anywhere on page
    if "operator_name" not in info:
        for span in spans:
            text = span.text.strip()
            if re.search(r"(?i)(magnolia|oxyrock|petro-hunt|hibernia)", text):
                info["operator_name"] = text
                break

    return info


def _find_value_right_of(label_span: TextSpan, all_spans: list[TextSpan]) -> Optional[str]:
    """Find the text value immediately to the right of a label on the same row."""
    for span in all_spans:
        if span is label_span:
            continue
        # Same row (within y tolerance) and to the right
        if abs(span.y0 - label_span.y0) < ROW_Y_TOLERANCE and span.x0 > label_span.x1 - 5:
            return span.text.strip()
    return None


def _parse_page_rows(
    spans: list[TextSpan],
    layout: EnverusColumnLayout,
    ctx: Optional[dict[str, Optional[str]]] = None,
) -> tuple[list[RevenueRow], dict[str, Optional[str]]]:
    """Parse data rows from a single page's spans.

    Accepts and returns a context dict to carry property/product state across pages.
    """
    rows: list[RevenueRow] = []

    # Only consider spans below the header row
    data_spans = [s for s in spans if s.y0 > layout.header_y + 10]
    if not data_spans:
        return rows, ctx or {}

    # Group spans into logical rows by y-position
    logical_rows = _group_into_rows(data_spans)

    # Track current property context (carry over from previous page)
    current_property_no: Optional[str] = (ctx or {}).get("property_no")
    current_property_name: Optional[str] = (ctx or {}).get("property_name")
    current_product: Optional[str] = (ctx or {}).get("product")
    current_interest_type: Optional[str] = (ctx or {}).get("interest_type")
    # For multi-line property headers (Petro-Hunt): property number on one row,
    # name/state on the next row
    pending_property_name: bool = False

    for row_spans in logical_rows:
        row_text = " ".join(s.text for s in row_spans)
        row_text_lower = row_text.lower().strip()

        # Skip known non-data rows
        if _is_skip_row(row_text_lower):
            pending_property_name = False
            continue

        # Handle multi-line property: previous row set property number,
        # this row should have the property name (e.g. "COPPERHEAD 53-14 1H")
        # or "State: TX, County: LOVING"
        if pending_property_name:
            pending_property_name = False
            # Check if this row is a State/County continuation
            state_match = re.match(r"State:\s*\w+", row_text, re.IGNORECASE)
            if state_match:
                # State-only continuation row — property name stays as-is from number row
                continue
            # Check if this row has name + state (e.g. "COPPERHEAD 53-14 1H, State: TX...")
            name_state = re.match(r"(.+?),\s*State:", row_text, re.IGNORECASE)
            if name_state:
                current_property_name = name_state.group(1).strip()
                continue
            # Otherwise treat entire row text as property name if it's not
            # a product label or numeric data
            if not _extract_standalone_product(row_text) and not re.match(
                r"^[\d,.\-()]+$", row_text.replace(" ", "")
            ):
                current_property_name = row_text.strip()
                continue

        # Check for property header line
        # Petro-Hunt/Oxyrock: "Property: 329*28097 COPPERHEAD 53-14 1H, State: TX..."
        # Magnolia: "422103106 JOHN DIETZ #2, State: TX, County: WASHINGTON"
        prop_match = re.search(
            r"property\s*:?\s*(\S+)\s+(.*?,\s*State:.*)", row_text, re.IGNORECASE
        )
        if not prop_match:
            # Try number-only property header (Magnolia style)
            prop_match = re.search(
                r"^(\d{5,})\s+(.*?,\s*State:.*)", row_text, re.IGNORECASE
            )
        if prop_match:
            current_property_no = prop_match.group(1)
            current_property_name = prop_match.group(2).strip()
            current_product = None
            current_interest_type = None
            continue

        # Fallback: "Property: NUMBER NAME" without ", State:" on same row
        # (Petro-Hunt multi-line headers)
        if not prop_match:
            partial_match = re.search(
                r"property\s*:\s*(\S+)\s*(.*)", row_text, re.IGNORECASE
            )
            if partial_match:
                current_property_no = partial_match.group(1)
                name_part = partial_match.group(2).strip()
                if name_part:
                    current_property_name = name_part
                else:
                    current_property_name = None
                current_product = None
                current_interest_type = None
                pending_property_name = not bool(name_part)
                continue

            # Number-only property header without ", State:" (e.g. "329*28097")
            num_only = re.match(r"^(\d[\d*]+)$", row_text.strip())
            if num_only and len(row_text.strip()) >= 5:
                current_property_no = num_only.group(1)
                current_property_name = None
                current_product = None
                current_interest_type = None
                pending_property_name = True
                continue

        # Check for standalone product name (e.g., "GAS", "OIL", "CONDENSATE")
        # These appear on their own line above the data rows
        standalone_product = _extract_standalone_product(row_text)
        if standalone_product:
            current_product = standalone_product
            current_interest_type = None  # reset until we see interest type
            continue

        # Check for combined product/interest type label rows
        # e.g., "GAS ROYALTY INTEREST" or "OIL WI" or "CONDENSATE WI REJLOD"
        product_label = _extract_product_label(row_text)
        if product_label:
            current_product = product_label["product"]
            current_interest_type = product_label["interest_type"]
            continue

        # Check for tax/deduction label rows
        tax_label = _extract_tax_label(row_text)
        if tax_label:
            current_interest_type = tax_label
            continue

        # Try to parse as a data row
        row = _parse_data_row(
            row_spans,
            layout,
            current_property_no,
            current_property_name,
            current_product,
            current_interest_type,
        )
        if row:
            rows.append(row)

    return rows, {
        "property_no": current_property_no,
        "property_name": current_property_name,
        "product": current_product,
        "interest_type": current_interest_type,
    }


def _group_into_rows(spans: list[TextSpan]) -> list[list[TextSpan]]:
    """Group spans into logical rows by y-coordinate proximity."""
    if not spans:
        return []

    sorted_spans = sorted(spans, key=lambda s: (s.y0, s.x0))
    rows: list[list[TextSpan]] = []
    current_row: list[TextSpan] = [sorted_spans[0]]
    current_y = sorted_spans[0].y0

    for span in sorted_spans[1:]:
        if abs(span.y0 - current_y) <= ROW_Y_TOLERANCE:
            current_row.append(span)
        else:
            # Sort by x-position for left-to-right reading order within the row.
            # Spans grouped by y-proximity may have slightly different y0 values,
            # causing incorrect ordering when sorted by (y0, x0).
            current_row.sort(key=lambda s: s.x0)
            rows.append(current_row)
            current_row = [span]
            current_y = span.y0

    if current_row:
        current_row.sort(key=lambda s: s.x0)
        rows.append(current_row)

    return rows


def _is_skip_row(text_lower: str) -> bool:
    """Check if a row should be skipped (totals, headers, footers, etc)."""
    skip_patterns = [
        "total",
        "page ",
        "price after deductions",
        "property no",
        "sales date",
        "sale date",
        "continued",
        "energylink",
        "www.energylink",
        "enverus",
        "owner code",
        "check number",
        "check date",
        "check amount",
        "owner name",
        "owner no",
        "product codes",
        "interest codes",
        "tax codes",
        "deduct codes",
    ]
    for pattern in skip_patterns:
        if pattern in text_lower:
            return True
    return False


# Product patterns: product name followed by optional interest type
_PRODUCT_PATTERNS = [
    # "GAS ROYALTY INTEREST" -> product=GAS, interest=RI
    (r"^(GAS|OIL|CONDENSATE|PLANT\s+PRODUCTS|NGL|RESIDUE\s+GAS|OIL\s+WELL\s+OIL|"
     r"GAS\s+DELIVERED\s+TO\s+PLANT|LEASE\s+USE[-\s]MKT\s+EQ|"
     r"LNG\s+WITH\s+NO\s+DETERMINED\s+BREAKDOWN|SKIM\s+FROM\s+GAS\s+WELL)"
     r"\s+ROYALTY\s+INTEREST",
     "RI"),
    # "GAS WI" or "OIL WI SOMETHING"
    (r"^(GAS|OIL|CONDENSATE|PLANT\s+PRODUCTS|NGL|RESIDUE\s+GAS|OIL\s+WELL\s+OIL|"
     r"GAS\s+DELIVERED\s+TO\s+PLANT|LEASE\s+USE[-\s]MKT\s+EQ|"
     r"LNG\s+WITH\s+NO\s+DETERMINED\s+BREAKDOWN|SKIM\s+FROM\s+GAS\s+WELL)"
     r"\s+WI(?:\s+|$)",
     "WI"),
    # "GAS OVERRIDING ROYALTY INTEREST"
    (r"^(GAS|OIL|CONDENSATE|PLANT\s+PRODUCTS|NGL|RESIDUE\s+GAS)"
     r"\s+OVERRIDING\s+ROYALTY\s+INTEREST",
     "OR"),
]


# Standalone product names (appear on their own line in Petro-Hunt/Oxyrock)
_STANDALONE_PRODUCTS = {
    "gas", "oil", "condensate", "plant products", "ngl",
    "residue gas", "oil well oil", "gas delivered to plant",
    "lease use-mkt eq", "lng with no determined breakdown",
    "skim from gas well",
}


def _extract_standalone_product(text: str) -> Optional[str]:
    """Check if a row is a standalone product name like 'GAS' or 'OIL'."""
    text_stripped = text.strip()
    if text_stripped.lower() in _STANDALONE_PRODUCTS:
        return map_product_code(text_stripped)
    return None


def _extract_product_label(text: str) -> Optional[dict]:
    """Extract product name and interest type from a label row."""
    text_stripped = text.strip()
    for pattern, interest_code in _PRODUCT_PATTERNS:
        match = re.match(pattern, text_stripped, re.IGNORECASE)
        if match:
            raw_product = match.group(1).strip()
            return {
                "product": map_product_code(raw_product),
                "interest_type": interest_code,
            }
    return None


_TAX_PATTERNS = [
    r"(?i)^(PRODUCTION\s+TAX|SEVERANCE\s+TAX|COMPRESSION|GATHERING|TRANSPORTATION|"
    r"MARKETING|PROCESSING|DEHYDRATION|TREATING)",
]


def _extract_tax_label(text: str) -> Optional[str]:
    """Check if text is a tax/deduction label. Returns the tax type string."""
    text_stripped = text.strip()
    for pattern in _TAX_PATTERNS:
        if re.match(pattern, text_stripped):
            return text_stripped.upper()
    return None


def _parse_data_row(
    row_spans: list[TextSpan],
    layout: EnverusColumnLayout,
    property_no: Optional[str],
    property_name: Optional[str],
    product: Optional[str],
    interest_type: Optional[str],
) -> Optional[RevenueRow]:
    """Parse a data row by assigning spans to columns based on x-position."""
    # A data row must have numeric values - check if we have at least 2 numbers
    numeric_count = sum(
        1 for s in row_spans
        if re.match(r"^[\d,.\-()]+$", s.text.replace(" ", ""))
    )
    if numeric_count < 2:
        return None

    # Assign each span to its column
    col_values: dict[str, str] = {}
    for span in row_spans:
        col = layout.assign_span_to_column(span)
        if col:
            col_values[col] = span.text.strip()

    if not col_values:
        return None

    # Extract sales date
    sales_date = None
    date_str = col_values.get("sales_date", "")
    if date_str:
        sales_date = parse_date(date_str)

    # Extract interest type from column if present
    col_interest = col_values.get("interest_type", "").strip()
    # Map common interest type text to codes
    if col_interest.upper() in ("ROYALTY INTEREST", "RI"):
        row_interest_type = "RI"
    elif col_interest.upper() in ("WI", "WORKING INTEREST"):
        row_interest_type = "WI"
    elif col_interest.upper() in ("OR", "OVERRIDING ROYALTY", "OVERRIDING ROYALTY INTEREST"):
        row_interest_type = "OR"
    elif col_interest:
        row_interest_type = col_interest
    else:
        row_interest_type = interest_type

    # Extract tax/deduct code from column (Magnolia has a dedicated column)
    col_tax_deduct = col_values.get("tax_deduct_code", "").strip()

    # Determine if this is a tax/deduction-only row.
    # In Magnolia-style layouts (which have taxes_deductions columns), each row is
    # a complete record with inline T&D — so they're NOT treated as tax-only rows.
    # In Petro-Hunt/Oxyrock layouts, taxes ARE separate rows.
    has_inline_td = "taxes_deductions" in layout.columns or "owner_taxes_deductions" in layout.columns
    is_tax = False
    tax_type = None
    deduct_code = None

    # For Petro-Hunt/Oxyrock: check from tracked interest type (separate tax rows)
    if not has_inline_td and interest_type and re.match(
        r"(?i)(PRODUCTION TAX|SEVERANCE TAX|COMPRESSION|"
        r"GATHERING|TRANSPORTATION|MARKETING|PROCESSING|"
        r"DEHYDRATION|TREATING)",
        interest_type,
    ):
        is_tax = True
        if "TAX" in interest_type.upper():
            tax_type = "SV"
        else:
            deduct_code = "10"

    # Parse numeric fields
    owner_interest = _parse_float(col_values.get("owner_interest"))
    dist_interest = _parse_float(col_values.get("dist_interest"))
    decimal_interest = owner_interest or dist_interest

    volume = _parse_float(col_values.get("volume"))
    price = _parse_float(col_values.get("price"))
    value = _parse_float(col_values.get("value"))
    owner_volume = _parse_float(col_values.get("owner_volume"))
    owner_value = _parse_float(col_values.get("owner_value"))
    owner_net_value = _parse_float(col_values.get("owner_net_value"))

    # Tax and deduction amounts (Magnolia has dedicated columns)
    tax_amount = _parse_float(
        col_values.get("taxes_deductions")
        or col_values.get("tax_amount")
    )
    deduction_amount = _parse_float(col_values.get("deductions"))
    owner_tax_deduct = _parse_float(col_values.get("owner_taxes_deductions"))
    owner_net_from_col = _parse_float(col_values.get("owner_net_value"))

    # Build the row
    if is_tax:
        return RevenueRow(
            property_name=property_name,
            property_number=property_no,
            sales_date=sales_date,
            product_code=product,
            decimal_interest=decimal_interest,
            interest_type=row_interest_type,
            property_gross_revenue=value,
            owner_tax_amount=owner_tax_deduct or owner_value if tax_type else None,
            tax_type=tax_type,
            owner_deduct_amount=owner_tax_deduct or owner_value if deduct_code else None,
            deduct_code=deduct_code,
        )

    # For Magnolia inline T&D: use the tax_deduct_code column for tax/deduct info
    row_tax_type = None
    row_deduct_code = None
    row_tax_amount = owner_tax_deduct if owner_tax_deduct else tax_amount
    row_deduct_amount = deduction_amount

    if col_tax_deduct:
        if col_tax_deduct.upper() in ("ST", "SEVSAV"):
            row_tax_type = "SV"
        elif col_tax_deduct.upper() not in ("", "RI", "WI", "OR"):
            row_deduct_code = col_tax_deduct
    elif row_tax_amount:
        row_tax_type = "SV"
    if row_deduct_amount and not row_deduct_code:
        row_deduct_code = "10"

    # Owner net revenue: prefer column value, then fall back to calculation
    computed_owner_net = owner_net_from_col or owner_net_value
    if computed_owner_net is None and owner_value is not None:
        computed_owner_net = _compute_owner_net(owner_value, row_tax_amount, row_deduct_amount)

    return RevenueRow(
        property_name=property_name,
        property_number=property_no,
        sales_date=sales_date,
        product_code=product,
        decimal_interest=decimal_interest,
        interest_type=row_interest_type,
        avg_price=price,
        property_gross_volume=volume,
        property_gross_revenue=value,
        owner_volume=owner_volume,
        owner_value=owner_value,
        owner_tax_amount=row_tax_amount,
        tax_type=row_tax_type,
        owner_deduct_amount=row_deduct_amount,
        deduct_code=row_deduct_code,
        owner_net_revenue=computed_owner_net,
    )


def _compute_owner_net(
    owner_value: float,
    tax_amount: Optional[float],
    deduct_amount: Optional[float],
) -> float:
    """Compute owner net revenue as owner_value minus taxes and deductions.

    For Petro-Hunt revenue rows (where taxes are separate rows), tax_amount
    and deduct_amount will be None/0, so this returns owner_value as-is.
    """
    return owner_value - (tax_amount or 0) - (deduct_amount or 0)


def _parse_float(value: Optional[str]) -> Optional[float]:
    """Parse a string value to float, handling parentheses for negatives."""
    if not value:
        return None
    d = parse_decimal(value)
    if d is not None:
        return float(d)
    return None

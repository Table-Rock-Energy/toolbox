"""Gemini-based revenue statement parser.

Uses Gemini 2.5 Flash to extract structured revenue data from PDF text,
replacing format-specific regex parsers. Falls back to traditional parsers
when Gemini is disabled or fails.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import date
from typing import TYPE_CHECKING, Any

from app.core.config import settings
from app.models.revenue import RevenueRow, RevenueStatement, StatementFormat

if TYPE_CHECKING:
    from google.genai import Client

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert oil and gas revenue statement parser. Your job is to extract structured data from the raw text of PDF revenue statements.

These statements come from operators like EnergyLink/Hibernia, Enverus, and Energy Transfer. They contain:
- Header info: payor/operator name, check number, check amount, check date, owner name/number
- Line items: each row represents a revenue entry, tax deduction, or processing deduction for a specific property and sales period

IMPORTANT CONVENTIONS:
- Product codes: "101" = Oil, "201" = Gas, "301" = NGL/Condensate, "400" = Plant Products. Some statements use text like "OIL", "GAS", "COND".
- Interest types: "RI" = Royalty Interest, "WI" = Working Interest, "OR" = Overriding Royalty, "NRI" = Net Revenue Interest
- Tax types: "SV" = Severance Tax, "CT" = Conservation Tax
- Deduction codes: "10" or similar numeric codes for gathering/transportation/processing deductions
- decimal_interest is a decimal between 0 and 1 (e.g., 0.00520833)
- Dates: sales_date is the production month (e.g., "Dec 2024" = 2024-12-01). Always use the first day of the month.
- Negative amounts: parentheses mean negative, e.g., "(1.23)" = -1.23. Taxes and deductions are typically negative.
- owner_net_revenue: may not be explicitly listed per row; include it if available
- check_amount: the total check/payment amount, usually found in the header or footer

NUMBER PRECISION: Preserve the exact precision from the document. If it says "0.00520833", output 0.00520833, not 0.005. Financial values should have 2 decimal places. Volumes can have varying precision.

OUTPUT: Return a JSON object matching the schema provided. Include ALL line items from the statement - revenue lines, tax lines, and deduction lines. Each gets its own row."""

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "payor": {"type": ["string", "null"]},
        "check_number": {"type": ["string", "null"]},
        "check_amount": {"type": ["number", "null"]},
        "check_date": {"type": ["string", "null"], "description": "ISO date YYYY-MM-DD"},
        "operator_name": {"type": ["string", "null"]},
        "owner_number": {"type": ["string", "null"]},
        "owner_name": {"type": ["string", "null"]},
        "rows": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "property_name": {"type": ["string", "null"]},
                    "property_number": {"type": ["string", "null"]},
                    "sales_date": {"type": ["string", "null"], "description": "ISO date YYYY-MM-DD (first of month)"},
                    "product_code": {"type": ["string", "null"]},
                    "product_description": {"type": ["string", "null"]},
                    "decimal_interest": {"type": ["number", "null"]},
                    "interest_type": {"type": ["string", "null"]},
                    "avg_price": {"type": ["number", "null"]},
                    "property_gross_volume": {"type": ["number", "null"]},
                    "property_gross_revenue": {"type": ["number", "null"]},
                    "owner_volume": {"type": ["number", "null"]},
                    "owner_value": {"type": ["number", "null"]},
                    "owner_tax_amount": {"type": ["number", "null"]},
                    "tax_type": {"type": ["string", "null"]},
                    "owner_deduct_amount": {"type": ["number", "null"]},
                    "deduct_code": {"type": ["string", "null"]},
                    "owner_net_revenue": {"type": ["number", "null"]},
                },
            },
        },
    },
    "required": ["rows"],
}


def _parse_date(value: Any) -> date | None:
    """Parse an ISO date string to a date object."""
    if not value or not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _build_statement(data: dict, filename: str) -> RevenueStatement:
    """Convert Gemini JSON response into a RevenueStatement model."""
    rows = []
    for r in data.get("rows", []):
        rows.append(RevenueRow(
            property_name=r.get("property_name"),
            property_number=r.get("property_number"),
            sales_date=_parse_date(r.get("sales_date")),
            product_code=r.get("product_code"),
            product_description=r.get("product_description"),
            decimal_interest=r.get("decimal_interest"),
            interest_type=r.get("interest_type"),
            avg_price=r.get("avg_price"),
            property_gross_volume=r.get("property_gross_volume"),
            property_gross_revenue=r.get("property_gross_revenue"),
            owner_volume=r.get("owner_volume"),
            owner_value=r.get("owner_value"),
            owner_tax_amount=r.get("owner_tax_amount"),
            tax_type=r.get("tax_type"),
            owner_deduct_amount=r.get("owner_deduct_amount"),
            deduct_code=r.get("deduct_code"),
            owner_net_revenue=r.get("owner_net_revenue"),
        ))

    return RevenueStatement(
        filename=filename,
        format=StatementFormat.UNKNOWN,  # Gemini doesn't know the format enum
        payor=data.get("payor"),
        check_number=data.get("check_number"),
        check_amount=data.get("check_amount"),
        check_date=_parse_date(data.get("check_date")),
        operator_name=data.get("operator_name"),
        owner_number=data.get("owner_number"),
        owner_name=data.get("owner_name"),
        rows=rows,
        errors=[],
    )


def _parse_gemini_sync(client: Client, text: str, filename: str) -> RevenueStatement:
    """Run the Gemini API call synchronously (called from thread)."""
    from google.genai import types

    from app.services.gemini_service import _check_rate_limit, _record_request, _record_spend

    allowed, remaining_minute, remaining_day = _check_rate_limit()
    if not allowed:
        raise RuntimeError(
            f"Gemini rate limited (RPM remaining: {remaining_minute}, RPD remaining: {remaining_day})"
        )

    user_prompt = f"""Extract all revenue data from this statement text. Return a JSON object matching the schema.

Statement from file: {filename}

--- BEGIN STATEMENT TEXT ---
{text}
--- END STATEMENT TEXT ---"""

    _record_request()
    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_json_schema=RESPONSE_SCHEMA,
            temperature=0.0,
        ),
    )

    if hasattr(response, "usage_metadata") and response.usage_metadata:
        _record_spend(
            response.usage_metadata.prompt_token_count or 0,
            response.usage_metadata.candidates_token_count or 0,
        )

    data = json.loads(response.text)
    statement = _build_statement(data, filename)

    logger.info(
        f"Gemini extracted {len(statement.rows)} rows from {filename}"
    )
    return statement


async def gemini_parse_revenue(text: str, filename: str) -> RevenueStatement:
    """Parse a revenue statement using Gemini AI.

    Runs the synchronous Gemini call in a thread to avoid blocking the event loop.

    Raises:
        RuntimeError: If rate limited or Gemini is not enabled.
        Exception: On any Gemini API or parsing failure.
    """
    from app.services.gemini_service import _get_client

    if not settings.use_gemini:
        raise RuntimeError("Gemini is not enabled")

    client = _get_client()
    return await asyncio.to_thread(_parse_gemini_sync, client, text, filename)

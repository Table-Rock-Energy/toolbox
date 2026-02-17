"""Export service for generating CSV files in M1 Upload format."""

from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Any

import pandas as pd

from app.models.revenue import M1_COLUMNS, RevenueStatement
from app.services.revenue.m1_transformer import get_m1_row_as_dict, transform_to_m1
from app.services.shared.export_utils import (
    MINERAL_EXPORT_COLUMNS,
    dataframe_to_csv_bytes,
)


def export_to_csv(statements: list[RevenueStatement]) -> tuple[str, str, int]:
    """
    Export revenue statements to M1 Upload CSV format.

    Args:
        statements: List of parsed revenue statements

    Returns:
        Tuple of (csv_content, filename, row_count)
    """
    # Transform to M1 format
    m1_rows = transform_to_m1(statements)

    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"m1_upload_{timestamp}.csv"

    # Create CSV content with UTF-8 BOM for Excel compatibility
    output = io.StringIO()

    # Write BOM for Excel
    output.write("\ufeff")

    writer = csv.DictWriter(output, fieldnames=M1_COLUMNS)
    writer.writeheader()

    for row in m1_rows:
        row_dict = get_m1_row_as_dict(row)
        writer.writerow(row_dict)

    csv_content = output.getvalue()
    output.close()

    return csv_content, filename, len(m1_rows)


def export_to_csv_bytes(statements: list[RevenueStatement]) -> tuple[bytes, str, int]:
    """
    Export revenue statements to M1 Upload CSV format as bytes.

    Args:
        statements: List of parsed revenue statements

    Returns:
        Tuple of (csv_bytes, filename, row_count)
    """
    csv_content, filename, row_count = export_to_csv(statements)
    return csv_content.encode("utf-8"), filename, row_count


def generate_summary_report(statements: list[RevenueStatement]) -> dict:
    """Generate a summary report of the processed statements."""
    total_rows = sum(len(s.rows) for s in statements)
    total_errors = sum(len(s.errors) for s in statements)

    # Calculate totals
    total_gross = 0
    total_tax = 0
    total_deductions = 0
    total_net = 0

    for statement in statements:
        for row in statement.rows:
            if row.owner_value:
                total_gross += float(row.owner_value)
            if row.owner_tax_amount:
                total_tax += float(row.owner_tax_amount)
            if row.owner_deduct_amount:
                total_deductions += float(row.owner_deduct_amount)
            if row.owner_net_revenue:
                total_net += float(row.owner_net_revenue)

    # Group by payor
    by_payor = {}
    for statement in statements:
        payor = statement.payor or "Unknown"
        if payor not in by_payor:
            by_payor[payor] = {
                "statements": 0,
                "rows": 0,
                "check_amount": 0
            }
        by_payor[payor]["statements"] += 1
        by_payor[payor]["rows"] += len(statement.rows)
        if statement.check_amount:
            by_payor[payor]["check_amount"] += float(statement.check_amount)

    # Group by format
    by_format = {}
    for statement in statements:
        fmt = statement.format.value
        if fmt not in by_format:
            by_format[fmt] = 0
        by_format[fmt] += 1

    return {
        "total_statements": len(statements),
        "total_rows": total_rows,
        "total_errors": total_errors,
        "totals": {
            "gross": round(total_gross, 2),
            "tax": round(total_tax, 2),
            "deductions": round(total_deductions, 2),
            "net": round(total_net, 2)
        },
        "by_payor": by_payor,
        "by_format": by_format
    }


def to_mineral_csv(
    statements: list[RevenueStatement],
    *,
    county: str = "",
    campaign_name: str = "",
) -> bytes:
    """Export revenue statements to CRM mineral format CSV."""
    df = _statements_to_mineral_dataframe(
        statements, county=county, campaign_name=campaign_name
    )
    return dataframe_to_csv_bytes(df)


def _statements_to_mineral_dataframe(
    statements: list[RevenueStatement],
    *,
    county: str = "",
    campaign_name: str = "",
) -> pd.DataFrame:
    """Convert revenue statements to a pandas DataFrame in CRM mineral format.

    Groups by unique owner name across all statements, collecting properties
    and financial totals per owner.
    """
    # Aggregate by owner name
    owners: dict[str, dict[str, Any]] = {}

    for statement in statements:
        owner_name = statement.owner_name or ""
        if not owner_name:
            continue

        if owner_name not in owners:
            owners[owner_name] = {
                "operator": statement.operator_name or "",
                "payor": statement.payor or "",
                "properties": set(),
                "gross": 0.0,
                "net": 0.0,
            }

        info = owners[owner_name]
        for row in statement.rows:
            if row.property_name:
                info["properties"].add(row.property_name)
            if row.owner_value:
                info["gross"] += float(row.owner_value)
            if row.owner_net_revenue:
                info["net"] += float(row.owner_net_revenue)

    data: list[dict[str, Any]] = []
    for name, info in owners.items():
        row: dict[str, Any] = {col: "" for col in MINERAL_EXPORT_COLUMNS}
        row["Full Name"] = name
        row["County"] = county
        row["Campaign Name"] = campaign_name
        row["Company Name"] = info["operator"]
        row["Territory"] = ", ".join(sorted(info["properties"]))
        notes_parts = []
        if info["payor"]:
            notes_parts.append(f"Payor: {info['payor']}")
        notes_parts.append(f"Gross: ${info['gross']:.2f}")
        notes_parts.append(f"Net: ${info['net']:.2f}")
        row["Notes/Comments"] = "; ".join(notes_parts)
        data.append(row)

    return pd.DataFrame(data, columns=MINERAL_EXPORT_COLUMNS)

"""Export service for generating CSV, Excel, and PDF files."""

from __future__ import annotations

import csv
import io
from typing import TYPE_CHECKING

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

from app.models.proration import MineralHolderRow

if TYPE_CHECKING:
    pass


def to_csv(rows: list[MineralHolderRow]) -> bytes:
    """
    Export mineral holder rows to CSV format.

    Args:
        rows: List of MineralHolderRow objects

    Returns:
        CSV file as bytes
    """
    output = io.StringIO()
    writer = csv.writer(output)

    headers = [
        "Owner",
        "Year",
        "Appraisal Value",
        "Interest Type",
        "County",
        "Legal Description",
        "Property",
        "Operator",
        "Raw RRC",
        "New Record",
        "Estimated Monthly Revenue",
        "Interest",
        "Block",
        "Section",
        "Abstract",
        "RRC Acres",
        "Est NRA",
        "$/NRA",
        "Notes",
    ]
    writer.writerow(headers)

    for row in rows:
        writer.writerow([
            row.owner,
            row.year,
            row.appraisal_value,
            row.interest_type,
            row.county,
            row.legal_description,
            row.property,
            row.operator,
            row.raw_rrc,
            row.new_record,
            row.estimated_monthly_revenue,
            row.interest,
            row.block,
            row.section,
            row.abstract,
            row.rrc_acres,
            row.est_nra,
            row.dollars_per_nra,
            row.notes,
        ])

    return output.getvalue().encode("utf-8")


def to_excel(rows: list[MineralHolderRow]) -> bytes:
    """
    Export mineral holder rows to Excel format.

    Args:
        rows: List of MineralHolderRow objects

    Returns:
        Excel file as bytes
    """
    # Create workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Mineral Holders"

    # Define headers
    headers = [
        "Owner",
        "Year",
        "Appraisal Value",
        "Interest Type",
        "County",
        "Legal Description",
        "Property",
        "Operator",
        "Raw RRC",
        "New Record",
        "Estimated Monthly Revenue",
        "Interest",
        "Block",
        "Section",
        "Abstract",
        "RRC Acres",
        "Est NRA",
        "$/NRA",
        "Notes",
    ]

    # Write headers
    ws.append(headers)

    # Style header row
    header_font = Font(bold=True)
    for cell in ws[1]:
        cell.font = header_font

    # Write data rows
    for row in rows:
        ws.append(
            [
                row.owner,
                row.year,
                row.appraisal_value,
                row.interest_type,
                row.county,
                row.legal_description,
                row.property,
                row.operator,
                row.raw_rrc,
                row.new_record,
                row.estimated_monthly_revenue,
                row.interest,
                row.block,
                row.section,
                row.abstract,
                row.rrc_acres,
                row.est_nra,
                row.dollars_per_nra,
                row.notes,
            ]
        )

    # Save to bytes
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.read()


def to_pdf(rows: list[MineralHolderRow]) -> bytes:
    """
    Export mineral holder rows to PDF format.

    Args:
        rows: List of MineralHolderRow objects

    Returns:
        PDF file as bytes
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []

    # Get styles
    styles = getSampleStyleSheet()

    # Prepare data for table
    data = [
        [
            "Owner",
            "County",
            "Interest",
            "RRC Acres",
            "Est NRA",
            "$/NRA",
            "Appraisal Value",
        ]
    ]

    for row in rows:
        data.append(
            [
                row.owner or "",
                row.county or "",
                f"{row.interest:.4f}" if row.interest else "",
                f"{row.rrc_acres:.2f}" if row.rrc_acres else "",
                f"{row.est_nra:.4f}" if row.est_nra else "",
                f"${row.dollars_per_nra:.2f}" if row.dollars_per_nra else "",
                f"${row.appraisal_value:.2f}" if row.appraisal_value else "",
            ]
        )

    # Create table
    table = Table(data)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 12),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ]
        )
    )

    elements.append(table)

    # Build PDF
    doc.build(elements)

    buffer.seek(0)
    return buffer.read()

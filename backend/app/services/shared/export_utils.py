"""Shared export utilities used by all tool export services.

Contains helpers that were previously duplicated across multiple
``export_service.py`` files (e.g. ``_get_column_letter``).
"""

from __future__ import annotations

import io
from datetime import datetime

import pandas as pd


def get_column_letter(col_idx: int) -> str:
    """Convert a 1-based column index to an Excel column letter.

    ``1`` -> ``"A"``, ``26`` -> ``"Z"``, ``27`` -> ``"AA"``, etc.
    """
    result = ""
    while col_idx > 0:
        col_idx, remainder = divmod(col_idx - 1, 26)
        result = chr(65 + remainder) + result
    return result


def auto_adjust_columns(worksheet: "Worksheet", df: pd.DataFrame) -> None:  # noqa: F821
    """Auto-adjust column widths in an openpyxl worksheet to fit content."""
    for idx, col_name in enumerate(df.columns):
        if len(df) > 0:
            max_length = max(
                df[col_name].astype(str).map(len).max(),
                len(str(col_name)),
            )
        else:
            max_length = len(str(col_name))
        adjusted_width = min(max_length + 2, 50)
        worksheet.column_dimensions[get_column_letter(idx + 1)].width = adjusted_width


def dataframe_to_csv_bytes(df: pd.DataFrame, *, bom: bool = True) -> bytes:
    """Convert a DataFrame to CSV bytes (UTF-8 with optional BOM for Excel)."""
    buffer = io.BytesIO()
    encoding = "utf-8-sig" if bom else "utf-8"
    df.to_csv(buffer, index=False, encoding=encoding)
    buffer.seek(0)
    return buffer.getvalue()


def dataframe_to_excel_bytes(
    df: pd.DataFrame,
    *,
    sheet_name: str = "Sheet1",
    auto_width: bool = True,
) -> bytes:
    """Convert a DataFrame to Excel bytes with optional column auto-sizing."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
        if auto_width:
            auto_adjust_columns(writer.sheets[sheet_name], df)
    buffer.seek(0)
    return buffer.getvalue()


def generate_export_filename(base_name: str, extension: str) -> str:
    """Generate an export filename with a timestamp suffix."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{base_name}_{timestamp}.{extension}"

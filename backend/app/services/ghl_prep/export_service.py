"""Export service for GHL Prep Tool.

Handles CSV export generation and filename generation.
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)


def to_csv(rows: list[dict]) -> bytes:
    """Convert list of row dicts to CSV bytes.

    Args:
        rows: List of transformed row dictionaries

    Returns:
        CSV file contents as bytes
    """
    if not rows:
        # Return empty CSV with no rows
        return b""

    # Create DataFrame from rows (preserves column order from dict keys)
    df = pd.DataFrame(rows)

    # Convert to CSV bytes
    csv_str = df.to_csv(index=False)
    return csv_str.encode("utf-8")


def generate_filename(source_filename: str) -> str:
    """Generate export filename from source filename.

    Args:
        source_filename: Original uploaded filename

    Returns:
        Export filename with _ghl_prep suffix before extension
    """
    # Strip extension from source filename
    if "." in source_filename:
        base_name = source_filename.rsplit(".", 1)[0]
    else:
        base_name = source_filename

    # Add suffix
    return f"{base_name}_ghl_prep.csv"

"""CSV transformation service for GHL Prep Tool.

Transforms Mineral export CSVs for GoHighLevel import by:
1. Title-casing name fields (with Mc/Mac/O' prefix handling)
2. Extracting campaign names from JSON
3. Mapping Phone 1 to Phone column
4. Adding Contact Owner column if missing
"""

from __future__ import annotations

import io
import json
import logging
import re
from typing import Any

import pandas as pd

from app.models.ghl_prep import TransformResult

logger = logging.getLogger(__name__)

# Suffixes that should remain uppercase
UPPERCASE_SUFFIXES = {
    "LLC", "LP", "LLP", "INC", "CORP", "CO", "TRUST", "ESTATE",
    "JR", "SR", "II", "III", "IV", "V"
}

# Company indicators (for context-aware title-casing)
COMPANY_INDICATORS = {"LLC", "LP", "INC", "CORP", "CO", "TRUST", "ESTATE"}


def title_case_name(value: Any) -> str:
    """Apply title case to a name with special prefix and suffix handling.

    Handles:
    - Mc prefix: McDonald (not Mcdonald)
    - Mac prefix: MacArthur (not Macarthur)
    - O' prefix: O'Brien (not O'brien)
    - Uppercase suffixes: LLC, LP, Inc, Jr, Sr, II, III, IV

    Args:
        value: The name value to transform (may be NaN, None, or string)

    Returns:
        Title-cased string with proper prefix and suffix handling
    """
    if pd.isna(value) or value is None or str(value).strip() == "":
        return ""

    text = str(value).strip()

    # Apply basic title case
    result = text.title()

    # Fix Mc prefix: Mcdonald -> McDonald
    result = re.sub(r'\bMc([a-z])', lambda m: f"Mc{m.group(1).upper()}", result)

    # Fix Mac prefix: Macarthur -> MacArthur
    result = re.sub(r'\bMac([a-z])', lambda m: f"Mac{m.group(1).upper()}", result)

    # Fix O' prefix: O'brien -> O'Brien
    result = re.sub(r"\bO'([a-z])", lambda m: f"O'{m.group(1).upper()}", result)

    # Handle "MC DONALD" -> "McDonald" (space before prefix)
    result = re.sub(r'\bMc\s+([A-Z][a-z]+)', r'Mc\1', result)

    # Handle "O BRIEN" -> "O'Brien" (space instead of apostrophe)
    result = re.sub(r"\bO\s+([A-Z][a-z]+)", r"O'\1", result)

    # Preserve uppercase suffixes
    for suffix in UPPERCASE_SUFFIXES:
        # Match word boundary + suffix (case-insensitive) + word boundary
        pattern = r'\b' + re.escape(suffix.title()) + r'\b'
        result = re.sub(pattern, suffix, result, flags=re.IGNORECASE)

    return result


def transform_csv(file_bytes: bytes, filename: str) -> TransformResult:
    """Transform a Mineral export CSV for GoHighLevel import.

    Args:
        file_bytes: CSV file contents as bytes
        filename: Original filename

    Returns:
        TransformResult with transformed rows and metadata
    """
    warnings: list[str] = []
    transformed_fields: dict[str, int] = {
        "title_cased": 0,
        "campaigns_extracted": 0,
        "phone_mapped": 0,
        "contact_owner_added": 0
    }

    # Read CSV with encoding fallback
    try:
        df = pd.read_csv(io.BytesIO(file_bytes), encoding="utf-8")
    except UnicodeDecodeError:
        logger.warning("UTF-8 decoding failed, trying latin-1 encoding")
        df = pd.read_csv(io.BytesIO(file_bytes), encoding="latin-1")

    if df.empty:
        warnings.append("CSV file is empty")
        return TransformResult(
            success=False,
            rows=[],
            total_count=0,
            transformed_fields=transformed_fields,
            warnings=warnings,
            source_filename=filename
        )

    # Track original column order
    original_columns = df.columns.tolist()

    # 1. Title-case name fields
    name_patterns = ["name", "city", "county", "territory", "address"]
    title_case_columns = []

    for col in df.columns:
        col_lower = col.lower()
        # Check if column name contains any name pattern
        if any(pattern in col_lower for pattern in name_patterns):
            # Don't title-case email, phone, state, zip
            if not any(skip in col_lower for skip in ["email", "phone", "state", "zip"]):
                title_case_columns.append(col)

    # Apply title-casing to identified columns
    for col in title_case_columns:
        original_values = df[col].copy()
        df[col] = df[col].apply(title_case_name)
        # Count how many values actually changed
        changed = (original_values != df[col]).sum()
        transformed_fields["title_cased"] += int(changed)

    if title_case_columns:
        logger.info("Applied title-casing to columns: %s", title_case_columns)

    # 2. Extract campaign names from JSON
    campaigns_col = None
    for col in df.columns:
        if col.lower() == "campaigns":
            campaigns_col = col
            break

    if campaigns_col:
        def extract_campaign(value: Any) -> str:
            """Extract first campaign unit_name from JSON array."""
            if pd.isna(value) or value is None or str(value).strip() == "":
                return ""

            text = str(value).strip()
            try:
                # Try to parse as JSON array
                data = json.loads(text)
                if isinstance(data, list) and len(data) > 0:
                    # Extract unit_name from first element
                    first_campaign = data[0]
                    if isinstance(first_campaign, dict) and "unit_name" in first_campaign:
                        return str(first_campaign["unit_name"])
            except (json.JSONDecodeError, KeyError, TypeError):
                # If JSON parsing fails, return the raw value as-is
                pass

            return text

        original_values = df[campaigns_col].copy()
        df[campaigns_col] = df[campaigns_col].apply(extract_campaign)
        # Count successful extractions (values that changed)
        changed = (original_values != df[campaigns_col]).sum()
        transformed_fields["campaigns_extracted"] = int(changed)
        logger.info("Extracted campaign names from %d rows", changed)
    else:
        warnings.append("No 'Campaigns' column found")

    # 3. Map Phone 1 to Phone column
    phone1_col = None
    for col in df.columns:
        if col.lower().startswith("phone 1"):
            phone1_col = col
            break

    if phone1_col:
        # Check if Phone column already exists
        phone_col = None
        for col in df.columns:
            if col.lower() == "phone":
                phone_col = col
                break

        if phone_col:
            # Overwrite existing Phone column
            df[phone_col] = df[phone1_col]
        else:
            # Add new Phone column (insert after Phone 1 for logical ordering)
            phone1_idx = df.columns.tolist().index(phone1_col)
            df.insert(phone1_idx + 1, "Phone", df[phone1_col])

        # Count non-empty phone mappings
        non_empty = df[phone1_col].notna().sum()
        transformed_fields["phone_mapped"] = int(non_empty)
        logger.info("Mapped Phone 1 to Phone column (%d values)", non_empty)
    else:
        warnings.append("No 'Phone 1' column found")

    # 4. Add Contact Owner column if missing
    contact_owner_col = None
    for col in df.columns:
        if col.lower() == "contact owner":
            contact_owner_col = col
            break

    if not contact_owner_col:
        # Add Contact Owner column at the end with empty strings
        df["Contact Owner"] = ""
        transformed_fields["contact_owner_added"] = len(df)
        logger.info("Added 'Contact Owner' column with %d empty rows", len(df))
    else:
        logger.info("'Contact Owner' column already exists")

    # 5. Normalize checkbox columns to "Yes"/"No" for GHL import
    checkbox_columns_lower = {"bankruptcy", "deceased", "lien"}
    for col in df.columns:
        if col.lower() in checkbox_columns_lower:
            def normalize_checkbox(val: Any) -> str:
                if pd.isna(val) or val is None:
                    return "No"
                s = str(val).strip().lower()
                if s in ("true", "1", "1.0", "yes", "y"):
                    return "Yes"
                return "No"
            df[col] = df[col].apply(normalize_checkbox)

    # 6. Drop columns not needed for GHL import
    drop_columns_lower = {
        "department", "title", "stage", "status", "outcome",
        "lead source", "purchased data exists", "campaigns",
        "well interest count",
    }
    cols_to_drop = [col for col in df.columns if col.lower() in drop_columns_lower]
    if cols_to_drop:
        df.drop(columns=cols_to_drop, inplace=True)
        logger.info("Dropped columns: %s", cols_to_drop)

    # Convert to list of dicts (preserves all columns)
    rows = df.to_dict(orient="records")

    return TransformResult(
        success=True,
        rows=rows,
        total_count=len(rows),
        transformed_fields=transformed_fields,
        warnings=warnings,
        source_filename=filename
    )

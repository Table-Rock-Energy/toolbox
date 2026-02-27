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

    # 0. Re-split Name into First Name / Middle Name / Last Name
    # The source export often has incorrect splits, so we re-derive from the full Name column
    name_col = None
    first_col = None
    middle_col = None
    last_col = None
    for col in df.columns:
        cl = col.lower().strip()
        if cl == "name" or cl == "full name":
            name_col = col
        elif cl == "first name":
            first_col = col
        elif cl == "middle name":
            middle_col = col
        elif cl == "last name":
            last_col = col

    if name_col and first_col and last_col:
        for idx in df.index:
            full = df.at[idx, name_col]
            if pd.isna(full) or str(full).strip() == "":
                continue

            parts = str(full).strip().split()
            if len(parts) < 2:
                continue

            # Detect O' prefix names: ["Donny", "O'Burns"] or ["Donny", "O", "'Burns"]
            # Detect hyphenated/apostrophe last names by rejoining O + next part
            merged: list[str] = []
            i = 0
            while i < len(parts):
                p = parts[i]
                # "O" followed by another part that doesn't start with apostrophe -> "O'Next"
                if p.upper() == "O" and i + 1 < len(parts) and not parts[i + 1].startswith("'"):
                    merged.append(f"O'{parts[i + 1]}")
                    i += 2
                    continue
                # "Mc" or "MC" as standalone -> merge with next
                if p.upper() == "MC" and i + 1 < len(parts):
                    merged.append(f"Mc{parts[i + 1]}")
                    i += 2
                    continue
                merged.append(p)
                i += 1

            parts = merged

            # Pull trailing suffixes (JR, SR, II, III, IV, V) to attach to last name
            name_suffixes = {"JR", "SR", "II", "III", "IV", "V"}
            suffix_parts: list[str] = []
            while len(parts) > 2 and parts[-1].upper().rstrip(".") in name_suffixes:
                suffix_parts.insert(0, parts.pop())

            if len(parts) == 1:
                last_name = parts[0]
                if suffix_parts:
                    last_name += " " + " ".join(suffix_parts)
                df.at[idx, first_col] = last_name  # single word = just put in first
                if middle_col:
                    df.at[idx, middle_col] = ""
                df.at[idx, last_col] = ""
            elif len(parts) == 2:
                last_name = parts[1]
                if suffix_parts:
                    last_name += " " + " ".join(suffix_parts)
                df.at[idx, first_col] = parts[0]
                if middle_col:
                    df.at[idx, middle_col] = ""
                df.at[idx, last_col] = last_name
            else:
                # First word = first name, last word = last name, everything else = middle
                last_name = parts[-1]
                if suffix_parts:
                    last_name += " " + " ".join(suffix_parts)
                df.at[idx, first_col] = parts[0]
                df.at[idx, last_col] = last_name
                if middle_col:
                    df.at[idx, middle_col] = " ".join(parts[1:-1])

        logger.info("Re-split names from '%s' into first/middle/last", name_col)

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
        # Capture first non-empty campaign name for metadata
        campaign_values = df[campaigns_col].dropna().loc[lambda s: s.str.strip() != ""]
        extracted_campaign_name = str(campaign_values.iloc[0]) if len(campaign_values) > 0 else None
        logger.info("Extracted campaign names from %d rows", changed)
    else:
        extracted_campaign_name = None
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
            # Add new Phone column before Phone 1
            phone1_idx = df.columns.tolist().index(phone1_col)
            df.insert(phone1_idx, "Phone", df[phone1_col])

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
    # Match columns containing bankruptcy, deceased, or lien (covers "Bankruptcy", "Bankruptcy Flag", etc.)
    checkbox_keywords = ("bankruptcy", "deceased", "lien")
    for col in df.columns:
        if any(kw in col.lower() for kw in checkbox_keywords):
            def normalize_checkbox(val: Any) -> str:
                if pd.isna(val) or val is None:
                    return "No"
                s = str(val).strip().lower()
                if s in ("true", "1", "1.0", "yes", "y"):
                    return "Yes"
                return "No"
            df[col] = df[col].apply(normalize_checkbox)

    # 5b. Rename columns to match GHL field names for auto-mapping
    rename_map = {}
    existing_cols_lower = {c.lower() for c in df.columns}
    for col in df.columns:
        cl = col.lower()
        if cl.startswith("phone") and "purchased data" in cl:
            # "Phone 1 (Purchased Data)" -> "Phone 1", etc.
            num = cl.split()[1] if len(cl.split()) > 1 else ""
            new_name = f"Phone {num}" if num else col
            # Only rename if it won't create a duplicate column name
            if new_name.lower() not in existing_cols_lower:
                rename_map[col] = new_name
                existing_cols_lower.add(new_name.lower())
            else:
                logger.info("Skipping rename '%s' -> '%s' (duplicate)", col, new_name)
        elif "bankruptcy" in cl:
            rename_map[col] = "Bankruptcy"
        elif "deceased" in cl:
            rename_map[col] = "Deceased"
        elif "lien" in cl:
            rename_map[col] = "Lien"
    if rename_map:
        df.rename(columns=rename_map, inplace=True)
        logger.info("Renamed columns: %s", rename_map)

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

    # 7. Reorder columns:
    #    Regular cols -> Phone 2-5 -> Flag cols -> Campaign System Id -> Mineral Contact System Id
    extra_phone_cols = []      # Phone 2-5 (renamed or original)
    flag_cols = []             # Bankruptcy, Deceased, Lien
    campaign_system_col = []   # Campaign System Id
    mineral_system_col = []    # Mineral Contact System Id (very last)
    regular_cols = []

    for col in df.columns:
        cl = col.lower()
        # Match "Phone 2" through "Phone 9" or "Phone N (Purchased Data)" variants
        if re.match(r"^phone\s+[2-9]", cl):
            extra_phone_cols.append(col)
        elif any(kw in cl for kw in ("bankruptcy", "deceased", "lien")):
            flag_cols.append(col)
        elif "campaign system" in cl:
            campaign_system_col.append(col)
        elif "mineral" in cl and "system" in cl:
            mineral_system_col.append(col)
        else:
            regular_cols.append(col)

    # Sort extra phone cols by number (Phone 2, Phone 3, ... Phone 5)
    extra_phone_cols.sort(key=lambda c: c.lower())

    new_order = regular_cols + extra_phone_cols + flag_cols + campaign_system_col + mineral_system_col
    df = df[new_order]

    # 8. Ensure Phone 2-5 columns always exist (even if source CSV lacks them)
    for phone_num in range(2, 6):
        col_name = f"Phone {phone_num}"
        if col_name not in df.columns:
            # Insert after the last phone-related column in the current order
            df[col_name] = ""
            logger.info("Added missing column '%s' with empty values", col_name)

    # Re-run column ordering to place newly added Phone columns correctly
    extra_phone_cols_final = []
    flag_cols_final = []
    campaign_system_col_final = []
    mineral_system_col_final = []
    regular_cols_final = []

    for col in df.columns:
        cl = col.lower()
        if re.match(r"^phone\s+[2-9]", cl):
            extra_phone_cols_final.append(col)
        elif any(kw in cl for kw in ("bankruptcy", "deceased", "lien")):
            flag_cols_final.append(col)
        elif "campaign system" in cl:
            campaign_system_col_final.append(col)
        elif "mineral" in cl and "system" in cl:
            mineral_system_col_final.append(col)
        else:
            regular_cols_final.append(col)

    extra_phone_cols_final.sort(key=lambda c: c.lower())
    final_order = regular_cols_final + extra_phone_cols_final + flag_cols_final + campaign_system_col_final + mineral_system_col_final
    df = df[final_order]

    # Replace NaN with empty string to avoid JSON serialization issues
    df = df.fillna("")

    # Convert to list of dicts (preserves column order)
    rows = df.to_dict(orient="records")

    return TransformResult(
        success=True,
        rows=rows,
        total_count=len(rows),
        transformed_fields=transformed_fields,
        warnings=warnings,
        source_filename=filename,
        campaign_name=extracted_campaign_name,
    )

"""CSV transformation service for GHL Prep Tool.

Transforms Mineral export CSVs for GoHighLevel import by:
1. Title-casing name fields (with Mc/Mac/O' prefix handling)
2. Extracting campaign names from JSON
3. Mapping Phone 1 to Phone column
4. Adding Contact Owner column if missing
5. Normalizing checkbox columns to Yes/No
6. Renaming Phone N (Purchased Data) -> Phone N and flag columns
7. Dropping columns not needed for GHL import
8. Ensuring Phone 2-5 columns always exist
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

# Exact output columns in order. Only these columns appear in preview/export.
# Source columns not in this list are consumed during transform then discarded.
OUTPUT_COLUMNS = [
    "M1neral Contact System ID",
    "First Name",
    "Last Name",
    "Phone",
    "Phone 1",
    "Phone 2",
    "Phone 3",
    "Phone 4",
    "Phone 5",
    "Email",
    "Address",
    "City",
    "State",
    "County",
    "Zip",
    "Contact Owner",
    "Campaign Name",
    "Bankruptcy",
    "Deceased",
    "Lien",
    "Campaign System ID",
]


def title_case_name(value: Any) -> str:
    """Apply title case to a name with special prefix and suffix handling."""
    if pd.isna(value) or value is None or str(value).strip() == "":
        return ""

    text = str(value).strip()
    result = text.title()

    # Fix Mc prefix: Mcdonald -> McDonald
    result = re.sub(r'\bMc([a-z])', lambda m: f"Mc{m.group(1).upper()}", result)
    # Fix Mac prefix: Macarthur -> MacArthur
    result = re.sub(r'\bMac([a-z])', lambda m: f"Mac{m.group(1).upper()}", result)
    # Fix O' prefix: O'brien -> O'Brien
    result = re.sub(r"\bO'([a-z])", lambda m: f"O'{m.group(1).upper()}", result)
    # Handle "MC DONALD" -> "McDonald"
    result = re.sub(r'\bMc\s+([A-Z][a-z]+)', r'Mc\1', result)
    # Handle "O BRIEN" -> "O'Brien"
    result = re.sub(r"\bO\s+([A-Z][a-z]+)", r"O'\1", result)

    # Preserve uppercase suffixes
    for suffix in UPPERCASE_SUFFIXES:
        pattern = r'\b' + re.escape(suffix.title()) + r'\b'
        result = re.sub(pattern, suffix, result, flags=re.IGNORECASE)

    return result


def _find_col(df: pd.DataFrame, *candidates: str) -> str | None:
    """Find the first matching column name (case-insensitive, strip whitespace)."""
    col_map = {c.lower().strip(): c for c in df.columns}
    for candidate in candidates:
        if candidate.lower().strip() in col_map:
            return col_map[candidate.lower().strip()]
    return None


def transform_csv(file_bytes: bytes, filename: str) -> TransformResult:
    """Transform a Mineral export CSV for GoHighLevel import."""
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
            success=False, rows=[], total_count=0,
            transformed_fields=transformed_fields,
            warnings=warnings, source_filename=filename
        )

    # Strip whitespace from column names (handles "Bankruptcy Flag " trailing space)
    df.columns = [c.strip() for c in df.columns]

    # 0. Re-split Name into First Name / Middle Name / Last Name
    name_col = _find_col(df, "Name", "Full Name")
    first_col = _find_col(df, "First Name")
    middle_col = _find_col(df, "Middle Name")
    last_col = _find_col(df, "Last Name")

    if name_col and first_col and last_col:
        for idx in df.index:
            full = df.at[idx, name_col]
            if pd.isna(full) or str(full).strip() == "":
                continue

            parts = str(full).strip().split()
            if len(parts) < 2:
                continue

            merged: list[str] = []
            i = 0
            while i < len(parts):
                p = parts[i]
                if p.upper() == "O" and i + 1 < len(parts) and not parts[i + 1].startswith("'"):
                    merged.append(f"O'{parts[i + 1]}")
                    i += 2
                    continue
                if p.upper() == "MC" and i + 1 < len(parts):
                    merged.append(f"Mc{parts[i + 1]}")
                    i += 2
                    continue
                merged.append(p)
                i += 1

            parts = merged
            name_suffixes = {"JR", "SR", "II", "III", "IV", "V"}
            suffix_parts: list[str] = []
            while len(parts) > 2 and parts[-1].upper().rstrip(".") in name_suffixes:
                suffix_parts.insert(0, parts.pop())

            if len(parts) == 1:
                last_name = parts[0]
                if suffix_parts:
                    last_name += " " + " ".join(suffix_parts)
                df.at[idx, first_col] = last_name
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
        if any(pattern in col_lower for pattern in name_patterns):
            if not any(skip in col_lower for skip in ["email", "phone", "state", "zip", "system", "campaign"]):
                title_case_columns.append(col)

    for col in title_case_columns:
        original_values = df[col].copy()
        df[col] = df[col].apply(title_case_name)
        changed = (original_values != df[col]).sum()
        transformed_fields["title_cased"] += int(changed)

    if title_case_columns:
        logger.info("Applied title-casing to columns: %s", title_case_columns)

    # 2. Extract campaign name
    # Prefer plain text "Campaign Name" column if it exists
    campaign_name_col = _find_col(df, "Campaign Name")
    campaigns_json_col = _find_col(df, "Campaigns", "Campaign")

    extracted_campaign_name = None

    if campaign_name_col:
        campaign_values = df[campaign_name_col].dropna().astype(str).loc[lambda s: s.str.strip() != ""]
        extracted_campaign_name = str(campaign_values.iloc[0]) if len(campaign_values) > 0 else None
        if extracted_campaign_name:
            logger.info("Campaign name from '%s' column: %s", campaign_name_col, extracted_campaign_name)

    if not extracted_campaign_name and campaigns_json_col:
        def extract_campaign(value: Any) -> str:
            """Extract first campaign name from JSON array."""
            if pd.isna(value) or value is None or str(value).strip() == "":
                return ""
            text = str(value).strip()
            try:
                data = json.loads(text)
                if isinstance(data, list) and len(data) > 0:
                    first_campaign = data[0]
                    if isinstance(first_campaign, dict):
                        for key in ("unit_name", "name"):
                            if key in first_campaign:
                                return str(first_campaign[key])
            except (json.JSONDecodeError, KeyError, TypeError):
                pass
            return text

        original_values = df[campaigns_json_col].copy()
        df[campaigns_json_col] = df[campaigns_json_col].apply(extract_campaign)
        changed = (original_values != df[campaigns_json_col]).sum()
        transformed_fields["campaigns_extracted"] = int(changed)
        campaign_values = df[campaigns_json_col].dropna().loc[lambda s: s.str.strip() != ""]
        extracted_campaign_name = str(campaign_values.iloc[0]) if len(campaign_values) > 0 else None
        logger.info("Extracted campaign names from JSON (%d rows)", changed)

    if not extracted_campaign_name:
        warnings.append("No campaign name found in upload")

    # 3. Map phone to primary Phone column
    # Use first non-empty: Primary Mobile Phone > Primary Home Phone > Phone 1 (Purchased Data)
    primary_mobile_col = _find_col(df, "Primary Mobile Phone")
    primary_home_col = _find_col(df, "Primary Home Phone")
    phone1_col = None
    for col in df.columns:
        if col.lower().startswith("phone 1"):
            phone1_col = col
            break

    # Prefer Phone 1 (Purchased Data) since it's the primary data column,
    # then fall back to Primary Mobile / Primary Home
    phone_source_col = None
    for candidate_col in [phone1_col, primary_mobile_col, primary_home_col]:
        if candidate_col:
            non_empty = df[candidate_col].dropna().astype(str).loc[lambda s: s.str.strip() != ""]
            if len(non_empty) > 0:
                phone_source_col = candidate_col
                break
    if not phone_source_col and phone1_col:
        phone_source_col = phone1_col

    if phone_source_col:
        phone_col = _find_col(df, "Phone")
        if phone_col:
            df[phone_col] = df[phone_source_col]
        else:
            phone_source_idx = df.columns.tolist().index(phone_source_col)
            df.insert(phone_source_idx, "Phone", df[phone_source_col])

        non_empty = df[phone_source_col].notna().sum()
        transformed_fields["phone_mapped"] = int(non_empty)
        logger.info("Mapped '%s' to Phone column (%d values)", phone_source_col, non_empty)
    else:
        warnings.append("No phone column found to map")

    # 4. Add Contact Owner column if missing
    if not _find_col(df, "Contact Owner"):
        df["Contact Owner"] = ""
        transformed_fields["contact_owner_added"] = len(df)
        logger.info("Added 'Contact Owner' column with %d empty rows", len(df))

    # 5. Normalize checkbox columns to "Yes"/"No"
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

    # 6. Rename: Phone N (Purchased Data) -> Phone N, flag columns -> Bankruptcy/Deceased/Lien
    rename_map = {}
    cols_to_drop_post_rename = []
    existing_cols_lower = {c.lower() for c in df.columns}
    for col in df.columns:
        cl = col.lower()
        if cl.startswith("phone") and "purchased data" in cl:
            num = cl.split()[1] if len(cl.split()) > 1 else ""
            new_name = f"Phone {num}" if num else col
            if new_name.lower() not in existing_cols_lower:
                rename_map[col] = new_name
                existing_cols_lower.add(new_name.lower())
            else:
                cols_to_drop_post_rename.append(col)
                logger.info("Dropping duplicate '%s' (keeping existing '%s')", col, new_name)
        elif "bankruptcy" in cl:
            rename_map[col] = "Bankruptcy"
        elif "deceased" in cl:
            rename_map[col] = "Deceased"
        elif "lien" in cl:
            rename_map[col] = "Lien"
    if rename_map:
        df.rename(columns=rename_map, inplace=True)
        logger.info("Renamed columns: %s", rename_map)
    if cols_to_drop_post_rename:
        df.drop(columns=cols_to_drop_post_rename, inplace=True)
        logger.info("Dropped duplicate purchased data columns: %s", cols_to_drop_post_rename)

    # 7. Rename source columns to output names, then select only OUTPUT_COLUMNS.
    #    This handles varying source exports (users can toggle columns in Mineral).
    source_to_output = {
        "Primary Email": "Email",
        "Primary Address": "Address",
    }
    for src, dst in source_to_output.items():
        src_col = _find_col(df, src)
        if src_col and dst not in df.columns:
            df.rename(columns={src_col: dst}, inplace=True)

    # Build final DataFrame with only OUTPUT_COLUMNS (in order).
    # Missing columns get empty strings; extra source columns are discarded.
    final_df = pd.DataFrame()
    for col_name in OUTPUT_COLUMNS:
        matched = _find_col(df, col_name)
        if matched:
            final_df[col_name] = df[matched]
        else:
            final_df[col_name] = ""
            logger.info("Output column '%s' not in source — added empty", col_name)
    df = final_df

    # Replace NaN and convert all values to strings
    df = df.fillna("")
    for col in df.columns:
        df[col] = df[col].apply(
            lambda v: "" if v == "" or (isinstance(v, str) and v.strip() == "")
            else str(int(v)) if isinstance(v, (int, float)) and not isinstance(v, bool)
            else str(v)
        )

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

# Pandas Workflows Reference

## Contents
- RRC Data Load Workflow
- CSV Upload Processing Workflow
- Multi-Column M1 Export Workflow
- Firestore Sync from DataFrame
- Validation Checklist

---

## RRC Data Load Workflow

The RRC proration cache follows a download → parse → cache → lookup lifecycle. See `backend/app/services/proration/csv_processor.py`.

```python
import pandas as pd
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_oil_df: Optional[pd.DataFrame] = None
_gas_df: Optional[pd.DataFrame] = None

def load_rrc_data(oil_path: str, gas_path: str) -> tuple[int, int]:
    """Load RRC CSVs into memory. Returns (oil_count, gas_count)."""
    global _oil_df, _gas_df
    _oil_df = _load_clean(oil_path)
    _gas_df = _load_clean(gas_path)
    logger.info(f"RRC cache loaded: {len(_oil_df)} oil, {len(_gas_df)} gas rows")
    return len(_oil_df), len(_gas_df)

def _load_clean(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
    return df

def lookup_rrc(lease_name: str, operator: str, well_type: str = "oil") -> list[dict]:
    df = _oil_df if well_type == "oil" else _gas_df
    if df is None:
        return []
    mask = (
        df["lease_name"].str.upper().str.strip() == lease_name.upper().strip()
    ) & (
        df["operator_name"].str.upper().str.strip() == operator.upper().strip()
    )
    return df[mask].to_dict(orient="records")
```

Copy this checklist for adding a new RRC data source:
- [ ] Define expected columns and normalize names in `_load_clean()`
- [ ] Add a new module-level `_df` variable
- [ ] Expose a `lookup_*()` function with normalized string comparison
- [ ] Log row count after load for observability
- [ ] Add cache invalidation when a new download completes

---

## CSV Upload Processing Workflow

Used in Title and GHL Prep tools for user-uploaded spreadsheets.

```python
import io
import pandas as pd
from fastapi import UploadFile, HTTPException

async def read_uploaded_table(file: UploadFile) -> pd.DataFrame:
    contents = await file.read()
    if not contents:
        raise HTTPException(400, "Uploaded file is empty")

    buf = io.BytesIO(contents)
    ext = (file.filename or "").lower()

    if ext.endswith(".xlsx") or ext.endswith(".xls"):
        df = pd.read_excel(buf, dtype=str, keep_default_na=False)
    elif ext.endswith(".csv"):
        df = pd.read_csv(buf, dtype=str, keep_default_na=False)
    else:
        raise HTTPException(400, f"Unsupported file type: {file.filename}")

    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
    df = df.dropna(how="all")  # Remove blank rows
    return df
```

Validate required columns immediately after load:

```python
REQUIRED_COLUMNS = {"owner_name", "net_acres", "tract"}

def validate_columns(df: pd.DataFrame, required: set[str]) -> None:
    missing = required - set(df.columns)
    if missing:
        raise HTTPException(400, f"Missing required columns: {', '.join(sorted(missing))}")
```

---

## Multi-Column M1 Export Workflow

Revenue tool outputs 29-column M1 CSV. Column order is fixed; missing fields must be empty strings. See `backend/app/services/revenue/m1_transformer.py`.

```python
M1_COLUMNS = [
    "owner_name", "owner_id", "check_date", "property_name",
    # ... 25 more fixed columns
]

def build_m1_dataframe(records: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(records)
    # Add any missing M1 columns as empty string
    for col in M1_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    return df[M1_COLUMNS]  # Enforce column order

def export_m1_csv(records: list[dict]) -> bytes:
    df = build_m1_dataframe(records)
    return df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
```

**DO** always reindex to `M1_COLUMNS` at export time — never assume record dicts contain all keys in order.
**DON'T** use `df.reindex(columns=M1_COLUMNS, fill_value=None)` — use `""` not `None` for blank M1 cells.

---

## Firestore Sync from DataFrame

When syncing RRC data to Firestore, batch by 500 (Firestore limit). See the **firestore** skill for batch commit patterns.

```python
from google.cloud import firestore

def sync_df_to_firestore(
    df: pd.DataFrame,
    db: firestore.Client,
    collection: str,
    id_col: str,
) -> int:
    batch = db.batch()
    count = 0
    for i, row in enumerate(df.to_dict(orient="records")):
        doc_id = row[id_col].replace("/", "_")
        ref = db.collection(collection).document(doc_id)
        batch.set(ref, row, merge=True)
        count += 1
        if (i + 1) % 500 == 0:
            batch.commit()
            batch = db.batch()
    if count % 500 != 0:
        batch.commit()
    return count
```

Note: this must run in a background thread (not in an async route) — use the `rrc_background.py` pattern with a synchronous Firestore client.

---

## Validation Checklist

Run after any pandas processing to catch common issues:

```python
def validate_dataframe(df: pd.DataFrame, context: str = "") -> None:
    if df.empty:
        logger.warning(f"{context}: DataFrame is empty")
    dupes = df.duplicated().sum()
    if dupes > 0:
        logger.warning(f"{context}: {dupes} duplicate rows found")
    null_counts = df.isnull().sum()
    if null_counts.any():
        logger.warning(f"{context}: null values found: {null_counts[null_counts > 0].to_dict()}")
```

Iterate-until-pass for data pipeline issues:
1. Load CSV with `dtype=str, keep_default_na=False`
2. Log `df.dtypes` and `df.head()` to confirm column types
3. If comparisons fail, check `df["col"].unique()` for unexpected whitespace or encoding
4. Normalize: `.str.strip().str.upper()` on both sides of comparison
5. Only proceed to export when `validate_dataframe()` logs no warnings
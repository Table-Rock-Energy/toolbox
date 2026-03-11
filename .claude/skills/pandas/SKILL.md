---
name: pandas
description: |
  Processes CSV/Excel data with in-memory caching and lookups for FastAPI backend document processing tools.
  Use when: reading/writing CSV/Excel files, transforming tabular data, caching RRC data for lookups, aggregating/filtering datasets, or building in-memory lookup tables from downloaded files.
allowed-tools: Read, Edit, Write, Glob, Grep, Bash, mcp__plugin_context7_context7__resolve-library-id, mcp__plugin_context7_context7__query-docs
---

# Pandas Skill

Pandas 2.x is used exclusively in the backend for tabular data processing. The primary use case is loading RRC proration CSVs into memory for fast lease lookups — a pattern where a large CSV is downloaded once, parsed into a DataFrame, and cached as a module-level variable for the lifetime of the process. Export operations produce `.xlsx` (via `openpyxl`) and `.csv` outputs sent to GCS or local storage.

## Quick Start

### In-memory cache pattern (RRC data)

```python
import pandas as pd
from typing import Optional

_df_cache: Optional[pd.DataFrame] = None

def get_dataframe() -> Optional[pd.DataFrame]:
    return _df_cache

def load_csv(path: str) -> pd.DataFrame:
    global _df_cache
    _df_cache = pd.read_csv(path, dtype=str, keep_default_na=False)
    _df_cache.columns = _df_cache.columns.str.strip().str.lower()
    return _df_cache
```

### Lookup by key columns

```python
def lookup_lease(df: pd.DataFrame, operator: str, lease_name: str) -> list[dict]:
    mask = (
        df["operator_name"].str.upper() == operator.upper()
    ) & (
        df["lease_name"].str.upper() == lease_name.upper()
    )
    return df[mask].to_dict(orient="records")
```

### Export to Excel with openpyxl

```python
import io
import pandas as pd

def to_excel_bytes(records: list[dict]) -> bytes:
    df = pd.DataFrame(records)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Results")
    buf.seek(0)
    return buf.read()
```

## Key Concepts

| Concept | Usage | Example |
|---------|-------|---------|
| `dtype=str` on read | Prevents unwanted type coercion (lease numbers becoming floats) | `pd.read_csv(f, dtype=str)` |
| `keep_default_na=False` | Prevents empty strings → NaN, which breaks string comparisons | `pd.read_csv(f, keep_default_na=False)` |
| `str.strip()` on columns | RRC CSVs have trailing whitespace in headers | `df.columns.str.strip()` |
| `orient="records"` | Convert rows to list of dicts for JSON serialization | `df.to_dict(orient="records")` |
| `io.BytesIO` | Export to bytes for GCS upload or HTTP response | `buf = io.BytesIO()` |

## Common Patterns

### Normalize text before comparison

```python
def normalize(val: str) -> str:
    return val.strip().upper()

matches = df[df["lease_name"].apply(normalize) == normalize(query)]
```

### Read uploaded file from bytes

```python
async def process_upload(file: UploadFile) -> pd.DataFrame:
    contents = await file.read()
    buf = io.BytesIO(contents)
    if file.filename.endswith(".xlsx"):
        return pd.read_excel(buf, dtype=str)
    return pd.read_csv(buf, dtype=str, keep_default_na=False)
```

## See Also

- [patterns](references/patterns.md)
- [workflows](references/workflows.md)

## Related Skills

- See the **python** skill for async patterns and FastAPI integration
- See the **fastapi** skill for upload endpoint patterns
- See the **google-cloud-storage** skill for saving export bytes to GCS
- See the **reportlab** skill for PDF exports (complement to Excel exports)
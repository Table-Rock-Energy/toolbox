---
name: pandas
description: |
  Processes CSV/Excel data with in-memory caching and lookups for FastAPI backend document processing tools
  Use when: reading/writing CSV/Excel files, transforming tabular data, caching RRC data for lookups, aggregating/filtering datasets
allowed-tools: Read, Edit, Write, Glob, Grep, Bash, mcp__plugin_context7_context7__resolve-library-id, mcp__plugin_context7_context7__query-docs
---

# Pandas Skill

Use pandas for all CSV/Excel processing in the FastAPI backend. The codebase caches large RRC datasets (100k+ rows) in-memory as DataFrames for fast lookups during document processing. All tabular exports (Extract, Title, Proration, Revenue tools) go through pandas for data transformation and validation.

## Quick Start

### In-Memory CSV Caching (RRC Data)

```python
# toolbox/backend/app/services/proration/csv_processor.py
import pandas as pd

class CSVProcessor:
    def __init__(self):
        self._oil_df: pd.DataFrame | None = None
        self._gas_df: pd.DataFrame | None = None
    
    def load_csv(self, file_path: str, well_type: str) -> pd.DataFrame:
        """Load CSV into memory, cache for fast lookups"""
        df = pd.read_csv(
            file_path,
            dtype=str,  # Force all columns to string to preserve leading zeros
            na_values=[''],
            keep_default_na=False
        )
        # Cache in memory
        if well_type == "OIL":
            self._oil_df = df
        else:
            self._gas_df = df
        return df
    
    def query_lease(self, lease_number: str, district: str) -> pd.DataFrame:
        """Fast in-memory lookup by lease number + district"""
        df = self._oil_df if self._oil_df is not None else self._gas_df
        return df[
            (df['LEASE_NO'] == lease_number) & 
            (df['DISTRICT'] == district)
        ]
```

### Excel Export with Multiple Sheets

```python
# toolbox/backend/app/services/proration/export_service.py
import pandas as pd
from io import BytesIO

def export_to_excel(results: list[dict]) -> BytesIO:
    """Export to Excel with summary + detail sheets"""
    df = pd.DataFrame(results)
    
    # Create summary with aggregations
    summary = df.groupby('operator').agg({
        'net_revenue_acres': 'sum',
        'gross_acres': 'sum'
    }).reset_index()
    
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Detail', index=False)
        summary.to_excel(writer, sheet_name='Summary', index=False)
    
    buffer.seek(0)
    return buffer
```

## Key Concepts

| Concept | Usage | Example |
|---------|-------|---------|
| `dtype=str` | Preserve leading zeros in lease numbers | `pd.read_csv(path, dtype=str)` |
| `keep_default_na=False` | Treat empty strings as empty, not NaN | `pd.read_csv(path, keep_default_na=False)` |
| In-memory cache | Store DataFrame in class attribute for fast queries | `self._df = pd.read_csv(path)` |
| `ExcelWriter` | Multi-sheet Excel exports | `with pd.ExcelWriter(buffer) as writer:` |
| `groupby().agg()` | Aggregations for summary sheets | `df.groupby('col').agg({'val': 'sum'})` |

## Common Patterns

### CSV Upload Processing

**When:** User uploads CSV via FastAPI endpoint

```python
# toolbox/backend/app/api/proration.py
from fastapi import UploadFile
import pandas as pd

async def process_upload(file: UploadFile):
    """Read uploaded CSV into DataFrame"""
    contents = await file.read()
    df = pd.read_csv(
        BytesIO(contents),
        dtype=str,
        encoding='utf-8-sig'  # Handle Excel BOM
    )
    
    # Validate required columns
    required = ['Mineral Holder', 'NRI', 'Gross Acres']
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise HTTPException(400, f"Missing columns: {missing}")
    
    return df.to_dict('records')
```

### Boolean Masking for Filtering

**When:** Filter DataFrame by multiple conditions (RRC lease lookups)

```python
# GOOD - Use boolean masks for readable multi-condition filters
mask = (
    (df['LEASE_NO'] == lease_number) &
    (df['DISTRICT'] == district) &
    (df['WELL_TYPE'] == 'OIL')
)
filtered = df[mask]

# BAD - Chaining .loc[] calls is slower and harder to read
filtered = df.loc[df['LEASE_NO'] == lease_number]
filtered = filtered.loc[filtered['DISTRICT'] == district]
```

## See Also

- [patterns](references/patterns.md) - CSV/Excel processing patterns, dtype handling, export formatting
- [workflows](references/workflows.md) - End-to-end document processing flows, RRC data sync workflow

## Related Skills

- **python** - Base language patterns, snake_case naming, type hints
- **pydantic** - Validate DataFrames before converting to Pydantic models
- **fastapi** - Process uploaded CSV/Excel files in route handlers

## Documentation Resources

> Fetch latest pandas documentation with Context7.

**How to use Context7:**
1. Use `mcp__plugin_context7_context7__resolve-library-id` to search for "pandas"
2. **Prefer website documentation** (IDs starting with `/websites/`) over source code repositories when available
3. Query with `mcp__plugin_context7_context7__query-docs` using the resolved library ID

**Library ID:** Resolve using `mcp__plugin_context7_context7__resolve-library-id`, prefer `/websites/` when available

**Recommended Queries:**
- "pandas read_csv dtype parameter"
- "pandas ExcelWriter multiple sheets"
- "pandas groupby aggregation"
- "pandas boolean masking multiple conditions"
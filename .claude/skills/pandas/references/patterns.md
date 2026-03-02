# Pandas Patterns Reference

## Contents
- CSV Reading with dtype Preservation
- In-Memory Caching Pattern
- Excel Export Patterns
- DataFrame Validation
- Boolean Masking for Queries
- Aggregations and Grouping
- WARNING: Common Anti-Patterns

---

## CSV Reading with dtype Preservation

### WARNING: Leading Zeros Loss

**The Problem:**

```python
# BAD - Loses leading zeros in lease numbers
df = pd.read_csv('rrc_data.csv')
# Lease "00123456" becomes 123456 (integer)
```

**Why This Breaks:**
1. **Data corruption:** Lease number "00123456" != "123456" in RRC system
2. **Lookup failures:** String matching fails when querying by lease number
3. **Silent data loss:** No error, just wrong results

**The Fix:**

```python
# GOOD - Preserves all values as strings
df = pd.read_csv(
    'rrc_data.csv',
    dtype=str,  # Force all columns to string
    na_values=[''],  # Treat empty strings as NA
    keep_default_na=False  # Don't convert "NA", "null" strings to NaN
)
```

**When You Might Be Tempted:**
- "I'll just convert specific columns after reading" — You've already lost the data
- "I'll use converters parameter" — Just use `dtype=str`, it's simpler

**Real Example from Codebase:**

```python
# toolbox/backend/app/services/proration/csv_processor.py
def load_csv(self, file_path: str, well_type: str) -> pd.DataFrame:
    df = pd.read_csv(
        file_path,
        dtype=str,  # CRITICAL for RRC lease numbers
        na_values=[''],
        keep_default_na=False
    )
    return df
```

---

## In-Memory Caching Pattern

**Use for:** Large datasets (50k+ rows) that need fast repeated lookups during batch processing.

### Basic Pattern

```python
# toolbox/backend/app/services/proration/csv_processor.py
class CSVProcessor:
    def __init__(self):
        self._oil_df: pd.DataFrame | None = None
        self._gas_df: pd.DataFrame | None = None
    
    def load_oil_data(self, file_path: str) -> None:
        """Load once, query many times"""
        self._oil_df = pd.read_csv(file_path, dtype=str)
    
    def query_lease(self, lease_no: str, district: str) -> pd.DataFrame:
        """Fast in-memory lookup"""
        if self._oil_df is None:
            raise ValueError("Oil data not loaded")
        return self._oil_df[
            (self._oil_df['LEASE_NO'] == lease_no) &
            (self._oil_df['DISTRICT'] == district)
        ]
```

**Why This Works:**
- **100k row CSV:** Load once (2-3s) → query 500 times (0.001s each) vs re-reading CSV 500 times (1500s total)
- **Memory cost:** ~50MB for 100k rows with 20 columns (acceptable for server with 1Gi RAM)

**When NOT to Use:**
- Dataset > 500k rows → Consider chunking or database
- Data changes frequently → Cache invalidation becomes complex
- Multiple processes → Use shared cache (Redis) instead

---

## Excel Export Patterns

### Multi-Sheet Export with Summary

```python
# toolbox/backend/app/services/proration/export_service.py
from io import BytesIO
import pandas as pd

def create_proration_excel(results: list[dict]) -> BytesIO:
    """Export with Detail + Summary sheets"""
    df = pd.DataFrame(results)
    
    # Summary sheet with aggregations
    summary = df.groupby('operator_name').agg({
        'net_revenue_acres': 'sum',
        'gross_acres': 'sum',
        'lease_count': 'count'
    }).reset_index()
    
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        # Detail sheet
        df.to_excel(
            writer,
            sheet_name='Proration Detail',
            index=False,
            freeze_panes=(1, 0)  # Freeze header row
        )
        
        # Summary sheet
        summary.to_excel(
            writer,
            sheet_name='Summary',
            index=False
        )
    
    buffer.seek(0)
    return buffer
```

**Key Details:**
- `engine='openpyxl'` → Required for `.xlsx` format
- `freeze_panes=(1, 0)` → Freeze top row for scrolling
- `index=False` → Exclude DataFrame index from export
- `buffer.seek(0)` → Reset buffer position for reading

### Column Formatting

```python
# Format currency columns
with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
    df.to_excel(writer, sheet_name='Detail', index=False)
    
    # Access workbook for formatting
    worksheet = writer.sheets['Detail']
    for row in worksheet.iter_rows(min_row=2, max_row=worksheet.max_row, min_col=5, max_col=5):
        for cell in row:
            cell.number_format = '$#,##0.00'
```

---

## DataFrame Validation

### Column Validation Pattern

```python
# toolbox/backend/app/services/title/csv_processor.py
def validate_columns(df: pd.DataFrame, required: list[str]) -> None:
    """Validate required columns exist"""
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(
            f"Missing required columns: {', '.join(missing)}. "
            f"Found: {', '.join(df.columns)}"
        )

# Usage in route handler
required_cols = ['Mineral Holder', 'NRI', 'Gross Acres']
validate_columns(df, required_cols)
```

### Data Type Validation

```python
def validate_numeric_column(df: pd.DataFrame, col: str) -> None:
    """Ensure column can be converted to numeric"""
    try:
        pd.to_numeric(df[col], errors='raise')
    except (ValueError, TypeError) as e:
        invalid_values = df[~df[col].str.match(r'^[\d.]+$', na=False)][col].unique()
        raise ValueError(
            f"Column '{col}' contains non-numeric values: {invalid_values[:5]}"
        ) from e

# Validate before calculations
validate_numeric_column(df, 'NRI')
df['NRI'] = pd.to_numeric(df['NRI'])
```

---

## Boolean Masking for Queries

### Multi-Condition Filtering

```python
# GOOD - Readable boolean mask
mask = (
    (df['LEASE_NO'] == lease_number) &
    (df['DISTRICT'] == district) &
    (df['WELL_TYPE'].isin(['OIL', 'GAS']))
)
results = df[mask]

# BAD - Chained .loc[] calls (slower, less readable)
results = df.loc[df['LEASE_NO'] == lease_number]
results = results.loc[results['DISTRICT'] == district]
results = results.loc[results['WELL_TYPE'].isin(['OIL', 'GAS'])]
```

### String Pattern Matching

```python
# Case-insensitive partial match
mask = df['operator_name'].str.contains('ENERGY', case=False, na=False)
matching_operators = df[mask]

# Exact match with null handling
mask = (df['status'] == 'ACTIVE') & df['status'].notna()
active_records = df[mask]
```

---

## Aggregations and Grouping

### Summary Statistics by Group

```python
# toolbox/backend/app/services/proration/calculation_service.py
def calculate_operator_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate NRA by operator"""
    summary = df.groupby('operator_name').agg({
        'net_revenue_acres': ['sum', 'mean', 'count'],
        'gross_acres': 'sum'
    }).reset_index()
    
    # Flatten multi-level columns
    summary.columns = [
        'operator_name',
        'total_nra',
        'avg_nra',
        'lease_count',
        'total_gross_acres'
    ]
    
    return summary.sort_values('total_nra', ascending=False)
```

### Custom Aggregation Functions

```python
def weighted_average(group: pd.DataFrame) -> float:
    """Calculate weighted average NRI by gross acres"""
    return (group['nri'] * group['gross_acres']).sum() / group['gross_acres'].sum()

summary = df.groupby('lease_number').apply(
    weighted_average
).reset_index(name='weighted_avg_nri')
```

---

## WARNING: Common Anti-Patterns

### Anti-Pattern 1: SettingWithCopyWarning

**The Problem:**

```python
# BAD - Triggers SettingWithCopyWarning
filtered = df[df['status'] == 'ACTIVE']
filtered['new_col'] = filtered['old_col'] * 2  # WARNING!
```

**Why This Breaks:**
- `filtered` might be a view, not a copy
- Assignment might not modify the original DataFrame
- Leads to silent bugs where data isn't updated

**The Fix:**

```python
# GOOD - Explicit copy
filtered = df[df['status'] == 'ACTIVE'].copy()
filtered['new_col'] = filtered['old_col'] * 2

# GOOD - Modify original in-place with .loc
df.loc[df['status'] == 'ACTIVE', 'new_col'] = df.loc[df['status'] == 'ACTIVE', 'old_col'] * 2
```

### Anti-Pattern 2: Iterating Over Rows

**The Problem:**

```python
# BAD - Extremely slow for large DataFrames
for index, row in df.iterrows():
    df.at[index, 'result'] = row['value1'] + row['value2']
```

**Why This Breaks:**
- **Performance:** 100x-1000x slower than vectorized operations
- For 100k rows: `iterrows()` = 30s, vectorized = 0.03s

**The Fix:**

```python
# GOOD - Vectorized operations
df['result'] = df['value1'] + df['value2']

# GOOD - apply() for complex logic
def complex_calc(row):
    return row['value1'] * 0.8 if row['status'] == 'ACTIVE' else row['value1'] * 0.5

df['result'] = df.apply(complex_calc, axis=1)
```

**When You Might Be Tempted:**
- "I need row-by-row logic" → Use `apply()` or vectorized conditions
- "It's only 100 rows" → Still use vectorized for consistency

### Anti-Pattern 3: Chained Indexing

**The Problem:**

```python
# BAD - Chained indexing (ambiguous)
df[df['status'] == 'ACTIVE']['new_col'] = 10  # Might not work
```

**The Fix:**

```python
# GOOD - Use .loc for assignment
df.loc[df['status'] == 'ACTIVE', 'new_col'] = 10
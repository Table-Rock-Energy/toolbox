# Pandas Patterns Reference

## Contents
- CSV Loading Patterns
- Filtering and Lookup
- Export Patterns
- WARNING: Anti-Patterns

---

## CSV Loading Patterns

Always load with `dtype=str` and `keep_default_na=False` for document data. RRC lease numbers like `42-501` become floats (`42.0`) without `dtype=str`.

```python
# GOOD - safe for all document data
df = pd.read_csv(path, dtype=str, keep_default_na=False)
df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
```

```python
# For multi-sheet Excel (title opinions)
def read_excel_sheet(path: str, sheet: int = 0) -> pd.DataFrame:
    return pd.read_excel(path, sheet_name=sheet, dtype=str, keep_default_na=False)
```

Normalize column names immediately after load — never reference raw column strings from external CSVs without stripping/lowercasing first.

---

## Filtering and Lookup

### Case-insensitive string match

```python
# GOOD - handles mixed case from user input and RRC data
mask = df["operator_name"].str.upper().str.strip() == operator.upper().strip()
results = df[mask]
```

### Partial match for fuzzy lease lookup

```python
def search_leases(df: pd.DataFrame, query: str) -> pd.DataFrame:
    q = query.strip().upper()
    return df[
        df["lease_name"].str.upper().str.contains(q, na=False, regex=False)
    ]
```

### Safe `.iloc` / `.loc` when result may be empty

```python
results = df[mask]
if results.empty:
    return None
return results.iloc[0].to_dict()
```

---

## Export Patterns

### In-memory Excel export (for API response or GCS upload)

```python
import io
import pandas as pd

def export_excel(records: list[dict], sheet_name: str = "Results") -> bytes:
    df = pd.DataFrame(records)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return buf.getvalue()
```

### CSV export with explicit encoding

```python
def export_csv(records: list[dict]) -> bytes:
    df = pd.DataFrame(records)
    return df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
```

Use `utf-8-sig` (UTF-8 with BOM) for CSVs opened in Excel — plain `utf-8` causes encoding issues with special characters in owner names.

---

## WARNING: Anti-Patterns

### WARNING: Reading without `dtype=str`

**The Problem:**
```python
# BAD - numeric columns get coerced
df = pd.read_csv("rrc_data.csv")
# RRC operator number "042501" → 42501 (leading zeros lost)
# API number "42-501-12345-0001" may parse as float
```

**Why This Breaks:**
1. Lease/operator numbers with leading zeros are silently corrupted
2. String comparisons fail because `"042501" != 42501`
3. Data exported back to CSV will have wrong values

**The Fix:**
```python
df = pd.read_csv("rrc_data.csv", dtype=str, keep_default_na=False)
```

---

### WARNING: Chained assignment

**The Problem:**
```python
# BAD - SettingWithCopyWarning, may not modify the original
df[df["status"] == "active"]["count"] = 0
```

**Why This Breaks:** Pandas may return a copy, silently leaving the original unchanged. This causes hard-to-debug data integrity issues.

**The Fix:**
```python
# GOOD - use .loc
df.loc[df["status"] == "active", "count"] = 0
```

---

### WARNING: Iterating rows with `iterrows()`

**The Problem:**
```python
# BAD - extremely slow for >1000 rows
for idx, row in df.iterrows():
    results.append(process(row["lease_name"]))
```

**Why This Breaks:** `iterrows()` is 10-100x slower than vectorized operations. For RRC datasets with 50k+ rows, this is a multi-second bottleneck in a sync route handler.

**The Fix:**
```python
# GOOD - vectorized
df["processed"] = df["lease_name"].str.upper().str.strip()

# Or for complex logic, use apply() — still faster than iterrows
df["result"] = df["lease_name"].apply(process)
```

---

### WARNING: Global DataFrame mutated by concurrent requests

**The Problem:**
```python
_cache: pd.DataFrame = None

def filter_data(query: str) -> pd.DataFrame:
    _cache.drop_duplicates(inplace=True)  # BAD - mutates shared state
    return _cache[_cache["name"] == query]
```

**Why This Breaks:** FastAPI serves concurrent requests. `inplace=True` on a shared DataFrame is a race condition — one request's in-place operation corrupts another's view.

**The Fix:**
```python
def filter_data(query: str) -> pd.DataFrame:
    return _cache[_cache["name"] == query].copy()  # GOOD - never mutate _cache
```

Never use `inplace=True` on the cached DataFrame. Always return filtered copies.
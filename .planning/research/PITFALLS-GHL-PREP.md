# Domain Pitfalls: CSV Transformation Tools (GHL Prep)

**Domain:** CSV data transformation with title-casing, JSON parsing, and column manipulation
**Researched:** 2026-02-25
**Context:** Adding GHL Prep tool to existing Table Rock TX Tools (React + FastAPI toolbox)

## Critical Pitfalls

Mistakes that cause rewrites, data corruption, or production outages.

### Pitfall 1: Title-Casing Destroys Name Capitalization Patterns
**What goes wrong:** Python's built-in `str.title()` treats apostrophes and hyphens as word boundaries, converting "O'BRIEN" to "O'Brien" (correct) but also converting "MCDONALD" to "Mcdonald" (incorrect). Scottish/Irish name prefixes (Mc, Mac, O'), compound surnames, and generational suffixes (Jr, III, Sr) are mishandled.

**Why it happens:** `title()` capitalizes every letter following a non-letter character. It has no concept of proper name conventions or linguistic rules. "MCCALL" becomes "Mccall" instead of "McCall", "DEANGELO" becomes "Deangelo" instead of "DeAngelo", "O'REILLY" becomes "O'Reilly" (correct by chance), but "MC CANN" (with space) becomes "Mc Cann" instead of "McCann".

**Consequences:**
- Contact names in GoHighLevel will be incorrectly capitalized
- "JOHN MCDONALD JR" → "John Mcdonald Jr" (should be "John McDonald Jr")
- "MARY O'BRIEN III" → "Mary O'Brien Iii" (should be "Mary O'Brien III")
- Data quality degradation that's difficult to detect and expensive to fix
- Users lose trust in the tool when they see obviously wrong names

**Prevention:**
1. Use the `titlecase` library (pypi.org/project/titlecase) which handles many edge cases correctly
2. Maintain an exception dictionary for known patterns (Mc*, Mac*, O'*, De*, Van*, Von*, etc.)
3. Preserve all-caps suffixes: Jr, Sr, II, III, IV, PhD, MD, etc.
4. Add validation warnings when names contain suspicious patterns (all lowercase after Mc/Mac)
5. Provide a "review mode" showing before/after for first 10 records before full transformation
6. Document known limitations (e.g., "iPhone" will become "Iphone") in user-facing docs

**Detection:**
- Unit tests with known edge cases (McDonald, O'Brien, McConnell, DeAngelo, Van Buren)
- QA review with real Mineral export data before launch
- Warning flag when >5% of names contain "Mc" or "O'" followed by lowercase letters

**Sources:**
- [Python Morsels: Title-case a String](https://www.pythonmorsels.com/title-case-in-python/)
- [Propercasing last names in Python](https://casavant.org/technical/2018/01/28/propercasing-last-names.html)
- [Python Issue 7008: str.title() misbehaves with apostrophes](https://bugs.python.org/issue7008)
- [ESRI Community: Proper case for names beginning with Mc](https://community.esri.com/t5/python-questions/proper-case-for-names-beginning-with-mc-like/td-p/1381730)

### Pitfall 2: JSON Parsing Fails Silently on Malformed Data
**What goes wrong:** The Campaigns column in Mineral exports contains JSON strings like `[{"unit": "ACME 1"}]`, but malformed JSON (missing quotes, unescaped quotes, trailing commas, single quotes instead of double quotes) causes `json.loads()` to raise exceptions. If not caught properly, one bad row fails the entire batch.

**Why it happens:**
- Mineral may change export formatting without notice
- User data entry in Mineral creates invalid JSON (copy-paste from Excel adds smart quotes)
- String escaping issues when CSV contains quotes: `"[{\"unit\": \"ACME 1\"}]"` vs `[{"unit": "ACME 1"}]`
- Empty JSON arrays, null values, or completely non-JSON text in the Campaigns column

**Consequences:**
- Tool crashes mid-processing, leaving partial/corrupted output
- Silent failures where campaigns aren't extracted but no error is raised
- Row-level failures aren't logged, making debugging impossible
- Users lose work when the tool stops at row 3,427 of 10,000

**Prevention:**
1. Use `json_repair` library (github.com/mangiucugna/json_repair) as fallback for malformed JSON
2. Try-except with detailed logging: capture row number, raw value, error message
3. Continue processing with null/blank campaign when JSON fails (don't fail entire batch)
4. Add validation step: parse all JSON fields first, report failures before transformation
5. Use pandas error handling: `errors='coerce'` for JSON columns (returns null on failure)
6. Provide CSV validation endpoint that reports all JSON parsing errors upfront

**Detection:**
- Pre-flight validation: parse all JSON fields, collect errors, return to user
- Unit tests with malformed JSON: `[{"unit": "ACME 1}]` (missing quote), `{'unit': 'ACME 1'}` (single quotes)
- Monitor Sentry/logs for JSON decode exceptions with row context
- Warning count in UI: "15 rows had invalid campaign data and were skipped"

**Sources:**
- [Python JSON Parsing with Escaped Double Quotes](https://www.py4u.org/blog/python-parsing-json-with-escaped-double-quotes/)
- [json_repair library on GitHub](https://github.com/mangiucugna/json_repair)
- [Real-World Solution to Escape Embedded Double Quotes in JSON](https://kevinquinn.fun/blog/a-real-world-solution-to-escape-embedded-double-quotes-in-json/)
- [Single vs Double Quotes in Python JSON: Practical Guide for 2026](https://thelinuxcode.com/single-vs-double-quotes-in-python-json-practical-guide-for-2026/)

### Pitfall 3: CSV Encoding Corrupts Special Characters
**What goes wrong:** Mineral exports may include UTF-8 BOM (byte order mark), Latin-1 encoded characters, or mixed encodings. Without explicit encoding handling, special characters in names (é, ñ, ü, —) become mojibake (Ã©, Ã±, Ã¼) or cause decode errors. The BOM appears as `ï»¿` at the start of the first column name.

**Why it happens:**
- Mineral export settings may vary by user or export method
- Excel saves CSVs with UTF-8 BOM by default on Windows
- User edits CSV in Excel, saves with different encoding
- Mixed data sources: some rows UTF-8, some Windows-1252

**Consequences:**
- First column name becomes `ï»¿Name` instead of `Name`, breaking column detection
- Names with accents render incorrectly: "José García" → "JosÃ© GarcÃ­a"
- GoHighLevel import fails due to encoding mismatch
- Silent data corruption that's only visible in downstream system

**Prevention:**
1. Use `encoding='utf-8-sig'` in `pandas.read_csv()` (automatically strips BOM)
2. Fallback encoding chain: try UTF-8-sig → UTF-8 → Latin-1 → Windows-1252
3. Detect encoding with `chardet` library before parsing large files
4. Validate first column name matches expected pattern (no BOM characters)
5. Export CSVs with explicit UTF-8 (no BOM) using `encoding='utf-8'` in `to_csv()`
6. Log encoding used for debugging: "Detected UTF-8-BOM encoding, stripped BOM"

**Detection:**
- Check first column name for BOM: `df.columns[0].startswith('\ufeff')`
- Unit tests with UTF-8-BOM sample files, Latin-1 files, mixed encoding files
- Validate character rendering: assert "José" not in ["JosÃ©", "Jos?", "Jos_"]
- Pre-flight encoding validation: report detected encoding to user

**Sources:**
- [How to Read UTF-8 with BOM CSV Files in Python](https://www.w3reference.com/blog/reading-utf-8-with-bom-using-python-csv-module-causes-unwanted-extra-characters/)
- [CSV Encoding Problems: UTF-8, BOM, and Character Issues - Complete Guide 2025](https://www.elysiate.com/blog/csv-encoding-problems-utf8-bom-character-issues)
- [pandas to_csv encoding issue #44323](https://github.com/pandas-dev/pandas/issues/44323)
- [List of Pandas read_csv Encoding Options](https://saturncloud.io/blog/a-list-of-pandas-readcsv-encoding-options/)

### Pitfall 4: Column Detection Breaks When Source Format Changes
**What goes wrong:** Hard-coded column names ("Phone 1", "Campaigns", "Contact Owner") stop working when Mineral changes export format. Columns get renamed ("Phone 1" → "Primary Phone"), reordered, or removed entirely. Tool crashes with KeyError or produces blank output.

**Why it happens:**
- Mineral export format isn't versioned or documented
- Different Mineral workspaces export different column sets
- User customizes Mineral export template
- Spaces vs underscores: "Contact Owner" vs "Contact_Owner" vs "ContactOwner"
- Column name changes: "Phone 1" → "Phone1" → "Primary Phone"

**Consequences:**
- Tool breaks in production with no warning
- Silent failures: missing columns result in blank data
- No way to detect format version from CSV content
- Users blame the tool, not Mineral's format change

**Prevention:**
1. Use flexible column matching: try exact match → case-insensitive → fuzzy match → synonym lookup
2. Maintain column alias dictionary: `{"Phone 1": ["Phone1", "Primary Phone", "Phone", "Mobile"]}`
3. Validate required columns exist before processing: return clear error if missing
4. Version detection: check for known column sets, log detected version
5. Allow user column mapping UI: "Map your CSV columns to GHL format"
6. Store column mapping per workspace/user in Firestore for reuse

**Detection:**
- Pre-flight column validation: check required columns exist, suggest alternatives if missing
- Unit tests with multiple Mineral export formats (current + past versions)
- Log column names on every upload: track format drift over time
- Alert when unknown column set detected: "New Mineral format detected, columns: [...]"

**Sources:**
- [5 Common Data Import Errors and How to Fix Them](https://dromo.io/blog/common-data-import-errors-and-how-to-fix-them)
- [CSV Data Transformation Guide: Cleaning & Importing Client Data](https://dataflowmapper.com/blog/csv-data-transformation-guide-cleaning-import)
- [PandasSchema documentation](https://multimeric.github.io/PandasSchema/)
- [csv_file_validator on GitHub](https://github.com/datahappy1/csv_file_validator)

## Moderate Pitfalls

Issues that cause rework, confusion, or data quality problems but aren't critical.

### Pitfall 5: Phone Number Formatting Edge Cases
**What goes wrong:** Phone numbers in Mineral exports appear in multiple formats: "(512) 555-1234", "512-555-1234", "5125551234", "+1 512 555 1234", "555-1234" (missing area code), "512.555.1234". Mapping "Phone 1" to primary "Phone" field works for well-formatted numbers but breaks on edge cases.

**Why it happens:**
- User data entry is inconsistent
- Different import sources use different formats
- International numbers: +44, +52, +1
- Extensions: "512-555-1234 x105"
- Multiple numbers in one field: "512-555-1234 or 512-555-5678"

**Consequences:**
- GoHighLevel rejects improperly formatted phone numbers
- Silent data loss: numbers that don't match E.164 format are dropped
- Duplicate detection fails: "(512) 555-1234" ≠ "5125551234"

**Prevention:**
1. Normalize to E.164 format (+1XXXXXXXXXX for US) using `phonenumbers` library
2. Default country code to US (+1) if missing, make configurable
3. Handle extensions separately: extract "x105" to Notes field
4. Validate phone number length: US = 10 digits (after country code)
5. Log formatting failures: "Row 42: '555-1234' missing area code, skipped"
6. Provide phone number validation warnings before export

**Detection:**
- Unit tests with format variations: "(512) 555-1234", "5125551234", "+1-512-555-1234", "555-1234"
- Pre-flight validation: count how many phone numbers fail E.164 parsing
- Warning in UI: "15 phone numbers could not be formatted (missing area code)"

**Sources:**
- [What is E.164 Format? | Twilio](https://www.twilio.com/docs/glossary/what-e164)
- [How to untangle phone numbers](https://factbranch.com/blog/2024/normalize-phone-numbers/)
- [E.164 Format for International Phone Number Standardization](https://www.bandwidth.com/glossary/e164/)

### Pitfall 6: Null/Empty/Blank Value Inconsistency
**What goes wrong:** Pandas reads empty CSV cells as `NaN`, quoted empty strings `""` as empty strings, and missing columns as errors. When exporting, `NaN` becomes empty string, but code that checks `if value:` treats both as falsy. Different tools interpret null/empty/blank differently.

**Why it happens:**
- CSV has no native null type
- pandas defaults: empty cell → NaN, `""` → empty string, missing column → KeyError
- Python's truthy/falsy evaluation: `None`, `NaN`, `""`, `0`, `[]` all falsy
- GoHighLevel may require explicit empty string for "blank" vs null for "not provided"

**Consequences:**
- "Contact Owner" field: user wants blank (so GHL assigns default) but gets NaN (error)
- Inconsistent behavior: some rows have `""`, some have `NaN`, GHL treats differently
- Conditional logic breaks: `if row['Campaigns']:` skips both NaN and empty string

**Prevention:**
1. Use `keep_default_na=False` if you need to preserve empty strings vs NaN distinction
2. Fill NaN values explicitly: `df.fillna('')` or `df.fillna('BLANK')`
3. Use `.notna()` / `.isna()` for pandas null checks, not `if value:`
4. Standardize before export: decide whether blank = `""` or blank = omit column
5. Document null handling behavior in code comments

**Detection:**
- Unit tests with null, NaN, empty string, missing column scenarios
- Log null handling: "Replaced 42 NaN values with empty string in Contact Owner"
- Validate exported CSV: ensure consistent null representation

**Sources:**
- [Pandas for SQL Lovers: Handling Nulls read from CSV](https://susanibach.wordpress.com/2019/08/14/pandas-for-sql-lovers-part-4-handling-nulls-read-from-csv/)
- [How to Preserve Empty Strings While Converting Blank Cells to NaN](https://iifx.dev/en/articles/460160622/how-to-preserve-empty-strings-while-converting-blank-cells-to-nan-in-pandas)
- [Preventing strings from getting parsed as NaN](https://www.skytowner.com/explore/preventing_strings_from_getting_parsed_as_nan_for_read_csv_in_pandas)

### Pitfall 7: Memory Usage Explodes with Large CSVs
**What goes wrong:** Loading a 50MB CSV (10K rows) into pandas consumes 500MB+ RAM because pandas stores data inefficiently by default. Processing 100K+ row exports causes Cloud Run instances (1GB RAM) to OOM crash.

**Why it happens:**
- Pandas defaults all numeric columns to int64/float64 (8 bytes each)
- String columns stored as Python objects (high overhead)
- Intermediate DataFrames during transformation double memory usage
- No chunking: entire file loaded into memory at once

**Consequences:**
- Cloud Run instance crashes mid-processing
- Slow processing: GC thrashing when near memory limit
- Cannot process large exports (users hit file size limit)

**Prevention:**
1. Use `dtype` parameter: specify int8/int16 for small numbers, category for repeated strings
2. Use `usecols` to load only needed columns (skip unused columns from Mineral export)
3. Process in chunks: `pd.read_csv(chunksize=1000)` for 100K+ row files
4. Use `.copy()` carefully: avoid unnecessary DataFrame copies
5. Monitor memory: log memory usage before/after processing
6. Increase Cloud Run memory to 2GB if needed (still optimize code first)

**Detection:**
- Load testing with 10K, 50K, 100K row CSVs
- Memory profiling: `memory_profiler` or Cloud Run memory metrics
- Unit test: process 10K row file, assert memory usage < 200MB

**Sources:**
- [Scaling to large datasets — pandas documentation](https://pandas.pydata.org/docs/user_guide/scale.html)
- [Simple pandas read_csv tricks to boost speed up to 250x](https://medium.com/@sumakbn/data-handling-done-right-quick-tips-for-large-csvs-with-pandas-21c25f91380f)
- [How to Handle Large Data Processing with Pandas](https://oneuptime.com/blog/post/2026-02-02-python-pandas-large-data/view)

## Minor Pitfalls

Issues that cause annoyance or minor data quality issues but are easily fixed.

### Pitfall 8: Case Sensitivity in Column Matching
**What goes wrong:** Code checks `if 'Phone 1' in df.columns:` but CSV has "phone 1" or "PHONE 1", causing column to be skipped. CSV column names are case-sensitive in pandas.

**Prevention:**
- Normalize column names on load: `df.columns = df.columns.str.lower().str.strip()`
- Use case-insensitive matching: `df.columns.str.lower().isin(['phone 1', 'phone1'])`

**Detection:** Unit tests with mixed-case column names

### Pitfall 9: Leading/Trailing Whitespace in Data
**What goes wrong:** CSV cells contain "  John Doe  " (spaces), title-casing produces "  John Doe  ", GHL rejects leading spaces or treats as different name.

**Prevention:**
- Strip whitespace on load: `df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)`
- Apply before title-casing to avoid "  john doe  " → "  John Doe  "

**Detection:** Unit test with padded whitespace in names/fields

### Pitfall 10: Excel Date Auto-Conversion Corruption
**What goes wrong:** User opens Mineral CSV in Excel before uploading. Excel auto-converts "1-2" (lease name) to "Jan-2" (date), "3-14" to "Mar-14", phone numbers to scientific notation.

**Prevention:**
- Detect Excel corruption: check for date-like values in unexpected columns
- Warn user: "Detected possible Excel corruption in 3 rows (lease names look like dates)"
- Document: "Do not open CSV in Excel before uploading"

**Detection:** Regex patterns for Excel date formats (MMM-DD, MM/DD/YYYY) in non-date columns

### Pitfall 11: Duplicate Column Names
**What goes wrong:** Mineral export has two columns named "Phone" (Phone 1 and Phone 2 both export as "Phone"). Pandas renames to "Phone" and "Phone.1" but code expects "Phone 2".

**Prevention:**
- Check for duplicate columns: `assert df.columns.is_unique`
- Use positional access if needed: `df.iloc[:, 5]` instead of `df['Phone']`

**Detection:** Pre-flight validation logs duplicate column names

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Phase 1: Basic GHL Prep Implementation | Hard-coded column names break on format changes | Implement flexible column matching + alias dictionary early |
| Phase 1: Title-Casing | Using `str.title()` directly creates unfixable name corruption | Use `titlecase` library from day 1, add exception dictionary |
| Phase 1: JSON Parsing | Malformed JSON crashes entire batch | Add try-except with row-level error logging, continue on failure |
| Phase 2: Production Deployment | CSV encoding issues only appear with real user data | Test with UTF-8-BOM files, Latin-1 files before launch |
| Phase 2: Large File Handling | Cloud Run OOM with 50K+ row files | Add memory profiling, chunking for large files |
| Phase 3: User Feedback Integration | Phone number edge cases discovered post-launch | Plan for phone number normalization library integration |
| Phase 3: Column Mapping UI | Users expect GUI column mapper, not hard-coded mapping | Design flexible column mapping storage in Firestore early |

## Integration Pitfalls (Adding to Existing Toolbox)

### Pitfall 12: Inconsistent Error Handling Across Tools
**What goes wrong:** Existing tools (Extract, Title, Proration, Revenue) use different error response formats. GHL Prep uses yet another format. Frontend expects one format, breaks with another.

**Prevention:**
- Review existing error handling patterns in `api/extract.py`, `api/title.py`
- Use consistent HTTPException format: `{"error": "message", "details": {...}, "row": N}`
- Update frontend error display to handle all formats or standardize backend

**Detection:** Integration tests across tools, check error response schemas match

### Pitfall 13: File Upload Storage Conflicts
**What goes wrong:** GHL Prep saves to `gcs_bucket/ghl-prep/uploads/` but StorageService expects consistent path structure. Different tools use different path conventions.

**Prevention:**
- Follow existing storage conventions: review `storage_service.py` path structure
- Use tool-specific folders consistently: `{tool_name}/uploads/`, `{tool_name}/exports/`
- Check if Firestore job metadata expects specific path format

**Detection:** Review storage paths used by existing tools, maintain consistency

### Pitfall 14: Shared Component Breaking Changes
**What goes wrong:** GHL Prep needs slightly different FileUpload behavior (only CSV, not PDF). Modifying shared component breaks existing tools.

**Prevention:**
- Pass file type restrictions as props: `<FileUpload accept=".csv" />`
- Don't modify shared component behavior without testing all consumers
- Consider tool-specific wrapper if behavior diverges significantly

**Detection:** Run existing tool tests after shared component changes

### Pitfall 15: API Route Prefix Collision
**What goes wrong:** Registering `/api/ghl-prep/upload` but existing route patterns expect `/api/ghl_prep/upload` (underscore). URL routing breaks.

**Prevention:**
- Follow existing naming: check `main.py` router prefixes (extract, title, proration use underscore or hyphen?)
- Use consistent delimiter: `/api/ghl-prep/` or `/api/ghl_prep/`
- Update frontend API client with correct endpoint

**Detection:** Review existing route registrations in `backend/app/main.py`

### Pitfall 16: Firestore Collection Naming Collision
**What goes wrong:** GHL Prep uses `jobs` collection but existing tools also use `jobs`. Queries return wrong data.

**Prevention:**
- Review `firestore_service.py` collection naming conventions
- Use tool-specific subcollections or tool field filter: `jobs/{job_id}` with `tool: "ghl-prep"`
- Check existing tools' Firestore schema before designing new collections

**Detection:** Review Firestore structure, check existing job documents

## Validation Strategy

### Pre-Flight Validation (Before Processing)
1. **Encoding detection**: Try UTF-8-sig, log detected encoding
2. **Column validation**: Check required columns exist, suggest aliases if missing
3. **Row count check**: Warn if >50K rows (memory concerns)
4. **JSON validation**: Parse all JSON fields, report errors with row numbers
5. **Phone number preview**: Show sample formatted phone numbers for validation
6. **Title-case preview**: Show first 10 name transformations for user review

### Post-Processing Validation (Before Export)
1. **Name corruption check**: Flag names with suspicious patterns (Mc[a-z], O'[a-z])
2. **Null consistency**: Verify consistent null/empty handling across all rows
3. **Column completeness**: Warn if required GHL columns are mostly empty
4. **Phone format check**: Count how many phones failed E.164 parsing
5. **Character encoding**: Verify no mojibake in output

### Runtime Monitoring
1. **Memory usage**: Log memory before/after pandas operations
2. **Processing time**: Track per-row processing time, alert if >100ms average
3. **Error rate**: Track row-level errors, alert if >5% failure rate
4. **Format detection**: Log detected Mineral export version/format

## Sources Summary

**Title-Casing Issues:**
- [Python Morsels: Title-case a String](https://www.pythonmorsels.com/title-case-in-python/)
- [Propercasing last names in Python](https://casavant.org/technical/2018/01/28/propercasing-last-names.html)
- [Python Bug Tracker: str.title() misbehaves with apostrophes](https://bugs.python.org/issue7008)

**JSON Parsing:**
- [Python JSON Parsing with Escaped Quotes](https://www.py4u.org/blog/python-parsing-json-with-escaped-double-quotes/)
- [json_repair library](https://github.com/mangiucugna/json_repair)
- [Single vs Double Quotes in Python JSON 2026](https://thelinuxcode.com/single-vs-double-quotes-in-python-json-practical-guide-for-2026/)

**CSV Encoding:**
- [Reading UTF-8 with BOM in Python](https://www.w3reference.com/blog/reading-utf-8-with-bom-using-python-csv-module-causes-unwanted-extra-characters/)
- [CSV Encoding Problems Guide 2025](https://www.elysiate.com/blog/csv-encoding-problems-utf8-bom-character-issues)
- [Pandas Encoding Options](https://saturncloud.io/blog/a-list-of-pandas-readcsv-encoding-options/)

**Column Detection & Validation:**
- [Common Data Import Errors](https://dromo.io/blog/common-data-import-errors-and-how-to-fix-them)
- [CSV Data Transformation Guide](https://dataflowmapper.com/blog/csv-data-transformation-guide-cleaning-import)
- [PandasSchema documentation](https://multimeric.github.io/PandasSchema/)

**Phone Number Formatting:**
- [Twilio E.164 Format](https://www.twilio.com/docs/glossary/what-e164)
- [How to untangle phone numbers](https://factbranch.com/blog/2024/normalize-phone-numbers/)
- [E.164 Format Guide](https://www.bandwidth.com/glossary/e164/)

**Memory & Performance:**
- [Pandas Scaling to Large Datasets](https://pandas.pydata.org/docs/user_guide/scale.html)
- [Pandas read_csv speed tricks (250x faster)](https://medium.com/@sumakbn/data-handling-done-right-quick-tips-for-large-csvs-with-pandas-21c25f91380f)
- [Large Data Processing with Pandas 2026](https://oneuptime.com/blog/post/2026-02-02-python-pandas-large-data/view)

**Null Value Handling:**
- [Pandas Null Handling from CSV](https://susanibach.wordpress.com/2019/08/14/pandas-for-sql-lovers-part-4-handling-nulls-read-from-csv/)
- [Preserve Empty Strings While Converting NaN](https://iifx.dev/en/articles/460160622/how-to-preserve-empty-strings-while-converting-blank-cells-to-nan-in-pandas)
- [Preventing NaN Parsing](https://www.skytowner.com/explore/preventing_strings_from_getting_parsed_as_nan_for_read_csv_in_pandas)

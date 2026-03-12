# Phase 2: Convey 640 Processing - Research

**Researched:** 2026-03-12
**Domain:** CSV/Excel parsing, name normalization, pandas data processing
**Confidence:** HIGH

## Summary

Phase 2 builds a parser for Convey 640 CSV/Excel files that produces the same `PartyEntry` objects as the existing ECF PDF parser. The domain is well-understood: the sample file has been analyzed (357 rows, 12 columns), all edge cases catalogued, and the existing codebase provides extensive reusable infrastructure for entity detection, name parsing, and address handling.

The core challenge is name normalization -- the `name` column contains entry numbers baked in (~45% of rows), joint names with `&`, trust names with dates and trustees, deceased markers, a/k/a aliases, c/o care-of references, `CLO`/`ELO` notations (Convey 640's version of c/o), `NOW` married name patterns, and `NEE` maiden name references. The postal_code column arrives as float64 and must be converted to zero-padded 5-digit strings. Metadata (county, STR, case_no, etc.) is identical across all rows and should be extracted once.

**Primary recommendation:** Create a single `convey640_parser.py` module in `services/extract/` that reads the CSV/Excel into a pandas DataFrame with `dtype=str`, normalizes names using regex + existing patterns from `utils/patterns.py`, and returns an `ECFParseResult`-compatible structure (list of `PartyEntry` + `CaseMetadata`).

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- Strip leading entry numbers + optional period + whitespace from name column (regex like `^\d+\.?\s*`)
- ~45% of names have entry numbers prepended, ~55% don't
- Joint names with '&': first person is primary name, additional names go to notes field
- Trust names with dates: extract grantor's personal name as primary, trustee name goes to notes
- "deceased" markers: strip from name, set entity_type=ESTATE
- "now [married name]" patterns: use current/married name as primary, maiden name in notes
- Run entity type detection on CSV names using existing patterns
- Expected 12 columns: county, str, applicant, classification, case_no, curative, _date, name, address, city, state, postal_code
- `curative` (0/1) maps to section_type: 0 -> 'regular', 1 -> 'curative'
- `case_no` (numeric 2026000909) normalized to PDF format: 'CD 2026-000909-T'
- `classification` stored as-is, `str` stored as-is, `_date` stored as metadata
- postal_code (float64) converted to 5-digit zero-padded string: 73071.0 -> '73071', 2101.0 -> '02101', NaN -> empty string
- Entries with address baked into name field: flag as anomalous, don't attempt to split
- 6 entries without addresses -- keep them, don't filter
- Strict schema validation with fallback: expect 12 columns by name, return clear error if missing/renamed
- Accept both CSV (.csv) and Excel (.xlsx) files
- Integrated into existing upload endpoint (POST /api/extract/upload) -- frontend already sends CSV as second file

### Claude's Discretion
- Internal data model structure for parsed CSV rows (Pydantic model design)
- How to structure the parser module (single file vs multiple)
- Exact regex for entry number stripping
- How to detect and handle the rare embedded-address anomaly for flagging

### Deferred Ideas (OUT OF SCOPE)
- FMT-02 (Convey 640 schema variations across export versions) -- deferred to future release
- Fuzzy name matching between PDF and CSV when entry numbers don't align -- deferred to future (MATCH-01)

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CSV-01 | User can optionally upload a Convey 640 CSV or Excel file alongside the ECF PDF | Upload endpoint already accepts files; pandas reads both formats with `read_csv`/`read_excel` using `dtype=str` |
| CSV-02 | Parser strips entry line numbers from the name column and normalizes respondent names | Regex `^\d+\.?\s*` handles entry numbers; reuse `ecf_parser.py` patterns for deceased/now/trust/joint name handling |
| CSV-03 | Parser preserves ZIP codes as strings (prevents float/NaN loss of leading zeros) | Read with `dtype=str` or convert float64 -> zero-padded 5-digit string; sample data confirms 1 entry needs leading zero (02668) |
| CSV-04 | Parser extracts metadata columns (county, STR, applicant, case number, classification) | All 357 rows share identical metadata; extract from first row, return as `CaseMetadata` |

</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pandas | 2.x | CSV/Excel reading + data transformation | Already in dependencies, used extensively in proration |
| pydantic | 2.x | Data validation models | Project standard for all models |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| openpyxl | (transitive) | Excel file reading | Needed by `pd.read_excel()`, already installed |
| re (stdlib) | - | Name normalization regex | Entry number stripping, pattern matching |

No new dependencies needed. Everything required is already installed.

## Architecture Patterns

### Recommended Project Structure
```
backend/app/services/extract/
    convey640_parser.py     # NEW: Convey 640 CSV/Excel parser (single file)
    ecf_parser.py           # Existing: ECF PDF parser (reference patterns)
    name_parser.py          # Existing: parse_name() for first/middle/last
    ...
backend/app/models/
    extract.py              # Existing: PartyEntry, CaseMetadata, EntityType (reuse as-is)
backend/app/api/
    extract.py              # Existing: upload endpoint (add CSV processing branch)
backend/tests/
    test_convey640_parser.py  # NEW: Test suite for CSV parser
```

### Pattern: Single Parser Module
**What:** All Convey 640 parsing logic in one file (`convey640_parser.py`) -- read file, validate schema, normalize names, produce `PartyEntry` list + `CaseMetadata`.
**When to use:** This phase. The CSV parsing is straightforward enough for a single module.
**Rationale:** The ECF parser is a single file (ecf_parser.py, ~444 lines). The CSV parser will be simpler (no PDF text extraction, no section splitting, no address line detection). A single file keeps it discoverable and follows the tool-per-module project convention.

### Pattern: Return Same Types as ECF Parser
**What:** The CSV parser returns the same `PartyEntry` list + `CaseMetadata` that the ECF parser returns, wrapped in a compatible result structure.
**Why:** Phase 3 merge will consume both PDF and CSV results. Using identical output types means the merge logic is straightforward.

```python
# convey640_parser.py public API
from dataclasses import dataclass, field
from app.models.extract import CaseMetadata, PartyEntry

@dataclass
class Convey640ParseResult:
    entries: list[PartyEntry] = field(default_factory=list)
    metadata: CaseMetadata = field(default_factory=CaseMetadata)

def parse_convey640(file_bytes: bytes, filename: str) -> Convey640ParseResult:
    """Parse a Convey 640 CSV or Excel file."""
    ...
```

### Pattern: Read with dtype=str to Prevent Data Loss
**What:** Always use `dtype=str` when reading Convey 640 files to prevent pandas from coercing postal codes to float64.
**Critical:** Without `dtype=str`, ZIP code `02101` becomes `2101.0` and the leading zero is permanently lost.

```python
import io
import pandas as pd

buf = io.BytesIO(file_bytes)
if filename.lower().endswith(".xlsx"):
    df = pd.read_excel(buf, dtype=str)
else:
    df = pd.read_csv(buf, dtype=str, keep_default_na=False)
```

**However:** The sample file's postal_code column is already float64 in the Excel. Even with `dtype=str`, Excel files that store numeric values as numbers will read as `"73071.0"` strings. The parser must handle the `.0` suffix:

```python
def normalize_postal_code(val: str) -> str:
    """Convert postal_code string (possibly '73071.0' or 'nan') to 5-digit zero-padded."""
    if not val or val.lower() in ("nan", "none", ""):
        return ""
    # Remove .0 suffix from float-like strings
    if "." in val:
        val = val.split(".")[0]
    # Zero-pad to 5 digits
    try:
        return val.zfill(5)
    except (ValueError, AttributeError):
        return ""
```

### Pattern: Name Normalization Pipeline
**What:** Process names through a series of transformations in order.
**Why:** Order matters -- entry numbers must be stripped before entity detection, deceased markers before name parsing, etc.

Recommended order:
1. Strip leading entry number (`^\d+\.?\s*`)
2. Extract entry number for `PartyEntry.entry_number`
3. Detect `CLO`/`ELO`/`LO` care-of patterns -> notes
4. Detect `C/O` care-of -> notes
5. Detect `A/K/A` aliases -> notes
6. Detect `NEE` maiden name -> notes
7. Detect `NOW [married name]` -> use married name, maiden to notes
8. Detect `DECEASED`/`POSSIBLY DECEASED` -> entity_type=ESTATE, strip from name
9. Split joint names on `&` -> primary + notes
10. Run entity type detection (`detect_entity_type`)
11. For trusts: extract grantor name as primary, trust details to notes
12. Parse individual names via `parse_name()`

### Pattern: Metadata Extraction from First Row
**What:** All rows in the sample file share identical metadata. Extract once from the first row.
**Implementation:**

```python
def _extract_metadata(df: pd.DataFrame) -> CaseMetadata:
    row = df.iloc[0]
    case_no = _normalize_case_number(row.get("case_no", ""))
    return CaseMetadata(
        county=row.get("county", "").strip() or None,
        legal_description=row.get("str", "").strip() or None,
        applicant=row.get("applicant", "").strip() or None,
        case_number=case_no,
    )

def _normalize_case_number(raw: str) -> str | None:
    """Convert '2026000909' to 'CD 2026-000909-T'."""
    raw = raw.strip()
    if not raw or raw.lower() in ("nan", "none"):
        return None
    # Remove .0 suffix if present
    if "." in raw:
        raw = raw.split(".")[0]
    if len(raw) == 10:
        return f"CD {raw[:4]}-{raw[4:]}-T"
    return raw
```

### Anti-Patterns to Avoid
- **Reading without dtype=str:** Causes ZIP code data loss and case_no becoming int64.
- **Filtering out rows without addresses:** The user explicitly decided to keep all rows.
- **Splitting embedded-address names (entry 328):** Flag it, don't try to parse the Norwegian address out of the name.
- **Building a separate Pydantic model for CSV rows:** Reuse `PartyEntry` directly -- it has all needed fields.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Entity type detection | Custom regex for LLC/Trust/Estate/etc. | `utils/patterns.detect_entity_type()` | Already handles all entity types, tested |
| Name splitting (first/middle/last) | Custom name parser | `services/extract/name_parser.parse_name()` | Handles suffixes, middle initials, business names |
| Deceased/a.k.a/trust pattern matching | New regex from scratch | Adapt patterns from `ecf_parser.py` | `DECEASED_PATTERN`, `NOW_NAME_PATTERN`, `HEIRS_DEVISEES_PATTERN` already exist |
| CSV/Excel file reading | Custom file reader | `pandas.read_csv()` / `pandas.read_excel()` | Handles encoding, delimiters, missing values |

**Key insight:** The ECF parser already handles deceased markers, "now" married names, trust/trustee detection, and c/o patterns. The Convey 640 parser should reuse these patterns directly or adapt them minimally for the CSV name format.

## Common Pitfalls

### Pitfall 1: Entry Number Regex Too Greedy
**What goes wrong:** Regex `^\d+\s` strips the first digit from names like "2WOOD OIL & GAS LLC" (which has no entry number).
**Why it happens:** Some names genuinely start with digits that are not entry numbers.
**How to avoid:** Use `^\d+\.?\s+` which requires whitespace after the number (and optional period). Entry numbers always have a space after them. Names like "2WOOD" have no space between digit and letter.
**Warning signs:** Entity names like "2WOOD OIL & GAS LLC" getting mangled to "WOOD OIL & GAS LLC".
**Verified from data:** Entry 176 shows `0SCAR LEE MCCARTER` -- this is preceded by `176 `, so the regex strips `176 ` leaving `0SCAR LEE MCCARTER`. The leading `0` is a typo in the source data, not an entry number.

### Pitfall 2: CLO/ELO/LO Notation Not Recognized
**What goes wrong:** `CLO`, `ELO`, `LO` are Convey 640's notation for care-of (not standard `C/O`). If not handled, the care-of person's name gets concatenated into the primary name.
**Why it happens:** These abbreviations are specific to Convey 640 scraping and don't appear in the PDF source.
**How to avoid:** Add regex patterns for `\bCLO\b`, `\bELO\b`, and `\bLO\b` (with word boundary) to extract care-of names into notes.
**Caveat:** `LO` is risky as a standalone word boundary match -- it could match parts of names. Use `\bLO\s+` (requires trailing space) or only match when followed by a name-like pattern (uppercase word).
**Sample data:** 31 entries use CLO/ELO/LO patterns. Example: `"124 JOHN KER YOUNGHEIM DECEASED CLO LYNNE YOFFE"` should produce primary_name="JOHN KER YOUNGHEIM", entity_type=ESTATE, notes="deceased; c/o LYNNE YOFFE".

### Pitfall 3: Trust Name Grantor Extraction
**What goes wrong:** Trust names like `"INA NADINE TAYLOR REVOCABLE TRUST DATED THE 30TH DAY..."` are complex. Naively splitting on "TRUST" loses context.
**Why it happens:** The user wants a contactable person name, not the legal entity name.
**How to avoid:** For trusts, extract the text before the first trust keyword (TRUST, REVOCABLE, LIVING TRUST) as the grantor name. If a trustee is named (SUCCESSOR TRUSTEE, AS TRUSTEE OF), put that in notes. The entity_type should still be Trust.
**Important:** For trusts like `"JUDI K SMITH AS TRUSTEE OF THE JUDI K SMITH TRUST"`, the trustee IS the grantor -- extract "JUDI K SMITH" as primary name.

### Pitfall 4: Joint Name & Handling
**What goes wrong:** Splitting `"JAMES E DESHIELDS JR & RITA F DESHIELDS"` on `&` gives first person as primary, second goes to notes. But `"2WOOD OIL & GAS LLC"` should NOT be split.
**Why it happens:** `&` appears in both joint personal names and business entity names.
**How to avoid:** Run entity detection FIRST. If entity is LLC/Corporation/Partnership, don't split on `&`. Only split for Individuals. The existing `split_multiple_names()` in `name_parser.py` already handles this distinction with legal phrase exclusions.

### Pitfall 5: Postal Code Edge Cases
**What goes wrong:** ZIP `783160.0` in the sample is a 6-digit code (data error). Simple truncation to 5 digits gives `78316` which is wrong.
**Why it happens:** Source data quality issue.
**How to avoid:** After converting to integer string, if length > 5, flag the entry. If length < 5, zero-pad. Only convert to 5-digit if the value is plausible (1-99999).

### Pitfall 6: NEE Pattern
**What goes wrong:** `"ROSE MAURICE PODDER NEE YOUNGHEIM"` -- `NEE` means maiden name. If not handled, "YOUNGHEIM" gets treated as part of the current name.
**Why it happens:** `NEE` is a rare pattern (1 entry in sample) that the ECF parser doesn't handle.
**How to avoid:** Add pattern `\bNEE\s+(\w+)` -- extract maiden name to notes as `f/k/a YOUNGHEIM`, use everything before `NEE` as the current name.

## Code Examples

### Entry Number Stripping (verified from sample data analysis)
```python
import re

ENTRY_NUMBER_RE = re.compile(r"^(\d+)\.?\s+")

def strip_entry_number(name: str) -> tuple[str | None, str]:
    """Strip leading entry number from name.

    Returns (entry_number, cleaned_name).
    """
    match = ENTRY_NUMBER_RE.match(name)
    if match:
        return match.group(1), name[match.end():]
    return None, name

# Examples from actual sample data:
# "104 INA NADINE TAYLOR..." -> ("104", "INA NADINE TAYLOR...")
# "AARON TRACY" -> (None, "AARON TRACY")
# "2WOOD OIL & GAS LLC" -> (None, "2WOOD OIL & GAS LLC")  # No space after digit
```

### CLO/ELO Care-of Extraction
```python
# CLO = "Care/Letter Of", ELO = "Estate Letter Of", LO = "Letter Of"
CLO_ELO_RE = re.compile(r"\s+(?:CLO|ELO)\s+(.+)$", re.IGNORECASE)
LO_RE = re.compile(r"\s+LO\s+([A-Z].+)$")  # Strict: requires uppercase after LO

def extract_care_of(name: str) -> tuple[str, str | None]:
    """Extract CLO/ELO/LO care-of from name.

    Returns (cleaned_name, care_of_name_or_none).
    """
    for pattern in (CLO_ELO_RE, LO_RE):
        match = pattern.search(name)
        if match:
            return name[:match.start()].strip(), match.group(1).strip()
    return name, None
```

### Postal Code Normalization (verified against sample data)
```python
def normalize_postal_code(val: str) -> str:
    """Convert postal_code from string (possibly float-like) to 5-digit zero-padded.

    Examples:
        "73071.0" -> "73071"
        "2668.0"  -> "02668"  (West Bamstable, MA)
        "nan"     -> ""
        "783160.0" -> "78316" (flag: 6-digit, possible data error)
    """
    if not val or val.lower() in ("nan", "none", ""):
        return ""
    if "." in val:
        val = val.split(".")[0]
    val = val.strip()
    if not val.isdigit():
        return ""
    if len(val) > 5:
        # Data error -- truncate to 5 but this should be flagged
        return val[:5]
    return val.zfill(5)
```

### Case Number Normalization
```python
def normalize_case_number(raw: str) -> str | None:
    """Convert Convey 640 case_no to ECF format.

    '2026000909' -> 'CD 2026-000909-T'
    '2026000909.0' -> 'CD 2026-000909-T'  (if read as float)
    """
    raw = raw.strip()
    if not raw or raw.lower() in ("nan", "none"):
        return None
    if "." in raw:
        raw = raw.split(".")[0]
    if len(raw) == 10 and raw.isdigit():
        return f"CD {raw[:4]}-{raw[4:]}-T"
    return raw
```

### Schema Validation
```python
EXPECTED_COLUMNS = {
    "county", "str", "applicant", "classification", "case_no",
    "curative", "_date", "name", "address", "city", "state", "postal_code",
}

def validate_schema(df: pd.DataFrame) -> None:
    """Validate DataFrame has expected Convey 640 columns."""
    actual = set(df.columns.str.strip().str.lower())
    missing = EXPECTED_COLUMNS - actual
    if missing:
        raise ValueError(
            f"Missing expected columns: {sorted(missing)}. "
            f"Found columns: {sorted(actual)}"
        )
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Read CSV without dtype control | `dtype=str` + `keep_default_na=False` | pandas 1.x+ | Prevents ZIP code and case number data loss |
| Separate models per parser | Shared `PartyEntry` model | Phase 1 design | Enables Phase 3 merge with zero model mapping |

**Not deprecated/outdated:** All patterns and libraries used in this phase are current. No version concerns.

## Open Questions

1. **CLO/ELO/LO meaning precision**
   - What we know: CLO appears ~20 times, ELO ~5 times, LO ~6 times in the sample. They function as care-of references.
   - What's unclear: Whether CLO specifically means "Care/Letter Of" vs some other expansion.
   - Recommendation: Treat all three as equivalent to c/o. Store care-of name in notes field as "c/o [NAME]" for consistency with ECF parser's c/o handling.

2. **6-digit ZIP code (783160)**
   - What we know: One entry has postal_code=783160.0, which is 6 digits. The corresponding city/state is Moore, OK (expected ZIP: 73160).
   - What's unclear: Whether this is always a simple leading-digit error (7 prepended to 83160, or should be 73160).
   - Recommendation: Truncate to first 5 digits (78316) and flag the entry. Don't attempt auto-correction.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 7.x with pytest-asyncio |
| Config file | `backend/pytest.ini` |
| Quick run command | `cd backend && python3 -m pytest tests/test_convey640_parser.py -x -v` |
| Full suite command | `cd backend && python3 -m pytest -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CSV-01 | Parse CSV and Excel files with 12-column schema | unit | `cd backend && python3 -m pytest tests/test_convey640_parser.py::TestSchemaValidation -x` | -- Wave 0 |
| CSV-02 | Strip entry numbers, normalize names (deceased, joint, trust, now, CLO) | unit | `cd backend && python3 -m pytest tests/test_convey640_parser.py::TestNameNormalization -x` | -- Wave 0 |
| CSV-03 | ZIP code preservation (float->string, leading zeros, NaN) | unit | `cd backend && python3 -m pytest tests/test_convey640_parser.py::TestPostalCodeNormalization -x` | -- Wave 0 |
| CSV-04 | Metadata extraction (county, STR, applicant, case_no, classification) | unit | `cd backend && python3 -m pytest tests/test_convey640_parser.py::TestMetadataExtraction -x` | -- Wave 0 |

### Sampling Rate
- **Per task commit:** `cd backend && python3 -m pytest tests/test_convey640_parser.py -x -v`
- **Per wave merge:** `cd backend && python3 -m pytest -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_convey640_parser.py` -- covers CSV-01 through CSV-04
- No framework install needed -- pytest already configured
- No conftest changes needed -- existing `tests/conftest.py` is sufficient

## Sources

### Primary (HIGH confidence)
- Sample file analysis: `convey640_respondents_1686_20260_00909_19-10N-11W_2026-03-05_12_57_34.xlsx` -- 357 rows, 12 columns, all patterns verified
- Existing codebase: `ecf_parser.py`, `name_parser.py`, `patterns.py`, `models/extract.py` -- all reusable patterns confirmed
- pandas skill: `.claude/skills/pandas/SKILL.md` -- `dtype=str` pattern confirmed

### Secondary (MEDIUM confidence)
- None needed -- all findings from direct code/data analysis

### Tertiary (LOW confidence)
- CLO/ELO/LO abbreviation meanings -- inferred from context, not confirmed from Convey 640 documentation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already in use, no new dependencies
- Architecture: HIGH -- follows established tool-per-module pattern, reuses existing models
- Pitfalls: HIGH -- all edge cases verified against actual sample data (357 rows analyzed)
- Name normalization patterns: HIGH -- all patterns (entry numbers, deceased, joint, trust, CLO/ELO, NOW, NEE, c/o) verified from sample data counts

**Research date:** 2026-03-12
**Valid until:** 2026-04-12 (stable domain, no external API dependencies)

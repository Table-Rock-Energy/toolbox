# Phase 1: ECF PDF Parsing - Research

**Researched:** 2026-03-12
**Domain:** PDF text extraction, structured parsing of OCC ECF filings
**Confidence:** HIGH

## Summary

Phase 1 adds ECF (Electronic Case Filing) PDF parsing to the existing Extract tool. The ECF format is structurally simpler than the existing OCC Exhibit A formats -- it uses a single-column numbered list (not two-column like FREE_TEXT_LIST) with one entry per block, separated by blank lines. Each entry follows a consistent pattern: entry number, name line(s), street address line(s), city/state/ZIP line.

The existing codebase provides strong foundations: PyMuPDF text extraction, entity type detection via `patterns.py`, name parsing via `name_parser.py`, address parsing via `shared/address_parser.py`, and the upload endpoint already accepts `format_hint`. The main new work is: (1) a dedicated ECF parser module, (2) a CaseMetadata Pydantic model, (3) section-type tagging for respondent categories, (4) ECF enum value + routing in the upload endpoint, and (5) page header/footer stripping specific to ECF filings.

**Primary recommendation:** Build a new `ecf_parser.py` module in `services/extract/` that receives raw PDF text (extracted by existing `pdf_extractor.py`), strips ECF-specific headers/footers, splits into sections, parses entries with section tags, and extracts case metadata from the first page. The existing `parser.py` should not be modified -- ECF has different enough structure (no two-column, different section headers, metadata extraction) to warrant its own module.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- ECF is hint-only -- only parse as ECF when the user selects "ECF Filing" from the Extract page dropdown (format_hint='ECF')
- No auto-detection needed; the frontend already sends the hint via query parameter
- Add `ECF` to the `ExhibitFormat` enum but do not add detection patterns to `detect_format()`
- Parse ALL numbered entries from every section in the PDF (regular, curative, address_unknown, curative_unknown, informational)
- Tag each entry with its section type (regular, curative, address_unknown, curative_unknown, informational)
- Address-less entries are NOT filtered from parsing results -- they are kept for future matching
- Frontend provides a checkbox to hide entries without addresses (not a hard filter)
- Exports exclude entries without addresses
- Extract ALL metadata fields from the PDF header: county, legal_description, applicant, case_number, well_name
- "deceased" and "Heirs and Devisees of" entries -> EntityType.ESTATE
- "possibly deceased" entries -> EntityType.ESTATE (conservative classification)
- c/o person captured in notes field
- "now [married name]" patterns -> notes field, use current name as primary
- a/k/a, f/k/a chains -> existing name_parser and notes handling applies
- Trust, LLC, LP, Corporation, Partnership -> existing entity detection patterns apply unchanged

### Claude's Discretion
- Whether to build a dedicated ECF parser module or extend existing parser
- Two-column text splitting approach
- How to extract well name from the application body text
- Page header/footer stripping approach (red "CASE CD..." headers appear on every page)

### Deferred Ideas (OUT OF SCOPE)
- Convey 640 may have addresses for "address unknown" respondents -- Phase 3 merge can fill these in
- Checkbox UI for hiding address-less entries -- Phase 4 already built the frontend; may need minor update for this filter
- Future name matching against other data sources for address-unknown respondents -- beyond v1.4 scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ECF-01 | User can upload an ECF PDF and extract numbered respondent entries (name + address) | Existing upload endpoint + format_hint routing; new ECF parser module processes entries |
| ECF-02 | Parser correctly handles multi-line respondent names and addresses from PDF text | ECF format uses single-column layout; line-based splitting with section detection handles multi-line entries |
| ECF-03 | Parser extracts case metadata from PDF header (county, legal description, applicant name, case number, well name) | New CaseMetadata Pydantic model; regex extraction from first page text |
| ECF-04 | Entity type is detected for each respondent (Individual, Trust, LLC, Estate, Corporation, etc.) | Existing `detect_entity_type()` in `patterns.py` handles most cases; add "deceased" -> ESTATE and "now" -> notes patterns |
| ECF-05 | Format detector identifies ECF filings and routes to the correct parser | Add `ECF` to `ExhibitFormat` enum; route via format_hint only (no auto-detection per user decision) |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PyMuPDF (fitz) | Installed | PDF text extraction | Already primary extractor in `pdf_extractor.py`; returns clean single-column text for ECF |
| Pydantic | 2.x | CaseMetadata + updated ExtractionResult models | Already used for all models in `models/extract.py` |
| re (stdlib) | N/A | Regex parsing for entries, sections, metadata | Already used throughout `parser.py` and `patterns.py` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pdfplumber | Installed | Fallback PDF text extraction | Only if PyMuPDF returns < 100 chars (existing fallback pattern) |
| logging (stdlib) | N/A | Per-module logging | Standard pattern: `logger = logging.getLogger(__name__)` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Dedicated ECF parser | Extend existing `parser.py` | ECF is different enough (single-column, sections, metadata) that a separate module is cleaner and avoids conditional complexity in the existing parser |
| Regex metadata extraction | PyMuPDF dict-mode with positions | Overkill -- the metadata is in plain text on page 1, regex is simpler and more maintainable |

## Architecture Patterns

### Recommended Project Structure
```
backend/app/services/extract/
├── ecf_parser.py           # NEW: ECF-specific parsing (entry parsing, section detection, metadata extraction)
├── format_detector.py      # MODIFY: Add ECF to ExhibitFormat enum
├── parser.py               # UNCHANGED: existing Exhibit A parser
├── pdf_extractor.py        # UNCHANGED: text extraction reused as-is
├── name_parser.py          # UNCHANGED: name splitting reused
├── address_parser.py       # UNCHANGED: address parsing reused
├── export_service.py       # MINOR: filter address-less entries for ECF exports
└── table_parser.py         # UNCHANGED
```

### Pattern 1: ECF Parser Module
**What:** A standalone `ecf_parser.py` that exports `parse_ecf_filing(text: str) -> ECFParseResult` containing both entries and metadata.
**When to use:** When `format_hint='ECF'` is received by the upload endpoint.
**Example:**
```python
# backend/app/services/extract/ecf_parser.py
from app.models.extract import CaseMetadata, EntityType, PartyEntry

class ECFParseResult:
    entries: list[PartyEntry]
    metadata: CaseMetadata

def parse_ecf_filing(text: str) -> ECFParseResult:
    """Parse an ECF PDF's full text into entries and metadata."""
    metadata = _extract_metadata(text)
    exhibit_text = _extract_exhibit_a_section(text)
    cleaned = _strip_page_headers(exhibit_text)
    sections = _split_into_sections(cleaned)
    entries = []
    for section_type, section_text in sections:
        entries.extend(_parse_section_entries(section_text, section_type))
    return ECFParseResult(entries=entries, metadata=metadata)
```

### Pattern 2: Section-Aware Entry Splitting
**What:** Split the Exhibit A text into named sections based on section headers, then parse entries within each section with the section tag.
**When to use:** ECF filings have 5 distinct sections with different semantics.
**Example:**
```python
# Section headers found in the sample PDF:
SECTION_HEADERS = {
    "CURATIVE RESPONDENTS WITH ADDRESS UNKNOWN:": "curative_unknown",
    "CURATIVE RESPONDENTS:": "curative",
    "RESPONDENTS WITH ADDRESS UNKNOWN:": "address_unknown",
    "FOR INFORMATIONAL PURPOSES ONLY:": "informational",
}
# Default (before any header): "regular"
# IMPORTANT: Match longer headers first to avoid "CURATIVE RESPONDENTS:"
# matching before "CURATIVE RESPONDENTS WITH ADDRESS UNKNOWN:"
```

### Pattern 3: Case Metadata Extraction via Regex
**What:** Extract metadata from the structured header on page 1.
**When to use:** Always for ECF filings -- the header format is consistent across OCC filings.
**Example:**
```python
def _extract_metadata(text: str) -> CaseMetadata:
    # Applicant: "APPLICANT:  COTERRA ENERGY OPERATING CO."
    applicant_match = re.search(r'APPLICANT:\s+(.+?)(?:\n|$)', text)

    # Case number: "CAUSE NO. CD\n2026-000909-T" (may span two lines)
    case_match = re.search(r'CAUSE\s+NO\.?\s+(?:CD\s+)?(.+?)(?:\n\n|$)', text, re.DOTALL)

    # County: "CADDO COUNTY, OKLAHOMA" from LAND COVERED section
    county_match = re.search(r'(\w+)\s+COUNTY,\s+OKLAHOMA', text)

    # Legal description: "SECTION(S) 19, 30 AND 31, TOWNSHIP 10 NORTH, RANGE 11 WEST"
    legal_match = re.search(r'(SECTION\(S\)\s+.+?RANGE\s+\d+\s+\w+)', text)

    # Well name: "Diana Prince 1H-193031X well" from paragraph 2(D)
    well_match = re.search(r'\(the\s+(.+?)\s+well\)', text)
```

### Pattern 4: Page Header/Footer Stripping
**What:** Remove repeated page headers and footers that appear on every page of the ECF PDF.
**When to use:** Before splitting into entries -- these headers would otherwise corrupt entry parsing.
**Example:**
```python
# Headers seen on every page:
# Line 1: "MULTIUNIT HORIZONTAL WELL - CAUSE NO. CD 2026-000909-T"
# Line 2: "SECTION(S) 19, 30 AND 31-10N-11W, CADDO COUNTY, OKLAHOMA"
# Line 3: "COTERRA ENERGY OPERATING CO."
# Line 4: 'EXHIBIT "A"'
# Line 5: page number (e.g., "5", "16")
# Footer: "CASE CD CD2026-000909 ENTRY NO. 2 FILED IN OCC COURT CLERK'S OFFICE ON 03/03/2026 - PAGE X OF 21"

PAGE_HEADER_PATTERN = re.compile(
    r'^MULTIUNIT HORIZONTAL WELL.+?$', re.MULTILINE
)
PAGE_FOOTER_PATTERN = re.compile(
    r'^CASE\s+CD\s+CD\d+.+?PAGE\s+\d+\s+OF\s+\d+\s*$', re.MULTILINE
)
EXHIBIT_A_HEADER = re.compile(
    r'^EXHIBIT\s+"?A"?\s*$', re.MULTILINE
)
# Also strip standalone page numbers (single number on a line)
PAGE_NUMBER_PATTERN = re.compile(r'^\d{1,2}\s*$', re.MULTILINE)
```

### Anti-Patterns to Avoid
- **Modifying existing `parser.py`:** ECF has fundamentally different structure (single-column, sections, metadata). Adding conditionals to the existing parser creates fragile coupling. Use a separate module.
- **Auto-detecting ECF format:** Per user decision, ECF is hint-only. Do NOT add patterns to `detect_format()`.
- **Filtering address-unknown entries during parsing:** Per user decision, ALL entries stay in the result. Filtering happens at export time and via frontend checkbox.
- **Re-extracting PDF text for ECF:** The existing `extract_text_from_pdf()` works fine with default settings. ECF is single-column, so no special column count needed.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Entity type detection | New entity detection for ECF | Existing `detect_entity_type()` from `patterns.py` | Already handles Trust, LLC, Corporation, Estate, etc. -- just needs "deceased" -> ESTATE addition |
| Address parsing | Custom ECF address parser | Existing `parse_address()` from `shared/address_parser.py` | Handles PO Box, Suite, multi-line, ZIP+4 already |
| Name splitting (first/middle/last) | ECF-specific name splitter | Existing `parse_name()` from `name_parser.py` | Works on cleaned individual names |
| Notes extraction (a/k/a, f/k/a, c/o) | Custom notes extractor | Existing `_extract_notes()` from `parser.py` | Already extracts these patterns -- can import and reuse |
| PDF text extraction | New PyMuPDF extraction | Existing `extract_text_from_pdf()` | Works with default 3-column detection; ECF will detect as single/2-column which is fine |

**Key insight:** The ECF parser is mostly about splitting and routing -- the heavy lifting (text extraction, entity detection, address parsing, name parsing) already exists. The new code is primarily: section detection, metadata extraction, page header stripping, and a "deceased"/"now" pattern handler.

## Common Pitfalls

### Pitfall 1: Multi-Line Entry Boundaries
**What goes wrong:** Entry number regex splits incorrectly when names or addresses contain numbers that look like entry numbers (e.g., "12801 N Central Expressway").
**Why it happens:** A naive `^\d+\.` pattern matches street numbers at the start of address lines.
**How to avoid:** The entry number pattern must require the number to appear after a blank line or section boundary. In the ECF format, each entry is separated by blank lines, and the entry number format is `\d+\.\s+[A-Z]` (number-dot-space-uppercase-letter). Street addresses start with numbers followed by spaces and mixed case.
**Warning signs:** Entry count doesn't match expected (357 in sample). Street addresses getting parsed as separate entries.

### Pitfall 2: Section Header Ordering
**What goes wrong:** "CURATIVE RESPONDENTS:" regex matches inside "CURATIVE RESPONDENTS WITH ADDRESS UNKNOWN:" if checked first.
**Why it happens:** Substring match ambiguity.
**How to avoid:** Match longer/more-specific headers first, or use exact-match patterns with `:` terminator and line boundaries.
**Warning signs:** Curative entries tagged as `address_unknown` instead of `curative_unknown`.

### Pitfall 3: Case Number Spanning Two Lines
**What goes wrong:** "CAUSE NO. CD" is on one line, and "2026-000909-T" is on the next line in the PDF text extraction.
**Why it happens:** PyMuPDF preserves the PDF layout where "CAUSE NO. CD" and the actual number are in separate text blocks (the PDF uses a two-column header layout with `)` separators).
**How to avoid:** Use `re.DOTALL` or explicit `\n` in the regex pattern. Extract the number from the line following "CAUSE NO." text.
**Warning signs:** `case_number` is None or contains only "CD" without the actual number.

### Pitfall 4: "Deceased" Entity Type vs Existing Pattern
**What goes wrong:** `detect_entity_type()` in `patterns.py` only matches `", Deceased"` (with comma prefix) or `"Estate of"`. ECF entries like `"Karen Sue Henderson, deceased"` (lowercase) or `"possibly deceased"` don't match.
**Why it happens:** The existing `ESTATE_PATTERN` is `r"\b(?:Estate\s+of|,\s*Deceased)\b"` which requires a comma before "Deceased".
**How to avoid:** The ECF parser should check for "deceased" (case-insensitive) as an additional signal for EntityType.ESTATE, either by extending the pattern in `patterns.py` or handling it in the ECF parser's own entity detection.
**Warning signs:** Deceased respondents classified as INDIVIDUAL instead of ESTATE.

### Pitfall 5: "now [name]" Pattern Creates Incorrect Primary Name
**What goes wrong:** "Alisha Brummett now Recker" could be parsed as a three-word name with "now" as middle name.
**Why it happens:** `parse_person_name()` doesn't know about the "now" married-name pattern.
**How to avoid:** Extract "now [name]" into notes before passing to name parser. Use the married name (Recker) as primary or keep maiden name (Brummett) -- per user decision, use current name (Recker) as primary, maiden name in notes.
**Warning signs:** "now" appearing as a middle name in parsed output.

### Pitfall 6: Page Header Text Leaking into Entries
**What goes wrong:** The page header "COTERRA ENERGY OPERATING CO." gets parsed as part of an entry name when it appears between two entries that span a page break.
**Why it happens:** Page breaks can occur mid-entry-list, and the header lines sit between the end of one entry and the start of the next.
**How to avoid:** Strip ALL page headers/footers before splitting into entries. The header pattern is consistent across all pages.
**Warning signs:** Entries with applicant name mixed into their names; extra "entries" that are actually headers.

## Code Examples

### CaseMetadata Pydantic Model (to add to models/extract.py)
```python
class CaseMetadata(BaseModel):
    """Metadata extracted from ECF filing header."""
    county: Optional[str] = Field(None, description="County name (e.g., 'CADDO')")
    legal_description: Optional[str] = Field(
        None, description="Section/Township/Range legal description"
    )
    applicant: Optional[str] = Field(None, description="Applicant company name")
    case_number: Optional[str] = Field(None, description="OCC cause number")
    well_name: Optional[str] = Field(None, description="Well name from application")
```

### Updated ExtractionResult (add case_metadata field)
```python
class ExtractionResult(BaseModel):
    # ... existing fields ...
    case_metadata: Optional[CaseMetadata] = Field(
        None, description="Case metadata from ECF filing header"
    )
```

### Updated PartyEntry (add section_type field)
```python
class PartyEntry(BaseModel):
    # ... existing fields ...
    section_type: Optional[str] = Field(
        None, description="ECF section: regular, curative, address_unknown, curative_unknown, informational"
    )
```

### ECF Routing in Upload Endpoint
```python
# In api/extract.py upload_pdf():
elif fmt == ExhibitFormat.ECF:
    from app.services.extract.ecf_parser import parse_ecf_filing
    ecf_result = parse_ecf_filing(full_text)
    entries = ecf_result.entries
    case_metadata = ecf_result.metadata
```

### Entry Parsing Pattern for ECF Single-Column Format
```python
def _parse_entry_block(block: str, section_type: str) -> PartyEntry:
    """Parse a single ECF entry block (number + name lines + address lines)."""
    lines = [l.strip() for l in block.strip().split('\n') if l.strip()]

    # First line: "24. Carolyn Nell McBride, deceased"
    first_line = lines[0]
    num_match = re.match(r'^(\d+)\.\s+(.+)', first_line)
    entry_number = num_match.group(1)
    name_start = num_match.group(2)

    # Collect name lines vs address lines
    # Address lines: start with digit, "PO Box", or "c/o"
    # City/state/ZIP line: ends with state + ZIP pattern
    # Everything else before address start is name continuation
```

### "Deceased" and "now" Pattern Handling
```python
# Additional ECF-specific patterns
DECEASED_PATTERN = re.compile(r',?\s*(?:possibly\s+)?deceased\b', re.IGNORECASE)
NOW_NAME_PATTERN = re.compile(r'\s+now\s+(\w+)\s*$', re.IGNORECASE)
HEIRS_DEVISEES_PATTERN = re.compile(r'Heirs\s+and\s+Devisees\s+of\b', re.IGNORECASE)

def _classify_ecf_entity(text: str) -> tuple[EntityType, list[str]]:
    """Detect entity type with ECF-specific deceased/now handling.

    Returns (entity_type, extra_notes).
    """
    notes = []

    if DECEASED_PATTERN.search(text):
        # Strip deceased annotation, add to notes
        notes.append("deceased")
        return EntityType.ESTATE, notes

    if HEIRS_DEVISEES_PATTERN.search(text):
        return EntityType.ESTATE, notes

    now_match = NOW_NAME_PATTERN.search(text)
    if now_match:
        notes.append(f"f/k/a {text.split(' now ')[0].split()[-1]}")
        # The name will be rewritten to use married name as primary

    # Fall back to existing detection
    from app.utils.patterns import detect_entity_type
    return EntityType(detect_entity_type(text)), notes
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Two-column Exhibit A parsing | ECF is single-column | N/A (new format) | Simpler text extraction -- no column detection needed |
| No case metadata | CaseMetadata model | Phase 1 (new) | Frontend already has CaseMetadata interface waiting for data |
| Binary address status (has/missing) | Section-type tagging | Phase 1 (new) | Entries carry semantic context (curative, informational, etc.) |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 7.x + pytest-asyncio |
| Config file | `backend/pytest.ini` (if exists) or inline in `pyproject.toml` |
| Quick run command | `cd /Users/yojimbo/Documents/dev/toolbox/backend && python3 -m pytest tests/test_ecf_parser.py -x -v` |
| Full suite command | `cd /Users/yojimbo/Documents/dev/toolbox && make test` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ECF-01 | Upload ECF PDF, get numbered respondent entries | unit | `python3 -m pytest tests/test_ecf_parser.py::TestECFParseEntries -x` | Wave 0 |
| ECF-02 | Multi-line names and addresses correctly preserved | unit | `python3 -m pytest tests/test_ecf_parser.py::TestECFMultiLine -x` | Wave 0 |
| ECF-03 | Case metadata extracted from header | unit | `python3 -m pytest tests/test_ecf_parser.py::TestECFMetadata -x` | Wave 0 |
| ECF-04 | Entity type assigned (deceased -> ESTATE, etc.) | unit | `python3 -m pytest tests/test_ecf_parser.py::TestECFEntityTypes -x` | Wave 0 |
| ECF-05 | Format detector routes ECF via hint | unit | `python3 -m pytest tests/test_ecf_parser.py::TestECFFormatRouting -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `cd backend && python3 -m pytest tests/test_ecf_parser.py -x -v`
- **Per wave merge:** `make test`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/test_ecf_parser.py` -- covers ECF-01 through ECF-05 with inline text fixtures
- [ ] No new fixtures needed -- ECF test fixtures are inline text strings (same pattern as existing `test_extract_parser.py`)

## Open Questions

1. **International Addresses**
   - What we know: Entry 328 (Rocky Allen Wilson) has a Norway address. The shared `parse_address()` assumes US format.
   - What's unclear: How many ECF filings have international addresses? Is this a one-off edge case?
   - Recommendation: Flag international addresses (non-US state) during parsing. The existing flagging logic in `_check_flagging()` already flags invalid states. This is acceptable for Phase 1.

2. **Page Header Variability**
   - What we know: The sample PDF has consistent page headers across all 21 pages.
   - What's unclear: Do other ECF filings (different applicants, counties) use the same header format?
   - Recommendation: Build header stripping with patterns general enough for OCC filings (match "MULTIUNIT HORIZONTAL WELL" and "CASE CD" patterns rather than hardcoding applicant name). LOW risk -- OCC filing format is standardized.

3. **PyMuPDF Text Extraction Column Detection**
   - What we know: The existing `extract_text_from_pdf()` auto-detects column count and defaults to 3 columns. The ECF Exhibit A is single-column.
   - What's unclear: Whether the auto-detection correctly identifies ECF as 1-2 columns, or if it misreads as 3 columns.
   - Recommendation: Test with sample PDF. If column detection fails, pass `num_columns=1` explicitly for ECF format. The upload endpoint already has the format hint available before calling text extraction.

## Sources

### Primary (HIGH confidence)
- `ecf_20650786.pdf` -- actual sample PDF, 21 pages, 357 entries across 5 sections
- `backend/app/services/extract/parser.py` -- existing parser implementation and patterns
- `backend/app/services/extract/format_detector.py` -- ExhibitFormat enum and detection logic
- `backend/app/models/extract.py` -- PartyEntry, ExtractionResult Pydantic models
- `backend/app/utils/patterns.py` -- entity detection patterns (detect_entity_type)
- `backend/app/services/extract/pdf_extractor.py` -- PyMuPDF text extraction
- `backend/app/api/extract.py` -- upload endpoint with format_hint routing
- `frontend/src/pages/Extract.tsx` -- CaseMetadata interface definition (lines 31-37)

### Secondary (MEDIUM confidence)
- `backend/app/services/shared/address_parser.py` -- address parsing implementation
- `backend/app/services/extract/name_parser.py` -- name parsing and entity classification
- `backend/tests/test_extract_parser.py` -- existing test patterns for extract tool

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already installed and in use; no new dependencies
- Architecture: HIGH -- clear module separation follows existing tool-per-module pattern; sample PDF thoroughly analyzed
- Pitfalls: HIGH -- identified from direct analysis of sample PDF text extraction output and existing code patterns

**Research date:** 2026-03-12
**Valid until:** 2026-04-12 (stable -- OCC filing format unlikely to change)

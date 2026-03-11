---
phase: quick-2
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/app/services/extract/format_detector.py
  - backend/app/services/extract/table_parser.py
  - backend/app/services/extract/parser.py
  - backend/app/services/extract/pdf_extractor.py
  - backend/app/models/extract.py
  - backend/app/api/extract.py
  - frontend/src/pages/Extract.tsx
autonomous: true
requirements: [MULTI-FORMAT-PARSING]

must_haves:
  truths:
    - "Devon-style TABLE_ATTENTION PDFs (Name | Attention | Address 1 | Address 2) are correctly parsed into PartyEntry list"
    - "Mewbourne-style TABLE_SPLIT_ADDR PDFs (No. | Name | Address 1 | Address 2 | City | State | Zip) are correctly parsed with discrete address fields"
    - "Coterra-style FREE_TEXT_LIST PDFs (two-column numbered list with multi-line address blocks) are parsed using existing parser with proper column detection"
    - "Format is auto-detected from PDF text structure; user sees which format was detected"
    - "Quality score flags garbled/low-confidence output so user knows to try manual format override"
    - "User can manually select a format hint if auto-detection picks wrong format"
  artifacts:
    - path: "backend/app/services/extract/format_detector.py"
      provides: "ExhibitFormat enum + detect_format() function"
      exports: ["ExhibitFormat", "detect_format", "compute_quality_score"]
    - path: "backend/app/services/extract/table_parser.py"
      provides: "Table-based parsing for TABLE_ATTENTION and TABLE_SPLIT_ADDR formats using pdfplumber"
      exports: ["parse_table_pdf"]
    - path: "backend/app/models/extract.py"
      provides: "Updated ExtractionResult with format_detected, quality_score, format_warning"
    - path: "backend/app/api/extract.py"
      provides: "Upload endpoint with format detection routing and format_hint query param"
  key_links:
    - from: "backend/app/api/extract.py"
      to: "backend/app/services/extract/format_detector.py"
      via: "detect_format() call on extracted text"
      pattern: "detect_format\\("
    - from: "backend/app/api/extract.py"
      to: "backend/app/services/extract/table_parser.py"
      via: "parse_table_pdf() for table formats"
      pattern: "parse_table_pdf\\("
    - from: "backend/app/api/extract.py"
      to: "backend/app/services/extract/parser.py"
      via: "parse_exhibit_a() for FREE_TEXT formats (existing + improved)"
      pattern: "parse_exhibit_a\\("
    - from: "frontend/src/pages/Extract.tsx"
      to: "backend/app/api/extract.py"
      via: "format_hint query param and format_detected/quality_score in response"
      pattern: "format_hint|format_detected|quality_score"
---

<objective>
Add multi-format Exhibit A parsing to the Extract tool, supporting three new PDF formats (Devon table with Attention column, Mewbourne table with split City/State/Zip, and Coterra free-text numbered list) via format auto-detection and a strategy pattern that routes to the correct parser.

Purpose: Currently the Extract tool only handles one free-text Exhibit A format. Real-world OCC filings come in varied table and list layouts. This change makes the tool handle all common formats automatically.

Output: New format_detector.py, table_parser.py; modified parser.py, pdf_extractor.py, models, API, and frontend. All formats produce the same list[PartyEntry] output.
</objective>

<execution_context>
@/Users/ventinco/.claude/get-shit-done/workflows/execute-plan.md
@/Users/ventinco/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@backend/app/services/extract/pdf_extractor.py
@backend/app/services/extract/parser.py
@backend/app/services/extract/address_parser.py
@backend/app/models/extract.py
@backend/app/api/extract.py
@frontend/src/pages/Extract.tsx
@backend/app/utils/patterns.py

<interfaces>
<!-- Key types and contracts the executor needs -->

From backend/app/models/extract.py:
```python
class EntityType(str, Enum):
    INDIVIDUAL = "Individual"
    TRUST = "Trust"
    LLC = "LLC"
    CORPORATION = "Corporation"
    PARTNERSHIP = "Partnership"
    GOVERNMENT = "Government"
    ESTATE = "Estate"
    UNKNOWN_HEIRS = "Unknown Heirs"

class PartyEntry(BaseModel):
    entry_number: str
    primary_name: str
    entity_type: EntityType = EntityType.INDIVIDUAL
    mailing_address: Optional[str] = None
    mailing_address_2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    last_name: Optional[str] = None
    suffix: Optional[str] = None
    notes: Optional[str] = None
    flagged: bool = False
    flag_reason: Optional[str] = None

class ExtractionResult(BaseModel):
    success: bool
    entries: list[PartyEntry] = []
    total_count: int = 0
    flagged_count: int = 0
    error_message: Optional[str] = None
    source_filename: Optional[str] = None
    job_id: Optional[str] = None
```

From backend/app/services/extract/parser.py:
```python
def parse_exhibit_a(text: str) -> list[PartyEntry]  # Main entry point for free-text parsing
```

From backend/app/services/extract/pdf_extractor.py:
```python
def extract_text_from_pdf(file_bytes: bytes) -> str
def extract_party_list(text: str) -> str
def _sort_blocks_by_columns(blocks, page_width, num_columns=3) -> list[dict]
def _extract_with_pdfplumber(file_bytes: bytes) -> str
```

From backend/app/services/extract/address_parser.py:
```python
from app.services.shared.address_parser import parse_address  # Returns dict with street, street2, city, state, zip
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Backend format detection + table parser + API routing</name>
  <files>
    backend/app/services/extract/format_detector.py,
    backend/app/services/extract/table_parser.py,
    backend/app/services/extract/parser.py,
    backend/app/services/extract/pdf_extractor.py,
    backend/app/models/extract.py,
    backend/app/api/extract.py
  </files>
  <action>
**1. Create `format_detector.py`:**
- Define `ExhibitFormat(str, Enum)` with values: `FREE_TEXT_NUMBERED` (existing default), `TABLE_ATTENTION` (Devon-style), `TABLE_SPLIT_ADDR` (Mewbourne-style), `FREE_TEXT_LIST` (Coterra-style), `UNKNOWN`.
- `detect_format(text: str, file_bytes: bytes | None = None) -> ExhibitFormat`:
  - Check for TABLE_ATTENTION: look for "Attention" column header pattern near table headers like "Name" and "Address" (Devon pattern).
  - Check for TABLE_SPLIT_ADDR: look for column headers with separate "City", "State", "Zip" columns (Mewbourne pattern). Also check for "Curative Parties" section marker.
  - Check for FREE_TEXT_LIST: check for two-column numbered list pattern (numbers like "1." appearing in multiple columns per page), plus "RESPONDENTS WITH ADDRESS UNKNOWN" section header.
  - If file_bytes provided, also try pdfplumber `extract_tables()` to confirm table presence: if tables found with 4+ columns, lean toward TABLE_ATTENTION or TABLE_SPLIT_ADDR based on column count (4 cols with Attention = TABLE_ATTENTION, 7 cols with City/State/Zip = TABLE_SPLIT_ADDR).
  - Default to `FREE_TEXT_NUMBERED` if no clear signal.
- `compute_quality_score(entries: list[PartyEntry], total_expected: int | None = None) -> float`:
  - Score 0.0-1.0 based on: ratio of non-flagged entries, ratio with valid addresses, ratio with valid names (>5 chars, no garbled characters). Garbled detection: check for high ratio of non-ASCII/non-printable chars, or lines that are mostly numbers/symbols.

**2. Create `table_parser.py`:**
- `parse_table_pdf(file_bytes: bytes, fmt: ExhibitFormat) -> list[PartyEntry]`:
  - Open PDF with pdfplumber, iterate pages, call `page.extract_tables()`.
  - For `TABLE_ATTENTION`: expect columns [Name, Attention, Address1, Address2]. Map Attention to notes (as "c/o {attention}"). Parse Address2 for city/state/zip using `parse_address()`. Row number becomes entry_number.
  - For `TABLE_SPLIT_ADDR`: expect columns [No., Name, Address1, Address2, City, State, Zip]. Map directly to PartyEntry fields. Handle "Curative Parties" section by checking if a row contains that text and skipping it (or flagging subsequent entries with a note).
  - For both: skip header rows (detect by checking if first cell matches column header text). Skip empty rows. Use `_detect_entity_type()` from parser.py for entity detection. Use `parse_name()` from name_parser.py for individual name splitting.
  - Handle merged cells and multi-line cell content gracefully.
  - If `extract_tables()` returns empty/None for a page, fall back to text extraction for that page.

**3. Modify `parser.py`:**
- In `_split_into_entries()`: add handling for "RESPONDENTS WITH ADDRESS UNKNOWN" header. When this header is encountered, prefix subsequent entry numbers with "U" (for unknown address). The existing pattern already handles "U1." etc., but ensure entries after this header that lack the U prefix get it added.
- In `_clean_exhibit_text()`: add "RESPONDENTS WITH ADDRESS UNKNOWN" to skip_patterns so it does not appear as an entry name.

**4. Modify `pdf_extractor.py`:**
- In `_sort_blocks_by_columns()`: accept `num_columns` parameter (already exists, default 3). The Coterra format uses 2 columns, so the API layer will need to pass this. Add a helper function `detect_column_count(file_bytes: bytes) -> int` that analyzes text block x-positions on the first page to determine if layout is 2 or 3 columns. Use clustering: if blocks cluster into 2 distinct x-ranges, return 2; if 3, return 3; default 3.
- Modify `extract_text_from_pdf()` to accept optional `num_columns: int = None` parameter. If None, auto-detect using `detect_column_count()`. Pass to `_sort_blocks_by_columns()`.

**5. Modify `models/extract.py`:**
- Add to `ExtractionResult`:
  - `format_detected: Optional[str] = Field(None, description="Auto-detected format (e.g., TABLE_ATTENTION, FREE_TEXT_LIST)")`
  - `quality_score: Optional[float] = Field(None, description="Parsing quality score 0.0-1.0")`
  - `format_warning: Optional[str] = Field(None, description="Warning if quality is low or format uncertain")`

**6. Modify `api/extract.py`:**
- Add `format_hint: Optional[str] = Query(None)` parameter to `upload_pdf()`.
- After `extract_text_from_pdf()`, call `detect_format(full_text, file_bytes)` to determine format. If `format_hint` is provided and is a valid ExhibitFormat value, use that instead.
- Route by format:
  - `TABLE_ATTENTION` or `TABLE_SPLIT_ADDR`: call `parse_table_pdf(file_bytes, fmt)`.
  - `FREE_TEXT_LIST`: call `extract_text_from_pdf(file_bytes, num_columns=2)` then `extract_party_list()` then `parse_exhibit_a()`.
  - `FREE_TEXT_NUMBERED` (default): existing flow unchanged.
- After parsing, call `compute_quality_score(entries)`.
- If quality_score < 0.5, set format_warning to "Low parsing confidence. Try selecting a different format manually."
- Populate `format_detected`, `quality_score`, `format_warning` on ExtractionResult.
- Import new modules: `from app.services.extract.format_detector import ExhibitFormat, detect_format, compute_quality_score` and `from app.services.extract.table_parser import parse_table_pdf`.
  </action>
  <verify>
    <automated>cd "/Users/ventinco/Documents/Projects/Table Rock TX/Tools/toolbox" && python3 -c "from backend.app.services.extract.format_detector import ExhibitFormat, detect_format, compute_quality_score; from backend.app.services.extract.table_parser import parse_table_pdf; print('imports OK')" && python3 -c "from backend.app.models.extract import ExtractionResult; r = ExtractionResult(success=True, format_detected='TABLE_ATTENTION', quality_score=0.95); print(f'model OK: {r.format_detected} {r.quality_score}')" && cd backend && python3 -m py_compile app/api/extract.py && python3 -m py_compile app/services/extract/format_detector.py && python3 -m py_compile app/services/extract/table_parser.py && python3 -m py_compile app/services/extract/parser.py && python3 -m py_compile app/services/extract/pdf_extractor.py && echo "All compiles OK"</automated>
  </verify>
  <done>
    - format_detector.py exists with ExhibitFormat enum, detect_format(), and compute_quality_score()
    - table_parser.py exists with parse_table_pdf() that handles TABLE_ATTENTION and TABLE_SPLIT_ADDR using pdfplumber extract_tables()
    - parser.py handles "RESPONDENTS WITH ADDRESS UNKNOWN" header correctly
    - pdf_extractor.py supports configurable column count with auto-detection
    - ExtractionResult model has format_detected, quality_score, format_warning fields
    - API upload endpoint accepts format_hint param and routes to correct parser
    - All files compile without errors
  </done>
</task>

<task type="auto">
  <name>Task 2: Frontend format indicator + manual format selector</name>
  <files>frontend/src/pages/Extract.tsx</files>
  <action>
**Modify `Extract.tsx`:**

1. **Update TypeScript interfaces:**
   - Add to `ExtractionResult` interface: `format_detected?: string`, `quality_score?: number`, `format_warning?: string`.

2. **Add format_hint state:**
   - Add `const [formatHint, setFormatHint] = useState<string>('')` near other state declarations.

3. **Pass format_hint on upload:**
   - In `handleFilesSelected()`, when building the fetch URL, append `?format_hint={formatHint}` if formatHint is not empty. Change the fetch URL from `` `${API_BASE}/extract/upload` `` to `` `${API_BASE}/extract/upload${formatHint ? `?format_hint=${formatHint}` : ''}` ``.

4. **Add format selector dropdown in the upload area:**
   - Below the `<FileUpload>` component (in both the panelCollapsed and non-collapsed upload sections), add a small dropdown:
   ```tsx
   <div className="mt-3 flex items-center gap-2">
     <label className="text-xs text-gray-500">Format:</label>
     <select
       value={formatHint}
       onChange={(e) => setFormatHint(e.target.value)}
       className="text-xs border border-gray-300 rounded px-2 py-1 focus:ring-tre-teal focus:border-tre-teal"
     >
       <option value="">Auto-detect</option>
       <option value="FREE_TEXT_NUMBERED">Free Text (Default)</option>
       <option value="TABLE_ATTENTION">Table with Attention Column</option>
       <option value="TABLE_SPLIT_ADDR">Table with Split Address</option>
       <option value="FREE_TEXT_LIST">Two-Column Numbered List</option>
     </select>
   </div>
   ```

5. **Show format detection info in results header:**
   - In the results header section (after the "Processed by..." line), add a line showing detected format and quality:
   ```tsx
   {activeJob.result.format_detected && (
     <p className="text-xs text-gray-400 mt-0.5">
       Format: {activeJob.result.format_detected.replace(/_/g, ' ')}
       {activeJob.result.quality_score != null && (
         <span className={`ml-2 ${activeJob.result.quality_score < 0.5 ? 'text-red-500' : activeJob.result.quality_score < 0.75 ? 'text-yellow-500' : 'text-green-500'}`}>
           ({Math.round(activeJob.result.quality_score * 100)}% confidence)
         </span>
       )}
     </p>
   )}
   ```

6. **Show format warning banner:**
   - Right after the error banner (`{error && ...}`), add a format warning banner that shows when quality is low:
   ```tsx
   {activeJob?.result?.format_warning && (
     <div className="mb-4 p-4 bg-yellow-50 border border-yellow-200 rounded-lg flex items-center gap-2 text-yellow-700">
       <AlertCircle className="w-5 h-5" />
       <span className="text-sm">{activeJob.result.format_warning}</span>
       <span className="text-xs text-yellow-500 ml-2">Try selecting a format manually and re-uploading.</span>
     </div>
   )}
   ```
  </action>
  <verify>
    <automated>cd "/Users/ventinco/Documents/Projects/Table Rock TX/Tools/toolbox/frontend" && npx tsc --noEmit 2>&1 | head -30</automated>
  </verify>
  <done>
    - ExtractionResult interface includes format_detected, quality_score, format_warning
    - Format selector dropdown appears in upload area with Auto-detect + 4 format options
    - format_hint is passed as query param when uploading
    - Results header shows detected format name and color-coded confidence percentage
    - Yellow warning banner appears when format_warning is set
    - TypeScript compiles without errors
  </done>
</task>

</tasks>

<verification>
1. All Python files compile: `cd backend && python3 -m py_compile app/services/extract/format_detector.py && python3 -m py_compile app/services/extract/table_parser.py && python3 -m py_compile app/api/extract.py`
2. Frontend TypeScript compiles: `cd frontend && npx tsc --noEmit`
3. Backend lint passes: `cd backend && python3 -m ruff check app/services/extract/format_detector.py app/services/extract/table_parser.py app/api/extract.py app/models/extract.py`
4. Frontend lint passes: `cd frontend && npx eslint src/pages/Extract.tsx`
</verification>

<success_criteria>
- New format_detector.py with ExhibitFormat enum (5 values) and detect_format() function
- New table_parser.py with parse_table_pdf() using pdfplumber extract_tables()
- parser.py handles "RESPONDENTS WITH ADDRESS UNKNOWN" header
- pdf_extractor.py supports 2-column layout detection for Coterra format
- ExtractionResult model extended with format_detected, quality_score, format_warning
- API upload endpoint routes to correct parser based on detected/hinted format
- Frontend shows format selector, detected format info, and quality warning
- All code compiles and lints cleanly
</success_criteria>

<output>
After completion, create `.planning/quick/2-multi-format-exhibit-a-parsing-format-de/2-SUMMARY.md`
</output>

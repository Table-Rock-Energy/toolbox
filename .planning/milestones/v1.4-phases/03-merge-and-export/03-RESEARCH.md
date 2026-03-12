# Phase 3: Merge and Export - Research

**Researched:** 2026-03-12
**Domain:** Entry-number merge logic, metadata enrichment, mineral export formatting
**Confidence:** HIGH

## Summary

Phase 3 implements a merge service that combines ECF PDF parse results with optional Convey 640 CSV parse results, using entry number as the join key and PDF as the source of truth for contact fields. The merge also enriches entries with CSV metadata (county, STR, case number, applicant) and produces mineral export output with maximum field coverage.

All building blocks exist: `ECFParseResult` and `Convey640ParseResult` share the same `PartyEntry` and `CaseMetadata` types, the `ExtractionResult` model already has `merge_warnings` and `case_metadata` fields, the frontend already displays merge warnings, and the export service already accepts `county` and `campaign_name` parameters. The work is creating `merge_service.py`, wiring it into the upload endpoint, and enhancing export to populate Notes/Comments with metadata.

**Primary recommendation:** Build a single `merge_service.py` module with a pure function `merge_entries()` that takes both parse results, returns merged entries + merged metadata + warnings. Wire it into the existing ECF branch of the upload endpoint. Enhance export service to append metadata to Notes/Comments.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Entry-number matching is the join key (both parsers produce entry_number fields)
- PDF wins all contact fields: name, address, city, state, ZIP, entity type
- CSV only contributes: metadata fields (county, STR, case number, applicant) and fills genuinely blank PDF fields
- CSV-only entries (no PDF match): include in results with merge_warning flag -- don't drop them
- If entry numbers don't align at all (>50% unmatched): fall back to PDF-only mode, CSV metadata still populates export-level fields, per-entry merge skipped with warning
- Fuzzy matching deferred to future (MATCH-01) -- entry-number matching only for v1.4
- Single upload endpoint: add optional csv_file parameter to existing POST /api/extract/upload
- New services/extract/merge_service.py module
- AI address validation handled by existing unified AI post-processing pipeline, not a new merge-specific AI step
- Summary banner above results: "350 of 357 entries matched. 7 CSV-only entries included (unverified)."
- CSV-only entries: yellow warning icon with tooltip
- Uses existing PartyEntry.flagged and PartyEntry.notes fields for per-row warning data
- merge_warnings field in UploadResponse carries structured warning data
- Column mapping: county -> County, case_number -> Campaign Name (e.g., "CD 2026-000909-T")
- Remaining metadata (legal description, applicant, well name) appended to Notes/Comments
- Notes format: "Legal: S19-30-31 T10N R11W | Applicant: Coterra | Well: Diana Prince 1H"
- No new mineral export columns needed -- uses existing MINERAL_EXPORT_COLUMNS

### Claude's Discretion
- Internal merge_service.py function signatures and data structures
- Exact metadata-to-notes formatting
- How to detect "entry numbers don't align at all" threshold
- Warning banner component placement and styling details
- How to handle CSV metadata when CSV is present but merge falls back to PDF-only mode

### Deferred Ideas (OUT OF SCOPE)
- Fuzzy name matching between PDF and CSV (MATCH-01) -- deferred to future release
- Manual match override UI for unmatched entries (MATCH-02) -- deferred
- Match confidence scoring (MATCH-03) -- deferred
- Expandable warning banner with specific entry numbers -- possible future enhancement
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| MRG-01 | When both PDF and CSV are provided, merge uses PDF as source of truth for names and addresses | merge_service.py: PDF entry fields always win; CSV fills only genuinely blank fields |
| MRG-02 | CSV metadata (county, STR, case number) enriches the merged result | Merge CaseMetadata objects: prefer CSV values when PDF values are None |
| MRG-03 | Entries are matched between PDF and CSV by entry number | Dict-based lookup: `csv_by_entry = {e.entry_number: e for e in csv_entries}` |
| MRG-04 | Mismatched entry counts or unmatched entries are flagged for user review | merge_warnings list + per-entry flagged/flag_reason for CSV-only entries |
| EXP-01 | Merged results export to mineral export CSV format (MINERAL_EXPORT_COLUMNS) | Existing export_service.to_csv() already works -- just pass merged entries + metadata |
| EXP-02 | Merged results export to mineral export Excel format | Existing export_service.to_excel() already works -- just pass merged entries + metadata |
| EXP-03 | County, case number, applicant, and legal description populate appropriate mineral export fields | County -> County column, case_number -> Campaign Name, rest -> Notes/Comments |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.x | Upload endpoint modification (add csv_file param) | Already in use |
| Pydantic | 2.x | CaseMetadata, PartyEntry, ExtractionResult models | Already in use |
| Pandas | 2.x | Convey 640 file reading (existing parser) | Already in use |

### Supporting
No new libraries needed. This phase is pure Python logic on top of existing types.

### Alternatives Considered
None -- all decisions are locked. The merge uses entry-number matching only (no fuzzy matching libraries).

## Architecture Patterns

### Recommended Project Structure
```
backend/app/services/extract/
├── ecf_parser.py          # Existing -- returns ECFParseResult
├── convey640_parser.py    # Existing -- returns Convey640ParseResult
├── merge_service.py       # NEW -- merge_entries() pure function
├── export_service.py      # MODIFY -- add metadata-to-notes logic
└── ...
```

### Pattern 1: Pure Merge Function
**What:** A stateless function that takes two parse results and returns merged output. No side effects, no I/O, no state.
**When to use:** Always -- this is the core of Phase 3.

```python
@dataclass
class MergeResult:
    """Result of merging PDF and CSV parse results."""
    entries: list[PartyEntry]
    metadata: CaseMetadata
    warnings: list[str]

def merge_entries(
    pdf_result: ECFParseResult,
    csv_result: Convey640ParseResult | None,
) -> MergeResult:
    """Merge ECF PDF entries with optional Convey 640 CSV entries.

    PDF is source of truth for contact fields.
    CSV contributes metadata and fills genuinely blank PDF fields.
    """
```

### Pattern 2: Metadata Merging
**What:** Combine CaseMetadata from both sources, preferring CSV for metadata fields since CSV metadata (county, STR, case number) is more reliably structured than PDF header regex extraction.
**When to use:** When CSV is provided.

```python
def _merge_metadata(
    pdf_meta: CaseMetadata, csv_meta: CaseMetadata | None
) -> CaseMetadata:
    """CSV metadata fills gaps in PDF metadata."""
    if csv_meta is None:
        return pdf_meta
    return CaseMetadata(
        county=pdf_meta.county or csv_meta.county,
        legal_description=pdf_meta.legal_description or csv_meta.legal_description,
        applicant=pdf_meta.applicant or csv_meta.applicant,
        case_number=pdf_meta.case_number or csv_meta.case_number,
        well_name=pdf_meta.well_name,  # PDF only -- CSV doesn't have well_name
    )
```

### Pattern 3: Entry-Number Matching with Fallback
**What:** Build a dict of CSV entries keyed by entry_number. Iterate PDF entries, look up matching CSV entry. Track unmatched on both sides. If >50% unmatched, fall back to PDF-only mode.
**When to use:** Core merge logic.

```python
csv_by_entry = {e.entry_number: e for e in csv_entries}
matched = 0
for pdf_entry in pdf_entries:
    csv_entry = csv_by_entry.pop(pdf_entry.entry_number, None)
    if csv_entry:
        matched += 1
        _fill_blanks(pdf_entry, csv_entry)
    merged.append(pdf_entry)

# Remaining csv_by_entry values are CSV-only entries
match_rate = matched / len(pdf_entries) if pdf_entries else 0
if match_rate < 0.5:
    # Fall back to PDF-only mode
    ...
```

### Pattern 4: Notes/Comments Metadata Formatting
**What:** Append case metadata to each entry's Notes/Comments for the mineral export.
**When to use:** In export_service.py when building the export DataFrame.

```python
# Format: "Legal: S19-30-31 T10N R11W | Applicant: Coterra | Well: Diana Prince 1H"
metadata_parts = []
if case_metadata.legal_description:
    metadata_parts.append(f"Legal: {case_metadata.legal_description}")
if case_metadata.applicant:
    metadata_parts.append(f"Applicant: {case_metadata.applicant}")
if case_metadata.well_name:
    metadata_parts.append(f"Well: {case_metadata.well_name}")
metadata_note = " | ".join(metadata_parts)
```

### Anti-Patterns to Avoid
- **Mutating PDF entries in place during merge:** Create copies or use the existing PartyEntry model's `.model_copy(update=...)` for clarity.
- **Complex merge classes with state:** Keep it as pure functions. No MergeService class needed.
- **Overwriting PDF notes with CSV notes:** Combine them. PDF notes (c/o, deceased, etc.) must be preserved; CSV metadata appends.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Export formatting | Custom CSV writer | Existing `export_service.to_csv/to_excel` | Already handles MINERAL_EXPORT_COLUMNS, name parsing, section filtering |
| AI validation | Merge-specific AI step | Existing `auto_enrich` pipeline | Already runs on extraction results post-merge |
| File upload handling | Custom multipart parsing | FastAPI `UploadFile = File(None)` | Standard FastAPI pattern for optional file upload |

## Common Pitfalls

### Pitfall 1: Entry Number Type Mismatch
**What goes wrong:** ECF parser produces `entry_number` as string (e.g., "104"), Convey 640 parser also produces string, but edge cases exist: CSV row index fallback produces "1", "2" while PDF starts at "1" too.
**Why it happens:** Both parsers produce string entry numbers, but the numbering schemes must actually match for the join to work.
**How to avoid:** Join on exact string match of `entry_number`. The CONTEXT.md acknowledges alignment is unknown -- build robust warnings.
**Warning signs:** High unmatched rate in tests.

### Pitfall 2: Notes Field Concatenation
**What goes wrong:** Entry already has notes from PDF parser (e.g., "c/o Jane Smith; deceased"), and metadata notes need to be appended without losing existing content.
**Why it happens:** Multiple sources contribute to the same field.
**How to avoid:** When building export notes, join existing entry.notes with metadata notes using "; " separator. Never overwrite.

### Pitfall 3: CSV-Only Entries Missing Contact Data Quality
**What goes wrong:** CSV-only entries (no PDF match) may have OCR-corrupted names/addresses from Convey 640.
**Why it happens:** Convey 640 data can have OCR artifacts since it's exported from a system that ingests scanned documents.
**How to avoid:** Flag CSV-only entries with `flagged=True` and `flag_reason="No PDF match -- data from Convey 640 only (may contain OCR errors)"`. The frontend already displays flagged entries with yellow warning.

### Pitfall 4: PDF-Only Export Path Regression
**What goes wrong:** After adding merge logic, PDF-only uploads (no CSV) break because the code path assumes CSV is always present.
**Why it happens:** Branching logic not properly handling the None case.
**How to avoid:** `merge_entries()` should accept `csv_result=None` and return PDF entries unchanged with PDF metadata. Test both paths.

### Pitfall 5: Duplicate Notes in Metadata
**What goes wrong:** Notes/Comments gets metadata appended every time, or metadata appears twice (once from merge, once from export).
**Why it happens:** Metadata-to-notes logic placed in both merge_service and export_service.
**How to avoid:** Add metadata to Notes/Comments ONLY in export_service.py (at export time), not during merge. Merge service handles per-entry field merging only.

## Code Examples

### Upload Endpoint Modification
```python
# In api/extract.py -- add csv_file parameter
@router.post("/upload", response_model=UploadResponse)
async def upload_pdf(
    file: Annotated[UploadFile, File(description="PDF file")],
    request: Request,
    format_hint: Optional[str] = Query(None),
    csv_file: Optional[UploadFile] = File(None, description="Optional Convey 640 CSV/Excel"),
) -> UploadResponse:
```

### Merge Integration in Upload Handler
```python
# After ECF parsing, before post-processing
elif fmt == ExhibitFormat.ECF:
    from app.services.extract.ecf_parser import parse_ecf_filing
    ecf_result = parse_ecf_filing(full_text)
    entries = ecf_result.entries
    case_metadata = ecf_result.metadata

    # Merge with CSV if provided
    merge_warnings = None
    if csv_file:
        csv_bytes = await csv_file.read()
        from app.services.extract.convey640_parser import parse_convey640
        from app.services.extract.merge_service import merge_entries
        csv_result = parse_convey640(csv_bytes, csv_file.filename or "upload.csv")
        merge_result = merge_entries(ecf_result, csv_result)
        entries = merge_result.entries
        case_metadata = merge_result.metadata
        merge_warnings = merge_result.warnings or None
```

### Export Service Enhancement (Notes/Comments with metadata)
```python
# In export_service.py _entries_to_dataframe()
def _entries_to_dataframe(
    entries: list[PartyEntry],
    *,
    county: str = "",
    campaign_name: str = "",
    case_metadata: CaseMetadata | None = None,  # NEW parameter
) -> pd.DataFrame:
    # ... existing logic ...
    # After building row dict:
    if case_metadata:
        metadata_note = _format_metadata_note(case_metadata)
        existing_notes = row["Notes/Comments"]
        if existing_notes and metadata_note:
            row["Notes/Comments"] = f"{existing_notes}; {metadata_note}"
        elif metadata_note:
            row["Notes/Comments"] = metadata_note
```

### Fill-Blank Logic
```python
def _fill_blanks(pdf_entry: PartyEntry, csv_entry: PartyEntry) -> PartyEntry:
    """Fill genuinely blank PDF fields from CSV. PDF wins when both have data."""
    updates = {}
    for field_name in ("mailing_address", "city", "state", "zip_code"):
        pdf_val = getattr(pdf_entry, field_name)
        csv_val = getattr(csv_entry, field_name)
        if not pdf_val and csv_val:
            updates[field_name] = csv_val
    if updates:
        return pdf_entry.model_copy(update=updates)
    return pdf_entry
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Separate PDF and CSV processing | Unified PartyEntry + CaseMetadata types | Phase 1-2 (2026-03-12) | Both parsers return identical types -- merge is trivial dict join |

No deprecated patterns. The codebase is fresh (days old).

## Open Questions

1. **Entry number alignment rate in real data**
   - What we know: Both parsers extract entry numbers. ECF PDF uses "1.", "2." format. Convey 640 CSV has entry numbers in the name column (e.g., "104 INA NADINE TAYLOR").
   - What's unclear: Whether entry numbers always correspond 1:1 between sources for the same filing.
   - Recommendation: Build with >50% threshold for fallback as specified. Log match rate. Real-world testing will validate.

2. **ExportRequest model needs case_metadata parameter**
   - What we know: Current ExportRequest has `county` and `campaign_name` fields but not `case_metadata`.
   - What's unclear: Whether to add `case_metadata` to ExportRequest or derive it from county/campaign_name.
   - Recommendation: Add optional `case_metadata: CaseMetadata | None` to ExportRequest. Frontend sends it from the stored result. This allows Notes/Comments population.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.x with pytest-asyncio |
| Config file | backend/pytest.ini |
| Quick run command | `cd /Users/yojimbo/Documents/dev/toolbox/backend && python3 -m pytest tests/test_merge_service.py -x -v` |
| Full suite command | `cd /Users/yojimbo/Documents/dev/toolbox/backend && python3 -m pytest -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MRG-01 | PDF fields win over CSV fields in merged output | unit | `python3 -m pytest tests/test_merge_service.py::TestMergeEntries::test_pdf_wins_contact_fields -x` | No - Wave 0 |
| MRG-02 | CSV metadata enriches merged result | unit | `python3 -m pytest tests/test_merge_service.py::TestMergeMetadata::test_csv_fills_pdf_gaps -x` | No - Wave 0 |
| MRG-03 | Entries matched by entry number | unit | `python3 -m pytest tests/test_merge_service.py::TestMergeEntries::test_entry_number_matching -x` | No - Wave 0 |
| MRG-04 | Mismatched entries flagged with warnings | unit | `python3 -m pytest tests/test_merge_service.py::TestMergeWarnings -x` | No - Wave 0 |
| EXP-01 | Merged results export to mineral CSV | unit | `python3 -m pytest tests/test_merge_service.py::TestMergeExport::test_csv_export -x` | No - Wave 0 |
| EXP-02 | Merged results export to mineral Excel | unit | `python3 -m pytest tests/test_merge_service.py::TestMergeExport::test_excel_export -x` | No - Wave 0 |
| EXP-03 | County/case_number/applicant/legal populate export fields | unit | `python3 -m pytest tests/test_merge_service.py::TestMetadataNotes -x` | No - Wave 0 |

### Sampling Rate
- **Per task commit:** `cd /Users/yojimbo/Documents/dev/toolbox/backend && python3 -m pytest tests/test_merge_service.py -x -v`
- **Per wave merge:** `cd /Users/yojimbo/Documents/dev/toolbox/backend && python3 -m pytest -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/test_merge_service.py` -- covers MRG-01 through MRG-04, EXP-01 through EXP-03
- No framework install needed (pytest already configured)
- No conftest.py changes needed (tests are self-contained like existing test_convey640_parser.py)

## Sources

### Primary (HIGH confidence)
- Direct code inspection of `ecf_parser.py`, `convey640_parser.py`, `export_service.py`, `api/extract.py`, `models/extract.py`, `shared/export_utils.py`
- Direct code inspection of `frontend/src/pages/Extract.tsx` (merge_warnings display already exists)
- Existing test patterns from `tests/test_convey640_parser.py`

### Secondary (MEDIUM confidence)
- None needed -- this is pure internal logic with no external dependencies

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new libraries, all existing
- Architecture: HIGH -- both parsers return identical types, merge is a dict join
- Pitfalls: HIGH -- identified from direct code reading, known field overlap patterns

**Research date:** 2026-03-12
**Valid until:** 2026-04-12 (stable internal codebase, no external dependency risk)

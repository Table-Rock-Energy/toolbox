# Phase 3: Merge and Export - Context

**Gathered:** 2026-03-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Combine PDF-authoritative respondent data with optional Convey 640 CSV metadata, merge by entry number with PDF as source of truth, and export to mineral format with maximum field coverage. Handles three modes: PDF+CSV merge, PDF-only export, and edge cases (mismatched counts, unmatched entries). Frontend display of merge warnings is in scope (banner + row flags). AI validation handled by existing post-processing pipeline, not a new merge-specific step.

</domain>

<decisions>
## Implementation Decisions

### Merge Conflict Handling
- Entry-number matching is the join key (both parsers produce entry_number fields)
- PDF wins all contact fields: name, address, city, state, ZIP, entity type
- CSV only contributes: metadata fields (county, STR, case number, applicant) and fills genuinely blank PDF fields
- CSV-only entries (no PDF match): include in results with merge_warning flag — don't drop them
- If entry numbers don't align at all (>50% unmatched): fall back to PDF-only mode, CSV metadata still populates export-level fields, per-entry merge skipped with warning
- Fuzzy matching deferred to future (MATCH-01) — entry-number matching only for v1.4
- Reliability of entry number alignment is unknown across filings — build robust warning system so mismatches are visible

### PDF-Only Export Path
- When no CSV is uploaded, PDF header metadata auto-populates mineral export fields
- Column mapping: county → County, case_number → Campaign Name (e.g., "CD 2026-000909-T")
- Remaining metadata (legal description, applicant, well name) appended to each entry's Notes/Comments
- Notes format: "Legal: S19-30-31 T10N R11W | Applicant: Coterra | Well: Diana Prince 1H"
- No new mineral export columns needed — uses existing MINERAL_EXPORT_COLUMNS

### Merge Service Location
- Single upload endpoint: add optional csv_file parameter to existing POST /api/extract/upload
- Frontend already sends both files in one FormData (csv_file key) — backend just needs to accept it
- New services/extract/merge_service.py module with merge_entries(pdf_entries, csv_entries, pdf_metadata, csv_metadata)
- Upload handler calls merge_service when CSV is present, otherwise PDF-only flow
- AI address validation handled by existing unified AI post-processing pipeline (gemini_service.py), not a new merge-specific AI step

### Warning/Flag Display
- Summary banner above results: "350 of 357 entries matched. 7 CSV-only entries included (unverified)."
- Count summary only (no entry number lists in banner)
- CSV-only entries: yellow warning icon in table row with tooltip "No PDF match — data from Convey 640 only (may contain OCR errors)"
- Uses existing PartyEntry.flagged and PartyEntry.notes fields for per-row warning data
- merge_warnings field in UploadResponse carries structured warning data

### Claude's Discretion
- Internal merge_service.py function signatures and data structures
- Exact metadata-to-notes formatting
- How to detect "entry numbers don't align at all" threshold
- Warning banner component placement and styling details
- How to handle CSV metadata when CSV is present but merge falls back to PDF-only mode

</decisions>

<specifics>
## Specific Ideas

- User wants AI (Gemini) to validate addresses and help resolve outstanding issues — this should flow through the existing AI post-processing pipeline, not a custom merge step
- Notes/Comments should include legal description, applicant, and well name for every exported row (useful context when contacts are loaded into GHL)
- Campaign Name column gets the case number (e.g., "CD 2026-000909-T") — this is the identifier that groups contacts from the same filing

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `export_service.py`: Already handles ECF section_type filtering, county/campaign_name parameters — needs metadata pass-through
- `PartyEntry` model: Has `flagged`, `notes`, `section_type`, `entry_number` fields — all needed for merge
- `ExtractionResult` model: Already has `case_metadata` and `merge_warnings` fields (added in Phase 4 frontend)
- `convey640_parser.py`: Returns parsed entries + metadata separately — ready for merge consumption
- `ecf_parser.py`: Returns ECFParseResult with entries + metadata — ready for merge consumption
- `MINERAL_EXPORT_COLUMNS` in shared/export_utils.py: No changes needed
- `MineralExportModal`: Already auto-populates county for ECF format

### Established Patterns
- Tool-per-module: merge_service.py goes in services/extract/ alongside ecf_parser.py and convey640_parser.py
- Upload endpoint in api/extract.py: Currently ~80 lines with format routing — add CSV acceptance and merge call
- Frontend sends csv_file via FormData.append('csv_file', csvFile) — backend needs matching UploadFile parameter

### Integration Points
- `api/extract.py` upload endpoint: Add optional `csv_file: UploadFile = File(None)` parameter
- `export_service.py` to_csv/to_excel: Pass case_metadata for Notes/Comments population and county/campaign auto-fill
- Frontend Extract.tsx: Already sends csv_file, already has merge_warnings display capability, needs banner component for summary warnings
- Existing AI post-processing pipeline: merge results feed into it like any other extraction result

</code_context>

<deferred>
## Deferred Ideas

- Fuzzy name matching between PDF and CSV (MATCH-01) — deferred to future release
- Manual match override UI for unmatched entries (MATCH-02) — deferred
- Match confidence scoring (MATCH-03) — deferred
- Expandable warning banner with specific entry numbers — possible future enhancement

</deferred>

---

*Phase: 03-merge-and-export*
*Context gathered: 2026-03-12*

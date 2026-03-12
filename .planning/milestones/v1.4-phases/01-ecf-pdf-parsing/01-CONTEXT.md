# Phase 1: ECF PDF Parsing - Context

**Gathered:** 2026-03-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Parse ECF Exhibit A respondent lists from OCC multiunit horizontal well application PDFs. Produce numbered entries with names, addresses, entity types, and case metadata. This phase handles PDF parsing only — CSV processing (Phase 2) and merge logic (Phase 3) are separate.

</domain>

<decisions>
## Implementation Decisions

### Format Detection
- ECF is hint-only — only parse as ECF when the user selects "ECF Filing" from the Extract page dropdown (format_hint='ECF')
- No auto-detection needed; the frontend already sends the hint via query parameter
- Add `ECF` to the `ExhibitFormat` enum but do not add detection patterns to `detect_format()`

### Respondent Sections
- Parse ALL numbered entries from every section in the PDF:
  - Regular respondents (1-264 in sample)
  - CURATIVE RESPONDENTS (265-351 in sample)
  - RESPONDENTS WITH ADDRESS UNKNOWN (352-353 in sample)
  - CURATIVE RESPONDENTS WITH ADDRESS UNKNOWN (354-356 in sample)
  - FOR INFORMATIONAL PURPOSES ONLY (357 in sample)
- Tag each entry with its section type (regular, curative, address_unknown, curative_unknown, informational)
- Address-less entries are NOT filtered from parsing results — they are kept for future matching
- Frontend provides a checkbox to hide entries without addresses (not a hard filter)
- Exports exclude entries without addresses

### Two-Column Layout
- Claude's discretion on whether to reuse existing FREE_TEXT_LIST two-column splitting logic or build a new approach
- The ECF Exhibit A uses a consistent two-column numbered list layout (odd numbers left, even numbers right, reading left-to-right across columns)

### Case Metadata Extraction
- Extract ALL metadata fields from the PDF header to populate the CaseMetadata object:
  - `county`: "CADDO" (from "LAND COVERED" section)
  - `legal_description`: "SECTION(S) 19, 30 AND 31, TOWNSHIP 10 NORTH, RANGE 11 WEST" (from "LAND COVERED")
  - `applicant`: "COTERRA ENERGY OPERATING CO." (from "APPLICANT" line)
  - `case_number`: "CD 2026-000909-T" (from "CAUSE NO." line)
  - `well_name`: "Diana Prince 1H-193031X" (from paragraph 2(D) well name reference)
- The frontend CaseMetadata interface already expects these exact fields

### Entity Type Classification
- "deceased" and "Heirs and Devisees of" entries → EntityType.ESTATE
- "possibly deceased" entries → EntityType.ESTATE (conservative classification)
- c/o person captured in notes field (e.g., "c/o Oscar McCarter Jr")
- "now [married name]" patterns (e.g., "Alisha Brummett now Recker") → notes field, use current name as primary
- a/k/a, f/k/a chains → existing name_parser and notes handling applies
- Trust, LLC, LP, Corporation, Partnership → existing entity detection patterns apply unchanged

### Claude's Discretion
- Whether to build a dedicated ECF parser module or extend existing parser
- Two-column text splitting approach
- How to extract well name from the application body text
- Page header/footer stripping approach (red "CASE CD..." headers appear on every page)

</decisions>

<specifics>
## Specific Ideas

- Sample ECF PDF: `ecf_20650786.pdf` (Coterra Energy, Caddo County, 357 entries across 5 sections, 21 pages)
- Sample Convey 640: `convey640_respondents_1686_20260_00909_19-10N-11W_2026-03-05_12_57_34.xlsx` (357 rows, 12 columns)
- The Convey 640 name column has entry numbers prepended (e.g., "104 INA NADINE TAYLOR REVOCABLE TRUST...") — relevant for Phase 2 parsing, not Phase 1
- Some entries span 4-5 lines (trust names with trustees and dates are the longest)
- Entry 328 (Rocky Allen Wilson) has an international address (Norway) — edge case for address parsing
- The "FOR INFORMATIONAL PURPOSES ONLY" section (entry 357) is the applicant itself — may want to flag or skip this
- Address-less entries should remain in the database for future name matching when contact info becomes available from other sources

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ExhibitFormat` enum in `format_detector.py`: Add ECF variant
- `PartyEntry` model in `models/extract.py`: Already has all needed fields (entry_number, primary_name, entity_type, address fields, notes, flagged)
- `ExtractionResult` model: Frontend already expects `case_metadata` and `merge_warnings` fields (added in Phase 4)
- `name_parser.py`: parse_name() splits first/middle/last/suffix — reusable for ECF individuals
- `utils/patterns.py`: Entity detection regex patterns (TRUST_PATTERN, LLC_PATTERN, ESTATE_PATTERN, etc.) — directly applicable
- `pdf_extractor.py`: extract_text_from_pdf() via PyMuPDF — reusable for ECF text extraction
- `address_parser.py`: parse_address() handles street/city/state/zip splitting
- Upload endpoint in `api/extract.py`: Already accepts format_hint query parameter

### Established Patterns
- Tool-per-module: new ECF parser goes in `services/extract/` alongside existing parsers
- Format routing: upload endpoint routes to parser based on ExhibitFormat enum value
- Quality scoring: `compute_quality_score()` can be applied to ECF results

### Integration Points
- `api/extract.py` upload endpoint: Add ECF routing branch after format_hint parsing
- `ExtractionResult`: Add CaseMetadata model to `models/extract.py` (frontend interface already defined)
- `ExhibitFormat` enum: Add ECF value
- Export service: Must handle section_type tagging for address filtering

</code_context>

<deferred>
## Deferred Ideas

- Convey 640 may have addresses for "address unknown" respondents — Phase 3 merge can fill these in
- Checkbox UI for hiding address-less entries — Phase 4 already built the frontend; may need minor update for this filter
- Future name matching against other data sources for address-unknown respondents — beyond v1.4 scope

</deferred>

---

*Phase: 01-ecf-pdf-parsing*
*Context gathered: 2026-03-12*

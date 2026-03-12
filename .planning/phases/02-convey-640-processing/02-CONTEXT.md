# Phase 2: Convey 640 Processing - Context

**Gathered:** 2026-03-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Parse optional Convey 640 CSV/Excel files with name normalization, ZIP code preservation, metadata extraction, and entity type detection. This phase handles CSV/Excel parsing only — merge with PDF data (Phase 3) and frontend changes (Phase 4, already complete) are separate.

</domain>

<decisions>
## Implementation Decisions

### Name Parsing Rules
- Strip leading entry numbers + optional period + whitespace from name column (regex like `^\d+\.?\s*`)
- ~45% of names have entry numbers prepended (bleed from PDF source that Convey 640 scrapes), ~55% don't
- Joint names with '&' (e.g., "JAMES E DESHIELDS JR & RITA F DESHIELDS"): first person is primary name, additional names go to notes field
- Trust names with dates: extract grantor's personal name as primary (e.g., "INA NADINE TAYLOR" from trust name), trustee name goes to notes. Goal is a contactable person name, not the legal entity name
- "deceased" markers: strip from name, set entity_type=ESTATE
- "now [married name]" patterns (e.g., "ALISHA BRUMMETT NOW RECKER"): use current/married name as primary, maiden name in notes
- Run entity type detection on CSV names (Individual, Trust, LLC, Estate, Corporation, etc.) using existing patterns

### Column Mapping & Metadata
- Expected 12 columns: county, str, applicant, classification, case_no, curative, _date, name, address, city, state, postal_code
- `curative` (0/1) maps to section_type: 0 → 'regular', 1 → 'curative' (aligns with ECF parser's section_type field)
- `case_no` (numeric 2026000909) normalized to PDF format: 'CD 2026-000909-T'
- `classification` ('MULTIUNIT|HORIZONTAL') stored as-is, no splitting
- `str` (section-township-range) stored as-is in compact format ('19-10N-11W, 30-10N-11W, 31-10N-11W')
- `_date` stored as metadata (filing/scrape date)
- Metadata fields (county, str, applicant, classification, case_no, _date) extracted separately from respondent data

### Data Quality & Edge Cases
- postal_code (float64) converted to 5-digit zero-padded string: 73071.0 → '73071', 2101.0 → '02101', NaN → empty string
- Entries with address baked into name field (e.g., entry 328 "ROCKY ALLEN WILSON" + Norwegian address): flag as anomalous, don't attempt to split
- 6 entries without addresses in sample — keep them, don't filter (consistent with Phase 1 approach)

### Parser Scope
- Strict schema validation with fallback: expect the known 12 columns by name. If columns are missing or renamed, return clear error listing expected vs found columns
- Accept both CSV (.csv) and Excel (.xlsx) files — pandas handles both
- Integrated into existing upload endpoint (POST /api/extract/upload) — frontend already sends CSV as second file in dual-file upload
- User uploads each file they want before processing (both files in one request)

### Claude's Discretion
- Internal data model structure for parsed CSV rows (Pydantic model design)
- How to structure the parser module (single file vs multiple)
- Exact regex for entry number stripping
- How to detect and handle the rare embedded-address anomaly for flagging

</decisions>

<specifics>
## Specific Ideas

- Sample file: `convey640_respondents_1686_20260_00909_19-10N-11W_2026-03-05_12_57_34.xlsx` (357 rows, 12 columns, Coterra Energy / Caddo County)
- Business context: these names are used to find people to contact about buying mineral assets. A contactable person name (first + last) is more valuable than a legal entity name
- The entry numbers in the name column come from the PDF source that Convey 640 scrapes — sometimes the period separator between number and name gets lost, so numbers run into names
- Convey 640 only has curative=0/1, not the full 5 section types from the PDF (regular, curative, address_unknown, curative_unknown, informational)

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `services/extract/ecf_parser.py`: Entity detection, name parsing patterns (deceased, a/k/a, c/o, now/married) — reusable logic
- `utils/patterns.py`: TRUST_PATTERN, LLC_PATTERN, ESTATE_PATTERN, etc. — directly applicable for entity detection
- `services/extract/name_parser.py`: parse_name() for first/middle/last/suffix splitting
- `models/extract.py`: PartyEntry model (entry_number, primary_name, entity_type, address fields, notes, flagged, section_type)
- pandas: already in dependencies, used extensively in proration CSV processing

### Established Patterns
- Tool-per-module: new Convey 640 parser goes in `services/extract/` alongside ecf_parser.py
- Pydantic models for validation in `models/extract.py`
- Upload endpoint in `api/extract.py` already accepts format_hint and optional CSV file

### Integration Points
- `api/extract.py` upload endpoint: CSV file already accepted via dual-file upload (Phase 4 frontend)
- `PartyEntry` model: CSV parsed rows should produce the same PartyEntry objects that the ECF parser produces
- Phase 3 merge will consume both PDF PartyEntry list and CSV PartyEntry list

</code_context>

<deferred>
## Deferred Ideas

- FMT-02 (Convey 640 schema variations across export versions) — deferred to future release per REQUIREMENTS.md
- Fuzzy name matching between PDF and CSV when entry numbers don't align — deferred to future (MATCH-01)

</deferred>

---

*Phase: 02-convey-640-processing*
*Context gathered: 2026-03-12*

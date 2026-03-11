# Pitfalls Research

**Domain:** ECF PDF parsing and Convey 640 CSV/Excel merge for Extract tool
**Researched:** 2026-03-11
**Confidence:** HIGH

## Critical Pitfalls

### Pitfall 1: Multi-Line Address Parsing with Inconsistent Line Breaks

**What goes wrong:**
ECF PDFs contain multi-line addresses (name line, street line, city/state/ZIP line) but PDF text extraction may not preserve line breaks consistently. Addresses collapse into single-line text or break at wrong positions, causing name fragments to bleed into address fields or vice versa.

**Why it happens:**
PDF text extraction returns text in reading order but doesn't always preserve visual layout. Multi-column or complex layouts can result in text blocks being extracted out of order. The existing parser (`_separate_name_and_address`) relies on detecting street patterns (`^\d+\s+`, `P.O. Box`, `c/o`) and city/state/ZIP patterns, but if line breaks are missing, these patterns may match fragments within names (e.g., "123 Trust" detected as street address).

**How to avoid:**
- Test PDF extraction with multiple ECF filing formats to identify layout variations
- Implement line-aware parsing that preserves `\n` boundaries and treats each line as a parsing unit
- Add heuristic checks: if "street pattern" appears before sufficient name text (e.g., <10 chars), flag as suspicious
- Validate against known entity types: if detected "street address" contains trust/estate keywords, likely misclassification
- Use existing `_split_into_entries` pattern detection but enhance with address-specific line counting

**Warning signs:**
- Names shorter than 10 characters (flagging condition already exists in `_check_flagging`)
- ZIP codes or state abbreviations appearing in `primary_name` field
- Entity types detected as Individual when address contains "Trust" or "Estate"
- Very long street addresses (>150 chars) indicating collapsed multi-line data

**Phase to address:**
Phase 1 (ECF PDF Parsing) — parser implementation must handle line breaks correctly from the start

---

### Pitfall 2: Convey 640 Line Number Contamination in Name Fields

**What goes wrong:**
Convey 640 CSV/Excel exports from OCR often embed entry line numbers directly in name fields (e.g., "1. John Smith" or "U45 Jane Doe Trust"). When merging, these line numbers prevent exact string matching and contaminate the clean name data from PDFs.

**Why it happens:**
OCR tools parse the visual layout of PDFs and sometimes capture the entry number prefix as part of the name text. The Convey 640 export may not clean this up. If the merge logic uses naive string comparison or doesn't strip line numbers before matching, identical respondents won't match.

**How to avoid:**
- Pre-clean Convey 640 names: strip entry number patterns (`^\s*(U\s*)?\d+\.\s*`) before any matching logic
- Normalize both PDF and CSV names: lowercase, remove extra spaces, strip punctuation for comparison
- Use fuzzy matching (Levenshtein distance or Jaro-Winkler) with threshold (e.g., 85% similarity) instead of exact match
- Separate line number extraction into dedicated field (`entry_number`) before name comparison
- Test with known OCR datasets to identify contamination patterns

**Warning signs:**
- Merge success rate <70% when line numbers are present
- Duplicate entries with slight variations (e.g., "John Smith" vs "1. John Smith")
- Entry number field populated from CSV but not matching PDF entry numbers
- Names starting with digits in merged output

**Phase to address:**
Phase 2 (Convey 640 CSV Parsing) — normalization must happen before merge attempt in Phase 3

---

### Pitfall 3: ZIP Code Data Type Loss in Excel Import

**What goes wrong:**
ZIP codes for Northeastern US states (MA, CT, RI, NH, VT, NJ, NY) start with 0 (e.g., 02101, 06511). Excel automatically converts these to integers when opening CSV files, stripping leading zeros (02101 becomes 2101). When merging Convey 640 data, ZIP codes become invalid and don't match PDF-extracted values.

**Why it happens:**
Excel interprets numeric-looking strings as numbers by default, removing leading zeros. When saving CSV, the leading zero is permanently lost unless the column is pre-formatted as Text. Pandas `read_csv` with default `dtype=None` may infer numeric type for ZIP columns.

**How to avoid:**
- Force ZIP code columns to string dtype when reading CSV/Excel: `dtype={'zip': str}` in pandas
- Add validation: if ZIP is numeric and <10000, flag as missing leading zero
- Implement ZIP code formatting: pad to 5 digits with leading zeros if 4 digits detected
- Check state-ZIP correlation: if state is MA/CT/RI/NH/VT/ME and ZIP doesn't start with 0, auto-prepend 0
- Warn users during upload if ZIP codes appear malformed (all <10000 or mixed 4/5 digit)

**Warning signs:**
- ZIP codes with 4 digits instead of 5
- State abbreviations for Northeast states paired with ZIPs not starting with 0
- Merge logic favoring CSV ZIP over PDF when CSV has data type corruption
- ZIP validation failures in `_check_flagging` (existing pattern: `^\d{5}(-\d{4})?$`)

**Phase to address:**
Phase 2 (Convey 640 CSV Parsing) — must be handled at file ingestion, before any storage or merge

---

### Pitfall 4: Entity Type Detection Failure for Deceased Parties

**What goes wrong:**
Respondent entries like "John Smith, Deceased" or "Estate of Jane Doe" are misclassified as Individual instead of Estate. Deceased parties have special legal handling requirements (heirs, estate representatives), but if entity type is wrong, downstream workflows fail.

**Why it happens:**
The existing `detect_entity_type` pattern matching checks for "ESTATE" and "DECEASED" keywords, but pattern order matters. If "Deceased" appears after the name in comma-separated format and Individual pattern matches first (default fallback), Estate detection never runs. Additionally, "c/o [Executor Name]" patterns may override entity detection.

**How to avoid:**
- Reorder entity detection: check Estate patterns BEFORE Individual fallback
- Add deceased-specific patterns: `, Deceased`, `Deceased$`, `late [name]`, `formerly [name]`
- Extract deceased annotations to notes field but still classify as Estate
- Check for executor/administrator keywords: "by [Name], Executor" should flag Estate type
- Implement two-pass detection: first pass extracts annotations, second pass classifies base entity

**Warning signs:**
- Names ending with "Deceased" but entity_type=Individual
- "Estate of" in primary_name field but entity_type≠Estate
- Notes field contains "heir of" but no Estate classification
- c/o addresses with "Executor" or "Administrator" in recipient name

**Phase to address:**
Phase 1 (ECF PDF Parsing) — entity type detection must cover these edge cases from initial implementation

---

### Pitfall 5: Merge Logic Choosing CSV Over PDF for Name Data

**What goes wrong:**
PDF is designated as source of truth, but merge logic accidentally prefers Convey 640 CSV data when CSV fields are populated and PDF fields are parsed as None or empty string. OCR-corrupted names from CSV overwrite clean PDF names, defeating the purpose of the merge.

**Why it happens:**
Naive merge logic using `csv_value or pdf_value` or `csv_value if csv_value else pdf_value` will choose CSV when both exist, assuming CSV is equally trustworthy. If PDF parser fails to extract a field (e.g., address parsing fails, returns None), merge falls back to CSV, which may have OCR errors.

**How to avoid:**
- Implement explicit precedence: `pdf_value if pdf_value is not None else csv_value`
- For name fields: ALWAYS use PDF, ignore CSV (CSV only provides metadata like county, STR, case number)
- For address fields: PDF primary, CSV fallback only if PDF parsing completely fails
- Add merge audit logging: record which source was used for each field
- Flag merged records where CSV was used for name/address: require manual review

**Warning signs:**
- Exported data contains OCR artifacts in names (misspellings, garbled text) despite clean PDF source
- Address fields with impossible combinations (e.g., "Oklahoma City, TX" from OCR error)
- Merge output has fewer records than PDF input (indicates CSV-based deduplication happened)
- Entity types from CSV (if Convey 640 includes them) override PDF-detected types

**Phase to address:**
Phase 3 (PDF-CSV Merge) — merge logic must explicitly encode "PDF is source of truth" rule

---

### Pitfall 6: Name Parser Failure on Mc/Mac/O' Prefixes

**What goes wrong:**
Irish/Scottish names like "O'Brien", "McDonald's Trust", "MacGregor Estate" are misparsed. Apostrophes are stripped as punctuation, "Mc" is treated as middle initial, or name splitting separates "Mac" from rest of name. First/last name fields end up corrupted.

**Why it happens:**
The existing `parse_person_name` function splits on spaces and uses suffix/prefix detection, but doesn't have special handling for Celtic name prefixes. Apostrophes in "O'Name" may be removed by `clean_text` or treated as word boundary. "Mc"/"Mac" may match middle initial pattern if followed by capital letter (e.g., "McDonald" → first="Mc", middle="", last="Donald").

**How to avoid:**
- Add prefix preservation rules: keep "O'", "Mc", "Mac", "D'", "De", "Van", "Von" attached to following name part
- Use Unicode-aware apostrophe handling: recognize both ASCII apostrophe (U+0027) and typographic apostrophe (U+2019)
- Implement capitalization check: "McDonald" has two capital letters, not typical first/middle/last pattern
- Test against known Irish/Scottish name corpus
- Preserve original casing: don't force title case if original has internal capitals (McDonald not Mcdonald)

**Warning signs:**
- First names containing "Mc" or "O" as standalone values
- Last names missing expected prefix (e.g., "Brien" instead of "O'Brien")
- Names with apostrophes removed entirely
- Entity type detection failing because "McDonald Trust" became "Donald Trust"

**Phase to address:**
Phase 1 (ECF PDF Parsing) — name parsing enhancement before any export

---

### Pitfall 7: Trustee Name Conflation with Trust Entity Name

**What goes wrong:**
Entry text like "Smith Family Trust, John Smith as Trustee" is parsed with "John Smith" as primary_name instead of "Smith Family Trust". The trust entity is lost and replaced with individual trustee name, breaking entity type classification.

**Why it happens:**
The `_extract_notes` function extracts trustee info to notes field but doesn't restructure the primary name. The `_clean_name` function removes "c/o" prefixes which may contain trustee info, and the parser assumes first substantial text is the name. "Trustee" pattern matching happens after name extraction.

**How to avoid:**
- Reverse parsing order: detect trust/trustee patterns FIRST, extract trust name as primary
- Parse structure: "[Trust Name], [Trustee Name] as Trustee" → primary_name="[Trust Name]", notes="Trustee: [Trustee Name]"
- Use entity type to guide parsing: if "Trust" detected, prioritize trust name over individual names
- Handle "by [Name], Trustee" format: extract representative to notes, keep entity as primary
- Test with known trust naming patterns: "[Family Name] Trust", "[Name] Living Trust", etc.

**Warning signs:**
- Entity type detected as Trust but primary_name looks like individual name (First Last format)
- Notes field contains "Trustee: [Name]" but primary_name matches that same name
- Trust keyword in notes but entity_type=Individual
- Export shows individuals where trusts expected (e.g., all entries have first/middle/last names)

**Phase to address:**
Phase 1 (ECF PDF Parsing) — entity-aware parsing must prioritize entity name over representative name

---

### Pitfall 8: PDF Format Variation Across OCC Filing Dates

**What goes wrong:**
ECF PDF format changes over time as OCC updates filing templates. Older filings use different layout, fonts, spacing, or section headers. Parser works on recent filings but fails on older PDFs from different years.

**Why it happens:**
The existing Extract tool has format detection (`format_detector.py`) but only distinguishes OCC Exhibit A formats. ECF filings from different periods may have different:
- Section header text ("RESPONDENTS" vs "RESPONDENT LIST" vs "PARTIES")
- Entry numbering (continuous vs restarting after "ADDRESS UNKNOWN")
- Address formatting (comma-separated vs line-separated)
- Font/spacing affecting text extraction order

**How to avoid:**
- Collect sample ECF PDFs spanning multiple years (2020-2026) before building parser
- Implement format detection heuristics: detect section headers, numbering patterns, layout structure
- Use flexible pattern matching: regex with optional components for section headers
- Add version detection: extract filing date from header, apply version-specific parsing rules
- Fail gracefully: if format not recognized, flag entire filing for manual review rather than partial parse

**Warning signs:**
- Parser works on test PDFs but fails in production on older filings
- Entry number extraction fails (returns no matches or wrong sequence)
- Section detection misses "ADDRESS UNKNOWN" boundary in older formats
- Address parsing success rate varies dramatically by filing date

**Phase to address:**
Phase 1 (ECF PDF Parsing) — format detection must be robust before any production use

---

### Pitfall 9: Case Metadata Extraction Failure from PDF Header

**What goes wrong:**
County, legal description, applicant, and case number are required for mineral export output but are extracted incorrectly or missing. Header parsing fails when these fields span multiple lines or use inconsistent formatting.

**Why it happens:**
PDF headers often use non-standard layouts: fields may be in tables, use label-value pairs with varying separators, or split across pages. Text extraction may not preserve field structure. Applicant names may contain commas (e.g., "Smith Oil & Gas, LLC") which break comma-based parsing.

**How to avoid:**
- Develop header parser separately from respondent parser (different text structure)
- Use label-based extraction: find "County:", "Legal Description:", "Applicant:" labels and extract following text
- Handle multi-line fields: county may be "COUNTY OF GRADY" or just "GRADY"; legal description spans 3-5 lines
- Store unparsed header text for fallback: if structured extraction fails, provide raw text for manual entry
- Validate extracted values: county against known OK county list, case number format (e.g., CD-XXXXXX)

**Warning signs:**
- County field contains legal description text (multi-line bleed)
- Case number has extra text appended (parsing didn't stop at field boundary)
- Applicant field truncated or missing when name contains special characters
- Legal description incomplete (only first line captured)

**Phase to address:**
Phase 1 (ECF PDF Parsing) — metadata extraction is parallel track to respondent parsing

---

### Pitfall 10: Merge Match Rate Too Low (Undetected Mismatches)

**What goes wrong:**
PDF contains 50 respondents, Convey 640 CSV has 48, but merge only matches 25. Many valid matches missed due to overly strict matching criteria or name variations not accounted for. Users assume merge is complete but half the metadata is lost.

**Why it happens:**
String matching algorithms are too strict (exact match only) or fuzzy matching threshold too high (>95% similarity required). Name variations not normalized:
- "Smith, John A." (PDF) vs "John A Smith" (CSV) — comma placement differs
- "ABC Trust" (PDF) vs "ABC Living Trust" (CSV) — extra word in CSV
- "O'Brien" (PDF) vs "OBrien" (CSV) — apostrophe stripped in OCR
- Entry number mismatch: PDF entry U15 corresponds to CSV entry 30 (renumbering occurred)

**How to avoid:**
- Use multi-strategy matching: try exact match, then fuzzy (85% threshold), then phonetic (Soundex/Metaphone)
- Normalize aggressively: remove punctuation, extra spaces, "Living"/"Family", common trust words
- Try bidirectional matching: PDF→CSV and CSV→PDF, combine results
- Match by position first: PDF entry 1 likely matches CSV entry 1 even if names differ slightly
- Report match statistics: show matched/unmatched counts, flag records below similarity threshold for review
- Allow manual match confirmation: UI displays side-by-side PDF/CSV candidates for user approval

**Warning signs:**
- Match rate <60% when CSV has similar record count to PDF
- Unmatched records with visually similar names when inspected manually
- Position-based matching would succeed but name-based matching fails
- Many unmatched records have only minor differences (punctuation, spacing, word order)

**Phase to address:**
Phase 3 (PDF-CSV Merge) — matching algorithm must be tuned after parser testing, before UI implementation

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Exact string matching only (no fuzzy) | Simple implementation, fast | Low merge success rate, manual fixes required | Never — fuzzy matching is core requirement |
| CSV field overwrites PDF field if populated | Simple merge logic | Violates "PDF is source of truth", OCR errors propagate | Never — explicit precedence required |
| Skip entry number normalization | Faster CSV parsing | Line numbers contaminate names, merge fails | Never — must strip before any processing |
| Use pandas default dtypes for CSV | No explicit dtype specification | ZIP codes lose leading zeros | Never — dtype must be explicit |
| Single PDF format parser (no version detection) | Works for test files | Fails on older/newer filings in production | Only acceptable for MVP if all test files are recent (post-2024) |
| Manual case metadata entry (skip header parsing) | Faster Phase 1 implementation | Users must type county/case# for every filing | Acceptable for MVP if filing volume is low (<10/month) |
| Store merged data without audit trail | Simpler data model | Can't debug merge errors, unknown data provenance | Never — must track PDF vs CSV source per field |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Pandas CSV reading | Use default `read_csv()` without dtype | Specify `dtype={'zip': str, 'entry_number': str}` to prevent type coercion |
| Mineral export format | Assume Extract mineral export matches Title mineral export | Verify MINERAL_EXPORT_COLUMNS constant is shared/identical across tools |
| Entity type enum | Use string literals instead of EntityType enum | Import from `app.models.extract.EntityType`, use enum values consistently |
| Existing parser reuse | Copy-paste parser code for ECF format | Extend existing parser classes, add ECF format to format detection |
| Address parser | Write new address parser for ECF | Reuse `services/shared/address_parser.py`, extend if needed |
| Firestore job storage | Create separate collection for ECF jobs | Use existing `extract_jobs` collection, add `format` field to distinguish |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Loading entire CSV into memory for fuzzy matching | Slow merge (>30s for 50 records) | Use indexed lookup by entry number first, fuzzy match only for unmatched | >500 records in CSV |
| N×M fuzzy string comparison (PDF entries × CSV rows) | Exponential slowdown | Early termination: stop after first high-similarity match (>90%) | N×M >10,000 comparisons |
| Re-parsing PDF for every merge attempt | Redundant PDF extraction on each CSV upload | Cache parsed PDF results in session or Firestore | Users upload multiple CSV versions |
| Regex compilation inside loop | Slow pattern matching | Compile regex patterns once at module level (already done in `patterns.py`) | N/A — existing patterns are pre-compiled |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Trust CSV uploaded filenames | Path traversal, filename injection | Sanitize filenames, store with generated UUIDs, validate extensions |
| Display raw PDF text in error messages | Information disclosure (PII in logs) | Truncate text samples to first 50 chars, redact names/addresses in logs |
| Allow arbitrary CSV column names | CSV injection attacks in Excel | Validate column headers against expected schema, reject unexpected columns |
| Store uploaded files indefinitely | Storage cost, compliance risk | Implement retention policy (delete after 90 days), document in privacy policy |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| No merge preview before commit | Users don't see what data came from PDF vs CSV | Show side-by-side comparison table: PDF column, CSV column, Merged column |
| Silent merge failures | Low match rate goes unnoticed, incomplete data exported | Display match statistics: "45/50 matched (90%)", list unmatched entries |
| No manual match override | Users can't fix false negatives from fuzzy matching | Provide UI to manually link PDF entry to CSV row |
| Cryptic flagging reasons | Users see "flagged" but don't know why | Show specific reason: "No address found", "Invalid ZIP format: 1234" |
| PDF-only mode feels incomplete | Users expect CSV to be required, confused when optional | Clear UI messaging: "CSV optional — improves metadata, but PDF has all names/addresses" |
| No validation summary | Users export without reviewing flags | Show summary before export: "3 entries flagged, 5 addresses incomplete — review?" |

## "Looks Done But Isn't" Checklist

- [ ] **Merge logic:** Often missing audit trail (which fields came from PDF vs CSV) — verify `merge_audit` metadata stored
- [ ] **ZIP code handling:** Often missing leading zero restoration for Northeast states — verify state-ZIP correlation check exists
- [ ] **Entity type detection:** Often missing deceased/estate patterns — verify Estate patterns run before Individual fallback
- [ ] **Name normalization:** Often missing Mc/Mac/O' prefix handling — verify prefix preservation in name parser
- [ ] **Address parsing:** Often missing multi-line preservation — verify line-aware parsing for ECF format
- [ ] **CSV column validation:** Often missing dtype enforcement — verify `dtype={'zip': str}` in pandas read
- [ ] **Fuzzy matching threshold:** Often missing tuning/testing — verify match rate >75% on real sample data
- [ ] **Header metadata:** Often missing multi-line field support — verify legal description captures all lines
- [ ] **Format detection:** Often missing version handling — verify parser works on filings from 2020-2026
- [ ] **Match statistics:** Often missing from UI — verify unmatched record list displayed to user

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| ZIP code leading zeros lost | LOW | Run batch correction: detect state, prepend 0 if needed, update Firestore records |
| Merge used CSV names instead of PDF | MEDIUM | Re-run merge with corrected precedence logic, requires re-upload of PDF+CSV |
| Entry numbers contaminated names | MEDIUM | Run name cleaning script with regex strip, update database, re-export |
| Entity types misclassified | LOW | Re-run entity detection with corrected pattern order, update records in place |
| Multi-line addresses collapsed | HIGH | Re-parse original PDFs with fixed line-aware logic, replace all extracted data |
| Fuzzy matching too strict (low match rate) | MEDIUM | Lower threshold from 95% to 85%, re-run merge, review new matches manually |
| Case metadata extraction failed | LOW | Extract header text separately, provide manual entry form, store alongside auto-extracted |
| PDF format variation unhandled | MEDIUM | Add format detection for specific filing date range, re-parse affected PDFs |
| Trustee names replaced entity names | MEDIUM | Re-parse with entity-first logic, swap primary_name and notes fields if needed |
| Name parser broke Celtic prefixes | MEDIUM | Add prefix preservation rules, re-parse affected names, validate against originals |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Multi-line address parsing | Phase 1 | Test with 10 ECF PDFs, address parse success rate >90% |
| Line number contamination | Phase 2 | Inspect parsed CSV names, no entries start with digits or "U\d+" |
| ZIP code data type loss | Phase 2 | Load CSV, check all ZIP codes are strings with correct length |
| Deceased entity detection | Phase 1 | Test cases with "Deceased", "Estate of" patterns, verify Estate classification |
| Merge precedence (CSV over PDF) | Phase 3 | Merge audit log shows PDF source for name/address fields |
| Mc/Mac/O' name parsing | Phase 1 | Test with Irish/Scottish names, verify prefixes preserved |
| Trustee/trust name conflation | Phase 1 | Test with trust entries, verify entity name is primary not trustee |
| PDF format variation | Phase 1 | Test with PDFs from 2020-2026, parser handles all formats |
| Case metadata extraction | Phase 1 | Extract county/case#/applicant from 5 sample PDFs, 100% success |
| Low merge match rate | Phase 3 | Merge 3 PDF+CSV pairs, match rate >75%, report unmatched records |

## Sources

### PDF Parsing Research
- [A Comparative Study of PDF Parsing Tools](https://arxiv.org/html/2410.09871v1) — Layout and multi-column challenges
- [How to Parse PDFs Effectively: Tools, Methods & Use Cases](https://parabola.io/blog/best-methods-pdf-parsing) — Best practices for 2026
- [Challenges When Parsing PDFs With Python](https://www.theseattledataguy.com/challenges-you-will-face-when-parsing-pdfs-with-python-how-to-parse-pdfs-with-python/) — Multi-line text extraction issues

### CSV/Excel Data Quality
- [5 CSV File Import Errors (and How to Fix Them)](https://ingestro.com/blog/5-csv-file-import-errors-and-how-to-fix-them-quickly) — Column matching, encoding issues
- [Excel Import Errors and Fixes](https://flatfile.com/blog/the-top-excel-import-errors-and-how-to-fix-them/) — Data type coercion problems
- [How to Match and Merge Data in Excel](https://www.thebricks.com/resources/guide-how-to-match-and-merge-data-in-excel) — Merging strategies

### ZIP Code Handling
- [Working with Leading Zeros in Northeast ZIP Codes](https://help.littlegreenlight.com/article/53-working-with-leading-zeros-in-northeast-zip-codes) — Leading zero loss
- [Keeping Leading Zeros in Excel](https://support.microsoft.com/en-us/office/keeping-leading-zeros-and-large-numbers-1bf7b935-36e1-4985-842f-5dfa51f85fe7) — Microsoft official guidance
- [Excel ZIP Code Tricks](https://blog.batchgeo.com/excel-zip-code-tricks-leading-zeros-shorten-to-five-digits/) — Text formatting solutions

### Fuzzy String Matching
- [Fuzzy String Matching in Python Tutorial](https://www.datacamp.com/tutorial/fuzzy-string-python) — Algorithm overview
- [Deep Dive into String Similarity](https://medium.com/data-science-collective/deep-dive-into-string-similarity-from-edit-distance-to-fuzzy-matching-theory-and-practice-in-68e214c0cb1d) — Levenshtein, Jaro-Winkler
- [Fuzzy Matching 101: Complete Guide](https://dataladder.com/fuzzy-matching-101/) — False positive prevention

### Name Parsing Edge Cases
- [First and Last Name Validation for Forms](https://a-tokyo.medium.com/first-and-last-name-validation-for-forms-and-databases-d3edf29ad29d) — Special character handling
- [Why Mac and Mc Surnames Contain Second Capital Letter](https://www.todayifoundout.com/index.php/2014/02/mac-mc-surnames-often-contain-second-capital-letter/) — Celtic name patterns
- [HumanName Class Documentation](https://nameparser.readthedocs.io/en/latest/modules.html) — Nameparser library prefix handling

### Legal Entity Types
- [Estate vs. Trust: What's the Difference?](https://smartasset.com/estate-planning/estate-vs-trust) — Entity classification
- [Is a Trust a Legal Entity?](https://www.esapllc.com/is-a-trust-a-legal-entity-2024/) — Trust entity status

---
*Pitfalls research for: ECF PDF parsing and Convey 640 CSV/Excel merge*
*Researched: 2026-03-11*

# Architecture Patterns: ECF/Convey 640 Integration

**Domain:** ECF PDF + Convey 640 CSV/Excel merge for OCC multiunit well applications
**Researched:** 2026-03-11
**Context:** Adding new extraction format to existing Extract tool

## Executive Summary

ECF/Convey 640 integration fits naturally into the existing Extract tool architecture with **minimal structural changes**. The tool-per-module pattern accommodates this as a new format mode alongside existing OCC Exhibit A parsers. Key insight: this is primarily **parser diversification**, not architectural redesign.

**Integration strategy:** Add ECF-specific parsers + CSV merge logic to `services/extract/`, extend existing format detection, modify upload endpoint to accept dual files, reuse export infrastructure with metadata mapping.

**Confidence:** HIGH — existing architecture was designed for multiple Exhibit A formats; ECF is just another format with optional CSV accelerator.

---

## Existing Extract Tool Architecture (Baseline)

### Current Component Structure

```
api/extract.py (router)
  └─► validate_upload() → PDF bytes
      └─► extract_text_from_pdf() → full text
          └─► detect_format() → ExhibitFormat enum
              ├─► TABLE_ATTENTION → parse_table_pdf()
              ├─► TABLE_SPLIT_ADDR → parse_table_pdf()
              ├─► FREE_TEXT_LIST → parse_exhibit_a()
              └─► FREE_TEXT_NUMBERED → parse_exhibit_a()
                  └─► parse_single_entry() → PartyEntry
                      ├─► parse_address()
                      ├─► parse_name()
                      └─► detect_entity_type()

POST /extract/export/{csv,excel}
  └─► to_csv() / to_excel()
      └─► _entries_to_dataframe() → mineral export format
```

**Key characteristics:**
- Format detection drives parser selection
- All parsers output uniform `PartyEntry` model
- Export layer maps `PartyEntry` → `MINERAL_EXPORT_COLUMNS`
- Frontend is format-agnostic (works with `PartyEntry[]`)

---

## Recommended Architecture for ECF/Convey 640

### High-Level Data Flow

```
PDF (required) ─────┐
                    ├──► Merge Logic ──► PartyEntry[] ──► Export
CSV/Excel (opt) ────┘
```

**Merge principle:** PDF is source of truth for respondent list. CSV provides accelerator data (metadata, partial address corrections, property info).

### Component Mapping

| Component | Exists? | Modification | New? |
|-----------|---------|--------------|------|
| **Format Detection** | ✓ | Add `ECF_EXHIBIT_A` enum value | Extension |
| **PDF Parser** | — | — | NEW: `ecf_parser.py` |
| **CSV Parser** | — | — | NEW: `convey640_parser.py` |
| **Merge Logic** | — | — | NEW: `ecf_merge_service.py` |
| **Metadata Extractor** | — | — | NEW: `ecf_metadata_extractor.py` |
| **Upload Endpoint** | ✓ | Accept optional CSV/Excel file | Modification |
| **Export Service** | ✓ | Map ECF metadata to mineral columns | Extension |
| **PartyEntry Model** | ✓ | Add optional fields (case_number, legal_description, applicant) | Extension |
| **Frontend FileUpload** | ✓ | Support dual-file upload UI | Extension |
| **Frontend Extract.tsx** | ✓ | Show ECF metadata fields | Extension |

---

## New Components (Detail)

### 1. ECF Parser (`ecf_parser.py`)

**Location:** `backend/app/services/extract/ecf_parser.py`

**Responsibility:** Parse ECF PDF Exhibit A respondent list

**Interface:**
```python
def parse_ecf_exhibit_a(pdf_bytes: bytes) -> list[PartyEntry]:
    """Parse ECF multiunit well application Exhibit A."""
```

**Logic:**
1. Extract text via `extract_text_from_pdf()` (reuse existing)
2. Locate Exhibit A section (similar to `extract_party_list()`)
3. Split into numbered entries (reuse `_split_into_entries()` pattern)
4. Parse each entry:
   - Extract entry number
   - Extract name (may be multi-line)
   - Extract address (street, city, state, ZIP)
   - Detect entity type (reuse `detect_entity_type()`)
   - Populate `PartyEntry`

**Reuse opportunities:**
- `extract_text_from_pdf()` (pdf_extractor.py)
- `parse_address()` (address_parser.py)
- `parse_name()` (name_parser.py)
- `detect_entity_type()` (patterns.py)
- `_split_into_entries()` pattern (parser.py)

**Differences from existing parsers:**
- ECF format may have different header text (e.g., "RESPONDENTS" vs "Exhibit A")
- Entry numbering may not have "U" prefix for unknown addresses
- Address layout may be more standardized (single line vs multi-line)

---

### 2. Convey 640 Parser (`convey640_parser.py`)

**Location:** `backend/app/services/extract/convey640_parser.py`

**Responsibility:** Parse Convey 640 CSV/Excel export

**Interface:**
```python
def parse_convey640(file_bytes: bytes, filename: str) -> Convey640Data:
    """Parse Convey 640 CSV or Excel file."""

@dataclass
class Convey640Data:
    """Structured data from Convey 640 export."""
    metadata: CaseMetadata
    respondents: list[Convey640Respondent]

@dataclass
class CaseMetadata:
    county: str
    legal_description: str  # STR (Section-Township-Range)
    applicant: str
    case_number: str

@dataclass
class Convey640Respondent:
    entry_number: str
    name: str
    address: str
    city: str
    state: str
    zip_code: str
```

**Logic:**
1. Detect file type (CSV vs Excel)
2. Load into pandas DataFrame
3. Extract metadata from header rows or dedicated columns
4. Parse respondent rows into structured format
5. Return `Convey640Data` object

**Reuse opportunities:**
- Pandas CSV/Excel reading (already used in Title/Proration/GHL tools)
- Address parsing/validation (shared utilities)

---

### 3. Merge Service (`ecf_merge_service.py`)

**Location:** `backend/app/services/extract/ecf_merge_service.py`

**Responsibility:** Merge PDF respondents with CSV metadata/corrections

**Interface:**
```python
def merge_ecf_data(
    pdf_entries: list[PartyEntry],
    convey_data: Convey640Data | None,
) -> tuple[list[PartyEntry], CaseMetadata | None]:
    """Merge PDF (source of truth) with CSV accelerator data."""
```

**Merge strategy:**

| Field | PDF | CSV | Merge Rule |
|-------|-----|-----|------------|
| **Respondent list** | Authoritative | Reference | PDF wins; CSV used for validation only |
| **Names** | Primary | Secondary | PDF name is primary; CSV name used if PDF is garbled |
| **Addresses** | Primary | Secondary | PDF address is primary; CSV fills gaps if PDF missing |
| **Entity type** | Detected | Not present | PDF detection only |
| **County** | Not present | Present | CSV metadata populates this |
| **Legal description** | Not present | Present | CSV metadata populates this |
| **Applicant** | Not present | Present | CSV metadata populates this |
| **Case number** | Not present | Present | CSV metadata populates this |

**Merge logic:**
1. If no CSV: return PDF entries + null metadata
2. If CSV:
   - Match PDF entries to CSV entries by entry number
   - For each PDF entry:
     - Keep PDF name (primary)
     - Keep PDF address if present; otherwise use CSV address
     - Add CSV metadata to entry (county, case_number, etc.)
   - Return merged entries + CSV metadata

**Conflict resolution:**
- PDF entry count != CSV entry count → log warning, use PDF count
- Entry number mismatch → match by position if numbers don't align
- Name/address both garbled in PDF → flag entry, use CSV as fallback

---

### 4. Metadata Extractor (`ecf_metadata_extractor.py`)

**Location:** `backend/app/services/extract/ecf_metadata_extractor.py`

**Responsibility:** Extract case metadata from ECF PDF header

**Interface:**
```python
def extract_ecf_metadata(pdf_text: str) -> CaseMetadata | None:
    """Extract case metadata from ECF PDF header (county, case number, applicant, STR)."""
```

**Logic:**
1. Search for header patterns in first page text:
   - County: "County" followed by name
   - Case number: "Cause CD No." or "Case CD"
   - Applicant: "Application of" followed by name
   - Legal description: Section-Township-Range pattern
2. Return `CaseMetadata` object or None if not found

**Reuse opportunities:**
- Regex patterns for legal descriptions (reuse from Proration tool's `legal_description_parser.py`)
- Text cleaning utilities (utils/patterns.py)

---

## Modified Components (Detail)

### 5. Format Detection (MODIFIED: `format_detector.py`)

**Changes:**
- Add `ECF_EXHIBIT_A` to `ExhibitFormat` enum
- Add detection pattern for ECF format:
  ```python
  _ECF_HEADER = re.compile(
      r"(RESPONDENTS|multiunit\s+horizontal\s+well)", re.IGNORECASE
  )
  _CASE_NUMBER = re.compile(r"Cause\s+CD\s+No\.", re.IGNORECASE)
  ```
- Update `detect_format()` to check for ECF patterns before other formats

**Integration point:** `api/extract.py` uses format hint to route to ECF parser

---

### 6. Upload Endpoint (MODIFIED: `api/extract.py`)

**Changes:**
- Accept optional second file (`csv_file: UploadFile | None`)
- Detect ECF format (either via format_hint or auto-detection)
- If ECF format:
  1. Parse PDF → `pdf_entries`
  2. Parse CSV (if provided) → `convey_data`
  3. Merge → `merged_entries, metadata`
  4. Return `ExtractionResult` with entries + metadata

**New signature:**
```python
@router.post("/upload", response_model=UploadResponse)
async def upload_pdf(
    file: Annotated[UploadFile, File(description="PDF file containing Exhibit A")],
    csv_file: Annotated[UploadFile | None, File(description="Optional Convey 640 CSV/Excel")] = None,
    request: Request,
    format_hint: Optional[str] = Query(None, description="Manual format hint"),
) -> UploadResponse:
```

**Flow:**
```python
if fmt == ExhibitFormat.ECF_EXHIBIT_A:
    pdf_entries = parse_ecf_exhibit_a(file_bytes)
    convey_data = None
    if csv_file:
        csv_bytes = await csv_file.read()
        convey_data = parse_convey640(csv_bytes, csv_file.filename)
    merged_entries, metadata = merge_ecf_data(pdf_entries, convey_data)
    # Populate name fields for individuals
    for entry in merged_entries:
        parsed = parse_name(entry.primary_name, entry.entity_type.value)
        if parsed.is_person:
            entry.first_name = parsed.first_name
            # ...
    result = ExtractionResult(
        success=True,
        entries=merged_entries,
        metadata=metadata,  # NEW field
        # ...
    )
```

---

### 7. PartyEntry Model (EXTENDED: `models/extract.py`)

**New optional fields:**
```python
class PartyEntry(BaseModel):
    # ... existing fields ...

    # ECF-specific metadata (optional, populated from Convey 640 or PDF header)
    case_number: Optional[str] = Field(None, description="OCC case number (e.g., CD 202600909)")
    applicant: Optional[str] = Field(None, description="Well applicant name")
    legal_description: Optional[str] = Field(None, description="Section-Township-Range")
    county: Optional[str] = Field(None, description="County name")
```

**Backward compatibility:** All new fields are optional; existing OCC Exhibit A exports unchanged.

---

### 8. Export Service (EXTENDED: `export_service.py`)

**Changes:**
- Map ECF metadata to mineral export columns:
  - `entry.county` → `"County"` column
  - `entry.case_number` → `"Notes/Comments"` (or dedicated field if MINERAL_EXPORT_COLUMNS updated)
  - `entry.legal_description` → `"Notes/Comments"`
  - `entry.applicant` → `"Notes/Comments"` or `"Tags"`

**Modified function:**
```python
def _entries_to_dataframe(
    entries: list[PartyEntry],
    *,
    county: str = "",
    campaign_name: str = "",
) -> pd.DataFrame:
    # ...
    row["County"] = entry.county or county  # Prefer entry-level county
    notes_parts = []
    if entry.notes:
        notes_parts.append(entry.notes)
    if entry.case_number:
        notes_parts.append(f"Case: {entry.case_number}")
    if entry.legal_description:
        notes_parts.append(f"STR: {entry.legal_description}")
    row["Notes/Comments"] = "; ".join(notes_parts)
    # ...
```

---

### 9. Frontend FileUpload (EXTENDED: `components/FileUpload.tsx`)

**Current:** Single-file upload only

**Change:** Add dual-file upload mode

**New prop:**
```typescript
interface FileUploadProps {
  // ... existing props ...
  mode?: 'single' | 'dual'  // NEW
  primaryLabel?: string     // NEW (e.g., "PDF File")
  secondaryLabel?: string   // NEW (e.g., "CSV/Excel (Optional)")
  secondaryAccept?: string  // NEW (e.g., ".csv,.xlsx")
}
```

**UI change:**
- If `mode === 'dual'`:
  - Show two separate drop zones (side by side or stacked)
  - Primary zone: PDF only
  - Secondary zone: CSV/Excel, with "(Optional)" label
  - Return both files via callback: `onFilesSelected([pdfFile, csvFile?])`

**Alternative:** Keep single-file upload, show second FileUpload conditionally in Extract.tsx (simpler, recommended).

---

### 10. Frontend Extract Page (EXTENDED: `pages/Extract.tsx`)

**Changes:**

1. **Dual-file upload UI:**
   ```typescript
   const [csvFile, setCsvFile] = useState<File | null>(null)

   // Show second FileUpload when ECF format selected
   {formatHint === 'ECF_EXHIBIT_A' && (
     <div className="mt-4">
       <FileUpload
         onFilesSelected={(files) => setCsvFile(files[0])}
         accept=".csv,.xlsx"
         multiple={false}
         label="Convey 640 Data (Optional)"
         description="Upload CSV or Excel for metadata"
       />
     </div>
   )}
   ```

2. **Upload with both files:**
   ```typescript
   const formData = new FormData()
   formData.append('file', file)  // PDF
   if (csvFile) {
     formData.append('csv_file', csvFile)
   }
   ```

3. **Display ECF metadata:**
   ```typescript
   {activeJob?.result?.metadata && (
     <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
       <h4 className="font-medium text-blue-900 mb-2">Case Information</h4>
       <dl className="grid grid-cols-2 gap-2 text-sm">
         <dt className="text-gray-600">County:</dt>
         <dd className="text-gray-900">{metadata.county}</dd>
         <dt className="text-gray-600">Case Number:</dt>
         <dd className="text-gray-900">{metadata.case_number}</dd>
         {/* ... */}
       </dl>
     </div>
   )}
   ```

4. **Format hint dropdown:**
   ```typescript
   <option value="ECF_EXHIBIT_A">ECF Multiunit Well Application</option>
   ```

---

## Component Dependency Graph

```
api/extract.py (upload endpoint)
  ├─► format_detector.py (detect ECF format)
  │   └─► NEW: ECF_EXHIBIT_A enum
  ├─► ecf_parser.py (parse PDF) [NEW]
  │   ├─► pdf_extractor.py (reuse)
  │   ├─► address_parser.py (reuse)
  │   ├─► name_parser.py (reuse)
  │   └─► patterns.py (detect_entity_type, reuse)
  ├─► convey640_parser.py (parse CSV) [NEW]
  │   └─► pandas (already used)
  ├─► ecf_merge_service.py (merge logic) [NEW]
  │   └─► models/extract.py (PartyEntry)
  └─► export_service.py (to_csv/to_excel)
      └─► MODIFIED: map ECF metadata to columns

models/extract.py
  └─► PartyEntry (EXTENDED with optional fields)

pages/Extract.tsx
  ├─► FileUpload.tsx (reuse, conditionally show second instance)
  └─► API call (formData with file + csv_file)
```

---

## Integration Points

### 1. Backend Integration Points

| Component | Integration Type | Change |
|-----------|------------------|--------|
| `format_detector.py` | Extension | Add ECF pattern detection |
| `api/extract.py` | Modification | Accept optional CSV file, route to ECF parser |
| `models/extract.py` | Extension | Add optional ECF metadata fields to PartyEntry |
| `export_service.py` | Modification | Map ECF metadata to mineral export columns |

### 2. Frontend Integration Points

| Component | Integration Type | Change |
|-----------|------------------|--------|
| `Extract.tsx` | Modification | Conditional second FileUpload, display metadata |
| `FileUpload.tsx` | Reuse | No change; just use two instances |
| `api.ts` | No change | FormData already supports multiple files |

### 3. Shared Service Integration Points

| Service | Used By | Change |
|---------|---------|--------|
| `pdf_extractor.py` | ECF parser | Reuse (no change) |
| `address_parser.py` | ECF parser | Reuse (no change) |
| `name_parser.py` | ECF parser | Reuse (no change) |
| `patterns.py` | ECF parser | Reuse `detect_entity_type()` (no change) |
| `export_utils.py` | Export service | No change (MINERAL_EXPORT_COLUMNS already defined) |

---

## Data Flow (End-to-End)

### Scenario 1: PDF Only (No CSV)

```
User uploads ECF PDF
  └─► POST /extract/upload?format_hint=ECF_EXHIBIT_A
      └─► validate_upload(file) → pdf_bytes
          └─► extract_text_from_pdf(pdf_bytes) → full_text
              └─► detect_format(full_text) → ECF_EXHIBIT_A
                  └─► parse_ecf_exhibit_a(pdf_bytes) → pdf_entries
                      └─► extract_ecf_metadata(full_text) → metadata
                          └─► merge_ecf_data(pdf_entries, None) → (entries, metadata)
                              └─► ExtractionResult(entries, metadata)
                                  └─► Frontend displays table + metadata panel

User clicks "Mineral" export
  └─► POST /extract/export/csv
      └─► to_csv(entries, county=metadata.county)
          └─► _entries_to_dataframe() → DataFrame
              └─► dataframe_to_csv_bytes() → CSV download
```

### Scenario 2: PDF + CSV (Full Merge)

```
User uploads ECF PDF + Convey 640 CSV
  └─► POST /extract/upload (FormData with file + csv_file)
      └─► validate_upload(file) → pdf_bytes
      └─► validate_upload(csv_file) → csv_bytes
          └─► parse_ecf_exhibit_a(pdf_bytes) → pdf_entries
          └─► parse_convey640(csv_bytes) → convey_data
              └─► merge_ecf_data(pdf_entries, convey_data) → (merged_entries, metadata)
                  └─► ExtractionResult(merged_entries, metadata)
                      └─► Frontend displays table + metadata panel

Export flow same as Scenario 1
```

---

## Build Order (Dependency-Aware)

### Phase 1: Backend Foundation (No Frontend Changes)

1. **Extend PartyEntry model** (`models/extract.py`)
   - Add optional fields: `case_number`, `applicant`, `legal_description`, `county`
   - No dependencies

2. **Create ECF metadata extractor** (`ecf_metadata_extractor.py`)
   - Extract county, case number, applicant, STR from PDF text
   - Dependencies: `utils/patterns.py` (reuse legal description regex from Proration)

3. **Create ECF parser** (`ecf_parser.py`)
   - Parse ECF Exhibit A respondent list
   - Dependencies: `pdf_extractor.py`, `address_parser.py`, `name_parser.py`, `patterns.py`
   - Test independently with sample ECF PDF

### Phase 2: CSV Integration

4. **Create Convey 640 parser** (`convey640_parser.py`)
   - Parse CSV/Excel into structured format
   - Dependencies: `pandas` (already available)
   - Test independently with sample Convey 640 file

5. **Create merge service** (`ecf_merge_service.py`)
   - Merge PDF entries with CSV data
   - Dependencies: `models/extract.py` (PartyEntry), `convey640_parser.py`
   - Test with sample PDF + CSV pairs

### Phase 3: API Integration

6. **Extend format detector** (`format_detector.py`)
   - Add `ECF_EXHIBIT_A` enum value
   - Add detection patterns for ECF format
   - Test with sample ECF PDFs

7. **Modify upload endpoint** (`api/extract.py`)
   - Accept optional `csv_file` parameter
   - Route ECF format to ECF parser + merge service
   - Return result with metadata
   - Test via Swagger UI (`/docs`)

### Phase 4: Export Integration

8. **Extend export service** (`export_service.py`)
   - Map ECF metadata fields to mineral export columns
   - Test export output with merged entries

### Phase 5: Frontend Integration

9. **Update Extract page** (`Extract.tsx`)
   - Add ECF format option to dropdown
   - Show conditional second FileUpload for CSV
   - Display metadata panel when present
   - Send FormData with both files

10. **Test end-to-end**
    - Upload ECF PDF only → verify respondent list + metadata
    - Upload ECF PDF + CSV → verify merged data
    - Export mineral CSV → verify metadata in output

---

## Scalability Considerations

| Concern | At 100 entries | At 1000 entries | At 10,000 entries |
|---------|----------------|-----------------|-------------------|
| **PDF parsing** | In-memory (PyMuPDF) | In-memory | May need streaming/chunking for very large PDFs |
| **CSV parsing** | Pandas in-memory | Pandas in-memory | Pandas handles well (tested up to millions of rows) |
| **Merge logic** | O(n) linear match | O(n) with dict lookup | Use dict for O(1) lookups by entry_number |
| **Frontend preview** | Full table render | Virtualized table | Virtualized table (react-window) |

**Current state:** Proration tool already handles thousands of rows via pandas; no immediate scalability issues expected.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Separate ECF Tool
**What goes wrong:** Duplicates all Extract infrastructure (upload, preview, export, AI review, enrichment)
**Why it happens:** Temptation to create clean-room implementation
**Consequences:** Code duplication, divergent UX, maintenance burden
**Prevention:** Treat ECF as format extension, not new tool

### Anti-Pattern 2: CSV as Source of Truth
**What goes wrong:** CSV OCR errors propagate to final export, undermining data quality
**Why it happens:** CSV has richer metadata, tempting to prioritize it
**Consequences:** Garbage-in-garbage-out; users lose trust in extraction
**Prevention:** PDF is authoritative for respondent list; CSV is accelerator only

### Anti-Pattern 3: Tight Coupling Between PDF and CSV Parsers
**What goes wrong:** Merge logic embedded in parsers; can't test independently
**Why it happens:** Convenience of parsing + merging in one step
**Consequences:** Hard to debug mismatches, fragile to format changes
**Prevention:** Keep parsers pure (output structured data); merge in separate service

### Anti-Pattern 4: Frontend Dual-File Upload as Atomic Unit
**What goes wrong:** Forcing both files to upload simultaneously complicates state management
**Why it happens:** Desire for single upload button
**Consequences:** Poor UX if CSV fails; can't process PDF-only mode cleanly
**Prevention:** PDF uploads independently; CSV is optional second step (or conditional second FileUpload)

---

## Validation Strategy

### Unit Testing

| Component | Test Cases |
|-----------|------------|
| `ecf_parser.py` | Parse sample ECF PDF → verify entry count, names, addresses |
| `convey640_parser.py` | Parse sample CSV → verify metadata, respondent count |
| `ecf_merge_service.py` | Merge with matching entries → verify PDF wins; Merge with mismatched counts → verify handling |
| `ecf_metadata_extractor.py` | Extract from header text → verify county, case number, STR |

### Integration Testing

| Scenario | Test |
|----------|------|
| PDF only | Upload ECF PDF → verify entries + metadata extraction |
| PDF + CSV | Upload both → verify merge logic, metadata population |
| Export | Export merged data → verify mineral format columns populated |

### End-to-End Testing

1. Upload sample ECF PDF (no CSV) → verify preview table + metadata panel
2. Upload same PDF + Convey 640 CSV → verify merged entries differ from PDF-only
3. Export to mineral CSV → verify county, case number in output
4. Verify backward compatibility: upload non-ECF PDF → existing flow works unchanged

---

## Migration Path

**Phase 1 (Backend):** Implement parsers, merge service, API changes. Test via Swagger UI. No frontend changes yet.

**Phase 2 (Frontend):** Add ECF format option + conditional CSV upload. Test with Phase 1 backend.

**Phase 3 (Polish):** Add metadata display panel, improve merge conflict logging, add format detection confidence scoring.

**Rollback plan:** ECF format is opt-in (via format_hint). If bugs found, remove ECF option from dropdown; existing users unaffected.

---

## Sources

- **Existing Extract tool codebase:** `/api/extract.py`, `/services/extract/`, `/models/extract.py`
- **Frontend Extract page:** `Extract.tsx`, `FileUpload.tsx`
- **Export utilities:** `export_utils.py`, `MINERAL_EXPORT_COLUMNS`
- **PROJECT.md:** ECF/Convey 640 requirements
- **Confidence level:** HIGH (based on direct codebase analysis)

---

*Architecture analysis: 2026-03-11*

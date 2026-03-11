# Phase 4: Frontend Integration - Research

**Researched:** 2026-03-11
**Domain:** React frontend integration for ECF extraction into existing Extract tool
**Confidence:** HIGH

## Summary

Phase 4 wires the ECF extraction backend (Phases 1-3) into the existing Extract page UI. The Extract page (`frontend/src/pages/Extract.tsx`) is a 1250-line component with format selection, file upload, results table with column visibility, filtering, row selection, editing, AI review, enrichment, and mineral export. The page already supports a `formatHint` query parameter on upload, and the existing format options in the dropdown are `FREE_TEXT_NUMBERED`, `TABLE_ATTENTION`, `TABLE_SPLIT_ADDR`, and `FREE_TEXT_LIST`.

The work is straightforward because: (1) the Extract page already has format selection UI that just needs an `ECF` option added, (2) the results table already displays the exact columns needed (name, entity_type, address, city, state, zip), (3) the mineral export button already calls `/api/extract/export/csv` with the correct payload, and (4) the backend API contract from Phases 1-3 will return data in the same `ExtractionResult` shape. The two new things are: a **dual-file upload** (PDF required + optional CSV/Excel) when ECF format is selected, and a **case metadata summary panel** displayed above the results table.

**Primary recommendation:** Extend the existing Extract page with conditional ECF mode rather than creating a new page. Add a second FileUpload component for CSV/Excel that appears conditionally, and add a metadata summary card above the results table when case metadata is present in the response.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FE-01 | Extract page supports dual-file upload (PDF required, CSV/Excel optional) when ECF format is selected | Existing FileUpload component supports configurable `accept` prop; format dropdown already exists; conditional rendering based on `formatHint` state |
| FE-02 | Results table displays respondent entries with name, entity type, address, city, state, ZIP | Existing table already renders these exact columns via the COLUMNS config and `isColVisible()` system |
| FE-03 | Case metadata (county, case number, applicant, well name) displays above the results table | New metadata panel needed; data comes from `ExtractionResult` response (new `case_metadata` field from Phase 1-3 backend) |
| FE-04 | User can export results as mineral export CSV or Excel | Existing "Mineral" export button already calls `/api/extract/export/csv`; county from metadata can pre-fill the MineralExportModal |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| React | 19.x | Component framework | Already in use |
| TypeScript | 5.x | Type safety | Already in use, strict mode |
| Tailwind CSS | 3.x | Styling | Already in use with tre-* colors |
| Lucide React | 0.x | Icons | Already in use |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Vite | 7.x | Dev server | Already configured with /api proxy |

### Alternatives Considered
None -- this is purely extending existing UI with existing libraries.

## Architecture Patterns

### Existing Extract Page Structure
```
Extract.tsx (1250 lines)
├── State: jobs[], activeJob, formatHint, filters, columns, editing, enrichment
├── Upload section: FileUpload + format dropdown
├── Jobs sidebar: Recent jobs with lazy-load entries
├── Results panel:
│   ├── Results header (filename, format, quality)
│   ├── Filter controls
│   ├── Stats row (total, flagged, selected)
│   ├── Table with column visibility
│   └── Action buttons (Enrich, AI Review, Mineral Export)
└── Modals: Edit, Enrichment Progress
```

### Pattern 1: Conditional Dual-File Upload
**What:** When `formatHint === 'ECF'`, show a second FileUpload for CSV/Excel below the PDF upload.
**When to use:** Only when ECF format is selected.
**Example:**
```typescript
// In the upload section, after the existing FileUpload:
{formatHint === 'ECF' && (
  <div className="mt-4">
    <FileUpload
      onFilesSelected={handleCsvSelected}
      accept=".csv,.xlsx,.xls"
      label="Convey 640 (Optional)"
      description="Drop CSV or Excel file here"
      multiple={false}
    />
  </div>
)}
```

### Pattern 2: Case Metadata Summary Panel
**What:** A summary card showing county, case number, applicant, well name above the results table.
**When to use:** When `activeJob.result.case_metadata` exists (ECF results).
**Example:**
```typescript
// Above the results table, after the stats row:
{activeJob.result.case_metadata && (
  <div className="px-6 py-4 border-b border-gray-100 bg-blue-50/50">
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      <div>
        <p className="text-xs text-gray-500 uppercase tracking-wide">County</p>
        <p className="text-sm font-medium text-gray-900">
          {activeJob.result.case_metadata.county || '\u2014'}
        </p>
      </div>
      {/* ... case_number, applicant, well_name */}
    </div>
  </div>
)}
```

### Pattern 3: Modified Upload Handler for Dual Files
**What:** When ECF format is selected, send both PDF and optional CSV in a single FormData request.
**When to use:** ECF mode upload.
**Example:**
```typescript
const handleFilesSelected = async (files: File[]) => {
  const formData = new FormData()
  formData.append('file', files[0])  // PDF
  if (formatHint === 'ECF' && csvFile) {
    formData.append('csv_file', csvFile)  // Optional CSV
  }
  const uploadUrl = `${API_BASE}/extract/upload?format_hint=${formatHint}`
  // ... rest of fetch
}
```

### Pattern 4: Auto-Populate Export Modal with Metadata
**What:** When case metadata includes county, pre-fill the MineralExportModal county field.
**When to use:** ECF results with metadata.
**Example:**
```typescript
<MineralExportModal
  isOpen={showExportModal}
  onClose={() => setShowExportModal(false)}
  onExport={handleExport}
  initialCounty={activeJob?.result?.case_metadata?.county || ''}
/>
```

### Anti-Patterns to Avoid
- **Creating a separate ECF page:** The Extract page already has format detection and all the infrastructure. Adding a new page duplicates routing, job history, column visibility, filters, and export logic.
- **Rewriting the upload handler:** The existing handler works. Just add conditional FormData fields for the CSV when in ECF mode.
- **Using DataTable component for ECF results:** The Extract page uses a custom inline table (not the DataTable component) because it needs checkbox selection, inline editing, column visibility toggling, and row-level actions. Continue using the existing inline table.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| File upload UI | Custom drag-drop | Existing `FileUpload` component | Already handles drag-drop, validation, file list display |
| Export dialog | Custom form | Existing `MineralExportModal` component | Already has county and campaign name fields |
| Column visibility | New column system | Existing `COLUMNS` + `visibleColumns` state | Already persisted in localStorage per user |
| Format selection | New UI control | Existing `<select>` dropdown in upload section | Just add one more `<option>` |

**Key insight:** The Extract page already has 90% of what Phase 4 needs. The new work is (1) a second FileUpload that appears conditionally, (2) a metadata panel, and (3) wiring the CSV file into the upload request.

## Common Pitfalls

### Pitfall 1: FormData with Two Files
**What goes wrong:** Trying to send the CSV as a separate request or as JSON alongside the PDF.
**Why it happens:** The existing upload uses `FormData.append('file', file)` for a single file.
**How to avoid:** Use `FormData.append('csv_file', csvFile)` for the second file in the same request. The backend (Phase 3) will accept both `file` (PDF, required) and `csv_file` (CSV/Excel, optional) as `UploadFile` parameters.
**Warning signs:** 422 validation errors from FastAPI if field names don't match.

### Pitfall 2: FileUpload Component State Accumulation
**What goes wrong:** The FileUpload component keeps an internal `uploadedFiles` array that grows with each selection. When switching format away from ECF, the CSV file reference may persist.
**Why it happens:** FileUpload manages its own state independently.
**How to avoid:** Clear the CSV file state when `formatHint` changes away from `ECF`. Use a separate state variable `csvFile` that resets on format change.
**Warning signs:** A stale CSV file being sent with a non-ECF upload.

### Pitfall 3: Response Shape Assumption
**What goes wrong:** Assuming the backend response shape is identical to existing Extract responses.
**Why it happens:** Phase 1-3 will add `case_metadata` to the `ExtractionResult` model.
**How to avoid:** Add an optional `case_metadata` field to the frontend `ExtractionResult` interface. Use optional chaining (`activeJob.result?.case_metadata?.county`) everywhere.
**Warning signs:** TypeScript errors or runtime undefined access.

### Pitfall 4: Mineral Export Missing County
**What goes wrong:** User clicks Mineral export but the county field from case metadata doesn't flow to the export request.
**Why it happens:** The current `handleExport` takes county as a parameter from the MineralExportModal, but doesn't auto-populate from metadata.
**How to avoid:** Pass `activeJob.result.case_metadata?.county` as `initialCounty` to MineralExportModal.
**Warning signs:** Empty county in exported CSV despite it being visible in the metadata panel.

### Pitfall 5: Large Component Gets Unwieldy
**What goes wrong:** Extract.tsx is already 1250 lines. Adding ECF conditional logic bloats it further.
**Why it happens:** All tool logic is in a single component.
**How to avoid:** Extract the ECF-specific upload section into a small helper component (e.g., `EcfUploadSection`) if the diff exceeds ~100 new lines. But keep state management in the parent to avoid prop-drilling complexity.
**Warning signs:** Functions and JSX becoming hard to follow in a single file.

## Code Examples

### Frontend Interface Extensions (TypeScript)
```typescript
// Add to ExtractionResult interface
interface CaseMetadata {
  county?: string
  case_number?: string
  applicant?: string
  well_name?: string
  legal_description?: string
}

interface ExtractionResult {
  // ... existing fields ...
  case_metadata?: CaseMetadata  // NEW: from ECF parsing
  merge_warnings?: string[]     // NEW: from merge service
}
```

### Format Dropdown Extension
```typescript
// Add ECF to the existing format select options:
<option value="ECF">ECF Filing (Convey 640)</option>
```

### Dual Upload State Management
```typescript
// New state for CSV file:
const [csvFile, setCsvFile] = useState<File | null>(null)

// Clear CSV when format changes:
useEffect(() => {
  if (formatHint !== 'ECF') {
    setCsvFile(null)
  }
}, [formatHint])

// Modified upload to include CSV:
const formData = new FormData()
formData.append('file', file)
if (formatHint === 'ECF' && csvFile) {
  formData.append('csv_file', csvFile)
}
```

### Metadata Summary Panel
```typescript
// Render between stats and table when metadata exists
{activeJob.result?.case_metadata && (
  <div className="px-6 py-4 border-b border-gray-100">
    <h4 className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-3">
      Case Information
    </h4>
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {[
        { label: 'County', value: activeJob.result.case_metadata.county },
        { label: 'Case Number', value: activeJob.result.case_metadata.case_number },
        { label: 'Applicant', value: activeJob.result.case_metadata.applicant },
        { label: 'Well Name', value: activeJob.result.case_metadata.well_name },
      ].map(({ label, value }) => (
        <div key={label}>
          <p className="text-xs text-gray-500">{label}</p>
          <p className="text-sm font-medium text-gray-900">{value || '\u2014'}</p>
        </div>
      ))}
    </div>
  </div>
)}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Separate page per format | Single Extract page with format dropdown | Existing architecture | All formats share table, filters, export |
| Manual county entry on export | Auto-populate from case metadata | Phase 4 | Fewer clicks for ECF workflow |

**No deprecated/outdated approaches relevant here.** This is straightforward React feature work building on established patterns.

## Open Questions

1. **Backend API contract for dual-file upload**
   - What we know: Phase 3 will create the merge endpoint. The existing `/api/extract/upload` accepts one `UploadFile`.
   - What's unclear: Whether Phase 3 modifies the existing `/upload` endpoint to accept an optional second file, or creates a new endpoint like `/upload-ecf`.
   - Recommendation: Assume the existing `/upload` endpoint is extended with an optional `csv_file: UploadFile = File(None)` parameter. If Phase 3 creates a separate endpoint, the frontend just changes the URL. Either way the FormData approach works.

2. **ExtractionResult response shape for ECF**
   - What we know: Phases 1-3 will return parsed entries in the `ExtractionResult` model. The entries use the existing `PartyEntry` schema.
   - What's unclear: Exact shape of `case_metadata` in the response, and whether `merge_warnings` is a separate field or embedded in `format_warning`.
   - Recommendation: Define the frontend `CaseMetadata` interface with optional fields. Adapt when the backend implementation is finalized.

3. **Format hint value for ECF**
   - What we know: Phase 1 adds ECF to the `ExhibitFormat` enum in `format_detector.py`.
   - What's unclear: Whether the enum value will be `ECF`, `ECF_FILING`, or something else.
   - Recommendation: Use `ECF` as the format hint value. This aligns with the naming pattern in `ExhibitFormat` (short, descriptive).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | No frontend test framework configured |
| Config file | None |
| Quick run command | `npx tsc --noEmit` (type check only) |
| Full suite command | `npx tsc --noEmit && npx eslint src/` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FE-01 | Dual-file upload appears when ECF selected | manual-only | N/A -- no frontend test framework | N/A |
| FE-02 | Results table shows correct columns | manual-only | N/A | N/A |
| FE-03 | Metadata panel displays above results | manual-only | N/A | N/A |
| FE-04 | Mineral export works with ECF data | manual-only | N/A | N/A |

**Justification for manual-only:** The project has no frontend test framework (confirmed in CLAUDE.md: "Frontend: No test suite currently configured"). Adding one is out of scope for this milestone. TypeScript compilation (`npx tsc --noEmit`) catches type errors.

### Sampling Rate
- **Per task commit:** `npx tsc --noEmit` (type check)
- **Per wave merge:** `npx tsc --noEmit && cd ../backend && python3 -m pytest -x` (full stack check)
- **Phase gate:** TypeScript compiles, ESLint passes, manual browser verification of all 4 requirements

### Wave 0 Gaps
None -- no frontend test infrastructure to create. TypeScript type checking is the automated safety net.

## Sources

### Primary (HIGH confidence)
- Direct codebase analysis of `frontend/src/pages/Extract.tsx` (1250 lines)
- Direct codebase analysis of `frontend/src/components/FileUpload.tsx` (177 lines)
- Direct codebase analysis of `frontend/src/components/MineralExportModal.tsx` (80 lines)
- Direct codebase analysis of `frontend/src/utils/api.ts` (534 lines)
- Direct codebase analysis of `backend/app/api/extract.py` (267 lines)
- Direct codebase analysis of `backend/app/models/extract.py` (110 lines)
- Direct codebase analysis of `backend/app/services/extract/export_service.py` (90 lines)
- Direct codebase analysis of `backend/app/services/shared/export_utils.py` (131 lines)
- Direct codebase analysis of `backend/app/services/extract/format_detector.py` (220 lines)

### Secondary (MEDIUM confidence)
- `.planning/REQUIREMENTS.md` -- Phase 4 requirements FE-01 through FE-04
- `.planning/ROADMAP.md` -- Phase dependencies and success criteria
- `.planning/PROJECT.md` -- Constraints and key decisions

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- existing codebase, no new libraries needed
- Architecture: HIGH -- extending existing patterns, all code inspected
- Pitfalls: HIGH -- based on direct analysis of current component structure and state management

**Research date:** 2026-03-11
**Valid until:** 2026-04-11 (stable -- frontend patterns unlikely to change)

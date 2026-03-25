# Phase 5: ECF Upload Flow Fix - Research

**Researched:** 2026-03-13
**Domain:** React frontend upload UX + FastAPI backend format detection
**Confidence:** HIGH

## Summary

This phase fixes the ECF upload flow in the Extract tool. The core problem is that the current `FileUpload` component immediately triggers processing when a file is dropped/selected (via `onFilesSelected` -> `handleFilesSelected`), leaving no opportunity for the user to attach a Convey 640 CSV or see that ECF format was detected. The backend already has full ECF parsing, CSV merging, and format detection -- the fix is entirely in the frontend upload flow.

The solution requires: (1) a lightweight backend endpoint to detect PDF format without full processing, (2) frontend state machine changes to decouple file selection from processing, and (3) conditional UI that shows the CSV upload area when ECF is detected.

**Primary recommendation:** Add a `/api/extract/detect-format` endpoint that accepts a PDF and returns the detected format. Restructure the frontend `handleFilesSelected` to only stage the file (not process it), call the detect endpoint, auto-set `formatHint` to `ECF` when detected, show the CSV upload area, and require an explicit "Process" button click to trigger the actual `/api/extract/upload` call.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ECF-01 | Auto-detect ECF format and select it in dropdown | New `/detect-format` endpoint + frontend state update on file stage |
| ECF-02 | Show Convey 640 CSV upload after ECF detection | Conditional render already exists (`formatHint === 'ECF'`), just needs auto-trigger |
| ECF-03 | No auto-processing on file upload; wait for Process click | Decouple `onFilesSelected` from `handleFilesSelected`; add explicit Process button |
| ECF-04 | Merged results show PDF-corrected data with CSV head-start | Already works in backend `merge_service.py`; just needs both files sent together |
</phase_requirements>

## Standard Stack

### Core (already in project -- no new dependencies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| React | 19.x | Frontend SPA | Already in use |
| FastAPI | 0.x | Backend API | Already in use |
| PyMuPDF | - | PDF text extraction | Already used in `pdf_extractor.py` |

### Supporting (already in project)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Lucide React | 0.x | Icons (Play, Upload) | Process button icon |
| Tailwind CSS | 3.x | Styling | All UI changes |

### Alternatives Considered

None -- this is a UX fix within the existing stack. No new libraries needed.

## Architecture Patterns

### Current Flow (broken)

```
User drops PDF -> FileUpload.onFilesSelected fires
  -> handleFilesSelected immediately calls /api/extract/upload
  -> Processing starts, no chance to add CSV or see format
```

### Target Flow (fixed)

```
User drops PDF -> onFilesSelected stages file in state (NO processing)
  -> Frontend calls /api/extract/detect-format with PDF
  -> If ECF detected: formatHint set to "ECF", CSV upload area appears
  -> User optionally attaches Convey 640 CSV
  -> User clicks "Process" button
  -> handleFilesSelected called with staged PDF + optional CSV
  -> /api/extract/upload called with both files
```

### Pattern 1: Staged Upload with Deferred Processing

**What:** Decouple file selection from file processing by introducing a "staged file" state.

**When to use:** When the upload flow needs user confirmation or additional inputs before processing.

**Implementation approach:**

```typescript
// New state: staged PDF file (not yet processed)
const [stagedFile, setStagedFile] = useState<File | null>(null)
const [isDetecting, setIsDetecting] = useState(false)

// FileUpload.onFilesSelected now just stages the file
const handleFileStaged = async (files: File[]) => {
  if (files.length === 0) return
  const file = files[0]
  setStagedFile(file)
  setError(null)

  // Auto-detect format
  setIsDetecting(true)
  try {
    const formData = new FormData()
    formData.append('file', file)
    const headers = await authHeaders()
    const response = await fetch(`${API_BASE}/extract/detect-format`, {
      method: 'POST',
      headers,
      body: formData,
    })
    if (response.ok) {
      const data = await response.json()
      if (data.format) {
        setFormatHint(data.format) // auto-selects ECF in dropdown
      }
    }
  } catch { /* detection failed, user can still manually select */ }
  finally { setIsDetecting(false) }
}

// Process button handler -- does what handleFilesSelected does today
const handleProcess = () => {
  if (!stagedFile) return
  handleFilesSelected([stagedFile]) // existing logic
}
```

### Pattern 2: Lightweight Format Detection Endpoint

**What:** A new backend endpoint that extracts just enough text from the PDF to detect the format, without running the full parser pipeline.

**Implementation approach:**

```python
@router.post("/detect-format")
async def detect_format_endpoint(
    file: Annotated[UploadFile, File(description="PDF to detect format")],
    request: Request,
) -> dict:
    """Detect the format of an uploaded PDF without full extraction."""
    file_bytes = await validate_upload(file, allowed_extensions=[".pdf"])
    full_text = extract_text_from_pdf(file_bytes)
    if not full_text or len(full_text.strip()) < 50:
        return {"format": None, "error": "Could not extract text"}
    fmt = detect_format(full_text, file_bytes)
    return {"format": fmt.value, "format_label": _FORMAT_LABELS.get(fmt, fmt.value)}
```

### Pattern 3: Process Button Visibility

**What:** Show a prominent "Process" button after a file is staged, disabled while detecting format.

**When to use:** Always when a staged file exists.

```typescript
{stagedFile && (
  <div className="mt-4 flex items-center gap-3">
    <button
      onClick={handleProcess}
      disabled={isProcessing || isDetecting}
      className="flex items-center gap-2 px-4 py-2 bg-tre-teal text-white rounded-lg
                 hover:bg-tre-teal/90 disabled:opacity-50 disabled:cursor-not-allowed
                 transition-colors"
    >
      {isProcessing ? (
        <>
          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
          Processing...
        </>
      ) : (
        <>
          <Play className="w-4 h-4" />
          Process
        </>
      )}
    </button>
    <span className="text-sm text-gray-500">
      {stagedFile.name}
      {formatHint === 'ECF' && ' (ECF Filing detected)'}
    </span>
  </div>
)}
```

### Anti-Patterns to Avoid

- **Reading entire PDF on frontend for format detection:** Never try to parse PDF content in the browser. Always use the backend `detect_format` function which has access to PyMuPDF.
- **Auto-processing after CSV attach:** The CSV upload should not trigger processing either. Only the explicit Process button should start extraction.
- **Duplicating FileUpload state:** Don't try to externally control the `FileUpload` component's internal `uploadedFiles` state. Instead manage staged files in the parent (`Extract.tsx`) and use `FileUpload` as a pure trigger.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Format detection | Client-side PDF parsing | Backend `/detect-format` endpoint | PyMuPDF + regex patterns already exist server-side |
| File staging | Custom drag-drop from scratch | Existing `FileUpload` component + parent state | Component already handles validation and UX |

## Common Pitfalls

### Pitfall 1: Double PDF Upload

**What goes wrong:** The PDF gets uploaded twice -- once for format detection, once for processing.
**Why it happens:** If the detect-format endpoint stores the file and the upload endpoint re-reads it.
**How to avoid:** The detect-format endpoint is read-only (no persistence). The staged `File` object in React state is sent again for the actual `/upload` call. This is acceptable because PDF files for this tool are small (< 5MB typically). Alternatively, detect-format could return a temporary file ID, but that adds complexity not warranted here.
**Warning signs:** Slow upload experience, duplicate Firestore jobs.

### Pitfall 2: FileUpload Component Fires onFilesSelected Immediately

**What goes wrong:** The `FileUpload` component calls `onFilesSelected` on drop/select, which currently maps directly to processing.
**Why it happens:** The component was designed for immediate processing workflows.
**How to avoid:** Change the callback wired to `FileUpload.onFilesSelected` from `handleFilesSelected` to a new `handleFileStaged` function that only stores the file in state.

### Pitfall 3: CSV File Lost on Re-render

**What goes wrong:** The `csvFile` state gets cleared when `formatHint` changes.
**Why it happens:** The existing `useEffect` clears `csvFile` when `formatHint !== 'ECF'` (line 244-248 in Extract.tsx). If format detection sets `formatHint` to `ECF` and then something re-triggers, the CSV could be lost.
**How to avoid:** The existing effect is correct (clears CSV when switching away from ECF). Just ensure the format detection sets `formatHint` to `ECF` once and the user doesn't accidentally change it.

### Pitfall 4: Panel Collapsed vs Non-collapsed Upload Areas

**What goes wrong:** The Extract page renders the upload UI in TWO places -- once when `panelCollapsed` is true, once when false. Both need the same staged-upload logic.
**Why it happens:** The page has two layout modes for the upload section.
**How to avoid:** Extract the upload + staged file + process button into a shared component or inline fragment rendered in both places. Do NOT duplicate the logic.

## Code Examples

### Current handleFilesSelected (to be renamed/refactored)

```typescript
// Source: frontend/src/pages/Extract.tsx lines 362-439
// This currently fires on FileUpload.onFilesSelected
// After fix: this becomes handleProcess, called only on Process button click
const handleFilesSelected = async (files: File[]) => {
  if (files.length === 0) return
  const file = files[0]
  setIsProcessing(true)
  // ... builds FormData, calls /api/extract/upload
}
```

### Existing Format Detection (backend, already works)

```python
# Source: backend/app/services/extract/format_detector.py lines 65-110
# ECF detection uses regex: MULTIUNIT HORIZONTAL WELL + CAUSE CD pattern
def detect_format(text: str, file_bytes: bytes | None = None) -> ExhibitFormat:
    # ... checks patterns ...
    if _ECF_MULTIUNIT.search(text) and _ECF_CAUSE_CD.search(text):
        return ExhibitFormat.ECF
```

### Existing CSV Merge (backend, already works)

```python
# Source: backend/app/api/extract.py lines 101-119
# CSV merging already happens when csv_file is provided alongside ECF format
elif fmt == ExhibitFormat.ECF:
    ecf_result = parse_ecf_filing(full_text)
    if csv_file:
        csv_bytes = await csv_file.read()
        csv_result = parse_convey640(csv_bytes, csv_file.filename)
        merge_result = merge_entries(ecf_result, csv_result)
```

### Existing Conditional CSV Upload UI (already works, just needs auto-trigger)

```typescript
// Source: frontend/src/pages/Extract.tsx lines 665-675 and 711-721
// This already shows when formatHint === 'ECF'
{formatHint === 'ECF' && (
  <div className="mt-4">
    <FileUpload
      onFilesSelected={(files) => setCsvFile(files[0] || null)}
      accept=".csv,.xlsx,.xls"
      multiple={false}
      label="Convey 640 (Optional)"
      description="Drop CSV or Excel file here, or click to select"
    />
  </div>
)}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Upload triggers immediate processing | Staged upload with explicit Process button | This phase | Users can review format + add CSV before processing |

**No deprecated APIs or libraries involved.** All changes are UX flow restructuring within the existing stack.

## Open Questions

1. **Should the Process button replace or supplement the FileUpload's drag-drop behavior?**
   - What we know: FileUpload calls `onFilesSelected` immediately on drop. We need to intercept this.
   - What's unclear: Should we modify `FileUpload` component itself, or just change the callback at the Extract page level?
   - Recommendation: Change only at the Extract page level (pass a staging callback instead of the processing callback). Don't modify the shared `FileUpload` component since other tools (Title, Revenue, etc.) rely on immediate processing behavior.

2. **Should format detection be a separate HTTP round-trip or client-side heuristic?**
   - What we know: Format detection requires PDF text extraction (PyMuPDF), which only runs server-side.
   - What's unclear: Whether the extra network round-trip is noticeable.
   - Recommendation: Use a separate `/detect-format` endpoint. The PDF text extraction is fast (< 1 second for typical ECF filings). The UX benefit (correct format auto-selected) outweighs the latency.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 7.x + pytest-asyncio |
| Config file | `backend/pytest.ini` |
| Quick run command | `cd backend && python3 -m pytest tests/ -x -q` |
| Full suite command | `cd backend && python3 -m pytest tests/ -v` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ECF-01 | detect-format endpoint returns "ECF" for ECF PDFs | unit | `cd backend && python3 -m pytest tests/test_detect_format.py -x` | No -- Wave 0 |
| ECF-02 | CSV upload area appears when formatHint is ECF | manual-only | Visual inspection (no frontend test suite) | N/A |
| ECF-03 | Upload endpoint not called until Process clicked | manual-only | Visual inspection (no frontend test suite) | N/A |
| ECF-04 | Merged output includes CSV head-start fields + PDF corrections | unit | `cd backend && python3 -m pytest tests/test_merge_service.py -x` | Yes |

### Sampling Rate
- **Per task commit:** `cd backend && python3 -m pytest tests/ -x -q`
- **Per wave merge:** `cd backend && python3 -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_detect_format.py` -- covers ECF-01 (new detect-format endpoint returns correct format for ECF PDFs)
- [ ] No frontend test infrastructure exists (DEFER-02) -- ECF-02 and ECF-03 verified via manual testing only

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection: `frontend/src/pages/Extract.tsx` (1400+ lines, full upload flow)
- Direct codebase inspection: `backend/app/api/extract.py` (upload endpoint with ECF branch)
- Direct codebase inspection: `backend/app/services/extract/format_detector.py` (format detection logic)
- Direct codebase inspection: `backend/app/services/extract/merge_service.py` (PDF+CSV merge)
- Direct codebase inspection: `frontend/src/components/FileUpload.tsx` (shared upload component)

### Secondary (MEDIUM confidence)
- None needed -- all findings based on direct code analysis

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - no new libraries, all existing code
- Architecture: HIGH - clear problem (immediate processing on upload), clear solution (staged upload + detect endpoint)
- Pitfalls: HIGH - identified from direct code reading (dual upload areas, useEffect CSV clearing)

**Research date:** 2026-03-13
**Valid until:** 2026-04-13 (stable -- internal codebase, no external dependency changes expected)

---
phase: 05-ecf-upload-flow-fix
verified: 2026-03-13T13:20:17Z
status: human_needed
score: 6/6 must-haves verified
human_verification:
  - test: "Upload a non-ECF PDF via the Extract tool"
    expected: "File is staged (filename + Process button appear), no extraction runs, format dropdown updates to detected format"
    why_human: "Cannot verify absence of auto-processing or correct UI render without browser"
  - test: "Upload an ECF PDF via the Extract tool"
    expected: "Format dropdown auto-switches to ECF Filing, Convey 640 CSV upload area appears automatically"
    why_human: "Cannot verify ECF auto-detection triggers correct UI conditional in browser"
  - test: "Click the Process button after staging a PDF"
    expected: "Extraction runs and results appear in the table"
    why_human: "End-to-end extraction flow requires running app with auth"
  - test: "Upload both an ECF PDF and a Convey 640 CSV, then click Process"
    expected: "Merged results appear with CSV head-start fields filled in and PDF corrections applied"
    why_human: "Merge correctness requires real ECF + Convey 640 test files and visual result inspection"
  - test: "Toggle panel to collapsed mode, repeat upload and Process flow"
    expected: "Identical behavior in collapsed layout (same staged file, Process button, ECF CSV area)"
    why_human: "Both layout branches render from same state but visual parity needs browser confirmation"
---

# Phase 5: ECF Upload Flow Fix — Verification Report

**Phase Goal:** Users can upload ECF filings with the correct format pre-selected and optional CSV added before processing begins
**Verified:** 2026-03-13T13:20:17Z
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (from ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | When user uploads ECF PDF, format dropdown switches to "ECF Filing" without user intervention | VERIFIED | `handleFileStaged` calls `/extract/detect-format`; on `data.format` truthy, calls `setFormatHint(data.format)`. ECF text returns `format="ECF"`, confirmed by 3 passing backend tests. |
| 2 | After ECF detection, Convey 640 CSV upload area appears automatically before processing | VERIFIED | Both panelCollapsed (line 709) and non-collapsed (line 789) sections render `<FileUpload>` for CSV when `formatHint === 'ECF'`. Detection sets formatHint, which conditionally shows the area. |
| 3 | No processing occurs until user clicks Process button (uploading alone does not trigger extraction) | VERIFIED | `FileUpload.onFilesSelected` is wired to `handleFileStaged` (not `handleFilesSelected`) in both layouts (lines 689, 769). `handleFileStaged` only stages file and calls detect-format. `handleFilesSelected` (the extractor) is only called by `handleProcess`. |
| 4 | When both PDF and CSV are provided, merged results show PDF-corrected data with CSV head-start fields | VERIFIED | `handleFilesSelected` appends `csv_file` to FormData when `formatHint === 'ECF' && csvFile` (lines 422-424). Backend `/api/extract/upload` calls `merge_entries(ecf_result, csv_result)` with substantive `merge_service.py` (non-stub). |
| 5 | POST /api/extract/detect-format returns {format: "ECF"} for ECF PDFs | VERIFIED | Endpoint at `extract.py:41`, calls `detect_format()` on extracted text. 3 backend tests all pass: ECF, FREE_TEXT_NUMBERED, unreadable PDF. |
| 6 | POST /api/extract/detect-format returns {format: null, error: ...} for unreadable PDFs | VERIFIED | Endpoint returns `{"format": None, "error": "Could not extract text"}` when `len(full_text.strip()) < 50`. Test `test_detect_format_unreadable` confirms. |

**Score:** 6/6 truths verified (automated)

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/api/extract.py` | detect-format endpoint | VERIFIED | `@router.post("/detect-format")` at line 41, placed before `/upload` route. Calls `detect_format()` and returns `{format, format_label}`. |
| `backend/tests/test_detect_format.py` | Unit tests (min 30 lines) | VERIFIED | 87 lines. 3 async tests using `authenticated_client` fixture with `patch` on `extract_text_from_pdf`. All 3 pass. |
| `frontend/src/pages/Extract.tsx` | Staged upload with Process button | VERIFIED | `stagedFile` state (line 122), `isDetecting` state (line 123), `handleFileStaged` (line 364), `handleProcess` (line 394), `handleClearStaged` (line 399). Both layout branches have Process button and ECF CSV conditional. |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `backend/app/api/extract.py` | `backend/app/services/extract/format_detector.py` | `detect_format()` call | WIRED | `detect_format` imported at line 23, called at line 51 inside endpoint |
| `frontend/src/pages/Extract.tsx` | `/api/extract/detect-format` | `fetch` call in `handleFileStaged` | WIRED | `fetch(\`${API_BASE}/extract/detect-format\`, ...)` at line 376, response parsed and `setFormatHint(data.format)` called |
| `frontend/src/pages/Extract.tsx` | `/api/extract/upload` | `fetch` call in `handleFilesSelected` | WIRED | `fetch(uploadUrl, ...)` at line 428 where `uploadUrl` is built from `/extract/upload` at line 426 |
| `backend/app/api/extract.py` | `merge_service.merge_entries()` | called when `csv_file` provided for ECF | WIRED | Lines 134-141: imports and calls `parse_convey640` + `merge_entries` when `fmt == ECF and csv_file`. Return value used directly as `entries`. |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| ECF-01 | 05-01-PLAN.md | ECF format auto-detected and format dropdown auto-selects ECF | SATISFIED | `/detect-format` endpoint returns `format="ECF"`; frontend `setFormatHint(data.format)` wires auto-selection |
| ECF-02 | 05-02-PLAN.md | After ECF detection, Convey 640 CSV upload area opens automatically before processing | SATISFIED | `{formatHint === 'ECF' && <FileUpload ...>}` in both layout branches; detection sets `formatHint` |
| ECF-03 | 05-02-PLAN.md | Processing waits for explicit "Process" button click | SATISFIED | `FileUpload.onFilesSelected → handleFileStaged` (stages only); `Process` button → `handleProcess → handleFilesSelected` (extracts) |
| ECF-04 | 05-02-PLAN.md | CSV provides head-start data; PDF fills remaining fields (PDF authoritative) | SATISFIED | `merge_service.py` implements PDF-authoritative merge with `_FILL_BLANK_FIELDS` pattern; wired in `/upload` endpoint |

**Coverage:** 4/4 requirements satisfied. No orphaned requirements — all phase 5 requirements (ECF-01 through ECF-04) are claimed by plans 05-01 and 05-02.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None | — | — | — | — |

No stubs, placeholders, TODO comments, or empty implementations found in modified files.

---

### Human Verification Required

The automated checks pass completely. The following items require browser testing because they involve visual rendering, auth-gated flows, or end-to-end behavior that cannot be verified programmatically:

#### 1. Non-ECF Staged Upload

**Test:** Run `make dev`, open http://localhost:5173/extract, upload any non-ECF PDF.
**Expected:** File name and Process button appear immediately. No extraction starts. Format dropdown updates to detected format (e.g., "Free Text (Default)").
**Why human:** Cannot verify absence of auto-processing or dropdown state change without browser execution.

#### 2. ECF Format Auto-Detection in Browser

**Test:** Upload an ECF PDF (file matching "MULTIUNIT HORIZONTAL WELL" + "CAUSE CD" pattern).
**Expected:** Format dropdown auto-changes to "ECF Filing (Convey 640)". Convey 640 CSV upload area appears below the format selector without any user interaction.
**Why human:** UI conditional rendering correctness requires visual inspection in browser.

#### 3. Process Button Triggers Extraction

**Test:** With a PDF staged, click the Process button.
**Expected:** Button shows "Processing..." spinner, then results table populates with extracted entries.
**Why human:** Requires running app with Firebase auth and PDF extraction pipeline active.

#### 4. ECF + CSV Merged Results (ECF-04)

**Test:** Stage an ECF PDF, attach a Convey 640 CSV, click Process.
**Expected:** Results show entries with CSV head-start fields (e.g., pre-filled addresses from CSV) and PDF corrections applied. Merge warnings (if any) appear in results.
**Why human:** Merge correctness requires real test files and comparing CSV vs merged output visually.

#### 5. Both Panel Layouts Behave Identically

**Test:** Toggle the "Hide Panel" / "Show Panel" button and repeat the staged upload + ECF detection flow.
**Expected:** Collapsed layout shows same staged file display, Process button, and ECF CSV area as the expanded layout.
**Why human:** Both branches are wired to identical state and handlers, but visual parity needs browser confirmation.

---

### Summary

All 6 automated truths verified. All 4 requirements (ECF-01 through ECF-04) have concrete implementation evidence. No stubs or orphaned artifacts found.

**Backend (ECF-01):** The `/api/extract/detect-format` endpoint is fully implemented and tested (3 passing tests). It correctly calls `detect_format()`, returns `format="ECF"` for ECF-pattern text, non-ECF formats for other text, and `format=null` with error for unreadable PDFs.

**Frontend (ECF-02, ECF-03, ECF-04):** `Extract.tsx` has been refactored with the staged upload pattern. File drop → stage → detect → user confirms → process. Both the panelCollapsed and non-collapsed layouts use `handleFileStaged` (not immediate processing). The Process button gates extraction. The ECF CSV upload area is conditionally shown when `formatHint === 'ECF'`. The CSV is appended to the upload FormData when present, and the backend merge pipeline is wired end-to-end.

**TypeScript compiles cleanly.** Backend tests all pass.

Remaining uncertainty is visual/interactive — requires a brief browser smoke test on the deployed or local app.

---

_Verified: 2026-03-13T13:20:17Z_
_Verifier: Claude (gsd-verifier)_

---
phase: 7
slug: enrichment-ui-preview-state
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-03-13
---

# Phase 7 -- Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (backend) + TypeScript compiler (frontend) |
| **Config file** | `backend/pytest.ini` / `frontend/tsconfig.app.json` |
| **Quick run command** | `cd backend && python3 -m pytest tests/ -x -q` |
| **Full suite command** | `cd backend && python3 -m pytest tests/ -v && cd ../frontend && npx tsc --noEmit` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python3 -m pytest tests/ -x -q`
- **After every plan wave:** Run `cd backend && python3 -m pytest tests/ -v && cd ../frontend && npx tsc --noEmit`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 07-01-01 | 01 | 1 | ENRICH-01 | unit | `pytest tests/test_features_status.py -x -q` | Wave 0 | pending |
| 07-01-02 | 01 | 1 | ENRICH-02 | unit | `pytest tests/test_features_status.py -x -q` | Wave 0 | pending |
| 07-02-01 | 02 | 1 | ENRICH-07 | tsc | `npx tsc --noEmit` | yes | pending |
| 07-02-02 | 02 | 1 | ENRICH-08 | tsc | `npx tsc --noEmit` | yes | pending |
| 07-03-01 | 03 | 2 | ENRICH-09 | tsc+manual | `npx tsc --noEmit` | yes | pending |
| 07-03-02 | 03 | 2 | ENRICH-01,02 | tsc+manual | `npx tsc --noEmit` | yes | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_features_status.py` -- stubs for ENRICH-01, ENRICH-02 (feature flag endpoint)
- [ ] Frontend TypeScript compilation serves as automated check for component structure

*Existing pytest infrastructure covers backend. Frontend relies on tsc --noEmit.*

---

## ENRICH-09 Backend Test Deferral

`tests/test_export_preview.py` (identified in RESEARCH.md Validation Architecture) is **deferred to Phase 8**. Rationale: In Phase 7, export handlers are rewired to send `preview.entriesToExport` (frontend-derived) to the same backend export endpoints. The backend export endpoints themselves are unchanged -- they accept an entries array and produce CSV/Excel. The meaningful backend test for ENRICH-09 is verifying that export endpoints correctly handle entries with enrichment fields added (e.g., phone, email from PDL), which only becomes testable once Phase 8 wires actual enrichment data through the pipeline.

Phase 7 verification of ENRICH-09 relies on:
1. TypeScript compilation (ensures `entriesToExport` is wired to export handlers)
2. Manual checkpoint (Task 07-03-03: edit a cell, export CSV, verify edited value appears)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Buttons hidden when API keys missing | ENRICH-02 | Runtime config determines visibility | 1. Start dev without GEMINI_API_KEY 2. Verify no Clean Up button visible |
| Flagged rows sort to top | ENRICH-07 | Visual sorting in browser | 1. Flag a row via enrichment stub 2. Verify it appears at top of table |
| Inline edit reflects in export | ENRICH-09 | E2E browser interaction | 1. Edit a cell 2. Export CSV 3. Verify edited value in output |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [x] `nyquist_compliant: true` set in frontmatter
- [x] ENRICH-09 backend test deferral documented with rationale

**Approval:** pending

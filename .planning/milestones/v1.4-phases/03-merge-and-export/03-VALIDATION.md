---
phase: 3
slug: merge-and-export
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-12
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x with pytest-asyncio |
| **Config file** | backend/pytest.ini |
| **Quick run command** | `cd backend && python3 -m pytest tests/test_merge_service.py -x -v` |
| **Full suite command** | `cd backend && python3 -m pytest -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python3 -m pytest tests/test_merge_service.py -x -v`
- **After every plan wave:** Run `cd backend && python3 -m pytest -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | MRG-01 | unit | `python3 -m pytest tests/test_merge_service.py::TestMergeEntries::test_pdf_wins_contact_fields -x` | ❌ W0 | ⬜ pending |
| 03-01-02 | 01 | 1 | MRG-02 | unit | `python3 -m pytest tests/test_merge_service.py::TestMergeMetadata::test_csv_fills_pdf_gaps -x` | ❌ W0 | ⬜ pending |
| 03-01-03 | 01 | 1 | MRG-03 | unit | `python3 -m pytest tests/test_merge_service.py::TestMergeEntries::test_entry_number_matching -x` | ❌ W0 | ⬜ pending |
| 03-01-04 | 01 | 1 | MRG-04 | unit | `python3 -m pytest tests/test_merge_service.py::TestMergeWarnings -x` | ❌ W0 | ⬜ pending |
| 03-02-01 | 02 | 1 | EXP-01 | unit | `python3 -m pytest tests/test_merge_service.py::TestMergeExport::test_csv_export -x` | ❌ W0 | ⬜ pending |
| 03-02-02 | 02 | 1 | EXP-02 | unit | `python3 -m pytest tests/test_merge_service.py::TestMergeExport::test_excel_export -x` | ❌ W0 | ⬜ pending |
| 03-02-03 | 02 | 1 | EXP-03 | unit | `python3 -m pytest tests/test_merge_service.py::TestMetadataNotes -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_merge_service.py` — stubs for MRG-01 through MRG-04, EXP-01 through EXP-03
- No framework install needed (pytest already configured)
- No conftest.py changes needed (tests are self-contained)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Summary banner displays correctly in UI | MRG-04 | Visual rendering | Upload PDF+CSV, verify yellow banner shows "X of Y entries matched" |
| CSV-only entries show warning icon | MRG-04 | Visual rendering | Check yellow warning icon appears on flagged CSV-only rows |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

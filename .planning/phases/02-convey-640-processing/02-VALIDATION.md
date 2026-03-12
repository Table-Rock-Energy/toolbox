---
phase: 2
slug: convey-640-processing
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-12
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x with pytest-asyncio |
| **Config file** | `backend/pytest.ini` |
| **Quick run command** | `cd backend && python3 -m pytest tests/test_convey640_parser.py -x -v` |
| **Full suite command** | `cd backend && python3 -m pytest -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python3 -m pytest tests/test_convey640_parser.py -x -v`
- **After every plan wave:** Run `cd backend && python3 -m pytest -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | CSV-01 | unit | `cd backend && python3 -m pytest tests/test_convey640_parser.py::TestSchemaValidation -x` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 1 | CSV-02 | unit | `cd backend && python3 -m pytest tests/test_convey640_parser.py::TestNameNormalization -x` | ❌ W0 | ⬜ pending |
| 02-01-03 | 01 | 1 | CSV-03 | unit | `cd backend && python3 -m pytest tests/test_convey640_parser.py::TestPostalCodeNormalization -x` | ❌ W0 | ⬜ pending |
| 02-01-04 | 01 | 1 | CSV-04 | unit | `cd backend && python3 -m pytest tests/test_convey640_parser.py::TestMetadataExtraction -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_convey640_parser.py` — stubs for CSV-01 through CSV-04
- No framework install needed — pytest already configured
- No conftest changes needed — existing `tests/conftest.py` is sufficient

*Existing infrastructure covers framework requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Upload Excel via frontend dual-file upload | CSV-01 | Frontend integration | Upload sample .xlsx via Extract page, verify parsed rows appear |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

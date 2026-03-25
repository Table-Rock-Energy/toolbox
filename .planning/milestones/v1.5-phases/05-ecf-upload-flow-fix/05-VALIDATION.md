---
phase: 5
slug: ecf-upload-flow-fix
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-13
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x + pytest-asyncio |
| **Config file** | `backend/pytest.ini` |
| **Quick run command** | `cd backend && python3 -m pytest tests/ -x -q` |
| **Full suite command** | `cd backend && python3 -m pytest tests/ -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python3 -m pytest tests/ -x -q`
- **After every plan wave:** Run `cd backend && python3 -m pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 1 | ECF-01 | unit | `cd backend && python3 -m pytest tests/test_detect_format.py -x` | ❌ W0 | ⬜ pending |
| 05-01-02 | 01 | 1 | ECF-04 | unit | `cd backend && python3 -m pytest tests/test_merge_service.py -x` | ✅ | ⬜ pending |
| 05-02-01 | 02 | 1 | ECF-02 | manual | Visual inspection | N/A | ⬜ pending |
| 05-02-02 | 02 | 1 | ECF-03 | manual | Visual inspection | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_detect_format.py` — unit tests for new `/api/extract/detect-format` endpoint (ECF-01)
- [ ] No frontend test framework — ECF-02 and ECF-03 verified via manual testing only

*Existing `tests/test_merge_service.py` covers ECF-04.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| CSV upload area appears when ECF detected | ECF-02 | No frontend test suite | 1. Upload an ECF PDF 2. Verify format dropdown shows "ECF Filing" 3. Verify CSV upload area appears |
| No processing on file upload alone | ECF-03 | No frontend test suite | 1. Upload any PDF 2. Verify no API call to `/extract/upload` until Process clicked 3. Check network tab |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

---
phase: 11
slug: rrc-pipeline-fix
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-18
---

# Phase 11 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x + pytest-asyncio |
| **Config file** | `backend/pytest.ini` (asyncio_mode = auto) |
| **Quick run command** | `cd backend && python3 -m pytest tests/test_fetch_missing.py -x -v` |
| **Full suite command** | `cd backend && python3 -m pytest -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python3 -m pytest tests/test_fetch_missing.py -x -v`
- **After every plan wave:** Run `cd backend && python3 -m pytest -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 11-01-01 | 01 | 1 | RRC-01 | unit | `python3 -m pytest tests/test_fetch_missing.py::test_split_compound_lease_district_inheritance -x` | ❌ W0 | ⬜ pending |
| 11-01-02 | 01 | 1 | RRC-01 | unit | `python3 -m pytest tests/test_fetch_missing.py::test_compound_lease_integrated -x` | ❌ W0 | ⬜ pending |
| 11-01-03 | 01 | 1 | RRC-02 | unit | `python3 -m pytest tests/test_fetch_missing.py::test_individual_results_used_directly -x` | ✅ | ⬜ pending |
| 11-01-04 | 01 | 1 | RRC-03 | unit | `python3 -m pytest tests/test_fetch_missing.py::test_fetch_status_set_on_returned_rows -x` | ✅ | ⬜ pending |
| 11-01-05 | 01 | 1 | RRC-03 | unit | `python3 -m pytest tests/test_fetch_missing.py::test_split_lookup_status -x` | ❌ W0 | ⬜ pending |
| 11-01-06 | 01 | 1 | RRC-03 | unit | `python3 -m pytest tests/test_fetch_missing.py::test_sub_lease_results_annotation -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_fetch_missing.py` — add tests for `split_compound_lease` district inheritance (multiple formats)
- [ ] `tests/test_fetch_missing.py` — add tests for compound lease integration into fetch-missing loop
- [ ] `tests/test_fetch_missing.py` — add tests for `split_lookup` status assignment
- [ ] `tests/test_fetch_missing.py` — add tests for `sub_lease_results` annotation field populated

*Existing infrastructure covers framework/fixture needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Tooltip shows sub-lease breakdown on hover | RRC-03 | Frontend tooltip rendering requires browser interaction | Upload compound lease CSV, run fetch-missing, hover status icon |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

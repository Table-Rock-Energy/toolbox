---
phase: 6
slug: rrc-ghl-fixes
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-13
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x with pytest-asyncio |
| **Config file** | `backend/pytest.ini` |
| **Quick run command** | `cd backend && python3 -m pytest tests/test_fetch_missing.py -x -q` |
| **Full suite command** | `cd backend && python3 -m pytest tests/ -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python3 -m pytest tests/test_fetch_missing.py -x -q`
- **After every plan wave:** Run `cd backend && python3 -m pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 1 | RRC-01 | unit | `cd backend && python3 -m pytest tests/test_fetch_missing.py::test_uses_individual_results_directly -x` | ❌ W0 | ⬜ pending |
| 06-01-02 | 01 | 1 | RRC-02 | unit | `cd backend && python3 -m pytest tests/test_fetch_missing.py::test_split_compound_lease_numbers -x` | ❌ W0 | ⬜ pending |
| 06-01-03 | 01 | 1 | RRC-03 | unit | `cd backend && python3 -m pytest tests/test_fetch_missing.py::test_per_row_fetch_status -x` | ❌ W0 | ⬜ pending |
| 06-02-01 | 02 | 1 | GHL-01 | manual-only | N/A | N/A | ⬜ pending |
| 06-02-02 | 02 | 1 | GHL-02 | manual-only | Visual check in browser | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_fetch_missing.py` — stubs for RRC-01, RRC-02, RRC-03
- [ ] Mock fixtures for `fetch_individual_leases` return values and Firestore lookup functions

*Existing infrastructure covers framework setup; only test files are missing.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| SmartList not API-creatable | GHL-01 | Documentation/research verification, no code change | Confirmed in REQUIREMENTS.md Out of Scope section |
| GHL modal shows "Campaign Tag" with tooltip | GHL-02 | Visual UI change | Open GHL send modal, verify label reads "Campaign Tag" with hover tooltip explaining SmartList creation |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

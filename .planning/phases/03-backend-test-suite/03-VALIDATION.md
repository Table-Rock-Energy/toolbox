---
phase: 3
slug: backend-test-suite
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-11
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| **Config file** | `backend/pytest.ini` (asyncio_mode = auto) |
| **Quick run command** | `cd backend && python3 -m pytest -v -x` |
| **Full suite command** | `cd backend && python3 -m pytest -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python3 -m pytest -v -x`
- **After every plan wave:** Run `cd backend && python3 -m pytest -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | TEST-02 | smoke | `cd backend && python3 -m pytest tests/test_auth_enforcement.py -v` | Yes (expand) | pending |
| 03-02-01 | 02 | 1 | TEST-03 | unit | `cd backend && python3 -m pytest tests/test_extract_parser.py -v` | No — Wave 0 | pending |
| 03-02-02 | 02 | 1 | TEST-03 | unit | `cd backend && python3 -m pytest tests/test_revenue_parser.py -v` | No — Wave 0 | pending |
| 03-03-01 | 03 | 2 | TEST-01,02,03 | integration | `cd backend && python3 -m pytest -v` | N/A — CI workflow | pending |

*Status: pending · green · red · flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_extract_parser.py` — stub for TEST-03a (extract parser regression)
- [ ] `tests/test_revenue_parser.py` — stub for TEST-03b (revenue parser regression)
- [ ] `.github/workflows/test.yml` — CI test workflow (success criteria #4)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| GHL SSE progress endpoint auth | TEST-02 | Uses query-param token auth, not Bearer header | Document in test file; custom auth verification is out of scope for smoke tests |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

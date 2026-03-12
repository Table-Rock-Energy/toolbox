---
phase: 1
slug: ecf-pdf-parsing
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-12
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x + pytest-asyncio |
| **Config file** | `backend/pytest.ini` (if exists) or inline in `pyproject.toml` |
| **Quick run command** | `cd backend && python3 -m pytest tests/test_ecf_parser.py -x -v` |
| **Full suite command** | `make test` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python3 -m pytest tests/test_ecf_parser.py -x -v`
- **After every plan wave:** Run `make test`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 1 | ECF-05 | unit | `python3 -m pytest tests/test_ecf_parser.py::TestECFFormatRouting -x` | ❌ W0 | ⬜ pending |
| 01-01-02 | 01 | 1 | ECF-03 | unit | `python3 -m pytest tests/test_ecf_parser.py::TestECFMetadata -x` | ❌ W0 | ⬜ pending |
| 01-01-03 | 01 | 1 | ECF-01, ECF-02 | unit | `python3 -m pytest tests/test_ecf_parser.py::TestECFParseEntries -x` | ❌ W0 | ⬜ pending |
| 01-02-01 | 02 | 1 | ECF-04 | unit | `python3 -m pytest tests/test_ecf_parser.py::TestECFEntityTypes -x` | ❌ W0 | ⬜ pending |
| 01-02-02 | 02 | 1 | ECF-01 | unit | `python3 -m pytest tests/test_ecf_parser.py::TestECFMultiLine -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_ecf_parser.py` — stubs for ECF-01 through ECF-05 with inline text fixtures
- [ ] No new fixtures needed — ECF test fixtures are inline text strings (same pattern as existing test files)

*Existing infrastructure covers framework installation — pytest already configured.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Upload ECF PDF via frontend UI | ECF-01 | End-to-end browser flow | Upload `ecf_20650786.pdf` via Extract page with "ECF Filing" selected, verify 357 entries returned |
| International address flagging | ECF-02 | Edge case visual check | Verify entry 328 (Norway address) is flagged in results |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

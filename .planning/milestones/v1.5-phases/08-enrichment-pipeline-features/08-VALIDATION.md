---
phase: 08
slug: enrichment-pipeline-features
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-16
---

# Phase 08 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x + pytest-asyncio |
| **Config file** | `backend/pytest.ini` (asyncio_mode = auto) |
| **Quick run command** | `cd backend && python3 -m pytest tests/ -x -q` |
| **Full suite command** | `cd backend && python3 -m pytest tests/ -v` |
| **Estimated runtime** | ~15 seconds |

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
| 08-01-01 | 01 | 1 | ENRICH-10 | unit | `python3 -m pytest tests/test_llm_protocol.py -x` | ❌ W0 | ⬜ pending |
| 08-01-02 | 01 | 1 | ENRICH-03 | unit | `python3 -m pytest tests/test_pipeline_cleanup.py -x` | ❌ W0 | ⬜ pending |
| 08-01-03 | 01 | 1 | ENRICH-04 | unit | `python3 -m pytest tests/test_pipeline_validate.py -x` | ❌ W0 | ⬜ pending |
| 08-01-04 | 01 | 1 | ENRICH-05 | unit | `python3 -m pytest tests/test_pipeline_enrich.py -x` | ❌ W0 | ⬜ pending |
| 08-02-01 | 02 | 2 | ENRICH-06 | manual-only | N/A | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_llm_protocol.py` — verify Protocol structure, GeminiProvider satisfies it (ENRICH-10)
- [ ] `tests/test_pipeline_cleanup.py` — mock Gemini, verify ProposedChange output (ENRICH-03)
- [ ] `tests/test_pipeline_validate.py` — mock Google Maps, verify address correction proposals (ENRICH-04)
- [ ] `tests/test_pipeline_enrich.py` — mock PDL/SearchBug, verify phone/email proposals (ENRICH-05)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Preview table updates after each enrichment step | ENRICH-06 | React component behavior, no frontend test suite | 1. Upload file in any tool page 2. Run Clean Up 3. Verify proposed rows appear at top 4. Apply and verify data updates in preview |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

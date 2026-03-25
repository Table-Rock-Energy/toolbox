---
phase: 9
slug: tool-specific-ai-prompts
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-16
---

# Phase 9 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | backend/pytest.ini |
| **Quick run command** | `cd backend && python3 -m pytest tests/test_llm_protocol.py -v` |
| **Full suite command** | `cd backend && python3 -m pytest -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python3 -m pytest tests/test_llm_protocol.py -v`
- **After every plan wave:** Run `cd backend && python3 -m pytest -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 09-01-01 | 01 | 1 | ENRICH-11 | unit | `python3 -m pytest tests/test_llm_protocol.py -v` | ✅ | ⬜ pending |
| 09-01-02 | 01 | 1 | ENRICH-11 | unit | `python3 -m pytest tests/test_llm_protocol.py -v` | ✅ | ⬜ pending |
| 09-02-01 | 02 | 1 | ENRICH-11 | unit | `python3 -m pytest tests/test_llm_protocol.py -v` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. pytest and test_llm_protocol.py already exist.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Confidence badge renders correctly | ENRICH-11 | Visual UI element | Open any tool page, run Clean Up, verify colored badge appears next to each proposed change |
| ECF cross-file discrepancies show both values | ENRICH-11 | Requires real ECF PDF + CSV | Upload ECF PDF with Convey 640 CSV, run Clean Up, verify ProposedChangesPanel shows CSV value → PDF value for mismatches |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

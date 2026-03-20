---
phase: 16
slug: revenue-multi-pdf-streaming
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-20
---

# Phase 16 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x + TypeScript compiler |
| **Config file** | backend/pytest.ini, frontend/tsconfig.app.json |
| **Quick run command** | `cd backend && python3 -m pytest tests/ -x -q -k "revenue"` |
| **Full suite command** | `cd backend && python3 -m pytest tests/ -x -q && cd ../frontend && npx tsc --noEmit` |
| **Estimated runtime** | ~20 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick command
- **After every plan wave:** Run full suite
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 20 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 16-01-01 | 01 | 1 | REV-01 | unit | `cd backend && python3 -m pytest tests/ -k "streaming" -v` | ❌ W0 | ⬜ pending |
| 16-01-02 | 01 | 1 | REV-01 | compile | `cd frontend && npx tsc --noEmit` | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_revenue_streaming.py` — stubs for REV-01 (streaming upload endpoint)

*Existing pytest infrastructure covers framework needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Per-PDF progress visible during multi-file upload | REV-01 | Requires browser + multiple PDF files | Upload 3+ revenue PDFs, verify progress counter updates per file |
| Current file name displayed during processing | REV-01 | Requires browser UI | Upload multi-PDF, verify filename shown for each |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 20s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

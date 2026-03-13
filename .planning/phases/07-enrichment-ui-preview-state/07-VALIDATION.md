---
phase: 7
slug: enrichment-ui-preview-state
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-13
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (backend) + TypeScript compiler (frontend) |
| **Config file** | `backend/pytest.ini` / `frontend/tsconfig.app.json` |
| **Quick run command** | `cd backend && python3 -m pytest tests/ -x -q` |
| **Full suite command** | `cd backend && python3 -m pytest tests/ -v && cd ../frontend && npx tsc --noEmit` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python3 -m pytest tests/ -x -q`
- **After every plan wave:** Run `cd backend && python3 -m pytest tests/ -v && cd ../frontend && npx tsc --noEmit`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 07-01-01 | 01 | 1 | ENRICH-01 | unit | `pytest tests/test_features_status.py -x -q` | ❌ W0 | ⬜ pending |
| 07-01-02 | 01 | 1 | ENRICH-02 | unit | `pytest tests/test_features_status.py -x -q` | ❌ W0 | ⬜ pending |
| 07-02-01 | 02 | 1 | ENRICH-06 | tsc | `npx tsc --noEmit` | ✅ | ⬜ pending |
| 07-02-02 | 02 | 1 | ENRICH-07 | tsc | `npx tsc --noEmit` | ✅ | ⬜ pending |
| 07-03-01 | 03 | 2 | ENRICH-08 | tsc | `npx tsc --noEmit` | ✅ | ⬜ pending |
| 07-03-02 | 03 | 2 | ENRICH-09 | tsc+manual | `npx tsc --noEmit` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_features_status.py` — stubs for ENRICH-01, ENRICH-02 (feature flag endpoint)
- [ ] Frontend TypeScript compilation serves as automated check for component structure

*Existing pytest infrastructure covers backend. Frontend relies on tsc --noEmit.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Buttons hidden when API keys missing | ENRICH-02 | Runtime config determines visibility | 1. Start dev without GEMINI_API_KEY 2. Verify no Clean Up button visible |
| Flagged rows sort to top | ENRICH-08 | Visual sorting in browser | 1. Flag a row via enrichment stub 2. Verify it appears at top of table |
| Inline edit reflects in export | ENRICH-09 | E2E browser interaction | 1. Edit a cell 2. Export CSV 3. Verify edited value in output |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

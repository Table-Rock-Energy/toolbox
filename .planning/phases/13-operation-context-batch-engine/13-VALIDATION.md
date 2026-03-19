---
phase: 13
slug: operation-context-batch-engine
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-19
---

# Phase 13 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | vitest (frontend) + pytest 7.x (backend — no backend changes this phase) |
| **Config file** | `frontend/vitest.config.ts` (if exists) or inline |
| **Quick run command** | `cd frontend && npx tsc --noEmit` |
| **Full suite command** | `cd frontend && npx tsc --noEmit && cd ../backend && pytest -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd frontend && npx tsc --noEmit`
- **After every plan wave:** Run `cd frontend && npx tsc --noEmit && cd ../backend && pytest -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 13-01-01 | 01 | 1 | PERSIST-01 | type-check | `npx tsc --noEmit` | ✅ | ⬜ pending |
| 13-01-02 | 01 | 1 | PERSIST-01 | type-check | `npx tsc --noEmit` | ✅ | ⬜ pending |
| 13-02-01 | 02 | 2 | BATCH-01, BATCH-02 | type-check | `npx tsc --noEmit` | ✅ | ⬜ pending |
| 13-02-02 | 02 | 2 | RESIL-01, RESIL-03 | type-check | `npx tsc --noEmit` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements. This is a pure frontend refactor — TypeScript compiler is the primary automated gate.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Navigate away during operation, return to see it still running | PERSIST-01 | Requires browser navigation interaction | Start AI cleanup on Extract page, navigate to Dashboard, navigate back — operation should show progress |
| Batch progress shows "Batch N of M" | BATCH-01 | Visual UI verification | Start AI cleanup with >25 entries, observe progress indicator |
| ETA updates after each batch | BATCH-02 | Visual UI verification | Watch ETA during multi-batch run, confirm it updates |
| Partial results on batch failure | RESIL-01 | Requires simulated failure | Disconnect network mid-batch, verify previous batch results are preserved |
| No orphaned fetch on navigation | RESIL-03 | Requires DevTools network inspection | Start operation, navigate away, check Network tab for cancelled requests |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

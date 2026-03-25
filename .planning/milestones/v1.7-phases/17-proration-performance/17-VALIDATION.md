---
phase: 17
slug: proration-performance
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-20
---

# Phase 17 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | backend/pytest.ini |
| **Quick run command** | `cd backend && python3 -m pytest tests/ -x -q -k "proration"` |
| **Full suite command** | `cd backend && python3 -m pytest tests/ -x -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick command
- **After every plan wave:** Run full suite
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 17-01-01 | 01 | 1 | PERF-01, PERF-02 | unit | `cd backend && python3 -m pytest tests/ -k "cache" -v` | ❌ W0 | ⬜ pending |
| 17-01-02 | 01 | 1 | PERF-03 | unit | `cd backend && python3 -m pytest tests/ -k "batch" -v` | ❌ W0 | ⬜ pending |
| 17-01-03 | 01 | 1 | PERF-04 | unit | `cd backend && python3 -m pytest tests/ -k "invalidat" -v` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_proration_cache.py` — stubs for PERF-01/02/04 (cache pre-warming, lookup order, invalidation)
- [ ] `tests/test_proration_batch.py` — stubs for PERF-03 (batch Firestore reads)

*Existing pytest infrastructure covers framework needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Cold-start proration upload is fast | PERF-01 | Requires server restart + timing | Restart backend, upload proration CSV, verify no perceptible delay |
| 200-row upload faster than before | PERF-03 | Requires timing comparison | Upload 200-row CSV, compare with pre-phase timing |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

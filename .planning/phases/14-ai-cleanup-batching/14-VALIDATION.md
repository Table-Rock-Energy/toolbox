---
phase: 14
slug: ai-cleanup-batching
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-19
---

# Phase 14 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | backend/pytest.ini |
| **Quick run command** | `cd backend && python3 -m pytest tests/ -x -q --timeout=10` |
| **Full suite command** | `cd backend && python3 -m pytest tests/ -v --timeout=30` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python3 -m pytest tests/ -x -q --timeout=10`
- **After every plan wave:** Run `cd backend && python3 -m pytest tests/ -v --timeout=30`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 14-01-01 | 01 | 1 | BATCH-03 | unit | `cd backend && python3 -m pytest tests/ -k "batch_config" -v` | ❌ W0 | ⬜ pending |
| 14-01-02 | 01 | 1 | RESIL-02 | unit | `cd backend && python3 -m pytest tests/ -k "disconnect" -v` | ❌ W0 | ⬜ pending |
| 14-01-03 | 01 | 1 | RESIL-04 | unit | `cd backend && python3 -m pytest tests/ -k "retry" -v` | ❌ W0 | ⬜ pending |
| 14-02-01 | 02 | 1 | BATCH-04 | manual | Browser: run enrichment on 50+ entries, verify concurrent batches | N/A | ⬜ pending |
| 14-02-02 | 02 | 1 | BATCH-03 | manual | Browser: change batch size in admin, verify new value used | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_batch_config.py` — stubs for BATCH-03 (batch size config persistence)
- [ ] `tests/test_disconnect.py` — stubs for RESIL-02 (backend disconnect detection)
- [ ] `tests/test_retry.py` — stubs for RESIL-04 (retry logic)

*Existing pytest infrastructure covers framework needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Concurrent batch execution visible in UI | BATCH-04 | Requires browser + Gemini API | Run enrichment on 50+ entries, observe multiple batches in-flight in EnrichmentModal |
| Admin batch size config persists | BATCH-03 | Requires browser admin UI | Change batch size in admin settings, reload page, verify value persisted |
| Cancel stops backend processing | RESIL-02 | Requires active Gemini request | Start enrichment, cancel mid-batch, verify backend logs show early stop |

*If none: "All phase behaviors have automated verification."*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

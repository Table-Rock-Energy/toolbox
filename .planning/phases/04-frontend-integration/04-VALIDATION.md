---
phase: 4
slug: frontend-integration
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-11
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | No frontend test framework (TypeScript compiler as safety net) |
| **Config file** | `frontend/tsconfig.app.json` |
| **Quick run command** | `cd frontend && npx tsc --noEmit` |
| **Full suite command** | `cd frontend && npx tsc --noEmit && npx eslint src/` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd frontend && npx tsc --noEmit`
- **After every plan wave:** Run `cd frontend && npx tsc --noEmit && npx eslint src/`
- **Before `/gsd:verify-work`:** Full suite must be green + manual browser verification
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | FE-01 | manual + type-check | `cd frontend && npx tsc --noEmit` | N/A | ⬜ pending |
| 04-01-02 | 01 | 1 | FE-01 | manual + type-check | `cd frontend && npx tsc --noEmit` | N/A | ⬜ pending |
| 04-02-01 | 02 | 1 | FE-02, FE-03 | manual + type-check | `cd frontend && npx tsc --noEmit` | N/A | ⬜ pending |
| 04-02-02 | 02 | 1 | FE-04 | manual + type-check | `cd frontend && npx tsc --noEmit` | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements.* No frontend test framework to install (out of scope per milestone constraints). TypeScript compilation provides automated type safety verification.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Dual-file upload appears when ECF selected | FE-01 | No frontend test framework | Select ECF format, verify second upload field appears; switch away, verify it disappears |
| Results table shows respondent columns | FE-02 | No frontend test framework | Upload ECF PDF, verify name/entity_type/address/city/state/zip columns render |
| Metadata panel above results | FE-03 | No frontend test framework | Upload ECF PDF, verify county/case_number/applicant/well_name panel appears above table |
| Mineral export with ECF data | FE-04 | No frontend test framework | Click Mineral export button, verify county auto-populated, export succeeds |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

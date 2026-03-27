---
phase: 22
slug: database-models-schema
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-25
---

# Phase 22 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.4+ with pytest-asyncio |
| **Config file** | `backend/pytest.ini` |
| **Quick run command** | `cd backend && python3 -m pytest tests/test_db_models.py -x` |
| **Full suite command** | `cd backend && python3 -m pytest -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python3 -m pytest tests/test_db_models.py -x`
- **After every plan wave:** Run `cd backend && python3 -m pytest -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 22-01-01 | 01 | 1 | DB-02 | unit | `cd backend && python3 -m pytest tests/test_db_models.py -x` | No -- Wave 0 | pending |
| 22-01-02 | 01 | 1 | DB-02 | unit | `cd backend && python3 -m pytest tests/test_db_models.py::test_user_model_auth_columns -x` | No -- Wave 0 | pending |
| 22-01-03 | 01 | 1 | DB-03 | integration | `cd backend && alembic upgrade head` | N/A -- CLI | pending |

---

## Wave 0 Requirements

- [ ] `backend/tests/test_db_models.py` -- covers DB-02 (model completeness, column types, relationships)
- [ ] Alembic integration test requires running PostgreSQL -- manual verification acceptable

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `alembic upgrade head` creates all tables | DB-03 | Requires running PostgreSQL via Docker | Run `docker-compose up -d db && cd backend && alembic upgrade head` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

---
phase: 1
slug: auth-enforcement-and-cors-lockdown
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-11
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >=7.4.0 + pytest-asyncio >=0.23.0 |
| **Config file** | none — Wave 0 installs `backend/pytest.ini` |
| **Quick run command** | `cd backend && python3 -m pytest tests/ -x -q` |
| **Full suite command** | `cd backend && python3 -m pytest tests/ -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python3 -m pytest tests/ -x -q`
- **After every plan wave:** Run `cd backend && python3 -m pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 1 | AUTH-01 | integration | `cd backend && python3 -m pytest tests/test_auth_enforcement.py -x` | ❌ W0 | ⬜ pending |
| 01-01-02 | 01 | 1 | AUTH-01 | unit | `cd backend && python3 -m pytest tests/test_auth_enforcement.py::test_dev_mode_bypass -x` | ❌ W0 | ⬜ pending |
| 01-01-03 | 01 | 1 | SEC-01 | integration | `cd backend && python3 -m pytest tests/test_cors.py -x` | ❌ W0 | ⬜ pending |
| 01-02-01 | 02 | 2 | AUTH-02 | manual-only | Manual: stop backend, verify login screen | N/A | ⬜ pending |
| 01-02-02 | 02 | 2 | AUTH-01 | integration | `cd backend && python3 -m pytest tests/test_auth_enforcement.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/__init__.py` — package init
- [ ] `backend/tests/conftest.py` — shared fixtures: test client with auth override, mock Firebase user
- [ ] `backend/tests/test_auth_enforcement.py` — stubs for AUTH-01
- [ ] `backend/tests/test_cors.py` — stubs for SEC-01
- [ ] `backend/pytest.ini` — pytest configuration (asyncio mode, test paths)

*Framework already installed: pytest, pytest-asyncio, httpx in requirements.txt*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Frontend shows login screen when backend unreachable | AUTH-02 | Requires browser rendering + backend shutdown | 1. Stop backend 2. Load app in browser 3. Verify login screen with "Cannot connect" banner |
| Dev mode override allows local development | AUTH-02 | Requires Vite dev server context (`import.meta.env.DEV`) | 1. Run `make dev` without Firebase creds 2. Verify app loads with dev bypass |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

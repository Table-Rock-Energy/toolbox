---
phase: 10
slug: auth-hardening-ghl-cleanup
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-18
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x + pytest-asyncio |
| **Config file** | `backend/pytest.ini` |
| **Quick run command** | `cd backend && python3 -m pytest tests/test_auth_enforcement.py -x -q` |
| **Full suite command** | `cd backend && python3 -m pytest -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python3 -m pytest tests/test_auth_enforcement.py -x -q`
- **After every plan wave:** Run `cd backend && python3 -m pytest -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 10-01-01 | 01 | 1 | GHL-01 | manual | `grep -r "smart_list_name" frontend/src/` returns 0 | N/A | ⬜ pending |
| 10-01-02 | 01 | 1 | GHL-02 | unit | `python3 -m pytest tests/test_auth_enforcement.py -k "ghl_no_smart_list"` | ❌ W0 | ⬜ pending |
| 10-02-01 | 02 | 1 | AUTH-01 | unit | `python3 -m pytest tests/test_auth_enforcement.py -k "admin_options or admin_users or admin_settings"` | ✅ (needs update) | ⬜ pending |
| 10-02-02 | 02 | 1 | AUTH-02 | unit | `python3 -m pytest tests/test_auth_enforcement.py -k "admin_check_no_auth"` | ✅ | ⬜ pending |
| 10-03-01 | 03 | 1 | AUTH-03 | unit | `python3 -m pytest tests/test_auth_enforcement.py -k "history_scoped"` | ❌ W0 | ⬜ pending |
| 10-03-02 | 03 | 1 | AUTH-04 | unit | `python3 -m pytest tests/test_auth_enforcement.py -k "history_admin"` | ❌ W0 | ⬜ pending |
| 10-03-03 | 03 | 1 | AUTH-05 | unit | `python3 -m pytest tests/test_auth_enforcement.py -k "delete_ownership"` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Update `tests/test_auth_enforcement.py::test_admin_options_no_auth_required` — flip assertion: must return 401 without auth
- [ ] Add tests for admin GET settings endpoints returning 401 without auth
- [ ] Add tests for admin GET endpoints returning 403 for non-admin authenticated users
- [ ] Add `admin_client` fixture to `conftest.py` (mock user with admin role)
- [ ] Add tests for history user-scoping (mock `firestore_service.get_user_jobs`)
- [ ] Add tests for delete ownership (mock `firestore_service.get_job`)
- [ ] Add test for GHL smart_list_name removal from backend model

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| smart_list_name removed from frontend type | GHL-02 | Static grep check, not runtime | `grep -r "smart_list_name" frontend/src/` returns 0 results |
| GHL send modal no longer shows smart_list_name field | GHL-01 | Visual UI verification | Open GHL send modal, confirm no smart list name input |
| Frontend delete shows 403 modal | AUTH-05 | UI interaction test | Attempt to delete another user's job as non-admin, confirm modal |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

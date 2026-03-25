---
phase: 24
slug: auth-frontend-firebase-removal
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-25
---

# Phase 24 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x + pytest-asyncio (backend), TypeScript compiler (frontend) |
| **Config file** | `backend/pytest.ini` |
| **Quick run command** | `cd frontend && npx tsc --noEmit` |
| **Full suite command** | `cd backend && python3 -m pytest -v && cd ../frontend && npx tsc --noEmit` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd frontend && npx tsc --noEmit`
- **After every plan wave:** Run `cd backend && python3 -m pytest -v && cd ../frontend && npm run build`
- **Before `/gsd:verify-work`:** Full suite must be green + `grep -r firebase frontend/src/` returns nothing
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 24-01-01 | 01 | 1 | AUTH-05 | unit | `cd backend && python3 -m pytest tests/test_auth.py -x -q` | Needs new test | pending |
| 24-01-02 | 01 | 1 | AUTH-07 | smoke | `cd frontend && npx tsc --noEmit` | N/A -- CLI | pending |
| 24-02-01 | 02 | 2 | AUTH-05 | smoke | `cd frontend && npx tsc --noEmit` | N/A -- CLI | pending |
| 24-02-02 | 02 | 2 | AUTH-06 | smoke | `! grep -r 'firebase' frontend/src/` | N/A -- CLI | pending |

---

## Wave 0 Requirements

- [ ] `backend/tests/test_auth.py` -- add test for `POST /api/auth/change-password` endpoint

*No frontend test infrastructure exists (documented in CLAUDE.md) -- rely on TypeScript compilation + manual testing.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Login page has no Google Sign-In button | AUTH-07 | Visual UI verification | Open Login page, verify only email/password form visible |
| User stays logged in across refresh | AUTH-05 | Browser state | Login, refresh page, verify still authenticated |
| 401 redirects to login | AUTH-05 | Requires expired token | Login, wait for token expiry or manually clear, verify redirect |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

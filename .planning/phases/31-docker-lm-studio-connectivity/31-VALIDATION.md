---
phase: 31
slug: docker-lm-studio-connectivity
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-31
---

# Phase 31 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | backend/pytest.ini |
| **Quick run command** | `cd backend && python3 -m pytest tests/ -x -q --timeout=30` |
| **Full suite command** | `cd backend && python3 -m pytest tests/ -v --timeout=60` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python3 -m pytest tests/ -x -q --timeout=30`
- **After every plan wave:** Run `cd backend && python3 -m pytest tests/ -v --timeout=60`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 31-01-01 | 01 | 1 | DOCKER-01 | config | `grep -q 'host.docker.internal:host-gateway' docker-compose.yml` | ✅ | ⬜ pending |
| 31-01-02 | 01 | 1 | DOCKER-01 | config | `grep -q 'AI_PROVIDER' docker-compose.yml` | ✅ | ⬜ pending |
| 31-01-03 | 01 | 1 | DOCKER-02 | unit | `cd backend && python3 -m pytest tests/ -k "model" -x -q` | ❌ W0 | ⬜ pending |
| 31-02-01 | 02 | 2 | DOCKER-03 | integration | Manual — requires LM Studio running | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Existing test infrastructure covers docker-compose config verification via grep
- [ ] Model verification test may need a new test file if code changes are made

*If none: "Existing infrastructure covers all phase requirements."*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| LM Studio reachable from container | DOCKER-01 | Requires running LM Studio on host | `docker-compose exec backend python3 -c "import httpx; r=httpx.get('http://host.docker.internal:1234/v1/models'); print(r.json())"` |
| Full enrichment pipeline | DOCKER-03 | Requires file upload + UI interaction | Upload a file, click Enrich, verify AI-processed results return |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

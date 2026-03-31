# Requirements: Table Rock Tools

**Defined:** 2026-03-31
**Core Value:** The tools must reliably process uploaded documents and return accurate, exportable results.

## v2.2 Requirements

Requirements for Post-Migration Fixes & AI Enrichment milestone.

### Docker/AI Connectivity

- [ ] **DOCKER-01**: AI enrichment pipeline reaches LM Studio from Docker container via `--add-host=host.docker.internal:host-gateway`
- [ ] **DOCKER-02**: Backend verifies model ID against LM Studio's `/v1/models` endpoint before inference calls
- [ ] **DOCKER-03**: User can run full enrichment pipeline (upload → enrich → results) end-to-end on server with LM Studio

### Nginx Configuration

- [ ] **NGINX-01**: Nginx forwards `/api/pipeline/` requests with 600s timeout and disabled buffering for AI inference
- [ ] **NGINX-02**: Nginx forwards `/api/revenue/` requests with disabled buffering for NDJSON streaming progress

### Bug Fix Consolidation

- [x] **BUGFIX-01**: Revenue check_amount persists as float (not Decimal) to PostgreSQL
- [x] **BUGFIX-02**: Admin user creation uses correct password hashing import
- [x] **BUGFIX-03**: Job record creation resolves user email to UUID before insert
- [x] **BUGFIX-04**: GHL-prep tool filter works correctly
- [x] **BUGFIX-05**: RRC data migrated to PostgreSQL with model filesystem discovery

## Future Requirements

None deferred for this milestone.

## Out of Scope

| Feature | Reason |
|---------|--------|
| PostgreSQL connection pooling tuning | Not needed at current scale |
| CI/CD pipeline for on-prem | Manual deploy via git pull + docker-compose is sufficient |
| Frontend test suite | Deferred — backend stability is priority |
| Rate limiting | Deferred — internal tool with small user base |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| DOCKER-01 | — | Pending |
| DOCKER-02 | — | Pending |
| DOCKER-03 | — | Pending |
| NGINX-01 | — | Pending |
| NGINX-02 | — | Pending |
| BUGFIX-01 | — | Complete |
| BUGFIX-02 | — | Complete |
| BUGFIX-03 | — | Complete |
| BUGFIX-04 | — | Complete |
| BUGFIX-05 | — | Complete |

**Coverage:**
- v2.2 requirements: 10 total
- Mapped to phases: 0
- Unmapped: 5 (bug fixes already complete, 5 active) ⚠️

---
*Requirements defined: 2026-03-31*
*Last updated: 2026-03-31 after initial definition*

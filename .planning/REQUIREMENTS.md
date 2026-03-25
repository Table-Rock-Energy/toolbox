# Requirements: Table Rock Tools v2.0

**Defined:** 2026-03-25
**Core Value:** The tools must reliably process uploaded documents and return accurate, exportable results.

## v2.0 Requirements

Requirements for on-prem migration. Each maps to roadmap phases.

### Authentication

- [ ] **AUTH-01**: User can log in with email and password against local PostgreSQL users table
- [ ] **AUTH-02**: Backend provides /api/auth/login returning JWT access token and /api/auth/me returning user profile
- [x] **AUTH-03**: Backend verifies JWT tokens in require_auth/require_admin dependencies (replacing Firebase token verification)
- [ ] **AUTH-04**: Admin can create initial admin user via CLI seed script (james@tablerocktx.com)
- [ ] **AUTH-05**: Frontend uses local auth context with JWT storage, 401 refresh, and logout (replacing Firebase AuthContext)
- [ ] **AUTH-06**: All Firebase imports, packages (frontend firebase npm + backend firebase-admin), and firebase.ts are removed
- [ ] **AUTH-07**: Google Sign-In provider removed -- email/password authentication only

### Database

- [ ] **DB-01**: PostgreSQL is the sole database -- no Firestore code in any request path
- [x] **DB-02**: SQLAlchemy models cover all 13 Firestore collections (3 new models + auth columns on users table)
- [x] **DB-03**: Alembic initialized with async template and initial migration generated from models
- [ ] **DB-04**: One-time migration script exports all Firestore collections and imports into PostgreSQL (service account JSON as CLI arg)
- [ ] **DB-05**: Every firestore_service.py function has a working PostgreSQL equivalent in db_service.py
- [ ] **DB-06**: firestore_service.py deleted and all Firestore imports/dependencies removed from codebase

### AI Provider

- [ ] **AI-01**: OpenAI-compatible provider calls LM Studio at configurable base URL implementing LLMProvider protocol
- [ ] **AI-02**: Provider factory routes AI calls based on AI_PROVIDER config (lmstudio or none)
- [ ] **AI-03**: Gemini provider and google-genai dependency removed entirely -- LM Studio is the only AI backend

### Storage

- [ ] **STOR-01**: Local filesystem is default storage -- no GCS warnings or errors when GCS_BUCKET_NAME is empty/unset
- [ ] **STOR-02**: google-cloud-storage dependency and GCS-specific code paths removed from codebase

### Cleanup

- [ ] **CLEAN-01**: All Google dependencies removed from requirements.txt (firebase-admin, google-cloud-firestore, google-cloud-storage, google-genai)

## Future Requirements

Deferred to a later milestone. Tracked but not in current roadmap.

### User Management

- **UMGMT-01**: Admin can reset user passwords from admin settings UI
- **UMGMT-02**: Health endpoint reports PostgreSQL and AI provider connectivity status

## Out of Scope

| Feature | Reason |
|---------|--------|
| Google Sign-In / OAuth | No Google Cloud dependency on-prem |
| Self-registration / signup page | Internal tool -- admin controls access |
| Token blacklist / revocation | Short access token expiry sufficient for small team |
| Session storage in Redis | Stateless JWT -- no session store needed |
| Alembic downgrade migrations | Forward-only; PostgreSQL backup before migrations |
| Multi-tenant database | Single team, single instance |
| Local model fine-tuning | Out of scope for document processing |
| MFA / 2FA | Overkill for internal tool |
| Password complexity rules | Minimum 8 characters, no regex -- admin-created accounts |
| Frontend test suite | Deferred from previous milestones |
| Rate limiting | Deferred from previous milestones |
| Structured logging / request tracing | Deferred from previous milestones |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| AUTH-01 | Phase 23 | Pending |
| AUTH-02 | Phase 23 | Pending |
| AUTH-03 | Phase 23 | Complete |
| AUTH-04 | Phase 23 | Pending |
| AUTH-05 | Phase 24 | Pending |
| AUTH-06 | Phase 24 | Pending |
| AUTH-07 | Phase 24 | Pending |
| DB-01 | Phase 25 | Pending |
| DB-02 | Phase 22 | Complete |
| DB-03 | Phase 22 | Complete |
| DB-04 | Phase 27 | Pending |
| DB-05 | Phase 25 | Pending |
| DB-06 | Phase 25 | Pending |
| AI-01 | Phase 26 | Pending |
| AI-02 | Phase 26 | Pending |
| AI-03 | Phase 26 | Pending |
| STOR-01 | Phase 27 | Pending |
| STOR-02 | Phase 27 | Pending |
| CLEAN-01 | Phase 27 | Pending |

**Coverage:**
- v2.0 requirements: 19 total
- Mapped to phases: 19
- Unmapped: 0

---
*Requirements defined: 2026-03-25*
*Last updated: 2026-03-25 -- traceability populated by roadmapper*

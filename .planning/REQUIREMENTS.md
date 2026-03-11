# Requirements: Table Rock Tools v1.3 Security Hardening

**Defined:** 2026-03-11
**Core Value:** The tools must reliably process uploaded documents (PDFs, CSVs, Excel) and return accurate, exportable results. Everything else is secondary to parsing accuracy and data integrity.

## v1.3 Requirements

Requirements for security hardening milestone. Each maps to roadmap phases.

### Authentication

- [x] **AUTH-01**: All tool endpoints (Extract, Title, Proration, Revenue, GHL Prep, History, ETL) require authenticated Firebase token — unauthenticated requests return 401
- [ ] **AUTH-02**: Frontend AuthContext returns `false` (fail-closed) when backend is unreachable, with `import.meta.env.DEV` override for local development

### Network Security

- [x] **SEC-01**: CORS configured with explicit origin allowlist from environment config (`https://tools.tablerocktx.com` in production, `http://localhost:5173` in development); wildcard allowed only when `ENVIRONMENT=development`

### Encryption

- [ ] **ENC-01**: Application fails fast at startup if `ENCRYPTION_KEY` environment variable is missing when `ENVIRONMENT=production` — logs clear error message explaining what to set
- [ ] **ENC-02**: Sensitive admin/app settings (API keys for Gemini, Google Maps, PDL, SearchBug, GHL) encrypted before Firestore persistence using existing `shared/encryption.py` Fernet functions; decrypted on read

### Testing

- [ ] **TEST-01**: pytest + httpx test infrastructure with Firebase auth mocking via `app.dependency_overrides[require_auth]` pattern, reusable test client fixture
- [ ] **TEST-02**: Auth smoke tests verify every protected route returns 401 without token and 200/appropriate status with valid token
- [ ] **TEST-03**: Parsing regression tests with representative test fixtures for at least one revenue parser (EnergyLink or Enverus) and one extract parser (OCC Exhibit A), asserting expected output structure

## Future Requirements

Deferred to next milestone. Tracked but not in current roadmap.

### Authorization

- **AUTHZ-01**: Admin-only access control audit on admin endpoints (user management, settings, API key config)
- **AUTHZ-02**: Replace spoofable `x-user-email`/`x-user-name` headers with verified token-based user identity across all routes
- **AUTHZ-03**: Profile image upload ownership enforcement (user_id must match authenticated user unless admin)

### Data Optimization

- **DATA-01**: Revenue statement rows moved to Firestore subcollection to avoid 1MB document size limit
- **DATA-02**: ETL entity detail batch retrieval replacing N+1 Firestore fetches
- **DATA-03**: Firestore composite index definitions with client-side sorting fallback removal

## Out of Scope

| Feature | Reason |
|---------|--------|
| Frontend test suite | Backend tests have higher ROI for security and parsing accuracy |
| Rate limiting | Important but separate concern; small internal team |
| Structured logging / request tracing | Operational improvement, not security-critical |
| Audit logging for admin actions | Valuable but deferred; collection already defined |
| OAuth scopes / granular permissions | Over-engineering for ~5 users; admin vs. non-admin sufficient |
| JWT-based session tokens | Firebase Auth works and is already integrated |
| API key rotation system | Premature for this team size |
| Per-user data isolation | Small team, transparency preferred per PROJECT.md |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| AUTH-01 | Phase 1 | Complete |
| AUTH-02 | Phase 1 | Pending |
| SEC-01 | Phase 1 | Complete |
| ENC-01 | Phase 2 | Pending |
| ENC-02 | Phase 2 | Pending |
| TEST-01 | Phase 3 | Pending |
| TEST-02 | Phase 3 | Pending |
| TEST-03 | Phase 3 | Pending |

**Coverage:**
- v1.3 requirements: 8 total
- Mapped to phases: 8
- Unmapped: 0

---
*Requirements defined: 2026-03-11*
*Last updated: 2026-03-11 after 01-01 completion*

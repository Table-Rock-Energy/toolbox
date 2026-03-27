# Requirements: Table Rock Tools

**Defined:** 2026-03-27
**Core Value:** The tools must reliably process uploaded documents and return accurate, exportable results.

## v1 Requirements

Requirements for v2.1 Security Headers & Cleanup. Each maps to roadmap phases.

### Security Headers

- [ ] **SEC-01**: Server returns Content-Security-Policy header restricting script/style/font/img sources to self and trusted CDNs
- [ ] **SEC-02**: Server returns Strict-Transport-Security header with max-age >= 31536000 and includeSubDomains
- [ ] **SEC-03**: Server returns X-Frame-Options: DENY header preventing iframe embedding
- [ ] **SEC-04**: Server returns X-Content-Type-Options: nosniff header preventing MIME sniffing
- [ ] **SEC-05**: Server returns Referrer-Policy: strict-origin-when-cross-origin header
- [ ] **SEC-06**: Server returns Permissions-Policy header restricting camera, microphone, geolocation

### Cleanup

- [ ] **CLEAN-02**: Dockerfile contains zero VITE_FIREBASE_* ARGs or references
- [ ] **CLEAN-03**: Hardcoded admin email replaced with DEFAULT_ADMIN_EMAIL env var across auth.py and admin.py

### Testing

- [ ] **TEST-01**: Pytest tests verify all 6 security headers present on API responses with correct values

## Future Requirements

- **SEC-07**: Rate limiting on auth endpoints (login, password change)
- **SEC-08**: Structured logging with request tracing
- **SEC-09**: Frontend test suite

## Out of Scope

| Feature | Reason |
|---------|--------|
| WAF / DDoS protection | Infrastructure-level, not app-level -- handled by Cloud Run / reverse proxy |
| CSRF tokens | SPA with JWT Bearer auth, no cookie-based sessions |
| Subresource Integrity (SRI) | Vite bundles are self-hosted, no CDN scripts |
| Certificate pinning | Cloud Run manages TLS certificates |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| SEC-01 | Phase 28 | Pending |
| SEC-02 | Phase 28 | Pending |
| SEC-03 | Phase 28 | Pending |
| SEC-04 | Phase 28 | Pending |
| SEC-05 | Phase 28 | Pending |
| SEC-06 | Phase 28 | Pending |
| CLEAN-02 | Phase 29 | Pending |
| CLEAN-03 | Phase 29 | Pending |
| TEST-01 | Phase 28 | Pending |

**Coverage:**
- v1 requirements: 9 total
- Mapped to phases: 9
- Unmapped: 0

---
*Requirements defined: 2026-03-27*
*Last updated: 2026-03-27 after roadmap creation*

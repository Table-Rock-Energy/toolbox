# Research Summary: Table Rock Tools Security Hardening

**Domain:** Security hardening, Firestore optimization, and test coverage for an internal FastAPI + React toolbox
**Researched:** 2026-03-11
**Overall confidence:** HIGH

## Executive Summary

Table Rock Tools is a production internal web application deployed on Cloud Run with `--allow-unauthenticated` network access. Despite having a complete auth infrastructure (`require_auth`, `require_admin`, Firebase token verification, user allowlist), approximately 63 API endpoints have zero authentication enforcement. The app is publicly accessible and processes uploaded documents (PDFs, CSVs, Excel files) without verifying the caller's identity.

The security gaps are not architectural -- they are coverage gaps. The auth dependencies exist and work correctly on the GHL router (the only fully protected router). The fix is mechanical: apply `Depends(require_auth)` to unprotected routes, lock down CORS from wildcard to explicit origins, require the encryption key at startup, and fix the frontend's fail-open auth behavior. No new libraries are needed. Every tool required is already installed.

The most dangerous finding is that the current CORS configuration (`allow_origins=["*"]` with `allow_credentials=True`) is invalid per the CORS specification. FastAPI's own documentation confirms this combination must not be used. Browsers are supposed to reject it, but enforcement varies. This should be the first fix deployed.

Beyond security, Firestore revenue statements embed unbounded row arrays in single documents, risking the 1MB document size limit. The standard fix (subcollections) requires a careful dual-read migration pattern to avoid data loss. This is lower priority than auth but should follow in a later phase.

## Key Findings

**Stack:** No new dependencies required. All tools for security hardening (FastAPI dependencies, Fernet encryption, pytest + httpx, Firestore subcollections) are already installed.

**Architecture:** Apply `Depends(require_auth)` per-endpoint (not router-level) because some routers mix auth levels. Use `app.dependency_overrides` for test auth mocking -- FastAPI's official pattern.

**Critical pitfall:** The `/api/admin/users/{email}/check` endpoint is called by the frontend BEFORE auth is established. Blindly adding auth to all routes will lock out every user including the admin. The allowlist check must be moved into the `require_auth` dependency itself.

## Implications for Roadmap

Based on research, suggested phase structure:

1. **Pre-deployment Infrastructure** - Set ENCRYPTION_KEY in Cloud Run, deploy Firestore composite indexes
   - Addresses: Encryption requirement, index readiness
   - Avoids: Pitfall 5 (startup crash from missing env var), Pitfall 9 (indexes not ready)

2. **Auth Enforcement + CORS Lockdown** - Apply auth to all routes, fix CORS, fix frontend fail-open
   - Addresses: All 7 table-stakes security features from FEATURES.md
   - Avoids: Pitfall 1 (admin lockout) by restructuring the auth check flow first, Pitfall 2 (frontend fail-open) by deploying frontend fix simultaneously

3. **Encryption Hardening** - Encrypt sensitive Firestore config, require key at startup
   - Addresses: Plaintext API keys in Firestore
   - Avoids: Pitfall 10 (migration ordering) by deploying after key is confirmed present

4. **Test Infrastructure** - pytest fixtures, auth smoke tests, parsing regression tests
   - Addresses: Zero test coverage
   - Avoids: Pitfall 7 (flaky tests) by building mock infrastructure first

5. **Firestore Optimization** - Revenue subcollection migration, ETL batch fix, composite indexes
   - Addresses: 1MB document limit risk, N+1 queries
   - Avoids: Pitfall 4 (data loss) by using dual-read migration pattern

**Phase ordering rationale:**
- Infrastructure first because env vars and indexes must exist before code that uses them deploys
- Auth enforcement is highest severity and has no code dependencies on other phases
- CORS ships with auth because both are config/middleware changes that should deploy together
- Encryption after auth because encrypted config is read during auth flows -- auth must be stable first
- Tests after auth because they should verify the hardened system, and auth mocking fixtures need the final dependency structure
- Firestore optimization last because it is data modeling, not security, and the dual-read pattern means no downtime

**Research flags for phases:**
- Phase 2 (Auth): HIGH risk -- the admin lockout pitfall (Pitfall 1) is the most dangerous. Needs careful sequencing.
- Phase 5 (Firestore): MEDIUM risk -- subcollection migration needs a dual-read pattern. Standard but requires care.
- Phase 4 (Tests): LOW risk -- standard patterns, well-documented by FastAPI.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | No new dependencies. All recommendations verified against FastAPI official docs via WebFetch. |
| Features | HIGH | Based on direct codebase analysis. Security gaps are observable facts, not opinions. |
| Architecture | HIGH | Patterns (router dependencies, dependency_overrides, subcollections) verified against official docs. |
| Pitfalls | HIGH | 12 pitfalls identified from codebase analysis. Most critical (admin lockout, CORS spec violation) are verifiable facts. |

## Gaps to Address

- **SSE auth pattern:** EventSource API cannot send custom headers. The GHL progress endpoint needs a query-param token approach. Needs implementation-time research on the exact pattern.
- **Firestore index definitions:** The specific composite indexes needed have not been enumerated. Requires analysis of all Firestore queries with `order_by` + `where` combinations.
- **Test data curation:** Parsing regression tests need representative test fixtures (sanitized PDFs or text snapshots). These must be curated from real data, which requires domain knowledge from the Table Rock team.
- **Allowlist dual-storage fix:** The race condition between local JSON and Firestore (Pitfall 6) needs a design decision: eliminate the local file entirely, or make Firestore writes synchronous. Either works; needs a decision.

## Files Created

| File | Purpose |
|------|---------|
| `.planning/research/SUMMARY.md` | This file -- executive summary with roadmap implications |
| `.planning/research/STACK.md` | Technology recommendations (no new deps, patterns to adopt) |
| `.planning/research/FEATURES.md` | Feature landscape (9 table stakes, 5 differentiators, 8 anti-features) |
| `.planning/research/ARCHITECTURE.md` | Architecture patterns (auth flow, CORS, subcollections, testing) |
| `.planning/research/PITFALLS.md` | 12 domain pitfalls with prevention strategies |

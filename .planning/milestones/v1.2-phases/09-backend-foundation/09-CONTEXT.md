# Phase 9: Backend Foundation - Context

**Gathered:** 2026-02-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Backend infrastructure for GoHighLevel API integration. Securely store GHL connection credentials, validate tokens against GHL API, communicate with GHL endpoints (users list, contact upsert), and normalize contact data before sending. This phase delivers the backend services that Phases 10-13 build upon.

Requirements covered: CONF-01, CONF-02, CONF-03, CONF-04

</domain>

<decisions>
## Implementation Decisions

### Credential Storage
- Encrypt Private Integration Tokens using Fernet symmetric encryption (Python `cryptography` library)
- Encryption key stored as environment variable (`GHL_ENCRYPTION_KEY`)
- Connection record fields: name, encrypted_token, location_id, notes (optional), created_at, updated_at, validation_status
- Token last-4 characters stored unencrypted for masked display on edit (`token_last4`)
- On edit, show masked token (`••••••••last4`) — user only enters new token if changing it
- Connections are shared across all allowed users (team-wide, not per-user)
- Connections stored in Firestore `ghl_connections` collection
- Hard delete when removing a connection (no soft delete)

### GHL API Client
- Conservative rate limiting: 50 requests per 10 seconds (well under GHL's 100/10s limit)
- Exponential backoff on 429 responses (retry with increasing delay)
- Token validation uses `GET /users/` endpoint — validates both token and Location ID, also useful for contact owner dropdown later
- Pass through GHL error details to caller (don't normalize to generic errors) — frontend/batch engine decides what to show
- Logging: errors with full detail, successful requests as one-line summaries (method, endpoint, status code). Never log tokens or PII.
- Request timeout: Claude's discretion

### Contact Normalization
- Phone: assume US +1 country code for numbers without country code, format to E.164
- Email: trim whitespace + lowercase + basic format validation (has @ and domain)
- Names: apply title case as safety net (GHL Prep tool already does this, but normalize again at upsert layer)
- Backend validates early: reject contacts missing both email AND phone before calling GHL (save rate-limited API calls)

### API Surface Design
- Dedicated namespace: `/api/ghl/*` (not nested under admin)
- Planned endpoints:
  - `GET /api/ghl/connections` — list all connections
  - `POST /api/ghl/connections` — create connection (validates token on save)
  - `PUT /api/ghl/connections/{id}` — update connection
  - `DELETE /api/ghl/connections/{id}` — hard delete connection
  - `POST /api/ghl/connections/{id}/validate` — re-validate existing connection
  - `GET /api/ghl/connections/{id}/users` — fetch GHL users for contact owner dropdown
  - `POST /api/ghl/contacts/upsert` — upsert single contact
- Accept our own field names (first_name, last_name, phone, email), map to GHL field names internally
- All endpoints require Firebase auth token (no public GHL endpoints)

### Claude's Discretion
- Exact Fernet key rotation strategy
- Request timeout values for GHL API calls
- Retry count and backoff multiplier for 429s
- Internal GHL client class structure and httpx vs requests choice
- Firestore document structure details beyond the specified fields

</decisions>

<specifics>
## Specific Ideas

- User wants a preview window in the send flow where they can uncheck records with errors and click an edit link to fix individual records — this is frontend (Phase 10/11) but the backend validation should surface field-level errors clearly enough to support this UX
- "All of the records should have phone numbers" — phone is effectively the primary contact method for this use case
- GHL Prep tool already transforms names to title case, so the backend normalization is a safety net, not the primary transformation

</specifics>

<deferred>
## Deferred Ideas

- Preview/edit UI for contacts before send (uncheck bad records, edit link for manual fixes) — Phase 10/11 frontend concern
- Batch upsert endpoint — Phase 11 (Bulk Send Engine)
- Contact owner dropdown UI — Phase 10 (Frontend Foundation)
- Progress tracking for batch operations — Phase 12

</deferred>

---

*Phase: 09-backend-foundation*
*Context gathered: 2026-02-27*

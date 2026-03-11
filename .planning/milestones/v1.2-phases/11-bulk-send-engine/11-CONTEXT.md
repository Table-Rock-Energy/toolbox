# Phase 11: Bulk Send Engine - Context

**Gathered:** 2026-02-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Backend system that reliably sends contact batches to GoHighLevel with validation, formatting, tagging, and rate-limit-aware processing. Phase 9 provides the single-contact upsert, GHL API client, and rate limiting. Phase 10 provides the Send modal UI. This phase wires the bulk engine — taking a batch from the frontend, validating it, processing it through GHL, and tracking results.

Does NOT include: real-time progress via SSE (Phase 12), CSV export of failures (Phase 12), or production hardening (Phase 13).

</domain>

<decisions>
## Implementation Decisions

### Validation behavior
- Upfront validation pass — validate entire batch before sending any contacts
- Send valid contacts, skip invalid ones (do not reject entire batch)
- After validation, pause and show user the valid/invalid split in the modal (e.g., "42 valid, 3 invalid") — user clicks "Send 42 contacts" to proceed
- Validation checks presence AND format: email must pass regex validation, phone must be normalizable to E.164 format
- A contact is valid if it has at least one valid email OR one valid phone number

### Batch processing strategy
- Fixed batch size (~50 contacts per batch) — do not adaptively tune
- Skip-and-continue on per-contact failures: log the failure, keep processing remaining contacts
- No per-contact retry — if a contact fails, it's logged as failed and processing continues
- Cancel button available during processing — already-sent contacts stay sent, remaining are skipped, summary shows partial results
- Synchronous processing — modal stays open showing progress, API response returns full results when done (Phase 12 adds async background jobs with SSE)
- Expected to handle hundreds of rows in production

### Tagging & field mapping
- Campaign tag is auto-applied by default — tag name matches the campaign name from the modal
- "manual sms" tag (all lowercase) is optional via checkbox — applies to all contacts in batch when checked
- User can add additional tags: select from existing GHL sub-account tags OR create a new tag
- Tags are additive — always add alongside existing contact tags, never replace
- If a contact ends up with multiple campaign tags, add a note to the GHL contact record flagging the overlap (indicates contact appears in multiple properties/campaigns)
- All source columns map directly to GHL contact fields — column names match GHL field names, no manual field mapping config needed
- Contact Owner is the exception — set via dropdown from Phase 10 (populated by GHL Users API)
- Phone number is the primary dedup/match key for upsert (most records will not have email)
- If email exists in source data, it should be mapped but phone is the primary match field

### Success/failure tracking
- In-memory tracking during send — results stored in a list, returned in API response
- Mineral system ID is the unique identifier linking results back to source rows
- Result summary shows counts (created, updated, failed) plus a list of failed contacts with specific error messages
- Send results are persisted to Firestore as a job history record — user can revisit results later
- Contact statuses: created, updated, failed (with error message), skipped (validation failure)

### Claude's Discretion
- Exact batch delay/throttle timing between batches (within Phase 9's rate limit framework)
- How the multi-campaign note is formatted on the GHL contact record
- Internal data structures for tracking batch progress
- How cancellation signal is communicated from frontend to backend mid-request

</decisions>

<specifics>
## Specific Ideas

- Source data columns already match GHL contact field names — auto-mapping works like GHL's manual CSV import, except Contact Owner is set programmatically
- The mineral system ID from source data is the stable identifier for all result tracking — not row index, not phone number
- "manual sms" tag is always lowercase, always that exact string
- Multiple campaign tags on a contact means they appear in multiple properties — this is uncommon but should be flagged

</specifics>

<deferred>
## Deferred Ideas

- None — discussion stayed within phase scope

</deferred>

---

*Phase: 11-bulk-send-engine*
*Context gathered: 2026-02-27*

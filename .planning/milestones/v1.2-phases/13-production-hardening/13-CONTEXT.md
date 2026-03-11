# Phase 13: Production Hardening - Context

**Gathered:** 2026-02-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Polish the GHL integration for production readiness: rate limiting, error messaging, contact owner validation, SSE reconnection, and help documentation. This phase handles edge cases and production scenarios — no new features, just hardening what Phases 9-12 built.

</domain>

<decisions>
## Implementation Decisions

### Rate Limit UX
- Seamless experience — system auto-throttles, no extra user steps needed
- Subtle info line near send button showing daily capacity remaining (e.g., "Daily capacity: 198,450 remaining")
- Info line escalates to yellow/red styling only when batch size approaches the limit
- If daily limit is hit mid-batch: stop sending, inline yellow banner in progress view — "Daily limit reached. X of Y contacts sent. Remaining contacts can be sent after midnight."
- No modal interruption for rate limit — keep it inline in the progress view
- Stop and notify approach — do NOT auto-queue for next day

### Error Messaging
- GHL button disabled when no valid connection exists or credentials are invalid
- If connection was previously configured but is now broken: button visible but disabled
- Validate credentials on modal open (quick API check) — if bad, show error in modal immediately
- API-down errors display in the send modal, blocking further sends
- User-friendly messages with next action: "GHL connection expired. Go to Settings to reconnect."
- Per-contact errors (duplicate, invalid phone, etc.) shown only in final summary, not live during batch
- Success/fail counts shown live in progress view; detailed errors in summary

### Owner Validation & Sub-Account Selection
- Send modal flow: select sub-account → populates available GHL users → select contact owner(s) → verify campaign name → checkbox for manual SMS → send
- Multiple sub-accounts can be configured in Settings (each with Location ID + Private Integration Token)
- Upload goes to a single sub-account per send operation
- Pull GHL sub-account users dynamically when sub-account is selected
- User can select 1-2 contact owners from the sub-account's users
- If 2 owners selected: even split (first half to Owner A, second half to Owner B, odd contact to first)
- Owner assignment only applies to contacts WITHOUT an owner already set in the upload
- If contact already exists in GHL with a different owner: do NOT change the existing owner
- Never overwrite existing contact owner assignments

### SSE Reconnection
- Claude's Discretion: auto-reconnect logic for network interruptions, implementation details for graceful recovery

### Help Page Documentation
- Add "GHL Integration" section to existing Help page (accordion/expandable format)
- Text-only steps (no screenshots) for setup: creating Private Integration Token, finding Location ID, adding connection in Settings, sending first batch
- FAQ-style troubleshooting: "Why is my button disabled?", "Why did some contacts fail?", etc.
- Include field mapping table: CSV Column → GHL Field, with required vs optional notes

</decisions>

<specifics>
## Specific Ideas

- Rate limit info should feel invisible until it matters — subtle line that escalates visually
- Error messages always suggest a next action, never leave user wondering what to do
- Owner logic is additive only — fill gaps, never override existing assignments
- Phase 12 is currently executing — this phase builds on whatever Phase 12 delivers for progress/error UI

</specifics>

<deferred>
## Deferred Ideas

- Auto-queue remaining contacts for next day when rate limit hit — too complex for now, stop-and-notify is sufficient
- Background periodic credential validation (proactive button state updates) — on-modal-open validation is enough
- Round-robin owner distribution — even split is simpler and sufficient

</deferred>

---

*Phase: 13-production-hardening*
*Context gathered: 2026-02-27*

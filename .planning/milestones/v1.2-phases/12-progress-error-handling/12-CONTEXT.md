# Phase 12: Progress & Error Handling - Context

**Gathered:** 2026-02-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Real-time progress feedback and error reporting during bulk contact sends to GHL. Users see live progress, running totals, completion summary, and can manage failed contacts for retry. Send operations run as async background jobs with SSE streaming.

</domain>

<decisions>
## Implementation Decisions

### Progress UI
- Progress bar displays inline in the existing send modal (replaces send button area with progress view)
- Three real-time counters shown alongside progress bar: Created, Updated, Failed
- No estimated time remaining (ETA) — just X of Y processed with progress bar
- Cancel button available in the modal — shows confirmation dialog ("Are you sure?"), then stops processing remaining contacts; already-sent contacts are kept

### Completion Summary
- Same modal transitions from progress view to summary view (no new modal)
- Updated contacts shown as a viewable list for spot-checking
- Created contacts show just a count (no individual list needed)
- Failed contacts: summary shows failed count with a button to "View Failed Contacts"
- Clicking the button loads failed contacts into the preview window (not a separate modal)

### Failed Contact Management (replaces CSV export requirement)
- Failed contacts load into the existing preview window for management
- User can edit contact fields inline in the preview window
- User can exclude (discard) individual failed records
- User can download CSV of failed contacts from the preview window
- User can retry send for remaining failed contacts after editing
- Retry send carries forward the original send settings (tag, owner, SmartList) but all settings are editable before re-sending

### SSE & Async Job Flow
- POST to send endpoint returns job_id immediately; processing runs in background
- Progress streamed via Server-Sent Events (SSE) to the frontend
- Warn user before navigating away during active send ("Send in progress — leaving will disconnect from progress updates. The send will continue on the server.")
- Auto-reconnect to active job when user returns to the tool page — re-opens progress modal with current state
- Job results (counts, failed contacts with errors, status) persisted to Firestore for later review
- One send job at a time — if a send is active, send button is disabled with a message

### Claude's Discretion
- SSE reconnection implementation details (EventSource vs fetch-based)
- Progress bar animation and visual design
- Firestore schema for job persistence
- How job state is checked on page load for auto-reconnect
- Error categorization (validation vs API vs rate limit)

</decisions>

<specifics>
## Specific Ideas

- The preview window is the central place for managing failed contacts — same preview component used before sending, now reused for post-send error management
- The modal transitions smoothly from progress → summary (not a close + reopen)
- Updated contacts list serves as a spot-check mechanism — user wants to verify what was modified in GHL
- The retry flow should feel like a continuation, not starting over — settings carry forward, user just fixes what failed

</specifics>

<deferred>
## Deferred Ideas

- Rate limit backoff and warnings — Phase 13 (Production Hardening)
- SSE reconnection on network interruption — Phase 13

</deferred>

---

*Phase: 12-progress-error-handling*
*Context gathered: 2026-02-27*

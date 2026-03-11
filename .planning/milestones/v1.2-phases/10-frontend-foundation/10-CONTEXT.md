# Phase 10: Frontend Foundation - Context

**Gathered:** 2026-02-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the frontend UI for GHL sub-account management in Settings and the Send modal on the GHL Prep results page. All features use stub/mock data (local state) while Phase 9 backend runs in parallel. Real API wiring happens after Phase 9 completes.

</domain>

<decisions>
## Implementation Decisions

### Settings layout
- Card-based list for GHL connections (each card shows name, Location ID, status)
- Own section in Settings with "GoHighLevel Connections" heading, visually separated
- Not under a generic "Integrations" tab — GHL gets its own prominent section

### Add/edit flow
- Inline form appears below existing cards when clicking "Add Connection"
- Clicking a card expands it into edit mode (inline, no modal)
- Fields: connection name, Private Integration Token (password-masked), Location ID

### Delete flow
- Small trash icon on each connection card
- Clicking shows inline "Are you sure?" confirmation with Cancel/Delete buttons
- No modal for delete confirmation — stays inline

### Send modal field order
- Top-down priority order:
  1. Sub-account selector (dropdown of configured connections)
  2. Campaign tag input (auto-populated from uploaded data's campaign name; defaults to first if multiple; editable)
  3. Contact owner dropdown (disabled with "Connect GHL to load owners" placeholder in stub mode)
  4. SmartList/campaign name field
  5. Manual SMS checkbox
- Bottom of modal shows summary: "Sending X contacts to [Account Name] with tag [campaign-tag]"

### Button placement on results page
- "Send to GHL" and "Download CSV" side by side, top-right of results table
- "Send to GHL" is primary (teal filled button), "Download CSV" is secondary (outline)
- Send button uses Lucide Send or ArrowUpRight icon
- When no GHL connection exists: Send button is disabled with hover tooltip "Add a GHL connection in Settings first"

### Stub data strategy
- Connections stored in React local state (or localStorage) — no backend calls
- Add/edit/delete fully functional in UI, data doesn't persist across sessions
- Send button in modal is disabled with "GHL integration coming soon" message
- Token field is password-masked input, no validation occurs in stub mode
- Contact owner dropdown is disabled with placeholder text
- Subtle "Preview" badge on GHL section in Settings and Send button to set expectations

### Claude's Discretion
- Exact card styling (shadows, borders, spacing)
- Form validation patterns (required field indicators, error message placement)
- Loading state animations
- Responsive layout behavior for modal and Settings section
- SmartList name field label and placeholder text

</decisions>

<specifics>
## Specific Ideas

- Tag input should auto-populate from the campaign name in the uploaded CSV data, not require manual entry
- If multiple campaign names exist in the data, default to the first one but let the user edit
- The contact count summary at the bottom of the modal gives confidence before clicking Send
- "Preview" badges should be subtle enough to not feel broken, but clear enough to prevent confusion

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 10-frontend-foundation*
*Context gathered: 2026-02-27*

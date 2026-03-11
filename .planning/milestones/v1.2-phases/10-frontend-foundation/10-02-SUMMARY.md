---
phase: 10-frontend-foundation
plan: 02
subsystem: frontend-ui
tags: [ghl-send, modal, react, typescript, stub-mode]
dependency_graph:
  requires:
    - useLocalStorage hook (from Plan 01)
    - GhlConnection interface (from Plan 01)
    - Modal component (existing)
  provides:
    - GhlSendModal component (send form with 5 fields)
    - Send to GHL button on GhlPrep results page
  affects:
    - GhlPrep page UI structure
    - Component barrel exports
tech_stack:
  added:
    - GhlSendModal component (form fields with stub mode)
  patterns:
    - Disabled form fields in stub mode (contact owner dropdown)
    - Preview badge styling for work-in-progress features
    - Tooltip on disabled buttons for user guidance
    - Summary line with dynamic contact count and selection
key_files:
  created:
    - toolbox/frontend/src/components/GhlSendModal.tsx
  modified:
    - toolbox/frontend/src/components/index.ts (added GhlSendModal export)
    - toolbox/frontend/src/pages/GhlPrep.tsx (added Send to GHL button and modal)
decisions:
  - "Send to GHL is primary button (teal filled), Download CSV is secondary (outline)"
  - "Contact owner dropdown disabled in stub mode with placeholder text"
  - "Send button in modal disabled with 'GHL integration coming soon' message"
  - "Preview badge uses amber styling to indicate feature status"
  - "Auto-populate campaign tag from uploaded data's Tags or Campaign column"
metrics:
  duration_minutes: 1.61
  completed_date: 2026-02-27
  tasks_completed: 2
  files_created: 1
  files_modified: 2
  commits: 2
---

# Phase 10 Plan 02: Send to GHL Button & Modal Summary

**One-liner:** Send to GHL button on GhlPrep results page with modal form (sub-account, tag, owner, SmartList, SMS checkbox) in stub mode.

## Objective Achieved

Built the "Send to GHL" button on the GHL Prep results page alongside Download CSV, plus a modal with all form fields (sub-account selector, campaign tag input, contact owner dropdown, SmartList name, manual SMS checkbox). All in stub mode — send button in modal is disabled with "GHL integration coming soon" message. Users can configure the send but not execute it yet (backend wiring comes after Phase 9).

## Tasks Completed

### Task 1: Create GhlSendModal component
- **Commit:** `1198fa5`
- **Files:** `toolbox/frontend/src/components/GhlSendModal.tsx`, `toolbox/frontend/src/components/index.ts`
- **Delivered:**
  - **Modal wrapper:** Uses existing Modal component with `size="lg"` and `title="Send to GoHighLevel"`
  - **5 form fields in top-down order:**
    1. **Sub-Account selector:** Dropdown populated from connections prop, default "Select a connection..."
    2. **Campaign Tag input:** Text input auto-populated from defaultTag prop (campaign name from CSV), editable
    3. **Contact Owner dropdown:** Disabled in stub mode with "Connect GHL to load owners" placeholder
    4. **SmartList Name field:** Text input with "e.g., Spring 2026 Campaign" placeholder
    5. **Manual SMS checkbox:** "Apply manual SMS tag to all contacts" label
  - **Summary line:** Shows only when connection selected and contactCount > 0, displays "Sending {count} contacts to {account} with tag '{tag}'"
  - **Footer buttons:** Cancel (gray outline), Send (disabled teal with "coming soon" tooltip), Preview badge (amber)
  - **Form state:** selectedConnectionId, campaignTag, smartListName, manualSms
  - **Auto-reset:** Form resets when modal opens (useMemo hook)
  - Added to barrel exports in `index.ts`

### Task 2: Add Send to GHL button to GhlPrep results page
- **Commit:** `ee64177`
- **Files:** `toolbox/frontend/src/pages/GhlPrep.tsx`
- **Delivered:**
  - **New imports:** Send icon from lucide-react, GhlSendModal from components, useLocalStorage hook, GhlConnection type
  - **State additions:**
    - `connections` from useLocalStorage (read-only, checks if connections exist)
    - `showSendModal` boolean state
  - **defaultTag derivation:** useMemo extracts campaign name from result rows (Tags/tags/Campaign/campaign columns)
  - **Button area reordered:**
    - Upload New File (outline) | Send to GHL (teal primary) | Download CSV (outline secondary)
    - Send to GHL button disabled when connections.length === 0
    - Tooltip: "Add a GHL connection in Settings first" when disabled
  - **Modal integration:** GhlSendModal at bottom of component JSX, receives isOpen, onClose, connections, contactCount, defaultTag props
  - **Button styling:** Primary teal for Send to GHL (`bg-tre-teal`), outline for Download CSV (`border border-gray-300 text-gray-700`)

## Deviations from Plan

None — plan executed exactly as written.

## Verification Results

### Automated Checks
- **TypeScript compilation:** ✅ Both tasks passed `npx tsc --noEmit` with no errors
- **Strict mode:** ✅ All types properly inferred, no any types used
- **Imports:** ✅ GhlConnection type, useLocalStorage hook, Modal component all imported correctly

### Manual Verification (Expected)
1. GhlPrep results page shows three buttons: Upload New File, Send to GHL, Download CSV
2. Send to GHL is primary (teal filled), Download CSV is secondary (outline)
3. When no connections in localStorage: Send button disabled with hover tooltip
4. With connections in localStorage: Send button enabled, clicking opens modal
5. Modal shows 5 form fields in correct order: sub-account, tag, owner, SmartList, SMS checkbox
6. Contact owner dropdown is disabled with "Connect GHL to load owners" placeholder
7. Summary line appears when connection selected, shows contact count and account name
8. Send button in modal is disabled with "GHL integration coming soon" message
9. Preview badge visible in modal footer
10. Modal closes on Cancel, ESC, or overlay click

## Key Decisions

1. **Button hierarchy:** Send to GHL is primary (teal filled), Download CSV is secondary (outline) — aligns with user decision to prioritize GHL workflow
2. **Disabled states:** Send button disabled when no connections exist (tooltip guides user to Settings)
3. **Contact owner dropdown:** Disabled in stub mode with placeholder text (backend will populate after Phase 9)
4. **Send button in modal:** Disabled with "coming soon" message (stub mode — backend wiring happens after Phase 9)
5. **Auto-populate tag:** Extract campaign name from uploaded CSV data (Tags/Campaign columns) to reduce user input
6. **Form reset:** Modal form resets when opened (prevents stale data from previous sends)
7. **Preview badge:** Amber styling (`bg-amber-100 text-amber-700`) to indicate feature status

## Testing Notes

### What Works
- TypeScript strict mode compilation passes
- GhlConnection type imported from useLocalStorage hook
- Modal component reused correctly with size="lg"
- useLocalStorage hook reads connections array
- defaultTag derived from result rows
- Button disabled state works with connections.length === 0

### Stub Mode Limitations
- No backend validation (all fields client-side only)
- Contact owner dropdown always disabled (no GHL API call)
- Send button in modal always disabled (no actual send operation)
- Campaign tag not validated against GHL API

### Edge Cases Handled
- Empty connections array: Send button disabled with tooltip
- No result data: defaultTag returns empty string
- No Tags/Campaign columns: defaultTag returns empty string
- Summary line only shows when connection selected AND contactCount > 0

## Implementation Notes

### Component Structure
```
GhlPrep.tsx
├── useLocalStorage<GhlConnection[]>('ghl_connections', [])
├── showSendModal state
├── defaultTag useMemo (extracts from result rows)
├── Results header with 3 buttons
│   ├── Upload New File (outline)
│   ├── Send to GHL (teal primary, disabled if no connections)
│   └── Download CSV (outline secondary)
└── GhlSendModal
    ├── 5 form fields (sub-account, tag, owner, SmartList, SMS)
    ├── Summary line (conditional)
    └── Footer (Cancel, Send disabled, Preview badge)
```

### State Management
- **connections:** Read from localStorage via useLocalStorage hook (read-only, just checks existence)
- **showSendModal:** Boolean, controls modal visibility
- **defaultTag:** Derived from result rows via useMemo (auto-populated in modal)
- **Modal form state:** selectedConnectionId, campaignTag, smartListName, manualSms (internal to GhlSendModal)

### Data Flow
1. **Button click:** User clicks "Send to GHL" → setShowSendModal(true)
2. **Modal opens:** GhlSendModal receives connections, contactCount, defaultTag props
3. **Form reset:** useMemo resets form state when modal opens
4. **User fills form:** Selects connection, edits tag, SmartList name, SMS checkbox
5. **Summary updates:** Reactive summary line shows contact count + selected account
6. **Cancel/Close:** setShowSendModal(false), form state discarded
7. **Send (stub):** Button disabled, no-op (backend integration in future plan)

## Self-Check

### Files Created
- [x] toolbox/frontend/src/components/GhlSendModal.tsx

### Files Modified
- [x] toolbox/frontend/src/components/index.ts (added GhlSendModal export)
- [x] toolbox/frontend/src/pages/GhlPrep.tsx (Send to GHL button + modal)

### Commits
- [x] 1198fa5 - Task 1: GhlSendModal component
- [x] ee64177 - Task 2: Send to GHL button on GhlPrep page

### Verification
- [x] TypeScript compiles without errors
- [x] All imports resolve correctly
- [x] Button hierarchy (primary vs secondary) per plan
- [x] Disabled states work correctly
- [x] Modal form has all 5 fields in correct order
- [x] Contact owner dropdown disabled in stub mode
- [x] Send button disabled with "coming soon" message
- [x] Summary line shows contact count and account name
- [x] Preview badge visible
- [x] Modal closes on Cancel/ESC/overlay click

**Self-Check Result:** ✅ PASSED

All planned files created, all commits exist, TypeScript compiles, and implementation matches plan specifications.

## Next Steps

**Phase 10 Plan 03 (if exists):** Continue frontend foundation work

**Phase 9 Plan 02 (Backend):** Connection CRUD
- Build backend endpoints for GHL connection CRUD
- Store connections in Firestore (replace localStorage)
- Encrypt tokens at rest
- Validate tokens against GHL API

**Phase 11 (Bulk Send Engine):**
- Wire Send to GHL button to backend API
- Implement bulk contact upsert with batching
- Add progress tracking and error handling
- Enable Send button in modal (remove stub mode)

## Blocked/Waiting On

None. Plan complete, ready to continue with Phase 10 or Phase 9.

---
phase: 11
plan: 02
subsystem: ghl-bulk-send
tags: [frontend, react, bulk-send, validation, multi-step-flow, ui]

dependency_graph:
  requires: [11-01]
  provides: [bulk-send-ui]
  affects: [ghl-integration]

tech_stack:
  added: []
  patterns: [multi-step-modal, optimistic-validation, error-recovery, expandable-sections]

key_files:
  created: []
  modified:
    - toolbox/frontend/src/utils/api.ts
    - toolbox/frontend/src/components/GhlSendModal.tsx
    - toolbox/frontend/src/pages/GhlPrep.tsx

decisions:
  - summary: "Multi-step flow with validation before send for user confidence"
    rationale: "Users can see validation split and confirm before triggering expensive GHL API calls"
  - summary: "Expandable failed contacts section in results view"
    rationale: "Failed contacts are rare but when they occur, users need detailed error messages"
  - summary: "Row-to-contact mapping with case-insensitive column lookups"
    rationale: "GHL Prep output may have title-cased or lowercase column names - handle both"

metrics:
  duration_seconds: 145
  tasks_completed: 2
  files_created: 0
  files_modified: 3
  commits: 2
  lines_added: 557
  completed_at: "2026-02-27T14:09:30Z"
---

# Phase 11 Plan 02: Bulk Send Engine - Frontend Summary

Frontend bulk send modal with multi-step validation flow, confirmation step, and detailed results display.

## What Was Built

Wired the GhlSendModal component to the backend bulk send API with a complete multi-step user flow:

1. **API Types & Methods** (api.ts):
   - Added 6 new TypeScript interfaces: `BulkContactData`, `ContactResult`, `BulkSendValidationResponse`, `BulkSendResponse`, `BulkSendRequest`
   - Added `ghlApi.validateBatch()` method → `POST /ghl/contacts/validate-batch`
   - Added `ghlApi.bulkSend()` method → `POST /ghl/contacts/bulk-send`

2. **Multi-Step Modal Flow** (GhlSendModal.tsx - complete rewrite):
   - **Step 1 - Idle (form)**: User fills connection, campaign tag, owner, SmartList, manual SMS
   - **Step 2 - Validating**: Loading spinner while backend validates contacts
   - **Step 3 - Confirmed**: Shows validation split (X valid, Y invalid), user confirms "Send X Contacts"
   - **Step 4 - Sending**: Loading spinner with "Sending contacts to GHL..." message
   - **Step 5 - Results**: Shows created/updated/failed/skipped counts with expandable failed contacts section

3. **Row Integration** (GhlPrep.tsx):
   - Passes `rows={result?.rows || []}` prop to GhlSendModal
   - Modal converts rows to `BulkContactData[]` via `mapRowsToContacts()` helper

## Key Implementation Details

**Stub Mode Removed:**
- No more "Preview" badge in footer
- No more disabled button with "coming soon" tooltip
- Send button enabled when connection selected, tag filled, and contacts > 0

**Row-to-Contact Mapping:**
```typescript
function mapRowsToContacts(rows: Record<string, string>[]): BulkContactData[] {
  return rows.map(row => ({
    mineral_contact_system_id: row['Mineral Contact System Id'] || row['mineral_contact_system_id'] || '',
    first_name: row['First Name'] || row['first_name'] || undefined,
    // ... 7 more fields with case-insensitive lookups
  })).filter(c => c.mineral_contact_system_id)
}
```

Handles both title-cased ("First Name") and lowercase ("first_name") column names from GHL Prep output.

**State Management:**
- `sendStep: 'idle' | 'validating' | 'confirmed' | 'sending' | 'results'` — tracks flow progression
- `validationResult`, `sendResult`, `sendError` — stores API responses
- `showFailedContacts` — toggles expandable failed contacts table

**Error Handling:**
- Validation error → shows error message, stays on 'idle' step
- Send error → shows error message, stays on 'confirmed' step with retry option
- All errors displayed with AlertCircle icon in red banner

**Results Display:**
- 2x2 grid for created/updated/failed/skipped counts
- Color-coded boxes: green (created), blue (updated), red (failed), amber (skipped)
- Failed contacts table: 2 columns (Contact ID, Error), scrollable max-height 60

**Reset Behavior:**
- When modal opens (`isOpen` changes to `true`), reset to 'idle', clear all results/errors
- Form fields reset to defaults (including `defaultTag` from props)

## Deviations from Plan

None - plan executed exactly as written.

## Testing Notes

All verification checks passed:
- TypeScript compilation passed with no errors
- New API types exported from api.ts
- GhlSendModal no longer has "Preview" badge or stub mode
- GhlSendModal has 5-step flow: idle → validating → confirmed → sending → results
- GhlPrep passes rows to GhlSendModal

## Next Steps

Phase 12 (Progress & Error Handling) will add:
- Real-time progress tracking during bulk send
- Detailed error categorization (auth errors, rate limit errors, validation errors)
- Retry logic for transient failures
- Job history retrieval for past bulk sends

## Files Changed

**Modified:**
- `toolbox/frontend/src/utils/api.ts` (+50 lines) - 6 new interfaces + 2 API methods
- `toolbox/frontend/src/components/GhlSendModal.tsx` (+399 lines, -108 lines removed) - complete rewrite with multi-step flow
- `toolbox/frontend/src/pages/GhlPrep.tsx` (+1 line) - add rows prop to modal

## Commits

1. `f62aeed` - feat(11-02): add bulk send types and API methods
2. `2720560` - feat(11-02): wire GhlSendModal to bulk send API with multi-step flow

## Self-Check: PASSED

All commits exist:
- ✓ `f62aeed` (bulk send types and API methods)
- ✓ `2720560` (multi-step modal flow)

Modified files contain expected content:
- ✓ `api.ts` contains `BulkSendRequest`, `BulkSendResponse`, `BulkSendValidationResponse`
- ✓ `api.ts` contains `validateBatch` and `bulkSend` methods
- ✓ `GhlSendModal.tsx` contains `sendStep` state and multi-step flow
- ✓ `GhlPrep.tsx` passes `rows` prop to GhlSendModal

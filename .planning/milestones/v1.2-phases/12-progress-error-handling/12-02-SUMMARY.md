---
phase: 12-progress-error-handling
plan: 02
subsystem: ghl-frontend
tags: [sse-client, progress-ui, error-handling, retry-flow, active-job-detection]
dependency_graph:
  requires: [12-01]
  provides: [sse-progress-ui, failed-contacts-ui, retry-flow, active-job-reconnection]
  affects: [ghl-prep-page, ghl-send-modal]
tech_stack:
  added: []
  patterns: [sse-eventSource, localStorage-persistence, modal-state-management]
key_files:
  created:
    - toolbox/frontend/src/hooks/useSSEProgress.ts
  modified:
    - toolbox/frontend/src/utils/api.ts
    - toolbox/frontend/src/components/GhlSendModal.tsx
    - toolbox/frontend/src/pages/GhlPrep.tsx
decisions:
  - useSSEProgress hook manages EventSource lifecycle with cleanup on unmount
  - Active job ID stored in localStorage for page reload persistence
  - Failed contacts view replaces preview table (not separate modal)
  - Retry flow converts failed contacts back to rows and reopens send modal
  - Send button disabled during active job with tooltip message
  - Navigation warning via beforeunload during active send
  - Modal transitions: idle → validating → confirmed → sending → summary (no close/reopen)
metrics:
  duration: 279s
  tasks: 3
  commits: 3
  files: 4
  completed: 2026-02-27T14:56:51Z
requirements-completed: [SEND-03, SEND-04, SEND-05]
---

# Phase 12 Plan 02: Frontend Progress UI Summary

**One-liner:** SSE progress streaming UI with real-time counters, completion summary with updated contacts list, failed contacts management with CSV download and retry flow, and active job reconnection on page return.

## What Was Built

Integrated the async bulk-send backend from Plan 01 with a complete frontend UI for real-time progress tracking, error management, and retry workflows.

1. **useSSEProgress Hook (Task 1)**
   - EventSource management with automatic cleanup
   - Progress state: processed/total/created/updated/failed
   - Completion state: status, counts, failed_contacts, updated_contacts
   - Error handling for SSE connection failures
   - disconnect() method for manual cleanup

2. **GhlSendModal Updates (Task 2)**
   - SendStep: 'idle' | 'validating' | 'confirmed' | 'sending' | 'summary'
   - **Sending step:** Progress bar with bg-tre-teal fill (transition-all duration-300), "X of Y processed" text, three counter boxes (Created/Updated/Failed)
   - Cancel button during send with confirmation dialog
   - Navigation warning via beforeunload event
   - **Summary step:** Send Complete header, count boxes, expandable updated contacts list (max 50), View Failed Contacts button
   - Calls startBulkSend instead of bulkSend (returns immediately with job_id)
   - Props: activeJobId, onJobStarted, onViewFailedContacts

3. **GhlPrep Page Enhancements (Task 3)**
   - Active job detection on mount via localStorage check
   - Auto-reconnect to processing jobs (reopens modal with activeJobId)
   - Failed contacts view mode (replaces preview table)
   - Failed contacts table includes error columns (Error Category, Error Message)
   - Download Failed CSV button (generates CSV with all contact fields + error details)
   - Retry Send button (converts failed contacts back to rows, reopens modal)
   - Send button disabled during active job with tooltip "Send in progress"
   - localStorage cleanup on modal close

## Task Completion

| Task | Status | Commit | Description |
|------|--------|--------|-------------|
| 1 | ✓ | 009fbec | Add frontend types, API methods, and useSSEProgress hook |
| 2 | ✓ | 6da3333 | Rewrite GhlSendModal with progress view, summary view, and cancel support |
| 3 | ✓ | 2dc01a5 | Wire GhlPrep with active job detection, failed contacts, retry, and CSV download |

## Deviations from Plan

None - plan executed exactly as written.

## Key Implementation Details

**SSE Connection:**
- EventSource connects to `/api/ghl/send/{job_id}/progress`
- Listens for 'progress' and 'complete' events
- Auto-reconnects on network errors (EventSource default behavior)
- Sets error state only when readyState is CLOSED (not reconnecting)

**Progress Bar:**
- Width calculated as `(processed/total)*100%`
- CSS transition: `transition-all duration-300` for smooth updates
- bg-tre-teal fill color

**Counter Boxes:**
- Grid layout: `grid grid-cols-3 gap-3`
- Green (Created), Blue (Updated), Red (Failed)
- Updates in real-time as progress events arrive

**Active Job Persistence:**
- Stored in localStorage key: `ghl_active_job_id`
- Set when job starts (onJobStarted callback)
- Checked on page mount
- Cleared when modal closes after completion

**Failed Contacts Management:**
- Failed contacts loaded into existing preview table (not separate modal)
- Error columns appended: Error Category, Error Message
- CSV export includes all contact fields + error details
- Retry flow: converts failed contacts → rows → reopens modal with data

**Navigation Warning:**
- beforeunload event listener during 'sending' step
- Message: "Send in progress — leaving will disconnect from progress updates. The send will continue on the server."
- Removed when step changes or component unmounts

## User Experience Flow

1. **Normal Send:**
   - User uploads CSV → clicks "Send to GHL" → fills form → "Validate & Send"
   - Modal shows real-time progress bar with counters
   - Completion summary shows counts with expandable updated contacts list
   - User clicks "Close" or "View Failed Contacts"

2. **With Failures:**
   - Summary shows failed count with "View Failed Contacts" button
   - User clicks → modal closes → preview table loads failed contacts with error columns
   - User can exclude rows, download CSV, or click "Retry Send"
   - Retry reopens modal with failed contacts as input, all settings editable

3. **Page Reload During Send:**
   - User returns to GhlPrep page
   - Page detects active job in localStorage
   - Auto-opens modal in 'sending' step
   - SSE reconnects and shows current progress
   - User can cancel or wait for completion

4. **Cancel Send:**
   - User clicks "Cancel Send" during progress
   - Confirmation dialog: "Stop sending? Already-sent contacts will be kept."
   - If confirmed: calls cancelJob API, disconnects SSE, shows summary with partial results

## Success Criteria Met

- [x] Real-time progress bar shows X of Y processed with Created/Updated/Failed counters (SEND-03)
- [x] Summary view shows final counts with updated contacts list and View Failed Contacts button (SEND-04)
- [x] Failed contacts load into preview window with error details, CSV download, exclude, and retry (SEND-05)
- [x] Cancel button stops processing with confirmation dialog
- [x] Navigation warning shown during active send
- [x] Active job auto-reconnects on page return
- [x] Send button disabled during active job
- [x] TypeScript compilation passes with no errors
- [x] useSSEProgress hook exists at toolbox/frontend/src/hooks/useSSEProgress.ts
- [x] GhlSendModal imports and uses useSSEProgress hook
- [x] GhlPrep checks localStorage for active job on mount
- [x] GhlPrep has CSV download button for failed contacts
- [x] GhlPrep has retry flow that re-opens modal with failed contacts

## Integration Points

- **Backend SSE Endpoint:** `/api/ghl/send/{job_id}/progress` (Plan 01)
- **Backend Job Status:** `/api/ghl/send/{job_id}/status` (Plan 01)
- **Backend Cancel:** `/api/ghl/send/{job_id}/cancel` (Plan 01)
- **Error Categories:** validation, api_error, rate_limit, network, unknown (Plan 01)

## Testing Notes

Manual testing should verify:
1. Progress bar updates smoothly as contacts are processed
2. Counters increment in real-time
3. Cancel stops processing gracefully
4. Navigation warning appears during send
5. Page reload reconnects to active job
6. Failed contacts view shows error details correctly
7. CSV download includes all contact fields + error columns
8. Retry flow reopens modal with failed contacts as input

## Next Steps

Phase 13 (Production Hardening):
1. Add retry logic for transient GHL API errors
2. Add rate limit backoff handling
3. Add comprehensive error logging
4. Add user notifications for job completion (when not on page)
5. Add job history view (completed sends)
6. Add connection health monitoring

## Self-Check: PASSED

All files and commits verified:

- ✓ toolbox/frontend/src/hooks/useSSEProgress.ts (created)
- ✓ toolbox/frontend/src/utils/api.ts (modified)
- ✓ toolbox/frontend/src/components/GhlSendModal.tsx (modified)
- ✓ toolbox/frontend/src/pages/GhlPrep.tsx (modified)
- ✓ Commit 009fbec (Task 1)
- ✓ Commit 6da3333 (Task 2)
- ✓ Commit 2dc01a5 (Task 3)

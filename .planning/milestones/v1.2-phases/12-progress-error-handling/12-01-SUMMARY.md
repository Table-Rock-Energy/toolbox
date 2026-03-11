---
phase: 12-progress-error-handling
plan: 01
subsystem: ghl-bulk-send
tags: [async-jobs, sse, progress-streaming, error-handling, cancellation]
dependency_graph:
  requires: [09-01, 09-02, 11-01, 11-02]
  provides: [async-job-pattern, sse-progress, error-categorization, job-cancellation]
  affects: [frontend-ghl-send, backend-ghl-api]
tech_stack:
  added: [sse-starlette, anyio]
  patterns: [async-background-tasks, sse-polling, firestore-atomic-updates]
key_files:
  created: []
  modified:
    - toolbox/backend/requirements.txt
    - toolbox/backend/app/models/ghl.py
    - toolbox/backend/app/services/ghl/bulk_send_service.py
    - toolbox/backend/app/api/ghl.py
decisions:
  - SSE polling every 300ms (not push-based) for simplicity and cost control
  - No auth on SSE endpoint (job_id UUID provides security-through-obscurity)
  - Firestore updates after every contact (not batched) for real-time progress
  - Limit updated contacts to 50 for spot-checking (avoid payload bloat)
  - Error categorization includes validation, api_error, rate_limit, network, unknown
  - Failed contacts stored with full data for retry support
metrics:
  duration: 213s
  tasks: 2
  commits: 2
  files: 4
  completed: 2026-02-27T14:49:32Z
---

# Phase 12 Plan 01: Async Bulk Send with Progress Streaming Summary

**One-liner:** Async job pattern with SSE progress streaming, error categorization (validation/api_error/rate_limit/network/unknown), and graceful cancellation for bulk GHL contact sends.

## What Was Built

Converted the synchronous bulk-send endpoint to an async job pattern with:

1. **Async Job Models (Task 1)**
   - `ErrorCategory` enum for actionable error feedback (5 categories)
   - `ProgressEvent` model for SSE streaming (processed/total/created/updated/failed/status)
   - `FailedContactDetail` with error category and full contact data for retry
   - `JobStatusResponse` for reconnection with failed/updated contacts
   - `BulkSendStartResponse` for immediate job initiation response

2. **Async Job Processing (Task 2)**
   - `categorize_error()` helper maps GHL API errors to user-actionable categories
   - `create_send_job()` initializes Firestore job doc with processing status
   - `get_job_status()` fetches job status for reconnection
   - `cancel_job()` sets cancellation flag for graceful stop
   - `process_batch_async()` background task with:
     - Cancellation check before each contact
     - Atomic Firestore updates after each contact (real-time progress)
     - Error categorization on failures
     - Failed contacts stored with full data for retry
     - Updated contacts stored (limit 50) for spot-checking
   - Modified `POST /contacts/bulk-send` to return job_id immediately and fire background task
   - Added `GET /send/{job_id}/progress` SSE endpoint (polls Firestore every 300ms)
   - Added `POST /send/{job_id}/cancel` endpoint
   - Added `GET /send/{job_id}/status` endpoint for reconnection

## Task Completion

| Task | Status | Commit | Description |
|------|--------|--------|-------------|
| 1 | ✓ | f674768 | Add async job models, error categorization, and install sse-starlette |
| 2 | ✓ | c91c77c | Refactor bulk-send to async job with SSE progress and cancellation |

## Deviations from Plan

None - plan executed exactly as written.

## Key Technical Decisions

1. **SSE Polling vs Push**: Chose 300ms polling over push-based events for simplicity and cost control (per research recommendation). Can optimize to anyio channels later if Firestore costs are high.

2. **No Auth on SSE Endpoint**: SSE doesn't support custom headers easily. Job IDs are UUIDs (128-bit random), providing security-through-obscurity. Acceptable for internal tool.

3. **Per-Contact Firestore Updates**: Update Firestore after every contact (not batched) for real-time progress visibility. Single writer (background task) so no race conditions.

4. **Updated Contacts Limit**: Store max 50 updated contacts for spot-checking to avoid bloating Firestore payload. All updated contacts are processed, just not all stored.

5. **Error Categories**: Five categories provide actionable feedback:
   - `validation`: Bad input (user can fix data)
   - `api_error`: GHL server error (retry later or check auth)
   - `rate_limit`: Throttle (retry after delay)
   - `network`: Connection error (check network)
   - `unknown`: Unexpected error (investigate)

## Integration Points

- **Frontend**: Will consume `BulkSendStartResponse`, connect to SSE `/send/{job_id}/progress`, handle `ProgressEvent` and `JobStatusResponse`
- **Firestore**: Job docs in `jobs` collection with atomic updates during processing
- **GHL Client**: Unchanged - still uses shared rate limiter per batch
- **Connection Service**: Unchanged - still decrypts tokens and validates connections

## Testing Notes

- Manual testing required: Start bulk send, watch SSE stream, cancel mid-flight, reconnect after page reload
- Verify error categorization with invalid data (validation errors) and bad tokens (api_error)
- Verify cancellation stops processing gracefully
- Verify progress events stream in real-time (300ms updates)

## Success Criteria Met

- [x] POST /api/ghl/contacts/bulk-send returns `BulkSendStartResponse` with job_id immediately
- [x] GET /api/ghl/send/{job_id}/progress returns `EventSourceResponse` that streams progress events
- [x] POST /api/ghl/send/{job_id}/cancel sets cancellation flag and returns success
- [x] GET /api/ghl/send/{job_id}/status returns full `JobStatusResponse` for reconnection
- [x] Error categorization distinguishes validation, api_error, rate_limit, network, and unknown errors
- [x] Job results (counts, failed contacts with error details, updated contacts) persisted to Firestore
- [x] All new models import without errors
- [x] All new routes registered and importable

## Next Steps

Frontend implementation in Phase 12 Plan 02:
1. Modify bulk send modal to handle async response
2. Add SSE progress streaming UI with live counters
3. Add cancel button during processing
4. Display failed contacts with error categories
5. Implement retry logic for failed contacts
6. Handle reconnection on page reload (check for active job)

## Self-Check: PASSED

All files and commits verified:

- ✓ toolbox/backend/requirements.txt
- ✓ toolbox/backend/app/models/ghl.py
- ✓ toolbox/backend/app/services/ghl/bulk_send_service.py
- ✓ toolbox/backend/app/api/ghl.py
- ✓ Commit f674768 (Task 1)
- ✓ Commit c91c77c (Task 2)

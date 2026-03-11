---
phase: 11
plan: 01
subsystem: ghl-bulk-send
tags: [backend, ghl, bulk-send, validation, rate-limiting, firestore]

dependency_graph:
  requires: [09-01, 09-02]
  provides: [bulk-send-api]
  affects: [ghl-integration]

tech_stack:
  added: []
  patterns: [batch-validation, sequential-processing, shared-rate-limiter, job-persistence]

key_files:
  created:
    - toolbox/backend/app/services/ghl/bulk_send_service.py
  modified:
    - toolbox/backend/app/models/ghl.py
    - toolbox/backend/app/api/ghl.py

decisions:
  - summary: "Shared GHLClient instance for batch processing ensures single rate limiter across all contacts"
    rationale: "Token bucket rate limiter is instance-based, so reusing client prevents rate limit violations"
  - summary: "Skip-and-continue error handling for per-contact failures"
    rationale: "One contact failure shouldn't block the entire batch - track failed contacts in results"
  - summary: "Validation endpoint separate from send endpoint"
    rationale: "Frontend can show validation split and get user confirmation before actual send"

metrics:
  duration_seconds: 125
  tasks_completed: 2
  files_created: 1
  files_modified: 2
  commits: 2
  lines_added: 421
  completed_at: "2026-02-27T14:04:53Z"
---

# Phase 11 Plan 01: Bulk Send Engine Summary

Backend bulk send engine with batch validation, sequential processing with rate limiting, tagging, per-contact result tracking, and Firestore job persistence.

## What Was Built

Added backend infrastructure for bulk contact processing through GHL API:

1. **Pydantic Models** (5 new classes in `models/ghl.py`):
   - `BulkContactData` - Single contact in bulk request with mineral_contact_system_id
   - `BulkSendRequest` - Bulk send request with connection_id, contacts, campaign_tag, manual_sms, assigned_to
   - `ContactResult` - Per-contact result with status (created/updated/failed/skipped), ghl_contact_id, error
   - `BulkSendValidationResponse` - Validation split response (valid_count, invalid_count, invalid_contacts)
   - `BulkSendResponse` - Bulk send response with job_id, counts, results

2. **Bulk Send Service** (`services/ghl/bulk_send_service.py`):
   - `validate_batch()` - Separates valid/invalid contacts based on email OR phone presence + format
   - `process_batch()` - Sequential processing with shared GHLClient (single rate limiter), skip-and-continue error handling
   - `persist_send_job()` - Writes job results to Firestore jobs collection (non-critical, logs warning on failure)

3. **API Endpoints** (`api/ghl.py`):
   - `POST /api/ghl/contacts/validate-batch` - Returns validation split before sending
   - `POST /api/ghl/contacts/bulk-send` - Validates, processes, persists, returns full results

## Key Implementation Details

**Batch Validation:**
- Checks `mineral_contact_system_id` exists (skips with error if missing)
- Normalizes contact data (phone to E.164, email to lowercase)
- Validates contact has email OR phone (reuses existing `validate_contact()`)
- Returns tuple: (valid_contacts_list, invalid_contact_results_list)

**Sequential Processing:**
- Creates ONE `GHLClient` instance outside loop (critical: shared rate limiter)
- Processes contacts sequentially with `async for` (rate limiter automatically throttles)
- On success: tracks action (created/updated) + ghl_contact_id
- On error: logs, tracks as "failed", continues processing (skip-and-continue)
- Returns dict with created_count, updated_count, failed_count, total_count, results

**Tagging:**
- Always applies `campaign_tag` to all contacts
- Conditionally adds "manual sms" (lowercase) if `manual_sms=True`
- Tags passed to `client.upsert_contact()` via contact_data

**Job Persistence:**
- Writes to Firestore `jobs` collection with job_id as document ID
- Stores: tool="ghl_send", connection_id, campaign_name, counts, results, user_id, created_at, status="completed"
- Non-critical: wrapped in try/except, logs warning on failure but doesn't raise

**Error Handling:**
- `GHLAuthError` → 401 (invalid token)
- `GHLRateLimitError` → 429 (retries exhausted)
- `ValueError` → 400 (connection not found or validation error)
- Generic `Exception` → 500

## Deviations from Plan

None - plan executed exactly as written.

## Testing Notes

All verification checks passed:
- New Pydantic models import without errors
- Bulk send service functions import without errors
- Two new routes registered on GHL router
- Python syntax checks passed for all modified files
- TypeScript compilation passed (no frontend changes)

## Next Steps

Phase 11 Plan 02 will wire the frontend:
- Update GhlSendModal to call `/api/ghl/contacts/validate-batch` on open
- Show validation split (valid/invalid counts) in modal
- On confirm, call `/api/ghl/contacts/bulk-send` and show progress/results
- Handle errors (auth, rate limit, generic)

## Files Changed

**Created:**
- `toolbox/backend/app/services/ghl/bulk_send_service.py` (214 lines)

**Modified:**
- `toolbox/backend/app/models/ghl.py` (+50 lines) - 5 new Pydantic models
- `toolbox/backend/app/api/ghl.py` (+127 lines) - 2 new endpoints + imports

## Commits

1. `1b96617` - feat(11-01): add bulk send models and service
2. `c42e6c6` - feat(11-01): add validate-batch and bulk-send endpoints

## Self-Check: PASSED

All created files exist:
- ✓ `toolbox/backend/app/services/ghl/bulk_send_service.py`

All commits exist:
- ✓ `1b96617` (bulk send models and service)
- ✓ `c42e6c6` (validate-batch and bulk-send endpoints)

Modified files contain expected content:
- ✓ `models/ghl.py` contains `class BulkSendRequest`
- ✓ `api/ghl.py` contains `async def validate_batch_endpoint`
- ✓ `api/ghl.py` contains `async def bulk_send_endpoint`

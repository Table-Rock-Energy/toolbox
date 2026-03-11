---
phase: 09-backend-foundation
plan: 01
subsystem: ghl-api
tags: [backend, api-client, rate-limiting, normalization, validation]
dependency_graph:
  requires: [encryption_key, firestore_service]
  provides: [ghl_models, ghl_client, contact_normalization]
  affects: []
tech_stack:
  added: [phonenumbers]
  patterns: [token-bucket-rate-limiting, exponential-backoff, async-context-manager]
key_files:
  created:
    - toolbox/backend/app/models/ghl.py
    - toolbox/backend/app/services/ghl/__init__.py
    - toolbox/backend/app/services/ghl/normalization.py
    - toolbox/backend/app/services/ghl/client.py
  modified:
    - toolbox/backend/requirements.txt
decisions:
  - "Use existing encryption_key from Settings for GHL token encryption (no separate ghl_encryption_key needed)"
  - "Use phonenumbers library for E.164 normalization with US +1 default country code"
  - "Token bucket rate limiter: 50 requests per 10 seconds to match GHL API limits"
  - "Exponential backoff on 429: 1s, 2s, 4s (up to 3 retries)"
  - "Pass through GHL error details to caller (don't normalize to generic errors)"
  - "Never log tokens or PII - only log method, endpoint, status code"
metrics:
  duration_seconds: 163
  completed_at: "2026-02-27T12:29:14Z"
  tasks_completed: 2
  files_created: 4
  files_modified: 1
  commits: 2
---

# Phase 09 Plan 01: GHL API Foundation Summary

**One-liner:** GHL API client with token bucket rate limiting (50/10s), exponential backoff retry, and E.164 phone normalization using phonenumbers library.

## What Was Built

Created the foundational GHL API integration layer with:

1. **Pydantic Models** (`app/models/ghl.py`):
   - `GHLConnectionCreate/Update/Response` for connection CRUD operations
   - `ContactUpsertRequest/Response` for contact operations
   - `GHLUserResponse` for user listing (contact owner dropdown)
   - `GHLValidationResult` for connection validation

2. **Contact Normalization** (`services/ghl/normalization.py`):
   - `normalize_phone`: Parses phone numbers to E.164 format (+15127481234) using phonenumbers library with US +1 default
   - `normalize_email`: Lowercase, trim, validate @ and domain
   - `normalize_name`: Title case, trim
   - `normalize_contact`: Apply all normalizations to contact dict
   - `validate_contact`: Ensure contact has at least email OR phone

3. **GHL API Client** (`services/ghl/client.py`):
   - `RateLimiter`: Token bucket pattern (50 requests per 10 seconds)
   - `GHLClient`: Async context manager with httpx.AsyncClient
   - Rate-limited requests with exponential backoff on 429 (1s, 2s, 4s - up to 3 retries)
   - Methods: `get_users`, `search_contacts`, `create_contact`, `update_contact`, `upsert_contact`
   - Custom exceptions: `GHLAPIError`, `GHLRateLimitError`, `GHLAuthError`
   - Never logs tokens or PII (only method, endpoint, status code)

## Deviations from Plan

None - plan executed exactly as written.

**Note:** Plan mentioned potentially adding `ghl_encryption_key` to config.py, but discovered the existing `encryption_key` field (line 64) is already used by `encryption.py`. No config changes needed - GHL will reuse the same encryption key.

## Verification Results

All verification checks passed:

- ✓ All Pydantic models import without errors
- ✓ GHLClient class importable with async context manager interface
- ✓ RateLimiter has acquire() method
- ✓ normalize_phone("5127481234") returns "+15127481234"
- ✓ normalize_email("  Test@Example.COM  ") returns "test@example.com"
- ✓ validate_contact({"first_name": "John"}) returns (False, error_msg) - missing both email and phone
- ✓ validate_contact({"phone": "5127481234"}) returns (True, None) - has phone
- ✓ phonenumbers listed in requirements.txt

## Task Breakdown

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create Pydantic models and add phonenumbers dependency | 7407e4b | requirements.txt, app/models/ghl.py |
| 2 | Create GHL API client with rate limiting and contact normalization | 42611ff | services/ghl/__init__.py, services/ghl/normalization.py, services/ghl/client.py |

## Dependencies Created

**Provides:**
- `GHLConnectionCreate/Update/Response` - Connection CRUD models
- `ContactUpsertRequest/Response` - Contact operation models
- `GHLUserResponse` - User listing model
- `GHLValidationResult` - Validation result model
- `GHLClient` - Async API client with rate limiting
- `RateLimiter` - Token bucket rate limiter
- `normalize_contact`, `validate_contact` - Contact normalization utilities
- Custom exceptions: `GHLAPIError`, `GHLRateLimitError`, `GHLAuthError`

**Requires:**
- `encryption_key` from Settings (for Plan 02 connection token storage)
- `firestore_service` (for Plan 02 connection persistence)
- httpx (already in requirements.txt)
- phonenumbers>=8.13.0 (added to requirements.txt)

**Affects:**
- Plan 02 (Connection CRUD) - uses these models and client
- Plan 03+ (all GHL integration plans) - depend on this foundation

## Next Steps

**Immediate (Plan 02 - Connection CRUD):**
- Create Firestore collection for GHL connections
- Implement connection CRUD endpoints (create, list, update, delete)
- Add connection validation (test token via get_users call)
- Encrypt token using existing encryption service before storage
- Store token_last4 for masked display

**Future:**
- Bulk contact send (Plan 03+)
- Progress tracking and error handling
- Frontend Settings UI integration

## Self-Check

Verified all created files exist:

```bash
# All files created successfully
✓ toolbox/backend/app/models/ghl.py
✓ toolbox/backend/app/services/ghl/__init__.py
✓ toolbox/backend/app/services/ghl/normalization.py
✓ toolbox/backend/app/services/ghl/client.py
```

Verified all commits exist:

```bash
✓ 7407e4b (Task 1: Pydantic models + phonenumbers dependency)
✓ 42611ff (Task 2: GHL client + normalization)
```

## Self-Check: PASSED

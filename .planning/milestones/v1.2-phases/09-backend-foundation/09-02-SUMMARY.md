---
phase: 09-backend-foundation
plan: 02
subsystem: ghl-api
tags: [backend, fastapi, firestore, connection-crud, encryption]
dependency_graph:
  requires: [ghl_models, ghl_client, encryption, firestore_service, auth]
  provides: [connection_crud_api, ghl_endpoints]
  affects: [frontend_settings, ghl_send_flow]
tech_stack:
  added: []
  patterns: [lazy-imports, firestore-crud, encrypted-storage, immediate-validation]
key_files:
  created:
    - toolbox/backend/app/services/ghl/connection_service.py
    - toolbox/backend/app/api/ghl.py
  modified:
    - toolbox/backend/app/main.py
decisions:
  - "Validate connections immediately on create (not deferred to first use)"
  - "Re-validate automatically when token is updated via PUT endpoint"
  - "Hard delete connections from Firestore (no soft delete)"
  - "Never return encrypted_token field - always removed from response dicts"
  - "Pass through GHL error details to frontend (no generic error normalization)"
metrics:
  duration_seconds: 147
  completed_at: "2026-02-27T12:33:56Z"
  tasks_completed: 2
  files_created: 2
  files_modified: 1
  commits: 2
---

# Phase 09 Plan 02: Connection CRUD Summary

**One-liner:** GHL connection CRUD API with encrypted Firestore storage, immediate validation on create, and 7 authenticated endpoints for connection management and contact upsert.

## What Was Built

Created the full GHL connection management API layer with:

1. **Connection Service** (`services/ghl/connection_service.py`):
   - `create_connection`: Create with encrypted token storage, set validation_status to "pending"
   - `get_connection`: Fetch by ID with optional token decryption (never returns encrypted_token)
   - `list_connections`: List all connections sorted by name
   - `update_connection`: Update fields, re-encrypt token if changed, reset validation_status
   - `delete_connection`: Hard delete from Firestore
   - `validate_connection`: Test token via GHL API get_users call, update validation_status
   - `get_connection_users`: Fetch GHL users for contact owner dropdown
   - `upsert_contact_via_connection`: Delegate contact upsert to GHL client
   - All operations use lazy imports for Firestore and encryption services
   - Firestore collection: `ghl_connections`

2. **GHL API Router** (`api/ghl.py`):
   - `GET /api/ghl/connections` - List all connections
   - `POST /api/ghl/connections` - Create and validate new connection
   - `PUT /api/ghl/connections/{id}` - Update connection (re-validates if token changed)
   - `DELETE /api/ghl/connections/{id}` - Delete connection
   - `POST /api/ghl/connections/{id}/validate` - Re-validate existing connection
   - `GET /api/ghl/connections/{id}/users` - Fetch GHL users for dropdown
   - `POST /api/ghl/contacts/upsert` - Upsert single contact to GHL
   - All endpoints require Firebase auth (`Depends(require_auth)`)
   - Error handling: 400 for validation, 401 for auth, 404 for not found, 429 for rate limit, 502 for GHL API errors
   - GHL error details passed through to frontend per user decision

3. **Main App Integration** (`main.py`):
   - Registered GHL router at `/api/ghl` prefix
   - Added "ghl" to health check tools list

## Deviations from Plan

None - plan executed exactly as written.

**Note:** The plan mentioned checking for `tdd="true"` attributes - none were present in this plan, so standard execution flow was used.

## Verification Results

All verification checks passed:

- ✓ Connection service imports without errors
- ✓ All 8 functions are importable (create, get, list, update, delete, validate, get_users, upsert_contact)
- ✓ GHL router has 7 routes
- ✓ GHL router is imported and registered in main.py at `/api/ghl` prefix
- ✓ encrypted_token never present in response models (always removed by service layer)
- ✓ All endpoints use `Depends(require_auth)` for authentication
- ✓ GHL error details are passed through (not normalized to generic errors)

## Task Breakdown

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create connection CRUD service with encrypted token storage | ac333c9 | services/ghl/connection_service.py |
| 2 | Create GHL API router and register in main.py | a02f64f | api/ghl.py, main.py |

## Dependencies Created

**Provides:**
- `connection_service` - Full CRUD operations for GHL connections with encryption
- `/api/ghl/*` endpoints - 7 authenticated endpoints for connection and contact management
- Connection validation - Immediate validation on create, re-validation on token update
- User listing - GHL users for contact owner dropdown
- Contact upsert - Single contact upsert via connection

**Requires:**
- `ghl_models` (from Plan 01) - Pydantic request/response models
- `ghl_client` (from Plan 01) - GHL API client with rate limiting
- `encryption_service` - Token encryption/decryption
- `firestore_service` - Firestore CRUD operations
- `auth` - Firebase auth with require_auth dependency

**Affects:**
- Plan 10 (Frontend Foundation) - Settings UI will consume these endpoints
- Plan 11+ (Bulk Send Engine) - Send flow will use connection selection and contact upsert

## Next Steps

**Immediate (Plan 10 - Frontend Foundation):**
- Create Settings page with GHL Connections tab
- Connection CRUD UI (add/edit/delete connections)
- Connection validation status display
- Send modal with connection picker and contact field mapping

**Future:**
- Bulk contact send (Plan 11+)
- Progress tracking for bulk operations
- Error handling and retry logic for failed sends

## Self-Check

Verified all created files exist:

```bash
✓ toolbox/backend/app/services/ghl/connection_service.py
✓ toolbox/backend/app/api/ghl.py
```

Verified all modified files updated:

```bash
✓ toolbox/backend/app/main.py (added ghl_router import and registration)
```

Verified all commits exist:

```bash
✓ ac333c9 (Task 1: Connection CRUD service)
✓ a02f64f (Task 2: GHL API router)
```

## Self-Check: PASSED

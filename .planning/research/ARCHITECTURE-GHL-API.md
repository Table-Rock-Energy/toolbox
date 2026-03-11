# Architecture Patterns: GHL API Integration

**Domain:** GoHighLevel API integration for existing GHL Prep tool
**Researched:** 2026-02-26

## Recommended Architecture

The GHL API integration follows the existing toolbox architecture pattern while introducing new patterns for API key management, real-time progress tracking, and partial failure handling.

```
┌──────────────────────────────────────────────────────────────────┐
│                        Frontend (React)                          │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ GhlPrep.tsx │  │ Settings.tsx │  │ SendModal.tsx (new)  │   │
│  │             │  │              │  │ - Tag input          │   │
│  │ - Upload    │  │ - API Key UI │  │ - Owner dropdown     │   │
│  │ - Preview   │  │   (new)      │  │ - SmartList name     │   │
│  │ - CSV       │  │              │  │ - Manual SMS toggle  │   │
│  │ - Send (new)│  │              │  │ - Progress bar       │   │
│  └─────────────┘  └──────────────┘  └──────────────────────┘   │
│         │                │                      │                │
│         └────────────────┴──────────────────────┘                │
│                          │                                       │
└──────────────────────────┼───────────────────────────────────────┘
                           │
                           │ HTTP (REST API)
                           │
┌──────────────────────────┼───────────────────────────────────────┐
│                          ▼                                       │
│                   FastAPI Backend                                │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              api/ghl_prep.py (modified)                   │   │
│  │  - POST /upload (existing)                                │   │
│  │  - POST /export/csv (existing)                            │   │
│  │  - POST /send-to-ghl (new) — triggers send, returns job_id│   │
│  │  - GET  /send-status/{job_id} (new) — SSE progress stream│   │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │          api/admin.py (modified for API keys)             │   │
│  │  - GET  /ghl-settings (new) — retrieve GHL API key        │   │
│  │  - PUT  /ghl-settings (new) — save encrypted GHL API key  │   │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │            models/ghl_prep.py (extended)                  │   │
│  │  - SendRequest (new) — tag, owner, smartlist, manual_sms  │   │
│  │  - SendProgress (new) — current, total, status, message   │   │
│  │  - SendResult (new) — created, updated, failed, errors    │   │
│  │  - GHLSettings (new) — encrypted_api_key, location_id     │   │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │     services/ghl_prep/ghl_api_service.py (new)            │   │
│  │  - GHLClient class                                        │   │
│  │    - upsert_contact(contact_data) → result                │   │
│  │    - get_users(location_id) → List[User]                  │   │
│  │    - create_smartlist(name, location_id) → smartlist_id   │   │
│  │    - add_to_smartlist(contact_id, smartlist_id)           │   │
│  │  - HTTP 207 Multi-Status handling for partial failures    │   │
│  │  - Retry logic with exponential backoff                   │   │
│  │  - Rate limit handling (100 req/10s burst, 200k/day)      │   │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │     services/ghl_prep/send_service.py (new)               │   │
│  │  - async send_to_ghl(rows, config, job_id)                │   │
│  │    - Batch processing (50 contacts per batch)             │   │
│  │    - Progress updates via asyncio Queue                   │   │
│  │    - Error collection with row-level detail               │   │
│  │    - Summary aggregation (created/updated/failed)         │   │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │     services/encryption_service.py (new)                  │   │
│  │  - encrypt_api_key(key) → encrypted_string                │   │
│  │  - decrypt_api_key(encrypted) → plaintext_key             │   │
│  │  - Uses Fernet symmetric encryption (config.encryption_key)│ │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │         services/firestore_service.py (extended)          │   │
│  │  - save_ghl_settings(user_id, settings) → void            │   │
│  │  - get_ghl_settings(user_id) → GHLSettings or None        │   │
│  │  - update_send_job_progress(job_id, progress) → void      │   │
│  │  - get_send_job_status(job_id) → SendProgress             │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           │ HTTPS (REST API v2)
                           │
                ┌──────────▼──────────┐
                │  GoHighLevel API v2 │
                │  - Contacts upsert  │
                │  - Users list       │
                │  - Tags management  │
                │  - SmartLists       │
                └─────────────────────┘
```

## Component Boundaries

| Component | Responsibility | Communicates With | Location |
|-----------|---------------|-------------------|----------|
| **GhlPrep.tsx** | Upload, preview, CSV export, Send to GHL button | api/ghl_prep.py, SendModal.tsx | `frontend/src/pages/GhlPrep.tsx` (modified) |
| **SendModal.tsx** | Send configuration UI, progress display, results summary | api/ghl_prep.py (send endpoints) | `frontend/src/components/SendModal.tsx` (new) |
| **Settings.tsx** | GHL API key management UI (new section) | api/admin.py (GHL settings endpoints) | `frontend/src/pages/Settings.tsx` (modified) |
| **api/ghl_prep.py** | Send to GHL routes, progress streaming endpoint | services/ghl_prep/send_service.py, ghl_api_service.py | `backend/app/api/ghl_prep.py` (modified) |
| **api/admin.py** | GHL settings CRUD (encrypted storage) | services/encryption_service.py, firestore_service.py | `backend/app/api/admin.py` (modified) |
| **ghl_api_service.py** | GoHighLevel API client wrapper | GoHighLevel API v2 (external) | `backend/app/services/ghl_prep/ghl_api_service.py` (new) |
| **send_service.py** | Orchestrate bulk send, progress tracking, error collection | ghl_api_service.py, firestore_service.py | `backend/app/services/ghl_prep/send_service.py` (new) |
| **encryption_service.py** | Encrypt/decrypt API keys using Fernet | None (crypto lib) | `backend/app/services/encryption_service.py` (new) |
| **firestore_service.py** | GHL settings persistence, send job tracking | Firestore | `backend/app/services/firestore_service.py` (extended) |

## Data Flow

### 1. API Key Setup Flow
```
User (Settings page)
  → PUT /api/admin/ghl-settings {api_key, location_id}
    → encryption_service.encrypt_api_key(api_key)
    → firestore_service.save_ghl_settings(user_id, {encrypted_key, location_id})
    → Return success

User (Settings page)
  → GET /api/admin/ghl-settings
    → firestore_service.get_ghl_settings(user_id)
    → encryption_service.decrypt_api_key(encrypted_key)
    → Return {api_key: "[REDACTED]", location_id, is_configured: true}
```

### 2. Send to GHL Flow
```
User (GhlPrep page, after transform complete)
  → Click "Send to GHL" button
    → Open SendModal
      → Fetch GHL users: GET /api/admin/ghl-users?location_id={id}
        → ghl_api_service.get_users(location_id)
        → Return [{id, name, email}]
      → User configures: tag, contact_owner_id, smartlist_name, manual_sms
      → Click "Send"
        → POST /api/ghl-prep/send-to-ghl {rows, tag, owner_id, smartlist, manual_sms}
          → Validate API key exists (check firestore_service.get_ghl_settings)
          → Generate job_id
          → Start background task: send_service.send_to_ghl(rows, config, job_id)
          → Return {job_id, status: "started"}
        → Frontend opens EventSource: GET /api/ghl-prep/send-status/{job_id}
          → Stream progress updates via SSE as send_service processes batches
          → Progress format: {current: 50, total: 200, status: "processing", message: "Batch 1/4"}
          → Final message: {status: "complete", result: {created: 150, updated: 40, failed: 10, errors: [...]}}
        → Display summary modal with counts and failed rows
```

### 3. Background Send Process (send_service.py)
```
send_to_ghl(rows, config, job_id):
  1. Initialize progress tracker in Firestore
  2. Split rows into batches (50 per batch to respect rate limits)
  3. For each batch:
     a. For each row in batch:
        - Map row to GHL contact schema
        - ghl_api_service.upsert_contact(contact_data)
        - Collect result (success/failure)
     b. Update progress: firestore_service.update_send_job_progress(job_id, {current, total, message})
     c. Sleep if approaching rate limit (100 req/10s)
  4. Aggregate results (created, updated, failed counts)
  5. Persist final result to Firestore
  6. Mark job as complete
```

## Patterns to Follow

### Pattern 1: Server-Sent Events for Progress Tracking
**What:** Use SSE (not WebSocket or polling) for real-time progress updates during bulk send operations.

**When:** User initiates a long-running send operation with 100+ contacts.

**Why SSE:**
- Unidirectional (server → client only) — perfect for progress updates
- Built-in reconnection logic — handles network interruptions
- Simpler than WebSocket — no need for bidirectional communication
- HTTP-based — works through proxies and firewalls
- Native browser EventSource API — no extra libraries

**Example:**
```python
# backend/app/api/ghl_prep.py
from fastapi.responses import StreamingResponse
import asyncio

@router.get("/send-status/{job_id}")
async def stream_send_status(job_id: str):
    """Stream real-time progress updates via Server-Sent Events."""
    async def event_stream():
        while True:
            # Check Firestore for progress updates
            progress = await firestore_service.get_send_job_status(job_id)

            # Send SSE event
            yield f"data: {json.dumps(progress.dict())}\n\n"

            if progress.status in ["complete", "failed"]:
                break

            await asyncio.sleep(0.5)  # Poll every 500ms

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )
```

```typescript
// frontend/src/components/SendModal.tsx
const streamProgress = (jobId: string) => {
  const eventSource = new EventSource(`${API_BASE}/ghl-prep/send-status/${jobId}`)

  eventSource.onmessage = (event) => {
    const progress = JSON.parse(event.data)
    setProgress(progress)

    if (progress.status === 'complete' || progress.status === 'failed') {
      eventSource.close()
      if (progress.status === 'complete') {
        showSummaryModal(progress.result)
      }
    }
  }

  eventSource.onerror = () => {
    eventSource.close()
    setError('Connection lost. Progress may continue in background.')
  }
}
```

### Pattern 2: HTTP 207 Multi-Status for Partial Failures
**What:** Return HTTP 207 with per-item status for bulk operations where some contacts succeed and some fail.

**When:** Upserting multiple contacts to GHL where validation/duplicate/permission errors may affect individual contacts.

**Why:**
- Standard REST pattern for bulk operations
- Distinguishes between request-level errors (4xx/5xx) and item-level errors
- Provides detailed error context per failed item
- Client can retry only failed items

**Example:**
```python
# services/ghl_prep/ghl_api_service.py
class GHLClient:
    async def upsert_contacts_batch(self, contacts: list[dict]) -> dict:
        """
        Upsert multiple contacts, return detailed results.

        Returns:
            {
                "status": 207,
                "results": [
                    {"index": 0, "contact_id": "abc123", "status": "created"},
                    {"index": 1, "contact_id": "def456", "status": "updated"},
                    {"index": 2, "status": "failed", "error": "Invalid email"},
                ]
            }
        """
        results = []
        for idx, contact in enumerate(contacts):
            try:
                response = await self._upsert_single(contact)
                results.append({
                    "index": idx,
                    "contact_id": response["id"],
                    "status": response["status"],  # "created" or "updated"
                })
            except Exception as e:
                results.append({
                    "index": idx,
                    "status": "failed",
                    "error": str(e),
                    "row_data": contact,  # Include for retry/debugging
                })

        return {"status": 207, "results": results}
```

### Pattern 3: Encrypted API Key Storage
**What:** Store GHL Private Integration Token encrypted in Firestore, decrypt only when needed for API calls.

**When:** User saves API key in Settings page.

**Why:**
- Security best practice — keys never stored in plaintext
- Fernet symmetric encryption is fast and secure
- Encryption key lives in environment variable (not in codebase)
- Per-user storage in Firestore enables multi-user support

**Example:**
```python
# services/encryption_service.py
from cryptography.fernet import Fernet
from app.core.config import settings

class EncryptionService:
    def __init__(self):
        if not settings.encryption_key:
            raise ValueError("ENCRYPTION_KEY not configured")
        self.cipher = Fernet(settings.encryption_key.encode())

    def encrypt_api_key(self, plaintext: str) -> str:
        """Encrypt API key for storage."""
        return self.cipher.encrypt(plaintext.encode()).decode()

    def decrypt_api_key(self, encrypted: str) -> str:
        """Decrypt API key for use."""
        return self.cipher.decrypt(encrypted.encode()).decode()

encryption_service = EncryptionService()
```

### Pattern 4: Rate Limit Awareness with Batch Processing
**What:** Process contacts in batches of 50, track request count, sleep if approaching limits.

**When:** Sending 100+ contacts to GHL.

**Why:**
- GHL limits: 100 req/10s burst, 200k/day per app
- Batching reduces memory usage and enables progress updates
- Sleep prevents hitting rate limits and getting 429 errors
- Request tracking enables cost estimation and quota monitoring

### Pattern 5: Single Endpoint for Send (Not Multiple)
**What:** Single POST /send-to-ghl endpoint that returns job_id immediately, processes in background.

**When:** User clicks "Send" in modal.

**Why:**
- Avoids request timeout for large datasets (FastAPI default timeout is 30s)
- Frontend gets immediate response, can start progress stream
- Background task can run indefinitely
- Simpler error handling — initial request only validates inputs

## Anti-Patterns to Avoid

### Anti-Pattern 1: Storing Plaintext API Keys
**What goes wrong:** API keys stored in Firestore without encryption expose credentials if database is compromised.

**Why it happens:** Encryption adds complexity, developers skip it for MVP.

**Consequences:** Security breach, unauthorized access to GHL account, compliance violations.

**Prevention:** Always encrypt API keys with Fernet before storing. Add encryption_key to config.py (loaded from env var).

### Anti-Pattern 2: Polling for Progress Instead of SSE
**What goes wrong:** Frontend polls GET /send-status/{job_id} every second, creating 100s of unnecessary requests.

**Why it happens:** Polling is simpler to implement than SSE.

**Consequences:** Higher latency (1s intervals vs real-time), increased server load, slower progress updates.

**Prevention:** Use SSE (FastAPI StreamingResponse + EventSource) for real-time push.

### Anti-Pattern 3: Synchronous Send Blocking Request
**What goes wrong:** POST /send-to-ghl processes all 500 contacts synchronously, request times out after 30s.

**Why it happens:** Trying to return final result in single request.

**Consequences:** Request timeout, partial data loss, no progress visibility, poor UX.

**Prevention:** Return job_id immediately, use BackgroundTasks for processing, stream progress via SSE.

### Anti-Pattern 4: Not Handling Partial Failures
**What goes wrong:** One contact fails validation, entire batch of 200 contacts is rejected.

**Why it happens:** All-or-nothing error handling, no per-item error collection.

**Consequences:** Good data is blocked by bad data, user can't identify which rows failed, manual cleanup required.

**Prevention:** Collect errors per row, continue processing remaining rows, return detailed error report.

### Anti-Pattern 5: Hardcoding API Keys in Frontend
**What goes wrong:** API key stored in localStorage or React state, visible in browser DevTools.

**Why it happens:** Quick prototyping, misunderstanding of client-side security.

**Consequences:** API key exposed to users, can be extracted and misused, violates GHL security requirements.

**Prevention:** Store API keys server-side only (encrypted in Firestore), never send to frontend.

## Integration Points

### Existing Components (Modified)

| Component | Change Type | Details |
|-----------|-------------|---------|
| `frontend/src/pages/GhlPrep.tsx` | **Modified** | Add "Send to GHL" button next to "Download CSV" button. Button opens SendModal. |
| `frontend/src/pages/Settings.tsx` | **Modified** | Add "GoHighLevel Integration" section with API key input field, location ID input, "Test Connection" button. |
| `backend/app/api/ghl_prep.py` | **Modified** | Add POST /send-to-ghl, GET /send-status/{job_id} endpoints. |
| `backend/app/api/admin.py` | **Modified** | Add GET /ghl-settings, PUT /ghl-settings, GET /ghl-users endpoints. |
| `backend/app/models/ghl_prep.py` | **Modified** | Add SendRequest, SendProgress, SendResult, GHLSettings Pydantic models. |
| `backend/app/services/firestore_service.py` | **Modified** | Add save_ghl_settings, get_ghl_settings, create_send_job, update_send_job_progress, get_send_job_status functions. |
| `backend/app/core/config.py` | **Modified** | Add ghl_enabled (bool), encryption_key (str) settings. |

### New Components

| Component | Type | Purpose |
|-----------|------|---------|
| `frontend/src/components/SendModal.tsx` | **New** | Modal for configuring send parameters (tag, owner, smartlist, manual SMS). Displays progress bar during send, shows summary modal on completion. |
| `backend/app/services/ghl_prep/ghl_api_service.py` | **New** | GHLClient wrapper for GoHighLevel API v2. Methods: upsert_contact, get_users, create_smartlist, add_to_smartlist. Handles auth headers, rate limits, retries. |
| `backend/app/services/ghl_prep/send_service.py` | **New** | Orchestrates bulk send with batch processing, progress tracking, error collection. Main function: send_to_ghl(rows, config, job_id). |
| `backend/app/services/encryption_service.py` | **New** | Fernet-based encryption/decryption for API keys. Functions: encrypt_api_key, decrypt_api_key. |

### External Dependencies (New)

| Dependency | Purpose | Version |
|------------|---------|---------|
| `cryptography` (Python) | Fernet symmetric encryption for API keys | 42.x |
| `httpx` (Python) | Async HTTP client for GHL API calls (if not already installed) | 0.27.x |

## Suggested Build Order (Dependency-Driven)

### Phase 1: Foundation (API Key Management)
**Goal:** Users can store and retrieve GHL API key securely.

1. Backend config — Add encryption_key, ghl_enabled to config.py
2. Encryption service — Create encryption_service.py with encrypt/decrypt functions
3. Pydantic models — Add GHLSettings model to models/ghl_prep.py
4. Firestore extension — Add save_ghl_settings, get_ghl_settings to firestore_service.py
5. Admin API — Add GET/PUT /ghl-settings endpoints to api/admin.py
6. Settings UI — Add "GoHighLevel Integration" section to Settings.tsx with API key input
7. Test — Manually verify: save key → encrypted in Firestore → retrieve → [CONFIGURED] shown

**Deliverable:** Users can configure GHL API key in Settings page, key is stored encrypted in Firestore.

### Phase 2: GHL API Client
**Goal:** Backend can communicate with GoHighLevel API.

1. GHL models — Add User, Contact, UpsertResult models to models/ghl_prep.py
2. GHL client service — Create services/ghl_prep/ghl_api_service.py with GHLClient class
3. Implement methods: get_users, upsert_contact, create_smartlist
4. Test Connection endpoint — Add GET /admin/ghl-test-connection
5. Test — Settings page "Test Connection" button calls endpoint

**Deliverable:** Backend can authenticate with GHL API, fetch users, upsert contacts.

### Phase 3: Send Modal UI
**Goal:** Frontend UI for configuring send parameters.

1. SendRequest model — Add to models/ghl_prep.py
2. Send modal component — Create components/SendModal.tsx
3. Modal sections: tag input, contact owner dropdown, smartlist name, manual SMS toggle
4. Integrate — Add "Send to GHL" button to GhlPrep.tsx
5. Test — Modal opens, dropdowns populate, form validates

**Deliverable:** Users can click "Send to GHL", configure parameters in modal.

### Phase 4: Bulk Send Engine
**Goal:** Backend can send contacts in batches with progress tracking.

1. Send models — Add SendProgress, SendResult to models/ghl_prep.py
2. Send service — Create services/ghl_prep/send_service.py
3. Batch processing logic with rate limiting
4. Firestore tracking — Add create_send_job, update_send_job_progress
5. Send endpoint — Add POST /ghl-prep/send-to-ghl
6. Test — Manually trigger send, check Firestore for progress

**Deliverable:** Backend can send contacts to GHL in batches, track progress in Firestore.

### Phase 5: Real-Time Progress (SSE)
**Goal:** Frontend displays live progress bar during send.

1. SSE endpoint — Add GET /ghl-prep/send-status/{job_id}
2. Progress component — Add progress bar to SendModal.tsx
3. EventSource integration — Frontend opens EventSource on send
4. Auto-close — Close EventSource when status === "complete"
5. Test — Send 100 contacts, watch progress bar update

**Deliverable:** Users see real-time progress bar during send, summary modal on completion.

### Phase 6: Error Handling & Summary
**Goal:** Users see which contacts succeeded/failed with detailed error messages.

1. Error collection — send_service.py collects per-row errors
2. Summary modal — Add summary section to SendModal.tsx
3. Failed rows table — Show table with error messages, "Download Failed Rows" button
4. Test — Send dataset with errors, verify failed rows shown

**Deliverable:** Users see summary (150 created, 40 updated, 10 failed), can download failed rows.

### Phase 7: Polish & Edge Cases
**Goal:** Production-ready error handling, logging, documentation.

1. Error messages — User-friendly messages for common failures
2. Loading states — Disable "Send" button during processing
3. Reconnection logic — Handle SSE connection drops
4. Logging — Comprehensive logs in send_service.py
5. Documentation — Update Help.tsx with GHL integration instructions
6. Test — Manual QA with edge cases

**Deliverable:** Production-ready integration with robust error handling.

## New vs Modified Files

### New Files (4 total)
1. `frontend/src/components/SendModal.tsx` — Send configuration modal with progress bar
2. `backend/app/services/ghl_prep/ghl_api_service.py` — GoHighLevel API client
3. `backend/app/services/ghl_prep/send_service.py` — Bulk send orchestration
4. `backend/app/services/encryption_service.py` — API key encryption/decryption

### Modified Files (7 total)
1. `frontend/src/pages/GhlPrep.tsx` — Add "Send to GHL" button
2. `frontend/src/pages/Settings.tsx` — Add GHL API key section
3. `backend/app/api/ghl_prep.py` — Add send endpoints + SSE
4. `backend/app/api/admin.py` — Add GHL settings endpoints
5. `backend/app/models/ghl_prep.py` — Add new Pydantic models
6. `backend/app/services/firestore_service.py` — Add GHL settings + send job tracking
7. `backend/app/core/config.py` — Add encryption_key setting

### Total File Count
- **New:** 4 files
- **Modified:** 7 files
- **Total changes:** 11 files

## Questions for Validation

1. **API Key Rotation:** Should we support multiple API keys per user (e.g., dev/prod environments)? Current design assumes single key per user.
2. **SmartList Creation:** Should we auto-create SmartList if it doesn't exist, or fail with error? Current plan: create on demand.
3. **Duplicate Contact Strategy:** GHL "Allow Duplicate Contact" setting affects upsert behavior. Should we expose this in UI or rely on location-level config?
4. **Tag Behavior:** Should we append tags to existing contact tags or replace? Current plan: append (GHL default).
5. **Manual SMS:** Does this require additional GHL API permissions? Needs verification.
6. **Cost Tracking:** Should we track GHL API usage per user for quota monitoring? Not in current plan but easy to add.
7. **Retry Failed:** Should v1.2 include "Retry Failed" button, or defer to v1.3? Current plan: defer (show failed rows only).

## Sources

- [GoHighLevel API v2 Documentation](https://marketplace.gohighlevel.com/docs/)
- [Upsert Contact Endpoint](https://marketplace.gohighlevel.com/docs/ghl/contacts/upsert-contact/index.html)
- [Private Integration Token Setup](https://help.gohighlevel.com/support/solutions/articles/155000003054-private-integrations-everything-you-need-to-know)
- [GoHighLevel API v2 GitHub Repository](https://github.com/GoHighLevel/highlevel-api-docs)
- [How to Handle Partial Success in Bulk API Operations](https://oneuptime.com/blog/post/2026-02-02-rest-bulk-api-partial-success/view)
- [Real-Time Notifications in Python: Using SSE with FastAPI](https://medium.com/@inandelibas/real-time-notifications-in-python-using-sse-with-fastapi-1c8c54746eb7)
- [FastAPI Best Practices for Production: Complete 2026 Guide](https://fastlaunchapi.dev/blog/fastapi-best-practices-production-2026)
- [API Key Management Best Practices for Secure Services](https://oneuptime.com/blog/post/2026-02-20-api-key-management-best-practices/view)
- [WebSocket vs SSE vs Long Polling: Choosing Real-time in 2025](https://potapov.me/en/make/websocket-sse-longpolling-realtime)
- [FastAPI Error Handling Patterns](https://betterstack.com/community/guides/scaling-python/error-handling-fastapi/)

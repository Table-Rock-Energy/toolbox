# Feature Research: GoHighLevel API Integration

**Domain:** GoHighLevel API Integration for Direct Contact Push
**Researched:** 2026-02-26
**Confidence:** HIGH

**Context:** This research covers the NEW API integration features being added to the EXISTING GHL Prep tool (v1.1 → v1.2). The existing GHL Prep transformations (title-case, campaign extraction, phone mapping, etc.) are already built and documented in FEATURES.md. This document focuses ONLY on what's needed for direct API push to GHL.

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| API token management | Every API integration needs auth config | LOW | Store Private Integration Token in Settings, encrypted in Firestore |
| Upsert contacts | Core GHL operation, replaces manual CSV import | MEDIUM | POST `/contacts/upsert`, respects location-level duplicate detection settings |
| Contact owner assignment | Teams need contact ownership for follow-up | LOW | Use `assignedTo` field with user ID from `/users/` endpoint |
| Progress indicator | Users need to see API calls happening (not silent) | LOW | Real-time progress bar during batch send operation |
| Send summary | Users need confirmation of what happened | LOW | Modal showing created/updated/failed counts with error details |
| Tag assignment | GHL relies heavily on tags for segmentation | LOW | POST `/contacts/:contactId/tags` to add tags during upsert |
| Error handling | API calls fail, users need to know why | MEDIUM | Capture HTTP errors (400/401/422), retry logic, user-friendly messages |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not required, but valuable.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Batch operation with rate limiting | Reliable bulk send without hitting API limits | MEDIUM | Handle 100 requests per 10s burst limit, 200k/day limit, throttle automatically |
| Pre-flight validation | Catch errors before sending to GHL | LOW | Validate required fields (email/phone), check token before batch operation |
| Contact owner dropdown | Eliminates manual user ID lookup | LOW | Fetch users via GET `/users/`, populate dropdown in send modal |
| Selective retry | Re-send only failed contacts | MEDIUM | Track failed items, allow user to retry with fixes |
| Send configuration presets | Save common send settings (tag, owner, SmartList) | LOW | Store presets in Firestore under user settings |
| Duplicate detection preview | Show which contacts will merge vs create | HIGH | Query GHL API before upsert to preview matches (complex due to location-level dedup settings) |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Direct SmartList assignment | Users want to add contacts to SmartLists via API | SmartLists are filter-based, not manual membership lists. No direct API to add contacts to SmartList. | Assign tags that match SmartList filter criteria. Document SmartList creation in Help page. |
| Real-time sync on every edit | Feels modern, keeps GHL always updated | Creates excessive API calls, burns rate limits quickly, complex state management | Batch send after CSV is finalized. Manual trigger gives user control. |
| Automatic tag cleanup | Remove old tags when sending new contacts | Risk of data loss, users may have tags in GHL that shouldn't be touched | Additive only - add new tags without removing existing ones |
| Full contact history import | Import all historical data from Mineral to GHL | GHL API has rate limits (200k/day), historical data may not match current GHL schema | Focus on new/updated contacts only. Historical import is one-time manual task. |

## Feature Dependencies

```
[API Token Management]
    └──requires──> [Settings UI]
                       └──requires──> [Firestore persistence]

[Send to GHL Button]
    └──requires──> [API Token Management]
    └──requires──> [GHL API Service]
                       └──requires──> [Rate Limiting Logic]

[Contact Owner Dropdown]
    └──requires──> [List Users API]
                       └──requires──> [API Token Management]

[Send Modal]
    └──requires──> [Contact Owner Dropdown]
    └──requires──> [Tag Input]
    └──requires──> [Send to GHL Button]

[Progress Indicator]
    └──requires──> [Send to GHL Button]
    └──enhances──> [Send Summary]

[Selective Retry]
    └──requires──> [Send Summary]
    └──requires──> [Error Tracking]
```

### Dependency Notes

- **API Token Management requires Settings UI:** Token must be stored before any GHL API calls can be made. Settings page already exists, just needs new section for GHL API configuration.
- **Send to GHL requires GHL API Service:** Backend service handles authentication, rate limiting, and error handling. Core infrastructure for all GHL features.
- **Contact Owner Dropdown requires List Users API:** Must fetch GHL users before displaying dropdown. Empty list acceptable fallback if API fails.
- **Send Modal requires Contact Owner Dropdown:** Modal coordinates all send configuration (tag, owner, SmartList name, manual SMS checkbox).
- **Selective Retry requires Send Summary:** Users need to see what failed before choosing to retry.

## MVP Definition

### Launch With (v1.2)

Minimum viable product for GHL API integration milestone.

- [ ] **API Token Management** — Users must configure Private Integration Token before sending (Settings page)
- [ ] **GHL API Service** — Backend service with authentication, rate limiting, error handling (`services/ghl_api_service.py`)
- [ ] **Upsert Contacts Endpoint** — Core API call to create/update contacts in GHL (`POST /contacts/upsert`)
- [ ] **Add Tags Endpoint** — Apply tags during contact upsert (`POST /contacts/:contactId/tags`)
- [ ] **List Users Endpoint** — Fetch GHL users for contact owner dropdown (`GET /users/`)
- [ ] **Send to GHL Button** — New button on GHL Prep results page alongside Download CSV
- [ ] **Send Modal** — Configuration UI for tag, contact owner, SmartList name, manual SMS checkbox
- [ ] **Progress Indicator** — Real-time progress bar during batch send
- [ ] **Send Summary** — Modal with created/updated/failed counts after send completes

### Add After Validation (v1.x)

Features to add once core integration is working and user feedback is collected.

- [ ] **Pre-flight Validation** — Validate required fields and token before batch operation (trigger: users report confusing errors during send)
- [ ] **Selective Retry** — Re-send only failed contacts with fixes (trigger: users report partial failures)
- [ ] **Send Configuration Presets** — Save common send settings (trigger: users report repetitive configuration)
- [ ] **Enhanced Error Details** — Show specific error per contact in summary modal (trigger: users need to debug individual failures)

### Future Consideration (v2+)

Features to defer until GHL integration is proven valuable.

- [ ] **Duplicate Detection Preview** — Show merge vs create preview before send (why defer: complex, requires additional GHL API calls, unclear user value)
- [ ] **Bulk Tag Management** — Remove tags from contacts (why defer: additive-only is safer, unclear demand)
- [ ] **Scheduled Sends** — Schedule batch send for future time (why defer: no current user request, adds complexity)
- [ ] **GHL Workflow Triggers** — Automatically trigger GHL workflows after contact creation (why defer: requires advanced GHL configuration, power user feature)

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| API Token Management | HIGH | LOW | P1 |
| GHL API Service | HIGH | MEDIUM | P1 |
| Upsert Contacts | HIGH | MEDIUM | P1 |
| Add Tags | HIGH | LOW | P1 |
| List Users | HIGH | LOW | P1 |
| Send to GHL Button | HIGH | LOW | P1 |
| Send Modal | HIGH | LOW | P1 |
| Progress Indicator | HIGH | LOW | P1 |
| Send Summary | HIGH | LOW | P1 |
| Pre-flight Validation | MEDIUM | LOW | P2 |
| Selective Retry | MEDIUM | MEDIUM | P2 |
| Send Configuration Presets | MEDIUM | LOW | P2 |
| Enhanced Error Details | MEDIUM | LOW | P2 |
| Duplicate Detection Preview | LOW | HIGH | P3 |
| Bulk Tag Management | LOW | MEDIUM | P3 |
| Scheduled Sends | LOW | MEDIUM | P3 |
| GHL Workflow Triggers | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have for launch (v1.2)
- P2: Should have, add when possible (v1.x)
- P3: Nice to have, future consideration (v2+)

## GHL API Specifics

### Authentication

**Private Integration Token** authentication via `Authorization` header:

```http
Authorization: Bearer <PRIVATE_INTEGRATION_TOKEN>
Version: 2021-07-28
Content-Type: application/json
Accept: application/json
```

**Token management:**
- Static tokens, don't auto-refresh (unlike OAuth)
- Rotate every 90 days recommended (7-day overlap period during rotation)
- Scopes/permissions configurable per token at creation time
- Store encrypted in Firestore under user settings collection
- Never log or expose token in API responses

**Security notes:**
- Rotate immediately if compromised
- Share only with trusted parties
- Don't commit to version control
- Can modify scopes without regenerating token

### Contact Upsert

**Endpoint:** `POST https://rest.gohighlevel.com/v1/contacts/upsert`

**Request body:**
```json
{
  "firstName": "John",
  "lastName": "Doe",
  "email": "john.doe@example.com",
  "phone": "+14155551234",
  "locationId": "LOCATION_ID",
  "assignedTo": "USER_ID",
  "tags": ["Lead", "Mineral"],
  "customField": {
    "campaign": "Prospect List 2026",
    "source": "Mineral Export"
  }
}
```

**Required fields:**
- At least one of: `email`, `phone`, or full name (`firstName` + `lastName`)
- `locationId` (always required, identifies the sub-account)

**Optional fields:**
- `firstName`, `lastName`, `name` (full name)
- `email`, `phone`
- `address`, `city`, `state`, `postalCode`, `country`
- `assignedTo` (user ID for contact owner)
- `tags` (array of tag names)
- `customField` (object with custom field key-value pairs)
- `businessName`, `source`, `type`, `dateOfBirth`, `timezone`, `website`, `dnd`

**Deduplication logic:**
- Respects location-level "Allow Duplicate Contact" setting in GHL
- If enabled to check both email AND phone, uses priority sequence configured in GHL
- If two separate contacts exist (one with email match, one with phone match), updates the contact matching the first field in configured sequence
- If no match found, creates new contact
- **Key insight:** Dedup behavior is controlled by GHL settings, not API parameters

**Response codes:**
- **200:** Success (contact created or updated)
- **400:** Bad Request (invalid parameters, malformed JSON)
- **401:** Unauthorized (invalid or expired token)
- **422:** Unprocessable Entity (validation error, e.g., invalid email format)

**Response body (success):**
```json
{
  "contact": {
    "id": "CONTACT_ID",
    "locationId": "LOCATION_ID",
    "firstName": "John",
    "lastName": "Doe",
    "email": "john.doe@example.com",
    "phone": "+14155551234",
    "tags": ["Lead", "Mineral"],
    "createdAt": "2026-02-26T12:00:00Z",
    "updatedAt": "2026-02-26T12:00:00Z"
  }
}
```

### Add Tags

**Endpoint:** `POST https://rest.gohighlevel.com/v1/contacts/:contactId/tags`

**Request body:**
```json
{
  "tags": ["Lead", "Mineral", "2026-Q1"]
}
```

**Behavior:**
- Adds tags to existing contact (additive operation)
- Does not remove existing tags
- Creates tags if they don't exist in location
- Idempotent (adding same tag twice has no effect)

**Response codes:**
- **201:** Tags added successfully
- **400:** Bad Request (invalid request format)
- **401:** Unauthorized (invalid token)
- **422:** Unprocessable Entity (validation error)

**Alternative approach:**
- Tags can be included in upsert request body directly (simpler)
- Use separate tag endpoint only if updating tags post-creation

### Remove Tags

**Endpoint:** `DELETE https://rest.gohighlevel.com/v1/contacts/:contactId/tags`

**Request body:**
```json
{
  "tags": ["OldTag"]
}
```

**Behavior:**
- Removes specified tags from contact
- Does not affect other tags
- No error if tag doesn't exist on contact

**Response codes:**
- **200:** Tags removed successfully
- **400:** Bad Request
- **401:** Unauthorized
- **422:** Unprocessable Entity

**Note:** For v1.2, we're doing additive-only (no tag removal). This endpoint documented for future use.

### List Users

**Endpoint:** `GET https://rest.gohighlevel.com/v1/users/`

**Query parameters:**
- Location filtering may be supported (check API docs for exact parameter name)

**Response:**
```json
{
  "users": [
    {
      "id": "USER_ID",
      "name": "John Smith",
      "email": "john@tablerocktx.com",
      "role": "Admin"
    },
    {
      "id": "USER_ID_2",
      "name": "Jane Doe",
      "email": "jane@tablerocktx.com",
      "role": "User"
    }
  ]
}
```

**Response codes:**
- **200:** Success
- **400:** Bad Request
- **401:** Unauthorized

**Usage:**
- Fetch on modal open or on page load
- Cache for session (users list rarely changes)
- Populate dropdown with user name + email
- Store user ID in send configuration

### Rate Limits

**Burst limit:** 100 API requests per 10 seconds per resource (Location or Company)
**Daily limit:** 200,000 API requests per day per resource

**Response headers:**
```http
X-RateLimit-Remaining: 95
X-RateLimit-Daily-Remaining: 199850
```

**429 Too Many Requests response:**
```json
{
  "error": "Rate limit exceeded",
  "retryAfter": 10
}
```

**Implementation strategy:**
1. **Monitor rate limit headers:** Track remaining burst and daily limits
2. **Throttle requests:** Add 100-150ms delay between requests (target: 8-10 requests/second)
3. **Exponential backoff:** On 429, wait `retryAfter` seconds (or 10s default) before retry
4. **Daily usage tracking:** Count requests per day, warn user at 80% threshold (160k requests)
5. **Batch size:** For GHL Prep, typical batch is 50-500 contacts (well within limits)

**Rate limit math:**
- 100 contacts at 10 req/s = 10 seconds
- 500 contacts at 10 req/s = 50 seconds
- 1000 contacts at 10 req/s = 100 seconds (1.7 minutes)

**Edge cases:**
- If user sends 10k+ contacts, show warning about time estimate
- If daily limit reached, show error and suggest waiting until next day
- Provide "pause/resume" for very large batches

### Bulk Operations

**Bulk tag updates endpoint:** `POST https://rest.gohighlevel.com/v1/contacts/bulk/tags`

**Capabilities:**
- Add/remove tags for multiple contacts at once
- No specific batch size limit documented in API docs

**Why we're NOT using bulk endpoints for v1.2:**
1. **Better error granularity:** Individual upsert calls let us track which specific contact failed
2. **Progress visibility:** Can show per-contact progress (10/100 completed)
3. **Rate limit compliance:** Individual calls easier to throttle than bulk batches
4. **Retry logic:** Can retry individual failures without resending entire batch

**Future consideration:**
- If users request faster send times, investigate bulk endpoints
- May need to trade error granularity for speed

## Integration with Existing GHL Prep Tool

**Existing GHL Prep transformations** (already built in v1.1):
1. Title-case name formatting with Mc/Mac/O' handling
2. Campaign extraction from Mineral export (JSON → plain text)
3. Phone number mapping (Phone 1 → Phone)
4. Contact owner column handling
5. Name splitting (full name → firstName/lastName)

**How API integration builds on existing:**

```
┌─────────────────────────────────────────────────┐
│ EXISTING (v1.1): GHL Prep Tool                  │
├─────────────────────────────────────────────────┤
│ 1. User uploads Mineral export CSV              │
│ 2. Backend applies transformations              │
│    - Title-case names                           │
│    - Extract campaign from JSON                 │
│    - Map Phone 1 → Phone                        │
│    - Split full name → first/last               │
│ 3. Frontend displays DataTable with results     │
│ 4. User clicks "Download CSV"                   │
│ 5. Manual import to GHL via UI                  │
└─────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│ NEW (v1.2): GHL API Integration                 │
├─────────────────────────────────────────────────┤
│ 1-3. [Same as above - reuse existing flow]      │
│ 4a. User clicks "Send to GHL" button (NEW)      │
│ 5a. Send modal opens (NEW)                      │
│     - Tag input field                           │
│     - Contact owner dropdown (from GHL users)   │
│     - SmartList name field                      │
│     - Manual SMS checkbox                       │
│ 6a. User clicks "Send" in modal (NEW)           │
│ 7a. Backend sends to GHL API (NEW)              │
│     - Batch upsert with rate limiting           │
│     - Real-time progress updates via WebSocket  │
│ 8a. Frontend shows summary modal (NEW)          │
│     - X contacts created                        │
│     - Y contacts updated                        │
│     - Z contacts failed (with error details)    │
└─────────────────────────────────────────────────┘
```

**Key insight:** All data transformation logic is reused. API integration is a new export path alongside the existing CSV download. Both paths share the same transformed data.

**Data flow:**
```
Mineral CSV
    ↓
[Upload to GHL Prep]
    ↓
[Transform (existing v1.1 logic)]
    ↓
[Display in DataTable]
    ↓
    ├──> [Download CSV] (existing)
    └──> [Send to GHL] (NEW v1.2)
              ↓
         [GHL API Service]
              ↓
         [GHL Platform]
```

## Competitor Feature Analysis

| Feature | Manual CSV Import (Current v1.1) | Zapier GHL Integration | Our Approach (v1.2) |
|---------|----------------------------------|------------------------|---------------------|
| Contact upsert | Manual download CSV, then upload in GHL UI | Trigger-based, one-at-a-time via workflow | Direct batch API push from results page |
| Tag assignment | Manual tagging in GHL after import, or via CSV Tags column | Per-trigger configuration in Zap setup | Configure once per batch in send modal |
| Contact owner | Manual assignment in GHL or via CSV column | Static assignment per Zap | Dropdown populated from GHL users API, select per batch |
| Progress visibility | None (silent file import in GHL) | Zap history (delayed, hard to interpret) | Real-time progress bar with live count (X/Y contacts sent) |
| Error handling | Generic "import failed" in GHL UI | Zap errors in history (requires debugging individual runs) | Detailed summary modal with per-contact errors and retry option |
| Retry failed | Must fix CSV and re-upload entire file | Replay Zap (loses context, hard to target specific failures) | Selective retry of failed contacts only (future v1.x) |
| Setup complexity | None (just upload CSV) | Requires Zapier account, Zap configuration, trigger setup | One-time API token in Settings, then simple modal per send |

**Competitive advantage:**
- **Faster than manual CSV:** No download/upload round-trip, saves 30-60 seconds per batch
- **More visible than Zapier:** Real-time progress vs delayed history logs
- **Better error handling than both:** Specific per-contact errors vs generic failures
- **Retains CSV option:** Fallback if API is down or user prefers manual control

## Implementation Notes

### Backend Architecture

**New service:** `backend/app/services/ghl_api_service.py`

```python
class GHLAPIService:
    """GoHighLevel API v2 client with rate limiting."""

    def __init__(self, api_token: str):
        self.api_token = api_token
        self.base_url = "https://rest.gohighlevel.com/v1"
        self.rate_limiter = RateLimiter(burst=100, window=10)

    async def upsert_contact(self, contact_data: dict) -> dict:
        """Upsert single contact with rate limit handling."""
        pass

    async def add_tags(self, contact_id: str, tags: list[str]) -> dict:
        """Add tags to contact."""
        pass

    async def list_users(self, location_id: str) -> list[dict]:
        """Fetch users for location."""
        pass

    async def batch_upsert_contacts(
        self,
        contacts: list[dict],
        progress_callback: callable
    ) -> dict:
        """Batch upsert with progress tracking."""
        pass
```

**New API route:** `backend/app/api/ghl.py`

```python
@router.post("/api/ghl/send")
async def send_to_ghl(
    contacts: list[dict],
    tag: str,
    contact_owner_id: str,
    smartlist_name: str,
    manual_sms: bool,
    current_user: User = Depends(get_current_user)
):
    """Send transformed contacts to GHL via API."""
    # Get user's GHL API token from Firestore
    # Validate token and contacts
    # Call batch_upsert_contacts with progress WebSocket
    # Return summary
    pass

@router.get("/api/ghl/users")
async def get_ghl_users(current_user: User = Depends(get_current_user)):
    """Fetch GHL users for dropdown."""
    pass
```

**Rate limiting logic:** (in `ghl_api_service.py`)

```python
class RateLimiter:
    """Token bucket rate limiter for GHL API."""

    def __init__(self, burst: int = 100, window: int = 10):
        self.burst = burst  # 100 requests per window
        self.window = window  # 10 seconds
        self.tokens = burst
        self.last_refill = time.time()

    async def acquire(self):
        """Wait until token available, then consume."""
        while self.tokens <= 0:
            await self._refill()
            await asyncio.sleep(0.1)
        self.tokens -= 1

    async def _refill(self):
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        if elapsed >= self.window:
            self.tokens = self.burst
            self.last_refill = now
```

### Frontend Changes

**New component:** `frontend/src/components/SendToGHLModal.tsx`

```typescript
interface SendToGHLModalProps {
  contacts: Contact[];
  onSend: (config: SendConfig) => Promise<void>;
  onClose: () => void;
}

function SendToGHLModal({ contacts, onSend, onClose }: SendToGHLModalProps) {
  const [tag, setTag] = useState('');
  const [contactOwner, setContactOwner] = useState('');
  const [smartlistName, setSmartlistName] = useState('');
  const [manualSMS, setManualSMS] = useState(false);
  const [users, setUsers] = useState<User[]>([]);

  // Fetch users on mount
  // Render modal with form fields
  // Handle send button click
}
```

**Modified page:** `frontend/src/pages/GHLPrep.tsx`

```typescript
// Add "Send to GHL" button next to "Download CSV"
<button onClick={handleSendToGHL}>
  <Upload className="w-5 h-5" />
  Send to GHL
</button>

// Show SendToGHLModal when button clicked
{showSendModal && (
  <SendToGHLModal
    contacts={transformedData}
    onSend={handleSend}
    onClose={() => setShowSendModal(false)}
  />
)}

// Show progress during send
{sendProgress && (
  <div className="fixed bottom-4 right-4 bg-white p-4 rounded shadow-lg">
    <div className="text-sm mb-2">Sending to GHL...</div>
    <div className="w-64 bg-gray-200 rounded h-2">
      <div
        className="bg-tre-teal h-2 rounded"
        style={{ width: `${sendProgress.percent}%` }}
      />
    </div>
    <div className="text-xs mt-1 text-gray-600">
      {sendProgress.sent} / {sendProgress.total} contacts
    </div>
  </div>
)}

// Show summary modal after send completes
{sendSummary && (
  <Modal onClose={() => setSendSummary(null)}>
    <h2>Send Complete</h2>
    <div>Created: {sendSummary.created}</div>
    <div>Updated: {sendSummary.updated}</div>
    <div>Failed: {sendSummary.failed}</div>
    {sendSummary.errors.length > 0 && (
      <div className="mt-4">
        <h3>Errors:</h3>
        <ul>
          {sendSummary.errors.map(err => (
            <li key={err.contact}>{err.contact}: {err.error}</li>
          ))}
        </ul>
      </div>
    )}
  </Modal>
)}
```

**Settings page update:** `frontend/src/pages/Settings.tsx`

```typescript
// Add new section for GHL API configuration
<div className="mb-6">
  <h3 className="text-lg font-semibold mb-2">GoHighLevel API</h3>
  <label className="block mb-2">
    Private Integration Token
    <input
      type="password"
      value={ghlApiToken}
      onChange={(e) => setGhlApiToken(e.target.value)}
      className="w-full mt-1 p-2 border rounded"
      placeholder="Paste your GHL Private Integration Token"
    />
  </label>
  <p className="text-sm text-gray-600">
    Get your token from GHL Settings → Developer Tools → Private Integrations
  </p>
  <button onClick={saveGhlToken} className="mt-2 btn-primary">
    Save Token
  </button>
</div>
```

### Settings Storage

**Firestore structure:**

```
users/
  {userId}/
    settings/
      ghl_api_token: <encrypted_token>
      ghl_location_id: <location_id>
      ghl_send_presets: [
        {
          name: "Default Lead Import",
          tag: "Lead",
          contact_owner_id: "USER_123",
          smartlist_name: "New Leads",
          manual_sms: false
        }
      ]
```

**Encryption:** Use Firestore's built-in encryption at rest, plus application-level encryption for token field.

## Sources

**GoHighLevel Official API Documentation:**
- [HighLevel API Documentation Portal](https://marketplace.gohighlevel.com/docs/)
- [Upsert Contact Endpoint](https://marketplace.gohighlevel.com/docs/ghl/contacts/upsert-contact/index.html)
- [Private Integration Token Authentication](https://marketplace.gohighlevel.com/docs/Authorization/PrivateIntegrationsToken/)
- [Add Tags Endpoint](https://marketplace.gohighlevel.com/docs/ghl/contacts/add-tags/index.html)
- [Remove Tags Endpoint](https://marketplace.gohighlevel.com/docs/ghl/contacts/remove-tags/index.html)
- [Get Users by Location Endpoint](https://marketplace.gohighlevel.com/docs/ghl/users/get-user-by-location/index.html)
- [Bulk Operations Documentation](https://marketplace.gohighlevel.com/docs/ghl/contacts/bulk/index.html)

**GoHighLevel Support Resources:**
- [Private Integrations: Everything You Need to Know](https://help.gohighlevel.com/support/solutions/articles/155000003054-private-integrations-everything-you-need-to-know)
- [HighLevel API Documentation Support Article](https://help.gohighlevel.com/support/solutions/articles/48001060529-highlevel-api)
- [Getting Started With Smart Lists](https://help.gohighlevel.com/support/solutions/articles/48001062094-how-to-create-manage-smart-lists)

**Community and Third-Party Resources:**
- [GitHub - GoHighLevel API Documentation Repository](https://github.com/GoHighLevel/highlevel-api-docs)
- [Contact Upsert and Duplicate Contact Endpoint Announcement](https://blog.gohighlevel.com/contact-upsert-and-duplicate-contact-endpoint-live/)
- [HighLevel API FAQs](https://marketplace.gohighlevel.com/docs/oauth/Faqs/index.html)
- [Comprehensive Guide to GoHighLevel API 2025](https://www.linkedin.com/pulse/comprehensive-guide-gohighlevel-api-2025-unlocking-power-louis-okoh-qvj5f)

---
*Feature research for: GoHighLevel API Integration (v1.2 milestone)*
*Researched: 2026-02-26*
*Context: Subsequent milestone adding API integration to existing GHL Prep tool (v1.1)*

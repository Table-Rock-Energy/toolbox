# Pitfalls Research

**Domain:** GoHighLevel API v2 Integration for Contact Management
**Researched:** 2026-02-26
**Confidence:** MEDIUM

## Critical Pitfalls

### Pitfall 1: Rate Limit Exhaustion Without Proper Backoff

**What goes wrong:**
Application hits 429 (Too Many Requests) errors repeatedly, causing failed contact uploads, stalled operations, and poor user experience. The burst limit of 100 requests per 10 seconds and daily limit of 200,000 requests per day per resource are easily exhausted with naive parallel processing.

**Why it happens:**
Developers implement parallel contact creation to speed up bulk uploads without implementing proper rate limiting, queuing, or retry strategies. The burst limit (100/10s) is particularly easy to exceed when processing CSV files with hundreds of contacts.

**How to avoid:**
1. Implement client-side throttling with a token bucket or sliding window algorithm
2. Use a queue-based approach: batch contacts into groups of 80-90 per 10-second window (leaving headroom)
3. Implement exponential backoff with jitter for 429 responses (start at 2s, double until 60s max)
4. Track rate limit headers in responses to proactively slow down before hitting limits
5. Provide progress tracking that shows "Rate limited, retrying in Xs" to set user expectations

**Warning signs:**
- Backend logs showing repeated 429 errors
- User reports of "stuck" or "slow" uploads
- Contact creation progress bars that stall then suddenly jump
- Error rates spiking during high-volume operations

**Phase to address:**
Phase 2 (Backend Integration) — implement rate limiting before exposing "Send to GHL" button

---

### Pitfall 2: Upsert Deduplication Configuration Mismatch

**What goes wrong:**
Application creates duplicate contacts instead of updating existing ones, or updates the wrong contact when multiple exist with matching email/phone. This happens because the GHL upsert API respects the "Allow Duplicate Contact" setting at the location level, which the application doesn't control.

**Why it happens:**
The upsert API's duplicate handling depends on a location-level configuration that varies per GHL account. If the location is configured to check "Email (Primary) + Phone (Secondary)" but the application only sends email, or if two separate contacts exist (one with matching email, another with matching phone), the API's behavior is unpredictable without checking location settings first.

**How to avoid:**
1. Fetch location-level duplicate settings via GHL API before first upsert
2. Display current dedup settings in the send modal: "This location checks: Email (Primary), Phone (Secondary)"
3. Warn users if CSV has contacts with only email or only phone when both are required by location config
4. Normalize phone to E.164 format (`+1XXXXXXXXXX`) before sending to ensure consistent matching
5. Provide a "preview" mode that shows which contacts will be created vs updated before actual send
6. Log upsert responses and flag contacts that were created when update was expected

**Warning signs:**
- Users reporting "duplicate contacts appearing in GHL after upload"
- Contacts with same email but different phones being created as duplicates
- Upsert operations creating new contacts instead of updating existing ones

**Phase to address:**
Phase 2 (Backend Integration) — fetch and validate location settings before upsert operations

---

### Pitfall 3: API Token Stored in Frontend or Transmitted Insecurely

**What goes wrong:**
Private Integration Token is exposed in browser JavaScript, stored in localStorage, or transmitted in URL parameters. Since this token grants full location-level access, compromise allows attackers to read/modify all contact data, send SMS/emails, and execute workflows.

**Why it happens:**
Developers treat the GHL token like a Firebase ID token (which has short expiration) instead of a long-lived credential. The frontend needs to trigger GHL operations, leading to the temptation to send the token from Settings UI directly to GHL API.

**How to avoid:**
1. **NEVER send Private Integration Token to frontend** — store only in backend Firestore with encryption at rest
2. Backend-only access: Frontend sends request to backend `/api/ghl/send`, backend fetches token from Firestore and calls GHL API
3. Use environment-specific token management: dev location token != prod location token
4. Implement token rotation reminder in Settings UI: "Last rotated: X days ago" with warning at 60 days
5. If token is compromised, provide one-click "Rotate and expire now" flow in Settings that updates Firestore immediately
6. Log all GHL API calls with user ID for audit trail

**Warning signs:**
- Token visible in browser DevTools Network tab
- Token in frontend localStorage or sessionStorage
- Token passed as URL parameter or in GET request
- Token hardcoded in frontend source files

**Phase to address:**
Phase 1 (Settings Backend) — establish secure token storage pattern before building send feature

---

### Pitfall 4: Partial Failure Handling in Bulk Operations

**What goes wrong:**
Bulk contact upload partially succeeds (e.g., 80 of 100 contacts created) but application reports either "complete success" or "total failure." Users don't know which contacts failed or why, and retrying re-uploads successful contacts, potentially creating duplicates.

**Why it happens:**
The GHL API processes contacts individually — there's no true "batch upsert" endpoint that atomically succeeds or fails. Each contact upsert returns its own response. Developers implement naive error handling that doesn't track per-contact status.

**How to avoid:**
1. Track individual contact status: `{ contactIndex, status: "success" | "failed", contactId?, error? }`
2. Implement idempotent retry: assign each contact a stable identifier (CSV row hash or email+phone hash) to prevent duplicate retry
3. Show detailed progress UI: "Processed 80 of 100 contacts | 75 created | 5 updated | 20 failed"
4. Provide downloadable error report CSV with columns: `[Original Row, Email, Phone, Error Code, Error Message]`
5. Enable "Retry Failed Only" button that re-attempts only failed contacts
6. For 429 errors specifically, pause entire batch and resume after backoff period (don't skip those contacts)

**Warning signs:**
- Users reporting "some contacts missing in GHL after upload"
- Success message shown but contact count doesn't match CSV row count
- No way to identify which specific contacts failed
- Retrying causes duplicate contacts to appear

**Phase to address:**
Phase 3 (Send Modal + Progress) — design progress tracking with per-contact granularity

---

### Pitfall 5: Phone and Email Field Format Mismatches

**What goes wrong:**
Contact creation fails with validation errors because phone numbers aren't in E.164 format (`+1XXXXXXXXXX`), emails have leading/trailing whitespace, or phone numbers include formatting characters (dashes, parentheses, spaces). GHL's validation is stricter than CSV exports from Mineral.

**Why it happens:**
The GHL Prep tool currently transforms names, campaigns, and contact owners but doesn't normalize phone/email formats. The transformation runs in frontend before download, so backend doesn't have normalization logic. When adding API push, backend receives raw CSV data that hasn't been normalized for GHL API requirements.

**How to avoid:**
1. Backend phone normalization:
   - Strip all non-digit characters except leading `+`
   - If US number without country code, prepend `+1`
   - Validate length: US = 11 digits total (with country code)
   - Reject invalid formats before upsert attempt
2. Backend email normalization:
   - Trim leading/trailing whitespace
   - Convert to lowercase
   - Validate email regex: `^[^\s@]+@[^\s@]+\.[^\s@]+$`
   - Flag role-based emails (info@, admin@, sales@) as warning
3. Reuse existing GHL Prep transformation logic in backend service layer
4. Provide validation preview: "3 contacts have invalid phone formats, will be skipped" before send
5. Include format requirements in error messages: "Phone must be E.164 format: +1XXXXXXXXXX"

**Warning signs:**
- Validation errors mentioning "phone" or "email" format
- Contacts with valid-looking data failing to create
- Users reporting "phone numbers work in CSV import but fail in API push"
- Error messages like "Invalid phone number format"

**Phase to address:**
Phase 2 (Backend Integration) — add field normalization before first upsert attempt

---

### Pitfall 6: Long-Running Request Timeouts Without Progress Visibility

**What goes wrong:**
User clicks "Send to GHL", sees loading spinner for 2-3 minutes, then browser/backend timeout occurs with no indication of what succeeded. User doesn't know if they should retry (risking duplicates) or if contacts partially uploaded.

**Why it happens:**
Processing 500+ contacts sequentially with rate limiting can take 5-10 minutes (100 contacts per 10s = 50s per 100 contacts). FastAPI default timeout is 120s, browser timeout is often 60s. Synchronous request/response pattern doesn't work for long-running operations.

**How to avoid:**
1. Implement async job pattern:
   - Frontend sends request → backend creates job in Firestore → returns `jobId` immediately
   - Backend processes contacts asynchronously in background
   - Frontend polls `/api/ghl/jobs/{jobId}/status` every 2s for progress updates
2. Store job progress in Firestore:
   ```python
   {
     "jobId": "ghl-send-abc123",
     "status": "processing" | "completed" | "failed",
     "totalContacts": 500,
     "processed": 150,
     "created": 120,
     "updated": 25,
     "failed": 5,
     "errors": [{"contactIndex": 42, "error": "Invalid phone"}],
     "startedAt": "2026-02-26T10:00:00Z",
     "completedAt": null
   }
   ```
3. Show real-time progress in modal: progress bar, "Processing contact 150 of 500", estimated time remaining
4. Enable "background send" for large batches: "Upload started, you can close this and check History later"
5. Keep job history in Firestore for 30 days with downloadable error reports

**Warning signs:**
- Timeout errors in backend logs for `/api/ghl/send` endpoint
- User reports of "upload stuck" or "spinner never stops"
- Gateway timeout errors (504) from Cloud Run after 60s
- No way to resume interrupted uploads

**Phase to address:**
Phase 3 (Send Modal + Progress) — implement async job pattern before testing with large batches

---

### Pitfall 7: Missing Location ID Context

**What goes wrong:**
API requests fail with 401/403 errors: "The token does not have access to this location." This happens when the Private Integration Token is scoped to a specific location but the API request uses a different (or missing) location ID.

**Why it happens:**
GHL's OAuth model supports both Agency-level and Location-level access. Private Integration Tokens are typically scoped to a single location. If the backend doesn't include the correct location ID in requests, or if users have multiple GHL locations and configure the token for the wrong one, all API calls fail.

**How to avoid:**
1. Store `locationId` alongside Private Integration Token in Settings
2. Add location ID input field in Settings UI: "GHL Location ID (found in GHL Settings → Business Profile)"
3. Validate token + location ID on save: make test API call to `/locations/{locationId}` to verify access
4. Display location name/details in Settings after successful validation: "Connected to: [Location Name]"
5. Include location ID in all GHL API requests as required by endpoint (often in path or header)
6. If multiple locations needed, support multiple token/location pairs with dropdown in send modal

**Warning signs:**
- 401 or 403 errors in backend logs with "location" in error message
- API requests succeeding in Postman but failing in app (likely due to different location ID)
- Users reporting "token doesn't work" despite correct scopes

**Phase to address:**
Phase 1 (Settings Backend) — validate location ID + token together before exposing to send feature

---

### Pitfall 8: Custom Field ID Lookup Missing

**What goes wrong:**
Contact creation succeeds but custom fields (from Mineral export) aren't populated in GHL. Custom field data is silently dropped because the API requires custom field IDs (not field names) and the application sends field names directly.

**Why it happens:**
GHL's custom fields are defined per-location with auto-generated IDs. The API accepts custom fields as `customField: { "fieldId1": "value1", "fieldId2": "value2" }` but CSV headers have human-readable names like "Mineral ID" or "Campaign Name". Developers assume field names work like standard fields (firstName, email).

**How to avoid:**
1. Fetch custom fields schema on first send: `GET /locations/{locationId}/customFields`
2. Cache custom field mappings in memory: `{ "Mineral ID": "customFieldId123", "Campaign Name": "customFieldId456" }`
3. Map CSV column headers to custom field IDs before upsert:
   - Match by field name (case-insensitive)
   - If no match found, log warning: "Custom field 'Mineral ID' not found in GHL, data will be skipped"
4. Provide custom field mapping UI in Settings:
   - Show CSV columns → GHL custom fields mapping
   - Let users manually map if names don't match exactly
   - Save mappings per-location for reuse
5. Include custom fields in send preview: "Will populate 3 custom fields: Mineral ID, Campaign Name, NRA %"

**Warning signs:**
- Contacts created but custom field data missing in GHL
- No validation errors but expected data not visible in GHL contact details
- Users reporting "standard fields work but custom fields don't"

**Phase to address:**
Phase 2 (Backend Integration) — implement custom field lookup before first upsert with custom data

---

### Pitfall 9: Contact Owner ID Hardcoded or Not Validated

**What goes wrong:**
All contacts assigned to wrong user in GHL, or contact creation fails because `assignedTo` field contains invalid user ID. This happens when the application uses a hardcoded user ID from dev/testing, or when the selected user is no longer active in the GHL location.

**Why it happens:**
GHL's `assignedTo` field requires a valid user ID from the location's team. User IDs change between GHL locations and can become invalid if users are removed. The send modal needs to populate a dropdown with current users, but fetching users requires a separate API call that developers forget or implement incorrectly.

**How to avoid:**
1. Fetch users list on modal open: `GET /locations/{locationId}/users`
2. Populate dropdown with active users only: filter by `active: true` status
3. Store user selection in send modal state, not as default setting
4. If user ID from previous send is no longer valid, show warning: "Previously selected user is unavailable, please select a new contact owner"
5. Include "Unassigned" option that omits `assignedTo` field entirely (GHL's default behavior)
6. Validate user ID before bulk send: verify user exists in fetched users list

**Warning signs:**
- All contacts assigned to same user regardless of modal selection
- Contact creation fails with "Invalid assignedTo value"
- Dropdown shows users from different GHL location
- "Contact owner not found" errors

**Phase to address:**
Phase 3 (Send Modal) — implement user lookup before exposing contact owner dropdown

---

### Pitfall 10: Tag and SmartList Names Not Pre-Validated

**What goes wrong:**
User enters tag names or SmartList name in send modal, sends contacts, then discovers tags weren't applied or SmartList wasn't created. This happens because the application doesn't validate that tag names follow GHL's naming rules or check if SmartList names conflict with existing ones.

**Why it happens:**
GHL API will create new tags automatically if they don't exist, but has undocumented character restrictions (no special chars, length limits). SmartLists must be created separately via API — just sending a SmartList name with contact doesn't auto-create it. Developers assume both work like freeform text fields.

**How to avoid:**
1. Tag name validation:
   - Trim whitespace, enforce length limit (check GHL docs, likely 50 chars)
   - Warn on special characters (document which are allowed)
   - Provide autocomplete of existing tags: `GET /locations/{locationId}/tags`
   - Support multi-tag input: comma-separated or tag chips UI
2. SmartList handling:
   - Fetch existing SmartLists: `GET /locations/{locationId}/smartlists` (if endpoint exists)
   - Provide dropdown of existing SmartLists with "Create new" option
   - If creating new SmartList, validate name and create it BEFORE sending contacts
   - After contacts sent, add contacts to SmartList via separate API call
3. Show validation errors in modal before send: "Tag name 'Campaign #1' contains invalid character '#'"

**Warning signs:**
- Users reporting "tags didn't get applied"
- SmartList field populated but contacts not added to any list
- Contacts created but manual SmartList assignment needed afterward

**Phase to address:**
Phase 3 (Send Modal) — implement tag/SmartList validation before exposing input fields

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Skip async job pattern, use synchronous send | Faster to implement, simpler code | Timeouts on large batches, no progress visibility, poor UX | Never — timeouts will occur at ~200+ contacts |
| Store GHL token in Firestore without encryption | Works immediately, no crypto library needed | Token exposure if Firestore security rules misconfigured | Never — Private Integration Token = full location access |
| Skip phone/email normalization, send CSV data as-is | Reuse existing GHL Prep logic, no backend changes | Validation errors, failed contact creation, manual cleanup | Never — format mismatches are guaranteed |
| Hardcode rate limit delays (10s per batch) | Avoids tracking rate limit headers | Inefficient (slower than necessary), still fails if burst limit exceeded | Only for MVP testing with <50 contacts |
| Show generic "Upload failed" without per-contact errors | Simple error handling, less state management | Users can't identify failed contacts, manual GHL checking required | Never — partial failures will occur |
| Skip location ID validation on token save | Faster Settings save, one less API call | All sends fail with cryptic 401 errors | Never — validation prevents all downstream failures |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| GHL Upsert API | Assuming email+phone always creates one unique contact | Fetch location's "Allow Duplicate Contact" settings and respect the configured primary/secondary field priority |
| GHL Rate Limits | Implementing parallel requests to "speed up" uploads | Use queued sequential processing with 80-90 requests per 10s batch (leaving headroom), implement exponential backoff for 429s |
| Private Integration Token | Storing token in frontend localStorage for "easy access" | Store only in backend Firestore, frontend never sees token, backend fetches on each API request |
| Custom Fields | Sending custom field data using CSV column names | Fetch custom field schema from GHL API, map names to IDs, use IDs in upsert payload |
| Phone Format | Sending phone as-is from CSV: `(555) 123-4567` | Normalize to E.164: strip formatting, prepend +1 for US numbers, validate length before send |
| Contact Owner | Using first user from users list as default | Fetch users on modal open, populate dropdown, let user explicitly select (no hardcoded defaults) |
| SmartList Assignment | Sending `smartList: "name"` field with contact upsert | Create SmartList via separate API call first, then add contact IDs to SmartList after upsert |
| Error Handling | Catching all errors as "Upload failed" | Parse GHL error responses, extract error code + message, display per-contact errors, enable "retry failed" |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Sequential processing without rate awareness | Uploads take 10-20 minutes for 500 contacts, users report "too slow" | Batch 80-90 contacts per 10s (approaching but not exceeding burst limit), show progress bar | Always slow, but users complain at 200+ contacts |
| Fetching users/tags/custom fields on every contact | Repeated API calls for same data, rate limits exhausted on metadata | Fetch once on modal open, cache in memory for duration of send operation | 50+ contacts (wastes rate limit quota) |
| Polling job status every 500ms | Backend overloaded with status checks, Firestore read costs spike | Poll every 2-3 seconds, use exponential backoff if job status unchanged | 10+ concurrent uploads |
| Storing full contact data in job progress document | Firestore document size limit (1MB) exceeded, writes fail | Store only contact indices, counts, and error summaries — full data stays in CSV | 500+ contacts with long text fields |
| No pagination on job history | History page loads slowly, crashes browser with large result set | Paginate job history queries (25 per page), index by `createdAt DESC` | 100+ historical jobs |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Storing Private Integration Token in browser | Token exposed in DevTools, XSS attack could steal token and access all GHL contacts | Store token only in backend Firestore, frontend sends requests to backend API, backend fetches token and calls GHL |
| Not rotating token regularly | Compromised token remains valid indefinitely, undetected breach | Implement token rotation reminder (90-day cycle), show "Last rotated: X days ago" in Settings, one-click rotation flow |
| Logging full GHL API responses | Contact PII (email, phone, address) written to backend logs, exposed in Cloud Logging | Log only status codes, error messages, and contact IDs (not full contact data) |
| No audit trail for GHL sends | Can't determine who sent which contacts, when, or with what configuration | Log each GHL send job with user ID, timestamp, contact count, location ID in Firestore jobs collection |
| Token in environment variables without encryption | Token visible in Cloud Run settings, accessible to anyone with GCP console access | Store token in Firestore with application-level encryption, not in env vars (or use Secret Manager) |
| Sharing token between dev/prod locations | Dev testing pollutes prod GHL location, accidental prod data modification | Use separate GHL locations for dev/prod, different tokens per environment, Settings UI shows environment name |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| No progress visibility during long uploads | User stares at spinner for 5+ minutes, doesn't know if request is stuck or succeeding | Show real-time progress: "Processing contact 150 of 500 | 120 created | 25 updated | 5 failed" with progress bar |
| "Upload failed" without actionable error message | User doesn't know what failed or how to fix it, retries entire batch | Show per-contact errors: "20 contacts failed | Download error report CSV" with specific error codes and fix instructions |
| No way to retry only failed contacts | User must choose: retry all (risking duplicates) or manually fix in GHL | Track failed contacts by stable ID, provide "Retry Failed Only" button that re-processes only failed subset |
| Send button enabled before validation | User clicks send, then sees validation errors, interrupts flow | Validate on modal open: fetch users/custom fields, pre-check for issues, disable send until ready |
| No confirmation before overwriting existing contacts | User accidentally updates 500 existing contacts when they meant to create new ones | Show upsert preview: "Will create 300 new, update 200 existing — review changes?" with contact breakdown |
| Generic "Invalid token" error | User doesn't know if token is wrong, expired, or location mismatch | Specific error messages: "Token does not have access to location ABC123 — verify Location ID in Settings" |

## "Looks Done But Isn't" Checklist

- [ ] **Rate limiting:** Often missing exponential backoff + jitter — verify 429 responses trigger increasing delays (2s, 4s, 8s, 16s, 32s, 60s)
- [ ] **Partial failure handling:** Often reports "success" when 80% succeeded — verify per-contact status tracked and summary shows created/updated/failed counts
- [ ] **Phone normalization:** Often sends CSV format as-is — verify E.164 normalization (strip formatting, prepend +1, validate length)
- [ ] **Custom field mapping:** Often sends field names not IDs — verify custom fields fetched and mapped to IDs before upsert
- [ ] **Token security:** Often stored in frontend or logged — verify token never sent to frontend, not logged in API responses
- [ ] **Location validation:** Often skips location ID check — verify token + location ID validated together on save (test API call)
- [ ] **Progress tracking:** Often shows spinner with no updates — verify real-time progress (processed/created/updated/failed counts) with 2s poll interval
- [ ] **Error recovery:** Often no way to retry — verify "Retry Failed Only" button works with idempotent contact IDs
- [ ] **Long request timeout:** Often uses synchronous request — verify async job pattern with Firestore job document for uploads 100+ contacts
- [ ] **Contact owner validation:** Often hardcoded or not checked — verify users fetched on modal open, selected user validated before send

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Rate limit exhaustion | LOW | Already built into GHL API: automatic webhook retries with 10-min intervals for 429s; implement exponential backoff in client for immediate mitigation |
| Duplicate contacts created | MEDIUM | Use GHL's manual merge tool or Duplicate Contact API endpoint; prevent recurrence by validating location dedup settings before upsert |
| Token compromised | LOW | Use "Rotate and expire now" in Settings (both app + GHL console), update Firestore with new token, test with sample send |
| Partial upload failure | LOW | Download error report CSV from job history, fix data issues (phone format, etc.), use "Retry Failed Only" to re-send |
| Wrong location configured | LOW | Update location ID in Settings, validate with test API call, re-send contacts (upsert will update, not duplicate) |
| Custom fields not mapped | MEDIUM | Manually populate custom fields in GHL or re-send with correct custom field mapping after fetching schema |
| Contact owner mismatch | LOW | Bulk update contacts in GHL to reassign owner, or re-send with correct owner (upsert updates assignedTo field) |
| Missing tags | LOW | Use GHL bulk actions to apply tags to contacts, or re-send with correct tags (upsert merges tags) |
| SmartList not created | LOW | Manually create SmartList in GHL and add contacts, or implement SmartList creation in app and re-send |
| Phone format rejected | MEDIUM | Fix phone format in source CSV, re-upload to GHL Prep, re-send with normalized phones (app should auto-normalize) |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| API Token Stored Insecurely | Phase 1 (Settings Backend) | Token stored in Firestore only, never sent to frontend, test with DevTools Network tab |
| Missing Location ID Context | Phase 1 (Settings Backend) | Location ID validated with token on save, test API call succeeds, location name displayed |
| Rate Limit Exhaustion | Phase 2 (Backend Integration) | 429 responses trigger exponential backoff, batch size 80-90 per 10s, test with 200+ contacts |
| Phone/Email Format Mismatches | Phase 2 (Backend Integration) | E.164 normalization applied before upsert, validation errors caught pre-send, test with formatted phones |
| Upsert Dedup Configuration Mismatch | Phase 2 (Backend Integration) | Location dedup settings fetched and respected, preview shows create vs update, test with existing contacts |
| Custom Field ID Lookup Missing | Phase 2 (Backend Integration) | Custom fields fetched and mapped to IDs, unmapped fields logged as warnings, test with Mineral export |
| Long-Running Request Timeouts | Phase 3 (Send Modal + Progress) | Async job pattern implemented, frontend polls job status, test with 500+ contacts |
| Partial Failure Handling | Phase 3 (Send Modal + Progress) | Per-contact status tracked, error report downloadable, "Retry Failed Only" works, test with intentional failures |
| Contact Owner ID Not Validated | Phase 3 (Send Modal) | Users fetched on modal open, dropdown populated, selected user validated, test with inactive user |
| Tag/SmartList Names Not Pre-Validated | Phase 3 (Send Modal) | Tag names validated against rules, SmartLists fetched or created, test with special chars and long names |

## Sources

### Official GoHighLevel Documentation
- [HighLevel API Documentation (Support Portal)](https://help.gohighlevel.com/support/solutions/articles/48001060529-highlevel-api)
- [HighLevel API Developer Portal](https://marketplace.gohighlevel.com/docs/)
- [Upsert Contact API](https://marketplace.gohighlevel.com/docs/ghl/contacts/upsert-contact/index.html)
- [Contact Upsert and Duplicate Contact Endpoint Announcement](https://blog.gohighlevel.com/contact-upsert-and-duplicate-contact-endpoint-live/)
- [Private Integrations Documentation](https://help.gohighlevel.com/support/solutions/articles/155000003054-private-integrations-everything-you-need-to-know)
- [Private Integrations API](https://marketplace.gohighlevel.com/docs/Authorization/PrivateIntegrationsToken/)
- [Automated Webhook Retries](https://help.gohighlevel.com/support/solutions/articles/155000007071-automated-webhook-retries)
- [Troubleshooting Bulk Imports Via CSV](https://help.gohighlevel.com/support/solutions/articles/48001223155-troubleshooting-bulk-imports-via-csv)

### Rate Limiting & Performance
- [HighLevel API Rate Limits](https://marketplace.gohighlevel.com/docs/oauth/Faqs/index.html) — 100 requests per 10s burst, 200K per day
- [API Rate Limit Best Practices](https://www.digitalapi.ai/blogs/api-rate-limit-exceeded)
- [API Rate Limit 429 Errors Guide](https://dataprixa.com/api-rate-limit-exceeded/)

### Security & Token Management
- [Private Integrations for Agencies Changelog](https://ideas.gohighlevel.com/changelog/private-integrations-for-agencies)
- [Private Integrations Tutorial (Growthable)](https://growthable.io/gohighlevel-tutorials/integration-widget/private-integrations-in-gohighlevel-everything-you-need-to-know/)
- [HighLevel Private Integration Token Detection (GitGuardian)](https://docs.gitguardian.com/secrets-detection/secrets-detection-engine/detectors/specifics/hl_private_integration_token)

### Contact Management & Validation
- [How To Manage and Merge Duplicate Contacts](https://help.gohighlevel.com/support/solutions/articles/155000006647-contacts-manage-and-merge-duplicates)
- [Allow Duplicate Contacts (Deduplication Preferences)](https://help.gohighlevel.com/support/solutions/articles/48001181714-allow-duplicate-contacts-contact-deduplication-preferences-)
- [CSV File Format for Importing Contacts](https://help.gohighlevel.com/support/solutions/articles/155000005143-csv-file-format-for-importing-contacts-and-opportunities)
- [Email Validation Feature](https://help.gohighlevel.com/support/solutions/articles/155000002668-email-validation-feature-in-forms-and-surveys)
- [SMS and Phone Number Validation (Growthable)](https://growthable.io/gohighlevel-tutorials/phone/how-to-use-sms-and-phone-number-validation-for-gohighlevel/)

### SmartLists & Tags
- [Getting Started With Smart Lists](https://help.gohighlevel.com/support/solutions/articles/48001062094-how-to-create-manage-smart-lists)
- [Smart Lists Guide (Consultevo)](https://consultevo.com/gohighlevel-smart-lists-guide/)
- [How To Create and Edit Smart Lists (Growthable)](https://growthable.io/gohighlevel-tutorials/contacts/how-to-create-and-edit-smart-lists/)

### Custom Fields
- [How to Use Custom Fields](https://help.gohighlevel.com/support/solutions/articles/48001161579-how-to-use-custom-fields)
- [Custom Fields V2 API](https://marketplace.gohighlevel.com/docs/ghl/custom-fields/custom-fields-v-2-api/index.html)
- [Get Custom Fields API](https://marketplace.gohighlevel.com/docs/ghl/locations/get-custom-fields/index.html)

### Developer Support
- [HighLevel API Support](https://developers.gohighlevel.com/support)
- [GitHub: highlevel-api-docs](https://github.com/GoHighLevel/highlevel-api-docs)
- [HighLevel Developers Community](https://developers.gohighlevel.com/)

### Community Resources
- [GoHighLevel API Integration Guide (Centripe)](https://www.centripe.ai/gohighlevel-api-integration)
- [GoHighLevel Webhook Retry Guide (Consultevo)](https://consultevo.com/gohighlevel-automated-webhook-retries/)
- [Manage Duplicate Contacts (Consultevo)](https://consultevo.com/gohighlevel-manage-duplicate-contacts/)

---
*Pitfalls research for: GHL API Integration v1.2*
*Researched: 2026-02-26*

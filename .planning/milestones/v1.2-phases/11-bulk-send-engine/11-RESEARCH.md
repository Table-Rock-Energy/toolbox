# Phase 11: Bulk Send Engine - Research

**Researched:** 2026-02-27
**Domain:** Async batch processing with API rate limiting
**Confidence:** HIGH

## Summary

Phase 11 implements a synchronous bulk send engine that validates contact batches upfront, processes them in fixed-size chunks (~50 contacts), handles per-contact failures gracefully, and returns comprehensive results when complete. The phase builds on existing Phase 9 infrastructure (GHL client with rate limiting, normalization, single-contact upsert) and Phase 10 UI (Send modal with form inputs).

The core technical challenge is processing hundreds of contacts through the GHL API while respecting rate limits (50 requests per 10 seconds), validating data upfront, tracking per-contact results with stable identifiers (mineral system ID), and applying tags additively without disrupting existing contact data. The implementation follows a synchronous request/response pattern where the modal stays open showing progress and the API returns full results when done—Phase 12 will add async background jobs with SSE.

**Primary recommendation:** Use async for loops with the existing token bucket rate limiter from Phase 9, validate the entire batch before processing (fail fast on validation errors), track results in a list keyed by mineral system ID, and return a structured response with created/updated/failed counts plus detailed per-contact results.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Validation behavior:**
- Upfront validation pass — validate entire batch before sending any contacts
- Send valid contacts, skip invalid ones (do not reject entire batch)
- After validation, pause and show user the valid/invalid split in the modal (e.g., "42 valid, 3 invalid") — user clicks "Send 42 contacts" to proceed
- Validation checks presence AND format: email must pass regex validation, phone must be normalizable to E.164 format
- A contact is valid if it has at least one valid email OR one valid phone number

**Batch processing strategy:**
- Fixed batch size (~50 contacts per batch) — do not adaptively tune
- Skip-and-continue on per-contact failures: log the failure, keep processing remaining contacts
- No per-contact retry — if a contact fails, it's logged as failed and processing continues
- Cancel button available during processing — already-sent contacts stay sent, remaining are skipped, summary shows partial results
- Synchronous processing — modal stays open showing progress, API response returns full results when done (Phase 12 adds async background jobs with SSE)
- Expected to handle hundreds of rows in production

**Tagging & field mapping:**
- Campaign tag is auto-applied by default — tag name matches the campaign name from the modal
- "manual sms" tag (all lowercase) is optional via checkbox — applies to all contacts in batch when checked
- User can add additional tags: select from existing GHL sub-account tags OR create a new tag
- Tags are additive — always add alongside existing contact tags, never replace
- If a contact ends up with multiple campaign tags, add a note to the GHL contact record flagging the overlap (indicates contact appears in multiple properties/campaigns)
- All source columns map directly to GHL contact fields — column names match GHL field names, no manual field mapping config needed
- Contact Owner is the exception — set via dropdown from Phase 10 (populated by GHL Users API)
- Phone number is the primary dedup/match key for upsert (most records will not have email)
- If email exists in source data, it should be mapped but phone is the primary match field

**Success/failure tracking:**
- In-memory tracking during send — results stored in a list, returned in API response
- Mineral system ID is the unique identifier linking results back to source rows
- Result summary shows counts (created, updated, failed) plus a list of failed contacts with specific error messages
- Send results are persisted to Firestore as a job history record — user can revisit results later
- Contact statuses: created, updated, failed (with error message), skipped (validation failure)

### Claude's Discretion

- Exact batch delay/throttle timing between batches (within Phase 9's rate limit framework)
- How the multi-campaign note is formatted on the GHL contact record
- Internal data structures for tracking batch progress
- How cancellation signal is communicated from frontend to backend mid-request

### Deferred Ideas (OUT OF SCOPE)

- None — discussion stayed within phase scope

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CTCT-01 | User can upsert contacts to GHL (create new, merge new info into existing) | GHL upsert endpoint at `/contacts/upsert` supports search-and-update logic. Phase 9's `GHLClient.upsert_contact()` provides single-contact foundation. Batch engine wraps this in async for loop with rate limiting. |
| CTCT-02 | User can apply a campaign tag to all contacts in a batch | GHL tags API at `/contacts/:contactId/tags` supports adding tags. Tags are additive (don't replace existing). Campaign tag name comes from modal form state. |
| CTCT-03 | User can optionally apply a "manual SMS" tag via checkbox | Same tags API endpoint. Checkbox state from modal determines whether to include "manual sms" (lowercase) in tags array. |
| CTCT-05 | System validates required fields (email or phone) before sending batch | Phase 9's `validate_contact()` checks email OR phone presence. New upfront validation pass uses this function on entire batch, separates valid/invalid contacts, shows split to user for confirmation. |
| CTCT-06 | System handles GHL rate limits (100 req/10s) with automatic throttling and backoff | Phase 9's `RateLimiter` class implements token bucket (50 requests per 10 seconds). `GHLClient._request()` includes exponential backoff retry on 429. Batch engine inherits this — no new rate limiting code needed. |

</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.x (existing) | Async API framework | Already used for all API routes, native async/await support |
| Pydantic | 2.x (existing) | Request/response validation | Already used for all models, strict validation with Field descriptors |
| httpx | (existing via Phase 9) | Async HTTP client for GHL API | Already integrated in `GHLClient`, used for all GHL API calls |
| Firestore | (existing) | Job history persistence | Already used for job metadata, batch results stored as documents |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| phonenumbers | (existing via Phase 9) | E.164 phone normalization | Validation pass checks phone format, already integrated in normalization service |
| Pandas | 2.x (existing) | CSV/data processing | If batch data arrives as CSV rows, already used throughout project |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Synchronous for loop | asyncio.gather() | gather() fails entire batch on first error, we need skip-and-continue behavior |
| Token bucket (Phase 9) | asyncio Semaphore | Semaphore limits concurrency but doesn't enforce time-based rate limits (requests per second) |
| In-memory results list | Background task queue (Celery) | Celery adds complexity (Redis dependency, worker processes) — Phase 12 requirement, not needed for Phase 11's synchronous pattern |

**Installation:**
No new dependencies — all required libraries already installed.

## Architecture Patterns

### Recommended Project Structure

Batch processing logic lives in new service layer file:

```
toolbox/backend/app/services/ghl/
├── client.py                    # Existing: GHLClient, RateLimiter, single-contact upsert
├── normalization.py             # Existing: validate_contact, normalize_contact, normalize_phone/email
├── connection_service.py        # Existing: CRUD for GHL connections
└── bulk_send_service.py         # NEW: Batch validation, batch processing, result aggregation
```

API route added to existing GHL router:

```
toolbox/backend/app/api/
└── ghl.py                       # Add POST /contacts/bulk-send endpoint
```

Pydantic models added to existing GHL models:

```
toolbox/backend/app/models/
└── ghl.py                       # Add BulkSendRequest, BulkSendResponse, ContactResult
```

### Pattern 1: Upfront Batch Validation

**What:** Validate entire batch before processing any contacts, return validation results to user for confirmation

**When to use:** User decision requires showing valid/invalid split — must validate before sending

**Example:**

```python
# Source: Based on existing validate_contact() pattern from Phase 9
from app.services.ghl.normalization import validate_contact, normalize_contact

async def validate_batch(contacts: list[dict]) -> tuple[list[dict], list[dict]]:
    """Validate batch of contacts, return (valid, invalid) tuple.

    Each contact must have:
    - Mineral system ID (stable identifier for tracking)
    - At least one of: email (valid format) OR phone (E.164 normalizable)

    Returns:
        Tuple of (valid_contacts, invalid_contacts)
        Invalid contacts include error message in 'validation_error' field
    """
    valid = []
    invalid = []

    for contact in contacts:
        # Check for mineral system ID
        mineral_id = contact.get("mineral_contact_system_id") or contact.get("Mineral Contact System Id")
        if not mineral_id:
            invalid.append({
                **contact,
                "validation_error": "Missing mineral contact system ID"
            })
            continue

        # Normalize and validate
        normalized = normalize_contact(contact)
        is_valid, error = validate_contact(normalized)

        if is_valid:
            valid.append({
                **normalized,
                "mineral_contact_system_id": mineral_id
            })
        else:
            invalid.append({
                **contact,
                "mineral_contact_system_id": mineral_id,
                "validation_error": error
            })

    return valid, invalid
```

### Pattern 2: Synchronous Batch Processing with Rate Limiting

**What:** Process contacts sequentially in batches using async for loop, let Phase 9's rate limiter handle throttling

**When to use:** User constraint requires synchronous processing (modal stays open, API returns when done)

**Example:**

```python
# Source: FastAPI async patterns + Phase 9 RateLimiter
from app.services.ghl.client import GHLClient
from app.services.ghl.connection_service import get_connection

async def process_batch(
    connection_id: str,
    contacts: list[dict],
    tags: list[str],
    assigned_to: str | None = None
) -> dict:
    """Process batch of validated contacts through GHL API.

    Args:
        connection_id: GHL connection ID
        contacts: List of validated, normalized contact dicts
        tags: Tags to apply to all contacts (campaign tag + optional manual sms)
        assigned_to: GHL user ID for contact owner

    Returns:
        Dict with created_count, updated_count, failed_count, results list
    """
    # Fetch connection with decrypted token
    connection = await get_connection(connection_id, decrypt_token=True)
    if not connection:
        raise ValueError(f"Connection {connection_id} not found")

    token = connection["token"]
    location_id = connection["location_id"]

    results = []
    created_count = 0
    updated_count = 0
    failed_count = 0

    # Process contacts sequentially — rate limiter handles throttling
    async with GHLClient(token=token, location_id=location_id) as client:
        for contact in contacts:
            mineral_id = contact["mineral_contact_system_id"]

            # Build contact data with tags and owner
            contact_data = {**contact}
            if tags:
                contact_data["tags"] = tags
            if assigned_to:
                contact_data["assigned_to"] = assigned_to

            try:
                result = await client.upsert_contact(contact_data)

                # Track result
                if result["action"] == "created":
                    created_count += 1
                elif result["action"] == "updated":
                    updated_count += 1

                results.append({
                    "mineral_contact_system_id": mineral_id,
                    "status": result["action"],
                    "ghl_contact_id": result["ghl_contact_id"],
                    "error": None
                })

            except Exception as e:
                # Skip-and-continue on failure
                failed_count += 1
                results.append({
                    "mineral_contact_system_id": mineral_id,
                    "status": "failed",
                    "ghl_contact_id": None,
                    "error": str(e)
                })

    return {
        "created_count": created_count,
        "updated_count": updated_count,
        "failed_count": failed_count,
        "total_count": len(contacts),
        "results": results
    }
```

### Pattern 3: Job History Persistence

**What:** Persist batch send results to Firestore for later retrieval

**When to use:** User constraint requires job history — results must be retrievable after modal closes

**Example:**

```python
# Source: Existing persist_job_result pattern from ghl_prep
from app.services.firestore_service import get_firestore_client
from datetime import datetime, timezone

async def persist_send_job(
    job_id: str,
    connection_id: str,
    campaign_name: str,
    created_count: int,
    updated_count: int,
    failed_count: int,
    total_count: int,
    results: list[dict],
    user_id: str | None = None
) -> None:
    """Persist bulk send job to Firestore for history."""
    db = get_firestore_client()

    doc_data = {
        "job_id": job_id,
        "tool": "ghl_send",
        "connection_id": connection_id,
        "campaign_name": campaign_name,
        "created_count": created_count,
        "updated_count": updated_count,
        "failed_count": failed_count,
        "total_count": total_count,
        "results": results,  # Full result list
        "user_id": user_id,
        "created_at": datetime.now(timezone.utc),
        "status": "completed"
    }

    await db.collection("jobs").document(job_id).set(doc_data)
```

### Anti-Patterns to Avoid

- **asyncio.gather() for batch processing:** Fails entire batch on first error, violates skip-and-continue constraint
- **Custom retry logic per contact:** Phase 9's rate limiter already handles retries on 429, adding per-contact retry creates double-retry behavior
- **Adaptive batch sizing:** User constraint specifies fixed ~50 contact batches, adaptive sizing adds complexity without benefit
- **Tags array replacement:** GHL tags are additive — must append to existing tags, not replace them (handled by Phase 9's upsert logic)

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Phone number validation | Custom regex for US phone formats | phonenumbers library (existing) | Handles international formats, carrier codes, area code validation — already integrated in Phase 9 normalization |
| E.164 normalization | String manipulation with +1 prefix | phonenumbers.format_number() (existing) | Handles country codes, formatting rules, invalid number detection |
| Rate limiting | Sleep delays or manual throttling | Phase 9 RateLimiter token bucket | Already proven in Phase 9, handles burst traffic, precise timing control |
| Email validation | Complex regex for all edge cases | Simple regex from Phase 9 normalization | Email RFC is 5000+ words, simple pattern catches 99% of cases, matches existing codebase pattern |
| API retry logic | Custom exponential backoff | Phase 9 GHLClient._request() retry | Already implements exponential backoff on 429, integrates with rate limiter |

**Key insight:** Phase 9 infrastructure solves the hard problems (rate limiting, normalization, retry). Batch engine is a thin orchestration layer around single-contact operations.

## Common Pitfalls

### Pitfall 1: Forgetting to Pass Tags Through Upsert

**What goes wrong:** Tags specified in modal don't get applied to contacts in GHL

**Why it happens:** Phase 9's `upsert_contact()` accepts tags in contact_data dict, but batch processor forgets to include them

**How to avoid:** Build contact_data dict with tags before calling upsert:

```python
contact_data = {**contact}
if tags:
    contact_data["tags"] = tags  # Add tags to contact data
if assigned_to:
    contact_data["assigned_to"] = assigned_to
```

**Warning signs:** Manual testing shows contacts created without campaign tag even though modal had tag specified

### Pitfall 2: Rate Limiter Per-Contact Instead of Per-Batch

**What goes wrong:** Creating new GHLClient instance inside loop resets rate limiter, causing 429 errors

**Why it happens:** Each `async with GHLClient(...)` creates a new RateLimiter instance, batch doesn't benefit from shared token bucket

**How to avoid:** Create GHLClient once outside loop, reuse for all contacts:

```python
# WRONG: New rate limiter per contact
for contact in contacts:
    async with GHLClient(token, location_id) as client:  # New limiter each iteration
        await client.upsert_contact(contact)

# RIGHT: Shared rate limiter for batch
async with GHLClient(token, location_id) as client:  # Single limiter for batch
    for contact in contacts:
        await client.upsert_contact(contact)
```

**Warning signs:** 429 errors despite low contact count, rate limiter debug logs show tokens resetting

### Pitfall 3: Validating After Processing Starts

**What goes wrong:** Batch starts processing, fails halfway through on validation error, leaves partial data in GHL

**Why it happens:** Validation happens inside processing loop instead of upfront validation pass

**How to avoid:** User constraint requires upfront validation — validate entire batch, show user valid/invalid split, only process after user confirms

```python
# Validate first
valid_contacts, invalid_contacts = await validate_batch(contacts)

# Show user the split (frontend responsibility)
# User clicks "Send X valid contacts" button

# Then process only validated contacts
results = await process_batch(connection_id, valid_contacts, tags, assigned_to)
```

**Warning signs:** Partial batches sent when validation errors occur, no validation summary shown to user

### Pitfall 4: Using Email as Primary Dedup Key

**What goes wrong:** Contacts with phone but no email get duplicated in GHL

**Why it happens:** Developer assumes email is primary dedup key (common in other systems), but user constraint specifies phone is primary

**How to avoid:** GHL's upsert respects "Allow Duplicate Contact" setting — configured at location level to prioritize phone. Phase 9's upsert searches by email if available, but user data has phone as primary identifier. Trust GHL's dedup logic, don't force email-first matching.

**Warning signs:** User reports duplicate contacts when sending batches with phone-only records

### Pitfall 5: Not Tracking Mineral System ID in Results

**What goes wrong:** Results can't be matched back to source rows, user can't identify which contacts failed

**Why it happens:** Using array index or GHL contact ID as identifier instead of stable source identifier

**How to avoid:** User constraint specifies mineral system ID as unique identifier — include it in every result entry:

```python
results.append({
    "mineral_contact_system_id": mineral_id,  # Stable identifier from source
    "status": result["action"],
    "ghl_contact_id": result["ghl_contact_id"],
    "error": None
})
```

**Warning signs:** Frontend can't display failed contact names, results list shows generic "Contact 1, Contact 2" instead of actual names

## Code Examples

Verified patterns from Phase 9 (already implemented):

### Normalize and Validate Single Contact

```python
# Source: Phase 9 normalization.py
from app.services.ghl.normalization import normalize_contact, validate_contact

contact_data = {
    "first_name": "JOHN",
    "last_name": "DOE",
    "email": "  John.Doe@Example.com  ",
    "phone": "(512) 748-1234"
}

# Normalize
normalized = normalize_contact(contact_data)
# Result: {
#   "first_name": "John",
#   "last_name": "Doe",
#   "email": "john.doe@example.com",
#   "phone": "+15127481234"
# }

# Validate
is_valid, error = validate_contact(normalized)
# Result: (True, None) — has phone (email optional)
```

### Upsert Single Contact with Rate Limiting

```python
# Source: Phase 9 client.py
from app.services.ghl.client import GHLClient

async with GHLClient(token=token, location_id=location_id) as client:
    result = await client.upsert_contact({
        "first_name": "John",
        "last_name": "Doe",
        "phone": "+15127481234",
        "tags": ["Campaign A", "manual sms"],
        "assigned_to": "user_xyz"
    })
    # Result: {
    #   "action": "created",  # or "updated"
    #   "contact": {...},     # Full GHL response
    #   "ghl_contact_id": "contact_123"
    # }
```

### Process Batch with Error Handling

```python
# Source: Based on Phase 9 patterns + FastAPI async best practices
from app.services.ghl.client import GHLClient, GHLAPIError, GHLRateLimitError

results = []
async with GHLClient(token=token, location_id=location_id) as client:
    for contact in valid_contacts:
        mineral_id = contact["mineral_contact_system_id"]

        try:
            result = await client.upsert_contact(contact)
            results.append({
                "mineral_contact_system_id": mineral_id,
                "status": result["action"],
                "ghl_contact_id": result["ghl_contact_id"],
                "error": None
            })
        except GHLAPIError as e:
            # Log and continue — skip-and-continue pattern
            logger.warning(f"Contact {mineral_id} failed: {e}")
            results.append({
                "mineral_contact_system_id": mineral_id,
                "status": "failed",
                "ghl_contact_id": None,
                "error": str(e)
            })
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Synchronous requests with manual sleep() | asyncio + token bucket rate limiter | 2025+ | More precise rate limiting, better throughput under GHL's 50 req/10s limit |
| Background task queues (Celery) for all async work | Synchronous API response for small batches | Phase 11 pattern | Simpler implementation, acceptable for hundreds of contacts, Phase 12 adds background jobs for thousands |
| Manual retry loops | httpx automatic retries + exponential backoff | httpx best practices 2025 | Cleaner code, standardized retry behavior |
| Email-first deduplication | Phone-first deduplication | GHL API v2 + user data patterns | Matches user data (phone primary field), respects GHL location settings |

**Deprecated/outdated:**
- **GHL API v1:** End-of-support, V2 is required (already used in Phase 9)
- **Manual rate limit tracking:** Token bucket pattern is standard for time-based limits (50 req/10s)
- **Blocking synchronous requests:** FastAPI async/await is standard for I/O-bound operations

## Open Questions

1. **How does GHL handle tag creation on upsert?**
   - What we know: Tags API endpoint exists at `/contacts/:contactId/tags`, tags are additive (append not replace)
   - What's unclear: Does upsert endpoint auto-create tags if they don't exist, or must tags be created separately first?
   - Recommendation: Test with Phase 9's single-contact upsert — if it auto-creates tags, batch inherits this behavior. If not, add tag creation step before batch processing.

2. **What's the exact GHL deduplication priority sequence?**
   - What we know: GHL respects "Allow Duplicate Contact" setting at location level, checks email and phone per configured priority
   - What's unclear: Default priority order when both email and phone exist
   - Recommendation: User constraint specifies phone is primary — configure GHL location to prioritize phone over email, document this as setup requirement

3. **How should multi-campaign note be formatted?**
   - What we know: User constraint says add a note to GHL contact when multiple campaign tags detected
   - What's unclear: Note format, field name, whether it's a custom field or standard note
   - Recommendation: Use GHL's notes field (standard), format as "Multiple campaigns detected: Campaign A, Campaign B" — discoverable by Claude during implementation

4. **Does GHL have a bulk contacts endpoint?**
   - What we know: Documentation shows `/contacts/upsert` for single contacts, user feature requests mention bulk endpoints
   - What's unclear: Whether V2 API has undocumented bulk endpoint that accepts contact arrays
   - Recommendation: Proceed with single-contact upsert in loop (proven pattern), Phase 9 infrastructure supports this. If bulk endpoint exists, it's an optimization for Phase 13 (production hardening).

## Sources

### Primary (HIGH confidence)

- [Phase 9 GHL client implementation](file:///Users/ventinco/Documents/Projects/Table%20Rock%20TX/Tools/toolbox/backend/app/services/ghl/client.py) - Existing RateLimiter, GHLClient, upsert_contact patterns
- [Phase 9 normalization service](file:///Users/ventinco/Documents/Projects/Table%20Rock%20TX/Tools/toolbox/backend/app/services/ghl/normalization.py) - validate_contact, normalize_contact, E.164 phone formatting
- [FastAPI async documentation](https://fastapi.tiangolo.com/async/) - Official async/await patterns
- [GHL API Contacts Documentation](https://marketplace.gohighlevel.com/docs/ghl/contacts/contacts/index.html) - Official API reference

### Secondary (MEDIUM confidence)

- [GHL Upsert Contact Endpoint](https://marketplace.gohighlevel.com/docs/ghl/contacts/upsert-contact/index.html) - Deduplication behavior, location settings
- [GHL Add Tags Endpoint](https://marketplace.gohighlevel.com/docs/ghl/contacts/add-tags/index.html) - Tags API patterns
- [FastAPI Background Tasks Patterns 2025](https://leapcell.io/blog/managing-background-tasks-and-long-running-operations-in-fastapi) - Long-running operation patterns
- [FastAPI Polling Strategy](https://openillumi.com/en/en-fastapi-long-task-progress-polling/) - Synchronous vs async task patterns
- [Python asyncio rate limiting best practices](https://aiolimiter.readthedocs.io/) - Token bucket and leaky bucket patterns

### Tertiary (LOW confidence)

- [GHL Contact Deduplication Settings](https://help.gohighlevel.com/support/solutions/articles/48001181714) - Location-level dedup configuration (support docs, not API docs)
- [GHL bulk endpoint feature request](https://ideas.gohighlevel.com/apis/p/bulk-contact-update-endpoint) - User requests for bulk operations (not official feature)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries already integrated in Phase 9, proven patterns
- Architecture: HIGH - Builds directly on Phase 9 infrastructure, follows existing project patterns
- Pitfalls: HIGH - Based on Phase 9 implementation lessons, GHL API behavior, FastAPI async patterns

**Research date:** 2026-02-27
**Valid until:** 60 days (stable APIs — GHL v2, FastAPI async patterns, phonenumbers library)

# Phase 9: Backend Foundation - Research

**Researched:** 2026-02-27
**Domain:** GoHighLevel API integration, secure credential storage, HTTP client patterns
**Confidence:** HIGH

## Summary

This phase builds the backend infrastructure for GoHighLevel API integration. The project already has production-ready encryption (`cryptography.fernet`), Firestore persistence patterns, and FastAPI routing conventions in place. Research confirms GoHighLevel's Private Integration Token provides the simplest auth model (static Bearer tokens, no OAuth refresh flow needed). The GHL API uses standard REST patterns with well-documented rate limits (100 req/10s burst, 200k/day). Contact upsert requires manual lookup-then-create-or-update logic since GHL doesn't provide a native upsert endpoint. Phone normalization via `phonenumbers` library is the industry standard for E.164 formatting.

**Primary recommendation:** Reuse existing project patterns (encryption service, Firestore collections, FastAPI routers) and add httpx async client with conservative rate limiting (50 req/10s = half of GHL's 100/10s limit) for safety margin.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Credential Storage:**
- Encrypt Private Integration Tokens using Fernet symmetric encryption (Python `cryptography` library)
- Encryption key stored as environment variable (`GHL_ENCRYPTION_KEY`)
- Connection record fields: name, encrypted_token, location_id, notes (optional), created_at, updated_at, validation_status
- Token last-4 characters stored unencrypted for masked display on edit (`token_last4`)
- On edit, show masked token (`••••••••last4`) — user only enters new token if changing it
- Connections are shared across all allowed users (team-wide, not per-user)
- Connections stored in Firestore `ghl_connections` collection
- Hard delete when removing a connection (no soft delete)

**GHL API Client:**
- Conservative rate limiting: 50 requests per 10 seconds (well under GHL's 100/10s limit)
- Exponential backoff on 429 responses (retry with increasing delay)
- Token validation uses `GET /users/` endpoint — validates both token and Location ID, also useful for contact owner dropdown later
- Pass through GHL error details to caller (don't normalize to generic errors) — frontend/batch engine decides what to show
- Logging: errors with full detail, successful requests as one-line summaries (method, endpoint, status code). Never log tokens or PII.
- Request timeout: Claude's discretion

**Contact Normalization:**
- Phone: assume US +1 country code for numbers without country code, format to E.164
- Email: trim whitespace + lowercase + basic format validation (has @ and domain)
- Names: apply title case as safety net (GHL Prep tool already does this, but normalize again at upsert layer)
- Backend validates early: reject contacts missing both email AND phone before calling GHL (save rate-limited API calls)

**API Surface Design:**
- Dedicated namespace: `/api/ghl/*` (not nested under admin)
- Planned endpoints:
  - `GET /api/ghl/connections` — list all connections
  - `POST /api/ghl/connections` — create connection (validates token on save)
  - `PUT /api/ghl/connections/{id}` — update connection
  - `DELETE /api/ghl/connections/{id}` — hard delete connection
  - `POST /api/ghl/connections/{id}/validate` — re-validate existing connection
  - `GET /api/ghl/connections/{id}/users` — fetch GHL users for contact owner dropdown
  - `POST /api/ghl/contacts/upsert` — upsert single contact
- Accept our own field names (first_name, last_name, phone, email), map to GHL field names internally
- All endpoints require Firebase auth token (no public GHL endpoints)

### Claude's Discretion
- Exact Fernet key rotation strategy
- Request timeout values for GHL API calls
- Retry count and backoff multiplier for 429s
- Internal GHL client class structure and httpx vs requests choice
- Firestore document structure details beyond the specified fields

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CONF-01 | User can add a GHL sub-account connection (name, Private Integration Token, Location ID) in Settings | Pydantic models + Firestore persistence + FastAPI POST endpoint patterns |
| CONF-02 | User can manage multiple GHL sub-account connections (add, edit, delete) | Firestore CRUD operations + existing admin.py router patterns |
| CONF-03 | Token + Location ID are validated together on save via test API call to GHL | httpx async client + GHL `GET /users/` endpoint for validation |
| CONF-04 | Private Integration Token is stored encrypted in Firestore (never sent to frontend) | Existing `encryption.py` service with Fernet symmetric encryption |

</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx | 0.26.0+ | Async HTTP client for GHL API | Already in requirements.txt, async-native, better than requests for FastAPI |
| cryptography | 42.0.0+ | Fernet encryption for tokens | Already in requirements.txt, project already uses it for encryption |
| phonenumbers | 8.13.0+ | Phone number normalization to E.164 | Industry standard, Google's libphonenumber port, handles all edge cases |
| pydantic | 2.5.0+ | Request/response validation | Already project standard, FastAPI native |
| google-cloud-firestore | 2.14.0+ | Connection persistence | Already project standard database |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| tenacity | 8.2.0+ | Retry/backoff logic | Optional — exponential backoff for 429 responses, cleaner than manual retry loops |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| httpx | requests + requests-async | httpx is async-native, requests requires aiohttp wrapper, project already uses httpx in requirements |
| phonenumbers | Manual regex | phonenumbers handles country codes, extensions, validation — regex is error-prone |
| tenacity | Manual retry loop | tenacity is declarative, more readable, but adds dependency — acceptable to use manual loop if preferred |

**Installation:**

```bash
# Already in requirements.txt:
# httpx>=0.26.0
# cryptography>=42.0.0
# pydantic[email]>=2.5.0
# google-cloud-firestore>=2.14.0

# Add phonenumbers (not currently in requirements):
echo "phonenumbers>=8.13.0" >> toolbox/backend/requirements.txt

# Optional (if using tenacity for retry logic):
echo "tenacity>=8.2.0" >> toolbox/backend/requirements.txt
```

## Architecture Patterns

### Recommended Project Structure

```
toolbox/backend/app/
├── api/
│   └── ghl.py                    # NEW: GHL API endpoints (/api/ghl/*)
├── models/
│   └── ghl.py                    # NEW: Pydantic models (GHLConnection, ContactUpsertRequest)
├── services/
│   ├── ghl/                      # NEW: GHL service layer
│   │   ├── __init__.py
│   │   ├── client.py             # GHLClient class (httpx wrapper)
│   │   ├── connection_service.py # CRUD for ghl_connections
│   │   └── normalization.py      # Phone/email/name normalization
│   └── shared/
│       └── encryption.py         # EXISTING: Fernet encryption (already exists)
└── core/
    └── config.py                 # ADD: ghl_encryption_key setting
```

### Pattern 1: GHL API Client (httpx async wrapper)

**What:** Centralized httpx client with rate limiting, retry logic, and error handling

**When to use:** All GHL API interactions

**Example:**

```python
# Source: Project patterns + httpx official docs
from __future__ import annotations

import logging
import asyncio
from typing import Optional, Any
from datetime import datetime, timedelta

import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)

class RateLimiter:
    """Token bucket rate limiter: 50 requests per 10 seconds."""
    def __init__(self, max_requests: int = 50, period_seconds: float = 10.0):
        self.max_requests = max_requests
        self.period_seconds = period_seconds
        self.tokens = max_requests
        self.last_refill = datetime.utcnow()
        self._lock = asyncio.Lock()

    async def acquire(self):
        """Wait until a token is available."""
        async with self._lock:
            now = datetime.utcnow()
            elapsed = (now - self.last_refill).total_seconds()
            if elapsed > self.period_seconds:
                self.tokens = self.max_requests
                self.last_refill = now

            if self.tokens <= 0:
                wait_time = self.period_seconds - elapsed
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                self.tokens = self.max_requests
                self.last_refill = datetime.utcnow()

            self.tokens -= 1

class GHLClient:
    """Async HTTP client for GoHighLevel API v2."""
    BASE_URL = "https://services.leadconnectorhq.com"
    VERSION = "2021-07-28"

    def __init__(self, token: str, location_id: str):
        self.token = token
        self.location_id = location_id
        self.rate_limiter = RateLimiter(max_requests=50, period_seconds=10.0)
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Version": self.VERSION,
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(30.0, connect=10.0),
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()

    async def _request(
        self,
        method: str,
        endpoint: str,
        max_retries: int = 3,
        **kwargs: Any,
    ) -> dict:
        """Make rate-limited request with exponential backoff on 429."""
        await self.rate_limiter.acquire()

        for attempt in range(max_retries):
            try:
                response = await self._client.request(method, endpoint, **kwargs)

                if response.status_code == 429:
                    # Exponential backoff: 2^attempt seconds
                    wait_time = 2 ** attempt
                    logger.warning(f"Rate limited (429), retrying in {wait_time}s")
                    await asyncio.sleep(wait_time)
                    continue

                response.raise_for_status()
                logger.info(f"{method} {endpoint} → {response.status_code}")
                return response.json()

            except httpx.HTTPStatusError as e:
                logger.error(f"GHL API error: {e.response.status_code} {e.response.text}")
                raise
            except httpx.RequestError as e:
                logger.error(f"Request error: {e}")
                raise

        raise Exception("Max retries exceeded")

    async def get_users(self) -> dict:
        """Fetch users list (also validates token + location_id)."""
        return await self._request(
            "GET",
            "/users/",
            params={"locationId": self.location_id}
        )

    async def upsert_contact(self, contact_data: dict) -> dict:
        """Upsert contact (manual lookup-then-update-or-create)."""
        # GHL doesn't have native upsert — must lookup first
        # Implementation in normalization.py service layer
        pass
```

### Pattern 2: Connection CRUD with Encrypted Token

**What:** Firestore persistence with Fernet encryption for Private Integration Token

**When to use:** Creating, updating, listing GHL connections

**Example:**

```python
# Source: Existing project patterns (firestore_service.py, encryption.py)
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from app.services.firestore_service import get_firestore_client
from app.services.shared.encryption import encrypt_value, decrypt_value

logger = logging.getLogger(__name__)

GHL_CONNECTIONS_COLLECTION = "ghl_connections"

async def create_connection(
    name: str,
    token: str,
    location_id: str,
    notes: Optional[str] = None,
) -> dict:
    """Create encrypted GHL connection in Firestore."""
    db = get_firestore_client()

    encrypted_token = encrypt_value(token)
    token_last4 = token[-4:] if len(token) >= 4 else ""

    connection_data = {
        "name": name,
        "encrypted_token": encrypted_token,
        "token_last4": token_last4,
        "location_id": location_id,
        "notes": notes or "",
        "validation_status": "pending",  # Set to "valid" after validation
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }

    doc_ref = db.collection(GHL_CONNECTIONS_COLLECTION).document()
    await doc_ref.set(connection_data)

    return {"id": doc_ref.id, **connection_data}

async def get_connection(connection_id: str, decrypt_token: bool = False) -> Optional[dict]:
    """Get connection by ID, optionally decrypt token."""
    db = get_firestore_client()
    doc = await db.collection(GHL_CONNECTIONS_COLLECTION).document(connection_id).get()

    if not doc.exists:
        return None

    data = doc.to_dict()
    data["id"] = doc.id

    if decrypt_token and "encrypted_token" in data:
        data["token"] = decrypt_value(data["encrypted_token"])

    # Never send encrypted_token to frontend
    data.pop("encrypted_token", None)

    return data
```

### Pattern 3: Phone Normalization to E.164

**What:** Parse US phone numbers and format to E.164 standard (+1XXXXXXXXXX)

**When to use:** Before sending contact data to GHL API

**Example:**

```python
# Source: phonenumbers official docs
import phonenumbers
from phonenumbers import PhoneNumberFormat
import logging

logger = logging.getLogger(__name__)

def normalize_phone(phone: str) -> Optional[str]:
    """Normalize phone to E.164 format, assume US if no country code."""
    if not phone:
        return None

    try:
        # Try parsing with US as default region
        parsed = phonenumbers.parse(phone, "US")

        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(parsed, PhoneNumberFormat.E164)
        else:
            logger.warning(f"Invalid phone number: {phone}")
            return None
    except phonenumbers.NumberParseException as e:
        logger.warning(f"Failed to parse phone {phone}: {e}")
        return None

# Usage:
# normalize_phone("5127481234")       → "+15127481234"
# normalize_phone("+1 512-748-1234")  → "+15127481234"
# normalize_phone("512.748.1234")     → "+15127481234"
```

### Anti-Patterns to Avoid

- **Storing plaintext tokens in Firestore:** Always encrypt with Fernet before persisting
- **Sending encrypted_token to frontend:** Only send token_last4 for masked display
- **Manual phone regex:** Use phonenumbers library — it handles extensions, international prefixes, validation
- **Aggressive rate limiting:** Don't hit 100/10s limit — use 50/10s for safety margin
- **Silent GHL error swallowing:** Pass through GHL error details so frontend can show specific messages

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Phone number parsing | Regex for (XXX) XXX-XXXX | `phonenumbers` library | Handles country codes, extensions, format variations — regex fails on international, tollfree, etc. |
| Retry/backoff logic | Manual sleep loops | `tenacity` library or simple exponential backoff | Declarative, handles jitter, max attempts — manual loops are error-prone |
| Rate limiting | Time-based counters | Token bucket pattern (shown above) | Prevents burst over-usage, smooth distribution |
| Token encryption | Custom cipher | Fernet (already in project) | Symmetric encryption, handles key derivation, message authentication |

**Key insight:** GHL API is standard REST, but phone number normalization and rate limiting have edge cases that libraries solve better than custom code.

## Common Pitfalls

### Pitfall 1: GHL Has No Native Upsert Endpoint

**What goes wrong:** Calling `POST /contacts` with duplicate email creates second contact instead of updating existing one

**Why it happens:** GHL API is create-or-update by contact ID, not by email lookup

**How to avoid:**
1. Call `GET /contacts?email={email}` to search for existing contact
2. If found: `PUT /contacts/{id}` to update
3. If not found: `POST /contacts` to create

**Warning signs:** Duplicate contacts appearing in GHL after bulk sends

**Implementation:**

```python
async def upsert_contact(self, contact_data: dict) -> dict:
    """Upsert contact: lookup by email, update if exists, create if not."""
    email = contact_data.get("email")

    # Try to find existing contact by email
    if email:
        search_result = await self._request(
            "GET",
            "/contacts",
            params={"email": email, "locationId": self.location_id}
        )

        contacts = search_result.get("contacts", [])
        if contacts:
            # Update existing contact
            contact_id = contacts[0]["id"]
            return await self._request(
                "PUT",
                f"/contacts/{contact_id}",
                json=contact_data
            )

    # Create new contact
    return await self._request("POST", "/contacts", json=contact_data)
```

### Pitfall 2: Private Integration Token Rotation Without Grace Period

**What goes wrong:** User rotates token in GHL UI, old token expires immediately, all API calls fail

**Why it happens:** GHL provides 7-day grace period where both old and new tokens work, but user might not know this

**How to avoid:**
1. Document in UI: "GHL provides 7-day overlap when rotating tokens"
2. Store `token_created_at` timestamp
3. Show warning in Settings if token > 90 days old (GHL auto-expires unused tokens at 90 days)
4. On validation failure, check if token is old and prompt user to rotate

**Warning signs:** All GHL API calls failing with 401 Unauthorized

### Pitfall 3: Not Validating Both Token AND Location ID Together

**What goes wrong:** Token is valid but belongs to different location, API calls fail with 403

**Why it happens:** Private Integration Token is scoped to specific Location (sub-account)

**How to avoid:**
- Validate on save by calling `GET /users/?locationId={location_id}` with token
- If successful: both token and location_id are valid together
- If 401: invalid token
- If 403: token valid but wrong location_id

**Warning signs:** Connection saves successfully but all subsequent API calls fail

### Pitfall 4: Rate Limit Burst Exhaustion on Batch Operations

**What goes wrong:** Sending 200 contacts in parallel exhausts burst limit (100 req/10s), causes cascading 429 errors

**Why it happens:** No throttling on concurrent requests

**How to avoid:**
- Use token bucket rate limiter (50 req/10s conservative limit)
- Process contacts sequentially or in small batches (10 at a time)
- Phase 11 (Bulk Send Engine) will handle batch throttling

**Warning signs:** 429 errors during bulk operations, retry storms

### Pitfall 5: Logging Sensitive Data (Tokens, PII)

**What goes wrong:** Production logs contain full API tokens or contact email/phone

**Why it happens:** Verbose logging of request/response bodies

**How to avoid:**
- Never log `Authorization` header
- Never log `encrypted_token` field
- Never log contact email/phone in production
- Log structure: `logger.info(f"{method} {endpoint} → {status_code}")` — no body

**Warning signs:** Tokens visible in CloudWatch/Stackdriver logs

## Code Examples

Verified patterns from official sources:

### httpx Async Client with Bearer Auth

```python
# Source: https://context7.com/encode/httpx/llms.txt
import httpx

async with httpx.AsyncClient(
    base_url="https://services.leadconnectorhq.com",
    headers={
        "Authorization": f"Bearer {token}",
        "Version": "2021-07-28",
        "Content-Type": "application/json",
    },
    timeout=httpx.Timeout(30.0, connect=10.0),
) as client:
    response = await client.get("/users/", params={"locationId": location_id})
    response.raise_for_status()
    users = response.json()
```

### Fernet Encryption/Decryption (Existing Pattern)

```python
# Source: toolbox/backend/app/services/shared/encryption.py (already exists)
from app.services.shared.encryption import encrypt_value, decrypt_value

# Encrypt before saving
encrypted_token = encrypt_value("abc123_private_integration_token")
# Result: "enc:gAAAAABh..."

# Decrypt when needed
plaintext_token = decrypt_value(encrypted_token)
# Result: "abc123_private_integration_token"
```

### Phone Number E.164 Formatting

```python
# Source: https://daviddrysdale.github.io/python-phonenumbers/index
import phonenumbers
from phonenumbers import PhoneNumberFormat

phone = "512-748-1234"
parsed = phonenumbers.parse(phone, "US")

if phonenumbers.is_valid_number(parsed):
    e164 = phonenumbers.format_number(parsed, PhoneNumberFormat.E164)
    # Result: "+15127481234"
```

### Pydantic Model with Email Validation

```python
# Source: Project pattern (existing models/*.py files)
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime

class GHLConnectionCreate(BaseModel):
    """Request model for creating GHL connection."""
    name: str = Field(..., min_length=1, max_length=100, description="Connection name")
    token: str = Field(..., min_length=10, description="Private Integration Token")
    location_id: str = Field(..., description="GHL Location ID")
    notes: Optional[str] = Field(None, max_length=500, description="Optional notes")

class GHLConnectionResponse(BaseModel):
    """Response model for GHL connection (never includes encrypted_token)."""
    id: str
    name: str
    token_last4: str  # Masked display: "••••last4"
    location_id: str
    notes: str
    validation_status: str  # "pending" | "valid" | "invalid"
    created_at: datetime
    updated_at: datetime
```

### FastAPI Router Pattern (Existing Convention)

```python
# Source: toolbox/backend/app/api/admin.py (existing pattern)
from fastapi import APIRouter, HTTPException, Depends
from app.core.auth import require_admin

router = APIRouter()

@router.get("/connections")
async def list_connections(user: dict = Depends(require_admin)):
    """List all GHL connections (admin only)."""
    from app.services.ghl.connection_service import list_connections
    connections = await list_connections()
    return {"connections": connections}

@router.post("/connections")
async def create_connection(
    data: GHLConnectionCreate,
    user: dict = Depends(require_admin)
):
    """Create and validate GHL connection."""
    from app.services.ghl.connection_service import create_and_validate_connection
    connection = await create_and_validate_connection(
        name=data.name,
        token=data.token,
        location_id=data.location_id,
        notes=data.notes,
    )
    return {"connection": connection}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| requests library | httpx for async | httpx 0.23+ (2022) | Native async/await, better FastAPI integration |
| Manual OAuth 2.0 flow | Private Integration Token | GHL API v2 (2021) | Simpler for internal tools, no refresh token management |
| JSON allowlist files | Firestore persistence | Project migration (2025) | Centralized storage, no local file sync issues |
| Manual retry loops | Declarative retry (tenacity) | tenacity 8.0+ (2022) | Cleaner code, configurable backoff |

**Deprecated/outdated:**
- GHL API v1: Replaced by v2 in 2021, uses different endpoints and authentication
- OAuth for internal tools: Private Integration Token is simpler, OAuth is for marketplace apps

## Open Questions

1. **Should we cache GHL users list for contact owner dropdown?**
   - What we know: `GET /users/` is called on connection validation, could cache result
   - What's unclear: How often user list changes, whether to cache in Firestore or in-memory
   - Recommendation: Phase 9 fetches fresh on each request, Phase 10 can add caching if needed

2. **Should we store GHL contact IDs after upsert for faster updates?**
   - What we know: Upsert requires email lookup first (no native upsert endpoint)
   - What's unclear: Whether to persist mapping of email → GHL contact ID to skip lookup
   - Recommendation: Don't persist for Phase 9 — lookup overhead is acceptable for single contact upsert, Phase 11 (Bulk Send) can optimize

3. **How to handle connection name uniqueness?**
   - What we know: Users can create multiple connections to different GHL locations
   - What's unclear: Should connection names be unique, or can duplicates exist?
   - Recommendation: Don't enforce uniqueness in Phase 9 — user can create "Main Location", "Main Location 2" if needed

## Validation Architecture

> Phase 9 validation is primarily integration testing — verify API client works against real GHL sandbox account.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 7.4.0+ with pytest-asyncio 0.23.0+ |
| Config file | None — add `pytest.ini` in Wave 0 |
| Quick run command | `pytest backend/tests/test_ghl_client.py -x` |
| Full suite command | `pytest backend/tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CONF-01 | Create connection with encrypted token | unit | `pytest tests/test_ghl_connection_service.py::test_create_connection -x` | ❌ Wave 0 |
| CONF-02 | CRUD operations on connections | unit | `pytest tests/test_ghl_connection_service.py::test_crud -x` | ❌ Wave 0 |
| CONF-03 | Validate token + location_id via GHL API | integration | `pytest tests/test_ghl_client.py::test_validate_connection -x` | ❌ Wave 0 |
| CONF-04 | Token encrypted before Firestore save | unit | `pytest tests/test_ghl_connection_service.py::test_token_encryption -x` | ❌ Wave 0 |

**Additional coverage:**
- Phone normalization: `pytest tests/test_ghl_normalization.py -x`
- Rate limiting: `pytest tests/test_ghl_client.py::test_rate_limiting -x`
- Upsert logic: `pytest tests/test_ghl_client.py::test_upsert_contact -x`

### Sampling Rate

- **Per task commit:** `pytest backend/tests/test_ghl_client.py -x` (quick smoke test)
- **Per wave merge:** `pytest backend/tests/ -v` (full suite)
- **Phase gate:** Full suite green + manual test with real GHL sandbox before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `backend/pytest.ini` — basic config (asyncio mode, testpaths)
- [ ] `backend/tests/test_ghl_client.py` — GHLClient unit/integration tests
- [ ] `backend/tests/test_ghl_connection_service.py` — Connection CRUD tests
- [ ] `backend/tests/test_ghl_normalization.py` — Phone/email normalization tests
- [ ] `backend/tests/conftest.py` — Shared fixtures (mock Firestore, test encryption key)

## Sources

### Primary (HIGH confidence)

- [GoHighLevel API Official Docs](https://marketplace.gohighlevel.com/docs/) - Private Integration Token authentication, rate limits, contact endpoints
- [GoHighLevel Private Integration Token](https://marketplace.gohighlevel.com/docs/Authorization/PrivateIntegrationsToken/) - Bearer token usage, required headers
- Context7: `/gohighlevel/highlevel-api-docs` - API v2 endpoints, authentication, rate limits
- Context7: `/encode/httpx` - Async client patterns, timeout configuration, Bearer auth
- Context7: `/websites/daviddrysdale_github_io_python-phonenumbers` - E.164 formatting, US country code
- Project codebase: `toolbox/backend/app/services/shared/encryption.py` - Existing Fernet encryption service
- Project codebase: `toolbox/backend/app/services/firestore_service.py` - Firestore persistence patterns
- Project codebase: `toolbox/backend/app/core/config.py` - Pydantic Settings patterns

### Secondary (MEDIUM confidence)

- [GHL Support Portal - Private Integrations](https://help.gohighlevel.com/support/solutions/articles/155000003054-private-integrations-everything-you-need-to-know) - 90-day token rotation recommendation, 7-day grace period

### Tertiary (LOW confidence)

None — all key findings verified via official docs or Context7.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries already in project or well-documented official libraries
- Architecture: HIGH - Reusing existing project patterns (Firestore, FastAPI, encryption)
- Pitfalls: HIGH - Documented in official GHL support + Context7 API docs
- Validation: MEDIUM - Test framework exists (pytest in requirements), but no test files written yet

**Research date:** 2026-02-27
**Valid until:** 2026-04-27 (60 days — GHL API is stable, httpx/pydantic patterns unlikely to change)

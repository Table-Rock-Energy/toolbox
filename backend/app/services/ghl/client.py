"""GoHighLevel API client with rate limiting and retry logic.

Provides async HTTP client for GHL API v2 with:
- Token bucket rate limiting (50 requests per 10 seconds)
- Exponential backoff retry on 429 (up to 3 retries)
- Contact upsert (search by email, create or update)
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

import httpx

from app.services.ghl.normalization import normalize_contact, validate_contact

logger = logging.getLogger(__name__)


# Custom exceptions
class GHLAPIError(Exception):
    """Base exception for GHL API errors."""
    pass


class GHLRateLimitError(GHLAPIError):
    """Raised when rate limit retries are exhausted."""
    pass


class GHLAuthError(GHLAPIError):
    """Raised when authentication fails (401)."""
    pass


class RateLimiter:
    """Token bucket rate limiter for API requests.

    Allows burst of max_requests, then refills at rate of max_requests per period.
    """

    def __init__(self, max_requests: int = 50, period_seconds: float = 10.0):
        """Initialize rate limiter.

        Args:
            max_requests: Maximum number of requests allowed in the period
            period_seconds: Time period in seconds for the max_requests limit
        """
        self.max_requests = max_requests
        self.period_seconds = period_seconds
        self.tokens = max_requests
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Acquire a token from the bucket, waiting if necessary."""
        async with self._lock:
            # Refill tokens based on time elapsed
            now = time.monotonic()
            elapsed = now - self.last_refill

            # Add tokens based on elapsed time
            refill_amount = (elapsed / self.period_seconds) * self.max_requests
            self.tokens = min(self.max_requests, self.tokens + refill_amount)
            self.last_refill = now

            # Wait if no tokens available
            if self.tokens < 1:
                wait_time = ((1 - self.tokens) / self.max_requests) * self.period_seconds
                logger.debug(f"Rate limit: waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
                self.tokens = 1

            # Consume a token
            self.tokens -= 1


class GHLClient:
    """Async HTTP client for GoHighLevel API v2.

    Context manager that creates an httpx.AsyncClient with proper auth headers.
    """

    BASE_URL = "https://services.leadconnectorhq.com"
    VERSION = "2021-07-28"

    def __init__(self, token: str, location_id: str):
        """Initialize GHL client.

        Args:
            token: GHL Private Integration Token
            location_id: GHL Location ID
        """
        self.token = token
        self.location_id = location_id
        self.rate_limiter = RateLimiter(max_requests=50, period_seconds=10.0)
        self.client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        """Create async HTTP client with auth headers."""
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Version": self.VERSION,
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(timeout=30.0, connect=10.0),
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close async HTTP client."""
        if self.client:
            await self.client.aclose()

    async def _request(
        self, method: str, endpoint: str, max_retries: int = 3, **kwargs
    ) -> dict:
        """Make rate-limited HTTP request with retry on 429.

        Args:
            method: HTTP method (GET, POST, PUT, etc.)
            endpoint: API endpoint path (e.g., "/contacts/")
            max_retries: Maximum number of retries on 429
            **kwargs: Additional arguments for httpx request

        Returns:
            Response JSON as dict

        Raises:
            GHLAuthError: On 401 authentication failure
            GHLRateLimitError: When retries exhausted on 429
            GHLAPIError: On other HTTP errors
        """
        if not self.client:
            raise GHLAPIError("Client not initialized - use async with context manager")

        for attempt in range(max_retries + 1):
            # Acquire rate limit token
            await self.rate_limiter.acquire()

            try:
                response = await self.client.request(method, endpoint, **kwargs)
                response.raise_for_status()

                # Log success
                logger.info(f"{method} {endpoint} -> {response.status_code}")

                return response.json()

            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code

                # Handle auth errors
                if status_code == 401:
                    logger.error(f"{method} {endpoint} -> 401 Unauthorized")
                    raise GHLAuthError("Authentication failed - invalid token") from e

                # Handle rate limiting with exponential backoff
                if status_code == 429 and attempt < max_retries:
                    backoff_time = 2 ** attempt  # 1s, 2s, 4s
                    logger.warning(
                        f"{method} {endpoint} -> 429 Rate Limited (attempt {attempt + 1}/{max_retries}), "
                        f"backing off {backoff_time}s"
                    )
                    await asyncio.sleep(backoff_time)
                    continue

                # Max retries exhausted on 429
                if status_code == 429:
                    logger.error(f"{method} {endpoint} -> 429 Rate Limited (retries exhausted)")
                    raise GHLRateLimitError("Rate limit retries exhausted") from e

                # Other HTTP errors - log and re-raise
                logger.error(f"{method} {endpoint} -> {status_code}: {e.response.text}")
                raise GHLAPIError(f"HTTP {status_code}: {e.response.text}") from e

            except httpx.RequestError as e:
                logger.error(f"{method} {endpoint} -> RequestError: {e}")
                raise GHLAPIError(f"Request failed: {e}") from e

        # Should never reach here
        raise GHLRateLimitError("Max retries reached")

    async def get_users(self) -> dict:
        """Get users for the location.

        Used for token validation and contact owner dropdown.

        Returns:
            Response dict with "users" key
        """
        return await self._request("GET", "/users/", params={"locationId": self.location_id})

    async def search_contacts(self, email: str) -> list[dict]:
        """Search for contacts by email.

        Args:
            email: Email address to search for

        Returns:
            List of matching contact dicts
        """
        response = await self._request(
            "GET", "/contacts/", params={"email": email, "locationId": self.location_id}
        )
        return response.get("contacts", [])

    async def create_contact(self, contact_data: dict) -> dict:
        """Create a new contact.

        Args:
            contact_data: Contact data dict (must include locationId)

        Returns:
            Created contact dict
        """
        return await self._request("POST", "/contacts/", json=contact_data)

    async def update_contact(self, contact_id: str, contact_data: dict) -> dict:
        """Update an existing contact.

        Args:
            contact_id: GHL contact ID
            contact_data: Contact data dict (partial update)

        Returns:
            Updated contact dict
        """
        return await self._request("PUT", f"/contacts/{contact_id}", json=contact_data)

    async def upsert_contact(self, contact_data: dict) -> dict:
        """Upsert a contact (search by email, create or update).

        Normalizes and validates contact data before API calls.

        Args:
            contact_data: Contact data dict with our field names (first_name, last_name, etc.)

        Returns:
            Dict with keys: action ("created" | "updated"), contact (GHL response), ghl_contact_id

        Raises:
            ValueError: If contact validation fails
            GHLAPIError: On API errors
        """
        # Normalize contact data
        normalized = normalize_contact(contact_data)

        # Validate contact
        is_valid, error = validate_contact(normalized)
        if not is_valid:
            raise ValueError(error)

        # Map our field names to GHL field names
        ghl_data = {
            "locationId": self.location_id,
        }

        if normalized.get("first_name"):
            ghl_data["firstName"] = normalized["first_name"]

        if normalized.get("last_name"):
            ghl_data["lastName"] = normalized["last_name"]

        if normalized.get("email"):
            ghl_data["email"] = normalized["email"]

        if normalized.get("phone"):
            ghl_data["phone"] = normalized["phone"]

        if normalized.get("address1"):
            ghl_data["address1"] = normalized["address1"]

        if normalized.get("city"):
            ghl_data["city"] = normalized["city"]

        if normalized.get("state"):
            ghl_data["state"] = normalized["state"]

        if normalized.get("postal_code"):
            ghl_data["postalCode"] = normalized["postal_code"]

        if normalized.get("tags"):
            ghl_data["tags"] = normalized["tags"]

        if normalized.get("assigned_to"):
            ghl_data["assignedTo"] = normalized["assigned_to"]

        # Search by email first (if available)
        if normalized.get("email"):
            existing = await self.search_contacts(normalized["email"])

            if existing:
                # Update existing contact
                contact_id = existing[0]["id"]
                contact_response = await self.update_contact(contact_id, ghl_data)

                return {
                    "action": "updated",
                    "contact": contact_response,
                    "ghl_contact_id": contact_id,
                }

        # Create new contact
        contact_response = await self.create_contact(ghl_data)
        contact_id = contact_response.get("contact", {}).get("id") or contact_response.get("id")

        return {
            "action": "created",
            "contact": contact_response,
            "ghl_contact_id": contact_id,
        }

"""HTTP retry utilities for external API calls.

Wraps httpx (async) and requests (sync) calls with exponential backoff.
Only retries on 5xx, 429 (rate limit), and timeout errors — never on 4xx.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional

import httpx
import requests

logger = logging.getLogger(__name__)

DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_SECONDS = [1.0, 2.0, 4.0]

_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def _should_retry(status_code: int) -> bool:
    """Check if a response status code is retryable."""
    return status_code in _RETRYABLE_STATUS_CODES


async def async_request_with_retry(
    method: str,
    url: str,
    *,
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff: Optional[list[float]] = None,
    timeout: float = 15.0,
    **kwargs: Any,
) -> httpx.Response:
    """Make an async HTTP request with retry on transient failures.

    Args:
        method: HTTP method (GET, POST, etc.).
        url: Request URL.
        max_retries: Maximum number of attempts.
        backoff: List of sleep durations between retries.
        timeout: Request timeout in seconds.
        **kwargs: Passed to httpx.AsyncClient.request().

    Returns:
        httpx.Response on success.

    Raises:
        httpx.HTTPStatusError: On non-retryable 4xx errors.
        httpx.TimeoutException: If all retries are exhausted due to timeouts.
        Exception: If all retries are exhausted.
    """
    delays = backoff or DEFAULT_BACKOFF_SECONDS
    last_exception: Optional[Exception] = None

    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.request(method, url, **kwargs)

                if response.status_code < 400:
                    return response

                if not _should_retry(response.status_code):
                    return response

                logger.warning(
                    f"Retryable HTTP {response.status_code} from {url} "
                    f"(attempt {attempt + 1}/{max_retries})"
                )
                last_exception = httpx.HTTPStatusError(
                    f"HTTP {response.status_code}",
                    request=response.request,
                    response=response,
                )

        except httpx.TimeoutException as e:
            logger.warning(
                f"Timeout requesting {url} (attempt {attempt + 1}/{max_retries})"
            )
            last_exception = e

        except httpx.RequestError as e:
            logger.warning(
                f"Request error for {url}: {e} (attempt {attempt + 1}/{max_retries})"
            )
            last_exception = e

        if attempt < max_retries - 1:
            delay = delays[min(attempt, len(delays) - 1)]
            await asyncio.sleep(delay)

    raise last_exception  # type: ignore[misc]


def sync_request_with_retry(
    method: str,
    url: str,
    *,
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff: Optional[list[float]] = None,
    timeout: float = 10.0,
    **kwargs: Any,
) -> requests.Response:
    """Make a synchronous HTTP request with retry on transient failures.

    Args:
        method: HTTP method (GET, POST, etc.).
        url: Request URL.
        max_retries: Maximum number of attempts.
        backoff: List of sleep durations between retries.
        timeout: Request timeout in seconds.
        **kwargs: Passed to requests.request().

    Returns:
        requests.Response on success.

    Raises:
        requests.exceptions.Timeout: If all retries are exhausted due to timeouts.
        requests.exceptions.RequestException: If all retries are exhausted.
    """
    delays = backoff or DEFAULT_BACKOFF_SECONDS
    last_exception: Optional[Exception] = None

    for attempt in range(max_retries):
        try:
            response = requests.request(method, url, timeout=timeout, **kwargs)

            if response.status_code < 400:
                return response

            if not _should_retry(response.status_code):
                return response

            logger.warning(
                f"Retryable HTTP {response.status_code} from {url} "
                f"(attempt {attempt + 1}/{max_retries})"
            )
            last_exception = requests.exceptions.HTTPError(
                f"HTTP {response.status_code}", response=response
            )

        except requests.exceptions.Timeout as e:
            logger.warning(
                f"Timeout requesting {url} (attempt {attempt + 1}/{max_retries})"
            )
            last_exception = e

        except requests.exceptions.RequestException as e:
            logger.warning(
                f"Request error for {url}: {e} (attempt {attempt + 1}/{max_retries})"
            )
            last_exception = e

        if attempt < max_retries - 1:
            delay = delays[min(attempt, len(delays) - 1)]
            time.sleep(delay)

    raise last_exception  # type: ignore[misc]

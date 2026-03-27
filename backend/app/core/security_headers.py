"""Security headers middleware for all API responses.

Adds CSP, HSTS, X-Frame-Options, X-Content-Type-Options,
Referrer-Policy, and Permissions-Policy headers.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to every response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # SEC-01: Content Security Policy
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )

        # SEC-02: HTTP Strict Transport Security
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # SEC-03: X-Frame-Options
        response.headers["X-Frame-Options"] = "DENY"

        # SEC-04: X-Content-Type-Options
        response.headers["X-Content-Type-Options"] = "nosniff"

        # SEC-05: Referrer-Policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # SEC-06: Permissions-Policy
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

        return response

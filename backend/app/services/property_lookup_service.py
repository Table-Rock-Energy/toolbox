"""Property lookup service (stub).

Zillow web scraping was removed due to ToS violations.
A legitimate property data API integration can be added later.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class PropertyLookupResult:
    """Result of a property value lookup."""
    address: str = ""
    property_type: str = ""  # "residential", "commercial", "land", "unknown"
    estimated_value: Optional[float] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[float] = None
    sqft: Optional[int] = None
    lot_size: Optional[str] = None
    year_built: Optional[int] = None
    zestimate: Optional[float] = None
    zillow_url: Optional[str] = None
    found: bool = False
    error: Optional[str] = None


def lookup_property(
    street: str,
    city: str,
    state: str,
    zip_code: str = "",
) -> PropertyLookupResult:
    """Property lookup is currently disabled.

    Zillow web scraping was removed due to ToS violations.
    A legitimate property data API integration can be added later.
    """
    return PropertyLookupResult(
        address=", ".join(p for p in [street, city, state, zip_code] if p),
        error="Property lookup not available (pending API integration)",
    )

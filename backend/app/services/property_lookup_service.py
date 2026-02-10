"""Property lookup service for Zillow property value estimates.

Uses Zillow's public search API to look up property values and details
for validated addresses. Results include estimated value, property type
(residential/commercial), and basic property info.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# Rate limiting for Zillow requests
_zillow_timestamps: list[float] = []
MAX_ZILLOW_QPS = 5  # Conservative rate limit


def _zillow_rate_limit():
    """Enforce rate limit for Zillow requests."""
    global _zillow_timestamps
    now = time.time()
    _zillow_timestamps = [t for t in _zillow_timestamps if now - t < 1.0]
    if len(_zillow_timestamps) >= MAX_ZILLOW_QPS:
        sleep_time = 1.0 - (now - _zillow_timestamps[0])
        if sleep_time > 0:
            time.sleep(sleep_time)
    _zillow_timestamps.append(time.time())


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
    """Look up property info using Zillow's search API.

    This uses Zillow's public web search endpoint to find property data.
    """
    result = PropertyLookupResult()

    address_parts = [p for p in [street, city, state, zip_code] if p]
    if len(address_parts) < 2:
        result.error = "Insufficient address info"
        return result

    address_query = ", ".join(address_parts)
    result.address = address_query

    try:
        _zillow_rate_limit()

        # Use Zillow's public search API
        response = requests.get(
            "https://www.zillow.com/search/GetSearchPageState.htm",
            params={
                "searchQueryState": f'{{"searchQuery":"{address_query}","mapBounds":null,"isMapVisible":false,"filterState":{{}},"isListVisible":true}}',
                "wants": '{"cat1":["listResults"]}',
                "requestId": "1",
            },
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; TableRockTools/1.0)",
                "Accept": "application/json",
            },
            timeout=10,
        )

        if response.status_code != 200:
            # Zillow may block; fall back gracefully
            result.error = "Property lookup unavailable"
            return result

        data = response.json()

        # Parse results
        results_list = (
            data.get("cat1", {})
            .get("searchResults", {})
            .get("listResults", [])
        )

        if not results_list:
            result.error = "No property found"
            return result

        # Take the first (best match) result
        prop = results_list[0]
        hdp_data = prop.get("hdpData", {}).get("homeInfo", {})

        result.found = True
        result.estimated_value = hdp_data.get("zestimate") or prop.get("unformattedPrice")
        result.zestimate = hdp_data.get("zestimate")
        result.bedrooms = hdp_data.get("bedrooms")
        result.bathrooms = hdp_data.get("bathrooms")
        result.sqft = hdp_data.get("livingArea")
        result.year_built = hdp_data.get("yearBuilt")
        result.lot_size = hdp_data.get("lotAreaString")
        result.zillow_url = prop.get("detailUrl")
        if result.zillow_url and not result.zillow_url.startswith("http"):
            result.zillow_url = f"https://www.zillow.com{result.zillow_url}"

        # Determine property type from Zillow data
        home_type = hdp_data.get("homeType", "").upper()
        if home_type in ("SINGLE_FAMILY", "CONDO", "TOWNHOUSE", "MULTI_FAMILY", "MANUFACTURED", "APARTMENT"):
            result.property_type = "residential"
        elif home_type in ("LOT", "VACANT_LAND"):
            result.property_type = "land"
        elif home_type:
            result.property_type = "commercial"
        else:
            result.property_type = "unknown"

    except requests.exceptions.Timeout:
        result.error = "Property lookup timeout"
    except requests.exceptions.RequestException as e:
        result.error = f"Property lookup error: {str(e)}"
    except Exception as e:
        logger.warning(f"Property lookup failed for {address_query}: {e}")
        result.error = f"Lookup error: {str(e)}"

    return result

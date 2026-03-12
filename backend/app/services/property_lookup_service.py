"""Property/place lookup service using Google Places API.

Identifies institutional addresses (senior facilities, correctional facilities,
hospitals, etc.) by searching for nearby places at a geocoded lat/lng.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)

# Rate limiting (shared with address validation — same API key)
_request_timestamps: list[float] = []
MAX_QPS = 40

# Place types that indicate institutional addresses worth flagging
INSTITUTIONAL_TYPES = {
    # Senior / assisted living
    "nursing_home": "senior_facility",
    "senior_citizen_center": "senior_facility",
    # Correctional
    "prison": "correctional_facility",
    # Medical
    "hospital": "medical_facility",
    # Other institutional
    "cemetery": "cemetery",
    "church": "religious_institution",
    "funeral_home": "funeral_home",
}

# Text search keywords that help identify senior living when type alone isn't enough
SENIOR_KEYWORDS = {
    "senior living", "assisted living", "nursing home", "retirement",
    "memory care", "skilled nursing", "long term care", "long-term care",
    "rehabilitation center", "convalescent",
}

CORRECTIONAL_KEYWORDS = {
    "prison", "jail", "correctional", "detention", "penitentiary",
    "sheriff", "inmate",
}


@dataclass
class PlaceLookupResult:
    """Result of a place/institutional lookup for an address."""
    address: str = ""
    place_type: str = ""  # "senior_facility", "correctional_facility", etc.
    place_name: str = ""  # Name of the identified place
    place_flag: str = ""  # Human-readable flag reason
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    found: bool = False
    error: Optional[str] = None


def _rate_limit():
    """Enforce QPS rate limit."""
    global _request_timestamps
    now = time.time()
    _request_timestamps = [t for t in _request_timestamps if now - t < 1.0]
    if len(_request_timestamps) >= MAX_QPS:
        sleep_time = 1.0 - (now - _request_timestamps[0])
        if sleep_time > 0:
            time.sleep(sleep_time)
    _request_timestamps.append(time.time())


def _get_api_key() -> Optional[str]:
    """Get the Google API key for Places requests."""
    return settings.google_api_key or settings.google_maps_api_key


def _classify_place(place: dict) -> tuple[str, str]:
    """Classify a place result into a place_type and flag reason.

    Returns:
        (place_type, place_flag) tuple. Empty strings if not institutional.
    """
    place_types = set(place.get("types", []))
    place_name = place.get("name", "").lower()

    # Check explicit institutional types from Google
    for gtype, our_type in INSTITUTIONAL_TYPES.items():
        if gtype in place_types:
            return our_type, f"Address is at or near: {place.get('name', 'unknown')}"

    # Keyword matching on place name for senior facilities
    for keyword in SENIOR_KEYWORDS:
        if keyword in place_name:
            return "senior_facility", f"Address is at or near senior facility: {place.get('name', 'unknown')}"

    # Keyword matching for correctional
    for keyword in CORRECTIONAL_KEYWORDS:
        if keyword in place_name:
            return "correctional_facility", f"Address is at or near correctional facility: {place.get('name', 'unknown')}"

    return "", ""


def lookup_place(
    latitude: float,
    longitude: float,
    address: str = "",
) -> PlaceLookupResult:
    """Look up nearby institutional places at a geocoded address.

    Uses Google Places Nearby Search API to find senior facilities,
    correctional facilities, hospitals, etc. within a small radius.

    Args:
        latitude: Geocoded latitude from address validation.
        longitude: Geocoded longitude from address validation.
        address: Original address string (for result context).

    Returns:
        PlaceLookupResult with place_type and place_flag if institutional.
    """
    result = PlaceLookupResult(
        address=address,
        latitude=latitude,
        longitude=longitude,
    )

    api_key = _get_api_key()
    if not api_key:
        result.error = "Google API key not configured"
        return result

    try:
        from app.services.shared.http_retry import sync_request_with_retry

        _rate_limit()

        # Search nearby for institutional places (150m radius — tight to the address)
        response = sync_request_with_retry(
            "GET",
            "https://maps.googleapis.com/maps/api/place/nearbysearch/json",
            params={
                "location": f"{latitude},{longitude}",
                "radius": 150,
                "key": api_key,
            },
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()

        if data.get("status") not in ("OK", "ZERO_RESULTS"):
            result.error = f"Places API error: {data.get('status')}"
            return result

        # Check each result for institutional types
        for place in data.get("results", []):
            place_type, place_flag = _classify_place(place)
            if place_type:
                result.found = True
                result.place_type = place_type
                result.place_name = place.get("name", "")
                result.place_flag = place_flag
                return result

    except requests.exceptions.Timeout:
        result.error = "Places API timeout"
    except requests.exceptions.RequestException as e:
        result.error = f"Places API error: {str(e)}"
    except Exception as e:
        logger.exception(f"Unexpected error in place lookup: {e}")
        result.error = f"Unexpected error: {str(e)}"

    return result


def lookup_places_batch(
    entries: list[dict],
    progress_callback=None,
) -> list[PlaceLookupResult]:
    """Look up places for a batch of entries that have lat/lng.

    Args:
        entries: List of entry dicts with latitude/longitude fields.
        progress_callback: Optional callback(index, total, result).

    Returns:
        List of PlaceLookupResult for entries that had coordinates.
    """
    results: list[PlaceLookupResult] = []
    total = len(entries)

    for i, entry in enumerate(entries):
        lat = entry.get("latitude")
        lng = entry.get("longitude")

        if lat is None or lng is None:
            results.append(PlaceLookupResult(error="No coordinates"))
            if progress_callback:
                progress_callback(i, total, None)
            continue

        street = entry.get("mailing_address") or entry.get("address") or ""
        city = entry.get("city") or ""
        state = entry.get("state") or ""
        address_str = ", ".join(p for p in [street, city, state] if p)

        place_result = lookup_place(
            latitude=lat,
            longitude=lng,
            address=address_str,
        )
        results.append(place_result)

        if progress_callback:
            progress_callback(i, total, place_result)

    return results

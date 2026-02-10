"""Address validation service using Google Maps Geocoding API."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)

# Rate limiting
_request_timestamps: list[float] = []
MAX_QPS = 40  # Stay under Google's 50 QPS limit


@dataclass
class AddressValidationResult:
    """Result of validating a single address."""
    original_street: str = ""
    original_city: str = ""
    original_state: str = ""
    original_zip: str = ""
    validated_street: str = ""
    validated_street_2: str = ""
    validated_city: str = ""
    validated_state: str = ""
    validated_zip: str = ""
    formatted_address: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    property_type: str = ""  # "residential", "commercial", "unknown"
    confidence: str = "none"  # "high", "partial", "none"
    changed: bool = False
    changes: list[str] = field(default_factory=list)
    error: Optional[str] = None


# Google Maps result types that indicate residential vs commercial
RESIDENTIAL_TYPES = {"street_address", "premise", "subpremise"}
COMMERCIAL_TYPES = {"establishment", "store", "shopping_mall", "point_of_interest"}


def _classify_property_type(result_types: list[str], address_components: list[dict]) -> str:
    """Classify an address as residential or commercial based on geocoding result types."""
    type_set = set(result_types)

    if type_set & COMMERCIAL_TYPES:
        return "commercial"

    if type_set & RESIDENTIAL_TYPES:
        return "residential"

    # Check if PO Box
    for comp in address_components:
        if "post_box" in comp.get("types", []):
            return "po_box"

    # Default to residential for street-level results
    if "route" in type_set or "street_address" in type_set:
        return "residential"

    return "unknown"


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


def _build_address_string(
    street: str,
    city: str,
    state: str,
    zip_code: str,
) -> str:
    """Build a single address string from components."""
    parts = []
    if street:
        parts.append(street.strip())
    if city:
        parts.append(city.strip())
    if state and zip_code:
        parts.append(f"{state.strip()} {zip_code.strip()}")
    elif state:
        parts.append(state.strip())
    elif zip_code:
        parts.append(zip_code.strip())
    return ", ".join(parts)


def _extract_component(components: list[dict], comp_type: str, use_short: bool = True) -> str:
    """Extract a specific component from Google's address_components."""
    for comp in components:
        if comp_type in comp.get("types", []):
            return comp.get("short_name" if use_short else "long_name", "")
    return ""


def validate_address(
    street: str = "",
    street_2: str = "",
    city: str = "",
    state: str = "",
    zip_code: str = "",
) -> AddressValidationResult:
    """Validate and correct a single address using Google Maps Geocoding API.

    Returns an AddressValidationResult with corrected address fields.
    """
    result = AddressValidationResult(
        original_street=street,
        original_city=city,
        original_state=state,
        original_zip=zip_code,
    )

    if not settings.google_maps_api_key:
        result.error = "Google Maps API key not configured"
        return result

    address_string = _build_address_string(street, city, state, zip_code)
    if not address_string.strip():
        result.confidence = "none"
        return result

    try:
        from app.services.shared.http_retry import sync_request_with_retry

        _rate_limit()

        response = sync_request_with_retry(
            "GET",
            "https://maps.googleapis.com/maps/api/geocode/json",
            params={
                "address": address_string,
                "key": settings.google_maps_api_key,
            },
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()

        if data.get("status") != "OK" or not data.get("results"):
            if data.get("status") == "ZERO_RESULTS":
                result.confidence = "none"
                result.error = "Address not found"
            else:
                result.error = f"Geocoding API error: {data.get('status')}"
            return result

        top_result = data["results"][0]
        components = top_result.get("address_components", [])
        is_partial = top_result.get("partial_match", False)

        # Extract validated components
        street_number = _extract_component(components, "street_number")
        route = _extract_component(components, "route")
        locality = _extract_component(components, "locality", use_short=False)
        admin_area = _extract_component(components, "administrative_area_level_1")
        postal_code = _extract_component(components, "postal_code")
        subpremise = _extract_component(components, "subpremise")

        validated_street = f"{street_number} {route}".strip() if street_number or route else ""
        validated_street_2 = ""
        if subpremise:
            validated_street_2 = f"#{subpremise}"
        elif street_2:
            validated_street_2 = street_2

        result.validated_street = validated_street
        result.validated_street_2 = validated_street_2
        result.validated_city = locality
        result.validated_state = admin_area
        result.validated_zip = postal_code
        result.formatted_address = top_result.get("formatted_address", "")
        result.confidence = "partial" if is_partial else "high"

        # Extract coordinates
        geometry = top_result.get("geometry", {}).get("location", {})
        result.latitude = geometry.get("lat")
        result.longitude = geometry.get("lng")

        # Classify property type
        result_types = top_result.get("types", [])
        result.property_type = _classify_property_type(result_types, components)

        # Detect changes
        changes = []
        if validated_street and street and validated_street.lower() != street.strip().lower():
            changes.append(f"Street: '{street}' → '{validated_street}'")
        if locality and city and locality.lower() != city.strip().lower():
            changes.append(f"City: '{city}' → '{locality}'")
        if admin_area and state and admin_area.upper() != state.strip().upper():
            changes.append(f"State: '{state}' → '{admin_area}'")
        if postal_code and zip_code and not zip_code.strip().startswith(postal_code):
            changes.append(f"ZIP: '{zip_code}' → '{postal_code}'")

        result.changed = len(changes) > 0
        result.changes = changes

    except requests.exceptions.Timeout:
        result.error = "Geocoding API timeout"
    except requests.exceptions.RequestException as e:
        result.error = f"Geocoding API error: {str(e)}"
    except Exception as e:
        logger.exception(f"Unexpected error in address validation: {e}")
        result.error = f"Unexpected error: {str(e)}"

    return result


def validate_addresses_batch(
    entries: list[dict],
    street_field: str = "mailing_address",
    street_2_field: str = "mailing_address_2",
    city_field: str = "city",
    state_field: str = "state",
    zip_field: str = "zip_code",
    progress_callback=None,
) -> list[dict]:
    """Validate addresses for a batch of entries.

    Args:
        entries: List of entry dicts.
        street_field: Field name for street address.
        street_2_field: Field name for secondary address.
        city_field: Field name for city.
        state_field: Field name for state.
        zip_field: Field name for zip code.
        progress_callback: Optional callback(index, total, result) for progress.

    Returns:
        Updated entries list with corrected addresses.
    """
    total = len(entries)
    updated = []

    for i, entry in enumerate(entries):
        street = entry.get(street_field) or ""
        street_2 = entry.get(street_2_field) or ""
        city_val = entry.get(city_field) or ""
        state_val = entry.get(state_field) or ""
        zip_val = entry.get(zip_field) or ""

        # Skip entries without any address
        if not any([street, city_val, state_val, zip_val]):
            updated.append(entry)
            if progress_callback:
                progress_callback(i, total, None)
            continue

        result = validate_address(
            street=street,
            street_2=street_2,
            city=city_val,
            state=state_val,
            zip_code=zip_val,
        )

        if result.confidence in ("high", "partial") and result.changed:
            entry_copy = dict(entry)
            if result.validated_street:
                entry_copy[street_field] = result.validated_street
            if result.validated_street_2:
                entry_copy[street_2_field] = result.validated_street_2
            if result.validated_city:
                entry_copy[city_field] = result.validated_city
            if result.validated_state:
                entry_copy[state_field] = result.validated_state
            if result.validated_zip:
                entry_copy[zip_field] = result.validated_zip
            updated.append(entry_copy)
        else:
            updated.append(entry)

        if progress_callback:
            progress_callback(i, total, result)

    return updated

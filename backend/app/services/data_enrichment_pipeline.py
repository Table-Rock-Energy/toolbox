"""Data enrichment service for Extract and Title tools.

Orchestrates multi-step processing:
1. Address validation (Google Maps Geocoding API)
2. Property lookup (Zillow value + type confirmation)
3. Name validation (Gemini AI)
4. Name splitting (multiple names → individual entries)

Yields progress events as JSON-serializable dicts for streaming.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncGenerator

from app.core.config import settings

logger = logging.getLogger(__name__)

# Tool-specific field mappings
FIELD_MAPS = {
    "extract": {
        "name": "primary_name",
        "street": "mailing_address",
        "street_2": "mailing_address_2",
        "city": "city",
        "state": "state",
        "zip": "zip_code",
        "entity_type": "entity_type",
        "first_name": "first_name",
        "middle_name": "middle_name",
        "last_name": "last_name",
        "suffix": "suffix",
        "entry_number": "entry_number",
    },
    "title": {
        "name": "full_name",
        "street": "address",
        "street_2": "address_line_2",
        "city": "city",
        "state": "state",
        "zip": "zip_code",
        "entity_type": "entity_type",
        "first_name": "first_name",
        "middle_name": "middle_name",
        "last_name": "last_name",
    },
}

# Gemini prompt specifically for name correction
NAME_VALIDATION_PROMPT = """You are validating person and entity names from legal documents (OCC Exhibit A filings, title opinions).

For each entry, check:
1. Name casing: Should be proper Title Case (not ALL CAPS or all lower)
2. Common misspellings in legal names
3. Entity type accuracy: Is "Individual" correct or should it be "Trust", "LLC", etc.?
4. Name completeness: Missing obvious parts

Only suggest changes you are highly confident about. Do NOT change unusual but valid names.
Return suggestions as JSON array with: entry_index, field, current_value, suggested_value, reason, confidence (high/medium/low)."""


async def _validate_addresses_step(
    entries: list[dict],
    tool: str,
    field_map: dict,
) -> AsyncGenerator[dict, None]:
    """Step 1: Validate addresses using Google Maps API."""
    if not settings.use_google_maps:
        yield {"step": "addresses", "status": "skipped", "message": "Google Maps not configured"}
        return

    has_address = [
        i for i, e in enumerate(entries)
        if any([
            e.get(field_map["street"]),
            e.get(field_map["city"]),
            e.get(field_map["state"]),
            e.get(field_map["zip"]),
        ])
    ]

    if not has_address:
        yield {"step": "addresses", "status": "skipped", "message": "No addresses to validate"}
        return

    yield {
        "step": "addresses",
        "status": "started",
        "total": len(has_address),
        "message": f"Validating {len(has_address)} addresses...",
    }

    # Run in thread pool since the Google Maps calls are synchronous
    from app.services.address_validation_service import validate_address

    addresses_corrected = 0
    addresses_failed = 0

    for count, idx in enumerate(has_address):
        entry = entries[idx]

        result = await asyncio.to_thread(
            validate_address,
            street=entry.get(field_map["street"]) or "",
            street_2=entry.get(field_map["street_2"]) or "",
            city=entry.get(field_map["city"]) or "",
            state=entry.get(field_map["state"]) or "",
            zip_code=entry.get(field_map["zip"]) or "",
        )

        if result.confidence in ("high", "partial"):
            # Store property type and coordinates from geocoding
            if result.property_type:
                entries[idx]["property_type"] = result.property_type
            if result.latitude is not None:
                entries[idx]["latitude"] = result.latitude
            if result.longitude is not None:
                entries[idx]["longitude"] = result.longitude

            if result.changed:
                if result.validated_street:
                    entries[idx][field_map["street"]] = result.validated_street
                if result.validated_street_2:
                    entries[idx][field_map["street_2"]] = result.validated_street_2
                if result.validated_city:
                    entries[idx][field_map["city"]] = result.validated_city
                if result.validated_state:
                    entries[idx][field_map["state"]] = result.validated_state
                if result.validated_zip:
                    entries[idx][field_map["zip"]] = result.validated_zip
                addresses_corrected += 1
        elif result.error:
            addresses_failed += 1

        # Progress every 3 entries or on last entry
        if (count + 1) % 3 == 0 or count + 1 == len(has_address):
            yield {
                "step": "addresses",
                "status": "progress",
                "progress": count + 1,
                "total": len(has_address),
                "corrected": addresses_corrected,
                "message": f"Validating addresses... ({count + 1}/{len(has_address)})",
            }

    yield {
        "step": "addresses",
        "status": "completed",
        "corrected": addresses_corrected,
        "failed": addresses_failed,
        "total": len(has_address),
        "message": f"Address validation complete: {addresses_corrected} corrected",
    }


async def _property_lookup_step(
    entries: list[dict],
    tool: str,
    field_map: dict,
) -> AsyncGenerator[dict, None]:
    """Step 2: Look up property values and confirm property type via Zillow."""
    # Only run if Google Maps is enabled (we need validated addresses)
    if not settings.use_google_maps:
        yield {"step": "property", "status": "skipped", "message": "Address validation not configured"}
        return

    # Find entries that have a validated address with property_type
    has_property = [
        i for i, e in enumerate(entries)
        if e.get("property_type") and e.get(field_map["street"])
    ]

    if not has_property:
        yield {"step": "property", "status": "skipped", "message": "No validated addresses to look up"}
        return

    yield {
        "step": "property",
        "status": "started",
        "total": len(has_property),
        "message": f"Looking up {len(has_property)} properties...",
    }

    from app.services.property_lookup_service import lookup_property

    looked_up = 0
    values_found = 0

    for count, idx in enumerate(has_property):
        entry = entries[idx]

        try:
            result = await asyncio.to_thread(
                lookup_property,
                street=entry.get(field_map["street"]) or "",
                city=entry.get(field_map["city"]) or "",
                state=entry.get(field_map["state"]) or "",
                zip_code=entry.get(field_map["zip"]) or "",
            )

            if result.found:
                looked_up += 1
                # Update property type from Zillow (more specific than Google Maps)
                if result.property_type:
                    entries[idx]["property_type"] = result.property_type
                if result.estimated_value:
                    entries[idx]["property_value"] = result.estimated_value
                    values_found += 1
                if result.zillow_url:
                    entries[idx]["zillow_url"] = result.zillow_url
        except Exception as e:
            logger.warning(f"Property lookup failed for entry {idx}: {e}")

        # Progress every 3 entries or on last entry
        if (count + 1) % 3 == 0 or count + 1 == len(has_property):
            yield {
                "step": "property",
                "status": "progress",
                "progress": count + 1,
                "total": len(has_property),
                "values_found": values_found,
                "message": f"Looking up properties... ({count + 1}/{len(has_property)})",
            }

    yield {
        "step": "property",
        "status": "completed",
        "looked_up": looked_up,
        "values_found": values_found,
        "total": len(has_property),
        "message": f"Property lookup complete: {values_found} values found",
    }


async def _validate_names_step(
    entries: list[dict],
    tool: str,
    field_map: dict,
) -> AsyncGenerator[dict, None]:
    """Step 3: Validate names using Gemini AI."""
    if not settings.use_gemini:
        yield {"step": "names", "status": "skipped", "message": "Gemini AI not configured"}
        return

    total = len(entries)
    yield {
        "step": "names",
        "status": "started",
        "total": total,
        "message": f"Validating {total} names with AI...",
    }

    try:
        from app.services.gemini_service import validate_entries

        result = await validate_entries(tool, entries)

        if result.success and result.suggestions:
            applied = 0
            for suggestion in result.suggestions:
                idx = suggestion.entry_index
                if 0 <= idx < len(entries) and suggestion.confidence in ("high", "medium"):
                    field_name = suggestion.field
                    if field_name in entries[idx]:
                        entries[idx][field_name] = suggestion.suggested_value
                        applied += 1

            yield {
                "step": "names",
                "status": "completed",
                "suggestions": len(result.suggestions),
                "applied": applied,
                "total": total,
                "message": f"Name validation complete: {applied} corrections applied",
            }
        else:
            yield {
                "step": "names",
                "status": "completed",
                "suggestions": 0,
                "applied": 0,
                "total": total,
                "message": "Name validation complete: no corrections needed",
            }

    except Exception as e:
        logger.exception(f"Error in name validation: {e}")
        yield {
            "step": "names",
            "status": "error",
            "message": f"Name validation error: {str(e)}",
        }


async def _split_names_step(
    entries: list[dict],
    tool: str,
    field_map: dict,
) -> AsyncGenerator[dict, None]:
    """Step 4: Split entries with multiple names into individual entries."""
    from app.services.extract.name_parser import split_multiple_names, parse_person_name

    name_field = field_map["name"]
    entity_type_field = field_map.get("entity_type", "entity_type")
    entry_number_field = field_map.get("entry_number")

    total = len(entries)
    yield {
        "step": "splitting",
        "status": "started",
        "total": total,
        "message": "Splitting multiple names...",
    }

    new_entries = []
    split_count = 0

    for i, entry in enumerate(entries):
        name = entry.get(name_field, "")
        entity_type = entry.get(entity_type_field, "Individual")

        # Only split individual names (not businesses, trusts, etc.)
        is_individual = entity_type.lower() in ("individual", "unknown")
        if not is_individual or not name:
            new_entries.append(entry)
            continue

        names = split_multiple_names(name)

        if len(names) > 1:
            split_count += 1
            original_number = entry.get(entry_number_field, str(i + 1)) if entry_number_field else str(i + 1)

            for j, split_name in enumerate(names):
                new_entry = dict(entry)
                new_entry[name_field] = split_name

                # Update entry number with suffix
                if entry_number_field:
                    suffix_letter = chr(ord('a') + j)
                    new_entry[entry_number_field] = f"{original_number}{suffix_letter}"

                # Re-parse the name into first/middle/last
                parsed = parse_person_name(split_name)
                if parsed.is_person:
                    if "first_name" in field_map:
                        new_entry[field_map["first_name"]] = parsed.first_name or ""
                    if "middle_name" in field_map:
                        new_entry[field_map["middle_name"]] = parsed.middle_name or ""
                    if "last_name" in field_map:
                        new_entry[field_map["last_name"]] = parsed.last_name or ""
                    if "suffix" in field_map and hasattr(parsed, "suffix"):
                        new_entry[field_map["suffix"]] = parsed.suffix or ""

                new_entries.append(new_entry)
        else:
            new_entries.append(entry)

    yield {
        "step": "splitting",
        "status": "completed",
        "split_count": split_count,
        "original_count": total,
        "new_count": len(new_entries),
        "message": f"Split {split_count} entries with multiple names ({total} → {len(new_entries)} entries)",
    }

    # Replace entries in-place
    entries.clear()
    entries.extend(new_entries)


async def enrich_entries(
    tool: str,
    entries: list[dict],
) -> AsyncGenerator[str, None]:
    """Main enrichment pipeline. Yields newline-delimited JSON progress events.

    Steps:
    1. Validate addresses (Google Maps)
    2. Property lookup (Zillow values + type)
    3. Validate names (Gemini AI)
    4. Split multiple names

    Args:
        tool: Tool name ("extract" or "title").
        entries: List of entry dicts to enrich.

    Yields:
        JSON strings (one per line) with progress events.
    """
    field_map = FIELD_MAPS.get(tool)
    if not field_map:
        yield json.dumps({"step": "error", "message": f"Unknown tool: {tool}"}) + "\n"
        return

    total = len(entries)
    yield json.dumps({
        "step": "started",
        "total": total,
        "message": f"Starting enrichment for {total} entries...",
        "google_maps_enabled": settings.use_google_maps,
        "gemini_enabled": settings.use_gemini,
    }) + "\n"

    # Step 1: Address validation
    async for event in _validate_addresses_step(entries, tool, field_map):
        yield json.dumps(event) + "\n"

    # Step 2: Property lookup (after addresses are validated)
    async for event in _property_lookup_step(entries, tool, field_map):
        yield json.dumps(event) + "\n"

    # Step 3: Name validation
    async for event in _validate_names_step(entries, tool, field_map):
        yield json.dumps(event) + "\n"

    # Step 4: Split names
    async for event in _split_names_step(entries, tool, field_map):
        yield json.dumps(event) + "\n"

    # Final result
    yield json.dumps({
        "step": "complete",
        "entries": entries,
        "summary": {
            "original_count": total,
            "final_count": len(entries),
        },
        "message": "Enrichment complete",
    }) + "\n"

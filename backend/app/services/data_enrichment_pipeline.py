"""Data enrichment service for Extract and Title tools.

Orchestrates multi-step processing:
1. Programmatic fixes (name casing, entity type detection)
2. Address validation (Google Maps Geocoding API) — skips if address_verified
3. Places lookup (Google Places API) — flags institutional addresses
4. Data enrichment (PDL + SearchBug) — phones, emails, public records
5. AI QA — final quality review

Also provides `enrich_entries()` — a streaming pipeline that yields
progress events as JSON-serializable dicts.

Yields progress events as JSON-serializable dicts for streaming.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncGenerator

from app.core.config import settings
from app.models.ai_validation import (
    AutoCorrection,
    ConfidenceLevel,
    PostProcessResult,
)

logger = logging.getLogger(__name__)

# ── Preserved entity abbreviations for name casing ──
_PRESERVE_UPPER = {
    "LLC", "LP", "LLP", "INC", "CO", "CORP", "LTD", "PC", "PA", "NA",
    "II", "III", "IV", "JR", "SR", "MD", "DDS", "PHD", "ESQ",
    "NRA", "NGL", "OIL", "GAS",
}

# Revenue product code inference mapping
_PRODUCT_CODE_MAP = {
    "oil": "OIL",
    "crude": "OIL",
    "gas": "GAS",
    "natural gas": "GAS",
    "ngl": "NGL",
    "condensate": "COND",
    "cond": "COND",
    "plant products": "NGL",
}

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


def _title_case_word(word: str) -> str:
    """Title-case a single word, preserving known abbreviations."""
    upper = word.upper().rstrip(".,")
    if upper in _PRESERVE_UPPER:
        return word.upper()
    # Preserve words that are already mixed case (e.g., "McDonald")
    if not word.isupper() and not word.islower():
        return word
    return word.capitalize()


def _fix_name_casing(
    entries: list[dict],
    name_fields: list[str],
) -> list[AutoCorrection]:
    """Convert ALL CAPS names to Title Case, preserving entity abbreviations."""
    corrections: list[AutoCorrection] = []
    for i, entry in enumerate(entries):
        for field in name_fields:
            value = entry.get(field)
            if not value or not isinstance(value, str):
                continue
            # Only fix if the name is predominantly uppercase (>60% uppercase letters)
            alpha_chars = [c for c in value if c.isalpha()]
            if not alpha_chars:
                continue
            upper_ratio = sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars)
            if upper_ratio < 0.6:
                continue

            fixed = " ".join(_title_case_word(w) for w in value.split())
            if fixed != value:
                corrections.append(AutoCorrection(
                    entry_index=i,
                    field=field,
                    original_value=value,
                    corrected_value=fixed,
                    source="programmatic",
                    confidence=ConfidenceLevel.HIGH,
                ))
                entry[field] = fixed
    return corrections


def _fix_po_box(
    entries: list[dict],
    address_fields: list[str],
) -> list[AutoCorrection]:
    """Standardize PO Box variants to 'P.O. Box XXXXX'."""
    import re

    # Match common PO Box variants: PO Box, P O Box, P.O.Box, POB, Po Box, etc.
    po_box_re = re.compile(
        r'\b(?:P\.?\s*O\.?\s*(?:Box|B)\s*|POB\s+)(\d+)\b',
        re.IGNORECASE,
    )

    corrections: list[AutoCorrection] = []
    for i, entry in enumerate(entries):
        for field in address_fields:
            value = entry.get(field)
            if not value or not isinstance(value, str):
                continue

            match = po_box_re.search(value)
            if not match:
                continue

            box_number = match.group(1)
            standard = f"P.O. Box {box_number}"

            # Replace the matched portion
            fixed = value[:match.start()] + standard + value[match.end():]
            fixed = fixed.strip()

            if fixed != value:
                corrections.append(AutoCorrection(
                    entry_index=i,
                    field=field,
                    original_value=value,
                    corrected_value=fixed,
                    source="programmatic",
                    confidence=ConfidenceLevel.HIGH,
                ))
                entry[field] = fixed
    return corrections


def _fix_entity_type(
    entries: list[dict],
    name_field: str,
    entity_type_field: str,
    tool: str = "title",
) -> list[AutoCorrection]:
    """Re-run entity detection on corrected names to fix mismatched entity types."""
    corrections: list[AutoCorrection] = []
    for i, entry in enumerate(entries):
        name = entry.get(name_field)
        current_type = entry.get(entity_type_field)
        if not name:
            continue

        # Use the correct detector per tool to match enum values
        if tool == "extract":
            from app.utils.patterns import detect_entity_type as detect_extract
            detected_val = detect_extract(name)
        else:
            from app.services.title.entity_detector import detect_entity_type as detect_title
            detected_val = detect_title(name).value

        # Normalize comparison — extract and title use different enum value casing
        if current_type and str(current_type).upper() != detected_val.upper() and detected_val.upper() != "INDIVIDUAL":
            corrections.append(AutoCorrection(
                entry_index=i,
                field=entity_type_field,
                original_value=str(current_type),
                corrected_value=detected_val,
                source="programmatic",
                confidence=ConfidenceLevel.HIGH,
            ))
            entry[entity_type_field] = detected_val
    return corrections


def _infer_product_code(entries: list[dict]) -> list[AutoCorrection]:
    """Infer missing product_code from product_description."""
    corrections: list[AutoCorrection] = []
    for i, entry in enumerate(entries):
        code = entry.get("product_code")
        if code and str(code).strip():
            continue
        desc = entry.get("product_description") or ""
        desc_lower = desc.lower().strip()
        if not desc_lower:
            continue

        for keyword, mapped_code in _PRODUCT_CODE_MAP.items():
            if keyword in desc_lower:
                corrections.append(AutoCorrection(
                    entry_index=i,
                    field="product_code",
                    original_value=str(code) if code else "",
                    corrected_value=mapped_code,
                    source="programmatic",
                    confidence=ConfidenceLevel.HIGH,
                ))
                entry["product_code"] = mapped_code
                break
    return corrections


def _calculate_net_revenue(entries: list[dict]) -> list[AutoCorrection]:
    """Calculate owner_net_revenue when components exist but total is missing."""
    corrections: list[AutoCorrection] = []
    for i, entry in enumerate(entries):
        net = entry.get("owner_net_revenue")
        if net is not None:
            continue

        owner_value = entry.get("owner_value")
        if owner_value is None:
            continue

        tax = entry.get("owner_tax_amount") or 0
        deduct = entry.get("owner_deduct_amount") or 0

        try:
            calculated = float(owner_value) - float(tax) - float(deduct)
            calculated = round(calculated, 2)
            corrections.append(AutoCorrection(
                entry_index=i,
                field="owner_net_revenue",
                original_value="",
                corrected_value=str(calculated),
                source="programmatic",
                confidence=ConfidenceLevel.HIGH,
            ))
            entry["owner_net_revenue"] = calculated
        except (ValueError, TypeError):
            continue
    return corrections


def _propagate_statement_fields(
    entries: list[dict],
    context: dict | None = None,
) -> list[AutoCorrection]:
    """Copy property_name and interest_type from context or adjacent rows when missing."""
    corrections: list[AutoCorrection] = []

    # Propagate from context (statement-level fields)
    if context:
        for i, entry in enumerate(entries):
            for field in ("property_name", "interest_type"):
                if not entry.get(field) and context.get(field):
                    corrections.append(AutoCorrection(
                        entry_index=i,
                        field=field,
                        original_value="",
                        corrected_value=str(context[field]),
                        source="programmatic",
                        confidence=ConfidenceLevel.MEDIUM,
                    ))
                    entry[field] = context[field]

    # Forward-fill property_name from previous row
    last_property = None
    for i, entry in enumerate(entries):
        if entry.get("property_name"):
            last_property = entry["property_name"]
        elif last_property and not entry.get("property_name"):
            corrections.append(AutoCorrection(
                entry_index=i,
                field="property_name",
                original_value="",
                corrected_value=last_property,
                source="programmatic",
                confidence=ConfidenceLevel.MEDIUM,
            ))
            entry["property_name"] = last_property

    return corrections


async def auto_enrich(
    tool: str,
    entries: list[dict],
    context: dict | None = None,
) -> PostProcessResult:
    """Fast post-processing pipeline run during upload.

    Only runs instant programmatic fixes. External API calls (Google Maps,
    Places, PDL/SearchBug, Gemini) are deferred to the user-triggered
    Clean Up / Validate / Enrich buttons in the pipeline API.

    Args:
        tool: Tool name (extract, title, proration, revenue).
        entries: List of entry dicts (modified in-place).
        context: Optional context dict (e.g., statement-level info for revenue).

    Returns:
        PostProcessResult with corrections applied.
    """
    all_corrections: list[AutoCorrection] = []
    steps_completed: list[str] = []
    steps_skipped: list[str] = []

    # ── Step 1: Name casing (Extract, Title, Proration) ──
    if tool in ("extract", "title", "proration"):
        name_fields_map = {
            "extract": ["primary_name", "first_name", "middle_name", "last_name"],
            "title": ["full_name", "first_name", "middle_name", "last_name"],
            "proration": ["owner"],
        }
        name_fields = name_fields_map[tool]
        casing_fixes = _fix_name_casing(entries, name_fields)
        all_corrections.extend(casing_fixes)
        steps_completed.append("name_casing")
    else:
        steps_skipped.append("name_casing")

    # ── Step 1b: P.O. Box standardization (Extract, Title) ──
    if tool in ("extract", "title"):
        addr_fields_map = {
            "extract": ["mailing_address", "mailing_address_2"],
            "title": ["address", "address_line_2"],
        }
        po_fixes = _fix_po_box(entries, addr_fields_map[tool])
        all_corrections.extend(po_fixes)
        steps_completed.append("po_box")
    else:
        steps_skipped.append("po_box")

    # ── Step 2: Entity type re-detection (Extract, Title) ──
    if tool in ("extract", "title"):
        name_field = "primary_name" if tool == "extract" else "full_name"
        entity_fixes = _fix_entity_type(entries, name_field, "entity_type", tool=tool)
        all_corrections.extend(entity_fixes)
        steps_completed.append("entity_type")
    else:
        steps_skipped.append("entity_type")

    # ── Step 3: Revenue-specific programmatic fixes ──
    if tool == "revenue":
        code_fixes = _infer_product_code(entries)
        all_corrections.extend(code_fixes)

        net_fixes = _calculate_net_revenue(entries)
        all_corrections.extend(net_fixes)

        prop_fixes = _propagate_statement_fields(entries, context)
        all_corrections.extend(prop_fixes)

        steps_completed.append("revenue_inference")
    else:
        steps_skipped.append("revenue_inference")

    # External API steps (address validation, places, enrichment, AI QA)
    # are deferred to user-triggered pipeline buttons (Clean Up / Validate / Enrich)
    steps_skipped.extend([
        "address_validation", "places_lookup", "data_enrichment", "ai_verification",
    ])

    return PostProcessResult(
        corrections=all_corrections,
        ai_suggestions=[],
        steps_completed=steps_completed,
        steps_skipped=steps_skipped,
    )


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
        if not e.get("address_verified") and any([
            e.get(field_map["street"]),
            e.get(field_map["city"]),
            e.get(field_map["state"]),
            e.get(field_map["zip"]),
        ])
    ]

    if not has_address:
        already_verified = sum(1 for e in entries if e.get("address_verified"))
        msg = "No addresses to validate"
        if already_verified:
            msg = f"All {already_verified} addresses already verified"
        yield {"step": "addresses", "status": "skipped", "message": msg}
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

            # Mark as verified
            entries[idx]["address_verified"] = True
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


async def _places_lookup_step(
    entries: list[dict],
    tool: str,
    field_map: dict,
) -> AsyncGenerator[dict, None]:
    """Step 2: Look up institutional places near geocoded addresses."""
    if not settings.use_places:
        yield {"step": "places", "status": "skipped", "message": "Places API not configured"}
        return

    has_coords = [
        i for i, e in enumerate(entries)
        if not e.get("places_checked")
        and e.get("latitude") is not None
        and e.get("longitude") is not None
    ]

    if not has_coords:
        already_checked = sum(1 for e in entries if e.get("places_checked"))
        msg = "No geocoded addresses to check"
        if already_checked:
            msg = f"All {already_checked} addresses already checked"
        yield {"step": "places", "status": "skipped", "message": msg}
        return

    yield {
        "step": "places",
        "status": "started",
        "total": len(has_coords),
        "message": f"Checking {len(has_coords)} addresses for institutional places...",
    }

    from app.services.property_lookup_service import lookup_place

    flagged = 0
    for count, idx in enumerate(has_coords):
        entry = entries[idx]

        street = entry.get(field_map["street"]) or ""
        city = entry.get(field_map["city"]) or ""
        state = entry.get(field_map["state"]) or ""
        addr_str = ", ".join(p for p in [street, city, state] if p)

        result = await asyncio.to_thread(
            lookup_place,
            latitude=entry["latitude"],
            longitude=entry["longitude"],
            address=addr_str,
        )

        entry["places_checked"] = True

        if result.found:
            entry["place_type"] = result.place_type
            entry["place_name"] = result.place_name
            entry["place_flag"] = result.place_flag
            flagged += 1

        if (count + 1) % 3 == 0 or count + 1 == len(has_coords):
            yield {
                "step": "places",
                "status": "progress",
                "progress": count + 1,
                "total": len(has_coords),
                "flagged": flagged,
                "message": f"Checking places... ({count + 1}/{len(has_coords)})",
            }

    yield {
        "step": "places",
        "status": "completed",
        "flagged": flagged,
        "total": len(has_coords),
        "message": f"Places check complete: {flagged} institutional addresses flagged",
    }


async def _enrich_contacts_step(
    entries: list[dict],
    tool: str,
    field_map: dict,
) -> AsyncGenerator[dict, None]:
    """Step 3: Enrich contacts with PDL + SearchBug data."""
    from app.services.enrichment.enrichment_service import (
        enrich_person,
        is_enrichment_enabled,
    )

    if not is_enrichment_enabled():
        yield {"step": "enrichment", "status": "skipped", "message": "Data enrichment not configured"}
        return

    # Only enrich individuals
    eligible = [
        i for i, e in enumerate(entries)
        if not e.get("enrichment_completed")
        and (e.get(field_map.get("entity_type", "entity_type")) or "").upper()
            in ("INDIVIDUAL", "UNKNOWN", "")
        and e.get(field_map.get("name", ""))
    ]

    if not eligible:
        already_enriched = sum(1 for e in entries if e.get("enrichment_completed"))
        msg = "No eligible entries to enrich"
        if already_enriched:
            msg = f"All {already_enriched} entries already enriched"
        yield {"step": "enrichment", "status": "skipped", "message": msg}
        return

    yield {
        "step": "enrichment",
        "status": "started",
        "total": len(eligible),
        "message": f"Enriching {len(eligible)} contacts...",
    }

    enriched_count = 0
    for count, idx in enumerate(eligible):
        entry = entries[idx]

        name = entry.get(field_map.get("name", "")) or ""
        street = entry.get(field_map.get("street", "")) or ""
        city = entry.get(field_map.get("city", "")) or ""
        state = entry.get(field_map.get("state", "")) or ""
        zip_code = entry.get(field_map.get("zip", "")) or ""

        result = await enrich_person(
            name=name,
            address=street,
            city=city,
            state=state,
            zip_code=zip_code,
        )

        entry["enrichment_completed"] = True

        if result.enrichment_sources:
            enriched_count += 1
            if result.phones:
                entry["enrichment_phones"] = [
                    {"number": p.number, "type": p.type}
                    for p in result.phones
                ]
            if result.emails:
                entry["enrichment_emails"] = result.emails
            if result.social_profiles:
                entry["enrichment_social"] = [
                    {"platform": s.platform, "url": s.url}
                    for s in result.social_profiles
                ]
            if result.public_records:
                pr = result.public_records
                if pr.is_deceased or pr.has_bankruptcy or pr.has_liens:
                    entry["enrichment_flags"] = {
                        "is_deceased": pr.is_deceased,
                        "deceased_date": pr.deceased_date,
                        "has_bankruptcy": pr.has_bankruptcy,
                        "has_liens": pr.has_liens,
                    }
            entry["enrichment_sources"] = result.enrichment_sources
            entry["enrichment_confidence"] = result.match_confidence

        if (count + 1) % 3 == 0 or count + 1 == len(eligible):
            yield {
                "step": "enrichment",
                "status": "progress",
                "progress": count + 1,
                "total": len(eligible),
                "enriched": enriched_count,
                "message": f"Enriching contacts... ({count + 1}/{len(eligible)})",
            }

    yield {
        "step": "enrichment",
        "status": "completed",
        "enriched": enriched_count,
        "total": len(eligible),
        "message": f"Enrichment complete: {enriched_count} contacts enriched",
    }


async def _validate_names_step(
    entries: list[dict],
    tool: str,
    field_map: dict,
) -> AsyncGenerator[dict, None]:
    """Step 4: Validate names using AI."""
    if not settings.use_ai:
        yield {"step": "names", "status": "skipped", "message": "AI not configured"}
        return

    from app.services.llm import get_llm_provider

    provider = get_llm_provider()
    if provider is None:
        yield {"step": "names", "status": "skipped", "message": "AI provider not available"}
        return

    total = len(entries)
    yield {
        "step": "names",
        "status": "started",
        "total": total,
        "message": f"Validating {total} names with AI...",
    }

    try:
        result = await provider.validate_entries(tool, entries)

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
    """Step 5: Split entries with multiple names into individual entries."""
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
    1. Validate addresses (Google Maps) — skips verified
    2. Places lookup (Google Places) — flags institutional
    3. Enrich contacts (PDL + SearchBug) — skips enriched
    4. Validate names (AI)
    5. Split multiple names

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
        "places_enabled": settings.use_places,
        "enrichment_enabled": settings.use_enrichment,
        "ai_enabled": settings.use_ai,
    }) + "\n"

    # Step 1: Address validation
    async for event in _validate_addresses_step(entries, tool, field_map):
        yield json.dumps(event) + "\n"

    # Step 2: Places lookup
    async for event in _places_lookup_step(entries, tool, field_map):
        yield json.dumps(event) + "\n"

    # Step 3: Data enrichment
    async for event in _enrich_contacts_step(entries, tool, field_map):
        yield json.dumps(event) + "\n"

    # Step 4: Name validation (AI)
    async for event in _validate_names_step(entries, tool, field_map):
        yield json.dumps(event) + "\n"

    # Step 5: Split names
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

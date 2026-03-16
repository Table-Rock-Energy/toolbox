"""Pipeline API endpoints for enrichment pipeline steps.

Provides three endpoints that all return the same PipelineResponse format:
- POST /cleanup: AI-powered data correction via LLM
- POST /validate: Address validation via Google Maps
- POST /enrich: Contact enrichment via PDL/SearchBug
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter

from app.core.config import settings
from app.models.pipeline import PipelineRequest, PipelineResponse, ProposedChange
from app.services.llm import get_llm_provider
from app.services.address_validation_service import validate_address
from app.services.enrichment.enrichment_service import (
    enrich_persons,
    is_enrichment_enabled,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Default field mappings per tool for address validation.
# Maps abstract names (street, street_2, city, state, zip) to tool-specific field names.
DEFAULT_FIELD_MAPPINGS: dict[str, dict[str, str]] = {
    "extract": {
        "street": "mailing_address",
        "street_2": "mailing_address_2",
        "city": "city",
        "state": "state",
        "zip": "zip_code",
    },
    "title": {
        "street": "address",
        "street_2": "address_2",
        "city": "city",
        "state": "state",
        "zip": "zip_code",
    },
    "proration": {
        "street": "address",
        "street_2": "address_2",
        "city": "city",
        "state": "state",
        "zip": "zip_code",
    },
    "revenue": {},  # Revenue has no address fields
    "ecf": {
        "street": "mailing_address",
        "street_2": "mailing_address_2",
        "city": "city",
        "state": "state",
        "zip": "zip_code",
    },
}

# Default name/address field mappings for enrichment.
DEFAULT_ENRICH_MAPPINGS: dict[str, dict[str, str]] = {
    "extract": {
        "name": "name",
        "address": "mailing_address",
        "city": "city",
        "state": "state",
        "zip_code": "zip_code",
    },
    "title": {
        "name": "full_name",
        "address": "address",
        "city": "city",
        "state": "state",
        "zip_code": "zip_code",
    },
    "proration": {
        "name": "owner_name",
        "address": "address",
        "city": "city",
        "state": "state",
        "zip_code": "zip_code",
    },
    "revenue": {},
    "ecf": {
        "name": "name",
        "address": "mailing_address",
        "city": "city",
        "state": "state",
        "zip_code": "zip_code",
    },
}


@router.post("/cleanup", response_model=PipelineResponse)
async def pipeline_cleanup(request: PipelineRequest) -> PipelineResponse:
    """Run AI-powered data cleanup on entries.

    Uses the configured LLM provider (Gemini) to suggest corrections
    for name casing, abbreviations, entity types, etc.
    """
    provider = get_llm_provider()
    if provider is None:
        return PipelineResponse(
            success=False,
            error="AI cleanup not configured. Enable Gemini in settings.",
        )

    try:
        # Revenue: pre-compute batch median for outlier detection
        if request.tool == "revenue":
            from statistics import median as compute_median

            values = [
                float(e["owner_value"])
                for e in request.entries
                if e.get("owner_value") and float(e.get("owner_value", 0)) > 0
            ]
            if len(values) >= 3:
                med = compute_median(values)
                threshold = med * 3
                for e in request.entries:
                    e["_batch_median_value"] = round(med, 2)
                    e["_outlier_threshold"] = round(threshold, 2)

        changes = await provider.cleanup_entries(
            request.tool, request.entries, source_data=request.source_data
        )
        return PipelineResponse(
            success=True,
            proposed_changes=changes,
            entries_processed=len(request.entries),
        )
    except Exception as e:
        logger.exception("Pipeline cleanup error: %s", e)
        return PipelineResponse(
            success=False,
            error=f"Cleanup failed: {str(e)}",
        )


@router.post("/validate", response_model=PipelineResponse)
async def pipeline_validate(request: PipelineRequest) -> PipelineResponse:
    """Validate addresses using Google Maps Geocoding API.

    Returns ProposedChange objects with authoritative=True for address
    corrections from Google Maps.
    """
    if not settings.use_google_maps:
        return PipelineResponse(
            success=False,
            error="Address validation not configured. Enable Google Maps in settings.",
        )

    # Resolve field mapping: request overrides > tool defaults > empty
    tool_defaults = DEFAULT_FIELD_MAPPINGS.get(request.tool, {})
    mapping = {**tool_defaults, **request.field_mapping}

    street_field = mapping.get("street", "")
    street_2_field = mapping.get("street_2", "")
    city_field = mapping.get("city", "")
    state_field = mapping.get("state", "")
    zip_field = mapping.get("zip", "")

    # If no street field mapped (e.g., revenue), return empty
    if not street_field:
        return PipelineResponse(
            success=True,
            proposed_changes=[],
            entries_processed=len(request.entries),
        )

    proposed_changes: list[ProposedChange] = []

    for i, entry in enumerate(request.entries):
        street = entry.get(street_field) or ""
        street_2 = entry.get(street_2_field) or ""
        city = entry.get(city_field) or ""
        state = entry.get(state_field) or ""
        zip_code = entry.get(zip_field) or ""

        # Skip entries without any address
        if not any([street, city, state, zip_code]):
            continue

        # Run sync validate_address in a thread
        result = await asyncio.to_thread(
            validate_address,
            street=street,
            street_2=street_2,
            city=city,
            state=state,
            zip_code=zip_code,
        )

        if result.confidence in ("high", "partial") and result.changed:
            # Build ProposedChange per changed field
            if result.validated_street and result.validated_street.lower() != street.strip().lower():
                proposed_changes.append(
                    ProposedChange(
                        entry_index=i,
                        field=street_field,
                        current_value=street,
                        proposed_value=result.validated_street,
                        reason=f"Google Maps corrected street address",
                        confidence=result.confidence,
                        source="google_maps",
                        authoritative=True,
                    )
                )

            if result.validated_city and city and result.validated_city.lower() != city.strip().lower():
                proposed_changes.append(
                    ProposedChange(
                        entry_index=i,
                        field=city_field,
                        current_value=city,
                        proposed_value=result.validated_city,
                        reason="Google Maps corrected city",
                        confidence=result.confidence,
                        source="google_maps",
                        authoritative=True,
                    )
                )

            if result.validated_state and state and result.validated_state.upper() != state.strip().upper():
                proposed_changes.append(
                    ProposedChange(
                        entry_index=i,
                        field=state_field,
                        current_value=state,
                        proposed_value=result.validated_state,
                        reason="Google Maps corrected state",
                        confidence=result.confidence,
                        source="google_maps",
                        authoritative=True,
                    )
                )

            if result.validated_zip and zip_code and not zip_code.strip().startswith(result.validated_zip):
                proposed_changes.append(
                    ProposedChange(
                        entry_index=i,
                        field=zip_field,
                        current_value=zip_code,
                        proposed_value=result.validated_zip,
                        reason="Google Maps corrected ZIP code",
                        confidence=result.confidence,
                        source="google_maps",
                        authoritative=True,
                    )
                )

    return PipelineResponse(
        success=True,
        proposed_changes=proposed_changes,
        entries_processed=len(request.entries),
    )


@router.post("/enrich", response_model=PipelineResponse)
async def pipeline_enrich(request: PipelineRequest) -> PipelineResponse:
    """Enrich entries with contact data from PDL/SearchBug.

    Returns ProposedChange objects for discovered phone numbers and
    email addresses.
    """
    if not is_enrichment_enabled():
        return PipelineResponse(
            success=False,
            error="Contact enrichment not enabled. Configure API keys in settings.",
        )

    # Resolve field mapping for name/address fields
    tool_defaults = DEFAULT_ENRICH_MAPPINGS.get(request.tool, {})
    mapping = {**tool_defaults, **request.field_mapping}

    name_field = mapping.get("name", "name")
    address_field = mapping.get("address", "address")
    city_field = mapping.get("city", "city")
    state_field = mapping.get("state", "state")
    zip_field = mapping.get("zip_code", "zip_code")

    # Build persons list for enrichment service
    persons = []
    for entry in request.entries:
        name = entry.get(name_field) or ""
        if not name:
            continue
        persons.append({
            "name": name,
            "address": entry.get(address_field),
            "city": entry.get(city_field),
            "state": entry.get(state_field),
            "zip_code": entry.get(zip_field),
        })

    if not persons:
        return PipelineResponse(
            success=True,
            proposed_changes=[],
            entries_processed=len(request.entries),
        )

    try:
        enrichment_result = await enrich_persons(persons)
    except Exception as e:
        logger.exception("Pipeline enrichment error: %s", e)
        return PipelineResponse(
            success=False,
            error=f"Enrichment failed: {str(e)}",
        )

    if not enrichment_result.success:
        return PipelineResponse(
            success=False,
            error=enrichment_result.error_message or "Enrichment failed",
        )

    # Transform EnrichedPerson results into ProposedChange list
    proposed_changes: list[ProposedChange] = []
    for idx, result in enumerate(enrichment_result.results):
        # Determine source from enrichment_sources
        source = "pdl"
        if result.enrichment_sources:
            if "searchbug" in result.enrichment_sources:
                source = "searchbug"
            elif "peopledatalabs" in result.enrichment_sources:
                source = "pdl"

        if result.phones:
            proposed_changes.append(
                ProposedChange(
                    entry_index=idx,
                    field="phone",
                    current_value="",
                    proposed_value=result.phones[0].number,
                    reason=f"Phone number found via {source}",
                    confidence="medium",
                    source=source,
                    authoritative=False,
                )
            )

        if result.emails:
            proposed_changes.append(
                ProposedChange(
                    entry_index=idx,
                    field="email",
                    current_value="",
                    proposed_value=result.emails[0],
                    reason=f"Email found via {source}",
                    confidence="medium",
                    source=source,
                    authoritative=False,
                )
            )

    return PipelineResponse(
        success=True,
        proposed_changes=proposed_changes,
        entries_processed=len(request.entries),
    )

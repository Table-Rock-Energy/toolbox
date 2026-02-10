"""Orchestrator for data enrichment — combines PDL + SearchBug results."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from app.core.config import settings
from app.models.enrichment import (
    EnrichedPerson,
    EnrichmentResponse,
    EnrichmentStatusResponse,
    PublicRecordFlags,
)

logger = logging.getLogger(__name__)

# Runtime overrides for API keys (set via admin UI, persisted in Firestore)
_runtime_pdl_key: Optional[str] = None
_runtime_searchbug_key: Optional[str] = None
_runtime_enabled: Optional[bool] = None


def set_runtime_config(
    pdl_api_key: Optional[str] = None,
    searchbug_api_key: Optional[str] = None,
    enabled: Optional[bool] = None,
) -> None:
    """Update runtime enrichment config (called from admin API)."""
    global _runtime_pdl_key, _runtime_searchbug_key, _runtime_enabled
    if pdl_api_key is not None:
        _runtime_pdl_key = pdl_api_key
    if searchbug_api_key is not None:
        _runtime_searchbug_key = searchbug_api_key
    if enabled is not None:
        _runtime_enabled = enabled


def get_pdl_key() -> Optional[str]:
    """Get active PDL API key (runtime override > env var)."""
    return _runtime_pdl_key or settings.pdl_api_key


def get_searchbug_key() -> Optional[str]:
    """Get active SearchBug API key (runtime override > env var)."""
    return _runtime_searchbug_key or settings.searchbug_api_key


def is_enrichment_enabled() -> bool:
    """Check if enrichment is enabled."""
    if _runtime_enabled is not None:
        return _runtime_enabled and (bool(get_pdl_key()) or bool(get_searchbug_key()))
    return settings.use_enrichment


def get_enrichment_status() -> EnrichmentStatusResponse:
    """Get current enrichment configuration status."""
    return EnrichmentStatusResponse(
        enabled=is_enrichment_enabled(),
        pdl_configured=bool(get_pdl_key()),
        searchbug_configured=bool(get_searchbug_key()),
    )


def _split_name(full_name: str) -> tuple[str, str]:
    """Split a full name into first and last name."""
    parts = full_name.strip().split()
    if len(parts) == 0:
        return ("", "")
    if len(parts) == 1:
        return (parts[0], "")
    return (parts[0], " ".join(parts[1:]))


async def enrich_person(
    name: str,
    address: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    zip_code: Optional[str] = None,
) -> EnrichedPerson:
    """
    Enrich a single person using all available providers.

    Merges results from PDL (contact data) and SearchBug (public records).
    """
    now = datetime.now(timezone.utc).isoformat()
    first_name, last_name = _split_name(name)

    result = EnrichedPerson(
        original_name=name,
        original_address=address,
        enriched_at=now,
        public_records=PublicRecordFlags(),
    )

    pdl_key = get_pdl_key()
    searchbug_key = get_searchbug_key()

    # PDL: phones, emails, social profiles
    if pdl_key:
        try:
            from app.services.enrichment.pdl_provider import enrich_person_pdl, parse_pdl_response

            raw = await enrich_person_pdl(
                api_key=pdl_key,
                name=name,
                address=address,
                city=city,
                state=state,
                zip_code=zip_code,
            )
            if raw:
                pdl_result = parse_pdl_response(raw, name)
                result.phones = pdl_result.phones
                result.emails = pdl_result.emails
                result.social_profiles = pdl_result.social_profiles
                result.match_confidence = pdl_result.match_confidence
                result.enrichment_sources.append("peopledatalabs")
        except Exception as e:
            logger.exception(f"PDL enrichment failed for '{name}': {e}")

    # SearchBug: phones (if PDL didn't find any), deceased, bankruptcy, liens
    if searchbug_key and last_name:
        try:
            from app.services.enrichment.searchbug_provider import enrich_person_searchbug, parse_searchbug_response

            raw = await enrich_person_searchbug(
                api_key=searchbug_key,
                first_name=first_name,
                last_name=last_name,
                address=address,
                city=city,
                state=state,
                zip_code=zip_code,
            )
            if raw:
                sb_result = parse_searchbug_response(raw, name)
                # Merge phones from SearchBug if PDL didn't return enough
                existing_numbers = {p.number for p in result.phones}
                for ph in sb_result.phones:
                    if len(result.phones) >= 5:
                        break
                    if ph.number not in existing_numbers:
                        result.phones.append(ph)
                        existing_numbers.add(ph.number)

                # Merge emails
                existing_emails = set(result.emails)
                for em in sb_result.emails:
                    if em not in existing_emails:
                        result.emails.append(em)
                        existing_emails.add(em)

                # Public records always come from SearchBug
                result.public_records = sb_result.public_records
                result.enrichment_sources.append("searchbug")
        except Exception as e:
            logger.exception(f"SearchBug enrichment failed for '{name}': {e}")

    return result


async def enrich_persons(persons: list[dict]) -> EnrichmentResponse:
    """
    Enrich a list of persons.

    Each person dict should have: name, address (optional), city (optional),
    state (optional), zip_code (optional).
    """
    if not is_enrichment_enabled():
        return EnrichmentResponse(
            success=False,
            total_requested=len(persons),
            error_message="Data enrichment is not enabled. Configure API keys in Settings.",
        )

    if len(persons) > 50:
        return EnrichmentResponse(
            success=False,
            total_requested=len(persons),
            error_message="Maximum 50 persons per request.",
        )

    results: list[EnrichedPerson] = []
    for person in persons:
        name = person.get("name", "")
        if not name:
            continue

        enriched = await enrich_person(
            name=name,
            address=person.get("address"),
            city=person.get("city"),
            state=person.get("state"),
            zip_code=person.get("zip_code"),
        )
        results.append(enriched)

    return EnrichmentResponse(
        success=True,
        results=results,
        total_requested=len(persons),
        total_enriched=len([r for r in results if r.enrichment_sources]),
    )

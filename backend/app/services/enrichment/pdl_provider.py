"""People Data Labs provider for contact enrichment (phones, emails, social)."""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from app.models.enrichment import EnrichedPerson, PhoneNumber, SocialProfile

logger = logging.getLogger(__name__)

PDL_BASE_URL = "https://api.peopledatalabs.com/v5"


async def enrich_person_pdl(
    api_key: str,
    name: str,
    address: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    zip_code: Optional[str] = None,
) -> Optional[dict]:
    """
    Look up a person via People Data Labs Person Enrichment API.

    Returns raw PDL response dict or None if no match.
    """
    params: dict[str, str] = {
        "name": name,
        "pretty": "true",
    }

    # Build location string for PDL
    location_parts = []
    if address:
        params["street_address"] = address
    if city:
        location_parts.append(city)
    if state:
        location_parts.append(state)
    if zip_code:
        location_parts.append(zip_code)
    if location_parts:
        params["location"] = ", ".join(location_parts)

    headers = {
        "X-Api-Key": api_key,
        "Content-Type": "application/json",
    }

    try:
        from app.services.shared.http_retry import async_request_with_retry

        response = await async_request_with_retry(
            "GET",
            f"{PDL_BASE_URL}/person/enrich",
            params=params,
            headers=headers,
            timeout=15.0,
        )

        if response.status_code == 200:
            data = response.json()
            logger.info(f"PDL match found for '{name}' (likelihood={data.get('likelihood', 'N/A')})")
            return data
        elif response.status_code == 404:
            logger.info(f"PDL: no match for '{name}'")
            return None
        else:
            logger.warning(f"PDL API error {response.status_code}: {response.text[:200]}")
            return None

    except httpx.TimeoutException:
        logger.warning(f"PDL API timeout for '{name}'")
        return None
    except Exception as e:
        logger.exception(f"PDL API error for '{name}': {e}")
        return None


def parse_pdl_response(raw: dict, original_name: str) -> EnrichedPerson:
    """Parse raw PDL API response into our EnrichedPerson model."""
    data = raw.get("data", raw)

    # Extract phones (up to 5)
    phones: list[PhoneNumber] = []
    mobile_phone = data.get("mobile_phone")
    if mobile_phone:
        phones.append(PhoneNumber(number=mobile_phone, type="mobile"))

    phone_numbers = data.get("phone_numbers") or []
    for pn in phone_numbers:
        if len(phones) >= 5:
            break
        num = pn if isinstance(pn, str) else str(pn)
        if not any(p.number == num for p in phones):
            phones.append(PhoneNumber(number=num))

    # Extract emails
    emails: list[str] = []
    personal_emails = data.get("personal_emails") or []
    work_email = data.get("work_email")
    emails.extend(personal_emails)
    if work_email and work_email not in emails:
        emails.append(work_email)

    # Extract social profiles
    social_profiles: list[SocialProfile] = []
    profile_fields = [
        ("linkedin_url", "linkedin"),
        ("twitter_url", "twitter"),
        ("facebook_url", "facebook"),
        ("github_url", "github"),
    ]
    for field, platform in profile_fields:
        url = data.get(field)
        if url:
            username = data.get(f"{platform}_username")
            social_profiles.append(SocialProfile(platform=platform, url=url, username=username))

    # Also check profiles array
    profiles = data.get("profiles") or []
    for profile in profiles:
        platform = (profile.get("network") or "").lower()
        url = profile.get("url")
        username = profile.get("username")
        if url and not any(sp.platform == platform for sp in social_profiles):
            social_profiles.append(SocialProfile(platform=platform, url=url, username=username))

    likelihood = raw.get("likelihood")
    if likelihood and likelihood >= 8:
        confidence = "high"
    elif likelihood and likelihood >= 5:
        confidence = "medium"
    else:
        confidence = "low"

    return EnrichedPerson(
        original_name=original_name,
        phones=phones,
        emails=emails,
        social_profiles=social_profiles,
        enrichment_sources=["peopledatalabs"],
        match_confidence=confidence,
    )

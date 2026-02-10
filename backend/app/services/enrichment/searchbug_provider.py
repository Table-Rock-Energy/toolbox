"""SearchBug provider for public records enrichment (deceased, bankruptcy, liens)."""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from app.models.enrichment import EnrichedPerson, PhoneNumber, PublicRecordFlags

logger = logging.getLogger(__name__)

SEARCHBUG_BASE_URL = "https://api.searchbug.com/api"


async def enrich_person_searchbug(
    api_key: str,
    first_name: str,
    last_name: str,
    address: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    zip_code: Optional[str] = None,
) -> Optional[dict]:
    """
    Look up a person via SearchBug People Search API.

    Returns raw API response dict or None if no match.
    """
    params: dict[str, str] = {
        "api_key": api_key,
        "first_name": first_name,
        "last_name": last_name,
        "format": "json",
    }

    if address:
        params["address"] = address
    if city:
        params["city"] = city
    if state:
        params["state"] = state
    if zip_code:
        params["zip"] = zip_code

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                f"{SEARCHBUG_BASE_URL}/search.aspx",
                params=params,
            )

            if response.status_code == 200:
                data = response.json()
                results = data.get("results") or data.get("Records") or []
                if results:
                    logger.info(f"SearchBug match found for '{first_name} {last_name}' ({len(results)} results)")
                    return data
                else:
                    logger.info(f"SearchBug: no match for '{first_name} {last_name}'")
                    return None
            else:
                logger.warning(f"SearchBug API error {response.status_code}: {response.text[:200]}")
                return None

    except httpx.TimeoutException:
        logger.warning(f"SearchBug API timeout for '{first_name} {last_name}'")
        return None
    except Exception as e:
        logger.exception(f"SearchBug API error for '{first_name} {last_name}': {e}")
        return None


def parse_searchbug_response(raw: dict, original_name: str) -> EnrichedPerson:
    """Parse raw SearchBug API response into our EnrichedPerson model."""
    results = raw.get("results") or raw.get("Records") or []
    if not results:
        return EnrichedPerson(
            original_name=original_name,
            enrichment_sources=["searchbug"],
            match_confidence="low",
        )

    # Use first (best) result
    person = results[0] if isinstance(results, list) else results

    # Extract phones (up to 5)
    phones: list[PhoneNumber] = []
    phone_list = person.get("phones") or person.get("PhoneNumbers") or []
    for ph in phone_list[:5]:
        if isinstance(ph, dict):
            phones.append(PhoneNumber(
                number=ph.get("number") or ph.get("Phone", ""),
                type=ph.get("type") or ph.get("PhoneType"),
                carrier=ph.get("carrier"),
            ))
        elif isinstance(ph, str):
            phones.append(PhoneNumber(number=ph))

    # Extract emails
    emails: list[str] = []
    email_list = person.get("emails") or person.get("EmailAddresses") or []
    for em in email_list:
        if isinstance(em, dict):
            addr = em.get("address") or em.get("Email", "")
            if addr:
                emails.append(addr)
        elif isinstance(em, str):
            emails.append(em)

    # Extract public record flags
    is_deceased = False
    deceased_date = None
    has_bankruptcy = False
    bankruptcy_details: list[str] = []
    has_liens = False
    lien_details: list[str] = []

    # Check deceased
    dod = person.get("date_of_death") or person.get("DeathDate")
    if dod:
        is_deceased = True
        deceased_date = str(dod)
    if person.get("is_deceased") or person.get("Deceased"):
        is_deceased = True

    # Check bankruptcies
    bankruptcies = person.get("bankruptcies") or person.get("Bankruptcies") or []
    if bankruptcies:
        has_bankruptcy = True
        for b in bankruptcies:
            if isinstance(b, dict):
                detail = b.get("case_number") or b.get("CaseNumber") or str(b)
                bankruptcy_details.append(detail)
            else:
                bankruptcy_details.append(str(b))

    # Check liens/judgments
    liens = person.get("liens") or person.get("Liens") or person.get("judgments") or person.get("Judgments") or []
    if liens:
        has_liens = True
        for ln in liens:
            if isinstance(ln, dict):
                detail = ln.get("description") or ln.get("Type") or str(ln)
                lien_details.append(detail)
            else:
                lien_details.append(str(ln))

    public_records = PublicRecordFlags(
        is_deceased=is_deceased,
        deceased_date=deceased_date,
        has_bankruptcy=has_bankruptcy,
        bankruptcy_details=bankruptcy_details,
        has_liens=has_liens,
        lien_details=lien_details,
    )

    return EnrichedPerson(
        original_name=original_name,
        phones=phones,
        emails=emails,
        public_records=public_records,
        enrichment_sources=["searchbug"],
    )

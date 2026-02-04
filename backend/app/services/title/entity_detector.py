"""Entity type detection service for title tool."""

from __future__ import annotations

from app.models.title import EntityType
from app.utils.patterns import (
    CHURCH_PATTERNS,
    CORPORATION_PATTERNS,
    ESTATE_PATTERNS,
    FOUNDATION_PATTERNS,
    MINERAL_CO_PATTERNS,
    TRUST_PATTERNS,
    UNIVERSITY_PATTERNS,
)


def detect_entity_type(name: str) -> EntityType:
    """
    Detect the entity type from a name string.

    Order of detection (first match wins):
    1. ESTATE - estate, heirs, deceased
    2. TRUST - trust, trustee, u/t/a, u/d
    3. CORPORATION - inc, corp, llc, lp, ltd, partnership
    4. FOUNDATION - foundation
    5. UNIVERSITY - university, college
    6. CHURCH - church, diocese, parish, ministries
    7. MINERAL_CO - minerals, royalty, oil & gas, energy
    8. INDIVIDUAL - default when no patterns match

    Args:
        name: The entity name to analyze

    Returns:
        EntityType enum value
    """
    if not name or not name.strip():
        return EntityType.UNKNOWN

    name = name.strip()

    # Check for ESTATE first (most specific legal entity)
    for pattern in ESTATE_PATTERNS:
        if pattern.search(name):
            return EntityType.ESTATE

    # Check for TRUST
    for pattern in TRUST_PATTERNS:
        if pattern.search(name):
            return EntityType.TRUST

    # Check for CORPORATION/LLC/Partnership
    for pattern in CORPORATION_PATTERNS:
        if pattern.search(name):
            return EntityType.CORPORATION

    # Check for FOUNDATION
    for pattern in FOUNDATION_PATTERNS:
        if pattern.search(name):
            return EntityType.FOUNDATION

    # Check for UNIVERSITY
    for pattern in UNIVERSITY_PATTERNS:
        if pattern.search(name):
            return EntityType.UNIVERSITY

    # Check for CHURCH
    for pattern in CHURCH_PATTERNS:
        if pattern.search(name):
            return EntityType.CHURCH

    # Check for MINERAL CO (oil & gas companies)
    for pattern in MINERAL_CO_PATTERNS:
        if pattern.search(name):
            return EntityType.MINERAL_CO

    # Default to INDIVIDUAL
    return EntityType.INDIVIDUAL

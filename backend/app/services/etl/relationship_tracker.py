"""Relationship Tracker — Extracts and records relationships between entities.

Parses signals from tool outputs to identify inheritance chains, trust
relationships, name aliases, and other connections. This is the core
of the "Ancestry for mineral rights" capability.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from app.models.etl import (
    Entity,
    Relationship,
    RelationshipType,
    SourceReference,
    VerificationStatus,
)
from app.services.etl.entity_registry import (
    create_relationship,
    get_relationships_for_entity,
)
from app.services.etl.entity_resolver import resolve_entity

logger = logging.getLogger(__name__)

# =============================================================================
# Regex patterns for relationship extraction
# =============================================================================

# "Heir of John Smith" or "Heirs of John Smith"
HEIR_OF_PATTERN = re.compile(
    r"\bHeirs?\s+of\s+([A-Za-z][A-Za-z\s.,'-]+?)(?:\s*,|\s*$|\s*\()",
    re.IGNORECASE | re.MULTILINE,
)

# "Estate of Mary Jones"
ESTATE_OF_PATTERN = re.compile(
    r"\bEstate\s+of\s+([A-Za-z][A-Za-z\s.,'-]+?)(?:\s*,|\s*$|\s*\()",
    re.IGNORECASE,
)

# "Unknown Heirs of Robert Brown"
UNKNOWN_HEIRS_PATTERN = re.compile(
    r"\bUnknown\s+Heirs?\s+(?:of\s+)?([A-Za-z][A-Za-z\s.,'-]+?)(?:\s*,|\s*$|\s*\()",
    re.IGNORECASE,
)

# "a/k/a Jane Doe" or "aka Jane Doe"
AKA_PATTERN = re.compile(
    r"\ba/?k/?a\b\s*:?\s*([A-Za-z][A-Za-z\s.,'-]+?)(?:\s*,|\s*$|\s*\()",
    re.IGNORECASE,
)

# "f/k/a Old Name LLC" or "fka Old Name"
FKA_PATTERN = re.compile(
    r"\bf/?k/?a\b\s*:?\s*([A-Za-z][A-Za-z\s.,'-]+?)(?:\s*,|\s*$|\s*\()",
    re.IGNORECASE,
)

# "Trustee of The Smith Family Trust" or "as Trustee"
TRUSTEE_OF_PATTERN = re.compile(
    r"(?:as\s+)?(?:Successor\s+)?Trustee(?:s)?\s+of\s+([A-Za-z][A-Za-z\s.,'-]+?)(?:\s*,|\s*$|\s*\()",
    re.IGNORECASE,
)

# "c/o James Smith" (care of — suggests organizational relationship)
CARE_OF_PATTERN = re.compile(
    r"\bc/?o\b\s*:?\s*([A-Za-z][A-Za-z\s.,'-]+?)(?:\s*,|\s*$|\s*\()",
    re.IGNORECASE,
)

# "FBO John Smith" (for benefit of — trust beneficiary)
FBO_PATTERN = re.compile(
    r"\bFBO\s+([A-Za-z][A-Za-z\s.,'-]+?)(?:\s*,|\s*$|\s*\()",
    re.IGNORECASE,
)


# =============================================================================
# Relationship extraction from entity data
# =============================================================================


async def extract_relationships_from_entry(
    entity: Entity,
    raw_name: str,
    notes: Optional[str],
    source: SourceReference,
) -> list[Relationship]:
    """Extract relationship signals from an entity's name and notes.

    Parses the raw name and notes fields for patterns like:
    - "Heir of X" → heir relationship
    - "Estate of X" → estate/heir relationship
    - "a/k/a Y" → aka relationship
    - "f/k/a Z" → fka relationship
    - "Trustee of T" → trustee relationship
    - "FBO B" → beneficiary relationship

    Returns list of created relationships.
    """
    relationships: list[Relationship] = []
    text_to_search = f"{raw_name} {notes or ''}"

    # Extract heir relationships
    for match in HEIR_OF_PATTERN.finditer(text_to_search):
        related_name = _clean_extracted_name(match.group(1))
        if related_name:
            rel = await _create_relationship_with_resolution(
                from_entity=entity,
                related_name=related_name,
                relationship_type=RelationshipType.HEIR,
                source=source,
            )
            if rel:
                relationships.append(rel)

    # Extract estate relationships
    for match in ESTATE_OF_PATTERN.finditer(text_to_search):
        deceased_name = _clean_extracted_name(match.group(1))
        if deceased_name:
            rel = await _create_relationship_with_resolution(
                from_entity=entity,
                related_name=deceased_name,
                relationship_type=RelationshipType.HEIR,
                source=source,
                reverse=True,  # The estate is "of" the deceased
            )
            if rel:
                relationships.append(rel)

    # Extract unknown heirs
    for match in UNKNOWN_HEIRS_PATTERN.finditer(text_to_search):
        deceased_name = _clean_extracted_name(match.group(1))
        if deceased_name:
            rel = await _create_relationship_with_resolution(
                from_entity=entity,
                related_name=deceased_name,
                relationship_type=RelationshipType.HEIR,
                source=source,
                reverse=True,
            )
            if rel:
                relationships.append(rel)

    # Extract AKA relationships (same entity, different name)
    for match in AKA_PATTERN.finditer(text_to_search):
        aka_name = _clean_extracted_name(match.group(1))
        if aka_name:
            rel = await _create_relationship_with_resolution(
                from_entity=entity,
                related_name=aka_name,
                relationship_type=RelationshipType.AKA,
                source=source,
            )
            if rel:
                relationships.append(rel)

    # Extract FKA relationships
    for match in FKA_PATTERN.finditer(text_to_search):
        fka_name = _clean_extracted_name(match.group(1))
        if fka_name:
            rel = await _create_relationship_with_resolution(
                from_entity=entity,
                related_name=fka_name,
                relationship_type=RelationshipType.FKA,
                source=source,
            )
            if rel:
                relationships.append(rel)

    # Extract trustee relationships
    for match in TRUSTEE_OF_PATTERN.finditer(text_to_search):
        trust_name = _clean_extracted_name(match.group(1))
        if trust_name:
            rel = await _create_relationship_with_resolution(
                from_entity=entity,
                related_name=trust_name,
                relationship_type=RelationshipType.TRUSTEE,
                source=source,
            )
            if rel:
                relationships.append(rel)

    # Extract care-of relationships
    for match in CARE_OF_PATTERN.finditer(text_to_search):
        co_name = _clean_extracted_name(match.group(1))
        if co_name:
            rel = await _create_relationship_with_resolution(
                from_entity=entity,
                related_name=co_name,
                relationship_type=RelationshipType.CARE_OF,
                source=source,
            )
            if rel:
                relationships.append(rel)

    # Extract FBO (for benefit of) relationships
    for match in FBO_PATTERN.finditer(text_to_search):
        beneficiary_name = _clean_extracted_name(match.group(1))
        if beneficiary_name:
            rel = await _create_relationship_with_resolution(
                from_entity=entity,
                related_name=beneficiary_name,
                relationship_type=RelationshipType.BENEFICIARY,
                source=source,
            )
            if rel:
                relationships.append(rel)

    if relationships:
        logger.info(
            f"Extracted {len(relationships)} relationships from "
            f"entity '{entity.canonical_name}'"
        )

    return relationships


async def _create_relationship_with_resolution(
    from_entity: Entity,
    related_name: str,
    relationship_type: RelationshipType,
    source: SourceReference,
    reverse: bool = False,
) -> Optional[Relationship]:
    """Create a relationship, resolving the related name to an entity first.

    If reverse=True, the relationship goes FROM the resolved entity TO from_entity.
    """
    # Resolve the related name to an entity (create if new)
    related_entity, is_new = await resolve_entity(
        name=related_name,
        entity_type_str="UNKNOWN",
        source=source,
    )

    if not related_entity or not related_entity.id or not from_entity.id:
        return None

    # Don't create self-referencing relationships
    if from_entity.id == related_entity.id:
        return None

    # Check for duplicate relationship
    existing = await get_relationships_for_entity(from_entity.id)
    for rel in existing:
        if (
            rel.relationship_type == relationship_type
            and (
                (rel.from_entity_id == from_entity.id and rel.to_entity_id == related_entity.id)
                or (rel.from_entity_id == related_entity.id and rel.to_entity_id == from_entity.id)
            )
        ):
            # Relationship already exists
            return None

    if reverse:
        relationship = Relationship(
            from_entity_id=related_entity.id,
            from_entity_name=related_entity.canonical_name,
            to_entity_id=from_entity.id,
            to_entity_name=from_entity.canonical_name,
            relationship_type=relationship_type,
            evidence=[source],
            verification_status=VerificationStatus.INFERRED,
        )
    else:
        relationship = Relationship(
            from_entity_id=from_entity.id,
            from_entity_name=from_entity.canonical_name,
            to_entity_id=related_entity.id,
            to_entity_name=related_entity.canonical_name,
            relationship_type=relationship_type,
            evidence=[source],
            verification_status=VerificationStatus.INFERRED,
        )

    return await create_relationship(relationship)


def _clean_extracted_name(name: str) -> Optional[str]:
    """Clean an extracted name, removing trailing punctuation and whitespace."""
    if not name:
        return None

    # Strip trailing commas, periods, semicolons
    cleaned = name.strip().rstrip(",;.")

    # Remove "Deceased" suffix
    cleaned = re.sub(r",?\s*Deceased\s*$", "", cleaned, flags=re.IGNORECASE)

    # Must be at least 3 characters to be a valid name
    if len(cleaned) < 3:
        return None

    return cleaned.strip()

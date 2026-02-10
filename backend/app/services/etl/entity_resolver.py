"""Entity Resolver — Fuzzy name matching and entity merge logic.

When a tool processes a document, the resolver determines whether
an extracted name matches an existing entity or should create a new one.
Uses a multi-signal scoring approach: name similarity, address overlap,
property overlap, and entity type agreement.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from difflib import SequenceMatcher
from typing import Optional

from app.models.etl import (
    AddressRecord,
    Entity,
    EntityType,
    NameVariant,
    PropertyInterest,
    SourceReference,
    VerificationStatus,
)
from app.services.etl.entity_registry import (
    ENTITIES_COLLECTION,
    add_address,
    add_name_variant,
    add_property_interest,
    add_source_reference,
    create_entity,
    update_entity,
)

logger = logging.getLogger(__name__)

# Minimum score to consider a match
MATCH_THRESHOLD = 0.70

# Weights for different matching signals
NAME_WEIGHT = 0.50
ADDRESS_WEIGHT = 0.20
PROPERTY_WEIGHT = 0.20
TYPE_WEIGHT = 0.10


# =============================================================================
# Name normalization
# =============================================================================

# Words to strip when comparing names
NOISE_WORDS = {
    "the", "of", "and", "a", "an", "inc", "llc", "lp", "ltd", "co",
    "corp", "corporation", "company", "partnership", "limited",
    "incorporated", "trust", "estate", "heirs", "unknown",
}

SUFFIX_PATTERN = re.compile(
    r"\b(jr\.?|sr\.?|ii|iii|iv|v|md|m\.d\.|phd|ph\.d\.|esq\.?)\b",
    re.IGNORECASE,
)


def normalize_name(name: str) -> str:
    """Normalize a name for comparison.

    Strips suffixes, noise words, punctuation, and extra whitespace.
    Lowercases everything.
    """
    if not name:
        return ""

    normalized = name.lower().strip()

    # Remove suffixes
    normalized = SUFFIX_PATTERN.sub("", normalized)

    # Remove punctuation except hyphens (for hyphenated names)
    normalized = re.sub(r"[^\w\s-]", "", normalized)

    # Remove noise words
    words = normalized.split()
    words = [w for w in words if w not in NOISE_WORDS]

    # Collapse whitespace
    return " ".join(words).strip()


def name_similarity(name1: str, name2: str) -> float:
    """Calculate similarity between two names (0.0 to 1.0).

    Uses SequenceMatcher for fuzzy matching after normalization.
    Also checks for last-name-first vs first-name-last reordering.
    """
    n1 = normalize_name(name1)
    n2 = normalize_name(name2)

    if not n1 or not n2:
        return 0.0

    if n1 == n2:
        return 1.0

    # Direct sequence match
    direct_score = SequenceMatcher(None, n1, n2).ratio()

    # Try reordering: "Smith, John" vs "John Smith"
    parts1 = n1.replace(",", " ").split()
    parts2 = n2.replace(",", " ").split()

    reordered_score = 0.0
    if len(parts1) >= 2 and len(parts2) >= 2:
        # Try reversing word order
        reversed1 = " ".join(reversed(parts1))
        reordered_score = SequenceMatcher(None, reversed1, n2).ratio()

    # Check if one is a subset of the other (e.g., "John Smith" in "John F. Smith")
    subset_score = 0.0
    if n1 in n2 or n2 in n1:
        shorter = min(len(n1), len(n2))
        longer = max(len(n1), len(n2))
        subset_score = shorter / longer if longer > 0 else 0.0

    return max(direct_score, reordered_score, subset_score)


def address_similarity(addr1: AddressRecord, addr2: AddressRecord) -> float:
    """Compare two addresses (0.0 to 1.0)."""
    score = 0.0
    components = 0

    if addr1.zip_code and addr2.zip_code:
        components += 1
        if addr1.zip_code[:5] == addr2.zip_code[:5]:
            score += 1.0

    if addr1.state and addr2.state:
        components += 1
        if addr1.state.upper() == addr2.state.upper():
            score += 1.0

    if addr1.city and addr2.city:
        components += 1
        if addr1.city.lower().strip() == addr2.city.lower().strip():
            score += 1.0

    if addr1.street and addr2.street:
        components += 1
        s1 = addr1.street.lower().strip()
        s2 = addr2.street.lower().strip()
        score += SequenceMatcher(None, s1, s2).ratio()

    return score / components if components > 0 else 0.0


def property_overlap(props1: list[PropertyInterest], props2: list[PropertyInterest]) -> float:
    """Check how much property overlap exists between two entities."""
    if not props1 or not props2:
        return 0.0

    matches = 0
    for p1 in props1:
        for p2 in props2:
            if p1.property_id and p2.property_id and p1.property_id == p2.property_id:
                matches += 1
            elif p1.rrc_lease and p2.rrc_lease and p1.rrc_lease == p2.rrc_lease:
                matches += 1
            elif (
                p1.legal_description
                and p2.legal_description
                and p1.legal_description.lower() == p2.legal_description.lower()
                and p1.county
                and p2.county
                and p1.county.lower() == p2.county.lower()
            ):
                matches += 1

    total = max(len(props1), len(props2))
    return matches / total if total > 0 else 0.0


# =============================================================================
# Entity type mapping from tool-specific enums
# =============================================================================


def map_entity_type(entity_type_str: str) -> EntityType:
    """Map a tool-specific entity type string to the canonical ETL EntityType."""
    mapping = {
        # Extract tool types
        "Individual": EntityType.INDIVIDUAL,
        "Trust": EntityType.TRUST,
        "LLC": EntityType.LLC,
        "Corporation": EntityType.CORPORATION,
        "Partnership": EntityType.PARTNERSHIP,
        "Government": EntityType.GOVERNMENT,
        "Estate": EntityType.ESTATE,
        "Unknown Heirs": EntityType.ESTATE,
        # Title tool types
        "INDIVIDUAL": EntityType.INDIVIDUAL,
        "CORPORATION": EntityType.CORPORATION,
        "TRUST": EntityType.TRUST,
        "ESTATE": EntityType.ESTATE,
        "FOUNDATION": EntityType.FOUNDATION,
        "MINERAL CO": EntityType.MINERAL_CO,
        "UNIVERSITY": EntityType.UNIVERSITY,
        "CHURCH": EntityType.CHURCH,
        "UNKNOWN": EntityType.UNKNOWN,
    }
    return mapping.get(entity_type_str, EntityType.UNKNOWN)


# =============================================================================
# Core resolution logic
# =============================================================================


async def resolve_entity(
    name: str,
    entity_type_str: str,
    source: SourceReference,
    address: Optional[AddressRecord] = None,
    properties: Optional[list[PropertyInterest]] = None,
    first_name: Optional[str] = None,
    middle_name: Optional[str] = None,
    last_name: Optional[str] = None,
    suffix: Optional[str] = None,
    notes: Optional[str] = None,
) -> tuple[Entity, bool]:
    """Resolve a name to an existing entity or create a new one.

    Returns: (entity, is_new) — the matched/created entity and whether it's new.
    """
    from app.services.etl.entity_registry import _get_db

    entity_type = map_entity_type(entity_type_str)
    properties = properties or []

    # Search for candidates by normalized name prefix
    db = _get_db()
    normalized = normalize_name(name)
    if not normalized:
        # Can't match on empty name — create new
        return await _create_new_entity(
            name, entity_type, source, address, properties,
            first_name, middle_name, last_name, suffix, notes,
        ), True

    # Get candidate entities from Firestore
    candidates = await _find_candidates(db, normalized, entity_type)

    # Score each candidate
    best_match: Optional[Entity] = None
    best_score: float = 0.0

    for candidate in candidates:
        score = _score_match(
            name, entity_type, address, properties, candidate
        )
        if score > best_score:
            best_score = score
            best_match = candidate

    if best_match and best_score >= MATCH_THRESHOLD:
        # Merge into existing entity
        logger.info(
            f"Matched '{name}' to existing entity '{best_match.canonical_name}' "
            f"(score: {best_score:.2f})"
        )
        await _merge_into_entity(
            best_match, name, source, address, properties
        )
        return best_match, False

    # No match found — create new entity
    new_entity = await _create_new_entity(
        name, entity_type, source, address, properties,
        first_name, middle_name, last_name, suffix, notes,
    )
    return new_entity, True


async def _find_candidates(db, normalized: str, entity_type: EntityType) -> list[Entity]:
    """Find candidate entities from Firestore for matching."""
    from app.services.etl.entity_registry import _dict_to_entity

    candidates = []
    words = normalized.split()

    if not words:
        return candidates

    # Search by canonical_name_lower prefix (first word)
    prefix = words[0]
    prefix_upper = prefix[:-1] + chr(ord(prefix[-1]) + 1) if prefix else ""

    try:
        docs = await (
            db.collection(ENTITIES_COLLECTION)
            .where("canonical_name_lower", ">=", prefix)
            .where("canonical_name_lower", "<", prefix_upper)
            .limit(50)
            .get()
        )
        for doc in docs:
            data = doc.to_dict()
            data.pop("canonical_name_lower", None)
            data.pop("last_name_lower", None)
            data.pop("name_variants_lower", None)
            candidates.append(_dict_to_entity(data))
    except Exception as e:
        logger.debug(f"Candidate prefix search failed: {e}")

    # Also search by last_name_lower if we have parsed components
    if len(words) >= 2:
        last_word = words[-1]
        last_upper = last_word[:-1] + chr(ord(last_word[-1]) + 1) if last_word else ""
        try:
            docs = await (
                db.collection(ENTITIES_COLLECTION)
                .where("last_name_lower", ">=", last_word)
                .where("last_name_lower", "<", last_upper)
                .limit(50)
                .get()
            )
            existing_ids = {c.id for c in candidates}
            for doc in docs:
                data = doc.to_dict()
                if data.get("id") not in existing_ids:
                    data.pop("canonical_name_lower", None)
                    data.pop("last_name_lower", None)
                    data.pop("name_variants_lower", None)
                    candidates.append(_dict_to_entity(data))
        except Exception as e:
            logger.debug(f"Last name candidate search failed: {e}")

    return candidates


def _score_match(
    name: str,
    entity_type: EntityType,
    address: Optional[AddressRecord],
    properties: list[PropertyInterest],
    candidate: Entity,
) -> float:
    """Score how well a new entry matches an existing entity."""
    # Name similarity (check against all known variants)
    best_name_score = name_similarity(name, candidate.canonical_name)
    for variant in candidate.names:
        variant_score = name_similarity(name, variant.name)
        best_name_score = max(best_name_score, variant_score)

    # Address similarity
    addr_score = 0.0
    if address and candidate.addresses:
        for existing_addr in candidate.addresses:
            s = address_similarity(address, existing_addr)
            addr_score = max(addr_score, s)

    # Property overlap
    prop_score = property_overlap(properties, candidate.properties)

    # Entity type agreement
    type_score = 1.0 if entity_type == candidate.entity_type else 0.0

    # Weighted total
    total = (
        NAME_WEIGHT * best_name_score
        + ADDRESS_WEIGHT * addr_score
        + PROPERTY_WEIGHT * prop_score
        + TYPE_WEIGHT * type_score
    )

    return total


async def _create_new_entity(
    name: str,
    entity_type: EntityType,
    source: SourceReference,
    address: Optional[AddressRecord],
    properties: list[PropertyInterest],
    first_name: Optional[str] = None,
    middle_name: Optional[str] = None,
    last_name: Optional[str] = None,
    suffix: Optional[str] = None,
    notes: Optional[str] = None,
) -> Entity:
    """Create a brand new entity from extracted data."""
    now = datetime.utcnow()

    entity = Entity(
        canonical_name=name,
        entity_type=entity_type,
        names=[
            NameVariant(
                name=name,
                is_primary=True,
                source=source,
                first_seen=now,
                last_seen=now,
            )
        ],
        addresses=[address] if address else [],
        properties=properties,
        source_references=[source],
        first_name=first_name,
        middle_name=middle_name,
        last_name=last_name,
        suffix=suffix,
        confidence_score=0.5,  # Single source = moderate confidence
        verification_status=VerificationStatus.INFERRED,
        notes=notes,
    )

    return await create_entity(entity)


async def _merge_into_entity(
    entity: Entity,
    name: str,
    source: SourceReference,
    address: Optional[AddressRecord],
    properties: list[PropertyInterest],
) -> None:
    """Merge new data into an existing entity."""
    # Add name variant if new
    await add_name_variant(
        entity.id,
        NameVariant(name=name, is_primary=False, source=source),
    )

    # Add address if new
    if address:
        await add_address(entity.id, address)

    # Add property interests
    for prop in properties:
        await add_property_interest(entity.id, prop)

    # Add source reference
    await add_source_reference(entity.id, source)

    # Increase confidence with multiple sources
    new_confidence = min(1.0, entity.confidence_score + 0.1)
    if new_confidence != entity.confidence_score:
        entity.confidence_score = new_confidence
        if new_confidence >= 0.8:
            entity.verification_status = VerificationStatus.HIGH_CONFIDENCE
        await update_entity(entity)

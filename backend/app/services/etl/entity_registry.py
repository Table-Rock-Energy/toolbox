"""Entity Registry — CRUD operations for canonical entities in Firestore.

Manages the central entity collection that links together all name variants,
addresses, properties, and source references from across all tools.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional
from uuid import uuid4

from app.models.etl import (
    AddressRecord,
    Entity,
    EntityType,
    NameVariant,
    OwnershipRecord,
    PropertyInterest,
    Relationship,
    SourceReference,
    VerificationStatus,
)

logger = logging.getLogger(__name__)

# Firestore collection names for the ETL pipeline
ENTITIES_COLLECTION = "entities"
RELATIONSHIPS_COLLECTION = "relationships"
OWNERSHIP_RECORDS_COLLECTION = "ownership_records"


def _get_db():
    """Lazy import Firestore client to avoid circular imports."""
    from app.services.firestore_service import get_firestore_client
    return get_firestore_client()


# =============================================================================
# Entity CRUD
# =============================================================================


async def create_entity(entity: Entity) -> Entity:
    """Create a new entity in the registry."""
    db = _get_db()
    entity_id = entity.id or str(uuid4())
    now = datetime.utcnow()

    entity.id = entity_id
    entity.created_at = now
    entity.updated_at = now

    # Set first_seen/last_seen on names and addresses
    for name in entity.names:
        if not name.first_seen:
            name.first_seen = now
        name.last_seen = now
    for addr in entity.addresses:
        if not addr.first_seen:
            addr.first_seen = now
        addr.last_seen = now

    doc_data = _entity_to_dict(entity)
    await db.collection(ENTITIES_COLLECTION).document(entity_id).set(doc_data)
    logger.info(f"Created entity {entity_id}: {entity.canonical_name}")
    return entity


async def get_entity(entity_id: str) -> Optional[Entity]:
    """Get an entity by ID."""
    db = _get_db()
    doc = await db.collection(ENTITIES_COLLECTION).document(entity_id).get()
    if not doc.exists:
        return None
    return _dict_to_entity(doc.to_dict())


async def update_entity(entity: Entity) -> Entity:
    """Update an existing entity."""
    db = _get_db()
    if not entity.id:
        raise ValueError("Entity must have an ID to update")

    entity.updated_at = datetime.utcnow()
    doc_data = _entity_to_dict(entity)
    await db.collection(ENTITIES_COLLECTION).document(entity.id).update(doc_data)
    logger.info(f"Updated entity {entity.id}: {entity.canonical_name}")
    return entity


async def delete_entity(entity_id: str) -> bool:
    """Delete an entity and its associated relationships."""
    db = _get_db()
    doc = await db.collection(ENTITIES_COLLECTION).document(entity_id).get()
    if not doc.exists:
        return False

    # Delete relationships where this entity is involved
    for field in ["from_entity_id", "to_entity_id"]:
        rels = await db.collection(RELATIONSHIPS_COLLECTION).where(
            field, "==", entity_id
        ).get()
        for rel_doc in rels:
            await rel_doc.reference.delete()

    # Delete ownership records
    records = await db.collection(OWNERSHIP_RECORDS_COLLECTION).where(
        "entity_id", "==", entity_id
    ).get()
    for rec_doc in records:
        await rec_doc.reference.delete()

    await db.collection(ENTITIES_COLLECTION).document(entity_id).delete()
    logger.info(f"Deleted entity {entity_id}")
    return True


async def add_name_variant(entity_id: str, name: NameVariant) -> Optional[Entity]:
    """Add a name variant to an existing entity."""
    entity = await get_entity(entity_id)
    if not entity:
        return None

    # Check for duplicate name
    existing_names = {n.name.lower() for n in entity.names}
    if name.name.lower() in existing_names:
        # Update last_seen on existing
        for n in entity.names:
            if n.name.lower() == name.name.lower():
                n.last_seen = datetime.utcnow()
                break
    else:
        now = datetime.utcnow()
        if not name.first_seen:
            name.first_seen = now
        name.last_seen = now
        entity.names.append(name)

    return await update_entity(entity)


async def add_address(entity_id: str, address: AddressRecord) -> Optional[Entity]:
    """Add an address to an existing entity."""
    entity = await get_entity(entity_id)
    if not entity:
        return None

    # Check for duplicate address (simple street + zip match)
    for existing in entity.addresses:
        if (
            existing.street
            and address.street
            and existing.street.lower() == address.street.lower()
            and existing.zip_code == address.zip_code
        ):
            existing.last_seen = datetime.utcnow()
            return await update_entity(entity)

    now = datetime.utcnow()
    if not address.first_seen:
        address.first_seen = now
    address.last_seen = now
    entity.addresses.append(address)
    return await update_entity(entity)


async def add_source_reference(
    entity_id: str, source: SourceReference
) -> Optional[Entity]:
    """Add a source reference to an existing entity."""
    entity = await get_entity(entity_id)
    if not entity:
        return None

    entity.source_references.append(source)
    return await update_entity(entity)


async def add_property_interest(
    entity_id: str, prop: PropertyInterest
) -> Optional[Entity]:
    """Add or update a property interest for an entity."""
    entity = await get_entity(entity_id)
    if not entity:
        return None

    # Check for existing property by ID or name
    for existing in entity.properties:
        if (
            (existing.property_id and existing.property_id == prop.property_id)
            or (existing.rrc_lease and existing.rrc_lease == prop.rrc_lease)
        ):
            # Update with newer data
            if prop.interest is not None:
                existing.interest = prop.interest
            if prop.operator:
                existing.operator = prop.operator
            if prop.interest_type:
                existing.interest_type = prop.interest_type
            return await update_entity(entity)

    entity.properties.append(prop)
    return await update_entity(entity)


# =============================================================================
# Search
# =============================================================================


async def search_entities(
    query: str,
    entity_type: Optional[EntityType] = None,
    county: Optional[str] = None,
    limit: int = 20,
) -> list[tuple[Entity, float, str]]:
    """Search entities by name, returning (entity, score, reason) tuples.

    Uses a prefix-based search on canonical_name since Firestore
    doesn't support full-text search natively. For production, consider
    Algolia or Elasticsearch.
    """
    db = _get_db()
    results: list[tuple[Entity, float, str]] = []
    query_lower = query.lower().strip()

    if not query_lower:
        return results

    # Strategy 1: Exact canonical_name prefix match via Firestore range query
    # This is the most efficient Firestore-native approach
    query_upper = query_lower[:-1] + chr(ord(query_lower[-1]) + 1)

    base_query = db.collection(ENTITIES_COLLECTION)
    base_query = base_query.where("canonical_name_lower", ">=", query_lower)
    base_query = base_query.where("canonical_name_lower", "<", query_upper)

    if entity_type:
        base_query = base_query.where("entity_type", "==", entity_type.value)

    try:
        docs = await base_query.limit(limit).get()
        for doc in docs:
            entity = _dict_to_entity(doc.to_dict())
            results.append((entity, 0.9, "canonical name match"))
    except Exception as e:
        logger.warning(f"Prefix search failed, falling back to client-side: {e}")

    # Strategy 2: If few prefix results, also search by last_name for individuals
    if len(results) < limit:
        try:
            last_name_query = db.collection(ENTITIES_COLLECTION)
            last_name_query = last_name_query.where("last_name_lower", ">=", query_lower)
            last_name_query = last_name_query.where("last_name_lower", "<", query_upper)
            last_name_docs = await last_name_query.limit(limit).get()

            existing_ids = {r[0].id for r in results}
            for doc in last_name_docs:
                data = doc.to_dict()
                if data.get("id") not in existing_ids:
                    entity = _dict_to_entity(data)
                    results.append((entity, 0.8, "last name match"))
        except Exception as e:
            logger.debug(f"Last name search failed: {e}")

    # Filter by county if specified (client-side since it's nested)
    if county:
        county_lower = county.lower()
        results = [
            (entity, score, reason)
            for entity, score, reason in results
            if any(
                p.county and county_lower in p.county.lower()
                for p in entity.properties
            )
        ]

    return results[:limit]


async def get_entities_by_type(
    entity_type: EntityType, limit: int = 50
) -> list[Entity]:
    """Get entities filtered by type."""
    db = _get_db()
    docs = await (
        db.collection(ENTITIES_COLLECTION)
        .where("entity_type", "==", entity_type.value)
        .limit(limit)
        .get()
    )
    return [_dict_to_entity(doc.to_dict()) for doc in docs]


async def get_entity_count() -> int:
    """Get total entity count."""
    db = _get_db()
    count_query = db.collection(ENTITIES_COLLECTION).count()
    result = await count_query.get()
    return result[0][0].value if result else 0


# =============================================================================
# Relationship CRUD
# =============================================================================


async def create_relationship(relationship: Relationship) -> Relationship:
    """Create a new relationship between entities."""
    db = _get_db()
    rel_id = relationship.id or str(uuid4())
    now = datetime.utcnow()

    relationship.id = rel_id
    relationship.created_at = now
    relationship.updated_at = now

    doc_data = _relationship_to_dict(relationship)
    await db.collection(RELATIONSHIPS_COLLECTION).document(rel_id).set(doc_data)
    logger.info(
        f"Created relationship {rel_id}: {relationship.from_entity_name} "
        f"--[{relationship.relationship_type.value}]--> "
        f"{relationship.to_entity_name}"
    )
    return relationship


async def get_relationships_for_entity(entity_id: str) -> list[Relationship]:
    """Get all relationships where entity is either source or target."""
    db = _get_db()
    relationships = []

    # Where entity is the source
    from_docs = await (
        db.collection(RELATIONSHIPS_COLLECTION)
        .where("from_entity_id", "==", entity_id)
        .get()
    )
    relationships.extend(_dict_to_relationship(doc.to_dict()) for doc in from_docs)

    # Where entity is the target
    to_docs = await (
        db.collection(RELATIONSHIPS_COLLECTION)
        .where("to_entity_id", "==", entity_id)
        .get()
    )
    relationships.extend(_dict_to_relationship(doc.to_dict()) for doc in to_docs)

    return relationships


async def get_relationship_count() -> int:
    """Get total relationship count."""
    db = _get_db()
    count_query = db.collection(RELATIONSHIPS_COLLECTION).count()
    result = await count_query.get()
    return result[0][0].value if result else 0


# =============================================================================
# Ownership Record CRUD
# =============================================================================


async def create_ownership_record(record: OwnershipRecord) -> OwnershipRecord:
    """Create a new ownership history record."""
    db = _get_db()
    record_id = record.id or str(uuid4())
    now = datetime.utcnow()

    record.id = record_id
    record.created_at = now
    record.updated_at = now

    doc_data = record.model_dump(mode="json")
    await db.collection(OWNERSHIP_RECORDS_COLLECTION).document(record_id).set(doc_data)
    logger.info(f"Created ownership record {record_id} for entity {record.entity_id}")
    return record


async def get_ownership_records_for_entity(
    entity_id: str,
) -> list[OwnershipRecord]:
    """Get ownership history for an entity."""
    db = _get_db()
    docs = await (
        db.collection(OWNERSHIP_RECORDS_COLLECTION)
        .where("entity_id", "==", entity_id)
        .get()
    )
    return [OwnershipRecord(**doc.to_dict()) for doc in docs]


async def get_ownership_record_count() -> int:
    """Get total ownership record count."""
    db = _get_db()
    count_query = db.collection(OWNERSHIP_RECORDS_COLLECTION).count()
    result = await count_query.get()
    return result[0][0].value if result else 0


# =============================================================================
# Serialization helpers
# =============================================================================


def _entity_to_dict(entity: Entity) -> dict:
    """Convert Entity to Firestore-friendly dict with search indexes."""
    data = entity.model_dump(mode="json")

    # Add lowercase fields for search indexing
    data["canonical_name_lower"] = entity.canonical_name.lower()
    if entity.last_name:
        data["last_name_lower"] = entity.last_name.lower()
    else:
        data["last_name_lower"] = ""

    # Store all known name variants lowercase for search
    data["name_variants_lower"] = [
        n.name.lower() for n in entity.names
    ]

    return data


def _dict_to_entity(data: dict) -> Entity:
    """Convert Firestore dict back to Entity, stripping index fields."""
    # Remove search index fields that aren't part of the model
    data.pop("canonical_name_lower", None)
    data.pop("last_name_lower", None)
    data.pop("name_variants_lower", None)
    return Entity(**data)


def _relationship_to_dict(rel: Relationship) -> dict:
    """Convert Relationship to Firestore-friendly dict."""
    return rel.model_dump(mode="json")


def _dict_to_relationship(data: dict) -> Relationship:
    """Convert Firestore dict back to Relationship."""
    return Relationship(**data)

"""Entity Registry — CRUD operations for canonical entities in PostgreSQL.

Manages the central entity collection that links together all name variants,
addresses, properties, and source references from across all tools.

Uses AppConfig table as a key-value document store with prefixed keys
(e.g., "entity:{id}", "relationship:{id}", "ownership:{id}").
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
)

logger = logging.getLogger(__name__)

# Key prefixes for the AppConfig key-value store
ENTITY_PREFIX = "etl_entity:"
RELATIONSHIP_PREFIX = "etl_relationship:"
OWNERSHIP_PREFIX = "etl_ownership:"


def _get_session_maker():
    """Get async session maker."""
    from app.core.database import async_session_maker
    return async_session_maker


async def _get_doc(key: str) -> Optional[dict]:
    """Get a document from AppConfig by key."""
    from app.services import db_service
    session_maker = _get_session_maker()
    async with session_maker() as session:
        return await db_service.get_config_doc(session, key)


async def _set_doc(key: str, data: dict) -> None:
    """Set a document in AppConfig by key."""
    from app.services import db_service
    session_maker = _get_session_maker()
    async with session_maker() as session:
        await db_service.set_config_doc(session, key, data)
        await session.commit()


async def _delete_doc(key: str) -> bool:
    """Delete a document from AppConfig by key."""
    from sqlalchemy import select
    from app.models.db_models import AppConfig
    session_maker = _get_session_maker()
    async with session_maker() as session:
        result = await session.execute(
            select(AppConfig).where(AppConfig.key == key)
        )
        existing = result.scalar_one_or_none()
        if not existing:
            return False
        await session.delete(existing)
        await session.commit()
        return True


async def _query_docs_by_prefix(prefix: str, limit: int = 50) -> list[dict]:
    """Query all documents with a given key prefix."""
    from sqlalchemy import select
    from app.models.db_models import AppConfig
    session_maker = _get_session_maker()
    async with session_maker() as session:
        result = await session.execute(
            select(AppConfig)
            .where(AppConfig.key.startswith(prefix))
            .limit(limit)
        )
        rows = result.scalars().all()
        return [row.data for row in rows if row.data]


async def _query_docs_by_prefix_where(
    prefix: str,
    field: str,
    value: str,
    limit: int = 50,
) -> list[dict]:
    """Query documents with prefix and a JSON field match."""
    from sqlalchemy import select
    from app.models.db_models import AppConfig
    session_maker = _get_session_maker()
    async with session_maker() as session:
        result = await session.execute(
            select(AppConfig)
            .where(
                AppConfig.key.startswith(prefix),
                AppConfig.data[field].as_string() == value,
            )
            .limit(limit)
        )
        rows = result.scalars().all()
        return [row.data for row in rows if row.data]


async def _count_docs_by_prefix(prefix: str) -> int:
    """Count documents with a given key prefix."""
    from sqlalchemy import select, func
    from app.models.db_models import AppConfig
    session_maker = _get_session_maker()
    async with session_maker() as session:
        result = await session.execute(
            select(func.count(AppConfig.id))
            .where(AppConfig.key.startswith(prefix))
        )
        return result.scalar() or 0


# =============================================================================
# Entity CRUD
# =============================================================================


async def create_entity(entity: Entity) -> Entity:
    """Create a new entity in the registry."""
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
    await _set_doc(f"{ENTITY_PREFIX}{entity_id}", doc_data)
    logger.info(f"Created entity {entity_id}: {entity.canonical_name}")
    return entity


async def get_entity(entity_id: str) -> Optional[Entity]:
    """Get an entity by ID."""
    data = await _get_doc(f"{ENTITY_PREFIX}{entity_id}")
    if not data:
        return None
    return _dict_to_entity(data)


async def update_entity(entity: Entity) -> Entity:
    """Update an existing entity."""
    if not entity.id:
        raise ValueError("Entity must have an ID to update")

    entity.updated_at = datetime.utcnow()
    doc_data = _entity_to_dict(entity)
    await _set_doc(f"{ENTITY_PREFIX}{entity.id}", doc_data)
    logger.info(f"Updated entity {entity.id}: {entity.canonical_name}")
    return entity


async def delete_entity(entity_id: str) -> bool:
    """Delete an entity and its associated relationships."""
    exists = await _get_doc(f"{ENTITY_PREFIX}{entity_id}")
    if not exists:
        return False

    # Delete relationships where this entity is involved
    from_rels = await _query_docs_by_prefix_where(
        RELATIONSHIP_PREFIX, "from_entity_id", entity_id
    )
    for rel in from_rels:
        if rel.get("id"):
            await _delete_doc(f"{RELATIONSHIP_PREFIX}{rel['id']}")

    to_rels = await _query_docs_by_prefix_where(
        RELATIONSHIP_PREFIX, "to_entity_id", entity_id
    )
    for rel in to_rels:
        if rel.get("id"):
            await _delete_doc(f"{RELATIONSHIP_PREFIX}{rel['id']}")

    # Delete ownership records
    records = await _query_docs_by_prefix_where(
        OWNERSHIP_PREFIX, "entity_id", entity_id
    )
    for rec in records:
        if rec.get("id"):
            await _delete_doc(f"{OWNERSHIP_PREFIX}{rec['id']}")

    await _delete_doc(f"{ENTITY_PREFIX}{entity_id}")
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

    Uses client-side filtering since we store entities as JSONB documents.
    """
    results: list[tuple[Entity, float, str]] = []
    query_lower = query.lower().strip()

    if not query_lower:
        return results

    # Load all entities (limited) and filter client-side
    all_docs = await _query_docs_by_prefix(ENTITY_PREFIX, limit=200)

    for data in all_docs:
        try:
            entity = _dict_to_entity(data)
        except Exception:
            continue

        if entity_type and entity.entity_type != entity_type:
            continue

        # Check canonical name
        if entity.canonical_name.lower().startswith(query_lower):
            results.append((entity, 0.9, "canonical name match"))
            continue

        # Check last name
        if entity.last_name and entity.last_name.lower().startswith(query_lower):
            results.append((entity, 0.8, "last name match"))
            continue

        # Check name variants
        for name in entity.names:
            if name.name.lower().startswith(query_lower):
                results.append((entity, 0.7, "name variant match"))
                break

    # Filter by county if specified
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
    docs = await _query_docs_by_prefix_where(
        ENTITY_PREFIX, "entity_type", entity_type.value, limit=limit
    )
    return [_dict_to_entity(data) for data in docs]


async def get_entity_count() -> int:
    """Get total entity count."""
    return await _count_docs_by_prefix(ENTITY_PREFIX)


# =============================================================================
# Relationship CRUD
# =============================================================================


async def create_relationship(relationship: Relationship) -> Relationship:
    """Create a new relationship between entities."""
    rel_id = relationship.id or str(uuid4())
    now = datetime.utcnow()

    relationship.id = rel_id
    relationship.created_at = now
    relationship.updated_at = now

    doc_data = _relationship_to_dict(relationship)
    await _set_doc(f"{RELATIONSHIP_PREFIX}{rel_id}", doc_data)
    logger.info(
        f"Created relationship {rel_id}: {relationship.from_entity_name} "
        f"--[{relationship.relationship_type.value}]--> "
        f"{relationship.to_entity_name}"
    )
    return relationship


async def get_relationships_for_entity(entity_id: str) -> list[Relationship]:
    """Get all relationships where entity is either source or target."""
    relationships = []

    from_docs = await _query_docs_by_prefix_where(
        RELATIONSHIP_PREFIX, "from_entity_id", entity_id
    )
    relationships.extend(_dict_to_relationship(data) for data in from_docs)

    to_docs = await _query_docs_by_prefix_where(
        RELATIONSHIP_PREFIX, "to_entity_id", entity_id
    )
    relationships.extend(_dict_to_relationship(data) for data in to_docs)

    return relationships


async def get_relationship_count() -> int:
    """Get total relationship count."""
    return await _count_docs_by_prefix(RELATIONSHIP_PREFIX)


# =============================================================================
# Ownership Record CRUD
# =============================================================================


async def create_ownership_record(record: OwnershipRecord) -> OwnershipRecord:
    """Create or update an ownership history record.

    Uses a deterministic document ID derived from entity_id + property key
    so re-uploading the same data overwrites rather than duplicates.
    """
    import hashlib

    now = datetime.utcnow()

    # Build a deterministic key from the natural composite key
    key_parts = [
        record.entity_id,
        record.property_id or "",
        record.property_name or "",
        record.rrc_lease or "",
        record.county or "",
        record.interest_type or "",
    ]
    composite = "|".join(key_parts).lower()
    record_id = hashlib.sha256(composite.encode()).hexdigest()[:20]

    # Check if existing — preserve created_at, update the rest
    existing = await _get_doc(f"{OWNERSHIP_PREFIX}{record_id}")

    record.id = record_id
    record.updated_at = now
    if existing:
        record.created_at = existing.get("created_at", now)
    else:
        record.created_at = now

    doc_data = record.model_dump(mode="json")
    await _set_doc(f"{OWNERSHIP_PREFIX}{record_id}", doc_data)

    action = "Updated" if existing else "Created"
    logger.info(f"{action} ownership record {record_id} for entity {record.entity_id}")
    return record


async def get_ownership_records_for_entity(
    entity_id: str,
) -> list[OwnershipRecord]:
    """Get ownership history for an entity."""
    docs = await _query_docs_by_prefix_where(
        OWNERSHIP_PREFIX, "entity_id", entity_id
    )
    return [OwnershipRecord(**data) for data in docs]


async def get_ownership_record_count() -> int:
    """Get total ownership record count."""
    return await _count_docs_by_prefix(OWNERSHIP_PREFIX)


# =============================================================================
# Serialization helpers
# =============================================================================


def _entity_to_dict(entity: Entity) -> dict:
    """Convert Entity to dict with search indexes."""
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
    """Convert dict back to Entity, stripping index fields."""
    # Remove search index fields that aren't part of the model
    data.pop("canonical_name_lower", None)
    data.pop("last_name_lower", None)
    data.pop("name_variants_lower", None)
    return Entity(**data)


def _relationship_to_dict(rel: Relationship) -> dict:
    """Convert Relationship to dict."""
    return rel.model_dump(mode="json")


def _dict_to_relationship(data: dict) -> Relationship:
    """Convert dict back to Relationship."""
    return Relationship(**data)

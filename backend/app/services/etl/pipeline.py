"""ETL Pipeline — Processes tool outputs into the entity registry.

Each tool's upload endpoint calls the appropriate process_* function
after its normal processing is complete. These functions extract entities,
resolve them against the registry, and track relationships.

This module is the integration layer between the existing tools and
the new ETL pipeline. It runs as a non-blocking post-processing step
so it never disrupts the existing tool functionality.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.models.etl import (
    AddressRecord,
    OwnershipRecord,
    PropertyInterest,
    SourceReference,
    SourceTool,
)
from app.services.etl.entity_registry import create_ownership_record
from app.services.etl.entity_resolver import resolve_entity
from app.services.etl.relationship_tracker import extract_relationships_from_entry

logger = logging.getLogger(__name__)


# =============================================================================
# Extract Tool → ETL Pipeline
# =============================================================================


async def process_extract_entries(
    job_id: str,
    source_filename: str,
    entries: list[dict],
) -> dict:
    """Process Extract tool output into the entity registry.

    Extracts from PartyEntry dicts:
    - Entity names and types
    - Addresses
    - Relationships (heir, aka, fka, trustee from notes)
    """
    stats = {"entities_created": 0, "entities_merged": 0, "relationships": 0, "errors": 0}

    for entry in entries:
        try:
            source = SourceReference(
                tool=SourceTool.EXTRACT,
                job_id=job_id,
                document=source_filename,
                field="primary_name",
                extracted_text=entry.get("primary_name"),
            )

            address = _build_address(
                street=entry.get("mailing_address"),
                street_2=entry.get("mailing_address_2"),
                city=entry.get("city"),
                state=entry.get("state"),
                zip_code=entry.get("zip_code"),
                source=source,
            )

            entity, is_new = await resolve_entity(
                name=entry.get("primary_name", ""),
                entity_type_str=entry.get("entity_type", "Individual"),
                source=source,
                address=address,
                first_name=entry.get("first_name"),
                middle_name=entry.get("middle_name"),
                last_name=entry.get("last_name"),
                suffix=entry.get("suffix"),
                notes=entry.get("notes"),
            )

            if is_new:
                stats["entities_created"] += 1
            else:
                stats["entities_merged"] += 1

            # Extract relationships from name and notes
            rels = await extract_relationships_from_entry(
                entity=entity,
                raw_name=entry.get("primary_name", ""),
                notes=entry.get("notes"),
                source=source,
            )
            stats["relationships"] += len(rels)

        except Exception as e:
            logger.warning(f"ETL error processing extract entry: {e}")
            stats["errors"] += 1

    logger.info(f"ETL processed {len(entries)} extract entries: {stats}")
    return stats


# =============================================================================
# Title Tool → ETL Pipeline
# =============================================================================


async def process_title_entries(
    job_id: str,
    source_filename: str,
    entries: list[dict],
) -> dict:
    """Process Title tool output into the entity registry.

    Extracts from OwnerEntry dicts:
    - Entity names and types
    - Addresses
    - Property interests (via legal_description)
    - Relationships from notes
    """
    stats = {"entities_created": 0, "entities_merged": 0, "relationships": 0, "errors": 0}

    for entry in entries:
        try:
            source = SourceReference(
                tool=SourceTool.TITLE,
                job_id=job_id,
                document=source_filename,
                field="full_name",
                extracted_text=entry.get("full_name"),
            )

            address = _build_address(
                street=entry.get("address"),
                street_2=entry.get("address_line_2"),
                city=entry.get("city"),
                state=entry.get("state"),
                zip_code=entry.get("zip_code"),
                source=source,
            )

            properties = []
            if entry.get("legal_description"):
                properties.append(
                    PropertyInterest(
                        legal_description=entry.get("legal_description"),
                        source=source,
                    )
                )

            entity, is_new = await resolve_entity(
                name=entry.get("full_name", ""),
                entity_type_str=entry.get("entity_type", "INDIVIDUAL"),
                source=source,
                address=address,
                properties=properties,
                first_name=entry.get("first_name"),
                middle_name=entry.get("middle_name"),
                last_name=entry.get("last_name"),
                notes=entry.get("notes"),
            )

            if is_new:
                stats["entities_created"] += 1
            else:
                stats["entities_merged"] += 1

            # Extract relationships from notes
            rels = await extract_relationships_from_entry(
                entity=entity,
                raw_name=entry.get("full_name", ""),
                notes=entry.get("notes"),
                source=source,
            )
            stats["relationships"] += len(rels)

        except Exception as e:
            logger.warning(f"ETL error processing title entry: {e}")
            stats["errors"] += 1

    logger.info(f"ETL processed {len(entries)} title entries: {stats}")
    return stats


# =============================================================================
# Proration Tool → ETL Pipeline
# =============================================================================


async def process_proration_rows(
    job_id: str,
    source_filename: str,
    rows: list[dict],
) -> dict:
    """Process Proration tool output into the entity registry.

    Extracts from MineralHolderRow dicts:
    - Entity names (owner)
    - Property interests with RRC data
    - Ownership records with NRA calculations
    """
    stats = {"entities_created": 0, "entities_merged": 0, "ownership_records": 0, "errors": 0}

    for row in rows:
        try:
            source = SourceReference(
                tool=SourceTool.PRORATION,
                job_id=job_id,
                document=source_filename,
                field="owner",
                extracted_text=row.get("owner"),
            )

            properties = []
            prop = PropertyInterest(
                property_id=row.get("property_id"),
                property_name=row.get("property"),
                county=row.get("county"),
                state=row.get("state"),
                legal_description=row.get("legal_description"),
                interest=row.get("interest"),
                interest_type=row.get("interest_type"),
                rrc_lease=row.get("rrc_lease"),
                operator=row.get("operator"),
                source=source,
            )
            if prop.property_id or prop.property_name or prop.rrc_lease:
                properties.append(prop)

            entity, is_new = await resolve_entity(
                name=row.get("owner", ""),
                entity_type_str="UNKNOWN",  # Proration doesn't classify entity types
                source=source,
                properties=properties,
            )

            if is_new:
                stats["entities_created"] += 1
            else:
                stats["entities_merged"] += 1

            # Create ownership record
            if entity.id:
                ownership = OwnershipRecord(
                    entity_id=entity.id,
                    entity_name=entity.canonical_name,
                    property_id=row.get("property_id"),
                    property_name=row.get("property"),
                    county=row.get("county"),
                    state=row.get("state"),
                    legal_description=row.get("legal_description"),
                    interest=row.get("interest"),
                    interest_type=row.get("interest_type"),
                    rrc_lease=row.get("rrc_lease"),
                    operator=row.get("operator"),
                    rrc_acres=row.get("rrc_acres"),
                    est_nra=row.get("est_nra"),
                    source=source,
                )
                await create_ownership_record(ownership)
                stats["ownership_records"] += 1

        except Exception as e:
            logger.warning(f"ETL error processing proration row: {e}")
            stats["errors"] += 1

    logger.info(f"ETL processed {len(rows)} proration rows: {stats}")
    return stats


# =============================================================================
# Revenue Tool → ETL Pipeline
# =============================================================================


async def process_revenue_statements(
    job_id: str,
    statements: list[dict],
) -> dict:
    """Process Revenue tool output into the entity registry.

    Extracts from RevenueStatement dicts:
    - Owner entities
    - Property interests with revenue data
    - Ownership records confirming active interests
    """
    stats = {"entities_created": 0, "entities_merged": 0, "ownership_records": 0, "errors": 0}

    for statement in statements:
        owner_name = statement.get("owner_name")
        if not owner_name:
            continue

        try:
            source = SourceReference(
                tool=SourceTool.REVENUE,
                job_id=job_id,
                document=statement.get("filename"),
                field="owner_name",
                extracted_text=owner_name,
            )

            # Build property interests from statement rows
            properties = []
            seen_properties = set()
            for row in statement.get("rows", []):
                prop_key = (row.get("property_number"), row.get("property_name"))
                if prop_key not in seen_properties:
                    seen_properties.add(prop_key)
                    properties.append(
                        PropertyInterest(
                            property_id=row.get("property_number"),
                            property_name=row.get("property_name"),
                            interest=row.get("decimal_interest"),
                            interest_type=row.get("interest_type"),
                            operator=statement.get("operator_name"),
                            source=source,
                        )
                    )

            entity, is_new = await resolve_entity(
                name=owner_name,
                entity_type_str="UNKNOWN",
                source=source,
                properties=properties,
            )

            if is_new:
                stats["entities_created"] += 1
            else:
                stats["entities_merged"] += 1

            # Create ownership records from revenue line items
            if entity.id:
                for prop_id, prop_name in seen_properties:
                    # Sum revenue for this property
                    prop_revenue = sum(
                        r.get("owner_net_revenue") or 0
                        for r in statement.get("rows", [])
                        if r.get("property_number") == prop_id
                    )
                    ownership = OwnershipRecord(
                        entity_id=entity.id,
                        entity_name=entity.canonical_name,
                        property_id=prop_id,
                        property_name=prop_name,
                        operator=statement.get("operator_name"),
                        last_revenue_date=str(statement.get("check_date", "")),
                        total_revenue=prop_revenue if prop_revenue else None,
                        source=source,
                    )
                    await create_ownership_record(ownership)
                    stats["ownership_records"] += 1

        except Exception as e:
            logger.warning(f"ETL error processing revenue statement: {e}")
            stats["errors"] += 1

    logger.info(f"ETL processed {len(statements)} revenue statements: {stats}")
    return stats


# =============================================================================
# Helpers
# =============================================================================


def _build_address(
    street: Optional[str] = None,
    street_2: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    zip_code: Optional[str] = None,
    source: Optional[SourceReference] = None,
) -> Optional[AddressRecord]:
    """Build an AddressRecord if any address component is present."""
    if not any([street, city, state, zip_code]):
        return None

    return AddressRecord(
        street=street,
        street_2=street_2,
        city=city,
        state=state,
        zip_code=zip_code,
        source=source,
    )

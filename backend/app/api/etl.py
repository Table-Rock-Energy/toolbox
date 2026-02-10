"""API routes for the Bronze Database (mineral rights ETL pipeline).

Provides endpoints for searching, browsing, and correcting
entities in the bronze layer — raw ingested data from all tools.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException

from app.models.etl import (
    EntityCorrectionRequest,
    EntityDetailResponse,
    EntitySearchRequest,
    EntitySearchResponse,
    EntitySearchResult,
    EntityType,
    ETLPipelineStatus,
    RelationshipCreateRequest,
    RelationshipType,
    VerificationStatus,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health_check() -> dict:
    """Health check endpoint for ETL pipeline."""
    return {"status": "healthy", "service": "bronze-database"}


@router.get("/status", response_model=ETLPipelineStatus)
async def get_pipeline_status() -> ETLPipelineStatus:
    """Get overall ETL pipeline status and statistics."""
    try:
        from app.services.etl.entity_registry import (
            get_entity_count,
            get_ownership_record_count,
            get_relationship_count,
        )

        entity_count = await get_entity_count()
        rel_count = await get_relationship_count()
        ownership_count = await get_ownership_record_count()

        return ETLPipelineStatus(
            total_entities=entity_count,
            total_relationships=rel_count,
            total_ownership_records=ownership_count,
        )
    except Exception as e:
        logger.warning(f"Failed to get pipeline status: {e}")
        return ETLPipelineStatus()


@router.post("/search", response_model=EntitySearchResponse)
async def search_entities(request: EntitySearchRequest) -> EntitySearchResponse:
    """Search the entity registry by name, county, or property.

    Supports fuzzy name matching and filters by entity type and county.
    """
    try:
        from app.services.etl.entity_registry import search_entities as do_search

        results = await do_search(
            query=request.query,
            entity_type=request.entity_type,
            county=request.county,
            limit=request.limit,
        )

        return EntitySearchResponse(
            results=[
                EntitySearchResult(
                    entity=entity,
                    match_score=score,
                    match_reason=reason,
                )
                for entity, score, reason in results
            ],
            total_count=len(results),
            query=request.query,
        )

    except Exception as e:
        logger.exception(f"Search failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {str(e)}",
        ) from e


@router.get("/entities/{entity_id}", response_model=EntityDetailResponse)
async def get_entity_detail(entity_id: str) -> EntityDetailResponse:
    """Get full entity detail including relationships and ownership history."""
    try:
        from app.services.etl.entity_registry import (
            get_entity,
            get_ownership_records_for_entity,
            get_relationships_for_entity,
        )

        entity = await get_entity(entity_id)
        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found")

        relationships = await get_relationships_for_entity(entity_id)
        ownership_records = await get_ownership_records_for_entity(entity_id)

        # Fetch related entities from relationships
        related_entities = []
        related_ids = set()
        for rel in relationships:
            other_id = (
                rel.to_entity_id
                if rel.from_entity_id == entity_id
                else rel.from_entity_id
            )
            if other_id not in related_ids:
                related_ids.add(other_id)
                related_entity = await get_entity(other_id)
                if related_entity:
                    related_entities.append(related_entity)

        return EntityDetailResponse(
            entity=entity,
            relationships=relationships,
            ownership_records=ownership_records,
            related_entities=related_entities,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get entity detail: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get entity detail: {str(e)}",
        ) from e


@router.put("/entities/{entity_id}/correct")
async def correct_entity(
    entity_id: str, request: EntityCorrectionRequest
) -> dict:
    """Correct entity information (user verification)."""
    try:
        from app.services.etl.entity_registry import get_entity, update_entity

        entity = await get_entity(entity_id)
        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found")

        if request.canonical_name:
            entity.canonical_name = request.canonical_name
        if request.entity_type:
            entity.entity_type = request.entity_type
        if request.first_name is not None:
            entity.first_name = request.first_name
        if request.middle_name is not None:
            entity.middle_name = request.middle_name
        if request.last_name is not None:
            entity.last_name = request.last_name
        if request.notes is not None:
            entity.notes = request.notes

        entity.verification_status = VerificationStatus.USER_CORRECTED
        await update_entity(entity)

        return {"success": True, "message": f"Entity '{entity.canonical_name}' updated"}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to correct entity: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to correct entity: {str(e)}",
        ) from e


@router.post("/relationships")
async def create_relationship(request: RelationshipCreateRequest) -> dict:
    """Create a new relationship between two entities."""
    try:
        from app.models.etl import Relationship, SourceReference, SourceTool
        from app.services.etl.entity_registry import (
            create_relationship as do_create,
            get_entity,
        )

        from_entity = await get_entity(request.from_entity_id)
        if not from_entity:
            raise HTTPException(
                status_code=404, detail="Source entity not found"
            )

        to_entity = await get_entity(request.to_entity_id)
        if not to_entity:
            raise HTTPException(
                status_code=404, detail="Target entity not found"
            )

        relationship = Relationship(
            from_entity_id=request.from_entity_id,
            from_entity_name=from_entity.canonical_name,
            to_entity_id=request.to_entity_id,
            to_entity_name=to_entity.canonical_name,
            relationship_type=request.relationship_type,
            interest_transferred=request.interest_transferred,
            effective_date=request.effective_date,
            evidence=[
                SourceReference(tool=SourceTool.MANUAL)
            ],
            verification_status=VerificationStatus.USER_VERIFIED,
            notes=request.notes,
        )

        created = await do_create(relationship)
        return {
            "success": True,
            "relationship_id": created.id,
            "message": (
                f"Created {request.relationship_type.value} relationship: "
                f"{from_entity.canonical_name} -> {to_entity.canonical_name}"
            ),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to create relationship: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create relationship: {str(e)}",
        ) from e


@router.get("/entities/{entity_id}/relationships")
async def get_entity_relationships(entity_id: str) -> dict:
    """Get all relationships for an entity."""
    try:
        from app.services.etl.entity_registry import (
            get_entity,
            get_relationships_for_entity,
        )

        entity = await get_entity(entity_id)
        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found")

        relationships = await get_relationships_for_entity(entity_id)
        return {
            "entity_id": entity_id,
            "entity_name": entity.canonical_name,
            "relationships": [r.model_dump(mode="json") for r in relationships],
            "count": len(relationships),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get relationships: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get relationships: {str(e)}",
        ) from e


@router.get("/entities/{entity_id}/ownership")
async def get_entity_ownership(entity_id: str) -> dict:
    """Get ownership history for an entity."""
    try:
        from app.services.etl.entity_registry import (
            get_entity,
            get_ownership_records_for_entity,
        )

        entity = await get_entity(entity_id)
        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found")

        records = await get_ownership_records_for_entity(entity_id)
        return {
            "entity_id": entity_id,
            "entity_name": entity.canonical_name,
            "ownership_records": [r.model_dump(mode="json") for r in records],
            "count": len(records),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get ownership records: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get ownership records: {str(e)}",
        ) from e

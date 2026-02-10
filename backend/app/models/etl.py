"""Pydantic models for the Bronze Database (mineral rights ETL pipeline).

Core domain models for entity resolution, relationship tracking,
and ownership history across all toolbox data sources. This is the
bronze layer — raw ingested entities with basic resolution.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# =============================================================================
# Enums
# =============================================================================


class EntityType(str, Enum):
    """Canonical entity types across all tools."""

    INDIVIDUAL = "individual"
    TRUST = "trust"
    ESTATE = "estate"
    LLC = "llc"
    CORPORATION = "corporation"
    PARTNERSHIP = "partnership"
    FOUNDATION = "foundation"
    MINERAL_CO = "mineral_co"
    GOVERNMENT = "government"
    UNIVERSITY = "university"
    CHURCH = "church"
    UNKNOWN = "unknown"


class RelationshipType(str, Enum):
    """Types of relationships between entities."""

    HEIR = "heir"
    TRUSTEE = "trustee"
    BENEFICIARY = "beneficiary"
    SUCCESSOR = "successor"
    AKA = "aka"  # Also known as (same entity, different name)
    FKA = "fka"  # Formerly known as (name change)
    CARE_OF = "care_of"
    SPOUSE = "spouse"
    PARENT = "parent"
    CHILD = "child"
    MEMBER = "member"  # LLC/partnership member


class VerificationStatus(str, Enum):
    """How confident we are in a data point."""

    INFERRED = "inferred"  # Extracted automatically, not verified
    HIGH_CONFIDENCE = "high_confidence"  # Multiple sources agree
    USER_VERIFIED = "user_verified"  # Human confirmed
    USER_CORRECTED = "user_corrected"  # Human corrected from inferred
    DISPUTED = "disputed"  # Conflicting information


class SourceTool(str, Enum):
    """Which tool produced the data."""

    EXTRACT = "extract"
    TITLE = "title"
    PRORATION = "proration"
    REVENUE = "revenue"
    MANUAL = "manual"  # User-entered directly


# =============================================================================
# Source Reference (provenance tracking)
# =============================================================================


class SourceReference(BaseModel):
    """Tracks where a piece of data came from."""

    tool: SourceTool = Field(..., description="Which tool produced this data")
    job_id: Optional[str] = Field(None, description="Firestore job ID")
    document: Optional[str] = Field(None, description="Source filename")
    field: Optional[str] = Field(None, description="Specific field (e.g., 'primary_name')")
    extracted_text: Optional[str] = Field(None, description="Raw text that was parsed")
    created_at: Optional[datetime] = Field(None, description="When this was extracted")


# =============================================================================
# Name Variant
# =============================================================================


class NameVariant(BaseModel):
    """A known name for an entity, with source tracking."""

    name: str = Field(..., description="The name as it appeared")
    is_primary: bool = Field(default=False, description="Whether this is the canonical name")
    source: Optional[SourceReference] = Field(None, description="Where this name came from")
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None


# =============================================================================
# Address Record
# =============================================================================


class AddressRecord(BaseModel):
    """A known address for an entity."""

    street: Optional[str] = None
    street_2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    source: Optional[SourceReference] = None
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None


# =============================================================================
# Property Interest
# =============================================================================


class PropertyInterest(BaseModel):
    """An entity's interest in a specific property."""

    property_id: Optional[str] = Field(None, description="Property identifier")
    property_name: Optional[str] = Field(None, description="Property/lease name")
    county: Optional[str] = None
    state: Optional[str] = None
    legal_description: Optional[str] = None
    interest: Optional[float] = Field(None, description="Decimal interest (0.25 = 25%)")
    interest_type: Optional[str] = Field(None, description="mineral, royalty, working, etc.")
    rrc_lease: Optional[str] = Field(None, description="RRC lease identifier (DD-NNNNN)")
    operator: Optional[str] = None
    source: Optional[SourceReference] = None


# =============================================================================
# Entity (the core model)
# =============================================================================


class Entity(BaseModel):
    """A canonical entity in the mineral rights database.

    This is the central record that links together all name variants,
    addresses, properties, and relationships from across all tools.
    """

    id: Optional[str] = Field(None, description="Firestore document ID")
    canonical_name: str = Field(..., description="Best known name for this entity")
    entity_type: EntityType = Field(default=EntityType.UNKNOWN)
    names: list[NameVariant] = Field(
        default_factory=list, description="All known name variants"
    )
    addresses: list[AddressRecord] = Field(
        default_factory=list, description="All known addresses"
    )
    properties: list[PropertyInterest] = Field(
        default_factory=list, description="Known property interests"
    )
    source_references: list[SourceReference] = Field(
        default_factory=list, description="All data sources for this entity"
    )

    # Parsed name components (for individuals)
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    last_name: Optional[str] = None
    suffix: Optional[str] = None

    # Metadata
    confidence_score: float = Field(
        default=0.0, description="Overall confidence in entity data (0.0-1.0)"
    )
    verification_status: VerificationStatus = Field(
        default=VerificationStatus.INFERRED
    )
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# =============================================================================
# Relationship
# =============================================================================


class Relationship(BaseModel):
    """A relationship between two entities.

    Captures inheritance chains, trust relationships, name aliases,
    and other connections between entities in the mineral rights database.
    """

    id: Optional[str] = Field(None, description="Firestore document ID")
    from_entity_id: str = Field(..., description="Source entity ID")
    from_entity_name: Optional[str] = Field(None, description="Source entity name (denormalized)")
    to_entity_id: str = Field(..., description="Target entity ID")
    to_entity_name: Optional[str] = Field(None, description="Target entity name (denormalized)")
    relationship_type: RelationshipType = Field(..., description="Type of relationship")

    # Details
    interest_transferred: Optional[float] = Field(
        None, description="Interest percentage transferred (if applicable)"
    )
    effective_date: Optional[str] = Field(
        None, description="When relationship became effective"
    )
    evidence: list[SourceReference] = Field(
        default_factory=list, description="Source data supporting this relationship"
    )

    # Verification
    verification_status: VerificationStatus = Field(
        default=VerificationStatus.INFERRED
    )
    verified_by: Optional[str] = Field(None, description="Email of user who verified")
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# =============================================================================
# Ownership History Record
# =============================================================================


class OwnershipRecord(BaseModel):
    """A point-in-time record of property ownership.

    Tracks who owns what interest in which property over time,
    enabling reconstruction of ownership chains.
    """

    id: Optional[str] = Field(None, description="Firestore document ID")
    entity_id: str = Field(..., description="Entity that holds the interest")
    entity_name: Optional[str] = Field(None, description="Entity name (denormalized)")
    property_id: Optional[str] = None
    property_name: Optional[str] = None
    county: Optional[str] = None
    state: Optional[str] = None
    legal_description: Optional[str] = None
    interest: Optional[float] = Field(None, description="Decimal interest")
    interest_type: Optional[str] = None
    rrc_lease: Optional[str] = None
    operator: Optional[str] = None

    # Time range
    effective_from: Optional[str] = Field(None, description="When ownership started")
    effective_to: Optional[str] = Field(None, description="When ownership ended (null = current)")

    # Financial data (from Revenue tool)
    last_revenue_date: Optional[str] = None
    total_revenue: Optional[float] = Field(None, description="Cumulative revenue received")

    # RRC data
    rrc_acres: Optional[float] = None
    est_nra: Optional[float] = None

    source: Optional[SourceReference] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# =============================================================================
# API Request/Response Models
# =============================================================================


class EntitySearchRequest(BaseModel):
    """Search request for the entity registry."""

    query: str = Field(..., description="Name, property, or county to search for")
    entity_type: Optional[EntityType] = None
    county: Optional[str] = None
    state: Optional[str] = None
    limit: int = Field(default=20, ge=1, le=100)


class EntitySearchResult(BaseModel):
    """A single search result with match info."""

    entity: Entity
    match_score: float = Field(..., description="How well this matches the query (0.0-1.0)")
    match_reason: str = Field(..., description="Why this was matched")


class EntitySearchResponse(BaseModel):
    """Response for entity search."""

    results: list[EntitySearchResult] = Field(default_factory=list)
    total_count: int = 0
    query: str = ""


class EntityDetailResponse(BaseModel):
    """Full entity detail with relationships and ownership history."""

    entity: Entity
    relationships: list[Relationship] = Field(default_factory=list)
    ownership_records: list[OwnershipRecord] = Field(default_factory=list)
    related_entities: list[Entity] = Field(default_factory=list)


class EntityCorrectionRequest(BaseModel):
    """Request to correct entity information."""

    entity_id: str
    canonical_name: Optional[str] = None
    entity_type: Optional[EntityType] = None
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    last_name: Optional[str] = None
    notes: Optional[str] = None


class RelationshipCreateRequest(BaseModel):
    """Request to create a new relationship."""

    from_entity_id: str
    to_entity_id: str
    relationship_type: RelationshipType
    interest_transferred: Optional[float] = None
    effective_date: Optional[str] = None
    notes: Optional[str] = None


class ETLPipelineStatus(BaseModel):
    """Status of the ETL pipeline."""

    total_entities: int = 0
    total_relationships: int = 0
    total_ownership_records: int = 0
    entities_by_type: dict[str, int] = Field(default_factory=dict)
    relationships_by_type: dict[str, int] = Field(default_factory=dict)
    last_processed_at: Optional[datetime] = None
    sources_processed: dict[str, int] = Field(default_factory=dict)

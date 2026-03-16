"""Pydantic models for the enrichment pipeline API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProposedChange(BaseModel):
    """A single proposed change from any pipeline step (AI cleanup, address validation, enrichment)."""

    entry_index: int = Field(description="Index of the entry in the submitted list")
    field: str = Field(description="Field name to change")
    current_value: str = Field(description="Current value of the field")
    proposed_value: str = Field(description="Proposed new value")
    reason: str = Field(description="Brief explanation for the change")
    confidence: str = Field(
        description="Confidence level: high, medium, or low"
    )
    source: str = Field(
        description="Source of the change: ai_cleanup, google_maps, pdl, searchbug"
    )
    authoritative: bool = Field(
        default=False,
        description="Whether this change comes from an authoritative source (e.g., Google Maps)",
    )


class PipelineRequest(BaseModel):
    """Request body for pipeline endpoints."""

    tool: str = Field(description="Tool name: extract, title, proration, or revenue")
    entries: list[dict] = Field(description="List of entry dicts to process")
    field_mapping: dict[str, str] = Field(
        default_factory=dict,
        description="Maps abstract field names (street, city, state, zip) to tool-specific field names",
    )


class PipelineResponse(BaseModel):
    """Unified response from all pipeline endpoints."""

    success: bool = Field(description="Whether the operation completed")
    proposed_changes: list[ProposedChange] = Field(
        default_factory=list,
        description="List of proposed changes",
    )
    error: str | None = Field(
        default=None,
        description="Error message if operation failed",
    )
    entries_processed: int = Field(
        default=0,
        description="Number of entries processed",
    )

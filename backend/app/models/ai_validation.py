"""Pydantic models for AI-powered data validation."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class AiSuggestion(BaseModel):
    """A single AI-suggested correction for a data entry."""

    entry_index: int = Field(description="Index of the entry in the submitted list")
    field: str = Field(description="Field name to correct")
    current_value: str = Field(description="Current value of the field")
    suggested_value: str = Field(description="AI-suggested corrected value")
    reason: str = Field(description="Brief explanation for the suggestion")
    confidence: ConfidenceLevel = Field(
        default=ConfidenceLevel.MEDIUM,
        description="Confidence level of the suggestion",
    )


class AiValidationRequest(BaseModel):
    """Request to validate a set of entries using AI."""

    tool: str = Field(description="Tool name: extract, title, proration, or revenue")
    entries: list[dict] = Field(description="List of entry dicts to validate")


class AiValidationResult(BaseModel):
    """Result of AI validation containing suggestions."""

    success: bool = Field(description="Whether the validation completed")
    suggestions: list[AiSuggestion] = Field(
        default_factory=list,
        description="List of suggested corrections",
    )
    summary: str = Field(default="", description="Brief summary of findings")
    entries_reviewed: int = Field(default=0, description="Number of entries reviewed")
    issues_found: int = Field(default=0, description="Number of issues found")
    error_message: str | None = Field(
        default=None, description="Error message if validation failed"
    )


class AutoCorrection(BaseModel):
    """A single auto-applied correction from post-processing."""

    entry_index: int = Field(description="Index of the entry that was corrected")
    field: str = Field(description="Field name that was corrected")
    original_value: str = Field(description="Value before correction")
    corrected_value: str = Field(description="Value after correction")
    source: str = Field(description="Correction source: programmatic, google_maps, or ai")
    confidence: ConfidenceLevel = Field(
        default=ConfidenceLevel.HIGH,
        description="Confidence level of the correction",
    )


class PostProcessResult(BaseModel):
    """Result of automatic post-processing applied during upload."""

    corrections: list[AutoCorrection] = Field(
        default_factory=list,
        description="Auto-applied corrections (high confidence)",
    )
    ai_suggestions: list[AiSuggestion] = Field(
        default_factory=list,
        description="AI suggestions for manual review (medium/low confidence)",
    )
    steps_completed: list[str] = Field(
        default_factory=list,
        description="Post-processing steps that ran successfully",
    )
    steps_skipped: list[str] = Field(
        default_factory=list,
        description="Post-processing steps that were skipped",
    )


class AiStatusResponse(BaseModel):
    """Response for AI service status check."""

    enabled: bool = Field(description="Whether AI validation is enabled")
    model: str = Field(default="", description="Model being used")

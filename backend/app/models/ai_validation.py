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


class AiStatusResponse(BaseModel):
    """Response for AI service status check."""

    enabled: bool = Field(description="Whether AI validation is enabled")
    model: str = Field(default="", description="Model being used")
    requests_remaining_minute: int = Field(
        default=0, description="Remaining requests this minute"
    )
    requests_remaining_day: int = Field(
        default=0, description="Remaining requests today"
    )
    monthly_budget: float = Field(
        default=0, description="Monthly budget limit in USD"
    )
    monthly_spend: float = Field(
        default=0, description="Amount spent this month in USD"
    )
    monthly_budget_remaining: float = Field(
        default=0, description="Remaining budget this month in USD"
    )

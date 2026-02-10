"""Pydantic models for data enrichment (People Data Labs + SearchBug)."""

from typing import Optional

from pydantic import BaseModel, Field


class PhoneNumber(BaseModel):
    """A phone number with metadata."""

    number: str = Field(..., description="Phone number")
    type: Optional[str] = Field(None, description="Phone type: mobile, landline, voip")
    carrier: Optional[str] = Field(None, description="Phone carrier name")


class SocialProfile(BaseModel):
    """A social media profile link."""

    platform: str = Field(..., description="Platform name: linkedin, twitter, facebook, etc.")
    url: str = Field(..., description="Profile URL")
    username: Optional[str] = Field(None, description="Username on the platform")


class PublicRecordFlags(BaseModel):
    """Flags from public records searches."""

    is_deceased: bool = Field(default=False, description="Whether the person is deceased")
    deceased_date: Optional[str] = Field(None, description="Date of death if known")
    has_bankruptcy: bool = Field(default=False, description="Has bankruptcy on record")
    bankruptcy_details: list[str] = Field(default_factory=list, description="Bankruptcy case details")
    has_liens: bool = Field(default=False, description="Has liens or judgments on record")
    lien_details: list[str] = Field(default_factory=list, description="Lien/judgment details")


class EnrichedPerson(BaseModel):
    """Full enrichment result for a single person."""

    original_name: str = Field(..., description="Name as provided in the lookup")
    original_address: Optional[str] = Field(None, description="Address as provided")
    phones: list[PhoneNumber] = Field(default_factory=list, description="Phone numbers (up to 5)")
    emails: list[str] = Field(default_factory=list, description="Email addresses found")
    social_profiles: list[SocialProfile] = Field(default_factory=list, description="Social media profiles")
    public_records: PublicRecordFlags = Field(default_factory=PublicRecordFlags, description="Public record flags")
    enrichment_sources: list[str] = Field(default_factory=list, description="Which APIs contributed data")
    enriched_at: Optional[str] = Field(None, description="ISO timestamp of enrichment")
    match_confidence: Optional[str] = Field(None, description="Confidence of the match: high, medium, low")


class EnrichmentRequest(BaseModel):
    """Request to enrich one or more persons."""

    persons: list[dict] = Field(..., description="List of {name, address, city, state, zip_code} dicts")


class EnrichmentResponse(BaseModel):
    """Response from the enrichment endpoint."""

    success: bool = Field(..., description="Whether enrichment completed")
    results: list[EnrichedPerson] = Field(default_factory=list, description="Enrichment results")
    total_requested: int = Field(0, description="Number of persons requested")
    total_enriched: int = Field(0, description="Number successfully enriched")
    error_message: Optional[str] = Field(None, description="Error message if failed")


class EnrichmentStatusResponse(BaseModel):
    """Status of enrichment service configuration."""

    enabled: bool = Field(..., description="Whether enrichment is enabled")
    pdl_configured: bool = Field(..., description="Whether PDL API key is set")
    searchbug_configured: bool = Field(..., description="Whether SearchBug API key is set")


class EnrichmentConfigUpdateRequest(BaseModel):
    """Request to update enrichment API keys."""

    pdl_api_key: Optional[str] = Field(None, description="People Data Labs API key")
    searchbug_api_key: Optional[str] = Field(None, description="SearchBug API key")
    enabled: Optional[bool] = Field(None, description="Enable/disable enrichment")

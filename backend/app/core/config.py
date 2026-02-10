"""Unified application configuration using Pydantic settings."""

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings for the consolidated toolbox."""

    model_config = SettingsConfigDict(env_file=".env")

    # Application settings
    app_name: str = "Table Rock Toolbox"
    debug: bool = False
    version: str = "1.0.0"

    # Upload settings
    max_upload_size_mb: int = 50

    # Allowed file extensions by tool
    extract_extensions: list[str] = [".pdf"]
    title_extensions: list[str] = [".xlsx", ".xls", ".csv"]
    proration_extensions: list[str] = [".csv"]
    revenue_extensions: list[str] = [".pdf"]

    # Local data directory (fallback when GCS not available)
    data_dir: Path = Path(__file__).parent.parent.parent / "data"

    # Google Cloud Storage settings
    gcs_bucket_name: Optional[str] = "table-rock-tools-storage"
    gcs_project_id: Optional[str] = "tablerockenergy"

    # GCS folder paths
    gcs_rrc_data_folder: str = "rrc-data"
    gcs_uploads_folder: str = "uploads"
    gcs_profiles_folder: str = "profiles"

    # Database settings (PostgreSQL - optional, for local dev)
    # Local dev: postgresql+asyncpg://postgres:postgres@localhost:5432/toolbox
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/toolbox"
    database_enabled: bool = False  # Disabled by default, use Firestore instead

    # Firestore settings (primary database)
    firestore_enabled: bool = True

    # Gemini AI settings (optional AI-powered data validation)
    gemini_api_key: Optional[str] = None
    gemini_enabled: bool = False
    gemini_model: str = "gemini-2.5-flash"
    gemini_monthly_budget: float = 15.00  # Maximum monthly spend in USD

    # Google Maps API settings (address validation)
    google_maps_api_key: Optional[str] = None
    google_maps_enabled: bool = False

    # Data enrichment settings (People Data Labs + SearchBug)
    pdl_api_key: Optional[str] = None
    searchbug_api_key: Optional[str] = None
    enrichment_enabled: bool = False

    # Encryption key for sensitive data (Fernet key, generate with: python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
    encryption_key: Optional[str] = None

    # Entity matching threshold (0.0 - 1.0)
    entity_match_threshold: float = 0.85

    @property
    def use_gcs(self) -> bool:
        """Check if GCS should be used for storage."""
        return bool(self.gcs_bucket_name)

    @property
    def use_database(self) -> bool:
        """Check if database should be used."""
        return self.database_enabled and bool(self.database_url)

    @property
    def use_gemini(self) -> bool:
        """Check if Gemini AI validation should be used."""
        return self.gemini_enabled and bool(self.gemini_api_key)

    @property
    def use_google_maps(self) -> bool:
        """Check if Google Maps address validation should be used."""
        return self.google_maps_enabled and bool(self.google_maps_api_key)

    @property
    def use_enrichment(self) -> bool:
        """Check if data enrichment should be used."""
        return self.enrichment_enabled and (bool(self.pdl_api_key) or bool(self.searchbug_api_key))


settings = Settings()

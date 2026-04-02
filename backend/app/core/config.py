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

    # Local data directory
    data_dir: Path = Path(__file__).parent.parent.parent / "data"

    # Storage folder paths
    storage_rrc_data_folder: str = "rrc-data"
    storage_uploads_folder: str = "uploads"
    storage_profiles_folder: str = "profiles"

    # Database settings (PostgreSQL - always on)
    # Local dev: postgresql+asyncpg://postgres:postgres@localhost:5432/toolbox
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/toolbox"
    database_enabled: bool = True  # Always on -- PostgreSQL is the only database

    # Unified Google Cloud API key (Places, Geocoding/Maps)
    google_api_key: Optional[str] = None

    # AI provider settings (ollama or none)
    ai_provider: str = "none"
    llm_api_base: str = "http://host.docker.internal:11434/v1"
    llm_model: str = "qwen3.5-9b"
    llm_api_key: Optional[str] = None

    # Batch processing settings
    batch_size: int = 25
    batch_max_concurrency: int = 2
    batch_max_retries: int = 1

    # Shared secret for cron/CI auth (bypasses JWT verification)
    cron_secret: Optional[str] = None

    # JWT settings (local auth)
    jwt_secret_key: str = "dev-only-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440  # 24 hours

    # Google Maps API settings (address validation)
    google_maps_api_key: Optional[str] = None
    google_maps_enabled: bool = False

    # Google Places API settings
    places_enabled: bool = False

    # Data enrichment settings (People Data Labs + SearchBug)
    pdl_api_key: Optional[str] = None
    searchbug_api_key: Optional[str] = None
    enrichment_enabled: bool = False

    # Encryption key for sensitive data (Fernet key, generate with: python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
    encryption_key: Optional[str] = None

    # Entity matching threshold (0.0 - 1.0)
    entity_match_threshold: float = 0.85

    # Default admin email (fallback when no admin exists in DB)
    default_admin_email: str = "james@tablerocktx.com"

    # Environment and CORS settings
    environment: str = "development"
    cors_allowed_origins: str = ""

    @property
    def cors_origins(self) -> list[str]:
        """Get allowed CORS origins based on configuration."""
        if self.cors_allowed_origins:
            return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]
        if self.environment == "production":
            return ["https://tools.tablerocktx.com"]
        return ["http://localhost:5173"]

    @property
    def use_ai(self) -> bool:
        """Check if any AI provider is configured."""
        return self.ai_provider != "none"

    @property
    def use_database(self) -> bool:
        """Check if database should be used."""
        return self.database_enabled and bool(self.database_url)

    @property
    def use_google_maps(self) -> bool:
        """Check if Google Maps address validation should be used."""
        return self.google_maps_enabled and bool(self.google_maps_api_key or self.google_api_key)

    @property
    def use_places(self) -> bool:
        """Check if Google Places API should be used."""
        return self.places_enabled and bool(self.google_api_key or self.google_maps_api_key)

    @property
    def use_enrichment(self) -> bool:
        """Check if data enrichment should be used."""
        return self.enrichment_enabled and (bool(self.pdl_api_key) or bool(self.searchbug_api_key))


settings = Settings()

"""Unified application configuration using Pydantic settings."""

from pathlib import Path

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

    # Data directory for RRC proration data
    data_dir: Path = Path(__file__).parent.parent.parent / "data"


settings = Settings()

"""Application configuration."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # API Keys
    anthropic_api_key: str

    # Server
    cors_origins: str = "http://localhost:3000"
    log_level: str = "INFO"

    # Redis (optional)
    redis_url: str | None = None

    # Data / Storage
    data_dir: str = "./data"
    downloads_dir: str = "./downloads"
    preload_states: str = ""  # Comma-separated list

    # FIA Storage (tiered caching)
    fia_local_dir: str = "./data/fia"
    fia_local_cache_gb: float = 5.0
    fia_s3_bucket: str | None = Field(default=None, alias="FIA_S3_BUCKET")
    fia_s3_prefix: str = "fia-duckdb"
    s3_endpoint_url: str | None = None
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_region: str = "auto"

    # Usage tracking
    usage_storage_dir: str = "./data/usage"

    # Rate limiting
    rate_limit_requests: int = 100  # per minute
    rate_limit_downloads: int = 10  # per hour

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def preload_states_list(self) -> list[str]:
        if not self.preload_states:
            return []
        return [state.strip().upper() for state in self.preload_states.split(",")]


def get_settings() -> Settings:
    """Get settings instance."""
    return Settings()


settings = get_settings()

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

    # Authentication (JWT cookie-based)
    auth_password_hash: str | None = Field(
        default=None,
        alias="AUTH_PASSWORD_HASH",
        description="bcrypt hash of the shared password",
    )
    auth_jwt_secret: str | None = Field(
        default=None,
        alias="AUTH_JWT_SECRET",
        description="Secret key for JWT signing",
    )
    auth_access_token_expire: int = Field(
        default=1800,  # 30 minutes
        alias="AUTH_ACCESS_TOKEN_EXPIRE",
    )
    auth_refresh_token_expire: int = Field(
        default=604800,  # 7 days
        alias="AUTH_REFRESH_TOKEN_EXPIRE",
    )

    @property
    def auth_enabled(self) -> bool:
        """Check if authentication is enabled."""
        return bool(self.auth_password_hash and self.auth_jwt_secret)

    # Server
    cors_origins: str = "http://localhost:3000"
    log_level: str = "INFO"

    # Redis (optional)
    redis_url: str | None = None

    # Data / Storage
    data_dir: str = "./data"
    downloads_dir: str = "./downloads"
    preload_states: str = ""  # Comma-separated list

    # FIA Storage (tiered caching - legacy, kept for migration)
    fia_local_dir: str = "./data/fia"
    fia_local_cache_gb: float = 5.0
    fia_s3_bucket: str | None = Field(default=None, alias="FIA_S3_BUCKET")
    fia_s3_prefix: str = "fia-duckdb"
    s3_endpoint_url: str | None = None
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_region: str = "auto"

    # MotherDuck (serverless DuckDB - primary storage)
    motherduck_token: str | None = Field(default=None, alias="MOTHERDUCK_TOKEN")

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

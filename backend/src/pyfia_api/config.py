"""Application configuration."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Keys
    anthropic_api_key: str

    # Server
    cors_origins: str = "http://localhost:3000"
    log_level: str = "INFO"

    # Redis (optional)
    redis_url: str | None = None

    # Data
    data_dir: str = "./data"
    downloads_dir: str = "./downloads"
    preload_states: str = ""  # Comma-separated list

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

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()

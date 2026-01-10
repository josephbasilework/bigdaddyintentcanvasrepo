"""Application configuration loaded from environment variables."""

from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings.

    All configuration comes from environment variables. The application
    will fail to start if required secrets are missing.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Gateway
    pydantic_gateway_api_key: str = Field(
        default="", description="Pydantic AI Gateway API key (required)"
    )
    pydantic_gateway_base_url: str = Field(
        default="https://gateway.pydantic.dev/proxy/openai/",
        description="Pydantic AI Gateway base URL",
    )

    # xAI (for fallback models)
    xai_api_key: str = Field(default="", description="xAI API key (optional)")

    # Application
    app_name: str = Field(default="IntentUI Backend", description="Application name")
    app_version: str = Field(default="0.1.0", description="Application version")
    environment: Literal["dev", "staging", "prod"] = Field(
        default="dev", description="Deployment environment"
    )
    debug: bool = Field(default=False, description="Debug mode")
    log_level: str = Field(default="info", description="Log level")

    # API
    api_prefix: str = Field(default="/api/v1", description="API route prefix")
    cors_origins: list[str] = Field(
        default=["http://localhost:3000"], description="CORS allowed origins"
    )

    # Database
    database_url: str = Field(
        default="sqlite:///./intentui.db",
        description="Database connection URL (PostgreSQL or SQLite)",
    )

    # Backup
    backup_encryption_key: str = Field(
        default="",
        description="Fernet encryption key for backup data (base64 encoded)",
    )
    backup_retention_days: int = Field(
        default=30, description="Number of days to retain backups"
    )
    backup_schedule_hour: int = Field(
        default=2, ge=0, le=23, description="Hour to run daily backup (0-23)"
    )
    backup_enabled: bool = Field(
        default=True, description="Enable automatic daily backups"
    )

    # Redis (for job queue)
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis URL for job queue (e.g., redis://localhost:6379/0)",
    )
    redis_host: str = Field(
        default="localhost", description="Redis host for job queue (deprecated, use redis_url)"
    )
    redis_port: int = Field(
        default=6379, description="Redis port for job queue (deprecated, use redis_url)"
    )
    redis_db: int = Field(
        default=0, description="Redis database number for job queue (deprecated, use redis_url)"
    )
    redis_password: str = Field(
        default="", description="Redis password (optional, deprecated, use redis_url)"
    )

    @field_validator("pydantic_gateway_api_key")
    @classmethod
    def validate_gateway_api_key(cls, v: str) -> str:
        """Ensure gateway API key is not empty."""
        if not v or v.strip() == "":
            raise ValueError(
                "PYDANTIC_GATEWAY_API_KEY is required and cannot be empty"
            )
        return v


_settings: Settings | None = None


def get_settings() -> Settings:
    """Get cached settings instance.

    Creates the settings instance on first call and caches it for
    subsequent calls to avoid repeated environment variable lookups.
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

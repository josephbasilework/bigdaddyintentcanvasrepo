"""Unit tests for application configuration (app/config.py)."""


import pytest

from app.config import Settings, get_settings


class TestSettingsRequiredFieldValidation:
    """Tests for required field validation."""

    def test_pydantic_gateway_api_key_required(self):
        """Test that PYDANTIC_GATEWAY_API_KEY is required."""
        with pytest.raises(ValueError) as exc_info:
            Settings(pydantic_gateway_api_key="")
        assert "PYDANTIC_GATEWAY_API_KEY is required" in str(exc_info.value)

    def test_pydantic_gateway_api_key_whitespace_rejected(self):
        """Test that whitespace-only API key is rejected."""
        with pytest.raises(ValueError) as exc_info:
            Settings(pydantic_gateway_api_key="   ")
        assert "PYDANTIC_GATEWAY_API_KEY is required" in str(exc_info.value)

    def test_valid_api_key_accepted(self):
        """Test that valid API key is accepted."""
        settings = Settings(pydantic_gateway_api_key="test-key-123")
        assert settings.pydantic_gateway_api_key == "test-key-123"


class TestSettingsDefaultValues:
    """Tests for default configuration values."""

    def test_database_url_default(self):
        """Test DATABASE_URL defaults to SQLite."""
        settings = Settings(pydantic_gateway_api_key="test-key")
        assert settings.database_url == "sqlite:///./intentui.db"

    def test_redis_url_default(self):
        """Test REDIS_URL defaults to localhost:6379/0."""
        settings = Settings(pydantic_gateway_api_key="test-key")
        assert settings.redis_url == "redis://localhost:6379/0"

    def test_cors_origins_default(self):
        """Test CORS_ORIGINS defaults to localhost:3000."""
        settings = Settings(pydantic_gateway_api_key="test-key")
        # Default includes both frontend (3000) and backend (8000) ports
        assert "http://localhost:3000" in settings.cors_origins

    def test_gateway_base_url_default(self):
        """Test Gateway base URL has correct default."""
        settings = Settings(pydantic_gateway_api_key="test-key")
        assert settings.pydantic_gateway_base_url == "https://gateway.pydantic.dev/proxy/openai/"

    def test_app_name_default(self):
        """Test app name has correct default."""
        settings = Settings(pydantic_gateway_api_key="test-key")
        assert settings.app_name == "IntentUI Backend"

    def test_environment_default(self):
        """Test environment defaults to dev."""
        settings = Settings(pydantic_gateway_api_key="test-key")
        assert settings.environment == "dev"


class TestSettingsEnvironmentOverrides:
    """Tests for environment variable override behavior."""

    def test_database_url_override(self):
        """Test DATABASE_URL can be overridden."""
        settings = Settings(
            pydantic_gateway_api_key="test-key",
            database_url="postgresql://user:pass@localhost/db"
        )
        assert settings.database_url == "postgresql://user:pass@localhost/db"

    def test_redis_url_override(self):
        """Test REDIS_URL can be overridden."""
        settings = Settings(
            pydantic_gateway_api_key="test-key",
            redis_url="redis://redis-server:6380/1"
        )
        assert settings.redis_url == "redis://redis-server:6380/1"

    def test_cors_origins_override(self):
        """Test CORS_ORIGINS can be overridden."""
        settings = Settings(
            pydantic_gateway_api_key="test-key",
            cors_origins=["http://localhost:3000", "http://localhost:8000", "https://example.com"]
        )
        assert settings.cors_origins == [
            "http://localhost:3000",
            "http://localhost:8000",
            "https://example.com"
        ]

    def test_xai_api_key_optional(self):
        """Test XAI_API_KEY is optional with empty default."""
        # Create Settings class without env file to test actual defaults
        from pydantic_settings import SettingsConfigDict

        class SettingsNoEnvFile(Settings):
            model_config = SettingsConfigDict(
                env_file=None,
                env_file_encoding="utf-8",
                case_sensitive=False,
                extra="ignore",
            )

        settings = SettingsNoEnvFile(pydantic_gateway_api_key="test-key")
        assert settings.xai_api_key == ""

        settings_with_xai = SettingsNoEnvFile(
            pydantic_gateway_api_key="test-key",
            xai_api_key="xai-test-key"
        )
        assert settings_with_xai.xai_api_key == "xai-test-key"


class TestGetSettingsSingleton:
    """Tests for the get_settings() singleton function."""

    def test_get_settings_returns_settings_instance(self):
        """Test that get_settings returns a Settings instance."""
        settings = get_settings()
        assert isinstance(settings, Settings)

    def test_get_settings_caches_instance(self):
        """Test that get_settings caches the settings instance."""
        # Reset singleton for clean test
        import app.config as config_module
        config_module._settings = None

        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2

        # Clean up
        config_module._settings = None


class TestSettingsEnvFileLoading:
    """Tests for .env file loading behavior."""

    def test_env_file_configured(self):
        """Test that Settings is configured to read from .env file."""
        # Verify the model_config has env_file set
        assert Settings.model_config["env_file"] == ".env"
        assert Settings.model_config["env_file_encoding"] == "utf-8"

    def test_case_insensitive_enabled(self):
        """Test that environment variable names are case-insensitive."""
        # Verify case_sensitive=False is set
        assert Settings.model_config["case_sensitive"] is False

from functools import lru_cache
from typing import List, Literal, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    # Application
    environment: str = Field(default="development", env="ENVIRONMENT")
    debug: bool = Field(default=False, env="DEBUG")
    api_version: str = Field(default="v1", env="API_VERSION")

    # LLM Backend Configuration
    llm_provider: Literal["gemini", "openai", "ollama"] = Field(
        default="gemini", env="LLM_PROVIDER"
    )
    llm_model: str = Field(default="gemini-2.5-pro", env="LLM_MODEL")
    llm_temperature: float = Field(default=0.1, env="LLM_TEMPERATURE")
    llm_max_tokens: int = Field(default=8192, env="LLM_MAX_TOKENS")

    # Google Gemini AI configuration
    google_api_key: Optional[str] = Field(default=None, env="GOOGLE_API_KEY")
    gemini_rate_limit_rpm: int = Field(default=300, env="GEMINI_RATE_LIMIT_RPM")
    gemini_rate_limit_tpm: int = Field(default=50000, env="GEMINI_RATE_LIMIT_TPM")

    # OpenAI Configuration
    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    openai_base_url: Optional[str] = Field(default=None, env="OPENAI_BASE_URL")

    # Ollama Configuration
    ollama_base_url: str = Field(default="http://localhost:11434", env="OLLAMA_BASE_URL")
    ollama_timeout: int = Field(default=300, env="OLLAMA_TIMEOUT")  # 5 minutes for slow responses

    # Redis configuration
    redis_url: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    redis_max_connections: int = Field(default=50, env="REDIS_MAX_CONNECTIONS")

    # Document processing configuration
    max_file_size: int = Field(default=52428800, env="MAX_FILE_SIZE")  # 50MB
    batch_size_limit: int = Field(default=50, env="BATCH_SIZE_LIMIT")
    result_cache_ttl: int = Field(default=2592000, env="RESULT_CACHE_TTL")  # 30 days
    max_concurrent_jobs: int = Field(default=10, env="MAX_CONCURRENT_JOBS")

    # Security and CORS configuration
    secret_key: str = Field(..., env="SECRET_KEY")
    allowed_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"], env="ALLOWED_ORIGINS"
    )
    cors_enabled: bool = Field(default=True, env="CORS_ENABLED")

    # Monitoring and analytics configuration
    enable_usage_tracking: bool = Field(default=True, env="ENABLE_USAGE_TRACKING")
    cost_alert_threshold: float = Field(default=100.0, env="COST_ALERT_THRESHOLD")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    enable_metrics: bool = Field(default=True, env="ENABLE_METRICS")

    @field_validator("llm_temperature")
    @classmethod
    def validate_temperature(cls, v):
        if not 0.0 <= v <= 2.0:
            raise ValueError("Temperature must be between 0.0 and 2.0")
        return v

    @field_validator("llm_provider")
    @classmethod
    def validate_llm_provider(cls, v):
        valid_providers = ["gemini", "openai", "ollama"]
        if v not in valid_providers:
            raise ValueError(f"LLM provider must be one of: {valid_providers}")
        return v

    def model_post_init(self, __context):
        """Validate provider-specific API keys after model initialization."""
        if self.llm_provider == "gemini" and not self.google_api_key:
            raise ValueError("Google API key is required when using Gemini provider")
        elif self.llm_provider == "openai" and not self.openai_api_key:
            raise ValueError("OpenAI API key is required when using OpenAI provider")

    @field_validator("max_file_size")
    @classmethod
    def validate_max_file_size(cls, v):
        if v <= 0 or v > 100_000_000:  # 100MB max
            raise ValueError("Max file size must be between 1B and 100MB")
        return v

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v):
        if not v or len(v) < 32:
            raise ValueError("Secret key must be at least 32 characters long")
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v):
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of: {valid_levels}")
        return v.upper()

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v):
        valid_envs = ["development", "staging", "production"]
        if v not in valid_envs:
            raise ValueError(f"Environment must be one of: {valid_envs}")
        return v

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        return self.environment == "development"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Export settings instance
settings = get_settings()

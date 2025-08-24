from functools import lru_cache
from typing import List, Optional
from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class GeminiSettings(BaseSettings):
    """Google Gemini AI configuration."""
    
    api_key: str = Field(..., env="GOOGLE_API_KEY")
    model: str = Field(default="gemini-2.5-pro", env="GEMINI_MODEL")
    temperature: float = Field(default=0.1, env="GEMINI_TEMPERATURE")
    max_tokens: int = Field(default=8192, env="GEMINI_MAX_TOKENS")
    rate_limit_rpm: int = Field(default=300, env="GEMINI_RATE_LIMIT_RPM")
    rate_limit_tpm: int = Field(default=50000, env="GEMINI_RATE_LIMIT_TPM")
    
    @validator("temperature")
    def validate_temperature(cls, v):
        if not 0.0 <= v <= 2.0:
            raise ValueError("Temperature must be between 0.0 and 2.0")
        return v

    @validator("api_key")
    def validate_api_key(cls, v):
        if not v or len(v) < 10:
            raise ValueError("Valid Google API key is required")
        return v


class RedisSettings(BaseSettings):
    """Redis configuration for caching and job queue."""
    
    url: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    max_connections: int = Field(default=50, env="REDIS_MAX_CONNECTIONS")


class ProcessingSettings(BaseSettings):
    """Document processing configuration."""
    
    max_file_size: int = Field(default=52428800, env="MAX_FILE_SIZE")  # 50MB
    batch_size_limit: int = Field(default=50, env="BATCH_SIZE_LIMIT")
    result_cache_ttl: int = Field(default=2592000, env="RESULT_CACHE_TTL")  # 30 days
    max_concurrent_jobs: int = Field(default=10, env="MAX_CONCURRENT_JOBS")
    
    @validator("max_file_size")
    def validate_max_file_size(cls, v):
        if v <= 0 or v > 100_000_000:  # 100MB max
            raise ValueError("Max file size must be between 1B and 100MB")
        return v


class SecuritySettings(BaseSettings):
    """Security and CORS configuration."""
    
    secret_key: str = Field(..., env="SECRET_KEY")
    allowed_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"],
        env="ALLOWED_ORIGINS"
    )
    cors_enabled: bool = Field(default=True, env="CORS_ENABLED")
    
    @validator("secret_key")
    def validate_secret_key(cls, v):
        if not v or len(v) < 32:
            raise ValueError("Secret key must be at least 32 characters long")
        return v


class MonitoringSettings(BaseSettings):
    """Monitoring and analytics configuration."""
    
    enable_usage_tracking: bool = Field(default=True, env="ENABLE_USAGE_TRACKING")
    cost_alert_threshold: float = Field(default=100.0, env="COST_ALERT_THRESHOLD")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    enable_metrics: bool = Field(default=True, env="ENABLE_METRICS")
    
    @validator("log_level")
    def validate_log_level(cls, v):
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of: {valid_levels}")
        return v.upper()


class Settings(BaseSettings):
    """Main application settings."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Application
    environment: str = Field(default="development", env="ENVIRONMENT")
    debug: bool = Field(default=False, env="DEBUG")
    api_version: str = Field(default="v1", env="API_VERSION")
    
    # Component settings
    gemini: GeminiSettings = Field(default_factory=GeminiSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    processing: ProcessingSettings = Field(default_factory=ProcessingSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    monitoring: MonitoringSettings = Field(default_factory=MonitoringSettings)
    
    @validator("environment")
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
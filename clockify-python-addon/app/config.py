from functools import lru_cache
from typing import List, Optional

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Server
    base_url: str = "http://localhost:8000"
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    
    # Database
    database_url: str = "sqlite+aiosqlite:///./clockify_addon.db"
    
    # Security
    clockify_jwks_url: Optional[str] = None
    clockify_jwks_prod_url: str = "https://api.clockify.me/.well-known/jwks.json"
    clockify_jwks_dev_url: str = "https://developer.clockify.me/.well-known/jwks.json"
    clockify_environment: str = "prod"
    require_signature_verification: bool = True
    webhook_hmac_secret: Optional[str] = None
    
    # Clockify API
    clockify_api_base: str = "https://api.clockify.me/api/v1"
    clockify_developer_api_base: str = "https://developer.clockify.me/api/v1"
    clockify_pto_api_base: str = "https://pto.api.clockify.me/v1"
    clockify_reports_api_base: str = "https://reports.api.clockify.me/v1"
    allowed_api_domains: List[str] = [
        "*.clockify.me",
        "*.clockify.com",
        "developer.clockify.me",
        "api.clockify.me",
        "reports.api.clockify.me",
        "pto.api.clockify.me",
    ]
    
    # Rate Limiting
    rate_limit_rps: int = 50
    rate_limit_enabled: bool = True
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    use_redis: bool = False
    
    # Logging
    log_level: str = "INFO"
    log_format: str = "json"
    
    # Bootstrap
    auto_bootstrap_on_install: bool = True
    bootstrap_batch_size: int = 10
    bootstrap_max_retries: int = 3
    bootstrap_max_pages: int = 1000
    
    # Payload Limits (bytes)
    api_call_max_payload_bytes: int = 1_048_576  # 1 MB
    webhook_max_payload_bytes: int = 5_242_880  # 5 MB

    # Webhook HTTP retries
    webhook_request_max_retries: int = 5
    webhook_request_backoff_base: float = 0.5
    webhook_request_backoff_cap: float = 5.0
    
    # Addon Info
    addon_key: str = "clockify-python-addon"
    addon_name: str = "Clockify Python Addon Boilerplate"
    addon_description: str = "Production-ready Clockify Add-on with full API integration"
    addon_vendor_name: str = "Your Company"
    addon_vendor_url: str = "https://your-company.com"

    @model_validator(mode="after")
    def _validate_environment(self):
        errors = []
        if not (self.base_url and self.base_url.startswith(("http://", "https://"))):
            errors.append("BASE_URL must start with http:// or https://")
        if not self.addon_key:
            errors.append("ADDON_KEY must be provided")
        if not self.database_url:
            errors.append("DATABASE_URL must be configured")
        if not self.allowed_api_domains:
            errors.append("CLOCKIFY_ALLOWED_API_DOMAINS must include at least one domain")
        if self.webhook_request_max_retries < 1:
            errors.append("WEBHOOK_REQUEST_MAX_RETRIES must be >= 1")
        if errors:
            raise ValueError(
                "; ".join(errors)
            )
        return self

    @property
    def is_development(self) -> bool:
        # Keep debug-specific behavior separate from signature enforcement.
        return self.debug

    def get_clockify_jwks_url(self, api_base_url: Optional[str] = None) -> str:
        """Resolve the correct JWKS URL based on environment or overrides."""
        if self.clockify_jwks_url:
            return self.clockify_jwks_url
        env_hint = (self.clockify_environment or "prod").lower()
        if api_base_url:
            api_base = api_base_url.lower()
            if "developer.clockify.me" in api_base:
                env_hint = "dev"
            elif "clockify" in api_base:
                env_hint = "prod"
        if env_hint in {"dev", "developer", "staging", "sandbox"}:
            return self.clockify_jwks_dev_url
        return self.clockify_jwks_prod_url

    @field_validator("allowed_api_domains", mode="before")
    @classmethod
    def _coerce_allowed_domains(cls, value):
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value


@lru_cache()
def get_settings() -> Settings:
    return Settings()

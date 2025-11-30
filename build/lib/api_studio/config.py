from pydantic import Field

from clockify_core.config import BaseClockifySettings


class Settings(BaseClockifySettings):
    """API Studio specific settings."""
    
    db_url: str = Field(default="sqlite+aiosqlite:///./api_studio.db", alias="API_STUDIO_DB_URL")
    addon_key: str = Field(default="clockify-api-studio", alias="API_STUDIO_ADDON_KEY")
    require_signature_verification: bool = Field(
        default=True,
        alias="API_STUDIO_REQUIRE_SIGNATURE_VERIFICATION",
    )

    bootstrap_max_rps: int = Field(default=25, alias="API_STUDIO_BOOTSTRAP_MAX_RPS")
    bootstrap_include_heavy_endpoints: bool = Field(
        default=False, alias="API_STUDIO_BOOTSTRAP_INCLUDE_HEAVY_ENDPOINTS"
    )
    
    # Data retention (days, 0 = disable cleanup)
    webhook_log_retention_days: int = Field(default=90, alias="API_STUDIO_WEBHOOK_LOG_RETENTION_DAYS")
    flow_execution_retention_days: int = Field(default=30, alias="API_STUDIO_FLOW_EXECUTION_RETENTION_DAYS")


settings = Settings()

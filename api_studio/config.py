from pydantic import Field

from clockify_core.config import BaseClockifySettings


class Settings(BaseClockifySettings):
    """API Studio specific settings."""
    
    app_port: int = Field(default=8000, alias="APP_PORT")
    db_url: str = Field(default="sqlite+aiosqlite:///./api_studio.db", alias="API_STUDIO_DB_URL")

    bootstrap_max_rps: int = Field(default=25, alias="API_STUDIO_BOOTSTRAP_MAX_RPS")
    bootstrap_include_heavy_endpoints: bool = Field(
        default=False, alias="API_STUDIO_BOOTSTRAP_INCLUDE_HEAVY_ENDPOINTS"
    )
    
    # Data retention (days, 0 = disable cleanup)
    webhook_log_retention_days: int = Field(default=90, alias="API_STUDIO_WEBHOOK_LOG_RETENTION_DAYS")
    flow_execution_retention_days: int = Field(default=30, alias="API_STUDIO_FLOW_EXECUTION_RETENTION_DAYS")


settings = Settings()

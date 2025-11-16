"""Configuration for Universal Webhook add-on."""
from pydantic import Field

from clockify_core.config import BaseClockifySettings


class Settings(BaseClockifySettings):
    """Universal Webhook specific settings."""
    
    app_port: int = Field(default=8001, alias="UNIVERSAL_WEBHOOK_PORT")
    db_url: str = Field(
        default="sqlite+aiosqlite:///./universal_webhook.db",
        alias="UNIVERSAL_WEBHOOK_DB_URL"
    )
    addon_key: str = Field(default="universal-webhook-api", alias="UNIVERSAL_WEBHOOK_ADDON_KEY")
    require_signature_verification: bool = Field(
        default=True,
        alias="UNIVERSAL_WEBHOOK_REQUIRE_SIGNATURE_VERIFICATION",
    )

    # Bootstrap settings
    bootstrap_max_rps: int = Field(default=25, alias="UW_BOOTSTRAP_MAX_RPS")
    bootstrap_include_heavy_endpoints: bool = Field(
        default=False, alias="UW_BOOTSTRAP_INCLUDE_HEAVY"
    )
    bootstrap_include_time_entries: bool = Field(
        default=False, alias="UW_BOOTSTRAP_INCLUDE_TIME_ENTRIES"
    )
    bootstrap_time_entry_days_back: int = Field(
        default=30, alias="UW_BOOTSTRAP_TIME_ENTRY_DAYS"
    )
    bootstrap_max_pages: int = Field(
        default=200, alias="UW_BOOTSTRAP_MAX_PAGES"
    )

    # Webhook settings
    enable_custom_webhooks: bool = Field(default=True, alias="UW_ENABLE_CUSTOM_WEBHOOKS")
    webhook_log_retention_days: int = Field(default=90, alias="UW_WEBHOOK_LOG_RETENTION_DAYS")

    # Flow settings
    enable_flows: bool = Field(default=True, alias="UW_ENABLE_FLOWS")
    enable_generic_http_actions: bool = Field(
        default=False, alias="UW_ENABLE_GENERIC_HTTP_ACTIONS"
    )
    flow_execution_retention_days: int = Field(
        default=90, alias="UW_FLOW_EXECUTION_RETENTION_DAYS"
    )

    # Data settings
    cache_ttl_days: int = Field(default=7, alias="UW_CACHE_TTL_DAYS")


settings = Settings()

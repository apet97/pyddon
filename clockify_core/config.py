"""Base configuration for Clockify add-ons."""
from pydantic import Field
from pydantic_settings import BaseSettings


class BaseClockifySettings(BaseSettings):
    """Base settings shared across all Clockify add-ons."""
    
    clockify_api_base_url: str = Field(
        default="https://api.clockify.me",
        description="Base URL for Clockify API"
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level"
    )
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8"
    }

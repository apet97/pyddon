"""Re-export ClockifyClient from shared clockify_core package."""
from clockify_core import ClockifyClient, ClockifyClientError

__all__ = ["ClockifyClient", "ClockifyClientError"]

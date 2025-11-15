from fastapi import HTTPException, status
from typing import Optional, Dict, Any


class AddonError(Exception):
    """Base exception for addon-specific errors."""
    
    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(AddonError):
    """Validation error."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details
        )


class AuthenticationError(AddonError):
    """Authentication/authorization error."""
    
    def __init__(self, message: str = "Invalid or missing authentication", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            details=details
        )


class NotFoundError(AddonError):
    """Resource not found error."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            details=details
        )


class RateLimitError(AddonError):
    """Rate limit exceeded error."""
    
    def __init__(self, message: str = "Rate limit exceeded", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details=details
        )


class ExternalAPIError(AddonError):
    """External API call failed."""
    
    def __init__(self, message: str, status_code: int = 500, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=status_code,
            details=details
        )


def addon_error_to_http_exception(error: AddonError) -> HTTPException:
    """Convert AddonError to HTTPException."""
    return HTTPException(
        status_code=error.status_code,
        detail={
            "message": error.message,
            "details": error.details
        }
    )

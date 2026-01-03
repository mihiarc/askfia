"""Centralized exception classes for AskFIA API.

This module provides:
1. Custom exception classes for service-level errors
2. HTTP exception conversion utilities
3. A decorator for consistent error handling in route handlers
"""

from __future__ import annotations

import logging
from functools import wraps
from typing import Any, Callable, TypeVar

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

# Type variable for decorator return type
F = TypeVar("F", bound=Callable[..., Any])


# ============================================================================
# Service Layer Exceptions
# ============================================================================


class FIAServiceError(Exception):
    """Base exception for FIA service errors.

    All service-layer exceptions should inherit from this class.
    """

    pass


class StateNotFoundError(FIAServiceError):
    """Raised when a state's FIA data is not available."""

    def __init__(self, state: str, message: str | None = None):
        self.state = state
        super().__init__(message or f"FIA data not found for state: {state}")


class InvalidQueryError(FIAServiceError):
    """Raised for invalid query parameters."""

    def __init__(self, message: str, field: str | None = None):
        self.field = field
        super().__init__(message)


class DataUnavailableError(FIAServiceError):
    """Raised when required data (e.g., GRM tables) is not available."""

    def __init__(self, message: str, missing_data: list[str] | None = None):
        self.missing_data = missing_data or []
        super().__init__(message)


class QueryExecutionError(FIAServiceError):
    """Raised when a query fails during execution."""

    def __init__(self, message: str, original_error: Exception | None = None):
        self.original_error = original_error
        super().__init__(message)


# ============================================================================
# HTTP Exception Conversion
# ============================================================================


def service_error_to_http(e: FIAServiceError) -> HTTPException:
    """Convert a service exception to an appropriate HTTP exception.

    Args:
        e: The service layer exception.

    Returns:
        An HTTPException with appropriate status code and message.
    """
    if isinstance(e, StateNotFoundError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    if isinstance(e, InvalidQueryError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    if isinstance(e, DataUnavailableError):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        )

    if isinstance(e, QueryExecutionError):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )

    # Default for unknown FIAServiceError subclasses
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=str(e),
    )


# ============================================================================
# Error Handling Decorator
# ============================================================================


def with_error_handling(func: F) -> F:
    """Decorator for consistent error handling in route handlers.

    Catches service layer exceptions and converts them to appropriate
    HTTP responses. Also logs unexpected errors.

    Example:
        >>> @router.post("/area")
        ... @with_error_handling
        ... async def query_area(query: AreaQuery):
        ...     result = await fia_service.query_area(...)
        ...     return AreaResponse(**result)
    """

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return await func(*args, **kwargs)
        except HTTPException:
            # Re-raise HTTP exceptions as-is (validation errors, auth errors, etc.)
            raise
        except FIAServiceError as e:
            # Convert service exceptions to HTTP exceptions
            logger.warning(f"Service error in {func.__name__}: {e}")
            raise service_error_to_http(e)
        except Exception as e:
            # Log and convert unexpected errors
            logger.exception(f"Unexpected error in {func.__name__}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e),
            )

    return wrapper  # type: ignore[return-value]


def with_sync_error_handling(func: F) -> F:
    """Decorator for consistent error handling in synchronous route handlers.

    Same as with_error_handling but for non-async functions.
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except HTTPException:
            raise
        except FIAServiceError as e:
            logger.warning(f"Service error in {func.__name__}: {e}")
            raise service_error_to_http(e)
        except Exception as e:
            logger.exception(f"Unexpected error in {func.__name__}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e),
            )

    return wrapper  # type: ignore[return-value]

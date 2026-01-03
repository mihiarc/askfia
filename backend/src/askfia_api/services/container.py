"""Dependency injection container for services.

This module provides a consistent pattern for service instantiation and
dependency injection across the application, replacing the inconsistent
patterns previously used (module singletons, double-checked locking, etc.).
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any, Callable, TypeVar

if TYPE_CHECKING:
    from .fia_service import FIAService
    from .gridfia_service import GridFIAService
    from .user_service import UserService

T = TypeVar("T")


class ServiceContainer:
    """Thread-safe service container with lazy initialization.

    Provides a centralized registry for service singletons. Services are
    created on first access and cached for subsequent requests.

    Thread safety is ensured via double-checked locking pattern.

    Example:
        >>> fia = ServiceContainer.get(FIAService)
        >>> # Same instance on subsequent calls
        >>> fia2 = ServiceContainer.get(FIAService)
        >>> assert fia is fia2

        >>> # For testing, reset all services
        >>> ServiceContainer.reset()
    """

    _instances: dict[type, Any] = {}
    _locks: dict[type, threading.Lock] = {}
    _global_lock = threading.Lock()

    @classmethod
    def get(cls, service_type: type[T], factory: Callable[[], T] | None = None) -> T:
        """Get or create a service instance.

        Uses double-checked locking for thread safety with minimal contention.

        Args:
            service_type: The service class to instantiate.
            factory: Optional factory function. If not provided, the service
                    class is instantiated with no arguments.

        Returns:
            The singleton instance of the service.
        """
        # Fast path: instance already exists
        if service_type in cls._instances:
            return cls._instances[service_type]

        # Slow path: need to create instance
        # First, ensure we have a lock for this service type
        with cls._global_lock:
            if service_type not in cls._locks:
                cls._locks[service_type] = threading.Lock()
            service_lock = cls._locks[service_type]

        # Now acquire the service-specific lock
        with service_lock:
            # Double-check after acquiring lock
            if service_type not in cls._instances:
                if factory is not None:
                    cls._instances[service_type] = factory()
                else:
                    cls._instances[service_type] = service_type()

        return cls._instances[service_type]

    @classmethod
    def set(cls, service_type: type[T], instance: T) -> None:
        """Set a service instance directly.

        Useful for testing with mock services.

        Args:
            service_type: The service class.
            instance: The instance to use.
        """
        with cls._global_lock:
            cls._instances[service_type] = instance

    @classmethod
    def reset(cls, service_type: type | None = None) -> None:
        """Reset service instance(s).

        Args:
            service_type: Specific service to reset, or None to reset all.
        """
        with cls._global_lock:
            if service_type is not None:
                cls._instances.pop(service_type, None)
            else:
                cls._instances.clear()

    @classmethod
    def is_initialized(cls, service_type: type) -> bool:
        """Check if a service has been initialized.

        Args:
            service_type: The service class to check.

        Returns:
            True if the service has been instantiated.
        """
        return service_type in cls._instances


# ============================================================================
# FastAPI Dependencies
# ============================================================================


def get_fia_service() -> "FIAService":
    """FastAPI dependency for FIAService.

    Usage:
        >>> @router.post("/area")
        ... async def query_area(
        ...     query: AreaQuery,
        ...     service: FIAService = Depends(get_fia_service)
        ... ):
        ...     return await service.query_area(...)
    """
    from .fia_service import FIAService

    return ServiceContainer.get(FIAService)


def get_user_service() -> "UserService":
    """FastAPI dependency for UserService.

    Note: UserService requires configuration, so we use a factory.
    """
    from ..config import get_settings
    from .user_service import UserService

    def factory() -> UserService:
        settings = get_settings()
        return UserService(
            db_path=settings.user_db_path,
            daily_limit=settings.daily_query_limit,
        )

    return ServiceContainer.get(UserService, factory)


def get_gridfia_service() -> "GridFIAService":
    """FastAPI dependency for GridFIAService."""
    from .gridfia_service import GridFIAService

    return ServiceContainer.get(GridFIAService)

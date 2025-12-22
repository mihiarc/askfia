"""Authentication for pyFIA API."""

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from .config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str | None = Security(api_key_header)) -> str:
    """Verify API key if authentication is enabled.

    If API_KEY is not set in environment, authentication is disabled.
    """
    # If no API key configured, allow all requests (dev mode)
    if not settings.api_key:
        return "no-auth"

    # API key is required
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Include X-API-Key header.",
        )

    if api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key.",
        )

    return api_key


# Dependency for protected routes
require_auth = Depends(verify_api_key)

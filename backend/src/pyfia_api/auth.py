"""Authentication dependency for pyFIA API.

Uses JWT tokens stored in HTTP-only cookies for authentication.
"""

from fastapi import Cookie, Depends, HTTPException, status

from .config import get_settings


async def verify_auth(
    access_token: str | None = Cookie(default=None),
) -> None:
    """Verify authentication via JWT cookie.

    If AUTH_PASSWORD_HASH and AUTH_JWT_SECRET are not set in environment,
    authentication is disabled and all requests are allowed.

    Args:
        access_token: JWT access token from cookie

    Raises:
        HTTPException: 401 if not authenticated
    """
    # Import here to avoid circular imports
    from .api.routes.auth import verify_token

    settings = get_settings()

    # Skip auth check if authentication is disabled
    if not settings.auth_enabled:
        return

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    if not verify_token(access_token, "access"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


# Dependency for protected routes
require_auth = Depends(verify_auth)

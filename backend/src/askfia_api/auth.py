"""Authentication dependency for pyFIA API.

Uses JWT tokens stored in HTTP-only cookies for authentication.
"""

from fastapi import Cookie, Depends, HTTPException, status

from .config import get_settings


async def get_current_user_email(
    access_token: str | None = Cookie(default=None),
) -> str | None:
    """Extract user email from JWT cookie.

    Returns the authenticated user's email, or None if:
    - Authentication is disabled
    - No token is present
    - Token is invalid

    This is a non-raising dependency for use when you need the user's
    identity but don't want to block unauthenticated requests.

    Args:
        access_token: JWT access token from cookie

    Returns:
        User email string or None
    """
    from .api.routes.auth import decode_token, verify_token

    settings = get_settings()

    # Return None if auth disabled - can't track users
    if not settings.auth_enabled:
        return None

    if not access_token:
        return None

    # Verify token is valid before decoding
    if not verify_token(access_token, "access"):
        return None

    # Extract email from token payload
    payload = decode_token(access_token)
    if payload:
        return payload.get("email")

    return None


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

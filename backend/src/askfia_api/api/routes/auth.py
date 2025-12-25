"""Authentication endpoints with JWT cookie-based tokens."""

import logging
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from fastapi import APIRouter, Cookie, Response
from pydantic import BaseModel

from askfia_api.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


# --- Request/Response Models ---


class LoginRequest(BaseModel):
    """Login request with password."""

    password: str


class AuthResponse(BaseModel):
    """Authentication response."""

    authenticated: bool
    message: str


# --- Token Functions ---


def create_token(token_type: str, expires_delta: timedelta) -> str:
    """Create a JWT token.

    Args:
        token_type: Either "access" or "refresh"
        expires_delta: Token validity duration

    Returns:
        Encoded JWT token string
    """
    settings = get_settings()
    expire = datetime.now(UTC) + expires_delta
    payload = {
        "type": token_type,
        "exp": expire,
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, settings.auth_jwt_secret, algorithm="HS256")


def verify_token(token: str, token_type: str) -> bool:
    """Verify a JWT token.

    Args:
        token: The JWT token to verify
        token_type: Expected token type ("access" or "refresh")

    Returns:
        True if token is valid, False otherwise
    """
    settings = get_settings()
    if not settings.auth_jwt_secret:
        return False

    try:
        payload = jwt.decode(token, settings.auth_jwt_secret, algorithms=["HS256"])
        return payload.get("type") == token_type
    except jwt.ExpiredSignatureError:
        logger.debug("Token expired")
        return False
    except jwt.InvalidTokenError as e:
        logger.debug(f"Invalid token: {e}")
        return False


def set_auth_cookies(response: Response) -> None:
    """Set authentication cookies on response.

    Creates both access and refresh tokens and sets them as HTTP-only cookies.
    """
    settings = get_settings()

    access_token = create_token(
        "access",
        timedelta(seconds=settings.auth_access_token_expire),
    )
    refresh_token = create_token(
        "refresh",
        timedelta(seconds=settings.auth_refresh_token_expire),
    )

    # Access token cookie - available to all paths
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
        max_age=settings.auth_access_token_expire,
    )

    # Refresh token cookie - only available to auth endpoints
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="none",
        path="/api/v1/auth",
        max_age=settings.auth_refresh_token_expire,
    )


def clear_auth_cookies(response: Response) -> None:
    """Clear authentication cookies."""
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path="/api/v1/auth")


# --- Endpoints ---


@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest, response: Response) -> AuthResponse:
    """Authenticate with password and receive JWT tokens in cookies."""
    settings = get_settings()

    if not settings.auth_enabled:
        return AuthResponse(
            authenticated=True,
            message="Authentication disabled",
        )

    # Verify password using bcrypt
    password_bytes = request.password.encode("utf-8")
    hash_bytes = settings.auth_password_hash.encode("utf-8")

    if not bcrypt.checkpw(password_bytes, hash_bytes):
        logger.warning("Failed login attempt")
        return AuthResponse(
            authenticated=False,
            message="Invalid password",
        )

    # Set auth cookies
    set_auth_cookies(response)

    logger.info("Successful login")
    return AuthResponse(
        authenticated=True,
        message="Login successful",
    )


@router.post("/logout", response_model=AuthResponse)
async def logout(response: Response) -> AuthResponse:
    """Clear authentication tokens."""
    clear_auth_cookies(response)
    return AuthResponse(
        authenticated=False,
        message="Logged out successfully",
    )


@router.post("/refresh", response_model=AuthResponse)
async def refresh(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
) -> AuthResponse:
    """Refresh access token using refresh token."""
    settings = get_settings()

    if not settings.auth_enabled:
        return AuthResponse(
            authenticated=True,
            message="Authentication disabled",
        )

    if not refresh_token:
        return AuthResponse(
            authenticated=False,
            message="No refresh token",
        )

    if not verify_token(refresh_token, "refresh"):
        clear_auth_cookies(response)
        return AuthResponse(
            authenticated=False,
            message="Invalid refresh token",
        )

    # Issue new tokens
    set_auth_cookies(response)

    return AuthResponse(
        authenticated=True,
        message="Token refreshed",
    )


@router.get("/verify", response_model=AuthResponse)
async def verify(
    access_token: str | None = Cookie(default=None),
) -> AuthResponse:
    """Verify if current session is authenticated."""
    settings = get_settings()

    if not settings.auth_enabled:
        return AuthResponse(
            authenticated=True,
            message="Authentication disabled",
        )

    if not access_token:
        return AuthResponse(
            authenticated=False,
            message="Not authenticated",
        )

    if verify_token(access_token, "access"):
        return AuthResponse(
            authenticated=True,
            message="Authenticated",
        )

    return AuthResponse(
        authenticated=False,
        message="Invalid or expired token",
    )

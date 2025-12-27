"""Authentication endpoints with JWT cookie-based tokens."""

import logging
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from fastapi import APIRouter, Cookie, Response
from pydantic import BaseModel, EmailStr

from askfia_api.config import get_settings
from askfia_api.services.email_storage import (
    register_user,
    validate_email,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


# --- Request/Response Models ---


class LoginRequest(BaseModel):
    """Login request with password (legacy)."""

    password: str


class EmailSignupRequest(BaseModel):
    """Email signup request."""

    email: EmailStr


class AuthResponse(BaseModel):
    """Authentication response."""

    authenticated: bool
    message: str
    email: str | None = None
    is_new_user: bool | None = None


# --- Token Functions ---


def create_token(
    token_type: str,
    expires_delta: timedelta,
    email: str | None = None,
    user_id: str | None = None,
) -> str:
    """Create a JWT token.

    Args:
        token_type: Either "access" or "refresh"
        expires_delta: Token validity duration
        email: Optional user email to include in token
        user_id: Optional user ID to include in token

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
    if email:
        payload["email"] = email
    if user_id:
        payload["sub"] = user_id
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


def decode_token(token: str) -> dict | None:
    """Decode a JWT token and return the payload.

    Args:
        token: The JWT token to decode

    Returns:
        Token payload dict or None if invalid
    """
    settings = get_settings()
    if not settings.auth_jwt_secret:
        return None

    try:
        return jwt.decode(token, settings.auth_jwt_secret, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return None


def set_auth_cookies(
    response: Response,
    email: str | None = None,
    user_id: str | None = None,
) -> None:
    """Set authentication cookies on response.

    Creates both access and refresh tokens and sets them as HTTP-only cookies.

    Args:
        response: FastAPI Response object
        email: Optional user email to include in tokens
        user_id: Optional user ID to include in tokens
    """
    settings = get_settings()

    access_token = create_token(
        "access",
        timedelta(seconds=settings.auth_access_token_expire),
        email=email,
        user_id=user_id,
    )
    refresh_token = create_token(
        "refresh",
        timedelta(seconds=settings.auth_refresh_token_expire),
        email=email,
        user_id=user_id,
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


@router.post("/signup", response_model=AuthResponse)
async def signup(request: EmailSignupRequest, response: Response) -> AuthResponse:
    """Register or login with email address.

    This endpoint:
    - Validates email format
    - Creates a new user or returns existing user
    - Issues JWT tokens with email in payload
    """
    email = request.email.lower().strip()

    # Validate email format
    if not validate_email(email):
        return AuthResponse(
            authenticated=False,
            message="Invalid email format",
        )

    try:
        # Register user (or get existing)
        user, is_new = register_user(email)

        # Set auth cookies with email info
        set_auth_cookies(response, email=user["email"], user_id=user["id"])

        if is_new:
            logger.info(f"New user registered: {email}")
            return AuthResponse(
                authenticated=True,
                message="Welcome! Your account has been created.",
                email=user["email"],
                is_new_user=True,
            )
        else:
            logger.info(f"Existing user logged in: {email}")
            return AuthResponse(
                authenticated=True,
                message="Welcome back!",
                email=user["email"],
                is_new_user=False,
            )

    except ValueError as e:
        logger.warning(f"Email validation failed: {e}")
        return AuthResponse(
            authenticated=False,
            message=str(e),
        )
    except Exception as e:
        logger.error(f"Signup error: {e}")
        return AuthResponse(
            authenticated=False,
            message="An error occurred. Please try again.",
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
        # Decode token to get email
        payload = decode_token(access_token)
        email = payload.get("email") if payload else None
        return AuthResponse(
            authenticated=True,
            message="Authenticated",
            email=email,
        )

    return AuthResponse(
        authenticated=False,
        message="Invalid or expired token",
    )

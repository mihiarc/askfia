"""Email storage service for user registration."""

import json
import logging
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict

from askfia_api.config import get_settings

logger = logging.getLogger(__name__)


class UserRecord(TypedDict):
    """User registration record."""

    id: str
    email: str
    created_at: str
    last_login: str | None


# Email validation regex (RFC 5322 simplified)
EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
)


def _get_users_file() -> Path:
    """Get path to users JSON file."""
    settings = get_settings()
    data_dir = Path(settings.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "users.json"


def _load_users() -> dict[str, UserRecord]:
    """Load users from JSON file."""
    users_file = _get_users_file()
    if not users_file.exists():
        return {}

    try:
        with open(users_file) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Failed to load users file: {e}")
        return {}


def _save_users(users: dict[str, UserRecord]) -> None:
    """Save users to JSON file."""
    users_file = _get_users_file()
    try:
        with open(users_file, "w") as f:
            json.dump(users, f, indent=2)
    except OSError as e:
        logger.error(f"Failed to save users file: {e}")
        raise


def validate_email(email: str) -> bool:
    """Validate email format.

    Args:
        email: Email address to validate

    Returns:
        True if email format is valid
    """
    if not email or len(email) > 254:
        return False
    return bool(EMAIL_REGEX.match(email.lower()))


def normalize_email(email: str) -> str:
    """Normalize email to lowercase."""
    return email.lower().strip()


def register_user(email: str) -> tuple[UserRecord, bool]:
    """Register a new user or return existing user.

    Args:
        email: User's email address

    Returns:
        Tuple of (user_record, is_new_user)

    Raises:
        ValueError: If email format is invalid
    """
    email = normalize_email(email)

    if not validate_email(email):
        raise ValueError("Invalid email format")

    users = _load_users()

    # Check if user already exists
    if email in users:
        # Update last login
        users[email]["last_login"] = datetime.now(UTC).isoformat()
        _save_users(users)
        logger.info(f"Existing user logged in: {email}")
        return users[email], False

    # Create new user
    user: UserRecord = {
        "id": str(uuid.uuid4()),
        "email": email,
        "created_at": datetime.now(UTC).isoformat(),
        "last_login": datetime.now(UTC).isoformat(),
    }

    users[email] = user
    _save_users(users)
    logger.info(f"New user registered: {email}")
    return user, True


def get_user(email: str) -> UserRecord | None:
    """Get user by email.

    Args:
        email: User's email address

    Returns:
        User record or None if not found
    """
    email = normalize_email(email)
    users = _load_users()
    return users.get(email)


def get_all_users() -> list[UserRecord]:
    """Get all registered users.

    Returns:
        List of all user records
    """
    users = _load_users()
    return list(users.values())


def get_user_count() -> int:
    """Get total number of registered users."""
    return len(_load_users())

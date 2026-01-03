"""Centralized security validation for AskFIA API.

This module consolidates security-related validation that was previously
duplicated across models/schemas.py and services/agent.py.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

# ============================================================================
# Valid State Codes
# ============================================================================

# Valid US state codes (50 states + DC + territories)
VALID_STATE_CODES: frozenset[str] = frozenset({
    # 50 States
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    # District of Columbia
    "DC",
    # US Territories (FIA has some data)
    "PR", "VI", "GU", "AS", "MP",
})

# ============================================================================
# SQL Injection Prevention
# ============================================================================

# Dangerous SQL patterns that could indicate injection attempts
# Using word boundaries (\b) to avoid false positives (e.g., "UPDATED_DATE" is OK)
DANGEROUS_SQL_PATTERNS: tuple[str, ...] = (
    r"\bDROP\b",
    r"\bDELETE\b",
    r"\bINSERT\b",
    r"\bUPDATE\b",
    r"\bALTER\b",
    r"\bCREATE\b",
    r"\bEXEC\b",
    r"\bEXECUTE\b",
    r"\bTRUNCATE\b",
    r"\bUNION\b",
    r"\bSELECT\b",
    r"--",      # SQL comment
    r"/\*",    # SQL block comment start
    r"\*/",    # SQL block comment end
    r";",      # Statement terminator
)

# Pre-compile patterns for performance
_COMPILED_PATTERNS: list[tuple[re.Pattern[str], str, bool]] = [
    (
        re.compile(pattern, re.IGNORECASE if pattern.startswith(r"\b") else 0),
        pattern.replace(r"\b", "").replace("\\", ""),
        pattern.startswith(r"\b"),
    )
    for pattern in DANGEROUS_SQL_PATTERNS
]


# ============================================================================
# Validation Functions
# ============================================================================


def validate_state_codes(states: list[str]) -> list[str]:
    """Validate and normalize state codes.

    Args:
        states: List of state codes to validate.

    Returns:
        List of validated, uppercase state codes.

    Raises:
        ValueError: If the list is empty or contains invalid state codes.

    Examples:
        >>> validate_state_codes(["nc", "GA"])
        ['NC', 'GA']
        >>> validate_state_codes(["XX"])  # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
        ValueError: Invalid state code(s): XX. ...
    """
    if not states:
        raise ValueError("At least one state code is required")

    normalized: list[str] = []
    invalid: list[str] = []

    for state in states:
        code = state.strip().upper()
        if code in VALID_STATE_CODES:
            normalized.append(code)
        else:
            invalid.append(state)

    if invalid:
        raise ValueError(
            f"Invalid state code(s): {', '.join(invalid)}. "
            f"Must be valid 2-letter US state abbreviations (e.g., NC, GA, CA)."
        )

    return normalized


def validate_domain_expression(
    domain: str | None,
    domain_type: str = "domain",
) -> str | None:
    """Validate domain expression to prevent SQL injection.

    This validates filter expressions like 'DIA >= 10.0' to ensure they don't
    contain SQL injection attempts.

    Args:
        domain: The domain expression to validate.
        domain_type: Description for error messages (e.g., "tree_domain").

    Returns:
        The validated domain string, or None if input is None.

    Raises:
        TypeError: If domain is not a string.
        ValueError: If domain is empty or contains dangerous SQL patterns.

    Examples:
        >>> validate_domain_expression("DIA >= 10.0")
        'DIA >= 10.0'
        >>> validate_domain_expression("STATUSCD == 1", "tree_domain")
        'STATUSCD == 1'
        >>> validate_domain_expression(None)  # Returns None
        >>> validate_domain_expression("DROP TABLE--")  # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
        ValueError: domain contains potentially dangerous SQL pattern: ...
    """
    if domain is None:
        return None

    if not isinstance(domain, str):
        raise TypeError(
            f"{domain_type} must be a string, got {type(domain).__name__}"
        )

    stripped = domain.strip()
    if stripped == "":
        raise ValueError(f"{domain_type} cannot be an empty string")

    # Check for dangerous SQL patterns
    for compiled, keyword, use_upper in _COMPILED_PATTERNS:
        search_text = domain.upper() if use_upper else domain
        if compiled.search(search_text):
            raise ValueError(
                f"{domain_type} contains potentially dangerous SQL pattern: '{keyword}'. "
                f"Only simple filter expressions like 'DIA >= 10.0' are allowed."
            )

    return domain


def is_valid_state_code(state: str) -> bool:
    """Check if a state code is valid.

    Args:
        state: State code to check.

    Returns:
        True if valid, False otherwise.

    Examples:
        >>> is_valid_state_code("NC")
        True
        >>> is_valid_state_code("XX")
        False
    """
    return state.strip().upper() in VALID_STATE_CODES

"""Base Pydantic models with common validation logic.

This module provides base classes that consolidate duplicate validation
patterns across query schemas.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from ..security import validate_domain_expression, validate_state_codes


class StateValidatedModel(BaseModel):
    """Base model with automatic state code validation.

    All models that require state code validation should inherit from this class.
    The states field will automatically be validated and normalized to uppercase.

    Example:
        >>> class MyQuery(StateValidatedModel):
        ...     land_type: str = "forest"
        >>> q = MyQuery(states=["nc", "ga"])
        >>> q.states
        ['NC', 'GA']
    """

    states: list[str] = Field(
        ...,
        description="List of two-letter US state codes",
        examples=[["NC", "GA", "SC"]],
    )

    @field_validator("states")
    @classmethod
    def validate_states(cls, v: list[str]) -> list[str]:
        """Validate and normalize state codes."""
        return validate_state_codes(v)


class DomainValidatedModel(StateValidatedModel):
    """Base model with state and domain expression validation.

    Extends StateValidatedModel to add tree_domain and cond_domain validation.
    Domain expressions are validated to prevent SQL injection.

    Example:
        >>> class VolumeQuery(DomainValidatedModel):
        ...     by_species: bool = False
        >>> q = VolumeQuery(states=["NC"], tree_domain="DIA >= 10.0")
        >>> q.tree_domain
        'DIA >= 10.0'
    """

    tree_domain: str | None = Field(
        default=None,
        description="Tree-level filter expression (e.g., 'DIA >= 10.0')",
    )
    cond_domain: str | None = Field(
        default=None,
        description="Condition-level filter expression (e.g., 'FORTYPCD == 141')",
    )

    @field_validator("tree_domain", mode="before")
    @classmethod
    def validate_tree_domain(cls, v: str | None) -> str | None:
        """Validate tree_domain expression for SQL injection."""
        return validate_domain_expression(v, "tree_domain")

    @field_validator("cond_domain", mode="before")
    @classmethod
    def validate_cond_domain(cls, v: str | None) -> str | None:
        """Validate cond_domain expression for SQL injection."""
        return validate_domain_expression(v, "cond_domain")

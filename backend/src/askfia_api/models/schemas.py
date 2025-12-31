"""Pydantic schemas for API requests and responses."""

import re
from pydantic import BaseModel, Field, field_validator
from typing import Literal


# ============================================================================
# Security Validation
# ============================================================================

# Valid US state codes (50 states + DC + territories)
VALID_STATE_CODES = {
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
}


def validate_state_codes(states: list[str]) -> list[str]:
    """
    Validate and normalize state codes.

    Args:
        states: List of state codes to validate

    Returns:
        List of validated, uppercase state codes

    Raises:
        ValueError: If any state code is invalid
    """
    if not states:
        raise ValueError("At least one state code is required")

    normalized = []
    invalid = []

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


def validate_domain_expression(domain: str | None, domain_type: str = "tree_domain") -> str | None:
    """
    Validate domain expression to prevent SQL injection.

    This validates filter expressions like 'DIA >= 10.0' to ensure they don't
    contain SQL injection attempts.

    Args:
        domain: The domain expression to validate
        domain_type: Description for error messages

    Returns:
        The validated domain string, or None

    Raises:
        ValueError: If the domain contains dangerous SQL patterns
    """
    if domain is None:
        return None

    if not isinstance(domain, str):
        raise TypeError(f"{domain_type} must be a string, got {type(domain).__name__}")

    # Basic sanity checks
    if domain.strip() == "":
        raise ValueError(f"{domain_type} cannot be an empty string")

    # Check for dangerous SQL patterns with word boundaries
    # Using word boundaries to avoid false positives (e.g., "UPDATED_DATE" is OK)
    dangerous_patterns = [
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
        r"--",  # SQL comment
        r"/\*",  # SQL block comment start
        r"\*/",  # SQL block comment end
        r";",    # Statement terminator
    ]

    domain_upper = domain.upper()
    for pattern in dangerous_patterns:
        if re.search(pattern, domain_upper if pattern.startswith(r"\b") else domain):
            # Extract the keyword for the error message
            keyword = pattern.replace(r"\b", "").replace("\\", "")
            raise ValueError(
                f"{domain_type} contains potentially dangerous SQL pattern: '{keyword}'. "
                f"Only simple filter expressions like 'DIA >= 10.0' are allowed."
            )

    return domain


# ============================================================================
# Chat Models
# ============================================================================


class ChatMessage(BaseModel):
    """A single chat message."""

    role: Literal["user", "assistant", "system"]
    content: str


class ChatRequest(BaseModel):
    """Request body for chat endpoint."""

    messages: list[ChatMessage]


# ============================================================================
# Query Models
# ============================================================================


class AreaQuery(BaseModel):
    """Request for forest area query."""

    states: list[str] = Field(
        ..., description="List of two-letter state codes", examples=[["NC", "GA", "SC"]]
    )
    land_type: Literal["forest", "timber", "reserved", "productive"] = Field(
        default="forest", description="Land classification filter"
    )
    grp_by: str | None = Field(
        default=None,
        description="Column to group by (e.g., OWNGRPCD, FORTYPCD)",
    )

    @field_validator("states")
    @classmethod
    def validate_states(cls, v: list[str]) -> list[str]:
        return validate_state_codes(v)


class VolumeQuery(BaseModel):
    """Request for timber volume query."""

    states: list[str] = Field(..., description="List of two-letter state codes")
    by_species: bool = Field(default=False, description="Group results by species")
    tree_domain: str | None = Field(
        default=None,
        description="Filter expression (e.g., 'DIA >= 10.0')",
    )

    @field_validator("states")
    @classmethod
    def validate_states(cls, v: list[str]) -> list[str]:
        return validate_state_codes(v)

    @field_validator("tree_domain")
    @classmethod
    def validate_tree_domain(cls, v: str | None) -> str | None:
        """Validate tree_domain to prevent SQL injection."""
        return validate_domain_expression(v, "tree_domain")


class BiomassQuery(BaseModel):
    """Request for biomass/carbon query."""

    states: list[str] = Field(..., description="List of two-letter state codes")
    land_type: Literal["forest", "timber"] = Field(
        default="forest", description="Land classification"
    )
    by_species: bool = Field(default=False, description="Group by species")

    @field_validator("states")
    @classmethod
    def validate_states(cls, v: list[str]) -> list[str]:
        return validate_state_codes(v)


class TPAQuery(BaseModel):
    """Request for trees per acre query."""

    states: list[str] = Field(..., description="List of two-letter state codes")
    tree_domain: str = Field(
        default="STATUSCD == 1", description="Tree filter (1=live, 2=dead)"
    )
    by_species: bool = Field(default=False, description="Group by species")

    @field_validator("states")
    @classmethod
    def validate_states(cls, v: list[str]) -> list[str]:
        return validate_state_codes(v)

    @field_validator("tree_domain")
    @classmethod
    def validate_tree_domain(cls, v: str) -> str:
        """Validate tree_domain to prevent SQL injection."""
        result = validate_domain_expression(v, "tree_domain")
        return result if result is not None else "STATUSCD == 1"


class CompareQuery(BaseModel):
    """Request for state comparison."""

    states: list[str] = Field(
        ..., description="States to compare (2-10)", min_length=2, max_length=10
    )
    metric: Literal["area", "volume", "biomass", "tpa", "mortality", "growth"] = Field(
        ..., description="Metric to compare"
    )
    land_type: Literal["forest", "timber"] = Field(
        default="forest", description="Land type filter"
    )

    @field_validator("states")
    @classmethod
    def validate_states(cls, v: list[str]) -> list[str]:
        return validate_state_codes(v)


# ============================================================================
# Response Models
# ============================================================================


class QueryResponse(BaseModel):
    """Generic query response."""

    states: list[str]
    source: str = "USDA Forest Service FIA (pyFIA validated)"


class AreaResponse(QueryResponse):
    """Response for area query."""

    land_type: str
    total_area_acres: float
    se_percent: float
    breakdown: list[dict] | None = None


class VolumeResponse(QueryResponse):
    """Response for volume query."""

    total_volume_cuft: float
    total_volume_billion_cuft: float
    se_percent: float
    by_species: list[dict] | None = None


class BiomassResponse(QueryResponse):
    """Response for biomass query."""

    land_type: str
    total_biomass_tons: float
    carbon_mmt: float
    se_percent: float
    by_species: list[dict] | None = None


class StateComparison(BaseModel):
    """Single state in comparison."""

    state: str
    estimate: float | None
    se_percent: float | None
    error: str | None = None


class CompareResponse(BaseModel):
    """Response for state comparison."""

    metric: str
    states: list[StateComparison]
    source: str = "USDA Forest Service FIA (pyFIA validated)"


# ============================================================================
# Download Models
# ============================================================================


class DownloadRequest(BaseModel):
    """Request to prepare data download."""

    states: list[str] = Field(..., description="States to include")
    tables: list[str] = Field(
        default=["PLOT", "COND", "TREE"], description="FIA tables to include"
    )
    format: Literal["duckdb", "parquet", "csv"] = Field(
        default="parquet", description="Output format"
    )

    @field_validator("states")
    @classmethod
    def validate_states(cls, v: list[str]) -> list[str]:
        return validate_state_codes(v)


class DownloadResponse(BaseModel):
    """Response with download information."""

    download_id: str
    states: list[str]
    tables: list[str]
    format: str
    estimated_size_mb: float
    download_url: str
    expires_in_hours: int = 24

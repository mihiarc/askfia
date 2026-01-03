"""Pydantic schemas for API requests and responses."""

from pydantic import BaseModel, Field, field_validator
from typing import Literal

# Import validation functions from centralized security module
from ..security import validate_domain_expression, validate_state_codes, VALID_STATE_CODES

# Import base classes for schema inheritance
from .base import DomainValidatedModel, StateValidatedModel


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


class AreaQuery(StateValidatedModel):
    """Request for forest area query."""

    land_type: Literal["forest", "timber", "reserved", "productive"] = Field(
        default="forest", description="Land classification filter"
    )
    grp_by: str | None = Field(
        default=None,
        description="Column to group by (e.g., OWNGRPCD, FORTYPCD)",
    )
    cond_domain: str | None = Field(
        default=None,
        description="Condition-level filter expression (e.g., 'FORTYPCD == 141')",
    )

    @field_validator("cond_domain", mode="before")
    @classmethod
    def validate_cond_domain(cls, v: str | None) -> str | None:
        """Validate cond_domain to prevent SQL injection."""
        return validate_domain_expression(v, "cond_domain")


class VolumeQuery(DomainValidatedModel):
    """Request for timber volume query."""

    by_species: bool = Field(default=False, description="Group results by species")


class BiomassQuery(StateValidatedModel):
    """Request for biomass/carbon query."""

    land_type: Literal["forest", "timber"] = Field(
        default="forest", description="Land classification"
    )
    by_species: bool = Field(default=False, description="Group by species")


class TPAQuery(StateValidatedModel):
    """Request for trees per acre query."""

    tree_domain: str = Field(
        default="STATUSCD == 1", description="Tree filter (1=live, 2=dead)"
    )
    by_species: bool = Field(default=False, description="Group by species")

    @field_validator("tree_domain", mode="before")
    @classmethod
    def validate_tree_domain(cls, v: str | None) -> str:
        """Validate tree_domain to prevent SQL injection."""
        if v is None:
            return "STATUSCD == 1"
        result = validate_domain_expression(v, "tree_domain")
        return result if result is not None else "STATUSCD == 1"


class CompareQuery(StateValidatedModel):
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


class TPAResponse(QueryResponse):
    """Response for trees per acre query."""

    tree_domain: str
    total_tpa: float
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


class DownloadRequest(StateValidatedModel):
    """Request to prepare data download."""

    tables: list[str] = Field(
        default=["PLOT", "COND", "TREE"], description="FIA tables to include"
    )
    format: Literal["duckdb", "parquet", "csv"] = Field(
        default="parquet", description="Output format"
    )


class DownloadResponse(BaseModel):
    """Response with download information."""

    download_id: str
    states: list[str]
    tables: list[str]
    format: str
    estimated_size_mb: float
    download_url: str
    expires_in_hours: int = 24

"""Pydantic schemas for API requests and responses."""

from pydantic import BaseModel, Field
from typing import Literal


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


class VolumeQuery(BaseModel):
    """Request for timber volume query."""

    states: list[str] = Field(..., description="List of two-letter state codes")
    by_species: bool = Field(default=False, description="Group results by species")
    tree_domain: str | None = Field(
        default=None,
        description="Filter expression (e.g., 'DIA >= 10.0')",
    )


class BiomassQuery(BaseModel):
    """Request for biomass/carbon query."""

    states: list[str] = Field(..., description="List of two-letter state codes")
    land_type: Literal["forest", "timber"] = Field(
        default="forest", description="Land classification"
    )
    by_species: bool = Field(default=False, description="Group by species")


class TPAQuery(BaseModel):
    """Request for trees per acre query."""

    states: list[str] = Field(..., description="List of two-letter state codes")
    tree_domain: str = Field(
        default="STATUSCD == 1", description="Tree filter (1=live, 2=dead)"
    )
    by_species: bool = Field(default=False, description="Group by species")


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


class DownloadResponse(BaseModel):
    """Response with download information."""

    download_id: str
    states: list[str]
    tables: list[str]
    format: str
    estimated_size_mb: float
    download_url: str
    expires_in_hours: int = 24

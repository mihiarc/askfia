"""LangChain tools for GridFIA spatial analysis.

This module defines LangChain tools that wrap GridFIA functionality,
enabling natural language queries about species diversity, biomass,
and other spatial forest metrics.

These tools are conditionally registered with the FIAAgent when
GridFIA is installed.
"""

import logging

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from .gridfia_service import GRIDFIA_AVAILABLE, get_gridfia_service

logger = logging.getLogger(__name__)


# =============================================================================
# Input Schemas (Pydantic Models)
# =============================================================================


class SpeciesListInput(BaseModel):
    """Input for listing available species."""

    filter_text: str | None = Field(
        default=None,
        description=(
            "Optional text to filter species by common or scientific name. "
            "For example, 'pine' will return all pine species."
        ),
    )
    limit: int = Field(
        default=20,
        description="Maximum number of species to return. Default 20, max 50.",
    )


class SpeciesDiversityInput(BaseModel):
    """Input for species diversity query."""

    state: str = Field(
        description=(
            "State name or two-letter abbreviation (e.g., 'NC', 'North Carolina', 'California')"
        ),
    )
    county: str | None = Field(
        default=None,
        description=(
            "County name for finer resolution analysis (e.g., 'Wake', 'Wake County'). "
            "If not provided, analyzes the entire state."
        ),
    )
    metric: str = Field(
        default="shannon",
        description=(
            "Diversity metric to calculate. Options: "
            "'shannon' (Shannon diversity index H'), "
            "'simpson' (Simpson diversity index), "
            "'richness' (count of unique species per pixel)"
        ),
    )


class GridFIABiomassInput(BaseModel):
    """Input for GridFIA biomass query."""

    state: str = Field(
        description=(
            "State name or two-letter abbreviation (e.g., 'NC', 'North Carolina')"
        ),
    )
    county: str | None = Field(
        default=None,
        description=(
            "County name for finer resolution (e.g., 'Durham', 'Durham County'). "
            "If not provided, analyzes the entire state."
        ),
    )


# =============================================================================
# Tool Functions
# =============================================================================


@tool(args_schema=SpeciesListInput)
async def query_gridfia_species_list(
    filter_text: str | None = None,
    limit: int = 20,
) -> str:
    """
    List available tree species from BIGMAP 2018 raster data.

    Use for questions about:
    - What tree species are available in GridFIA/BIGMAP data
    - Looking up species codes for specific trees
    - Finding species by common or scientific name
    - Understanding what species can be analyzed spatially
    """
    if not GRIDFIA_AVAILABLE:
        return "GridFIA is not installed. Spatial analysis tools are unavailable."

    try:
        service = get_gridfia_service()
        species_list = await service.list_species()

        # Apply filter if provided
        if filter_text:
            filter_lower = filter_text.lower()
            species_list = [
                s
                for s in species_list
                if filter_lower in s["common_name"].lower()
                or filter_lower in s["scientific_name"].lower()
            ]

        # Limit results
        limit = min(limit, 50)
        total_count = len(species_list)
        species_list = species_list[:limit]

        # Format response
        response = "**Available Tree Species (BIGMAP 2018)**\n\n"

        if filter_text:
            response += f"Filter: '{filter_text}'\n"
            response += f"Found: {total_count} matching species\n\n"
        else:
            response += f"Total species available: {total_count}\n"
            response += f"Showing first {len(species_list)}:\n\n"

        response += "| Code | Common Name | Scientific Name |\n"
        response += "|------|-------------|----------------|\n"

        for species in species_list:
            response += (
                f"| {species['species_code']} | "
                f"{species['common_name']} | "
                f"*{species['scientific_name']}* |\n"
            )

        response += "\n*Data source: USDA Forest Service BIGMAP 2018 (30m resolution)*"

        return response

    except Exception as e:
        logger.exception("Error listing species")
        return f"Error listing species: {e}"


@tool(args_schema=SpeciesDiversityInput)
async def query_species_diversity(
    state: str,
    county: str | None = None,
    metric: str = "shannon",
) -> str:
    """
    Calculate species diversity indices from GridFIA 30m raster data.

    Use for questions about:
    - How diverse are the forests in a state or county
    - Shannon diversity index for a region
    - Simpson diversity index for a region
    - Species richness (how many species per pixel)
    - Comparing biodiversity across areas
    - Forest composition complexity

    Note: This provides spatially continuous data at 30m resolution,
    complementing PyFIA's survey-based statistical estimates.
    """
    if not GRIDFIA_AVAILABLE:
        return "GridFIA is not installed. Spatial analysis tools are unavailable."

    # Validate metric
    valid_metrics = ["shannon", "simpson", "richness"]
    if metric.lower() not in valid_metrics:
        return f"Invalid metric: {metric}. Valid options: {', '.join(valid_metrics)}"

    try:
        service = get_gridfia_service()
        result = await service.query_diversity(
            state=state,
            county=county,
            metric=metric.lower(),
        )

        # Format response based on metric
        location = result["location"]
        metric_name = metric.lower()

        response = f"**Species Diversity Analysis - {location}**\n\n"
        response += f"*Metric: {metric_name.title()} "

        if metric_name == "shannon":
            response += "(Shannon Diversity Index H')*\n\n"
            response += "Higher values indicate greater diversity.\n"
            response += "Typical range: 0 (single species) to ~4 (highly diverse)\n\n"
        elif metric_name == "simpson":
            response += "(Simpson Diversity Index)*\n\n"
            response += "Higher values indicate greater diversity (using 1-D form).\n"
            response += "Range: 0 to 1\n\n"
        else:  # richness
            response += "(Species Richness)*\n\n"
            response += "Count of unique tree species per 30m pixel.\n\n"

        # Statistics
        response += "**Results:**\n"
        response += f"- Mean: {result['mean']:.2f}\n"
        response += f"- Std Dev: {result['std']:.2f}\n"
        response += f"- Range: {result['min']:.2f} - {result['max']:.2f}\n"

        if "richness_max" in result:
            response += f"\n**Species Richness:**\n"
            response += f"- Maximum species per pixel: {result['richness_max']}\n"
            response += f"- Mean species per pixel: {result['richness_mean']:.1f}\n"

        # Coverage info
        pixel_count = result.get("pixel_count", 0)
        area_ha = pixel_count * 0.09  # 30m pixel = 0.09 ha
        area_acres = area_ha * 2.471

        response += f"\n**Coverage:**\n"
        response += f"- Forested pixels analyzed: {pixel_count:,}\n"
        response += f"- Area: {area_ha:,.0f} hectares ({area_acres:,.0f} acres)\n"

        response += "\n*Data source: USDA Forest Service BIGMAP 2018 (30m resolution)*"

        return response

    except Exception as e:
        logger.exception(f"Error calculating diversity for {state} {county or ''}")
        return f"Error calculating diversity: {e}"


@tool(args_schema=GridFIABiomassInput)
async def query_gridfia_biomass(
    state: str,
    county: str | None = None,
) -> str:
    """
    Query aboveground biomass from GridFIA 30m raster data.

    Use for questions about:
    - Total forest biomass in a state or county (spatial view)
    - Mean biomass per hectare across a region
    - Biomass distribution and variation
    - Spatial patterns of forest carbon storage
    - Comparing biomass density across areas

    Note: This provides spatially continuous biomass data at 30m resolution
    from BIGMAP 2018 model outputs. For survey-based statistical estimates
    with standard errors, use the PyFIA biomass query.
    """
    if not GRIDFIA_AVAILABLE:
        return "GridFIA is not installed. Spatial analysis tools are unavailable."

    try:
        service = get_gridfia_service()
        result = await service.query_biomass(
            state=state,
            county=county,
        )

        location = result["location"]

        response = f"**Aboveground Biomass Analysis - {location}**\n\n"
        response += "*Source: BIGMAP 2018 modeled biomass at 30m resolution*\n\n"

        # Main statistics
        response += "**Biomass Statistics:**\n"
        response += f"- Mean biomass: {result['mean_biomass_mgha']:.1f} Mg/ha\n"
        response += f"- Std Dev: {result['std']:.1f} Mg/ha\n"
        response += f"- Range: {result['min']:.1f} - {result['max']:.1f} Mg/ha\n"

        # Total estimates
        total_mg = result["total_biomass_mg"]
        total_tonnes = total_mg  # Mg = metric tonnes

        response += f"\n**Estimated Totals:**\n"

        if total_tonnes >= 1_000_000:
            response += f"- Total biomass: {total_tonnes / 1_000_000:.2f} million tonnes\n"
        else:
            response += f"- Total biomass: {total_tonnes:,.0f} tonnes\n"

        # Carbon estimate (biomass * 0.5 is common conversion)
        carbon_tonnes = total_tonnes * 0.5
        if carbon_tonnes >= 1_000_000:
            response += f"- Est. carbon storage: {carbon_tonnes / 1_000_000:.2f} million tonnes C\n"
        else:
            response += f"- Est. carbon storage: {carbon_tonnes:,.0f} tonnes C\n"

        # Coverage
        area_ha = result.get("area_hectares", 0)
        area_acres = area_ha * 2.471

        response += f"\n**Coverage:**\n"
        response += f"- Forested area: {area_ha:,.0f} hectares ({area_acres:,.0f} acres)\n"
        response += f"- Pixels analyzed: {result['pixel_count']:,}\n"

        # Interpretation
        mean_biomass = result["mean_biomass_mgha"]
        response += f"\n**Interpretation:**\n"
        if mean_biomass < 50:
            response += "Low biomass density - typical of young forests or sparse cover.\n"
        elif mean_biomass < 100:
            response += "Moderate biomass density - typical of mid-successional forests.\n"
        elif mean_biomass < 200:
            response += "High biomass density - typical of mature forests.\n"
        else:
            response += "Very high biomass density - typical of old-growth or highly productive sites.\n"

        response += "\n*Note: For survey-based estimates with statistical uncertainty (SE%), "
        response += "use the PyFIA biomass query.*"

        return response

    except Exception as e:
        logger.exception(f"Error calculating biomass for {state} {county or ''}")
        return f"Error calculating biomass: {e}"


# =============================================================================
# Export List for Agent Registration
# =============================================================================

GRIDFIA_TOOLS = [
    query_gridfia_species_list,
    query_species_diversity,
    query_gridfia_biomass,
]

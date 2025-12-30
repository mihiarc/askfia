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

from .gridfia_service import (
    GRIDFIA_AVAILABLE,
    get_gridfia_service,
    get_gridfia_service_extended,
)

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


class SpeciesInLocationInput(BaseModel):
    """Input for listing species in a specific location."""

    state: str = Field(
        description=(
            "State name or two-letter abbreviation (e.g., 'RI', 'Rhode Island')"
        ),
    )
    filter_text: str | None = Field(
        default=None,
        description=(
            "Optional text to filter species by name. "
            "For example, 'oak' will return all oak species."
        ),
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


class DominantSpeciesInput(BaseModel):
    """Input for dominant species query."""

    state: str = Field(
        description=(
            "State name or two-letter abbreviation (e.g., 'NC', 'North Carolina')"
        ),
    )
    county: str | None = Field(
        default=None,
        description=(
            "County name for finer resolution (e.g., 'Wake', 'Wake County'). "
            "If not provided, analyzes the entire state."
        ),
    )
    top_n: int = Field(
        default=5,
        description="Number of top species to return (default 5, max 20).",
    )


class CompareLocationsInput(BaseModel):
    """Input for comparing two locations."""

    state1: str = Field(
        description="First state name or abbreviation (e.g., 'NC')",
    )
    county1: str | None = Field(
        default=None,
        description="First county name (optional)",
    )
    state2: str = Field(
        description="Second state name or abbreviation (e.g., 'SC')",
    )
    county2: str | None = Field(
        default=None,
        description="Second county name (optional)",
    )
    metric: str = Field(
        default="diversity",
        description=(
            "Metric to compare. Options: 'diversity' (Shannon index), 'biomass' (mean Mg/ha)"
        ),
    )


class SpeciesBiomassInput(BaseModel):
    """Input for species-specific biomass query."""

    state: str = Field(
        description=(
            "State name or two-letter abbreviation (e.g., 'NC', 'North Carolina')"
        ),
    )
    species_code: str = Field(
        description=(
            "4-digit FIA species code (e.g., '0131' for Loblolly Pine, "
            "'0316' for Red Maple). Use query_gridfia_species_list to find codes."
        ),
    )
    county: str | None = Field(
        default=None,
        description=(
            "County name for finer resolution (e.g., 'Wake'). "
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
    List ALL tree species codes available in the BIGMAP 2018 dataset.

    IMPORTANT: This returns the master list of all ~300 species in BIGMAP,
    NOT species present in a specific location. Use query_dominant_species
    to find what species actually exist in a particular state or county.

    Use for questions about:
    - What species codes are available in BIGMAP/GridFIA
    - Looking up the 4-digit FIA code for a tree (e.g., "what is the code for oak")
    - Finding species by common or scientific name
    - Getting the species code before running species-specific queries

    Do NOT use for:
    - "What species are in Rhode Island" -> use query_dominant_species
    - "What trees grow in California" -> use query_dominant_species
    - Species diversity or richness -> use query_species_diversity
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


@tool(args_schema=SpeciesInLocationInput)
async def query_species_in_location(
    state: str,
    filter_text: str | None = None,
) -> str:
    """
    List tree species present in a specific state from GridFIA cloud data.

    THIS IS THE BEST TOOL for "what species are in [state]" questions.
    Fast and lightweight - reads only metadata, no heavy computation.

    Use for questions about:
    - "What tree species are in Rhode Island"
    - "What trees grow in Connecticut"
    - "List the species found in RI"
    - "What oaks are in Rhode Island" (with filter_text="oak")

    Currently available states: Rhode Island (RI), Connecticut (CT)
    For states not yet in cloud, use query_dominant_species instead.
    """
    if not GRIDFIA_AVAILABLE:
        return "GridFIA is not installed. Spatial analysis tools are unavailable."

    try:
        service = get_gridfia_service()
        cloud_service = service._cloud_service

        # Check if state is available in cloud
        if not cloud_service.is_state_available(state):
            return (
                f"State '{state}' is not yet available in cloud storage. "
                f"Available states: Rhode Island (RI), Connecticut (CT). "
                f"For other states, use query_dominant_species which downloads data."
            )

        # Get species list from cloud metadata
        species_list = cloud_service.get_species_in_state(state)
        if species_list is None:
            return f"Error loading species data for {state}."

        # Apply filter if provided
        if filter_text:
            filter_lower = filter_text.lower()
            species_list = [
                s for s in species_list
                if filter_lower in s["common_name"].lower()
            ]

        # Format response
        state_name = cloud_service._normalize_state(state)
        state_full = {"RI": "Rhode Island", "CT": "Connecticut"}.get(state_name, state)

        response = f"**Tree Species in {state_full}**\n\n"

        if filter_text:
            response += f"Filter: '{filter_text}'\n"

        response += f"Total species present: {len(species_list)}\n\n"

        if len(species_list) == 0:
            response += "No matching species found.\n"
        else:
            response += "| Code | Common Name |\n"
            response += "|------|-------------|\n"

            for species in species_list:
                response += f"| {species['species_code']} | {species['common_name']} |\n"

        response += "\n*Data source: USDA Forest Service BIGMAP 2018 (30m resolution)*"

        return response

    except Exception as e:
        logger.exception(f"Error listing species for {state}")
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


@tool(args_schema=DominantSpeciesInput)
async def query_dominant_species(
    state: str,
    county: str | None = None,
    top_n: int = 5,
) -> str:
    """
    Find what tree species exist in a specific state or county.

    THIS IS THE PRIMARY TOOL for location-specific species questions.
    Returns species ranked by total biomass, showing which trees
    actually grow in that location.

    Use for questions about:
    - "What species are in Rhode Island" (set top_n=20 or higher)
    - "What trees grow in California"
    - What are the most common/dominant trees in an area
    - Which species are present in a forest region
    - What is the primary tree cover in a county or state
    - Ranking species by abundance/biomass
    - Understanding forest composition of a specific location

    Do NOT use for:
    - Looking up species codes -> use query_gridfia_species_list
    - Diversity metrics (Shannon/Simpson) -> use query_species_diversity
    """
    if not GRIDFIA_AVAILABLE:
        return "GridFIA is not installed. Spatial analysis tools are unavailable."

    # Validate top_n
    top_n = min(max(top_n, 1), 20)

    try:
        service = get_gridfia_service_extended()
        result = await service.query_dominant_species(
            state=state,
            county=county,
            top_n=top_n,
        )

        location = result["location"]

        response = f"**Dominant Tree Species - {location}**\n\n"
        response += f"*Top {top_n} species by total biomass (BIGMAP 2018)*\n\n"
        response += f"Total species with presence: {result['total_species_present']}\n\n"

        response += "| Rank | Species | Code | Total Biomass | Mean Mg/ha |\n"
        response += "|------|---------|------|---------------|------------|\n"

        for i, sp in enumerate(result["dominant_species"], 1):
            total_mg = sp["total_biomass_mg"]
            if total_mg >= 1_000_000:
                total_str = f"{total_mg / 1_000_000:.2f}M tonnes"
            elif total_mg >= 1_000:
                total_str = f"{total_mg / 1_000:.1f}K tonnes"
            else:
                total_str = f"{total_mg:.0f} tonnes"

            response += (
                f"| {i} | {sp['species_name']} | {sp['species_code']} | "
                f"{total_str} | {sp['mean_biomass_mgha']:.1f} |\n"
            )

        response += "\n*Data source: USDA Forest Service BIGMAP 2018 (30m resolution)*"

        return response

    except Exception as e:
        logger.exception(f"Error finding dominant species for {state} {county or ''}")
        return f"Error finding dominant species: {e}"


@tool(args_schema=CompareLocationsInput)
async def compare_gridfia_locations(
    state1: str,
    county1: str | None = None,
    state2: str = "",
    county2: str | None = None,
    metric: str = "diversity",
) -> str:
    """
    Compare forest diversity or biomass between two locations.

    Use for questions about:
    - Which area has higher species diversity
    - Comparing biomass between counties or states
    - Regional forest composition differences
    - Identifying more productive forest regions
    - Biodiversity comparisons
    """
    if not GRIDFIA_AVAILABLE:
        return "GridFIA is not installed. Spatial analysis tools are unavailable."

    if not state2:
        return "Error: Please provide both locations to compare (state2 is required)."

    # Validate metric
    valid_metrics = ["diversity", "biomass"]
    if metric.lower() not in valid_metrics:
        return f"Invalid metric: {metric}. Valid options: {', '.join(valid_metrics)}"

    try:
        service = get_gridfia_service_extended()
        result = await service.compare_locations(
            location1={"state": state1, "county": county1},
            location2={"state": state2, "county": county2},
            metric=metric.lower(),
        )

        loc1 = result["location1"]
        loc2 = result["location2"]
        comparison = result["comparison"]

        metric_name = metric.lower()
        if metric_name == "diversity":
            unit = "(Shannon Index)"
            interpretation = (
                "Higher Shannon values indicate greater species diversity. "
                "Values typically range from 0 to ~4."
            )
        else:
            unit = "(Mg/ha)"
            interpretation = (
                "Higher biomass indicates denser forest cover or larger trees."
            )

        response = f"**Forest Comparison: {loc1['name']} vs {loc2['name']}**\n\n"
        response += f"*Metric: {metric_name.title()} {unit}*\n\n"

        response += "| Location | Mean | Std Dev | Range | Pixels |\n"
        response += "|----------|------|---------|-------|--------|\n"
        response += (
            f"| {loc1['name']} | {loc1['mean']:.2f} | {loc1['std']:.2f} | "
            f"{loc1['min']:.2f}-{loc1['max']:.2f} | {loc1['pixel_count']:,} |\n"
        )
        response += (
            f"| {loc2['name']} | {loc2['mean']:.2f} | {loc2['std']:.2f} | "
            f"{loc2['min']:.2f}-{loc2['max']:.2f} | {loc2['pixel_count']:,} |\n"
        )

        response += f"\n**Result:**\n"
        response += f"- Higher: **{comparison['higher']}**\n"
        response += f"- Difference: {comparison['difference']:+.2f}\n"
        response += f"- Percent difference: {comparison['percent_difference']:+.1f}%\n"

        response += f"\n*Interpretation: {interpretation}*\n"
        response += "\n*Data source: USDA Forest Service BIGMAP 2018 (30m resolution)*"

        return response

    except Exception as e:
        logger.exception(f"Error comparing {state1} and {state2}")
        return f"Error comparing locations: {e}"


@tool(args_schema=SpeciesBiomassInput)
async def query_species_specific_biomass(
    state: str,
    species_code: str,
    county: str | None = None,
) -> str:
    """
    Query biomass for a specific tree species from GridFIA 30m raster data.

    Use for questions about:
    - How much loblolly pine biomass is in North Carolina
    - Total red maple volume in a county
    - Species-specific forest resources
    - Individual species distribution and density
    - Biomass of a particular tree type

    Note: Use query_gridfia_species_list first to find the species code.
    Common codes: 0131 (Loblolly Pine), 0316 (Red Maple), 0802 (White Oak).
    """
    if not GRIDFIA_AVAILABLE:
        return "GridFIA is not installed. Spatial analysis tools are unavailable."

    # Validate species code format
    if not species_code.isdigit() or len(species_code) != 4:
        return (
            f"Invalid species code: '{species_code}'. "
            "Must be a 4-digit code (e.g., '0131' for Loblolly Pine). "
            "Use query_gridfia_species_list to find valid codes."
        )

    try:
        service = get_gridfia_service_extended()
        result = await service.query_species_biomass(
            state=state,
            species_code=species_code,
            county=county,
        )

        location = result["location"]
        species_name = result["species_name"]

        if not result.get("found"):
            return result.get("message", f"Species {species_code} not found in {location}.")

        if not result.get("has_data"):
            return result.get("message", f"No biomass data for {species_name} in {location}.")

        response = f"**{species_name} (SPCD {species_code}) Biomass - {location}**\n\n"
        response += "*Source: BIGMAP 2018 modeled biomass at 30m resolution*\n\n"

        # Main statistics
        response += "**Biomass Statistics:**\n"
        response += f"- Mean biomass: {result['mean_biomass_mgha']:.1f} Mg/ha\n"
        response += f"- Std Dev: {result['std']:.1f} Mg/ha\n"
        response += f"- Range: {result['min']:.1f} - {result['max']:.1f} Mg/ha\n"

        # Total estimates
        total_mg = result["total_biomass_mg"]
        if total_mg >= 1_000_000:
            response += f"- Total biomass: {total_mg / 1_000_000:.2f} million tonnes\n"
        else:
            response += f"- Total biomass: {total_mg:,.0f} tonnes\n"

        # Carbon estimate
        carbon_tonnes = total_mg * 0.5
        if carbon_tonnes >= 1_000_000:
            response += f"- Est. carbon storage: {carbon_tonnes / 1_000_000:.2f} million tonnes C\n"
        else:
            response += f"- Est. carbon storage: {carbon_tonnes:,.0f} tonnes C\n"

        # Coverage
        response += f"\n**Coverage:**\n"
        response += f"- Species present in: {result['pixel_count']:,} pixels\n"
        response += f"- Area with species: {result['area_hectares']:,.0f} hectares\n"
        response += f"  ({result['area_hectares'] * 2.471:,.0f} acres)\n"

        response += "\n*Note: Use query_gridfia_biomass for total forest biomass across all species.*"

        return response

    except Exception as e:
        logger.exception(f"Error querying biomass for species {species_code}")
        return f"Error querying species biomass: {e}"


# =============================================================================
# Export List for Agent Registration
# =============================================================================

GRIDFIA_TOOLS = [
    query_gridfia_species_list,
    query_species_in_location,  # Fast cloud-based species list for RI/CT
    query_species_diversity,
    query_gridfia_biomass,
    query_dominant_species,
    compare_gridfia_locations,
    query_species_specific_biomass,
]

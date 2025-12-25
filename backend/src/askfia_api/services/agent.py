"""LangChain agent for FIA queries."""

import logging
import time
from collections.abc import AsyncGenerator

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from ..config import settings
from .fia_service import fia_service
from .forest_types import get_forest_type_name
from .usage_tracker import usage_tracker

logger = logging.getLogger(__name__)


# ============================================================================
# Tool Definitions
# ============================================================================


# FIA code lookups for human-readable output
# Forest types are now in forest_types.py module

OWNERSHIP_GROUPS = {
    10: "National Forest",
    20: "Other federal",
    30: "State & local government",
    40: "Private",
}

STAND_SIZE_CLASSES = {
    1: 'Large diameter (>11" softwood, >9" hardwood)',
    2: 'Medium diameter (5-11" softwood, 5-9" hardwood)',
    3: 'Small diameter (<5")',
    5: "Nonstocked",
}


class ForestAreaInput(BaseModel):
    """Input for forest area query."""

    states: list[str] = Field(description="Two-letter state codes (e.g., ['NC', 'GA'])")
    land_type: str = Field(default="forest", description="forest, timber, or reserved")
    grp_by: str | None = Field(
        default=None,
        description=(
            "Column to group results by. Common options: "
            "FORTYPCD (forest type - loblolly pine, oak-hickory, etc.), "
            "OWNGRPCD (ownership - public, private), "
            "STDSZCD (stand size class - large/medium/small diameter)"
        ),
    )


@tool(args_schema=ForestAreaInput)
async def query_forest_area(
    states: list[str], land_type: str = "forest", grp_by: str | None = None
) -> str:
    """
    Query forest land area from FIA database.

    Use for questions about:
    - How much forest land is in a state
    - Forest area by ownership type (use grp_by='OWNGRPCD')
    - Forest area by forest type (use grp_by='FORTYPCD')
    - Forest area by stand size (use grp_by='STDSZCD')
    - Timberland vs reserved forest area
    """
    result = await fia_service.query_area(states, land_type, grp_by)

    response = f"**Forest Area ({land_type})**\n"
    response += f"States: {', '.join(states)}\n"
    response += f"Total: {result['total_area_acres']:,.0f} acres\n"
    response += f"SE: {result['se_percent']:.1f}%\n"

    if result.get("breakdown") and grp_by:
        response += f"\nBreakdown by {grp_by}:\n"

        # Sort by estimate descending
        sorted_rows = sorted(
            result["breakdown"],
            key=lambda x: x.get("AREA", x.get("ESTIMATE", 0)),
            reverse=True,
        )

        for row in sorted_rows[:15]:
            code = row.get(grp_by)
            estimate = row.get("AREA", row.get("ESTIMATE", 0))

            # Look up human-readable names
            if grp_by == "FORTYPCD":
                label = get_forest_type_name(code) if code else "Unknown"
            elif grp_by == "OWNGRPCD" and code in OWNERSHIP_GROUPS:
                label = OWNERSHIP_GROUPS[code]
            elif grp_by == "STDSZCD" and code in STAND_SIZE_CLASSES:
                label = STAND_SIZE_CLASSES[code]
            else:
                label = f"Code {code}"

            response += f"- {label}: {estimate:,.0f} acres\n"

    return response


class TimberVolumeInput(BaseModel):
    """Input for timber volume query."""

    states: list[str] = Field(description="Two-letter state codes")
    by_species: bool = Field(default=False, description="Group by species")
    tree_domain: str | None = Field(
        default=None, description="Filter (e.g., 'DIA >= 10.0')"
    )


@tool(args_schema=TimberVolumeInput)
async def query_timber_volume(
    states: list[str], by_species: bool = False, tree_domain: str | None = None
) -> str:
    """
    Query timber volume from FIA database.

    Use for questions about:
    - How much timber is in a state
    - Volume by species
    - Sawtimber volume (use tree_domain='DIA >= 10.0')
    """
    result = await fia_service.query_volume(states, by_species, tree_domain)

    response = "**Timber Volume**\n"
    response += f"States: {', '.join(states)}\n"
    response += f"Total: {result['total_volume_cuft']:,.0f} cubic feet\n"
    response += f"  ({result['total_volume_billion_cuft']:.2f} billion cu ft)\n"
    response += f"SE: {result['se_percent']:.1f}%\n"

    if result.get("by_species"):
        response += "\nTop species:\n"
        sorted_species = sorted(
            result["by_species"], key=lambda x: x.get("ESTIMATE", x.get("estimate", 0)), reverse=True
        )
        for row in sorted_species[:10]:
            estimate = row.get("ESTIMATE", row.get("estimate", 0))
            spcd = row.get("SPCD", row.get("spcd", "?"))
            response += f"- SPCD {spcd}: {estimate:,.0f} cu ft\n"

    return response


class BiomassInput(BaseModel):
    """Input for biomass query."""

    states: list[str] = Field(description="Two-letter state codes")
    land_type: str = Field(default="forest", description="forest or timber")
    by_species: bool = Field(default=False, description="Group by species")


@tool(args_schema=BiomassInput)
async def query_biomass_carbon(
    states: list[str], land_type: str = "forest", by_species: bool = False
) -> str:
    """
    Query biomass and carbon stocks from FIA database.

    Use for questions about:
    - Forest carbon stocks
    - Biomass by state or region
    - Carbon sequestration
    """
    result = await fia_service.query_biomass(states, land_type, by_species)

    response = f"**Biomass & Carbon ({land_type})**\n"
    response += f"States: {', '.join(states)}\n"
    response += f"Biomass: {result['total_biomass_tons']:,.0f} short tons\n"
    response += f"Carbon: {result['carbon_mmt']:.2f} million metric tons\n"
    response += f"SE: {result['se_percent']:.1f}%\n"

    if result.get("by_species"):
        response += "\nTop species:\n"
        sorted_species = sorted(
            result["by_species"], key=lambda x: x.get("ESTIMATE", 0), reverse=True
        )
        for row in sorted_species[:5]:
            response += f"- SPCD {row.get('SPCD', '?')}: {row['ESTIMATE']:,.0f} tons\n"

    return response


class MortalityInput(BaseModel):
    """Input for mortality query."""

    states: list[str] = Field(description="Two-letter state codes")
    by_species: bool = Field(default=False, description="Group by species")
    tree_domain: str | None = Field(
        default=None, description="Filter (e.g., 'DIA >= 10.0')"
    )


@tool(args_schema=MortalityInput)
async def query_mortality(
    states: list[str], by_species: bool = False, tree_domain: str | None = None
) -> str:
    """
    Query annual tree mortality from FIA database.

    Use for questions about:
    - Annual tree mortality rates
    - Mortality by species
    - Dead tree volume
    - Forest health and mortality trends
    """
    result = await fia_service.query_mortality(states, by_species, tree_domain)

    response = "**Annual Tree Mortality**\n"
    response += f"States: {', '.join(states)}\n"
    response += f"Total: {result['total_mortality_cuft']:,.0f} cubic feet/year\n"
    response += f"  ({result['total_mortality_million_cuft']:.2f} million cu ft/year)\n"
    response += f"SE: {result['se_percent']:.1f}%\n"

    if result.get("by_species"):
        response += "\nTop species:\n"
        sorted_species = sorted(
            result["by_species"], key=lambda x: x.get("MORT_TOTAL", 0), reverse=True
        )
        for row in sorted_species[:10]:
            mort_total = row.get("MORT_TOTAL", 0)
            response += f"- SPCD {row.get('SPCD', '?')}: {mort_total:,.0f} cu ft/year\n"

    return response


class RemovalsInput(BaseModel):
    """Input for removals query."""

    states: list[str] = Field(description="Two-letter state codes")
    by_species: bool = Field(default=False, description="Group by species")
    tree_domain: str | None = Field(
        default=None, description="Filter (e.g., 'DIA >= 10.0')"
    )


@tool(args_schema=RemovalsInput)
async def query_removals(
    states: list[str], by_species: bool = False, tree_domain: str | None = None
) -> str:
    """
    Query timber removals (harvest) from FIA database.

    Use for questions about:
    - How much timber was harvested in a state
    - Annual removals by species
    - Harvest rates and trends
    """
    result = await fia_service.query_removals(states, by_species, tree_domain)

    response = "**Timber Removals (Harvest)**\n"
    response += f"States: {', '.join(states)}\n"
    response += f"Total: {result['total_removals_cuft']:,.0f} cubic feet/year\n"
    response += f"  ({result['total_removals_million_cuft']:.2f} million cu ft/year)\n"
    response += f"SE: {result['se_percent']:.1f}%\n"

    if result.get("by_species"):
        response += "\nTop species:\n"
        sorted_species = sorted(
            result["by_species"], key=lambda x: x.get("REMOVALS_TOTAL", 0), reverse=True
        )
        for row in sorted_species[:10]:
            response += f"- SPCD {row.get('SPCD', '?')}: {row['REMOVALS_TOTAL']:,.0f} cu ft/year\n"

    return response


class GrowthInput(BaseModel):
    """Input for growth query."""

    states: list[str] = Field(description="Two-letter state codes")
    by_species: bool = Field(default=False, description="Group by species")
    tree_domain: str | None = Field(
        default=None, description="Filter (e.g., 'DIA >= 5.0')"
    )
    measure: str = Field(default="volume", description="volume, biomass, or count")
    land_type: str = Field(default="forest", description="forest or timber")


@tool(args_schema=GrowthInput)
async def query_growth(
    states: list[str],
    by_species: bool = False,
    tree_domain: str | None = None,
    measure: str = "volume",
    land_type: str = "forest",
) -> str:
    """
    Query annual tree growth from FIA database.

    Use for questions about:
    - Annual tree growth rates
    - Volume or biomass growth
    - Growth by species
    - Forest productivity and health
    """
    result = await fia_service.query_growth(
        states, by_species, tree_domain, measure, land_type
    )

    # Handle error case when GRM tables are not available
    if "error" in result:
        response = "**Growth Data Not Available**\n\n"
        response += f"{result['error']}\n\n"
        response += "**Alternative metrics available:**\n"
        for metric in result.get("available_metrics", []):
            response += f"- {metric}\n"
        return response

    response = "**Annual Tree Growth**\n"
    response += f"States: {', '.join(states)}\n"
    response += f"Measure: {measure}\n"
    response += f"Land type: {land_type}\n"

    # Add warning if some states were missing GRM data
    if result.get("warning"):
        response += f"\n⚠️  {result['warning']}\n"

    if measure == "volume":
        response += f"Total: {result['total_growth_cuft']:,.0f} cubic feet/year\n"
        response += (
            f"  ({result['total_growth_million_cuft']:.2f} million cu ft/year)\n"
        )
    elif measure == "biomass":
        response += f"Total: {result['total_growth_tons']:,.0f} short tons/year\n"
        response += f"  ({result['total_growth_million_tons']:.2f} million tons/year)\n"
    else:  # count
        response += f"Total: {result['total_growth_trees']:,.0f} trees/year\n"

    response += f"SE: {result['se_percent']:.1f}%\n"

    if result.get("by_species"):
        response += "\nTop species:\n"
        sorted_species = sorted(
            result["by_species"], key=lambda x: x.get("GROWTH_TOTAL", 0), reverse=True
        )
        for row in sorted_species[:10]:
            growth_total = row.get("GROWTH_TOTAL", 0)
            response += f"- SPCD {row.get('SPCD', '?')}: {growth_total:,.0f}/year\n"

    return response


class AreaChangeInput(BaseModel):
    """Input for area change query."""

    states: list[str] = Field(description="Two-letter state codes")
    land_type: str = Field(default="forest", description="forest or timber")
    change_type: str = Field(
        default="net",
        description="net (gains minus losses), gross_gain (forest gained), or gross_loss (forest lost)",
    )
    grp_by: str | None = Field(
        default=None,
        description="Column to group results by (e.g., OWNGRPCD for ownership)",
    )


@tool(args_schema=AreaChangeInput)
async def query_area_change(
    states: list[str],
    land_type: str = "forest",
    change_type: str = "net",
    grp_by: str | None = None,
) -> str:
    """
    Query annual forest area change from FIA database.

    Use for questions about:
    - Forest land transitions (gains and losses)
    - Annual net forest area change
    - Forest area gained from non-forest land
    - Forest area lost to non-forest land (e.g., development, conversion)
    - Area change by ownership type

    Results show annualized change in acres per year based on remeasured plots.
    Positive values indicate net gain, negative values indicate net loss.
    """
    result = await fia_service.query_area_change(states, land_type, change_type, grp_by)

    response = f"**Annual Forest Area Change ({land_type}, {change_type})**\n"
    response += f"States: {', '.join(states)}\n"

    change_value = result["total_area_change_acres_per_year"]

    # Format with appropriate sign
    if change_value >= 0:
        response += f"Total: +{change_value:,.0f} acres/year\n"
    else:
        response += f"Total: {change_value:,.0f} acres/year\n"

    response += f"SE: {result['se_percent']:.1f}%\n"

    if result.get("breakdown") and grp_by:
        response += f"\nBreakdown by {grp_by}:\n"

        # Sort by absolute change value descending
        sorted_rows = sorted(
            result["breakdown"],
            key=lambda x: abs(x.get("AREA_CHANGE_TOTAL", 0)),
            reverse=True,
        )

        for row in sorted_rows[:15]:
            code = row.get(grp_by)
            change = row.get("AREA_CHANGE_TOTAL", 0)

            # Look up human-readable names for ownership groups
            if grp_by == "OWNGRPCD" and code in OWNERSHIP_GROUPS:
                label = OWNERSHIP_GROUPS[code]
            else:
                label = f"Code {code}"

            # Format with sign
            if change >= 0:
                response += f"- {label}: +{change:,.0f} acres/year\n"
            else:
                response += f"- {label}: {change:,.0f} acres/year\n"

    return response


class TPAInput(BaseModel):
    """Input for trees per acre query."""

    states: list[str] = Field(description="Two-letter state codes")
    by_species: bool = Field(default=False, description="Group by species")
    by_size_class: bool = Field(
        default=False, description="Group by 2-inch diameter size classes"
    )
    tree_domain: str | None = Field(
        default=None, description="Tree filter (e.g., 'DIA >= 10.0')"
    )
    land_type: str = Field(default="forest", description="forest, timber, or all")
    tree_type: str = Field(
        default="live", description="live, dead, gs (growing stock), or all"
    )


class ForestTypeInput(BaseModel):
    """Input for forest type analysis."""

    states: list[str] = Field(description="Two-letter state codes (e.g., ['NC', 'GA'])")
    metric: str = Field(
        default="area", description="Metric to analyze: area, volume, or biomass"
    )
    land_type: str = Field(default="forest", description="forest, timber, or reserved")
    tree_domain: str | None = Field(
        default=None, description="Optional tree filter (e.g., 'DIA >= 10.0')"
    )


class CompareInput(BaseModel):
    """Input for state comparison."""

    states: list[str] = Field(description="States to compare (2-10)")
    metric: str = Field(
        description="area, volume, biomass, tpa, mortality, removals, or growth"
    )


@tool(args_schema=TPAInput)
async def query_tpa(
    states: list[str],
    by_species: bool = False,
    by_size_class: bool = False,
    tree_domain: str | None = None,
    land_type: str = "forest",
    tree_type: str = "live",
) -> str:
    """
    Query trees per acre (TPA) and basal area from FIA database.

    Use for questions about:
    - Tree density (trees per acre)
    - Basal area (square feet per acre)
    - Tree counts by species (use by_species=True)
    - Tree distribution by size class (use by_size_class=True)
    - Large tree density (use tree_domain='DIA >= 10.0')
    - Growing stock trees (use tree_type='gs')
    """
    result = await fia_service.query_tpa(
        states,
        by_species,
        by_size_class,
        tree_domain,
        land_type,
        tree_type,
    )

    response = f"**Trees Per Acre ({land_type}, {tree_type} trees)**\n"
    response += f"States: {', '.join(states)}\n"
    response += f"Total TPA: {result['total_tpa']:.1f} trees/acre\n"
    response += f"SE: {result['se_percent']:.1f}%\n"

    if tree_domain:
        response += f"Tree filter: {tree_domain}\n"

    if result.get("by_species"):
        response += "\nTop species by TPA:\n"
        sorted_species = sorted(
            result["by_species"], key=lambda x: x.get("ESTIMATE", x.get("TPA", 0)), reverse=True
        )
        for row in sorted_species[:10]:
            tpa = row.get("ESTIMATE", row.get("TPA", 0))
            baa = row.get("BAA", 0)
            spcd = row.get("SPCD", "?")
            response += f"- SPCD {spcd}: {tpa:.1f} trees/acre, {baa:.1f} sq ft/acre\n"

    if result.get("by_size_class"):
        response += "\nBy size class (2-inch DBH classes):\n"
        sorted_sizes = sorted(
            result["by_size_class"], key=lambda x: x.get("SIZE_CLASS", 0)
        )
        for row in sorted_sizes[:15]:
            size_class = row.get("SIZE_CLASS", 0)
            tpa = row.get("ESTIMATE", row.get("TPA", 0))
            baa = row.get("BAA", 0)
            response += f'- {size_class}-{size_class + 2}" DBH: {tpa:.1f} trees/acre, {baa:.1f} sq ft/acre\n'

    return response


@tool(args_schema=ForestTypeInput)
async def query_by_forest_type(
    states: list[str],
    metric: str = "area",
    land_type: str = "forest",
    tree_domain: str | None = None,
) -> str:
    """
    Query forest metrics grouped by forest type.

    Use for questions about:
    - Forest area by type (e.g., loblolly pine, oak-hickory, maple-beech)
    - Volume by forest type
    - Biomass by forest type
    - Which forest types are most common in a region
    - Distribution of different forest ecosystems
    """
    result = await fia_service.query_by_forest_type(
        states, metric, land_type, tree_domain
    )

    units = {
        "area": "acres",
        "volume": "cubic feet",
        "biomass": "short tons",
    }

    response = f"**Forest Metrics by Type ({metric})**\n"
    response += f"States: {', '.join(states)}\n"
    response += f"Land type: {land_type}\n"
    if tree_domain:
        response += f"Tree filter: {tree_domain}\n"
    response += (
        f"\nTotal: {result['total_estimate']:,.0f} {units.get(metric, metric)}\n"
    )
    response += f"SE: {result['se_percent']:.1f}%\n"

    if result.get("breakdown"):
        response += "\nTop forest types:\n"
        # Show top 15 forest types
        for row in result["breakdown"][:15]:
            forest_type = row.get("FOREST_TYPE_NAME", "Unknown")
            estimate = row.get("ESTIMATE", 0)
            se_pct = row.get("SE_PERCENT", 0)
            response += f"- {forest_type}: {estimate:,.0f} {units.get(metric, metric)} (SE: {se_pct:.1f}%)\n"

    return response


@tool(args_schema=CompareInput)
async def compare_states(states: list[str], metric: str) -> str:
    """
    Compare forest metrics across multiple states.

    Use for questions about:
    - Which state has more forest
    - Ranking states by timber volume
    - Regional comparisons
    """
    result = await fia_service.compare_states(states, metric)

    units = {
        "area": "acres",
        "volume": "cubic feet",
        "biomass": "short tons",
        "tpa": "trees/acre",
        "mortality": "trees/year",
        "growth": "cubic feet/year",
    }

    response = f"**State Comparison: {metric.title()}**\n"
    response += f"Unit: {units.get(metric, metric)}\n\n"
    response += "| State | Estimate | SE% |\n"
    response += "|-------|----------|-----|\n"

    for row in result["states"]:
        est = f"{row['estimate']:,.0f}" if row["estimate"] else "N/A"
        se = f"{row['se_percent']:.1f}%" if row["se_percent"] else "N/A"
        response += f"| {row['state']} | {est} | {se} |\n"

    return response


class StandSizeInput(BaseModel):
    """Input for stand size class query."""

    states: list[str] = Field(description="Two-letter state codes (e.g., ['NC', 'GA'])")
    metric: str = Field(
        default="area", description="Metric: area, volume, biomass, or tpa"
    )
    land_type: str = Field(default="forest", description="forest, timber, or reserved")
    tree_domain: str | None = Field(
        default=None, description="Tree filter (e.g., 'DIA >= 10.0')"
    )


@tool(args_schema=StandSizeInput)
async def query_by_stand_size(
    states: list[str],
    metric: str = "area",
    land_type: str = "forest",
    tree_domain: str | None = None,
) -> str:
    """
    Query forest metrics grouped by stand size class.

    Use for questions about:
    - Forest distribution by tree size (large/medium/small diameter)
    - Area, volume, biomass, or tree density by stand size
    - Stand structure analysis
    - Young forest vs mature forest comparisons

    Stand size classes:
    - Large diameter: DBH >11" (softwood) or >9" (hardwood)
    - Medium diameter: DBH 5-11" (softwood) or 5-9" (hardwood)
    - Small diameter: DBH <5"
    - Nonstocked: No trees or very sparse stocking
    """
    result = await fia_service.query_by_stand_size(
        states, metric, land_type, tree_domain
    )

    units = {
        "area": "acres",
        "volume": "cubic feet",
        "biomass": "short tons",
        "tpa": "trees/acre",
    }

    response = f"**{metric.title()} by Stand Size Class**\n"
    response += f"States: {', '.join(states)}\n"
    response += f"Land type: {land_type}\n"
    response += f"Total: {result['total_estimate']:,.0f} {units.get(metric, metric)}\n"
    response += f"SE: {result['se_percent']:.1f}%\n"

    if tree_domain:
        response += f"Tree filter: {tree_domain}\n"

    if result.get("by_stand_size"):
        response += "\nBreakdown by stand size:\n"

        # Sort by estimate descending
        sorted_rows = sorted(
            result["by_stand_size"], key=lambda x: x.get("STDSZCD", 99)
        )

        for row in sorted_rows:
            code = row.get("STDSZCD")
            if code is None:
                continue

            # Translate code to human-readable name
            label = STAND_SIZE_CLASSES.get(code, f"Code {code}")

            # Get the estimate value (column name varies by metric)
            estimate = 0.0
            if metric == "area":
                estimate = row.get("AREA", row.get("ESTIMATE", 0))
            elif metric == "volume":
                estimate = row.get("VOL_TOTAL", row.get("ESTIMATE", 0))
            elif metric == "biomass":
                estimate = row.get("BIO_TOTAL", row.get("ESTIMATE", 0))
            elif metric == "tpa":
                estimate = row.get("TPA", row.get("ESTIMATE", 0))

            response += f"- {label}: {estimate:,.0f} {units.get(metric, metric)}\n"

    return response


class OwnershipInput(BaseModel):
    """Input for ownership analysis query."""

    states: list[str] = Field(description="Two-letter state codes (e.g., ['NC', 'GA'])")
    metric: str = Field(
        default="area", description="Metric: area, volume, biomass, or tpa"
    )
    land_type: str = Field(default="forest", description="forest or timber")
    tree_domain: str | None = Field(
        default=None, description="Tree filter (e.g., 'DIA >= 10.0')"
    )


@tool(args_schema=OwnershipInput)
async def query_by_ownership(
    states: list[str],
    metric: str = "area",
    land_type: str = "forest",
    tree_domain: str | None = None,
) -> str:
    """
    Query forest metrics grouped by ownership type.

    Use for questions about:
    - Forest area, volume, biomass, or tree density by ownership
    - National Forest vs private land comparisons
    - Federal vs state vs private forest distribution
    - Public vs private forest resources

    Ownership groups:
    - Forest Service: National Forests managed by USDA Forest Service
    - Other Federal: BLM, National Parks, Military, etc.
    - State and Local Government: State forests, county parks, etc.
    - Private: Corporate, family, and individual private landowners
    """
    result = await fia_service.query_by_ownership(
        states, metric, land_type, tree_domain
    )

    # Define units for each metric
    units = {
        "area": "acres",
        "volume": "cubic feet",
        "biomass": "short tons",
        "tpa": "trees/acre",
    }

    response = f"**Forest Ownership Analysis ({metric})**\n"
    response += f"States: {', '.join(states)}\n"
    if result.get("land_type"):
        response += f"Land type: {result['land_type']}\n"
    if result.get("tree_domain"):
        response += f"Tree filter: {result['tree_domain']}\n"
    response += (
        f"Total: {result['total_estimate']:,.0f} {units.get(metric, metric)}\n\n"
    )

    response += "Breakdown by ownership:\n"

    for row in result["ownership_breakdown"]:
        ownership_name = row["ownership_name"]
        estimate = row["estimate"]
        se_pct = row["se_percent"]

        # Calculate percentage of total
        pct_of_total = (
            (estimate / result["total_estimate"] * 100)
            if result["total_estimate"] > 0
            else 0
        )

        response += f"- {ownership_name}: {estimate:,.0f} {units.get(metric, metric)} "
        response += f"({pct_of_total:.1f}%, SE: {se_pct:.1f}%)\n"

    return response


# County FIPS code helper - common counties for quick lookup
COMMON_COUNTY_FIPS = {
    # North Carolina
    ("NC", "WAKE"): 183,
    ("NC", "MECKLENBURG"): 119,
    ("NC", "GUILFORD"): 81,
    ("NC", "FORSYTH"): 67,
    ("NC", "DURHAM"): 63,
    ("NC", "BUNCOMBE"): 21,
    ("NC", "CUMBERLAND"): 51,
    ("NC", "NEW HANOVER"): 129,
    # Georgia
    ("GA", "FULTON"): 121,
    ("GA", "GWINNETT"): 135,
    ("GA", "COBB"): 67,
    ("GA", "DEKALB"): 89,
    ("GA", "CHATHAM"): 51,
    # Florida
    ("FL", "MIAMI-DADE"): 86,
    ("FL", "BROWARD"): 11,
    ("FL", "PALM BEACH"): 99,
    ("FL", "HILLSBOROUGH"): 57,
    ("FL", "ORANGE"): 95,
    # South Carolina
    ("SC", "GREENVILLE"): 45,
    ("SC", "RICHLAND"): 79,
    ("SC", "CHARLESTON"): 19,
    # Virginia
    ("VA", "FAIRFAX"): 59,
    ("VA", "PRINCE WILLIAM"): 153,
    ("VA", "LOUDOUN"): 107,
}


def parse_county_input(state: str, county_input: str | int) -> int:
    """Parse county name or FIPS code to return FIPS code."""
    if isinstance(county_input, int):
        return county_input
    if county_input.isdigit():
        return int(county_input)

    state = state.upper()
    county_name = county_input.upper().strip()

    # Try direct lookup
    fips = COMMON_COUNTY_FIPS.get((state, county_name))
    if fips:
        return fips

    # Try with "COUNTY" suffix removed
    if county_name.endswith(" COUNTY"):
        county_name = county_name[:-7].strip()
        fips = COMMON_COUNTY_FIPS.get((state, county_name))
        if fips:
            return fips

    # Not found - helpful error
    available = [name for (st, name) in COMMON_COUNTY_FIPS.keys() if st == state]
    if available:
        raise ValueError(
            f"County '{county_input}' not found. Please provide the 3-digit FIPS code, "
            f"or use one of these: {', '.join(sorted(available)[:3])}..."
        )
    raise ValueError(f"Please provide the 3-digit county FIPS code for {state}.")


class CountyQueryInput(BaseModel):
    """Input for county-level forest query."""

    state: str = Field(description="Two-letter state code (e.g., 'NC', 'GA')")
    county: str | int = Field(
        description="County name (e.g., 'Wake', 'Mecklenburg') or 3-digit FIPS code"
    )
    metric: str = Field(
        default="area",
        description="Metric to query: area, volume, biomass, or tpa (trees per acre)",
    )
    land_type: str = Field(default="forest", description="Land type: forest or timber")
    by_species: bool = Field(
        default=False,
        description="Group results by species (volume, biomass, tpa only)",
    )
    tree_domain: str | None = Field(
        default=None, description="Tree filter (e.g., 'DIA >= 10.0') for volume and tpa"
    )


@tool(args_schema=CountyQueryInput)
async def query_by_county(
    state: str,
    county: str | int,
    metric: str = "area",
    land_type: str = "forest",
    by_species: bool = False,
    tree_domain: str | None = None,
) -> str:
    """
    Query forest metrics for a specific county.

    Use for questions about:
    - Forest area in a specific county
    - Timber volume in a county
    - Biomass/carbon stocks in a county
    - Tree density (TPA) in a county
    - County-level forest statistics
    """
    # Parse county input to FIPS code
    try:
        county_fips = parse_county_input(state, county)
    except ValueError as e:
        return f"Error: {e}"

    # Query the metric
    result = await fia_service.query_by_county(
        state=state,
        county_fips=county_fips,
        metric=metric,
        land_type=land_type,
        by_species=by_species,
        tree_domain=tree_domain,
    )

    # Format response based on metric
    response = f"**County-Level {metric.title()}**\n"
    response += f"State: {state.upper()}\n"
    response += f"County FIPS: {county_fips}\n"

    if metric == "area":
        response += f"Land type: {land_type}\n"
        response += f"Total: {result['total_area_acres']:,.0f} acres\n"
        response += f"SE: {result['se_percent']:.1f}%\n"
    elif metric == "volume":
        response += f"Total: {result['total_volume_cuft']:,.0f} cubic feet\n"
        response += f"  ({result['total_volume_billion_cuft']:.2f} billion cu ft)\n"
        response += f"SE: {result['se_percent']:.1f}%\n"
        if result.get("by_species"):
            response += "\nTop species:\n"
            sorted_species = sorted(
                result["by_species"], key=lambda x: x.get("ESTIMATE", 0), reverse=True
            )
            for row in sorted_species[:10]:
                response += (
                    f"- SPCD {row.get('SPCD', '?')}: {row['ESTIMATE']:,.0f} cu ft\n"
                )
    elif metric == "biomass":
        response += f"Land type: {land_type}\n"
        response += f"Biomass: {result['total_biomass_tons']:,.0f} short tons\n"
        response += f"Carbon: {result['carbon_mmt']:.2f} million metric tons\n"
        response += f"SE: {result['se_percent']:.1f}%\n"
        if result.get("by_species"):
            response += "\nTop species:\n"
            sorted_species = sorted(
                result["by_species"], key=lambda x: x.get("BIO_TOTAL", 0), reverse=True
            )
            for row in sorted_species[:5]:
                bio = row.get("BIO_TOTAL", 0)
                response += f"- SPCD {row.get('SPCD', '?')}: {bio:,.0f} tons\n"
    elif metric == "tpa":
        response += f"Land type: {land_type}\n"
        response += f"Total TPA: {result['total_tpa']:.1f} trees/acre\n"
        response += f"SE: {result['se_percent']:.1f}%\n"
        if tree_domain:
            response += f"Tree filter: {tree_domain}\n"
        if result.get("by_species"):
            response += "\nTop species:\n"
            sorted_species = sorted(
                result["by_species"], key=lambda x: x.get("TPA", 0), reverse=True
            )
            for row in sorted_species[:10]:
                tpa = row.get("TPA", 0)
                response += f"- SPCD {row.get('SPCD', '?')}: {tpa:.1f} trees/acre\n"

    return response


class SpeciesLookupInput(BaseModel):
    """Input for species lookup."""

    spcd: int | None = Field(
        default=None, description="Species code to lookup (e.g., 316)"
    )
    common_name: str | None = Field(
        default=None, description="Common name to search for (e.g., 'pine', 'oak')"
    )
    state: str | None = Field(
        default=None, description="State code to get top species for (e.g., 'NC', 'GA')"
    )
    limit: int = Field(default=10, description="Maximum results to return")


@tool(args_schema=SpeciesLookupInput)
async def lookup_species(
    spcd: int | None = None,
    common_name: str | None = None,
    state: str | None = None,
    limit: int = 10,
) -> str:
    """
    Lookup species information from FIA reference data.

    Use for questions about:
    - What species code 131 is (converts SPCD to common/scientific name)
    - Finding the code for 'loblolly pine' (searches by common name)
    - Top species in North Carolina (lists by volume)
    - Understanding species codes in query results

    Provides three modes:
    1. spcd: Convert species code to names
    2. common_name: Search for species by name
    3. state: List top species by volume in a state
    """
    result = await fia_service.lookup_species(spcd, common_name, state, limit)

    # Check for error
    if "error" in result:
        return f"Error: {result['error']}"

    # Format response based on mode
    mode = result.get("mode")

    if mode == "lookup_by_code":
        if result.get("found"):
            response = f"**Species Code {result['spcd']}**\n"
            response += f"Common Name: {result['common_name']}\n"
            response += f"Scientific Name: {result['scientific_name']}\n"
            if result.get("genus"):
                response += f"Genus: {result['genus']}\n"
            if result.get("species"):
                response += f"Species: {result['species']}\n"
        else:
            response = result.get("message", "Species not found")

    elif mode == "search_by_name":
        if result.get("found"):
            response = f"**Species matching '{result['search_term']}'** ({result['count']} found)\n\n"
            for sp in result["results"]:
                response += f"- **SPCD {sp['spcd']}**: {sp['common_name']}\n"
                response += f"  {sp['scientific_name']}\n"
        else:
            response = result.get("message", "No species found")

    elif mode == "top_species_by_state":
        response = f"**Top {result['count']} Species in {result['state']}** (by timber volume)\n\n"
        for i, sp in enumerate(result["results"], 1):
            response += f"{i}. **{sp['common_name']}** (SPCD {sp['spcd']})\n"
            response += (
                f"   {sp['scientific_name'] or 'Scientific name not available'}\n"
            )
            response += f"   Volume: {sp['volume_cuft']:,.0f} cubic feet\n"

    else:
        response = "Unknown response mode"

    return response


# All available tools
TOOLS = [
    query_forest_area,
    query_timber_volume,
    query_biomass_carbon,
    query_mortality,
    query_removals,
    query_growth,
    query_area_change,
    query_tpa,
    query_by_forest_type,
    compare_states,
    query_by_stand_size,
    query_by_ownership,
    query_by_county,
    lookup_species,
]

# System prompt
SYSTEM_PROMPT = """You are a forest inventory analyst with access to the USDA Forest Service
Forest Inventory and Analysis (FIA) database through pyFIA.

## Your Capabilities

You can query validated forest inventory data including:
- Forest area by state, county, ownership, and forest type
- Timber volume (cubic feet) by species and size class
- Biomass and carbon stocks
- Trees per acre (TPA)
- Annual mortality and growth
- Timber removals/harvest
- Annual area change (forest land gains and losses)
- County-level statistics for all metrics

## Guidelines

1. **Statistical Validity**: All estimates come from pyFIA, which implements proper
   design-based estimation following Bechtold & Patterson (2005).

2. **Standard Errors**: FIA is sample-based. Always note the SE% when reporting.
   SE% < 20% is generally reliable.

3. **State Codes**: Use two-letter abbreviations (NC, GA, OR, etc.)

4. **Always cite** "USDA Forest Service FIA" as the data source.

5. **Be helpful**: Suggest related queries that might interest the user.

## Example Queries You Can Answer

- "How much forest is in North Carolina?"
- "What is the forest area in Wake County, NC?"
- "Compare timber volume in GA, SC, and FL"
- "What are the carbon stocks in Mecklenburg County, North Carolina?"
- "Which state has more biomass: Oregon or Washington?"
- "How many trees per acre are in Fulton County, Georgia?"
"""


class FIAAgent:
    """Agent for handling FIA-related queries."""

    def __init__(self):
        self.llm = ChatAnthropic(
            model="claude-sonnet-4-5-20250929",
            api_key=settings.anthropic_api_key,
            temperature=0,
            max_tokens=4096,
        )
        self.llm_with_tools = self.llm.bind_tools(TOOLS)

    async def stream(
        self,
        messages: list[dict],
        user_id: str | None = None,
        session_id: str | None = None,
    ) -> AsyncGenerator[dict, None]:
        """Stream a response with tool use, supporting multi-turn tool calling."""
        from langchain_core.messages import ToolMessage

        start_time = time.time()
        total_input_tokens = 0
        total_output_tokens = 0
        tool_calls_count = 0
        query_type = None

        # Convert to LangChain message format
        lc_messages = [SystemMessage(content=SYSTEM_PROMPT)]

        for msg in messages:
            if msg["role"] == "user":
                lc_messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                lc_messages.append(AIMessage(content=msg["content"]))

        # Tool execution loop - supports multiple rounds of tool calls
        max_iterations = 10  # Allow complex multi-step queries
        iteration = 0

        while iteration < max_iterations:
            iteration += 1

            # Get response (may include tool calls)
            response = await self.llm_with_tools.ainvoke(lc_messages)

            # Track token usage
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                total_input_tokens += response.usage_metadata.get("input_tokens", 0)
                total_output_tokens += response.usage_metadata.get("output_tokens", 0)

            # Check for tool calls
            if not response.tool_calls:
                # No tool calls - we have the final response
                if query_type is None:
                    query_type = "direct_response"

                # Stream the text response
                content = response.content
                logger.info(f"Response content type: {type(content)}")
                if isinstance(content, str):
                    logger.info(f"Content (first 200 chars): {content[:200]!r}")
                    yield {"type": "text", "content": content}
                elif isinstance(content, list):
                    # Handle list of content blocks - join them to preserve structure
                    logger.info(f"Content is list with {len(content)} blocks")
                    text_parts = []
                    for block in content:
                        if isinstance(block, str):
                            text_parts.append(block)
                        elif hasattr(block, "text"):
                            text_parts.append(block.text)
                        elif isinstance(block, dict) and "text" in block:
                            text_parts.append(block["text"])
                    # Join all text parts and yield as single response
                    full_text = "".join(text_parts)
                    logger.info(
                        f"Joined content (first 200 chars): {full_text[:200]!r}"
                    )
                    yield {"type": "text", "content": full_text}
                break

            # Process tool calls
            tool_calls_count += len(response.tool_calls)
            tool_results = {}

            for tool_call in response.tool_calls:
                # Track query type from first tool call
                if query_type is None:
                    query_type = tool_call["name"]

                yield {
                    "type": "tool_call",
                    "tool_name": tool_call["name"],
                    "tool_call_id": tool_call["id"],
                    "args": tool_call["args"],
                }

                # Execute the tool
                tool_func = {t.name: t for t in TOOLS}.get(tool_call["name"])
                if tool_func:
                    try:
                        result = await tool_func.ainvoke(tool_call["args"])
                        tool_results[tool_call["id"]] = result
                        yield {
                            "type": "tool_result",
                            "tool_call_id": tool_call["id"],
                            "result": result,
                        }
                    except Exception as e:
                        error_result = f"Error: {e}"
                        tool_results[tool_call["id"]] = error_result
                        logger.error(f"Tool execution failed: {e}", exc_info=True)
                        yield {
                            "type": "tool_result",
                            "tool_call_id": tool_call["id"],
                            "result": error_result,
                        }

            # Add assistant response and tool results to messages for next iteration
            lc_messages.append(response)
            for tool_call in response.tool_calls:
                result = tool_results.get(tool_call["id"], "Tool execution failed")
                lc_messages.append(
                    ToolMessage(
                        content=result,
                        tool_call_id=tool_call["id"],
                    )
                )

        # Check if we hit the iteration limit without a final response
        if iteration >= max_iterations:
            logger.warning(f"Hit max_iterations limit ({max_iterations}) without final response")
            yield {
                "type": "text",
                "content": "I apologize, but this query required more steps than expected. "
                "Please try breaking it into simpler questions, or try again with a more specific query.",
            }

        # Calculate latency
        latency_ms = int((time.time() - start_time) * 1000)

        # Record usage
        try:
            await usage_tracker.record(
                model="claude-sonnet-4-5-20250929",
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
                user_id=user_id,
                session_id=session_id,
                tool_calls=tool_calls_count,
                latency_ms=latency_ms,
                query_type=query_type,
            )
        except Exception as e:
            logger.warning(f"Failed to record usage: {e}")

        yield {"type": "finish"}


# Singleton
fia_agent = FIAAgent()

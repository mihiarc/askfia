"""LangChain agent for FIA queries."""

import json
import logging
import time
from typing import AsyncGenerator

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from ..config import settings
from .fia_service import fia_service
from .usage_tracker import usage_tracker

logger = logging.getLogger(__name__)


# ============================================================================
# Tool Definitions
# ============================================================================


# FIA code lookups for human-readable output
# Common forest type codes (FORTYPCD) - subset of most common types
FOREST_TYPES = {
    101: "Jack pine",
    102: "Red pine",
    103: "Eastern white pine",
    104: "Eastern white pine / hemlock",
    105: "Eastern hemlock",
    121: "Balsam fir",
    122: "White spruce",
    123: "Red spruce",
    124: "Red spruce / balsam fir",
    125: "Black spruce",
    126: "Tamarack",
    127: "Northern white-cedar",
    141: "Longleaf pine",
    142: "Slash pine",
    161: "Loblolly pine",
    162: "Shortleaf pine",
    163: "Loblolly pine / hardwood",
    164: "Shortleaf pine / oak",
    165: "Virginia pine",
    166: "Virginia pine / oak",
    167: "Sand pine",
    168: "Table Mountain pine",
    171: "Pitch pine",
    381: "Scotch pine",
    383: "Other exotic softwoods",
    401: "Eastern white pine / N hardwoods",
    402: "Eastern redcedar / hardwood",
    403: "Longleaf pine / oak",
    404: "Shortleaf pine / oak",
    405: "Virginia pine / southern red oak",
    406: "Loblolly pine / hardwood",
    407: "Slash pine / hardwood",
    409: "Other pine / hardwood",
    501: "Post oak / blackjack oak",
    502: "Chestnut oak",
    503: "White oak / red oak / hickory",
    504: "White oak",
    505: "Northern red oak",
    506: "Yellow-poplar / white oak / N red oak",
    507: "Scarlet oak",
    508: "Chestnut oak / black oak / scarlet oak",
    509: "Southern red oak / yellow pine",
    510: "Mixed upland hardwoods",
    511: "Black walnut",
    512: "Black locust",
    513: "Southern scrub oak",
    514: "Yellow-poplar",
    515: "Red maple / northern hardwoods",
    516: "Mixed central hardwoods",
    517: "Elm / ash / locust",
    519: "Red maple / oak",
    520: "Pin oak / sweetgum",
    601: "Swamp chestnut oak / cherrybark oak",
    602: "Sweetgum / yellow-poplar",
    605: "Overcup oak / water hickory",
    606: "Atlantic white-cedar",
    607: "Baldcypress / water tupelo",
    608: "Sweetbay / swamp tupelo / red maple",
    701: "Black ash / American elm / red maple",
    702: "River birch / sycamore",
    703: "Cottonwood",
    704: "Willow",
    705: "Sycamore / pecan / American elm",
    706: "Sugarberry / hackberry / elm / green ash",
    707: "Silver maple / American elm",
    708: "Red maple / lowland",
    709: "Cottonwood / willow",
    801: "Sugar maple / beech / yellow birch",
    802: "Black cherry",
    805: "Hard maple / basswood",
    809: "Red maple / upland",
    901: "Aspen",
    902: "Paper birch",
    904: "Balsam poplar",
    962: "Other hardwoods",
    999: "Nonstocked",
}

OWNERSHIP_GROUPS = {
    10: "National Forest",
    20: "Other federal",
    30: "State & local government",
    40: "Private",
}

STAND_SIZE_CLASSES = {
    1: "Large diameter (>11\" softwood, >9\" hardwood)",
    2: "Medium diameter (5-11\" softwood, 5-9\" hardwood)",
    3: "Small diameter (<5\")",
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
        )
    )


@tool(args_schema=ForestAreaInput)
async def query_forest_area(states: list[str], land_type: str = "forest", grp_by: str | None = None) -> str:
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
        sorted_rows = sorted(result["breakdown"], key=lambda x: x.get('AREA', x.get('ESTIMATE', 0)), reverse=True)

        for row in sorted_rows[:15]:
            code = row.get(grp_by)
            estimate = row.get('AREA', row.get('ESTIMATE', 0))

            # Look up human-readable names
            if grp_by == "FORTYPCD" and code in FOREST_TYPES:
                label = FOREST_TYPES[code]
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
    tree_domain: str | None = Field(default=None, description="Filter (e.g., 'DIA >= 10.0')")


@tool(args_schema=TimberVolumeInput)
async def query_timber_volume(states: list[str], by_species: bool = False, tree_domain: str | None = None) -> str:
    """
    Query timber volume from FIA database.
    
    Use for questions about:
    - How much timber is in a state
    - Volume by species
    - Sawtimber volume (use tree_domain='DIA >= 10.0')
    """
    result = await fia_service.query_volume(states, by_species, tree_domain)
    
    response = f"**Timber Volume**\n"
    response += f"States: {', '.join(states)}\n"
    response += f"Total: {result['total_volume_cuft']:,.0f} cubic feet\n"
    response += f"  ({result['total_volume_billion_cuft']:.2f} billion cu ft)\n"
    response += f"SE: {result['se_percent']:.1f}%\n"
    
    if result.get("by_species"):
        response += "\nTop species:\n"
        sorted_species = sorted(result["by_species"], key=lambda x: x.get("ESTIMATE", 0), reverse=True)
        for row in sorted_species[:10]:
            response += f"- SPCD {row.get('SPCD', '?')}: {row['ESTIMATE']:,.0f} cu ft\n"
    
    return response


class BiomassInput(BaseModel):
    """Input for biomass query."""

    states: list[str] = Field(description="Two-letter state codes")
    land_type: str = Field(default="forest", description="forest or timber")
    by_species: bool = Field(default=False, description="Group by species")


@tool(args_schema=BiomassInput)
async def query_biomass_carbon(states: list[str], land_type: str = "forest", by_species: bool = False) -> str:
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
        sorted_species = sorted(result["by_species"], key=lambda x: x.get("ESTIMATE", 0), reverse=True)
        for row in sorted_species[:5]:
            response += f"- SPCD {row.get('SPCD', '?')}: {row['ESTIMATE']:,.0f} tons\n"
    
    return response


class CompareInput(BaseModel):
    """Input for state comparison."""

    states: list[str] = Field(description="States to compare (2-10)")
    metric: str = Field(description="area, volume, biomass, tpa, mortality, or growth")


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


# All available tools
TOOLS = [
    query_forest_area,
    query_timber_volume,
    query_biomass_carbon,
    compare_states,
]

# System prompt
SYSTEM_PROMPT = """You are a forest inventory analyst with access to the USDA Forest Service 
Forest Inventory and Analysis (FIA) database through pyFIA.

## Your Capabilities

You can query validated forest inventory data including:
- Forest area by state, ownership, and forest type
- Timber volume (cubic feet) by species and size class
- Biomass and carbon stocks
- Trees per acre (TPA)
- Annual mortality and growth

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
- "Compare timber volume in GA, SC, and FL"
- "What are the carbon stocks in California?"
- "Which state has more biomass: Oregon or Washington?"
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
        max_iterations = 5  # Prevent infinite loops
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
                    logger.info(f"Joined content (first 200 chars): {full_text[:200]!r}")
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

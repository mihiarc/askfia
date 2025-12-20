"""LangChain agent for FIA queries."""

import json
import logging
from typing import AsyncGenerator

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from ..config import settings
from .fia_service import fia_service

logger = logging.getLogger(__name__)


# ============================================================================
# Tool Definitions
# ============================================================================


class ForestAreaInput(BaseModel):
    """Input for forest area query."""

    states: list[str] = Field(description="Two-letter state codes (e.g., ['NC', 'GA'])")
    land_type: str = Field(default="forest", description="forest, timber, or reserved")
    grp_by: str | None = Field(default=None, description="Group by column (e.g., OWNGRPCD)")


@tool(args_schema=ForestAreaInput)
async def query_forest_area(states: list[str], land_type: str = "forest", grp_by: str | None = None) -> str:
    """
    Query forest land area from FIA database.
    
    Use for questions about:
    - How much forest land is in a state
    - Forest area by ownership type
    - Timberland vs reserved forest area
    """
    result = await fia_service.query_area(states, land_type, grp_by)
    
    response = f"**Forest Area ({land_type})**\n"
    response += f"States: {', '.join(states)}\n"
    response += f"Total: {result['total_area_acres']:,.0f} acres\n"
    response += f"SE: {result['se_percent']:.1f}%\n"
    
    if result.get("breakdown"):
        response += "\nBreakdown:\n"
        for row in result["breakdown"][:10]:
            response += f"- {row.get(grp_by, 'Unknown')}: {row['ESTIMATE']:,.0f} acres\n"
    
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

    async def stream(self, messages: list[dict]) -> AsyncGenerator[dict, None]:
        """Stream a response with tool use."""
        # Convert to LangChain message format
        lc_messages = [SystemMessage(content=SYSTEM_PROMPT)]
        
        for msg in messages:
            if msg["role"] == "user":
                lc_messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                lc_messages.append(AIMessage(content=msg["content"]))

        # Get response (may include tool calls)
        response = await self.llm_with_tools.ainvoke(lc_messages)

        # Check for tool calls
        if response.tool_calls:
            for tool_call in response.tool_calls:
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
                        yield {
                            "type": "tool_result",
                            "tool_call_id": tool_call["id"],
                            "result": result,
                        }
                    except Exception as e:
                        yield {
                            "type": "tool_result",
                            "tool_call_id": tool_call["id"],
                            "result": f"Error: {e}",
                        }

            # Get final response after tool execution
            # Add tool results to messages and get completion
            lc_messages.append(response)
            for tool_call in response.tool_calls:
                tool_func = {t.name: t for t in TOOLS}.get(tool_call["name"])
                if tool_func:
                    result = await tool_func.ainvoke(tool_call["args"])
                    from langchain_core.messages import ToolMessage
                    lc_messages.append(ToolMessage(
                        content=result,
                        tool_call_id=tool_call["id"],
                    ))

            final_response = await self.llm.ainvoke(lc_messages)
            
            # Stream the text response
            for chunk in final_response.content:
                yield {"type": "text", "content": chunk}
        else:
            # No tool calls, just stream the text
            yield {"type": "text", "content": response.content}

        yield {"type": "finish"}


# Singleton
fia_agent = FIAAgent()

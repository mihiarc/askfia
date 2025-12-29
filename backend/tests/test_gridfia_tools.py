"""Integration tests for GridFIA tools.

These tests verify that the GridFIA integration works correctly,
including the service wrapper, tools, and conditional loading.
"""

import asyncio
import os
import sys

import pytest

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from askfia_api.services.gridfia_service import (
    GRIDFIA_AVAILABLE,
    check_gridfia_available,
)


class TestGridFIAAvailability:
    """Test GridFIA availability detection."""

    def test_gridfia_available_flag(self):
        """Test that GRIDFIA_AVAILABLE is a boolean."""
        assert isinstance(GRIDFIA_AVAILABLE, bool)

    def test_check_gridfia_available(self):
        """Test the check function returns same as flag."""
        assert check_gridfia_available() == GRIDFIA_AVAILABLE


@pytest.mark.skipif(not GRIDFIA_AVAILABLE, reason="GridFIA not installed")
class TestGridFIAService:
    """Test GridFIA service wrapper."""

    def test_service_initialization(self):
        """Test that the service can be initialized."""
        from askfia_api.services.gridfia_service import GridFIAService

        service = GridFIAService()
        assert service is not None
        assert service._api is not None

    def test_location_config(self):
        """Test location configuration retrieval."""
        from askfia_api.services.gridfia_service import GridFIAService

        service = GridFIAService()
        config = service.get_location_config(state="NC", county="Wake")

        assert config is not None
        assert hasattr(config, 'location_name')
        assert hasattr(config, 'location_type')

    @pytest.mark.asyncio
    async def test_list_species(self):
        """Test species listing."""
        from askfia_api.services.gridfia_service import GridFIAService

        service = GridFIAService()
        species = await service.list_species()

        assert isinstance(species, list)
        assert len(species) > 0

        # Check structure of first species
        first = species[0]
        assert "species_code" in first
        assert "common_name" in first
        assert "scientific_name" in first


@pytest.mark.skipif(not GRIDFIA_AVAILABLE, reason="GridFIA not installed")
class TestGridFIATools:
    """Test GridFIA LangChain tools."""

    @pytest.mark.asyncio
    async def test_species_list_tool(self):
        """Test the species list tool."""
        from askfia_api.services.gridfia_tools import query_gridfia_species_list

        result = await query_gridfia_species_list.ainvoke({
            "filter_text": "pine",
            "limit": 10,
        })

        assert isinstance(result, str)
        assert "BIGMAP" in result
        assert "pine" in result.lower() or "Pine" in result

    @pytest.mark.asyncio
    async def test_species_list_tool_no_filter(self):
        """Test the species list tool without filter."""
        from askfia_api.services.gridfia_tools import query_gridfia_species_list

        result = await query_gridfia_species_list.ainvoke({
            "limit": 5,
        })

        assert isinstance(result, str)
        assert "Available Tree Species" in result


@pytest.mark.skipif(not GRIDFIA_AVAILABLE, reason="GridFIA not installed")
class TestAgentIntegration:
    """Test agent integration with GridFIA tools.

    Note: These tests require ANTHROPIC_API_KEY to be set because
    agent.py imports settings at module level.
    """

    def test_tools_registered(self):
        """Test that GridFIA tools are registered in the agent."""
        import os
        if not os.environ.get("ANTHROPIC_API_KEY"):
            pytest.skip("ANTHROPIC_API_KEY not set")

        from askfia_api.services.agent import TOOLS, GRIDFIA_TOOLS

        # Should have GridFIA tools registered
        assert len(GRIDFIA_TOOLS) == 3

        # TOOLS should include both PyFIA and GridFIA
        tool_names = [t.name for t in TOOLS]
        assert "query_gridfia_species_list" in tool_names
        assert "query_species_diversity" in tool_names
        assert "query_gridfia_biomass" in tool_names

    def test_system_prompt_includes_gridfia(self):
        """Test that system prompt includes GridFIA capabilities."""
        import os
        if not os.environ.get("ANTHROPIC_API_KEY"):
            pytest.skip("ANTHROPIC_API_KEY not set")

        from askfia_api.services.agent import SYSTEM_PROMPT

        assert "GridFIA" in SYSTEM_PROMPT
        assert "BIGMAP" in SYSTEM_PROMPT
        assert "diversity" in SYSTEM_PROMPT.lower()


class TestGracefulDegradation:
    """Test graceful degradation when GridFIA is not available."""

    def test_tools_message_when_unavailable(self):
        """Test that tools return appropriate message when GridFIA unavailable."""
        # This test always runs, but the behavior depends on availability
        if not GRIDFIA_AVAILABLE:
            # When GridFIA is not available, importing tools should still work
            from askfia_api.services.gridfia_tools import GRIDFIA_AVAILABLE as tools_flag
            assert tools_flag is False


# Manual test runner for development
async def run_manual_tests():
    """Run manual tests for development verification."""
    print("=" * 60)
    print("GridFIA Integration Tests")
    print("=" * 60)

    print(f"\n1. GridFIA Available: {GRIDFIA_AVAILABLE}")

    if not GRIDFIA_AVAILABLE:
        print("\nGridFIA is not installed. Skipping service tests.")
        print("Install with: pip install askfia-api[gridfia]")
        return

    print("\n2. Testing GridFIA Service...")
    try:
        from askfia_api.services.gridfia_service import GridFIAService
        service = GridFIAService()
        print("   Service initialized successfully")

        # Test species listing
        print("\n3. Testing species listing...")
        species = await service.list_species()
        print(f"   Found {len(species)} species")
        if species:
            print(f"   First species: {species[0]}")

        # Test location config
        print("\n4. Testing location config...")
        config = service.get_location_config(state="NC", county="Durham")
        print(f"   Config location_name: {config.location_name}")
        print(f"   Config location_type: {config.location_type}")

    except Exception as e:
        print(f"   ERROR: {e}")
        import traceback
        traceback.print_exc()

    print("\n5. Testing LangChain Tools...")
    try:
        from askfia_api.services.gridfia_tools import (
            query_gridfia_species_list,
            query_species_diversity,
            query_gridfia_biomass,
        )

        # Test species list tool
        print("\n   5a. Species list tool...")
        result = await query_gridfia_species_list.ainvoke({
            "filter_text": "oak",
            "limit": 5,
        })
        print(f"   Result preview: {result[:200]}...")

    except Exception as e:
        print(f"   ERROR: {e}")
        import traceback
        traceback.print_exc()

    print("\n6. Testing Agent Integration...")
    try:
        from askfia_api.services.agent import TOOLS, GRIDFIA_TOOLS, SYSTEM_PROMPT

        print(f"   Total tools: {len(TOOLS)}")
        print(f"   GridFIA tools: {len(GRIDFIA_TOOLS)}")
        print(f"   GridFIA in system prompt: {'GridFIA' in SYSTEM_PROMPT}")

        tool_names = [t.name for t in TOOLS]
        gridfia_tool_names = [n for n in tool_names if 'gridfia' in n.lower() or 'diversity' in n.lower()]
        print(f"   GridFIA tool names: {gridfia_tool_names}")

    except Exception as e:
        print(f"   ERROR: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("Tests complete")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_manual_tests())

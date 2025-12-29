"""Integration tests for GridFIA tools.

These tests verify that the GridFIA integration works correctly,
including the service wrapper, tools, and conditional loading.
"""

import asyncio
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from askfia_api.services.gridfia_service import (
    GRIDFIA_AVAILABLE,
    check_gridfia_available,
    reset_gridfia_service,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the GridFIA service singleton before each test."""
    reset_gridfia_service()
    yield
    reset_gridfia_service()


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


@pytest.mark.skipif(not GRIDFIA_AVAILABLE, reason="GridFIA not installed")
class TestRasterStatistics:
    """Test the raster statistics computation function."""

    def test_compute_raster_statistics_with_valid_data(self):
        """Test computing statistics from a mock raster file."""
        from askfia_api.services.gridfia_service import _compute_raster_statistics
        import rasterio
        from rasterio.transform import from_bounds

        # Create a temporary GeoTIFF with known values
        with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            # Create test data: 10x10 array with values 1-100
            data = np.arange(1, 101, dtype=np.float32).reshape(10, 10)
            transform = from_bounds(0, 0, 10, 10, 10, 10)

            with rasterio.open(
                tmp_path,
                "w",
                driver="GTiff",
                height=10,
                width=10,
                count=1,
                dtype=np.float32,
                crs="EPSG:4326",
                transform=transform,
            ) as dst:
                dst.write(data, 1)

            # Compute statistics
            stats = _compute_raster_statistics(tmp_path)

            assert stats["count"] == 100
            assert abs(stats["mean"] - 50.5) < 0.01  # Mean of 1-100
            assert abs(stats["min"] - 1.0) < 0.01
            assert abs(stats["max"] - 100.0) < 0.01
            assert stats["std"] > 0  # Should have variance

        finally:
            tmp_path.unlink(missing_ok=True)

    def test_compute_raster_statistics_with_nodata(self):
        """Test that nodata values are properly excluded."""
        from askfia_api.services.gridfia_service import _compute_raster_statistics
        import rasterio
        from rasterio.transform import from_bounds

        with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            # Create test data with nodata values
            data = np.array([[1, 2, -9999], [3, 4, -9999], [5, 6, -9999]], dtype=np.float32)
            transform = from_bounds(0, 0, 3, 3, 3, 3)

            with rasterio.open(
                tmp_path,
                "w",
                driver="GTiff",
                height=3,
                width=3,
                count=1,
                dtype=np.float32,
                crs="EPSG:4326",
                transform=transform,
                nodata=-9999,
            ) as dst:
                dst.write(data, 1)

            stats = _compute_raster_statistics(tmp_path)

            # Should only count valid values (1-6)
            assert stats["count"] == 6
            assert abs(stats["mean"] - 3.5) < 0.01  # Mean of 1-6
            assert abs(stats["min"] - 1.0) < 0.01
            assert abs(stats["max"] - 6.0) < 0.01

        finally:
            tmp_path.unlink(missing_ok=True)


@pytest.mark.skipif(not GRIDFIA_AVAILABLE, reason="GridFIA not installed")
class TestCloudServicePlaceholders:
    """Test the cloud service placeholder classes."""

    def test_cloud_data_service_not_available(self):
        """Test that CloudDataService returns None (not implemented)."""
        from askfia_api.services.gridfia_service import CloudDataService

        service = CloudDataService()
        assert service.is_available() is False

    @pytest.mark.asyncio
    async def test_cloud_data_service_diversity_returns_none(self):
        """Test that diversity lookup returns None."""
        from askfia_api.services.gridfia_service import CloudDataService

        service = CloudDataService()
        result = await service.get_diversity_stats(state="NC", county="Wake")
        assert result is None

    @pytest.mark.asyncio
    async def test_cloud_data_service_biomass_returns_none(self):
        """Test that biomass lookup returns None."""
        from askfia_api.services.gridfia_service import CloudDataService

        service = CloudDataService()
        result = await service.get_biomass_stats(state="NC", county="Wake")
        assert result is None

    def test_tile_service_not_available(self):
        """Test that TileService returns None (not implemented)."""
        from askfia_api.services.gridfia_service import TileService

        service = TileService()
        assert service.is_available() is False

    def test_tile_service_returns_none(self):
        """Test that tile URL returns None."""
        from askfia_api.services.gridfia_service import TileService

        service = TileService()
        result = service.get_tile_url(state="NC", county="Wake", layer="diversity")
        assert result is None


@pytest.mark.skipif(not GRIDFIA_AVAILABLE, reason="GridFIA not installed")
class TestServiceSecurity:
    """Test security features of the GridFIA service."""

    def test_path_traversal_prevention(self):
        """Test that path traversal attacks are prevented."""
        from askfia_api.services.gridfia_service import GridFIAService

        service = GridFIAService()

        # These should be sanitized to safe paths
        path1 = service._get_zarr_path(state="../etc", county="passwd")
        assert ".." not in str(path1)
        assert "etc" in str(path1)  # Sanitized version

        path2 = service._get_zarr_path(state="NC/../../root", county=None)
        assert ".." not in str(path2)


@pytest.mark.skipif(not GRIDFIA_AVAILABLE, reason="GridFIA not installed")
class TestThreadSafeSingleton:
    """Test thread safety of the singleton pattern."""

    def test_singleton_returns_same_instance(self):
        """Test that get_gridfia_service returns the same instance."""
        from askfia_api.services.gridfia_service import get_gridfia_service

        service1 = get_gridfia_service()
        service2 = get_gridfia_service()

        assert service1 is service2

    def test_reset_creates_new_instance(self):
        """Test that reset allows a new instance to be created."""
        from askfia_api.services.gridfia_service import (
            get_gridfia_service,
            reset_gridfia_service,
        )

        service1 = get_gridfia_service()
        reset_gridfia_service()
        service2 = get_gridfia_service()

        # After reset, should be a different instance
        assert service1 is not service2


@pytest.mark.skipif(not GRIDFIA_AVAILABLE, reason="GridFIA not installed")
@pytest.mark.slow
class TestDiversityTool:
    """Test the species diversity tool.

    These tests are marked as slow because they may require data downloads.
    Run with: pytest -m slow
    """

    @pytest.mark.asyncio
    async def test_diversity_tool_invalid_metric(self):
        """Test that invalid metrics return an error message."""
        from askfia_api.services.gridfia_tools import query_species_diversity

        result = await query_species_diversity.ainvoke({
            "state": "NC",
            "county": "Wake",
            "metric": "invalid_metric",
        })

        assert "Invalid metric" in result
        assert "shannon" in result.lower()

    @pytest.mark.asyncio
    async def test_diversity_tool_returns_markdown(self):
        """Test that diversity tool returns properly formatted markdown."""
        from askfia_api.services.gridfia_tools import query_species_diversity

        # Mock the service to avoid actual data downloads
        mock_result = {
            "location": "Wake, NC",
            "metric": "shannon",
            "mean": 1.5,
            "std": 0.3,
            "min": 0.0,
            "max": 2.5,
            "pixel_count": 100000,
            "richness_max": 8,
            "richness_mean": 4.2,
        }

        with patch(
            "askfia_api.services.gridfia_tools.get_gridfia_service"
        ) as mock_get_service:
            mock_service = MagicMock()
            mock_service.query_diversity = AsyncMock(return_value=mock_result)
            mock_get_service.return_value = mock_service

            result = await query_species_diversity.ainvoke({
                "state": "NC",
                "county": "Wake",
                "metric": "shannon",
            })

            assert "Species Diversity Analysis" in result
            assert "Wake" in result
            assert "Shannon" in result
            assert "Mean:" in result
            assert "BIGMAP" in result


@pytest.mark.skipif(not GRIDFIA_AVAILABLE, reason="GridFIA not installed")
@pytest.mark.slow
class TestBiomassTool:
    """Test the biomass query tool.

    These tests are marked as slow because they may require data downloads.
    Run with: pytest -m slow
    """

    @pytest.mark.asyncio
    async def test_biomass_tool_returns_markdown(self):
        """Test that biomass tool returns properly formatted markdown."""
        from askfia_api.services.gridfia_tools import query_gridfia_biomass

        # Mock the service to avoid actual data downloads
        mock_result = {
            "location": "Durham, NC",
            "species": "All Species",
            "mean_biomass_mgha": 120.5,
            "total_biomass_mg": 5000000.0,
            "std": 45.2,
            "min": 0.0,
            "max": 350.0,
            "pixel_count": 50000,
            "area_hectares": 4500.0,
        }

        with patch(
            "askfia_api.services.gridfia_tools.get_gridfia_service"
        ) as mock_get_service:
            mock_service = MagicMock()
            mock_service.query_biomass = AsyncMock(return_value=mock_result)
            mock_get_service.return_value = mock_service

            result = await query_gridfia_biomass.ainvoke({
                "state": "NC",
                "county": "Durham",
            })

            assert "Aboveground Biomass Analysis" in result
            assert "Durham" in result
            assert "Mean biomass" in result
            assert "Mg/ha" in result
            assert "carbon" in result.lower()

    @pytest.mark.asyncio
    async def test_biomass_tool_interpretation_low(self):
        """Test biomass interpretation for low values."""
        from askfia_api.services.gridfia_tools import query_gridfia_biomass

        mock_result = {
            "location": "Test, NC",
            "species": "All Species",
            "mean_biomass_mgha": 30.0,  # Low biomass
            "total_biomass_mg": 100000.0,
            "std": 10.0,
            "min": 0.0,
            "max": 80.0,
            "pixel_count": 5000,
            "area_hectares": 450.0,
        }

        with patch(
            "askfia_api.services.gridfia_tools.get_gridfia_service"
        ) as mock_get_service:
            mock_service = MagicMock()
            mock_service.query_biomass = AsyncMock(return_value=mock_result)
            mock_get_service.return_value = mock_service

            result = await query_gridfia_biomass.ainvoke({
                "state": "NC",
            })

            assert "Low biomass" in result or "young forests" in result.lower()


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

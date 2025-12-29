"""GridFIA integration service for spatial raster analysis.

This module provides a wrapper around the GridFIA library for calculating
species diversity, biomass metrics, and other spatial analyses from
BIGMAP 2018 30m resolution raster data.

The service gracefully degrades when GridFIA is not installed, allowing
the main AskFIA application to function without spatial analysis capabilities.
"""

import asyncio
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Graceful degradation - check if GridFIA is available
try:
    from gridfia import GridFIA
    from gridfia.utils.location_config import LocationConfig

    GRIDFIA_AVAILABLE = True
    logger.info("GridFIA is available - spatial analysis tools enabled")
except ImportError:
    GRIDFIA_AVAILABLE = False
    GridFIA = None  # type: ignore
    LocationConfig = None  # type: ignore
    logger.info("GridFIA is not installed - spatial analysis tools disabled")


def check_gridfia_available() -> bool:
    """Check if GridFIA is installed and available."""
    return GRIDFIA_AVAILABLE


class GridFIAService:
    """Service wrapper for GridFIA spatial analysis operations.

    This service provides async-compatible methods for:
    - Listing available species
    - Calculating diversity metrics (Shannon, Simpson, richness)
    - Calculating biomass statistics
    - Managing location configurations and data caching

    All CPU-bound operations are executed in a thread pool to avoid
    blocking the async event loop.
    """

    def __init__(self, cache_dir: str | Path = "./data/gridfia_cache"):
        """Initialize the GridFIA service.

        Args:
            cache_dir: Directory for caching downloaded data and Zarr stores.

        Raises:
            ImportError: If GridFIA is not installed.
        """
        if not GRIDFIA_AVAILABLE:
            raise ImportError(
                "GridFIA is not installed. Install with: pip install askfia-api[gridfia]"
            )
        self._api = GridFIA()
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"GridFIA service initialized with cache at {self._cache_dir}")

    @lru_cache(maxsize=100)
    def _get_location_config_cached(
        self, state: str, county: str | None = None
    ) -> "LocationConfig":
        """Get cached location configuration.

        Args:
            state: State name or two-letter abbreviation.
            county: Optional county name.

        Returns:
            LocationConfig object with bounding boxes and CRS info.
        """
        return self._api.get_location_config(state=state, county=county)

    def get_location_config(
        self, state: str, county: str | None = None
    ) -> "LocationConfig":
        """Get location configuration for a state/county.

        Args:
            state: State name or two-letter abbreviation (e.g., 'NC', 'North Carolina').
            county: Optional county name (e.g., 'Wake', 'Wake County').

        Returns:
            LocationConfig with bounding boxes, CRS, and metadata.
        """
        return self._get_location_config_cached(state, county)

    async def list_species(self) -> list[dict[str, str]]:
        """List all available tree species from BIGMAP.

        Returns:
            List of species dictionaries with keys:
            - species_code: 4-digit FIA species code
            - common_name: Common name (e.g., 'Loblolly Pine')
            - scientific_name: Scientific name (e.g., 'Pinus taeda')
        """
        loop = asyncio.get_event_loop()
        species_list = await loop.run_in_executor(None, self._api.list_species)

        return [
            {
                "species_code": s.species_code,
                "common_name": s.common_name,
                "scientific_name": s.scientific_name,
            }
            for s in species_list
        ]

    def _get_zarr_path(self, state: str, county: str | None = None) -> Path:
        """Get the path to the Zarr store for a location.

        Args:
            state: State name or abbreviation.
            county: Optional county name.

        Returns:
            Path to the Zarr store.
        """
        if county:
            safe_county = county.lower().replace(" ", "_").replace("county", "").strip()
            safe_state = state.lower().replace(" ", "_")
            return self._cache_dir / f"{safe_state}_{safe_county}.zarr"
        else:
            safe_state = state.lower().replace(" ", "_")
            return self._cache_dir / f"{safe_state}.zarr"

    def _ensure_zarr_exists(self, state: str, county: str | None = None) -> Path:
        """Ensure Zarr store exists for location, downloading if necessary.

        This method checks if a Zarr store exists for the given location.
        If not, it downloads the species data and creates the store.

        Args:
            state: State name or abbreviation.
            county: Optional county name.

        Returns:
            Path to the Zarr store.
        """
        zarr_path = self._get_zarr_path(state, county)

        if zarr_path.exists():
            logger.info(f"Using existing Zarr store: {zarr_path}")
            return zarr_path

        logger.info(f"Zarr store not found, downloading data for {state} {county or ''}")

        # Get location config
        config = self.get_location_config(state, county)

        # Create download directory
        download_dir = self._cache_dir / "downloads" / zarr_path.stem
        download_dir.mkdir(parents=True, exist_ok=True)

        # Download species data
        downloaded_files = self._api.download_species(
            output_dir=download_dir,
            state=state,
            county=county,
        )

        if not downloaded_files:
            raise RuntimeError(f"No species data downloaded for {state} {county or ''}")

        logger.info(f"Downloaded {len(downloaded_files)} species files")

        # Create Zarr store
        zarr_path = self._api.create_zarr(
            input_dir=download_dir,
            output_path=zarr_path,
        )

        logger.info(f"Created Zarr store: {zarr_path}")
        return zarr_path

    async def query_diversity(
        self,
        state: str,
        county: str | None = None,
        metric: str = "shannon",
    ) -> dict[str, Any]:
        """Calculate species diversity metrics for a location.

        Args:
            state: State name or two-letter abbreviation.
            county: Optional county name for finer resolution.
            metric: Diversity metric to calculate. Options:
                - 'shannon': Shannon diversity index (H')
                - 'simpson': Simpson diversity index (D)
                - 'richness': Species richness (count of species)

        Returns:
            Dictionary containing:
            - location: Human-readable location name
            - metric: The metric calculated
            - mean: Mean value across all pixels
            - std: Standard deviation
            - min: Minimum value
            - max: Maximum value
            - richness_max: Maximum species count (if applicable)
            - pixel_count: Number of forested pixels analyzed
        """
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, self._calculate_diversity_sync, state, county, metric
        )
        return result

    def _calculate_diversity_sync(
        self, state: str, county: str | None, metric: str
    ) -> dict[str, Any]:
        """Synchronous diversity calculation (runs in thread pool).

        Args:
            state: State name or abbreviation.
            county: Optional county name.
            metric: Diversity metric name.

        Returns:
            Dictionary with diversity statistics.
        """
        # Ensure Zarr store exists
        zarr_path = self._ensure_zarr_exists(state, county)

        # Map metric name to calculation name
        calc_map = {
            "shannon": "shannon_diversity",
            "simpson": "simpson_diversity",
            "richness": "species_richness",
        }

        if metric not in calc_map:
            raise ValueError(
                f"Unknown metric: {metric}. Valid options: {list(calc_map.keys())}"
            )

        calculations = [calc_map[metric]]

        # Always include richness for context
        if metric != "richness":
            calculations.append("species_richness")

        # Run calculations
        results = self._api.calculate_metrics(
            zarr_path=zarr_path,
            calculations=calculations,
        )

        # Extract statistics
        primary_result = results[0]
        stats = primary_result.statistics

        # Use location_name from config if available, otherwise construct it
        location_name = f"{county}, {state}" if county else state

        response = {
            "location": location_name,
            "metric": metric,
            "mean": stats.get("mean", 0.0),
            "std": stats.get("std", 0.0),
            "min": stats.get("min", 0.0),
            "max": stats.get("max", 0.0),
            "pixel_count": stats.get("count", 0),
        }

        # Add richness if calculated separately
        if len(results) > 1:
            richness_stats = results[1].statistics
            response["richness_max"] = int(richness_stats.get("max", 0))
            response["richness_mean"] = richness_stats.get("mean", 0.0)

        return response

    async def query_biomass(
        self,
        state: str,
        county: str | None = None,
        species_code: str | None = None,
    ) -> dict[str, Any]:
        """Calculate biomass statistics for a location.

        Args:
            state: State name or two-letter abbreviation.
            county: Optional county name for finer resolution.
            species_code: Optional 4-digit species code for species-specific biomass.
                If None, calculates total biomass across all species.

        Returns:
            Dictionary containing:
            - location: Human-readable location name
            - species: Species name if species_code provided, else 'All Species'
            - mean_biomass_mgha: Mean biomass in Mg/ha (megagrams per hectare)
            - total_biomass_mg: Estimated total biomass in Mg
            - std: Standard deviation of biomass
            - min: Minimum biomass value
            - max: Maximum biomass value
            - pixel_count: Number of pixels analyzed
        """
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, self._calculate_biomass_sync, state, county, species_code
        )
        return result

    def _calculate_biomass_sync(
        self, state: str, county: str | None, species_code: str | None
    ) -> dict[str, Any]:
        """Synchronous biomass calculation (runs in thread pool).

        Args:
            state: State name or abbreviation.
            county: Optional county name.
            species_code: Optional species code for species-specific analysis.

        Returns:
            Dictionary with biomass statistics.
        """
        # Ensure Zarr store exists
        zarr_path = self._ensure_zarr_exists(state, county)

        # Run total biomass calculation
        results = self._api.calculate_metrics(
            zarr_path=zarr_path,
            calculations=["total_biomass"],
        )

        stats = results[0].statistics
        location_name = f"{county}, {state}" if county else state

        # Calculate estimated total (mean * pixel_count * pixel_area)
        # BIGMAP is 30m resolution, so each pixel is 0.09 ha
        pixel_area_ha = 0.09
        pixel_count = stats.get("count", 0)
        mean_biomass = stats.get("mean", 0.0)
        total_biomass = mean_biomass * pixel_count * pixel_area_ha

        response = {
            "location": location_name,
            "species": "All Species" if not species_code else species_code,
            "mean_biomass_mgha": mean_biomass,
            "total_biomass_mg": total_biomass,
            "std": stats.get("std", 0.0),
            "min": stats.get("min", 0.0),
            "max": stats.get("max", 0.0),
            "pixel_count": pixel_count,
            "area_hectares": pixel_count * pixel_area_ha,
        }

        return response


# Singleton instance - created lazily to allow graceful degradation
_gridfia_service: GridFIAService | None = None


def get_gridfia_service() -> GridFIAService:
    """Get or create the GridFIA service singleton.

    Returns:
        GridFIAService instance.

    Raises:
        ImportError: If GridFIA is not installed.
    """
    global _gridfia_service
    if _gridfia_service is None:
        _gridfia_service = GridFIAService()
    return _gridfia_service

"""GridFIA integration service for spatial raster analysis.

This module provides a wrapper around the GridFIA library for calculating
species diversity, biomass metrics, and other spatial analyses from
BIGMAP 2018 30m resolution raster data.

The service gracefully degrades when GridFIA is not installed, allowing
the main AskFIA application to function without spatial analysis capabilities.

Architecture:
- GridFIAService: Main service wrapper with async support
- CloudDataService: Placeholder for cloud-hosted pre-computed data (Phase 2)
- TileService: Placeholder for TiTiler integration (Phase 3)
"""

import asyncio
import logging
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# Graceful degradation - check if GridFIA is available
try:
    from gridfia import GridFIA
    from gridfia.utils.location_config import LocationConfig
    import rasterio

    GRIDFIA_AVAILABLE = True
    logger.info("GridFIA is available - spatial analysis tools enabled")
except ImportError:
    GRIDFIA_AVAILABLE = False
    GridFIA = None  # type: ignore
    LocationConfig = None  # type: ignore
    rasterio = None  # type: ignore
    logger.info("GridFIA is not installed - spatial analysis tools disabled")


# Constants
PIXEL_AREA_HA = 0.09  # 30m x 30m = 900 sq m = 0.09 ha
HA_TO_ACRES = 2.471
DEFAULT_SPECIES_FOR_DIVERSITY = [
    "0131",  # Loblolly pine
    "0110",  # Shortleaf pine
    "0121",  # Longleaf pine
    "0802",  # White oak
    "0833",  # Red oak
    "0316",  # Red maple
    "0621",  # Sweetgum
    "0611",  # American beech
    "0541",  # Black cherry
    "0971",  # American elm
]


def check_gridfia_available() -> bool:
    """Check if GridFIA is installed and available."""
    return GRIDFIA_AVAILABLE


class CloudDataService:
    """Placeholder for cloud-hosted pre-computed data service.

    Phase 2 will implement:
    - Pre-computed diversity/biomass statistics for all US counties
    - Cloud storage (R2/S3) for Zarr stores and COGs
    - Fast lookups without local data download

    For now, returns None to indicate cloud data is not available,
    falling back to local GridFIA processing.
    """

    def __init__(self, base_url: str | None = None):
        """Initialize cloud data service.

        Args:
            base_url: Base URL for cloud data API (e.g., https://data.fiatools.org)
        """
        self.base_url = base_url
        self._available = False  # Will be True when implemented

    async def get_diversity_stats(
        self,
        state: str,
        county: str | None = None,
        metric: str = "shannon"
    ) -> dict[str, Any] | None:
        """Get pre-computed diversity statistics from cloud.

        Returns None if cloud data not available (falls back to local).

        Phase 2 implementation will:
        - Query pre-computed stats from cloud API
        - Return cached statistics instantly
        - Support all US states and counties
        """
        # TODO: Implement cloud data lookup
        return None

    async def get_biomass_stats(
        self,
        state: str,
        county: str | None = None
    ) -> dict[str, Any] | None:
        """Get pre-computed biomass statistics from cloud.

        Returns None if cloud data not available (falls back to local).
        """
        # TODO: Implement cloud data lookup
        return None

    def is_available(self) -> bool:
        """Check if cloud data service is available."""
        return self._available


class TileService:
    """Placeholder for TiTiler dynamic tile service integration.

    Phase 3 will implement:
    - Dynamic tile generation from Cloud Optimized GeoTIFFs (COGs)
    - Integration with TiTiler for map visualization
    - Tile URLs for frontend map rendering

    For now, returns None to indicate tiles are not available.
    """

    def __init__(self, titiler_url: str | None = None):
        """Initialize tile service.

        Args:
            titiler_url: Base URL for TiTiler instance
        """
        self.titiler_url = titiler_url
        self._available = False  # Will be True when implemented

    def get_tile_url(
        self,
        state: str,
        county: str | None = None,
        layer: str = "diversity"
    ) -> str | None:
        """Get tile URL for map visualization.

        Returns None if tile service not available.

        Phase 3 implementation will return URLs like:
        https://tiles.fiatools.org/cog/tiles/{z}/{x}/{y}.png?url=...
        """
        # TODO: Implement TiTiler URL generation
        return None

    def is_available(self) -> bool:
        """Check if tile service is available."""
        return self._available


def _compute_raster_statistics(raster_path: Path) -> dict[str, float]:
    """Compute statistics from a GeoTIFF raster file.

    Args:
        raster_path: Path to the GeoTIFF file.

    Returns:
        Dictionary with mean, std, min, max, count statistics.
    """
    if rasterio is None:
        return {}

    with rasterio.open(raster_path) as src:
        data = src.read(1)  # Read first band
        nodata = src.nodata

        # Mask nodata values
        if nodata is not None:
            valid_data = data[data != nodata]
        else:
            valid_data = data[~np.isnan(data)]

        if len(valid_data) == 0:
            return {
                "mean": 0.0,
                "std": 0.0,
                "min": 0.0,
                "max": 0.0,
                "count": 0,
            }

        return {
            "mean": float(np.mean(valid_data)),
            "std": float(np.std(valid_data)),
            "min": float(np.min(valid_data)),
            "max": float(np.max(valid_data)),
            "count": int(len(valid_data)),
        }


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

        # Cloud services (placeholders for Phase 2/3)
        self._cloud_service = CloudDataService()
        self._tile_service = TileService()

        logger.info(f"GridFIA service initialized with cache at {self._cache_dir}")

    @lru_cache(maxsize=100)
    def _get_location_config_cached(
        self, state: str, county: str | None = None
    ) -> "LocationConfig":
        """Get cached location configuration."""
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
        loop = asyncio.get_running_loop()
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

        Uses secure path construction to prevent path traversal.
        """
        # Sanitize inputs to prevent path traversal
        safe_state = "".join(c for c in state.lower() if c.isalnum() or c == "_")

        if county:
            safe_county = "".join(c for c in county.lower() if c.isalnum() or c == "_")
            filename = f"{safe_state}_{safe_county}.zarr"
        else:
            filename = f"{safe_state}.zarr"

        # Ensure path stays within cache directory
        zarr_path = (self._cache_dir / filename).resolve()
        if not str(zarr_path).startswith(str(self._cache_dir.resolve())):
            raise ValueError("Invalid location name - path traversal detected")

        return zarr_path

    def _ensure_zarr_exists(
        self,
        state: str,
        county: str | None = None,
        species_codes: list[str] | None = None
    ) -> Path:
        """Ensure Zarr store exists for location, downloading if necessary.

        Args:
            state: State name or abbreviation.
            county: Optional county name.
            species_codes: Optional list of species to download. If None,
                downloads a default subset for diversity calculations.
        """
        zarr_path = self._get_zarr_path(state, county)

        if zarr_path.exists():
            logger.info(f"Using existing Zarr store: {zarr_path}")
            return zarr_path

        logger.info(f"Zarr store not found, downloading data for {state} {county or ''}")

        # Create download directory
        download_dir = self._cache_dir / "downloads" / zarr_path.stem
        download_dir.mkdir(parents=True, exist_ok=True)

        # Use subset of species for faster downloads if not specified
        # Full downloads can be 1GB+, this reduces to ~100MB
        if species_codes is None:
            species_codes = DEFAULT_SPECIES_FOR_DIVERSITY
            logger.info(f"Using default species subset ({len(species_codes)} species)")

        # Download species data
        downloaded_files = self._api.download_species(
            output_dir=download_dir,
            state=state,
            county=county,
            species_codes=species_codes,
        )

        if not downloaded_files:
            raise RuntimeError(
                f"No species data downloaded for {state} {county or ''}. "
                "The region may not have BIGMAP coverage."
            )

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
            Dictionary containing diversity statistics and metadata.
        """
        # Try cloud data first (Phase 2)
        cloud_result = await self._cloud_service.get_diversity_stats(state, county, metric)
        if cloud_result is not None:
            return cloud_result

        # Fall back to local calculation
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, self._calculate_diversity_sync, state, county, metric
        )
        return result

    def _calculate_diversity_sync(
        self, state: str, county: str | None, metric: str
    ) -> dict[str, Any]:
        """Synchronous diversity calculation (runs in thread pool)."""
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

        # Ensure Zarr store exists
        zarr_path = self._ensure_zarr_exists(state, county)

        calculations = [calc_map[metric]]
        if metric != "richness":
            calculations.append("species_richness")

        # Run calculations
        results = self._api.calculate_metrics(
            zarr_path=zarr_path,
            calculations=calculations,
        )

        if not results:
            raise RuntimeError(f"No calculation results for {state} {county or ''}")

        # FIX: Compute statistics from output raster files
        # The API returns empty statistics, so we compute them ourselves
        primary_result = results[0]
        stats = _compute_raster_statistics(primary_result.output_path)

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
            richness_stats = _compute_raster_statistics(results[1].output_path)
            response["richness_max"] = int(richness_stats.get("max", 0))
            response["richness_mean"] = richness_stats.get("mean", 0.0)

        # Add tile URL if available (Phase 3)
        tile_url = self._tile_service.get_tile_url(state, county, f"{metric}_diversity")
        if tile_url:
            response["tile_url"] = tile_url

        return response

    async def query_biomass(
        self,
        state: str,
        county: str | None = None,
    ) -> dict[str, Any]:
        """Calculate biomass statistics for a location.

        Args:
            state: State name or two-letter abbreviation.
            county: Optional county name for finer resolution.

        Returns:
            Dictionary containing biomass statistics and metadata.
        """
        # Try cloud data first (Phase 2)
        cloud_result = await self._cloud_service.get_biomass_stats(state, county)
        if cloud_result is not None:
            return cloud_result

        # Fall back to local calculation
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, self._calculate_biomass_sync, state, county
        )
        return result

    def _calculate_biomass_sync(
        self, state: str, county: str | None
    ) -> dict[str, Any]:
        """Synchronous biomass calculation (runs in thread pool)."""
        # Ensure Zarr store exists
        zarr_path = self._ensure_zarr_exists(state, county)

        # Run total biomass calculation
        results = self._api.calculate_metrics(
            zarr_path=zarr_path,
            calculations=["total_biomass"],
        )

        if not results:
            raise RuntimeError(f"No calculation results for {state} {county or ''}")

        # FIX: Compute statistics from output raster file
        stats = _compute_raster_statistics(results[0].output_path)

        location_name = f"{county}, {state}" if county else state

        # Calculate totals
        pixel_count = stats.get("count", 0)
        mean_biomass = stats.get("mean", 0.0)
        total_biomass = mean_biomass * pixel_count * PIXEL_AREA_HA
        area_hectares = pixel_count * PIXEL_AREA_HA

        response = {
            "location": location_name,
            "species": "All Species",
            "mean_biomass_mgha": mean_biomass,
            "total_biomass_mg": total_biomass,
            "std": stats.get("std", 0.0),
            "min": stats.get("min", 0.0),
            "max": stats.get("max", 0.0),
            "pixel_count": pixel_count,
            "area_hectares": area_hectares,
        }

        # Add tile URL if available (Phase 3)
        tile_url = self._tile_service.get_tile_url(state, county, "biomass")
        if tile_url:
            response["tile_url"] = tile_url

        return response


# Thread-safe singleton implementation
_gridfia_service: GridFIAService | None = None
_gridfia_service_lock = threading.Lock()


def get_gridfia_service() -> GridFIAService:
    """Get or create the GridFIA service singleton (thread-safe).

    Returns:
        GridFIAService instance.

    Raises:
        ImportError: If GridFIA is not installed.
    """
    global _gridfia_service

    if _gridfia_service is None:
        with _gridfia_service_lock:
            # Double-check locking pattern
            if _gridfia_service is None:
                _gridfia_service = GridFIAService()

    return _gridfia_service


def reset_gridfia_service() -> None:
    """Reset the GridFIA service singleton (for testing)."""
    global _gridfia_service
    with _gridfia_service_lock:
        _gridfia_service = None

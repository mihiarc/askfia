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
    """Cloud-hosted data service using GridFIA's B2 streaming.

    Streams forest data directly from Backblaze B2 for states that have
    pre-processed Zarr stores available. For states not yet in cloud,
    falls back to local GridFIA processing.

    Currently available states: RI (Rhode Island)
    """

    def __init__(self, gridfia_api: "GridFIA | None" = None):
        """Initialize cloud data service.

        Args:
            gridfia_api: GridFIA API instance for cloud access.
        """
        self._api = gridfia_api
        self._available_states: set[str] = set()
        self._store_cache: dict[str, Any] = {}  # Cache loaded stores

        # Determine available states from GridFIA config
        if self._api is not None:
            try:
                self._available_states = set(self._api._STATE_METADATA.keys())
                logger.info(f"Cloud states available: {self._available_states}")
            except Exception as e:
                logger.warning(f"Could not get cloud state list: {e}")

    def _normalize_state(self, state: str) -> str | None:
        """Normalize state name to abbreviation.

        Returns None if state not recognized.
        """
        # Common state name to abbreviation mapping
        STATE_ABBREVS = {
            "rhode island": "RI",
            "connecticut": "CT",
            "ri": "RI",
            "ct": "CT",
        }
        state_lower = state.lower().strip()
        return STATE_ABBREVS.get(state_lower, state.upper() if len(state) == 2 else None)

    def is_state_available(self, state: str) -> bool:
        """Check if state data is available in cloud."""
        abbr = self._normalize_state(state)
        return abbr is not None and abbr in self._available_states

    def _get_cloud_store(self, state: str) -> Any | None:
        """Get ZarrStore for a state from cloud, with caching."""
        abbr = self._normalize_state(state)
        if abbr is None or abbr not in self._available_states:
            return None

        if abbr not in self._store_cache:
            try:
                logger.info(f"Loading {abbr} from cloud storage...")
                self._store_cache[abbr] = self._api.load_state(abbr)
                logger.info(f"Loaded {abbr} cloud store: {self._store_cache[abbr].shape}")
            except Exception as e:
                logger.warning(f"Failed to load {abbr} from cloud: {e}")
                return None

        return self._store_cache[abbr]

    async def get_diversity_stats(
        self,
        state: str,
        county: str | None = None,
        metric: str = "shannon"
    ) -> dict[str, Any] | None:
        """Get diversity statistics from cloud-streamed data.

        Returns None if state not available in cloud (falls back to local).
        County-level queries are not yet supported for cloud data.
        """
        # County queries fall back to local processing for now
        if county is not None:
            return None

        if not self.is_state_available(state):
            return None

        store = self._get_cloud_store(state)
        if store is None:
            return None

        # Calculate diversity from streamed data
        try:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None, self._calculate_diversity_sync, store, state, metric
            )
            return result
        except Exception as e:
            logger.error(f"Error calculating diversity from cloud: {e}")
            return None

    def _calculate_diversity_sync(
        self, store: Any, state: str, metric: str
    ) -> dict[str, Any]:
        """Synchronous diversity calculation from ZarrStore."""
        abbr = self._normalize_state(state)
        location_name = self._api._STATE_METADATA.get(abbr, {}).get("name", state)

        # Get biomass data and calculate diversity
        biomass = store.biomass[:]  # Shape: (species, rows, cols)

        # Calculate presence (biomass > 0)
        presence = (biomass > 0).astype(np.float32)

        # Calculate metric
        if metric == "richness":
            # Count of species per pixel
            diversity = np.sum(presence, axis=0)
        elif metric == "shannon":
            # Shannon diversity index
            total = np.sum(biomass, axis=0)
            total = np.where(total > 0, total, 1)  # Avoid division by zero
            proportions = biomass / total
            # Only compute where proportion > 0
            log_p = np.where(proportions > 0, np.log(proportions), 0)
            diversity = -np.sum(proportions * log_p, axis=0)
        elif metric == "simpson":
            # Simpson diversity index (1 - D)
            total = np.sum(biomass, axis=0)
            total = np.where(total > 0, total, 1)
            proportions = biomass / total
            diversity = 1 - np.sum(proportions ** 2, axis=0)
        else:
            raise ValueError(f"Unknown metric: {metric}")

        # Mask out non-forest pixels (where all species are 0)
        forest_mask = np.sum(presence, axis=0) > 0
        valid_diversity = diversity[forest_mask]

        # Calculate richness stats for all metrics
        richness = np.sum(presence, axis=0)
        valid_richness = richness[forest_mask]

        return {
            "location": location_name,
            "metric": metric,
            "mean": float(np.mean(valid_diversity)) if len(valid_diversity) > 0 else 0.0,
            "std": float(np.std(valid_diversity)) if len(valid_diversity) > 0 else 0.0,
            "min": float(np.min(valid_diversity)) if len(valid_diversity) > 0 else 0.0,
            "max": float(np.max(valid_diversity)) if len(valid_diversity) > 0 else 0.0,
            "pixel_count": int(np.sum(forest_mask)),
            "richness_mean": float(np.mean(valid_richness)) if len(valid_richness) > 0 else 0.0,
            "richness_max": int(np.max(valid_richness)) if len(valid_richness) > 0 else 0,
            "source": "cloud",
        }

    async def get_biomass_stats(
        self,
        state: str,
        county: str | None = None
    ) -> dict[str, Any] | None:
        """Get biomass statistics from cloud-streamed data.

        Returns None if state not available in cloud (falls back to local).
        """
        if county is not None:
            return None

        if not self.is_state_available(state):
            return None

        store = self._get_cloud_store(state)
        if store is None:
            return None

        try:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None, self._calculate_biomass_sync, store, state
            )
            return result
        except Exception as e:
            logger.error(f"Error calculating biomass from cloud: {e}")
            return None

    def _calculate_biomass_sync(self, store: Any, state: str) -> dict[str, Any]:
        """Synchronous biomass calculation from ZarrStore."""
        abbr = self._normalize_state(state)
        location_name = self._api._STATE_METADATA.get(abbr, {}).get("name", state)

        # Get total biomass (sum across species)
        biomass = store.biomass[:]  # Shape: (species, rows, cols)
        total_biomass = np.sum(biomass, axis=0)

        # Mask non-forest pixels
        forest_mask = total_biomass > 0
        valid_biomass = total_biomass[forest_mask]

        # Calculate pixel area (30m resolution = 0.09 ha)
        pixel_area_ha = 0.09
        area_hectares = int(np.sum(forest_mask)) * pixel_area_ha

        return {
            "location": location_name,
            "mean_biomass_mgha": float(np.mean(valid_biomass)) if len(valid_biomass) > 0 else 0.0,
            "std": float(np.std(valid_biomass)) if len(valid_biomass) > 0 else 0.0,
            "min": float(np.min(valid_biomass)) if len(valid_biomass) > 0 else 0.0,
            "max": float(np.max(valid_biomass)) if len(valid_biomass) > 0 else 0.0,
            "total_biomass_mg": float(np.sum(valid_biomass) * pixel_area_ha),
            "pixel_count": int(np.sum(forest_mask)),
            "area_hectares": area_hectares,
            "source": "cloud",
        }

    def is_available(self) -> bool:
        """Check if cloud data service is available."""
        return len(self._available_states) > 0


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

        # Cloud services - pass API for B2 streaming
        self._cloud_service = CloudDataService(gridfia_api=self._api)
        self._tile_service = TileService()

        logger.info(f"GridFIA service initialized with cache at {self._cache_dir}")
        if self._cloud_service.is_available():
            logger.info(f"Cloud streaming enabled for states: {self._cloud_service._available_states}")

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


class GridFIAServiceExtended(GridFIAService):
    """Extended service with additional query methods for full implementation.

    Adds:
    - query_dominant_species: Find the dominant species in a location
    - compare_locations: Compare diversity/biomass between locations
    - query_species_biomass: Query biomass for specific species
    - list_calculations: List available calculations
    """

    async def query_dominant_species(
        self,
        state: str,
        county: str | None = None,
        top_n: int = 5,
    ) -> dict[str, Any]:
        """Find the dominant tree species in a location by biomass.

        Args:
            state: State name or two-letter abbreviation.
            county: Optional county name for finer resolution.
            top_n: Number of top species to return (default 5).

        Returns:
            Dictionary containing dominant species information.
        """
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, self._calculate_dominant_species_sync, state, county, top_n
        )
        return result

    def _calculate_dominant_species_sync(
        self, state: str, county: str | None, top_n: int
    ) -> dict[str, Any]:
        """Synchronous dominant species calculation (runs in thread pool)."""
        # Ensure Zarr store exists
        zarr_path = self._ensure_zarr_exists(state, county)

        import zarr
        import numpy as np

        # Open the Zarr store and analyze species biomass
        store = zarr.open(zarr_path, mode='r')
        biomass = store['biomass'][:]

        # Get species codes and names
        species_codes = list(store['species_codes'][:])
        species_names = list(store['species_names'][:])

        # Calculate total biomass per species (excluding nodata)
        species_totals = []
        for i in range(len(species_codes)):
            if species_codes[i] == '0000':  # Skip total biomass layer
                continue
            layer = biomass[i]
            valid_mask = (layer > 0) & (layer != -9999)
            total = float(np.sum(layer[valid_mask])) if np.any(valid_mask) else 0.0
            mean = float(np.mean(layer[valid_mask])) if np.any(valid_mask) else 0.0
            pixel_count = int(np.sum(valid_mask))

            if total > 0:
                species_totals.append({
                    'species_code': species_codes[i],
                    'species_name': species_names[i] if i < len(species_names) else 'Unknown',
                    'total_biomass_mg': total * PIXEL_AREA_HA,  # Convert to Mg
                    'mean_biomass_mgha': mean,
                    'pixel_count': pixel_count,
                })

        # Sort by total biomass and get top N
        species_totals.sort(key=lambda x: x['total_biomass_mg'], reverse=True)
        top_species = species_totals[:top_n]

        location_name = f"{county}, {state}" if county else state

        return {
            "location": location_name,
            "top_n": top_n,
            "total_species_present": len(species_totals),
            "dominant_species": top_species,
        }

    async def compare_locations(
        self,
        location1: dict[str, str],
        location2: dict[str, str],
        metric: str = "diversity",
    ) -> dict[str, Any]:
        """Compare two locations by diversity or biomass.

        Args:
            location1: Dict with 'state' and optional 'county' keys.
            location2: Dict with 'state' and optional 'county' keys.
            metric: 'diversity' (Shannon index) or 'biomass'.

        Returns:
            Dictionary containing comparison results.
        """
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            self._compare_locations_sync,
            location1,
            location2,
            metric
        )
        return result

    def _compare_locations_sync(
        self,
        location1: dict[str, str],
        location2: dict[str, str],
        metric: str,
    ) -> dict[str, Any]:
        """Synchronous location comparison (runs in thread pool)."""
        results = {}

        for i, loc in enumerate([location1, location2], 1):
            state = loc['state']
            county = loc.get('county')

            zarr_path = self._ensure_zarr_exists(state, county)

            if metric == "diversity":
                # Run Shannon diversity calculation
                calc_results = self._api.calculate_metrics(
                    zarr_path=zarr_path,
                    calculations=["shannon_diversity"],
                )
                stats = _compute_raster_statistics(calc_results[0].output_path)
            else:  # biomass
                calc_results = self._api.calculate_metrics(
                    zarr_path=zarr_path,
                    calculations=["total_biomass"],
                )
                stats = _compute_raster_statistics(calc_results[0].output_path)

            location_name = f"{county}, {state}" if county else state
            results[f"location{i}"] = {
                "name": location_name,
                "mean": stats.get("mean", 0.0),
                "std": stats.get("std", 0.0),
                "min": stats.get("min", 0.0),
                "max": stats.get("max", 0.0),
                "pixel_count": stats.get("count", 0),
            }

        # Calculate comparison metrics
        loc1 = results["location1"]
        loc2 = results["location2"]

        difference = loc1["mean"] - loc2["mean"]
        if loc2["mean"] != 0:
            percent_difference = (difference / loc2["mean"]) * 100
        else:
            percent_difference = 0.0 if loc1["mean"] == 0 else float('inf')

        return {
            "metric": metric,
            "location1": loc1,
            "location2": loc2,
            "comparison": {
                "difference": difference,
                "percent_difference": percent_difference,
                "higher": loc1["name"] if loc1["mean"] > loc2["mean"] else loc2["name"],
            }
        }

    async def query_species_biomass(
        self,
        state: str,
        species_code: str,
        county: str | None = None,
    ) -> dict[str, Any]:
        """Query biomass for a specific species.

        Args:
            state: State name or two-letter abbreviation.
            species_code: 4-digit FIA species code.
            county: Optional county name for finer resolution.

        Returns:
            Dictionary containing species-specific biomass statistics.
        """
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            self._query_species_biomass_sync,
            state,
            species_code,
            county
        )
        return result

    def _query_species_biomass_sync(
        self, state: str, species_code: str, county: str | None
    ) -> dict[str, Any]:
        """Synchronous species biomass query (runs in thread pool)."""
        # Ensure Zarr store exists with the requested species
        zarr_path = self._ensure_zarr_exists(state, county, species_codes=[species_code])

        import zarr
        import numpy as np

        store = zarr.open(zarr_path, mode='r')
        species_codes = list(store['species_codes'][:])
        species_names = list(store['species_names'][:])

        # Find the species index
        try:
            species_idx = species_codes.index(species_code)
        except ValueError:
            # Species not found in the store, return empty result
            location_name = f"{county}, {state}" if county else state
            return {
                "location": location_name,
                "species_code": species_code,
                "species_name": "Unknown",
                "found": False,
                "message": f"Species {species_code} not found in {location_name}",
            }

        species_name = species_names[species_idx] if species_idx < len(species_names) else "Unknown"

        # Extract biomass for this species
        biomass_layer = store['biomass'][species_idx]
        valid_mask = (biomass_layer > 0) & (biomass_layer != -9999)
        valid_data = biomass_layer[valid_mask]

        if len(valid_data) == 0:
            location_name = f"{county}, {state}" if county else state
            return {
                "location": location_name,
                "species_code": species_code,
                "species_name": species_name,
                "found": True,
                "has_data": False,
                "message": f"Species {species_name} has no biomass data in {location_name}",
            }

        pixel_count = int(len(valid_data))
        mean_biomass = float(np.mean(valid_data))
        total_biomass = float(np.sum(valid_data)) * PIXEL_AREA_HA

        location_name = f"{county}, {state}" if county else state

        return {
            "location": location_name,
            "species_code": species_code,
            "species_name": species_name,
            "found": True,
            "has_data": True,
            "mean_biomass_mgha": mean_biomass,
            "std": float(np.std(valid_data)),
            "min": float(np.min(valid_data)),
            "max": float(np.max(valid_data)),
            "total_biomass_mg": total_biomass,
            "pixel_count": pixel_count,
            "area_hectares": pixel_count * PIXEL_AREA_HA,
        }

    def list_calculations(self) -> list[str]:
        """List all available calculations.

        Returns:
            List of calculation names that can be run.
        """
        return self._api.list_calculations()


# Override the get function to use the extended service
_gridfia_service_extended: GridFIAServiceExtended | None = None
_gridfia_service_extended_lock = threading.Lock()


def get_gridfia_service_extended() -> GridFIAServiceExtended:
    """Get or create the extended GridFIA service singleton (thread-safe).

    Returns:
        GridFIAServiceExtended instance.

    Raises:
        ImportError: If GridFIA is not installed.
    """
    global _gridfia_service_extended

    if _gridfia_service_extended is None:
        with _gridfia_service_extended_lock:
            if _gridfia_service_extended is None:
                _gridfia_service_extended = GridFIAServiceExtended()

    return _gridfia_service_extended


def reset_gridfia_service_extended() -> None:
    """Reset the extended GridFIA service singleton (for testing)."""
    global _gridfia_service_extended
    with _gridfia_service_extended_lock:
        _gridfia_service_extended = None

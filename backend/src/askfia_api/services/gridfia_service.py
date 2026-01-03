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
    import rasterio
    from gridfia import GridFIA
    from gridfia.utils.location_config import LocationConfig

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
        self._species_catalog: dict[str, str] = {}  # Cache: code -> name
        self._species_presence_cache: dict[str, list[int]] = {}  # Cache: state -> indices with data

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

    def _get_species_catalog(self) -> dict[str, str]:
        """Get species code -> name mapping from FIA REST API.

        Lazily loads and caches the catalog on first call.
        """
        if not self._species_catalog and self._api is not None:
            try:
                species_list = self._api.list_species()
                self._species_catalog = {
                    s.species_code: s.common_name for s in species_list
                }
                logger.info(f"Loaded species catalog with {len(self._species_catalog)} species")
            except Exception as e:
                logger.warning(f"Failed to load species catalog: {e}")
        return self._species_catalog

    def _get_present_species_indices(self, state: str) -> list[int]:
        """Get indices of species that have actual biomass data in a state.

        Uses efficient sampling - checks sum of each layer to detect presence.
        Results are cached per state.
        """
        abbr = self._normalize_state(state)
        if abbr is None:
            return []

        # Return cached result if available
        if abbr in self._species_presence_cache:
            return self._species_presence_cache[abbr]

        store = self._get_cloud_store(state)
        if store is None:
            return []

        num_species = store.shape[0]
        present_indices = []

        logger.info(f"Scanning {num_species} species layers for {abbr}...")

        # Check each species layer for non-zero data
        # This downloads each layer but is cached per state
        for i in range(num_species):
            if i == 0:  # Skip total biomass layer
                continue
            try:
                # Just get the sum - Zarr streaming makes this reasonably fast
                layer = store.biomass[i, :, :]
                total = float(np.sum(layer))
                if total > 0:
                    present_indices.append(i)
            except Exception as e:
                logger.warning(f"Error checking species at index {i}: {e}")
                continue

        logger.info(f"Found {len(present_indices)} species with data in {abbr}")
        self._species_presence_cache[abbr] = present_indices
        return present_indices

    def get_species_in_state(self, state: str, check_presence: bool = True) -> list[dict[str, str]] | None:
        """Get list of species present in a state from cloud data.

        By default, checks which species have actual biomass data in the state
        (not just metadata entries). This requires scanning all species layers
        but results are cached.

        Species names are looked up from the FIA REST API catalog since
        the B2 Zarr stores may have empty species_names arrays.

        Args:
            state: State name or abbreviation.
            check_presence: If True, only returns species that have actual
                biomass data in the state (recommended, cached after first call).
                If False, returns all species in the metadata (faster initially
                but may include species not actually present).
        """
        store = self._get_cloud_store(state)
        if store is None:
            return None

        try:
            # Get species codes from store metadata
            species_codes = store.species_codes
            species_names = store.species_names

            # Get the FIA species catalog for name lookup
            catalog = self._get_species_catalog()

            # Get indices of present species (cached)
            if check_presence:
                present_indices = set(self._get_present_species_indices(state))
            else:
                present_indices = None

            # Build species list
            species_list = []
            for i, code in enumerate(species_codes):
                if not code or code == "0000":
                    continue

                # Check if species has actual biomass data
                if present_indices is not None and i not in present_indices:
                    continue

                # Try to get name from store first, fall back to catalog
                name = species_names[i] if i < len(species_names) else ""
                if not name:
                    name = catalog.get(code, "")

                if name:
                    species_list.append({
                        "species_code": code,
                        "common_name": name,
                    })

            return species_list
        except Exception as e:
            logger.error(f"Error getting species list from cloud: {e}")
            return None

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
        """Synchronous diversity calculation from ZarrStore using chunked processing.

        This implementation processes data in spatial tiles to avoid loading the
        entire array into memory. For Rhode Island (326 species x 3407 x 2264),
        the full array would be ~10 GB. By processing in 512x512 tiles, we keep
        memory usage under 1 GB.

        Uses WelfordStatisticsAccumulator for numerically stable, vectorized
        computation of mean and variance across tiles.
        """
        from .statistics import WelfordStatisticsAccumulator

        abbr = self._normalize_state(state)
        location_name = self._api._STATE_METADATA.get(abbr, {}).get("name", state)

        # Get array shape without loading data
        num_species, height, width = store.shape

        # Tile size for chunked processing
        # Must account for multiple intermediate arrays during calculation:
        # - tile_biomass, tile_presence, tile_proportions, tile_log_p
        # With 326 species at 64x64: 326 * 64 * 64 * 4 = ~5 MB per array
        # Peak with 4 arrays: ~20 MB, well under memory limits
        tile_size = 64

        # Use WelfordStatisticsAccumulator for running statistics
        div_stats = WelfordStatisticsAccumulator()
        rich_stats = WelfordStatisticsAccumulator()
        rich_max = 0

        # Process in tiles
        for row_start in range(0, height, tile_size):
            row_end = min(row_start + tile_size, height)

            for col_start in range(0, width, tile_size):
                col_end = min(col_start + tile_size, width)

                # Load only this tile (all species, but limited spatial extent)
                # Shape: (num_species, tile_height, tile_width)
                tile_biomass = store.biomass[:, row_start:row_end, col_start:col_end]

                # Calculate presence for this tile
                tile_presence = (tile_biomass > 0).astype(np.float32)

                # Calculate richness for this tile
                tile_richness = np.sum(tile_presence, axis=0)

                # Forest mask for this tile
                tile_forest_mask = tile_richness > 0

                if not np.any(tile_forest_mask):
                    # No forest pixels in this tile, skip
                    continue

                # Calculate diversity metric for this tile
                if metric == "richness":
                    tile_diversity = tile_richness
                elif metric == "shannon":
                    # Shannon diversity index: H' = -sum(p_i * ln(p_i))
                    tile_total = np.sum(tile_biomass, axis=0)
                    tile_total = np.where(tile_total > 0, tile_total, 1)
                    tile_proportions = tile_biomass / tile_total
                    tile_log_p = np.where(tile_proportions > 0, np.log(tile_proportions), 0)
                    tile_diversity = -np.sum(tile_proportions * tile_log_p, axis=0)
                elif metric == "simpson":
                    # Simpson diversity index: 1 - D = 1 - sum(p_i^2)
                    tile_total = np.sum(tile_biomass, axis=0)
                    tile_total = np.where(tile_total > 0, tile_total, 1)
                    tile_proportions = tile_biomass / tile_total
                    tile_diversity = 1 - np.sum(tile_proportions ** 2, axis=0)
                else:
                    raise ValueError(f"Unknown metric: {metric}")

                # Get valid values for this tile (flattened arrays)
                valid_div = tile_diversity[tile_forest_mask].ravel()
                valid_rich = tile_richness[tile_forest_mask].ravel()

                # Update statistics using WelfordStatisticsAccumulator
                div_stats.update(valid_div)
                rich_stats.update(valid_rich)
                if len(valid_rich) > 0:
                    rich_max = max(rich_max, int(np.max(valid_rich)))

                # Free memory explicitly
                del tile_biomass, tile_presence, tile_richness, tile_diversity
                del tile_forest_mask, valid_div, valid_rich

        # Handle edge case where no forest pixels were found
        if div_stats.count == 0:
            return {
                "location": location_name,
                "metric": metric,
                "mean": 0.0,
                "std": 0.0,
                "min": 0.0,
                "max": 0.0,
                "pixel_count": 0,
                "richness_mean": 0.0,
                "richness_max": 0,
                "source": "cloud",
            }

        div_result = div_stats.to_dict()
        rich_result = rich_stats.to_dict()

        return {
            "location": location_name,
            "metric": metric,
            "mean": div_result["mean"],
            "std": div_result["std"],
            "min": div_result["min"],
            "max": div_result["max"],
            "pixel_count": div_result["count"],
            "richness_mean": rich_result["mean"],
            "richness_max": rich_max,
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
        """Synchronous biomass calculation from ZarrStore using chunked processing.

        This implementation processes data in spatial tiles to avoid loading the
        entire array into memory. Uses WelfordStatisticsAccumulator for numerically
        stable, vectorized computation of mean and variance across tiles.
        """
        from .statistics import WelfordStatisticsAccumulator

        abbr = self._normalize_state(state)
        location_name = self._api._STATE_METADATA.get(abbr, {}).get("name", state)

        # Get array shape without loading data
        num_species, height, width = store.shape

        # Tile size for chunked processing (64x64 keeps memory under 20 MB)
        tile_size = 64

        # Use WelfordStatisticsAccumulator for running statistics
        biomass_stats = WelfordStatisticsAccumulator()
        total_sum = 0.0  # Running sum for total biomass

        # Calculate pixel area (30m resolution = 0.09 ha)
        pixel_area_ha = 0.09

        # Process in tiles
        for row_start in range(0, height, tile_size):
            row_end = min(row_start + tile_size, height)

            for col_start in range(0, width, tile_size):
                col_end = min(col_start + tile_size, width)

                # Load only this tile (all species, limited spatial extent)
                tile_biomass = store.biomass[:, row_start:row_end, col_start:col_end]

                # Calculate total biomass for this tile (sum across species)
                tile_total = np.sum(tile_biomass, axis=0)

                # Forest mask for this tile
                tile_forest_mask = tile_total > 0

                if not np.any(tile_forest_mask):
                    del tile_biomass, tile_total, tile_forest_mask
                    continue

                # Get valid biomass values (flattened)
                valid_biomass = tile_total[tile_forest_mask].ravel()

                # Update statistics using WelfordStatisticsAccumulator
                biomass_stats.update(valid_biomass)
                total_sum += float(np.sum(valid_biomass))

                # Free memory explicitly
                del tile_biomass, tile_total, tile_forest_mask, valid_biomass

        # Handle edge case where no forest pixels were found
        if biomass_stats.count == 0:
            return {
                "location": location_name,
                "mean_biomass_mgha": 0.0,
                "std": 0.0,
                "min": 0.0,
                "max": 0.0,
                "total_biomass_mg": 0.0,
                "pixel_count": 0,
                "area_hectares": 0.0,
                "source": "cloud",
            }

        result = biomass_stats.to_dict()
        area_hectares = result["count"] * pixel_area_ha

        return {
            "location": location_name,
            "mean_biomass_mgha": result["mean"],
            "std": result["std"],
            "min": result["min"],
            "max": result["max"],
            "total_biomass_mg": float(total_sum * pixel_area_ha),
            "pixel_count": result["count"],
            "area_hectares": area_hectares,
            "source": "cloud",
        }

    def is_available(self) -> bool:
        """Check if cloud data service is available."""
        return len(self._available_states) > 0


class CONUSCloudService:
    """Cloud-hosted data service for CONUS tile-based queries.

    This service enables queries against pre-processed national forest data
    stored as tiles on Backblaze B2. It maps state/county queries to the
    appropriate tiles and aggregates results across multiple tiles.

    The tile grid covers continental US (CONUS) with:
    - 4096 x 4096 pixel tiles at 30m resolution
    - EPSG:3857 (Web Mercator) projection
    - ~1537 total tiles covering the continental US

    Tiles are stored at: https://f005.backblazeb2.com/file/gridfia-conus/tiles/
    """

    # B2 public URL for CONUS tiles
    B2_BASE_URL = "https://f005.backblazeb2.com/file/gridfia-conus"

    # CONUS bounds in EPSG:3857 (Web Mercator)
    CONUS_BOUNDS_3857 = {
        "xmin": -13914936,
        "ymin": 2814455,
        "xmax": -7402746,
        "ymax": 6360131,
    }

    # Tile specifications
    TILE_SIZE_PX = 4096
    PIXEL_SIZE_M = 30
    TILE_SIZE_M = TILE_SIZE_PX * PIXEL_SIZE_M  # 122,880 meters

    # State abbreviation to full name mapping
    STATE_NAMES = {
        "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
        "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
        "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
        "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
        "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
        "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
        "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
        "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
        "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
        "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
        "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
        "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
        "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
    }

    # CONUS states (exclude Alaska, Hawaii)
    CONUS_STATES = set(STATE_NAMES.keys()) - {"AK", "HI"}

    def __init__(self, gridfia_api: "GridFIA | None" = None):
        """Initialize CONUS cloud data service.

        Args:
            gridfia_api: GridFIA API instance for cloud access and species catalog.
        """
        self._api = gridfia_api
        self._tile_store_cache: dict[str, Any] = {}  # Cache: tile_id -> ZarrStore
        self._species_catalog: dict[str, str] = {}  # Cache: code -> name
        self._available_tiles: set[str] = set()  # Tiles verified to exist
        self._state_bounds_cache: dict[str, tuple] = {}  # Cache: state -> bbox_3857

        # Grid dimensions
        import math
        extent_x = self.CONUS_BOUNDS_3857["xmax"] - self.CONUS_BOUNDS_3857["xmin"]
        extent_y = self.CONUS_BOUNDS_3857["ymax"] - self.CONUS_BOUNDS_3857["ymin"]
        self._num_cols = math.ceil(extent_x / self.TILE_SIZE_M)
        self._num_rows = math.ceil(extent_y / self.TILE_SIZE_M)

        logger.info(f"CONUSCloudService initialized: {self._num_cols}x{self._num_rows} tile grid")

    def _normalize_state(self, state: str) -> str | None:
        """Normalize state name to 2-letter abbreviation.

        Returns None if state not recognized or not in CONUS.
        """
        state_clean = state.strip()

        # Already an abbreviation?
        if len(state_clean) == 2:
            abbr = state_clean.upper()
            if abbr in self.CONUS_STATES:
                return abbr
            return None

        # Full name lookup (case-insensitive)
        state_lower = state_clean.lower()
        for abbr, name in self.STATE_NAMES.items():
            if name.lower() == state_lower:
                if abbr in self.CONUS_STATES:
                    return abbr
                return None

        return None

    def is_state_available(self, state: str) -> bool:
        """Check if state is in CONUS (tile data potentially available)."""
        abbr = self._normalize_state(state)
        return abbr is not None

    def _get_tile_id(self, col: int, row: int) -> str:
        """Generate tile ID from column and row indices."""
        return f"conus_{col:03d}_{row:03d}"

    def _get_tile_bbox(self, col: int, row: int) -> tuple[float, float, float, float]:
        """Get bounding box for a tile in EPSG:3857.

        Returns:
            Tuple of (xmin, ymin, xmax, ymax)
        """
        origin_x = self.CONUS_BOUNDS_3857["xmin"]
        origin_y = self.CONUS_BOUNDS_3857["ymin"]

        xmin = origin_x + col * self.TILE_SIZE_M
        ymin = origin_y + row * self.TILE_SIZE_M
        xmax = xmin + self.TILE_SIZE_M
        ymax = ymin + self.TILE_SIZE_M
        return (xmin, ymin, xmax, ymax)

    def _get_tiles_for_bbox(
        self, bbox: tuple[float, float, float, float]
    ) -> list[tuple[int, int]]:
        """Get all tile indices that intersect a bounding box in EPSG:3857.

        Args:
            bbox: (xmin, ymin, xmax, ymax) in EPSG:3857

        Returns:
            List of (col, row) tuples
        """
        xmin, ymin, xmax, ymax = bbox
        origin_x = self.CONUS_BOUNDS_3857["xmin"]
        origin_y = self.CONUS_BOUNDS_3857["ymin"]

        # Calculate tile range
        col_min = max(0, int((xmin - origin_x) / self.TILE_SIZE_M))
        col_max = min(self._num_cols - 1, int((xmax - origin_x) / self.TILE_SIZE_M))
        row_min = max(0, int((ymin - origin_y) / self.TILE_SIZE_M))
        row_max = min(self._num_rows - 1, int((ymax - origin_y) / self.TILE_SIZE_M))

        tiles = []
        for row in range(row_min, row_max + 1):
            for col in range(col_min, col_max + 1):
                tiles.append((col, row))
        return tiles

    def _get_state_bbox_3857(self, state: str) -> tuple[float, float, float, float] | None:
        """Get state bounding box in EPSG:3857.

        Uses geopandas to get state boundaries and reproject to Web Mercator.
        Results are cached.
        """
        abbr = self._normalize_state(state)
        if abbr is None:
            return None

        if abbr in self._state_bounds_cache:
            return self._state_bounds_cache[abbr]

        try:
            import geopandas as gpd
            from pyproj import CRS

            # Get state boundaries from census data (Natural Earth or similar)
            # This uses the built-in US states dataset
            states_url = "https://www2.census.gov/geo/tiger/GENZ2021/shp/cb_2021_us_state_500k.zip"

            # Try to load from cache or download
            try:
                states_gdf = gpd.read_file(states_url)
            except Exception:
                # Fall back to approximate bounds for common states
                logger.warning(f"Could not load state boundaries, using approximate bounds for {abbr}")
                return self._get_approximate_state_bounds(abbr)

            # Filter to our state
            state_gdf = states_gdf[states_gdf["STUSPS"] == abbr]
            if state_gdf.empty:
                logger.warning(f"State {abbr} not found in boundaries file")
                return None

            # Reproject to EPSG:3857
            state_gdf = state_gdf.to_crs(CRS.from_epsg(3857))

            # Get bounds
            bounds = state_gdf.total_bounds  # [xmin, ymin, xmax, ymax]
            bbox = (bounds[0], bounds[1], bounds[2], bounds[3])

            self._state_bounds_cache[abbr] = bbox
            logger.info(f"State {abbr} bbox (3857): {bbox}")
            return bbox

        except Exception as e:
            logger.error(f"Error getting state bounds for {abbr}: {e}")
            return self._get_approximate_state_bounds(abbr)

    def _get_approximate_state_bounds(self, abbr: str) -> tuple[float, float, float, float] | None:
        """Get approximate state bounds in EPSG:3857 for fallback.

        These are rough estimates for the most common states.
        """
        # Approximate bounds in EPSG:3857 for some states
        # Format: (xmin, ymin, xmax, ymax)
        APPROX_BOUNDS = {
            "NC": (-9424000, 4005000, -8399000, 4380000),
            "VA": (-9176000, 4359000, -8345000, 4796000),
            "TX": (-11689000, 2960000, -9381000, 4277000),
            "CA": (-13856000, 3764000, -12638000, 5162000),
            "FL": (-9858000, 2787000, -8894000, 3640000),
            "GA": (-9472000, 3586000, -8926000, 3990000),
            "RI": (-8014000, 5068000, -7904000, 5175000),
            "CT": (-8155000, 5021000, -7978000, 5160000),
        }

        return APPROX_BOUNDS.get(abbr)

    def _get_tiles_for_state(self, state: str) -> list[str]:
        """Get tile IDs that cover a state.

        Args:
            state: State name or abbreviation

        Returns:
            List of tile IDs (e.g., ["conus_027_015", "conus_027_016", ...])
        """
        bbox = self._get_state_bbox_3857(state)
        if bbox is None:
            return []

        tile_indices = self._get_tiles_for_bbox(bbox)
        return [self._get_tile_id(col, row) for col, row in tile_indices]

    def _get_tile_url(self, tile_id: str) -> str:
        """Get the B2 URL for a tile's Zarr store."""
        return f"{self.B2_BASE_URL}/tiles/{tile_id}/biomass.zarr"

    def _load_tile_store(self, tile_id: str) -> Any | None:
        """Load a tile's ZarrStore from B2, with caching.

        Returns None if tile doesn't exist or can't be loaded.
        """
        if tile_id in self._tile_store_cache:
            return self._tile_store_cache[tile_id]

        url = self._get_tile_url(tile_id)

        try:
            # Import ZarrStore from gridfia
            from gridfia.utils.zarr_utils import ZarrStore

            logger.info(f"Loading tile {tile_id} from {url}")
            store = ZarrStore.from_url(url)
            self._tile_store_cache[tile_id] = store
            self._available_tiles.add(tile_id)
            return store

        except Exception as e:
            logger.warning(f"Could not load tile {tile_id}: {e}")
            return None

    async def get_diversity_stats(
        self,
        state: str,
        county: str | None = None,
        metric: str = "shannon"
    ) -> dict[str, Any] | None:
        """Get diversity statistics from CONUS tiles.

        Maps the state/county to tiles and aggregates diversity stats
        across all relevant tiles using parallel Welford's algorithm.

        Returns None if state not in CONUS (falls back to other services).
        County-level queries use state bounds for now (TODO: county bounds).
        """
        if not self.is_state_available(state):
            return None

        # Get tiles for this state
        tile_ids = self._get_tiles_for_state(state)
        if not tile_ids:
            logger.warning(f"No tiles found for state: {state}")
            return None

        logger.info(f"State {state} spans {len(tile_ids)} tiles")

        # Calculate diversity across tiles
        try:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None, self._calculate_diversity_across_tiles, tile_ids, state, metric
            )
            return result
        except Exception as e:
            logger.error(f"Error calculating diversity from CONUS tiles: {e}")
            return None

    def _calculate_diversity_across_tiles(
        self,
        tile_ids: list[str],
        state: str,
        metric: str
    ) -> dict[str, Any]:
        """Synchronous diversity calculation across multiple tiles.

        Uses WelfordStatisticsAccumulator to aggregate stats across tiles
        without loading all data into memory.
        """
        from .statistics import WelfordStatisticsAccumulator

        abbr = self._normalize_state(state)
        location_name = self.STATE_NAMES.get(abbr, state)

        # Accumulators for running statistics
        div_stats = WelfordStatisticsAccumulator()
        rich_stats = WelfordStatisticsAccumulator()
        rich_max = 0

        tiles_processed = 0
        tiles_failed = 0

        for tile_id in tile_ids:
            store = self._load_tile_store(tile_id)
            if store is None:
                tiles_failed += 1
                continue

            try:
                # Process this tile with chunked calculation
                tile_result = self._calculate_tile_diversity(store, metric)

                if tile_result["count"] == 0:
                    continue

                tiles_processed += 1

                # Merge diversity stats using accumulator
                tile_div = WelfordStatisticsAccumulator.from_stats(
                    count=tile_result["count"],
                    mean=tile_result["mean"],
                    m2=tile_result["m2"],
                    min_val=tile_result["min"],
                    max_val=tile_result["max"],
                )
                div_stats.merge(tile_div)

                # Merge richness stats
                if tile_result["rich_count"] > 0:
                    tile_rich = WelfordStatisticsAccumulator.from_stats(
                        count=tile_result["rich_count"],
                        mean=tile_result["rich_mean"],
                        m2=tile_result["rich_m2"],
                    )
                    rich_stats.merge(tile_rich)
                    rich_max = max(rich_max, tile_result["rich_max"])

            except Exception as e:
                logger.warning(f"Error processing tile {tile_id}: {e}")
                tiles_failed += 1
                continue

        logger.info(f"Processed {tiles_processed} tiles, {tiles_failed} failed")

        if div_stats.count == 0:
            return {
                "location": location_name,
                "metric": metric,
                "mean": 0.0,
                "std": 0.0,
                "min": 0.0,
                "max": 0.0,
                "pixel_count": 0,
                "richness_mean": 0.0,
                "richness_max": 0,
                "source": "conus_tiles",
                "tiles_processed": tiles_processed,
            }

        div_result = div_stats.to_dict()
        return {
            "location": location_name,
            "metric": metric,
            "mean": div_result["mean"],
            "std": div_result["std"],
            "min": div_result["min"],
            "max": div_result["max"],
            "pixel_count": div_result["count"],
            "richness_mean": rich_stats.mean if rich_stats.count > 0 else 0.0,
            "richness_max": rich_max,
            "source": "conus_tiles",
            "tiles_processed": tiles_processed,
        }

    def _calculate_tile_diversity(self, store: Any, metric: str) -> dict[str, Any]:
        """Calculate diversity stats for a single tile using chunked processing.

        Returns intermediate statistics suitable for parallel Welford aggregation.
        Uses WelfordStatisticsAccumulator for numerically stable computation.
        """
        from .statistics import WelfordStatisticsAccumulator

        num_species, height, width = store.shape
        tile_size = 64  # Process in 64x64 chunks

        # Use accumulators for running stats
        div_stats = WelfordStatisticsAccumulator()
        rich_stats = WelfordStatisticsAccumulator()
        rich_max = 0

        for row_start in range(0, height, tile_size):
            row_end = min(row_start + tile_size, height)

            for col_start in range(0, width, tile_size):
                col_end = min(col_start + tile_size, width)

                # Load chunk
                chunk_biomass = store.biomass[:, row_start:row_end, col_start:col_end]

                # Calculate presence and richness
                chunk_presence = (chunk_biomass > 0).astype(np.float32)
                chunk_richness = np.sum(chunk_presence, axis=0)
                chunk_forest_mask = chunk_richness > 0

                if not np.any(chunk_forest_mask):
                    continue

                # Calculate diversity metric
                if metric == "richness":
                    chunk_diversity = chunk_richness
                elif metric == "shannon":
                    chunk_total = np.sum(chunk_biomass, axis=0)
                    chunk_total = np.where(chunk_total > 0, chunk_total, 1)
                    chunk_proportions = chunk_biomass / chunk_total
                    chunk_log_p = np.where(chunk_proportions > 0, np.log(chunk_proportions), 0)
                    chunk_diversity = -np.sum(chunk_proportions * chunk_log_p, axis=0)
                elif metric == "simpson":
                    chunk_total = np.sum(chunk_biomass, axis=0)
                    chunk_total = np.where(chunk_total > 0, chunk_total, 1)
                    chunk_proportions = chunk_biomass / chunk_total
                    chunk_diversity = 1 - np.sum(chunk_proportions ** 2, axis=0)
                else:
                    raise ValueError(f"Unknown metric: {metric}")

                # Get valid values
                valid_div = chunk_diversity[chunk_forest_mask].ravel()
                valid_rich = chunk_richness[chunk_forest_mask].ravel()

                # Update accumulators
                div_stats.update(valid_div)
                rich_stats.update(valid_rich)
                if len(valid_rich) > 0:
                    rich_max = max(rich_max, int(np.max(valid_rich)))

                # Free memory
                del chunk_biomass, chunk_presence, chunk_richness, chunk_diversity

        return {
            "count": div_stats.count,
            "mean": div_stats.mean,
            "m2": div_stats.m2,
            "min": div_stats.min_val if div_stats.count > 0 else 0.0,
            "max": div_stats.max_val if div_stats.count > 0 else 0.0,
            "rich_count": rich_stats.count,
            "rich_mean": rich_stats.mean,
            "rich_m2": rich_stats.m2,
            "rich_max": rich_max,
        }

    async def get_biomass_stats(
        self,
        state: str,
        county: str | None = None
    ) -> dict[str, Any] | None:
        """Get biomass statistics from CONUS tiles.

        Returns None if state not in CONUS (falls back to other services).
        """
        if not self.is_state_available(state):
            return None

        tile_ids = self._get_tiles_for_state(state)
        if not tile_ids:
            return None

        try:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None, self._calculate_biomass_across_tiles, tile_ids, state
            )
            return result
        except Exception as e:
            logger.error(f"Error calculating biomass from CONUS tiles: {e}")
            return None

    def _calculate_biomass_across_tiles(
        self,
        tile_ids: list[str],
        state: str
    ) -> dict[str, Any]:
        """Synchronous biomass calculation across multiple tiles.

        Uses WelfordStatisticsAccumulator for numerically stable aggregation.
        """
        from .statistics import WelfordStatisticsAccumulator

        abbr = self._normalize_state(state)
        location_name = self.STATE_NAMES.get(abbr, state)

        biomass_stats = WelfordStatisticsAccumulator()
        total_sum = 0.0
        tiles_processed = 0
        pixel_area_ha = 0.09

        for tile_id in tile_ids:
            store = self._load_tile_store(tile_id)
            if store is None:
                continue

            try:
                tile_result = self._calculate_tile_biomass(store)

                if tile_result["count"] == 0:
                    continue

                tiles_processed += 1

                # Merge stats using accumulator
                tile_stats = WelfordStatisticsAccumulator.from_stats(
                    count=tile_result["count"],
                    mean=tile_result["mean"],
                    m2=tile_result["m2"],
                    min_val=tile_result["min"],
                    max_val=tile_result["max"],
                )
                biomass_stats.merge(tile_stats)
                total_sum += tile_result["sum"]

            except Exception as e:
                logger.warning(f"Error processing tile {tile_id} for biomass: {e}")
                continue

        if biomass_stats.count == 0:
            return {
                "location": location_name,
                "mean_biomass_mgha": 0.0,
                "std": 0.0,
                "min": 0.0,
                "max": 0.0,
                "total_biomass_mg": 0.0,
                "pixel_count": 0,
                "area_hectares": 0.0,
                "source": "conus_tiles",
                "tiles_processed": tiles_processed,
            }

        result = biomass_stats.to_dict()
        area_hectares = result["count"] * pixel_area_ha

        return {
            "location": location_name,
            "mean_biomass_mgha": result["mean"],
            "std": result["std"],
            "min": result["min"],
            "max": result["max"],
            "total_biomass_mg": float(total_sum * pixel_area_ha),
            "pixel_count": result["count"],
            "area_hectares": area_hectares,
            "source": "conus_tiles",
            "tiles_processed": tiles_processed,
        }

    def _calculate_tile_biomass(self, store: Any) -> dict[str, Any]:
        """Calculate biomass stats for a single tile.

        Uses WelfordStatisticsAccumulator for numerically stable computation.
        """
        from .statistics import WelfordStatisticsAccumulator

        num_species, height, width = store.shape
        tile_size = 64

        biomass_stats = WelfordStatisticsAccumulator()
        total_sum = 0.0

        for row_start in range(0, height, tile_size):
            row_end = min(row_start + tile_size, height)

            for col_start in range(0, width, tile_size):
                col_end = min(col_start + tile_size, width)

                chunk_biomass = store.biomass[:, row_start:row_end, col_start:col_end]
                chunk_total = np.sum(chunk_biomass, axis=0)
                chunk_forest_mask = chunk_total > 0

                if not np.any(chunk_forest_mask):
                    del chunk_biomass, chunk_total, chunk_forest_mask
                    continue

                valid_biomass = chunk_total[chunk_forest_mask].ravel()

                # Update accumulator
                biomass_stats.update(valid_biomass)
                total_sum += float(np.sum(valid_biomass))

                del chunk_biomass, chunk_total, chunk_forest_mask, valid_biomass

        return {
            "count": biomass_stats.count,
            "mean": biomass_stats.mean,
            "m2": biomass_stats.m2,
            "sum": total_sum,
            "min": biomass_stats.min_val if biomass_stats.count > 0 else 0.0,
            "max": biomass_stats.max_val if biomass_stats.count > 0 else 0.0,
        }

    def is_available(self) -> bool:
        """Check if CONUS cloud service is available."""
        # Always available for CONUS states (tiles may still be processing)
        return True


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
        self._conus_service = CONUSCloudService(gridfia_api=self._api)
        self._tile_service = TileService()

        logger.info(f"GridFIA service initialized with cache at {self._cache_dir}")
        if self._cloud_service.is_available():
            logger.info(f"Cloud streaming enabled for states: {self._cloud_service._available_states}")
        if self._conus_service.is_available():
            logger.info("CONUS tile service enabled for continental US states")

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
        # Try state-level cloud data first (small states with pre-processed stores)
        cloud_result = await self._cloud_service.get_diversity_stats(state, county, metric)
        if cloud_result is not None:
            return cloud_result

        # Try CONUS tile service for continental US (tile-based processing)
        conus_result = await self._conus_service.get_diversity_stats(state, county, metric)
        if conus_result is not None:
            return conus_result

        # Fall back to local calculation (downloads data from FIA API)
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
        # Try state-level cloud data first (small states with pre-processed stores)
        cloud_result = await self._cloud_service.get_biomass_stats(state, county)
        if cloud_result is not None:
            return cloud_result

        # Try CONUS tile service for continental US (tile-based processing)
        conus_result = await self._conus_service.get_biomass_stats(state, county)
        if conus_result is not None:
            return conus_result

        # Fall back to local calculation (downloads data from FIA API)
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

        import numpy as np
        import zarr

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

        import numpy as np
        import zarr

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

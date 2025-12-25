"""Service layer for pyFIA operations."""

import logging
import re
from collections.abc import Generator
from contextlib import contextmanager
from functools import lru_cache

import duckdb
import pandas as pd

from ..config import settings
from . import species_data
from .storage import storage

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_motherduck_databases(token: str) -> dict[str, str]:
    """Get available FIA databases from MotherDuck.

    Returns a dict mapping state codes to their latest database names.
    Database naming convention: fia_{state}_eval{year}

    Falls back to legacy naming (fia_{state}) if no eval year databases found.
    """
    state_to_db = {}

    try:
        conn = duckdb.connect(f"md:?motherduck_token={token}")
        result = conn.execute("SHOW DATABASES").fetchall()
        conn.close()

        # Parse database names and find latest eval year per state
        # Pattern: fia_{state}_eval{year} or legacy fia_{state}
        eval_pattern = re.compile(r"^fia_([a-z]{2})_eval(\d{4})$")
        legacy_pattern = re.compile(r"^fia_([a-z]{2})$")

        state_eval_years: dict[str, list[tuple[int, str]]] = {}

        for (db_name,) in result:
            db_name = db_name.lower()

            # Try new naming convention first
            match = eval_pattern.match(db_name)
            if match:
                state = match.group(1).upper()
                year = int(match.group(2))
                if state not in state_eval_years:
                    state_eval_years[state] = []
                state_eval_years[state].append((year, db_name))
                continue

            # Try legacy naming
            match = legacy_pattern.match(db_name)
            if match:
                state = match.group(1).upper()
                # Use year 0 for legacy databases (lowest priority)
                if state not in state_eval_years:
                    state_eval_years[state] = []
                state_eval_years[state].append((0, db_name))

        # Select latest eval year for each state
        for state, year_dbs in state_eval_years.items():
            year_dbs.sort(reverse=True)  # Sort by year descending
            latest_db = year_dbs[0][1]
            state_to_db[state] = latest_db
            if year_dbs[0][0] > 0:
                logger.info(f"Found {state}: {latest_db} (eval {year_dbs[0][0]})")
            else:
                logger.info(f"Found {state}: {latest_db} (legacy naming)")

    except Exception as e:
        logger.warning(f"Could not query MotherDuck databases: {e}")

    return state_to_db


def get_motherduck_database(state: str, token: str) -> str | None:
    """Get the MotherDuck database name for a state.

    Returns the latest eval year database if available, or None if not found.
    """
    state = state.upper()
    databases = _get_motherduck_databases(token)
    return databases.get(state)


def _get_estimate_column(df: pd.DataFrame, metric: str) -> str:
    """Find the estimate column name dynamically."""
    # Try metric-specific columns first (e.g., AREA, VOLUME, BIOMASS)
    # Column names should match pyFIA output
    metric_cols = {
        "area": ["AREA", "AREA_TOTAL", "area", "ESTIMATE", "estimate"],
        "volume": ["VOLCFNET_TOTAL", "VOL_TOTAL", "VOLUME", "volume", "VOLCFNET", "ESTIMATE", "estimate"],
        "biomass": [
            "BIO_TOTAL",
            "BIO_ACRE",
            "BIOMASS",
            "biomass",
            "DRYBIO_AG",
            "ESTIMATE",
            "estimate",
        ],
        "tpa": ["TPA", "TPA_TOTAL", "tpa", "ESTIMATE", "estimate"],
        "mortality": [
            "MORT_TOTAL",
            "MORT_ACRE",
            "MORTALITY",
            "mortality",
            "ESTIMATE",
            "estimate",
        ],
        "growth": [
            "GROWTH_TOTAL",
            "GROWTH_ACRE",
            "GROWTH",
            "growth",
            "ESTIMATE",
            "estimate",
        ],
    }

    candidates = metric_cols.get(metric, ["ESTIMATE", "estimate"])
    for col in candidates:
        if col in df.columns:
            return col

    # Fallback: first numeric column that's not SE/variance related
    for col in df.columns:
        if df[col].dtype in ["float64", "int64"] and not any(
            x in col.upper() for x in ["SE", "VAR", "CV", "CI", "PLOT", "YEAR"]
        ):
            return col

    raise KeyError(f"Could not find estimate column. Available: {list(df.columns)}")


def _get_se_column(df: pd.DataFrame, metric: str) -> str | None:
    """Find the SE column name dynamically.

    Note: pyFIA returns SE in the same units as the estimate (e.g., acres for area),
    NOT as a percentage. Use _calculate_se_percent() to convert to percentage.
    """
    # Try metric-specific SE columns first (matching pyFIA output)
    metric_se_cols = {
        "area": ["AREA_SE", "SE"],
        "volume": ["VOL_TOTAL_SE", "VOLUME_SE", "SE"],
        "biomass": ["BIO_TOTAL_SE", "BIO_ACRE_SE", "BIOMASS_SE", "SE"],
        "tpa": ["TPA_SE", "TPA_TOTAL_SE", "SE"],
        "mortality": ["MORT_TOTAL_SE", "MORT_ACRE_SE", "MORTALITY_SE", "SE"],
        "growth": ["GROWTH_TOTAL_SE", "GROWTH_ACRE_SE", "GROWTH_SE", "SE"],
        "removals": ["REMOV_TOTAL_SE", "REMOV_ACRE_SE", "REMOVALS_SE", "SE"],
    }

    # Try metric-specific columns first
    if metric in metric_se_cols:
        for col in metric_se_cols[metric]:
            if col in df.columns and df[col].notna().any():
                return col

    # Try common patterns
    candidates = [
        f"{metric.upper()}_SE",
        "SE",
    ]

    for col in candidates:
        if col in df.columns and df[col].notna().any():
            return col

    # Look for any column ending with _SE
    for col in df.columns:
        if col.upper().endswith("_SE") and df[col].notna().any():
            return col

    return None


def _calculate_se_percent(se_value: float, estimate: float) -> float:
    """Calculate SE as a percentage of the estimate.

    SE% = (SE / Estimate) * 100

    Args:
        se_value: Standard error in the same units as the estimate
        estimate: The estimate value

    Returns:
        SE as a percentage (e.g., 5.2 means 5.2%)
    """
    if estimate <= 0 or se_value <= 0:
        return 0.0
    return (se_value / estimate) * 100


# Keep backward compatibility alias
_get_se_percent_column = _get_se_column


class FIAService:
    """Service for querying FIA data using pyFIA."""

    def __init__(self):
        self.storage = storage
        self._motherduck_token = settings.motherduck_token

    def _get_db_path(self, state: str) -> str:
        """Get path to state database using tiered storage."""
        return self.storage.get_db_path(state)

    @contextmanager
    def _get_fia_connection(self, state: str) -> Generator:
        """Get FIA connection, preferring MotherDuck if configured."""
        state = state.upper()

        # Use MotherDuck if token is configured
        if self._motherduck_token:
            from pyfia import MotherDuckFIA

            # Find the database for this state (supports eval year naming)
            database = get_motherduck_database(state, self._motherduck_token)

            if database:
                logger.info(f"Using MotherDuck for {state}: {database}")
                with MotherDuckFIA(
                    database, motherduck_token=self._motherduck_token
                ) as db:
                    db.clip_most_recent()
                    yield db
            else:
                # State not found in MotherDuck, fall back to local storage
                logger.warning(
                    f"State {state} not found in MotherDuck, falling back to local storage"
                )
                from pyfia import FIA

                db_path = self._get_db_path(state)
                with FIA(db_path) as db:
                    db.clip_most_recent()
                    yield db
        else:
            # Fall back to local storage
            from pyfia import FIA

            logger.info(f"Using local storage for {state}")
            db_path = self._get_db_path(state)
            with FIA(db_path) as db:
                db.clip_most_recent()
                yield db

    async def query_area(
        self,
        states: list[str],
        land_type: str = "forest",
        grp_by: str | None = None,
    ) -> dict:
        """Query forest area across states."""
        results = []

        for state in states:
            state = state.upper()

            with self._get_fia_connection(state) as db:
                # Use db.area() method which uses server-side aggregation for MotherDuck
                # This avoids loading full tables into memory
                result_df = db.area(land_type=land_type, grp_by=grp_by)
                df = (
                    result_df.to_pandas()
                    if hasattr(result_df, "to_pandas")
                    else result_df
                )
                df["STATE"] = state
                results.append(df)

        combined = pd.concat(results, ignore_index=True)

        est_col = _get_estimate_column(combined, "area")
        se_col = _get_se_column(combined, "area")

        total_area = float(combined[est_col].sum())
        # Calculate SE% properly: combine SEs using variance propagation, then convert to %
        if se_col and se_col in combined.columns:
            combined_se = float((combined[se_col].dropna() ** 2).sum() ** 0.5)
            se_pct = _calculate_se_percent(combined_se, total_area)
        else:
            se_pct = 0.0

        return {
            "states": states,
            "land_type": land_type,
            "total_area_acres": total_area,
            "se_percent": se_pct,
            "breakdown": combined.to_dict("records") if grp_by else None,
            "source": "USDA Forest Service FIA (pyFIA validated)",
        }

    async def query_volume(
        self,
        states: list[str],
        by_species: bool = False,
        tree_domain: str | None = None,
    ) -> dict:
        """Query timber volume across states."""
        results = []

        for state in states:
            state = state.upper()

            with self._get_fia_connection(state) as db:
                kwargs = {}
                if by_species:
                    kwargs["grp_by"] = "SPCD"
                if tree_domain:
                    kwargs["tree_domain"] = tree_domain

                # Use db.volume() method which handles MotherDuck type compatibility
                result_df = db.volume(**kwargs)
                df = (
                    result_df.to_pandas()
                    if hasattr(result_df, "to_pandas")
                    else result_df
                )
                df["STATE"] = state
                results.append(df)

        combined = pd.concat(results, ignore_index=True)

        est_col = _get_estimate_column(combined, "volume")
        se_col = _get_se_column(combined, "volume")

        total_vol = float(combined[est_col].sum())
        # Calculate SE% properly
        if se_col and se_col in combined.columns:
            combined_se = float((combined[se_col].dropna() ** 2).sum() ** 0.5)
            se_pct = _calculate_se_percent(combined_se, total_vol)
        else:
            se_pct = 0.0

        # Standardize column names for by_species output
        by_species_data = None
        if by_species:
            species_df = combined.copy()
            # Rename estimate column to ESTIMATE for consistent agent access
            if est_col != "ESTIMATE":
                species_df = species_df.rename(columns={est_col: "ESTIMATE"})
            by_species_data = species_df.to_dict("records")

        return {
            "states": states,
            "total_volume_cuft": total_vol,
            "total_volume_billion_cuft": total_vol / 1e9,
            "se_percent": se_pct,
            "by_species": by_species_data,
            "source": "USDA Forest Service FIA (pyFIA validated)",
        }

    async def query_biomass(
        self,
        states: list[str],
        land_type: str = "forest",
        by_species: bool = False,
    ) -> dict:
        """Query biomass and carbon stocks."""
        results = []

        for state in states:
            state = state.upper()

            with self._get_fia_connection(state) as db:
                kwargs = {"land_type": land_type, "variance": True}
                if by_species:
                    kwargs["grp_by"] = "SPCD"

                # Use db.biomass() method which handles MotherDuck type compatibility
                result_df = db.biomass(**kwargs)
                df = (
                    result_df.to_pandas()
                    if hasattr(result_df, "to_pandas")
                    else result_df
                )
                df["STATE"] = state
                results.append(df)

        combined = pd.concat(results, ignore_index=True)

        # pyFIA returns BIO_TOTAL and CARB_TOTAL columns directly
        total_biomass = (
            float(combined["BIO_TOTAL"].sum())
            if "BIO_TOTAL" in combined.columns
            else 0.0
        )
        total_carbon = (
            float(combined["CARB_TOTAL"].sum())
            if "CARB_TOTAL" in combined.columns
            else total_biomass * 0.47
        )

        # Get SE if available (pyFIA returns BIO_TOTAL_SE)
        se_col = _get_se_percent_column(combined, "biomass")
        if se_col and se_col in combined.columns:
            # Calculate SE as percentage of total
            total_se = float(combined[se_col].sum()) if se_col else 0.0
            se_pct = (total_se / total_biomass * 100) if total_biomass > 0 else 0.0
        else:
            se_pct = 0.0

        # Standardize column names for by_species output
        by_species_data = None
        if by_species:
            species_df = combined.copy()
            # Rename estimate column to ESTIMATE for consistent agent access
            if "BIO_TOTAL" in species_df.columns:
                species_df = species_df.rename(columns={"BIO_TOTAL": "ESTIMATE"})
            by_species_data = species_df.to_dict("records")

        return {
            "states": states,
            "land_type": land_type,
            "total_biomass_tons": total_biomass,
            "carbon_mmt": total_carbon / 1e6,  # Convert to million metric tons
            "se_percent": se_pct,
            "by_species": by_species_data,
            "source": "USDA Forest Service FIA (pyFIA validated)",
        }

    async def query_tpa(
        self,
        states: list[str],
        by_species: bool = False,
        by_size_class: bool = False,
        tree_domain: str | None = None,
        land_type: str = "forest",
        tree_type: str = "live",
    ) -> dict:
        """Query trees per acre with optional grouping and filtering."""
        results = []

        for state in states:
            state = state.upper()

            with self._get_fia_connection(state) as db:
                kwargs = {
                    "land_type": land_type,
                    "tree_type": tree_type,
                }

                if by_species:
                    kwargs["by_species"] = True
                if by_size_class:
                    kwargs["by_size_class"] = True
                if tree_domain:
                    kwargs["tree_domain"] = tree_domain

                # Use db.tpa() method which handles MotherDuck type compatibility
                result_df = db.tpa(**kwargs)
                df = (
                    result_df.to_pandas()
                    if hasattr(result_df, "to_pandas")
                    else result_df
                )
                df["STATE"] = state
                results.append(df)

        combined = pd.concat(results, ignore_index=True)

        est_col = _get_estimate_column(combined, "tpa")
        se_col = _get_se_column(combined, "tpa")

        total_tpa = float(combined[est_col].sum())
        # Calculate SE% properly
        if se_col and se_col in combined.columns:
            combined_se = float((combined[se_col].dropna() ** 2).sum() ** 0.5)
            se_pct = _calculate_se_percent(combined_se, total_tpa)
        else:
            se_pct = 0.0

        # Standardize column names for by_species/by_size_class output
        by_species_data = None
        by_size_class_data = None
        if by_species or by_size_class:
            grouped_df = combined.copy()
            # Rename estimate column to ESTIMATE for consistent agent access
            if est_col != "ESTIMATE":
                grouped_df = grouped_df.rename(columns={est_col: "ESTIMATE"})
            records = grouped_df.to_dict("records")
            if by_species:
                by_species_data = records
            if by_size_class:
                by_size_class_data = records

        return {
            "states": states,
            "land_type": land_type,
            "tree_type": tree_type,
            "tree_domain": tree_domain,
            "total_tpa": total_tpa,
            "se_percent": se_pct,
            "by_species": by_species_data,
            "by_size_class": by_size_class_data,
            "source": "USDA Forest Service FIA (pyFIA validated)",
        }

    async def query_mortality(
        self,
        states: list[str],
        by_species: bool = False,
        tree_domain: str | None = None,
    ) -> dict:
        """Query annual tree mortality across states."""
        results = []
        missing_grm_states = []

        for state in states:
            state = state.upper()

            with self._get_fia_connection(state) as db:
                # Check if required GRM tables exist
                required_tables = ["TREE_GRM_COMPONENT", "TREE_GRM_MIDPT"]

                missing_tables = []
                for table in required_tables:
                    if hasattr(db._reader._backend, "table_exists"):
                        if not db._reader._backend.table_exists(table):
                            missing_tables.append(table)
                    else:
                        try:
                            if table not in db.tables:
                                db.load_table(table)
                        except Exception:
                            missing_tables.append(table)

                if missing_tables:
                    logger.warning(
                        f"State {state} is missing GRM tables: {missing_tables}. "
                        "Mortality data not available."
                    )
                    missing_grm_states.append(state)
                    continue

                kwargs = {"measure": "volume", "variance": True}
                if by_species:
                    kwargs["grp_by"] = "SPCD"
                if tree_domain:
                    kwargs["tree_domain"] = tree_domain

                try:
                    # Use db.mortality() method which handles MotherDuck type compatibility
                    result_df = db.mortality(**kwargs)
                    df = (
                        result_df.to_pandas()
                        if hasattr(result_df, "to_pandas")
                        else result_df
                    )
                    df["STATE"] = state
                    results.append(df)
                except Exception as e:
                    logger.error(f"Error querying mortality for {state}: {e}")
                    missing_grm_states.append(state)
                    continue

        # If no states had GRM data, return error response
        if not results:
            return {
                "error": (
                    f"Mortality data is not available for the requested state(s): {states}. "
                    "Mortality estimation requires GRM tables (TREE_GRM_COMPONENT, TREE_GRM_MIDPT) "
                    "which are not available in all FIA databases."
                ),
                "states": states,
                "missing_grm_states": missing_grm_states,
                "available_metrics": ["area", "volume", "biomass", "tpa"],
                "source": "USDA Forest Service FIA (pyFIA)",
            }

        combined = pd.concat(results, ignore_index=True)

        # Mortality returns MORT_TOTAL and MORT_ACRE columns
        total_mortality = (
            float(combined["MORT_TOTAL"].sum())
            if "MORT_TOTAL" in combined.columns
            else 0.0
        )

        # Get SE if available
        se_col = None
        if "MORT_TOTAL_SE" in combined.columns:
            se_col = "MORT_TOTAL_SE"

        if se_col:
            # Calculate SE as percentage of total
            total_se = float(combined[se_col].sum())
            se_pct = (total_se / total_mortality * 100) if total_mortality > 0 else 0.0
        else:
            se_pct = 0.0

        result = {
            "states": states,
            "total_mortality_cuft": total_mortality,
            "total_mortality_million_cuft": total_mortality / 1e6,
            "se_percent": se_pct,
            "by_species": combined.to_dict("records") if by_species else None,
            "source": "USDA Forest Service FIA (pyFIA validated)",
        }

        # Add warning if some states were missing GRM data
        if missing_grm_states:
            result["warning"] = (
                f"Mortality data not available for: {', '.join(missing_grm_states)}. "
                "Results only include states with GRM tables."
            )
            result["states_with_data"] = [
                s for s in states if s not in missing_grm_states
            ]

        return result

    async def query_removals(
        self,
        states: list[str],
        by_species: bool = False,
        tree_domain: str | None = None,
    ) -> dict:
        """Query timber removals (harvest) across states."""
        results = []

        for state in states:
            state = state.upper()

            with self._get_fia_connection(state) as db:
                kwargs = {"measure": "volume", "variance": True}
                if by_species:
                    kwargs["grp_by"] = "SPCD"
                if tree_domain:
                    kwargs["tree_domain"] = tree_domain

                # Use db.removals() method which handles MotherDuck type compatibility
                result_df = db.removals(**kwargs)
                df = (
                    result_df.to_pandas()
                    if hasattr(result_df, "to_pandas")
                    else result_df
                )
                df["STATE"] = state
                results.append(df)

        combined = pd.concat(results, ignore_index=True)

        # Removals returns REMOVALS_TOTAL and REMOVALS_PER_ACRE columns
        total_removals = (
            float(combined["REMOVALS_TOTAL"].sum())
            if "REMOVALS_TOTAL" in combined.columns
            else 0.0
        )

        # Get SE if available
        se_col = None
        if "REMOVALS_TOTAL_SE" in combined.columns:
            se_col = "REMOVALS_TOTAL_SE"

        if se_col:
            # Calculate SE as percentage of total
            total_se = float(combined[se_col].sum())
            se_pct = (total_se / total_removals * 100) if total_removals > 0 else 0.0
        else:
            se_pct = 0.0

        return {
            "states": states,
            "total_removals_cuft": total_removals,
            "total_removals_million_cuft": total_removals / 1e6,
            "se_percent": se_pct,
            "by_species": combined.to_dict("records") if by_species else None,
            "source": "USDA Forest Service FIA (pyFIA validated)",
        }

    async def query_growth(
        self,
        states: list[str],
        by_species: bool = False,
        tree_domain: str | None = None,
        measure: str = "volume",
        land_type: str = "forest",
    ) -> dict:
        """Query annual growth across states."""
        results = []
        missing_grm_states = []

        for state in states:
            state = state.upper()

            with self._get_fia_connection(state) as db:
                # Check if required GRM tables exist
                # Growth requires: TREE_GRM_COMPONENT, TREE_GRM_MIDPT, TREE_GRM_BEGIN, BEGINEND
                required_tables = [
                    "TREE_GRM_COMPONENT",
                    "TREE_GRM_MIDPT",
                    "TREE_GRM_BEGIN",
                    "BEGINEND",
                ]

                missing_tables = []
                for table in required_tables:
                    if hasattr(db._reader._backend, "table_exists"):
                        if not db._reader._backend.table_exists(table):
                            missing_tables.append(table)
                    else:
                        # Fallback: try to load table and catch error
                        try:
                            if table not in db.tables:
                                db.load_table(table)
                        except Exception:
                            missing_tables.append(table)

                if missing_tables:
                    logger.warning(
                        f"State {state} is missing GRM tables: {missing_tables}. "
                        "Growth data not available."
                    )
                    missing_grm_states.append(state)
                    continue

                kwargs = {
                    "land_type": land_type,
                    "measure": measure,
                    "variance": True,
                }
                if by_species:
                    kwargs["grp_by"] = "SPCD"
                if tree_domain:
                    kwargs["tree_domain"] = tree_domain

                try:
                    # Use db.growth() method which handles MotherDuck type compatibility
                    result_df = db.growth(**kwargs)
                    df = (
                        result_df.to_pandas()
                        if hasattr(result_df, "to_pandas")
                        else result_df
                    )
                    df["STATE"] = state
                    results.append(df)
                except Exception as e:
                    logger.error(f"Error querying growth for {state}: {e}")
                    missing_grm_states.append(state)
                    continue

        # If no states had GRM data, return error response
        if not results:
            error_msg = (
                f"Growth data is not available for the requested state(s): {states}. "
                "Growth estimation requires GRM (Growth-Removal-Mortality) tables "
                "(TREE_GRM_COMPONENT, TREE_GRM_MIDPT, TREE_GRM_BEGIN, BEGINEND) "
                "which are not available in all FIA databases."
            )
            if missing_grm_states:
                error_msg += f" Missing GRM data for: {', '.join(missing_grm_states)}"

            return {
                "error": error_msg,
                "states": states,
                "missing_grm_states": missing_grm_states,
                "available_metrics": [
                    "area",
                    "volume",
                    "biomass",
                    "tpa",
                    "mortality",
                    "removals",
                ],
                "source": "USDA Forest Service FIA (pyFIA)",
            }

        combined = pd.concat(results, ignore_index=True)

        # Growth estimator returns GROWTH_TOTAL and GROWTH_ACRE columns
        total_growth = (
            float(combined["GROWTH_TOTAL"].sum())
            if "GROWTH_TOTAL" in combined.columns
            else 0.0
        )

        # Get SE if available
        se_col = None
        if "GROWTH_TOTAL_SE" in combined.columns:
            se_col = "GROWTH_TOTAL_SE"

        if se_col:
            # Calculate SE as percentage of total
            total_se = float(combined[se_col].sum())
            se_pct = (total_se / total_growth * 100) if total_growth > 0 else 0.0
        else:
            se_pct = 0.0

        # Build base response with optional warning about missing states
        base_response = {
            "states": states,
            "measure": measure,
            "land_type": land_type,
            "se_percent": se_pct,
            "by_species": combined.to_dict("records") if by_species else None,
            "source": "USDA Forest Service FIA (pyFIA validated)",
        }

        # Add warning if some states were missing GRM data
        if missing_grm_states:
            base_response["warning"] = (
                f"Growth data not available for: {', '.join(missing_grm_states)}. "
                "Results only include states with GRM tables."
            )
            base_response["states_with_data"] = [
                s for s in states if s not in missing_grm_states
            ]

        # Format response based on measure type
        if measure == "volume":
            return {
                **base_response,
                "total_growth_cuft": total_growth,
                "total_growth_million_cuft": total_growth / 1e6,
            }
        elif measure == "biomass":
            return {
                **base_response,
                "total_growth_tons": total_growth,
                "total_growth_million_tons": total_growth / 1e6,
            }
        else:  # count
            return {
                **base_response,
                "total_growth_trees": total_growth,
            }

    async def query_area_change(
        self,
        states: list[str],
        land_type: str = "forest",
        change_type: str = "net",
        grp_by: str | None = None,
    ) -> dict:
        """Query forest area change across states."""
        results = []

        for state in states:
            state = state.upper()

            with self._get_fia_connection(state) as db:
                kwargs = {
                    "land_type": land_type,
                    "change_type": change_type,
                    "annual": True,
                    "variance": True,
                }
                if grp_by:
                    kwargs["grp_by"] = grp_by

                # Use db.area_change() method which handles MotherDuck type compatibility
                result_df = db.area_change(**kwargs)
                df = (
                    result_df.to_pandas()
                    if hasattr(result_df, "to_pandas")
                    else result_df
                )
                df["STATE"] = state
                results.append(df)

        combined = pd.concat(results, ignore_index=True)

        # Area change returns AREA_CHANGE_TOTAL column
        total_change = (
            float(combined["AREA_CHANGE_TOTAL"].sum())
            if "AREA_CHANGE_TOTAL" in combined.columns
            else 0.0
        )

        # Get SE if available
        se_col = None
        if "SE" in combined.columns:
            se_col = "SE"

        if se_col:
            # Calculate SE as percentage of total (absolute value for division)
            total_se = float(combined[se_col].sum())
            se_pct = (total_se / abs(total_change) * 100) if total_change != 0 else 0.0
        else:
            se_pct = 0.0

        return {
            "states": states,
            "land_type": land_type,
            "change_type": change_type,
            "total_area_change_acres_per_year": total_change,
            "se_percent": se_pct,
            "breakdown": combined.to_dict("records") if grp_by else None,
            "source": "USDA Forest Service FIA (pyFIA validated)",
        }

    async def query_by_stand_size(
        self,
        states: list[str],
        metric: str = "area",
        land_type: str = "forest",
        tree_domain: str | None = None,
    ) -> dict:
        """Query forest metrics grouped by stand size class.

        Args:
            states: List of state codes (e.g., ['NC', 'GA'])
            metric: Metric to query - 'area', 'volume', 'biomass', or 'tpa'
            land_type: Land type - 'forest', 'timber', or 'reserved'
            tree_domain: Optional tree filter (e.g., 'DIA >= 10.0')

        Returns:
            Dictionary with results grouped by stand size class
        """
        valid_metrics = ["area", "volume", "biomass", "tpa"]
        if metric not in valid_metrics:
            raise ValueError(f"Unknown metric: {metric}. Available: {valid_metrics}")

        results = []

        for state in states:
            state = state.upper()

            with self._get_fia_connection(state) as db:
                kwargs = {"grp_by": "STDSZCD", "variance": True}

                # Add metric-specific parameters
                if metric in ("area", "biomass", "tpa"):
                    kwargs["land_type"] = land_type
                if metric in ("volume", "biomass", "tpa") and tree_domain:
                    kwargs["tree_domain"] = tree_domain

                # Use db methods which handle MotherDuck type compatibility
                if metric == "area":
                    result_df = db.area(**kwargs)
                elif metric == "volume":
                    result_df = db.volume(**kwargs)
                elif metric == "biomass":
                    result_df = db.biomass(**kwargs)
                elif metric == "tpa":
                    result_df = db.tpa(**kwargs)
                else:
                    raise ValueError(f"Unknown metric: {metric}")

                df = (
                    result_df.to_pandas()
                    if hasattr(result_df, "to_pandas")
                    else result_df
                )
                df["STATE"] = state
                results.append(df)

        combined = pd.concat(results, ignore_index=True)

        # Get estimate and SE columns
        est_col = _get_estimate_column(combined, metric)
        se_col = _get_se_percent_column(combined, metric)

        # Calculate total
        total_estimate = float(combined[est_col].sum())

        # Calculate SE percent - handle different SE column formats
        if se_col and se_col in combined.columns:
            # If we have SE_PERCENT column, use it
            if "PERCENT" in se_col.upper():
                se_pct = float(combined[se_col].mean(skipna=True))
            else:
                # If we have absolute SE (e.g., AREA_SE), calculate percent
                # SE percent = (SE / estimate) * 100
                # Filter out NaN values before summing
                se_values = combined[se_col].dropna()
                total_se = float(se_values.sum()) if len(se_values) > 0 else 0.0
                se_pct = (
                    (total_se / total_estimate * 100) if total_estimate > 0 else 0.0
                )
        else:
            se_pct = 0.0

        return {
            "states": states,
            "metric": metric,
            "land_type": land_type,
            "tree_domain": tree_domain,
            "total_estimate": total_estimate,
            "se_percent": se_pct,
            "by_stand_size": combined.to_dict("records"),
            "source": "USDA Forest Service FIA (pyFIA validated)",
        }

    async def query_by_forest_type(
        self,
        states: list[str],
        metric: str = "area",
        land_type: str = "forest",
        tree_domain: str | None = None,
    ) -> dict:
        """Query forest metrics grouped by forest type.

        Args:
            states: List of state codes (e.g., ['NC', 'GA'])
            metric: Metric to query - 'area', 'volume', or 'biomass'
            land_type: Land type - 'forest', 'timber', or 'reserved'
            tree_domain: Optional tree filter (e.g., 'DIA >= 10.0')

        Returns:
            Dictionary with results grouped by forest type with human-readable names
        """
        valid_metrics = ["area", "volume", "biomass"]
        if metric not in valid_metrics:
            raise ValueError(f"Unknown metric: {metric}. Available: {valid_metrics}")

        results = []

        for state in states:
            state = state.upper()

            with self._get_fia_connection(state) as db:
                kwargs = {"grp_by": "FORTYPCD", "variance": True}

                # Add metric-specific parameters
                if metric in ("area", "biomass"):
                    kwargs["land_type"] = land_type
                if metric in ("volume", "biomass") and tree_domain:
                    kwargs["tree_domain"] = tree_domain

                # Use db methods which handle MotherDuck type compatibility
                if metric == "area":
                    result_df = db.area(**kwargs)
                elif metric == "volume":
                    result_df = db.volume(**kwargs)
                elif metric == "biomass":
                    result_df = db.biomass(**kwargs)
                else:
                    raise ValueError(f"Unknown metric: {metric}")

                df = (
                    result_df.to_pandas()
                    if hasattr(result_df, "to_pandas")
                    else result_df
                )
                df["STATE"] = state
                results.append(df)

        combined = pd.concat(results, ignore_index=True)

        # Always use hardcoded forest type names for consistency
        # The REF_FOREST_TYPE table is often missing from MotherDuck databases
        # and our hardcoded dictionary is based on official FIA documentation
        from .forest_types import get_forest_type_name

        # Add forest type names using our hardcoded dictionary
        combined["FOREST_TYPE_NAME"] = combined["FORTYPCD"].apply(
            lambda x: get_forest_type_name(int(x)) if pd.notna(x) else "Unknown"
        )
        logger.info("Using hardcoded forest type names from FIA documentation")

        # Get estimate and SE columns
        est_col = _get_estimate_column(combined, metric)
        se_col = _get_se_column(combined, metric)

        # Aggregation function for SE: combine using sqrt(sum(SE^2))
        def combine_se(x):
            return (x**2).sum() ** 0.5

        # Aggregate by forest type across states
        if "FOREST_TYPE_NAME" in combined.columns:
            agg_dict = {est_col: "sum"}
            if se_col:
                agg_dict[se_col] = combine_se
            grouped = (
                combined.groupby(["FORTYPCD", "FOREST_TYPE_NAME"], dropna=False)
                .agg(agg_dict)
                .reset_index()
            )
        else:
            # Final fallback if something went wrong
            agg_dict = {est_col: "sum"}
            if se_col:
                agg_dict[se_col] = combine_se
            grouped = (
                combined.groupby(["FORTYPCD"], dropna=False)
                .agg(agg_dict)
                .reset_index()
            )
            grouped["FOREST_TYPE_NAME"] = "Unknown"

        total_estimate = float(grouped[est_col].sum())
        # Calculate overall SE% properly
        if se_col and se_col in grouped.columns:
            overall_se_value = float((grouped[se_col].dropna() ** 2).sum() ** 0.5)
            overall_se = _calculate_se_percent(overall_se_value, total_estimate)
        else:
            overall_se = 0.0

        # Sort by estimate descending
        grouped = grouped.sort_values(est_col, ascending=False)

        # Format breakdown
        breakdown = []
        for _, row in grouped.iterrows():
            est_value = float(row[est_col])
            se_value = float(row[se_col]) if se_col and pd.notna(row.get(se_col)) else 0.0
            se_pct = _calculate_se_percent(se_value, est_value)
            breakdown.append(
                {
                    "FORTYPCD": int(row["FORTYPCD"])
                    if pd.notna(row["FORTYPCD"])
                    else None,
                    "FOREST_TYPE_NAME": row["FOREST_TYPE_NAME"]
                    if pd.notna(row.get("FOREST_TYPE_NAME"))
                    else "Unknown",
                    "ESTIMATE": est_value,
                    "SE_PERCENT": se_pct,
                }
            )

        return {
            "states": states,
            "metric": metric,
            "land_type": land_type,
            "tree_domain": tree_domain,
            "total_estimate": total_estimate,
            "se_percent": overall_se,
            "breakdown": breakdown,
            "source": "USDA Forest Service FIA (pyFIA validated)",
        }

    async def compare_states(
        self,
        states: list[str],
        metric: str,
        land_type: str = "forest",
    ) -> dict:
        """Compare a metric across states."""
        valid_metrics = ["area", "volume", "biomass", "tpa", "mortality", "growth"]

        if metric not in valid_metrics:
            raise ValueError(f"Unknown metric: {metric}. Available: {valid_metrics}")

        results = []

        for state in states:
            state = state.upper()
            try:
                with self._get_fia_connection(state) as db:
                    # Build kwargs based on metric
                    kwargs = {}
                    if metric in ("area", "biomass", "growth"):
                        kwargs["land_type"] = land_type
                    if metric in ("mortality", "growth"):
                        kwargs["variance"] = True

                    # Use db methods which handle MotherDuck type compatibility
                    if metric == "area":
                        result_df = db.area(**kwargs)
                    elif metric == "volume":
                        result_df = db.volume(**kwargs)
                    elif metric == "biomass":
                        result_df = db.biomass(**kwargs)
                    elif metric == "tpa":
                        result_df = db.tpa(**kwargs)
                    elif metric == "mortality":
                        result_df = db.mortality(**kwargs)
                    elif metric == "growth":
                        result_df = db.growth(**kwargs)
                    else:
                        raise ValueError(f"Unknown metric: {metric}")

                    df = (
                        result_df.to_pandas()
                        if hasattr(result_df, "to_pandas")
                        else result_df
                    )

                    est_col = _get_estimate_column(df, metric)
                    se_col = _get_se_column(df, metric)

                    estimate = float(df[est_col].sum())
                    # Calculate SE% properly
                    if se_col and se_col in df.columns:
                        combined_se = float((df[se_col].dropna() ** 2).sum() ** 0.5)
                        se_pct = _calculate_se_percent(combined_se, estimate)
                    else:
                        se_pct = None

                    results.append(
                        {
                            "state": state,
                            "estimate": estimate,
                            "se_percent": se_pct,
                            "error": None,
                        }
                    )
            except Exception as e:
                logger.error(f"Error querying {state}: {e}")
                results.append(
                    {
                        "state": state,
                        "estimate": None,
                        "se_percent": None,
                        "error": str(e),
                    }
                )

        # Sort by estimate descending
        results.sort(key=lambda x: x.get("estimate") or 0, reverse=True)

        return {
            "metric": metric,
            "states": results,
            "source": "USDA Forest Service FIA (pyFIA validated)",
        }

    async def query_by_ownership(
        self,
        states: list[str],
        metric: str = "area",
        land_type: str = "forest",
        tree_domain: str | None = None,
    ) -> dict:
        """Query forest metrics grouped by ownership.

        Args:
            states: List of two-letter state codes
            metric: Metric to query (area, volume, biomass, tpa)
            land_type: Land type filter (forest, timber)
            tree_domain: Optional tree filter (e.g., 'DIA >= 10.0')

        Returns:
            Dictionary with ownership breakdown and human-readable names
        """
        valid_metrics = ["area", "volume", "biomass", "tpa"]
        if metric not in valid_metrics:
            raise ValueError(f"Unknown metric: {metric}. Available: {valid_metrics}")

        # Ownership code to name mapping (matching pyFIA conventions)
        ownership_names = {
            10: "Forest Service",
            20: "Other Federal",
            30: "State and Local Government",
            40: "Private",
        }

        results = []

        for state in states:
            state = state.upper()

            with self._get_fia_connection(state) as db:
                # Build kwargs based on metric
                kwargs = {"grp_by": "OWNGRPCD"}

                if metric in ("area", "biomass"):
                    kwargs["land_type"] = land_type
                if metric in ("volume", "tpa") and tree_domain:
                    kwargs["tree_domain"] = tree_domain

                # Execute the appropriate query
                if metric == "area":
                    result_df = db.area(**kwargs)
                elif metric == "volume":
                    result_df = db.volume(**kwargs)
                elif metric == "biomass":
                    result_df = db.biomass(variance=True, **kwargs)
                elif metric == "tpa":
                    result_df = db.tpa(**kwargs)

                df = (
                    result_df.to_pandas()
                    if hasattr(result_df, "to_pandas")
                    else result_df
                )
                df["STATE"] = state
                results.append(df)

        # Combine all states
        combined = pd.concat(results, ignore_index=True)

        # Filter out rows with null/NaN ownership codes before processing
        # Some plots may have missing ownership data which causes NaN conversion errors
        combined = combined[combined["OWNGRPCD"].notna()]

        # Get estimate column dynamically
        est_col = _get_estimate_column(combined, metric)
        se_col = _get_se_percent_column(combined, metric)

        # Group by ownership and aggregate
        ownership_breakdown = []
        for owngrpcd in sorted(combined["OWNGRPCD"].unique()):
            subset = combined[combined["OWNGRPCD"] == owngrpcd]
            estimate = float(subset[est_col].sum())

            # Calculate SE% properly: SE values need to be combined using variance propagation
            # For sums: Var(sum) = sum(Var) assuming independence, so SE = sqrt(sum(SE^2))
            if se_col and se_col in subset.columns:
                se_values = subset[se_col].dropna()
                # Combine SEs: sqrt(sum of squared SEs)
                combined_se = float((se_values**2).sum() ** 0.5)
                se_pct = _calculate_se_percent(combined_se, estimate)
            else:
                se_pct = 0.0

            ownership_breakdown.append(
                {
                    "OWNGRPCD": int(owngrpcd),
                    "ownership_name": ownership_names.get(
                        int(owngrpcd), f"Code {owngrpcd}"
                    ),
                    "estimate": estimate,
                    "se_percent": se_pct,
                }
            )

        # Sort by estimate descending
        ownership_breakdown.sort(key=lambda x: x["estimate"], reverse=True)

        # Calculate totals
        total_estimate = sum(row["estimate"] for row in ownership_breakdown)

        return {
            "states": states,
            "metric": metric,
            "land_type": land_type if metric in ("area", "biomass") else None,
            "tree_domain": tree_domain,
            "total_estimate": total_estimate,
            "ownership_breakdown": ownership_breakdown,
            "source": "USDA Forest Service FIA (pyFIA validated)",
        }

    # Singleton instance

    async def query_by_county(
        self,
        state: str,
        county_fips: int,
        metric: str = "area",
        land_type: str = "forest",
        by_species: bool = False,
        tree_domain: str | None = None,
    ) -> dict:
        """Query forest metrics by county.

        Args:
            state: Two-letter state code
            county_fips: County FIPS code (3-digit)
            metric: Metric to query (area, volume, biomass, tpa)
            land_type: Land type filter (forest, timber)
            by_species: Group results by species (volume, biomass, tpa only)
            tree_domain: Tree-level filter expression (volume, tpa only)

        Returns:
            Dictionary with metric results filtered to the specified county
        """
        state = state.upper()
        valid_metrics = ["area", "volume", "biomass", "tpa"]

        if metric not in valid_metrics:
            raise ValueError(f"Unknown metric: {metric}. Available: {valid_metrics}")

        with self._get_fia_connection(state) as db:
            # Use plot_domain to filter by COUNTYCD (PLOT-level attribute)
            plot_domain = f"COUNTYCD == {county_fips}"

            # Build kwargs based on metric
            kwargs = {"plot_domain": plot_domain}
            if metric in ("area", "biomass", "tpa"):
                kwargs["land_type"] = land_type

            if metric == "area":
                pass  # No additional kwargs needed
            elif metric == "volume":
                if by_species:
                    kwargs["grp_by"] = "SPCD"
                if tree_domain:
                    kwargs["tree_domain"] = tree_domain
            elif metric == "biomass":
                if by_species:
                    kwargs["grp_by"] = "SPCD"
                kwargs["variance"] = True
            elif metric == "tpa":
                if by_species:
                    kwargs["by_species"] = True
                if tree_domain:
                    kwargs["tree_domain"] = tree_domain

            # Execute query with plot_domain filter
            if metric == "area":
                result_df = db.area(**kwargs)
            elif metric == "volume":
                result_df = db.volume(**kwargs)
            elif metric == "biomass":
                result_df = db.biomass(**kwargs)
            elif metric == "tpa":
                result_df = db.tpa(**kwargs)
            else:
                raise ValueError(f"Unknown metric: {metric}")

            df = result_df.to_pandas() if hasattr(result_df, "to_pandas") else result_df

            if df.empty:
                return {
                    "state": state,
                    "county_fips": county_fips,
                    "metric": metric,
                    "error": f"No data found for county FIPS {county_fips} in {state}",
                    "hint": "Check that the county FIPS code is correct (3-digit code)",
                    "source": "USDA Forest Service FIA (pyFIA)",
                }

            # Get estimate and SE columns (df is already filtered to county)
            est_col = _get_estimate_column(df, metric)
            se_col = _get_se_column(df, metric)

            # Helper to calculate SE% for this function
            def calc_se_pct(estimate: float) -> float:
                if se_col and se_col in df.columns:
                    combined_se = float((df[se_col].dropna() ** 2).sum() ** 0.5)
                    return _calculate_se_percent(combined_se, estimate)
                return 0.0

            # Format response based on metric
            if metric == "area":
                total_area = float(df[est_col].sum())
                se_pct = calc_se_pct(total_area)
                return {
                    "state": state,
                    "county_fips": county_fips,
                    "metric": metric,
                    "land_type": land_type,
                    "total_area_acres": total_area,
                    "se_percent": se_pct,
                    "source": "USDA Forest Service FIA (pyFIA validated)",
                }
            elif metric == "volume":
                total_vol = float(df[est_col].sum())
                se_pct = calc_se_pct(total_vol)
                return {
                    "state": state,
                    "county_fips": county_fips,
                    "metric": metric,
                    "total_volume_cuft": total_vol,
                    "total_volume_billion_cuft": total_vol / 1e9,
                    "se_percent": se_pct,
                    "by_species": df.to_dict("records") if by_species else None,
                    "source": "USDA Forest Service FIA (pyFIA validated)",
                }
            elif metric == "biomass":
                total_biomass = (
                    float(df["BIO_TOTAL"].sum()) if "BIO_TOTAL" in df.columns else 0.0
                )
                total_carbon = (
                    float(df["CARB_TOTAL"].sum())
                    if "CARB_TOTAL" in df.columns
                    else total_biomass * 0.47
                )
                se_pct = calc_se_pct(total_biomass)
                return {
                    "state": state,
                    "county_fips": county_fips,
                    "metric": metric,
                    "land_type": land_type,
                    "total_biomass_tons": total_biomass,
                    "carbon_mmt": total_carbon / 1e6,
                    "se_percent": se_pct,
                    "by_species": df.to_dict("records") if by_species else None,
                    "source": "USDA Forest Service FIA (pyFIA validated)",
                }
            elif metric == "tpa":
                total_tpa = float(df[est_col].sum())
                se_pct = calc_se_pct(total_tpa)
                return {
                    "state": state,
                    "county_fips": county_fips,
                    "metric": metric,
                    "land_type": land_type,
                    "total_tpa": total_tpa,
                    "se_percent": se_pct,
                    "by_species": df.to_dict("records") if by_species else None,
                    "source": "USDA Forest Service FIA (pyFIA validated)",
                }
            else:
                raise ValueError(f"Unknown metric: {metric}")

    async def lookup_species(
        self,
        spcd: int | None = None,
        common_name: str | None = None,
        state: str | None = None,
        limit: int = 10,
    ) -> dict:
        """
        Lookup species information using in-memory species reference data.

        This method provides three main use cases:
        1. Convert species code (SPCD) to common/scientific names
        2. Search for species by common name to get codes
        3. List top species by volume in a given state

        Parameters
        ----------
        spcd : int, optional
            Species code to lookup (e.g., 131 for loblolly pine)
        common_name : str, optional
            Common name to search for (case-insensitive, partial match)
        state : str, optional
            State code to get top species for (e.g., 'NC', 'GA')
        limit : int, default 10
            Maximum number of results to return for searches

        Returns
        -------
        dict
            Species information including SPCD, common name, scientific name,
            and optionally volume data for state queries
        """
        try:
            # Case 1: Lookup by species code
            if spcd is not None:
                species_info = species_data.lookup_by_code(spcd)
                if species_info is None:
                    return {
                        "mode": "lookup_by_code",
                        "spcd": spcd,
                        "found": False,
                        "message": f"No species found with code {spcd}",
                    }

                return {
                    "mode": "lookup_by_code",
                    "spcd": spcd,
                    "common_name": species_info["common_name"],
                    "scientific_name": species_info["scientific_name"],
                    "found": True,
                }

            # Case 2: Search by common name
            if common_name is not None:
                results = species_data.search_by_name(common_name, limit=limit)

                if not results:
                    return {
                        "mode": "search_by_name",
                        "search_term": common_name,
                        "found": False,
                        "count": 0,
                        "results": [],
                        "message": f"No species found matching '{common_name}'",
                    }

                return {
                    "mode": "search_by_name",
                    "search_term": common_name,
                    "found": True,
                    "count": len(results),
                    "results": results,
                }

            # Case 3: List top species by volume in a state
            if state is not None:
                state = state.upper()

                with self._get_fia_connection(state) as db:
                    # Query volume by species for the state
                    volume_df = db.volume(grp_by="SPCD")
                    vol_pd = (
                        volume_df.to_pandas()
                        if hasattr(volume_df, "to_pandas")
                        else volume_df
                    )

                    # Get estimate column
                    vol_col = _get_estimate_column(vol_pd, "volume")

                    # Sort by volume and take top N
                    top_species = vol_pd.nlargest(limit, vol_col)

                    # Add species names from our reference data
                    results = []
                    for _, row in top_species.iterrows():
                        spcd_val = int(row["SPCD"])
                        species_info = species_data.lookup_by_code(spcd_val)

                        if species_info:
                            results.append(
                                {
                                    "spcd": spcd_val,
                                    "common_name": species_info["common_name"],
                                    "scientific_name": species_info["scientific_name"],
                                    "volume_cuft": float(row[vol_col]),
                                }
                            )
                        else:
                            # Unknown species - include anyway with placeholder name
                            results.append(
                                {
                                    "spcd": spcd_val,
                                    "common_name": f"Unknown (SPCD {spcd_val})",
                                    "scientific_name": None,
                                    "volume_cuft": float(row[vol_col]),
                                }
                            )

                    return {
                        "mode": "top_species_by_state",
                        "state": state,
                        "count": len(results),
                        "results": results,
                    }

            # No valid parameters provided
            return {
                "error": "Must provide spcd, common_name, or state parameter",
            }

        except Exception as e:
            logger.error(f"Error in lookup_species: {e}", exc_info=True)
            return {
                "error": str(e),
                "spcd": spcd,
                "common_name": common_name,
                "state": state,
            }

fia_service = FIAService()

"""Service layer for pyFIA operations."""

import logging
import re
from collections.abc import Generator
from contextlib import contextmanager
from functools import lru_cache

import duckdb
import pandas as pd

from ..config import settings
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
    metric_cols = {
        "area": ["AREA", "area", "ESTIMATE", "estimate"],
        "volume": ["VOLUME", "volume", "VOLCFNET", "ESTIMATE", "estimate"],
        "biomass": ["BIOMASS", "biomass", "DRYBIO_AG", "ESTIMATE", "estimate"],
        "tpa": ["TPA", "tpa", "ESTIMATE", "estimate"],
        "mortality": ["MORTALITY", "mortality", "ESTIMATE", "estimate"],
        "growth": ["GROWTH", "growth", "ESTIMATE", "estimate"],
    }

    candidates = metric_cols.get(metric, ["ESTIMATE", "estimate"])
    for col in candidates:
        if col in df.columns:
            return col

    # Fallback: first numeric column that's not SE/variance related
    for col in df.columns:
        if df[col].dtype in ['float64', 'int64'] and not any(x in col.upper() for x in ['SE', 'VAR', 'CV', 'CI', 'PLOT', 'YEAR']):
            return col

    raise KeyError(f"Could not find estimate column. Available: {list(df.columns)}")


def _get_se_percent_column(df: pd.DataFrame, metric: str) -> str | None:
    """Find the SE percent column name dynamically."""
    # Try common patterns
    candidates = [
        f"{metric.upper()}_SE_PERCENT",
        f"{metric.upper()}_SE_PERC",
        "SE_PERCENT",
        "se_percent",
        "CV",
        "cv",
    ]

    for col in candidates:
        if col in df.columns:
            return col

    # Look for any column containing SE_PERC or cv
    for col in df.columns:
        if "SE_PERC" in col.upper() or col.upper() == "CV":
            return col

    return None


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
                with MotherDuckFIA(database, motherduck_token=self._motherduck_token) as db:
                    db.clip_most_recent()
                    yield db
            else:
                # State not found in MotherDuck, fall back to local storage
                logger.warning(f"State {state} not found in MotherDuck, falling back to local storage")
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
                df = result_df.to_pandas() if hasattr(result_df, "to_pandas") else result_df
                df["STATE"] = state
                results.append(df)

        combined = pd.concat(results, ignore_index=True)

        est_col = _get_estimate_column(combined, "area")
        se_col = _get_se_percent_column(combined, "area")

        total_area = float(combined[est_col].sum())
        se_pct = float(combined[se_col].mean()) if se_col else 0.0

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
                df = result_df.to_pandas() if hasattr(result_df, "to_pandas") else result_df
                df["STATE"] = state
                results.append(df)

        combined = pd.concat(results, ignore_index=True)

        est_col = _get_estimate_column(combined, "volume")
        se_col = _get_se_percent_column(combined, "volume")

        total_vol = float(combined[est_col].sum())
        se_pct = float(combined[se_col].mean()) if se_col else 0.0

        return {
            "states": states,
            "total_volume_cuft": total_vol,
            "total_volume_billion_cuft": total_vol / 1e9,
            "se_percent": se_pct,
            "by_species": combined.to_dict("records") if by_species else None,
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
                kwargs = {"land_type": land_type}
                if by_species:
                    kwargs["grp_by"] = "SPCD"

                # Use db.biomass() method which handles MotherDuck type compatibility
                result_df = db.biomass(**kwargs)
                df = result_df.to_pandas() if hasattr(result_df, "to_pandas") else result_df
                df["STATE"] = state
                results.append(df)

        combined = pd.concat(results, ignore_index=True)

        est_col = _get_estimate_column(combined, "biomass")
        se_col = _get_se_percent_column(combined, "biomass")

        total_biomass = float(combined[est_col].sum())
        se_pct = float(combined[se_col].mean()) if se_col else 0.0

        return {
            "states": states,
            "land_type": land_type,
            "total_biomass_tons": total_biomass,
            "carbon_mmt": total_biomass * 0.5 / 1e6,  # Standard conversion
            "se_percent": se_pct,
            "by_species": combined.to_dict("records") if by_species else None,
            "source": "USDA Forest Service FIA (pyFIA validated)",
        }

    async def query_tpa(
        self,
        states: list[str],
        tree_domain: str = "STATUSCD == 1",
        by_species: bool = False,
    ) -> dict:
        """Query trees per acre."""
        results = []

        for state in states:
            state = state.upper()

            with self._get_fia_connection(state) as db:
                kwargs = {"tree_domain": tree_domain}
                if by_species:
                    kwargs["grp_by"] = "SPCD"

                # Use db.tpa() method which handles MotherDuck type compatibility
                result_df = db.tpa(**kwargs)
                df = result_df.to_pandas() if hasattr(result_df, "to_pandas") else result_df
                df["STATE"] = state
                results.append(df)

        combined = pd.concat(results, ignore_index=True)

        return {
            "states": states,
            "tree_domain": tree_domain,
            "results": combined.to_dict("records"),
            "source": "USDA Forest Service FIA (pyFIA validated)",
        }

    async def compare_states(
        self,
        states: list[str],
        metric: str,
        land_type: str = "forest",
    ) -> dict:
        """Compare a metric across states."""
        valid_metrics = ["area", "volume", "biomass", "tpa"]

        if metric not in valid_metrics:
            raise ValueError(f"Unknown metric: {metric}. Available: {valid_metrics}")

        results = []

        for state in states:
            state = state.upper()
            try:
                with self._get_fia_connection(state) as db:
                    # Build kwargs based on metric
                    kwargs = {}
                    if metric in ("area", "biomass"):
                        kwargs["land_type"] = land_type

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

                    df = result_df.to_pandas() if hasattr(result_df, "to_pandas") else result_df

                    est_col = _get_estimate_column(df, metric)
                    se_col = _get_se_percent_column(df, metric)

                    results.append({
                        "state": state,
                        "estimate": float(df[est_col].sum()),
                        "se_percent": float(df[se_col].mean()) if se_col else None,
                        "error": None,
                    })
            except Exception as e:
                logger.error(f"Error querying {state}: {e}")
                results.append({
                    "state": state,
                    "estimate": None,
                    "se_percent": None,
                    "error": str(e),
                })

        # Sort by estimate descending
        results.sort(key=lambda x: x.get("estimate") or 0, reverse=True)

        return {
            "metric": metric,
            "states": results,
            "source": "USDA Forest Service FIA (pyFIA validated)",
        }


# Singleton instance
fia_service = FIAService()

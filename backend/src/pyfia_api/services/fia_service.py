"""Service layer for pyFIA operations."""

import logging

import pandas as pd

from .storage import storage

logger = logging.getLogger(__name__)


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

    def _get_db_path(self, state: str) -> str:
        """Get path to state database using tiered storage."""
        return self.storage.get_db_path(state)

    async def query_area(
        self,
        states: list[str],
        land_type: str = "forest",
        grp_by: str | None = None,
    ) -> dict:
        """Query forest area across states."""
        from pyfia import FIA, area

        results = []

        for state in states:
            state = state.upper()
            db_path = self._get_db_path(state)

            with FIA(db_path) as db:
                result_df = area(db, land_type=land_type, grp_by=grp_by)
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
        from pyfia import FIA, volume

        results = []

        for state in states:
            state = state.upper()
            db_path = self._get_db_path(state)

            with FIA(db_path) as db:
                kwargs = {}
                if by_species:
                    kwargs["grp_by"] = "SPCD"
                if tree_domain:
                    kwargs["tree_domain"] = tree_domain

                result_df = volume(db, **kwargs)
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
        from pyfia import FIA, biomass

        results = []

        for state in states:
            state = state.upper()
            db_path = self._get_db_path(state)

            with FIA(db_path) as db:
                kwargs = {"land_type": land_type}
                if by_species:
                    kwargs["grp_by"] = "SPCD"

                result_df = biomass(db, **kwargs)
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
        from pyfia import FIA, tpa

        results = []

        for state in states:
            state = state.upper()
            db_path = self._get_db_path(state)

            with FIA(db_path) as db:
                kwargs = {"tree_domain": tree_domain}
                if by_species:
                    kwargs["grp_by"] = "SPCD"

                result_df = tpa(db, **kwargs)
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
        from pyfia import FIA, area, volume, biomass, tpa

        metric_funcs = {
            "area": area,
            "volume": volume,
            "biomass": biomass,
            "tpa": tpa,
        }

        if metric not in metric_funcs:
            raise ValueError(f"Unknown metric: {metric}. Available: {list(metric_funcs.keys())}")

        func = metric_funcs[metric]
        results = []

        for state in states:
            state = state.upper()
            try:
                db_path = self._get_db_path(state)

                with FIA(db_path) as db:
                    # Build kwargs based on metric
                    kwargs = {}
                    if metric in ("area", "biomass"):
                        kwargs["land_type"] = land_type

                    result_df = func(db, **kwargs)
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

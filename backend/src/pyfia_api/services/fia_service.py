"""Service layer for pyFIA operations."""

import logging
from functools import lru_cache
from pathlib import Path

import pandas as pd

from ..config import settings

logger = logging.getLogger(__name__)


class FIAService:
    """Service for querying FIA data using pyFIA."""

    def __init__(self, data_dir: str | None = None):
        self.data_dir = data_dir or settings.data_dir
        Path(self.data_dir).mkdir(parents=True, exist_ok=True)

    @lru_cache(maxsize=100)
    def _get_db_path(self, state: str) -> str:
        """Download and cache state database path."""
        from pyfia import download

        logger.info(f"Loading FIA data for {state}...")
        return download(state, dir=self.data_dir)

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
                db.clip_by_state(state)
                db.clip_most_recent(eval_type="EXPALL")

                result_df = area(db, land_type=land_type, grp_by=grp_by)
                df = result_df.to_pandas() if hasattr(result_df, "to_pandas") else result_df
                df["STATE"] = state
                results.append(df)

        combined = pd.concat(results, ignore_index=True)

        return {
            "states": states,
            "land_type": land_type,
            "total_area_acres": float(combined["ESTIMATE"].sum()),
            "se_percent": float(combined["SE_PERCENT"].mean()),
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
                db.clip_by_state(state)
                db.clip_most_recent(eval_type="EXPVOL")

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
        total_vol = float(combined["ESTIMATE"].sum())

        return {
            "states": states,
            "total_volume_cuft": total_vol,
            "total_volume_billion_cuft": total_vol / 1e9,
            "se_percent": float(combined["SE_PERCENT"].mean()),
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
                db.clip_by_state(state)
                db.clip_most_recent(eval_type="EXPVOL")

                result_df = biomass(db, land_type=land_type, by_species=by_species)
                df = result_df.to_pandas() if hasattr(result_df, "to_pandas") else result_df
                df["STATE"] = state
                results.append(df)

        combined = pd.concat(results, ignore_index=True)
        total_biomass = float(combined["ESTIMATE"].sum())

        return {
            "states": states,
            "land_type": land_type,
            "total_biomass_tons": total_biomass,
            "carbon_mmt": total_biomass * 0.5 / 1e6,  # Standard conversion
            "se_percent": float(combined["SE_PERCENT"].mean()),
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
                db.clip_by_state(state)
                db.clip_most_recent(eval_type="EXPVOL")

                result_df = tpa(db, tree_domain=tree_domain, by_species=by_species)
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
        from pyfia import FIA, area, volume, biomass, tpa, mortality, growth

        metric_funcs = {
            "area": (area, "EXPALL"),
            "volume": (volume, "EXPVOL"),
            "biomass": (biomass, "EXPVOL"),
            "tpa": (tpa, "EXPVOL"),
            "mortality": (mortality, "EXPMORT"),
            "growth": (growth, "EXPGROW"),
        }

        if metric not in metric_funcs:
            raise ValueError(f"Unknown metric: {metric}")

        func, eval_type = metric_funcs[metric]
        results = []

        for state in states:
            state = state.upper()
            try:
                db_path = self._get_db_path(state)

                with FIA(db_path) as db:
                    db.clip_by_state(state)
                    db.clip_most_recent(eval_type=eval_type)

                    # Some functions accept land_type
                    if metric in ("area", "biomass"):
                        result_df = func(db, land_type=land_type)
                    else:
                        result_df = func(db)

                    df = result_df.to_pandas() if hasattr(result_df, "to_pandas") else result_df

                    results.append({
                        "state": state,
                        "estimate": float(df["ESTIMATE"].sum()),
                        "se_percent": float(df["SE_PERCENT"].mean()),
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

"""MotherDuck-compatible FIA class.

This module provides a custom FIA class that works with MotherDuck
instead of requiring local DuckDB files.
"""

import logging
import warnings
from typing import Any, Dict, List, Optional, Union

import duckdb
import polars as pl

logger = logging.getLogger(__name__)


class MotherDuckBackend:
    """DuckDB backend that connects to MotherDuck."""

    def __init__(
        self,
        database: str,
        motherduck_token: str,
        read_only: bool = True,
    ):
        """
        Initialize MotherDuck backend.

        Parameters
        ----------
        database : str
            MotherDuck database name (e.g., "fia_ga")
        motherduck_token : str
            MotherDuck authentication token
        read_only : bool
            Open database in read-only mode (default True)
        """
        self.database = database
        self.motherduck_token = motherduck_token
        self.read_only = read_only
        self._connection: Optional[duckdb.DuckDBPyConnection] = None
        self._schema_cache: Dict[str, Dict[str, str]] = {}

    def connect(self) -> None:
        """Establish MotherDuck connection."""
        if self._connection is not None:
            return

        try:
            conn_string = f"md:{self.database}?motherduck_token={self.motherduck_token}"
            self._connection = duckdb.connect(conn_string, read_only=self.read_only)
            logger.info(f"Connected to MotherDuck database: {self.database}")
        except Exception as e:
            logger.error(f"Failed to connect to MotherDuck: {e}")
            raise

    def disconnect(self) -> None:
        """Close MotherDuck connection."""
        if self._connection is not None:
            try:
                self._connection.close()
                self._connection = None
                logger.info("Disconnected from MotherDuck database")
            except Exception as e:
                logger.error(f"Error closing MotherDuck connection: {e}")

    def execute_query(self, query: str) -> pl.DataFrame:
        """Execute SQL query and return results as Polars DataFrame."""
        if not self._connection:
            self.connect()

        try:
            result = self._connection.execute(query)
            df: pl.DataFrame = result.pl()
            return df
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise

    def get_table_schema(self, table_name: str) -> Dict[str, str]:
        """Get schema information for a table."""
        if table_name in self._schema_cache:
            return self._schema_cache[table_name]

        if not self._connection:
            self.connect()

        try:
            result = self._connection.execute(f"DESCRIBE {table_name}").fetchall()
            schema = {row[0]: row[1] for row in result}
            self._schema_cache[table_name] = schema
            return schema
        except Exception as e:
            logger.error(f"Failed to get schema for table {table_name}: {e}")
            raise

    def is_cn_column(self, column_name: str) -> bool:
        """Check if a column is a CN (Control Number) field."""
        return column_name.endswith("_CN") or column_name == "CN"

    def build_select_clause(
        self, table_name: str, columns: Optional[List[str]] = None
    ) -> str:
        """Build SELECT clause with appropriate type casting for FIA data."""
        schema = self.get_table_schema(table_name)

        if columns is None:
            columns = list(schema.keys())

        select_parts = []
        for col in columns:
            if self.is_cn_column(col):
                select_parts.append(f"CAST({col} AS VARCHAR) AS {col}")
            else:
                select_parts.append(col)

        return ", ".join(select_parts)

    def read_table(
        self,
        table_name: str,
        columns: Optional[List[str]] = None,
        where: Optional[str] = None,
        lazy: bool = True,
    ) -> Union[pl.DataFrame, pl.LazyFrame]:
        """Read a table from the FIA database."""
        select_clause = self.build_select_clause(table_name, columns)
        query = f"SELECT {select_clause} FROM {table_name}"

        if where:
            query += f" WHERE {where}"

        df = self.execute_query(query)

        if lazy:
            return df.lazy()
        return df


def _add_parsed_evalid_columns(
    df: pl.DataFrame | pl.LazyFrame,
) -> pl.DataFrame | pl.LazyFrame:
    """Add parsed EVALID columns to a DataFrame for sorting."""
    return df.with_columns(
        [
            pl.when(pl.col("EVALID").cast(pl.Utf8).str.slice(2, 2).cast(pl.Int32) <= 30)
            .then(2000 + pl.col("EVALID").cast(pl.Utf8).str.slice(2, 2).cast(pl.Int32))
            .otherwise(
                1900 + pl.col("EVALID").cast(pl.Utf8).str.slice(2, 2).cast(pl.Int32)
            )
            .alias("EVALID_YEAR"),
            pl.col("EVALID")
            .cast(pl.Utf8)
            .str.slice(0, 2)
            .cast(pl.Int32)
            .alias("EVALID_STATE"),
            pl.col("EVALID")
            .cast(pl.Utf8)
            .str.slice(4, 2)
            .cast(pl.Int32)
            .alias("EVALID_TYPE"),
        ]
    )


class MotherDuckFIA:
    """
    FIA class that uses MotherDuck for data storage.

    This class provides the same interface as pyFIA's FIA class
    but connects to MotherDuck instead of local DuckDB files.
    """

    def __init__(self, state: str, motherduck_token: str):
        """
        Initialize MotherDuck FIA connection.

        Parameters
        ----------
        state : str
            State abbreviation (e.g., "GA", "NC")
        motherduck_token : str
            MotherDuck authentication token
        """
        self.state = state.upper()
        self.database = f"fia_{state.lower()}"
        self.motherduck_token = motherduck_token

        self.tables: Dict[str, pl.LazyFrame] = {}
        self.evalid: Optional[List[int]] = None
        self.most_recent: bool = False
        self.state_filter: Optional[List[int]] = None
        self._valid_plot_cns: Optional[List[str]] = None

        self._backend = MotherDuckBackend(
            database=self.database,
            motherduck_token=motherduck_token,
        )
        self._backend.connect()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, _exc_type, _exc_val, _exc_tb):
        """Context manager exit."""
        self._backend.disconnect()

    def load_table(
        self, table_name: str, columns: Optional[List[str]] = None
    ) -> pl.LazyFrame:
        """Load a table from the FIA database as a lazy frame."""
        base_where_clause = None
        if self.state_filter and table_name in ["PLOT", "COND", "TREE"]:
            state_list = ", ".join(str(s) for s in self.state_filter)
            base_where_clause = f"STATECD IN ({state_list})"

        if self.evalid and table_name in ["TREE", "COND"]:
            valid_plot_cns = self._get_valid_plot_cns()
            if valid_plot_cns:
                batch_size = 900
                dfs = []

                for i in range(0, len(valid_plot_cns), batch_size):
                    batch = valid_plot_cns[i : i + batch_size]
                    cn_str = ", ".join(f"'{cn}'" for cn in batch)
                    plt_cn_where = f"PLT_CN IN ({cn_str})"

                    if base_where_clause:
                        where_clause = f"{base_where_clause} AND {plt_cn_where}"
                    else:
                        where_clause = plt_cn_where

                    df = self._backend.read_table(
                        table_name,
                        columns=columns,
                        where=where_clause,
                        lazy=True,
                    )
                    dfs.append(df)

                if len(dfs) == 1:
                    result = dfs[0]
                else:
                    result = pl.concat(dfs)

                self.tables[table_name] = result
                return self.tables[table_name]

        df = self._backend.read_table(
            table_name,
            columns=columns,
            where=base_where_clause,
            lazy=True,
        )

        self.tables[table_name] = df
        return self.tables[table_name]

    def _get_valid_plot_cns(self) -> Optional[List[str]]:
        """Get plot CNs valid for the current EVALID filter."""
        if self.evalid is None:
            return None

        if self._valid_plot_cns is not None:
            return self._valid_plot_cns

        evalid_str = ", ".join(str(e) for e in self.evalid)
        ppsa = self._backend.read_table(
            "POP_PLOT_STRATUM_ASSGN",
            columns=["PLT_CN"],
            where=f"EVALID IN ({evalid_str})",
            lazy=True,
        ).collect()

        self._valid_plot_cns = ppsa["PLT_CN"].unique().to_list()
        return self._valid_plot_cns

    def find_evalid(
        self,
        most_recent: bool = True,
        state: Optional[Union[int, List[int]]] = None,
        year: Optional[Union[int, List[int]]] = None,
        eval_type: Optional[str] = None,
    ) -> List[int]:
        """Find EVALID values matching criteria."""
        try:
            if "POP_EVAL" not in self.tables:
                self.load_table("POP_EVAL")
            if "POP_EVAL_TYP" not in self.tables:
                self.load_table("POP_EVAL_TYP")

            pop_eval = self.tables["POP_EVAL"].collect()
            pop_eval_typ = self.tables["POP_EVAL_TYP"].collect()

            if "EVALID" not in pop_eval.columns:
                raise ValueError(f"EVALID column not found in POP_EVAL table")

            df = pop_eval.join(
                pop_eval_typ, left_on="CN", right_on="EVAL_CN", how="left"
            )
        except Exception as e:
            warnings.warn(f"Could not load evaluation tables: {e}")
            return []

        if state is not None:
            if isinstance(state, int):
                state = [state]
            df = df.filter(pl.col("STATECD").is_in(state))

        if year is not None:
            if isinstance(year, int):
                year = [year]
            df = df.filter(pl.col("END_INVYR").is_in(year))

        if eval_type is not None:
            if eval_type.upper() == "ALL":
                eval_type_full = "EXPALL"
            else:
                eval_type_full = f"EXP{eval_type}"
            df = df.filter(pl.col("EVAL_TYP") == eval_type_full)

        if most_recent:
            df = _add_parsed_evalid_columns(df)

            if not df.is_empty():
                df = (
                    df.sort(
                        ["STATECD", "EVAL_TYP", "EVALID_YEAR", "EVALID_TYPE"],
                        descending=[False, False, True, False],
                    )
                    .group_by(["STATECD", "EVAL_TYP"])
                    .first()
                    .drop(["EVALID_YEAR", "EVALID_STATE", "EVALID_TYPE"])
                )

        evalids = df.select("EVALID").unique().sort("EVALID")["EVALID"].to_list()
        return evalids

    def clip_by_evalid(self, evalid: Union[int, List[int]]) -> "MotherDuckFIA":
        """Filter FIA data by EVALID."""
        if isinstance(evalid, int):
            evalid = [evalid]

        self.evalid = evalid
        self._valid_plot_cns = None
        self.tables.clear()
        return self

    def clip_by_state(
        self,
        state: Union[int, List[int]],
        most_recent: bool = True,
        eval_type: Optional[str] = "ALL",
    ) -> "MotherDuckFIA":
        """Filter FIA data by state code(s)."""
        if isinstance(state, int):
            state = [state]

        self.state_filter = state

        if eval_type is not None:
            evalids = self.find_evalid(
                state=state, most_recent=most_recent, eval_type=eval_type
            )
            if evalids:
                self.clip_by_evalid([evalids[0]] if len(evalids) > 1 else evalids)
        else:
            evalids = self.find_evalid(state=state, most_recent=most_recent)
            if evalids:
                self.clip_by_evalid(evalids)

        return self

    def clip_most_recent(self, eval_type: str = "VOL") -> "MotherDuckFIA":
        """Filter to most recent evaluation of specified type."""
        self.most_recent = True
        state_filter = getattr(self, "state_filter", None)
        evalids = self.find_evalid(
            most_recent=True,
            eval_type=eval_type,
            state=state_filter,
        )

        if not evalids:
            warnings.warn(f"No evaluations found for type {eval_type}")
            return self

        return self.clip_by_evalid(evalids)

    def get_plots(self, columns: Optional[List[str]] = None) -> pl.DataFrame:
        """Get PLOT table filtered by current EVALID and state settings."""
        if "PLOT" not in self.tables:
            self.load_table("PLOT")

        if self.evalid:
            evalid_str = ", ".join(str(e) for e in self.evalid)
            ppsa = self._backend.read_table(
                "POP_PLOT_STRATUM_ASSGN",
                columns=["PLT_CN", "STRATUM_CN", "EVALID"],
                where=f"EVALID IN ({evalid_str})",
                lazy=True,
            )

            plots = self.tables["PLOT"].join(
                ppsa.select(["PLT_CN", "EVALID"]).unique(),
                left_on="CN",
                right_on="PLT_CN",
                how="inner",
            )
        else:
            plots = self.tables["PLOT"]

        if columns:
            plots = plots.select(columns)

        plots_df = plots.collect()

        if "PLT_CN" not in plots_df.columns and "CN" in plots_df.columns:
            plots_df = plots_df.with_columns(pl.col("CN").alias("PLT_CN"))

        return plots_df

    def get_trees(self, columns: Optional[List[str]] = None) -> pl.DataFrame:
        """Get TREE table filtered by current EVALID and state settings."""
        if "TREE" not in self.tables:
            self.load_table("TREE")

        trees = self.tables["TREE"]

        if columns:
            trees = trees.select(columns)

        return trees.collect()

    def get_conditions(self, columns: Optional[List[str]] = None) -> pl.DataFrame:
        """Get COND table filtered by current EVALID and state settings."""
        if "COND" not in self.tables:
            self.load_table("COND")

        conds = self.tables["COND"]

        if columns:
            conds = conds.select(columns)

        return conds.collect()

    def prepare_estimation_data(self) -> Dict[str, pl.DataFrame]:
        """Prepare standard set of tables for estimation functions."""
        if not self.evalid and not self.most_recent:
            warnings.warn("No EVALID filter set. Using most recent volume evaluation.")
            self.clip_most_recent(eval_type="VOL")

        if "POP_STRATUM" not in self.tables:
            self.load_table("POP_STRATUM")
        if "POP_PLOT_STRATUM_ASSGN" not in self.tables:
            self.load_table("POP_PLOT_STRATUM_ASSGN")
        if "POP_ESTN_UNIT" not in self.tables:
            self.load_table("POP_ESTN_UNIT")

        plots = self.get_plots()
        trees = self.get_trees()
        conds = self.get_conditions()

        plot_cns = plots["CN"].to_list()
        if self.evalid is None:
            raise ValueError("No EVALID specified or found")

        ppsa = (
            self.tables["POP_PLOT_STRATUM_ASSGN"]
            .filter(pl.col("PLT_CN").is_in(plot_cns))
            .filter(pl.col("EVALID").is_in(self.evalid))
            .collect()
        )

        stratum_cns = ppsa["STRATUM_CN"].unique().to_list()
        pop_stratum = (
            self.tables["POP_STRATUM"].filter(pl.col("CN").is_in(stratum_cns)).collect()
        )

        estn_unit_cns = pop_stratum["ESTN_UNIT_CN"].unique().to_list()
        pop_estn_unit = (
            self.tables["POP_ESTN_UNIT"]
            .filter(pl.col("CN").is_in(estn_unit_cns))
            .collect()
        )

        return {
            "plot": plots,
            "tree": trees,
            "cond": conds,
            "pop_plot_stratum_assgn": ppsa,
            "pop_stratum": pop_stratum,
            "pop_estn_unit": pop_estn_unit,
        }

    # Estimation methods - delegate to pyFIA
    def tpa(self, **kwargs) -> pl.DataFrame:
        """Estimate trees per acre."""
        from pyfia.estimation.tpa import tpa
        return tpa(self, **kwargs)

    def biomass(self, **kwargs) -> pl.DataFrame:
        """Estimate biomass."""
        from pyfia.estimation.biomass import biomass
        return biomass(self, **kwargs)

    def volume(self, **kwargs) -> pl.DataFrame:
        """Estimate volume."""
        from pyfia.estimation.volume import volume
        return volume(self, **kwargs)

    def mortality(self, **kwargs) -> pl.DataFrame:
        """Estimate mortality."""
        from pyfia.estimation.estimators.mortality import mortality
        return mortality(self, **kwargs)

    def area(self, **kwargs) -> pl.DataFrame:
        """Estimate forest area."""
        from pyfia.estimation.estimators.area import area
        return area(self, **kwargs)

    def growth(self, **kwargs) -> pl.DataFrame:
        """Estimate annual growth."""
        from pyfia.estimation.estimators.growth import growth
        return growth(self, **kwargs)

    def removals(self, **kwargs) -> pl.DataFrame:
        """Estimate annual removals/harvest."""
        from pyfia.estimation.estimators.removals import removals
        return removals(self, **kwargs)

    def carbon_flux(self, **kwargs) -> pl.DataFrame:
        """Estimate annual net carbon flux."""
        from pyfia.estimation.estimators.carbon_flux import carbon_flux
        return carbon_flux(self, **kwargs)


def get_motherduck_fia(state: str, motherduck_token: str) -> MotherDuckFIA:
    """Create a MotherDuckFIA instance for the specified state."""
    return MotherDuckFIA(state=state, motherduck_token=motherduck_token)

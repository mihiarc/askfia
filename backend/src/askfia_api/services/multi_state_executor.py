"""Multi-state query execution utilities.

This module consolidates the repeated pattern of iterating over states,
getting connections, executing queries, and combining results that appears
in 13+ methods in fia_service.py.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Generator

import pandas as pd

if TYPE_CHECKING:
    from pyfia import FIA

logger = logging.getLogger(__name__)


@dataclass
class StateQueryResult:
    """Result from querying a single state.

    Attributes:
        state: State code (uppercase)
        data: DataFrame with query results, or None if query failed
        error: Error message if query failed
        warning: Warning message (e.g., missing GRM tables)
        skipped: True if state was skipped due to pre-check failure
    """

    state: str
    data: pd.DataFrame | None = None
    error: str | None = None
    warning: str | None = None
    skipped: bool = False

    @property
    def success(self) -> bool:
        """Check if query was successful."""
        return self.data is not None and not self.data.empty


@dataclass
class MultiStateQueryResult:
    """Combined result from querying multiple states.

    Attributes:
        combined: Combined DataFrame from all successful states
        successful_states: List of states that returned data
        failed_states: List of states that failed or were skipped
        warnings: List of warning messages
        errors: List of error messages
    """

    combined: pd.DataFrame = field(default_factory=pd.DataFrame)
    successful_states: list[str] = field(default_factory=list)
    failed_states: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def has_data(self) -> bool:
        """Check if any data was returned."""
        return not self.combined.empty

    @property
    def all_failed(self) -> bool:
        """Check if all states failed."""
        return len(self.successful_states) == 0 and len(self.failed_states) > 0

    @property
    def partial_success(self) -> bool:
        """Check if some states succeeded and some failed."""
        return len(self.successful_states) > 0 and len(self.failed_states) > 0


# Type alias for connection factory
ConnectionFactory = Callable[[str], Generator[Any, None, None]]

# Type alias for pre-check function
# Takes db connection and state, returns (ok, warning_message)
PreCheckFunc = Callable[[Any, str], tuple[bool, str | None]]


class MultiStateQueryExecutor:
    """Execute pyFIA queries across multiple states with consistent handling.

    This class consolidates the repeated pattern of:
    1. Iterating over states
    2. Getting database connections
    3. Executing queries with state-specific kwargs
    4. Converting results to pandas
    5. Adding STATE column
    6. Combining results

    It also supports optional pre-checks (e.g., verifying GRM tables exist)
    and collects warnings/errors for partial failures.

    Example usage:
        >>> executor = MultiStateQueryExecutor(fia_service._get_fia_connection)
        >>> result = await executor.execute(
        ...     states=["NC", "GA"],
        ...     query_method="area",
        ...     query_kwargs={"land_type": "forest"}
        ... )
        >>> if result.has_data:
        ...     print(f"Total rows: {len(result.combined)}")
        ...     print(f"Successful states: {result.successful_states}")
    """

    def __init__(self, connection_factory: ConnectionFactory):
        """Initialize executor with a connection factory.

        Args:
            connection_factory: Context manager that yields a pyFIA connection
                              for a given state code.
        """
        self._get_connection = connection_factory

    async def execute(
        self,
        states: list[str],
        query_method: str,
        query_kwargs: dict[str, Any] | None = None,
        pre_check: PreCheckFunc | None = None,
    ) -> MultiStateQueryResult:
        """Execute a query method across multiple states.

        Args:
            states: List of state codes to query.
            query_method: Name of the pyFIA method to call (e.g., "area", "volume").
            query_kwargs: Keyword arguments to pass to the query method.
            pre_check: Optional function to check prerequisites before querying.
                      Takes (db, state) and returns (ok, warning_message).
                      If ok is False, state is skipped with the warning.

        Returns:
            MultiStateQueryResult with combined data and metadata.
        """
        if query_kwargs is None:
            query_kwargs = {}

        results: list[StateQueryResult] = []

        for state in states:
            state = state.upper()
            result = await self._execute_single_state(
                state=state,
                query_method=query_method,
                query_kwargs=query_kwargs,
                pre_check=pre_check,
            )
            results.append(result)

        return self._combine_results(results)

    async def execute_with_state_kwargs(
        self,
        states: list[str],
        query_method: str,
        kwargs_builder: Callable[[str], dict[str, Any]],
        pre_check: PreCheckFunc | None = None,
    ) -> MultiStateQueryResult:
        """Execute a query with state-specific kwargs.

        Use this when kwargs need to vary per state.

        Args:
            states: List of state codes to query.
            query_method: Name of the pyFIA method to call.
            kwargs_builder: Function that takes state and returns kwargs dict.
            pre_check: Optional function to check prerequisites.

        Returns:
            MultiStateQueryResult with combined data and metadata.
        """
        results: list[StateQueryResult] = []

        for state in states:
            state = state.upper()
            query_kwargs = kwargs_builder(state)
            result = await self._execute_single_state(
                state=state,
                query_method=query_method,
                query_kwargs=query_kwargs,
                pre_check=pre_check,
            )
            results.append(result)

        return self._combine_results(results)

    async def _execute_single_state(
        self,
        state: str,
        query_method: str,
        query_kwargs: dict[str, Any],
        pre_check: PreCheckFunc | None,
    ) -> StateQueryResult:
        """Execute query for a single state.

        Args:
            state: State code (already uppercased).
            query_method: Name of the pyFIA method to call.
            query_kwargs: Keyword arguments for the query.
            pre_check: Optional pre-check function.

        Returns:
            StateQueryResult with data or error information.
        """
        try:
            with self._get_connection(state) as db:
                # Run pre-check if provided
                if pre_check is not None:
                    ok, warning = pre_check(db, state)
                    if not ok:
                        return StateQueryResult(
                            state=state,
                            warning=warning,
                            skipped=True,
                        )

                # Get the query method
                method = getattr(db, query_method)

                # Execute query
                result_df = method(**query_kwargs)

                # Convert to pandas if needed
                df = self._ensure_pandas(result_df)

                # Add state column
                df["STATE"] = state

                return StateQueryResult(state=state, data=df)

        except Exception as e:
            logger.error(f"Error querying {query_method} for state {state}: {e}")
            return StateQueryResult(
                state=state,
                error=str(e),
            )

    def _ensure_pandas(self, result: Any) -> pd.DataFrame:
        """Convert result to pandas DataFrame if needed.

        Args:
            result: Query result (may be polars or pandas).

        Returns:
            Pandas DataFrame.
        """
        if hasattr(result, "to_pandas"):
            return result.to_pandas()
        return result

    def _combine_results(
        self, results: list[StateQueryResult]
    ) -> MultiStateQueryResult:
        """Combine individual state results into a single result.

        Args:
            results: List of StateQueryResult objects.

        Returns:
            MultiStateQueryResult with combined data and metadata.
        """
        successful_dfs: list[pd.DataFrame] = []
        successful_states: list[str] = []
        failed_states: list[str] = []
        warnings: list[str] = []
        errors: list[str] = []

        for result in results:
            if result.success:
                successful_dfs.append(result.data)
                successful_states.append(result.state)
            else:
                failed_states.append(result.state)

            if result.warning:
                warnings.append(result.warning)
            if result.error:
                errors.append(result.error)

        # Combine successful DataFrames
        if successful_dfs:
            combined = pd.concat(successful_dfs, ignore_index=True)
        else:
            combined = pd.DataFrame()

        return MultiStateQueryResult(
            combined=combined,
            successful_states=successful_states,
            failed_states=failed_states,
            warnings=warnings,
            errors=errors,
        )


def create_grm_table_check(required_tables: list[str]) -> PreCheckFunc:
    """Create a pre-check function for GRM table availability.

    Args:
        required_tables: List of table names that must exist.

    Returns:
        A pre-check function that validates table availability.
    """

    def check_grm_tables(db: Any, state: str) -> tuple[bool, str | None]:
        """Check if required GRM tables exist in database.

        Uses the same pattern as FIAService.query_mortality():
        1. Try db._reader._backend.table_exists() if available
        2. Otherwise try loading the table and catch exceptions
        """
        missing_tables = []

        for table in required_tables:
            # Try the backend table_exists method first (MotherDuck)
            if hasattr(db, "_reader") and hasattr(db._reader, "_backend"):
                backend = db._reader._backend
                if hasattr(backend, "table_exists"):
                    if not backend.table_exists(table):
                        missing_tables.append(table)
                    continue

            # Fallback: check if table is in db.tables dict, or try to load it
            try:
                if table not in db.tables:
                    db.load_table(table)
            except Exception:
                missing_tables.append(table)

        if missing_tables:
            warning = (
                f"State {state} is missing GRM tables: {', '.join(missing_tables)}. "
                "Skipping this state."
            )
            return False, warning

        return True, None

    return check_grm_tables


# Pre-configured GRM checks for common use cases
GRM_MORTALITY_CHECK = create_grm_table_check(
    ["TREE_GRM_COMPONENT", "TREE_GRM_MIDPT"]
)

GRM_GROWTH_CHECK = create_grm_table_check(
    ["TREE_GRM_COMPONENT", "TREE_GRM_MIDPT", "TREE_GRM_BEGIN", "BEGINEND"]
)

GRM_REMOVALS_CHECK = create_grm_table_check(
    ["TREE_GRM_COMPONENT", "TREE_GRM_MIDPT"]
)

"""Tests for MultiStateQueryExecutor.

Tests use real FIA data to validate multi-state query execution.
"""

import pandas as pd
import pytest

from askfia_api.services.multi_state_executor import (
    GRM_GROWTH_CHECK,
    GRM_MORTALITY_CHECK,
    MultiStateQueryExecutor,
    MultiStateQueryResult,
    StateQueryResult,
    create_grm_table_check,
)


class TestStateQueryResult:
    """Tests for StateQueryResult dataclass."""

    def test_success_with_data(self):
        """Result with data is successful."""
        df = pd.DataFrame({"A": [1, 2, 3]})
        result = StateQueryResult(state="NC", data=df)
        assert result.success is True

    def test_success_with_empty_data(self):
        """Result with empty DataFrame is not successful."""
        df = pd.DataFrame()
        result = StateQueryResult(state="NC", data=df)
        assert result.success is False

    def test_success_with_no_data(self):
        """Result with None data is not successful."""
        result = StateQueryResult(state="NC", data=None)
        assert result.success is False

    def test_error_result(self):
        """Result with error is not successful."""
        result = StateQueryResult(state="NC", error="Connection failed")
        assert result.success is False

    def test_skipped_result(self):
        """Skipped result is not successful."""
        result = StateQueryResult(
            state="NC", warning="Missing GRM tables", skipped=True
        )
        assert result.success is False


class TestMultiStateQueryResult:
    """Tests for MultiStateQueryResult dataclass."""

    def test_has_data_with_rows(self):
        """Result with rows has_data is True."""
        df = pd.DataFrame({"A": [1, 2, 3]})
        result = MultiStateQueryResult(combined=df, successful_states=["NC"])
        assert result.has_data is True

    def test_has_data_empty(self):
        """Empty result has_data is False."""
        result = MultiStateQueryResult()
        assert result.has_data is False

    def test_all_failed(self):
        """all_failed when no successful states."""
        result = MultiStateQueryResult(failed_states=["NC", "GA"])
        assert result.all_failed is True
        assert result.partial_success is False

    def test_partial_success(self):
        """partial_success when some states succeeded."""
        df = pd.DataFrame({"A": [1]})
        result = MultiStateQueryResult(
            combined=df, successful_states=["NC"], failed_states=["GA"]
        )
        assert result.partial_success is True
        assert result.all_failed is False

    def test_full_success(self):
        """Neither all_failed nor partial_success when all succeeded."""
        df = pd.DataFrame({"A": [1, 2]})
        result = MultiStateQueryResult(
            combined=df, successful_states=["NC", "GA"], failed_states=[]
        )
        assert result.all_failed is False
        assert result.partial_success is False


class TestMultiStateQueryExecutorUnit:
    """Unit tests for MultiStateQueryExecutor."""

    def test_combine_results_empty(self):
        """Combining empty results returns empty result."""
        from askfia_api.services.fia_service import FIAService

        service = FIAService()
        executor = MultiStateQueryExecutor(service._get_fia_connection)

        combined = executor._combine_results([])

        assert combined.combined.empty
        assert len(combined.successful_states) == 0
        assert len(combined.failed_states) == 0

    def test_combine_results_all_success(self):
        """Combining successful results returns combined data."""
        from askfia_api.services.fia_service import FIAService

        service = FIAService()
        executor = MultiStateQueryExecutor(service._get_fia_connection)

        results = [
            StateQueryResult(
                state="NC", data=pd.DataFrame({"A": [1], "STATE": ["NC"]})
            ),
            StateQueryResult(
                state="GA", data=pd.DataFrame({"A": [2], "STATE": ["GA"]})
            ),
        ]

        combined = executor._combine_results(results)

        assert len(combined.combined) == 2
        assert combined.successful_states == ["NC", "GA"]
        assert len(combined.failed_states) == 0

    def test_combine_results_mixed(self):
        """Combining mixed results tracks failures."""
        from askfia_api.services.fia_service import FIAService

        service = FIAService()
        executor = MultiStateQueryExecutor(service._get_fia_connection)

        results = [
            StateQueryResult(
                state="NC", data=pd.DataFrame({"A": [1], "STATE": ["NC"]})
            ),
            StateQueryResult(state="GA", error="Connection failed"),
            StateQueryResult(
                state="SC", warning="Missing GRM tables", skipped=True
            ),
        ]

        combined = executor._combine_results(results)

        assert len(combined.combined) == 1
        assert combined.successful_states == ["NC"]
        assert set(combined.failed_states) == {"GA", "SC"}
        assert len(combined.warnings) == 1
        assert len(combined.errors) == 1


class TestMultiStateQueryExecutorIntegration:
    """Integration tests using real FIA data."""

    @pytest.mark.asyncio
    async def test_execute_single_state(self):
        """Execute area query for a single state."""
        from askfia_api.services.fia_service import FIAService

        service = FIAService()
        executor = MultiStateQueryExecutor(service._get_fia_connection)

        result = await executor.execute(
            states=["NC"],
            query_method="area",
            query_kwargs={"land_type": "forest"},
        )

        assert result.has_data
        assert "NC" in result.successful_states
        assert "STATE" in result.combined.columns
        assert result.combined["STATE"].iloc[0] == "NC"

    @pytest.mark.asyncio
    async def test_execute_multi_state(self):
        """Execute area query across multiple states."""
        from askfia_api.services.fia_service import FIAService

        service = FIAService()
        executor = MultiStateQueryExecutor(service._get_fia_connection)

        result = await executor.execute(
            states=["NC", "GA"],
            query_method="area",
            query_kwargs={"land_type": "forest"},
        )

        assert result.has_data
        assert set(result.successful_states) == {"NC", "GA"}
        assert len(result.combined) >= 2  # At least one row per state
        assert set(result.combined["STATE"].unique()) == {"NC", "GA"}

    @pytest.mark.asyncio
    async def test_execute_volume_with_tree_domain(self):
        """Execute volume query with tree domain filter."""
        from askfia_api.services.fia_service import FIAService

        service = FIAService()
        executor = MultiStateQueryExecutor(service._get_fia_connection)

        result = await executor.execute(
            states=["NC"],
            query_method="volume",
            query_kwargs={"tree_domain": "DIA >= 10.0"},
        )

        assert result.has_data
        assert "NC" in result.successful_states

    @pytest.mark.asyncio
    async def test_execute_with_pre_check(self):
        """Execute with pre-check that passes."""
        from askfia_api.services.fia_service import FIAService

        service = FIAService()
        executor = MultiStateQueryExecutor(service._get_fia_connection)

        def always_pass(db, state):
            return True, None

        result = await executor.execute(
            states=["NC"],
            query_method="area",
            query_kwargs={"land_type": "forest"},
            pre_check=always_pass,
        )

        assert result.has_data

    @pytest.mark.asyncio
    async def test_execute_with_failing_pre_check(self):
        """Execute with pre-check that fails."""
        from askfia_api.services.fia_service import FIAService

        service = FIAService()
        executor = MultiStateQueryExecutor(service._get_fia_connection)

        def always_fail(db, state):
            return False, f"Test failure for {state}"

        result = await executor.execute(
            states=["NC"],
            query_method="area",
            query_kwargs={"land_type": "forest"},
            pre_check=always_fail,
        )

        assert not result.has_data
        assert "NC" in result.failed_states
        assert len(result.warnings) == 1
        assert "Test failure" in result.warnings[0]

    @pytest.mark.asyncio
    async def test_lowercase_states_normalized(self):
        """Lowercase state codes are normalized to uppercase."""
        from askfia_api.services.fia_service import FIAService

        service = FIAService()
        executor = MultiStateQueryExecutor(service._get_fia_connection)

        result = await executor.execute(
            states=["nc", "ga"],  # lowercase
            query_method="area",
            query_kwargs={"land_type": "forest"},
        )

        assert result.has_data
        # States should be normalized to uppercase
        assert "NC" in result.successful_states or "nc" not in result.successful_states
        assert result.combined["STATE"].iloc[0].isupper()


class TestGRMTableChecks:
    """Tests for GRM table pre-check functions."""

    def test_create_grm_table_check(self):
        """create_grm_table_check creates a callable."""
        check = create_grm_table_check(["TABLE1", "TABLE2"])
        assert callable(check)

    @pytest.mark.asyncio
    async def test_grm_mortality_check_with_available_state(self):
        """GRM mortality check works with state that has GRM tables."""
        from askfia_api.services.fia_service import FIAService

        service = FIAService()

        # Test with NC which should have GRM tables
        with service._get_fia_connection("NC") as db:
            ok, warning = GRM_MORTALITY_CHECK(db, "NC")
            # Result depends on NC having GRM tables
            # We're testing the function works, not specific state data
            assert isinstance(ok, bool)
            if not ok:
                assert warning is not None
                assert "GRM" in warning or "missing" in warning.lower()

    @pytest.mark.asyncio
    async def test_grm_growth_check_signature(self):
        """GRM growth check has correct signature."""
        from askfia_api.services.fia_service import FIAService

        service = FIAService()

        with service._get_fia_connection("NC") as db:
            ok, warning = GRM_GROWTH_CHECK(db, "NC")
            assert isinstance(ok, bool)
            assert warning is None or isinstance(warning, str)

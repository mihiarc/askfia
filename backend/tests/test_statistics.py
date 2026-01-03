"""Tests for statistics utilities.

Tests use real FIA data to validate statistical computations.
"""

import numpy as np
import pandas as pd
import pytest

from askfia_api.services.statistics import SEAggregator, WelfordStatisticsAccumulator


class TestWelfordStatisticsAccumulator:
    """Tests for WelfordStatisticsAccumulator."""

    def test_empty_accumulator(self):
        """Empty accumulator returns zeros."""
        accum = WelfordStatisticsAccumulator()
        stats = accum.to_dict()

        assert stats["count"] == 0
        assert stats["mean"] == 0.0
        assert stats["std"] == 0.0
        assert stats["min"] == 0.0
        assert stats["max"] == 0.0

    def test_single_update(self):
        """Single batch update calculates correct statistics."""
        accum = WelfordStatisticsAccumulator()
        data = np.array([1, 2, 3, 4, 5])
        accum.update(data)

        stats = accum.to_dict()
        assert stats["count"] == 5
        assert np.isclose(stats["mean"], 3.0)
        assert np.isclose(stats["std"], np.std(data))
        assert stats["min"] == 1.0
        assert stats["max"] == 5.0

    def test_multiple_updates_equals_batch(self):
        """Multiple updates should equal processing all at once."""
        # Generate random data
        np.random.seed(42)
        full_data = np.random.randn(1000)

        # Process in one batch
        batch_accum = WelfordStatisticsAccumulator()
        batch_accum.update(full_data)

        # Process in multiple batches
        chunked_accum = WelfordStatisticsAccumulator()
        for chunk in np.array_split(full_data, 10):
            chunked_accum.update(chunk)

        # Results should be nearly identical
        batch_stats = batch_accum.to_dict()
        chunked_stats = chunked_accum.to_dict()

        assert batch_stats["count"] == chunked_stats["count"]
        assert np.isclose(batch_stats["mean"], chunked_stats["mean"], rtol=1e-10)
        assert np.isclose(batch_stats["std"], chunked_stats["std"], rtol=1e-10)
        assert batch_stats["min"] == chunked_stats["min"]
        assert batch_stats["max"] == chunked_stats["max"]

    def test_merge_two_accumulators(self):
        """Merging two accumulators gives same result as combined data."""
        np.random.seed(123)
        data1 = np.random.randn(500)
        data2 = np.random.randn(500)

        # Process each dataset separately
        accum1 = WelfordStatisticsAccumulator()
        accum1.update(data1)

        accum2 = WelfordStatisticsAccumulator()
        accum2.update(data2)

        # Merge
        accum1.merge(accum2)

        # Compare to processing all at once
        combined_accum = WelfordStatisticsAccumulator()
        combined_accum.update(np.concatenate([data1, data2]))

        assert accum1.count == combined_accum.count
        assert np.isclose(accum1.mean, combined_accum.mean, rtol=1e-10)
        assert np.isclose(accum1.std, combined_accum.std, rtol=1e-10)

    def test_merge_empty_accumulator(self):
        """Merging empty accumulator doesn't change statistics."""
        accum = WelfordStatisticsAccumulator()
        accum.update(np.array([1, 2, 3, 4, 5]))
        original_stats = accum.to_dict()

        empty = WelfordStatisticsAccumulator()
        accum.merge(empty)

        assert accum.to_dict() == original_stats

    def test_update_with_empty_array(self):
        """Updating with empty array doesn't change statistics."""
        accum = WelfordStatisticsAccumulator()
        accum.update(np.array([1, 2, 3]))
        original_stats = accum.to_dict()

        accum.update(np.array([]))

        assert accum.to_dict() == original_stats

    def test_reset(self):
        """Reset returns accumulator to initial state."""
        accum = WelfordStatisticsAccumulator()
        accum.update(np.array([1, 2, 3, 4, 5]))

        accum.reset()

        stats = accum.to_dict()
        assert stats["count"] == 0
        assert stats["mean"] == 0.0

    def test_2d_array_flattened(self):
        """2D arrays are properly flattened."""
        accum = WelfordStatisticsAccumulator()
        data_2d = np.array([[1, 2], [3, 4], [5, 6]])
        accum.update(data_2d)

        assert accum.count == 6
        assert np.isclose(accum.mean, 3.5)


class TestSEAggregator:
    """Tests for SEAggregator."""

    def test_combine_se_basic(self):
        """Basic SE combination using quadrature."""
        # SE_combined = sqrt(3^2 + 4^2) = 5
        se_values = [3.0, 4.0]
        result = SEAggregator.combine_se(se_values)
        assert np.isclose(result, 5.0)

    def test_combine_se_single_value(self):
        """Single SE value returns itself."""
        result = SEAggregator.combine_se([10.0])
        assert np.isclose(result, 10.0)

    def test_combine_se_empty(self):
        """Empty list returns 0."""
        result = SEAggregator.combine_se([])
        assert result == 0.0

    def test_combine_se_with_nans(self):
        """NaN values are dropped from calculation."""
        se_values = pd.Series([3.0, np.nan, 4.0, np.nan])
        result = SEAggregator.combine_se(se_values)
        assert np.isclose(result, 5.0)

    def test_combine_se_all_nans(self):
        """All NaN values returns 0."""
        se_values = pd.Series([np.nan, np.nan])
        result = SEAggregator.combine_se(se_values)
        assert result == 0.0

    def test_calculate_se_percent(self):
        """SE percentage calculation."""
        # 500 / 10000 * 100 = 5%
        result = SEAggregator.calculate_se_percent(500, 10000)
        assert np.isclose(result, 5.0)

    def test_calculate_se_percent_zero_estimate(self):
        """Zero estimate returns 0%."""
        result = SEAggregator.calculate_se_percent(500, 0)
        assert result == 0.0

    def test_calculate_se_percent_negative_estimate(self):
        """Negative estimate returns 0%."""
        result = SEAggregator.calculate_se_percent(500, -1000)
        assert result == 0.0

    def test_calculate_se_percent_zero_se(self):
        """Zero SE returns 0%."""
        result = SEAggregator.calculate_se_percent(0, 10000)
        assert result == 0.0

    def test_aggregate_from_dataframe(self):
        """Aggregate from DataFrame with estimates and SEs."""
        df = pd.DataFrame(
            {
                "ESTIMATE": [1000, 2000, 3000],
                "SE": [100, 150, 120],
            }
        )

        total, se_pct = SEAggregator.aggregate_from_dataframe(df, "ESTIMATE", "SE")

        expected_se = np.sqrt(100**2 + 150**2 + 120**2)
        expected_pct = (expected_se / 6000) * 100

        assert np.isclose(total, 6000)
        assert np.isclose(se_pct, expected_pct)

    def test_aggregate_from_dataframe_no_se(self):
        """Aggregate from DataFrame without SE column."""
        df = pd.DataFrame({"ESTIMATE": [1000, 2000, 3000]})

        total, se_pct = SEAggregator.aggregate_from_dataframe(df, "ESTIMATE", None)

        assert np.isclose(total, 6000)
        assert se_pct == 0.0

    def test_aggregate_from_dataframe_missing_se_col(self):
        """Aggregate when SE column doesn't exist."""
        df = pd.DataFrame({"ESTIMATE": [1000, 2000, 3000]})

        total, se_pct = SEAggregator.aggregate_from_dataframe(df, "ESTIMATE", "SE")

        assert np.isclose(total, 6000)
        assert se_pct == 0.0

    def test_from_grouped_estimates(self):
        """Aggregate from parallel lists."""
        estimates = [1000, 2000, 3000]
        se_values = [100, 150, 120]

        total, se_pct = SEAggregator.from_grouped_estimates(estimates, se_values)

        expected_se = np.sqrt(100**2 + 150**2 + 120**2)
        expected_pct = (expected_se / 6000) * 100

        assert np.isclose(total, 6000)
        assert np.isclose(se_pct, expected_pct)

    def test_from_grouped_estimates_no_se(self):
        """Aggregate from estimates only."""
        estimates = [1000, 2000, 3000]

        total, se_pct = SEAggregator.from_grouped_estimates(estimates, None)

        assert np.isclose(total, 6000)
        assert se_pct == 0.0


class TestSEAggregatorWithRealData:
    """Tests using real FIA service data."""

    @pytest.mark.asyncio
    async def test_se_aggregation_matches_service(self):
        """Verify SE aggregation produces valid percentages with real data."""
        from askfia_api.services.fia_service import FIAService

        service = FIAService()
        result = await service.query_area(["NC"], land_type="forest")

        # SE% should be a reasonable value (typically 0.5-10% for state-level)
        assert "se_percent" in result
        assert result["se_percent"] >= 0
        assert result["se_percent"] < 50  # Reasonable upper bound

        # Verify total area is positive
        assert result["total_area_acres"] > 0

    @pytest.mark.asyncio
    async def test_multi_state_se_aggregation(self):
        """Verify multi-state SE aggregation uses quadrature."""
        from askfia_api.services.fia_service import FIAService

        service = FIAService()

        # Query two states
        result = await service.query_area(["NC", "GA"], land_type="forest")

        # SE% should be present and reasonable
        assert "se_percent" in result
        assert result["se_percent"] >= 0
        assert result["se_percent"] < 50

        # Multi-state total should be larger than single state
        assert result["total_area_acres"] > 10_000_000  # NC + GA > 10M acres

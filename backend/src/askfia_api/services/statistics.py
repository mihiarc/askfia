"""Statistical utilities for FIA data analysis.

This module consolidates duplicated statistical computation patterns including:
- Welford's parallel algorithm for incremental mean/variance (from gridfia_service.py)
- Standard error aggregation using variance propagation (from fia_service.py)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class WelfordStatisticsAccumulator:
    """Numerically stable incremental statistics using Welford's parallel algorithm.

    This class implements the parallel variant of Welford's online algorithm for
    computing running mean and variance. It allows merging statistics from multiple
    batches (tiles/chunks) without needing all data in memory simultaneously.

    Algorithm reference:
    https://en.wikipedia.org/wiki/Algorithms_for_calculating_variance#Parallel_algorithm

    Example usage:
        >>> accum = WelfordStatisticsAccumulator()
        >>> for tile_data in tiles:
        ...     accum.update(tile_data)
        >>> stats = accum.to_dict()
        >>> print(f"Mean: {stats['mean']:.2f}, Std: {stats['std']:.2f}")

    Attributes:
        count: Total number of values accumulated
        mean: Running mean of all values
        m2: Sum of squared differences from the mean (for variance calculation)
        min_val: Minimum value seen
        max_val: Maximum value seen
    """

    count: int = 0
    mean: float = 0.0
    m2: float = 0.0
    min_val: float = field(default_factory=lambda: float("inf"))
    max_val: float = field(default_factory=lambda: float("-inf"))

    def update(self, values: np.ndarray) -> None:
        """Update statistics with a batch of new values.

        Uses parallel Welford's algorithm to merge batch statistics with
        running statistics in a numerically stable way.

        Args:
            values: NumPy array of values to incorporate. Can be any shape;
                   will be flattened internally.
        """
        values = np.asarray(values).ravel()
        if len(values) == 0:
            return

        # Calculate batch statistics
        batch_n = len(values)
        batch_mean = float(np.mean(values))
        batch_m2 = float(np.sum((values - batch_mean) ** 2))
        batch_min = float(np.min(values))
        batch_max = float(np.max(values))

        # Merge with running statistics
        if self.count == 0:
            self.count = batch_n
            self.mean = batch_mean
            self.m2 = batch_m2
            self.min_val = batch_min
            self.max_val = batch_max
        else:
            # Parallel Welford's formula
            combined_count = self.count + batch_n
            delta = batch_mean - self.mean
            self.mean = (self.count * self.mean + batch_n * batch_mean) / combined_count
            self.m2 = (
                self.m2
                + batch_m2
                + delta**2 * self.count * batch_n / combined_count
            )
            self.count = combined_count
            self.min_val = min(self.min_val, batch_min)
            self.max_val = max(self.max_val, batch_max)

    def merge(self, other: WelfordStatisticsAccumulator) -> None:
        """Merge another accumulator's statistics into this one.

        Useful for combining results from parallel processing.

        Args:
            other: Another WelfordStatisticsAccumulator to merge in.
        """
        if other.count == 0:
            return

        if self.count == 0:
            self.count = other.count
            self.mean = other.mean
            self.m2 = other.m2
            self.min_val = other.min_val
            self.max_val = other.max_val
        else:
            combined_count = self.count + other.count
            delta = other.mean - self.mean
            self.mean = (
                self.count * self.mean + other.count * other.mean
            ) / combined_count
            self.m2 = (
                self.m2
                + other.m2
                + delta**2 * self.count * other.count / combined_count
            )
            self.count = combined_count
            self.min_val = min(self.min_val, other.min_val)
            self.max_val = max(self.max_val, other.max_val)

    @property
    def variance(self) -> float:
        """Calculate population variance from accumulated statistics."""
        if self.count < 1:
            return 0.0
        return self.m2 / self.count

    @property
    def std(self) -> float:
        """Calculate population standard deviation from accumulated statistics."""
        return float(np.sqrt(self.variance))

    def to_dict(self) -> dict[str, Any]:
        """Export statistics as a dictionary.

        Returns:
            Dictionary with keys: count, mean, std, min, max
        """
        return {
            "count": self.count,
            "mean": self.mean if self.count > 0 else 0.0,
            "std": self.std,
            "min": self.min_val if self.count > 0 else 0.0,
            "max": self.max_val if self.count > 0 else 0.0,
        }

    def reset(self) -> None:
        """Reset accumulator to initial state."""
        self.count = 0
        self.mean = 0.0
        self.m2 = 0.0
        self.min_val = float("inf")
        self.max_val = float("-inf")


class SEAggregator:
    """Aggregator for combining standard errors using variance propagation.

    Standard errors from independent estimates can be combined using the
    formula: SE_combined = sqrt(sum(SE_i^2))

    This is based on variance propagation for independent random variables:
    Var(X + Y) = Var(X) + Var(Y), and since SE = sqrt(Var),
    SE_total = sqrt(SE_1^2 + SE_2^2 + ... + SE_n^2)

    Example usage:
        >>> se_values = pd.Series([100, 150, 120])  # SE for 3 states
        >>> combined_se = SEAggregator.combine_se(se_values)
        >>> total_estimate = 5000000  # Total acres across states
        >>> se_pct = SEAggregator.calculate_se_percent(combined_se, total_estimate)
        >>> print(f"SE%: {se_pct:.1f}%")
    """

    @staticmethod
    def combine_se(se_values: pd.Series | np.ndarray | list[float]) -> float:
        """Combine standard errors using variance propagation (quadrature).

        SE_combined = sqrt(sum(SE_i^2))

        Args:
            se_values: Series, array, or list of individual SE values.
                      NaN values are automatically dropped.

        Returns:
            Combined standard error as a single float.
        """
        if isinstance(se_values, pd.Series):
            se_values = se_values.dropna()
        else:
            se_values = np.asarray(se_values)
            se_values = se_values[~np.isnan(se_values)]

        if len(se_values) == 0:
            return 0.0

        return float(np.sqrt(np.sum(np.asarray(se_values) ** 2)))

    @staticmethod
    def calculate_se_percent(se_value: float, estimate: float) -> float:
        """Calculate SE as a percentage of the estimate.

        SE% = (SE / Estimate) * 100

        Args:
            se_value: Standard error in the same units as the estimate.
            estimate: The estimate value.

        Returns:
            SE as a percentage (e.g., 5.2 means 5.2%).
            Returns 0.0 if estimate or se_value is <= 0.
        """
        if estimate <= 0 or se_value <= 0:
            return 0.0
        return (se_value / estimate) * 100

    @staticmethod
    def aggregate_from_dataframe(
        df: pd.DataFrame,
        estimate_col: str,
        se_col: str | None,
    ) -> tuple[float, float]:
        """Calculate total estimate and SE% from a DataFrame.

        Combines estimates by summing and combines SEs using variance propagation,
        then calculates the SE percentage of the total estimate.

        Args:
            df: DataFrame containing estimate and optional SE columns.
            estimate_col: Name of the column containing estimates.
            se_col: Name of the column containing SE values, or None.

        Returns:
            Tuple of (total_estimate, se_percent).
            If se_col is None or not in df, se_percent will be 0.0.
        """
        if estimate_col not in df.columns:
            return 0.0, 0.0

        total_estimate = float(df[estimate_col].sum())

        if se_col is None or se_col not in df.columns:
            return total_estimate, 0.0

        combined_se = SEAggregator.combine_se(df[se_col])
        se_percent = SEAggregator.calculate_se_percent(combined_se, total_estimate)

        return total_estimate, se_percent

    @staticmethod
    def from_grouped_estimates(
        estimates: list[float],
        se_values: list[float] | None = None,
    ) -> tuple[float, float]:
        """Calculate aggregates from parallel lists of estimates and SEs.

        Convenience method for when data is not in a DataFrame.

        Args:
            estimates: List of estimate values to sum.
            se_values: Optional list of SE values to combine.

        Returns:
            Tuple of (total_estimate, se_percent).
        """
        total_estimate = sum(estimates)

        if se_values is None or len(se_values) == 0:
            return total_estimate, 0.0

        combined_se = SEAggregator.combine_se(se_values)
        se_percent = SEAggregator.calculate_se_percent(combined_se, total_estimate)

        return total_estimate, se_percent

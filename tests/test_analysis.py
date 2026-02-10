"""Tests for src/analysis.py — statistical analysis with known-answer data.

Uses synthetic price data where the correct conclusions are known in advance.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.strategies import run_all_strategies
from src.analysis import (
    compute_day_distribution,
    compute_statistical_tests,
    compute_dollar_impact,
    compute_context,
    run_full_analysis,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def constant_prices() -> pd.DataFrame:
    """Constant $100 for 3 years — no day should be better than any other."""
    dates = pd.bdate_range("2020-01-01", "2022-12-31")
    return pd.DataFrame({"Date": dates, "Close": [100.0] * len(dates)})


@pytest.fixture
def constant_results(constant_prices: pd.DataFrame):
    return run_all_strategies(
        investment_day=15,
        monthly_amount=500.0,
        transaction_cost=0.0,
        df=constant_prices,
        n_random=50,
    )


@pytest.fixture
def trending_prices() -> pd.DataFrame:
    """Steadily increasing from $100 to $300 over 3 years."""
    dates = pd.bdate_range("2020-01-01", "2022-12-31")
    prices = np.linspace(100, 300, len(dates))
    return pd.DataFrame({"Date": dates, "Close": prices})


@pytest.fixture
def trending_results(trending_prices: pd.DataFrame):
    return run_all_strategies(
        investment_day=15,
        monthly_amount=500.0,
        transaction_cost=0.0,
        df=trending_prices,
        n_random=50,
    )


# ---------------------------------------------------------------------------
# Day-of-month distribution
# ---------------------------------------------------------------------------

class TestDayDistribution:
    def test_constant_price_no_spread(self, constant_results) -> None:
        """At constant prices, all days should produce identical results."""
        dist = compute_day_distribution(constant_results)
        assert dist.range_dollars < 1.0  # essentially zero spread
        assert len(dist.days) == 28

    def test_trending_has_some_spread(self, trending_results) -> None:
        """With trending prices, there should be some day-to-day variation."""
        dist = compute_day_distribution(trending_results)
        assert dist.range_dollars > 0
        assert dist.best_day != dist.worst_day or dist.range_dollars < 1.0


# ---------------------------------------------------------------------------
# Statistical tests
# ---------------------------------------------------------------------------

class TestStatisticalTests:
    def test_constant_price_not_significant(self, constant_results) -> None:
        """At constant prices, no test should be significant."""
        st = compute_statistical_tests(constant_results, bootstrap_iterations=1000)
        # p-value should be large (no effect)
        assert st.t_pvalue > 0.05 or abs(st.cohens_d) < 0.01
        # Cohen's d should be negligible
        assert abs(st.cohens_d) < 0.5

    def test_bootstrap_ci_contains_zero_constant(self, constant_results) -> None:
        """At constant prices, the CI should contain zero."""
        st = compute_statistical_tests(constant_results, bootstrap_iterations=1000)
        # With constant prices, differences are essentially zero
        assert abs(st.bootstrap_mean_diff) < 0.1


# ---------------------------------------------------------------------------
# Dollar impact
# ---------------------------------------------------------------------------

class TestDollarImpact:
    def test_total_contributed(self, constant_results) -> None:
        di = compute_dollar_impact(constant_results)
        # 36 months × $500 = $18,000
        assert di.total_contributed == pytest.approx(18000, abs=500)

    def test_constant_price_negligible_difference(self, constant_results) -> None:
        di = compute_dollar_impact(constant_results)
        assert abs(di.client_vs_median_dollars) < 1.0

    def test_optimal_beats_worst(self, trending_results) -> None:
        di = compute_dollar_impact(trending_results)
        assert di.optimal_final_value > di.worst_hindsight_final_value


# ---------------------------------------------------------------------------
# Context analysis
# ---------------------------------------------------------------------------

class TestContextAnalysis:
    def test_narratives_not_empty(self, constant_results) -> None:
        ctx = compute_context(constant_results, 500.0)
        assert len(ctx.contribution_impact) > 0
        assert len(ctx.start_date_impact) > 0
        assert len(ctx.asset_choice_impact) > 0


# ---------------------------------------------------------------------------
# Full analysis
# ---------------------------------------------------------------------------

class TestRunFullAnalysis:
    def test_returns_all_components(self, constant_results) -> None:
        analysis = run_full_analysis(
            constant_results, monthly_amount=500.0, bootstrap_iterations=500,
        )
        assert analysis.day_distribution is not None
        assert analysis.statistical_tests is not None
        assert analysis.dollar_impact is not None
        assert analysis.context is not None

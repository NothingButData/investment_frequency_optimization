"""Tests for src/strategies.py — DCA strategy simulators.

Uses a small, hand-crafted 3-month price series so results can be verified
by hand.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.strategies import (
    StrategyResult,
    monthly_fixed_day,
    all_monthly_days,
    weekly_dca,
    daily_dca,
    random_day_monthly,
    optimal_hindsight,
    worst_hindsight,
    run_all_strategies,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def simple_prices() -> pd.DataFrame:
    """A tiny, deterministic price series for hand-verification.

    3 months of business days, constant price $100.
    This makes share calculations trivial: $500 buys 5 shares each month.
    """
    dates = pd.bdate_range("2023-01-02", "2023-03-31")
    return pd.DataFrame({
        "Date": dates,
        "Close": [100.0] * len(dates),
    })


@pytest.fixture
def trending_prices() -> pd.DataFrame:
    """Prices that trend from $100 to $200 over 3 months."""
    dates = pd.bdate_range("2023-01-02", "2023-03-31")
    prices = np.linspace(100, 200, len(dates))
    return pd.DataFrame({"Date": dates, "Close": prices})


# ---------------------------------------------------------------------------
# StrategyResult
# ---------------------------------------------------------------------------

class TestStrategyResult:
    def test_cost_basis(self) -> None:
        # cost_basis = total_invested (fees are deducted from each
        # investment, not charged on top)
        r = StrategyResult(
            name="test", total_shares=10, total_invested=1000,
            total_transaction_costs=50, final_value=1200,
        )
        assert r.cost_basis == 1000

    def test_total_return(self) -> None:
        r = StrategyResult(
            name="test", total_shares=10, total_invested=1000,
            total_transaction_costs=0, final_value=1200,
        )
        assert abs(r.total_return - 0.20) < 1e-9

    def test_gain(self) -> None:
        # gain = final_value - cost_basis = 1200 - 1000 = 200
        r = StrategyResult(
            name="test", total_shares=10, total_invested=1000,
            total_transaction_costs=50, final_value=1200,
        )
        assert r.gain == 200.0


# ---------------------------------------------------------------------------
# monthly_fixed_day — constant price
# ---------------------------------------------------------------------------

class TestMonthlyFixedDay:
    def test_constant_price(self, simple_prices: pd.DataFrame) -> None:
        """At $100/share, $500/month buys exactly 5 shares/month."""
        result = monthly_fixed_day(15, 500.0, 0.0, simple_prices)
        # 3 months → 3 purchases → 15 shares
        assert result.total_shares == pytest.approx(15.0, abs=0.01)
        assert result.total_invested == pytest.approx(1500.0)
        assert result.final_value == pytest.approx(1500.0, abs=1.0)

    def test_with_transaction_cost(self, simple_prices: pd.DataFrame) -> None:
        """$5 transaction cost → $495 net → 4.95 shares/month."""
        result = monthly_fixed_day(15, 500.0, 5.0, simple_prices)
        expected_shares = 3 * (495.0 / 100.0)
        assert result.total_shares == pytest.approx(expected_shares, abs=0.01)
        assert result.total_transaction_costs == pytest.approx(15.0)


# ---------------------------------------------------------------------------
# all_monthly_days
# ---------------------------------------------------------------------------

class TestAllMonthlyDays:
    def test_returns_28_days(self, simple_prices: pd.DataFrame) -> None:
        results = all_monthly_days(500.0, 0.0, simple_prices)
        assert len(results) == 28
        assert set(results.keys()) == set(range(1, 29))

    def test_constant_price_all_same(self, simple_prices: pd.DataFrame) -> None:
        """At constant $100, every day should produce the same total."""
        results = all_monthly_days(500.0, 0.0, simple_prices)
        values = [r.total_shares for r in results.values()]
        # All should be 15 shares (3 months × 5 shares)
        for v in values:
            assert v == pytest.approx(15.0, abs=0.01)


# ---------------------------------------------------------------------------
# weekly_dca
# ---------------------------------------------------------------------------

class TestWeeklyDCA:
    def test_total_invested_roughly_matches(self, simple_prices: pd.DataFrame) -> None:
        """Weekly DCA should invest approximately the same annual total."""
        monthly_result = monthly_fixed_day(15, 500.0, 0.0, simple_prices)
        weekly_result = weekly_dca(500.0, 0.0, simple_prices, weekday=0)
        # Over 3 months, both should invest roughly $1500
        # Weekly: ~13 Mondays × (500/4.333) ≈ $1500
        ratio = weekly_result.total_invested / monthly_result.total_invested
        assert 0.8 < ratio < 1.2  # within 20% (short period, edge effects)


# ---------------------------------------------------------------------------
# daily_dca
# ---------------------------------------------------------------------------

class TestDailyDCA:
    def test_invests_every_trading_day(self, simple_prices: pd.DataFrame) -> None:
        """Daily DCA should invest on every trading day in the series."""
        daily_result = daily_dca(500.0, 0.0, simple_prices)
        assert len(daily_result.dates) == len(simple_prices)

    def test_constant_price_shares_correct(self, simple_prices: pd.DataFrame) -> None:
        """At $100 constant, total shares = total_invested / 100."""
        daily_result = daily_dca(500.0, 0.0, simple_prices)
        expected_shares = daily_result.total_invested / 100.0
        assert daily_result.total_shares == pytest.approx(expected_shares, abs=0.01)


# ---------------------------------------------------------------------------
# random_day_monthly
# ---------------------------------------------------------------------------

class TestRandomDayMonthly:
    def test_returns_n_simulations(self, simple_prices: pd.DataFrame) -> None:
        results = random_day_monthly(500.0, 0.0, simple_prices, n_simulations=50)
        assert len(results) == 50

    def test_constant_price_all_similar(self, simple_prices: pd.DataFrame) -> None:
        """At constant prices, random day doesn't matter."""
        results = random_day_monthly(500.0, 0.0, simple_prices, n_simulations=50)
        values = [r.total_shares for r in results]
        assert all(v == pytest.approx(15.0, abs=0.1) for v in values)


# ---------------------------------------------------------------------------
# optimal / worst hindsight
# ---------------------------------------------------------------------------

class TestHindsight:
    def test_optimal_beats_worst_trending(self, trending_prices: pd.DataFrame) -> None:
        opt = optimal_hindsight(500.0, 0.0, trending_prices)
        wrst = worst_hindsight(500.0, 0.0, trending_prices)
        # When prices trend up, buying the monthly low gets more shares
        assert opt.total_shares > wrst.total_shares

    def test_constant_price_equal(self, simple_prices: pd.DataFrame) -> None:
        """At constant prices, optimal and worst are identical."""
        opt = optimal_hindsight(500.0, 0.0, simple_prices)
        wrst = worst_hindsight(500.0, 0.0, simple_prices)
        assert opt.total_shares == pytest.approx(wrst.total_shares, abs=0.01)


# ---------------------------------------------------------------------------
# run_all_strategies
# ---------------------------------------------------------------------------

class TestRunAllStrategies:
    def test_returns_all_components(self, simple_prices: pd.DataFrame) -> None:
        results = run_all_strategies(
            investment_day=15,
            monthly_amount=500.0,
            transaction_cost=0.0,
            df=simple_prices,
            n_random=10,
        )
        assert results.client_day is not None
        assert len(results.all_days) == 28
        assert results.weekly is not None
        assert results.daily is not None
        assert len(results.random) == 10
        assert results.optimal is not None
        assert results.worst is not None

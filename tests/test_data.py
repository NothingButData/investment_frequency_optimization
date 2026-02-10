"""Tests for src/data.py — data ingestion, caching, and trading-day helpers."""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from src.data import (
    build_trading_calendar,
    get_monthly_investment_dates,
    get_price_on_date,
    map_to_trading_day,
    validate_prices,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_prices() -> pd.DataFrame:
    """A small, realistic price DataFrame for testing."""
    dates = pd.bdate_range("2023-01-02", "2023-03-31")  # business days only
    np.random.seed(42)
    prices = 100 + np.cumsum(np.random.randn(len(dates)) * 0.5)
    return pd.DataFrame({"Date": dates, "Close": prices})


@pytest.fixture
def trading_days(sample_prices: pd.DataFrame) -> pd.DatetimeIndex:
    return build_trading_calendar(sample_prices)


# ---------------------------------------------------------------------------
# validate_prices
# ---------------------------------------------------------------------------

class TestValidatePrices:
    def test_valid(self, sample_prices: pd.DataFrame) -> None:
        validate_prices(sample_prices, "2023-01-02", "2023-03-31")

    def test_empty_raises(self) -> None:
        df = pd.DataFrame({"Date": [], "Close": []})
        with pytest.raises(ValueError, match="empty"):
            validate_prices(df, "2023-01-01", "2023-12-31")

    def test_negative_price_raises(self, sample_prices: pd.DataFrame) -> None:
        sample_prices.loc[5, "Close"] = -1.0
        with pytest.raises(ValueError, match="non-positive"):
            validate_prices(sample_prices, "2023-01-02", "2023-03-31")

    def test_large_gap_raises(self) -> None:
        dates = [pd.Timestamp("2023-01-03"), pd.Timestamp("2023-02-15")]
        df = pd.DataFrame({"Date": dates, "Close": [100.0, 105.0]})
        with pytest.raises(ValueError, match="gap"):
            validate_prices(df, "2023-01-03", "2023-02-15")


# ---------------------------------------------------------------------------
# map_to_trading_day
# ---------------------------------------------------------------------------

class TestMapToTradingDay:
    def test_exact_match(self, trading_days: pd.DatetimeIndex) -> None:
        td = trading_days[10]
        assert map_to_trading_day(td, trading_days) == td

    def test_weekend_maps_to_monday(self, trading_days: pd.DatetimeIndex) -> None:
        # Jan 7 2023 is a Saturday
        saturday = pd.Timestamp("2023-01-07")
        result = map_to_trading_day(saturday, trading_days)
        assert result is not None
        assert result.weekday() < 5  # Must be a weekday
        assert result >= saturday

    def test_before_first_day(self, trading_days: pd.DatetimeIndex) -> None:
        before = pd.Timestamp("2022-12-01")
        result = map_to_trading_day(before, trading_days)
        assert result == trading_days[0]

    def test_after_last_day_returns_none(self, trading_days: pd.DatetimeIndex) -> None:
        after = pd.Timestamp("2024-01-01")
        result = map_to_trading_day(after, trading_days)
        assert result is None


# ---------------------------------------------------------------------------
# get_monthly_investment_dates
# ---------------------------------------------------------------------------

class TestGetMonthlyInvestmentDates:
    def test_returns_one_per_month(self, trading_days: pd.DatetimeIndex) -> None:
        pairs = get_monthly_investment_dates(15, trading_days)
        months_seen = set()
        for target, actual in pairs:
            ym = (actual.year, actual.month)
            months_seen.add(ym)
        # Jan, Feb, Mar 2023 — should have 3 months
        assert len(months_seen) == 3

    def test_actual_is_trading_day(self, trading_days: pd.DatetimeIndex) -> None:
        pairs = get_monthly_investment_dates(15, trading_days)
        for _target, actual in pairs:
            assert actual in trading_days

    def test_actual_on_or_after_target(self, trading_days: pd.DatetimeIndex) -> None:
        pairs = get_monthly_investment_dates(15, trading_days)
        for target, actual in pairs:
            assert actual >= target

    def test_invalid_day_raises(self, trading_days: pd.DatetimeIndex) -> None:
        with pytest.raises(ValueError):
            get_monthly_investment_dates(0, trading_days)
        with pytest.raises(ValueError):
            get_monthly_investment_dates(29, trading_days)

    def test_day_1(self, trading_days: pd.DatetimeIndex) -> None:
        pairs = get_monthly_investment_dates(1, trading_days)
        assert len(pairs) >= 3  # at least Jan, Feb, Mar


# ---------------------------------------------------------------------------
# get_price_on_date
# ---------------------------------------------------------------------------

class TestGetPriceOnDate:
    def test_known_date(self, sample_prices: pd.DataFrame) -> None:
        first_date = sample_prices["Date"].iloc[0]
        price = get_price_on_date(first_date, sample_prices)
        assert price == sample_prices["Close"].iloc[0]

    def test_missing_date_raises(self, sample_prices: pd.DataFrame) -> None:
        with pytest.raises(KeyError):
            get_price_on_date(pd.Timestamp("2020-01-01"), sample_prices)

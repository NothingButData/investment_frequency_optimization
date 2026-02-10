"""DCA strategy simulators.

Every strategy invests the *same total annual amount*; they differ only in
how that amount is distributed across time.  Each simulator returns a
StrategyResult dataclass that captures shares, value, and cost basis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd

from src.data import (
    build_trading_calendar,
    get_monthly_investment_dates,
    get_price_on_date,
    map_to_trading_day,
)


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class StrategyResult:
    """Holds the output of a single back-tested strategy."""

    name: str
    total_shares: float
    total_invested: float
    total_transaction_costs: float
    final_value: float
    # Per-investment records
    dates: list[pd.Timestamp] = field(default_factory=list)
    prices: list[float] = field(default_factory=list)
    shares_bought: list[float] = field(default_factory=list)
    cumulative_shares: list[float] = field(default_factory=list)
    cumulative_value: list[float] = field(default_factory=list)

    @property
    def cost_basis(self) -> float:
        return self.total_invested + self.total_transaction_costs

    @property
    def total_return(self) -> float:
        if self.cost_basis == 0:
            return 0.0
        return (self.final_value - self.cost_basis) / self.cost_basis

    @property
    def gain(self) -> float:
        return self.final_value - self.cost_basis


# ---------------------------------------------------------------------------
# Core simulation helper
# ---------------------------------------------------------------------------

def _simulate(
    name: str,
    investment_dates: list[pd.Timestamp],
    amount_per_investment: float,
    transaction_cost: float,
    df: pd.DataFrame,
) -> StrategyResult:
    """Run a generic DCA simulation.

    Parameters
    ----------
    name : str
        Human-readable strategy label.
    investment_dates : list[pd.Timestamp]
        The actual trading day for each investment.
    amount_per_investment : float
        Dollar amount invested on each date.
    transaction_cost : float
        Flat fee per trade.
    df : pd.DataFrame
        Price data with columns ["Date", "Close"].
    """
    dates_out: list[pd.Timestamp] = []
    prices_out: list[float] = []
    shares_list: list[float] = []
    cum_shares: list[float] = []
    cum_value: list[float] = []

    total_shares = 0.0
    total_invested = 0.0
    total_costs = 0.0

    last_price = df["Close"].iloc[-1]

    for inv_date in investment_dates:
        price = get_price_on_date(inv_date, df)
        net_amount = amount_per_investment - transaction_cost
        if net_amount <= 0:
            continue
        shares = net_amount / price

        total_shares += shares
        total_invested += amount_per_investment
        total_costs += transaction_cost

        dates_out.append(inv_date)
        prices_out.append(price)
        shares_list.append(shares)
        cum_shares.append(total_shares)
        cum_value.append(total_shares * price)

    final_value = total_shares * last_price

    return StrategyResult(
        name=name,
        total_shares=total_shares,
        total_invested=total_invested,
        total_transaction_costs=total_costs,
        final_value=final_value,
        dates=dates_out,
        prices=prices_out,
        shares_bought=shares_list,
        cumulative_shares=cum_shares,
        cumulative_value=cum_value,
    )


# ---------------------------------------------------------------------------
# Individual strategies
# ---------------------------------------------------------------------------

def monthly_fixed_day(
    day_of_month: int,
    monthly_amount: float,
    transaction_cost: float,
    df: pd.DataFrame,
) -> StrategyResult:
    """Strategy 1/2: invest on a fixed day of each month."""
    trading_days = build_trading_calendar(df)
    pairs = get_monthly_investment_dates(day_of_month, trading_days)
    inv_dates = [actual for _target, actual in pairs]

    return _simulate(
        name=f"Monthly (day {day_of_month})",
        investment_dates=inv_dates,
        amount_per_investment=monthly_amount,
        transaction_cost=transaction_cost,
        df=df,
    )


def all_monthly_days(
    monthly_amount: float,
    transaction_cost: float,
    df: pd.DataFrame,
) -> dict[int, StrategyResult]:
    """Strategy 2: run monthly_fixed_day for every day 1–28."""
    results: dict[int, StrategyResult] = {}
    for day in range(1, 29):
        results[day] = monthly_fixed_day(day, monthly_amount, transaction_cost, df)
    return results


def weekly_dca(
    monthly_amount: float,
    transaction_cost: float,
    df: pd.DataFrame,
    weekday: int = 0,  # 0=Monday
) -> StrategyResult:
    """Strategy 3: invest weekly on a fixed weekday.

    Weekly amount = monthly_amount / 4.33 so annual total matches.
    """
    weekly_amount = monthly_amount / (52 / 12)  # ~4.333
    trading_days = build_trading_calendar(df)

    inv_dates: list[pd.Timestamp] = []
    for td in trading_days:
        if td.weekday() == weekday:
            inv_dates.append(td)

    return _simulate(
        name=f"Weekly (weekday {weekday})",
        investment_dates=inv_dates,
        amount_per_investment=weekly_amount,
        transaction_cost=transaction_cost,
        df=df,
    )


def daily_dca(
    monthly_amount: float,
    transaction_cost: float,
    df: pd.DataFrame,
) -> StrategyResult:
    """Strategy 4: invest every trading day.

    Daily amount = monthly_amount / avg_trading_days_per_month (~21.7).
    """
    trading_days = build_trading_calendar(df)
    total_months = len(pd.date_range(
        trading_days.min(), trading_days.max(), freq="MS",
    ))
    avg_days_per_month = len(trading_days) / max(total_months, 1)
    daily_amount = monthly_amount / avg_days_per_month

    return _simulate(
        name="Daily DCA",
        investment_dates=list(trading_days),
        amount_per_investment=daily_amount,
        transaction_cost=transaction_cost,
        df=df,
    )


def random_day_monthly(
    monthly_amount: float,
    transaction_cost: float,
    df: pd.DataFrame,
    n_simulations: int = 1000,
    seed: int = 42,
) -> list[StrategyResult]:
    """Strategy 5: invest on a uniformly random trading day each month.

    Returns a list of n_simulations StrategyResult objects.
    """
    trading_days = build_trading_calendar(df)
    rng = np.random.default_rng(seed)

    # Group trading days by (year, month)
    td_series = pd.Series(trading_days)
    groups = td_series.groupby([td_series.dt.year, td_series.dt.month]).apply(list)

    results: list[StrategyResult] = []
    for i in range(n_simulations):
        inv_dates: list[pd.Timestamp] = []
        for month_days in groups:
            chosen = rng.choice(month_days)
            inv_dates.append(pd.Timestamp(chosen))

        res = _simulate(
            name=f"Random (sim {i})",
            investment_dates=sorted(inv_dates),
            amount_per_investment=monthly_amount,
            transaction_cost=transaction_cost,
            df=df,
        )
        results.append(res)

    return results


def optimal_hindsight(
    monthly_amount: float,
    transaction_cost: float,
    df: pd.DataFrame,
) -> StrategyResult:
    """Strategy 6: invest on each month's lowest close (best possible)."""
    return _hindsight(
        monthly_amount, transaction_cost, df, best=True,
    )


def worst_hindsight(
    monthly_amount: float,
    transaction_cost: float,
    df: pd.DataFrame,
) -> StrategyResult:
    """Strategy 7: invest on each month's highest close (worst possible)."""
    return _hindsight(
        monthly_amount, transaction_cost, df, best=False,
    )


def _hindsight(
    monthly_amount: float,
    transaction_cost: float,
    df: pd.DataFrame,
    *,
    best: bool,
) -> StrategyResult:
    """Helper for optimal/worst hindsight strategies."""
    df_copy = df.copy()
    df_copy["YM"] = df_copy["Date"].dt.to_period("M")

    if best:
        idx = df_copy.groupby("YM")["Close"].idxmin()
        name = "Optimal hindsight (monthly low)"
    else:
        idx = df_copy.groupby("YM")["Close"].idxmax()
        name = "Worst hindsight (monthly high)"

    inv_dates = df_copy.loc[idx, "Date"].sort_values().tolist()

    return _simulate(
        name=name,
        investment_dates=inv_dates,
        amount_per_investment=monthly_amount,
        transaction_cost=transaction_cost,
        df=df,
    )


# ---------------------------------------------------------------------------
# Run all strategies at once
# ---------------------------------------------------------------------------

@dataclass
class AllStrategyResults:
    """Container for all strategy results."""

    client_day: StrategyResult
    all_days: dict[int, StrategyResult]
    weekly: StrategyResult
    daily: StrategyResult
    random: list[StrategyResult]
    optimal: StrategyResult
    worst: StrategyResult


def run_all_strategies(
    investment_day: int,
    monthly_amount: float,
    transaction_cost: float,
    df: pd.DataFrame,
    n_random: int = 1000,
) -> AllStrategyResults:
    """Execute every strategy and return bundled results."""
    all_days = all_monthly_days(monthly_amount, transaction_cost, df)
    client_day = all_days[investment_day]

    return AllStrategyResults(
        client_day=client_day,
        all_days=all_days,
        weekly=weekly_dca(monthly_amount, transaction_cost, df),
        daily=daily_dca(monthly_amount, transaction_cost, df),
        random=random_day_monthly(monthly_amount, transaction_cost, df, n_random),
        optimal=optimal_hindsight(monthly_amount, transaction_cost, df),
        worst=worst_hindsight(monthly_amount, transaction_cost, df),
    )

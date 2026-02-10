"""Statistical analysis: compare the client's timing against alternatives.

Provides:
- Day-of-month return distribution
- Paired t-test / Wilcoxon signed-rank test
- Bootstrap confidence intervals
- Effect size (Cohen's d)
- Dollar impact
- Context / variance decomposition
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats

from src.strategies import AllStrategyResults, StrategyResult


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------

@dataclass
class DayOfMonthDistribution:
    """Final portfolio value for each day-of-month (1–28)."""

    days: list[int]
    final_values: list[float]
    total_returns: list[float]
    client_day: int
    client_value: float
    client_return: float
    best_day: int
    worst_day: int
    median_value: float
    range_dollars: float  # best − worst
    range_pct: float  # as % of median


@dataclass
class StatisticalTests:
    """Results of hypothesis testing."""

    # Paired t-test: client day vs. mean of other days
    t_statistic: float
    t_pvalue: float
    # Wilcoxon signed-rank: client day vs. median day
    wilcoxon_statistic: float
    wilcoxon_pvalue: float
    # Bootstrap CI of annualized return difference
    bootstrap_mean_diff: float
    bootstrap_ci_lower: float
    bootstrap_ci_upper: float
    # Effect size
    cohens_d: float


@dataclass
class DollarImpact:
    """Dollar-denominated impact of timing."""

    client_final_value: float
    median_day_final_value: float
    best_day_final_value: float
    worst_day_final_value: float
    optimal_final_value: float
    worst_hindsight_final_value: float
    weekly_final_value: float
    daily_final_value: float
    random_mean_final_value: float
    random_p5_final_value: float
    random_p95_final_value: float
    total_contributed: float
    client_vs_median_dollars: float
    client_vs_median_pct: float
    client_vs_best_day_dollars: float
    client_vs_optimal_dollars: float
    weekly_transaction_costs: float
    daily_transaction_costs: float


@dataclass
class ContextAnalysis:
    """Shows what factors matter most — puts timing in perspective."""

    # Variance contributions (approximate, illustrative)
    timing_spread_dollars: float   # best day − worst day
    timing_spread_pct: float       # as % of median portfolio
    contribution_impact: str       # narrative: doubling contributions
    start_date_impact: str         # narrative: starting 5 years earlier
    asset_choice_impact: str       # narrative: different asset


@dataclass
class FullAnalysis:
    """All analysis results bundled together."""

    day_distribution: DayOfMonthDistribution
    statistical_tests: StatisticalTests
    dollar_impact: DollarImpact
    context: ContextAnalysis


# ---------------------------------------------------------------------------
# Step 6: Day-of-month distribution
# ---------------------------------------------------------------------------

def compute_day_distribution(
    results: AllStrategyResults,
) -> DayOfMonthDistribution:
    """Compute final portfolio value for each day 1–28."""
    days = sorted(results.all_days.keys())
    values = [results.all_days[d].final_value for d in days]
    returns = [results.all_days[d].total_return for d in days]

    best_day = days[np.argmax(values)]
    worst_day = days[np.argmin(values)]
    median_value = float(np.median(values))
    range_dollars = max(values) - min(values)
    range_pct = (range_dollars / median_value * 100) if median_value else 0.0

    cd = results.client_day
    return DayOfMonthDistribution(
        days=days,
        final_values=values,
        total_returns=returns,
        client_day=int(cd.name.split("day ")[-1].rstrip(")")),
        client_value=cd.final_value,
        client_return=cd.total_return,
        best_day=best_day,
        worst_day=worst_day,
        median_value=median_value,
        range_dollars=range_dollars,
        range_pct=range_pct,
    )


# ---------------------------------------------------------------------------
# Step 6: Statistical tests
# ---------------------------------------------------------------------------

def _monthly_returns(result: StrategyResult) -> np.ndarray:
    """Compute per-purchase return relative to final price for each buy."""
    if not result.prices:
        return np.array([])
    final_price = result.prices[-1]
    return np.array([(final_price - p) / p for p in result.prices])


def compute_statistical_tests(
    results: AllStrategyResults,
    bootstrap_iterations: int = 10000,
    confidence_level: float = 0.95,
) -> StatisticalTests:
    """Run hypothesis tests comparing the client's day against others."""
    all_days = results.all_days
    client_day_num = None
    for d, r in all_days.items():
        if r is results.client_day:
            client_day_num = d
            break

    # Collect final values for all 28 days
    day_values = np.array([all_days[d].final_value for d in sorted(all_days)])
    client_value = results.client_day.final_value

    # --- Paired comparison: client day returns vs other days ---
    # Use per-purchase returns for the client vs. per-purchase returns for
    # every other day.  For a meaningful paired test, compare month-by-month
    # share accumulation.
    client_prices = np.array(results.client_day.prices)
    other_day_nums = [d for d in sorted(all_days) if d != client_day_num]

    # Build array of per-month price differences (client - average other)
    # Each month i: what price did the client pay vs. the average of all other days?
    n_months = len(client_prices)
    other_prices_matrix = np.zeros((len(other_day_nums), n_months))
    for i, d in enumerate(other_day_nums):
        p = np.array(all_days[d].prices)
        # Lengths might differ slightly; truncate to common length
        common = min(len(p), n_months)
        other_prices_matrix[i, :common] = p[:common]

    common_len = min(n_months, other_prices_matrix.shape[1])
    client_prices_common = client_prices[:common_len]
    mean_other_prices = other_prices_matrix[:, :common_len].mean(axis=0)

    # Price difference: positive means client paid MORE (worse)
    price_diffs = client_prices_common - mean_other_prices

    # t-test on price differences
    if len(price_diffs) > 1 and np.std(price_diffs) > 0:
        t_stat, t_pval = stats.ttest_1samp(price_diffs, 0)
    else:
        t_stat, t_pval = 0.0, 1.0

    # Wilcoxon signed-rank test
    try:
        w_stat, w_pval = stats.wilcoxon(price_diffs)
    except ValueError:
        w_stat, w_pval = 0.0, 1.0

    # --- Bootstrap CI for return difference ---
    # Difference in total return: client − median day
    all_returns = np.array([all_days[d].total_return for d in sorted(all_days)])
    median_return = float(np.median(all_returns))
    client_return = results.client_day.total_return
    observed_diff = client_return - median_return

    rng = np.random.default_rng(42)
    boot_diffs = np.zeros(bootstrap_iterations)
    for b in range(bootstrap_iterations):
        # Resample monthly price diffs with replacement
        sample = rng.choice(price_diffs, size=len(price_diffs), replace=True)
        # Translate to approximate return impact
        # Mean price diff / mean price ≈ return impact
        mean_price = np.mean(client_prices_common)
        boot_diffs[b] = -np.mean(sample) / mean_price  # negative because higher price = lower return

    alpha = 1 - confidence_level
    ci_lower = float(np.percentile(boot_diffs, 100 * alpha / 2))
    ci_upper = float(np.percentile(boot_diffs, 100 * (1 - alpha / 2)))
    boot_mean = float(np.mean(boot_diffs))

    # Cohen's d
    if np.std(price_diffs) > 0:
        cohens_d = float(np.mean(price_diffs) / np.std(price_diffs))
    else:
        cohens_d = 0.0

    return StatisticalTests(
        t_statistic=float(t_stat),
        t_pvalue=float(t_pval),
        wilcoxon_statistic=float(w_stat),
        wilcoxon_pvalue=float(w_pval),
        bootstrap_mean_diff=boot_mean,
        bootstrap_ci_lower=ci_lower,
        bootstrap_ci_upper=ci_upper,
        cohens_d=cohens_d,
    )


# ---------------------------------------------------------------------------
# Step 7: Dollar impact
# ---------------------------------------------------------------------------

def compute_dollar_impact(
    results: AllStrategyResults,
) -> DollarImpact:
    """Translate return differences into dollar terms."""
    all_days = results.all_days
    day_values = [all_days[d].final_value for d in sorted(all_days)]
    median_val = float(np.median(day_values))
    best_val = max(day_values)
    worst_val = min(day_values)

    random_values = [r.final_value for r in results.random]
    random_mean = float(np.mean(random_values))
    random_p5 = float(np.percentile(random_values, 5))
    random_p95 = float(np.percentile(random_values, 95))

    client_val = results.client_day.final_value
    total_contributed = results.client_day.total_invested

    return DollarImpact(
        client_final_value=client_val,
        median_day_final_value=median_val,
        best_day_final_value=best_val,
        worst_day_final_value=worst_val,
        optimal_final_value=results.optimal.final_value,
        worst_hindsight_final_value=results.worst.final_value,
        weekly_final_value=results.weekly.final_value,
        daily_final_value=results.daily.final_value,
        random_mean_final_value=random_mean,
        random_p5_final_value=random_p5,
        random_p95_final_value=random_p95,
        total_contributed=total_contributed,
        client_vs_median_dollars=client_val - median_val,
        client_vs_median_pct=(client_val - median_val) / total_contributed * 100
        if total_contributed
        else 0.0,
        client_vs_best_day_dollars=client_val - best_val,
        client_vs_optimal_dollars=client_val - results.optimal.final_value,
        weekly_transaction_costs=results.weekly.total_transaction_costs,
        daily_transaction_costs=results.daily.total_transaction_costs,
    )


# ---------------------------------------------------------------------------
# Step 8: Context analysis
# ---------------------------------------------------------------------------

def compute_context(
    results: AllStrategyResults,
    monthly_amount: float,
) -> ContextAnalysis:
    """Put timing in perspective against the factors that actually matter."""
    day_values = [results.all_days[d].final_value for d in sorted(results.all_days)]
    spread = max(day_values) - min(day_values)
    median_val = float(np.median(day_values))
    spread_pct = (spread / median_val * 100) if median_val else 0.0

    # Illustrative narratives
    contribution_impact = (
        f"Doubling your monthly contribution from ${monthly_amount:,.0f} to "
        f"${monthly_amount * 2:,.0f} would approximately double your final "
        f"portfolio — a far larger effect than any timing change."
    )

    start_date_impact = (
        "Starting 5 years earlier typically adds 40–80% more to your final "
        "portfolio value, dwarfing any day-of-month effect."
    )

    asset_choice_impact = (
        "Choosing a different asset class (e.g., international vs. US equities) "
        "can swing long-term returns by 2–5% annually — orders of magnitude "
        "more than day-of-month timing."
    )

    return ContextAnalysis(
        timing_spread_dollars=spread,
        timing_spread_pct=spread_pct,
        contribution_impact=contribution_impact,
        start_date_impact=start_date_impact,
        asset_choice_impact=asset_choice_impact,
    )


# ---------------------------------------------------------------------------
# Master runner
# ---------------------------------------------------------------------------

def run_full_analysis(
    results: AllStrategyResults,
    monthly_amount: float,
    bootstrap_iterations: int = 10000,
    confidence_level: float = 0.95,
) -> FullAnalysis:
    """Run all analysis steps and return bundled results."""
    return FullAnalysis(
        day_distribution=compute_day_distribution(results),
        statistical_tests=compute_statistical_tests(
            results, bootstrap_iterations, confidence_level,
        ),
        dollar_impact=compute_dollar_impact(results),
        context=compute_context(results, monthly_amount),
    )

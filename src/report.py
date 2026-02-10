"""Narrative report builder.

Generates a structured markdown report with:
1. One-line verdict
2. Key numbers
3. Chart references
4. Context section
5. Recommendation details
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from src.analysis import FullAnalysis
from src.strategies import AllStrategyResults

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"


def _fmt(val: float) -> str:
    """Format a dollar amount."""
    if abs(val) >= 1_000_000:
        return f"${val:,.0f}"
    return f"${val:,.2f}"


def _pct(val: float) -> str:
    """Format a percentage (input is a ratio, e.g. 0.05 → 5.00%)."""
    return f"{val * 100:.2f}%"


def _pct_raw(val: float) -> str:
    """Format a value already in percent form."""
    return f"{val:.2f}%"


# ---------------------------------------------------------------------------
# Decision framework
# ---------------------------------------------------------------------------

def _make_verdict(analysis: FullAnalysis) -> tuple[str, str]:
    """Return (verdict_short, verdict_detail).

    Decision framework:
      IF annualized return gap > 0.10% AND p-value < 0.05
         AND dollar impact > 1% of contributions:
          → Recommend switching
      ELSE:
          → Stay the course
    """
    st = analysis.statistical_tests
    di = analysis.dollar_impact
    dist = analysis.day_distribution

    annualized_gap = abs(st.bootstrap_mean_diff)
    p_value = st.t_pvalue
    dollar_impact_pct = abs(di.client_vs_median_pct)

    should_change = (
        annualized_gap > 0.001  # 0.10%
        and p_value < 0.05
        and dollar_impact_pct > 1.0
    )

    if should_change:
        # Find the best day
        best_day = dist.best_day
        short = (
            f"Consider switching to day {best_day} of the month."
        )
        detail = (
            f"The analysis found a statistically significant difference "
            f"(p = {p_value:.4f}) between your investment day ({dist.client_day}) "
            f"and the best-performing day ({best_day}). The estimated impact is "
            f"{_fmt(abs(di.client_vs_best_day_dollars))} over your investment "
            f"horizon, representing {dollar_impact_pct:.1f}% of your total "
            f"contributions. While this is meaningful enough to flag, remember "
            f"that past patterns may not persist."
        )
    else:
        short = "Stay the course — the difference is not meaningful."
        reasons = []
        if annualized_gap <= 0.001:
            reasons.append(
                f"the annualized return gap is tiny ({annualized_gap * 100:.3f}%)"
            )
        if p_value >= 0.05:
            reasons.append(
                f"the difference is not statistically significant (p = {p_value:.3f})"
            )
        if dollar_impact_pct <= 1.0:
            reasons.append(
                f"the dollar impact is only {dollar_impact_pct:.2f}% of "
                f"your contributions"
            )
        detail = (
            f"Your investment day ({dist.client_day}) performs within the "
            f"normal range of all possible monthly dates. Specifically, "
            + "; ".join(reasons)
            + ". Your energy is better spent on contribution amount, "
            "asset allocation, and staying invested."
        )

    return short, detail


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------

def generate_report(
    results: AllStrategyResults,
    analysis: FullAnalysis,
    ticker: str,
    monthly_amount: float,
    start_date: str,
    end_date: str,
) -> str:
    """Generate a complete markdown report."""
    verdict_short, verdict_detail = _make_verdict(analysis)
    dist = analysis.day_distribution
    st = analysis.statistical_tests
    di = analysis.dollar_impact
    ctx = analysis.context

    report = dedent(f"""\
    # Investment Timing Analysis Report

    **Ticker:** {ticker}
    **Monthly investment:** {_fmt(monthly_amount)}
    **Your investment day:** {dist.client_day}
    **Period:** {start_date} to {end_date}

    ---

    ## Verdict

    ### {verdict_short}

    {verdict_detail}

    ---

    ## Key Numbers

    | Metric | Value |
    |--------|-------|
    | Your final portfolio value | {_fmt(di.client_final_value)} |
    | Median day final value | {_fmt(di.median_day_final_value)} |
    | Best day ({dist.best_day}) final value | {_fmt(di.best_day_final_value)} |
    | Worst day ({dist.worst_day}) final value | {_fmt(di.worst_day_final_value)} |
    | Day-of-month spread | {_fmt(dist.range_dollars)} ({_pct_raw(dist.range_pct)} of median) |
    | Your day vs. median | {_fmt(di.client_vs_median_dollars)} ({_pct_raw(di.client_vs_median_pct)} of contributions) |
    | Total contributed | {_fmt(di.total_contributed)} |
    | Optimal hindsight value | {_fmt(di.optimal_final_value)} |
    | Worst hindsight value | {_fmt(di.worst_hindsight_final_value)} |
    | Weekly DCA value | {_fmt(di.weekly_final_value)} |
    | Daily DCA value | {_fmt(di.daily_final_value)} |
    | Random-day mean value | {_fmt(di.random_mean_final_value)} |

    ---

    ## Statistical Evidence

    | Test | Result | Interpretation |
    |------|--------|----------------|
    | Paired t-test (price diff) | t = {st.t_statistic:.3f}, p = {st.t_pvalue:.4f} | {"Significant" if st.t_pvalue < 0.05 else "Not significant"} at 5% level |
    | Wilcoxon signed-rank | W = {st.wilcoxon_statistic:.1f}, p = {st.wilcoxon_pvalue:.4f} | {"Significant" if st.wilcoxon_pvalue < 0.05 else "Not significant"} at 5% level |
    | Bootstrap 95% CI | [{st.bootstrap_ci_lower * 100:.3f}%, {st.bootstrap_ci_upper * 100:.3f}%] | {"Does not contain" if st.bootstrap_ci_lower > 0 or st.bootstrap_ci_upper < 0 else "Contains"} zero |
    | Cohen's d (effect size) | {st.cohens_d:.4f} | {"Negligible" if abs(st.cohens_d) < 0.2 else "Small" if abs(st.cohens_d) < 0.5 else "Medium" if abs(st.cohens_d) < 0.8 else "Large"} effect |

    ---

    ## Strategy Comparison

    | Strategy | Final Value | vs. Your Day |
    |----------|-------------|--------------|
    | Your day ({dist.client_day}) | {_fmt(di.client_final_value)} | — |
    | Best monthly day ({dist.best_day}) | {_fmt(di.best_day_final_value)} | {_fmt(di.best_day_final_value - di.client_final_value)} |
    | Worst monthly day ({dist.worst_day}) | {_fmt(di.worst_day_final_value)} | {_fmt(di.worst_day_final_value - di.client_final_value)} |
    | Weekly DCA | {_fmt(di.weekly_final_value)} | {_fmt(di.weekly_final_value - di.client_final_value)} |
    | Daily DCA | {_fmt(di.daily_final_value)} | {_fmt(di.daily_final_value - di.client_final_value)} |
    | Random day (mean) | {_fmt(di.random_mean_final_value)} | {_fmt(di.random_mean_final_value - di.client_final_value)} |
    | Optimal hindsight | {_fmt(di.optimal_final_value)} | {_fmt(di.optimal_final_value - di.client_final_value)} |
    | Worst hindsight | {_fmt(di.worst_hindsight_final_value)} | {_fmt(di.worst_hindsight_final_value - di.client_final_value)} |

    {"**Note:** Weekly DCA incurred " + _fmt(di.weekly_transaction_costs) + " in transaction costs. Daily DCA incurred " + _fmt(di.daily_transaction_costs) + "." if di.weekly_transaction_costs > 0 or di.daily_transaction_costs > 0 else ""}

    ---

    ## What Matters More Than Timing

    The difference between the best and worst investment day over {start_date}–{end_date}
    was **{_fmt(ctx.timing_spread_dollars)}** ({_pct_raw(ctx.timing_spread_pct)} of the
    median portfolio). Here's what moves the needle far more:

    1. **Contribution amount:** {ctx.contribution_impact}

    2. **Time in market:** {ctx.start_date_impact}

    3. **Asset allocation:** {ctx.asset_choice_impact}

    ---

    ## Charts

    The following charts have been saved to the `output/` directory:

    1. **day_of_month.png** — Final value by investment day (1–28)
    2. **strategy_comparison.png** — Side-by-side strategy comparison
    3. **growth_curves.png** — Portfolio growth over time
    4. **bootstrap_histogram.png** — Statistical confidence interval
    5. **waterfall.png** — What factors matter most
    6. **purchase_overlay.png** — Your purchase prices on the price chart

    ---

    ## Bottom Line

    {verdict_short} {verdict_detail}

    The most impactful actions you can take are: (1) increase your contribution
    amount if possible, (2) stay invested for the long term, and (3) ensure your
    asset allocation matches your goals.  Day-of-month timing is noise.
    """)

    return report


def save_report(report_text: str) -> Path:
    """Save the report to output/report.md and return the path."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / "report.md"
    path.write_text(report_text)
    return path

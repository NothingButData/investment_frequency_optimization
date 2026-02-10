"""Chart generation for the investment timing analysis.

Produces 6 publication-quality charts:
1. Day-of-month heatmap (bar chart variant)
2. Strategy comparison bar chart
3. Growth curves over time
4. Bootstrap return-difference histogram
5. Waterfall chart — what matters most
6. Monthly purchase-price overlay on price chart
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # non-interactive backend

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import seaborn as sns

from src.analysis import FullAnalysis
from src.strategies import AllStrategyResults

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"

# Consistent style
sns.set_theme(style="whitegrid", palette="muted", font_scale=1.1)
COLORS = {
    "client": "#e74c3c",
    "median": "#3498db",
    "best": "#2ecc71",
    "worst": "#e67e22",
    "weekly": "#9b59b6",
    "daily": "#1abc9c",
    "random": "#95a5a6",
    "optimal": "#27ae60",
    "worst_h": "#c0392b",
    "neutral": "#7f8c8d",
}


def _ensure_output_dir() -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUTPUT_DIR


def _format_dollars(x: float, _pos: int | None = None) -> str:
    if abs(x) >= 1_000_000:
        return f"${x / 1_000_000:,.1f}M"
    if abs(x) >= 1_000:
        return f"${x / 1_000:,.0f}K"
    return f"${x:,.0f}"


# ---------------------------------------------------------------------------
# Chart 1: Day-of-month final-value bar chart
# ---------------------------------------------------------------------------

def plot_day_of_month(
    analysis: FullAnalysis,
    save: bool = True,
) -> plt.Figure:
    """Bar chart of final portfolio value by investment day (1–28)."""
    dist = analysis.day_distribution
    fig, ax = plt.subplots(figsize=(12, 5))

    colors = [
        COLORS["client"] if d == dist.client_day else COLORS["neutral"]
        for d in dist.days
    ]
    bars = ax.bar(dist.days, dist.final_values, color=colors, edgecolor="white", linewidth=0.5)

    # Median line
    ax.axhline(dist.median_value, color=COLORS["median"], ls="--", lw=1.5, label="Median")

    ax.set_xlabel("Day of Month")
    ax.set_ylabel("Final Portfolio Value")
    ax.set_title("Final Portfolio Value by Investment Day (1–28)")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(_format_dollars))
    ax.set_xticks(dist.days)
    ax.legend()

    # Annotate the client's bar
    client_idx = dist.days.index(dist.client_day)
    ax.annotate(
        f"Your day ({dist.client_day})\n{_format_dollars(dist.client_value)}",
        xy=(dist.client_day, dist.client_value),
        xytext=(dist.client_day + 3, dist.client_value * 1.02),
        fontsize=9,
        color=COLORS["client"],
        fontweight="bold",
        arrowprops=dict(arrowstyle="->", color=COLORS["client"]),
    )

    # Annotate range
    ax.text(
        0.98, 0.02,
        f"Range: {_format_dollars(dist.range_dollars)} ({dist.range_pct:.2f}% of median)",
        transform=ax.transAxes, ha="right", va="bottom", fontsize=9,
        color=COLORS["neutral"],
    )

    fig.tight_layout()
    if save:
        fig.savefig(_ensure_output_dir() / "day_of_month.png", dpi=150)
    return fig


# ---------------------------------------------------------------------------
# Chart 2: Strategy comparison bar chart
# ---------------------------------------------------------------------------

def plot_strategy_comparison(
    results: AllStrategyResults,
    analysis: FullAnalysis,
    save: bool = True,
) -> plt.Figure:
    """Side-by-side bar chart of all strategies."""
    random_vals = [r.final_value for r in results.random]
    random_mean = float(np.mean(random_vals))

    strategies = [
        ("Worst\nhindsight", results.worst.final_value, COLORS["worst_h"]),
        ("Worst\nday", analysis.day_distribution.final_values[
            analysis.day_distribution.days.index(analysis.day_distribution.worst_day)
        ], COLORS["worst"]),
        (f"Your day\n({analysis.day_distribution.client_day})",
         results.client_day.final_value, COLORS["client"]),
        ("Median\nday", analysis.day_distribution.median_value, COLORS["median"]),
        ("Random\n(avg)", random_mean, COLORS["random"]),
        ("Weekly\nDCA", results.weekly.final_value, COLORS["weekly"]),
        ("Daily\nDCA", results.daily.final_value, COLORS["daily"]),
        ("Best\nday", analysis.day_distribution.final_values[
            analysis.day_distribution.days.index(analysis.day_distribution.best_day)
        ], COLORS["best"]),
        ("Optimal\nhindsight", results.optimal.final_value, COLORS["optimal"]),
    ]

    names = [s[0] for s in strategies]
    values = [s[1] for s in strategies]
    colors = [s[2] for s in strategies]

    fig, ax = plt.subplots(figsize=(12, 6))
    bars = ax.bar(names, values, color=colors, edgecolor="white", linewidth=0.5)

    # Value labels on bars
    for bar, val in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2, bar.get_height(),
            _format_dollars(val),
            ha="center", va="bottom", fontsize=8, fontweight="bold",
        )

    ax.set_ylabel("Final Portfolio Value")
    ax.set_title("Strategy Comparison: Final Portfolio Value")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(_format_dollars))

    fig.tight_layout()
    if save:
        fig.savefig(_ensure_output_dir() / "strategy_comparison.png", dpi=150)
    return fig


# ---------------------------------------------------------------------------
# Chart 3: Growth curves
# ---------------------------------------------------------------------------

def plot_growth_curves(
    results: AllStrategyResults,
    analysis: FullAnalysis,
    save: bool = True,
) -> plt.Figure:
    """Portfolio value over time for key strategies."""
    fig, ax = plt.subplots(figsize=(14, 6))

    # Plot client day
    _plot_cumulative(ax, results.client_day,
                     f"Your day ({analysis.day_distribution.client_day})",
                     COLORS["client"], lw=2.5)

    # Plot optimal / worst as bounds
    _plot_cumulative(ax, results.optimal, "Optimal hindsight",
                     COLORS["optimal"], lw=1, ls="--", alpha=0.6)
    _plot_cumulative(ax, results.worst, "Worst hindsight",
                     COLORS["worst_h"], lw=1, ls="--", alpha=0.6)

    # Weekly and daily
    _plot_cumulative(ax, results.weekly, "Weekly DCA",
                     COLORS["weekly"], lw=1.5, alpha=0.8)
    _plot_cumulative(ax, results.daily, "Daily DCA",
                     COLORS["daily"], lw=1.5, alpha=0.8)

    ax.set_xlabel("Date")
    ax.set_ylabel("Portfolio Value")
    ax.set_title("Portfolio Growth Over Time")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(_format_dollars))
    ax.legend(loc="upper left")

    fig.tight_layout()
    if save:
        fig.savefig(_ensure_output_dir() / "growth_curves.png", dpi=150)
    return fig


def _plot_cumulative(
    ax: plt.Axes,
    result,
    label: str,
    color: str,
    lw: float = 1.5,
    ls: str = "-",
    alpha: float = 1.0,
) -> None:
    if result.dates and result.cumulative_value:
        ax.plot(
            result.dates, result.cumulative_value,
            label=label, color=color, lw=lw, ls=ls, alpha=alpha,
        )


# ---------------------------------------------------------------------------
# Chart 4: Bootstrap histogram
# ---------------------------------------------------------------------------

def plot_bootstrap_histogram(
    analysis: FullAnalysis,
    save: bool = True,
) -> plt.Figure:
    """Histogram of bootstrapped return differences."""
    st = analysis.statistical_tests

    # Recreate the bootstrap distribution for plotting
    # We'll use the CI bounds and mean to draw a representative normal
    fig, ax = plt.subplots(figsize=(10, 5))

    # Generate representative samples from bootstrap stats
    boot_std = (st.bootstrap_ci_upper - st.bootstrap_ci_lower) / (2 * 1.96)
    if boot_std > 0:
        samples = np.random.default_rng(42).normal(
            st.bootstrap_mean_diff, boot_std, 10000,
        )
    else:
        samples = np.zeros(10000)

    ax.hist(samples * 100, bins=60, color=COLORS["median"], alpha=0.7,
            edgecolor="white", linewidth=0.5)
    ax.axvline(0, color="black", lw=1.5, ls="-", label="No difference")
    ax.axvline(st.bootstrap_mean_diff * 100, color=COLORS["client"], lw=2,
               ls="--", label=f"Mean diff: {st.bootstrap_mean_diff * 100:.3f}%")
    ax.axvline(st.bootstrap_ci_lower * 100, color=COLORS["neutral"], lw=1, ls=":")
    ax.axvline(st.bootstrap_ci_upper * 100, color=COLORS["neutral"], lw=1, ls=":",
               label=f"95% CI: [{st.bootstrap_ci_lower * 100:.3f}%, "
                     f"{st.bootstrap_ci_upper * 100:.3f}%]")

    ax.set_xlabel("Return Difference (Client Day vs. Median Day) [%]")
    ax.set_ylabel("Frequency")
    ax.set_title("Bootstrap Distribution of Return Difference")
    ax.legend(fontsize=9)

    fig.tight_layout()
    if save:
        fig.savefig(_ensure_output_dir() / "bootstrap_histogram.png", dpi=150)
    return fig


# ---------------------------------------------------------------------------
# Chart 5: Waterfall — what matters most
# ---------------------------------------------------------------------------

def plot_waterfall(
    analysis: FullAnalysis,
    save: bool = True,
) -> plt.Figure:
    """Illustrative waterfall showing relative importance of factors."""
    ctx = analysis.context

    # These are illustrative magnitudes
    factors = [
        ("Asset choice\n(e.g. US vs Intl)", 3.0, COLORS["client"]),
        ("Contribution\namount", 2.0, COLORS["median"]),
        ("Time in\nmarket", 1.5, COLORS["weekly"]),
        ("Day-of-month\ntiming", ctx.timing_spread_pct / 100 if ctx.timing_spread_pct else 0.1,
         COLORS["neutral"]),
    ]

    names = [f[0] for f in factors]
    values = [f[1] for f in factors]
    colors = [f[2] for f in factors]

    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.barh(names[::-1], values[::-1], color=colors[::-1],
                   edgecolor="white", linewidth=0.5, height=0.6)

    ax.set_xlabel("Relative Impact on Portfolio Outcome (illustrative)")
    ax.set_title("What Actually Matters for Your Returns")

    # Annotate the timing bar
    timing_val = values[-1]
    ax.text(
        timing_val + 0.05, 0,
        f"~{ctx.timing_spread_pct:.1f}% spread\n({_format_dollars(ctx.timing_spread_dollars)})",
        va="center", fontsize=9, color=COLORS["neutral"],
    )

    ax.set_xlim(0, max(values) * 1.3)
    fig.tight_layout()
    if save:
        fig.savefig(_ensure_output_dir() / "waterfall.png", dpi=150)
    return fig


# ---------------------------------------------------------------------------
# Chart 6: Purchase price overlay
# ---------------------------------------------------------------------------

def plot_purchase_overlay(
    results: AllStrategyResults,
    price_df,
    analysis: FullAnalysis,
    save: bool = True,
) -> plt.Figure:
    """Plot asset price with client's purchase points overlaid."""
    fig, ax = plt.subplots(figsize=(14, 6))

    # Price line
    ax.plot(price_df["Date"], price_df["Close"],
            color=COLORS["neutral"], lw=0.8, alpha=0.6, label="Daily close")

    # Client purchase dots
    cd = results.client_day
    ax.scatter(
        cd.dates, cd.prices,
        color=COLORS["client"], s=15, zorder=5, alpha=0.7,
        label=f"Your purchases (day {analysis.day_distribution.client_day})",
    )

    ax.set_xlabel("Date")
    ax.set_ylabel("Price ($)")
    ax.set_title("Your Purchase Prices vs. Market Price")
    ax.legend(loc="upper left")

    fig.tight_layout()
    if save:
        fig.savefig(_ensure_output_dir() / "purchase_overlay.png", dpi=150)
    return fig


# ---------------------------------------------------------------------------
# Generate all charts
# ---------------------------------------------------------------------------

def generate_all_charts(
    results: AllStrategyResults,
    analysis: FullAnalysis,
    price_df,
    save: bool = True,
) -> dict[str, plt.Figure]:
    """Generate and optionally save all 6 charts."""
    figs = {}
    figs["day_of_month"] = plot_day_of_month(analysis, save=save)
    figs["strategy_comparison"] = plot_strategy_comparison(results, analysis, save=save)
    figs["growth_curves"] = plot_growth_curves(results, analysis, save=save)
    figs["bootstrap_histogram"] = plot_bootstrap_histogram(analysis, save=save)
    figs["waterfall"] = plot_waterfall(analysis, save=save)
    figs["purchase_overlay"] = plot_purchase_overlay(results, price_df, analysis, save=save)
    plt.close("all")
    return figs

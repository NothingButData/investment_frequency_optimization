"""Streamlit interactive tool for investment timing exploration.

Run with:  streamlit run app/streamlit_app.py
"""

from __future__ import annotations

from datetime import date

import matplotlib
matplotlib.use("Agg")

import numpy as np
import streamlit as st

from src.data import download_prices, resolve_ticker
from src.strategies import run_all_strategies
from src.analysis import run_full_analysis
from src.visualization import (
    plot_day_of_month,
    plot_strategy_comparison,
    plot_growth_curves,
    plot_bootstrap_histogram,
    plot_waterfall,
    plot_purchase_overlay,
)
from src.report import generate_report

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Investment Timing Analysis",
    page_icon="📊",
    layout="wide",
)

st.title("Investment Timing Analysis")
st.markdown(
    "**Does your monthly investment day hurt your returns?** "
    "Configure your scenario below and click **Run Analysis**."
)

# ---------------------------------------------------------------------------
# Sidebar inputs
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("Configuration")

    ticker = st.text_input(
        "Ticker symbol",
        value="SPY",
        help="US tickers work as-is (SPY, VTI). For non-US tickers, add "
             "the exchange suffix (e.g. VWCE.DE for Xetra, VWCE.AS for "
             "Amsterdam). If omitted, common suffixes are tried automatically.",
    ).upper()
    monthly_amount = st.number_input(
        "Monthly investment ($)", min_value=1.0, value=500.0, step=50.0,
    )
    investment_day = st.slider(
        "Your investment day of month", min_value=1, max_value=28, value=15,
    )
    start_date = st.date_input(
        "Start date", value=date(2005, 1, 1), min_value=date(1990, 1, 1),
    )
    end_date = st.date_input(
        "End date", value=date(2024, 12, 31), max_value=date(2026, 1, 1),
    )
    transaction_cost = st.number_input(
        "Transaction cost per trade ($)", min_value=0.0, value=0.0, step=0.50,
    )

    st.markdown("---")
    st.subheader("Analysis Settings")
    n_random = st.slider(
        "Random simulations", min_value=100, max_value=5000, value=1000, step=100,
    )
    bootstrap_iter = st.slider(
        "Bootstrap iterations", min_value=1000, max_value=50000, value=10000,
        step=1000,
    )

    run_btn = st.button("Run Analysis", type="primary", use_container_width=True)

# ---------------------------------------------------------------------------
# Main panel
# ---------------------------------------------------------------------------

if run_btn:
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    with st.spinner("Downloading price data..."):
        try:
            df = download_prices(ticker, start_str, end_str)
        except ValueError as e:
            st.error(str(e))
            st.stop()
        except Exception as e:
            st.error(f"Failed to download data: {e}")
            st.stop()

    # Check if the ticker was auto-resolved to a different suffix
    resolved, _ = resolve_ticker(ticker, start_str, end_str)
    if resolved != ticker:
        st.info(f"Ticker **{ticker}** was resolved to **{resolved}**")
        ticker = resolved

    st.success(f"Loaded {len(df):,} trading days for {ticker}")

    with st.spinner(f"Running all strategies ({n_random} random sims)..."):
        results = run_all_strategies(
            investment_day=investment_day,
            monthly_amount=monthly_amount,
            transaction_cost=transaction_cost,
            df=df,
            n_random=n_random,
        )

    with st.spinner("Running statistical analysis..."):
        analysis = run_full_analysis(
            results=results,
            monthly_amount=monthly_amount,
            bootstrap_iterations=bootstrap_iter,
        )

    # ---- Verdict ----
    st.markdown("---")
    st.header("Verdict")
    dist = analysis.day_distribution
    di = analysis.dollar_impact
    stat = analysis.statistical_tests

    # Decision logic (mirrors report.py)
    annualized_gap = abs(stat.bootstrap_mean_diff)
    p_value = stat.t_pvalue
    dollar_impact_pct = abs(di.client_vs_median_pct)
    should_change = (
        annualized_gap > 0.001 and p_value < 0.05 and dollar_impact_pct > 1.0
    )

    if should_change:
        st.warning(
            f"Consider switching to day **{dist.best_day}**. "
            f"Estimated impact: **${abs(di.client_vs_best_day_dollars):,.0f}** "
            f"over the period."
        )
    else:
        st.info(
            "**Stay the course** — the difference is not meaningful. "
            f"Your day ({dist.client_day}) is well within the normal range."
        )

    # ---- Key metrics ----
    st.markdown("---")
    st.header("Key Metrics")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Your Portfolio", f"${di.client_final_value:,.0f}")
    col2.metric("Median Day", f"${di.median_day_final_value:,.0f}",
                delta=f"${di.client_vs_median_dollars:,.0f}")
    col3.metric("Best Day", f"${di.best_day_final_value:,.0f}")
    col4.metric("Total Contributed", f"${di.total_contributed:,.0f}")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("p-value", f"{p_value:.4f}")
    col6.metric("Cohen's d", f"{stat.cohens_d:.4f}")
    col7.metric("Day Spread", f"${dist.range_dollars:,.0f}")
    col8.metric("Spread %", f"{dist.range_pct:.2f}%")

    # ---- Charts ----
    st.markdown("---")
    st.header("Charts")

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "Day-of-Month", "Strategy Comparison", "Growth Curves",
        "Bootstrap CI", "What Matters", "Purchase Overlay",
    ])

    with tab1:
        fig1 = plot_day_of_month(analysis, save=False)
        st.pyplot(fig1)

    with tab2:
        fig2 = plot_strategy_comparison(results, analysis, save=False)
        st.pyplot(fig2)

    with tab3:
        fig3 = plot_growth_curves(results, analysis, save=False)
        st.pyplot(fig3)

    with tab4:
        fig4 = plot_bootstrap_histogram(analysis, save=False)
        st.pyplot(fig4)

    with tab5:
        fig5 = plot_waterfall(analysis, save=False)
        st.pyplot(fig5)

    with tab6:
        fig6 = plot_purchase_overlay(results, df, analysis, save=False)
        st.pyplot(fig6)

    # ---- Strategy table ----
    st.markdown("---")
    st.header("Strategy Details")

    import pandas as pd
    random_vals = [r.final_value for r in results.random]
    table_data = [
        {"Strategy": f"Your day ({dist.client_day})",
         "Final Value": di.client_final_value,
         "vs. Your Day": 0},
        {"Strategy": f"Best day ({dist.best_day})",
         "Final Value": di.best_day_final_value,
         "vs. Your Day": di.best_day_final_value - di.client_final_value},
        {"Strategy": f"Worst day ({dist.worst_day})",
         "Final Value": di.worst_day_final_value,
         "vs. Your Day": di.worst_day_final_value - di.client_final_value},
        {"Strategy": "Weekly DCA",
         "Final Value": di.weekly_final_value,
         "vs. Your Day": di.weekly_final_value - di.client_final_value},
        {"Strategy": "Daily DCA",
         "Final Value": di.daily_final_value,
         "vs. Your Day": di.daily_final_value - di.client_final_value},
        {"Strategy": "Random (mean)",
         "Final Value": di.random_mean_final_value,
         "vs. Your Day": di.random_mean_final_value - di.client_final_value},
        {"Strategy": "Optimal hindsight",
         "Final Value": di.optimal_final_value,
         "vs. Your Day": di.optimal_final_value - di.client_final_value},
        {"Strategy": "Worst hindsight",
         "Final Value": di.worst_hindsight_final_value,
         "vs. Your Day": di.worst_hindsight_final_value - di.client_final_value},
    ]
    st_df = pd.DataFrame(table_data)
    st_df["Final Value"] = st_df["Final Value"].map("${:,.0f}".format)
    st_df["vs. Your Day"] = st_df["vs. Your Day"].map("${:+,.0f}".format)
    st.dataframe(st_df, use_container_width=True, hide_index=True)

    # ---- Context ----
    st.markdown("---")
    st.header("What Matters More Than Timing")
    ctx = analysis.context
    st.markdown(f"- **Contribution amount:** {ctx.contribution_impact}")
    st.markdown(f"- **Time in market:** {ctx.start_date_impact}")
    st.markdown(f"- **Asset allocation:** {ctx.asset_choice_impact}")

    # ---- Full report download ----
    st.markdown("---")
    report_text = generate_report(
        results, analysis, ticker, monthly_amount, start_str, end_str,
    )
    st.download_button(
        "Download Full Report (Markdown)",
        data=report_text,
        file_name="investment_timing_report.md",
        mime="text/markdown",
    )

else:
    st.info("Configure your scenario in the sidebar and click **Run Analysis**.")

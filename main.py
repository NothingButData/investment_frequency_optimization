"""CLI entrypoint: run the full analysis from config.yaml.

Usage:
    python main.py                  # uses default config.yaml
    python main.py --config my.yaml # uses custom config file
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.config import load_config
from src.data import download_prices
from src.strategies import run_all_strategies
from src.analysis import run_full_analysis
from src.visualization import generate_all_charts
from src.report import generate_report, save_report


def main(config_path: str | None = None) -> None:
    print("=" * 60)
    print("  Investment Timing Analysis")
    print("=" * 60)

    # 1. Load config
    cfg = load_config(config_path)
    c = cfg.client
    a = cfg.analysis
    print(f"\nTicker:     {c.ticker}")
    print(f"Amount:     ${c.monthly_amount:,.2f}/month")
    print(f"Day:        {c.investment_day}")
    print(f"Period:     {c.start_date} to {c.end_date}")
    print(f"Tx cost:    ${c.transaction_cost:,.2f}")

    # 2. Download data
    print("\n[1/5] Downloading price data...")
    df = download_prices(c.ticker, c.start_date, c.end_date)
    print(f"       {len(df):,} trading days loaded.")

    # 3. Run strategies
    print(f"[2/5] Simulating strategies ({a.random_simulations} random sims)...")
    results = run_all_strategies(
        investment_day=c.investment_day,
        monthly_amount=c.monthly_amount,
        transaction_cost=c.transaction_cost,
        df=df,
        n_random=a.random_simulations,
    )
    print("       Done.")

    # 4. Statistical analysis
    print(f"[3/5] Running statistical analysis ({a.bootstrap_iterations} bootstrap iters)...")
    analysis = run_full_analysis(
        results=results,
        monthly_amount=c.monthly_amount,
        bootstrap_iterations=a.bootstrap_iterations,
        confidence_level=a.confidence_level,
    )
    print("       Done.")

    # 5. Generate charts
    print("[4/5] Generating charts...")
    generate_all_charts(results, analysis, df, save=True)
    print("       Saved to output/")

    # 6. Generate report
    print("[5/5] Generating report...")
    report_text = generate_report(
        results, analysis, c.ticker, c.monthly_amount, c.start_date, c.end_date,
    )
    report_path = save_report(report_text)
    print(f"       Saved to {report_path}")

    # Print summary
    print("\n" + "=" * 60)
    dist = analysis.day_distribution
    di = analysis.dollar_impact
    st = analysis.statistical_tests

    print(f"  Your day ({dist.client_day}): ${di.client_final_value:,.0f}")
    print(f"  Median day:       ${di.median_day_final_value:,.0f}")
    print(f"  Best day ({dist.best_day}):    ${di.best_day_final_value:,.0f}")
    print(f"  Worst day ({dist.worst_day}):   ${di.worst_day_final_value:,.0f}")
    print(f"  Spread:           ${dist.range_dollars:,.0f} ({dist.range_pct:.2f}%)")
    print(f"  p-value:          {st.t_pvalue:.4f}")
    print(f"  Cohen's d:        {st.cohens_d:.4f}")
    print("=" * 60)

    annualized_gap = abs(st.bootstrap_mean_diff)
    should_change = (
        annualized_gap > 0.001
        and st.t_pvalue < 0.05
        and abs(di.client_vs_median_pct) > 1.0
    )
    if should_change:
        print(f"\n  >> RECOMMENDATION: Consider switching to day {dist.best_day}.")
    else:
        print("\n  >> RECOMMENDATION: Stay the course. The difference is negligible.")

    print(f"\nFull report: {report_path}")
    print(f"Charts:      output/")
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Investment Timing Analysis")
    parser.add_argument(
        "--config", "-c", type=str, default=None,
        help="Path to config YAML file (default: config.yaml)",
    )
    args = parser.parse_args()
    main(args.config)

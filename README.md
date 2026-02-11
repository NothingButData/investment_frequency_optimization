# Investment Frequency Optimization

**Does your monthly investment date hurt your returns?**

This project analyzes whether investing on a specific day of the month (e.g.,
payday) systematically coincides with market peaks — and whether switching to a
different timing strategy (weekly, daily, or a different monthly date) would
meaningfully improve outcomes.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Edit your parameters
vi config.yaml

# Run the full analysis (CLI)
python main.py

# Or launch the interactive dashboard
streamlit run app/streamlit_app.py
```

## Configuration

Edit `config.yaml` to match your situation:

```yaml
client:
  monthly_amount: 500        # dollars invested per month
  investment_day: 15         # day of month (1-28)
  ticker: "SPY"              # Yahoo Finance ticker
  start_date: "2005-01-01"  # backtest start
  end_date: "2024-12-31"    # backtest end
  transaction_cost: 0.00     # cost per trade in dollars
```

**Non-US tickers:** Specify the exchange suffix directly (e.g. `VWCE.DE` for
Xetra, `VWCE.AS` for Amsterdam, `VWCE.L` for London). If you omit the suffix,
common suffixes are tried automatically before raising an error.

## What It Does

The tool compares 7 investment strategies — all investing the same annual total:

| Strategy | Description |
|----------|-------------|
| **Your day** | Invest monthly on your chosen day |
| **All 28 days** | Every possible monthly day, side by side |
| **Weekly DCA** | Invest weekly (same total per year) |
| **Daily DCA** | Invest every trading day |
| **Random day** | Random day each month (1,000 Monte Carlo sims) |
| **Optimal hindsight** | Each month's lowest price (theoretical best) |
| **Worst hindsight** | Each month's highest price (theoretical worst) |

It then runs statistical tests (paired t-test, Wilcoxon signed-rank,
bootstrap confidence intervals, Cohen's d) and produces:

- A clear verdict: **"Stay the course"** or **"Consider switching to day X"**
- 6 publication-quality charts
- Dollar-impact analysis
- Context: why contribution amount and time-in-market matter far more

## Output

After running `python main.py`, check the `output/` directory:

| File | Contents |
|------|----------|
| `report.md` | Full analysis report with verdict and key numbers |
| `day_of_month.png` | Portfolio value by investment day (1-28) |
| `strategy_comparison.png` | Side-by-side strategy comparison |
| `growth_curves.png` | Portfolio growth over time (with total-invested baseline) |
| `bootstrap_histogram.png` | Statistical confidence interval |
| `waterfall.png` | What factors matter most |
| `purchase_overlay.png` | Your purchase prices on the price chart |

## Interactive Dashboard

```bash
streamlit run app/streamlit_app.py
```

Adjust parameters in the sidebar and click **Run Analysis** to explore
different scenarios interactively.

The dashboard shows two rows of KPI cards:

- **Row 1:** Total Invested, Your Portfolio (with gain), Your Return %,
  Median Day, Best Day
- **Row 2:** p-value, Cohen's d, Day Spread, Spread %

When a non-US ticker is entered without a suffix, the app auto-resolves it
and displays which suffix was matched.

## Project Structure

```
├── main.py              # CLI entrypoint
├── config.yaml          # Client parameters
├── src/
│   ├── config.py        # Config loader & validation
│   ├── data.py          # Price data download & caching
│   ├── strategies.py    # 7 DCA strategy simulators
│   ├── analysis.py      # Statistical tests & dollar impact
│   ├── visualization.py # 6 chart generators
│   └── report.py        # Markdown report builder
├── app/
│   └── streamlit_app.py # Interactive Streamlit dashboard
├── tests/               # pytest suite (44 tests)
├── .devcontainer/       # GitHub Codespaces / VS Code dev container
└── output/              # Generated reports & charts
```

## GitHub Codespaces

A dev container is included (`.devcontainer/devcontainer.json`). Opening
the repo in GitHub Codespaces (or VS Code Dev Containers) will:

1. Install all Python dependencies automatically.
2. Launch the Streamlit dashboard on port 8501 with a browser preview.

No local setup required.

## Tests

```bash
pytest tests/ -v
```

## Decision Framework

The tool recommends a change **only** when all three conditions are met:

1. Annualized return gap > 0.10%
2. p-value < 0.05 (statistically significant)
3. Dollar impact > 1% of total contributions

Otherwise: **stay the course**.

## Design Notes

See [PROJECT_PLAN.md](PROJECT_PLAN.md) for the full plan and design decisions.

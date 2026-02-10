# Investment Timing Analysis — Project Plan

## Problem Statement

Clients who invest monthly on a fixed date (e.g., payday) worry that their
timing systematically coincides with market peaks, reducing their returns.
This project answers one question:

> **"Is my monthly investment date meaningfully reducing my returns compared to
> alternative timing strategies?"**

---

## Scope

- **Data**: 15–20 years of daily price history for user-specified tickers
  (default: broad market ETFs like SPY, VTI, VXUS).
- **Client inputs**: investment amount, day-of-month, ticker, horizon,
  transaction costs — supplied via a YAML/JSON config file.
- **Output**: a clear recommendation backed by statistics, dollar impact, and
  charts.

---

## Proposed Tech Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Language | Python 3.10+ | Rich financial/data ecosystem |
| Data source | `yfinance` | Free, reliable daily OHLCV history |
| Core analysis | `pandas`, `numpy` | Industry standard for tabular/time-series work |
| Statistics | `scipy.stats` | Hypothesis testing (t-tests, bootstrap CIs) |
| Visualization | `matplotlib`, `seaborn` | Publication-quality static charts |
| Interactive tool | `streamlit` | Zero-JS interactive dashboards |
| Config | `pyyaml` | Simple, human-readable client config |
| Testing | `pytest` | Standard Python test framework |

---

## Project Structure

```
investment_frequency_optimization/
├── PROJECT_PLAN.md          ← this file
├── README.md                ← user-facing docs & quickstart
├── requirements.txt         ← pinned dependencies
├── config.yaml              ← client-editable parameters
├── src/
│   ├── __init__.py
│   ├── data.py              ← download & cache price data
│   ├── strategies.py        ← DCA strategy simulators
│   ├── analysis.py          ← statistical tests & comparisons
│   ├── visualization.py     ← chart generation
│   └── report.py            ← narrative report builder
├── app/
│   └── streamlit_app.py     ← interactive exploration tool
├── tests/
│   ├── test_data.py
│   ├── test_strategies.py
│   └── test_analysis.py
├── output/                  ← generated charts & reports (gitignored)
└── .gitignore
```

---

## Step-by-Step Implementation Plan

### Phase 1 — Data Foundation

**Step 1: Project scaffolding**
- Create the directory structure above.
- Write `requirements.txt`, `.gitignore`, and a skeleton `config.yaml`.
- Set up `pytest` so `pytest` runs from the repo root.

**Step 2: Data ingestion (`src/data.py`)**
- Download daily adjusted-close prices via `yfinance` for a given ticker and
  date range.
- Cache downloads locally (parquet or CSV) to avoid repeated API calls.
- Handle missing trading days (weekends, holidays) — map calendar dates to the
  next available trading day.
- Validate: no large gaps, correct date range, prices > 0.

**Step 3: Configuration (`config.yaml`)**
- Define a sample config:
  ```yaml
  client:
    monthly_amount: 500        # dollars invested per period
    investment_day: 15         # day-of-month (1-28)
    ticker: "SPY"
    start_date: "2005-01-01"
    end_date: "2024-12-31"
    transaction_cost: 0.00     # per-trade cost in dollars
  ```
- Write a loader that validates and parses this config.

---

### Phase 2 — Strategy Simulation Engine

**Step 4: Define investment strategies (`src/strategies.py`)**

Each strategy takes the same total annual investment and distributes it
differently. All strategies are back-tested over the full date range.

| # | Strategy | Description |
|---|----------|-------------|
| 1 | **Client baseline** | Invest $X on day-of-month N |
| 2 | **Every other monthly date** | Invest $X on each of the other ~27 possible days (1–28) |
| 3 | **Weekly DCA** | Invest $X/4.33 every week (same weekday) |
| 4 | **Daily DCA** | Invest $X/~21.7 every trading day |
| 5 | **Random date each month** | Invest $X on a uniformly random trading day per month (run 1,000+ simulations) |
| 6 | **Optimal hindsight** | Invest on each month's lowest close (upper bound — not achievable) |
| 7 | **Worst hindsight** | Invest on each month's highest close (lower bound) |

For each strategy, compute:
- Total shares accumulated
- Final portfolio value
- Time-weighted & money-weighted returns (IRR)
- Cost basis

**Step 5: Trading-day mapping**
- Build a helper: given "day 15 of March 2012," return the actual trading day
  used (same day if open, else next trading day).
- This is critical for correctness — off-by-one here skews results.

---

### Phase 3 — Statistical Analysis

**Step 6: Core comparison (`src/analysis.py`)**

Answer: *"Does investing on day N produce statistically different returns than
other days?"*

- **Day-of-month return distribution**: For each day 1–28, compute the
  annualized return of a DCA strategy starting on that day. Plot the
  distribution. Where does the client's day fall?
- **Paired t-test / Wilcoxon signed-rank test**: Compare the client's day
  returns against the mean of all other days' returns over rolling windows.
- **Bootstrap confidence interval**: Resample monthly return differences
  (client day vs. median day) with 10,000 iterations. Report the 95% CI of the
  annualized return difference.
- **Effect size**: Cohen's d for practical significance, not just statistical
  significance.

**Step 7: Dollar impact**
- Translate the return difference into actual dollar terms over the client's
  horizon.
  - Example: "Over 20 years, investing on day 15 vs. the median day resulted
    in a difference of $X,XXX on a $500/month contribution — that's Y% of
    your total contributions."
- Compare against transaction costs of more-frequent strategies (weekly,
  daily).

**Step 8: Context analysis**
- Compute how much of total return variance is explained by:
  1. **Asset allocation** (which ticker) — dominant factor
  2. **Contribution amount** — second factor
  3. **Time in market** (start date) — third factor
  4. **Day-of-month timing** — expected to be negligible
- This puts the timing question in perspective.

---

### Phase 4 — Visualization

**Step 9: Chart suite (`src/visualization.py`)**

| Chart | Purpose |
|-------|---------|
| **Day-of-month heatmap** | Final portfolio value for each day 1–28 — shows how little variation there is |
| **Strategy comparison bar chart** | Side-by-side: client day, weekly, daily, random, best, worst |
| **Growth curves** | Portfolio value over time for each strategy — lines nearly overlap |
| **Return difference histogram** | Bootstrap distribution of annualized return gap — centered near zero |
| **Waterfall chart** | Breaks down what matters: asset choice → contributions → time → timing |
| **Monthly purchase price overlay** | Client's actual purchase prices plotted on the price chart — visual check for "peak buying" |

---

### Phase 5 — Report & Recommendation

**Step 10: Report generator (`src/report.py`)**
- Produce a structured text/markdown report with:
  1. **One-line verdict**: "Stay the course" or "Consider switching to X"
  2. **Key numbers**: dollar difference, annualized return gap, p-value
  3. **Charts**: embedded or saved to `output/`
  4. **Context section**: why contribution amount and time-in-market dominate
  5. **Recommendation details**: if a change is warranted, specify the
     alternative and expected benefit

Decision framework:
```
IF annualized return gap > 0.10% AND p-value < 0.05 AND dollar impact > 1% of contributions:
    → Recommend switching to the better-performing strategy
ELSE:
    → "Stay the course — the difference is not meaningful"
```

---

### Phase 6 — Interactive Tool

**Step 11: Streamlit app (`app/streamlit_app.py`)**
- Sidebar inputs: ticker, amount, day, date range, transaction cost.
- Main panel: auto-updating charts and summary statistics.
- "Compare" button: run all strategies and show results.
- Lets the client explore "what if I invested on day 1 instead of day 15?"
  scenarios interactively.

---

### Phase 7 — Testing & Polish

**Step 12: Test suite**
- `test_data.py`: mock `yfinance` responses, verify caching, date mapping.
- `test_strategies.py`: hand-calculated 3-month examples — verify share
  counts and values match.
- `test_analysis.py`: synthetic data where the answer is known — verify
  statistical tests produce correct conclusions.

**Step 13: Documentation**
- Update `README.md` with: purpose, quickstart, config reference, sample
  output, interpretation guide.

---

## Key Design Decisions

1. **Day range 1–28 only**: Avoids month-end complexity (months with 28–31
   days). Day 29–31 investors get mapped to 28.

2. **Adjusted close prices**: Accounts for dividends and splits automatically.

3. **Same total invested across strategies**: All strategies invest the same
   annual dollar amount. Weekly invests monthly_amount/4.33 per week. This
   ensures apples-to-apples comparison.

4. **Random strategy as the null hypothesis**: If the client's day performs
   within the distribution of 1,000 random-day simulations, there is no
   systematic timing problem.

5. **Transaction costs matter for higher-frequency strategies**: Daily DCA
   with a $5/trade fee would cost $1,260/year — this must be factored in.

6. **No lookahead bias**: All strategies use only information available at
   the time of each investment.

---

## Expected Outcome

Based on well-established research on dollar-cost averaging:

> The day-of-month choice is very likely to be **statistically insignificant
> and financially negligible** (< 0.05% annualized difference). The dominant
> factors are asset choice, contribution rate, and time in market.

The value of this project is giving the client **concrete, personalized
evidence** using their specific ticker, amount, and dates — so they can stop
worrying and keep investing.

---

## Execution Order Summary

| Phase | Steps | Deliverable |
|-------|-------|-------------|
| 1 — Data | 1–3 | Working data pipeline + config |
| 2 — Strategies | 4–5 | All 7 strategies simulated |
| 3 — Statistics | 6–8 | p-values, CIs, dollar impact, context |
| 4 — Charts | 9 | 6 publication-quality visualizations |
| 5 — Report | 10 | Actionable recommendation document |
| 6 — Interactive | 11 | Streamlit exploration tool |
| 7 — Testing | 12–13 | Test suite + documentation |

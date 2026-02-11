# Methodology Guide

A plain-language reference for anyone reviewing or extending this analysis.
No finance PhD required.

---

## Table of Contents

1. [What This Tool Does](#1-what-this-tool-does)
2. [Data: Where It Comes From and How We Clean It](#2-data-where-it-comes-from-and-how-we-clean-it)
3. [How the Simulation Works](#3-how-the-simulation-works)
4. [The Seven Strategies](#4-the-seven-strategies)
5. [Measure Definitions (Glossary)](#5-measure-definitions-glossary)
6. [Statistical Tests Explained](#6-statistical-tests-explained)
7. [The Decision Framework](#7-the-decision-framework)
8. [Charts and How to Read Them](#8-charts-and-how-to-read-them)
9. [Assumptions and Limitations](#9-assumptions-and-limitations)

---

## 1. What This Tool Does

A client invests a fixed dollar amount every month on a specific day (for
example, the 15th — their payday). They worry: *"Am I buying at the worst
possible time every month?"*

This tool answers that question by:

1. Downloading 15–20 years of real market prices.
2. Simulating what would have happened if the client had invested on every
   possible day of the month (1st through 28th), or weekly, or daily.
3. Comparing those outcomes with statistical tests.
4. Translating the difference into real dollars.
5. Putting it all in context: does timing even matter compared to how much
   you invest, how long you stay invested, and what you invest in?

The final output is a clear verdict: **"Stay the course"** or **"Consider
switching."**

---

## 2. Data: Where It Comes From and How We Clean It

### Source

Prices come from **Yahoo Finance** via the `yfinance` Python library. We
download **daily adjusted close prices** for the requested ticker and date
range.

### What is "Adjusted Close"?

The adjusted close is the closing price after accounting for:

- **Stock splits** — e.g. if a stock splits 2-for-1, all historical prices
  before the split are halved so the chart is continuous.
- **Dividends** — the price is adjusted downward on ex-dividend dates to
  reflect the cash paid out.

This means we don't need to track dividends or splits separately. The price
series already includes their effect, giving us a true total-return picture.

### Validation checks

Before we use the data, we verify:

| Check | Why |
|-------|-----|
| DataFrame is not empty | The ticker might be invalid or the date range might have no data. |
| All prices are > 0 | Negative or zero prices indicate data corruption. |
| No gap > 10 calendar days | A gap larger than ~2 trading weeks suggests missing data (holidays can cause up to ~4 day gaps normally). |

### Trading-day mapping

Markets are closed on weekends and holidays. If the client's chosen day (say
the 15th) falls on a Saturday, we can't invest that day. The tool handles
this by mapping to **the next available trading day**:

```
Target day:  Saturday Jan 15
Actual day:  Monday Jan 17  (the next day the market is open)
```

This is called "forward-filling" — we always move forward, never backward.
If Jan 17 is also a holiday (e.g. MLK Day), we move to Jan 18, and so on.

### Why days 1–28 only?

We restrict the day-of-month to the range 1–28 because every month has at
least 28 days. This avoids special handling for February (28/29 days) and
months with 30 or 31 days. If a client invests on the 29th, 30th, or 31st,
they would be mapped to day 28 in our analysis.

### Non-US ticker resolution

Yahoo Finance requires exchange suffixes for non-US tickers (e.g. `VWCE.DE`
for the Xetra-listed version of the Vanguard FTSE All-World ETF). If you
supply a bare ticker (e.g. `VWCE`) and it returns no data, the tool
automatically retries with 10 common suffixes in order:

| Suffix | Exchange |
|--------|----------|
| `.DE`  | Xetra (Germany) |
| `.AS`  | Euronext Amsterdam |
| `.L`   | London Stock Exchange |
| `.MI`  | Borsa Italiana (Milan) |
| `.PA`  | Euronext Paris |
| `.SW`  | SIX Swiss Exchange |
| `.TO`  | Toronto Stock Exchange |
| `.AX`  | Australian Securities Exchange |
| `.HK`  | Hong Kong Stock Exchange |
| `.T`   | Tokyo Stock Exchange |

The first suffix that returns data is used. If the ticker already contains a
`"."`, no further guessing is attempted. If nothing works, the error message
lists every ticker that was tried and suggests how to specify the suffix
directly.

### Caching

Downloaded data is saved locally as a Parquet file (a compact binary format)
so that repeated runs don't re-download from Yahoo Finance. The cache key is
based on the **resolved** ticker (after any suffix substitution), start date,
and end date.

---

## 3. How the Simulation Works

Every strategy goes through the same simulation engine. Here is what happens
on each investment date:

```
For each investment date:
    1. Look up the closing price on that day.
    2. Subtract the transaction cost from the investment amount.
       net_amount = amount - transaction_cost
       (The fee is taken out of the money you send to the broker,
        not added on top.)
    3. Calculate shares bought: shares = net_amount / price
    4. Add those shares to the running total.
    5. Accumulate total_invested += amount
       and       total_transaction_costs += transaction_cost

After all dates are processed:
    final_value = total_shares * last_closing_price_in_the_dataset
    cost_basis  = total_invested   (fees are already inside this figure)
```

### Worked example

Suppose you invest $500/month on day 15, with $0 transaction cost, and the
price is $100 on Jan 15, $110 on Feb 15, and $90 on Mar 15.

| Month | Price | Shares bought | Total shares | Value at month's price |
|-------|-------|---------------|--------------|------------------------|
| Jan   | $100  | 5.000         | 5.000        | $500.00                |
| Feb   | $110  | 4.545         | 9.545        | $1,050.00              |
| Mar   | $90   | 5.556         | 15.101       | $1,359.05              |

Final value = 15.101 shares x (last price in dataset).

If the last price in the full dataset is $120, then:
**Final value = 15.101 x $120 = $1,812.08**

This is the number we compare across strategies.

### Key principle: same total invested

All strategies invest the **same annual dollar amount**. If you contribute
$500/month = $6,000/year with a monthly strategy, then:

- **Weekly** invests $500 / 4.333 = **$115.38/week** (52 weeks/12 months = 4.333)
- **Daily** invests $500 / ~21.7 = **$23.04/trading day** (~21.7 trading
  days per month on average)

This ensures we are comparing timing only, not total dollars invested.

---

## 4. The Seven Strategies

### Strategy 1: Client's Chosen Day (Baseline)

Invest the full monthly amount on the client's specified day of each month.
If that day is not a trading day, invest on the next trading day.

*Example: $500 on the 15th of every month.*

### Strategy 2: All 28 Monthly Days

Run Strategy 1 for every day from 1 to 28. This produces 28 separate
portfolio outcomes, showing whether any particular day is consistently
better or worse.

*Think of it as: "What if my payday were the 1st? The 2nd? The 3rd?..."*

### Strategy 3: Weekly DCA

Invest every Monday (or another fixed weekday). The per-week amount is
$500 / 4.333 = $115.38 so that the annual total matches the monthly strategy.

*Tests whether splitting the contribution into smaller, more frequent
purchases helps.*

### Strategy 4: Daily DCA

Invest every single trading day. The per-day amount is $500 / ~21.7 =
$23.04.

*The maximum-frequency strategy. Provides the smoothest possible entry.*

### Strategy 5: Random Day Each Month (Monte Carlo)

For each month, pick a random trading day and invest $500. Repeat this
process 1,000 times (or however many simulations are configured). This
produces a distribution of outcomes.

*The null hypothesis: if you picked your investment day by throwing a dart
at the calendar, what range of outcomes would you see?*

If the client's actual result falls within this distribution, there is no
evidence of systematic bad timing.

### Strategy 6: Optimal Hindsight (Theoretical Best)

For each month, look at all trading days and find the one with the **lowest
closing price**. Invest the full $500 on that day.

*This is impossible in practice — you would need a time machine. It serves
as an upper bound: the best any monthly investor could ever achieve.*

### Strategy 7: Worst Hindsight (Theoretical Worst)

The mirror image: for each month, invest on the day with the **highest
closing price**.

*Also impossible to consistently achieve. It serves as a lower bound: the
worst any monthly investor could do.*

### Why include the impossible strategies?

They bracket the range of all possible monthly outcomes. If the gap between
optimal and worst hindsight is small, it proves that day-of-month timing
doesn't matter much — even with perfect foresight you can't do much better.

---

## 5. Measure Definitions (Glossary)

### Portfolio measures

| Measure | Definition | Formula |
|---------|------------|---------|
| **Total shares** | The cumulative number of shares purchased across all investment dates. | Sum of (net_amount / price) for each purchase |
| **Total invested** | The sum of all dollar amounts sent to the broker (before transaction costs are subtracted from each purchase). | Sum of amount_per_investment for each purchase |
| **Total transaction costs** | The sum of all per-trade fees paid. These are deducted *from* each investment amount, not charged on top. | Sum of transaction_cost for each purchase |
| **Cost basis** | Total out-of-pocket cost: the full amount sent to the broker each period. Because fees are deducted from each investment (not added on top), this equals total_invested. | total_invested |
| **Final value** | What the portfolio is worth at the end of the analysis period. | total_shares x last_closing_price |
| **Gain** | Profit or loss in dollar terms. | final_value - cost_basis |
| **Total return** | Percentage gain or loss relative to cost basis. | (final_value - cost_basis) / cost_basis |

### Comparison measures

| Measure | Definition |
|---------|------------|
| **Client vs. median (dollars)** | Client's final value minus the median final value across all 28 monthly days. Positive = client did better than average. |
| **Client vs. median (%)** | Same difference expressed as a percentage of total contributed dollars. |
| **Day-of-month spread (dollars)** | Best day's final value minus worst day's final value. Shows the total range of outcomes across all 28 days. |
| **Day-of-month spread (%)** | The spread divided by the median day's final value, times 100. |
| **Random mean/p5/p95** | The mean, 5th percentile, and 95th percentile of final values from the 1,000 random-day simulations. The p5–p95 range shows where 90% of random outcomes fall. |

### Price measures

| Measure | Definition |
|---------|------------|
| **Adjusted close** | The closing price corrected for dividends and splits. This is what we use for all calculations. |
| **Monthly price difference** | For a given month, the price the client paid minus the average price across all 27 other days. Positive = client paid more (worse). |

---

## 6. Statistical Tests Explained

We run four tests. Here is what each one does and how to interpret it.

### 6a. Paired t-test

**What it tests:** "Is the average price the client paid each month
systematically different from the average price across all other days?"

**How it works:**

1. For each month, calculate: `price_diff = client_price - mean_of_other_days_prices`
2. You now have one number per month (e.g. 240 numbers for 20 years).
3. The t-test asks: is the average of those numbers significantly different
   from zero?

**How to read the output:**

| Output | Meaning |
|--------|---------|
| **t-statistic** | How many standard deviations the mean price difference is from zero. Larger absolute value = stronger signal. |
| **p-value** | The probability of seeing a result this extreme if there were truly no difference. Below 0.05 = "statistically significant." |

**Example interpretation:**
- t = 0.42, p = 0.67 → "No significant difference. The client's day prices
  are indistinguishable from other days."
- t = 2.31, p = 0.02 → "Significant. The client tends to pay slightly
  higher/lower prices than average."

### 6b. Wilcoxon signed-rank test

**What it tests:** Same question as the t-test, but without assuming the
data follows a normal (bell-curve) distribution.

**Why we use it:** Financial data is often skewed (big moves in one
direction). The Wilcoxon test is more robust to outliers and skewness.

**How to read it:** Same as the t-test — look at the p-value. Below 0.05 =
significant.

### 6c. Bootstrap confidence interval

**What it tests:** "What is the likely range of the return difference
between the client's day and the median day?"

**How it works:**

1. Take the monthly price differences (same ones from the t-test).
2. Randomly resample them with replacement (like drawing from a hat and
   putting the slip back). Do this 10,000 times.
3. For each resample, compute the mean return impact.
4. Sort all 10,000 results. The middle 95% gives you the 95% confidence
   interval.

**How to read it:**

| Result | Meaning |
|--------|---------|
| CI contains zero (e.g. [-0.05%, +0.03%]) | The difference could easily be zero. No meaningful timing effect. |
| CI entirely above zero (e.g. [+0.02%, +0.08%]) | The client's day consistently provides slightly better returns. |
| CI entirely below zero (e.g. [-0.09%, -0.01%]) | The client's day consistently provides slightly worse returns. |

The **bootstrap mean** is the center of the distribution — our best estimate
of the true return difference.

### 6d. Cohen's d (effect size)

**What it measures:** The *practical* size of the difference, regardless of
whether it's statistically significant.

**Formula:** `d = mean(price_differences) / std(price_differences)`

**How to interpret:**

| Cohen's d | Interpretation |
|-----------|----------------|
| < 0.2 | **Negligible** — the difference is trivially small |
| 0.2 – 0.5 | **Small** — detectable but minor |
| 0.5 – 0.8 | **Medium** — noticeable |
| > 0.8 | **Large** — substantial |

**Why we need this:** A p-value can be "significant" (p < 0.05) even when
the actual difference is tiny, especially with large sample sizes (240+
months of data). Cohen's d tells you whether the difference is large enough
to care about in practice.

---

## 7. The Decision Framework

The tool makes a recommendation using a three-gate framework. All three
conditions must be true to recommend a change:

```
Gate 1: Annualized return gap > 0.10%
        (The bootstrap mean difference must exceed 10 basis points.)

Gate 2: p-value < 0.05
        (The paired t-test must be statistically significant.)

Gate 3: Dollar impact > 1% of total contributions
        (The difference between client's day and the median day,
         expressed as a percentage of total dollars invested,
         must exceed 1%.)
```

### Why three gates?

| Gate | What it prevents |
|------|------------------|
| Gate 1 (return gap) | Filters out trivially small return differences that wouldn't matter even if real. 0.10% per year is the "do I care?" threshold. |
| Gate 2 (p-value) | Ensures the pattern is not due to random noise. With 20 years of data, we have enough power to detect even small effects, so this gate filters out the truly random ones. |
| Gate 3 (dollar impact) | Translates the abstract percentage into real money. A difference that sounds small in percentage terms but adds up to >1% of your contributions is worth noting. |

### Outcome

- **All three gates pass:** "Consider switching to day X" — with a
  caveat that historical patterns may not persist.
- **Any gate fails:** "Stay the course — the difference is not
  meaningful." The report lists which specific gates failed and why.

---

## 8. Charts and How to Read Them

### Chart 1: Day-of-Month Bar Chart (`day_of_month.png`)

**What it shows:** 28 bars, one for each possible investment day, showing
the final portfolio value.

**What to look for:**
- The client's bar is highlighted in red.
- A dashed blue line shows the median across all 28 days.
- The annotation in the bottom-right shows the total dollar spread and
  its percentage. If this percentage is small (typically < 1%), then the
  day truly doesn't matter.

**Common pattern:** All 28 bars are nearly the same height, often within a
fraction of a percent of each other.

### Chart 2: Strategy Comparison (`strategy_comparison.png`)

**What it shows:** A bar for each strategy — ordered from worst to best:
worst hindsight, worst day, client day, median day, random mean, weekly,
daily, best day, optimal hindsight.

**What to look for:**
- How close the client's bar is to the median/random/weekly/daily bars.
- The gap between optimal and worst hindsight — this is the absolute maximum
  that timing could ever matter.

### Chart 3: Growth Curves (`growth_curves.png`)

**What it shows:** Portfolio value over time for the client's day, weekly
DCA, daily DCA, and the optimal/worst hindsight bounds. A shaded area with
a dotted line shows cumulative contributions ("Total invested") so you can
immediately see how much the market has grown your money above what you put in.

**What to look for:**
- All the lines should nearly overlap, which demonstrates visually that
  timing differences are dwarfed by the overall market trend.
- The gap between the strategy lines and the shaded "Total invested" area
  represents actual gains.
- The optimal/worst hindsight lines form an envelope — the client's line
  should sit comfortably within it.

### Chart 4: Bootstrap Histogram (`bootstrap_histogram.png`)

**What it shows:** The distribution of 10,000 bootstrapped return
differences (client day vs. median day).

**What to look for:**
- The histogram should be centered near zero.
- A vertical black line at zero marks "no difference."
- Dotted gray lines mark the 95% confidence interval bounds.
- If zero is well within the histogram (and within the CI), there is no
  meaningful timing effect.

### Chart 5: Waterfall — What Matters Most (`waterfall.png`)

**What it shows:** Horizontal bars comparing the relative importance of
four factors: asset choice, contribution amount, time in market, and
day-of-month timing.

**What to look for:**
- The timing bar should be vanishingly small compared to the other three.
- This is the "so what?" chart — it puts the whole analysis in perspective.

### Chart 6: Purchase Price Overlay (`purchase_overlay.png`)

**What it shows:** The asset's daily closing price as a gray line, with red
dots marking each of the client's actual purchase dates and prices.

**What to look for:**
- Are the red dots clustered at peaks? That would support the worry.
- More likely, the dots are scattered randomly across the price line — which
  means there is no systematic "peak buying" pattern.

---

## 9. Assumptions and Limitations

### Assumptions

| Assumption | Implication |
|------------|-------------|
| **Fractional shares are allowed** | We assume you can buy $115.38 worth of stock even if one share costs $400. Most modern brokerages support fractional shares. If yours doesn't, there would be small rounding effects. |
| **Prices are adjusted for dividends and splits** | We use total-return prices. If you're in a non-dividend-reinvesting account, actual results would differ slightly. |
| **Transaction costs are flat per trade, deducted from the investment** | We model a fixed dollar fee (e.g. $5) per transaction, deducted from each investment amount (`net_amount = amount - fee`). The fee is *not* charged on top; it reduces the amount used to buy shares. Percentage-based fees are not currently supported. |
| **Same total annual investment** | All strategies invest the same total per year. In practice, switching from monthly to weekly or daily doesn't change how much you invest — just when. |
| **No tax effects** | We don't model capital gains taxes, tax-loss harvesting, or the tax implications of more-frequent trading. |
| **No market impact** | We assume your trades don't move the market price. Valid for retail-size investments. |
| **Historical prices predict the structure (not the level) of future markets** | We assume that the *lack* of a day-of-month effect in the past means there won't be one in the future. We do NOT assume past returns will repeat. |

### Limitations

| Limitation | What it means |
|------------|---------------|
| **Survivorship bias in tickers** | If you test SPY, you're looking at a fund that has been successful for 20+ years. Tickers that went to zero aren't in the analysis. |
| **Backtesting is not a guarantee** | All results are historical. A strategy that "worked" in the past may not work going forward. |
| **Short periods can distort results** | With fewer than 5 years of data, the sample size for monthly purchases is small (<60) and statistical power is limited. |
| **The random strategy uses a fixed seed** | Results are reproducible but represent one particular set of random draws. Changing the seed would give slightly different (but similarly distributed) results. |
| **Context analysis is illustrative** | The waterfall chart comparing asset choice, contribution, and timing uses general research-based estimates, not a formal variance decomposition from the client's specific data. |
| **One asset at a time** | The tool analyzes one ticker per run. If a client holds multiple assets, each would need a separate analysis. |

---

## Quick Reference Card

| Term | One-line definition |
|------|---------------------|
| DCA | Dollar-cost averaging: investing a fixed dollar amount at regular intervals |
| Adjusted close | Closing price corrected for dividends and splits |
| Trading day | A day the stock market is open (excludes weekends and holidays) |
| Forward-fill | When a target date is not a trading day, use the next available one |
| Cost basis | Total money sent to the broker: equals total_invested (fees are deducted from each investment, not added on top) |
| Final value | total_shares x last_closing_price |
| Total return | (final_value - cost_basis) / cost_basis |
| p-value | Probability of observing this result if there were truly no difference |
| Cohen's d | Practical effect size: mean / standard deviation of price differences |
| Bootstrap CI | Confidence interval built by resampling the data 10,000 times |
| Hindsight strategy | Investing at each month's best/worst price (impossible in practice) |
| Monte Carlo | Running many random simulations to see the range of possible outcomes |

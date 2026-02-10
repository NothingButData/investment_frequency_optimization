"""Data ingestion: download, cache, and validate daily price data."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

DATA_CACHE_DIR = Path(__file__).resolve().parent.parent / "data_cache"

# Common Yahoo Finance exchange suffixes, ordered by popularity.
EXCHANGE_SUFFIXES = [
    ".DE",   # Xetra (Germany)
    ".AS",   # Euronext Amsterdam
    ".L",    # London Stock Exchange
    ".MI",   # Borsa Italiana (Milan)
    ".PA",   # Euronext Paris
    ".SW",   # SIX Swiss Exchange
    ".TO",   # Toronto Stock Exchange
    ".AX",   # Australian Securities Exchange
    ".HK",   # Hong Kong Stock Exchange
    ".T",    # Tokyo Stock Exchange
]


# ---------------------------------------------------------------------------
# Ticker resolution
# ---------------------------------------------------------------------------

def resolve_ticker(
    ticker: str, start: str, end: str,
) -> tuple[str, pd.DataFrame]:
    """Try to download data for *ticker*, falling back to exchange suffixes.

    If the bare ticker returns no data **and** does not already contain a
    ``"."``, common exchange suffixes are tried automatically.

    Returns (resolved_ticker, raw_dataframe).  The DataFrame may be empty if
    nothing worked.
    """
    raw = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)
    if not raw.empty:
        return ticker, raw

    # If the ticker already carries a suffix, don't guess further.
    if "." in ticker:
        return ticker, raw

    for suffix in EXCHANGE_SUFFIXES:
        candidate = f"{ticker}{suffix}"
        raw = yf.download(candidate, start=start, end=end, auto_adjust=True, progress=False)
        if not raw.empty:
            return candidate, raw

    return ticker, pd.DataFrame()


# ---------------------------------------------------------------------------
# Download & cache
# ---------------------------------------------------------------------------

def _cache_path(ticker: str, start: str, end: str) -> Path:
    """Return a deterministic cache file path for a given query."""
    key = f"{ticker}_{start}_{end}"
    h = hashlib.md5(key.encode()).hexdigest()[:10]
    return DATA_CACHE_DIR / f"{ticker}_{h}.parquet"


def download_prices(
    ticker: str,
    start: str,
    end: str,
    *,
    use_cache: bool = True,
) -> pd.DataFrame:
    """Download daily adjusted-close prices and return a clean DataFrame.

    Parameters
    ----------
    ticker : str
        Yahoo Finance ticker symbol (e.g. "SPY", "VWCE.DE").
        If the ticker is not found and contains no ``"."``, common
        exchange suffixes (.DE, .AS, .L, etc.) are tried automatically.
    start, end : str
        Date strings in "YYYY-MM-DD" format.
    use_cache : bool
        If True, read from / write to the local parquet cache.

    Returns
    -------
    pd.DataFrame
        Columns: ["Date", "Close"]  (Date is datetime, Close is float).
        Sorted by Date ascending.  Only trading days are included.
    """
    if use_cache:
        cache = _cache_path(ticker, start, end)
        if cache.exists():
            df = pd.read_parquet(cache)
            return df

    resolved, raw = resolve_ticker(ticker, start, end)

    if raw.empty:
        tried = [ticker] + [f"{ticker}{s}" for s in EXCHANGE_SUFFIXES]
        raise ValueError(
            f"No data returned for ticker={ticker!r} "
            f"between {start} and {end}.\n"
            f"Tried: {', '.join(tried)}\n"
            f"If this is a non-US ticker, specify the exchange suffix "
            f"directly, e.g. VWCE.DE (Xetra), VWCE.AS (Amsterdam), "
            f"VWCE.L (London)."
        )

    if resolved != ticker:
        print(f"Note: ticker {ticker!r} resolved to {resolved!r}")
        # Cache under the resolved name so future lookups hit the cache
        ticker = resolved

    # yfinance may return MultiIndex columns when auto_adjust=True
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)

    df = (
        raw[["Close"]]
        .copy()
        .reset_index()
        .rename(columns={"Date": "Date", "Close": "Close"})
    )
    df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
    df["Close"] = df["Close"].astype(float)
    df = df.sort_values("Date").reset_index(drop=True)

    validate_prices(df, start, end)

    if use_cache:
        DATA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        df.to_parquet(cache, index=False)

    return df


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_prices(df: pd.DataFrame, start: str, end: str) -> None:
    """Raise if the data looks wrong."""
    if df.empty:
        raise ValueError("Price DataFrame is empty.")

    if (df["Close"] <= 0).any():
        raise ValueError("Found non-positive prices.")

    # Flag gaps > 5 trading days (~1 calendar week)
    gaps = df["Date"].diff().dt.days
    max_gap = gaps.max()
    if max_gap > 10:
        raise ValueError(
            f"Largest gap between trading days is {max_gap} calendar days "
            f"(expected <=10). Data may be incomplete."
        )


# ---------------------------------------------------------------------------
# Trading-day helpers
# ---------------------------------------------------------------------------

def build_trading_calendar(df: pd.DataFrame) -> pd.DatetimeIndex:
    """Return a DatetimeIndex of all trading days present in df."""
    return pd.DatetimeIndex(df["Date"].values)


def map_to_trading_day(
    target_date: pd.Timestamp,
    trading_days: pd.DatetimeIndex,
) -> pd.Timestamp | None:
    """Map a calendar date to the next available trading day.

    If *target_date* is a trading day, return it.  Otherwise return the
    first trading day **on or after** *target_date*.  Returns None if
    there is no such day in the calendar.
    """
    target_date = pd.Timestamp(target_date).normalize()
    # searchsorted returns the insertion point – the first day >= target
    idx = trading_days.searchsorted(target_date, side="left")
    if idx < len(trading_days):
        return trading_days[idx]
    return None


def get_monthly_investment_dates(
    day_of_month: int,
    trading_days: pd.DatetimeIndex,
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """For each month in the calendar, compute the target date and actual
    trading day used.

    Parameters
    ----------
    day_of_month : int
        Desired calendar day (1–28).
    trading_days : pd.DatetimeIndex
        Sorted index of trading days.

    Returns
    -------
    list of (target_date, actual_trading_day) tuples.
    """
    if not 1 <= day_of_month <= 28:
        raise ValueError(f"day_of_month must be 1–28, got {day_of_month}")

    first = trading_days.min()
    last = trading_days.max()

    # Generate one target date per month
    months = pd.date_range(
        start=first.replace(day=1),
        end=last,
        freq="MS",  # month start
    )

    results: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    for month_start in months:
        try:
            target = month_start.replace(day=day_of_month)
        except ValueError:
            # Should not happen for days 1-28, but guard anyway
            target = month_start + pd.offsets.MonthEnd(0)

        actual = map_to_trading_day(target, trading_days)
        if actual is not None and actual <= last:
            results.append((target, actual))

    return results


def get_price_on_date(
    date: pd.Timestamp,
    df: pd.DataFrame,
) -> float:
    """Return the closing price on a specific trading day."""
    mask = df["Date"] == pd.Timestamp(date).normalize()
    if mask.any():
        return float(df.loc[mask, "Close"].iloc[0])
    raise KeyError(f"No price data for {date}")

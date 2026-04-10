"""
MONAD Quant - Alpha Vantage Data Fetcher
Fetches OHLCV data for ETFs and BTC with local CSV caching
to conserve free-tier API calls (25/day limit).
"""

import os
import time
import logging
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dotenv import load_dotenv
import yfinance as yf

log = logging.getLogger(__name__)

load_dotenv()

API_KEY = os.getenv("ALPHA_VANTAGE_KEY")
BASE_URL = "https://www.alphavantage.co/query"
CACHE_DIR = os.path.join(os.path.dirname(__file__), "../../data/cache")


def _ensure_cache_dir():
    os.makedirs(CACHE_DIR, exist_ok=True)


def _cache_path(symbol: str, interval: str) -> str:
    return os.path.join(CACHE_DIR, f"{symbol}_{interval}.csv")


def _cache_is_fresh(path: str, max_age_hours: int = 24) -> bool:
    if not os.path.exists(path):
        return False
    modified = datetime.fromtimestamp(os.path.getmtime(path))
    return datetime.now() - modified < timedelta(hours=max_age_hours)


def fetch_daily(symbol: str, outputsize: str = "full", use_cache: bool = True) -> pd.DataFrame:
    """
    Fetch daily OHLCV data for a stock/ETF symbol.
    Returns a DataFrame indexed by date.
    """
    _ensure_cache_dir()
    cache_file = _cache_path(symbol, "daily")

    if use_cache and _cache_is_fresh(cache_file):
        print(f"[cache] Loading {symbol} daily from cache")
        df = pd.read_csv(cache_file, index_col=0, parse_dates=True)
        return df

    print(f"[api] Fetching {symbol} daily from Alpha Vantage...")
    params = {
        "function": "TIME_SERIES_DAILY",
        "symbol": symbol,
        "outputsize": outputsize,
        "apikey": API_KEY,
    }
    resp = requests.get(BASE_URL, params=params)
    resp.raise_for_status()
    data = resp.json()

    if "Time Series (Daily)" not in data:
        raise ValueError(f"Unexpected response for {symbol}: {data.get('Note') or data.get('Information') or data}")

    ts = data["Time Series (Daily)"]
    df = pd.DataFrame.from_dict(ts, orient="index")
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    df.columns = ["open", "high", "low", "close", "volume"]
    df = df.astype(float)

    df.to_csv(cache_file)
    print(f"[cache] Saved {symbol} daily to {cache_file}")
    return df


def fetch_crypto_daily(symbol: str = "BTC", market: str = "USD", use_cache: bool = True) -> pd.DataFrame:
    """
    Fetch daily OHLCV data for a crypto asset (default BTC/USD).
    """
    _ensure_cache_dir()
    cache_key = f"{symbol}{market}"
    cache_file = _cache_path(cache_key, "daily")

    if use_cache and _cache_is_fresh(cache_file):
        print(f"[cache] Loading {symbol}/{market} from cache")
        df = pd.read_csv(cache_file, index_col=0, parse_dates=True)
        return df

    print(f"[api] Fetching {symbol}/{market} from Alpha Vantage...")
    params = {
        "function": "DIGITAL_CURRENCY_DAILY",
        "symbol": symbol,
        "market": market,
        "apikey": API_KEY,
    }
    resp = requests.get(BASE_URL, params=params)
    resp.raise_for_status()
    data = resp.json()

    key = f"Time Series (Digital Currency Daily)"
    if key not in data:
        raise ValueError(f"Unexpected response: {data.get('Note') or data.get('Information') or data}")

    ts = data[key]
    rows = []
    for date, vals in ts.items():
        rows.append({
            "date": date,
            "open":   float(vals["1. open"]),
            "high":   float(vals["2. high"]),
            "low":    float(vals["3. low"]),
            "close":  float(vals["4. close"]),
            "volume": float(vals["5. volume"]),
        })
    df = pd.DataFrame(rows).set_index("date")
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()

    df.to_csv(cache_file)
    print(f"[cache] Saved {symbol}/{market} to {cache_file}")
    return df


def fetch_crypto_hourly(symbol: str = "BTC", market: str = "USD", use_cache: bool = True) -> pd.DataFrame:
    """
    Fetch hourly OHLCV data for a crypto asset using Alpha Vantage CRYPTO_INTRADAY.
    Returns a DataFrame indexed by datetime (UTC).
    """
    _ensure_cache_dir()
    cache_key = f"{symbol}{market}"
    cache_file = _cache_path(cache_key, "60min")

    if use_cache and _cache_is_fresh(cache_file, max_age_hours=1):
        print(f"[cache] Loading {symbol}/{market} hourly from cache")
        df = pd.read_csv(cache_file, index_col=0, parse_dates=True)
        return df

    print(f"[api] Fetching {symbol}/{market} hourly from Alpha Vantage...")
    params = {
        "function": "CRYPTO_INTRADAY",
        "symbol": symbol,
        "market": market,
        "interval": "60min",
        "outputsize": "full",
        "apikey": API_KEY,
    }
    resp = requests.get(BASE_URL, params=params)
    resp.raise_for_status()
    data = resp.json()

    key = "Time Series Crypto (60min)"
    if key not in data:
        raise ValueError(f"Unexpected response for {symbol}: {data.get('Note') or data.get('Information') or data}")

    ts = data[key]
    df = pd.DataFrame.from_dict(ts, orient="index")
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    df.columns = ["open", "high", "low", "close", "volume"]
    df = df.astype(float)

    df.to_csv(cache_file)
    print(f"[cache] Saved {symbol}/{market} hourly to {cache_file}")
    return df


def fetch_rsi(symbol: str, interval: str = "daily", time_period: int = 14) -> pd.DataFrame:
    """Fetch RSI directly from Alpha Vantage technical indicator endpoint."""
    print(f"[api] Fetching RSI for {symbol}...")
    params = {
        "function": "RSI",
        "symbol": symbol,
        "interval": interval,
        "time_period": time_period,
        "series_type": "close",
        "apikey": API_KEY,
    }
    resp = requests.get(BASE_URL, params=params)
    resp.raise_for_status()
    data = resp.json()

    ts = data.get("Technical Analysis: RSI", {})
    df = pd.DataFrame.from_dict(ts, orient="index").astype(float)
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    df.columns = ["rsi"]
    return df


def fetch_macd(symbol: str, interval: str = "daily") -> pd.DataFrame:
    """Fetch MACD from Alpha Vantage."""
    print(f"[api] Fetching MACD for {symbol}...")
    params = {
        "function": "MACD",
        "symbol": symbol,
        "interval": interval,
        "series_type": "close",
        "apikey": API_KEY,
    }
    resp = requests.get(BASE_URL, params=params)
    resp.raise_for_status()
    data = resp.json()

    ts = data.get("Technical Analysis: MACD", {})
    df = pd.DataFrame.from_dict(ts, orient="index").astype(float)
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    df.columns = ["macd", "macd_signal", "macd_hist"]
    return df


def validate_ohlc(df: pd.DataFrame, symbol: str = "") -> pd.DataFrame:
    """Validate OHLC invariants and drop bars with bad data.

    Checks: low <= open <= high, low <= close <= high, volume >= 0.
    Drops invalid rows and logs warnings. Returns cleaned DataFrame.
    """
    if df.empty:
        return df

    bad_low_high = df["low"] > df["high"]
    bad_open = (df["open"] < df["low"]) | (df["open"] > df["high"])
    bad_close = (df["close"] < df["low"]) | (df["close"] > df["high"])
    bad_volume = df["volume"] < 0
    bad_mask = bad_low_high | bad_open | bad_close | bad_volume

    n_bad = bad_mask.sum()
    if n_bad > 0:
        log.warning(
            f"[ohlc] {symbol}: dropping {n_bad}/{len(df)} bars with invalid OHLC "
            f"(low>high={bad_low_high.sum()}, open_range={bad_open.sum()}, "
            f"close_range={bad_close.sum()}, neg_vol={bad_volume.sum()})"
        )
        df = df[~bad_mask].copy()

    # Check for zero/NaN prices (corrupt data)
    zero_price = (df[["open", "high", "low", "close"]] == 0).any(axis=1)
    nan_price = df[["open", "high", "low", "close"]].isna().any(axis=1)
    corrupt = zero_price | nan_price
    n_corrupt = corrupt.sum()
    if n_corrupt > 0:
        log.warning(f"[ohlc] {symbol}: dropping {n_corrupt} bars with zero/NaN prices")
        df = df[~corrupt].copy()

    return df


def fetch_yfinance(symbol: str, start: str, end: str, interval: str = "1d",
                   max_retries: int = 4) -> pd.DataFrame:
    """Fetch OHLCV data from yfinance with retry logic and OHLC validation.

    Retries up to max_retries times with exponential backoff (2s, 4s, 8s, 16s)
    on network errors. Validates OHLC invariants before returning.
    """
    print(f"[yfinance] Fetching {symbol} {interval} from {start} to {end}...")

    last_error = None
    for attempt in range(max_retries):
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start, end=end, interval=interval)
            break
        except Exception as exc:
            last_error = exc
            if attempt < max_retries - 1:
                wait = 2 ** (attempt + 1)
                log.warning(
                    f"[yfinance] {symbol} fetch failed (attempt {attempt + 1}/{max_retries}): "
                    f"{exc} — retrying in {wait}s"
                )
                time.sleep(wait)
            else:
                log.error(f"[yfinance] {symbol} fetch failed after {max_retries} attempts: {exc}")
                raise

    df.columns = [c.lower() for c in df.columns]
    df = df[["open", "high", "low", "close", "volume"]]
    df.index = pd.to_datetime(df.index)
    if df.index.tz is not None:
        df.index = df.index.tz_convert(None)
    if interval in ("1d", "1wk", "1mo"):
        df.index = df.index.normalize()

    df = validate_ohlc(df, symbol)
    return df
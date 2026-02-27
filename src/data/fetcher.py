"""
MONAD Quant - Alpha Vantage Data Fetcher
Fetches OHLCV data for ETFs and BTC with local CSV caching
to conserve free-tier API calls (25/day limit).
"""

import os
import requests
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
import yfinance as yf

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


def fetch_btc_hourly(start: str, end: str) -> pd.DataFrame:
    """
    Fetch hourly BTC-USD OHLCV via yfinance.
    yfinance supports up to 730 days of hourly history.
    """
    print(f"[yfinance] Fetching BTC-USD hourly from {start} to {end}...")
    ticker = yf.Ticker("BTC-USD")
    df = ticker.history(start=start, end=end, interval="1h")
    df.columns = [c.lower() for c in df.columns]
    df = df[["open", "high", "low", "close", "volume"]]
    df.index = pd.to_datetime(df.index)
    if df.index.tz is not None:
        df.index = df.index.tz_convert(None)
    return df


def fetch_yfinance(symbol: str, start: str, end: str) -> pd.DataFrame:
    print(f"[yfinance] Fetching {symbol} from {start} to {end}...")
    ticker = yf.Ticker(symbol)
    df = ticker.history(start=start, end=end)
    df.columns = [c.lower() for c in df.columns]
    df = df[["open", "high", "low", "close", "volume"]]
    df.index = pd.to_datetime(df.index)
    if df.index.tz is not None:
        df.index = df.index.tz_convert(None)  # strip timezone
    df.index = df.index.normalize()           # remove time component
    return df
"""
MONAD Quant - Main Entry Point

Run modes:
  python main.py                      — standard backtest (default)
  python main.py --mode=walk-forward  — walk-forward parameter optimization (OOS)
"""

import argparse
from datetime import datetime, timedelta
import config
from src.data.fetcher import fetch_yfinance
from src.backtest.runner import run_backtest

# yfinance limits hourly data to the most recent 730 days.
_YFINANCE_HOURLY_MAX_DAYS = 730

# Map ACTIVE_MODE to (yfinance symbol, interval, asset config key)
MODE_MAP = {
    "BTC_HOURLY":  ("BTC-USD", "1h",  "BTC_HOURLY"),
    "BTC_DAILY":   ("BTC-USD", "1d",  "BTC"),
    "QQQ":         ("QQQ",     "1d",  "QQQ"),
    "QQQ_HOURLY":  ("QQQ",     "1h",  "QQQ_HOURLY"),
    "TQQQ_HOURLY": ("TQQQ",    "1h",  "TQQQ_HOURLY"),
    "GDXU_HOURLY": ("GDXU",    "1h",  "GDXU_HOURLY"),
    "SOXL_HOURLY": ("SOXL",    "1h",  "SOXL_HOURLY"),
    "SOXL_DAILY":  ("SOXL",    "1d",  "SOXL"),
    "LABU_HOURLY": ("LABU",    "1h",  "LABU_HOURLY"),
    "TNA_HOURLY":  ("TNA",     "1h",  "TNA_HOURLY"),
}

def _validate_config(mode: str, asset_key: str, asset_config: dict) -> None:
    """Validate critical config invariants at startup.

    Catches misconfigurations that would otherwise produce silent wrong results
    or confusing runtime errors deep in the backtest/live loop.
    """
    errors = []

    # 1. Asset key must exist in ASSETS dict
    if asset_key not in config.ASSETS:
        errors.append(
            f"MODE_MAP['{mode}'] references asset_key '{asset_key}' "
            f"which does not exist in config.ASSETS. "
            f"Available: {', '.join(sorted(config.ASSETS.keys()))}"
        )

    # 2. Mode should be in _MODE_TO_ASSET for correct DEFAULT_ASSET resolution
    if mode not in config._MODE_TO_ASSET:
        errors.append(
            f"ACTIVE_MODE='{mode}' is not in config._MODE_TO_ASSET. "
            f"DEFAULT_ASSET will fall back to 'BTC'. "
            f"Add '{mode}' to _MODE_TO_ASSET in config.py."
        )

    # 3. Required keys must be present in asset config
    required_keys = ["target_gain_pct", "stop_loss_pct", "require_signals"]
    missing = [k for k in required_keys if k not in asset_config]
    if missing:
        errors.append(
            f"ASSETS['{asset_key}'] is missing required keys: {missing}"
        )

    # 4. Stop must be less than target (otherwise every trade is a structural loser)
    target = asset_config.get("target_gain_pct", 0)
    stop = asset_config.get("stop_loss_pct", 0)
    if target > 0 and stop > 0 and stop >= target:
        errors.append(
            f"stop_loss_pct ({stop}) >= target_gain_pct ({target}) in "
            f"ASSETS['{asset_key}'] — every trade structurally loses."
        )

    if errors:
        print("=" * 60)
        print("  CONFIG VALIDATION FAILED")
        print("=" * 60)
        for e in errors:
            print(f"  ERROR: {e}")
        print()
        raise SystemExit(1)


def main():
    print("\n🔺 MONAD QUANT FUND — STRATEGY ENGINE 🔺\n")

    mode = config.ACTIVE_MODE
    if mode not in MODE_MAP:
        print(f"ERROR: ACTIVE_MODE='{mode}' not in MODE_MAP.")
        print(f"Available modes: {', '.join(sorted(MODE_MAP.keys()))}")
        return
    yf_symbol, interval, asset_key = MODE_MAP[mode]
    asset_config = config.ASSETS[asset_key]
    _validate_config(mode, asset_key, asset_config)

    # Pull asset-specific params with fallback to global defaults
    target_gain = asset_config.get("target_gain_pct", config.TARGET_GAIN_PCT)
    stop_loss   = asset_config.get("stop_loss_pct",   config.STOP_LOSS_PCT)
    req_signals = asset_config.get("require_signals", config.REQUIRE_SIGNALS)

    # Hourly trade filter — match live scheduler behavior.
    # The live trader's APScheduler only fires Mon-Fri 9:32-15:32 ET (trader.py:584),
    # and live/signals.py double-guards with _is_market_hours(). Equity ETF backtests
    # must gate entries identically or they diverge from live (trading phantom after-hours
    # bars that yfinance sometimes includes but the live bot never sees).
    # BTC/crypto trades 24/7 on spot exchanges — no hour filter applies.
    if interval == "1h":
        is_crypto = yf_symbol.endswith("-USD")
        if is_crypto:
            trade_hours = None  # 24/7
        elif config.HOURLY_TRADE_FILTER:
            # Explicit config override (e.g., a stricter intraday window)
            trade_hours = (config.HOURLY_TRADE_HOURS_START, config.HOURLY_TRADE_HOURS_END)
        else:
            # Default for equities: US regular trading hours (9:30–16:00 ET → bars 9-15)
            # Matches live scheduler: CronTrigger(hour="9-15", timezone="America/New_York")
            trade_hours = (9, 16)
    else:
        trade_hours = None

    # Hourly modes use separate date range config
    if interval == "1h":
        bt_start = getattr(config, "BACKTEST_START_HOURLY", config.BACKTEST_START)
        bt_end   = getattr(config, "BACKTEST_END_HOURLY",   config.BACKTEST_END)

        # Auto-clamp: yfinance only serves ~730 days of hourly data.
        earliest_allowed = (datetime.now() - timedelta(days=_YFINANCE_HOURLY_MAX_DAYS)).strftime("%Y-%m-%d")
        if bt_start < earliest_allowed:
            print(f"  WARNING: BACKTEST_START '{bt_start}' exceeds yfinance 730-day hourly limit.")
            print(f"           Clamping to '{earliest_allowed}'.")
            bt_start = earliest_allowed
    else:
        bt_start = config.BACKTEST_START
        bt_end   = config.BACKTEST_END

    df = fetch_yfinance(symbol=yf_symbol, start=bt_start, end=bt_end, interval=interval)
    df = df.loc[bt_start:bt_end]
    print(f"Loaded {len(df)} bars for {config.ACTIVE_MODE} ({bt_start} → {bt_end})\n")

    timeframe = "hourly" if interval == "1h" else "daily"

    results = run_backtest(
        df=df,
        initial_capital=config.INITIAL_CAPITAL,
        target_gain_pct=target_gain,
        stop_loss_pct=stop_loss,
        require_signals=req_signals,
        kelly_multiplier=config.KELLY_MULTIPLIER,
        bull_kelly_multiplier=getattr(config, "BULL_KELLY_MULTIPLIER", 0.75),
        trade_hours=trade_hours,
        timeframe=timeframe,
        plot=config.PLOT_RESULTS,
        backtest_mode=getattr(config, "BACKTEST_MODE", "realistic"),
        debug=getattr(config, "BACKTEST_DEBUG", False),
    )


if __name__ == "__main__":
    main()

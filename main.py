"""
MONAD Quant - Main Entry Point
Run: python main.py
"""

import config
from src.data.fetcher import fetch_yfinance
from src.backtest.runner import run_backtest

# Map ACTIVE_MODE to (yfinance symbol, interval, asset config key)
MODE_MAP = {
    "BTC_HOURLY": ("BTC-USD", "1h",  "BTC"),
    "BTC_DAILY":  ("BTC-USD", "1d",  "BTC"),
    "QQQ_DAILY":  ("QQQ",     "1d",  "QQQ"),
    "SOXL_DAILY": ("SOXL",    "1d",  "SOXL"),
}

def main():
    print("\n🔺 MONAD QUANT FUND — STRATEGY ENGINE 🔺\n")

    yf_symbol, interval, asset_key = MODE_MAP[config.ACTIVE_MODE]
    asset_config = config.ASSETS[asset_key]

    # Pull asset-specific params with fallback to global defaults
    target_gain = asset_config.get("target_gain_pct", config.TARGET_GAIN_PCT)
    stop_loss   = asset_config.get("stop_loss_pct",   config.STOP_LOSS_PCT)
    req_signals = asset_config.get("require_signals", config.REQUIRE_SIGNALS)

    # Hourly trade filter — only applied when interval is hourly
    if interval == "1h" and config.HOURLY_TRADE_FILTER:
        trade_hours = (config.HOURLY_TRADE_HOURS_START, config.HOURLY_TRADE_HOURS_END)
    else:
        trade_hours = None

    df = fetch_yfinance(symbol=yf_symbol, start=config.BACKTEST_START,
                        end=config.BACKTEST_END, interval=interval)
    df = df.loc[config.BACKTEST_START:config.BACKTEST_END]
    print(f"Loaded {len(df)} bars for {config.ACTIVE_MODE} "
          f"({config.BACKTEST_START} → {config.BACKTEST_END})\n")

    results = run_backtest(
        df=df,
        initial_capital=config.INITIAL_CAPITAL,
        target_gain_pct=target_gain,
        stop_loss_pct=stop_loss,
        require_signals=req_signals,
        kelly_multiplier=config.KELLY_MULTIPLIER,
        bull_kelly_multiplier=config.BULL_KELLY_MULTIPLIER,
        trade_hours=trade_hours,
        plot=config.PLOT_RESULTS,
    )

    return results


if __name__ == "__main__":
    main()

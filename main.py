"""
MONAD Quant - Main Entry Point
Run: python main.py
"""

import config
from src.data.fetcher import fetch_crypto_daily, fetch_daily, fetch_yfinance, fetch_btc_hourly
from src.backtest.runner import run_backtest

def main():
    print("\n🔺 MONAD QUANT FUND — STRATEGY ENGINE 🔺\n")

    asset = config.DEFAULT_ASSET
    asset_config = config.ASSETS[asset]

    # Pull asset-specific params with fallback to global defaults
    target_gain  = asset_config.get("target_gain_pct", config.TARGET_GAIN_PCT)
    stop_loss    = asset_config.get("stop_loss_pct", config.STOP_LOSS_PCT)
    req_signals  = asset_config.get("require_signals", config.REQUIRE_SIGNALS)

    # Fetch data based on asset type
    asset_type = asset_config["type"]
    if asset_type == "crypto_hourly":
        df = fetch_btc_hourly(start=config.BACKTEST_START_HOURLY, end=config.BACKTEST_END_HOURLY)
        start, end, timeframe = config.BACKTEST_START_HOURLY, config.BACKTEST_END_HOURLY, "hourly"
    elif asset_type == "crypto":
        df = fetch_crypto_daily(symbol=asset, market=asset_config.get("market", "USD"))
        start, end, timeframe = config.BACKTEST_START, config.BACKTEST_END, "daily"
    else:
        df = fetch_yfinance(symbol=asset, start=config.BACKTEST_START, end=config.BACKTEST_END)
        start, end, timeframe = config.BACKTEST_START, config.BACKTEST_END, "daily"

    # Filter to backtest window
    df = df.loc[start:end]
    print(f"Loaded {len(df)} bars for {asset} ({start} → {end}) [{timeframe}]\n")

    # Run backtest
    results = run_backtest(
        df=df,
        initial_capital=config.INITIAL_CAPITAL,
        target_gain_pct=target_gain,
        stop_loss_pct=stop_loss,
        require_signals=req_signals,
        kelly_multiplier=config.KELLY_MULTIPLIER,
        timeframe=timeframe,
        plot=config.PLOT_RESULTS,
    )

    return results


if __name__ == "__main__":
    main()

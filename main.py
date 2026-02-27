"""
MONAD Quant - Main Entry Point
Run: python main.py
"""

import config
from src.data.fetcher import fetch_crypto_daily, fetch_daily, fetch_yfinance
from src.backtest.runner import run_backtest

def main():
    print("\n🔺 MONAD QUANT FUND — STRATEGY ENGINE 🔺\n")

    asset = config.DEFAULT_ASSET
    asset_config = config.ASSETS[asset]

    # Pull asset-specific params with fallback to global defaults
    target_gain  = asset_config.get("target_gain_pct", config.TARGET_GAIN_PCT)
    stop_loss    = asset_config.get("stop_loss_pct", config.STOP_LOSS_PCT)
    req_signals  = asset_config.get("require_signals", config.REQUIRE_SIGNALS)

    # Fetch data
    if asset_config["type"] == "crypto":
        df = fetch_crypto_daily(symbol=asset, market=asset_config.get("market", "USD"))
    else:
        df = fetch_yfinance(symbol=asset, start=config.BACKTEST_START, end=config.BACKTEST_END)
   
   
    # Filter to backtest window
    df = df.loc[config.BACKTEST_START:config.BACKTEST_END]
    print(f"Loaded {len(df)} bars for {asset} "
          f"({config.BACKTEST_START} → {config.BACKTEST_END})\n")

    # Run backtest
    results = run_backtest(
        df=df,
        initial_capital=config.INITIAL_CAPITAL,
        target_gain_pct=target_gain,
        stop_loss_pct=stop_loss,
        require_signals=req_signals,
        kelly_multiplier=config.KELLY_MULTIPLIER,
        plot=config.PLOT_RESULTS,
    )

    return results


if __name__ == "__main__":
    main()

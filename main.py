"""
MONAD Quant - Main Entry Point
Run: python main.py
"""

import config
from src.data.fetcher import fetch_yfinance
from src.backtest.runner import run_backtest

CRYPTO_YFINANCE_SUFFIX = "USD=X"  # yfinance uses BTC-USD for crypto

def main():
    print("\n🔺 MONAD QUANT FUND — STRATEGY ENGINE 🔺\n")

    asset = config.DEFAULT_ASSET
    asset_config = config.ASSETS[asset]

    # Pull asset-specific params with fallback to global defaults
    target_gain  = asset_config.get("target_gain_pct", config.TARGET_GAIN_PCT)
    stop_loss    = asset_config.get("stop_loss_pct", config.STOP_LOSS_PCT)
    req_signals  = asset_config.get("require_signals", config.REQUIRE_SIGNALS)

    # Fetch data — crypto uses yfinance with BTC-USD ticker at hourly resolution
    if asset_config["type"] == "crypto":
        market = asset_config.get("market", "USD")
        yf_symbol = f"{asset}-{market}"
        df = fetch_yfinance(symbol=yf_symbol, start=config.BACKTEST_START,
                            end=config.BACKTEST_END, interval="1h")
    else:
        df = fetch_yfinance(symbol=asset, start=config.BACKTEST_START,
                            end=config.BACKTEST_END)

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
        bull_kelly_multiplier=config.BULL_KELLY_MULTIPLIER,
        trade_hours=(config.TRADE_HOURS_START, config.TRADE_HOURS_END),
        plot=config.PLOT_RESULTS,
    )

    return results




"""
MONAD Quant - Main Entry Point

Run modes:
  python main.py                      — standard backtest (default)
  python main.py --mode=walk-forward  — walk-forward parameter optimization (OOS)
"""

import argparse
import config
from src.data.fetcher import (
    fetch_crypto_daily, fetch_daily, fetch_yfinance,
    fetch_btc_hourly, fetch_qqq_hourly, fetch_btc_hourly_binance,
)
from src.backtest.runner import run_backtest


def _load_data():
    """Load and slice the configured asset's OHLCV data."""
    asset = config.DEFAULT_ASSET
    asset_config = config.ASSETS[asset]
    asset_type = asset_config["type"]

    if asset_type == "crypto_hourly_binance":
        start = getattr(config, "BACKTEST_START_HOURLY_AGG", config.BACKTEST_START_HOURLY)
        end   = getattr(config, "BACKTEST_END_HOURLY_AGG",   config.BACKTEST_END_HOURLY)
        df = fetch_btc_hourly_binance(start=start, end=end)
        timeframe = "hourly"
    elif asset_type == "crypto_hourly":
        df = fetch_btc_hourly(start=config.BACKTEST_START_HOURLY, end=config.BACKTEST_END_HOURLY)
        start, end, timeframe = config.BACKTEST_START_HOURLY, config.BACKTEST_END_HOURLY, "hourly"
    elif asset_type == "etf_hourly":
        df = fetch_qqq_hourly(start=config.BACKTEST_START_QQQ_HOURLY, end=config.BACKTEST_END_QQQ_HOURLY)
        start, end, timeframe = config.BACKTEST_START_QQQ_HOURLY, config.BACKTEST_END_QQQ_HOURLY, "hourly"
    elif asset_type == "crypto":
        df = fetch_crypto_daily(symbol=asset, market=asset_config.get("market", "USD"))
        start, end, timeframe = config.BACKTEST_START, config.BACKTEST_END, "daily"
    else:
        df = fetch_yfinance(symbol=asset, start=config.BACKTEST_START, end=config.BACKTEST_END)
        start, end, timeframe = config.BACKTEST_START, config.BACKTEST_END, "daily"

    df = df.loc[start:end]
    print(f"Loaded {len(df)} bars for {asset} ({start} → {end}) [{timeframe}]\n")
    return df, asset, asset_config, timeframe


def main():
    parser = argparse.ArgumentParser(description="MONAD Quant Strategy Engine")
    parser.add_argument(
        "--mode",
        default="normal",
        choices=["normal", "walk-forward"],
        help="normal = standard backtest; walk-forward = rolling OOS optimizer",
    )
    parser.add_argument("--start", default=None, help="Override backtest start date (YYYY-MM-DD)")
    parser.add_argument("--end",   default=None, help="Override backtest end date (YYYY-MM-DD)")
    args = parser.parse_args()

    if args.start:
        config.BACKTEST_START = args.start
    if args.end:
        config.BACKTEST_END = args.end

    print("\n🔺 MONAD QUANT FUND — STRATEGY ENGINE 🔺\n")
    df, asset, asset_config, timeframe = _load_data()

    if args.mode == "walk-forward":
        if timeframe != "daily":
            print("Walk-forward optimization is only supported for daily assets.")
            return {}
        from src.optimization.walk_forward import walk_forward_optimize
        return walk_forward_optimize(df)

    # ── Standard backtest ────────────────────────────────────────────────────
    target_gain = asset_config.get("target_gain_pct", config.TARGET_GAIN_PCT)
    stop_loss   = asset_config.get("stop_loss_pct",   config.STOP_LOSS_PCT)
    req_signals = asset_config.get("require_signals",  config.REQUIRE_SIGNALS)

    return run_backtest(
        df=df,
        initial_capital=config.INITIAL_CAPITAL,
        target_gain_pct=target_gain,
        stop_loss_pct=stop_loss,
        require_signals=req_signals,
        kelly_multiplier=config.KELLY_MULTIPLIER,
        timeframe=timeframe,
        plot=config.PLOT_RESULTS,
    )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
GDXU Hourly parameter sweep — target/stop, VWAP, RSI.
Run locally where yfinance can reach the internet.

Usage:
    python sweep_gdxu.py                # Run all sweeps
    python sweep_gdxu.py --sweep ts     # Target/stop only
    python sweep_gdxu.py --sweep vwap   # VWAP only
    python sweep_gdxu.py --sweep rsi    # RSI only
"""
import sys, os, io, argparse, contextlib
sys.path.insert(0, os.path.dirname(__file__))

import config
# Force GDXU mode
config.ACTIVE_MODE = "GDXU_HOURLY"
config.DEFAULT_ASSET = "GDXU_HOURLY"
config.PLOT_RESULTS = False  # no charts during sweep

from src.data.fetcher import fetch_gdxu_hourly
from src.backtest.runner import run_backtest

import warnings
warnings.filterwarnings("ignore")

# ── Parse args ──────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--sweep", choices=["ts", "vwap", "rsi", "all"], default="all")
args = parser.parse_args()

# ── Load data once ──────────────────────────────────────────────────────────
print("Loading GDXU data...")
df_raw = fetch_gdxu_hourly(config.BACKTEST_START_GDXU_HOURLY, config.BACKTEST_END_GDXU_HOURLY)
print(f"Loaded {len(df_raw)} bars\n")


def run_quiet(target, stop, rsi_os=None, vwap=None):
    """Run a single backtest quietly, return result dict or error string."""
    # Override config-level params that engine reads directly
    if rsi_os is not None:
        config.RSI_OVERSOLD_GDXU_HOURLY = rsi_os
        config.ASSETS["GDXU_HOURLY"]["rsi_oversold"] = rsi_os
    if vwap is not None:
        config.VWAP_ZSCORE_THRESH_GDXU_HOURLY = vwap
        config.ASSETS["GDXU_HOURLY"]["vwap_zscore_thresh"] = vwap

    try:
        # Suppress all stdout from runner
        with contextlib.redirect_stdout(io.StringIO()):
            result = run_backtest(
                df=df_raw.copy(),
                initial_capital=config.INITIAL_CAPITAL,
                target_gain_pct=target,
                stop_loss_pct=stop,
                require_signals=1,
                kelly_multiplier=config.KELLY_MULTIPLIER,
                timeframe="hourly",
                plot=False,
            )
        if not result:
            return None
        return result
    except Exception as e:
        return str(e)


def fmt(result, label):
    if result is None:
        return f"  {label} | NO TRADES"
    if isinstance(result, str):
        return f"  {label} | ERROR: {result}"
    r = result
    trades = r["total_trades"]
    wr = r["win_rate"] * 100
    ret = r["total_return"] * 100
    sharpe = r["sharpe_ratio"]
    dd = r["max_drawdown"] * 100
    avg_mo = r["monthly_returns"]
    avg_mo_pct = avg_mo[avg_mo != 0].mean() * 100 if len(avg_mo[avg_mo != 0]) > 0 else 0
    return (f"  {label} | trades={trades:4d} WR={wr:5.1f}% "
            f"ret={ret:7.2f}% Sharpe={sharpe:6.1f} "
            f"DD={dd:6.2f}% avg/mo={avg_mo_pct:+.2f}%")


# Save original config values for restoration
ORIG_RSI = config.RSI_OVERSOLD_GDXU_HOURLY
ORIG_VWAP = config.VWAP_ZSCORE_THRESH_GDXU_HOURLY

def restore_config():
    config.RSI_OVERSOLD_GDXU_HOURLY = ORIG_RSI
    config.VWAP_ZSCORE_THRESH_GDXU_HOURLY = ORIG_VWAP
    config.ASSETS["GDXU_HOURLY"]["rsi_oversold"] = ORIG_RSI
    config.ASSETS["GDXU_HOURLY"]["vwap_zscore_thresh"] = ORIG_VWAP


# ════════════════════════════════════════════════════════════════════════════
# SWEEP 1: Target/Stop grid (2:1 R:R maintained)
# ════════════════════════════════════════════════════════════════════════════
if args.sweep in ("ts", "all"):
    restore_config()
    print("=" * 95)
    print("SWEEP 1a: Target/Stop (2:1 R:R)")
    print("=" * 95)

    for t_pct in [0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.4, 1.6, 2.0]:
        t = t_pct / 100
        s = t / 2
        r = run_quiet(target=t, stop=s)
        print(fmt(r, f"target={t_pct:4.1f}% stop={t_pct/2:5.2f}%"))

    print()
    print("=" * 95)
    print("SWEEP 1b: R:R ratio variations at target=1.0%")
    print("=" * 95)

    for s_pct in [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.70]:
        r = run_quiet(target=0.010, stop=s_pct / 100)
        rr = 1.0 / s_pct
        print(fmt(r, f"R:R={rr:4.1f}:1 stop={s_pct:.2f}%"))


# ════════════════════════════════════════════════════════════════════════════
# SWEEP 2: VWAP z-score threshold
# ════════════════════════════════════════════════════════════════════════════
if args.sweep in ("vwap", "all"):
    restore_config()
    print()
    print("=" * 95)
    print("SWEEP 2: VWAP z-score threshold (target/stop at baseline 1.0%/0.5%)")
    print("=" * 95)

    for v in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0, 1.2]:
        r = run_quiet(target=0.010, stop=0.005, vwap=v)
        print(fmt(r, f"VWAP={v:.1f}"))


# ════════════════════════════════════════════════════════════════════════════
# SWEEP 3: RSI oversold threshold
# ════════════════════════════════════════════════════════════════════════════
if args.sweep in ("rsi", "all"):
    restore_config()
    print()
    print("=" * 95)
    print("SWEEP 3: RSI oversold threshold (target/stop at baseline 1.0%/0.5%)")
    print("=" * 95)

    for rsi in [42, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100]:
        r = run_quiet(target=0.010, stop=0.005, rsi_os=rsi)
        print(fmt(r, f"RSI={rsi:3d}"))


restore_config()
print("\n✓ Sweep complete.")

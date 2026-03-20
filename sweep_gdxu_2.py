#!/usr/bin/env python3
"""GDXU Hourly sweep round 2 — cross-validate best R:R with RSI=85, and fine-tune."""
import sys, os, io, contextlib
sys.path.insert(0, os.path.dirname(__file__))

import config
config.ACTIVE_MODE = "GDXU_HOURLY"
config.DEFAULT_ASSET = "GDXU_HOURLY"
config.PLOT_RESULTS = False

from src.data.fetcher import fetch_gdxu_hourly
from src.backtest.runner import run_backtest
import warnings
warnings.filterwarnings("ignore")

print("Loading GDXU data...")
df_raw = fetch_gdxu_hourly(config.BACKTEST_START_GDXU_HOURLY, config.BACKTEST_END_GDXU_HOURLY)
print(f"Loaded {len(df_raw)} bars\n")

ORIG_RSI = config.RSI_OVERSOLD_GDXU_HOURLY
ORIG_VWAP = config.VWAP_ZSCORE_THRESH_GDXU_HOURLY

def restore():
    config.RSI_OVERSOLD_GDXU_HOURLY = ORIG_RSI
    config.VWAP_ZSCORE_THRESH_GDXU_HOURLY = ORIG_VWAP
    config.ASSETS["GDXU_HOURLY"]["rsi_oversold"] = ORIG_RSI
    config.ASSETS["GDXU_HOURLY"]["vwap_zscore_thresh"] = ORIG_VWAP

def run_quiet(target, stop, rsi_os=None, vwap=None):
    if rsi_os is not None:
        config.RSI_OVERSOLD_GDXU_HOURLY = rsi_os
        config.ASSETS["GDXU_HOURLY"]["rsi_oversold"] = rsi_os
    if vwap is not None:
        config.VWAP_ZSCORE_THRESH_GDXU_HOURLY = vwap
        config.ASSETS["GDXU_HOURLY"]["vwap_zscore_thresh"] = vwap
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            result = run_backtest(
                df=df_raw.copy(), initial_capital=config.INITIAL_CAPITAL,
                target_gain_pct=target, stop_loss_pct=stop,
                require_signals=1, kelly_multiplier=config.KELLY_MULTIPLIER,
                timeframe="hourly", plot=False,
            )
        return result if result else None
    except Exception as e:
        return str(e)

def fmt(result, label):
    if result is None: return f"  {label} | NO TRADES"
    if isinstance(result, str): return f"  {label} | ERROR: {result}"
    r = result
    avg_mo = r["monthly_returns"]
    avg_mo_pct = avg_mo[avg_mo != 0].mean() * 100 if len(avg_mo[avg_mo != 0]) > 0 else 0
    return (f"  {label} | trades={r['total_trades']:4d} WR={r['win_rate']*100:5.1f}% "
            f"ret={r['total_return']*100:7.2f}% Sharpe={r['sharpe_ratio']:6.1f} "
            f"DD={r['max_drawdown']*100:6.2f}% avg/mo={avg_mo_pct:+.2f}%")

# ════════════════════════════════════════════════════════════════════════════
# CROSS 1: Best R:R ratios × RSI=85
# ════════════════════════════════════════════════════════════════════════════
print("=" * 95)
print("CROSS 1: R:R variations × RSI=85 (was 80)")
print("=" * 95)

for s_pct in [0.25, 0.30, 0.35, 0.40, 0.50]:
    restore()
    r = run_quiet(target=0.010, stop=s_pct/100, rsi_os=85)
    rr = 1.0 / s_pct
    print(fmt(r, f"RSI=85 R:R={rr:4.1f}:1 stop={s_pct:.2f}%"))

# ════════════════════════════════════════════════════════════════════════════
# CROSS 2: Fine-tune target around 1.0% at stop=0.30%
# ════════════════════════════════════════════════════════════════════════════
print()
print("=" * 95)
print("CROSS 2: Target fine-tune at stop=0.30%, RSI=85")
print("=" * 95)

for t_pct in [0.7, 0.8, 0.9, 1.0, 1.1, 1.2]:
    restore()
    r = run_quiet(target=t_pct/100, stop=0.003, rsi_os=85)
    print(fmt(r, f"target={t_pct:.1f}% stop=0.30% RSI=85"))

# ════════════════════════════════════════════════════════════════════════════
# CROSS 3: Fine-tune stop around 0.30% at target=1.0%, RSI=85
# ════════════════════════════════════════════════════════════════════════════
print()
print("=" * 95)
print("CROSS 3: Stop fine-tune at target=1.0%, RSI=85")
print("=" * 95)

for s_pct in [0.20, 0.25, 0.28, 0.30, 0.32, 0.35]:
    restore()
    r = run_quiet(target=0.010, stop=s_pct/100, rsi_os=85)
    rr = 1.0 / s_pct
    print(fmt(r, f"stop={s_pct:.2f}% (R:R={rr:.1f}:1)"))

# ════════════════════════════════════════════════════════════════════════════
# CROSS 4: RSI fine-tune 75-90 at best target/stop
# ════════════════════════════════════════════════════════════════════════════
print()
print("=" * 95)
print("CROSS 4: RSI fine-tune 75-90 at target=1.0%, stop=0.30%")
print("=" * 95)

for rsi in [75, 78, 80, 82, 85, 87, 90]:
    restore()
    r = run_quiet(target=0.010, stop=0.003, rsi_os=rsi)
    print(fmt(r, f"RSI={rsi:3d}"))

restore()
print("\n✓ Cross-sweep complete.")

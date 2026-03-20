#!/usr/bin/env python3
"""
MONAD Quant — Universal Parameter Sweep Tool

Finds optimal signal and risk params for any equity/ETF on hourly bars.
Fetches data via yfinance, runs a multi-phase sweep, and reports the best config.

Usage:
    python sweep.py GDXU                    # Full sweep with defaults (2yr lookback)
    python sweep.py SOXL --start 2024-06-01 # Custom start date
    python sweep.py TQQQ --phase 1          # Run only phase 1 (target/stop)
    python sweep.py NVDA --phase 2          # Run only phase 2 (cross-validation)

Phases:
    1 = Coarse sweep (target/stop, VWAP, RSI)
    2 = Cross-validation (fine-tune best params from phase 1)
    all = Both phases (default)
"""
import sys, os, io, argparse, contextlib, json
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))

import config
import warnings
warnings.filterwarnings("ignore")


# ═══════════════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════════════
parser = argparse.ArgumentParser(
    description="MONAD Quant — Universal Parameter Sweep",
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog="Example: python sweep.py GDXU\n         python sweep.py SOXL --start 2024-06-01",
)
parser.add_argument("ticker", help="Ticker symbol (e.g., GDXU, SOXL, TQQQ, NVDA)")
parser.add_argument("--start", default=None, help="Backtest start date (default: 2yr ago)")
parser.add_argument("--end", default=None, help="Backtest end date (default: today)")
parser.add_argument("--phase", default="all", choices=["1", "2", "all"],
                    help="Which sweep phase to run (default: all)")
args = parser.parse_args()

TICKER = args.ticker.upper()
END_DATE = args.end or datetime.now().strftime("%Y-%m-%d")
# yfinance hourly data limit is 730 days. Use 710 to stay safely inside the window.
START_DATE = args.start or (datetime.now() - timedelta(days=710)).strftime("%Y-%m-%d")


# ═══════════════════════════════════════════════════════════════════════════
#  SETUP — inject temporary config for this ticker
# ═══════════════════════════════════════════════════════════════════════════
MODE_NAME = f"{TICKER}_HOURLY"

# Set config attributes the engine reads via getattr(config, ...)
# Start with sensible defaults — the sweep will override these per-run
_defaults = {
    f"RSI_PERIOD_{MODE_NAME}":          7,
    f"RSI_OVERSOLD_{MODE_NAME}":        80,   # start high (hourly ETFs need loose RSI)
    f"RSI_OVERBOUGHT_{MODE_NAME}":      62,
    f"MACD_FAST_{MODE_NAME}":           6,
    f"MACD_SLOW_{MODE_NAME}":           13,
    f"MACD_SIGNAL_{MODE_NAME}":         4,
    f"VWAP_WINDOW_{MODE_NAME}":         10,
    f"VWAP_ZSCORE_THRESH_{MODE_NAME}":  0.3,
    f"BB_WINDOW_{MODE_NAME}":           14,
}
for k, v in _defaults.items():
    setattr(config, k, v)

# Default target/stop — will be overridden per sweep run
DEFAULT_TARGET = 0.010  # 1.0%
DEFAULT_STOP   = 0.005  # 0.5%

# Register in ASSETS dict so the engine can route it
config.ASSETS[MODE_NAME] = {
    "type":               f"etf_hourly_{TICKER.lower()}",
    "target_gain_pct":    DEFAULT_TARGET,
    "stop_loss_pct":      DEFAULT_STOP,
    "require_signals":    1,
    "rsi_oversold":       _defaults[f"RSI_OVERSOLD_{MODE_NAME}"],
    "rsi_overbought":     _defaults[f"RSI_OVERBOUGHT_{MODE_NAME}"],
    "vwap_zscore_thresh": _defaults[f"VWAP_ZSCORE_THRESH_{MODE_NAME}"],
}

config.ACTIVE_MODE = MODE_NAME
config.DEFAULT_ASSET = MODE_NAME
config.PLOT_RESULTS = False
config.VERBOSE_SIGNALS = False

# Register the mode→asset mapping
config._MODE_TO_ASSET[MODE_NAME] = MODE_NAME

# ═══════════════════════════════════════════════════════════════════════════
#  PATCH engine to handle unknown hourly modes generically
# ═══════════════════════════════════════════════════════════════════════════
import src.strategy.engine as engine

_original_build_features = engine.build_features

def _patched_build_features(df, timeframe="daily", signal_overrides=None):
    """Intercept build_features for unknown hourly modes — use generic config."""
    import config as cfg
    active = getattr(cfg, "ACTIVE_MODE", "")
    # If engine already handles this mode, use original
    if active in ("QQQ_HOURLY", "TQQQ_HOURLY", "GDXU_HOURLY", "BTC_HOURLY"):
        return _original_build_features(df, timeframe, signal_overrides)
    if timeframe != "hourly":
        return _original_build_features(df, timeframe, signal_overrides)

    # Generic hourly mode — read params from config using MODE_NAME pattern
    from src.signals.momentum import add_momentum_features
    from src.signals.volume import add_volume_features
    from src.signals.volatility import add_volatility_features

    mode = active
    df = add_momentum_features(
        df,
        rsi_period=getattr(cfg, f"RSI_PERIOD_{mode}", 7),
        macd_fast=getattr(cfg, f"MACD_FAST_{mode}", 6),
        macd_slow=getattr(cfg, f"MACD_SLOW_{mode}", 13),
        macd_signal_period=getattr(cfg, f"MACD_SIGNAL_{mode}", 4),
        rsi_oversold=getattr(cfg, f"RSI_OVERSOLD_{mode}", 80),
        rsi_overbought=getattr(cfg, f"RSI_OVERBOUGHT_{mode}", 62),
    )
    df = add_volume_features(
        df,
        window=getattr(cfg, f"VWAP_WINDOW_{mode}", 10),
        zscore_threshold=getattr(cfg, f"VWAP_ZSCORE_THRESH_{mode}", 0.3),
    )
    df = add_volatility_features(
        df, window=getattr(cfg, f"BB_WINDOW_{mode}", 14),
    )
    return df

engine.build_features = _patched_build_features


# ═══════════════════════════════════════════════════════════════════════════
#  DATA LOADING
# ═══════════════════════════════════════════════════════════════════════════
from src.data.fetcher import _ensure_cache_dir, _cache_path, _cache_is_fresh, _fetch_hourly
from src.backtest.runner import run_backtest
import pandas as pd

def fetch_ticker_hourly(ticker, start, end):
    """Fetch hourly data for any ticker, with caching."""
    _ensure_cache_dir()
    cache_file = _cache_path(ticker, "1h")
    start_dt, end_dt = pd.Timestamp(start), pd.Timestamp(end)

    if os.path.exists(cache_file) and _cache_is_fresh(cache_file):
        df = pd.read_csv(cache_file, index_col=0, parse_dates=True)
        if len(df) > 0 and df.index[0] <= start_dt and df.index[-1] >= end_dt - timedelta(days=2):
            print(f"[cache] Loading {ticker} hourly from cache ({len(df)} bars)")
            return df.loc[start:end]

    print(f"[yfinance] Fetching {ticker} hourly from {start} to {end}...")
    df = _fetch_hourly(ticker, start, end)
    df = df.between_time("09:30", "16:00")
    df.to_csv(cache_file)
    print(f"[cache] Saved {ticker} hourly to {cache_file} ({len(df)} bars)")
    return df.loc[start:end]


print(f"\n{'='*70}")
print(f"  MONAD QUANT — UNIVERSAL SWEEP: {TICKER}")
print(f"  Period: {START_DATE} → {END_DATE}")
print(f"{'='*70}\n")

df_raw = fetch_ticker_hourly(TICKER, START_DATE, END_DATE)
print(f"Loaded {len(df_raw)} bars\n")

if len(df_raw) < 100:
    print(f"ERROR: Only {len(df_raw)} bars loaded. Need at least 100 for meaningful backtest.")
    print("Try a wider date range or check if the ticker is valid.")
    sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════════
#  SWEEP ENGINE
# ═══════════════════════════════════════════════════════════════════════════
def run_quiet(target, stop, rsi_os=None, vwap=None):
    """Run a single backtest quietly. Returns result dict or None."""
    if rsi_os is not None:
        setattr(config, f"RSI_OVERSOLD_{MODE_NAME}", rsi_os)
        config.ASSETS[MODE_NAME]["rsi_oversold"] = rsi_os
    if vwap is not None:
        setattr(config, f"VWAP_ZSCORE_THRESH_{MODE_NAME}", vwap)
        config.ASSETS[MODE_NAME]["vwap_zscore_thresh"] = vwap

    try:
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
        return result if result else None
    except Exception as e:
        return {"error": str(e)}


def fmt(r, label):
    if r is None:
        return f"  {label} | NO TRADES"
    if "error" in r:
        return f"  {label} | ERROR: {r['error']}"
    trades = r["total_trades"]
    wr = r["win_rate"] * 100
    ret = r["total_return"] * 100
    sharpe = r["sharpe_ratio"]
    dd = r["max_drawdown"] * 100
    mo = r["monthly_returns"]
    avg_mo = mo[mo != 0].mean() * 100 if len(mo[mo != 0]) > 0 else 0
    return (f"  {label} | trades={trades:4d} WR={wr:5.1f}% "
            f"ret={ret:7.2f}% Sharpe={sharpe:6.1f} "
            f"DD={dd:6.2f}% avg/mo={avg_mo:+.2f}%")


def score(r):
    """Composite score: prioritize Sharpe, then return, penalize DD."""
    if r is None or "error" in r:
        return -9999
    return r["sharpe_ratio"] * 0.5 + r["total_return"] * 100 * 0.3 + r["max_drawdown"] * 100 * 0.2


def restore():
    setattr(config, f"RSI_OVERSOLD_{MODE_NAME}", _defaults[f"RSI_OVERSOLD_{MODE_NAME}"])
    setattr(config, f"VWAP_ZSCORE_THRESH_{MODE_NAME}", _defaults[f"VWAP_ZSCORE_THRESH_{MODE_NAME}"])
    config.ASSETS[MODE_NAME]["rsi_oversold"] = _defaults[f"RSI_OVERSOLD_{MODE_NAME}"]
    config.ASSETS[MODE_NAME]["vwap_zscore_thresh"] = _defaults[f"VWAP_ZSCORE_THRESH_{MODE_NAME}"]


# Track best params across sweeps
best = {"target": DEFAULT_TARGET, "stop": DEFAULT_STOP,
        "rsi": _defaults[f"RSI_OVERSOLD_{MODE_NAME}"],
        "vwap": _defaults[f"VWAP_ZSCORE_THRESH_{MODE_NAME}"],
        "score": -9999, "result": None}


def update_best(r, target, stop, rsi=None, vwap=None):
    s = score(r)
    if s > best["score"]:
        best["score"] = s
        best["result"] = r
        best["target"] = target
        best["stop"] = stop
        if rsi is not None:
            best["rsi"] = rsi
        if vwap is not None:
            best["vwap"] = vwap


# ═══════════════════════════════════════════════════════════════════════════
#  PHASE 1 — COARSE SWEEP
# ═══════════════════════════════════════════════════════════════════════════
if args.phase in ("1", "all"):
    # ── 1a: Target/Stop at 2:1 R:R ────────────────────────────────────────
    restore()
    print("=" * 95)
    print(f"PHASE 1a: Target/Stop sweep (2:1 R:R) — {TICKER}")
    print("=" * 95)

    for t_pct in [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.2, 1.4, 1.6, 2.0]:
        t = t_pct / 100
        s = t / 2
        r = run_quiet(target=t, stop=s)
        print(fmt(r, f"target={t_pct:4.1f}% stop={t_pct/2:5.2f}%"))
        if r and "error" not in r:
            update_best(r, t, s)

    # ── 1b: R:R ratio variations at best target ──────────────────────────
    best_target = best["target"]
    best_t_pct = best_target * 100
    print()
    print("=" * 95)
    print(f"PHASE 1b: R:R variations at target={best_t_pct:.1f}%")
    print("=" * 95)

    for s_pct in [0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50, 0.60]:
        s = s_pct / 100
        if s >= best_target:
            continue  # skip R:R < 1:1
        r = run_quiet(target=best_target, stop=s)
        rr = best_t_pct / s_pct
        print(fmt(r, f"R:R={rr:4.1f}:1 stop={s_pct:.2f}%"))
        if r and "error" not in r:
            update_best(r, best_target, s)

    # ── 1c: VWAP threshold ─────────────────────────────────────────────────
    restore()
    print()
    print("=" * 95)
    print(f"PHASE 1c: VWAP z-score threshold (at best target/stop so far)")
    print("=" * 95)

    for v in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0, 1.2]:
        r = run_quiet(target=best["target"], stop=best["stop"], vwap=v)
        print(fmt(r, f"VWAP={v:.1f}"))
        if r and "error" not in r:
            update_best(r, best["target"], best["stop"], vwap=v)

    # ── 1d: RSI oversold threshold ──────────────────────────────────────────
    restore()
    print()
    print("=" * 95)
    print(f"PHASE 1d: RSI oversold threshold (at best target/stop so far)")
    print("=" * 95)

    for rsi in [42, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100]:
        r = run_quiet(target=best["target"], stop=best["stop"], rsi_os=rsi)
        print(fmt(r, f"RSI={rsi:3d}"))
        if r and "error" not in r:
            update_best(r, best["target"], best["stop"], rsi=rsi)

    print(f"\n  Phase 1 best: target={best['target']*100:.2f}% stop={best['stop']*100:.2f}% "
          f"RSI={best['rsi']} VWAP={best['vwap']} → score={best['score']:.1f}")


# ═══════════════════════════════════════════════════════════════════════════
#  PHASE 2 — CROSS-VALIDATION (fine-tune around phase 1 best)
# ═══════════════════════════════════════════════════════════════════════════
if args.phase in ("2", "all"):
    bt = best["target"]
    bs = best["stop"]
    br = best["rsi"]
    bv = best["vwap"]

    # ── 2a: Fine-tune target at best stop + RSI ────────────────────────────
    print()
    print("=" * 95)
    print(f"PHASE 2a: Target fine-tune at stop={bs*100:.2f}%, RSI={br}")
    print("=" * 95)

    bt_pct = bt * 100
    for t_pct in sorted(set([bt_pct * 0.6, bt_pct * 0.7, bt_pct * 0.8, bt_pct * 0.9,
                              bt_pct, bt_pct * 1.1, bt_pct * 1.2, bt_pct * 1.4])):
        t_pct = round(t_pct, 2)
        if t_pct <= 0:
            continue
        r = run_quiet(target=t_pct / 100, stop=bs, rsi_os=br)
        print(fmt(r, f"target={t_pct:.2f}% stop={bs*100:.2f}% RSI={br}"))
        if r and "error" not in r:
            update_best(r, t_pct / 100, bs, rsi=br)

    # ── 2b: Fine-tune stop at best target + RSI ───────────────────────────
    bt = best["target"]  # may have updated
    print()
    print("=" * 95)
    print(f"PHASE 2b: Stop fine-tune at target={bt*100:.2f}%, RSI={br}")
    print("=" * 95)

    bs_pct = bs * 100
    for s_pct in sorted(set([bs_pct * 0.5, bs_pct * 0.7, bs_pct * 0.85,
                              bs_pct, bs_pct * 1.15, bs_pct * 1.3, bs_pct * 1.5])):
        s_pct = round(s_pct, 3)
        if s_pct <= 0 or s_pct / 100 >= bt:
            continue
        r = run_quiet(target=bt, stop=s_pct / 100, rsi_os=br)
        rr = bt * 100 / s_pct
        print(fmt(r, f"stop={s_pct:.3f}% (R:R={rr:.1f}:1)"))
        if r and "error" not in r:
            update_best(r, bt, s_pct / 100, rsi=br)

    # ── 2c: Fine-tune RSI around best ──────────────────────────────────────
    bt = best["target"]
    bs = best["stop"]
    print()
    print("=" * 95)
    print(f"PHASE 2c: RSI fine-tune around {br} at target={bt*100:.2f}% stop={bs*100:.2f}%")
    print("=" * 95)

    rsi_range = sorted(set([max(40, br - 10), max(40, br - 5), max(40, br - 3),
                             br, min(100, br + 3), min(100, br + 5), min(100, br + 10)]))
    for rsi in rsi_range:
        r = run_quiet(target=bt, stop=bs, rsi_os=rsi)
        print(fmt(r, f"RSI={rsi:3d}"))
        if r and "error" not in r:
            update_best(r, bt, bs, rsi=rsi)


# ═══════════════════════════════════════════════════════════════════════════
#  RESULTS SUMMARY
# ═══════════════════════════════════════════════════════════════════════════
restore()
print()
print("=" * 95)
print(f"  OPTIMAL PARAMETERS FOR {TICKER} HOURLY")
print("=" * 95)

r = best["result"]
if r and "error" not in r:
    mo = r["monthly_returns"]
    avg_mo = mo[mo != 0].mean() * 100 if len(mo[mo != 0]) > 0 else 0
    neg_months = (mo[mo != 0] < 0).sum()
    total_months = (mo != 0).sum()

    print(f"""
  TARGET_GAIN_PCT  = {best['target']:.4f}   ({best['target']*100:.2f}%)
  STOP_LOSS_PCT    = {best['stop']:.4f}   ({best['stop']*100:.2f}%)
  RSI_OVERSOLD     = {best['rsi']}
  VWAP_ZSCORE      = {best['vwap']}
  R:R Ratio        = {best['target']/best['stop']:.1f}:1

  ── Performance ──
  Total Return:    {r['total_return']*100:+.2f}%
  Annualized:      {((1+r['total_return'])**(365.25/((pd.Timestamp(END_DATE)-pd.Timestamp(START_DATE)).days))-1)*100:.2f}%
  Sharpe Ratio:    {r['sharpe_ratio']:.1f}
  Max Drawdown:    {r['max_drawdown']*100:.2f}%
  Avg Monthly:     {avg_mo:+.2f}%
  Trades:          {r['total_trades']}
  Win Rate:        {r['win_rate']*100:.1f}%
  Neg Months:      {neg_months}/{total_months}
""")

    # Save results to JSON for easy ingestion
    out = {
        "ticker": TICKER,
        "period": f"{START_DATE} → {END_DATE}",
        "bars": len(df_raw),
        "optimal": {
            "target_gain_pct": best["target"],
            "stop_loss_pct": best["stop"],
            "rsi_oversold": best["rsi"],
            "vwap_zscore_thresh": best["vwap"],
        },
        "performance": {
            "total_return_pct": round(r["total_return"] * 100, 2),
            "sharpe_ratio": r["sharpe_ratio"],
            "max_drawdown_pct": round(r["max_drawdown"] * 100, 2),
            "avg_monthly_pct": round(avg_mo, 2),
            "trades": r["total_trades"],
            "win_rate_pct": round(r["win_rate"] * 100, 1),
            "negative_months": int(neg_months),
            "total_months": int(total_months),
        },
    }
    outfile = f"sweep_results_{TICKER}.json"
    with open(outfile, "w") as f:
        json.dump(out, f, indent=2)
    print(f"  Results saved → {outfile}")
else:
    print("  No valid results found. The ticker may not have enough data or liquidity.")

print()

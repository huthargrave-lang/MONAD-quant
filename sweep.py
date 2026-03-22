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
    python sweep.py LABU --min-stop 0.15    # Force realistic stops (≥0.15%)

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
parser.add_argument("--min-stop", type=float, default=None,
                    help="Minimum stop loss %% (e.g., 0.15 = 0.15%%). Default: auto-calculated from price/spread. Use 0 to disable.")
parser.add_argument("--spread", type=float, default=None,
                    help="Assumed bid-ask spread in dollars (default: auto-estimated from price level)")
parser.add_argument("--broker", default=None, choices=["ibkr", "schwab", "fidelity", "retail"],
                    help="Broker preset for spread/fee estimates (default: conservative retail)")
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

# Engine's build_features() now handles any hourly mode generically via config suffix.
# No monkey-patching needed — sweep just sets config attributes and the engine reads them.


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
#  AUTO-CALCULATE SAFE STOP LOSS (live-trading guard)
# ═══════════════════════════════════════════════════════════════════════════
# Estimate bid-ask spread from price level, then set minimum stop = 5× spread.
# This prevents the optimizer from recommending stops inside the bid-ask noise.

median_price = df_raw["close"].median()

# Broker presets: spread estimates for liquid ETFs by broker
_BROKER_SPREADS = {
    "ibkr":     {"<15": 0.01, "<50": 0.01, "<150": 0.01, "else": 0.02},
    "schwab":   {"<15": 0.01, "<50": 0.02, "<150": 0.03, "else": 0.03},
    "fidelity": {"<15": 0.01, "<50": 0.02, "<150": 0.03, "else": 0.03},
    "retail":   {"<15": 0.02, "<50": 0.03, "<150": 0.04, "else": 0.05},
}

def _estimate_spread(price, broker=None):
    tiers = _BROKER_SPREADS.get(broker, _BROKER_SPREADS["retail"])
    if price < 15:
        return tiers["<15"]
    elif price < 50:
        return tiers["<50"]
    elif price < 150:
        return tiers["<150"]
    else:
        return tiers["else"]

if args.spread is not None:
    est_spread = args.spread
else:
    est_spread = _estimate_spread(median_price, args.broker)

# Safe stop = 5× spread as % of price (round-trip: entry slippage + exit slippage)
# Floor at 0.10% to prevent absurdly tight stops on high-priced tickers
auto_min_stop_pct = max(0.10, (5 * est_spread / median_price) * 100)

if args.min_stop is not None:
    if args.min_stop == 0:
        MIN_STOP_PCT = 0  # user explicitly disabled
        print(f"  ⚠ Safe stop DISABLED (--min-stop 0). Optimizer may recommend unrealistic stops.\n")
    else:
        MIN_STOP_PCT = args.min_stop
        print(f"  Min stop: {MIN_STOP_PCT:.2f}% (user override)\n")
else:
    MIN_STOP_PCT = round(auto_min_stop_pct, 2)
    broker_label = f" ({args.broker.upper()})" if args.broker else " (conservative)"
    print(f"  Median price:     ${median_price:.2f}")
    print(f"  Est. bid-ask:     ${est_spread:.3f}{broker_label}")
    print(f"  Safe stop (5x):   {MIN_STOP_PCT:.2f}%  (${median_price * MIN_STOP_PCT / 100:.3f}/share)")
    print(f"  [override with --broker ibkr | --min-stop N | --spread N]\n")


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


def score(r, stop=None):
    """Composite score: prioritize Sharpe, then return, penalize DD.
    Applies a live-safety penalty for stops too close to bid-ask spread."""
    if r is None or "error" in r:
        return -9999
    base = r["sharpe_ratio"] * 0.5 + r["total_return"] * 100 * 0.3 + r["max_drawdown"] * 100 * 0.2
    # Penalize stops that won't survive live bid-ask spread
    if stop is not None and est_spread > 0:
        stop_dollars = median_price * stop
        spread_mult = stop_dollars / est_spread
        if spread_mult < 3:
            base *= 0.3   # severe penalty: stop inside spread noise
        elif spread_mult < 5:
            base *= 0.7   # moderate penalty: borderline viability
    return base


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
    s = score(r, stop=stop)
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
        if MIN_STOP_PCT and t_pct / 2 < MIN_STOP_PCT:
            continue  # skip: stop below safe minimum
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
        if MIN_STOP_PCT and s_pct < MIN_STOP_PCT:
            continue  # skip stops below safe minimum
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
        if MIN_STOP_PCT and s_pct < MIN_STOP_PCT:
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
#  PHASE 3 — ROBUSTNESS CHECK (rolling 2-month windows)
# ═══════════════════════════════════════════════════════════════════════════
if best["result"] and "error" not in best["result"]:
    print()
    print("=" * 95)
    print(f"PHASE 3: Robustness check — rolling 2-month windows with optimal params")
    print("=" * 95)

    bt = best["target"]
    bs = best["stop"]
    br = best["rsi"]
    bv = best["vwap"]

    # Set optimal params
    setattr(config, f"RSI_OVERSOLD_{MODE_NAME}", br)
    config.ASSETS[MODE_NAME]["rsi_oversold"] = br
    setattr(config, f"VWAP_ZSCORE_THRESH_{MODE_NAME}", bv)
    config.ASSETS[MODE_NAME]["vwap_zscore_thresh"] = bv

    # Build 2-month rolling windows, sliding by 1 month
    window_days = 60
    slide_days = 30
    start_ts = df_raw.index[0]
    end_ts = df_raw.index[-1]
    windows = []
    w_start = start_ts
    while w_start + pd.Timedelta(days=window_days) <= end_ts:
        w_end = w_start + pd.Timedelta(days=window_days)
        windows.append((w_start, w_end))
        w_start += pd.Timedelta(days=slide_days)

    window_results = []
    for w_start, w_end in windows:
        df_window = df_raw.loc[w_start:w_end].copy()
        if len(df_window) < 50:
            continue  # not enough bars for meaningful backtest
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                wr = run_backtest(
                    df=df_window,
                    initial_capital=config.INITIAL_CAPITAL,
                    target_gain_pct=bt,
                    stop_loss_pct=bs,
                    require_signals=1,
                    kelly_multiplier=config.KELLY_MULTIPLIER,
                    timeframe="hourly",
                    plot=False,
                )
            if wr and "error" not in wr:
                window_results.append({
                    "start": w_start.strftime("%Y-%m-%d"),
                    "end": w_end.strftime("%Y-%m-%d"),
                    "return": wr["total_return"],
                    "sharpe": wr["sharpe_ratio"],
                    "max_dd": wr["max_drawdown"],
                    "trades": wr["total_trades"],
                    "win_rate": wr["win_rate"],
                })
        except Exception:
            continue

    if window_results:
        # Sort by return to find worst/best
        by_return = sorted(window_results, key=lambda x: x["return"])
        worst = by_return[0]
        best_window = by_return[-1]

        # Stats across all windows
        returns = [w["return"] for w in window_results]
        dds = [w["max_dd"] for w in window_results]
        wrs = [w["win_rate"] for w in window_results]
        neg_windows = sum(1 for r in returns if r < 0)

        print(f"\n  {len(window_results)} rolling windows tested ({window_days}-day, {slide_days}-day slide)")
        print(f"  Negative windows:  {neg_windows}/{len(window_results)}")
        print(f"  Avg window return: {sum(returns)/len(returns)*100:+.2f}%")
        print(f"  Avg window WR:     {sum(wrs)/len(wrs)*100:.1f}%")
        print()
        print(f"  WORST window:  {worst['start']} → {worst['end']}")
        print(f"    Return={worst['return']*100:+.2f}%  DD={worst['max_dd']*100:.2f}%  "
              f"WR={worst['win_rate']*100:.1f}%  Trades={worst['trades']}")
        print(f"  BEST window:   {best_window['start']} → {best_window['end']}")
        print(f"    Return={best_window['return']*100:+.2f}%  DD={best_window['max_dd']*100:.2f}%  "
              f"WR={best_window['win_rate']*100:.1f}%  Trades={best_window['trades']}")

        # Fragility checks
        fragile = False
        fragile_reasons = []
        if neg_windows > len(window_results) * 0.25:
            fragile = True
            fragile_reasons.append(f"{neg_windows}/{len(window_results)} windows negative (>25%)")
        if worst["max_dd"] < -0.02:  # worse than -2% DD in any window
            fragile = True
            fragile_reasons.append(f"worst window DD {worst['max_dd']*100:.2f}% exceeds -2%")
        if worst["return"] < -0.02:  # worse than -2% return in any window
            fragile = True
            fragile_reasons.append(f"worst window return {worst['return']*100:.2f}% exceeds -2%")

        stop_dollars = median_price * bs
        spread_mult = stop_dollars / est_spread if est_spread > 0 else 999
        if spread_mult < 5:
            fragile = True
            fragile_reasons.append(f"stop ${stop_dollars:.3f} is only {spread_mult:.1f}x spread — live slippage risk")

        if fragile:
            print(f"\n  *** FRAGILE — params may not survive live trading ***")
            for reason in fragile_reasons:
                print(f"    - {reason}")

            # Auto-test fallback: widen stop to safe minimum, keep same R:R
            fallback_stop = max(bs, auto_min_stop_pct / 100)
            fallback_target = fallback_stop * (bt / bs)  # preserve R:R ratio
            if fallback_stop > bs:
                print(f"\n  Testing fallback config: target={fallback_target*100:.2f}% "
                      f"stop={fallback_stop*100:.2f}% (same {bt/bs:.1f}:1 R:R, live-safe stop)")
                fr = run_quiet(target=fallback_target, stop=fallback_stop, rsi_os=br, vwap=bv)
                if fr and "error" not in fr:
                    fmo = fr["monthly_returns"]
                    favg = fmo[fmo != 0].mean() * 100 if len(fmo[fmo != 0]) > 0 else 0
                    print(f"  Fallback result: trades={fr['total_trades']} WR={fr['win_rate']*100:.1f}% "
                          f"ret={fr['total_return']*100:+.2f}% Sharpe={fr['sharpe_ratio']:.1f} "
                          f"DD={fr['max_drawdown']*100:.2f}% avg/mo={favg:+.2f}%")

                    # Run robustness on fallback too
                    fb_neg = 0
                    fb_worst_ret = 999
                    fb_worst_dd = 0
                    for w_start, w_end in windows:
                        df_window = df_raw.loc[w_start:w_end].copy()
                        if len(df_window) < 50:
                            continue
                        try:
                            with contextlib.redirect_stdout(io.StringIO()):
                                fwr = run_backtest(
                                    df=df_window,
                                    initial_capital=config.INITIAL_CAPITAL,
                                    target_gain_pct=fallback_target,
                                    stop_loss_pct=fallback_stop,
                                    require_signals=1,
                                    kelly_multiplier=config.KELLY_MULTIPLIER,
                                    timeframe="hourly",
                                    plot=False,
                                )
                            if fwr and "error" not in fwr:
                                if fwr["total_return"] < 0:
                                    fb_neg += 1
                                if fwr["total_return"] < fb_worst_ret:
                                    fb_worst_ret = fwr["total_return"]
                                if fwr["max_drawdown"] < fb_worst_dd:
                                    fb_worst_dd = fwr["max_drawdown"]
                        except Exception:
                            continue

                    print(f"  Fallback robustness: neg_windows={fb_neg}/{len(window_results)} "
                          f"worst_ret={fb_worst_ret*100:+.2f}% worst_DD={fb_worst_dd*100:.2f}%")
                    if fb_neg < neg_windows or fb_worst_ret > worst["return"]:
                        print(f"  --> Fallback is MORE robust. Consider using fallback for live trading.")
                    else:
                        print(f"  --> Fallback is not better. Original params OK if slippage is managed.")
        else:
            print(f"\n  ✓ ROBUST — params survived all rolling windows with acceptable performance.")

        # Store window results for JSON output
        _phase3_results = {
            "windows_tested": len(window_results),
            "negative_windows": neg_windows,
            "avg_window_return_pct": round(sum(returns) / len(returns) * 100, 2),
            "worst_window": worst,
            "best_window": best_window,
            "fragile": fragile,
            "fragile_reasons": fragile_reasons if fragile else [],
        }
    else:
        print("  No valid windows — not enough data for robustness check.")
        _phase3_results = None
else:
    _phase3_results = None


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

    # Live-trading viability warning
    stop_dollars = median_price * best["stop"]
    spread_multiple = stop_dollars / est_spread if est_spread > 0 else 999
    if spread_multiple < 3:
        print(f"  ⚠ LIVE TRADING WARNING: stop (${stop_dollars:.3f}) is only {spread_multiple:.1f}x the")
        print(f"    estimated bid-ask spread (${est_spread:.3f}). Slippage will likely degrade WR.")
        print(f"    Consider using --min-stop {auto_min_stop_pct:.2f} or wider.\n")
    elif spread_multiple < 5:
        print(f"  ℹ Note: stop (${stop_dollars:.3f}) is {spread_multiple:.1f}x the estimated spread")
        print(f"    (${est_spread:.3f}). Viable but monitor slippage in live trading.\n")
    else:
        print(f"  ✓ Stop (${stop_dollars:.3f}) is {spread_multiple:.1f}x the estimated spread — live-safe.\n")

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
        "live_trading": {
            "median_price": round(median_price, 2),
            "est_spread": round(est_spread, 3),
            "stop_dollars": round(median_price * best["stop"], 3),
            "spread_multiple": round(spread_multiple, 1),
            "min_stop_pct_used": MIN_STOP_PCT,
            "live_safe": spread_multiple >= 5,
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
    if _phase3_results:
        out["robustness"] = _phase3_results

    outfile = f"sweep_results_{TICKER}.json"
    with open(outfile, "w") as f:
        json.dump(out, f, indent=2)
    print(f"  Results saved → {outfile}")
else:
    print("  No valid results found. The ticker may not have enough data or liquidity.")

print()

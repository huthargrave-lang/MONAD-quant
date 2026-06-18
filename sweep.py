#!/usr/bin/env python3
"""
MONAD Quant — Universal Parameter Sweep Tool

Finds optimal signal and risk params for any equity/ETF on hourly bars.
Fetches data via yfinance, runs a multi-phase sweep, and reports the best config.

Selection logic: optimizes on train split, picks the final winner using holdout
performance via a live-oriented scoring function that penalizes stop_hit ratio,
negative months, ambiguous same-bar exits, too few trades, and train→holdout
degradation. Uses fixed 10% position sizing to match the live trader. Outputs
multiple preset candidates (best overall, most robust, high-R:R, high-trade-count).

Usage:
    python sweep.py GDXU                    # Full sweep with defaults (2yr lookback)
    python sweep.py SOXL --start 2024-06-01 # Custom start date
    python sweep.py TQQQ --phase 1          # Run only phase 1 (target/stop)
    python sweep.py NVDA --phase 2          # Run only phase 2 (cross-validation)
    python sweep.py LABU --min-stop 0.15    # Force realistic stops (≥0.15%)
    python sweep.py GDXU --apply            # Auto-apply optimal params to config.py

Phases:
    1 = Coarse sweep (target/stop, VWAP, RSI)
    2 = Cross-validation (fine-tune target/stop/RSI + MAX_TRADE_BARS)
    all = Both phases (default)
"""
import sys, os, io, argparse, contextlib, json, re
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
parser.add_argument("--phase", default="all", choices=["1", "2", "all", "exit-tuning"],
                    help="Which sweep phase to run (default: all). "
                         "'exit-tuning' sweeps RSI_OVERBOUGHT for opposing-signal exit tuning.")
parser.add_argument("--min-stop", type=float, default=None,
                    help="Minimum stop loss %% (e.g., 0.15 = 0.15%%). Default: auto-calculated from price/spread. Use 0 to disable.")
parser.add_argument("--spread", type=float, default=None,
                    help="Assumed bid-ask spread in dollars (default: auto-estimated from price level)")
parser.add_argument("--broker", default=None, choices=["ibkr", "schwab", "fidelity", "retail"],
                    help="Broker preset for spread/fee estimates (default: conservative retail)")
parser.add_argument("--apply", action="store_true",
                    help="Auto-apply optimal params to config.py without prompting")
parser.add_argument("--mode", default="realistic", choices=["optimistic", "realistic", "harsh"],
                    help="Backtest fairness mode (default: realistic)")
parser.add_argument("--holdout-pct", type=float, default=20,
                    help="Percentage of data to reserve as untouched holdout (default: 20%%). "
                         "Set to 0 to disable holdout.")
parser.add_argument("--validate-best", action="store_true",
                    help="After the sweep, automatically validate the top candidates across multiple holdout splits and modes.")
# Optional parameter overrides / filters
parser.add_argument("--rsi", type=int, default=None,
                    help="Force a single RSI oversold value instead of sweeping RSI values.")
parser.add_argument("--vwap", type=float, default=None,
                    help="Force a single VWAP z-score threshold instead of sweeping VWAP values.")
parser.add_argument("--target", type=float, default=None,
                    help="Force a single target %% instead of sweeping target values (example: 1.4 for 1.4%%).")
parser.add_argument("--stop", type=float, default=None,
                    help="Force a single stop %% instead of sweeping stop values (example: 0.65 for 0.65%%).")
parser.add_argument("--short-rsi", type=int, default=None,
                    help="Force a single RSI overbought value for exit-tuning sweep instead of sweeping.")
parser.add_argument("--compare-opposing-exit", action="store_true",
                    help="Skip the full sweep. Run the current config (or --target/--stop/--rsi/--vwap overrides) "
                         "twice — once with use_opposing_signal_exit=False and once with =True — and print a "
                         "side-by-side comparison. Useful for validating whether an opposing-signal exit helps "
                         "a specific instrument before wiring it into the live trader.")
parser.add_argument("--sizing", default=None, choices=["fixed", "kelly", "kelly_clamped"],
                    help="Position sizing the backtest uses (default: config.POSITION_SIZING_MODE). "
                         "Use '--sizing fixed --fixed-pct 0.10' to match the live trader's fixed 10%%.")
parser.add_argument("--fixed-pct", type=float, default=0.10,
                    help="Capital fraction per trade when --sizing fixed (default 0.10 = live trader).")
parser.add_argument("--adaptive", default=None, choices=["on", "off"],
                    help="Run the sweep with adaptive Kelly on/off (default: config.USE_ADAPTIVE_KELLY).")
args = parser.parse_args()

TICKER = args.ticker.upper()
END_DATE = args.end or datetime.now().strftime("%Y-%m-%d")
# yfinance hourly data limit is 730 days. Use 710 to stay safely inside the window.
START_DATE = args.start or (datetime.now() - timedelta(days=710)).strftime("%Y-%m-%d")

# ── Position-sizing mode for this sweep — so results reflect how you'll run it.
#    (The live trader uses fixed 10%; the backtest default is adaptive Kelly.
#    Sweeping with the sizing you intend to deploy avoids the sizing mismatch.) ──
if args.sizing is not None:
    config.POSITION_SIZING_MODE = args.sizing
    if args.sizing == "fixed":
        config.FIXED_POSITION_PCT = args.fixed_pct
    print(f"  Sizing mode: {args.sizing}"
          + (f" @ {args.fixed_pct:.0%}" if args.sizing == "fixed" else ""))
if args.adaptive is not None:
    config.USE_ADAPTIVE_KELLY = (args.adaptive == "on")
    print(f"  Adaptive Kelly: {'ON' if config.USE_ADAPTIVE_KELLY else 'OFF'}")


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

# ── Match live trader sizing: fixed 10% per trade ────────────────────────
# Live trader (live/state.py) uses hardcoded 10%. Force the backtest runner
# to use the same so sweep results are directly comparable to live performance.
config.POSITION_SIZING_MODE = "fixed"
config.FIXED_POSITION_PCT = 0.10
# Disable adaptive Kelly — live trader doesn't use it
config.USE_ADAPTIVE_KELLY = False

# Register the mode→asset mapping
config._MODE_TO_ASSET[MODE_NAME] = MODE_NAME

# Engine's build_features() now handles any hourly mode generically via config suffix.
# No monkey-patching needed — sweep just sets config attributes and the engine reads them.


# ═══════════════════════════════════════════════════════════════════════════
#  DATA LOADING
# ═══════════════════════════════════════════════════════════════════════════
from src.data.fetcher import _ensure_cache_dir, _cache_path, _cache_is_fresh, fetch_yfinance
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

    df = fetch_yfinance(symbol=ticker, start=start, end=end, interval="1h")
    df = df.between_time("09:30", "16:00")
    df.to_csv(cache_file)
    print(f"[cache] Saved {ticker} hourly to {cache_file} ({len(df)} bars)")
    return df.loc[start:end]


print(f"\n{'='*70}")
print(f"  MONAD QUANT — UNIVERSAL SWEEP: {TICKER}  [{args.mode.upper()}]")
print(f"  Period: {START_DATE} → {END_DATE}")
print(f"{'='*70}\n")

df_full = fetch_ticker_hourly(TICKER, START_DATE, END_DATE)
print(f"Loaded {len(df_full)} bars\n")

if len(df_full) < 100:
    print(f"ERROR: Only {len(df_full)} bars loaded. Need at least 100 for meaningful backtest.")
    print("Try a wider date range or check if the ticker is valid.")
    sys.exit(1)

# ── Holdout split: reserve the last N% of data as untouched test set ─────
HOLDOUT_PCT = args.holdout_pct / 100.0
if HOLDOUT_PCT > 0 and len(df_full) > 200:
    split_idx = int(len(df_full) * (1 - HOLDOUT_PCT))
    df_raw = df_full.iloc[:split_idx].copy()
    df_holdout = df_full.iloc[split_idx:].copy()
    print(f"  Train/optimize: {len(df_raw)} bars ({df_raw.index[0].strftime('%Y-%m-%d')} → {df_raw.index[-1].strftime('%Y-%m-%d')})")
    print(f"  Holdout (OOS):  {len(df_holdout)} bars ({df_holdout.index[0].strftime('%Y-%m-%d')} → {df_holdout.index[-1].strftime('%Y-%m-%d')})")
    print(f"  Holdout is NEVER used during optimization.\n")
else:
    df_raw = df_full.copy()
    df_holdout = None
    if HOLDOUT_PCT > 0:
        print("  Holdout disabled — not enough bars to split meaningfully.\n")
    else:
        print("  Holdout disabled (--holdout-pct 0).\n")


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

# Safe stop = 5x spread as % of price (round-trip: entry slippage + exit slippage)
# Floor at 0.15% — stops below this create same-bar ambiguity on hourly bars
# (both stop and target fit inside one bar's range, making the result random)
auto_min_stop_pct = max(0.15, (5 * est_spread / median_price) * 100)

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
def _set_opposing_exit(enabled: bool):
    """Toggle the opposing-signal exit flag read by runner.py.

    Uses the mode-override set so the flag is scoped to this MODE_NAME only
    and doesn't leak into unrelated imports during the process lifetime.
    """
    if enabled:
        config.USE_OPPOSING_SIGNAL_EXIT = True
    else:
        config.USE_OPPOSING_SIGNAL_EXIT = False
    # Clear any per-mode set override so the global flag is the single source.
    config.OPPOSING_SIGNAL_EXIT_MODES = set()


def _update_mode_param(const_suffix: str, asset_key: str, value):
    """Keep a swept parameter consistent in BOTH places the engine reads it:
    the top-level config constant (``<SUFFIX>_<MODE>``) AND ``config.ASSETS[mode]``.
    Routing every update through here prevents the silent dual-sync bug where the
    two disagree and the backtest runs with inconsistent params."""
    setattr(config, f"{const_suffix}_{MODE_NAME}", value)
    config.ASSETS[MODE_NAME][asset_key] = value


def run_quiet(target, stop, rsi_os=None, vwap=None, short_rsi_ob=None):
    """Run a single backtest quietly. Returns result dict or None.

    Args:
        short_rsi_ob: When set, temporarily overrides RSI_OVERBOUGHT_{MODE_NAME}
                      (the bearish/short signal threshold). This controls how
                      sensitive the opposing-signal exit is — lower values make
                      the exit fire earlier, higher values make it fire later.
                      Only meaningful when USE_OPPOSING_SIGNAL_EXIT is True.
    """
    if rsi_os is not None:
        _update_mode_param("RSI_OVERSOLD", "rsi_oversold", rsi_os)
    if vwap is not None:
        _update_mode_param("VWAP_ZSCORE_THRESH", "vwap_zscore_thresh", vwap)
    if short_rsi_ob is not None:
        _update_mode_param("RSI_OVERBOUGHT", "rsi_overbought", short_rsi_ob)

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
                backtest_mode=args.mode,
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


def extract_metrics(r):
    """Pull live-relevant metrics from a backtest result dict."""
    if r is None or "error" in r:
        return None
    mo = r["monthly_returns"]
    active_months = mo[mo != 0]
    neg_months = int((active_months < 0).sum())
    total_months = int(len(active_months))
    avg_mo = float(active_months.mean()) if total_months > 0 else 0.0

    eb = r.get("exit_breakdown", {})
    total_trades = r["total_trades"]
    stop_hits = eb.get("stop_hit", 0)
    ambiguous = eb.get("ambiguous_same_bar", 0)
    target_hits = eb.get("target_hit", 0)

    time_exits = eb.get("time_exit", 0)

    return {
        "total_return_pct":    round(r["total_return"] * 100, 3),
        "sharpe_ratio":        r["sharpe_ratio"],
        "max_drawdown_pct":    round(r["max_drawdown"] * 100, 3),
        "avg_monthly_pct":     round(avg_mo * 100, 3),
        "total_trades":        total_trades,
        "win_rate_pct":        round(r["win_rate"] * 100, 2),
        "neg_months":          neg_months,
        "total_months":        total_months,
        "stop_hit_ratio":      round(stop_hits / total_trades, 3) if total_trades else 0,
        "ambiguous_ratio":     round(ambiguous / total_trades, 3) if total_trades else 0,
        "target_hit_count":    target_hits,
        "stop_hit_count":      stop_hits,
        "ambiguous_count":     ambiguous,
        "time_exit_count":     time_exits,
    }


def live_score(r, stop=None, train_metrics=None):
    """Live-oriented scoring: Sharpe + return, penalised by live-hostile traits.

    Penalties:
      - High stop_hit ratio (>50%): trades are noise-stopped too often
      - Negative months: income strategy should have near-zero neg months
      - Ambiguous same-bar exits: result is random (stop or target in same bar)
      - Too few trades (<5/month): not enough for statistical confidence
      - Large train→holdout degradation (when train_metrics provided)
      - Stop inside bid-ask spread noise
    """
    if r is None or "error" in r:
        return -9999

    m = extract_metrics(r)
    if m is None:
        return -9999

    # Base: Sharpe × 0.5 + return × 0.3 + DD bonus × 0.2  (DD is negative, so bonus)
    base = m["sharpe_ratio"] * 0.5 + m["total_return_pct"] * 0.3 + m["max_drawdown_pct"] * 0.2

    # ── Penalty: stop_hit ratio ──────────────────────────────────────────
    if m["stop_hit_ratio"] > 0.55:
        base *= 0.6     # >55% stops = mostly noise
    elif m["stop_hit_ratio"] > 0.50:
        base *= 0.8     # >50% stops = marginal

    # ── Penalty: negative months ─────────────────────────────────────────
    if m["total_months"] > 0:
        neg_frac = m["neg_months"] / m["total_months"]
        if neg_frac > 0.25:
            base *= 0.5   # >25% of months negative = not income-grade
        elif neg_frac > 0.10:
            base *= 0.75  # >10% negative = caution

    # ── Penalty: ambiguous same-bar exits ────────────────────────────────
    if m["ambiguous_ratio"] > 0.20:
        base *= 0.5      # >20% ambiguous = R:R too tight for bar range
    elif m["ambiguous_ratio"] > 0.10:
        base *= 0.75

    # ── Penalty: too few trades ──────────────────────────────────────────
    if m["total_months"] > 0:
        trades_per_mo = m["total_trades"] / max(m["total_months"], 1)
        if trades_per_mo < 3:
            base *= 0.5   # <3 trades/month = no statistical edge
        elif trades_per_mo < 5:
            base *= 0.75

    # ── Penalty: train→holdout degradation ───────────────────────────────
    if train_metrics is not None:
        train_avg = train_metrics.get("avg_monthly_pct", 0)
        holdout_avg = m["avg_monthly_pct"]
        if train_avg > 0:
            retention = holdout_avg / train_avg
            if retention < 0:
                base *= 0.3    # holdout negative = likely overfit
            elif retention < 0.4:
                base *= 0.5    # >60% decay
            elif retention < 0.6:
                base *= 0.7    # >40% decay

    # ── Penalty: stop inside bid-ask spread ──────────────────────────────
    if stop is not None and est_spread > 0:
        stop_dollars = median_price * stop
        spread_mult = stop_dollars / est_spread
        if spread_mult < 3:
            base *= 0.3
        elif spread_mult < 5:
            base *= 0.7

    return base


_default_max_trade_bars = getattr(config, "MAX_TRADE_BARS", 20)


def restore():
    setattr(config, f"RSI_OVERSOLD_{MODE_NAME}", _defaults[f"RSI_OVERSOLD_{MODE_NAME}"])
    setattr(config, f"RSI_OVERBOUGHT_{MODE_NAME}", _defaults[f"RSI_OVERBOUGHT_{MODE_NAME}"])
    setattr(config, f"VWAP_ZSCORE_THRESH_{MODE_NAME}", _defaults[f"VWAP_ZSCORE_THRESH_{MODE_NAME}"])
    config.ASSETS[MODE_NAME]["rsi_oversold"] = _defaults[f"RSI_OVERSOLD_{MODE_NAME}"]
    config.ASSETS[MODE_NAME]["rsi_overbought"] = _defaults[f"RSI_OVERBOUGHT_{MODE_NAME}"]
    config.ASSETS[MODE_NAME]["vwap_zscore_thresh"] = _defaults[f"VWAP_ZSCORE_THRESH_{MODE_NAME}"]
    config.MAX_TRADE_BARS = _default_max_trade_bars


# ── Candidate collector: store ALL valid results, not just one best ──────
all_candidates = []   # list of {params, train_result, train_metrics, train_score}


def collect(r, target, stop, rsi=None, vwap=None):
    """Record a candidate with its train-set result."""
    if r is None or "error" in r or r.get("total_trades", 0) == 0:
        return
    _rsi = rsi if rsi is not None else getattr(config, f"RSI_OVERSOLD_{MODE_NAME}")
    _vwap = vwap if vwap is not None else getattr(config, f"VWAP_ZSCORE_THRESH_{MODE_NAME}")
    m = extract_metrics(r)
    s = live_score(r, stop=stop)
    all_candidates.append({
        "params": {"target": target, "stop": stop, "rsi": _rsi, "vwap": _vwap},
        "train_result": r,
        "train_metrics": m,
        "train_score": s,
    })


# Track best for phase progression (coarse → fine-tune)
best = {"target": DEFAULT_TARGET, "stop": DEFAULT_STOP,
        "rsi": _defaults[f"RSI_OVERSOLD_{MODE_NAME}"],
        "vwap": _defaults[f"VWAP_ZSCORE_THRESH_{MODE_NAME}"],
        "max_trade_bars": _default_max_trade_bars,
        "score": -9999, "result": None}


def update_best(r, target, stop, rsi=None, vwap=None):
    s = live_score(r, stop=stop)
    collect(r, target, stop, rsi=rsi, vwap=vwap)
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
#  OPPOSING-SIGNAL EXIT COMPARISON (short-circuit mode)
# ═══════════════════════════════════════════════════════════════════════════
# When --compare-opposing-exit is passed, skip the full sweep and run the
# current config (with any --target/--stop/--rsi/--vwap CLI overrides applied)
# twice — once with use_opposing_signal_exit=False, once with =True. This lets
# you validate whether the opposing-signal exit helps a specific instrument
# before wiring it into the live trader.
if args.compare_opposing_exit:
    # Resolve comparison params — CLI overrides first, then ASSETS defaults.
    cmp_target = args.target if args.target is not None else config.ASSETS[MODE_NAME]["target_gain_pct"]
    cmp_stop   = args.stop   if args.stop   is not None else config.ASSETS[MODE_NAME]["stop_loss_pct"]
    # --target/--stop are in PERCENT on the CLI (e.g. 0.42), but run_quiet
    # expects DECIMALS (0.0042). Detect and convert if user passed a percent.
    if args.target is not None and cmp_target >= 0.1:
        cmp_target = cmp_target / 100.0
    if args.stop is not None and cmp_stop >= 0.1:
        cmp_stop = cmp_stop / 100.0
    cmp_rsi  = args.rsi  if args.rsi  is not None else config.ASSETS[MODE_NAME]["rsi_oversold"]
    cmp_vwap = args.vwap if args.vwap is not None else config.ASSETS[MODE_NAME]["vwap_zscore_thresh"]

    print("=" * 95)
    print(f"  OPPOSING-SIGNAL EXIT COMPARISON — {TICKER}")
    print("=" * 95)
    print(f"  target={cmp_target*100:.3f}%  stop={cmp_stop*100:.3f}%  "
          f"rsi={cmp_rsi}  vwap={cmp_vwap}")
    print(f"  Period: {START_DATE} → {END_DATE}  ({len(df_raw)} bars train)\n")

    _set_opposing_exit(False)
    r_off = run_quiet(cmp_target, cmp_stop, cmp_rsi, cmp_vwap)
    _set_opposing_exit(True)
    r_on  = run_quiet(cmp_target, cmp_stop, cmp_rsi, cmp_vwap)
    _set_opposing_exit(False)   # leave config in its default state

    print(fmt(r_off, "OFF  (baseline)        "))
    print(fmt(r_on,  "ON   (opposing-exit)   "))

    # Compute delta for each extractable metric
    m_off = extract_metrics(r_off) if r_off else None
    m_on  = extract_metrics(r_on)  if r_on  else None
    if m_off and m_on:
        print("\n  DELTA (ON − OFF):")
        fields = [
            ("total_return_pct", "total_return", "%"),
            ("sharpe_ratio",     "sharpe",       ""),
            ("max_drawdown_pct", "max_drawdown", "%"),
            ("avg_monthly_pct",  "avg/mo",       "%"),
            ("total_trades",     "trades",       ""),
            ("win_rate_pct",     "win_rate",     "%"),
        ]
        for key, label, unit in fields:
            delta = m_on[key] - m_off[key]
            sign = "+" if delta >= 0 else ""
            print(f"    {label:14s} {sign}{delta:.3f}{unit}")

        # Count how many trades ended as opposing_signal in the ON run.
        eb_on = r_on.get("exit_breakdown", {}) if r_on else {}
        opp_count = eb_on.get("opposing_signal", 0)
        print(f"\n  Opposing-signal exits in ON run: {opp_count} / {m_on['total_trades']}")

        # Simple verdict
        if m_on["sharpe_ratio"] > m_off["sharpe_ratio"] and m_on["total_return_pct"] > m_off["total_return_pct"]:
            verdict = "HELPS — higher return and Sharpe"
        elif m_on["sharpe_ratio"] < m_off["sharpe_ratio"] and m_on["total_return_pct"] < m_off["total_return_pct"]:
            verdict = "HURTS — lower return and Sharpe"
        else:
            verdict = "MIXED — one metric up, another down (manual review)"
        print(f"\n  Verdict: {verdict}")

    print()
    sys.exit(0)


# ═══════════════════════════════════════════════════════════════════════════
#  EXIT-TUNING PHASE — Sweep RSI_OVERBOUGHT for opposing-signal exit tuning
# ═══════════════════════════════════════════════════════════════════════════
# When --phase exit-tuning is passed, hold the best long-side params fixed
# and sweep the RSI overbought threshold that drives the bearish (opposing)
# signal. For each candidate, run the backtest twice (OFF/ON), compare, and
# pick the RSI_OVERBOUGHT that produces the best Sharpe/DD improvement.
#
# This is strictly an EXIT-tuning workflow — no short positions are opened.
# The bearish signal only fires inside compute_trade_returns() to close
# an existing long trade early when the signal flips against it.
if args.phase == "exit-tuning":
    # ── Resolve fixed long params from CLI overrides or config defaults ────
    et_target = args.target if args.target is not None else config.ASSETS[MODE_NAME]["target_gain_pct"]
    et_stop   = args.stop   if args.stop   is not None else config.ASSETS[MODE_NAME]["stop_loss_pct"]
    if args.target is not None and et_target >= 0.1:
        et_target = et_target / 100.0
    if args.stop is not None and et_stop >= 0.1:
        et_stop = et_stop / 100.0
    et_rsi  = args.rsi  if args.rsi  is not None else config.ASSETS[MODE_NAME]["rsi_oversold"]
    et_vwap = args.vwap if args.vwap is not None else config.ASSETS[MODE_NAME]["vwap_zscore_thresh"]

    # ── Build the short-RSI candidate list ─────────────────────────────────
    if args.short_rsi is not None:
        short_rsi_values = [args.short_rsi]
    else:
        short_rsi_values = [45, 50, 55, 58, 60, 62, 65, 68, 70, 75, 80, 85]

    print("=" * 100)
    print(f"  EXIT-TUNING PHASE: Opposing-signal RSI_OVERBOUGHT sweep — {TICKER}")
    print("=" * 100)
    print(f"  Fixed long params: target={et_target*100:.3f}%  stop={et_stop*100:.3f}%  "
          f"rsi_oversold={et_rsi}  vwap={et_vwap}")
    print(f"  Period: {START_DATE} → {END_DATE}  ({len(df_raw)} bars train)")
    print(f"  Short RSI candidates: {short_rsi_values}")
    print(f"  NOTE: Long-only exit tuning. No short positions are opened.\n")

    # ── Run baseline (opposing-exit OFF) once ──────────────────────────────
    restore()
    _set_opposing_exit(False)
    r_baseline = run_quiet(et_target, et_stop, rsi_os=et_rsi, vwap=et_vwap)
    m_baseline = extract_metrics(r_baseline) if r_baseline else None
    eb_baseline = r_baseline.get("exit_breakdown", {}) if r_baseline else {}

    print(f"  BASELINE (opposing-exit OFF, RSI_OB={_defaults[f'RSI_OVERBOUGHT_{MODE_NAME}']}):")
    print(fmt(r_baseline, "  OFF"))
    if m_baseline:
        print(f"       Exits: " + "  ".join(f"{k}={v}" for k, v in sorted(eb_baseline.items())))
    print()

    # ── Table header ───────────────────────────────────────────────────────
    print(f"  {'RSI_OB':>6}  {'Trades':>6}  {'WR':>6}  {'Return':>8}  {'Sharpe':>7}  "
          f"{'MaxDD':>7}  {'Avg/mo':>7}  {'OppExit':>7}  {'dRet':>7}  {'dSharpe':>8}  "
          f"{'dDD':>6}  {'Score':>7}  {'Verdict'}")
    print("  " + "-" * 115)

    # ── Sweep each short RSI candidate with opposing-exit ON ───────────────
    exit_tuning_results = []

    for short_rsi in short_rsi_values:
        restore()
        _set_opposing_exit(True)
        r_on = run_quiet(et_target, et_stop, rsi_os=et_rsi, vwap=et_vwap,
                         short_rsi_ob=short_rsi)
        _set_opposing_exit(False)
        restore()

        m_on = extract_metrics(r_on) if r_on else None
        eb_on = r_on.get("exit_breakdown", {}) if r_on else {}
        opp_count = eb_on.get("opposing_signal", 0)

        if m_on is None or m_baseline is None:
            print(f"  {short_rsi:>6}  {'ERROR or NO TRADES':>50}")
            continue

        # Compute deltas vs baseline
        d_ret    = m_on["total_return_pct"] - m_baseline["total_return_pct"]
        d_sharpe = m_on["sharpe_ratio"] - m_baseline["sharpe_ratio"]
        d_dd     = m_on["max_drawdown_pct"] - m_baseline["max_drawdown_pct"]
        d_wr     = m_on["win_rate_pct"] - m_baseline["win_rate_pct"]
        total_t  = m_on["total_trades"]

        # ── Exit-tuning score ──────────────────────────────────────────────
        # Prefers: Sharpe improvement, DD improvement, stable/improved return,
        # penalizes overactive exits (>25% of trades) or zero opposing exits.
        score = 0.0
        # Sharpe improvement is the primary signal (weighted 50%)
        score += d_sharpe * 5.0
        # DD improvement: more negative d_dd is better (less drawdown)
        # d_dd > 0 means ON has worse DD (more negative), so we want d_dd < 0
        score += (-d_dd) * 2.0
        # Return stability: mild penalty for lost return, bonus for gained
        score += d_ret * 1.0
        # Overactive exit penalty: if opposing exits > 25% of trades
        if total_t > 0:
            opp_ratio = opp_count / total_t
            if opp_ratio > 0.40:
                score -= 5.0    # very overactive
            elif opp_ratio > 0.25:
                score -= 2.0    # somewhat overactive
        # Zero opposing exits means the setting is inert
        if opp_count == 0:
            score -= 10.0

        # Verdict
        if d_sharpe > 0 and d_ret >= 0:
            verdict = "HELPS"
        elif d_sharpe > 0 and d_ret < 0 and abs(d_ret) < 0.5:
            verdict = "MIXED+"
        elif d_sharpe <= 0 and d_ret <= 0:
            verdict = "HURTS"
        elif opp_count == 0:
            verdict = "INERT"
        else:
            verdict = "MIXED"

        print(f"  {short_rsi:>6}  {total_t:>6}  {m_on['win_rate_pct']:>5.1f}%  "
              f"{m_on['total_return_pct']:>+7.2f}%  {m_on['sharpe_ratio']:>7.1f}  "
              f"{m_on['max_drawdown_pct']:>6.2f}%  {m_on['avg_monthly_pct']:>+6.2f}%  "
              f"{opp_count:>4}/{total_t:<3}  {d_ret:>+6.2f}%  {d_sharpe:>+7.2f}  "
              f"{d_dd:>+5.2f}%  {score:>+6.1f}  {verdict}")

        exit_tuning_results.append({
            "short_rsi": short_rsi,
            "result_on": r_on,
            "metrics_on": m_on,
            "exit_breakdown_on": eb_on,
            "opp_count": opp_count,
            "d_ret": d_ret,
            "d_sharpe": d_sharpe,
            "d_dd": d_dd,
            "d_wr": d_wr,
            "score": score,
            "verdict": verdict,
        })

    # ── Pick the best exit-tuning RSI_OVERBOUGHT ──────────────────────────
    print()
    if exit_tuning_results:
        # Filter to candidates that actually produced opposing exits
        active = [c for c in exit_tuning_results if c["opp_count"] > 0]
        if active:
            best_et = max(active, key=lambda c: c["score"])
            print(f"  BEST EXIT-TUNING RSI_OVERBOUGHT: {best_et['short_rsi']}")
            print(f"    Score: {best_et['score']:+.1f}  Verdict: {best_et['verdict']}")
            print(f"    Opposing exits: {best_et['opp_count']}/{best_et['metrics_on']['total_trades']}")
            print(f"    vs baseline: ret {best_et['d_ret']:+.2f}%  "
                  f"Sharpe {best_et['d_sharpe']:+.2f}  DD {best_et['d_dd']:+.2f}%  "
                  f"WR {best_et['d_wr']:+.1f}%")

            # Print full exit breakdown for the winner
            eb_w = best_et["exit_breakdown_on"]
            print(f"    Exit breakdown: " + "  ".join(f"{k}={v}" for k, v in sorted(eb_w.items())))

            if best_et["score"] <= 0:
                print(f"\n  RECOMMENDATION: Do NOT enable opposing-signal exit for {TICKER}.")
                print(f"    Best candidate still has negative score ({best_et['score']:+.1f}).")
                print(f"    The baseline (OFF) outperforms all tested RSI_OVERBOUGHT values.")
            else:
                print(f"\n  RECOMMENDATION: Enable opposing-signal exit for {TICKER}.")
                print(f"    Set RSI_OVERBOUGHT_{MODE_NAME} = {best_et['short_rsi']}")
                print(f"    Set USE_OPPOSING_SIGNAL_EXIT = True (or add '{MODE_NAME}' to "
                      f"OPPOSING_SIGNAL_EXIT_MODES)")
        else:
            print(f"  No RSI_OVERBOUGHT setting produced any opposing-signal exits.")
            print(f"  The long params (target={et_target*100:.3f}%, stop={et_stop*100:.3f}%) "
                  f"may resolve too fast for opposing signals to fire.")
            print(f"  Try wider target/stop or review signal generation diagnostics.")
    else:
        print("  No valid results from exit-tuning sweep.")

    # ── Save exit-tuning results to JSON ──────────────────────────────────
    if exit_tuning_results:
        et_out = {
            "ticker": TICKER,
            "period": f"{START_DATE} → {END_DATE}",
            "train_bars": len(df_raw),
            "backtest_mode": args.mode,
            "fixed_long_params": {
                "target_gain_pct": et_target,
                "stop_loss_pct": et_stop,
                "rsi_oversold": et_rsi,
                "vwap_zscore_thresh": et_vwap,
            },
            "baseline": m_baseline,
            "candidates": [
                {
                    "rsi_overbought": c["short_rsi"],
                    "opp_exits": c["opp_count"],
                    "total_trades": c["metrics_on"]["total_trades"],
                    "d_return_pct": round(c["d_ret"], 3),
                    "d_sharpe": round(c["d_sharpe"], 3),
                    "d_drawdown_pct": round(c["d_dd"], 3),
                    "d_win_rate_pct": round(c["d_wr"], 2),
                    "score": round(c["score"], 2),
                    "verdict": c["verdict"],
                }
                for c in exit_tuning_results
            ],
        }
        outfile = f"sweep_exit_tuning_{TICKER}.json"
        with open(outfile, "w") as f:
            json.dump(et_out, f, indent=2, default=str)
        print(f"\n  Results saved -> {outfile}")

    print()
    sys.exit(0)


# ═══════════════════════════════════════════════════════════════════════════
#  PHASE 1 — COARSE SWEEP
# ═══════════════════════════════════════════════════════════════════════════
# Optional sweep override lists
target_values_phase1a = [args.target] if args.target is not None else [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.2, 1.4, 1.6, 2.0]
stop_values_phase1b = [args.stop] if args.stop is not None else [0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50, 0.60]
vwap_values_phase1c = [args.vwap] if args.vwap is not None else [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0, 1.2]
rsi_values_phase1d = [args.rsi] if args.rsi is not None else [42, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100]

if args.phase in ("1", "all"):
    # ── 1a: Target/Stop at 2:1 R:R ────────────────────────────────────────
    restore()
    print("=" * 95)
    print(f"PHASE 1a: Target/Stop sweep (2:1 R:R) — {TICKER}")
    print("=" * 95)

    for t_pct in target_values_phase1a:
        t = t_pct / 100
        s = t / 2
        if args.stop is not None:
            s = args.stop / 100
        if MIN_STOP_PCT and s * 100 < MIN_STOP_PCT:
            continue
        if s >= t:
            continue
        r = run_quiet(target=t, stop=s)
        print(fmt(r, f"target={t*100:4.1f}% stop={s*100:5.2f}%"))
        if r and "error" not in r:
            update_best(r, t, s)

    # ── 1b: R:R ratio variations at best target ──────────────────────────
    best_target = best["target"]
    best_t_pct = best_target * 100
    print()
    print("=" * 95)
    print(f"PHASE 1b: R:R variations at target={best_t_pct:.1f}%")
    print("=" * 95)

    for s_pct in stop_values_phase1b:
        s = s_pct / 100
        if s >= best_target:
            continue
        if MIN_STOP_PCT and s_pct < MIN_STOP_PCT:
            continue
        r = run_quiet(target=best_target, stop=s)
        rr = best_t_pct / s_pct
        print(fmt(r, f"R:R={rr:4.1f}:1 stop={s_pct:.2f}%"))
        if r and "error" not in r:
            update_best(r, best_target, s)

    # ── 1c: VWAP threshold ────────────────────────────────────────────────
    restore()
    print()
    print("=" * 95)
    print(f"PHASE 1c: VWAP z-score threshold (at best target/stop so far)")
    print("=" * 95)

    for v in vwap_values_phase1c:
        r = run_quiet(target=best["target"], stop=best["stop"], vwap=v)
        print(fmt(r, f"VWAP={v:.1f}"))
        if r and "error" not in r:
            update_best(r, best["target"], best["stop"], vwap=v)

    # ── 1d: RSI oversold threshold ────────────────────────────────────────
    restore()
    print()
    print("=" * 95)
    print(f"PHASE 1d: RSI oversold threshold (at best target/stop so far)")
    print("=" * 95)

    for rsi in rsi_values_phase1d:
        r = run_quiet(target=best["target"], stop=best["stop"], rsi_os=rsi)
        print(fmt(r, f"RSI={rsi:3d}"))
        if r and "error" not in r:
            update_best(r, best["target"], best["stop"], rsi=rsi)

# ═══════════════════════════════════════════════════════════════════════════
#  PHASE 2 — CROSS-VALIDATION (fine-tune around phase 1 best)
    print(f"\n  Phase 1 best: target={best['target']*100:.2f}% stop={best['stop']*100:.2f}% "
          f"RSI={best['rsi']} VWAP={best['vwap']} → score={best['score']:.1f}")

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

    # ── 2d: MAX_TRADE_BARS sweep ─────────────────────────────────────────
    # Test hold-period limits on the best params found so far.
    # Mean-reversion should resolve quickly — shorter bars reduce stale trades,
    # but too short clips winners before target is hit.
    bt = best["target"]
    bs = best["stop"]
    br = best["rsi"]
    bv = best["vwap"]
    print()
    print("=" * 95)
    print(f"PHASE 2d: MAX_TRADE_BARS sweep at target={bt*100:.2f}% stop={bs*100:.2f}% RSI={br}")
    print("=" * 95)

    mtb_candidates = [8, 10, 12, 15, 20]
    best_mtb = _default_max_trade_bars
    best_mtb_score = best["score"]
    best_mtb_result = None

    for mtb in mtb_candidates:
        config.MAX_TRADE_BARS = mtb
        r = run_quiet(target=bt, stop=bs, rsi_os=br, vwap=bv)
        config.MAX_TRADE_BARS = _default_max_trade_bars  # restore immediately

        if r and "error" not in r:
            m = extract_metrics(r)
            s = live_score(r, stop=bs)
            eb = r.get("exit_breakdown", {})
            te = eb.get("time_exit", 0)
            tgt = eb.get("target_hit", 0)
            stp = eb.get("stop_hit", 0)
            amb = eb.get("ambiguous_same_bar", 0)
            print(f"  MTB={mtb:3d} | trades={m['total_trades']:4d} WR={m['win_rate_pct']:5.1f}% "
                  f"ret={m['total_return_pct']:7.2f}% Sharpe={m['sharpe_ratio']:6.1f} "
                  f"DD={m['max_drawdown_pct']:6.2f}% neg_mo={m['neg_months']}/{m['total_months']} "
                  f"| exits: target={tgt} stop={stp} time={te} ambig={amb} "
                  f"| score={s:.1f}")
            if s > best_mtb_score:
                best_mtb_score = s
                best_mtb = mtb
                best_mtb_result = r
        else:
            print(f"  MTB={mtb:3d} | NO TRADES or ERROR")

    best["max_trade_bars"] = best_mtb
    if best_mtb_result is not None:
        best["result"] = best_mtb_result
        best["score"] = best_mtb_score
        # Re-collect the winning MTB as a candidate
        config.MAX_TRADE_BARS = best_mtb
        collect(best_mtb_result, bt, bs, rsi=br, vwap=bv)
        config.MAX_TRADE_BARS = _default_max_trade_bars

    print(f"\n  Phase 2d best: MAX_TRADE_BARS={best_mtb} → score={best_mtb_score:.1f}")


# ═══════════════════════════════════════════════════════════════════════════
#  PHASE 3 — HOLDOUT EVALUATION + LIVE-SCORE RANKING
#  Evaluate top N train candidates on holdout. Final winner = best holdout
#  live_score, NOT best train score. This prevents in-sample overfitting.
# ═══════════════════════════════════════════════════════════════════════════

def _run_on_data(df, target, stop, rsi, vwap, holdout_start=None, backtest_mode=None,
                 short_rsi_ob=None):
    """Run a single backtest on arbitrary data slice. Returns result or None."""
    setattr(config, f"RSI_OVERSOLD_{MODE_NAME}", rsi)
    config.ASSETS[MODE_NAME]["rsi_oversold"] = rsi
    setattr(config, f"VWAP_ZSCORE_THRESH_{MODE_NAME}", vwap)
    config.ASSETS[MODE_NAME]["vwap_zscore_thresh"] = vwap
    if short_rsi_ob is not None:
        setattr(config, f"RSI_OVERBOUGHT_{MODE_NAME}", short_rsi_ob)
        config.ASSETS[MODE_NAME]["rsi_overbought"] = short_rsi_ob
    mode_to_use = backtest_mode or args.mode
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            r = run_backtest(
                df=df.copy(),
                initial_capital=config.INITIAL_CAPITAL,
                target_gain_pct=target,
                stop_loss_pct=stop,
                require_signals=1,
                kelly_multiplier=config.KELLY_MULTIPLIER,
                timeframe="hourly",
                plot=False,
                backtest_mode=mode_to_use,
            )

            # If the engine produced no trades, `run_backtest()` returns `{}`.
            # Preserve that case for Phase 3 so it doesn't get treated as "missing".
            if r == {}:
                r = {
                    "total_trades": 0,
                    "bull_trades": 0,
                    "bear_trades": 0,
                    "win_rate": 0.0,
                    "avg_win_pct": 0.0,
                    "avg_loss_pct": 0.0,
                    "total_return": 0.0,
                    "sharpe_ratio": 0.0,
                    "max_drawdown": 0.0,
                    "final_capital": config.INITIAL_CAPITAL,
                    "equity_curve": pd.Series([config.INITIAL_CAPITAL], dtype=float),
                    "trade_returns": pd.Series(dtype=float),
                    "trades_df": pd.DataFrame(),
                    "monthly_returns": pd.Series(dtype=float),
                    "backtest_mode": mode_to_use,
                    "slippage_pct": 0.0,
                    "trades_per_year": 0.0,
                    "exit_breakdown": {},
                }

        if holdout_start is not None and isinstance(r, dict) and "error" not in r:
            trades_df = r.get("trades_df")
            if trades_df is not None and not trades_df.empty:
                trade_timestamps = pd.to_datetime(trades_df["timestamp"])
                filtered_trades = trades_df.loc[trade_timestamps >= holdout_start].copy()
                filtered_trades["timestamp"] = pd.to_datetime(filtered_trades["timestamp"])
            else:
                filtered_trades = pd.DataFrame()

            if filtered_trades.empty:
                r = {
                    "total_trades": 0,
                    "bull_trades": 0,
                    "bear_trades": 0,
                    "win_rate": 0.0,
                    "avg_win_pct": 0.0,
                    "avg_loss_pct": 0.0,
                    "total_return": 0.0,
                    "sharpe_ratio": 0.0,
                    "max_drawdown": 0.0,
                    "final_capital": config.INITIAL_CAPITAL,
                    "equity_curve": pd.Series([config.INITIAL_CAPITAL], dtype=float),
                    "trade_returns": pd.Series(dtype=float),
                    "trades_df": pd.DataFrame(),
                    "monthly_returns": pd.Series(dtype=float),
                    "backtest_mode": mode_to_use,
                    "slippage_pct": 0.0,
                    "trades_per_year": 0.0,
                    "exit_breakdown": {},
                }
            else:
                trade_returns = filtered_trades["return"].astype(float)
                trade_returns.index = pd.to_datetime(filtered_trades["timestamp"])
                wins = trade_returns[trade_returns > 0]
                losses = trade_returns[trade_returns < 0]
                equity_curve = (1.0 + trade_returns).cumprod() * config.INITIAL_CAPITAL
                monthly_returns = trade_returns.resample("ME").sum()
                running_max = equity_curve.cummax()
                drawdown = (equity_curve / running_max) - 1.0
                bull_trades = int((filtered_trades["trend_regime"] == 1).sum()) if "trend_regime" in filtered_trades.columns else 0
                bear_trades = int((filtered_trades["trend_regime"] == -1).sum()) if "trend_regime" in filtered_trades.columns else 0
                exit_breakdown = (
                    filtered_trades["exit_type"].value_counts().to_dict()
                    if "exit_type" in filtered_trades.columns else {}
                )

                r = {
                    "total_trades": int(len(filtered_trades)),
                    "bull_trades": bull_trades,
                    "bear_trades": bear_trades,
                    "win_rate": float((trade_returns > 0).mean()) if len(trade_returns) else 0.0,
                    "avg_win_pct": float(wins.mean()) if len(wins) else 0.0,
                    "avg_loss_pct": float(losses.mean()) if len(losses) else 0.0,
                    "total_return": float((equity_curve.iloc[-1] / config.INITIAL_CAPITAL) - 1.0),
                    "sharpe_ratio": float(
                        (trade_returns.mean() / trade_returns.std(ddof=0)) * (len(trade_returns) ** 0.5)
                    ) if len(trade_returns) > 1 and trade_returns.std(ddof=0) > 0 else 0.0,
                    "max_drawdown": float(drawdown.min()) if len(drawdown) else 0.0,
                    "final_capital": float(equity_curve.iloc[-1]) if len(equity_curve) else config.INITIAL_CAPITAL,
                    "equity_curve": equity_curve,
                    "trade_returns": trade_returns,
                    "trades_df": filtered_trades,
                    "monthly_returns": monthly_returns,
                    "backtest_mode": mode_to_use,
                    "slippage_pct": float(r.get("slippage_pct", 0.0) or 0.0),
                    "trades_per_year": float(r.get("trades_per_year", 0.0) or 0.0),
                    "exit_breakdown": exit_breakdown,
                }

        if r is None:
            return None
        if isinstance(r, dict) and "error" in r:
            return None
        return r
    except Exception:
        return None


# De-duplicate candidates (same params can appear from multiple sweep steps)
_seen_params = set()
unique_candidates = []
for c in all_candidates:
    p = c["params"]
    key = (p["target"], p["stop"], p["rsi"], p["vwap"])
    if key not in _seen_params:
        _seen_params.add(key)
        unique_candidates.append(c)

# Sort by train live_score descending, keep top 20 for holdout eval
unique_candidates.sort(key=lambda c: c["train_score"], reverse=True)
TOP_N = min(20, len(unique_candidates))
top_candidates = unique_candidates[:TOP_N]

print()
print("=" * 95)
print(f"PHASE 3: HOLDOUT evaluation — top {TOP_N} candidates on OOS data")
print("=" * 95)

all_zero_holdout = False

if df_holdout is not None and len(top_candidates) > 0:
    # Use the best MAX_TRADE_BARS from Phase 2d for holdout evaluation
    config.MAX_TRADE_BARS = best.get("max_trade_bars", _default_max_trade_bars)
    print(f"  Holdout: {len(df_holdout)} bars "
          f"({df_holdout.index[0].strftime('%Y-%m-%d')} → {df_holdout.index[-1].strftime('%Y-%m-%d')})")
    print(f"  MAX_TRADE_BARS: {config.MAX_TRADE_BARS}")
    print()

    for c in top_candidates:
        p = c["params"]
        hold_r = _run_on_data(
            df_full,
            p["target"],
            p["stop"],
            p["rsi"],
            p["vwap"],
            holdout_start=df_holdout.index[0],
        )

        ZERO_TRADE_PENALTY = -9999.0
        holdout_ok = (hold_r is not None and "error" not in hold_r)

        # Exactly one holdout evaluation call above; exactly one score path here.
        holdout_result = hold_r if holdout_ok else None
        holdout_metrics = extract_metrics(hold_r) if holdout_ok else None

        hold_trades = int((holdout_metrics or {}).get("total_trades", 0) or 0)
        has_holdout_trades = hold_trades > 0

        if has_holdout_trades:
            holdout_score = float(live_score(holdout_result, stop=p["stop"], train_metrics=c.get("train_metrics")))
        else:
            holdout_score = ZERO_TRADE_PENALTY

        hold_ret = float((holdout_metrics or {}).get("total_return_pct", 0.0) or 0.0)
        hold_wr = float((holdout_metrics or {}).get("win_rate_pct", 0.0) or 0.0)
        hold_sharpe = float((holdout_metrics or {}).get("sharpe_ratio", 0.0) or 0.0)
        hold_neg = int((holdout_metrics or {}).get("neg_months", 0) or 0)

        # Single assignment block for Phase 3 records (even if 0-trade)
        c["holdout_result"] = holdout_result
        c["holdout_metrics"] = holdout_metrics
        c["holdout_score"] = holdout_score
        c["holdout_trades"] = hold_trades
        c["holdout_return"] = hold_ret
        c["holdout_win_rate"] = hold_wr
        c["holdout_sharpe"] = hold_sharpe
        c["holdout_neg_months"] = hold_neg
        c["has_holdout_trades"] = has_holdout_trades

    # Rank by holdout score — THIS is the final selection criterion
    top_candidates.sort(
        key=lambda x: (
            1 if x.get("has_holdout_trades", False) else 0,
            x.get("holdout_score", -9999.0),
            x.get("train_score", 0.0),
        ),
        reverse=True,
    )

    all_zero_holdout = (
        len(top_candidates) > 0 and
        all(not row.get("has_holdout_trades", False) for row in top_candidates)
    )

    if all_zero_holdout:
        print("\nWARNING: all holdout candidates produced zero trades; final selection is diagnostic only.\n")

    print(f"  {'Rank':>4}  {'Target':>7} {'Stop':>7} {'RSI':>4} {'VWAP':>5} "
          f"| {'TrainRet':>9} {'HoldRet':>9} {'HoldSharpe':>11} {'HoldWR':>7} "
          f"{'HoldNeg':>8} {'Stop%':>6} {'Ambig%':>7} {'HScore':>7}")
    print("  " + "-" * 105)
    for i, c in enumerate(top_candidates[:10]):
        p = c["params"]
        tm = c["train_metrics"]
        hm = c["holdout_metrics"]
        if hm:
            print(f"  {i+1:>4}  {p['target']*100:>6.2f}% {p['stop']*100:>6.3f}% {p['rsi']:>4} {p['vwap']:>5.1f} "
                  f"| {tm['total_return_pct']:>+8.2f}% {hm['total_return_pct']:>+8.2f}% "
                  f"{hm['sharpe_ratio']:>11.1f} {hm['win_rate_pct']:>6.1f}% "
                  f"{hm['neg_months']:>3}/{hm['total_months']:<3} "
                  f"{hm['stop_hit_ratio']*100:>5.1f}% {hm['ambiguous_ratio']*100:>6.1f}% "
                  f"{c['holdout_score']:>7.1f}")
        else:
            print(f"  {i+1:>4}  {p['target']*100:>6.2f}% {p['stop']*100:>6.3f}% {p['rsi']:>4} {p['vwap']:>5.1f} "
                  f"| {tm['total_return_pct']:>+8.2f}% {'NO TRADES':>9}")

    # Update best to holdout winner
    holdout_winner = top_candidates[0]
    best["target"] = holdout_winner["params"]["target"]
    best["stop"] = holdout_winner["params"]["stop"]
    best["rsi"] = holdout_winner["params"]["rsi"]
    best["vwap"] = holdout_winner["params"]["vwap"]
    best["result"] = holdout_winner["train_result"]
    best["score"] = holdout_winner["holdout_score"]

    print(f"\n  Winner (by holdout live_score): "
          f"target={best['target']*100:.2f}% stop={best['stop']*100:.3f}% "
          f"RSI={best['rsi']} VWAP={best['vwap']}")
elif df_holdout is None:
    print("  Holdout disabled — using train score for ranking.")
else:
    print("  No valid candidates to evaluate.")


# ═══════════════════════════════════════════════════════════════════════════
#  PHASE 4 — PERTURBATION ROBUSTNESS TEST
#  For each top candidate, jitter target/stop/RSI/VWAP by small steps.
#  A robust candidate performs well across all neighbours, not just at
#  one lucky param point.
# ═══════════════════════════════════════════════════════════════════════════
PERTURB_TOP_N = min(5, len(top_candidates))
print()
print("=" * 95)
print(f"PHASE 4: Perturbation robustness — testing {PERTURB_TOP_N} candidates")
print("=" * 95)

# Use the data source that the candidate was ranked on
perturb_df = df_holdout if df_holdout is not None else df_raw

for c in top_candidates[:PERTURB_TOP_N]:
    p = c["params"]
    base_target = p["target"]
    base_stop = p["stop"]
    base_rsi = p["rsi"]
    base_vwap = p["vwap"]

    # Small perturbation steps relative to param magnitude
    target_step = round(max(base_target * 0.1, 0.0002), 5)   # ~10% of target or 0.02%
    stop_step = round(max(base_stop * 0.1, 0.0001), 5)       # ~10% of stop or 0.01%

    neighbours = []
    for t_delta in [-target_step, 0, target_step]:
        for s_delta in [-stop_step, 0, stop_step]:
            for rsi_delta in [-5, 0, 5]:
                for vwap_delta in [-0.1, 0, 0.1]:
                    nt = round(base_target + t_delta, 6)
                    ns = round(base_stop + s_delta, 6)
                    nr = base_rsi + rsi_delta
                    nv = round(base_vwap + vwap_delta, 2)
                    # Skip invalid combos
                    if nt <= 0 or ns <= 0 or ns >= nt or nr < 30 or nr > 100 or nv < 0.0:
                        continue
                    if MIN_STOP_PCT and ns * 100 < MIN_STOP_PCT:
                        continue
                    neighbours.append((nt, ns, nr, nv))

    # Run all neighbours
    perturb_scores = []
    perturb_returns = []
    for nt, ns, nr, nv in neighbours:
        if df_holdout is not None:
            pr = _run_on_data(
                df_full,
                nt,
                ns,
                nr,
                nv,
                holdout_start=df_holdout.index[0],
            )
        else:
            pr = _run_on_data(perturb_df, nt, ns, nr, nv)

        if pr is not None and "error" not in pr:
            ps = live_score(pr, stop=ns)
            perturb_scores.append(ps)
            perturb_returns.append(float(pr.get("total_return", 0.0) or 0.0))
        else:
            perturb_scores.append(0.0)
            perturb_returns.append(0.0)

    # Compute robustness metrics
    valid_scores = perturb_scores
    valid_returns = perturb_returns

    if valid_scores:
        avg_score = sum(valid_scores) / len(valid_scores)
        min_score = min(valid_scores)
        pct_positive = sum(1 for r in valid_returns if r > 0) / len(valid_returns) * 100
        score_std = (sum((s - avg_score)**2 for s in valid_scores) / len(valid_scores)) ** 0.5
        avg_ret = sum(valid_returns) / len(valid_returns) * 100
        min_ret = min(valid_returns) * 100

        c["robustness"] = {
            "neighbours_tested": len(neighbours),
            "neighbours_valid": len(valid_scores),
            "avg_score": round(avg_score, 2),
            "min_score": round(min_score, 2),
            "score_std": round(score_std, 2),
            "avg_return_pct": round(avg_ret, 2),
            "min_return_pct": round(min_ret, 2),
            "pct_positive": round(pct_positive, 1),
        }
        print(f"\n  target={base_target*100:.2f}% stop={base_stop*100:.3f}% RSI={base_rsi} VWAP={base_vwap}")
        print(f"    {len(valid_scores)}/{len(neighbours)} neighbours valid | "
              f"avg_score={avg_score:.1f} min={min_score:.1f} std={score_std:.1f} | "
              f"avg_ret={avg_ret:+.2f}% min_ret={min_ret:+.2f}% | "
              f"{pct_positive:.0f}% positive")
    else:
        c["robustness"] = {
            "neighbours_tested": len(neighbours),
            "neighbours_valid": 0,
            "avg_score": -9999,
        }
        print(f"\n  target={base_target*100:.2f}% stop={base_stop*100:.3f}% — no valid neighbours")


# ═══════════════════════════════════════════════════════════════════════════
#  PHASE 5 — SELECT PRESETS (best overall, most robust, high-R:R, high-trade)
# ═══════════════════════════════════════════════════════════════════════════
print()
print("=" * 95)
print(f"PHASE 5: Final preset selection for {TICKER} HOURLY")
print("=" * 95)


def _build_preset(c, label):
    """Build a JSON-friendly preset dict from a candidate."""
    p = c["params"]
    rr = p["target"] / p["stop"] if p["stop"] > 0 else 0
    stop_d = median_price * p["stop"]
    sp_mult = stop_d / est_spread if est_spread > 0 else 999
    mtb = c.get("max_trade_bars", best.get("max_trade_bars", _default_max_trade_bars))

    preset = {
        "label": label,
        "params": {
            "target_gain_pct": p["target"],
            "stop_loss_pct": p["stop"],
            "rsi_oversold": p["rsi"],
            "vwap_zscore_thresh": p["vwap"],
            "rr_ratio": round(rr, 2),
            "max_trade_bars": mtb,
        },
        "live_trading": {
            "stop_dollars": round(stop_d, 3),
            "spread_multiple": round(sp_mult, 1),
            "live_safe": sp_mult >= 5,
            "position_sizing": "fixed_10pct",
        },
        "train": c["train_metrics"],
        "train_score": round(c["train_score"], 2),
    }
    if c.get("holdout_metrics"):
        preset["holdout"] = c["holdout_metrics"]
        preset["holdout_score"] = round(c.get("holdout_score", -9999), 2)
        # Compute retention
        if c["train_metrics"]["avg_monthly_pct"] > 0:
            retention = c["holdout_metrics"]["avg_monthly_pct"] / c["train_metrics"]["avg_monthly_pct"] * 100
            preset["holdout"]["oos_retention_pct"] = round(retention, 1)
    if c.get("robustness"):
        preset["robustness"] = c["robustness"]
    return preset


def _candidate_max_trade_bars(c):
    return int(c.get("max_trade_bars", best.get("max_trade_bars", _default_max_trade_bars)))


def _candidate_key(c):
    p = c["params"]
    return (
        round(p["target"], 6),
        round(p["stop"], 6),
        int(p["rsi"]),
        round(p["vwap"], 2),
        _candidate_max_trade_bars(c),
    )


def _candidate_param_str(c):
    p = c["params"]
    return (f"t={p['target']*100:.2f}% s={p['stop']*100:.3f}% "
            f"r={p['rsi']} v={p['vwap']:.1f} m={_candidate_max_trade_bars(c)}")


def _robustness_summary(c):
    rob = c.get("robustness", {})
    if rob.get("avg_score", -9999) <= -9999:
        return "-"
    return f"{rob.get('avg_score', 0):.1f}/{rob.get('pct_positive', 0):.0f}%"


def _validate_candidate_holdout(c, holdout_pct, backtest_mode):
    holdout_frac = holdout_pct / 100.0
    if holdout_frac <= 0 or holdout_frac >= 1 or len(df_full) <= 200:
        return {
            "holdout_pct": holdout_pct,
            "mode": backtest_mode,
            "result": None,
            "metrics": None,
            "score": -9999.0,
            "holdout_bars": 0,
            "holdout_start": None,
        }

    split_idx = int(len(df_full) * (1 - holdout_frac))
    if split_idx <= 0 or split_idx >= len(df_full):
        return {
            "holdout_pct": holdout_pct,
            "mode": backtest_mode,
            "result": None,
            "metrics": None,
            "score": -9999.0,
            "holdout_bars": 0,
            "holdout_start": None,
        }

    df_validation_holdout = df_full.iloc[split_idx:].copy()
    holdout_start = df_validation_holdout.index[0]
    prev_mtb = config.MAX_TRADE_BARS
    try:
        config.MAX_TRADE_BARS = _candidate_max_trade_bars(c)
        vr = _run_on_data(
            df_full,
            c["params"]["target"],
            c["params"]["stop"],
            c["params"]["rsi"],
            c["params"]["vwap"],
            holdout_start=holdout_start,
            backtest_mode=backtest_mode,
        )
    finally:
        config.MAX_TRADE_BARS = prev_mtb

    metrics = extract_metrics(vr) if vr is not None and "error" not in vr else None
    score = (float(live_score(vr, stop=c["params"]["stop"], train_metrics=c.get("train_metrics")))
             if vr is not None and "error" not in vr else -9999.0)
    return {
        "holdout_pct": holdout_pct,
        "mode": backtest_mode,
        "result": vr,
        "metrics": metrics,
        "score": score,
        "holdout_bars": len(df_validation_holdout),
        "holdout_start": holdout_start,
    }


# ── 1. Best overall = top holdout score (already sorted) ─────────────────
presets = {}
preset_candidate_rows = {}

def _selection_key(row):
    return (
        1 if row.get("has_holdout_trades", False) else 0,
        row.get("holdout_score", -9999.0),
        row.get("train_score", 0.0),
        row.get("total_trades", 0),
    )

if df_holdout is None:
    valid_top = [c for c in top_candidates if c.get("train_score", -9999) > -9999]
else:
    if all_zero_holdout:
        valid_top = top_candidates
    else:
        valid_top = [c for c in top_candidates if c.get("has_holdout_trades", False)]

if valid_top:
    phase3_rows = valid_top
    best_overall = max(phase3_rows, key=_selection_key)
    presets["best_overall"] = _build_preset(best_overall, "best_overall")
    preset_candidate_rows["best_overall"] = best_overall

# ── 2. Most robust = highest avg perturbation score ──────────────────────
robust_candidates = [c for c in top_candidates[:PERTURB_TOP_N]
                     if c.get("robustness", {}).get("avg_score", -9999) > -9999]
if df_holdout is not None and not all_zero_holdout:
    robust_candidates = [c for c in robust_candidates if c.get("has_holdout_trades", False)]
if robust_candidates:
    most_robust = max(robust_candidates, key=lambda c: c["robustness"]["avg_score"])
    presets["most_robust"] = _build_preset(most_robust, "most_robust")
    preset_candidate_rows["most_robust"] = most_robust

# ── 3. High-R:R challenger = highest R:R ratio among valid candidates ────
rr_candidates = [c for c in valid_top if c["params"]["stop"] > 0]
if rr_candidates:
    high_rr = max(rr_candidates, key=lambda c: c["params"]["target"] / c["params"]["stop"])
    presets["high_rr"] = _build_preset(high_rr, "high_rr")
    preset_candidate_rows["high_rr"] = high_rr

# ── 4. High-trade-count = most trades among valid candidates ─────────────
trade_source = "holdout_metrics" if df_holdout is not None else "train_metrics"
tc_candidates = [c for c in valid_top if c.get(trade_source)]
if tc_candidates:
    high_tc = max(tc_candidates, key=lambda c: c[trade_source]["total_trades"])
    presets["high_trade_count"] = _build_preset(high_tc, "high_trade_count")
    preset_candidate_rows["high_trade_count"] = high_tc

# Print presets
for label, preset in presets.items():
    p = preset["params"]
    hm = preset.get("holdout") or preset["train"]
    rob = preset.get("robustness", {})
    print(f"\n  [{label.upper()}]")
    print(f"    target={p['target_gain_pct']*100:.2f}%  stop={p['stop_loss_pct']*100:.3f}%  "
          f"R:R={p['rr_ratio']:.1f}:1  RSI={p['rsi_oversold']}  VWAP={p['vwap_zscore_thresh']}  "
          f"MTB={p.get('max_trade_bars', _default_max_trade_bars)}")
    src = "holdout" if "holdout" in preset else "train"
    print(f"    {src}: ret={hm['total_return_pct']:+.2f}%  Sharpe={hm['sharpe_ratio']:.1f}  "
          f"DD={hm['max_drawdown_pct']:.2f}%  WR={hm['win_rate_pct']:.1f}%  "
          f"trades={hm['total_trades']}  neg_mo={hm['neg_months']}/{hm['total_months']}")
    print(f"    stop_hit={hm['stop_hit_ratio']*100:.1f}%  ambiguous={hm['ambiguous_ratio']*100:.1f}%  "
          f"spread_mult={preset['live_trading']['spread_multiple']:.1f}x  "
          f"{'LIVE-SAFE' if preset['live_trading']['live_safe'] else 'SLIPPAGE RISK'}")
    if rob:
        print(f"    robustness: {rob.get('neighbours_valid', 0)}/{rob.get('neighbours_tested', 0)} valid  "
              f"avg_score={rob.get('avg_score', 0):.1f}  min_score={rob.get('min_score', 0):.1f}  "
              f"{rob.get('pct_positive', 0):.0f}% positive")


validation_stage = {}
if args.validate_best:
    print()
    print("=" * 95)
    print(f"VALIDATION: Cross-split / cross-mode check for {TICKER} HOURLY")
    print("=" * 95)

    validation_candidates = []
    seen_validation_keys = set()
    for label in ("best_overall", "most_robust", "high_rr", "high_trade_count"):
        row = preset_candidate_rows.get(label)
        if row is None:
            continue
        key = _candidate_key(row)
        if key in seen_validation_keys:
            continue
        seen_validation_keys.add(key)
        validation_candidates.append(row)
        if len(validation_candidates) >= 3:
            break

    for row in valid_top:
        if len(validation_candidates) >= 3:
            break
        key = _candidate_key(row)
        if key in seen_validation_keys:
            continue
        seen_validation_keys.add(key)
        validation_candidates.append(row)

    if not validation_candidates:
        print("  No final candidates available for validation.")
    else:
        validation_rows = []
        validation_aggregates = []
        validation_holdouts = [10, 20, 30]
        validation_modes = ["realistic", "harsh"]

        print(f"  {'Cand':>4}  {'Params':<38} {'Split':>5} {'Mode':>10} {'Trades':>6} "
              f"{'Ret':>9} {'Sharpe':>7} {'DD':>8} {'Rob':>10}")
        print("  " + "-" * 114)

        for idx, candidate in enumerate(validation_candidates, start=1):
            cand_id = f"C{idx}"
            cand_param_str = _candidate_param_str(candidate)
            rob_summary = _robustness_summary(candidate)
            candidate_runs = []

            for holdout_pct in validation_holdouts:
                for validation_mode in validation_modes:
                    vr = _validate_candidate_holdout(candidate, holdout_pct, validation_mode)
                    candidate_runs.append(vr)
                    validation_rows.append({"candidate_id": cand_id, **vr})
                    vm = vr["metrics"] or {}
                    print(f"  {cand_id:>4}  {cand_param_str:<38} {holdout_pct:>4}% {validation_mode:>10} "
                          f"{int(vm.get('total_trades', 0) or 0):>6d} "
                          f"{float(vm.get('total_return_pct', 0.0) or 0.0):>+8.2f}% "
                          f"{float(vm.get('sharpe_ratio', 0.0) or 0.0):>7.1f} "
                          f"{float(vm.get('max_drawdown_pct', 0.0) or 0.0):>7.2f}% "
                          f"{rob_summary:>10}")

            returns = [float((run["metrics"] or {}).get("total_return_pct", 0.0) or 0.0) for run in candidate_runs]
            sharpes = [float((run["metrics"] or {}).get("sharpe_ratio", 0.0) or 0.0) for run in candidate_runs]
            scores = [float(run.get("score", -9999.0) or 0.0) for run in candidate_runs]
            positive_cells = sum(1 for ret in returns if ret > 0)
            zero_trade_cells = sum(
                1 for run in candidate_runs if int(((run["metrics"] or {}).get("total_trades", 0) or 0)) == 0
            )
            realistic_returns = [returns[i] for i, run in enumerate(candidate_runs) if run["mode"] == "realistic"]
            harsh_returns = [returns[i] for i, run in enumerate(candidate_runs) if run["mode"] == "harsh"]

            validation_aggregates.append({
                "candidate_id": cand_id,
                "candidate": candidate,
                "avg_return_pct": sum(returns) / len(returns) if returns else 0.0,
                "worst_return_pct": min(returns) if returns else 0.0,
                "avg_sharpe": sum(sharpes) / len(sharpes) if sharpes else 0.0,
                "avg_score": sum(scores) / len(scores) if scores else -9999.0,
                "positive_cells": positive_cells,
                "zero_trade_cells": zero_trade_cells,
                "return_range_pct": (max(returns) - min(returns)) if returns else 0.0,
                "realistic_avg_return_pct": (
                    sum(realistic_returns) / len(realistic_returns) if realistic_returns else 0.0
                ),
                "harsh_avg_return_pct": (
                    sum(harsh_returns) / len(harsh_returns) if harsh_returns else 0.0
                ),
            })

        print()
        print(f"  {'Cand':>4}  {'Params':<38} {'AvgRet':>9} {'WorstRet':>10} {'AvgSharpe':>10} "
              f"{'Pos':>5} {'Zero':>5} {'AvgScore':>10}")
        print("  " + "-" * 101)
        for agg in validation_aggregates:
            print(f"  {agg['candidate_id']:>4}  {_candidate_param_str(agg['candidate']):<38} "
                  f"{agg['avg_return_pct']:>+8.2f}% {agg['worst_return_pct']:>+9.2f}% "
                  f"{agg['avg_sharpe']:>10.2f} {agg['positive_cells']:>5d} "
                  f"{agg['zero_trade_cells']:>5d} {agg['avg_score']:>10.2f}")

        best_raw = max(
            validation_aggregates,
            key=lambda row: (row["avg_return_pct"], row["avg_sharpe"], row["worst_return_pct"]),
        )
        best_robust = max(
            validation_aggregates,
            key=lambda row: (
                row["avg_score"],
                row["worst_return_pct"],
                row["positive_cells"],
                -row["zero_trade_cells"],
            ),
        )

        print()
        print("  Recommendation:")
        print(f"    Best raw performer: {best_raw['candidate_id']}  "
              f"{_candidate_param_str(best_raw['candidate'])}  "
              f"(avg_ret={best_raw['avg_return_pct']:+.2f}%, worst={best_raw['worst_return_pct']:+.2f}%, "
              f"avg_sharpe={best_raw['avg_sharpe']:.2f})")
        print(f"    Best robust performer: {best_robust['candidate_id']}  "
              f"{_candidate_param_str(best_robust['candidate'])}  "
              f"(avg_score={best_robust['avg_score']:.2f}, zero_cells={best_robust['zero_trade_cells']}, "
              f"positive_cells={best_robust['positive_cells']}/6)")

        sensitivity_warnings = []
        for agg in validation_aggregates:
            reasons = []
            if agg["return_range_pct"] > 5.0:
                reasons.append(f"split-sensitive (range {agg['return_range_pct']:.2f}%)")
            mode_gap = abs(agg["realistic_avg_return_pct"] - agg["harsh_avg_return_pct"])
            if mode_gap > 3.0:
                reasons.append(f"mode-sensitive (realistic-harsh gap {mode_gap:.2f}%)")
            if agg["zero_trade_cells"] >= 2:
                reasons.append(f"{agg['zero_trade_cells']} zero-trade cells")
            if reasons:
                sensitivity_warnings.append(
                    f"    Warning: {agg['candidate_id']} {_candidate_param_str(agg['candidate'])} -> "
                    + ", ".join(reasons)
                )

        if sensitivity_warnings:
            for warning_line in sensitivity_warnings:
                print(warning_line)
        else:
            print("    No major split-sensitivity or mode-sensitivity warnings.")

        validation_stage = {
            "candidates": [
                {
                    "candidate_id": agg["candidate_id"],
                    "params": {
                        **agg["candidate"]["params"],
                        "max_trade_bars": _candidate_max_trade_bars(agg["candidate"]),
                    },
                    "avg_return_pct": round(agg["avg_return_pct"], 3),
                    "worst_return_pct": round(agg["worst_return_pct"], 3),
                    "avg_sharpe": round(agg["avg_sharpe"], 3),
                    "avg_score": round(agg["avg_score"], 3),
                    "positive_cells": agg["positive_cells"],
                    "zero_trade_cells": agg["zero_trade_cells"],
                }
                for agg in validation_aggregates
            ],
            "runs": [
                {
                    "candidate_id": row["candidate_id"],
                    "holdout_pct": row["holdout_pct"],
                    "mode": row["mode"],
                    "metrics": row["metrics"],
                    "score": round(float(row["score"]), 3),
                }
                for row in validation_rows
            ],
            "best_raw_candidate_id": best_raw["candidate_id"],
            "best_robust_candidate_id": best_robust["candidate_id"],
        }


# ═══════════════════════════════════════════════════════════════════════════
#  SAVE JSON + EXPERIMENT JOURNAL
# ═══════════════════════════════════════════════════════════════════════════
restore()

r = best["result"]
if r and "error" not in r:
    out = {
        "ticker": TICKER,
        "period": f"{START_DATE} → {END_DATE}",
        "train_bars": len(df_raw),
        "holdout_bars": len(df_holdout) if df_holdout is not None else 0,
        "backtest_mode": args.mode,
        "position_sizing": "fixed_10pct",
        "selection_method": "holdout_live_score" if df_holdout is not None else "train_live_score",
        "live_trading": {
            "median_price": round(median_price, 2),
            "est_spread": round(est_spread, 3),
            "min_stop_pct_used": MIN_STOP_PCT,
        },
        "presets": presets,
    }
    if validation_stage:
        out["validation_best"] = validation_stage

    outfile = f"sweep_results_{TICKER}.json"
    with open(outfile, "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\n  Results saved -> {outfile}")

    # ── Append to experiment journal ────────────────────────────────────
    bo = presets.get("best_overall", {})
    journal_entry = {
        "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "ticker": TICKER,
        "period": f"{START_DATE} → {END_DATE}",
        "backtest_mode": args.mode,
        "position_sizing": "fixed_10pct",
        "selection_method": out["selection_method"],
        "params": bo.get("params", {}),
        "train": bo.get("train", {}),
        "holdout": bo.get("holdout", {}),
        "robustness": bo.get("robustness", {}),
        "holdout_score": bo.get("holdout_score"),
        "train_score": bo.get("train_score"),
    }
    try:
        import subprocess as _sp
        _hash = _sp.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=os.path.dirname(__file__) or ".",
            stderr=_sp.DEVNULL,
        ).decode().strip()
        journal_entry["git_hash"] = _hash
    except Exception:
        pass
    journal_path = os.path.join(os.path.dirname(__file__) or ".", "experiments.jsonl")
    with open(journal_path, "a") as jf:
        jf.write(json.dumps(journal_entry, default=str) + "\n")
    print(f"  Experiment logged -> experiments.jsonl")

    # ── Apply params to config.py? ──────────────────────────────────────
    if args.apply:
        answer = "y"
    else:
        try:
            answer = input("\n  Apply best_overall params to config.py? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = "n"

    if answer in ("y", "yes"):
        config_path = os.path.join(os.path.dirname(__file__), "config.py")
        with open(config_path, "r") as f:
            cfg_text = f.read()

        bp = presets.get("best_overall", {}).get("params", {})
        param_map = {
            f"TARGET_GAIN_PCT_{MODE_NAME}":     bp.get("target_gain_pct", best["target"]),
            f"STOP_LOSS_PCT_{MODE_NAME}":       bp.get("stop_loss_pct", best["stop"]),
            f"RSI_OVERSOLD_{MODE_NAME}":        bp.get("rsi_oversold", best["rsi"]),
            f"VWAP_ZSCORE_THRESH_{MODE_NAME}":  bp.get("vwap_zscore_thresh", best["vwap"]),
            "MAX_TRADE_BARS":                    bp.get("max_trade_bars", best.get("max_trade_bars", _default_max_trade_bars)),
        }

        updated = 0
        for param, value in param_map.items():
            pattern = rf'^({param}\s*=\s*)([^\s#]+)(.*)'
            if isinstance(value, int):
                new_val = str(value)
            elif isinstance(value, float):
                if "VWAP" in param or "RSI" in param:
                    new_val = f"{value}"
                else:
                    new_val = f"{value:.6f}".rstrip("0").rstrip(".")
                    if "." in new_val:
                        decimals = len(new_val.split(".")[1])
                        if decimals < 4:
                            new_val = f"{value:.4f}"
            else:
                new_val = str(value)

            new_text, count = re.subn(
                pattern,
                rf'\g<1>{new_val}\3',
                cfg_text,
                flags=re.MULTILINE,
            )
            if count > 0:
                cfg_text = new_text
                updated += count

        if updated > 0:
            with open(config_path, "w") as f:
                f.write(cfg_text)
            print(f"\n  Updated {updated} params in config.py:")
            for param, value in param_map.items():
                if isinstance(value, float) and "VWAP" not in param and "RSI" not in param:
                    print(f"    {param} = {value:.4f}  ({value*100:.2f}%)")
                else:
                    print(f"    {param} = {value}")
        else:
            print(f"\n  No matching params found in config.py for {MODE_NAME}.")
            print(f"  You may need to add a {MODE_NAME} section manually.")
else:
    print("  No valid results found. The ticker may not have enough data or liquidity.")

print()

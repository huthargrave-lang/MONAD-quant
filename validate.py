"""
validate.py — Stress-test companion to sweep.py

Consumes sweep_results_{TICKER}.json (or custom params) and runs deeper
validation that sweep doesn't cover:

  1. Rolling walk-forward windows (is the edge stable across time?)
  2. Monte Carlo trade-order shuffle (is profit from signal or luck?)
  3. Regime-split analysis (does it work in bull AND bear?)
  4. Drawdown profile (max DD duration, worst month, consecutive losses)
  5. Slippage sensitivity (how fragile is the R:R to execution costs?)

Usage:
  python validate.py TQQQ                          # validate all presets from sweep JSON
  python validate.py TQQQ --preset best_overall     # validate one preset
  python validate.py TQQQ --target 1.0 --stop 0.5   # validate custom params
  python validate.py TQQQ --skip-mc --skip-slippage  # skip expensive tests
"""

import argparse
import contextlib
import io
import json
import os
import sys
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

import config
from src.data.fetcher import fetch_yfinance
from src.backtest.runner import run_backtest

# ═══════════════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════════════
parser = argparse.ArgumentParser(
    description="MONAD Quant — Sweep Validation & Stress Testing",
    formatter_class=argparse.RawDescriptionHelpFormatter,
)
parser.add_argument("ticker", help="Ticker symbol (e.g., TQQQ, SOXL, QQQ)")
parser.add_argument("--start", default=None, help="Start date (default: 2yr ago)")
parser.add_argument("--end", default=None, help="End date (default: today)")
parser.add_argument("--preset", default=None,
                    help="Validate one preset (best_overall, most_robust, high_rr, high_trade_count)")
parser.add_argument("--target", type=float, default=None, help="Custom target %% (e.g., 1.0)")
parser.add_argument("--stop", type=float, default=None, help="Custom stop %% (e.g., 0.5)")
parser.add_argument("--rsi", type=int, default=None, help="Custom RSI oversold")
parser.add_argument("--vwap", type=float, default=None, help="Custom VWAP z-score threshold")
parser.add_argument("--max-trade-bars", type=int, default=20, help="MAX_TRADE_BARS (default: 20)")
parser.add_argument("--mode", default="realistic", choices=["optimistic", "realistic", "harsh"])
parser.add_argument("--mc-samples", type=int, default=1000, help="Monte Carlo samples (default: 1000)")
parser.add_argument("--windows", type=int, default=4, help="Rolling walk-forward windows (default: 4)")
parser.add_argument("--skip-mc", action="store_true", help="Skip Monte Carlo test")
parser.add_argument("--skip-slippage", action="store_true", help="Skip slippage sensitivity")
parser.add_argument("--skip-regime", action="store_true", help="Skip regime-split test")
parser.add_argument("--skip-rolling", action="store_true", help="Skip rolling walk-forward")
args = parser.parse_args()

TICKER = args.ticker.upper()
END_DATE = args.end or datetime.now().strftime("%Y-%m-%d")
START_DATE = args.start or (datetime.now() - timedelta(days=710)).strftime("%Y-%m-%d")


# ═══════════════════════════════════════════════════════════════════════════
#  TICKER SETUP — same injection pattern as sweep.py
# ═══════════════════════════════════════════════════════════════════════════
MODE_NAME = f"{TICKER}_HOURLY"

_defaults = {
    f"RSI_PERIOD_{MODE_NAME}":          7,
    f"RSI_OVERSOLD_{MODE_NAME}":        80,
    f"RSI_OVERBOUGHT_{MODE_NAME}":      62,
    f"MACD_FAST_{MODE_NAME}":           6,
    f"MACD_SLOW_{MODE_NAME}":           13,
    f"MACD_SIGNAL_{MODE_NAME}":         4,
    f"VWAP_WINDOW_{MODE_NAME}":         10,
    f"VWAP_ZSCORE_THRESH_{MODE_NAME}":  0.3,
    f"BB_WINDOW_{MODE_NAME}":           14,
}
for k, v in _defaults.items():
    if not hasattr(config, k):
        setattr(config, k, v)

if MODE_NAME not in config.ASSETS:
    config.ASSETS[MODE_NAME] = {
        "type":               f"etf_hourly_{TICKER.lower()}",
        "target_gain_pct":    0.010,
        "stop_loss_pct":      0.005,
        "require_signals":    1,
        "rsi_oversold":       _defaults[f"RSI_OVERSOLD_{MODE_NAME}"],
        "rsi_overbought":     _defaults[f"RSI_OVERBOUGHT_{MODE_NAME}"],
        "vwap_zscore_thresh": _defaults[f"VWAP_ZSCORE_THRESH_{MODE_NAME}"],
    }

config.ACTIVE_MODE = MODE_NAME
config.DEFAULT_ASSET = MODE_NAME
config.PLOT_RESULTS = False
config.VERBOSE_SIGNALS = False
config.POSITION_SIZING_MODE = "fixed"
config.FIXED_POSITION_PCT = 0.10
config.USE_ADAPTIVE_KELLY = False
if MODE_NAME not in config._MODE_TO_ASSET:
    config._MODE_TO_ASSET[MODE_NAME] = MODE_NAME


# ═══════════════════════════════════════════════════════════════════════════
#  DATA FETCHER — shares cache with sweep.py via src.data.fetcher
# ═══════════════════════════════════════════════════════════════════════════
from src.data.fetcher import _ensure_cache_dir, _cache_path, _cache_is_fresh

def fetch_ticker_hourly(ticker, start, end):
    _ensure_cache_dir()
    cache_file = _cache_path(ticker, "1h")
    start_dt, end_dt = pd.Timestamp(start), pd.Timestamp(end)
    if os.path.exists(cache_file) and _cache_is_fresh(cache_file):
        df = pd.read_csv(cache_file, index_col=0, parse_dates=True)
        if len(df) > 0 and df.index[0] <= start_dt and df.index[-1] >= end_dt - timedelta(days=2):
            print(f"  [cache] Loading {ticker} hourly ({len(df)} bars)")
            return df.loc[start:end]
    df = fetch_yfinance(symbol=ticker, start=start, end=end, interval="1h")
    df = df.between_time("09:30", "16:00")
    df.to_csv(cache_file)
    print(f"  [cache] Saved {ticker} hourly to cache ({len(df)} bars)")
    return df.loc[start:end]


# ═══════════════════════════════════════════════════════════════════════════
#  BACKTEST RUNNER — quiet single-run helper
# ═══════════════════════════════════════════════════════════════════════════
def _set_params(target, stop, rsi, vwap, max_trade_bars):
    """Push params into both config attrs and ASSETS dict (dual-sync)."""
    setattr(config, f"RSI_OVERSOLD_{MODE_NAME}", rsi)
    config.ASSETS[MODE_NAME]["rsi_oversold"] = rsi
    setattr(config, f"VWAP_ZSCORE_THRESH_{MODE_NAME}", vwap)
    config.ASSETS[MODE_NAME]["vwap_zscore_thresh"] = vwap
    config.ASSETS[MODE_NAME]["target_gain_pct"] = target
    config.ASSETS[MODE_NAME]["stop_loss_pct"] = stop
    config.MAX_TRADE_BARS = max_trade_bars


def run_quiet(df, target, stop, rsi, vwap, max_trade_bars=20,
              backtest_mode="realistic"):
    """Run a single backtest silently. Returns result dict or None."""
    _set_params(target, stop, rsi, vwap, max_trade_bars)
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
                backtest_mode=backtest_mode,
            )
        return r if r else None
    except Exception as e:
        return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════
#  PARAM LOADING — from sweep JSON or CLI overrides
# ═══════════════════════════════════════════════════════════════════════════
def load_candidates_from_sweep(ticker):
    """Load presets from sweep_results_{ticker}.json. Returns list of (label, params) tuples."""
    path = os.path.join(os.path.dirname(__file__) or ".", f"sweep_results_{ticker}.json")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        data = json.load(f)
    candidates = []
    for label, preset in data.get("presets", {}).items():
        p = preset.get("params", {})
        candidates.append((label, {
            "target": p.get("target_gain_pct", 0.01),
            "stop":   p.get("stop_loss_pct", 0.005),
            "rsi":    int(p.get("rsi_oversold", 80)),
            "vwap":   p.get("vwap_zscore_thresh", 0.5),
            "mtb":    int(p.get("max_trade_bars", 20)),
        }))
    return candidates


def build_candidate_list():
    """Build list of (label, params) from CLI args or sweep JSON."""
    # Custom params from CLI
    if args.target is not None and args.stop is not None:
        return [("custom", {
            "target": args.target / 100,
            "stop":   args.stop / 100,
            "rsi":    args.rsi or 80,
            "vwap":   args.vwap or 0.5,
            "mtb":    args.max_trade_bars,
        })]

    # Load from sweep JSON
    all_candidates = load_candidates_from_sweep(TICKER)
    if not all_candidates:
        print(f"  No sweep_results_{TICKER}.json found and no --target/--stop given.")
        print(f"  Run: python sweep.py {TICKER}    OR    python validate.py {TICKER} --target 1.0 --stop 0.5")
        sys.exit(1)

    if args.preset:
        match = [(l, p) for l, p in all_candidates if l == args.preset]
        if not match:
            print(f"  Preset '{args.preset}' not found. Available: {[l for l,_ in all_candidates]}")
            sys.exit(1)
        return match

    return all_candidates


# ═══════════════════════════════════════════════════════════════════════════
#  TEST 1: Rolling Walk-Forward Windows
# ═══════════════════════════════════════════════════════════════════════════
def test_rolling_windows(df, params, n_windows=4):
    """Split data into N equal windows, backtest each independently.

    Returns dict with per-window metrics and stability assessment.
    A stable strategy should perform similarly across all windows.
    """
    n = len(df)
    window_size = n // n_windows
    results = []

    for i in range(n_windows):
        start_idx = i * window_size
        end_idx = start_idx + window_size if i < n_windows - 1 else n
        window_df = df.iloc[start_idx:end_idx].copy()

        if len(window_df) < 50:
            results.append({"window": i + 1, "error": "too_few_bars"})
            continue

        r = run_quiet(window_df, params["target"], params["stop"],
                      params["rsi"], params["vwap"], params["mtb"], args.mode)

        if r is None or "error" in (r or {}):
            results.append({
                "window": i + 1,
                "start": str(window_df.index[0].date()),
                "end": str(window_df.index[-1].date()),
                "bars": len(window_df),
                "trades": 0, "return_pct": 0, "sharpe": 0, "win_rate": 0,
                "max_dd_pct": 0,
            })
            continue

        mo = r["monthly_returns"]
        avg_mo = float(mo[mo != 0].mean()) * 100 if len(mo[mo != 0]) > 0 else 0

        results.append({
            "window": i + 1,
            "start": str(window_df.index[0].date()),
            "end": str(window_df.index[-1].date()),
            "bars": len(window_df),
            "trades": r["total_trades"],
            "return_pct": round(r["total_return"] * 100, 2),
            "sharpe": r["sharpe_ratio"],
            "win_rate": round(r["win_rate"] * 100, 1),
            "max_dd_pct": round(r["max_drawdown"] * 100, 2),
            "avg_monthly_pct": round(avg_mo, 2),
        })

    returns = [w["return_pct"] for w in results if w.get("trades", 0) > 0]
    sharpes = [w["sharpe"] for w in results if w.get("trades", 0) > 0]
    positive_windows = sum(1 for r in returns if r > 0)

    summary = {
        "windows": results,
        "positive_windows": f"{positive_windows}/{len(returns)}",
        "return_range_pct": round(max(returns) - min(returns), 2) if returns else 0,
        "return_std_pct": round(float(np.std(returns)), 2) if returns else 0,
        "sharpe_range": round(max(sharpes) - min(sharpes), 1) if sharpes else 0,
        "stable": len(returns) > 0 and positive_windows == len(returns) and (max(returns) - min(returns)) < 10,
    }
    return summary


# ═══════════════════════════════════════════════════════════════════════════
#  TEST 2: Monte Carlo Trade-Order Shuffle
# ═══════════════════════════════════════════════════════════════════════════
def _equity_max_drawdown(returns_arr, initial=100_000):
    """Compute max drawdown from a sequence of trade returns."""
    equity = initial * np.cumprod(1 + returns_arr)
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / peak
    return float(dd.min())


def test_monte_carlo(trade_returns, n_samples=1000, initial=100_000):
    """Reshuffle trade order N times, compare MAX DRAWDOWN distributions.

    Terminal compound return is identical for all shuffles (multiplication is
    commutative), so we test path-dependent metrics instead:
    - Max drawdown: is the realized DD better than most random orderings?
    - If realized DD is worse than P75 of shuffles, the strategy's drawdown
      profile may be order-dependent (unlucky sequencing).
    """
    if len(trade_returns) < 5:
        return {"error": "too_few_trades", "samples": 0}

    returns_arr = trade_returns.values
    realized_dd = _equity_max_drawdown(returns_arr, initial)
    realized_return = float((np.prod(1 + returns_arr) - 1) * 100)
    shuffle_dds = np.empty(n_samples)

    rng = np.random.default_rng(seed=42)
    for i in range(n_samples):
        shuffled = rng.permutation(returns_arr)
        shuffle_dds[i] = _equity_max_drawdown(shuffled, initial)

    shuffle_dds_pct = shuffle_dds * 100
    realized_dd_pct = realized_dd * 100
    # Higher percentile = realized DD is less severe than most shuffles (good)
    dd_percentile = float(np.mean(shuffle_dds <= realized_dd))

    return {
        "samples": n_samples,
        "realized_return_pct": round(realized_return, 2),
        "realized_max_dd_pct": round(realized_dd_pct, 2),
        "shuffle_dd_p05_pct": round(float(np.percentile(shuffle_dds_pct, 5)), 2),
        "shuffle_dd_p25_pct": round(float(np.percentile(shuffle_dds_pct, 25)), 2),
        "shuffle_dd_p50_pct": round(float(np.percentile(shuffle_dds_pct, 50)), 2),
        "shuffle_dd_p75_pct": round(float(np.percentile(shuffle_dds_pct, 75)), 2),
        "shuffle_dd_p95_pct": round(float(np.percentile(shuffle_dds_pct, 95)), 2),
        "dd_percentile_rank": round(dd_percentile, 3),
        "lucky_sequencing": dd_percentile > 0.75,
        "unlucky_sequencing": dd_percentile < 0.25,
    }


# ═══════════════════════════════════════════════════════════════════════════
#  TEST 3: Regime-Split Analysis
# ═══════════════════════════════════════════════════════════════════════════
def test_regime_split(df, params):
    """Run backtest on full data, then break trades by regime.

    Reports trade count, win rate, and contribution per regime state.
    """
    r = run_quiet(df, params["target"], params["stop"],
                  params["rsi"], params["vwap"], params["mtb"], args.mode)

    if r is None or "error" in (r or {}) or r.get("total_trades", 0) == 0:
        return {"error": "no_trades"}

    trades_df = r.get("trades_df", pd.DataFrame())
    if trades_df.empty or "regime" not in trades_df.columns:
        # Fall back to trend_regime if regime column not available
        if "trend_regime" in trades_df.columns:
            regime_col = "trend_regime"
        else:
            return {
                "note": "No regime column in trades_df",
                "total_trades": r["total_trades"],
                "bull_trades": r.get("bull_trades", 0),
                "bear_trades": r.get("bear_trades", 0),
            }
    else:
        regime_col = "regime"

    regime_stats = {}
    for regime_val, grp in trades_df.groupby(regime_col):
        wins = (grp["return"] > 0).sum()
        total = len(grp)
        avg_ret = grp["return"].mean() * 100
        regime_stats[str(regime_val)] = {
            "trades": total,
            "win_rate_pct": round(wins / total * 100, 1) if total > 0 else 0,
            "avg_return_pct": round(avg_ret, 3),
            "total_contribution_pct": round(grp["return"].sum() * 100, 2),
        }

    warnings = []
    for regime, stats in regime_stats.items():
        if stats["trades"] < 3:
            warnings.append(f"Regime {regime}: only {stats['trades']} trades (low confidence)")

    return {
        "regimes": regime_stats,
        "total_trades": r["total_trades"],
        "warnings": warnings,
    }


# ═══════════════════════════════════════════════════════════════════════════
#  TEST 4: Drawdown & Streak Profile
# ═══════════════════════════════════════════════════════════════════════════
def test_drawdown_profile(result):
    """Analyze drawdown depth, duration, and consecutive loss streaks."""
    if result is None or "error" in (result or {}):
        return {"error": "no_result"}

    equity = result.get("equity_curve", pd.Series(dtype=float))
    trade_returns = result.get("trade_returns", pd.Series(dtype=float))
    monthly = result.get("monthly_returns", pd.Series(dtype=float))

    if len(equity) < 2:
        return {"error": "no_equity_curve"}

    # Drawdown series
    peak = equity.cummax()
    dd = (equity - peak) / peak
    max_dd_pct = round(float(dd.min()) * 100, 3)

    # Drawdown duration (in trade-steps, not calendar time)
    in_dd = dd < 0
    dd_durations = []
    current_duration = 0
    for is_dd in in_dd:
        if is_dd:
            current_duration += 1
        else:
            if current_duration > 0:
                dd_durations.append(current_duration)
            current_duration = 0
    if current_duration > 0:
        dd_durations.append(current_duration)

    # Consecutive loss streak
    if len(trade_returns) > 0:
        losses = (trade_returns <= 0).astype(int).values
        max_streak = 0
        current = 0
        for l in losses:
            if l:
                current += 1
                max_streak = max(max_streak, current)
            else:
                current = 0
    else:
        max_streak = 0

    # Monthly stats
    active_months = monthly[monthly != 0] if len(monthly) > 0 else pd.Series(dtype=float)
    worst_month = round(float(active_months.min()) * 100, 2) if len(active_months) > 0 else 0
    best_month = round(float(active_months.max()) * 100, 2) if len(active_months) > 0 else 0
    month_std = round(float(active_months.std()) * 100, 2) if len(active_months) > 1 else 0
    neg_months = int((active_months < 0).sum())

    return {
        "max_drawdown_pct": max_dd_pct,
        "max_dd_duration_trades": max(dd_durations) if dd_durations else 0,
        "avg_dd_duration_trades": round(float(np.mean(dd_durations)), 1) if dd_durations else 0,
        "num_drawdown_periods": len(dd_durations),
        "max_consecutive_losses": max_streak,
        "worst_month_pct": worst_month,
        "best_month_pct": best_month,
        "monthly_return_std_pct": month_std,
        "negative_months": neg_months,
        "total_active_months": len(active_months),
    }


# ═══════════════════════════════════════════════════════════════════════════
#  TEST 5: Slippage Sensitivity
# ═══════════════════════════════════════════════════════════════════════════
def test_slippage_sensitivity(df, params):
    """Re-run backtest across multiple slippage levels.

    Tests [0bps, 2bps (realistic default), 5bps, 10bps].
    Reports return degradation curve — fragile strategies collapse quickly.
    """
    from src.backtest.runner import BACKTEST_MODES

    slippage_levels = [0.0, 0.0002, 0.0005, 0.0010]
    results = []

    for slip in slippage_levels:
        mode_key = args.mode
        original_slip = BACKTEST_MODES[mode_key]["slippage_pct"]
        BACKTEST_MODES[mode_key]["slippage_pct"] = slip
        try:
            r = run_quiet(df, params["target"], params["stop"],
                          params["rsi"], params["vwap"], params["mtb"], args.mode)
        finally:
            BACKTEST_MODES[mode_key]["slippage_pct"] = original_slip

        if r and "error" not in r:
            mo = r["monthly_returns"]
            avg_mo = float(mo[mo != 0].mean()) * 100 if len(mo[mo != 0]) > 0 else 0
            results.append({
                "slippage_bps": round(slip * 10000),
                "return_pct": round(r["total_return"] * 100, 2),
                "sharpe": r["sharpe_ratio"],
                "win_rate_pct": round(r["win_rate"] * 100, 1),
                "avg_monthly_pct": round(avg_mo, 2),
            })
        else:
            results.append({
                "slippage_bps": round(slip * 10000),
                "return_pct": 0, "sharpe": 0, "win_rate_pct": 0, "avg_monthly_pct": 0,
            })

    # Compute fragility: return drop per bps of slippage
    if len(results) >= 2 and results[0]["return_pct"] != 0:
        base = results[0]["return_pct"]
        worst = results[-1]["return_pct"]
        total_bps = results[-1]["slippage_bps"] - results[0]["slippage_bps"]
        degradation_per_bps = round((base - worst) / total_bps, 3) if total_bps > 0 else 0
    else:
        degradation_per_bps = 0

    return {
        "levels": results,
        "degradation_per_bps": degradation_per_bps,
        "fragile": degradation_per_bps > 0.5,
    }


# ═══════════════════════════════════════════════════════════════════════════
#  VERDICT — combine all tests into a confidence rating
# ═══════════════════════════════════════════════════════════════════════════
def compute_verdict(rolling, mc, regime, drawdown, slippage):
    """Combine test results into HIGH / MEDIUM / LOW confidence."""
    warnings = []
    score = 100  # start at 100, deduct for issues

    # Rolling walk-forward
    if rolling and not rolling.get("error"):
        if not rolling.get("stable"):
            score -= 20
            warnings.append("Unstable across time windows")
        pos = rolling.get("positive_windows", "0/0")
        parts = pos.split("/")
        if len(parts) == 2 and int(parts[1]) > 0:
            frac = int(parts[0]) / int(parts[1])
            if frac < 0.75:
                score -= 15
                warnings.append(f"Only {pos} windows profitable")

    # Monte Carlo (drawdown path analysis)
    if mc and not mc.get("error"):
        if mc.get("unlucky_sequencing"):
            score -= 20
            warnings.append(f"MC DD percentile {mc['dd_percentile_rank']:.0%} — realized DD worse than most shuffles")
        if mc.get("lucky_sequencing"):
            score -= 10
            warnings.append(f"MC DD percentile {mc['dd_percentile_rank']:.0%} — realized DD unusually good (may not persist)")

    # Regime split
    if regime and not regime.get("error"):
        for w in regime.get("warnings", []):
            score -= 5
            warnings.append(w)

    # Drawdown
    if drawdown and not drawdown.get("error"):
        if drawdown.get("max_consecutive_losses", 0) > 8:
            score -= 10
            warnings.append(f"Max {drawdown['max_consecutive_losses']} consecutive losses")
        if drawdown.get("worst_month_pct", 0) < -5:
            score -= 15
            warnings.append(f"Worst month {drawdown['worst_month_pct']}%")
        if drawdown.get("negative_months", 0) > drawdown.get("total_active_months", 1) * 0.3:
            score -= 10
            warnings.append(f"{drawdown['negative_months']}/{drawdown['total_active_months']} months negative")

    # Slippage
    if slippage and not slippage.get("error"):
        if slippage.get("fragile"):
            score -= 20
            warnings.append(f"Fragile to slippage ({slippage['degradation_per_bps']}%/bps)")

    score = max(0, min(100, score))
    if score >= 75:
        level = "HIGH"
    elif score >= 50:
        level = "MEDIUM"
    else:
        level = "LOW"

    return {
        "confidence": level,
        "score": score,
        "warnings": warnings,
    }


# ═══════════════════════════════════════════════════════════════════════════
#  PRETTY PRINT — human-readable summary
# ═══════════════════════════════════════════════════════════════════════════
def print_summary(label, params, baseline, rolling, mc, regime, drawdown, slippage, verdict):
    """Print a formatted summary of all validation tests."""
    print(f"\n{'─'*70}")
    print(f"  CANDIDATE: {label}")
    print(f"  Params: target={params['target']*100:.2f}%  stop={params['stop']*100:.3f}%  "
          f"RSI={params['rsi']}  VWAP={params['vwap']}  MTB={params['mtb']}")
    print(f"{'─'*70}")

    # Baseline
    if baseline and "error" not in (baseline or {}):
        print(f"\n  BASELINE (full window):")
        print(f"    Trades: {baseline['total_trades']}  |  WR: {baseline['win_rate']*100:.1f}%  |  "
              f"Return: {baseline['total_return']*100:.2f}%  |  Sharpe: {baseline['sharpe_ratio']:.1f}  |  "
              f"Max DD: {baseline['max_drawdown']*100:.2f}%")

    # Rolling windows
    if rolling and not rolling.get("error"):
        print(f"\n  ROLLING WALK-FORWARD ({len(rolling['windows'])} windows):")
        for w in rolling["windows"]:
            if w.get("trades", 0) > 0:
                print(f"    W{w['window']}: {w['start']} → {w['end']}  "
                      f"trades={w['trades']:3d}  WR={w['win_rate']:5.1f}%  "
                      f"ret={w['return_pct']:+6.2f}%  Sharpe={w['sharpe']:5.1f}")
            else:
                print(f"    W{w['window']}: {w.get('start','?')} → {w.get('end','?')}  NO TRADES")
        status = "STABLE" if rolling["stable"] else "UNSTABLE"
        print(f"    → {rolling['positive_windows']} positive | "
              f"range={rolling['return_range_pct']:.1f}%  std={rolling['return_std_pct']:.1f}%  [{status}]")

    # Monte Carlo (drawdown path analysis)
    if mc and not mc.get("error"):
        print(f"\n  MONTE CARLO — Drawdown Path Analysis ({mc['samples']} shuffles):")
        print(f"    Realized Max DD: {mc['realized_max_dd_pct']:+.2f}%")
        print(f"    Shuffle DD distribution: "
              f"P5={mc['shuffle_dd_p05_pct']:+.2f}%  P25={mc['shuffle_dd_p25_pct']:+.2f}%  "
              f"P50={mc['shuffle_dd_p50_pct']:+.2f}%  P75={mc['shuffle_dd_p75_pct']:+.2f}%  "
              f"P95={mc['shuffle_dd_p95_pct']:+.2f}%")
        status = "OK"
        if mc.get("unlucky_sequencing"):
            status = "⚠ UNLUCKY SEQUENCING (DD worse than 75% of shuffles)"
        elif mc.get("lucky_sequencing"):
            status = "~ LUCKY SEQUENCING (DD better than 75% of shuffles — may not persist)"
        print(f"    DD Percentile: {mc['dd_percentile_rank']:.0%}  [{status}]")

    # Regime split
    if regime and not regime.get("error") and regime.get("regimes"):
        print(f"\n  REGIME SPLIT:")
        for name, s in sorted(regime["regimes"].items()):
            print(f"    {name:>12}: trades={s['trades']:3d}  WR={s['win_rate_pct']:5.1f}%  "
                  f"avg_ret={s['avg_return_pct']:+.3f}%  contribution={s['total_contribution_pct']:+.2f}%")
        for w in regime.get("warnings", []):
            print(f"    ⚠ {w}")

    # Drawdown profile
    if drawdown and not drawdown.get("error"):
        print(f"\n  DRAWDOWN PROFILE:")
        print(f"    Max DD: {drawdown['max_drawdown_pct']:.2f}%  |  "
              f"Max streak: {drawdown['max_consecutive_losses']} consecutive losses")
        print(f"    Worst month: {drawdown['worst_month_pct']:+.2f}%  |  "
              f"Best month: {drawdown['best_month_pct']:+.2f}%  |  "
              f"Monthly std: {drawdown['monthly_return_std_pct']:.2f}%")
        print(f"    Negative months: {drawdown['negative_months']}/{drawdown['total_active_months']}")

    # Slippage sensitivity
    if slippage and not slippage.get("error"):
        print(f"\n  SLIPPAGE SENSITIVITY:")
        for lvl in slippage["levels"]:
            print(f"    {lvl['slippage_bps']:2d} bps: ret={lvl['return_pct']:+7.2f}%  "
                  f"Sharpe={lvl['sharpe']:5.1f}  WR={lvl['win_rate_pct']:.1f}%")
        status = "FRAGILE" if slippage["fragile"] else "ROBUST"
        print(f"    → Degradation: {slippage['degradation_per_bps']:.3f}%/bps  [{status}]")

    # Verdict
    print(f"\n  {'='*50}")
    v = verdict
    icon = {"HIGH": "✓", "MEDIUM": "~", "LOW": "✗"}[v["confidence"]]
    print(f"  VERDICT: {icon} {v['confidence']} CONFIDENCE (score: {v['score']}/100)")
    for w in v["warnings"]:
        print(f"    ⚠ {w}")
    print()


# ═══════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print(f"\n{'='*70}")
    print(f"  MONAD QUANT — VALIDATE: {TICKER}")
    print(f"  Period: {START_DATE} → {END_DATE}  |  Mode: {args.mode}")
    print(f"{'='*70}\n")

    df_full = fetch_ticker_hourly(TICKER, START_DATE, END_DATE)
    print(f"  Loaded {len(df_full)} bars\n")

    if len(df_full) < 100:
        print(f"  ERROR: Only {len(df_full)} bars. Need >= 100.")
        sys.exit(1)

    candidates = build_candidate_list()
    print(f"  Validating {len(candidates)} candidate(s): {[l for l,_ in candidates]}")

    all_results = {}

    for label, params in candidates:
        print(f"\n{'='*70}")
        print(f"  Running tests for: {label}")
        print(f"{'='*70}")

        # Baseline: full-window backtest
        print("  [1/5] Baseline backtest...")
        baseline = run_quiet(df_full, params["target"], params["stop"],
                             params["rsi"], params["vwap"], params["mtb"], args.mode)

        # Test 1: Rolling walk-forward
        rolling = None
        if not args.skip_rolling:
            print(f"  [2/5] Rolling walk-forward ({args.windows} windows)...")
            rolling = test_rolling_windows(df_full, params, args.windows)
        else:
            print("  [2/5] Rolling walk-forward... SKIPPED")

        # Test 2: Monte Carlo
        mc = None
        if not args.skip_mc and baseline and "error" not in (baseline or {}):
            print(f"  [3/5] Monte Carlo ({args.mc_samples} samples)...")
            mc = test_monte_carlo(baseline["trade_returns"], args.mc_samples)
        else:
            print("  [3/5] Monte Carlo... SKIPPED")

        # Test 3: Regime split
        regime = None
        if not args.skip_regime:
            print("  [4/5] Regime-split analysis...")
            regime = test_regime_split(df_full, params)
        else:
            print("  [4/5] Regime split... SKIPPED")

        # Test 4: Drawdown profile (always runs — uses baseline result)
        print("  [5a/5] Drawdown profile...")
        drawdown = test_drawdown_profile(baseline) if baseline else None

        # Test 5: Slippage sensitivity
        slippage = None
        if not args.skip_slippage:
            print("  [5b/5] Slippage sensitivity (4 levels)...")
            slippage = test_slippage_sensitivity(df_full, params)
        else:
            print("  [5b/5] Slippage sensitivity... SKIPPED")

        # Verdict
        verdict = compute_verdict(rolling, mc, regime, drawdown, slippage)

        # Print
        print_summary(label, params, baseline, rolling, mc, regime, drawdown, slippage, verdict)

        # Collect for JSON output
        candidate_result = {
            "label": label,
            "params": {
                "target_gain_pct": params["target"],
                "stop_loss_pct": params["stop"],
                "rsi_oversold": params["rsi"],
                "vwap_zscore_thresh": params["vwap"],
                "max_trade_bars": params["mtb"],
            },
            "verdict": verdict,
        }
        if baseline and "error" not in (baseline or {}):
            candidate_result["baseline"] = {
                "total_return_pct": round(baseline["total_return"] * 100, 2),
                "sharpe": baseline["sharpe_ratio"],
                "max_dd_pct": round(baseline["max_drawdown"] * 100, 2),
                "trades": baseline["total_trades"],
                "win_rate_pct": round(baseline["win_rate"] * 100, 1),
            }
        if rolling:
            candidate_result["rolling_windows"] = rolling
        if mc:
            candidate_result["monte_carlo"] = mc
        if regime:
            candidate_result["regime_split"] = regime
        if drawdown:
            candidate_result["drawdown_profile"] = drawdown
        if slippage:
            candidate_result["slippage_sensitivity"] = slippage

        all_results[label] = candidate_result

    # ── Save JSON output ──────────────────────────────────────────────────
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    outfile = f"validate_{TICKER}_{ts}.json"
    output = {
        "ticker": TICKER,
        "period": f"{START_DATE} → {END_DATE}",
        "bars": len(df_full),
        "backtest_mode": args.mode,
        "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "candidates": all_results,
    }
    with open(outfile, "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\n  Results saved → {outfile}")

    # ── Final comparison table ────────────────────────────────────────────
    if len(all_results) > 1:
        print(f"\n{'='*70}")
        print(f"  COMPARISON TABLE")
        print(f"{'='*70}")
        print(f"  {'Preset':<20} {'Return':>8} {'Sharpe':>7} {'WR':>6} {'MC DD%':>7} "
              f"{'Windows':>8} {'Slip':>6} {'Verdict':>8}")
        print(f"  {'─'*20} {'─'*8} {'─'*7} {'─'*6} {'─'*7} {'─'*8} {'─'*6} {'─'*8}")
        for label, cr in all_results.items():
            b = cr.get("baseline", {})
            m = cr.get("monte_carlo", {})
            rw = cr.get("rolling_windows", {})
            sl = cr.get("slippage_sensitivity", {})
            v = cr.get("verdict", {})
            mc_dd = f"{m.get('dd_percentile_rank', 0)*100:.0f}%" if m and not m.get("error") else "N/A"
            print(f"  {label:<20} "
                  f"{b.get('total_return_pct', 0):>+7.1f}% "
                  f"{b.get('sharpe', 0):>6.1f} "
                  f"{b.get('win_rate_pct', 0):>5.1f}% "
                  f"{mc_dd:>7} "
                  f"{rw.get('positive_windows', 'N/A'):>8} "
                  f"{'FRAG' if sl.get('fragile') else 'OK':>6} "
                  f"{v.get('confidence', '?'):>8}")
        print()

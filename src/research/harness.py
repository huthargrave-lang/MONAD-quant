"""
src/research/harness.py — Shared research infrastructure for sweep, validate, autosweep.

Provides reusable functions for:
  - Ticker/mode config injection
  - Hourly data fetching with caching
  - Quiet backtest execution
  - Metrics extraction and scoring
  - Validation test suite (rolling, MC, regime, drawdown, slippage)
  - Confidence rating

Design: all functions are stateless (config mutation is encapsulated in
setup_hourly_mode / set_candidate_params). No CLI parsing at module level.
"""

import contextlib
import io
import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd

import config
from src.data.fetcher import (
    fetch_yfinance,
    _ensure_cache_dir,
    _cache_path,
    _cache_is_fresh,
)
from src.backtest.runner import run_backtest


# ═══════════════════════════════════════════════════════════════════════════
#  Data classes
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class CandidateParams:
    ticker: str
    target: float
    stop: float
    rsi: int = 80
    vwap: float = 0.3
    max_trade_bars: int = 20
    entry_start_hour: int = 9
    entry_end_hour: int = 16
    use_opposing_signal_exit: bool = False
    backtest_mode: str = "realistic"

    @property
    def trade_hours(self) -> tuple:
        return (self.entry_start_hour, self.entry_end_hour)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "CandidateParams":
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in d.items() if k in known})


@dataclass
class CandidateResult:
    params: CandidateParams
    total_return_pct: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    avg_monthly_pct: float = 0.0
    total_trades: int = 0
    win_rate_pct: float = 0.0
    neg_months: int = 0
    total_months: int = 0
    stop_hit_ratio: float = 0.0
    ambiguous_ratio: float = 0.0
    target_hit_count: int = 0
    stop_hit_count: int = 0
    ambiguous_count: int = 0
    time_exit_count: int = 0
    trades_per_month: float = 0.0
    score: float = 0.0
    raw_result: dict = field(default_factory=dict, repr=False)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("raw_result", None)
        d["params"] = self.params.to_dict()
        return d


@dataclass
class ValidationResult:
    rolling: Optional[dict] = None
    monte_carlo: Optional[dict] = None
    regime_split: Optional[dict] = None
    drawdown_profile: Optional[dict] = None
    slippage_sensitivity: Optional[dict] = None
    confidence: str = "LOW"
    confidence_score: int = 0
    warnings: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AutoSweepConfig:
    validate_top: int = 10
    refine_rounds: int = 1
    mc_samples: int = 500
    rolling_windows: int = 4
    holdout_pct: float = 0.20
    backtest_mode: str = "realistic"
    skip_mc: bool = False
    skip_slippage: bool = False
    skip_regime: bool = False
    skip_rolling: bool = False


# ═══════════════════════════════════════════════════════════════════════════
#  Config injection
# ═══════════════════════════════════════════════════════════════════════════

def setup_hourly_mode(ticker: str) -> str:
    """Inject config for a ticker's hourly mode. Returns the MODE_NAME."""
    mode_name = f"{ticker.upper()}_HOURLY"

    defaults = {
        f"RSI_PERIOD_{mode_name}":          7,
        f"RSI_OVERSOLD_{mode_name}":        80,
        f"RSI_OVERBOUGHT_{mode_name}":      62,
        f"MACD_FAST_{mode_name}":           6,
        f"MACD_SLOW_{mode_name}":           13,
        f"MACD_SIGNAL_{mode_name}":         4,
        f"VWAP_WINDOW_{mode_name}":         10,
        f"VWAP_ZSCORE_THRESH_{mode_name}":  0.3,
        f"BB_WINDOW_{mode_name}":           14,
    }
    for k, v in defaults.items():
        if not hasattr(config, k):
            setattr(config, k, v)

    if mode_name not in config.ASSETS:
        config.ASSETS[mode_name] = {
            "type":               f"etf_hourly_{ticker.lower()}",
            "target_gain_pct":    0.010,
            "stop_loss_pct":      0.005,
            "require_signals":    1,
            "rsi_oversold":       defaults[f"RSI_OVERSOLD_{mode_name}"],
            "rsi_overbought":     defaults[f"RSI_OVERBOUGHT_{mode_name}"],
            "vwap_zscore_thresh": defaults[f"VWAP_ZSCORE_THRESH_{mode_name}"],
        }

    config.ACTIVE_MODE = mode_name
    config.DEFAULT_ASSET = mode_name
    config.PLOT_RESULTS = False
    config.VERBOSE_SIGNALS = False
    config.POSITION_SIZING_MODE = "fixed"
    config.FIXED_POSITION_PCT = 0.10
    config.USE_ADAPTIVE_KELLY = False
    if mode_name not in config._MODE_TO_ASSET:
        config._MODE_TO_ASSET[mode_name] = mode_name

    return mode_name


def set_candidate_params(mode_name: str, params: CandidateParams) -> None:
    """Push candidate params into config (dual-sync: attrs + ASSETS dict)."""
    setattr(config, f"RSI_OVERSOLD_{mode_name}", params.rsi)
    config.ASSETS[mode_name]["rsi_oversold"] = params.rsi
    setattr(config, f"VWAP_ZSCORE_THRESH_{mode_name}", params.vwap)
    config.ASSETS[mode_name]["vwap_zscore_thresh"] = params.vwap
    config.ASSETS[mode_name]["target_gain_pct"] = params.target
    config.ASSETS[mode_name]["stop_loss_pct"] = params.stop
    config.MAX_TRADE_BARS = params.max_trade_bars

    if params.use_opposing_signal_exit:
        config.USE_OPPOSING_SIGNAL_EXIT = True
    else:
        config.USE_OPPOSING_SIGNAL_EXIT = False
    config.OPPOSING_SIGNAL_EXIT_MODES = set()


# ═══════════════════════════════════════════════════════════════════════════
#  Data fetching
# ═══════════════════════════════════════════════════════════════════════════

def fetch_ticker_hourly(ticker: str, start: str, end: str) -> pd.DataFrame:
    """Fetch hourly OHLCV data with caching. Strips after-hours bars."""
    _ensure_cache_dir()
    cache_file = _cache_path(ticker, "1h")
    start_dt, end_dt = pd.Timestamp(start), pd.Timestamp(end)

    if os.path.exists(cache_file) and _cache_is_fresh(cache_file):
        df = pd.read_csv(cache_file, index_col=0, parse_dates=True)
        if len(df) > 0 and df.index[0] <= start_dt and df.index[-1] >= end_dt - timedelta(days=2):
            return df.loc[start:end]

    df = fetch_yfinance(symbol=ticker, start=start, end=end, interval="1h")
    df = df.between_time("09:30", "16:00")
    df.to_csv(cache_file)
    return df.loc[start:end]


# ═══════════════════════════════════════════════════════════════════════════
#  Backtest execution
# ═══════════════════════════════════════════════════════════════════════════

def run_candidate(df: pd.DataFrame, params: CandidateParams,
                  mode_name: str = None) -> dict:
    """Run a single quiet backtest. Returns raw result dict or error dict."""
    if mode_name is None:
        mode_name = setup_hourly_mode(params.ticker)
    set_candidate_params(mode_name, params)

    try:
        with contextlib.redirect_stdout(io.StringIO()):
            result = run_backtest(
                df=df.copy(),
                initial_capital=config.INITIAL_CAPITAL,
                target_gain_pct=params.target,
                stop_loss_pct=params.stop,
                require_signals=1,
                kelly_multiplier=config.KELLY_MULTIPLIER,
                trade_hours=params.trade_hours,
                timeframe="hourly",
                plot=False,
                backtest_mode=params.backtest_mode,
            )
        return result if result else {"error": "no_result"}
    except Exception as e:
        return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════
#  Metrics extraction
# ═══════════════════════════════════════════════════════════════════════════

def extract_metrics(r: dict) -> Optional[CandidateResult]:
    """Extract live-relevant metrics from a backtest result dict."""
    if r is None or "error" in r:
        return None

    mo = r.get("monthly_returns", pd.Series(dtype=float))
    active_months = mo[mo != 0] if len(mo) > 0 else pd.Series(dtype=float)
    neg_months = int((active_months < 0).sum())
    total_months = int(len(active_months))
    avg_mo = float(active_months.mean()) if total_months > 0 else 0.0

    eb = r.get("exit_breakdown", {})
    total_trades = r.get("total_trades", 0)
    stop_hits = eb.get("stop_hit", 0)
    ambiguous = eb.get("ambiguous_same_bar", 0)
    target_hits = eb.get("target_hit", 0)
    time_exits = eb.get("time_exit", 0)
    tpm = total_trades / max(total_months, 1)

    return CandidateResult(
        params=CandidateParams(ticker=""),  # placeholder, caller should set
        total_return_pct=round(r.get("total_return", 0) * 100, 3),
        sharpe_ratio=r.get("sharpe_ratio", 0),
        max_drawdown_pct=round(r.get("max_drawdown", 0) * 100, 3),
        avg_monthly_pct=round(avg_mo * 100, 3),
        total_trades=total_trades,
        win_rate_pct=round(r.get("win_rate", 0) * 100, 2),
        neg_months=neg_months,
        total_months=total_months,
        stop_hit_ratio=round(stop_hits / total_trades, 3) if total_trades else 0,
        ambiguous_ratio=round(ambiguous / total_trades, 3) if total_trades else 0,
        target_hit_count=target_hits,
        stop_hit_count=stop_hits,
        ambiguous_count=ambiguous,
        time_exit_count=time_exits,
        trades_per_month=round(tpm, 1),
        raw_result=r,
    )


def live_score(metrics: CandidateResult,
               median_price: float = 50.0,
               est_spread: float = 0.03,
               train_metrics: Optional[CandidateResult] = None) -> float:
    """Live-oriented scoring: Sharpe + return, penalised by live-hostile traits."""
    m = metrics
    if m is None or m.total_trades == 0:
        return -9999

    base = m.sharpe_ratio * 0.5 + m.total_return_pct * 0.3 + m.max_drawdown_pct * 0.2

    if m.stop_hit_ratio > 0.55:
        base *= 0.6
    elif m.stop_hit_ratio > 0.50:
        base *= 0.8

    if m.total_months > 0:
        neg_frac = m.neg_months / m.total_months
        if neg_frac > 0.25:
            base *= 0.5
        elif neg_frac > 0.10:
            base *= 0.75

    if m.ambiguous_ratio > 0.20:
        base *= 0.5
    elif m.ambiguous_ratio > 0.10:
        base *= 0.75

    if m.total_months > 0:
        tpm = m.total_trades / max(m.total_months, 1)
        if tpm < 3:
            base *= 0.5
        elif tpm < 5:
            base *= 0.75

    if train_metrics is not None and train_metrics.avg_monthly_pct > 0:
        retention = m.avg_monthly_pct / train_metrics.avg_monthly_pct
        if retention < 0:
            base *= 0.3
        elif retention < 0.4:
            base *= 0.5
        elif retention < 0.6:
            base *= 0.7

    if est_spread > 0:
        stop_dollars = median_price * m.params.stop
        spread_mult = stop_dollars / est_spread if est_spread > 0 else 999
        if spread_mult < 3:
            base *= 0.3
        elif spread_mult < 5:
            base *= 0.7

    return base


# ═══════════════════════════════════════════════════════════════════════════
#  Validation tests
# ═══════════════════════════════════════════════════════════════════════════

def test_rolling_windows(df: pd.DataFrame, params: CandidateParams,
                         mode_name: str, n_windows: int = 4) -> dict:
    """Split data into N windows, backtest each independently."""
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

        r = run_candidate(window_df, params, mode_name)
        if r is None or "error" in (r or {}):
            results.append({
                "window": i + 1,
                "start": str(window_df.index[0].date()),
                "end": str(window_df.index[-1].date()),
                "bars": len(window_df),
                "trades": 0, "return_pct": 0, "sharpe": 0,
                "win_rate": 0, "max_dd_pct": 0,
            })
            continue

        mo = r.get("monthly_returns", pd.Series(dtype=float))
        avg_mo = float(mo[mo != 0].mean()) * 100 if len(mo[mo != 0]) > 0 else 0

        results.append({
            "window": i + 1,
            "start": str(window_df.index[0].date()),
            "end": str(window_df.index[-1].date()),
            "bars": len(window_df),
            "trades": r.get("total_trades", 0),
            "return_pct": round(r.get("total_return", 0) * 100, 2),
            "sharpe": r.get("sharpe_ratio", 0),
            "win_rate": round(r.get("win_rate", 0) * 100, 1),
            "max_dd_pct": round(r.get("max_drawdown", 0) * 100, 2),
            "avg_monthly_pct": round(avg_mo, 2),
        })

    returns = [w["return_pct"] for w in results if w.get("trades", 0) > 0]
    sharpes = [w["sharpe"] for w in results if w.get("trades", 0) > 0]
    positive_windows = sum(1 for r in returns if r > 0)

    return {
        "windows": results,
        "positive_windows": f"{positive_windows}/{len(returns)}",
        "return_range_pct": round(max(returns) - min(returns), 2) if returns else 0,
        "return_std_pct": round(float(np.std(returns)), 2) if returns else 0,
        "sharpe_range": round(max(sharpes) - min(sharpes), 1) if sharpes else 0,
        "stable": len(returns) > 0 and positive_windows == len(returns) and (max(returns) - min(returns)) < 10,
    }


def equity_max_drawdown(returns_arr: np.ndarray, initial: float = 100_000) -> float:
    """Max drawdown from a sequence of trade returns."""
    equity = initial * np.cumprod(1 + returns_arr)
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / peak
    return float(dd.min())


def test_monte_carlo(trade_returns: pd.Series,
                     n_samples: int = 500, initial: float = 100_000) -> dict:
    """Shuffle trade order N times, compare max drawdown distributions."""
    if len(trade_returns) < 5:
        return {"error": "too_few_trades", "samples": 0}

    returns_arr = trade_returns.values
    realized_dd = equity_max_drawdown(returns_arr, initial)
    shuffle_dds = np.empty(n_samples)

    rng = np.random.default_rng(seed=42)
    for i in range(n_samples):
        shuffled = rng.permutation(returns_arr)
        shuffle_dds[i] = equity_max_drawdown(shuffled, initial)

    shuffle_dds_pct = shuffle_dds * 100
    realized_dd_pct = realized_dd * 100
    dd_percentile = float(np.mean(shuffle_dds <= realized_dd))

    return {
        "samples": n_samples,
        "realized_max_dd_pct": round(realized_dd_pct, 2),
        "shuffle_dd_p25_pct": round(float(np.percentile(shuffle_dds_pct, 25)), 2),
        "shuffle_dd_p50_pct": round(float(np.percentile(shuffle_dds_pct, 50)), 2),
        "shuffle_dd_p75_pct": round(float(np.percentile(shuffle_dds_pct, 75)), 2),
        "dd_percentile_rank": round(dd_percentile, 3),
        "lucky_sequencing": dd_percentile > 0.75,
        "unlucky_sequencing": dd_percentile < 0.25,
    }


def test_regime_split(df: pd.DataFrame, params: CandidateParams,
                      mode_name: str) -> dict:
    """Run backtest, break trades by regime."""
    r = run_candidate(df, params, mode_name)
    if r is None or "error" in (r or {}) or r.get("total_trades", 0) == 0:
        return {"error": "no_trades"}

    trades_df = r.get("trades_df", pd.DataFrame())
    regime_col = None
    if not trades_df.empty:
        if "regime" in trades_df.columns:
            regime_col = "regime"
        elif "trend_regime" in trades_df.columns:
            regime_col = "trend_regime"

    if regime_col is None:
        return {
            "note": "No regime column in trades_df",
            "total_trades": r.get("total_trades", 0),
        }

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
            warnings.append(f"Regime {regime}: only {stats['trades']} trades")

    return {"regimes": regime_stats, "total_trades": r.get("total_trades", 0), "warnings": warnings}


def test_drawdown_profile(result: dict) -> dict:
    """Analyze drawdown depth, duration, and consecutive loss streaks."""
    if result is None or "error" in (result or {}):
        return {"error": "no_result"}

    equity = result.get("equity_curve", pd.Series(dtype=float))
    trade_returns = result.get("trade_returns", pd.Series(dtype=float))
    monthly = result.get("monthly_returns", pd.Series(dtype=float))

    if len(equity) < 2:
        return {"error": "no_equity_curve"}

    peak = equity.cummax()
    dd = (equity - peak) / peak
    max_dd_pct = round(float(dd.min()) * 100, 3)

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

    active_months = monthly[monthly != 0] if len(monthly) > 0 else pd.Series(dtype=float)
    worst_month = round(float(active_months.min()) * 100, 2) if len(active_months) > 0 else 0
    best_month = round(float(active_months.max()) * 100, 2) if len(active_months) > 0 else 0
    month_std = round(float(active_months.std()) * 100, 2) if len(active_months) > 1 else 0
    neg_months = int((active_months < 0).sum())

    return {
        "max_drawdown_pct": max_dd_pct,
        "max_dd_duration_trades": max(dd_durations) if dd_durations else 0,
        "max_consecutive_losses": max_streak,
        "worst_month_pct": worst_month,
        "best_month_pct": best_month,
        "monthly_return_std_pct": month_std,
        "negative_months": neg_months,
        "total_active_months": len(active_months),
    }


def test_slippage_sensitivity(df: pd.DataFrame, params: CandidateParams,
                              mode_name: str) -> dict:
    """Re-run backtest across multiple slippage levels."""
    from src.backtest.runner import BACKTEST_MODES

    slippage_levels = [0.0, 0.0002, 0.0005, 0.0010]
    results = []

    for slip in slippage_levels:
        mode_key = params.backtest_mode
        original_slip = BACKTEST_MODES[mode_key]["slippage_pct"]
        BACKTEST_MODES[mode_key]["slippage_pct"] = slip
        try:
            r = run_candidate(df, params, mode_name)
        finally:
            BACKTEST_MODES[mode_key]["slippage_pct"] = original_slip

        if r and "error" not in r:
            mo = r.get("monthly_returns", pd.Series(dtype=float))
            avg_mo = float(mo[mo != 0].mean()) * 100 if len(mo[mo != 0]) > 0 else 0
            results.append({
                "slippage_bps": round(slip * 10000),
                "return_pct": round(r.get("total_return", 0) * 100, 2),
                "sharpe": r.get("sharpe_ratio", 0),
                "win_rate_pct": round(r.get("win_rate", 0) * 100, 1),
                "avg_monthly_pct": round(avg_mo, 2),
            })
        else:
            results.append({
                "slippage_bps": round(slip * 10000),
                "return_pct": 0, "sharpe": 0, "win_rate_pct": 0, "avg_monthly_pct": 0,
            })

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
#  Validation orchestrator
# ═══════════════════════════════════════════════════════════════════════════

def validate_candidate(df: pd.DataFrame, params: CandidateParams,
                       mode_name: str,
                       cfg: AutoSweepConfig = None) -> ValidationResult:
    """Run all validation tests on a candidate."""
    if cfg is None:
        cfg = AutoSweepConfig()

    result = ValidationResult()

    baseline = run_candidate(df, params, mode_name)

    if not cfg.skip_rolling:
        result.rolling = test_rolling_windows(df, params, mode_name, cfg.rolling_windows)

    if not cfg.skip_mc and baseline and "error" not in baseline:
        tr = baseline.get("trade_returns", pd.Series(dtype=float))
        if len(tr) >= 5:
            result.monte_carlo = test_monte_carlo(tr, cfg.mc_samples)

    if not cfg.skip_regime:
        result.regime_split = test_regime_split(df, params, mode_name)

    result.drawdown_profile = test_drawdown_profile(baseline)

    if not cfg.skip_slippage:
        result.slippage_sensitivity = test_slippage_sensitivity(df, params, mode_name)

    verdict = compute_confidence(result)
    result.confidence = verdict["confidence"]
    result.confidence_score = verdict["score"]
    result.warnings = verdict["warnings"]
    return result


def compute_confidence(vr: ValidationResult) -> dict:
    """Combine test results into HIGH / MEDIUM / LOW / REJECTED confidence."""
    warnings = []
    score = 100

    rolling = vr.rolling
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

    mc = vr.monte_carlo
    if mc and not mc.get("error"):
        if mc.get("unlucky_sequencing"):
            score -= 20
            warnings.append("MC DD worse than 75% of shuffles")
        if mc.get("lucky_sequencing"):
            score -= 10
            warnings.append("MC DD unusually good — may not persist")

    regime = vr.regime_split
    if regime and not regime.get("error"):
        for w in regime.get("warnings", []):
            score -= 5
            warnings.append(w)

    dd = vr.drawdown_profile
    if dd and not dd.get("error"):
        if dd.get("max_consecutive_losses", 0) > 8:
            score -= 10
            warnings.append(f"Max {dd['max_consecutive_losses']} consecutive losses")
        if dd.get("worst_month_pct", 0) < -5:
            score -= 15
            warnings.append(f"Worst month {dd['worst_month_pct']}%")
        if dd.get("negative_months", 0) > dd.get("total_active_months", 1) * 0.3:
            score -= 10
            neg = dd["negative_months"]
            tot = dd["total_active_months"]
            warnings.append(f"{neg}/{tot} months negative")

    slip = vr.slippage_sensitivity
    if slip and not slip.get("error"):
        if slip.get("fragile"):
            score -= 20
            warnings.append(f"Fragile to slippage ({slip['degradation_per_bps']}%/bps)")

    score = max(0, min(100, score))
    if score >= 75:
        level = "HIGH"
    elif score >= 50:
        level = "MEDIUM"
    elif score >= 25:
        level = "LOW"
    else:
        level = "REJECTED"

    return {"confidence": level, "score": score, "warnings": warnings}


# ═══════════════════════════════════════════════════════════════════════════
#  Candidate comparison
# ═══════════════════════════════════════════════════════════════════════════

def compare_candidates(a: CandidateResult, b: CandidateResult) -> dict:
    """Compare two candidates on key metrics. Returns delta dict."""
    fields = [
        "total_return_pct", "sharpe_ratio", "max_drawdown_pct",
        "avg_monthly_pct", "total_trades", "win_rate_pct",
        "stop_hit_ratio", "ambiguous_ratio", "trades_per_month",
    ]
    delta = {}
    for f in fields:
        va = getattr(a, f, 0)
        vb = getattr(b, f, 0)
        delta[f] = round(vb - va, 4)
    return delta


# ═══════════════════════════════════════════════════════════════════════════
#  I/O helpers
# ═══════════════════════════════════════════════════════════════════════════

def save_json(path: str, payload: dict) -> None:
    """Write dict to JSON file."""
    with open(path, "w") as f:
        json.dump(payload, f, indent=2, default=str)


def load_sweep_results(ticker: str) -> Optional[dict]:
    """Load sweep_results_{ticker}.json if it exists."""
    path = f"sweep_results_{ticker.upper()}.json"
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)

"""
MONAD Quant - Position Sizing
Kelly Criterion with fractional Kelly for risk management.
"""

import numpy as np
import pandas as pd


def kelly_fraction(win_rate: float, avg_win: float, avg_loss: float) -> float:
    """
    Full Kelly Criterion.
    f* = (p * b - q) / b
    where p=win_rate, q=1-p, b=avg_win/avg_loss
    """
    if avg_loss == 0:
        return 0.0
    b = avg_win / avg_loss
    q = 1 - win_rate
    f = (win_rate * b - q) / b
    return max(0.0, f)


def half_kelly(win_rate: float, avg_win: float, avg_loss: float) -> float:
    """Half-Kelly — safer, reduces drawdown significantly."""
    return kelly_fraction(win_rate, avg_win, avg_loss) * 0.5


def compute_position_size(capital: float,
                           win_rate: float,
                           avg_win_pct: float,
                           avg_loss_pct: float,
                           kelly_multiplier: float = 0.5,
                           max_position_pct: float = 0.20,
                           min_position_pct: float = 0.0) -> dict:
    """
    Compute position size in dollars given account capital and historical stats.
    Caps at max_position_pct; floors at min_position_pct when Kelly > 0 so
    a thin sample doesn't silently zero out all capital deployment.
    min_position_pct is only applied when full Kelly is positive — if the
    strategy has genuine negative edge, Kelly stays at 0 (don't override).
    """
    f = kelly_fraction(win_rate, avg_win_pct, avg_loss_pct)
    f_adjusted = f * kelly_multiplier
    # Apply floor only when raw Kelly is positive (edge exists, sample just thin)
    if f > 0:
        f_adjusted = max(f_adjusted, min_position_pct)
    f_capped = min(f_adjusted, max_position_pct)

    position_dollars = capital * f_capped

    return {
        "kelly_full": round(f, 4),
        "kelly_adjusted": round(f_adjusted, 4),
        "kelly_capped": round(f_capped, 4),
        "position_dollars": round(position_dollars, 2),
        "position_pct": round(f_capped * 100, 2),
    }


def recent_win_rate(returns, lookback: int) -> float:
    """Win rate over the most recent `lookback` trade returns (0.0 if too few)."""
    recent = list(returns)[-lookback:]
    if not recent:
        return 0.0
    return sum(1 for x in recent if x > 0) / len(recent)


def adaptive_kelly_multiplier(base_fraction: float,
                              recent_returns,
                              *,
                              lookback: int = 20,
                              high_wr: float = 0.52,
                              low_wr: float = 0.42,
                              pause_wr: float = 0.35,
                              high_mult: float = 1.5,
                              low_mult: float = 0.5,
                              pause_mult: float = 0.2,
                              high_cap: float = 0.30) -> float:
    """Scale a base Kelly fraction by the recent rolling win-rate tier.

    Mirrors the live/backtest adaptive-Kelly behaviour exactly:
      * fewer than `lookback` recent trades → unchanged (warming up)
      * recent WR >= high_wr   → base * high_mult, capped at high_cap   (size up)
      * recent WR <  pause_wr  → base * pause_mult                      (de-risk hard)
      * recent WR <  low_wr    → base * low_mult                        (de-risk)
      * otherwise              → unchanged                             (normal)

    `recent_returns` is the list of prior trade returns (most recent last). It is
    used read-only — callers must append the current trade's return AFTER sizing
    to avoid look-ahead.
    """
    recent = list(recent_returns)
    if len(recent) < lookback:
        return base_fraction
    wr = recent_win_rate(recent, lookback)
    if wr >= high_wr:
        return min(base_fraction * high_mult, high_cap)
    if wr < pause_wr:
        return base_fraction * pause_mult
    if wr < low_wr:
        return base_fraction * low_mult
    return base_fraction


def position_fraction(*,
                      mode: str = "kelly",
                      kelly_mode: str = "rolling",
                      rolling_returns=None,
                      full_sample_stats: dict | None = None,
                      kelly_multiplier: float = 0.5,
                      min_pct: float = 0.02,
                      max_pct: float = 0.20,
                      fixed_pct: float = 0.08,
                      min_trades_for_kelly: int = 10,
                      adaptive: dict | None = None,
                      clamp_min: float = 0.02,
                      clamp_max: float = 0.10) -> float:
    """Capital fraction to deploy for the next trade — the single, testable entry
    point used by the backtest/sweep. Pure (returns a fraction, no capital state).

    mode:        "fixed" | "kelly" | "kelly_clamped"
    kelly_mode:  "rolling" (size from recent trades) | "full" (full-sample stats)
    adaptive:    None to disable, or a dict of adaptive_kelly_multiplier kwargs to
                 apply the rolling win-rate tier scaling (i.e. "run with adaptive Kelly").
    """
    rolling_returns = list(rolling_returns or [])

    if mode == "fixed":
        return fixed_pct

    # Base Kelly fraction (capital-independent → use capital=1.0).
    if kelly_mode == "rolling":
        if len(rolling_returns) >= min_trades_for_kelly:
            st = estimate_stats_from_backtest(pd.Series(rolling_returns))
            frac = compute_position_size(
                capital=1.0, win_rate=st["win_rate"],
                avg_win_pct=st["avg_win_pct"], avg_loss_pct=st["avg_loss_pct"],
                kelly_multiplier=kelly_multiplier,
                min_position_pct=min_pct, max_position_pct=max_pct,
            )["kelly_capped"]
        else:
            frac = min_pct
    else:  # full-sample
        st = full_sample_stats or {}
        frac = compute_position_size(
            capital=1.0, win_rate=st.get("win_rate", 0),
            avg_win_pct=st.get("avg_win_pct", 0), avg_loss_pct=st.get("avg_loss_pct", 0),
            kelly_multiplier=kelly_multiplier,
            min_position_pct=min_pct, max_position_pct=max_pct,
        )["kelly_capped"]

    if adaptive is not None:
        frac = adaptive_kelly_multiplier(frac, rolling_returns, **adaptive)

    if mode == "kelly_clamped":
        frac = max(clamp_min, min(frac, clamp_max))

    return frac


def estimate_stats_from_backtest(returns: pd.Series) -> dict:
    """Extract win rate and avg win/loss from a series of trade returns."""
    wins = returns[returns > 0]
    losses = returns[returns < 0]

    win_rate = len(wins) / len(returns) if len(returns) > 0 else 0
    avg_win = wins.mean() if len(wins) > 0 else 0
    avg_loss = abs(losses.mean()) if len(losses) > 0 else 0

    return {
        "win_rate": round(win_rate, 4),
        "avg_win_pct": round(avg_win, 4),
        "avg_loss_pct": round(avg_loss, 4),
        "total_trades": len(returns),
    }

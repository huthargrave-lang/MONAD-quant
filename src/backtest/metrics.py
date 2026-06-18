"""
MONAD Quant — Pure performance-metric functions for the backtest runner.

Extracted from ``runner.run_backtest`` so the metric math can be unit-tested on
fixed synthetic equity curves, independent of the engine/config (see
``tests/test_runner_metrics.py``), and so there is **one** Sharpe annualization
used across the codebase. The historical walk-forward Sharpe bug came from a
second, divergent Sharpe implementation; ``walk_forward._sharpe`` now reuses
``annualized_sharpe`` below.

All functions are pure: same inputs → same outputs, no config/IO side effects.
"""
import numpy as np
import pandas as pd


def annualized_sharpe(period_returns, trades_per_year, degenerate: float = 0.0) -> float:
    """Sharpe ratio annualized by trade frequency.

    Args:
        period_returns: per-trade (or per-period) returns; their mean/std define
            the raw (unannualized) ratio.
        trades_per_year: annualization frequency. The multiplier is its sqrt —
            this is what makes Sharpe comparable across timeframes. Using a fixed
            252 here (the old bug) assumes 252 trades/year regardless of how often
            the strategy actually trades.
        degenerate: value to return when the ratio is undefined (<2 points, zero
            or non-finite std). ``runner`` reports 0.0; the walk-forward selector
            uses -inf so a degenerate window never "wins".
    """
    r = pd.Series(period_returns, dtype=float)
    std = r.std()
    if len(r) < 2 or std == 0 or not np.isfinite(std):
        return degenerate
    return (r.mean() / std) * np.sqrt(trades_per_year)


def trades_per_year(n_trades: int, start, end) -> float:
    """Trades/year implied by a trade count over the [start, end] calendar span.

    Mirrors ``runner``: spans of <= 0 days collapse to one year (so the result is
    just ``n_trades``), which keeps very short windows finite rather than blowing up.
    """
    n_days = (end - start).days
    years = n_days / 365.25 if n_days > 0 else 1
    return n_trades / years if years > 0 else n_trades


def max_drawdown(equity) -> float:
    """Most negative peak-to-trough drawdown of an equity curve (<= 0)."""
    eq = pd.Series(equity, dtype=float)
    if eq.empty:
        return 0.0
    rolling_max = eq.cummax()
    drawdown = (eq - rolling_max) / rolling_max
    return float(drawdown.min())


def total_return(equity, initial_capital: float) -> float:
    """Fractional return of the final equity vs the initial capital."""
    eq = pd.Series(equity, dtype=float)
    if eq.empty or initial_capital == 0:
        return 0.0
    return (eq.iloc[-1] - initial_capital) / initial_capital


def buy_hold_return(close) -> float:
    """Fractional return of buying at the first close and holding to the last."""
    c = pd.Series(close, dtype=float)
    if c.empty or c.iloc[0] == 0:
        return 0.0
    return (c.iloc[-1] - c.iloc[0]) / c.iloc[0]


def annualize_return(total_ret: float, years: float) -> float:
    """Compound a total return down to an annual rate."""
    return (1 + total_ret) ** (1 / years) - 1 if years > 0 else total_ret


def monthly_returns(capital_ret_series) -> pd.Series:
    """Compound per-trade capital returns into calendar-month returns.

    Input is a Series (or dict) of per-trade capital-fraction changes indexed by
    trade timestamp; output is one compounded return per calendar month (months
    with no trades resolve to 0.0).
    """
    s = pd.Series(capital_ret_series, dtype=float)
    if s.empty:
        return s
    s.index = pd.to_datetime(s.index)
    return s.resample("ME").apply(lambda x: (1 + x).prod() - 1 if len(x) > 0 else 0.0)

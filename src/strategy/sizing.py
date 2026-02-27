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
                           max_position_pct: float = 0.20) -> dict:
    """
    Compute position size in dollars given account capital and historical stats.
    Caps at max_position_pct of capital as a risk guardrail.
    """
    f = kelly_fraction(win_rate, avg_win_pct, avg_loss_pct)
    f_adjusted = f * kelly_multiplier
    f_capped = min(f_adjusted, max_position_pct)

    position_dollars = capital * f_capped

    return {
        "kelly_full": round(f, 4),
        "kelly_adjusted": round(f_adjusted, 4),
        "kelly_capped": round(f_capped, 4),
        "position_dollars": round(position_dollars, 2),
        "position_pct": round(f_capped * 100, 2),
    }


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

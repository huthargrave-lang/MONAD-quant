"""
MONAD Quant — Sweep scoring (the parameter-selection decision layer).

Extracted from ``sweep.py`` so the functions that *select production parameters*
are importable and unit-testable (``sweep.py`` itself is a CLI script that parses
args and fetches data at import time). ``live_score`` is now pure: the bid-ask
spread inputs it previously read from module globals (``est_spread``,
``median_price``) are explicit arguments. ``sweep.py`` keeps a thin wrapper that
injects those globals, so its call sites and behavior are unchanged.

This is the "live-oriented" objective: reward Sharpe + return, penalize traits
that don't survive live execution (noise-stops, negative months, same-bar
ambiguity, thin trade counts, holdout decay, stops inside the spread).
"""


def extract_metrics(r):
    """Pull live-relevant metrics from a backtest result dict.

    Returns None for a missing/errored result. Otherwise a flat dict of the
    metrics ``live_score`` consumes (returns, Sharpe, drawdown, monthly stats,
    exit-type ratios).
    """
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


def live_score(r, stop=None, train_metrics=None, est_spread=0.0, median_price=0.0):
    """Live-oriented scoring: Sharpe + return, penalised by live-hostile traits.

    Penalties (each a multiplicative shrink of the base score):
      - High stop_hit ratio (>50%): trades are noise-stopped too often
      - Negative months: income strategy should have near-zero neg months
      - Ambiguous same-bar exits: result is random (stop or target in same bar)
      - Too few trades (<5/month): not enough for statistical confidence
      - Large train→holdout degradation (when train_metrics provided)
      - Stop inside bid-ask spread noise (when est_spread/median_price provided)

    Args:
        r: backtest result dict (or None/errored → -9999).
        stop: stop-loss fraction; only used for the spread penalty.
        train_metrics: train-window metrics; enables the holdout-decay penalty.
        est_spread: estimated bid-ask spread in dollars. 0 disables the spread
            penalty (matches the original ``est_spread > 0`` guard).
        median_price: median close used to convert ``stop`` to dollars.
    """
    if r is None or "error" in r:
        return -9999

    m = extract_metrics(r)
    if m is None:
        return -9999

    # Base: Sharpe × 0.5 + return × 0.3 + DD bonus × 0.2  (DD is negative, so bonus)
    base = m["sharpe_ratio"] * 0.5 + m["total_return_pct"] * 0.3 + m["max_drawdown_pct"] * 0.2
    return _apply_penalties(base, m, stop=stop, train_metrics=train_metrics,
                            est_spread=est_spread, median_price=median_price)


def _apply_penalties(base, m, stop=None, train_metrics=None, est_spread=0.0, median_price=0.0):
    """Apply the live-hostile-trait penalties to a base score (shared by every
    objective). Each is a multiplicative shrink of ``base``."""
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


def ev_score(r, stop=None, train_metrics=None, est_spread=0.0, median_price=0.0,
             min_wr_pct: float = 34.0):
    """Net-of-cost EV objective (C4 — opt-in via ``--objective ev``).

    Rewards total return (which, with C3's round-trip cost baked into every
    trade, IS net-of-cost EV × trades) instead of Sharpe. Sharpe scales with
    √(trade frequency), so the default ``live_score`` (Sharpe × 0.5) quietly
    rewards churn; this objective does not. Applies the same live-hostile-trait
    penalties, then HARD-rejects any config whose win rate is below the 2:1 R:R
    breakeven (~33.3%) — structurally unprofitable however good the sample looks.
    """
    if r is None or "error" in r:
        return -9999

    m = extract_metrics(r)
    if m is None:
        return -9999

    base = m["total_return_pct"]
    scored = _apply_penalties(base, m, stop=stop, train_metrics=train_metrics,
                              est_spread=est_spread, median_price=median_price)
    if m["win_rate_pct"] < min_wr_pct:
        return scored - 1000.0   # hard reject: below breakeven WR
    return scored

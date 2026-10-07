"""
Daily mark-to-market basis for price-strategy trials (gate rules v2, decision debate
2026-10-06, docs/research/DEFLATION_RULE_QUESTION.md (iii)).

A price strategy's trade returns are sparse, irregular and overlap session boundaries, so
the familywise SPA cannot compare two of them directly. Under (iii) every ENGINE_VERSION 3
trial is put on one daily grid instead:

* **Fixed notional.** Each trade is one unit of notional. On every session close it is
  held through, it is marked at ``sign x (close / entry - 1)``; on its exit session it is
  marked at its booked (net) return. A session's PnL is the change in mark, so a trade's
  daily PnL sums to exactly its booked return.
* **Exposure** is the notional held at each session close (0 or 1 under one position).
* **Active PnL** = PnL - f x the instrument's daily total return, with f the mean close
  exposure: an exposure-matched static holding of the same instrument, daily rebalanced,
  at zero cost. A rule that merely holds the instrument a fraction f of the time has
  active PnL near zero; a timing edge does not.

Sessions are New York calendar dates of the bars. ``trade_marks`` keeps one row per
(trade, session) so a producer that scores only trades at or after a cut can restrict
the marks the same way it restricts the trades, then aggregate with ``daily_series``.
"""
from __future__ import annotations

import pandas as pd

SESSION_TZ = "America/New_York"


def session_dates(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """The New York session date of each bar timestamp (naive midnight dates). A
    tz-aware index is converted to New York; a naive one is taken as New York wall time
    already (so a daily bar dated at midnight is its own session)."""
    idx = pd.DatetimeIndex(index)
    if idx.tz is not None:
        idx = idx.tz_convert(SESSION_TZ).tz_localize(None)
    return idx.normalize().astype("datetime64[ns]")


def trade_marks(trades: pd.DataFrame, bars: pd.DataFrame) -> pd.DataFrame:
    """One row per (trade, session): ``trade`` (the trade's signal timestamp), ``session``,
    ``pnl`` (that session's change in mark) and ``exposure`` (notional held at its close).

    ``trades`` needs ``timestamp``, ``entry_time``, ``exit_time``, ``return`` and
    ``direction`` (+1 long, -1 short); ``bars`` needs ``open`` and ``close`` on the
    index the trades were simulated on.
    """
    cols = ["trade", "session", "pnl", "exposure"]
    if trades is None or not len(trades):
        return pd.DataFrame(columns=cols)
    sess = session_dates(bars.index)
    last_bar = pd.Series(bars.index, index=sess).groupby(level=0).max()
    session_close = pd.Series(bars["close"].reindex(last_bar.to_numpy()).to_numpy(dtype=float),
                              index=last_bar.index)
    pos = {ts: i for i, ts in enumerate(bars.index)}
    rows = []
    for ts, entry, exit_, ret, direction in zip(trades["timestamp"], trades["entry_time"],
                                                trades["exit_time"], trades["return"],
                                                trades["direction"]):
        entry, exit_ = pd.Timestamp(entry), pd.Timestamp(exit_)
        p0 = float(bars["open"].iloc[pos[entry]])
        s_entry = session_dates(pd.DatetimeIndex([entry]))[0]
        s_exit = session_dates(pd.DatetimeIndex([exit_]))[0]
        prev = 0.0
        for d in last_bar.index[(last_bar.index >= s_entry) & (last_bar.index <= s_exit)]:
            if d < s_exit and last_bar[d] < exit_:
                mark, held = float(direction) * (session_close[d] / p0 - 1.0), 1.0
            elif d == s_exit:
                mark, held = float(ret), 0.0
            else:
                continue
            rows.append((pd.Timestamp(ts), d, mark - prev, held))
            prev = mark
    return pd.DataFrame(rows, columns=cols)


def daily_series(marks: pd.DataFrame, sessions: pd.DatetimeIndex) -> tuple[pd.Series, pd.Series]:
    """``(pnl, exposure)`` on ``sessions``, zero where no trade is open."""
    sessions = pd.DatetimeIndex(sessions)
    if marks is None or not len(marks):
        zero = pd.Series(0.0, index=sessions)
        return zero, zero.copy()
    g = marks.groupby("session")
    pnl = g["pnl"].sum().reindex(sessions, fill_value=0.0).astype(float)
    exposure = g["exposure"].sum().reindex(sessions, fill_value=0.0).astype(float)
    return pnl, exposure


def active_pnl(pnl: pd.Series, exposure: pd.Series, instrument_return: pd.Series) -> pd.Series:
    """PnL minus the exposure-matched static holding: f x the instrument's daily total
    return, f = mean close exposure. Raises if the instrument return does not cover
    every session of ``pnl``."""
    r = instrument_return.reindex(pnl.index)
    if r.isna().any():
        raise ValueError(f"the instrument's daily return is missing on {int(r.isna().sum())} "
                         f"of {len(r)} sessions")
    f = float(exposure.mean()) if len(exposure) else 0.0
    return (pnl - f * r).astype(float)


def bar_session_returns(bars: pd.DataFrame) -> pd.Series:
    """Close-to-close daily return of the instrument from its own bars (price return:
    no distributions). The gate prefers a frozen daily snapshot's total return; this is
    the fallback for synthetic data and the study."""
    sess = session_dates(bars.index)
    close = pd.Series(bars["close"].to_numpy(dtype=float), index=sess).groupby(level=0).last()
    return close.pct_change().fillna(0.0)


__all__ = ["session_dates", "trade_marks", "daily_series", "active_pnl", "bar_session_returns",
           "SESSION_TZ"]

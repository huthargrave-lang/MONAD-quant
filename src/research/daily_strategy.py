"""
MONAD Quant — The daily-strategy evaluator: portfolios held between sessions, counted.

The hourly engine's numbers are upper bounds until its execution model matches live
(F404703). Daily strategies avoid most of that problem, but only if the daily evaluator
does not reintroduce it. So this evaluator commits to an execution model and charges for it:

  * **Decisions trade at the NEXT session.** A strategy decides at the close of day t,
    using data through that close, and the order executes at day t+1's open ("open"
    orders) or close ("close" orders). Nothing trades at the price it was computed from
    (F404703's O1, at daily scale).
  * **Holdings drift.** Between rebalances each position moves with its own returns. A
    monthly strategy is NOT silently re-weighted every day, and a rebalance pays for the
    turnover from the drifted weights back to target.
  * **Two legs per session, compounded.** Night (close to open, including an ex-date's
    distribution) and day (open to close) are applied in sequence to the holdings; cash
    accrues at the T-bill rate on whatever is uninvested.
  * **Costs per asset and era** (``COST_BPS``; ``tiers`` maps an asset to its tier, the
    default being the ETF tiers), charged one-way on traded notional at every rebalance,
    at open or close alike. ``cost_multiple`` scales them (the gate's cost stress uses 2).
  * **Tranches.** A strategy may run as several equal-capital sub-portfolios (for example
    one per rebalance-day offset, removing rebalance-date luck). Each drifts and rebalances
    on its own schedule; the portfolio is their sum.
  * **Long only, no leverage.** Target weights are >= 0 and sum to <= 1; the remainder is cash.

``evaluate_daily`` is an engine evaluation in the sense of ``src/strategy/counted.py``: it
refuses to run without a begun trial, so every daily backtest is in the trial ledger.

What it does NOT model: intraday price impact beyond the cost table, borrow, taxes, and
unscheduled exchange closures (the calendar is the snapshot's own sessions, treated as
known in advance, which is true of every scheduled NYSE holiday).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

import numpy as np
import pandas as pd

from src.research.daily_data import SessionReturns, Snapshot
from src.strategy.counted import evaluator as _counted_evaluator

#: Bumped whenever the execution model changes what a strategy would have earned.
#: Family names carry it (``daily_alloc.v<N>``), so trials from different models are
#: never deflated together.
EVALUATOR_VERSION = 1
EVALUATOR_NAME = "daily_strategy"

#: One-way cost in basis points of traded notional (half the quoted spread, plus
#: commission and slippage at ~$100k notional). Era boundary: 2010, when ETF spreads
#: compressed after decimal-era market-making matured and the 2008-09 wide markets ended.
#: Tier 2 are the thinner ETFs (emerging equity, commodities, REITs). These are
#: assumptions, stated so a refuter can attack them; the gate's cost stress doubles them.
#: Tier "cef" is closed-end funds: smaller, thinner books than any ETF here (quoted spreads
#: of roughly 10-40 bps on the median fund), so a higher assumption, doubled under stress.
COST_ERA_BOUNDARY = pd.Timestamp("2010-01-01")
COST_BPS = {
    "tier1": {"pre": 5.0, "post": 2.0},
    "tier2": {"pre": 12.0, "post": 5.0},
    "cef": {"pre": 30.0, "post": 15.0},
    # Spot crypto at small size: between IBKR's 12-18 bps commission and retail exchange
    # taker fees (40-60 bps), with spread; one rate, as the market starts after 2010.
    "crypto": {"pre": 25.0, "post": 25.0},
    # Small and micro caps around insider-buying events: half-spreads of 20-60 bps plus
    # impact at small size; one rate after 2010, wider before.
    "smallcap": {"pre": 50.0, "post": 30.0},
    # A miner basket before decimalisation (1/8-dollar ticks until 1997, about 15-40 bps
    # half-spread on $15-40 shares) and physical bullion against a daily fixing, for the
    # 1984-2005 miner/metal test (docs/research/MINER_TILT_PREPERIOD.md, board 2026-10-09).
    "basket_pre_decimal": {"pre": 35.0, "post": 35.0},
    "bullion": {"pre": 20.0, "post": 20.0},
}
TIER2 = frozenset({"EEM", "DBC", "VNQ"})


def default_tier(asset: str) -> str:
    return "tier2" if asset in TIER2 else "tier1"


def cost_bps(asset: str, day: pd.Timestamp, tiers: Mapping[str, str] | None = None) -> float:
    tier = (tiers or {}).get(asset) or default_tier(asset)
    return COST_BPS[tier]["pre" if day < COST_ERA_BOUNDARY else "post"]


def cost_matrix(assets: Sequence[str], dates: pd.DatetimeIndex,
                tiers: Mapping[str, str] | None = None) -> np.ndarray:
    """(sessions, assets) one-way cost in basis points (``cost_bps`` for every cell)."""
    names = [(tiers or {}).get(a) or default_tier(a) for a in assets]
    pre = np.array([COST_BPS[t]["pre"] for t in names])
    post = np.array([COST_BPS[t]["post"] for t in names])
    early = np.asarray(dates < COST_ERA_BOUNDARY)[:, None]
    return np.where(early, pre[None, :], post[None, :])


@dataclass(frozen=True)
class Tranche:
    """One sub-portfolio's orders, keyed by DECISION date (a snapshot session).

    ``open_orders``: target weights to hold from the open of the session AFTER the
    decision date. ``close_orders``: target weights to hold from the close of the session
    after the decision date. A row of NaN, or a date absent from the frame, places no
    order. Columns are asset symbols; missing assets are weight 0.
    """
    open_orders: pd.DataFrame
    close_orders: pd.DataFrame


@dataclass
class DailyResult:
    returns: pd.Series                 # portfolio simple return per session, scored window
    cash: pd.Series                    # the cash return per session, same index
    rebalances: int                    # orders executed (all tranches)
    turnover: float                    # sum over sessions of traded notional / portfolio value
                                       # at the previous close (all tranches together)
    cost_paid: float                   # the same for fees
    exposure: pd.Series = field(repr=False, default=None)   # invested fraction at each close
    #: Each asset's fraction of the portfolio at each close (all tranches together);
    #: ``exposure`` is its row sum.
    weights: pd.DataFrame = field(repr=False, default=None)
    #: The book at the last scored close, to continue from (``evaluate_daily(initial=)``).
    final: BookState = field(repr=False, default=None)

    @property
    def excess(self) -> pd.Series:
        return self.returns - self.cash


class OrderError(ValueError):
    """A strategy produced an order the evaluator cannot execute."""


@dataclass(frozen=True)
class BookState:
    """Every tranche's holdings (dollars per asset) and cash at the close of ``session``:
    what ``evaluate_daily`` needs to continue a book from where an earlier evaluation (or
    a forward log) left it, exactly. Dollars are on the scale the earlier evaluation
    used; only their ratios matter."""
    session: str                       # ISO date of the close the state describes
    tranches: tuple                    # ({"holdings": {asset: dollars}, "cash": dollars}, ...)

    def to_json(self) -> dict:
        return {"session": self.session,
                "tranches": [{"holdings": dict(t["holdings"]), "cash": t["cash"]} for t in self.tranches]}

    @classmethod
    def from_json(cls, d) -> "BookState":
        return cls(session=d["session"],
                   tranches=tuple({"holdings": {a: float(v) for a, v in t["holdings"].items()},
                                   "cash": float(t["cash"])} for t in d["tranches"]))


def _orders_by_execution(orders: pd.DataFrame, dates: pd.DatetimeIndex,
                         assets: Sequence[str]) -> dict[int, np.ndarray]:
    """{execution session index: target weight vector}. A decision on dates[i] executes
    at dates[i+1]; a decision on the last session executes nowhere."""
    if orders is None or not len(orders):
        return {}
    unknown = set(orders.columns) - set(assets)
    if unknown:
        raise OrderError(f"orders name assets outside the snapshot: {sorted(unknown)}")
    pos = dates.get_indexer(orders.index)
    if (pos < 0).any():
        bad = orders.index[pos < 0][0]
        raise OrderError(f"order decided on {bad}, which is not a snapshot session")
    frame = orders.reindex(columns=list(assets))
    out = {}
    for p, row in zip(pos, frame.to_numpy(dtype=float)):
        if np.isnan(row).all():
            continue
        w = np.nan_to_num(row, nan=0.0)
        if (w < -1e-12).any():
            raise OrderError(f"negative target weight on {dates[p].date()}: long only")
        if w.sum() > 1.0 + 1e-9:
            raise OrderError(f"target weights sum to {w.sum():.6f} on {dates[p].date()}: no leverage")
        if p + 1 < len(dates):
            out[p + 1] = np.clip(w, 0.0, None)
    return out


@_counted_evaluator
def evaluate_daily(tranches: Sequence[Tranche], snap: Snapshot, *, start: pd.Timestamp,
                   end: pd.Timestamp | None = None, cost_multiple: float = 1.0,
                   rets: SessionReturns | None = None,
                   tiers: Mapping[str, str] | None = None,
                   initial: BookState | None = None) -> DailyResult:
    """Run ``tranches`` on ``snap`` and score sessions in [start, end].

    Every tranche starts in cash at the close of the session before ``start``, with
    equal capital, and buys into the target of its latest order that executed before
    ``start`` at ``start``'s open (paying for that build like any rebalance). So a
    tranche whose next rebalance is twenty sessions away holds its strategy's position
    from the first scored session, rather than sitting in cash until then, which would
    bias every tranche differently by its offset.

    ``initial``: continue instead from a book left by an earlier evaluation at the close
    of the session before ``start`` (its ``final``): no build at ``start``, the same
    holdings and cash per tranche. Chaining evaluations this way reproduces one
    evaluation over the whole span exactly.
    """
    if not tranches:
        raise OrderError("a strategy needs at least one tranche")
    if cost_multiple <= 0:
        raise OrderError("cost_multiple must be positive")
    rets = rets or snap.returns()
    dates = snap.dates
    assets = list(snap.assets)
    i0 = int(dates.searchsorted(pd.Timestamp(start)))
    i1 = len(dates) - 1 if end is None else int(dates.searchsorted(pd.Timestamp(end), side="right")) - 1
    if i0 < 1 or i0 > i1:
        raise OrderError(f"scoring window {start}..{end} is empty or has no prior session")

    night = rets.night.reindex(columns=assets).to_numpy(dtype=float)
    day = rets.day.reindex(columns=assets).to_numpy(dtype=float)
    cash = rets.cash.to_numpy(dtype=float)
    cost = cost_matrix(assets, dates, tiers) * 1e-4 * cost_multiple

    n_t = len(tranches)
    if initial is not None:
        if initial.session != dates[i0 - 1].date().isoformat():
            raise OrderError(f"initial book is at {initial.session}, but scoring starts after "
                             f"{dates[i0 - 1].date()}")
        if len(initial.tranches) != n_t:
            raise OrderError(f"initial book has {len(initial.tranches)} tranches, the strategy {n_t}")
        unknown = {a for t in initial.tranches for a, v in t["holdings"].items() if v} - set(assets)
        if unknown:
            raise OrderError(f"initial book holds assets outside the snapshot: {sorted(unknown)}")
    finals = []
    total = np.zeros(i1 - i0 + 2)               # value at the close of i0-1 .. i1
    invested = np.zeros(i1 - i0 + 1)
    held = np.zeros((i1 - i0 + 1, len(assets)))     # dollars per asset at each close
    rebalances = 0
    # Traded notional and fees in DOLLARS per scored session, summed over tranches, then
    # divided by the WHOLE portfolio's value: a tranche's fee as a fraction of its own
    # capital is 1/n_t of that as a fraction of the portfolio.
    traded_d = np.zeros(i1 - i0 + 1)
    fee_d = np.zeros(i1 - i0 + 1)
    for n, tr in enumerate(tranches):
        opens = _orders_by_execution(tr.open_orders, dates, assets)
        closes = _orders_by_execution(tr.close_orders, dates, assets)
        _refuse_unreliable_opens(opens, snap, assets, dates)
        if initial is None:
            _carry_in(opens, closes, i0)
            h = np.zeros(len(assets))           # dollars per asset
            k = 1.0 / n_t                       # dollars in cash
        else:
            start_book = initial.tranches[n]["holdings"]
            h = np.array([float(start_book.get(a, 0.0)) for a in assets])
            k = float(initial.tranches[n]["cash"])
        total[0] += h.sum() + k
        for j, i in enumerate(range(i0, i1 + 1)):
            if h.any():
                r = night[i]
                if np.isnan(r[h > 0]).any():
                    raise OrderError(f"a held asset has no night return on {dates[i].date()}")
                h = h * (1.0 + np.nan_to_num(r))
            if i in opens:
                h, k, t, c = _rebalance(h, k, opens[i], cost[i], night[i], dates[i])
                rebalances += 1
                traded_d[j] += t
                fee_d[j] += c
            if h.any():
                r = day[i]
                if np.isnan(r[h > 0]).any():
                    raise OrderError(f"a held asset has no day return on {dates[i].date()}")
                h = h * (1.0 + np.nan_to_num(r))
            k = k * (1.0 + (cash[i] if np.isfinite(cash[i]) else 0.0))
            if i in closes:
                h, k, t, c = _rebalance(h, k, closes[i], cost[i], day[i], dates[i])
                rebalances += 1
                traded_d[j] += t
                fee_d[j] += c
            total[j + 1] += h.sum() + k
            invested[j] += h.sum()
            held[j] += h
        finals.append({"holdings": {a: float(v) for a, v in zip(assets, h) if v}, "cash": float(k)})
    values = pd.Series(total, index=dates[i0 - 1:i1 + 1])
    returns = values.pct_change().iloc[1:]
    prior = values.iloc[:-1].to_numpy()           # portfolio value at the previous close
    turnover = float((traded_d / prior).sum())
    cost_paid = float((fee_d / prior).sum())
    return DailyResult(returns=returns, cash=rets.cash.iloc[i0:i1 + 1].fillna(0.0),
                       rebalances=rebalances, turnover=turnover, cost_paid=cost_paid,
                       exposure=pd.Series(invested / values.iloc[1:].to_numpy(),
                                          index=dates[i0:i1 + 1]),
                       weights=pd.DataFrame(held / values.iloc[1:].to_numpy()[:, None],
                                            index=dates[i0:i1 + 1], columns=assets),
                       final=BookState(session=dates[i1].date().isoformat(), tranches=tuple(finals)))


def _refuse_unreliable_opens(opens: dict, snap: Snapshot, assets: Sequence[str],
                             dates: pd.DatetimeIndex) -> None:
    """An order may not trade an asset at an open the snapshot flagged as synthesised:
    the fill price would be a vendor's back-filled number, not a market."""
    bad = [assets.index(a) for a in snap.unreliable_opens if a in assets]
    if not bad:
        return
    for i, w in opens.items():
        if (w[bad] > 0).any():
            raise OrderError(f"open order on {dates[i].date()} trades an asset whose opens are "
                             f"unreliable ({sorted(snap.unreliable_opens)}); trade it at the close")


def _carry_in(opens: dict, closes: dict, i0: int) -> None:
    """Make the latest pre-``start`` target the opening order at ``start`` (in place),
    unless an order already executes at ``start``'s open. Among orders before ``start``,
    a close order on a session follows that session's open order."""
    if i0 in opens:
        return
    prior = [(p, 0, w) for p, w in opens.items() if p < i0]
    prior += [(p, 1, w) for p, w in closes.items() if p < i0]
    if prior:
        opens[i0] = max(prior, key=lambda x: (x[0], x[1]))[2]


def _rebalance(h, k, target, cost_row, leg_returns, day):
    """Trade holdings ``h`` (+ cash ``k``) to ``target`` weights of current value, paying
    one-way cost on traded notional. Returns (h, k, traded, fee), traded notional and fee
    in dollars."""
    value = h.sum() + k
    if value <= 0:
        raise OrderError(f"portfolio value is {value} on {day.date()}")
    tradeable = np.isfinite(leg_returns)
    if (target[~tradeable] > 0).any():
        raise OrderError(f"order targets an asset with no price on {day.date()}")
    want = target * value
    traded = np.abs(want - h)
    fee = float((traded * cost_row).sum())
    # Fees come out of the post-trade portfolio pro rata, so the target weights hold
    # after costs: holdings and cash both shrink by the same factor.
    scale = (value - fee) / value
    return want * scale, (value - want.sum()) * scale, float(traded.sum()), fee


def static_tranches(weights: Mapping[str, float], dates: pd.DatetimeIndex, *,
                    every: int, offsets: Sequence[int]) -> list[Tranche]:
    """Constant target weights rebalanced (at the open) every ``every`` sessions, one
    tranche per offset. The reference portfolio uses this, as can any static rule."""
    w = pd.Series(weights, dtype=float)
    out = []
    for off in offsets:
        days = dates[off::every]
        orders = pd.DataFrame([w.to_dict()] * len(days), index=days)
        out.append(Tranche(open_orders=orders, close_orders=pd.DataFrame()))
    return out

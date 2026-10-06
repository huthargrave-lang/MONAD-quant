"""
MONAD Quant — Closed-end-fund discount selection: the rules and their frozen grid
(domain ``cef_discount``, family ``cef_discount.v1``).

The question: within the universe of listed closed-end funds, does buying the funds
trading at the deepest discount to NAV, relative to their own history, beat simply owning
the whole universe? Discount mean reversion is documented (Thompson 1978; Pontiff 1995)
and is a capacity-constrained effect, the kind an institution cannot harvest at size, so it
is a plausible edge for a small account where the liquid-ETF timing rules
(F404704/F404705) were not.

Everything below was fixed on 2026-10-05, BEFORE the price snapshot was inspected for
returns. The NAV panel's coverage and universe size were known; the dates of the search
were not chosen on them.

  * Signals, as of each decision session t, from the weekly NAV panel (``NavPanel.as_of``:
    observations dated on or before t only):
      - ``level``: the latest discount, price / NAV - 1;
      - ``z52``:   that discount's z-score against the fund's own last 52 weekly
                   observations (including the latest);
      - ``z52_cat``: z52, but selection is WITHIN each CEFConnect category (municipal,
                   high yield, equity...), so the strategy cannot just load on whichever
                   category is cheap.
  * Eligible at t: priced in the snapshot at t, listed for ``MIN_LISTED_SESSIONS``, with
    ``MIN_WEEKS`` of NAV history, the latest dated within ``MAX_STALE_DAYS``.
  * Selection: the cheapest fraction f (lowest signal) of eligible funds, at least
    ``MIN_HOLDINGS``, equal weight. For ``z52_cat``, the cheapest fraction f of each category
    with at least ``MIN_CATEGORY`` eligible members.
  * Execution: decided at t's close, traded at the CLOSE of t+1 (``close_orders``): many CEF
    opens on Yahoo are synthesised, and the evaluator refuses open orders into such assets.
  * Cadence: every 21 sessions, 21 staggered tranches.
  * Benchmark (``cef_equal_weight``): every eligible fund, equal weight, same cadence,
    tranches, execution and costs. The comparison isolates SELECTION.
"""
from __future__ import annotations

import itertools
from typing import Mapping

import numpy as np
import pandas as pd

from src.research.cef_data import NavPanel
from src.research.daily_classes import MONTH, OFFSETS
from src.research.daily_data import Snapshot
from src.research.daily_strategy import Tranche

MIN_LISTED_SESSIONS = 252
MIN_WEEKS = 52
MAX_STALE_DAYS = 14
MIN_HOLDINGS = 5
MIN_CATEGORY = 5
#: The scoring window starts at the first session with at least this many eligible funds,
#: so the selection always chooses from a real cross-section.
MIN_ELIGIBLE_FOR_WINDOW = 60

REFERENCE = {"class": "cef_equal_weight", "params": {}}


def grid() -> list[dict]:
    """The first search, frozen: 6 points (``GRIDS`` lists every search)."""
    return [{"class": "cef_discount", "params": {"signal": sig, "fraction": f}}
            for sig, f in itertools.product(("level", "z52", "z52_cat"), (0.2, 0.1))]


def _signals(snap: Snapshot, panel: NavPanel) -> dict:
    """Session-indexed frames (as of each session) over the funds in both datasets.

    Rolling statistics run over each fund's OWN observations, so a removed inconsistent
    row (``cef_data.MAX_BAD_ROW_SHARE``) costs that week, not a year of eligibility."""
    funds = sorted(set(panel.price.columns) & set(snap.assets))
    disc = panel.discount[funds]
    z = pd.DataFrame(index=disc.index, columns=funds, dtype=float)
    obs = pd.DataFrame(index=disc.index, columns=funds, dtype="datetime64[ns]")
    for f in funds:
        d = disc[f].dropna()
        roll = d.rolling(MIN_WEEKS, min_periods=MIN_WEEKS)
        z.loc[d.index, f] = ((d - roll.mean()) / roll.std()).to_numpy()
        obs.loc[d.index, f] = d.index
    sessions = snap.dates
    as_of = lambda frame: panel.as_of(frame, sessions)          # noqa: E731
    last_obs = as_of(obs)
    age_days = (sessions.to_numpy()[:, None] - last_obs.to_numpy(dtype="datetime64[ns]")) \
        / np.timedelta64(1, "D")
    fresh = pd.DataFrame(age_days <= MAX_STALE_DAYS, index=sessions, columns=funds)
    priced = snap.close[funds].notna()
    listed = priced.cumsum() >= MIN_LISTED_SESSIONS
    z_now = as_of(z)
    eligible = priced & listed & z_now.notna() & fresh
    return {"funds": funds, "level": as_of(disc), "z52": z_now, "eligible": eligible}


def eligible_counts(snap: Snapshot, panel: NavPanel) -> pd.Series:
    return _signals(snap, panel)["eligible"].sum(axis=1)


def scoring_start(snap: Snapshot, panel: NavPanel) -> pd.Timestamp:
    counts = eligible_counts(snap, panel)
    ok = counts[counts >= MIN_ELIGIBLE_FOR_WINDOW]
    if not len(ok):
        raise ValueError(f"never {MIN_ELIGIBLE_FOR_WINDOW} eligible funds")
    return ok.index[0]


def _select(row_signal: pd.Series, row_eligible: pd.Series, fraction: float,
            categories: Mapping[str, str] | None) -> list[str]:
    s = row_signal[row_eligible & row_signal.notna()]
    if categories is None:
        n = max(MIN_HOLDINGS, int(np.floor(len(s) * fraction)))
        return list(s.sort_values(kind="mergesort").index[:n]) if len(s) >= MIN_HOLDINGS else []
    picks = []
    cats = pd.Series({f: categories.get(f) for f in s.index})
    for _, members in s.groupby(cats):
        if len(members) < MIN_CATEGORY:
            continue
        n = max(1, int(np.floor(len(members) * fraction)))
        picks += list(members.sort_values(kind="mergesort").index[:n])
    return sorted(picks) if len(picks) >= MIN_HOLDINGS else []


def _tranches(weights_by_decision: pd.DataFrame, dates: pd.DatetimeIndex) -> list[Tranche]:
    out = []
    for off in OFFSETS:
        days = dates[off::MONTH].intersection(weights_by_decision.index)
        out.append(Tranche(open_orders=pd.DataFrame(),
                           close_orders=weights_by_decision.loc[days]))
    return out


def decide(snap: Snapshot, panel: NavPanel, point: Mapping) -> list[Tranche]:
    sig = _signals(snap, panel)
    funds, elig = sig["funds"], sig["eligible"]
    dates = snap.dates
    decision_days = sorted({d for off in OFFSETS for d in dates[off::MONTH]})
    rows = {}
    if point["class"] == "cef_equal_weight":
        for d in decision_days:
            e = elig.loc[d]
            members = list(e.index[e])
            if len(members) >= MIN_HOLDINGS:
                rows[d] = {f: 1.0 / len(members) for f in members}
    elif point["class"] == "cef_discount":
        p = point["params"]
        signal = sig["z52"] if p["signal"] in ("z52", "z52_cat") else sig["level"]
        cats = panel.category if p["signal"] == "z52_cat" else None
        for d in decision_days:
            picks = _select(signal.loc[d], elig.loc[d], float(p["fraction"]), cats)
            if picks:
                rows[d] = {f: 1.0 / len(picks) for f in picks}
    elif point["class"] == "cef_taxloss":
        return taxloss(snap, panel, point)
    elif point["class"] == "cef_banded":
        return banded(snap, panel, point)
    else:
        raise ValueError(f"unknown CEF class {point['class']!r}")
    w = pd.DataFrame.from_dict(rows, orient="index").reindex(columns=funds).fillna(0.0)
    w.index = pd.DatetimeIndex(w.index)
    return _tranches(w.sort_index(), dates)


# ── the tax-loss season (the 2026-10-06 second CEF search) ──────────────────
TAXLOSS_ENTRY = (12, 15)          # first session on or after 15 December decides the entry
TAXLOSS_FRACTION = 0.2


def taxloss_grid() -> list[dict]:
    """Frozen before it ran: 2 points. Selection by the year's worst total return (the
    tax-loss candidates) or by the year's largest discount widening."""
    return [{"class": "cef_taxloss", "params": {"signal": s}} for s in ("ytd_return", "ytd_discount")]


def taxloss(snap: Snapshot, panel: NavPanel, point: Mapping) -> list[Tranche]:
    """CEF tax-loss selling (Brauer & Chang 1990): outside the season, EXACTLY the
    equal-weight benchmark's orders; from the first session on or after 15 December to
    the last session of January, every tranche holds the cheapest ``TAXLOSS_FRACTION`` of
    eligible funds by the year's total return (``ytd_return``) or discount change
    (``ytd_discount``), measured from the previous year's last session. Base rebalances
    that would execute inside the season are suppressed; at exit every tranche returns to
    the equal-weight universe. The active series is therefore near zero outside the season
    and isolates it."""
    from src.research.daily_classes import total_return_index

    sig = _signals(snap, panel)
    funds, elig = sig["funds"], sig["eligible"]
    dates = snap.dates
    tr = total_return_index(snap.returns())[funds]
    level = sig["level"]
    year_end = pd.Series(dates, index=dates).groupby(dates.year).max()
    base = decide(snap, panel, REFERENCE)
    entries, exits, picks_at = [], [], {}
    for year in sorted(set(dates.year)):
        start = pd.Timestamp(year=year, month=TAXLOSS_ENTRY[0], day=TAXLOSS_ENTRY[1])
        d_in = dates[dates >= start]
        jan = dates[(dates.year == year + 1) & (dates.month == 1)]
        if year - 1 not in year_end.index or not len(d_in) or not len(jan):
            continue
        d_in, d_out, prev_end = d_in[0], jan[-1], year_end[year - 1]
        if point["params"]["signal"] == "ytd_return":
            signal = tr.loc[d_in] / tr.loc[prev_end] - 1.0
        elif point["params"]["signal"] == "ytd_discount":
            signal = level.loc[d_in] - level.loc[prev_end]
        else:
            raise ValueError(f"unknown tax-loss signal {point['params']['signal']!r}")
        chosen = _select(signal, elig.loc[d_in], TAXLOSS_FRACTION, None)
        if not chosen:
            continue
        entries.append(d_in)
        exits.append(d_out)
        picks_at[d_in] = {f: 1.0 / len(chosen) for f in chosen}
    pos = {d: i for i, d in enumerate(dates)}
    windows = [(pos[a] + 1, pos[b] + 1) for a, b in zip(entries, exits)]   # execution sessions

    def inside(decision) -> bool:
        x = pos[decision] + 1
        return any(lo < x <= hi for lo, hi in windows)

    exit_rows = {}
    for d in exits:
        e = elig.loc[d]
        members = list(e.index[e])
        if len(members) >= MIN_HOLDINGS:
            exit_rows[d] = {f: 1.0 / len(members) for f in members}
    out = []
    for tr_ in base:
        kept = tr_.close_orders.loc[[d for d in tr_.close_orders.index if not inside(d)]]
        extra = pd.DataFrame.from_dict({**picks_at, **exit_rows}, orient="index")
        frame = pd.concat([kept, extra]).reindex(columns=funds).fillna(0.0)
        frame = frame[~frame.index.duplicated(keep="last")].sort_index()
        frame.index = pd.DatetimeIndex(frame.index)
        out.append(Tranche(open_orders=pd.DataFrame(), close_orders=frame))
    return out


# ── hysteresis (the 2026-10-06 third CEF search) ────────────────────────────
def banded_grid() -> list[dict]:
    """Frozen before it ran: 4 points. Enter at the cheapest 20%; exit only when a holding
    leaves the cheapest ``exit`` fraction. The v1 search found the within-category z-score
    the strongest signal but its 12x/yr turnover consumed the edge (F404706); banding is the
    standard way to keep a signal while trading less."""
    return [{"class": "cef_banded", "params": {"signal": sig, "exit": ex}}
            for sig, ex in itertools.product(("level", "z52_cat"), (0.4, 0.5))]


def _percentile_ranks(signal: pd.Series, eligible: pd.Series, categories) -> pd.Series:
    """Rank in (0, 1] among eligible funds (cheapest = smallest); within category when
    ``categories`` is given, categories under MIN_CATEGORY members excluded."""
    s = signal[eligible & signal.notna()]
    if categories is None:
        return s.rank(method="first", pct=True)
    cats = pd.Series({f: categories.get(f) for f in s.index})
    out = []
    for _, members in s.groupby(cats):
        if len(members) >= MIN_CATEGORY:
            out.append(members.rank(method="first", pct=True))
    return pd.concat(out) if out else pd.Series(dtype=float)


def banded(snap: Snapshot, panel: NavPanel, point: Mapping) -> list[Tranche]:
    """Hysteresis selection, per tranche: at each of the tranche's rebalance decisions,
    keep every holding still eligible and inside the cheapest ``exit`` fraction, add every
    fund newly inside the cheapest ``TAXLOSS_FRACTION`` (20%), equal weight. A tranche's
    holdings depend on its own earlier decisions, so each is computed in order; nothing
    after a decision date is read."""
    p = point["params"]
    exit_frac = float(p["exit"])
    if not 0.2 < exit_frac < 1.0:
        raise ValueError("exit fraction must be between the 20% entry and 100%")
    sig = _signals(snap, panel)
    funds, elig = sig["funds"], sig["eligible"]
    signal = sig["z52"] if p["signal"] == "z52_cat" else sig["level"]
    cats = panel.category if p["signal"] == "z52_cat" else None
    dates = snap.dates
    out = []
    for off in OFFSETS:
        held: set = set()
        rows = {}
        for d in dates[off::MONTH]:
            ranks = _percentile_ranks(signal.loc[d], elig.loc[d], cats)
            if len(ranks) < MIN_HOLDINGS:
                continue
            keep = {f for f in held if f in ranks.index and ranks[f] <= exit_frac}
            enter = set(ranks.index[ranks <= TAXLOSS_FRACTION])
            held = keep | enter
            if len(held) >= MIN_HOLDINGS:
                rows[d] = {f: 1.0 / len(held) for f in held}
        w = pd.DataFrame.from_dict(rows, orient="index").reindex(columns=funds).fillna(0.0)
        w.index = pd.DatetimeIndex(w.index)
        out.append(Tranche(open_orders=pd.DataFrame(), close_orders=w.sort_index()))
    return out


GRIDS = {"v1": grid, "taxloss": taxloss_grid, "banded": banded_grid}


def tiers(snap: Snapshot, panel: NavPanel) -> dict:
    """Every fund in the panel trades at the CEF cost tier."""
    return {f: "cef" for f in panel.price.columns if f in snap.assets}


def truncation_violations(snap: Snapshot, panel: NavPanel, point: Mapping, cuts) -> list[str]:
    """The look-ahead check with BOTH datasets erased after each cut: prices in the
    snapshot and observations in the NAV panel."""
    from src.research import allocation_stats as stats
    from src.research.cef_data import masked_after as panel_masked

    full = decide(snap, panel, point)
    problems = []
    for cut in cuts:
        cut = pd.Timestamp(cut)
        cut_tr = decide(stats.masked_after(snap, cut), panel_masked(panel, cut), point)
        problems += stats.compare_orders(full, cut_tr, cut)
    return problems

"""
MONAD Quant — Country ETF selection against the equal-weight country universe (domain
``country_select``, family ``country_select.v1``).

Question: within the iShares single-country ETFs, does selecting countries by a published
cross-sectional signal beat owning every listed country equally? Country-index momentum
is one of the effects in Asness, Moskowitz & Pedersen (2013), "Value and Momentum
Everywhere"; short-term reversal and low volatility are the other standard candidates.
Fully invested in both legs, so the comparison isolates SELECTION (the CEF result,
F404706/H404702, was a selection effect; timing rules were not, F404704).

Frozen 2026-10-06, before any return on the snapshot was examined:
  * signals at a close, from total-return indices through that close: momentum over 6 or
    12 months skipping the latest month (highest third held); 1-month return (lowest third
    held: reversal); 63-session volatility (lowest third held);
  * eligible: listed for 13 months and priced; at least ``MIN_HOLDINGS`` funds selected;
  * execution at the NEXT session's open, every 21 sessions in 21 tranches, equal weight;
  * costs: tier2 (12 bps one-way before 2010, 5 after) for every country fund: thinner
    books than the big ETFs;
  * window: from the first session with ``MIN_ELIGIBLE`` eligible countries.

Survivorship: today's listings only. Country ETFs rarely close, but some have (Global
X Colombia, GXG, delisted), so the universe misses a few failures. Disclosed, not assumed away.
"""
from __future__ import annotations

from typing import Mapping

import pandas as pd

from src.research.cef_classes import _select
from src.research.daily_classes import MONTH, OFFSETS, total_return_index
from src.research.daily_data import SessionReturns, Snapshot
from src.research.daily_strategy import Tranche

UNIVERSE = ("EWA EWC EWD EWG EWH EWI EWJ EWK EWL EWM EWN EWO EWP EWQ EWS EWT EWU EWW EWY EWZ "
            "EZA ECH TUR THD EIDO EPHE INDA MCHI EPOL ENZL EIS KSA QAT UAE EPU ARGT NORW EDEN "
            "EFNL EIRL VNM").split()
LISTED_SESSIONS = 13 * MONTH
VOL_WINDOW = 63
FRACTION = 1 / 3
MIN_HOLDINGS = 4
MIN_ELIGIBLE = 15
ERAS = (("start", "2007-12-31"), ("2008-01-01", "2016-12-31"), ("2017-01-01", "end"))
REFERENCE = {"class": "country_equal_weight", "params": {}}


def grid() -> list[dict]:
    return ([{"class": "country_select", "params": {"signal": "momentum", "months": m}} for m in (6, 12)]
            + [{"class": "country_select", "params": {"signal": "reversal", "months": 1}},
               {"class": "country_select", "params": {"signal": "low_vol", "months": 3}}])


GRIDS = {"v1": grid}


def _frames(snap: Snapshot, rets: SessionReturns | None):
    rets = rets or snap.returns()
    funds = [f for f in UNIVERSE if f in snap.assets]
    tr = total_return_index(rets)[funds]
    priced = snap.close[funds].notna()
    eligible = priced & (priced.cumsum() >= LISTED_SESSIONS)
    return funds, tr, eligible


def eligible_counts(snap: Snapshot) -> pd.Series:
    return _frames(snap, None)[2].sum(axis=1)


def scoring_start(snap: Snapshot) -> pd.Timestamp:
    c = eligible_counts(snap)
    ok = c[c >= MIN_ELIGIBLE]
    if not len(ok):
        raise ValueError(f"never {MIN_ELIGIBLE} eligible countries")
    return ok.index[0]


def decide(snap: Snapshot, point: Mapping, rets: SessionReturns | None = None) -> list[Tranche]:
    funds, tr, elig = _frames(snap, rets)
    if point["class"] == "country_equal_weight":
        score = None
    elif point["class"] == "country_select":
        p = point["params"]
        if p["signal"] == "momentum":
            L = int(p["months"]) * MONTH
            score = -(tr.shift(MONTH) / tr.shift(MONTH + L) - 1.0)      # lowest = strongest
        elif p["signal"] == "reversal":
            score = tr / tr.shift(MONTH) - 1.0                           # lowest = biggest loser
        elif p["signal"] == "low_vol":
            score = (tr / tr.shift(1) - 1.0).rolling(VOL_WINDOW).std()
        else:
            raise ValueError(f"unknown country signal {p['signal']!r}")
    else:
        raise ValueError(f"unknown country class {point['class']!r}")
    out = []
    for off in OFFSETS:
        rows = {}
        for d in snap.dates[off::MONTH]:
            e = elig.loc[d]
            if score is None:
                members = list(e.index[e])
            else:
                s = score.loc[d]
                n_ok = int((e & s.notna()).sum())
                members = _select(s, e, FRACTION, None) if n_ok >= MIN_ELIGIBLE else []
                members = members if len(members) >= MIN_HOLDINGS else []
            if members:
                rows[d] = {f: 1.0 / len(members) for f in members}
        w = pd.DataFrame.from_dict(rows, orient="index").reindex(columns=funds).fillna(0.0)
        w.index = pd.DatetimeIndex(w.index)
        out.append(Tranche(open_orders=w.sort_index(), close_orders=pd.DataFrame()))
    return out


def tiers(snap: Snapshot) -> dict:
    return {f: "tier2" for f in UNIVERSE if f in snap.assets}


def truncation_violations(snap: Snapshot, point: Mapping, cuts) -> list[str]:
    from src.research import allocation_stats as stats
    full = decide(snap, point)
    out = []
    for cut in cuts:
        cut = pd.Timestamp(cut)
        out += stats.compare_orders(full, decide(stats.masked_after(snap, cut), point), cut)
    return out


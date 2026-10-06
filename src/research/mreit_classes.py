"""
MONAD Quant — mortgage REIT book-value discount selection: a second disjoint test of the
CEF discount mechanism (domain ``mreit_discount``, family ``mreit_discount.v1``).

The H404701 rule (hold the cheapest fraction by discount to NAV), unchanged in spirit, on
listed mortgage REITs (src/research/mreit_data.py): vehicles whose book is mostly marked
securities, priced against book value per common share. Protocol:
docs/research/MREIT_DISCOUNT_TEST.md, frozen before any mREIT price was loaded.

  * discount at session t = close_t / book value per common share known at t - 1, using
    the latest 10-Q/10-K value known by t (filed date + 1 day); eligible if priced, listed
    for 126 sessions, and the known value describes a period at most 200 days old;
  * hold the cheapest 1/5 or 1/3 of eligible mREITs, equal weight, at least 4;
  * decided at a close, traded at the next close, every 21 sessions in 21 tranches, at the
    CEF cost tier (30/15 bps one-way);
  * benchmark: every eligible mREIT, equal weight, same cadence and costs;
  * window: from the first session with 12 eligible mREITs (the universe is about 20).
"""
from __future__ import annotations

from typing import Mapping

import pandas as pd

from src.research.bdc_data import BdcPanel
from src.research.cef_classes import _select
from src.research.daily_classes import MONTH, OFFSETS
from src.research.daily_data import Snapshot
from src.research.daily_strategy import Tranche

LISTED_SESSIONS = 126
MAX_BV_AGE_DAYS = 200
MIN_HOLDINGS = 4
MIN_ELIGIBLE = 12
ERAS = (("start", "2016-12-31"), ("2017-01-01", "2021-12-31"), ("2022-01-01", "end"))
REFERENCE = {"class": "mreit_equal_weight", "params": {}}
PANEL_PREFIX = "MREITBV"


def grid() -> list[dict]:
    return [{"class": "mreit_discount", "params": {"fraction": f}} for f in (0.2, 1 / 3)]


GRIDS = {"v1": grid}


def _frames(snap: Snapshot, panel: BdcPanel):
    names = sorted(set(panel.rows["ticker"]) & set(snap.assets))
    bv = panel.nav_known(snap.dates).reindex(columns=names)
    age = panel.period_age_days(snap.dates).reindex(columns=names)
    close = snap.close[names]
    priced = close.notna()
    eligible = priced & (priced.cumsum() >= LISTED_SESSIONS) & bv.notna() & (age <= MAX_BV_AGE_DAYS)
    return names, close / bv - 1.0, eligible


def scoring_start(snap: Snapshot, panel: BdcPanel) -> pd.Timestamp:
    c = _frames(snap, panel)[2].sum(axis=1)
    ok = c[c >= MIN_ELIGIBLE]
    if not len(ok):
        raise ValueError(f"never {MIN_ELIGIBLE} eligible mREITs")
    return ok.index[0]


def decide(snap: Snapshot, panel: BdcPanel, point: Mapping) -> list[Tranche]:
    names, disc, elig = _frames(snap, panel)
    out = []
    for off in OFFSETS:
        rows = {}
        for d in snap.dates[off::MONTH]:
            e = elig.loc[d]
            if point["class"] == "mreit_equal_weight":
                members = list(e.index[e])
            elif point["class"] == "mreit_discount":
                members = _select(disc.loc[d], e, float(point["params"]["fraction"]), None)
            else:
                raise ValueError(f"unknown mREIT class {point['class']!r}")
            if len(members) >= MIN_HOLDINGS:
                rows[d] = {f: 1.0 / len(members) for f in members}
        w = pd.DataFrame.from_dict(rows, orient="index").reindex(columns=names).fillna(0.0)
        w.index = pd.DatetimeIndex(w.index)
        out.append(Tranche(open_orders=pd.DataFrame(), close_orders=w.sort_index()))
    return out


def tiers(snap: Snapshot, panel: BdcPanel) -> dict:
    return {f: "cef" for f in set(panel.rows["ticker"]) & set(snap.assets)}


def masked_panel(panel: BdcPanel, cut: pd.Timestamp) -> BdcPanel:
    keep = panel.rows["known"] <= pd.Timestamp(cut)
    return BdcPanel(sha=f"{panel.sha}@{pd.Timestamp(cut).date()}", rows=panel.rows.loc[keep],
                    manifest=panel.manifest)


def truncation_violations(snap: Snapshot, panel: BdcPanel, point: Mapping, cuts) -> list[str]:
    from src.research import allocation_stats as stats
    full = decide(snap, panel, point)
    out = []
    for cut in cuts:
        cut = pd.Timestamp(cut)
        out += stats.compare_orders(full, decide(stats.masked_after(snap, cut),
                                                 masked_panel(panel, cut), point), cut)
    return out

"""
MONAD Quant — BDC discount selection: an out-of-sample test of the CEF mechanism (domain
``bdc_discount``, family ``bdc_discount.v1``).

The CEF discount rule (H404701: hold the cheapest fraction by raw discount to NAV) is
re-tested, unchanged in spirit, on a disjoint universe: listed business development
companies (src/research/bdc_data.py), which are NAV vehicles but not closed-end funds and
are absent from the CEF panel. If buying below NAV is a structural edge in listed NAV
vehicles, it should show up here too. Power is low (point-in-time NAVs exist only from
2022), so a null here would not refute it, and a positive result in an untouched universe
would corroborate it.

Frozen 2026-10-06, before any return on the snapshot was examined:
  * discount at session t = close_t / NAV known at t - 1, using the latest 10-Q/10-K NAV
    known by t (filed date + 1 day); eligible if priced, listed for 126 sessions, and the
    known NAV describes a period at most 200 days old;
  * hold the cheapest 1/3 or 1/5 of eligible BDCs, equal weight, at least 5;
  * decided at a close, traded at the next close, every 21 sessions in 21 tranches, at the
    CEF cost tier (30/15 bps one-way);
  * benchmark: every eligible BDC, equal weight, same cadence and costs;
  * window: from the first session with 20 eligible BDCs.
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
MAX_NAV_AGE_DAYS = 200
MIN_HOLDINGS = 5
MIN_ELIGIBLE = 20
ERAS = (("start", "2023-12-31"), ("2024-01-01", "2024-12-31"), ("2025-01-01", "end"))
REFERENCE = {"class": "bdc_equal_weight", "params": {}}


def grid() -> list[dict]:
    return [{"class": "bdc_discount", "params": {"fraction": f}} for f in (1 / 3, 0.2)]


GRIDS = {"v1": grid}


def _frames(snap: Snapshot, panel: BdcPanel):
    funds = sorted(set(panel.rows["ticker"]) & set(snap.assets))
    nav = panel.nav_known(snap.dates).reindex(columns=funds)
    age = panel.period_age_days(snap.dates).reindex(columns=funds)
    close = snap.close[funds]
    priced = close.notna()
    eligible = priced & (priced.cumsum() >= LISTED_SESSIONS) & nav.notna() & (age <= MAX_NAV_AGE_DAYS)
    return funds, close / nav - 1.0, eligible


def scoring_start(snap: Snapshot, panel: BdcPanel) -> pd.Timestamp:
    c = _frames(snap, panel)[2].sum(axis=1)
    ok = c[c >= MIN_ELIGIBLE]
    if not len(ok):
        raise ValueError(f"never {MIN_ELIGIBLE} eligible BDCs")
    return ok.index[0]


def decide(snap: Snapshot, panel: BdcPanel, point: Mapping) -> list[Tranche]:
    funds, disc, elig = _frames(snap, panel)
    out = []
    for off in OFFSETS:
        rows = {}
        for d in snap.dates[off::MONTH]:
            e = elig.loc[d]
            if point["class"] == "bdc_equal_weight":
                members = list(e.index[e])
            elif point["class"] == "bdc_discount":
                members = _select(disc.loc[d], e, float(point["params"]["fraction"]), None)
            else:
                raise ValueError(f"unknown BDC class {point['class']!r}")
            if len(members) >= MIN_HOLDINGS:
                rows[d] = {f: 1.0 / len(members) for f in members}
        w = pd.DataFrame.from_dict(rows, orient="index").reindex(columns=funds).fillna(0.0)
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

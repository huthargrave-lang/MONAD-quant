"""
MONAD Quant — the CEF discount mechanism as a live product (domain ``cef_product``,
family ``cef_product.v1``), exactly as frozen in docs/research/CEF_PRODUCT_PROTOCOL.md
before any CEFS or PCEF price was loaded.

H404702 finds that buying closed-end funds cheap against their own discount history
beats owning them all, in a backtest. Saba Capital's ETF (CEFS, since 2017) runs a
version of that mechanism live: it buys discounted CEFs and agitates to close the
discounts. A broad CEF index ETF (PCEF) owns the universe. The comparison is an
out-of-sample, survivorship-free test of whether the mechanism survives real trading,
fees and capacity, chosen by nobody in this repo.

  * candidate (``static_product``, CEFS): 100% CEFS; benchmark (``product_benchmark``):
    100% PCEF; every 21 sessions in 21 tranches at the open, tier1 costs;
  * window: from the first session both are priced for 21 sessions.
"""
from __future__ import annotations

from typing import Mapping

import pandas as pd

from src.research.daily_classes import MONTH, OFFSETS
from src.research.daily_data import Snapshot, common_start
from src.research.daily_strategy import Tranche, static_tranches

BENCH = "PCEF"
CANDIDATE = "CEFS"
ERAS = (("start", "2019-12-31"), ("2020-01-01", "2022-12-31"), ("2023-01-01", "end"))
REFERENCE = {"class": "product_benchmark", "params": {"asset": BENCH}}
WARMUP = 21


def grid() -> list[dict]:
    return [{"class": "static_product", "params": {"asset": CANDIDATE}}]


GRIDS = {"v1": grid}


def decide(snap: Snapshot, point: Mapping) -> list[Tranche]:
    if point["class"] not in ("static_product", "product_benchmark"):
        raise ValueError(f"unknown CEF product class {point['class']!r}")
    return static_tranches({point["params"]["asset"]: 1.0}, snap.dates, every=MONTH, offsets=OFFSETS)


def scoring_start(snap: Snapshot) -> pd.Timestamp:
    return common_start(snap, [CANDIDATE, BENCH], WARMUP)


def truncation_violations(snap: Snapshot, point: Mapping, cuts) -> list[str]:
    from src.research import allocation_stats as stats
    full = decide(snap, point)
    out = []
    for cut in cuts:
        cut = pd.Timestamp(cut)
        out += stats.compare_orders(full, decide(stats.masked_after(snap, cut), point), cut)
    return out

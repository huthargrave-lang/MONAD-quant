"""
MONAD Quant — the fallen-angel premium as a credit sleeve (domain ``credit_sleeve``,
family ``credit_sleeve.v1``), exactly as frozen in docs/research/FALLEN_ANGEL_PROTOCOL.md
before any ANGL or HYG price was loaded.

Bonds cut from investment grade to high yield are sold by holders whose mandates forbid
junk, whatever the price: forced selling, the mechanism behind H404702 and F404728. A
long-only investor can own the effect through a fallen-angel index fund. The question is
a static one: as the credit sleeve of a bond alternative (D6), does a fallen-angel fund
beat the broad high-yield fund?

  * candidate (``static_sleeve``, ANGL): 100% ANGL; benchmark (``sleeve_benchmark``): 100%
    HYG (a separate class, so the report tells the two apart);
  * both rebalanced (trivially) every 21 sessions in 21 tranches at the open, tier1 costs;
  * window: from the first session both are priced for 21 sessions to the snapshot's end.
"""
from __future__ import annotations

from typing import Mapping

import pandas as pd

from src.research.daily_classes import MONTH, OFFSETS
from src.research.daily_data import Snapshot, common_start
from src.research.daily_strategy import Tranche, static_tranches

BENCH = "HYG"
ERAS = (("start", "2016-12-31"), ("2017-01-01", "2021-12-31"), ("2022-01-01", "end"))
REFERENCE = {"class": "sleeve_benchmark", "params": {"asset": BENCH}}
WARMUP = 21


def grid() -> list[dict]:
    return [{"class": "static_sleeve", "params": {"asset": "ANGL"}}]


def robustness() -> list[dict]:
    """A second fallen-angel fund from another index provider (iShares, since 2016): run
    after v1 corroborated, as a robustness check (FALLEN_ANGEL_PROTOCOL.md, amendment)."""
    return [{"class": "static_sleeve", "params": {"asset": "FALN"}}]


GRIDS = {"v1": grid, "robustness": robustness}


def decide(snap: Snapshot, point: Mapping) -> list[Tranche]:
    if point["class"] not in ("static_sleeve", "sleeve_benchmark"):
        raise ValueError(f"unknown credit class {point['class']!r}")
    return static_tranches({point["params"]["asset"]: 1.0}, snap.dates, every=MONTH, offsets=OFFSETS)


def scoring_start(snap: Snapshot) -> pd.Timestamp:
    assets = ["ANGL", BENCH] + (["FALN"] if "FALN" in snap.assets else [])
    return common_start(snap, assets, WARMUP)


def truncation_violations(snap: Snapshot, point: Mapping, cuts) -> list[str]:
    from src.research import allocation_stats as stats
    full = decide(snap, point)
    out = []
    for cut in cuts:
        cut = pd.Timestamp(cut)
        out += stats.compare_orders(full, decide(stats.masked_after(snap, cut), point), cut)
    return out

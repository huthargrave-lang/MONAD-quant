"""
MONAD Quant — a live product as an out-of-sample test of a mechanism: hold one ETF that
implements it against one ETF that owns its universe, statically.

A product has no survivorship (both funds live throughout), pays real fees and trading
costs, and was chosen by no search in this repo. Each pair is its own domain and family;
its protocol is frozen before any of its prices is loaded.

``ProductFamily`` holds the frozen choices: one or more candidate funds, each its own grid
point, against one benchmark fund (``ProductPair`` is the one-candidate case). The
classes are ``static_product`` (a candidate) and ``product_benchmark`` (the benchmark),
each 100% one fund, every 21 sessions in 21 tranches at the open. Every member is scored
from the first session all of them have been priced for 21 sessions.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import pandas as pd

from src.research.daily_classes import MONTH, OFFSETS
from src.research.daily_data import Snapshot, common_start
from src.research.daily_strategy import Tranche, static_tranches

WARMUP = 21


@dataclass(frozen=True)
class ProductFamily:
    candidates: tuple
    benchmark: str
    eras: tuple

    def __post_init__(self):
        if not self.candidates or self.benchmark in self.candidates:
            raise ValueError("a product family needs candidates distinct from its benchmark")

    @property
    def reference(self) -> dict:
        return {"class": "product_benchmark", "params": {"asset": self.benchmark}}

    def grid(self) -> list[dict]:
        return [{"class": "static_product", "params": {"asset": c}} for c in self.candidates]

    def decide(self, snap: Snapshot, point: Mapping) -> list[Tranche]:
        if point["class"] not in ("static_product", "product_benchmark"):
            raise ValueError(f"unknown product class {point['class']!r}")
        return static_tranches({point["params"]["asset"]: 1.0}, snap.dates, every=MONTH,
                               offsets=OFFSETS)

    def scoring_start(self, snap: Snapshot) -> pd.Timestamp:
        return common_start(snap, [*self.candidates, self.benchmark], WARMUP)

    def truncation_violations(self, snap: Snapshot, point: Mapping, cuts) -> list[str]:
        from src.research import allocation_stats as stats
        full = self.decide(snap, point)
        out = []
        for cut in cuts:
            cut = pd.Timestamp(cut)
            out += stats.compare_orders(full, self.decide(stats.masked_after(snap, cut), point), cut)
        return out


def ProductPair(candidate: str, benchmark: str, eras: tuple) -> ProductFamily:
    """One live product against one benchmark."""
    return ProductFamily(candidates=(candidate,), benchmark=benchmark, eras=eras)


#: Live spin-off product against mid caps (docs/research/SPINOFF_PRODUCT_PROTOCOL.md).
SPINOFF_PRODUCT = ProductPair(candidate="CSD", benchmark="IJH",
                              eras=(("start", "2012-12-31"), ("2013-01-01", "2019-12-31"),
                                    ("2020-01-01", "end")))

#: Live merger-arbitrage product against the bond leg it would replace
#: (docs/research/MERGER_ARB_PRODUCT_PROTOCOL.md).
MERGER_ARB_PRODUCT = ProductPair(candidate="MNA", benchmark="IEF",
                                 eras=(("start", "2014-12-31"), ("2015-01-01", "2020-12-31"),
                                       ("2021-01-01", "end")))

#: Live buyback product against the market (docs/research/BUYBACK_PRODUCT_PROTOCOL.md).
BUYBACK_PRODUCT = ProductPair(candidate="PKW", benchmark="SPY",
                              eras=(("start", "2012-12-31"), ("2013-01-01", "2019-12-31"),
                                    ("2020-01-01", "end")))

#: Live micro-cap product against small caps: the illiquidity premium
#: (docs/research/MICROCAP_PRODUCT_PROTOCOL.md).
MICROCAP_PRODUCT = ProductPair(candidate="IWC", benchmark="IWM",
                               eras=(("start", "2012-12-31"), ("2013-01-01", "2019-12-31"),
                                     ("2020-01-01", "end")))

# ── High-risk stock picking, live (docs/research/RISKY_PICKS_PROTOCOL.md) ────────────
#: Packaged momentum against the market, on the longest window (PDP, 2007-).
MOMENTUM_LONG = ProductPair(candidate="PDP", benchmark="SPY",
                            eras=(("start", "2009-12-31"), ("2010-01-01", "2019-12-31"),
                                  ("2020-01-01", "end")))
#: Packaged momentum, every product listed by 2015-12 (window set by QMOM).
MOMENTUM_RECENT = ProductFamily(candidates=("QMOM", "MTUM", "SPMO", "PDP"), benchmark="SPY",
                                eras=(("start", "2019-12-31"), ("2020-01-01", "2022-12-31"),
                                      ("2023-01-01", "end")))
#: High-risk ("lottery") picks: IPOs and high beta, on the longest window (SPHB, 2011-).
LOTTERY_LONG = ProductFamily(candidates=("FPX", "SPHB"), benchmark="SPY",
                             eras=(("start", "2015-12-31"), ("2016-01-01", "2020-12-31"),
                                   ("2021-01-01", "end")))
#: High-risk picks, every product listed by 2015-04 (window set by FFTY).
LOTTERY_RECENT = ProductFamily(candidates=("FPX", "SPHB", "IPO", "ARKK", "FFTY"), benchmark="SPY",
                               eras=(("start", "2019-12-31"), ("2020-01-01", "2022-12-31"),
                                     ("2023-01-01", "end")))
#: Low beta against high beta in the same S&P 500 universe (betting against beta, live).
BETA_PAIR = ProductPair(candidate="SPLV", benchmark="SPHB",
                        eras=(("start", "2015-12-31"), ("2016-01-01", "2020-12-31"),
                              ("2021-01-01", "end")))

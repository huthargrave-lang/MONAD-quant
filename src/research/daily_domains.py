"""
MONAD Quant — Daily-strategy domains: one definition of each research question's data,
rules, benchmark, costs and scoring window, shared by the search tools and the gate.

A domain answers one question against one benchmark (``daily_trials.DOMAINS``). Its
adapter says how to load the frozen data a trial names, how a grid point becomes orders,
which portfolio it is judged against, at what cost tier its assets trade, which sessions
are scored, and how look-ahead is checked. The search tool (``tools/domain_search.py``,
with ``daily_search.py`` and ``cef_search.py`` as named entry points) and the admission
gate (``tools/admit_tactical.py``) all use it,
so the gate re-runs a candidate exactly as the search ran it, and can prove so.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

import pandas as pd

from src.research import daily_classes as dc
from src.research import daily_data


@dataclass(frozen=True)
class Context:
    """The frozen data one evaluation runs on."""
    snap: daily_data.Snapshot
    panel: Any = None                  # cef_data.NavPanel for the CEF domain

    def data_spec(self, start, end) -> dict:
        from src.research.daily_trials import daily_data_spec
        return daily_data_spec(self.snap.sha, start, end,
                               panel_sha=self.panel.sha if self.panel is not None else None)


@dataclass(frozen=True)
class Domain:
    name: str
    reference: Mapping
    eras: tuple
    load: Callable[[Mapping], Context]                  # trial data spec -> Context
    decide: Callable[[Context, Mapping], list]
    tiers: Callable[[Context], dict | None]
    start: Callable[[Context], pd.Timestamp]
    truncation: Callable[[Context, Mapping, list], list]
    grids: Callable[[], dict]                            # name -> frozen grid function
    prior_search_trials: int                             # declared search the ledger cannot see
    #: The file prefix of the domain's second frozen dataset (``data["nav_panel"]``), so the
    #: gate's witness stage checks the right files (None: the domain has only a snapshot).
    panel_prefix: str | None = None

    def grid(self) -> list:
        """Every point of every frozen search in the domain."""
        return [p for g in self.grids().values() for p in g()]

    def window(self, ctx: Context) -> tuple[pd.Timestamp, pd.Timestamp]:
        return self.start(ctx), ctx.snap.dates[-1]


# ── ETF timing against the static 60/40 ──────────────────────────────────────
def _etf_load(data: Mapping) -> Context:
    return Context(snap=daily_data.load_snapshot(data["snapshot"]))


def _etf_start(ctx: Context) -> pd.Timestamp:
    """One window for every ETF grid, so all family members cover the same sessions."""
    assets = sorted({a for g in dc.GRIDS.values() for p in g() for a in dc.assets_used(p)}
                    | set(dc.assets_used(dc.REFERENCE)))
    return daily_data.common_start(ctx.snap, assets, dc.WARMUP_SESSIONS)


def _etf_truncation(ctx: Context, point: Mapping, cuts) -> list:
    from src.research import allocation_stats
    return allocation_stats.truncation_violations(ctx.snap, point, cuts)


ETF = Domain(
    name="etf_alloc", reference=dc.REFERENCE, eras=dc.ERAS, load=_etf_load,
    decide=lambda ctx, point: dc.decide(ctx.snap, point),
    tiers=lambda ctx: None, start=_etf_start, truncation=_etf_truncation,
    grids=lambda: dc.GRIDS,
    # Declared before each search ran; it only grows (history in DAILY_STRATEGIES.md):
    # the D6 arc's ~15 builds, 5 famous v1 rules x 3, FOMC and sell-in-May x 3 each, the
    # Treasury auction cycle x 3, the Fed-liquidity rule x 3 (a widely-circulated market
    # meme with many variants), the lunar and geomagnetic effects x 3 each, and the
    # month-end Treasury extension x 3.
    prior_search_trials=51)


# ── closed-end-fund selection against the equal-weight universe ─────────────
def _cef_load(data: Mapping) -> Context:
    from src.research import cef_data
    return Context(snap=daily_data.load_snapshot(data["snapshot"]),
                   panel=cef_data.load_panel(data["nav_panel"]))


def _cef():
    from src.research import cef_classes
    return cef_classes


CEF = Domain(
    name="cef_discount", reference={"class": "cef_equal_weight", "params": {}}, eras=dc.ERAS,
    load=_cef_load,
    decide=lambda ctx, point: _cef().decide(ctx.snap, ctx.panel, point),
    tiers=lambda ctx: _cef().tiers(ctx.snap, ctx.panel),
    start=lambda ctx: _cef().scoring_start(ctx.snap, ctx.panel),
    truncation=lambda ctx, point, cuts: _cef().truncation_violations(ctx.snap, ctx.panel, point, cuts),
    grids=lambda: _cef().GRIDS,
    # Discount mean reversion x 3 and the F257 pilot (4), the CEF January effect x 3 (7),
    # hysteresis as a practitioner variant x 2 (9). It only grows.
    prior_search_trials=9, panel_prefix="CEFNAV")

# ── crypto trend-following against a static half-crypto blend ───────────────
from src.research import crypto_classes as _crypto  # noqa: E402  (no import cycle)

CRYPTO = Domain(
    name="crypto_trend", reference=_crypto.REFERENCE, eras=_crypto.ERAS,
    load=lambda data: Context(snap=daily_data.load_snapshot(data["snapshot"])),
    decide=lambda ctx, point: _crypto.decide(ctx.snap, point),
    tiers=lambda ctx: _crypto.tiers(ctx.snap),
    start=lambda ctx: _crypto.scoring_start(ctx.snap),
    truncation=lambda ctx, point, cuts: _crypto.truncation_violations(ctx.snap, point, cuts),
    grids=lambda: _crypto.GRIDS,
    # Trend-following on BTC is a famous retail rule with many published MA variants:
    # counted as the survivor of 3.
    prior_search_trials=3)

# ── country ETF selection against the equal-weight country universe ─────────
from src.research import country_classes as _country  # noqa: E402

COUNTRY = Domain(
    name="country_select", reference=_country.REFERENCE, eras=_country.ERAS,
    load=lambda data: Context(snap=daily_data.load_snapshot(data["snapshot"])),
    decide=lambda ctx, point: _country.decide(ctx.snap, point),
    tiers=lambda ctx: _country.tiers(ctx.snap),
    start=lambda ctx: _country.scoring_start(ctx.snap),
    truncation=lambda ctx, point, cuts: _country.truncation_violations(ctx.snap, point, cuts),
    grids=lambda: _country.GRIDS,
    # Country momentum (AMP 2013), reversal and low volatility are published, each
    # counted as the survivor of 3 variants.
    prior_search_trials=9)

# ── BDC discount selection: an out-of-sample test of the CEF mechanism ───────
from src.research import bdc_classes as _bdc  # noqa: E402


def _bdc_load(data: Mapping) -> Context:
    from src.research import bdc_data
    return Context(snap=daily_data.load_snapshot(data["snapshot"]),
                   panel=bdc_data.load_panel(data["nav_panel"]))


BDC = Domain(
    name="bdc_discount", reference=_bdc.REFERENCE, eras=_bdc.ERAS, load=_bdc_load,
    decide=lambda ctx, point: _bdc.decide(ctx.snap, ctx.panel, point),
    tiers=lambda ctx: _bdc.tiers(ctx.snap, ctx.panel),
    start=lambda ctx: _bdc.scoring_start(ctx.snap, ctx.panel),
    truncation=lambda ctx, point, cuts: _bdc.truncation_violations(ctx.snap, ctx.panel, point, cuts),
    grids=lambda: _bdc.GRIDS,
    # A replication of the CEF mechanism the CEF family found (its search is counted
    # there); BDC price-to-NAV is also a published screen: counted as 3.
    prior_search_trials=3, panel_prefix="BDCNAV")

# ── insider purchase clusters against the small-cap index ────────────────────
from src.research import insider_classes as _ins  # noqa: E402


def _ins_load(data: Mapping) -> Context:
    from src.research import insider_data
    return Context(snap=daily_data.load_snapshot(data["snapshot"]),
                   panel=_ins.InsiderEvents(sha=data["nav_panel"],
                                            events=insider_data.load(data["nav_panel"])))


INSIDER = Domain(
    name="insider_cluster", reference=_ins.REFERENCE, eras=_ins.ERAS, load=_ins_load,
    decide=lambda ctx, point: _ins.decide(ctx.snap, ctx.panel, point),
    tiers=lambda ctx: _ins.tiers(ctx.snap, ctx.panel),
    start=lambda ctx: _ins.scoring_start(ctx.snap, ctx.panel),
    truncation=lambda ctx, point, cuts: _ins.truncation_violations(ctx.snap, ctx.panel, point, cuts),
    grids=lambda: _ins.GRIDS,
    # A published effect (Lakonishok-Lee; Cohen-Malloy-Pomorski): counted as 3.
    prior_search_trials=3, panel_prefix="INSIDER")

# ── mortgage REIT book-value discount: a second disjoint test of the CEF mechanism ──
from src.research import mreit_classes as _mreit  # noqa: E402


def _mreit_load(data: Mapping) -> Context:
    from src.research import bdc_data
    return Context(snap=daily_data.load_snapshot(data["snapshot"]),
                   panel=bdc_data.load_panel(data["nav_panel"], prefix=_mreit.PANEL_PREFIX))


MREIT = Domain(
    name="mreit_discount", reference=_mreit.REFERENCE, eras=_mreit.ERAS, load=_mreit_load,
    decide=lambda ctx, point: _mreit.decide(ctx.snap, ctx.panel, point),
    tiers=lambda ctx: _mreit.tiers(ctx.snap, ctx.panel),
    start=lambda ctx: _mreit.scoring_start(ctx.snap, ctx.panel),
    truncation=lambda ctx, point, cuts: _mreit.truncation_violations(ctx.snap, ctx.panel, point, cuts),
    grids=lambda: _mreit.GRIDS,
    # The CEF mechanism's second out-of-sample replication (docs/research/
    # MREIT_DISCOUNT_TEST.md); mREIT price-to-book is a common screen: counted as 3.
    prior_search_trials=3, panel_prefix="MREITBV")

# ── the earnings-announcement premium in small caps ─────────────────────────
from src.research import earnings_classes as _earn  # noqa: E402


def _earn_load(data: Mapping) -> Context:
    from src.research import earnings_data
    return Context(snap=daily_data.load_snapshot(data["snapshot"]),
                   panel=earnings_data.load(data["nav_panel"]))


EARNINGS = Domain(
    name="earnings_premium", reference=_earn.REFERENCE, eras=_earn.ERAS, load=_earn_load,
    decide=lambda ctx, point: _earn.decide(ctx.snap, ctx.panel, point),
    tiers=lambda ctx: _earn.tiers(ctx.snap, ctx.panel),
    start=lambda ctx: _earn.scoring_start(ctx.snap, ctx.panel),
    truncation=lambda ctx, point, cuts: _earn.truncation_violations(ctx.snap, ctx.panel, point, cuts),
    grids=lambda: _earn.GRIDS,
    # A published effect (Frazzini-Lamont 2007; Barber et al. 2013): counted as the
    # survivor of 3 variants (docs/research/EARNINGS_PREMIUM_PROTOCOL.md).
    prior_search_trials=3, panel_prefix="EARNDATES")

# ── spin-off drift ─────────────────────────────────────────────────────────
from src.research import spinoff_classes as _spin  # noqa: E402


def _spin_load(data: Mapping) -> Context:
    return Context(snap=daily_data.load_snapshot(data["snapshot"]),
                   panel=_spin.load_events(data["nav_panel"]))


SPINOFF = Domain(
    name="spinoff_drift", reference=_spin.REFERENCE, eras=_spin.ERAS, load=_spin_load,
    decide=lambda ctx, point: _spin.decide(ctx.snap, ctx.panel, point),
    tiers=lambda ctx: _spin.tiers(ctx.snap, ctx.panel),
    start=lambda ctx: _spin.scoring_start(ctx.snap, ctx.panel),
    truncation=lambda ctx, point, cuts: _spin.truncation_violations(ctx.snap, ctx.panel, point, cuts),
    grids=lambda: _spin.GRIDS,
    # A published effect (Cusatis, Miles and Woolridge 1993): counted as 3.
    prior_search_trials=3, panel_prefix="SPINEVENTS")

# ── S&P 500 deletion rebound ──────────────────────────────────────────────
from src.research import deletion_classes as _del  # noqa: E402


def _del_load(data: Mapping) -> Context:
    return Context(snap=daily_data.load_snapshot(data["snapshot"]),
                   panel=_del.load_events(data["nav_panel"]))


DELETION = Domain(
    name="index_deletion", reference=_del.REFERENCE, eras=_del.ERAS, load=_del_load,
    decide=lambda ctx, point: _del.decide(ctx.snap, ctx.panel, point),
    tiers=lambda ctx: _del.tiers(ctx.snap, ctx.panel),
    start=lambda ctx: _del.scoring_start(ctx.snap, ctx.panel),
    truncation=lambda ctx, point, cuts: _del.truncation_violations(ctx.snap, ctx.panel, point, cuts),
    grids=lambda: _del.GRIDS,
    # A published effect (Chen, Noronha and Singal 2004): counted as 3.
    prior_search_trials=3, panel_prefix="IDXDEL")

# ── the fallen-angel premium as a credit sleeve ──────────────────────────────
from src.research import credit_classes as _credit  # noqa: E402

CREDIT = Domain(
    name="credit_sleeve", reference=_credit.REFERENCE, eras=_credit.ERAS,
    load=lambda data: Context(snap=daily_data.load_snapshot(data["snapshot"])),
    decide=lambda ctx, point: _credit.decide(ctx.snap, point),
    tiers=lambda ctx: None,
    start=lambda ctx: _credit.scoring_start(ctx.snap),
    truncation=lambda ctx, point, cuts: _credit.truncation_violations(ctx.snap, point, cuts),
    grids=lambda: _credit.GRIDS,
    # A published, widely marketed effect (fallen-angel index research): counted as 3.
    prior_search_trials=3)

DOMAINS: dict[str, Domain] = {d.name: d for d in (ETF, CEF, CRYPTO, COUNTRY, BDC, INSIDER, MREIT,
                                                  EARNINGS, SPINOFF, DELETION, CREDIT)}


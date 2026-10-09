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
    #: The series the domain's verdict and familywise SPA read: "active" (member minus
    #: benchmark) or "vol_matched" (``allocation_stats.vol_matched_active``: positive in
    #: mean exactly when the member's Sharpe beats the benchmark's). ``sign`` -1 tests a
    #: predicted UNDERperformance: the SPA then asks whether the benchmark beats members.
    primary: str = "active"
    sign: int = 1

    def __post_init__(self):
        if self.primary not in ("active", "vol_matched") or self.sign not in (1, -1):
            raise ValueError(f"{self.name}: primary must be active or vol_matched, sign +-1")

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

# ── the CEF discount mechanism as a live product ───────────────────────────
from src.research import cef_product_classes as _cefp  # noqa: E402

CEF_PRODUCT = Domain(
    name="cef_product", reference=_cefp.REFERENCE, eras=_cefp.ERAS,
    load=lambda data: Context(snap=daily_data.load_snapshot(data["snapshot"])),
    decide=lambda ctx, point: _cefp.decide(ctx.snap, point),
    tiers=lambda ctx: None,
    start=lambda ctx: _cefp.scoring_start(ctx.snap),
    truncation=lambda ctx, point, cuts: _cefp.truncation_violations(ctx.snap, point, cuts),
    grids=lambda: _cefp.GRIDS,
    # One comparison, suggested by H404702's mechanism: counted as 3 to be conservative
    # (docs/research/CEF_PRODUCT_PROTOCOL.md).
    prior_search_trials=3)

# ── live products as out-of-sample tests of a mechanism ─────────────────────
from src.research import product_pairs as _pp  # noqa: E402


def _product_domain(name: str, pair: "_pp.ProductFamily", prior: int, *,
                    primary: str = "active", sign: int = 1) -> Domain:
    return Domain(
        primary=primary, sign=sign,
        name=name, reference=pair.reference, eras=pair.eras,
        load=lambda data: Context(snap=daily_data.load_snapshot(data["snapshot"])),
        decide=lambda ctx, point: pair.decide(ctx.snap, point),
        tiers=lambda ctx: None,
        start=lambda ctx: pair.scoring_start(ctx.snap),
        truncation=lambda ctx, point, cuts: pair.truncation_violations(ctx.snap, point, cuts),
        grids=lambda: {"v1": pair.grid},
        prior_search_trials=prior)


# CSD (Invesco S&P Spin-Off ETF, 2006-) vs IJH: an out-of-sample test of F404728's spin-off
# drift. A published effect, counted as 3 (docs/research/SPINOFF_PRODUCT_PROTOCOL.md).
SPINOFF_PRODUCT = _product_domain("spinoff_product", _pp.SPINOFF_PRODUCT, 3)
# MNA (IQ Merger Arbitrage ETF, 2009-) vs IEF: is merger arbitrage a better bond sleeve?
# A published premium, counted as 3 (docs/research/MERGER_ARB_PRODUCT_PROTOCOL.md).
MERGER_ARB_PRODUCT = _product_domain("merger_arb_product", _pp.MERGER_ARB_PRODUCT, 3)
# PKW (Invesco BuyBack Achievers ETF, 2006-) vs SPY: the buyback drift, live. A published
# effect, counted as 3 (docs/research/BUYBACK_PRODUCT_PROTOCOL.md).
BUYBACK_PRODUCT = _product_domain("buyback_product", _pp.BUYBACK_PRODUCT, 3)
# IWC (iShares Micro-Cap, 2005-) vs IWM: the illiquidity premium, live. A published effect,
# counted as 3 (docs/research/MICROCAP_PRODUCT_PROTOCOL.md).
MICROCAP_PRODUCT = _product_domain("microcap_product", _pp.MICROCAP_PRODUCT, 3)

# High-risk stock picking, live (docs/research/RISKY_PICKS_PROTOCOL.md). Every verdict reads
# the vol-matched series: high-risk products carry beta above 1, and beating the market by
# holding more of it is not an edge. Momentum predicts outperformance; betting against beta,
# the lottery effect and long-run IPO underperformance predict UNDERperformance (sign -1).
MOMENTUM_LONG = _product_domain("momentum_product_long", _pp.MOMENTUM_LONG, 3, primary="vol_matched")
MOMENTUM_RECENT = _product_domain("momentum_product_recent", _pp.MOMENTUM_RECENT, 3,
                                  primary="vol_matched")
LOTTERY_LONG = _product_domain("lottery_product_long", _pp.LOTTERY_LONG, 3,
                               primary="vol_matched", sign=-1)
LOTTERY_RECENT = _product_domain("lottery_product_recent", _pp.LOTTERY_RECENT, 3,
                                 primary="vol_matched", sign=-1)
BETA_PAIR = _product_domain("beta_pair_product", _pp.BETA_PAIR, 3, primary="vol_matched")


# ── Trend-timed leverage, live (docs/research/LEVERED_TREND_PROTOCOL.md) ─────────────
from src.research import levered_classes as _lv  # noqa: E402


def _levered_load(data: Mapping) -> Context:
    snap = daily_data.load_snapshot(data["snapshot"])
    bad = _lv.leg_errors(snap)
    if bad:
        raise daily_data.SnapshotError(f"levered_trend refuses snapshot {snap.sha[:12]}: "
                                       f"{len(bad)} implausible legs, first {bad[0]}")
    return Context(snap=snap)


# Prior search 7: the published rule (3) plus F404704's four SMA points, the same filter
# searched at 1x (board, 2026-10-08).
LEVERED = Domain(
    name="levered_trend", reference=_lv.REFERENCE, eras=_lv.ERAS, load=_levered_load,
    decide=lambda ctx, point: _lv.decide(ctx.snap, point),
    tiers=lambda ctx: None, start=lambda ctx: _lv.scoring_start(ctx.snap),
    truncation=lambda ctx, point, cuts: _lv.truncation_violations(ctx.snap, point, cuts),
    grids=lambda: _lv.GRIDS, prior_search_trials=7, primary="vol_matched")

# ── Commodity-to-equity linkage, confirmation (docs/research/COMMODITY_LINKAGE_CONFIRMATION.md) ─
from src.research import commodity_classes as _cc  # noqa: E402
from src.research import futures_panel as _fut  # noqa: E402

def _ratio_domain(name: str, miner: str, metal: str, prior: int, *, execution: str = "open",
                  floor=_cc.CONFIRMATION_START, eras=_cc.ERAS, tiers: Mapping | None = None,
                  grid=None, fixings: bool = False) -> Domain:
    """The frozen miner/metal ratio tilt on one pair. ``tiers``: cost tier per leg (None:
    the default ETF tiers). ``grid``: the points (default: the rule alone)."""
    points = grid if grid is not None else (lambda: _cc.ratio_grid(miner, metal, execution=execution))
    return Domain(
        name=name, reference=_cc.ratio_reference(miner, metal, execution=execution, fixings=fixings),
        eras=eras, load=lambda data: Context(snap=daily_data.load_snapshot(data["snapshot"])),
        decide=lambda ctx, point: _cc.decide_ratio(ctx.snap, point),
        tiers=(lambda ctx: None) if tiers is None else (lambda ctx: dict(tiers)),
        start=lambda ctx: _cc.ratio_start(ctx.snap, miner, metal, floor=floor),
        truncation=lambda ctx, point, cuts: _cc.ratio_truncation(ctx.snap, point, cuts),
        grids=lambda: {"v1": points}, prior_search_trials=prior)


# Prior search: every statistic of the discovery atlas, 1401 (board, 2026-10-08).
MINER_RATIO = _ratio_domain("miner_metal_ratio", "GDX", "GLD", _cc.ATLAS_CELLS)
# The same frozen rule, replicated unchanged (docs/research/MINER_TILT_REPLICATION.md).
# Prior search 2: the two choices made after seeing GDX/GLD's result (which rule to
# replicate, which pair is primary). Only silver_miner_ratio carries a verdict; the other
# three are counted robustness, contamination and placebo runs.
SILVER_RATIO = _ratio_domain("silver_miner_ratio", "SIL", "SLV", 2)
JUNIOR_RATIO = _ratio_domain("junior_miner_ratio", "GDXJ", "GLD", 2)
GOLD_SILVER_RATIO = _ratio_domain("gold_silver_ratio", "GLD", "SLV", 2)
PLACEBO_RATIO = _ratio_domain("placebo_ratio", "IWM", "SPY", 2)
OIL_TREND = Domain(
    name="oil_trend_equities", reference=_cc.TREND_REFERENCE, eras=_cc.ERAS,
    load=lambda data: Context(snap=daily_data.load_snapshot(data["snapshot"]),
                              panel=_fut.load(data["nav_panel"])),
    decide=lambda ctx, point: _cc.decide_trend(ctx.snap, ctx.panel, point),
    tiers=lambda ctx: None, start=lambda ctx: _cc.trend_start(ctx.snap, ctx.panel),
    truncation=lambda ctx, point, cuts: _cc.trend_truncation(ctx.snap, ctx.panel, point, cuts),
    grids=lambda: {"v1": _cc.trend_grid}, prior_search_trials=_cc.ATLAS_CELLS,
    panel_prefix=_fut.PREFIX, primary="vol_matched")

# ── The 1984-2005 test of the same frozen rule (docs/research/MINER_TILT_PREPERIOD.md) ──
from src.research import miner_preperiod as _mp  # noqa: E402

#: Decided only on sessions where both legs printed (``fresh``), executed at the next
#: close on a session where gold fixed (``fixings``): close-only data, stale-print guards.
_PRE_RULE = dict(execution="close", fresh=True, fixings=True)
_PRE_TIERS = {_mp.MINER: "basket_pre_decimal", _mp.PLACEBO: "basket_pre_decimal",
              _mp.GOLD_FFM: "bullion", _mp.GOLD_COMEX: "bullion"}
_ERAS_A = (("start", "1989-04-30"), ("1989-05-01", "1994-01-31"), ("1994-02-01", "end"))
_ERAS_B = (("start", "2002-12-31"), ("2003-01-01", "end"))


def _preperiod_domain(name: str, miner: str, gold: str, floor: str, eras, *, lags=(1,)) -> Domain:
    # Prior 5: the verdict gate charges the alpha already spent on this rule's promotion
    # gates (board, 2026-10-09): p_gate = worst p x (1 + 5).
    return _ratio_domain(
        name, miner, gold, 5, execution="close", floor=pd.Timestamp(floor), eras=eras,
        tiers={miner: _PRE_TIERS[miner], gold: _PRE_TIERS[gold]}, fixings=True,
        grid=lambda: [_cc.ratio_point(miner, gold, lag=k, **_PRE_RULE) for k in lags])


PRE_A = _preperiod_domain("miner_preperiod_a", _mp.MINER, _mp.GOLD_FFM, _mp.XAU_FIRST_TRADE, _ERAS_A)
PRE_B = _preperiod_domain("miner_preperiod_b", _mp.MINER, _mp.GOLD_COMEX, "2000-08-30", _ERAS_B)
PRE_PLACEBO = _preperiod_domain("placebo_preperiod", _mp.PLACEBO, _mp.GOLD_FFM, _mp.XAU_FIRST_TRADE, _ERAS_A)
PRE_LAGS = _preperiod_domain("miner_preperiod_lags", _mp.MINER, _mp.GOLD_FFM, _mp.XAU_FIRST_TRADE,
                             _ERAS_A, lags=(3, 6))


# ── CEF vs matched-ETF discount tilt (docs/research/CEF_ETF_TILT_PROTOCOL.md) ─────────
from src.research import cef_etf_tilt as _ce  # noqa: E402


def _cef_etf_load(data: Mapping) -> Context:
    inputs = _ce.load_inputs(data["nav_panel"])
    return Context(snap=daily_data.load_snapshot(data["snapshot"]), panel=inputs)


def _cef_etf_domain(name: str, grid, reference, start) -> Domain:
    # Prior 24: the metal trust's 22 plus drafts F and G (board, 2026-10-09). Not an
    # admission candidate (the gate would need worst-block p <= 0.002).
    return Domain(
        name=name, reference=reference, eras=_ce.ERAS, load=_cef_etf_load,
        decide=lambda ctx, point: _ce.decide(ctx.snap, ctx.panel, point),
        tiers=lambda ctx: _ce.tiers(ctx.panel), start=start,
        truncation=lambda ctx, point, cuts: _ce.truncation_violations(ctx.snap, ctx.panel, point, cuts),
        grids=lambda: {"v1": grid}, prior_search_trials=_ce.PRIOR, panel_prefix=_ce.PREFIX)


CEF_ETF = _cef_etf_domain("cef_etf_tilt", _ce.grid, _ce.REFERENCE, lambda ctx: _ce.scoring_start(ctx.panel))
CEF_ETF_LAG = _cef_etf_domain("cef_etf_tilt_lag", _ce.lag_grid, _ce.REFERENCE,
                              lambda ctx: _ce.scoring_start(ctx.panel))
CEF_ETF_STAGED = _cef_etf_domain("cef_etf_tilt_staged", _ce.staged_grid, _ce.STAGED_REFERENCE,
                                 lambda ctx: _ce.staged_start(ctx.snap, ctx.panel))


# ── Physical-metal trust discount tilt (docs/research/METAL_TRUST_DISCOUNT_PROTOCOL.md) ──
from src.research import metal_trust_classes as _mt  # noqa: E402
from src.research import cef_data as _cef_data  # noqa: E402

METAL_TRUST = Domain(
    name="metal_trust_discount", reference=_mt.REFERENCE, eras=_mt.ERAS,
    load=lambda data: Context(snap=daily_data.load_snapshot(data["snapshot"]),
                              panel=_cef_data.load_panel(data["nav_panel"])),
    decide=lambda ctx, point: _mt.decide(ctx.snap, ctx.panel, point),
    tiers=lambda ctx: _mt.tiers(ctx.snap, ctx.panel),
    start=lambda ctx: _mt.scoring_start(ctx.snap, ctx.panel),
    truncation=lambda ctx, point, cuts: _mt.truncation_violations(ctx.snap, ctx.panel, point, cuts),
    grids=lambda: _mt.GRIDS, prior_search_trials=_mt.PRIOR, panel_prefix="CEFNAV")

DOMAINS: dict[str, Domain] = {d.name: d for d in (ETF, CEF, CRYPTO, COUNTRY, BDC, INSIDER, MREIT,
                                                  EARNINGS, SPINOFF, DELETION, CREDIT, CEF_PRODUCT,
                                                  SPINOFF_PRODUCT, MERGER_ARB_PRODUCT,
                                                  BUYBACK_PRODUCT, MICROCAP_PRODUCT,
                                                  MOMENTUM_LONG, MOMENTUM_RECENT, LOTTERY_LONG,
                                                  LOTTERY_RECENT, BETA_PAIR, LEVERED,
                                                  MINER_RATIO, OIL_TREND, SILVER_RATIO,
                                                  JUNIOR_RATIO, GOLD_SILVER_RATIO, PLACEBO_RATIO,
                                                  METAL_TRUST, PRE_A, PRE_B, PRE_PLACEBO, PRE_LAGS,
                                                  CEF_ETF, CEF_ETF_LAG, CEF_ETF_STAGED)}


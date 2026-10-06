"""
MONAD Quant — Daily-strategy domains: one definition of each research question's data,
rules, benchmark, costs and scoring window, shared by the search tools and the gate.

A domain answers one question against one benchmark (``daily_trials.DOMAINS``). Its
adapter says how to load the frozen data a trial names, how a grid point becomes orders,
which portfolio it is judged against, at what cost tier its assets trade, which sessions
are scored, and how look-ahead is checked. The search tools (``tools/daily_search.py``,
``tools/cef_search.py``) and the admission gate (``tools/admit_tactical.py``) all use it,
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
    grid: Callable[[], list]

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
    grid=lambda: [p for g in dc.GRIDS.values() for p in g()])


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
    grid=lambda: [p for g in _cef().GRIDS.values() for p in g()])

DOMAINS: dict[str, Domain] = {d.name: d for d in (ETF, CEF)}


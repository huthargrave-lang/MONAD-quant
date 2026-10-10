"""
MONAD Quant — the 1984-2005 test of the miner/metal ratio tilt: data build and mechanical
screens, exactly as frozen in docs/research/MINER_TILT_PREPERIOD.md.

Two segments, each its own snapshot (observations kept in the private store: neither
Yahoo's index history nor the Bundesbank's Frankfurt fixings may be redistributed from a
public repo; manifests with payload hashes are committed):

  A  1983-12-19 .. 1998-12-30: ^XAU (PHLX Gold & Silver Sector index) against gold, the
     Frankfurt gold fixing (DM/kg) over the Frankfurt USD fixing (DM/USD), USD per oz;
  B  2000-08-30 .. 2005-12-30: ^XAU against COMEX gold futures (Yahoo GC=F, front month,
     unadjusted rolls, disclosed).

The calendar asset is ^GSPC (NYSE sessions). Every series is close-only. A session
without a gold observation carries the previous one and is classified:
  * explained (segment A): the Frankfurt USD fixing is also absent (the exchange was shut);
  * unexplained: anything else. Unexplained carries above 0.5% of the window's sessions
    mean NOT RUN.
The sessions at which gold printed its own observation are the manifest's fixing calendar
(``calendars``), which the rule executes on.

``screens`` are the protocol's data screens; each failure is a NOT RUN reason.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import re
from dataclasses import dataclass
from typing import Callable, Mapping

import numpy as np
import pandas as pd

from src.research import bundesbank as bb
from src.research import daily_data
from src.research.xlsx_reader import read_sheet

CALENDAR, MINER, PLACEBO = "^GSPC", "^XAU", "^GSPC"
GOLD_FFM, GOLD_COMEX = "GOLD_FFM", "GOLD_COMEX"
XAU_FIRST_TRADE = "1983-12-19"
MAX_UNEXPLAINED_SHARE = 0.005
MIN_YEARLY_XAU_COVERAGE = 0.98
EXTREME_MOVE = 0.15
WB_TOLERANCE = 0.02
FUND_PANEL = ("OPGSX", "VGPMX", "USAGX", "FSAGX", "UNWPX")
WORLD_BANK_URL = ("https://thedocs.worldbank.org/en/doc/18675f1d1639c7a34d463f59263ba0a2-0050012025/"
                  "related/CMO-Historical-Data-Monthly.xlsx")
ATTRIBUTION = ("Source: Deutsche Bundesbank (Frankfurt Stock Exchange gold fixing; Frankfurt official "
               "FX fixing); USD conversion own calculation. Index history: Yahoo Finance.")


@dataclass(frozen=True)
class Segment:
    name: str
    fetch_start: str            # first date fetched (inclusive)
    fetch_end: str              # exclusive
    floor: str                  # scoring starts at the first session on/after it with warm-up
    gold: str                   # the gold asset's name in the snapshot


SEGMENTS = {
    "A": Segment("A", XAU_FIRST_TRADE, "1999-01-01", XAU_FIRST_TRADE, GOLD_FFM),
    "B": Segment("B", "2000-08-30", "2006-01-01", "2000-08-30", GOLD_COMEX),
}


class NotRun(RuntimeError):
    """A frozen screen failed: the protocol closes NOT RUN with these reasons."""

    def __init__(self, reasons):
        super().__init__("; ".join(reasons))
        self.reasons = list(reasons)


@dataclass(frozen=True)
class GoldBuild:
    bars: pd.DataFrame
    fixings: list               # sessions with the asset's own observation
    explained: list             # carried sessions with the exchange shut
    unexplained: list           # every other carried session
    report: dict


def _carry_split(carried: list, fx_dates: pd.DatetimeIndex | None) -> tuple[list, list]:
    if fx_dates is None:
        return [], list(carried)
    fx = {d.date().isoformat() for d in fx_dates}
    return [d for d in carried if d not in fx], [d for d in carried if d in fx]


def build_gold(segment: Segment, sessions: pd.DatetimeIndex, *,
               bbk_get: Callable = bb._http_get,
               yahoo: Callable = daily_data.yahoo_raw) -> GoldBuild:
    """The segment's gold leg as close-only bars on NYSE ``sessions``."""
    end_incl = (pd.Timestamp(segment.fetch_end) - pd.Timedelta(days=1)).date().isoformat()
    if segment.gold == GOLD_FFM:
        usd, rep = bb.frankfurt_gold_usd(segment.fetch_start, end_incl, get=bbk_get)
        fx = bb.fetch_series(*bb.DEM_PER_USD, segment.fetch_start, end_incl, get=bbk_get)
        fx_dates = fx.index
    else:
        h = yahoo("GC=F", segment.fetch_start, segment.fetch_end)
        usd = h["Close"].dropna().rename(GOLD_COMEX)
        usd = usd[usd > 0]
        rep, fx_dates = {"source": "Yahoo GC=F (front month, unadjusted rolls)", "observations": int(len(usd))}, None
    sb = bb.bars_on_sessions(usd, sessions)
    explained, unexplained = _carry_split(sb.carried, fx_dates)
    fixings = [d.date().isoformat() for d in sb.bars.index if d.date().isoformat() not in set(sb.carried)]
    rep = {**rep, "sessions": int(len(sb.bars)), "carried_explained": len(explained),
           "carried_unexplained": len(unexplained), "dropped_off_calendar": sb.dropped_off_calendar}
    return GoldBuild(bars=sb.bars, fixings=fixings, explained=explained, unexplained=unexplained,
                     report=rep)


def build_segment(segment: Segment, *, yahoo: Callable = daily_data.yahoo_raw,
                  bbk_get: Callable = bb._http_get, private_dir=None, data_dir=None,
                  **fetchers) -> tuple[str, GoldBuild]:
    """Fetch, screen the carries, and write the segment's private snapshot: ^GSPC
    (calendar), ^XAU, gold. Returns (sha, gold build)."""
    cal = yahoo(CALENDAR, segment.fetch_start, segment.fetch_end)
    gold = build_gold(segment, pd.DatetimeIndex(cal.index), bbk_get=bbk_get, yahoo=yahoo)
    if len(gold.unexplained) > MAX_UNEXPLAINED_SHARE * len(gold.bars):
        raise NotRun([f"segment {segment.name}: {len(gold.unexplained)} unexplained gold carries "
                      f"> {MAX_UNEXPLAINED_SHARE:.1%} of {len(gold.bars)} sessions"])
    # Every series spans the gold leg's sessions, so no asset has a session the calendar
    # lacks or a hole after its first session.
    lo, hi = gold.bars.index[0], gold.bars.index[-1]

    def route(symbol, start, end):
        if symbol == segment.gold:
            return gold.bars
        h = cal if symbol == CALENDAR else yahoo(symbol, start, end)
        return h.loc[lo:hi]

    universe = [CALENDAR, MINER, segment.gold]
    sha = daily_data.build_snapshot(
        universe, segment.fetch_start, segment.fetch_end, close_only=universe, private=True,
        asset_sources={segment.gold: (ATTRIBUTION if segment.gold == GOLD_FFM
                                      else "Yahoo GC=F front month, unadjusted rolls")},
        manifest_extra={"calendars": {segment.gold: gold.fixings},
                        "gold_carries": {"explained": gold.explained, "unexplained": gold.unexplained,
                                         "report": gold.report},
                        "redistribution": "observations private; " + ATTRIBUTION},
        data_dir=data_dir, private_dir=private_dir, fetch_asset=route, **fetchers)
    return sha, gold


# ── screens ──────────────────────────────────────────────────────────────────
def xau_coverage(close: pd.Series) -> pd.Series:
    """Per calendar year, the share of sessions at which the index printed a NEW close
    (an unchanged close counts as missing)."""
    c = close.dropna()
    fresh = c.ne(c.shift(1))
    fresh.iloc[0] = True
    return fresh.groupby(fresh.index.year).mean()


def extreme_moves(close: pd.Series, threshold: float = EXTREME_MOVE) -> pd.Series:
    r = close.dropna().pct_change().dropna()
    return r[r.abs() > threshold]


def fund_confirms(moves: pd.Series, funds: pd.DataFrame) -> dict:
    """Each extreme index move against the same-day median return of the fund panel:
    confirmed when the median has the same sign. Unpriced days are unconfirmed."""
    fr = funds.pct_change()
    out = {}
    for day, r in moves.items():
        same = fr.loc[day].dropna() if day in fr.index else pd.Series(dtype=float)
        med = float(same.median()) if len(same) else float("nan")
        out[day.date().isoformat()] = {"index": float(r), "fund_median": med,
                                       "confirmed": bool(np.isfinite(med) and np.sign(med) == np.sign(r))}
    return out


def world_bank_gold(xlsx: bytes) -> pd.Series:
    """Monthly gold, $/troy oz, from the Pink Sheet's 'Monthly Prices' sheet."""
    rows = read_sheet(xlsx, "Monthly Prices")
    hdr = next((r for r in sorted(rows) if any(isinstance(v, str) and v.strip().lower() == "gold"
                                               for v in rows[r].values())), None)
    if hdr is None:
        raise ValueError("no Gold column in the Pink Sheet")
    col = next(c for c, v in rows[hdr].items() if isinstance(v, str) and v.strip().lower() == "gold")
    out = {}
    for r in sorted(rows):
        a = rows[r].get("A")
        if isinstance(a, str) and re.fullmatch(r"\d{4}M\d{2}", a) and isinstance(rows[r].get(col), float):
            out[pd.Period(f"{a[:4]}-{a[5:]}", freq="M")] = rows[r][col]
    return pd.Series(out, dtype=float).sort_index()


def world_bank_check(gold: pd.Series, fixings: list, wb: pd.Series, *,
                     tolerance: float = WB_TOLERANCE) -> dict:
    """Monthly mean of the gold leg's own observations against the Pink Sheet. Reports
    only deviations (no prices: the derived series is not redistributable)."""
    own = gold.reindex(pd.DatetimeIndex(pd.to_datetime(fixings))).dropna()
    monthly = own.groupby(own.index.to_period("M")).mean()
    common = monthly.index.intersection(wb.index)
    dev = (monthly.loc[common] / wb.loc[common] - 1.0)
    bad = dev[dev.abs() > tolerance]
    return {"months": int(len(common)), "max_abs_deviation": float(dev.abs().max()) if len(dev) else None,
            "months_beyond_tolerance": {str(k): round(float(v), 4) for k, v in bad.items()}}


def screens(snap: daily_data.Snapshot, segment: Segment, *, funds: pd.DataFrame, wb: pd.Series,
            window: tuple[pd.Timestamp, pd.Timestamp]) -> dict:
    """The frozen data screens over the scoring window. Returns the report; ``reasons``
    lists every failure (empty = pass)."""
    lo, hi = window
    xau = snap.close[MINER].loc[lo:hi]
    gold = snap.close[segment.gold].loc[lo:hi]
    reasons = []
    cov = xau_coverage(xau)
    low = cov[cov < MIN_YEARLY_XAU_COVERAGE]
    if len(low):
        reasons.append(f"^XAU fresh-close coverage below {MIN_YEARLY_XAU_COVERAGE:.0%} in "
                       + ", ".join(f"{y} ({v:.1%})" for y, v in low.items()))
    for name, s in ((MINER, xau), (segment.gold, gold)):
        if (s <= 0).any():
            reasons.append(f"{name} has non-positive closes")
    moves = extreme_moves(xau)
    conf = fund_confirms(moves, funds)
    unconfirmed = [d for d, v in conf.items() if not v["confirmed"]]
    if unconfirmed:
        reasons.append(f"^XAU moves beyond {EXTREME_MOVE:.0%} not confirmed by the fund panel: {unconfirmed}")
    fixings = snap.manifest.get("calendars", {}).get(segment.gold, [])
    wbc = world_bank_check(gold, fixings, wb)
    if wbc["months_beyond_tolerance"]:
        reasons.append(f"gold monthly mean beyond {WB_TOLERANCE:.0%} of the World Bank in "
                       f"{len(wbc['months_beyond_tolerance'])} months")
    return {"segment": segment.name, "window": [str(lo.date()), str(hi.date())],
            "xau_yearly_fresh_coverage": {int(k): round(float(v), 4) for k, v in cov.items()},
            "extreme_moves": conf, "world_bank": wbc, "reasons": reasons}


def payload_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch_funds(start: str, end: str, *, yahoo_adjusted: Callable | None = None) -> pd.DataFrame:
    """The fund panel's dividend-adjusted closes (validation only; not stored)."""
    import yfinance as yf
    get = yahoo_adjusted or (lambda s: yf.Ticker(s).history(start=start, end=end, auto_adjust=True)["Close"])
    cols = {}
    for s in FUND_PANEL:
        try:
            c = get(s)
        except Exception:  # noqa: BLE001 — a missing fund narrows the panel; recorded by absence
            continue
        if c is not None and len(c):
            idx = pd.DatetimeIndex(c.index)
            if idx.tz is not None:
                idx = idx.tz_convert("America/New_York").tz_localize(None)
            cols[s] = pd.Series(c.to_numpy(), index=idx.normalize())
    return pd.DataFrame(cols)


def today() -> str:
    return _dt.date.today().isoformat()

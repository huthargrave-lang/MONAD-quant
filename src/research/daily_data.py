"""
MONAD Quant — Frozen daily data snapshots: what a daily-strategy trial ran on, replayable.

A trial that cannot be re-run on the same data is a claim, not evidence. yfinance's
adjusted history is rewritten whenever a distribution is booked, so an unpinned fetch of
"SPY since 2003" is a different series next month. A snapshot pins it:

  * raw (split-adjusted, NOT dividend-adjusted) open and close per asset, plus each
    asset's cash distributions (dividends and capital gains) on their ex-dates, so total
    returns are BUILT here, deterministically, instead of trusted from a vendor's
    adjustment factor;
  * the 3-month T-bill discount rate (FRED DTB3), the cash leg every return is measured
    over, cross-checked at build time against Yahoo's ^IRX;
  * stored as canonical CSV under ``docs/research/data/DS-<sha>.csv.gz``. The sha is of
    the DECOMPRESSED CSV, whose float formatting is Python's shortest round-trip ``repr``
    (independent of pandas and zlib versions); gzip is written with mtime 0. A manifest
    ``DS-<sha>.json`` records the universe, window, sources and validation results.

``load_snapshot`` re-hashes and refuses a mismatch, so a trial's ``data.snapshot`` field
names exactly one series. The trading calendar is the snapshot's own dates (the first
asset's sessions), never ``bdate_range``, which counts NYSE holidays as trading days.

Return conventions (``returns``), per asset, for session i (dates d[i-1] -> d[i]):

  night  r_n = (open_i + dist_i) / close_{i-1} - 1    an ex-date's distribution is
                                                      already out of the open
  day    r_d = close_i / open_i - 1
  cash   c_i = DTB3 observed at d[i-1], as a bond-equivalent yield, accrued over the
         calendar days d[i-1] -> d[i] (weekends earn, which a per-session accrual misses)
"""
from __future__ import annotations

import csv
import datetime as _dt
import gzip
import hashlib
import io
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence

import numpy as np
import pandas as pd

from src.research.trials import REPO, LedgerError, canonical_json

DATA_REL = Path("docs/research/data")
DATA_DIR = REPO / DATA_REL
SCHEMA_VERSION = 1

#: Validation bounds. A real ETF panel clears each by a wide margin; a failed or partial
#: fetch, or a vendor glitch, does not.
MIN_SESSIONS = 1000
MAX_ABS_SESSION_RETURN = 0.5          # a +/-50% total return in one session is a data error
#: Synthesised opens: vendors back-fill a missing open with the previous close, so a faked
#: era reads near 100% "open == previous close". Genuine data is not zero, and how far from
#: zero depends on tick size: SPY in calm 2017 opened at the prior close (to the half-cent)
#: on 5% of sessions; SHY in 2012, its price pinned near the tick, on 28%, while its CLOSE
#: was unchanged on 21% (both measured 2026-10-05). So a year is flagged only when the
#: stale-open share is above the floor AND above a multiple of the asset's own
#: unchanged-close share in that year: price that barely moves explains equal opens; a
#: vendor back-fill does not.
MAX_STALE_OPEN_SHARE = 0.25
STALE_TO_UNCHANGED_RATIO = 3.0
PRICE_TICK_TOLERANCE = 0.005          # dollars: "equal" within half a cent
MAX_CASH_GAP_SESSIONS = 5             # DTB3 forward-filled over at most this many sessions
MAX_IRX_DISAGREEMENT = 0.15           # mean |DTB3 - ^IRX| in percentage points
TBILL_DAYS = 91                       # DTB3 is the 13-week bill


class SnapshotError(LedgerError):
    """A snapshot failed validation, or a stored one does not match its name."""


@dataclass(frozen=True)
class Snapshot:
    sha: str
    dates: pd.DatetimeIndex
    assets: tuple
    open: pd.DataFrame
    close: pd.DataFrame
    dist: pd.DataFrame
    dtb3: pd.Series                   # percent, discount basis, aligned to dates
    manifest: dict

    def returns(self) -> "SessionReturns":
        return session_returns(self)


@dataclass(frozen=True)
class SessionReturns:
    dates: pd.DatetimeIndex
    night: pd.DataFrame
    day: pd.DataFrame
    cash: pd.Series


# ── fetching ─────────────────────────────────────────────────────────────────
def yahoo_raw(symbol: str, start: str, end: str) -> pd.DataFrame:
    """Raw daily OHLC with distributions from yfinance: Open, Close (split-adjusted, not
    dividend-adjusted), Dividends, Capital Gains, Stock Splits; index = session date."""
    import yfinance as yf

    h = yf.Ticker(symbol).history(start=start, end=end, auto_adjust=False, actions=True)
    if h is None or not len(h):
        raise SnapshotError(f"yfinance returned nothing for {symbol} {start}..{end}")
    idx = pd.DatetimeIndex(h.index)
    if idx.tz is not None:
        idx = idx.tz_convert("America/New_York").tz_localize(None)
    h.index = idx.normalize()
    for col in ("Dividends", "Capital Gains", "Stock Splits"):
        if col not in h.columns:
            h[col] = 0.0
    return h[["Open", "Close", "Dividends", "Capital Gains", "Stock Splits"]]


def fred_dtb3(start: str, end: str) -> pd.Series:
    """FRED DTB3 (3-month T-bill secondary market rate, discount basis, percent)."""
    import urllib.request

    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DTB3"
    with urllib.request.urlopen(url, timeout=60) as resp:  # noqa: S310 — fixed https URL
        text = resp.read().decode("utf-8")
    df = pd.read_csv(io.StringIO(text), na_values=["."])
    df.columns = ["date", "dtb3"]
    s = pd.Series(df["dtb3"].to_numpy(dtype=float), index=pd.to_datetime(df["date"]))
    return s.loc[start:end].dropna()


def yahoo_irx(start: str, end: str) -> pd.Series:
    """Yahoo ^IRX (13-week bill, percent): used only to cross-check DTB3."""
    h = yahoo_raw("^IRX", start, end)
    return h["Close"].dropna()


# ── building ─────────────────────────────────────────────────────────────────
def build_frames(universe: Sequence[str], start: str, end: str, *,
                 fetch_asset: Callable = yahoo_raw, fetch_cash: Callable = fred_dtb3,
                 fetch_check: Callable | None = yahoo_irx) -> tuple[dict, dict]:
    """Fetch and validate. Returns ({"open","close","dist","dtb3"}, validation report).
    Raises SnapshotError on any failed check: a snapshot is all-valid or not written."""
    if not universe or len(set(universe)) != len(universe):
        raise SnapshotError("universe must be a non-empty list of distinct symbols")
    raw = {s: fetch_asset(s, start, end) for s in universe}
    calendar = raw[universe[0]].index
    if not calendar.is_monotonic_increasing or calendar.has_duplicates:
        raise SnapshotError(f"{universe[0]}'s sessions are not strictly increasing")
    if len(calendar) < MIN_SESSIONS:
        raise SnapshotError(f"only {len(calendar)} sessions (need {MIN_SESSIONS})")
    if (calendar.dayofweek >= 5).any():
        raise SnapshotError("the calendar contains weekend sessions")

    report = {"sessions": len(calendar), "assets": {}}
    opens, closes, dists = {}, {}, {}
    for s in universe:
        h = raw[s]
        if h.index.has_duplicates:
            raise SnapshotError(f"{s} has duplicate sessions")
        extra = h.index.difference(calendar)
        if len(extra):
            raise SnapshotError(f"{s} has {len(extra)} sessions outside the calendar "
                                f"(first {extra[0].date()})")
        h = h.reindex(calendar)
        o, c = h["Open"], h["Close"]
        first = c.first_valid_index()
        if first is None:
            raise SnapshotError(f"{s} has no data in the window")
        live = c.loc[first:].index
        missing = int(c.loc[live].isna().sum() + o.loc[live].isna().sum())
        if missing:
            raise SnapshotError(f"{s} is missing {missing} open/close values after its "
                                f"first session {first.date()}")
        if (c.loc[live] <= 0).any() or (o.loc[live] <= 0).any():
            raise SnapshotError(f"{s} has non-positive prices")
        dist = (h["Dividends"].fillna(0.0) + h["Capital Gains"].fillna(0.0)).loc[live]
        if (dist < 0).any():
            raise SnapshotError(f"{s} has negative distributions")
        prev = c.loc[live].shift(1)
        total = ((c.loc[live] + dist) / prev - 1.0).iloc[1:]
        if (total.abs() > MAX_ABS_SESSION_RETURN).any():
            bad = total[total.abs() > MAX_ABS_SESSION_RETURN]
            raise SnapshotError(f"{s} has a {bad.iloc[0]:+.1%} session on {bad.index[0].date()} "
                                f"(an unadjusted split or a vendor glitch)")
        stale = ((o.loc[live] - prev).abs() < PRICE_TICK_TOLERANCE).iloc[1:]
        unchanged = ((c.loc[live] - prev).abs() < PRICE_TICK_TOLERANCE).iloc[1:]
        by_year = stale.groupby(stale.index.year).mean()
        unchanged_by_year = unchanged.groupby(unchanged.index.year).mean()
        faked = by_year[(by_year > MAX_STALE_OPEN_SHARE)
                        & (by_year > STALE_TO_UNCHANGED_RATIO * unchanged_by_year)]
        if len(faked):
            yr = int(faked.idxmax())
            raise SnapshotError(f"{s}'s open equals the previous close on {faked.max():.0%} "
                                f"of {yr}'s sessions while its close was unchanged on only "
                                f"{unchanged_by_year[yr]:.0%}: the opens are not real")
        splits = h["Stock Splits"].fillna(0.0)
        report["assets"][s] = {
            "first_session": first.date().isoformat(),
            "sessions": int(len(live)),
            "distributions": int((dist > 0).sum()),
            "splits": {d.date().isoformat(): float(v) for d, v in splits[splits > 0].items()},
            "max_stale_open_share": round(float(by_year.max()), 4) if len(by_year) else 0.0,
        }
        opens[s], closes[s] = o, c
        dists[s] = (h["Dividends"].fillna(0.0) + h["Capital Gains"].fillna(0.0)).where(c.notna())

    cash = fetch_cash(start, end)
    aligned = cash.reindex(calendar.union(cash.index)).ffill(limit=None).reindex(calendar)
    raw_on_cal = cash.reindex(calendar)
    gap = _longest_gap(raw_on_cal)
    if gap > MAX_CASH_GAP_SESSIONS:
        raise SnapshotError(f"DTB3 has a {gap}-session gap (max {MAX_CASH_GAP_SESSIONS})")
    if aligned.isna().any():
        raise SnapshotError(f"DTB3 is missing at the start of the window "
                            f"(first {aligned.first_valid_index()})")
    report["dtb3"] = {"longest_gap_sessions": gap}
    if fetch_check is not None:
        irx = fetch_check(start, end).reindex(calendar)
        both = pd.concat([raw_on_cal.rename("d"), irx.rename("i")], axis=1).dropna()
        disagreement = float((both["d"] - both["i"]).abs().mean()) if len(both) else math.inf
        if disagreement > MAX_IRX_DISAGREEMENT:
            raise SnapshotError(f"DTB3 and ^IRX disagree by {disagreement:.3f} pct points on "
                                f"average (max {MAX_IRX_DISAGREEMENT})")
        report["dtb3"]["mean_abs_vs_irx_pct"] = round(disagreement, 4)
        report["dtb3"]["irx_sessions_compared"] = int(len(both))
    frames = {"open": pd.DataFrame(opens), "close": pd.DataFrame(closes),
              "dist": pd.DataFrame(dists), "dtb3": aligned}
    return frames, report


def _longest_gap(s: pd.Series) -> int:
    run = best = 0
    for missing in s.isna().to_numpy():
        run = run + 1 if missing else 0
        best = max(best, run)
    return best


# ── canonical encoding ───────────────────────────────────────────────────────
def _fmt(x) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return ""
    v = float(x)
    if not math.isfinite(v):
        raise SnapshotError(f"non-finite value {x!r} cannot be stored")
    return repr(v)


def encode_csv(frames: Mapping[str, object]) -> bytes:
    """The canonical CSV: header ``date,dtb3,<A>.open,<A>.close,<A>.dist,...`` in
    universe order, one row per session, floats as shortest round-trip repr."""
    o, c, d, cash = frames["open"], frames["close"], frames["dist"], frames["dtb3"]
    assets = list(o.columns)
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["date", "dtb3"] + [f"{a}.{k}" for a in assets for k in ("open", "close", "dist")])
    for i, day in enumerate(o.index):
        row = [day.date().isoformat(), _fmt(cash.iloc[i])]
        for a in assets:
            row += [_fmt(o[a].iloc[i]), _fmt(c[a].iloc[i]), _fmt(d[a].iloc[i])]
        w.writerow(row)
    return buf.getvalue().encode("utf-8")


def decode_csv(data: bytes) -> dict:
    df = pd.read_csv(io.BytesIO(data), dtype={"date": str})
    idx = pd.DatetimeIndex(pd.to_datetime(df["date"]))
    cols = [c for c in df.columns if c not in ("date", "dtb3")]
    assets = list(dict.fromkeys(c.rsplit(".", 1)[0] for c in cols))

    def frame(kind):
        return pd.DataFrame({a: df[f"{a}.{kind}"].to_numpy(dtype=float) for a in assets}, index=idx)

    return {"open": frame("open"), "close": frame("close"), "dist": frame("dist"),
            "dtb3": pd.Series(df["dtb3"].to_numpy(dtype=float), index=idx)}


def write_snapshot(frames: Mapping[str, object], report: Mapping, *, universe: Sequence[str],
                   start: str, end: str, sources: Mapping[str, str],
                   data_dir: Path | None = None) -> str:
    """Write ``DS-<sha>.csv.gz`` and its manifest. Idempotent: an existing snapshot with
    the same sha is left as is (it is byte-identical by construction)."""
    data = encode_csv(frames)
    sha = hashlib.sha256(data).hexdigest()
    base = Path(data_dir) if data_dir is not None else DATA_DIR
    base.mkdir(parents=True, exist_ok=True)
    csv_path = base / f"DS-{sha}.csv.gz"
    if not csv_path.exists():
        buf = io.BytesIO()
        with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0, compresslevel=9) as gz:
            gz.write(data)
        _write_exclusive(csv_path, buf.getvalue())
    manifest = {"schema": SCHEMA_VERSION, "sha": sha, "universe": list(universe),
                "window": {"start": start, "end": end},
                "first_session": frames["open"].index[0].date().isoformat(),
                "last_session": frames["open"].index[-1].date().isoformat(),
                "sources": dict(sources), "validation": dict(report),
                "built_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")}
    man_path = base / f"DS-{sha}.json"
    if not man_path.exists():
        _write_exclusive(man_path, (canonical_json(manifest) + "\n").encode("utf-8"))
    return sha


def _write_exclusive(path: Path, data: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())


def build_snapshot(universe: Sequence[str], start: str, end: str, *,
                   data_dir: Path | None = None, **fetchers) -> str:
    """Fetch, validate and write a snapshot. Returns its sha."""
    import yfinance

    frames, report = build_frames(universe, start, end, **fetchers)
    sources = {"prices": f"yfinance {yfinance.__version__} history(auto_adjust=False, actions=True)",
               "cash": "FRED DTB3 (fredgraph.csv)", "cash_check": "Yahoo ^IRX"}
    return write_snapshot(frames, report, universe=universe, start=start, end=end,
                          sources=sources, data_dir=data_dir)


def load_snapshot(sha: str, *, data_dir: Path | None = None) -> Snapshot:
    """The snapshot named ``sha``. Refuses a file whose content does not hash to its name."""
    base = Path(data_dir) if data_dir is not None else DATA_DIR
    path = base / f"DS-{sha}.csv.gz"
    try:
        data = gzip.decompress(path.read_bytes())
    except FileNotFoundError:
        raise SnapshotError(f"no snapshot {sha[:12]} in {base}") from None
    actual = hashlib.sha256(data).hexdigest()
    if actual != sha:
        raise SnapshotError(f"{path.name} hashes to {actual[:12]}: the file was altered")
    man_path = base / f"DS-{sha}.json"
    manifest = json.loads(man_path.read_text(encoding="utf-8")) if man_path.exists() else {}
    f = decode_csv(data)
    return Snapshot(sha=sha, dates=f["open"].index, assets=tuple(f["open"].columns),
                    open=f["open"], close=f["close"], dist=f["dist"], dtb3=f["dtb3"],
                    manifest=manifest)


# ── returns ──────────────────────────────────────────────────────────────────
def bond_equivalent_yield(discount_pct: pd.Series) -> pd.Series:
    """Discount-basis bill rate (percent) -> bond-equivalent annual yield (decimal):
    BEY = 365 d / (360 - d * days), d the discount rate as a decimal."""
    d = discount_pct / 100.0
    return 365.0 * d / (360.0 - d * TBILL_DAYS)


def session_returns(snap: Snapshot) -> SessionReturns:
    """Night, day and cash returns per session (see the module docstring). Row 0 is the
    first session, which has no predecessor: its returns are NaN."""
    o, c, dist = snap.open, snap.close, snap.dist.fillna(0.0)
    prev_close = c.shift(1)
    night = (o + dist) / prev_close - 1.0
    day = c / o - 1.0
    bey = bond_equivalent_yield(snap.dtb3).shift(1)
    gap_days = pd.Series(snap.dates, index=snap.dates).diff().dt.days
    cash = bey * gap_days / 365.0
    return SessionReturns(dates=snap.dates, night=night, day=day, cash=cash)


def common_start(snap: Snapshot, assets: Sequence[str], warmup_sessions: int) -> pd.Timestamp:
    """The first session at which every asset in ``assets`` has ``warmup_sessions`` of
    history: the start of a window every trial using these assets can be scored on."""
    firsts = [snap.close[a].first_valid_index() for a in assets]
    if any(f is None for f in firsts):
        raise SnapshotError(f"some of {list(assets)} have no data in snapshot {snap.sha[:12]}")
    latest = max(firsts)
    pos = snap.dates.get_loc(latest) + warmup_sessions
    if pos >= len(snap.dates):
        raise SnapshotError("the warm-up runs past the end of the snapshot")
    return snap.dates[pos]


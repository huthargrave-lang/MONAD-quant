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
  * stored as canonical CSV ``DS-<sha>.csv.gz``. The sha is of the DECOMPRESSED CSV, whose
    float formatting is Python's shortest round-trip ``repr`` (independent of pandas and
    zlib versions); gzip is written with mtime 0. A manifest ``DS-<sha>.json`` (committed,
    in ``docs/research/data``) records the universe, window, sources and validation
    results. Yahoo's terms grant no redistribution right, so a snapshot of Yahoo prices
    keeps its csv.gz in the gitignored private store (``data_store``) and its manifest
    records where.

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
import hashlib
import io
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence

import numpy as np
import pandas as pd

from src.research import data_store
# Re-exported: every data module imports its store paths and error type from here.
from src.research.data_store import (DATA_DIR, DATA_REL, PRIVATE_DATA_DIR,  # noqa: F401
                                     PRIVATE_DATA_REL, SnapshotError)
from src.research.trials import canonical_json

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

    @property
    def unreliable_opens(self) -> frozenset:
        """Assets whose opens failed the synthesised-open check (kept for close-only use)."""
        assets = (self.manifest.get("validation") or {}).get("assets") or {}
        return frozenset(a for a, info in assets.items() if info.get("opens_unreliable"))


@dataclass(frozen=True)
class SessionReturns:
    dates: pd.DatetimeIndex
    night: pd.DataFrame
    day: pd.DataFrame
    cash: pd.Series


# ── fetching ─────────────────────────────────────────────────────────────────
def yahoo_raw(symbol: str, start: str, end: str, *, tz: str = "America/New_York") -> pd.DataFrame:
    """Raw daily OHLC with distributions from yfinance: Open, Close (split-adjusted, not
    dividend-adjusted), Dividends, Capital Gains, Stock Splits; index = session date.

    ``tz``: the zone a bar's timestamp is read in to get its session date. Exchange-listed
    assets use New York. Crypto bars are stamped at UTC midnight and must keep their UTC
    date (``yahoo_crypto``): read in New York they would land on the previous day."""
    import yfinance as yf

    h = yf.Ticker(symbol).history(start=start, end=end, auto_adjust=False, actions=True)
    if h is None or not len(h):
        raise SnapshotError(f"yfinance returned nothing for {symbol} {start}..{end}")
    idx = pd.DatetimeIndex(h.index)
    if idx.tz is not None:
        idx = idx.tz_convert(tz).tz_localize(None)
    h.index = idx.normalize()
    for col in ("Dividends", "Capital Gains", "Stock Splits"):
        if col not in h.columns:
            h[col] = 0.0
    return h[["Open", "Close", "Dividends", "Capital Gains", "Stock Splits"]]


def yahoo_crypto(symbol: str, start: str, end: str) -> pd.DataFrame:
    """Daily crypto bars (24/7, UTC-midnight dates). A bar dated today is still forming
    and is dropped."""
    h = yahoo_raw(symbol, start, end, tz="UTC")
    today = pd.Timestamp(_dt.datetime.now(_dt.timezone.utc).date())
    return h[h.index < today]


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
class AssetError(SnapshotError):
    """One asset failed validation."""


#: An extreme session (beyond MAX_ABS_SESSION_RETURN) is accepted only if an independent
#: source's closes on its nearest observations before and after it agree with the vendor's
#: closes on those dates within this tolerance. Closed-end funds really did move more than
#: 50% in a session in October 2008 and March 2020 (TYG $40.04 -> $63.12 around 2008-10-13,
#: corroborated by CEFConnect's weekly prices), and dropping such funds would remove exactly
#: the crash rebounds a discount strategy would have held.
CORROBORATION_TOLERANCE = 0.02
CORROBORATION_WINDOW_DAYS = 10


def corroborated(close: pd.Series, day: pd.Timestamp, independent: pd.Series) -> bool:
    """True if ``independent`` (another source's closes for the same asset) has an
    observation within CORROBORATION_WINDOW_DAYS before ``day`` AND one on or after it, and
    the vendor's ``close`` agrees with both within CORROBORATION_TOLERANCE."""
    ind = independent.dropna()
    before = ind[(ind.index < day) & (ind.index >= day - pd.Timedelta(days=CORROBORATION_WINDOW_DAYS))]
    after = ind[(ind.index >= day) & (ind.index <= day + pd.Timedelta(days=CORROBORATION_WINDOW_DAYS))]
    if not len(before) or not len(after):
        return False
    for d, v in ((before.index[-1], before.iloc[-1]), (after.index[0], after.iloc[0])):
        mine = close.get(d)
        if mine is None or not np.isfinite(mine) or abs(mine / v - 1.0) > CORROBORATION_TOLERANCE:
            return False
    return True


def _validate_asset(s: str, h: pd.DataFrame, calendar: pd.DatetimeIndex, *, strict_opens: bool,
                    independent: pd.Series | None = None,
                    extreme_bounds: tuple[float, float] | None = None):
    """(open, close, dist, info) for one asset on ``calendar``, or AssetError.

    ``strict_opens``: synthesised opens fail the asset. Otherwise they are recorded in
    ``info["opens_unreliable"]`` and the asset is kept, for strategies that trade it only
    at the close (the evaluator refuses open orders into such an asset)."""
    if h.index.has_duplicates:
        raise AssetError(f"{s} has duplicate sessions")
    extra = h.index.difference(calendar)
    if len(extra):
        raise AssetError(f"{s} has {len(extra)} sessions outside the calendar "
                         f"(first {extra[0].date()})")
    h = h.reindex(calendar)
    o, c = h["Open"], h["Close"]
    first = c.first_valid_index()
    if first is None:
        raise AssetError(f"{s} has no data in the window")
    live = c.loc[first:].index
    missing = int(c.loc[live].isna().sum() + o.loc[live].isna().sum())
    if missing:
        raise AssetError(f"{s} is missing {missing} open/close values after its "
                         f"first session {first.date()}")
    if (c.loc[live] <= 0).any() or (o.loc[live] <= 0).any():
        raise AssetError(f"{s} has non-positive prices")
    dist = (h["Dividends"].fillna(0.0) + h["Capital Gains"].fillna(0.0)).loc[live]
    if (dist < 0).any():
        raise AssetError(f"{s} has negative distributions")
    prev = c.loc[live].shift(1)
    total = ((c.loc[live] + dist) / prev - 1.0).iloc[1:]
    lo, hi = extreme_bounds or (-MAX_ABS_SESSION_RETURN, MAX_ABS_SESSION_RETURN)
    extremes = total[(total < lo) | (total > hi)]
    accepted_extremes = {}
    for day, ret in extremes.items():
        if independent is not None and corroborated(c, day, independent):
            accepted_extremes[day.date().isoformat()] = round(float(ret), 4)
            continue
        raise AssetError(f"{s} has a {ret:+.1%} session on {day.date()} (an unadjusted split "
                         f"or a vendor glitch{', not corroborated' if independent is not None else ''})")
    stale = ((o.loc[live] - prev).abs() < PRICE_TICK_TOLERANCE).iloc[1:]
    unchanged = ((c.loc[live] - prev).abs() < PRICE_TICK_TOLERANCE).iloc[1:]
    by_year = stale.groupby(stale.index.year).mean()
    unchanged_by_year = unchanged.groupby(unchanged.index.year).mean()
    faked = by_year[(by_year > MAX_STALE_OPEN_SHARE)
                    & (by_year > STALE_TO_UNCHANGED_RATIO * unchanged_by_year)]
    opens_unreliable = False
    if len(faked):
        yr = int(faked.idxmax())
        msg = (f"{s}'s open equals the previous close on {faked.max():.0%} of {yr}'s "
               f"sessions while its close was unchanged on only {unchanged_by_year[yr]:.0%}: "
               f"the opens are not real")
        if strict_opens:
            raise AssetError(msg)
        opens_unreliable = True
    splits = h["Stock Splits"].fillna(0.0)
    info = {"first_session": first.date().isoformat(), "sessions": int(len(live)),
            "distributions": int((dist > 0).sum()),
            "splits": {d.date().isoformat(): float(v) for d, v in splits[splits > 0].items()},
            "max_stale_open_share": round(float(by_year.max()), 4) if len(by_year) else 0.0}
    if opens_unreliable:
        info["opens_unreliable"] = True
    if accepted_extremes:
        info["corroborated_extreme_sessions"] = accepted_extremes
    full_dist = (h["Dividends"].fillna(0.0) + h["Capital Gains"].fillna(0.0)).where(c.notna())
    return o, c, full_dist, info


def close_only_bars(h: pd.DataFrame) -> pd.DataFrame:
    """A close-only series (an old index, a once-daily fixing) as bars: the open is the
    previous close, so the whole session's move is in the day leg and the night leg is
    zero (the crypto convention for a market without an opening print). The first
    session opens at its own close."""
    out = h.copy()
    out["Open"] = out["Close"].shift(1).fillna(out["Close"])
    return out


def build_frames(universe: Sequence[str], start: str, end: str, *,
                 optional: Sequence[str] = (),
                 close_only: Sequence[str] = (),
                 independent_closes: Mapping[str, pd.Series] | None = None,
                 continuous: bool = False,
                 extreme_bounds: tuple[float, float] | None = None,
                 fetch_asset: Callable = yahoo_raw, fetch_cash: Callable = fred_dtb3,
                 fetch_check: Callable | None = yahoo_irx) -> tuple[dict, dict]:
    """Fetch and validate. Returns ({"open","close","dist","dtb3"}, validation report).

    Every asset NOT in ``optional`` must pass every check, or the build raises: a core
    panel is all-valid or not written. Assets in ``optional`` (a large universe, such as
    every listed closed-end fund) that fail are DROPPED with the reason recorded in
    ``report["dropped"]``, and ones with synthesised opens are kept but flagged
    ``opens_unreliable``. ``independent_closes`` (asset -> another source's closes) lets
    an extreme session be accepted when that source corroborates it (``corroborated``).
    The calendar is the first asset's sessions; it must be core.

    ``close_only``: assets with no real opening print (an index before electronic
    opens, a daily fixing). Their opens are rebuilt from the previous close
    (``close_only_bars``) and flagged ``opens_unreliable`` with ``close_only``, so the
    evaluator refuses open orders into them: strategies trade them at the close.

    ``continuous``: a 24/7 market (crypto). Weekend sessions are allowed, and every
    asset's opens are flagged unreliable: a market that never closes has no opening print,
    only the previous bar's close, so strategies on it trade at the close.

    ``extreme_bounds``: (low, high) session total-return bounds beyond which a session is
    a suspected vendor error unless corroborated. Default +/-MAX_ABS_SESSION_RETURN suits
    ETFs and funds. Small-cap equities really do move 50%+ in a day, so a study of them
    widens the bounds (recorded in the manifest), keeping a check that still catches an
    unadjusted reverse split (+900%)."""
    if not universe or len(set(universe)) != len(universe):
        raise SnapshotError("universe must be a non-empty list of distinct symbols")
    optional = set(optional)
    if universe[0] in optional:
        raise SnapshotError("the calendar asset (the first) cannot be optional")
    unknown = optional - set(universe)
    if unknown:
        raise SnapshotError(f"optional assets outside the universe: {sorted(unknown)}")
    close_only = set(close_only)
    if close_only - set(universe):
        raise SnapshotError(f"close-only assets outside the universe: {sorted(close_only - set(universe))}")
    calendar = None
    report = {"sessions": 0, "assets": {}, "dropped": {}}
    opens, closes, dists = {}, {}, {}
    for s in universe:
        try:
            h = fetch_asset(s, start, end)
        except Exception as exc:  # noqa: BLE001 — a vendor failure on one optional asset
            if s not in optional:
                raise
            report["dropped"][s] = f"fetch failed: {type(exc).__name__}: {exc}"
            continue
        if s in close_only:
            h = close_only_bars(h)
        if calendar is None:
            calendar = h.index
            if not calendar.is_monotonic_increasing or calendar.has_duplicates:
                raise SnapshotError(f"{s}'s sessions are not strictly increasing")
            if len(calendar) < MIN_SESSIONS:
                raise SnapshotError(f"only {len(calendar)} sessions (need {MIN_SESSIONS})")
            if not continuous and (calendar.dayofweek >= 5).any():
                raise SnapshotError("the calendar contains weekend sessions")
            report["sessions"] = len(calendar)
        try:
            o, c, d, info = _validate_asset(s, h, calendar,
                                            strict_opens=(s not in optional and not continuous
                                                          and s not in close_only),
                                            independent=(independent_closes or {}).get(s),
                                            extreme_bounds=extreme_bounds)
            if continuous or s in close_only:
                info["opens_unreliable"] = True
            if s in close_only:
                info["close_only"] = True
        except AssetError as exc:
            if s not in optional:
                raise
            report["dropped"][s] = str(exc)
            continue
        report["assets"][s] = info
        opens[s], closes[s], dists[s] = o, c, d

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
    if continuous:
        report["calendar"] = "continuous (24/7)"
    if extreme_bounds is not None:
        report["extreme_bounds"] = list(extreme_bounds)
    if not report["dropped"]:
        del report["dropped"]
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
                   data_dir: Path | None = None, private_dir: Path | None = None,
                   private: bool | None = None, manifest_extra: Mapping | None = None) -> str:
    """Write ``DS-<sha>.csv.gz`` and its manifest. Idempotent: an existing snapshot with
    the same sha is left as is (it is byte-identical by construction).

    Where the csv.gz goes is decided by ``data_store.must_be_private`` from ``sources``:
    a snapshot naming a restricted vendor (Yahoo, CEFConnect, ...) is private, its csv.gz
    written to the private store (``PRIVATE_DATA_DIR`` beside the committed store, or
    ``private_dir``), and its manifest records ``observations``. ``private=True`` keeps
    unrestricted data private too; ``private=False`` with a restricted vendor is refused.
    ``manifest_extra``: further manifest fields (e.g. a scheduled fixing calendar); it
    cannot override the core fields."""
    data = encode_csv(frames)
    sha = hashlib.sha256(data).hexdigest()
    vendors = data_store.restricted_vendors(dict(sources))
    keep_private = data_store.must_be_private(dict(sources), private)
    base = data_store.write_stores(data_dir, private_dir).manifests
    built_at = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    manifest = {"schema_version": SCHEMA_VERSION, "sha": sha, "universe": list(universe),
                "vintage": built_at[:10],      # vendor data as fetched that day
                "window": {"start": start, "end": end},
                "first_session": frames["open"].index[0].date().isoformat(),
                "last_session": frames["open"].index[-1].date().isoformat(),
                "sources": dict(sources), "validation": dict(report), "built_at": built_at}
    if keep_private:
        manifest["observations"] = data_store.private_record(sha)
    for k, v in dict(manifest_extra or {}).items():
        if k in manifest:
            raise SnapshotError(f"manifest field {k!r} is reserved")
        manifest[k] = v
    # Observations first, then the manifest: a manifest never names bytes that were not
    # written (and write() refuses a restricted destination before anything is created).
    data_store.write("DS", data, private=keep_private, data_dir=data_dir,
                     private_dir=private_dir, vendors=vendors)
    data_store.write_manifest(base / f"DS-{sha}.json", manifest,
                              serialize=lambda m: canonical_json(m) + "\n")
    return sha


def build_snapshot(universe: Sequence[str], start: str, end: str, *,
                   optional: Sequence[str] = (), close_only: Sequence[str] = (),
                   independent_closes: Mapping | None = None,
                   independent_source: str | None = None, continuous: bool = False,
                   extreme_bounds: tuple[float, float] | None = None,
                   asset_sources: Mapping[str, str] | None = None,
                   private: bool | None = None, manifest_extra: Mapping | None = None,
                   data_dir: Path | None = None, private_dir: Path | None = None,
                   **fetchers) -> str:
    """Fetch, validate and write a snapshot. Returns its sha. The manifest's universe is
    what was REQUESTED; ``validation.dropped`` says what was left out and why.
    ``asset_sources``: provenance for assets that do not come from Yahoo (a custom
    ``fetch_asset`` routes them), recorded per asset in the manifest. Its prices come from
    Yahoo, so by default (``private=None``) the observations go to the private store
    (``PRIVATE_DATA_DIR``, or ``private_dir``) and only the manifest is committed
    (``write_snapshot``)."""
    import yfinance

    frames, report = build_frames(universe, start, end, optional=optional, close_only=close_only,
                                  independent_closes=independent_closes, continuous=continuous,
                                  extreme_bounds=extreme_bounds, **fetchers)
    sources = {"prices": f"yfinance {yfinance.__version__} history(auto_adjust=False, actions=True)",
               "cash": "FRED DTB3 (fredgraph.csv)", "cash_check": "Yahoo ^IRX"}
    if independent_source:
        sources["extreme_session_corroboration"] = independent_source
    if asset_sources:
        unknown = set(asset_sources) - set(universe)
        if unknown:
            raise SnapshotError(f"asset sources for assets outside the universe: {sorted(unknown)}")
        sources["per_asset"] = dict(asset_sources)
    if close_only:
        sources["close_only"] = sorted(close_only)
    return write_snapshot(frames, report, universe=universe, start=start, end=end,
                          sources=sources, data_dir=data_dir, private_dir=private_dir,
                          private=private, manifest_extra=manifest_extra)


def load_snapshot(sha: str, *, data_dir: Path | None = None,
                  private_dir: Path | None = None) -> Snapshot:
    """The snapshot named ``sha``. Refuses a file whose content does not hash to its name.
    The observations are looked for in ``data_dir`` (default: the committed store), then
    in the private store (``private_dir``, default ``PRIVATE_DATA_DIR`` when ``data_dir`` is
    the default); the manifest is always read from ``data_dir``."""
    data = data_store.read("DS", sha, data_dir=data_dir, private_dir=private_dir)
    manifest = data_store.read_manifest("DS", sha, data_dir=data_dir) or {}
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


"""
MONAD Quant — Business development company NAV panels from SEC XBRL, point in time.

An out-of-sample test of the CEF discount mechanism (H404701/H404702) needs a universe that
shares the structure, a listed vehicle with a reported NAV, but none of the funds. Listed
BDCs are that universe. Their NAV per share is reported quarterly in 10-Q/10-K filings.

Universe (``build_universe``): every filer that reported us-gaap NetAssetValuePerShare in
any quarterly XBRL frame 2012-2026, that is exchange-listed today (data.sec.gov
submissions), that has no SIC code (EDGAR files investment companies without one;
commodity grantor trusts carry SIC 6221 and operating companies their own), and that is
NOT in the CEFConnect closed-end fund universe, so the test is disjoint from the CEF
domain. Survivorship: listed today only.

Point in time (``build_panel``): an observation is (period end, NAV per share, filed date)
from a 10-Q or 10-K, keeping the FIRST filing that reports each period end. A NAV becomes
known the day AFTER its filing date (filings often arrive after the close). Inline XBRL
became mandatory for BDCs in 2022, so point-in-time NAVs begin then. An earlier period
reported later as a comparative carries that later filing date, which is conservative
(knowledge is delayed, never advanced).
"""
from __future__ import annotations

import csv
import datetime as _dt
import gzip
import hashlib
import io
import json
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

import pandas as pd

from src.research.daily_data import DATA_DIR, SnapshotError, _fmt, _write_exclusive
from src.research.trials import canonical_json

API = "https://data.sec.gov/api/xbrl/"
SUBMISSIONS = "https://data.sec.gov/submissions/CIK{:010d}.json"
UA = {"User-Agent": "MONAD-quant research"}
LISTED_EXCHANGES = {"Nasdaq", "NYSE", "NYSE MKT", "NYSE American"}
PAUSE = 0.12                                   # SEC allows ~10 requests/second
KNOWN_LAG_DAYS = 1


def _get(url: str) -> dict:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:  # noqa: S310
        return json.loads(r.read())


def build_universe(exclude_tickers: Iterable[str], *, get: Callable[[str], dict] = _get,
                   first_year: int = 2012, last_year: int | None = None) -> list[dict]:
    last_year = last_year or _dt.date.today().year
    names = {}
    for y in range(first_year, last_year + 1):
        for q in (1, 2, 3, 4):
            try:
                frame = get(f"{API}frames/us-gaap/NetAssetValuePerShare/USD-per-shares/CY{y}Q{q}I.json")
            except Exception:  # noqa: BLE001 — a frame that does not exist yet
                continue
            for r in frame.get("data", []):
                names[r["cik"]] = r["entityName"]
            time.sleep(PAUSE)
    excluded = set(exclude_tickers)
    out = []
    for cik in sorted(names):
        try:
            sub = get(SUBMISSIONS.format(cik))
        except Exception:  # noqa: BLE001
            continue
        time.sleep(PAUSE)
        tickers = sub.get("tickers") or []
        exchanges = set(sub.get("exchanges") or [])
        if not tickers or not exchanges & LISTED_EXCHANGES or sub.get("sic"):
            continue
        if set(tickers) & excluded:
            continue
        out.append({"cik": cik, "ticker": tickers[0], "name": names[cik]})
    return out


def nav_history(cik: int, *, get: Callable[[str], dict] = _get) -> list[dict]:
    facts = get(f"{API}companyfacts/CIK{cik:010d}.json")
    units = facts.get("facts", {}).get("us-gaap", {}).get("NetAssetValuePerShare", {}).get("units", {})
    first = {}
    for v in units.get("USD/shares", []):
        if v.get("form") not in ("10-Q", "10-K") or v.get("val") is None or v["val"] <= 0:
            continue
        end, filed = v["end"], v["filed"]
        if end not in first or filed < first[end]["filed"]:
            first[end] = {"end": end, "nav": float(v["val"]), "filed": filed}
    return sorted(first.values(), key=lambda r: r["end"])


def build_panel(universe: list[dict], *, get: Callable[[str], dict] = _get) -> tuple[list, dict]:
    rows, dropped = [], {}
    for f in universe:
        try:
            hist = nav_history(f["cik"], get=get)
        except Exception as exc:  # noqa: BLE001 — one filer's failure drops that filer
            dropped[f["ticker"]] = f"companyfacts failed: {type(exc).__name__}: {exc}"
            continue
        time.sleep(PAUSE)
        if len(hist) < 4:
            dropped[f["ticker"]] = f"{len(hist)} NAV observations (need 4)"
            continue
        for h in hist:
            known = (pd.Timestamp(h["filed"]) + pd.Timedelta(days=KNOWN_LAG_DAYS)).date().isoformat()
            rows.append((f["ticker"], h["end"], h["nav"], h["filed"], known))
    report = {"universe_size": len(universe), "kept": len({r[0] for r in rows}), "dropped": dropped,
              "names": {f["ticker"]: f["name"] for f in universe}}
    return rows, report


def encode(rows: list) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["ticker", "period_end", "nav", "filed", "known"])
    for t, end, nav, filed, known in sorted(rows):
        w.writerow([t, end, _fmt(nav), filed, known])
    return buf.getvalue().encode("utf-8")


TAGGED_SOURCE = "SEC XBRL frames + companyfacts (us-gaap NetAssetValuePerShare, 10-Q/10-K)"


def write_panel(rows: list, report: dict, *, data_dir: Path | None = None,
                source: str = TAGGED_SOURCE) -> str:
    data = encode(rows)
    sha = hashlib.sha256(data).hexdigest()
    base = Path(data_dir) if data_dir is not None else DATA_DIR
    path = base / f"BDCNAV-{sha}.csv.gz"
    if not path.exists():
        b = io.BytesIO()
        with gzip.GzipFile(fileobj=b, mode="wb", mtime=0, compresslevel=9) as gz:
            gz.write(data)
        _write_exclusive(path, b.getvalue())
    fetched = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    man = base / f"BDCNAV-{sha}.json"
    if not man.exists():
        _write_exclusive(man, (canonical_json({
            "schema_version": 1, "sha": sha, "vintage": fetched[:10], "fetched_at": fetched,
            "source": source,
            "universe_rule": "listed today, no SIC code, not in the CEFConnect universe",
            "survivorship": "listed today only", "known_lag_days": KNOWN_LAG_DAYS, **report})
            + "\n").encode("utf-8"))
    return sha


@dataclass(frozen=True)
class BdcPanel:
    sha: str
    rows: pd.DataFrame          # ticker, period_end, nav, filed, known (datetimes)
    manifest: dict

    def _state(self, ticker_rows: pd.DataFrame) -> pd.DataFrame:
        """Knowledge state over time for one BDC: at each known date, the observation with
        the LATEST period end among everything known so far. A 10-K reports many periods at
        once (financial highlights go back a decade), so 'the last row filed' is not the
        current NAV; the most recent period is."""
        g = ticker_rows.sort_values(["known", "period_end"])
        best_end, states = None, {}
        for known, grp in g.groupby("known", sort=True):
            top = grp.loc[grp["period_end"].idxmax()]
            if best_end is None or top["period_end"] > best_end:
                best_end = top["period_end"]
                states[known] = (top["nav"], top["period_end"])
        return pd.DataFrame.from_dict(states, orient="index", columns=["nav", "period_end"])

    def nav_known(self, sessions: pd.DatetimeIndex) -> pd.DataFrame:
        """NAV per share as KNOWN at each session: the latest-period NAV whose known date
        is on or before it."""
        out = {}
        for t, g in self.rows.groupby("ticker"):
            st = self._state(g)["nav"]
            out[t] = st.reindex(st.index.union(sessions)).ffill().reindex(sessions)
        return pd.DataFrame(out)

    def period_age_days(self, sessions: pd.DatetimeIndex) -> pd.DataFrame:
        """Days between each session and the period end of the NAV known then."""
        out = {}
        for t, g in self.rows.groupby("ticker"):
            ends = self._state(g)["period_end"]
            known = ends.reindex(ends.index.union(sessions)).ffill().reindex(sessions)
            out[t] = (pd.Series(sessions, index=sessions) - pd.to_datetime(known)).dt.days
        return pd.DataFrame(out)


def load_panel(sha: str, *, data_dir: Path | None = None) -> BdcPanel:
    base = Path(data_dir) if data_dir is not None else DATA_DIR
    data = gzip.decompress((base / f"BDCNAV-{sha}.csv.gz").read_bytes())
    if hashlib.sha256(data).hexdigest() != sha:
        raise SnapshotError(f"BDCNAV-{sha[:12]} does not hash to its name")
    df = pd.read_csv(io.BytesIO(data), parse_dates=["period_end", "filed", "known"])
    return BdcPanel(sha=sha, rows=df, manifest=json.loads((base / f"BDCNAV-{sha}.json").read_text()))

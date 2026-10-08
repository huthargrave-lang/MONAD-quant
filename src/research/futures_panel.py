"""
MONAD Quant — a frozen panel of commodity futures closes, for rules that read a commodity's
price but trade equities (docs/research/COMMODITY_LINKAGE_CONFIRMATION.md).

A futures series cannot sit in a price snapshot: it trades on another calendar, its front
month can print a negative price (WTI on 2020-04-20), and it is never held. The panel
stores raw Yahoo closes (``<SYM>=F``: the unadjusted front month, rolled by the vendor,
settlement time 13:30-14:30 ET) as ``date,symbol,close`` rows, named by the sha-256 of its
canonical bytes (``FUT-<sha>.csv.gz`` beside the snapshots). A rule reads the latest close
dated on or before a session, which settled before that session's 16:00 equity close.
"""
from __future__ import annotations

import datetime as _dt
import gzip
import hashlib
import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

import pandas as pd

from src.research.daily_data import DATA_DIR, SnapshotError

PREFIX = "FUT"


@dataclass(frozen=True)
class FuturesPanel:
    sha: str
    close: pd.DataFrame            # index = vendor date, columns = symbols
    manifest: dict

    def on_sessions(self, symbol: str, sessions: pd.DatetimeIndex) -> pd.Series:
        """The latest close dated on or before each session (NaN before the first)."""
        s = self.close[symbol].dropna()
        return s.reindex(s.index.union(sessions)).ffill().reindex(sessions)


def yahoo_raw_closes(symbol: str, start: str, end: str) -> pd.Series:
    import yfinance as yf
    h = yf.Ticker(symbol).history(start=start, end=end, auto_adjust=False, actions=False)
    s = h["Close"].dropna()
    s.index = pd.DatetimeIndex(s.index.date)
    return s


def encode(close: pd.DataFrame) -> bytes:
    rows = ["date,symbol,close"]
    for sym in close.columns:
        for day, v in close[sym].dropna().items():
            rows.append(f"{day.date().isoformat()},{sym},{float(v)!r}")
    return ("\n".join(rows) + "\n").encode("utf-8")


def build(symbols: Sequence[str], start: str, end: str, *, fetch: Callable = yahoo_raw_closes,
          data_dir: Path | None = None) -> str:
    """Fetch, write and return the sha of a panel of ``symbols`` on [start, end)."""
    close = pd.DataFrame({s: fetch(s, start, end) for s in symbols}).sort_index()
    if close.empty or close.index.max() >= pd.Timestamp(end):
        raise SnapshotError(f"futures fetch is empty or runs past {end}")
    data = encode(close)
    sha = hashlib.sha256(data).hexdigest()
    base = Path(data_dir) if data_dir is not None else DATA_DIR
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"{PREFIX}-{sha}.csv.gz"
    if not path.exists():
        buf = io.BytesIO()
        with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0, compresslevel=9) as gz:
            gz.write(data)
        path.write_bytes(buf.getvalue())
    now = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    manifest = {"schema_version": 1, "sha": sha, "symbols": list(symbols),
                "window": {"start": start, "end": end}, "fetched_at": now,
                "source": "yfinance history(auto_adjust=False): vendor front-month, unadjusted rolls",
                "rows": {s: int(close[s].notna().sum()) for s in symbols},
                "non_positive": {s: [d.date().isoformat() for d in close.index[close[s] <= 0]]
                                 for s in symbols}}
    (base / f"{PREFIX}-{sha}.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    return sha


def load(sha: str, *, data_dir: Path | None = None) -> FuturesPanel:
    base = Path(data_dir) if data_dir is not None else DATA_DIR
    path = base / f"{PREFIX}-{sha}.csv.gz"
    try:
        data = gzip.decompress(path.read_bytes())
    except FileNotFoundError:
        raise SnapshotError(f"no futures panel {sha[:12]} in {base}") from None
    if hashlib.sha256(data).hexdigest() != sha:
        raise SnapshotError(f"{path.name} does not hash to its name: the file was altered")
    df = pd.read_csv(io.BytesIO(data), parse_dates=["date"])
    close = df.pivot(index="date", columns="symbol", values="close").sort_index()
    man = base / f"{PREFIX}-{sha}.json"
    manifest = json.loads(man.read_text(encoding="utf-8")) if man.exists() else {}
    return FuturesPanel(sha=sha, close=close, manifest=manifest)


def masked_after(panel: FuturesPanel, cut: pd.Timestamp) -> FuturesPanel:
    return FuturesPanel(sha=f"{panel.sha}@{pd.Timestamp(cut).date()}",
                        close=panel.close.loc[: pd.Timestamp(cut)], manifest=panel.manifest)

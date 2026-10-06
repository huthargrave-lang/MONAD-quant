"""
MONAD Quant — FRED series as dated fixtures with provenance.

A series is fetched from FRED's public CSV endpoint and frozen with the page's sha256 and
the fetch date (its vintage) under ``docs/research/data/fred_<ID>.json``. FRED serves the
LATEST vintage: a series that is revised after release (payrolls, GDP) is not point in
time here, and a study using one must say so or use ALFRED vintages. A rule using a series
also needs its RELEASE lag (``release_lag_days``): an observation dated d is not known on d.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import io
import json
import urllib.request
from pathlib import Path

import pandas as pd

from src.research.trials import REPO, LedgerError, canonical_json

DATA = REPO / "docs/research/data"


class FredError(LedgerError):
    pass


def fixture_path(series_id: str) -> Path:
    return DATA / f"fred_{series_id}.json"


def fetch(series_id: str) -> tuple[bytes, str]:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research; MONAD-quant)"})
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 — fixed https host
        return resp.read(), url


def build(series_id: str, *, release_lag_days: int, note: str, raw: bytes | None = None,
          url: str | None = None) -> dict:
    if raw is None:
        raw, url = fetch(series_id)
    df = pd.read_csv(io.BytesIO(raw), na_values=["."])
    if list(df.columns) != ["observation_date", series_id]:
        raise FredError(f"unexpected columns {list(df.columns)}")
    df = df.dropna()
    if not len(df) or not df["observation_date"].is_monotonic_increasing:
        raise FredError(f"{series_id}: empty or unordered")
    fetched = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    return {"schema_version": 1, "series": series_id, "source": url,
            "sha256": hashlib.sha256(raw).hexdigest(), "fetched_at": fetched,
            "vintage": fetched[:10], "release_lag_days": int(release_lag_days), "note": note,
            "observations": [[d, float(v)] for d, v in zip(df["observation_date"], df[series_id])]}


def write(record: dict) -> Path:
    path = fixture_path(record["series"])
    path.write_text(canonical_json(record) + "\n", encoding="utf-8")
    return path


def known_by(series_id: str, sessions: pd.DatetimeIndex) -> pd.Series:
    """The series as KNOWN at each session's close: the latest observation whose date plus
    the release lag is on or before the session."""
    rec = json.loads(fixture_path(series_id).read_text(encoding="utf-8"))
    obs = pd.Series({pd.Timestamp(d) + pd.Timedelta(days=rec["release_lag_days"]): v
                     for d, v in rec["observations"]}).sort_index()
    return obs.reindex(obs.index.union(sessions)).ffill().reindex(sessions)

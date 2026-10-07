"""
MONAD Quant — earnings-announcement dates from EDGAR, content-addressed.

An announcement is an 8-K whose items include 2.02 (Results of Operations and Financial
Condition), dated by its filing date. The panel is (ticker, filed) for the tickers of a
price snapshot, built from data.sec.gov submissions (recent and paged history; 8-K/A
excluded). Written as ``EARNDATES-<sha>.csv.gz`` with a manifest, like every snapshot, so
a domain names exactly the dates it decided from.
"""
from __future__ import annotations

import csv
import datetime as _dt
import gzip
import hashlib
import io
import json
from pathlib import Path

import pandas as pd

from src.research.daily_data import DATA_DIR, SnapshotError, _write_exclusive
from src.research.trials import canonical_json

PREFIX = "EARNDATES"


def encode(rows) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["ticker", "filed"])
    for t, filed in sorted(set(rows)):
        w.writerow([t, filed])
    return buf.getvalue().encode("utf-8")


def write(rows, report: dict, *, data_dir: Path | None = None) -> str:
    data = encode(rows)
    sha = hashlib.sha256(data).hexdigest()
    base = Path(data_dir) if data_dir is not None else DATA_DIR
    path = base / f"{PREFIX}-{sha}.csv.gz"
    if not path.exists():
        b = io.BytesIO()
        with gzip.GzipFile(fileobj=b, mode="wb", mtime=0, compresslevel=9) as gz:
            gz.write(data)
        _write_exclusive(path, b.getvalue())
    man = base / f"{PREFIX}-{sha}.json"
    if not man.exists():
        fetched = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        _write_exclusive(man, (canonical_json({
            "schema_version": 1, "sha": sha, "vintage": fetched[:10], "fetched_at": fetched,
            "source": "data.sec.gov submissions: 8-K filings with item 2.02, filing date", **report})
            + "\n").encode("utf-8"))
    return sha


def load(sha: str, *, data_dir: Path | None = None):
    from src.research.earnings_classes import Announcements
    base = Path(data_dir) if data_dir is not None else DATA_DIR
    data = gzip.decompress((base / f"{PREFIX}-{sha}.csv.gz").read_bytes())
    if hashlib.sha256(data).hexdigest() != sha:
        raise SnapshotError(f"{PREFIX}-{sha[:12]} does not hash to its name")
    return Announcements(sha=sha, dates=pd.read_csv(io.BytesIO(data), parse_dates=["filed"]))

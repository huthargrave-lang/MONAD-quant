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
import hashlib
import io
from pathlib import Path

import pandas as pd

from src.research import data_store
from src.research.trials import canonical_json

PREFIX = "EARNDATES"


def encode(rows) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["ticker", "filed"])
    for t, filed in sorted(set(rows)):
        w.writerow([t, filed])
    return buf.getvalue().encode("utf-8")


SOURCE = "data.sec.gov submissions: 8-K filings with item 2.02, filing date"


def write(rows, report: dict, *, data_dir: Path | None = None) -> str:
    """Write ``EARNDATES-<sha>`` (SEC filing dates: public, so committed) and return the
    sha. ``data_store`` makes the public/private decision from the source."""
    data = encode(rows)
    sha = hashlib.sha256(data).hexdigest()
    keep_private = data_store.must_be_private(SOURCE)
    base = data_store.write_stores(data_dir).manifests
    fetched = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    manifest = {"schema_version": 1, "sha": sha, "vintage": fetched[:10], "fetched_at": fetched,
                "source": SOURCE, **report}
    if keep_private:
        manifest["observations"] = data_store.private_record(sha)
    data_store.write(PREFIX, data, private=keep_private, data_dir=data_dir,
                     vendors=data_store.restricted_vendors(SOURCE))
    data_store.write_manifest(base / f"{PREFIX}-{sha}.json", manifest,
                              serialize=lambda m: canonical_json(m) + "\n")
    return sha


def load(sha: str, *, data_dir: Path | None = None, private_dir: Path | None = None):
    """The announcement dates named ``sha``, verified (committed store, then private)."""
    from src.research.earnings_classes import Announcements
    data = data_store.read(PREFIX, sha, data_dir=data_dir, private_dir=private_dir)
    return Announcements(sha=sha, dates=pd.read_csv(io.BytesIO(data), parse_dates=["filed"]))

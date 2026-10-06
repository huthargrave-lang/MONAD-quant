"""
MONAD Quant — Insider purchase clusters from SEC's Form 3/4/5 structured data sets.

Lakonishok & Lee (2001) and Cohen, Malloy & Pomorski (2012): open-market purchases by a
company's own officers and directors predict returns, most strongly when several insiders
buy together. This module turns SEC's quarterly "Insider Transactions Data Sets"
(sec.gov/files/structureddata/data/insider-transactions-data-sets/<YYYY>q<Q>_form345.zip)
into a frozen list of cluster EVENTS, each with the date it became public.

A purchase: a Form 4 non-derivative transaction with code P (open-market or private
purchase), acquired (A), positive shares and price, by a reporting owner whose relationship
includes Director or Officer (a 10% holder who is neither is excluded: a fund's buying is a
different signal). Amendments (4/A) are excluded: they restate, they do not announce.

A cluster: at least ``MIN_INSIDERS`` distinct insiders' purchases in the same issuer whose
FILING dates fall within ``WINDOW_DAYS`` calendar days. It becomes public on the filing date
of the purchase that completes it, and actionable the next day (``known`` = filing date
+ 1): Form 4s are often accepted after the close. After an event, the issuer cannot produce
another until ``COOLDOWN_DAYS`` have passed, so one buying spree is one event.

Frozen as ``docs/research/data/INSIDER-<sha>.csv.gz`` (ticker, issuer CIK, known date,
number of insiders, purchase value) with a manifest naming every source zip's sha256.
"""
from __future__ import annotations

import csv
import datetime as _dt
import gzip
import hashlib
import io
import json
import zipfile
from pathlib import Path
from typing import Iterable

import pandas as pd

from src.research.daily_data import DATA_DIR, SnapshotError, _write_exclusive
from src.research.trials import canonical_json

URL = "https://www.sec.gov/files/structureddata/data/insider-transactions-data-sets/{}_form345.zip"
MIN_INSIDERS = 3
WINDOW_DAYS = 10
COOLDOWN_DAYS = 90
KNOWN_LAG_DAYS = 1


def _read(z: zipfile.ZipFile, name: str, cols: list[str]) -> pd.DataFrame:
    with z.open(name) as fh:
        df = pd.read_csv(fh, sep="\t", dtype=str, usecols=cols, quoting=csv.QUOTE_NONE,
                         on_bad_lines="skip", encoding="latin-1")
    return df


def purchases(zip_path: Path) -> pd.DataFrame:
    """Officer/director open-market purchases from one quarterly zip."""
    with zipfile.ZipFile(zip_path) as z:
        sub = _read(z, "SUBMISSION.tsv", ["ACCESSION_NUMBER", "FILING_DATE", "DOCUMENT_TYPE",
                                          "ISSUERCIK", "ISSUERTRADINGSYMBOL"])
        own = _read(z, "REPORTINGOWNER.tsv", ["ACCESSION_NUMBER", "RPTOWNERCIK", "RPTOWNER_RELATIONSHIP"])
        trn = _read(z, "NONDERIV_TRANS.tsv", ["ACCESSION_NUMBER", "TRANS_CODE", "TRANS_SHARES",
                                              "TRANS_PRICEPERSHARE", "TRANS_ACQUIRED_DISP_CD"])
    sub = sub[sub["DOCUMENT_TYPE"] == "4"]
    rel = own["RPTOWNER_RELATIONSHIP"].fillna("")
    own = own[rel.str.contains("Director") | rel.str.contains("Officer")]
    trn = trn[(trn["TRANS_CODE"] == "P") & (trn["TRANS_ACQUIRED_DISP_CD"] == "A")].copy()
    trn["shares"] = pd.to_numeric(trn["TRANS_SHARES"], errors="coerce")
    trn["price"] = pd.to_numeric(trn["TRANS_PRICEPERSHARE"], errors="coerce")
    trn = trn[(trn["shares"] > 0) & (trn["price"] > 0)]
    trn["value"] = trn["shares"] * trn["price"]
    val = trn.groupby("ACCESSION_NUMBER").agg(value=("value", "sum"), shares=("shares", "sum")).reset_index()
    df = sub.merge(val, on="ACCESSION_NUMBER").merge(own, on="ACCESSION_NUMBER")
    df["filed"] = pd.to_datetime(df["FILING_DATE"], format="%d-%b-%Y", errors="coerce")
    df = df.dropna(subset=["filed", "ISSUERTRADINGSYMBOL"])
    df["ticker"] = df["ISSUERTRADINGSYMBOL"].str.strip().str.upper()
    df = df[df["ticker"].str.fullmatch(r"[A-Z]{1,5}")]
    return df[["ticker", "ISSUERCIK", "RPTOWNERCIK", "filed", "value", "shares"]].rename(
        columns={"ISSUERCIK": "issuer_cik", "RPTOWNERCIK": "owner_cik"})


def clusters(p: pd.DataFrame) -> pd.DataFrame:
    """Cluster events from a purchase table (see the module docstring)."""
    out = []
    for (ticker, cik), g in p.sort_values("filed").groupby(["ticker", "issuer_cik"]):
        g = g.reset_index(drop=True)
        last_event = None
        for i in range(len(g)):
            now = g.loc[i, "filed"]
            if last_event is not None and (now - last_event).days < COOLDOWN_DAYS:
                continue
            window = g[(g["filed"] > now - pd.Timedelta(days=WINDOW_DAYS)) & (g["filed"] <= now)]
            n = window["owner_cik"].nunique()
            if n >= MIN_INSIDERS:
                out.append({"ticker": ticker, "issuer_cik": cik,
                            "known": (now + pd.Timedelta(days=KNOWN_LAG_DAYS)).date().isoformat(),
                            "insiders": int(n), "value": float(window["value"].sum()),
                            # value-weighted purchase price: corroborates the ticker's price
                            # series (a reused ticker's prices will not match it)
                            "price": float(window["value"].sum() / window["shares"].sum())})
                last_event = now
    return pd.DataFrame(out, columns=["ticker", "issuer_cik", "known", "insiders", "value", "price"])


def build(zip_paths: Iterable[Path]) -> tuple[pd.DataFrame, dict]:
    zips = sorted(Path(z) for z in zip_paths)
    p = pd.concat([purchases(z) for z in zips], ignore_index=True)
    p = p.drop_duplicates(["ticker", "owner_cik", "filed", "value"])
    ev = clusters(p).sort_values(["known", "ticker"]).reset_index(drop=True)
    report = {"sources": [{"file": z.name, "sha256": hashlib.sha256(z.read_bytes()).hexdigest()} for z in zips],
              "purchases": int(len(p)), "events": int(len(ev)),
              "rule": {"min_insiders": MIN_INSIDERS, "window_days": WINDOW_DAYS,
                       "cooldown_days": COOLDOWN_DAYS, "known_lag_days": KNOWN_LAG_DAYS}}
    return ev, report


def write(ev: pd.DataFrame, report: dict, *, data_dir: Path | None = None) -> str:
    buf = io.StringIO()
    ev.to_csv(buf, index=False, lineterminator="\n", float_format="%.4f")
    data = buf.getvalue().encode("utf-8")
    sha = hashlib.sha256(data).hexdigest()
    base = Path(data_dir) if data_dir is not None else DATA_DIR
    path = base / f"INSIDER-{sha}.csv.gz"
    if not path.exists():
        b = io.BytesIO()
        with gzip.GzipFile(fileobj=b, mode="wb", mtime=0, compresslevel=9) as gz:
            gz.write(data)
        _write_exclusive(path, b.getvalue())
    fetched = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    man = base / f"INSIDER-{sha}.json"
    if not man.exists():
        _write_exclusive(man, (canonical_json({"schema_version": 1, "sha": sha, "vintage": fetched[:10],
                                               "source": "SEC Insider Transactions Data Sets", **report})
                               + "\n").encode("utf-8"))
    return sha


def load(sha: str, *, data_dir: Path | None = None) -> pd.DataFrame:
    base = Path(data_dir) if data_dir is not None else DATA_DIR
    data = gzip.decompress((base / f"INSIDER-{sha}.csv.gz").read_bytes())
    if hashlib.sha256(data).hexdigest() != sha:
        raise SnapshotError(f"INSIDER-{sha[:12]} does not hash to its name")
    return pd.read_csv(io.BytesIO(data), parse_dates=["known"])

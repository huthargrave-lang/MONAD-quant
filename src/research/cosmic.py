"""
MONAD Quant — "Cosmic" calendars for the intentionally strange hypotheses (correlation
atlas J): lunar phase, and the daily geomagnetic Ap index.

Lunar phase is computed from the mean synodic month and a reference new moon (2000-01-06
18:14 UTC; Meeus). The mean model is within about half a day of the true phase, enough for
windows of +/-3 and +/-7 days, and it needs no data, so it cannot leak.

The geomagnetic Ap index is GFZ Potsdam's (https://kp.gfz.de, Kp_ap_Ap_SN_F107_since_1932.txt),
frozen as ``docs/research/data/geomag_ap_daily.json`` with the file's sha256. A UTC day's
Ap is complete at 24:00 UTC (20:00 New York, after the US close), so a storm on UTC day d is
first actionable at the close of the next US session after d (``storm_known_by``).
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

from src.research.trials import REPO, LedgerError, canonical_json

SYNODIC_DAYS = 29.530588853
REFERENCE_NEW_MOON = pd.Timestamp("2000-01-06 18:14")
GEOMAG_URL = "https://kp.gfz.de/app/files/Kp_ap_Ap_SN_F107_since_1932.txt"
GEOMAG_FIXTURE = REPO / "docs/research/data/geomag_ap_daily.json"


def lunar_age_days(days: pd.DatetimeIndex) -> np.ndarray:
    """Days since the last mean new moon, at 16:00 New York (~21:00 UTC) of each date."""
    t = (pd.DatetimeIndex(days) + pd.Timedelta(hours=21) - REFERENCE_NEW_MOON) / pd.Timedelta(days=1)
    return np.mod(np.asarray(t, dtype=float), SYNODIC_DAYS)


def days_from_full_moon(days: pd.DatetimeIndex) -> np.ndarray:
    return np.abs(lunar_age_days(days) - SYNODIC_DAYS / 2)


def days_from_new_moon(days: pd.DatetimeIndex) -> np.ndarray:
    age = lunar_age_days(days)
    return np.minimum(age, SYNODIC_DAYS - age)


def build_geomag(first_year: int = 2000) -> dict:
    req = urllib.request.Request(GEOMAG_URL, headers={"User-Agent": "Mozilla/5.0 (research; MONAD-quant)"})
    with urllib.request.urlopen(req, timeout=120) as resp:  # noqa: S310 — fixed https host
        raw = resp.read()
    rows = []
    for line in raw.decode("ascii", "replace").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        f = line.split()
        if len(f) < 28 or int(f[0]) < first_year:
            continue
        ap = int(f[23])
        if ap < 0:
            continue                                  # missing
        rows.append([f"{f[0]}-{f[1]}-{f[2]}", ap, int(f[27])])
    if not rows:
        raise LedgerError("no geomagnetic rows parsed")
    fetched = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    return {"schema_version": 1, "source": GEOMAG_URL, "sha256": hashlib.sha256(raw).hexdigest(),
            "fetched_at": fetched, "vintage": fetched[:10],
            "columns": ["date_utc", "Ap", "definitive_flag"], "rows": rows}


def write_geomag(record: dict, path: Path = GEOMAG_FIXTURE) -> None:
    path.write_text(canonical_json(record) + "\n", encoding="utf-8")


def storm_known_by(sessions: pd.DatetimeIndex, threshold: int) -> pd.Series:
    """True at each session whose close is the first US close after a UTC day with
    Ap >= threshold (that day's Ap completes at 20:00 New York, after the close)."""
    rec = json.loads(GEOMAG_FIXTURE.read_text(encoding="utf-8"))
    storms = pd.DatetimeIndex([pd.Timestamp(d) for d, ap, _ in rec["rows"] if ap >= threshold])
    pos = sessions.searchsorted(storms, side="right")          # first session strictly after d
    flags = pd.Series(False, index=sessions)
    hits = pos[pos < len(sessions)]
    flags.iloc[np.unique(hits)] = True
    return flags

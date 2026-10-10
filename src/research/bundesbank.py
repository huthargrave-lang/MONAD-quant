"""
MONAD Quant — Deutsche Bundesbank statistical time series, for history no free US vendor
redistributes (docs/research/MINER_TILT_PREPERIOD.md).

The repo is public, so its frozen data must be redistributable. LBMA gold prices are
licensed (FRED withdrew them in 2022); the Bundesbank publishes its statistics for reuse
with attribution. It carries the Frankfurt gold fixing in DM per kilogram up to the end of
1998, and the Frankfurt USD fixing (DM per dollar), both fixed in Frankfurt around midday,
so their ratio is a synchronous USD gold price.

``fetch_series`` reads one series over the SDMX REST API (generic data XML).
``frankfurt_gold_usd`` builds USD per troy ounce. ``bars_on_sessions`` puts a once-daily
series on an exchange calendar as close-only bars, carrying a missing fixing (a German
holiday on a NYSE session) forward at most ``max_carry`` sessions and reporting every
carry.
"""
from __future__ import annotations

import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Callable

import pandas as pd

BASE = "https://api.statistiken.bundesbank.de/rest/data"
ACCEPT = "application/vnd.sdmx.genericdata+xml;version=2.1"
ATTRIBUTION = "Source: Deutsche Bundesbank, time series database (api.statistiken.bundesbank.de)"
#: Frankfurt gold fixing, DM per kg of fine gold, up to the end of 1998.
GOLD_DEM_PER_KG = ("BBEX3", "D.XAU.DEM.EA.AC.C01")
#: Frankfurt exchange fixing, DM per USD.
DEM_PER_USD = ("BBEX3", "D.USD.DEM.AA.AC.000")
TROY_OUNCES_PER_KG = 32.1507466
MAX_CARRY = 3
TIMEOUT = 60

_GENERIC = "{http://www.sdmx.org/resources/sdmxml/schemas/v2_1/data/generic}"


class SourceError(RuntimeError):
    """The Bundesbank returned nothing usable."""


def _http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"Accept": ACCEPT, "User-Agent": "MONAD-quant research"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:  # noqa: S310 — fixed https host
        return resp.read()


def url_for(flow: str, key: str, start: str, end: str) -> str:
    return f"{BASE}/{flow}/{key}?startPeriod={start}&endPeriod={end}"


def parse_generic(xml: bytes | str) -> tuple[pd.Series, int]:
    """(observations of a single-series SDMX generic-data message as floats by date,
    number of observations without a value). The database marks a day without a fixing
    (a weekend, a holiday) by an observation with a status and no value; those are
    counted, never filled."""
    root = ET.fromstring(xml.encode("utf-8") if isinstance(xml, str) else xml)
    rows, empty = {}, 0
    for obs in root.iter(f"{_GENERIC}Obs"):
        dim = obs.find(f"{_GENERIC}ObsDimension")
        val = obs.find(f"{_GENERIC}ObsValue")
        if dim is None:
            continue
        if val is None or val.get("value") in (None, ""):
            empty += 1
            continue
        rows[pd.Timestamp(dim.get("value"))] = float(val.get("value"))
    return pd.Series(rows, dtype=float).sort_index(), empty


def fetch_series(flow: str, key: str, start: str, end: str, *,
                 get: Callable[[str], bytes] = _http_get) -> pd.Series:
    """One daily series on [start, end] (both inclusive, ISO dates)."""
    xml = get(url_for(flow, key, start, end))
    if b"Series" not in (xml if isinstance(xml, bytes) else xml.encode()):
        raise SourceError(f"no series {flow}.{key} for {start}..{end}")
    s, _ = parse_generic(xml)
    if s.empty:
        raise SourceError(f"{flow}.{key} has no numeric observations in {start}..{end}")
    return s


def frankfurt_gold_usd(start: str, end: str, *, get: Callable[[str], bytes] = _http_get
                       ) -> tuple[pd.Series, dict]:
    """USD per troy ounce = (DM per kg) / (DM per USD) / ounces per kg, on the dates both
    fixings exist. The report counts dates where only one of them printed."""
    gold = fetch_series(*GOLD_DEM_PER_KG, start, end, get=get)
    fx = fetch_series(*DEM_PER_USD, start, end, get=get)
    both = gold.index.intersection(fx.index)
    usd = (gold.loc[both] / fx.loc[both] / TROY_OUNCES_PER_KG).rename("GOLD_FRANKFURT")
    report = {"gold_fixings": int(len(gold)), "fx_fixings": int(len(fx)), "both": int(len(both)),
              "gold_without_fx": int(len(gold.index.difference(fx.index))),
              "fx_without_gold": int(len(fx.index.difference(gold.index))),
              "series": [".".join(GOLD_DEM_PER_KG), ".".join(DEM_PER_USD)],
              "attribution": ATTRIBUTION}
    return usd, report


@dataclass(frozen=True)
class SessionBars:
    bars: pd.DataFrame               # Open, Close, Dividends, Capital Gains, Stock Splits
    carried: list                    # sessions that carry the previous fixing
    dropped_off_calendar: int        # fixings on dates that are not sessions


def bars_on_sessions(series: pd.Series, sessions: pd.DatetimeIndex, *,
                     max_carry: int = MAX_CARRY) -> SessionBars:
    """A once-daily series as close-only bars on ``sessions``, from its first observation
    to its last. A session without an observation carries the previous one; more than
    ``max_carry`` sessions in a row is a gap the series cannot bridge (SourceError).
    Fixings on non-sessions are dropped and counted. The open is left for
    ``daily_data.close_only_bars`` to rebuild."""
    s = series.dropna().sort_index()
    if s.empty:
        raise SourceError("empty series")
    window = sessions[(sessions >= s.index[0]) & (sessions <= s.index[-1])]
    on = s.reindex(window)
    missing = on.isna().to_numpy()
    run = 0
    for i, m in enumerate(missing):
        run = run + 1 if m else 0
        if run > max_carry:
            raise SourceError(f"{run} consecutive sessions without an observation ending "
                              f"{window[i].date()} (max {max_carry})")
    carried = [d.date().isoformat() for d in window[missing]]
    close = on.ffill()
    bars = pd.DataFrame({"Open": close, "Close": close, "Dividends": 0.0, "Capital Gains": 0.0,
                         "Stock Splits": 0.0}, index=window)
    return SessionBars(bars=bars, carried=carried,
                       dropped_off_calendar=int(len(s.index.difference(sessions))))

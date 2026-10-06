"""
MONAD Quant — The FOMC's SCHEDULED meeting calendar, as a dated fixture with provenance.

The pre-FOMC announcement drift (Lucca & Moench 2015) is a property of SCHEDULED meetings:
their dates are published a year or more ahead, so a strategy may know them in advance.
Unscheduled meetings, conference calls and notation votes are surprises by construction,
and including them would be look-ahead.

Source: the Federal Reserve's own pages, never a hand-typed list (a reference label is
generated from the authoritative artifact as a dated fixture, never hand-curated):

  * ``fomchistorical<YEAR>.htm`` for years old enough to be archived (one ``<h5>`` per
    event: "January 29-30 Meeting - 2008", "March 15 (unscheduled) Meeting - 2020",
    "January 9 Conference Call - 2008", "March 19 (notation vote) - 2020");
  * ``fomccalendars.htm`` for recent and planned years (one ``fomc-meeting`` row per
    event: month cell "April/May", date cell "30-1*"; the asterisk marks a Summary of
    Economic Projections).

The ANNOUNCEMENT date is the meeting's last day. The fixture,
``docs/research/data/fomc_scheduled_meetings.json``, records every page's URL, fetch time
and sha256, so a later fetch that disagrees is detectable rather than silently different.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import re
import urllib.request
from pathlib import Path
from typing import Callable

from src.research.trials import REPO, LedgerError, canonical_json

FIXTURE = REPO / "docs/research/data/fomc_scheduled_meetings.json"
BASE = "https://www.federalreserve.gov/monetarypolicy/"
MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July", "August", "September",
     "October", "November", "December"], start=1)}
# The current page abbreviates the months of a meeting that crosses a month end ("Apr/May").
MONTHS.update({name[:3]: num for name, num in list(MONTHS.items())})
_EXCLUDE = re.compile(r"unscheduled|cancel+ed|notation vote|conference call", re.I)


class CalendarError(LedgerError):
    pass


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research; MONAD-quant)"})
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 — fixed https host
        return resp.read()


def _date(year: int, month: str, day: str) -> _dt.date:
    if month not in MONTHS:
        raise CalendarError(f"unknown month {month!r}")
    return _dt.date(year, MONTHS[month], int(day))


def parse_historical(html: str, year: int) -> list[dict]:
    """Scheduled meetings from one archived year page."""
    out = []
    for heading in re.findall(r"<h5[^>]*>([^<]+)</h5>", html):
        text = " ".join(heading.split())
        if not text.endswith(f"- {year}") or "Meeting" not in text or _EXCLUDE.search(text):
            continue
        # "January 29-30", "March 18", "April/May 30-1", "January 31-February 1"
        m = re.match(r"^([A-Z][a-z]+)(?:/([A-Z][a-z]+))?\s+(\d{1,2})"
                     r"(?:-(?:([A-Z][a-z]+)\s+)?(\d{1,2}))?\s+Meeting\s+-\s+\d{4}$", text)
        if not m:
            raise CalendarError(f"unparsed meeting heading {text!r}")
        m1, m_slash, d1, m_dash, d2 = m.groups()
        start = _date(year, m1, d1)
        end = _date(year, m_slash or m_dash or m1, d2 or d1)
        if end < start:
            raise CalendarError(f"meeting ends before it starts: {text!r}")
        out.append({"start": start.isoformat(), "announcement": end.isoformat(), "label": text})
    return out


def parse_current(html: str) -> list[dict]:
    """Scheduled meetings from the current calendars page, every year it shows."""
    out = []
    sections = re.split(r'<h4><a[^>]*>(\d{4}) FOMC Meetings</a></h4>', html)
    for year_text, body in zip(sections[1::2], sections[2::2]):
        year = int(year_text)
        # Alternate rows are "fomc-meeting--shaded row fomc-meeting": split on the row class
        # wherever it appears in the class list, not only at its start.
        rows = re.split(r'<div class="(?:[^"]*\s)?row fomc-meeting["\s]', body)[1:]
        for row in rows:
            month = re.search(r'fomc-meeting__month[^>]*>\s*<strong>([^<]+)</strong>', row)
            date = re.search(r'fomc-meeting__date[^>]*>([^<]+)<', row)
            if not month or not date:
                continue
            month_t = " ".join(month.group(1).split())
            date_t = " ".join(date.group(1).split())
            if _EXCLUDE.search(row[:600]) or _EXCLUDE.search(date_t):
                continue
            months = month_t.split("/")
            days = re.findall(r"\d{1,2}", date_t)
            if not days or len(months) > 2:
                raise CalendarError(f"unparsed calendar row {month_t!r} {date_t!r} ({year})")
            start = _date(year, months[0], days[0])
            end = _date(year, months[-1], days[-1])
            if end < start:
                raise CalendarError(f"meeting ends before it starts: {month_t} {date_t} ({year})")
            out.append({"start": start.isoformat(), "announcement": end.isoformat(),
                        "label": f"{month_t} {date_t} {year}"})
    return out


def build(first_year: int, *, fetcher: Callable[[str], bytes] = fetch) -> dict:
    """Fetch and parse every year from ``first_year`` to the last year the current page
    shows. Archived years come from their own pages; the current page covers the rest."""
    pages = []
    meetings = {}
    cur_url = BASE + "fomccalendars.htm"
    cur = fetcher(cur_url)
    pages.append({"url": cur_url, "sha256": hashlib.sha256(cur).hexdigest()})
    current = parse_current(cur.decode("utf-8", "replace"))
    current_years = sorted({int(m["announcement"][:4]) for m in current})
    if not current_years:
        raise CalendarError("the current calendar page lists no meetings")
    for year in range(first_year, current_years[0]):
        url = f"{BASE}fomchistorical{year}.htm"
        raw = fetcher(url)
        pages.append({"url": url, "sha256": hashlib.sha256(raw).hexdigest()})
        found = parse_historical(raw.decode("utf-8", "replace"), year)
        if not 6 <= len(found) <= 10:
            raise CalendarError(f"{year}: {len(found)} scheduled meetings (expected 8)")
        for m in found:
            meetings[m["announcement"]] = m
    for m in current:
        meetings.setdefault(m["announcement"], m)
    per_year = {}
    for d in meetings:
        per_year[d[:4]] = per_year.get(d[:4], 0) + 1
    odd = {y: n for y, n in per_year.items() if not 6 <= n <= 10}
    if odd:
        raise CalendarError(f"implausible scheduled-meeting counts: {odd}")
    return {"schema": 1, "source": "federalreserve.gov", "pages": pages,
            "fetched_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "meetings": [meetings[k] for k in sorted(meetings)]}


def write_fixture(record: dict, path: Path = FIXTURE) -> None:
    path.write_text(canonical_json(record) + "\n", encoding="utf-8")


def announcements(path: Path = FIXTURE) -> list[_dt.date]:
    record = json.loads(path.read_text(encoding="utf-8"))
    return [_dt.date.fromisoformat(m["announcement"]) for m in record["meetings"]]

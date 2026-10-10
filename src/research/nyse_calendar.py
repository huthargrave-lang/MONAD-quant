"""
NYSE full-day closures by rule, for counting sessions where no data is at hand (the
gate rules v2 price-window floor, prereg.MIN_PRICE_WINDOW_DAYS). Where a snapshot exists,
its own session index is the calendar (daily_data); this is for windows not yet fetched.

Rules (NYSE Rule 7.2 and its history): New Year's Day (Sunday -> Monday; a Saturday New
Year is not made up), Martin Luther King Jr. Day (3rd Monday of January, from 1998),
Washington's Birthday (3rd Monday of February), Good Friday, Memorial Day (last Monday of
May), Juneteenth (June 19, from 2022), Independence Day, Labor Day (1st Monday of
September), Thanksgiving (4th Thursday of November) and Christmas. Fixed-date holidays on
a Saturday close the Friday before and on a Sunday the Monday after, except New Year's Day.
Unscheduled closures are listed explicitly; a future one is unknown until it happens, so
counts for future years can only overstate sessions by those days.
"""
from __future__ import annotations

import datetime as _dt
from functools import lru_cache

SPECIAL_CLOSURES = frozenset(_dt.date.fromisoformat(d) for d in (
    "1985-09-27",                                               # Hurricane Gloria
    "1994-04-27",                                               # President Nixon
    "2001-09-11", "2001-09-12", "2001-09-13", "2001-09-14",   # September 11
    "2004-06-11",                                               # President Reagan
    "2007-01-02",                                               # President Ford
    "2012-10-29", "2012-10-30",                                 # Hurricane Sandy
    "2018-12-05",                                               # President G.H.W. Bush
    "2025-01-09",                                               # President Carter
))


def _easter(year: int) -> _dt.date:
    """Gregorian Easter Sunday (anonymous algorithm)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    month = (h + l_ - 7 * m + 114) // 31
    day = (h + l_ - 7 * m + 114) % 31 + 1
    return _dt.date(year, month, day)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> _dt.date:
    first = _dt.date(year, month, 1)
    return first + _dt.timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> _dt.date:
    nxt = _dt.date(year + (month == 12), month % 12 + 1, 1)
    last = nxt - _dt.timedelta(days=1)
    return last - _dt.timedelta(days=(last.weekday() - weekday) % 7)


def _observed(day: _dt.date) -> _dt.date:
    if day.weekday() == 5:
        return day - _dt.timedelta(days=1)
    if day.weekday() == 6:
        return day + _dt.timedelta(days=1)
    return day


@lru_cache(maxsize=None)
def holidays(year: int) -> frozenset:
    """The year's rule-based full-day closures (special closures excluded)."""
    out = set()
    ny = _dt.date(year, 1, 1)
    if ny.weekday() == 6:
        out.add(ny + _dt.timedelta(days=1))
    elif ny.weekday() < 5:
        out.add(ny)
    if year >= 1998:
        out.add(_nth_weekday(year, 1, 0, 3))
    out.add(_nth_weekday(year, 2, 0, 3))
    out.add(_easter(year) - _dt.timedelta(days=2))
    out.add(_last_weekday(year, 5, 0))
    if year >= 2022:
        out.add(_observed(_dt.date(year, 6, 19)))
    out.add(_observed(_dt.date(year, 7, 4)))
    out.add(_nth_weekday(year, 9, 0, 1))
    out.add(_nth_weekday(year, 11, 3, 4))
    out.add(_observed(_dt.date(year, 12, 25)))
    return frozenset(d for d in out if d.year == year)


def is_session(day: _dt.date) -> bool:
    return day.weekday() < 5 and day not in holidays(day.year) and day not in SPECIAL_CLOSURES


def sessions_between(start: _dt.date, end: _dt.date) -> int:
    """Sessions in [start, end], both ends included."""
    n, d = 0, start
    while d <= end:
        n += is_session(d)
        d += _dt.timedelta(days=1)
    return n

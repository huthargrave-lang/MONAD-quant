#!/usr/bin/env python3
"""Detect holes that `validate_ohlc` leaves behind — F204's open half, H30's item.

`src/data/fetcher.py::validate_ohlc` removes every corruption class it finds (F204/F262
verified all six, each dropping exactly one bar). It **drops rather than raises**, and
nothing downstream notices the gap: the `min_bars` floor does not fire because the panel
is still long, the staleness check inspects only the latest bar, and the NaN gate sees
finite values because they are finite. The validation catches bad VALUES; nothing catches
the DISCONTINUITY it creates.

**The reason this was not trivial to add.** A naive "flag any gap larger than the modal
step" detector is useless on intraday equity data, because *most* gaps are legitimate:
a US session is ~7 hourly bars and an overnight gap follows every one. Measured on the
committed live archive, 15% of steps exceed one hour and every one of those is a session
boundary. A detector that fires on all of them would be noise, and noise is how the
original poison-cache footgun survived (F167).

So the question is not "is there a gap" but **"is there a gap WITHIN a session"** — an
hour missing from the middle of a trading day, which no market calendar explains. That is
exactly the shape `validate_ohlc` produces when it drops a corrupt bar, and it is
distinguishable without any calendar data: an intra-session hole has bars on both sides on
the SAME calendar date.

This is a detector, not a behaviour change. Nothing on the live path calls it. Wiring it
into `fetch_yfinance` — to raise, or to emit a monitor event rather than a `log.warning`
(F204's third instance of "degraded paths announce themselves to a log nobody keeps") — is
a one-line owner decision, deliberately left to the owner.

Usage::

    python3 tools/bar_continuity.py            # report on the committed live archive
"""
from __future__ import annotations

import collections
import json
import os
import sys
from typing import Dict, List, Optional, Sequence

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVE = os.path.join(
    REPO, "data", "live_runs", "archive_2026-06-18_pre_clean_run",
    "signal_history.jsonl")


def _modal_step_seconds(stamps: Sequence) -> Optional[float]:
    """The panel's own cadence, inferred rather than assumed.

    Taking the MODE, not the min or the mean: the min is fooled by a duplicate bar and
    the mean by the overnight gaps that dominate the tail.
    """
    if len(stamps) < 3:
        return None
    steps = [(stamps[i + 1] - stamps[i]).total_seconds()
             for i in range(len(stamps) - 1)]
    steps = [s for s in steps if s > 0]
    if not steps:
        return None
    return collections.Counter(steps).most_common(1)[0][0]


def analyse(index) -> Dict[str, object]:
    """Classify every gap in a DatetimeIndex as intra-session or session-boundary.

    Returns counts plus the intra-session holes, which are the actionable ones.
    """
    stamps = list(index)
    step = _modal_step_seconds(stamps)
    if step is None:
        return {"bars": len(stamps), "step_seconds": None, "intra_session_holes": [],
                "session_boundaries": 0, "duplicate_stamps": 0}

    holes: List[dict] = []
    boundaries = 0
    duplicates = 0
    for i in range(len(stamps) - 1):
        delta = (stamps[i + 1] - stamps[i]).total_seconds()
        if delta <= 0:
            duplicates += 1
            continue
        if delta <= step * 1.01:
            continue
        # A gap whose two sides fall on the SAME calendar date cannot be an overnight
        # or weekend break, so no market calendar is needed to call it suspicious.
        if stamps[i].date() == stamps[i + 1].date():
            holes.append({
                "after": str(stamps[i]),
                "before": str(stamps[i + 1]),
                "gap_seconds": delta,
                "missing_bars": int(round(delta / step)) - 1,
            })
        else:
            boundaries += 1
    return {
        "bars": len(stamps),
        "step_seconds": step,
        "intra_session_holes": holes,
        "missing_bars": sum(h["missing_bars"] for h in holes),
        "session_boundaries": boundaries,
        "duplicate_stamps": duplicates,
    }


def is_continuous(index) -> bool:
    """True when no bar is missing from the middle of a trading day."""
    return not analyse(index)["intra_session_holes"]


def _archive_index():
    import pandas as pd
    by = {}
    with open(ARCHIVE, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                row = json.loads(line)
                if row.get("bar_time"):
                    by[row["bar_time"]] = row
    return pd.DatetimeIndex(sorted(pd.to_datetime(list(by))))


def main(argv: Optional[Sequence[str]] = None) -> int:
    idx = _archive_index()
    out = analyse(idx)
    print("BAR CONTINUITY — committed live archive")
    print("  bars                : {}".format(out["bars"]))
    print("  inferred cadence    : {:.0f} s".format(out["step_seconds"]))
    print("  session boundaries  : {}  (expected — overnight/weekend)".format(
        out["session_boundaries"]))
    print("  duplicate stamps    : {}".format(out["duplicate_stamps"]))
    print("  INTRA-SESSION HOLES : {}".format(len(out["intra_session_holes"])))
    for h in out["intra_session_holes"][:10]:
        print("     {} -> {}  ({} bar(s) missing)".format(
            h["after"], h["before"], h["missing_bars"]))
    return 1 if out["intra_session_holes"] else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
export_stop_exits.py — one row per stop-type exit of the archived paper run, for
ENGINE_V3 item (g). The rows are DATA POINTS with their provenance labelled; they are
not an estimate of `stop_slippage_pct` (docs/research/DECOMMISSION_TRADER_QUESTION.md,
the (g) amendment in docs/research/ENGINE_V3_QUESTION.md).

Why this exists: the `trades` table has no stop level (live/state.py keeps `stop_price`
only on the transient `position` row), `trades.exit_time` is the BOOKING cycle, not the
fill (live/state.py `close_position`: `datetime.now()`), and IBKR-native and software
stops share `exit_type="stop_hit"` (live/trader.py vs live/broker.py). So the stop level,
the fill time and the fill source have to be recovered from the monitor events and the
trader log, and every row says where each value came from.

Inputs (all read-only):
  --archive DIR       the sanitized archive written by ops/archive_and_start_new_run.py.
                      trades.jsonl / monitor_events.jsonl are read from it when present
                      (they are the export of the same state.db, written seconds earlier);
                      otherwise --db is read in sqlite read-only mode.
  --trader-log PATH   optional. local_logs/trader.log (gitignored). Supplies
                      `Position opened … SL=` (stop_level_source=log_sl, direction) and
                      `Bracket filled … fill_time=` (fill_time_source=ibkr_execution).
  --bars PATH         optional. Hourly OHLC csv (data/cache/<SYMBOL>_1h.csv) for
                      exit_bar_open. Missing -> null.
  --log-tz NAME       timezone of the log's timestamps (default Europe/London, the Pi).

Outputs:
  DIR/stop_exits.jsonl                                 (committable; redacted)
  local_backups/trader_log_exits_<date>.redacted.txt   (gitignored; the log excerpt is
                                                        NEVER written into the archive —
                                                        OPERATIONS.md §1 rule 3)
  a summary on stdout: counts by fill_source / fill_time_source, and the slippage data
  points in price units with n stated (no compounding, F160).

Row schema (exactly, in this order):
  entry_time, exit_time (booking), fill_time, fill_time_source ∈ {ibkr_execution,
  software_cycle, booking}, symbol, qty, direction, entry_basis, stop_level,
  stop_level_source ∈ {log_sl, event_stop, reconstructed}, exit_price,
  fill_source ∈ {ibkr_native_stp, ibkr_native_untyped, software_fill,
  software_mark_estimate, inferred}, exit_bar_open, session_boundary, duplicate_writer

Row selection: exit_type == "stop_hit", or exit_type == "bracket_exit" with return_pct < 0
(the untyped native exit of the fills() fallback, live/broker.py).

Exclusions the consumer must apply (stated in the summary too): `software_mark_estimate`
and `inferred` are not fills; `fill_time_source=booking` rows cannot be split into
intraday vs gap, so they are excluded from that split.

Never prints or writes an account id: every string is passed through the widened
redaction regex before it is written or printed.
"""
from __future__ import annotations

import argparse
import bisect
import csv
import json
import os
import re
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACCT_RE = re.compile(r"\b(?:DU[A-Z]?|U)[0-9]{5,}\b")   # widened: DU…, DUD…, U…

EVENT_WINDOW_BEFORE = timedelta(seconds=120)   # exit event precedes booking by seconds
EVENT_WINDOW_AFTER = timedelta(seconds=5)
LOG_MATCH_WINDOW = timedelta(seconds=180)
DUPLICATE_WINDOW = timedelta(seconds=60)       # F97/F160: two writers inside one cycle

LOG_LINE = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) \[(\w+)\] (\S+) \u2014 (.*)$")
LOG_KEEP = re.compile(r"Position opened|Bracket filled|Software stop filled|SOFTWARE STOP"
                      r"|fill unavailable|inferred")
RX_OPENED = re.compile(r"Position opened: (LONG|SHORT) (\d+) (\S+) @ ([0-9.]+) \| TP=(\S+) SL=(\S+)")
RX_BRACKET = re.compile(r"Bracket filled \| fill_price=([0-9.]+) \| fill_time=(\S+) \| ret=")
RX_EVENT_STOP = re.compile(r"breached stop=([0-9.]+)")


def _redact(v):
    return ACCT_RE.sub("<acct-redacted>", v) if isinstance(v, str) else v


def _say(msg):
    print(_redact(str(msg)))


def _parse_ts(s):
    """ISO-ish string -> aware UTC datetime, or None."""
    if s in (None, "", "None"):
        return None
    s = str(s).strip().replace("Z", "+00:00")
    try:
        t = datetime.fromisoformat(s)
    except ValueError:
        try:
            t = datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return t.astimezone(timezone.utc)


def _tz(name):
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(name)
    except Exception:
        return None


def _f(v):
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


# ── Sources ──────────────────────────────────────────────────────────────────────
def _load_jsonl(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


def load_tables(archive, db):
    """trades + monitor_events from the archive JSONL, else from state.db read-only."""
    tj = os.path.join(archive, "trades.jsonl")
    ej = os.path.join(archive, "monitor_events.jsonl")
    if os.path.exists(tj) and os.path.exists(ej):
        return _load_jsonl(tj), _load_jsonl(ej), "archive_jsonl"
    if not os.path.exists(db):
        raise SystemExit(f"FATAL: neither {archive}/trades.jsonl nor {db} found")
    ro = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    ro.row_factory = sqlite3.Row
    trades = [dict(r) for r in ro.execute("SELECT * FROM trades ORDER BY entry_time")]
    events = [dict(r) for r in ro.execute("SELECT * FROM monitor_events ORDER BY id")]
    ro.close()
    return trades, events, "state_db_readonly"


def parse_log(path, log_tz):
    """The trader log, reduced to the exit-relevant lines, timestamps converted to UTC."""
    opened, brackets, sw_filled, sw_unavail, inferred, kept = [], [], [], [], [], []
    tz = _tz(log_tz)
    if not path or not os.path.exists(path):
        return {"opened": opened, "brackets": brackets, "sw_filled": sw_filled,
                "sw_unavail": sw_unavail, "inferred": inferred, "kept": kept,
                "available": False}
    with open(path, errors="replace", encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            m = LOG_LINE.match(line)
            if not m:
                continue
            ts, level, _name, msg = m.groups()
            if not LOG_KEEP.search(msg):
                continue
            kept.append(_redact(line))
            t = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
            t = (t.replace(tzinfo=tz) if tz else t.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)
            mo = RX_OPENED.search(msg)
            if mo:
                opened.append({"t": t, "direction": mo.group(1).lower(), "qty": int(mo.group(2)),
                               "symbol": mo.group(3), "entry_price": _f(mo.group(4)),
                               "tp": _f(mo.group(5)), "sl": _f(mo.group(6))})
                continue
            mb = RX_BRACKET.search(msg)
            if mb:
                brackets.append({"t": t, "fill_price": _f(mb.group(1)),
                                 "fill_time": _parse_ts(mb.group(2))})
                continue
            ms = re.search(r"Software stop filled \| price=([0-9.]+)", msg)
            mu = re.search(r"SOFTWARE STOP fill unavailable \u2014 using mark ([0-9.]+)", msg)
            if ms:
                sw_filled.append({"t": t, "price": _f(ms.group(1))})
            elif mu:
                sw_unavail.append({"t": t, "price": _f(mu.group(1))})
            elif "inferred" in msg and "Fill data unavailable" in msg:
                inferred.append({"t": t})
    return {"opened": opened, "brackets": brackets, "sw_filled": sw_filled,
            "sw_unavail": sw_unavail, "inferred": inferred, "kept": kept, "available": True}


def load_bars(path):
    """Hourly bars -> sorted list of (start_utc, open). Tolerant of column naming."""
    if not path or not os.path.exists(path):
        return []
    out = []
    with open(path, newline="", encoding="utf-8") as fh:
        rdr = csv.reader(fh)
        header = next(rdr, None)
        if not header:
            return []
        lower = [h.strip().lower() for h in header]
        try:
            oi = lower.index("open")
        except ValueError:
            oi = next((i for i, h in enumerate(lower) if h.startswith("open")), None)
        if oi is None:
            return []
        for row in rdr:
            if not row or len(row) <= oi:
                continue
            t = _parse_ts(row[0])
            o = _f(row[oi])
            if t is not None and o is not None:
                out.append((t, o))
    out.sort(key=lambda x: x[0])
    return out


def exit_bar_open(bars, fill_time):
    """Open of the hourly bar containing fill_time; if the fill falls between sessions,
    the open of the first bar at/after it (the v3 gap-fill reference, rule (b)1)."""
    if not bars or fill_time is None:
        return None
    starts = [b[0] for b in bars]
    i = bisect.bisect_right(starts, fill_time) - 1
    if i >= 0 and fill_time < starts[i] + timedelta(hours=1):
        return bars[i][1]
    j = bisect.bisect_left(starts, fill_time)
    return bars[j][1] if j < len(bars) else None


# ── Row construction ─────────────────────────────────────────────────────────────
def _nearest(items, t, window, key="t", pred=None):
    best, best_d = None, None
    for it in items:
        if pred and not pred(it):
            continue
        d = abs(it[key] - t)
        if d <= window and (best_d is None or d < best_d):
            best, best_d = it, d
    return best


def _events_near(events, t, before=EVENT_WINDOW_BEFORE, after=EVENT_WINDOW_AFTER):
    lo, hi = t - before, t + after
    return [e for e in events if e["_t"] is not None and lo <= e["_t"] <= hi]


def build_rows(trades, events, log, bars, stop_pct, ny_tz):
    for e in events:
        e["_t"] = _parse_ts(e.get("event_time"))
    exitish = [e for e in events if e["_t"] is not None and (
        e.get("category") in ("stop", "fill", "exit")
        or str(e.get("message", "")).startswith("Exit filled"))]

    rows = []
    for tr in trades:
        et = tr.get("exit_type")
        ret = _f(tr.get("return_pct"))
        if not (et == "stop_hit" or (et == "bracket_exit" and ret is not None and ret < 0)):
            continue
        entry_t = _parse_ts(tr.get("entry_time"))
        exit_t = _parse_ts(tr.get("exit_time"))
        exit_price = _f(tr.get("exit_price"))
        qty = tr.get("qty")

        # direction: the log's "Position opened" line if it matches; else long (the trader
        # gates shorts off, TRADER_ALLOW_SHORTS=False; trades has no direction column)
        opened = _nearest(log["opened"], entry_t, LOG_MATCH_WINDOW,
                          pred=lambda o: qty is None or o["qty"] == qty) if entry_t else None
        direction = opened["direction"] if opened else "long"

        if exit_price is None or ret is None:
            entry_basis = None
        elif direction == "long":
            entry_basis = exit_price / (1 + ret) if ret != -1 else None
        else:
            entry_basis = exit_price / (1 - ret) if ret != 1 else None

        near = _events_near(exitish, exit_t) if exit_t else []
        sw_trigger = [e for e in near if e.get("category") == "stop"
                      and "SOFTWARE STOP triggered" in str(e.get("message", ""))]
        sw_unavail = [e for e in near if e.get("category") == "stop"
                      and "fill unavailable" in str(e.get("message", ""))]
        inferred_ev = [e for e in near if e.get("category") == "fill"
                       and "inferred" in str(e.get("message", ""))]
        # Log-only fallback (the monitor event is the primary witness): a software
        # stop line counts for THIS trade only if its price is this trade's exit_price,
        # because a same-cycle neighbour books within the same seconds (F97).
        def _same_price(x):
            return exit_price is not None and x.get("price") is not None \
                and abs(x["price"] - exit_price) < 0.005
        if exit_t and not sw_unavail and log["sw_unavail"]:
            hit = _nearest(log["sw_unavail"], exit_t, LOG_MATCH_WINDOW, pred=_same_price)
            if hit:
                sw_unavail = [{"_t": hit["t"], "message": ""}]
        if exit_t and not sw_trigger and log["sw_filled"]:
            hit = _nearest(log["sw_filled"], exit_t, LOG_MATCH_WINDOW, pred=_same_price)
            if hit:
                sw_trigger = [{"_t": hit["t"], "message": ""}]

        # fill_source
        if sw_unavail:
            fill_source = "software_mark_estimate"
        elif sw_trigger:
            fill_source = "software_fill"
        elif inferred_ev:
            fill_source = "inferred"
        elif et == "stop_hit":
            fill_source = "ibkr_native_stp"
        else:
            fill_source = "ibkr_native_untyped"

        # fill_time
        bracket = None
        if exit_t and exit_price is not None and fill_source.startswith("ibkr_native"):
            bracket = _nearest(log["brackets"], exit_t, LOG_MATCH_WINDOW,
                               pred=lambda b: b["fill_price"] is not None
                               and abs(b["fill_price"] - exit_price) < 0.005)
        if bracket and bracket["fill_time"] is not None:
            fill_time, fill_time_source = bracket["fill_time"], "ibkr_execution"
        elif fill_source in ("software_fill", "software_mark_estimate") and (sw_trigger or sw_unavail):
            src = (sw_trigger or sw_unavail)[0]["_t"]
            fill_time, fill_time_source = src, "software_cycle"
        else:
            fill_time, fill_time_source = exit_t, "booking"

        # stop_level
        stop_level, stop_level_source = None, "reconstructed"
        if opened and opened["sl"] is not None:
            stop_level, stop_level_source = opened["sl"], "log_sl"
        else:
            for e in sw_trigger:
                m = RX_EVENT_STOP.search(str(e.get("message", "")))
                if m:
                    stop_level, stop_level_source = _f(m.group(1)), "event_stop"
                    break
        if stop_level is None and entry_basis is not None and stop_pct is not None:
            stop_level = round(entry_basis * (1 - stop_pct), 2) if direction == "long" \
                else round(entry_basis * (1 + stop_pct), 2)
            stop_level_source = "reconstructed"

        # exit_bar_open / session_boundary: only when the fill time is a fill time
        if fill_time_source == "booking":
            bar_open, boundary = None, None
        else:
            bar_open = exit_bar_open(bars, fill_time)
            if entry_t is None or fill_time is None:
                boundary = None
            elif ny_tz:
                boundary = entry_t.astimezone(ny_tz).date() != fill_time.astimezone(ny_tz).date()
            else:
                boundary = entry_t.date() != fill_time.date()

        duplicate_writer = bool(exit_t) and len(
            _events_near(exitish, exit_t, DUPLICATE_WINDOW, DUPLICATE_WINDOW)) >= 2

        rows.append({
            "entry_time": _redact(tr.get("entry_time")),
            "exit_time": _redact(tr.get("exit_time")),
            "fill_time": fill_time.isoformat() if fill_time else None,
            "fill_time_source": fill_time_source,
            "symbol": _redact(tr.get("symbol")),
            "qty": qty,
            "direction": direction,
            "entry_basis": round(entry_basis, 6) if entry_basis is not None else None,
            "stop_level": stop_level,
            "stop_level_source": stop_level_source,
            "exit_price": exit_price,
            "fill_source": fill_source,
            "exit_bar_open": bar_open,
            "session_boundary": boundary,
            "duplicate_writer": duplicate_writer,
        })
    return rows


# ── Summary (data points, n stated; price units; no compounding) ─────────────────
def summarize(rows):
    def adverse(level, price, direction):
        # positive = fill worse than the level, in price units of the level
        if level in (None, 0) or price is None:
            return None
        return (level - price) / level if direction == "long" else (price - level) / level

    usable = [r for r in rows if r["fill_source"] in ("ibkr_native_stp", "ibkr_native_untyped")
              and r["fill_time_source"] != "booking"]
    intraday = [r for r in usable if r["session_boundary"] is False]
    gap = [r for r in usable if r["session_boundary"] is True]
    software = [r for r in rows if r["fill_source"] == "software_fill"]
    excluded = [r for r in rows if r["fill_source"] in ("software_mark_estimate", "inferred")]
    booking = [r for r in rows if r["fill_source"].startswith("ibkr_native")
               and r["fill_time_source"] == "booking"]

    _say(f"stop_exits: {len(rows)} rows")
    _say(f"  by fill_source:      {dict(Counter(r['fill_source'] for r in rows))}")
    _say(f"  by fill_time_source: {dict(Counter(r['fill_time_source'] for r in rows))}")
    _say(f"  by stop_level_source:{dict(Counter(r['stop_level_source'] for r in rows))}")
    _say(f"  n_native_intraday={len(intraday)}  n_native_gap={len(gap)}  n_software={len(software)}  "
         f"n_native_booking_only(excluded from split)={len(booking)}  n_not_fills(excluded)={len(excluded)}")
    _say("  data points (price units, positive = adverse; NOT an estimate of stop_slippage_pct):")
    for r in intraday:
        _say(f"    intraday native  stop-vs-fill  {adverse(r['stop_level'], r['exit_price'], r['direction'])!r}"
             f"  [{r['stop_level_source']}, {r['fill_source']}, fill {r['fill_time']}]")
    for r in gap:
        ref = r["exit_bar_open"]
        v = None if ref in (None, 0) or r["exit_price"] is None else (
            (ref - r["exit_price"]) / ref if r["direction"] == "long" else (r["exit_price"] - ref) / ref)
        _say(f"    gap native       open-vs-fill  {v!r}  [exit_bar_open={ref}, {r['fill_source']}, fill {r['fill_time']}]")
    for r in software:
        _say(f"    software         trigger-vs-fill {adverse(r['stop_level'], r['exit_price'], r['direction'])!r}"
             f"  [{r['stop_level_source']}; the :32-mark lateness is DIVERGE under (i), reported, never used]")
    if not intraday:
        _say("  n_native_intraday = 0 in this source: the archived-live instrument is CLOSED for (g); "
             "use the gap distribution + the stated prior (docs/research/ENGINE_V3_QUESTION.md (g) amendment)")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--archive", required=True, help="sanitized archive dir (output goes here)")
    ap.add_argument("--trader-log", default=None, help="local_logs/trader.log (optional, gitignored)")
    ap.add_argument("--bars", default=None, help="hourly OHLC csv for exit_bar_open (optional)")
    ap.add_argument("--db", default=os.path.join(REPO, "live", "state.db"),
                    help="fallback source when the archive has no JSONL (read-only)")
    ap.add_argument("--log-tz", default="Europe/London", help="timezone of trader.log timestamps")
    ap.add_argument("--stop-pct", type=float, default=None,
                    help="stop fraction for stop_level_source=reconstructed "
                         "(default: config.ASSETS[<LIVE_SYMBOL>_HOURLY]['stop_loss_pct'] if importable)")
    ap.add_argument("--date", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    ap.add_argument("--backups-dir", default=os.path.join(REPO, "local_backups"))
    args = ap.parse_args()

    archive = os.path.abspath(args.archive)
    if not os.path.isdir(archive):
        raise SystemExit(f"FATAL: archive dir {archive} not found")

    stop_pct = args.stop_pct
    if stop_pct is None:
        try:
            sys.path.insert(0, REPO)
            import config  # noqa: WPS433
            mode = f"{getattr(config, 'LIVE_SYMBOL', 'TQQQ')}_HOURLY"
            stop_pct = float(config.ASSETS[mode]["stop_loss_pct"])
        except Exception:
            stop_pct = None
            _say("warning: no --stop-pct and config not importable; reconstructed stop_level will be null")

    trades, events, source = load_tables(archive, args.db)
    log = parse_log(args.trader_log, args.log_tz)
    bars = load_bars(args.bars)
    rows = build_rows(trades, events, log, bars, stop_pct, _tz("America/New_York"))

    out = os.path.join(archive, "stop_exits.jsonl")
    with open(out, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, default=str) + "\n")
    _say(f"wrote {out} ({len(rows)} rows; source={source}; log={'yes' if log['available'] else 'no'}; "
         f"bars={len(bars)})")

    if log["available"]:
        os.makedirs(args.backups_dir, exist_ok=True)
        excerpt = os.path.join(args.backups_dir, f"trader_log_exits_{args.date}.redacted.txt")
        with open(excerpt, "w", encoding="utf-8") as fh:
            fh.write("\n".join(log["kept"]) + ("\n" if log["kept"] else ""))
        _say(f"log excerpt (LOCAL ONLY, gitignored, redacted): {excerpt} ({len(log['kept'])} lines)")

    summarize(rows)
    # Belt and braces: the file we just wrote must not contain an account id.
    with open(out, encoding="utf-8") as fh:
        if ACCT_RE.search(fh.read()):
            os.unlink(out)
            raise SystemExit("FATAL: redaction failed — stop_exits.jsonl removed; do not commit")
    return 0


if __name__ == "__main__":
    sys.exit(main())

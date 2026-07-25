#!/usr/bin/env python3
"""Replay a candidate threshold config against a recorded live signal history (H26).

H26 asks for a shadow evaluator — "a non-trading process that replays bars and logs what
a candidate config would have done" — as infrastructure to de-risk active-engine
experiments. Most of it already exists and nobody had joined the pieces.

`live/signals.py` logs one row per scheduler cycle into `signal_history.jsonl`, and each
row carries the **raw indicator values** alongside the derived signals::

    {"bar_time": ..., "bar_close": ..., "rsi": 40.7, "vwap_zscore": -0.96,
     "momentum_signal": 0, "volume_signal": 0, "signal": 0}

`rsi` and `vwap_zscore` are exactly the quantities the entry thresholds are compared
against. So any candidate RSI/VWAP threshold set can be replayed over a recorded run
**offline, with no market data and no new logging** — which is the part of H26 that does
not need to be built.

What this does NOT do, stated so the tool is not over-read:

* It cannot replay a different RSI *period* or MACD window — those change the indicator,
  and only its value was logged (the F23 territory).
* It cannot replay the MACD histogram-turn term, which is not logged; the momentum long
  condition is `(rsi < oversold) & (hist rising)` and only the first half is replayable.
  So the counts below are an **upper bound** on how often a candidate would fire.
* It says nothing about fills, PnL or drawdown. It answers "would this bar have been a
  candidate?", not "would the trade have made money".

Usage::

    python3 tools/shadow_replay.py [--history PATH] [--oversold 80 38] [--zthresh 0.5]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Dict, List, Sequence

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_HISTORY = os.path.join(
    REPO, "data", "live_runs", "archive_2026-06-18_pre_clean_run",
    "signal_history.jsonl")


def load_bars(path: str = DEFAULT_HISTORY) -> List[dict]:
    """Distinct BARS from a cycle-keyed history.

    The logger writes one row per scheduler cycle, so an unchanged bar repeats across
    cycles — 543 rows collapse to 322 bars in the committed archive. Counting rows
    instead of bars would weight quiet hours by how often the scheduler happened to run.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(
            "no signal history at {}. This tool replays a RECORDED run; it does not "
            "fetch data.".format(path))
    by_bar: Dict[str, dict] = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("bar_time"):
                by_bar[row["bar_time"]] = row
    return list(by_bar.values())


def replay(bars: Sequence[dict], oversold: float, overbought: float,
           z_threshold: float) -> dict:
    """Candidate-threshold hit rates over recorded bars. Upper bounds — see module doc."""
    rsi = [b["rsi"] for b in bars if b.get("rsi") is not None]
    z = [b["vwap_zscore"] for b in bars if b.get("vwap_zscore") is not None]
    n = len(rsi) or 1
    both = sum(1 for x in rsi if overbought < x < oversold)
    return {
        "bars": len(bars),
        "rsi_below_oversold_pct": round(sum(1 for x in rsi if x < oversold) / n * 100, 1),
        "rsi_above_overbought_pct": round(sum(1 for x in rsi if x > overbought) / n * 100, 1),
        "in_both_zones_pct": round(both / n * 100, 1),
        "vwap_long_pct": round(
            sum(1 for x in z if x < -z_threshold) / (len(z) or 1) * 100, 1),
        "zones_overlap": oversold > overbought,
    }


def main(argv: Sequence[str] | None = None) -> int:
    sys.path.insert(0, REPO)
    import config

    mode = config.ACTIVE_MODE
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--history", default=DEFAULT_HISTORY)
    ap.add_argument("--oversold", type=float, nargs="+",
                    default=[getattr(config, "RSI_OVERSOLD_{}".format(mode), 38),
                             config.RSI_OVERSOLD])
    ap.add_argument("--overbought", type=float,
                    default=getattr(config, "RSI_OVERBOUGHT_{}".format(mode), 62))
    ap.add_argument("--zthresh", type=float,
                    default=getattr(config, "VWAP_ZSCORE_THRESH_{}".format(mode), 1.0))
    args = ap.parse_args(argv)

    try:
        bars = load_bars(args.history)
    except FileNotFoundError as exc:
        print("  {}".format(exc))
        return 2

    print("  shadow replay over {} recorded bars ({})".format(
        len(bars), os.path.relpath(args.history, REPO)))
    print("  NOTE: upper bounds — the MACD histogram-turn term is not logged, so a real")
    print("        entry fires on a SUBSET of the bars counted here.\n")
    print("  {:>9} {:>12} {:>14} {:>16} {:>13}".format(
        "oversold", "rsi<os %", "rsi>ob %", "in BOTH zones %", "vwap long %"))
    for oversold in args.oversold:
        r = replay(bars, oversold, args.overbought, args.zthresh)
        flag = "  <- zones OVERLAP" if r["zones_overlap"] else ""
        print("  {:>9} {:>12} {:>14} {:>16} {:>13}{}".format(
            oversold, r["rsi_below_oversold_pct"], r["rsi_above_overbought_pct"],
            r["in_both_zones_pct"], r["vwap_long_pct"], flag))
    print("\n  overbought={}  vwap z-threshold={}".format(args.overbought, args.zthresh))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

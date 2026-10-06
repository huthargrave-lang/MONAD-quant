#!/usr/bin/env python3
"""Census: where do the backtest and the live bot decide differently?

This project's central unexplained fact is that the backtest shows an edge and the live
bot is flat. Individual divergences are recorded — F141 (the entry gate), F148 (the UTC
time gate), F26 (the slope flags) — but nobody had enumerated the decision inputs in one
place and marked each AGREE or DIVERGE.

Every dimension below is extracted from source at run time rather than written down, so
the table cannot quietly rot as the code moves. A dimension where the two paths happen to
hold the same value but read it from different places is reported as `COINCIDENT`: it
agrees today and nothing keeps it agreeing.

Usage::

    python3 tools/live_backtest_parity.py [--json out.json]
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

RUNNER = "src/backtest/runner.py"
SIGNALS = "live/signals.py"
TRADER = "live/trader.py"
STATE = "live/state.py"
ENGINE = "src/strategy/engine.py"

AGREE, DIVERGE, COINCIDENT, DORMANT = "AGREE", "DIVERGE", "COINCIDENT", "DORMANT"
# DORMANT: the backtest has a capability the live path lacks, but its flag is OFF, so
# there is no behavioural difference TODAY. Counting these as divergences would inflate
# the headline; ignoring them would hide a trap, because enabling the flag in a sweep
# silently makes the backtest model something the bot cannot do.


def _tree(rel):
    with open(os.path.join(REPO, rel), encoding="utf-8") as fh:
        return ast.parse(fh.read())


def _source(rel):
    with open(os.path.join(REPO, rel), encoding="utf-8") as fh:
        return fh.read()


def _call_keywords(rel, func_name):
    """{kwarg: unparsed value} for the first call to `func_name` in `rel`."""
    for node in ast.walk(_tree(rel)):
        if isinstance(node, ast.Call):
            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if name == func_name:
                return {kw.arg: ast.unparse(kw.value) for kw in node.keywords if kw.arg}
    return {}


def _signature_default(rel, func_name, param):
    for node in ast.walk(_tree(rel)):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            names = [a.arg for a in node.args.args]
            defaults = list(node.args.defaults)
            offset = len(names) - len(defaults)
            if param in names and names.index(param) >= offset:
                return ast.unparse(defaults[names.index(param) - offset])
    return None


def entry_gate():
    """The vol-regime gate each path APPLIES: the backtest's resolved value (the function
    run_backtest calls) against the literal the live path passes."""
    from src.backtest.runner import resolve_regime_filter
    backtest = resolve_regime_filter("hourly")
    live_src = _call_keywords(SIGNALS, "generate_trades").get("use_regime_filter")
    live = None if live_src is None else live_src == "True"
    verdict = AGREE if live is not None and backtest == live else DIVERGE
    return "use_regime_filter={} (resolved)".format(backtest), \
        "use_regime_filter={}".format(live_src or "(omitted)"), verdict, "F141"


def slope_flags():
    bt = _call_keywords(RUNNER, "generate_trades")
    lv = _call_keywords(SIGNALS, "generate_trades")
    passed_bt = [f for f in ("use_slope_regime", "longs_only") if f in bt]
    passed_lv = [f for f in ("use_slope_regime", "longs_only") if f in lv]
    # Both end up False; the backtest gets there by omission and the live path by
    # explicit argument, so a change to either signature or config moves only one.
    verdict = COINCIDENT if passed_bt != passed_lv else AGREE
    return ("omitted" if not passed_bt else ", ".join(passed_bt),
            "explicit False" if passed_lv else "omitted", verdict, "F26")


def _live_cron():
    """(hours, minute) of the live scheduler's CronTrigger, read from live/trader.py."""
    for node in ast.walk(_tree(TRADER)):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "CronTrigger":
            kw = {k.arg: ast.literal_eval(k.value) for k in node.keywords}
            lo, hi = (int(x) for x in str(kw["hour"]).split("-"))
            return list(range(lo, hi + 1)), int(kw["minute"])
    return None


def acted_bars(days=10):
    """Which session bars each path can act on, over a synthetic fortnight.

    Backtest: raw 24h bars through the canonical session loader filter
    (fetcher.regular_session), then run_backtest's default trade_hours gate.
    Live: yfinance session bars (the same filter); at each cron firing (ET) the bot acts
    on the latest bar at least 60 minutes old (live/signals.py drops younger bars).
    Returns (backtest_set, live_set), both restricted to bars live had a later firing for.
    """
    import pandas as pd
    from src.data.fetcher import regular_session
    cron = _live_cron()
    raw = pd.DataFrame({"close": 1.0}, index=pd.date_range("2026-03-02 00:30", periods=24 * days, freq="h"))
    session = regular_session(raw)
    gate = _signature_default(RUNNER, "run_backtest", "trade_hours")
    lo, hi = ast.literal_eval(gate) if gate and gate != "None" else (0, 24)
    backtest = {t for t in session.index if lo <= t.hour < hi}
    live = set()
    if cron:
        hours, minute = cron
        starts = list(session.index)
        et_days = sorted({t.tz_localize("UTC").tz_convert("America/New_York").normalize() for t in starts})
        for day in et_days:
            if day.weekday() >= 5:
                continue
            for h in hours:
                fire = (day + pd.Timedelta(hours=h, minutes=minute)).tz_convert("UTC").tz_localize(None)
                done = [t for t in starts if fire - t >= pd.Timedelta(minutes=60)]
                if done:
                    live.add(max(done))
        horizon = max(live) if live else None
        backtest = {t for t in backtest if horizon is not None and t <= horizon}
    return backtest, live


def time_gate():
    """Behavioural: the exact set of session bars each path acts on (F148 found the old
    UTC hour gate kept only the morning)."""
    backtest, live = acted_bars()
    verdict = AGREE if backtest == live and backtest else DIVERGE
    return ("{} session bars acted on".format(len(backtest)),
            "{} bars acted on at the :{} cron".format(len(live), (_live_cron() or (0, "?"))[1]),
            verdict, "F148")


def shorts():
    """Behavioural: short entries the backtest path emits on a synthetic tape, against the
    live bot's policy (it computes shorts and skips them unless TRADER_ALLOW_SHORTS).
    `longs_only` gates no entry (F26), so only an actual count can show agreement."""
    import config
    import entry_gate_probe as probe
    from src.backtest.runner import resolve_regime_filter, suppress_disallowed_shorts
    from src.strategy.engine import build_features, generate_trades
    n_bt = 0
    for _, seed, drift in probe.PANELS:
        feat = build_features(probe.synth_panel(seed, drift, 1500, "1h", 0.008), timeframe="hourly")
        trades = generate_trades(feat, require_signals=1,
                                 use_regime_filter=resolve_regime_filter("hourly"))
        n_bt += int((suppress_disallowed_shorts(trades)["entry_signal"] == -1).sum())
    allow = bool(getattr(config, "TRADER_ALLOW_SHORTS", False))
    live = "shorts allowed" if allow else "0 (TRADER_ALLOW_SHORTS=False)"
    verdict = AGREE if (allow or n_bt == 0) else DIVERGE
    return "{} short entries emitted".format(n_bt), live, verdict, "F26"


def max_hold():
    """DIVERGE in the config, immaterial in practice — see `time_exit_bind_rate`.

    Measured across four seeded panels at the live band (1.00%/0.50%): at 0.8%/bar the
    time exit fires on 3 of 1759 trades and the mean-return difference between 8 and 10
    bars is under 0.1 bp. It only starts to bind below about 0.4%/bar. So this row is a
    real config divergence whose behavioural cost is ~zero at the volatility this
    strategy trades — recorded rather than dropped, because the *reason* it is harmless
    is that the bands resolve first, and that reason changes if the bands widen.
    """
    import config
    from src.backtest.runner import resolve_hold
    live_mode = "{}_HOURLY".format(getattr(config, "LIVE_SYMBOL", ""))
    bt = resolve_hold(live_mode, "hourly")   # what run_backtest uses for the live mode
    lv = getattr(config, "MAX_TRADE_BARS_LIVE", None)
    return ("{} bars (resolved for {})".format(bt, live_mode),
            "MAX_TRADE_BARS_LIVE={}".format(lv), AGREE if bt == lv else DIVERGE, None)


def time_exit_bind_rate(sigma=0.008, bars=4000, target=0.010, stop=0.005):
    """How often the clock, rather than a band, ends a trade — and what 8 vs 10 costs.

    Returns {trades, time_exits_at_8, time_exits_at_10, mean_return_delta_bp}. Offline:
    seeded synthetic panels, so it is a statement about the MECHANISM (a narrow band
    resolves before a short clock), not a measurement of any instrument.
    """
    import collections

    import entry_gate_probe as probe
    from src.strategy.engine import (build_features, compute_trade_returns,
                                     generate_trades)
    totals = collections.Counter()
    deltas = []
    for _, seed, drift in probe.PANELS:
        feat = build_features(probe.synth_panel(seed, drift, bars, "1h", sigma),
                              timeframe="hourly")
        trades = generate_trades(feat, require_signals=1, target_gain_pct=target,
                                 stop_loss_pct=stop)
        runs = {}
        # Seeded synthetic panels: a statement about the exit MECHANISM, measuring no
        # instrument, so it is not a counted trial (src/research/trials.UNCOUNTED_ALLOWED).
        from src.strategy.counted import uncounted
        with uncounted("synthetic mechanism panels for the time-exit bind rate"):
            for hold in (8, 10):
                runs[hold] = compute_trade_returns(trades, target_gain_pct=target,
                                                   stop_loss_pct=stop, max_trade_bars=hold)
        totals["trades"] += len(runs[8])
        for hold in (8, 10):
            counts = collections.Counter(runs[hold]["exit_type"])
            totals["time_exits_at_{}".format(hold)] += counts.get("time_exit", 0)
        if len(runs[8]):
            deltas.append(10000 * (runs[10]["return"].mean() - runs[8]["return"].mean()))
    return {"trades": totals["trades"],
            "time_exits_at_8": totals["time_exits_at_8"],
            "time_exits_at_10": totals["time_exits_at_10"],
            "mean_return_delta_bp": sum(deltas) / len(deltas) if deltas else 0.0}


def position_size():
    import config
    reads_config = "FIXED_POSITION_PCT" in _source(RUNNER)
    live_src = _source(STATE)
    hardcoded = None
    for node in ast.walk(_tree(STATE)):
        if isinstance(node, ast.FunctionDef) and node.name == "get_position_plan":
            for sub in ast.walk(node):
                if (isinstance(sub, ast.Assign)
                        and any(getattr(t, "id", None) == "position_pct"
                                for t in sub.targets)):
                    hardcoded = ast.unparse(sub.value)
    cfg = getattr(config, "FIXED_POSITION_PCT", None)
    same_value = hardcoded is not None and str(cfg) == hardcoded
    verdict = COINCIDENT if same_value else (AGREE if not hardcoded else DIVERGE)
    return ("config.FIXED_POSITION_PCT={}".format(cfg) if reads_config else "?",
            "position_pct = {} (literal)".format(hardcoded), verdict, None)


def _capability(flag, runner_token, trader_token):
    import config
    bt_has = runner_token in _source(RUNNER)
    lv_has = trader_token in _source(TRADER)
    on = bool(getattr(config, flag, False))
    backtest = "{} ({})".format("supported" if bt_has else "absent",
                                "ON" if on else "off")
    live = "supported" if lv_has else "absent"
    if bt_has == lv_has:
        return backtest, live, AGREE, None
    return backtest, live, DIVERGE if on else DORMANT, None


def opposing_exit():
    return _capability("USE_OPPOSING_SIGNAL_EXIT", "USE_OPPOSING_SIGNAL_EXIT", "OPPOSING")


def atr_stops():
    return _capability("USE_ATR_DYNAMIC_STOPS", "USE_ATR_DYNAMIC_STOPS", "ATR_STOP")


DIMENSIONS = [
    ("entry regime gate", entry_gate),
    ("slope-regime flags", slope_flags),
    ("intraday time gate", time_gate),
    ("max hold (time exit)", max_hold),
    ("short entries", shorts),
    ("position size", position_size),
    ("opposing-signal exit", opposing_exit),
    ("ATR dynamic stops", atr_stops),
]


def census():
    rows = []
    for name, probe in DIMENSIONS:
        backtest, live, verdict, node = probe()
        rows.append({"dimension": name, "backtest": str(backtest), "live": str(live),
                     "verdict": verdict, "recorded_in": node})
    counts = {v: sum(1 for r in rows if r["verdict"] == v)
              for v in (AGREE, COINCIDENT, DORMANT, DIVERGE)}
    return {"subject": "repository",  # not an observation of the world; see F230
            "rows": rows, "counts": counts}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", default=None)
    args = ap.parse_args(argv)

    report = census()
    width = max(len(r["dimension"]) for r in report["rows"])
    print("{:<{w}}  {:<10} {:<38} {}".format("dimension", "verdict", "backtest", "live",
                                             w=width))
    for row in report["rows"]:
        print("{:<{w}}  {:<10} {:<38} {}".format(
            row["dimension"], row["verdict"], row["backtest"][:38], row["live"][:44],
            w=width))
    counts = report["counts"]
    print("\n{} agree · {} coincident · {} dormant · {} divergent".format(
        counts[AGREE], counts[COINCIDENT], counts[DORMANT], counts[DIVERGE]))
    print("COINCIDENT = same value today, read from different places — nothing keeps "
          "them in step.")
    print("DORMANT   = the backtest can do something live cannot, but the flag is off.")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, sort_keys=True)
            fh.write("\n")
        print("\nwrote {}".format(args.json))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

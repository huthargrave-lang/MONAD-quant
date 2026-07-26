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
    bt = _call_keywords(RUNNER, "generate_trades")
    lv = _call_keywords(SIGNALS, "generate_trades")
    backtest = bt.get("use_regime_filter") or "(omitted → default {})".format(
        _signature_default(ENGINE, "generate_trades", "use_regime_filter"))
    live = lv.get("use_regime_filter", "(omitted)")
    verdict = AGREE if backtest == live else DIVERGE
    return backtest, live, verdict, "F141"


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


def time_gate():
    bt = "trade_hours=" + _call_keywords(RUNNER, "generate_trades").get(
        "trade_hours", "(omitted)")
    live_src = _source(TRADER)
    live = ("_is_market_hours() in ET" if "def _is_market_hours" in live_src
            else "(none found)")
    return bt, live, DIVERGE, "F148"


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
    bt = getattr(config, "MAX_TRADE_BARS", None)
    lv = getattr(config, "MAX_TRADE_BARS_LIVE", None)
    return ("MAX_TRADE_BARS={}".format(bt), "MAX_TRADE_BARS_LIVE={}".format(lv),
            AGREE if bt == lv else DIVERGE, None)


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

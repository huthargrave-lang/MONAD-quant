#!/usr/bin/env python3
"""Measure which entry gates in `generate_trades()` actually move entries (F26).

F26 says the 6-state slope-regime gate — CLAUDE.md's "core innovation" — is dead-wired,
and notes as a *separate* bug that `use_regime_filter` defaults to True while
`config.USE_REGIME_FILTER` is False. F26 states both qualitatively ("all 4 combos give
byte-identical entries", "this one DOES change entries") and carries no figures for the
second. This probe supplies them.

Three questions, in increasing order of how much the answer depends on the data:

1. **Structural.** Where do `use_slope_regime` and `longs_only` appear in the source of
   `generate_trades()`? If they appear only *after* `entry_signal` is assigned, and only
   inside blocks that write `regime_kelly_mult`, then entry-vector equality across the
   four flag combinations is a property of the code, not a statistic about a sample.
2. **Empirical, flag matrix.** Run the four combinations through the production
   `build_features` → `generate_trades` and hash the `entry_signal` vector. This confirms
   (1) rather than establishing it; a disagreement would mean the source read was wrong.
3. **Empirical, magnitude.** Toggle `use_regime_filter` and count entries. This one is a
   genuine measurement and its size depends on the panel, so it is reported per panel and
   never as a single headline number.

Panels are **synthetic and deterministic** (seeded), because this repo ships no cached
market data and the network is unavailable here. That is adequate for (1) and (2), which
are claims about wiring, and it is why (3) is reported as a range across four different
generated regimes rather than as one figure.

Usage::

    python3 tools/entry_gate_probe.py [--json PATH] [--bars 1500]
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import sys

import numpy as np
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

import config  # noqa: E402
from src.strategy.engine import build_features, generate_trades  # noqa: E402

FLAG_MATRIX = [(False, False), (False, True), (True, False), (True, True)]

# Four regimes so a count is never reported from a single generated tape.
HIGHVOL_SEEDS = (3, 5, 9, 21, 33)
HIGHVOL_BARS = 6000

PANELS = [
    ("drift_up", 7, 0.00030),
    ("drift_down", 11, -0.00030),
    ("flat", 13, 0.0),
    ("choppy", 17, 0.00008),
]


def synth_panel(seed: int, drift: float, bars: int, freq: str,
                sigma: float = 0.006) -> pd.DataFrame:
    """A deterministic OHLCV tape. Not a market model — a fixed input to the gates."""
    rng = np.random.default_rng(seed)
    steps = rng.normal(drift, sigma, bars)
    close = 100.0 * np.exp(np.cumsum(steps))
    spread = np.abs(rng.normal(0, 0.004, bars)) * close
    idx = pd.date_range("2021-01-04 09:00", periods=bars, freq=freq, tz="UTC")
    return pd.DataFrame(
        {
            "open": close * (1 + rng.normal(0, 0.001, bars)),
            "high": close + spread,
            "low": close - spread,
            "close": close,
            "volume": rng.uniform(1e5, 1e6, bars),
        },
        index=idx,
    )


def entry_hash(df: pd.DataFrame) -> str:
    raw = df["entry_signal"].to_numpy(dtype=np.int8).tobytes()
    return hashlib.sha256(raw).hexdigest()[:16]


def source_of(func_name: str, path: str) -> ast.FunctionDef:
    tree = ast.parse(open(os.path.join(REPO, path), encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            return node
    raise LookupError(func_name)


def structural_report() -> dict:
    """Where the two slope flags are read, relative to where entry_signal is written.

    A *write* is an assignment whose target names the column — `df["entry_signal"] = …`
    or `df.loc[mask, "entry_signal"] = …`. An earlier version of this counted
    `bear_long_mask = (df["entry_signal"] == 1) & …` as a write, because it matched on
    the unparsed statement rather than the target, and so reported the last write three
    lines later than it is.
    """
    fn = source_of("generate_trades", "src/strategy/engine.py")
    flag_lines, entry_write_lines, kelly_write_lines = [], [], []
    for node in ast.walk(fn):
        if isinstance(node, ast.Name) and node.id in ("use_slope_regime", "longs_only"):
            flag_lines.append(node.lineno)
        if isinstance(node, (ast.Assign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            target_text = " ".join(ast.unparse(t) for t in targets)
            if "entry_signal" in target_text:
                entry_write_lines.append(node.lineno)
            if "regime_kelly_mult" in target_text:
                kelly_write_lines.append(node.lineno)
    return {
        "slope_flag_read_lines": sorted(flag_lines),
        "entry_signal_write_lines": sorted(entry_write_lines),
        "regime_kelly_mult_write_lines": sorted(kelly_write_lines),
        "last_entry_signal_write": max(entry_write_lines),
        "first_slope_flag_read": min(flag_lines),
        "all_slope_reads_after_last_entry_write": (
            min(flag_lines) > max(entry_write_lines)
        ),
    }


def runner_call_report() -> dict:
    """Which keywords runner.py actually passes to generate_trades()."""
    tree = ast.parse(
        open(os.path.join(REPO, "src/backtest/runner.py"), encoding="utf-8").read())
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call)
                and getattr(node.func, "id", None) == "generate_trades"):
            return {
                "line": node.lineno,
                "keywords": sorted(k.arg for k in node.keywords if k.arg),
            }
    raise LookupError("generate_trades call in runner.py")


def probe_panel(name: str, seed: int, drift: float, bars: int,
                timeframe: str, sigma: float = 0.006) -> dict:
    freq = "1h" if timeframe == "hourly" else "1D"
    df = synth_panel(seed, drift, bars, freq, sigma)
    feat = build_features(df, timeframe=timeframe)
    common = dict(require_signals=1, target_gain_pct=0.01, stop_loss_pct=0.006)

    combos = {}
    for slope, longs in FLAG_MATRIX:
        out = generate_trades(feat, use_slope_regime=slope, longs_only=longs, **common)
        key = "slope={},longs_only={}".format(int(slope), int(longs))
        kelly = out["regime_kelly_mult"] if "regime_kelly_mult" in out else None
        combos[key] = {
            "entry_hash": entry_hash(out),
            "n_entries": int((out["entry_signal"] != 0).sum()),
            "kelly_mult_hash": (
                hashlib.sha256(kelly.round(6).to_numpy().tobytes()).hexdigest()[:16]
                if kelly is not None else None),
        }

    gate_on = generate_trades(feat, use_regime_filter=True, **common)
    gate_off = generate_trades(feat, use_regime_filter=False, **common)
    on_n = int((gate_on["entry_signal"] != 0).sum())
    off_n = int((gate_off["entry_signal"] != 0).sum())

    # The soft 50-MA gate branches on the presence of a `regime` column. `build_features`
    # always writes one — on hourly too — so the else-branch the code labels "Hourly mode"
    # never runs in production. Dropping the column reproduces what that branch WOULD do.
    with_regime = generate_trades(feat, **common)
    without_regime = generate_trades(feat.drop(columns=["regime"]), **common)
    prior = config.STRONG_BULL_SOFT_50MA_PCT
    try:                       # 0 disables the gate entirely — the candidate baseline
        config.STRONG_BULL_SOFT_50MA_PCT = 0.0
        ungated = generate_trades(feat, **common)
    finally:
        config.STRONG_BULL_SOFT_50MA_PCT = prior

    return {
        "panel": name,
        "timeframe": timeframe,
        "bars": bars,
        "sigma_per_bar": sigma,
        "has_regime_column": "regime" in feat.columns,
        "combos": combos,
        "distinct_entry_hashes": len({c["entry_hash"] for c in combos.values()}),
        "distinct_kelly_hashes": len({c["kelly_mult_hash"] for c in combos.values()}),
        "regime_filter": {
            "on_default_what_runner_gets": on_n,
            "off_what_config_says": off_n,
            "suppressed": off_n - on_n,
            "retained_fraction": round(on_n / off_n, 4) if off_n else None,
        },
        "soft_50ma_gate": {
            "strong_bull_bar_fraction": round(
                float((feat["regime"] == "STRONG_BULL").mean()), 4),
            "long_candidates_gate_disabled": int((ungated["entry_signal"] == 1).sum()),
            "longs_taken_branch": int((with_regime["entry_signal"] == 1).sum()),
            "longs_else_branch": int((without_regime["entry_signal"] == 1).sum()),
            "blocked_taken_branch": int((ungated["entry_signal"] == 1).sum()
                                        - (with_regime["entry_signal"] == 1).sum()),
            "blocked_else_branch": int((ungated["entry_signal"] == 1).sum()
                                       - (without_regime["entry_signal"] == 1).sum()),
        },
    }


def run(bars: int = 1500) -> dict:
    results = []
    for timeframe in ("hourly", "daily"):
        n = bars if timeframe == "hourly" else max(400, bars // 3)
        for name, seed, drift in PANELS:
            results.append(probe_panel(name, seed, drift, n, timeframe))
    # F194 measured the soft 50-MA gate on a sigma=1.1%/bar "3x ETF-like" hourly series.
    # Re-run at that volatility so the correction is stated in F194's own units.
    highvol = []
    for seed in HIGHVOL_SEEDS:
        highvol.append(probe_panel("hv_seed{}".format(seed), seed, 0.0002,
                                   HIGHVOL_BARS, "hourly", sigma=0.011))
    return {
        "structural": structural_report(),
        "runner_call": runner_call_report(),
        "panels": results,
        "highvol_panels": highvol,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bars", type=int, default=1500)
    ap.add_argument("--json", default=None, help="write the full report here")
    args = ap.parse_args(argv)

    report = run(args.bars)
    st = report["structural"]
    print("structural — generate_trades()")
    print("  entry_signal written at lines   : {}".format(
        st["entry_signal_write_lines"]))
    print("  slope flags read at lines       : {}".format(st["slope_flag_read_lines"]))
    print("  regime_kelly_mult written at    : {}".format(
        st["regime_kelly_mult_write_lines"]))
    print("  every slope read is after the last entry write: {}".format(
        st["all_slope_reads_after_last_entry_write"]))
    print("\nrunner.py call (line {}) passes: {}".format(
        report["runner_call"]["line"], ", ".join(report["runner_call"]["keywords"])))

    print("\n{:10s} {:6s} {:>6s} {:>6s} {:>8s} {:>9s} {:>6s} {:>7s} {:>6s} {:>7s} {:>6s}"
          .format("panel", "tf", "hashes", "kelly", "gate_on", "gate_off", "kept",
                  "SB_bars", "cands", "blk_run", "blk_doc"))
    for p in report["panels"]:
        rf, sg = p["regime_filter"], p["soft_50ma_gate"]
        print("{:10s} {:6s} {:>6d} {:>6d} {:>8d} {:>9d} {:>5.1%} {:>6.1%} {:>6d} {:>7d} "
              "{:>6d}".format(
                  p["panel"], p["timeframe"], p["distinct_entry_hashes"],
                  p["distinct_kelly_hashes"], rf["on_default_what_runner_gets"],
                  rf["off_what_config_says"], rf["retained_fraction"] or 0.0,
                  sg["strong_bull_bar_fraction"], sg["long_candidates_gate_disabled"],
                  sg["blocked_taken_branch"], sg["blocked_else_branch"]))

    print("\nF194's own volatility (sigma=1.1%/bar, {} hourly bars)".format(HIGHVOL_BARS))
    print("{:10s} {:>8s} {:>7s} {:>9s} {:>9s} {:>8s}".format(
        "panel", "SB_bars", "cands", "blk_run", "blk_doc", "ratio"))
    for p in report["highvol_panels"]:
        sg = p["soft_50ma_gate"]
        c = sg["long_candidates_gate_disabled"]
        run_r = sg["blocked_taken_branch"] / c
        doc_r = sg["blocked_else_branch"] / c
        print("{:10s} {:>7.1%} {:>7d} {:>8.1%} {:>9.1%} {:>7.1f}x".format(
            p["panel"], sg["strong_bull_bar_fraction"], c, run_r, doc_r,
            doc_r / run_r if run_r else float("inf")))

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, sort_keys=True)
            fh.write("\n")
        print("\nwrote {}".format(args.json))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

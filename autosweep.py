#!/usr/bin/env python3
"""
autosweep.py — Autonomous research pipeline for MONAD Quant.

Runs a full sweep → score → validate → refine → rank cycle for any ticker.
Uses src/research/harness.py for all backtest/validation logic.

Usage:
    python autosweep.py TQQQ                    # Full pipeline
    python autosweep.py TQQQ --quick            # Fast mode (fewer candidates)
    python autosweep.py SOXL --start 2024-06-01 # Custom date range
    python autosweep.py TQQQ --validate-only    # Skip sweep, validate existing results
    python autosweep.py TQQQ --export-ibkr-fills  # Export fill audit before sweep
"""

import argparse
import json
import sys
import os
import warnings
from datetime import datetime, timedelta

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
import pandas as pd

import config
from src.research.harness import (
    AutoSweepConfig,
    CandidateParams,
    CandidateResult,
    ValidationResult,
    setup_hourly_mode,
    set_candidate_params,
    fetch_ticker_hourly,
    run_candidate,
    extract_metrics,
    live_score,
    validate_candidate,
    save_json,
    load_sweep_results,
)


# ═══════════════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════════════
parser = argparse.ArgumentParser(
    description="MONAD Quant — Autonomous Sweep + Validate Pipeline",
)
parser.add_argument("ticker", help="Ticker symbol (e.g., TQQQ, SOXL)")
parser.add_argument("--start", default=None, help="Start date (default: 2yr ago)")
parser.add_argument("--end", default=None, help="End date (default: today)")
parser.add_argument("--quick", action="store_true",
                    help="Fast mode: coarser grid, fewer validation rounds")
parser.add_argument("--validate-only", action="store_true",
                    help="Skip sweep, validate presets from sweep_results JSON")
parser.add_argument("--validate-top", type=int, default=10,
                    help="Number of top candidates to validate (default: 10)")
parser.add_argument("--holdout-pct", type=float, default=20,
                    help="Holdout percentage (default: 20)")
parser.add_argument("--mode", default="realistic",
                    choices=["optimistic", "realistic", "harsh"])
parser.add_argument("--skip-mc", action="store_true", help="Skip Monte Carlo")
parser.add_argument("--skip-slippage", action="store_true", help="Skip slippage test")
parser.add_argument("--skip-regime", action="store_true", help="Skip regime split")
parser.add_argument("--skip-rolling", action="store_true", help="Skip rolling windows")
parser.add_argument("--mc-samples", type=int, default=500)
parser.add_argument("--rolling-windows", type=int, default=4)
parser.add_argument("--entry-start-hour", type=int, default=9)
parser.add_argument("--export-ibkr-fills", action="store_true",
                    help="Export IBKR fill audit before running")
parser.add_argument("--fill-audit-path", default="live_fill_audit.json")
parser.add_argument("--use-ibkr-fills", action="store_true",
                    help="Use IBKR fill data for slippage calibration")
args = parser.parse_args()

TICKER = args.ticker.upper()
END_DATE = args.end or datetime.now().strftime("%Y-%m-%d")
START_DATE = args.start or (datetime.now() - timedelta(days=710)).strftime("%Y-%m-%d")


# ═══════════════════════════════════════════════════════════════════════════
#  Fill audit export (optional, runs before everything else)
# ═══════════════════════════════════════════════════════════════════════════
if args.export_ibkr_fills:
    from src.research.fill_audit import export_fill_audit
    print(f"  Exporting state DB fill audit → {args.fill_audit_path}")
    export_fill_audit(output_path=args.fill_audit_path)
    print("  Done.\n")

observed_slippage_bps = None
if args.use_ibkr_fills:
    from src.research.fill_audit import read_trades as _read_fill_trades
    from src.research.fill_audit import compute_slippage_stats as _compute_slippage
    _fill_trades = _read_fill_trades(limit=200)
    if len(_fill_trades) < 20:
        print(f"  WARNING: Only {len(_fill_trades)} fill records in state.db "
              f"(need >= 20 for reliable slippage). Using default slippage.\n")
    else:
        _fill_stats = _compute_slippage(_fill_trades)
        observed_slippage_bps = _fill_stats.median_slippage_bps
        print(f"  Fill audit: {len(_fill_trades)} trades, "
              f"median slippage {observed_slippage_bps:.1f} bps\n")


# ═══════════════════════════════════════════════════════════════════════════
#  SPREAD ESTIMATION (from sweep.py)
# ═══════════════════════════════════════════════════════════════════════════
_BROKER_SPREADS = {
    "retail": {"<15": 0.02, "<50": 0.03, "<150": 0.04, "else": 0.05},
}

def _estimate_spread(price: float) -> float:
    tiers = _BROKER_SPREADS["retail"]
    if price < 15:
        return tiers["<15"]
    elif price < 50:
        return tiers["<50"]
    elif price < 150:
        return tiers["<150"]
    return tiers["else"]


# ═══════════════════════════════════════════════════════════════════════════
#  SETUP + DATA LOADING
# ═══════════════════════════════════════════════════════════════════════════
MODE_NAME = setup_hourly_mode(TICKER)

print(f"\n{'='*70}")
print(f"  MONAD QUANT — AUTOSWEEP: {TICKER}  [{args.mode.upper()}]")
print(f"  Period: {START_DATE} → {END_DATE}")
print(f"{'='*70}\n")

df_full = fetch_ticker_hourly(TICKER, START_DATE, END_DATE)
print(f"  Loaded {len(df_full)} bars\n")

if len(df_full) < 100:
    print(f"  ERROR: Only {len(df_full)} bars. Need >= 100.")
    sys.exit(1)

# Holdout split
holdout_frac = args.holdout_pct / 100.0
if holdout_frac > 0 and len(df_full) > 200:
    split_idx = int(len(df_full) * (1 - holdout_frac))
    df_train = df_full.iloc[:split_idx].copy()
    df_holdout = df_full.iloc[split_idx:].copy()
    print(f"  Train: {len(df_train)} bars | Holdout: {len(df_holdout)} bars\n")
else:
    df_train = df_full.copy()
    df_holdout = None
    print("  Holdout disabled.\n")

median_price = float(df_train["close"].median())
est_spread = _estimate_spread(median_price)
min_stop_pct = max(0.15, (5 * est_spread / median_price) * 100)

print(f"  Median price: ${median_price:.2f}")
print(f"  Est. spread:  ${est_spread:.3f}")
print(f"  Min stop:     {min_stop_pct:.2f}%\n")


# ══════════════════════════════════════════════════════════════��════════════
#  SWEEP GRIDS
# ═���═══════════════════════════════════════════════��═════════════════════════
if args.quick:
    TARGETS_PCT = [0.4, 0.6, 0.8, 1.0, 1.4, 2.0]
    STOPS_PCT   = [0.20, 0.30, 0.40, 0.50, 0.60]
    VWAP_VALUES = [0.0, 0.3, 0.5, 0.8, 1.2]
    RSI_VALUES  = [50, 65, 75, 80, 90, 100]
else:
    TARGETS_PCT = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.2, 1.4, 1.6, 2.0]
    STOPS_PCT   = [0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50, 0.60]
    VWAP_VALUES = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0, 1.2]
    RSI_VALUES  = [42, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100]


def _make_params(target_pct, stop_pct, rsi=80, vwap=0.3) -> CandidateParams:
    return CandidateParams(
        ticker=TICKER,
        target=target_pct / 100,
        stop=stop_pct / 100,
        rsi=rsi,
        vwap=vwap,
        entry_start_hour=args.entry_start_hour,
        backtest_mode=args.mode,
    )


def _score_result(r: dict, params: CandidateParams,
                  train_metrics: CandidateResult = None) -> tuple:
    """Run extract_metrics + live_score on a raw result. Returns (metrics, score)."""
    m = extract_metrics(r, params)
    if m is None:
        return None, -9999
    s = live_score(m, median_price, est_spread, train_metrics)
    m.score = s
    return m, s


# ═══��══════════════════════════════════════════════════════════════════���════
#  STAGE 1: COARSE SWEEP (target/stop → VWAP → RSI)
# ══════════════════════��════════════════════════════════════��═══════════════
all_candidates: list[tuple[CandidateParams, CandidateResult, float]] = []
best_score = -9999
best_params = _make_params(1.0, 0.5)


def _sweep_and_collect(params: CandidateParams, label: str = "") -> float:
    """Run one candidate on train data, collect if valid. Returns score."""
    global best_score, best_params
    r = run_candidate(df_train, params, MODE_NAME)
    if r is None or "error" in (r or {}) or r.get("total_trades", 0) == 0:
        return -9999
    m, s = _score_result(r, params)
    if m is not None:
        all_candidates.append((params, m, s))
        if s > best_score:
            best_score = s
            best_params = params
    return s


if not args.validate_only:
    print("=" * 70)
    print(f"  STAGE 1: Coarse Sweep")
    print("=" * 70)

    # 1a: Target/Stop at 2:1 R:R
    print(f"\n  1a: Target/Stop (2:1 R:R)")
    for t_pct in TARGETS_PCT:
        s_pct = t_pct / 2
        if s_pct < min_stop_pct:
            continue
        p = _make_params(t_pct, s_pct)
        s = _sweep_and_collect(p)
        print(f"    target={t_pct:.1f}% stop={s_pct:.2f}% → score={s:.1f}")

    # 1b: R:R variations at best target
    best_t = best_params.target * 100
    print(f"\n  1b: R:R variations at target={best_t:.1f}%")
    for s_pct in STOPS_PCT:
        if s_pct >= best_t or s_pct < min_stop_pct:
            continue
        p = _make_params(best_t, s_pct)
        s = _sweep_and_collect(p)
        rr = best_t / s_pct
        print(f"    R:R={rr:.1f}:1 stop={s_pct:.2f}% → score={s:.1f}")

    # 1c: VWAP threshold
    print(f"\n  1c: VWAP threshold")
    bt, bs = best_params.target * 100, best_params.stop * 100
    for v in VWAP_VALUES:
        p = _make_params(bt, bs, vwap=v)
        s = _sweep_and_collect(p)
        print(f"    VWAP={v:.1f} → score={s:.1f}")

    # 1d: RSI oversold
    print(f"\n  1d: RSI threshold")
    bv = best_params.vwap
    for rsi in RSI_VALUES:
        p = _make_params(bt, bs, rsi=rsi, vwap=bv)
        s = _sweep_and_collect(p)
        print(f"    RSI={rsi} → score={s:.1f}")

    print(f"\n  Stage 1 best: target={best_params.target*100:.2f}% "
          f"stop={best_params.stop*100:.2f}% "
          f"RSI={best_params.rsi} VWAP={best_params.vwap} "
          f"→ score={best_score:.1f}")
    print(f"  Total candidates: {len(all_candidates)}")

    # ════════════���═══════════════════════════��══════════════════════════════
    #  STAGE 2: REFINEMENT (fine-tune around best)
    # ════════════════��══════════════════════════════════════════════════════
    print(f"\n{'='*70}")
    print(f"  STAGE 2: Refinement around best")
    print(f"{'='*70}")

    bt_pct = best_params.target * 100
    bs_pct = best_params.stop * 100
    br = best_params.rsi
    bv = best_params.vwap

    # 2a: Fine-tune target
    print(f"\n  2a: Target fine-tune")
    for mult in [0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.4]:
        t = round(bt_pct * mult, 2)
        if t <= 0:
            continue
        p = _make_params(t, bs_pct, rsi=br, vwap=bv)
        s = _sweep_and_collect(p)
        print(f"    target={t:.2f}% → score={s:.1f}")

    # 2b: Fine-tune stop
    bt_pct = best_params.target * 100
    print(f"\n  2b: Stop fine-tune")
    for mult in [0.5, 0.7, 0.85, 1.0, 1.15, 1.3, 1.5]:
        s_pct = round(bs_pct * mult, 3)
        if s_pct <= 0 or s_pct / 100 >= best_params.target or s_pct < min_stop_pct:
            continue
        p = _make_params(bt_pct, s_pct, rsi=br, vwap=bv)
        s = _sweep_and_collect(p)
        print(f"    stop={s_pct:.3f}% → score={s:.1f}")

    # 2c: Fine-tune RSI
    bt_pct = best_params.target * 100
    bs_pct = best_params.stop * 100
    print(f"\n  2c: RSI fine-tune around {br}")
    rsi_range = sorted(set([
        max(40, br - 10), max(40, br - 5), max(40, br - 3),
        br, min(100, br + 3), min(100, br + 5), min(100, br + 10),
    ]))
    for rsi in rsi_range:
        p = _make_params(bt_pct, bs_pct, rsi=rsi, vwap=bv)
        s = _sweep_and_collect(p)
        print(f"    RSI={rsi} → score={s:.1f}")

    # 2d: MAX_TRADE_BARS
    bt_pct = best_params.target * 100
    bs_pct = best_params.stop * 100
    br = best_params.rsi
    bv = best_params.vwap
    print(f"\n  2d: MAX_TRADE_BARS")
    best_mtb = 20
    best_mtb_score = best_score
    for mtb in [8, 10, 12, 15, 20]:
        p = _make_params(bt_pct, bs_pct, rsi=br, vwap=bv)
        p.max_trade_bars = mtb
        s = _sweep_and_collect(p)
        print(f"    MTB={mtb} → score={s:.1f}")
        if s > best_mtb_score:
            best_mtb_score = s
            best_mtb = mtb

    print(f"\n  Stage 2 best MTB: {best_mtb}")
    print(f"  Total candidates: {len(all_candidates)}")


# ═══════��═══════════════════════════════════════════════════════════════════
#  STAGE 3: RANK + HOLDOUT EVALUATION
# ═══════════════════���═══════════════════════════════════════════════════════
print(f"\n{'='*70}")
print(f"  STAGE 3: Rank + Holdout Evaluation")
print(f"{'='*70}")

if args.validate_only:
    sweep_data = load_sweep_results(TICKER)
    if sweep_data is None:
        print(f"  No sweep_results_{TICKER}.json found. Run without --validate-only first.")
        sys.exit(1)
    for label, preset in sweep_data.get("presets", {}).items():
        p = preset.get("params", {})
        params = CandidateParams(
            ticker=TICKER,
            target=p.get("target_gain_pct", 0.01),
            stop=p.get("stop_loss_pct", 0.005),
            rsi=int(p.get("rsi_oversold", 80)),
            vwap=p.get("vwap_zscore_thresh", 0.5),
            max_trade_bars=int(p.get("max_trade_bars", 20)),
            entry_start_hour=args.entry_start_hour,
            backtest_mode=args.mode,
        )
        r = run_candidate(df_train, params, MODE_NAME)
        if r and "error" not in r:
            m, s = _score_result(r, params)
            if m is not None:
                all_candidates.append((params, m, s))
    print(f"  Loaded {len(all_candidates)} candidates from sweep_results_{TICKER}.json")

# Sort by score, take top N
all_candidates.sort(key=lambda x: x[2], reverse=True)
top_n = args.validate_top
top_candidates = all_candidates[:top_n]

print(f"\n  Top {len(top_candidates)} candidates by train score:")
for i, (p, m, s) in enumerate(top_candidates):
    print(f"    #{i+1}: target={p.target*100:.2f}% stop={p.stop*100:.3f}% "
          f"RSI={p.rsi} VWAP={p.vwap} MTB={p.max_trade_bars} "
          f"| ret={m.total_return_pct:.1f}% Sharpe={m.sharpe_ratio:.1f} "
          f"WR={m.win_rate_pct:.1f}% score={s:.1f}")

# Holdout evaluation
if df_holdout is not None and len(top_candidates) > 0:
    print(f"\n  Evaluating top {len(top_candidates)} on holdout ({len(df_holdout)} bars)...")
    holdout_scores = []
    for p, train_m, train_s in top_candidates:
        r = run_candidate(df_holdout, p, MODE_NAME)
        if r and "error" not in r:
            m, s = _score_result(r, p, train_metrics=train_m)
            holdout_scores.append((p, train_m, train_s, m, s))
            print(f"    target={p.target*100:.2f}% stop={p.stop*100:.3f}% "
                  f"→ holdout ret={m.total_return_pct:.1f}% score={s:.1f}")
        else:
            holdout_scores.append((p, train_m, train_s, None, -9999))
            print(f"    target={p.target*100:.2f}% stop={p.stop*100:.3f}% → NO TRADES")

    holdout_scores.sort(key=lambda x: x[4], reverse=True)
    top_candidates = [(p, tm, ts) for p, tm, ts, _, _ in holdout_scores[:top_n]]


# ═══════════════════════════════════════════════════════════════════════════
#  STAGE 4: VALIDATE TOP CANDIDATES
# ═══════════════════════════════════════════════════════════════════════════
print(f"\n{'='*70}")
print(f"  STAGE 4: Validation ({len(top_candidates)} candidates)")
print(f"{'='*70}")

sweep_cfg = AutoSweepConfig(
    validate_top=args.validate_top,
    mc_samples=args.mc_samples,
    rolling_windows=args.rolling_windows,
    holdout_pct=args.holdout_pct,
    backtest_mode=args.mode,
    skip_mc=args.skip_mc,
    skip_slippage=args.skip_slippage,
    skip_regime=args.skip_regime,
    skip_rolling=args.skip_rolling,
)

validated: list[tuple[CandidateParams, CandidateResult, float, ValidationResult]] = []

for i, (p, m, s) in enumerate(top_candidates):
    print(f"\n  Validating #{i+1}: target={p.target*100:.2f}% stop={p.stop*100:.3f}% "
          f"RSI={p.rsi} VWAP={p.vwap}")
    vr = validate_candidate(df_full, p, MODE_NAME, sweep_cfg)
    validated.append((p, m, s, vr))
    print(f"    → {vr.confidence} (score {vr.confidence_score}/100)")
    for w in vr.warnings[:3]:
        print(f"      {w}")


# ═══════════════════════════════════════════════════════════════════════════
#  STAGE 5: FINAL RANKINGS + JSON OUTPUT
# ═══════════════════════════════════════════════════════════════════════════
print(f"\n{'='*70}")
print(f"  STAGE 5: Final Rankings")
print(f"{'='*70}")

# Sort by: confidence_score first, then train score as tiebreaker
validated.sort(key=lambda x: (x[3].confidence_score, x[2]), reverse=True)

print(f"\n  {'Rank':<5} {'Target':>7} {'Stop':>7} {'RSI':>4} {'VWAP':>5} "
      f"{'Ret%':>7} {'Sharpe':>7} {'WR%':>6} {'Score':>6} {'Conf':>8}")
print(f"  {'─'*5} {'─'*7} {'─'*7} {'─'*4} {'─'*5} "
      f"{'─'*7} {'─'*7} {'─'*6} {'─'*6} {'─'*8}")

for rank, (p, m, s, vr) in enumerate(validated, 1):
    print(f"  {rank:<5} {p.target*100:>6.2f}% {p.stop*100:>6.3f}% {p.rsi:>4} {p.vwap:>5.1f} "
          f"{m.total_return_pct:>+6.1f}% {m.sharpe_ratio:>6.1f} {m.win_rate_pct:>5.1f}% "
          f"{s:>5.0f} {vr.confidence:>8}")

# Build JSON output
output = {
    "ticker": TICKER,
    "period": f"{START_DATE} → {END_DATE}",
    "bars": len(df_full),
    "train_bars": len(df_train),
    "holdout_bars": len(df_holdout) if df_holdout is not None else 0,
    "backtest_mode": args.mode,
    "quick_mode": args.quick,
    "median_price": median_price,
    "est_spread": est_spread,
    "min_stop_pct": min_stop_pct,
    "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    "total_candidates_swept": len(all_candidates),
    "observed_slippage_bps": observed_slippage_bps,
    "rankings": [],
}

for rank, (p, m, s, vr) in enumerate(validated, 1):
    entry = {
        "rank": rank,
        "params": p.to_dict(),
        "metrics": m.to_dict(),
        "train_score": round(s, 2),
        "validation": {
            "confidence": vr.confidence,
            "confidence_score": vr.confidence_score,
            "warnings": vr.warnings,
        },
    }
    if vr.rolling:
        entry["validation"]["rolling"] = vr.rolling
    if vr.monte_carlo:
        entry["validation"]["monte_carlo"] = vr.monte_carlo
    if vr.drawdown_profile:
        entry["validation"]["drawdown_profile"] = vr.drawdown_profile
    if vr.slippage_sensitivity:
        entry["validation"]["slippage_sensitivity"] = vr.slippage_sensitivity
    output["rankings"].append(entry)

# Best candidate summary
if validated:
    best_p, best_m, best_s, best_vr = validated[0]
    output["best"] = {
        "params": best_p.to_dict(),
        "metrics": best_m.to_dict(),
        "train_score": round(best_s, 2),
        "confidence": best_vr.confidence,
        "confidence_score": best_vr.confidence_score,
    }

outfile = f"autosweep_results_{TICKER}.json"
save_json(outfile, output)
print(f"\n  Results saved → {outfile}")

if validated:
    bp = validated[0]
    print(f"\n  RECOMMENDED: target={bp[0].target*100:.2f}% stop={bp[0].stop*100:.3f}% "
          f"RSI={bp[0].rsi} VWAP={bp[0].vwap}")
    print(f"  Confidence: {bp[3].confidence} ({bp[3].confidence_score}/100)")

print()

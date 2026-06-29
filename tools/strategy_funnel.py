#!/usr/bin/env python3
"""
MONAD Quant — offline strategy promotion funnel (the brutal gate before paper).

Every candidate (a ticker + a parameter set) must *prove itself* before it earns
even a SHADOW (paper-watch) verdict. This tool runs the candidate through the
project's existing, vetted machinery — realistic & harsh backtests, the leak-free
walk-forward (``tools/walkforward_eval.walkforward``), 1×/2×/3× cost stress,
parameter-stability perturbation, a buy & hold benchmark, and bootstrap bands —
then hands the resulting numbers to the PURE decision logic in
``src/optimization/funnel.py`` for a PASS / SHADOW / REJECT verdict with reasons.

It writes one survivor/rejection card (JSON + Markdown) per candidate.

Honesty stance (the project's hard-won lesson, RESEARCH_WEB D6/F13): a backtest
looking good is NOT evidence a strategy is tradable. The default thresholds are
skeptical and the funnel REJECTs on missing evidence. A SHADOW or PASS verdict is
a recommendation to *watch*, never an instruction to arm capital — this tool never
touches ``config.ACTIVE_MODE``, the live trader, broker code, or any runtime state.

Usage:
    venv/bin/python tools/strategy_funnel.py --tickers QQQ TQQQ SOXL GDXU --mode realistic
    venv/bin/python tools/strategy_funnel.py --tickers TQQQ --folds 4 --out data/funnel_runs
    venv/bin/python tools/strategy_funnel.py --tickers QQQ --quick      # fewer runs, for a fast look

OFFLINE ONLY: reads cached OHLCV from data/cache/<TICKER>_1h.csv (no network). A
ticker with no cached data is REJECTed with that reason (e.g. GDXU is uncached).
"""
from __future__ import annotations

import argparse
import contextlib
import io
import os
import sys
from datetime import datetime

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # for sibling tools

import config
from src.backtest.runner import run_backtest
from src.backtest import metrics
from src.backtest import uncertainty as unc
from src.optimization.sweep_costs import estimate_spread, round_trip_cost_pct
from src.optimization import funnel as F
from walkforward_eval import walkforward as leakfree_walkforward

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "cache")
DEFAULT_OUT = os.path.join(os.path.dirname(__file__), "..", "data", "funnel_runs")
HARSH_SLIPPAGE_PCT = 0.0005  # the BACKTEST_MODES["harsh"] preset (5 bps)
SIZING_PCT = 0.10            # live-representative fixed sizing (matches walkforward_eval)
_DD_FLOOR = 1e-6            # avoid div-by-zero in Calmar when drawdown is ~0

# The five tunable knobs, and how each is perturbed for the stability gate.
STABILITY_GRID = {
    "target_gain_pct":    ("mult", (0.8, 0.9, 1.1, 1.2)),
    "stop_loss_pct":      ("mult", (0.8, 0.9, 1.1, 1.2)),
    "rsi_oversold":       ("add_int", (-10, -5, 5, 10)),
    "vwap_zscore_thresh": ("add", (-0.2, -0.1, 0.1, 0.2)),
    "max_trade_bars":     ("add_int", (-4, -2, 2, 4)),
}


# ── Config injection (mutates the global config module; mirrors the proven
#    walkforward_eval._configure pattern but covers all 5 knobs) ──────────────
_CONFIG_SCALARS = ("ACTIVE_MODE", "MAX_TRADE_BARS", "PLOT_RESULTS", "VERBOSE_SIGNALS",
                   "POSITION_SIZING_MODE", "FIXED_POSITION_PCT", "USE_ADAPTIVE_KELLY")


def _snapshot_config() -> dict:
    """Shallow snapshot of the config state this tool mutates, for restore-on-exit."""
    snap = {k: getattr(config, k, None) for k in _CONFIG_SCALARS}
    snap["ASSETS"] = dict(getattr(config, "ASSETS", {}))
    snap["_MODE_TO_ASSET"] = dict(getattr(config, "_MODE_TO_ASSET", {}))
    return snap


def _restore_config(snap: dict) -> None:
    for k in _CONFIG_SCALARS:
        setattr(config, k, snap[k])
    config.ASSETS = snap["ASSETS"]
    config._MODE_TO_ASSET = snap["_MODE_TO_ASSET"]


def _apply_config(ticker: str, params: dict) -> str:
    """Inject the per-ticker hourly config the engine reads. Returns the mode name.

    The engine's hourly path gates entries on config.<PARAM>_<MODE> globals (the
    daily signal_overrides dict is ignored on hourly), so RSI/VWAP must be set as
    module attributes; max_trade_bars is the global config.MAX_TRADE_BARS.
    """
    mode = f"{ticker.upper()}_HOURLY"
    # Preserve existing per-mode feature params if present, else sensible hourly defaults.
    feat_defaults = {"RSI_PERIOD": 7, "RSI_OVERBOUGHT": 62, "MACD_FAST": 6, "MACD_SLOW": 13,
                     "MACD_SIGNAL": 4, "VWAP_WINDOW": 10, "BB_WINDOW": 14}
    for k, v in feat_defaults.items():
        setattr(config, f"{k}_{mode}", getattr(config, f"{k}_{mode}", v))
    setattr(config, f"RSI_OVERSOLD_{mode}", params["rsi_oversold"])
    setattr(config, f"VWAP_ZSCORE_THRESH_{mode}", params["vwap_zscore_thresh"])
    config.MAX_TRADE_BARS = int(params["max_trade_bars"])
    config.ASSETS[mode] = {
        "type": f"etf_hourly_{ticker.lower()}",
        "target_gain_pct": params["target_gain_pct"],
        "stop_loss_pct": params["stop_loss_pct"],
        "require_signals": 1,
        "rsi_oversold": params["rsi_oversold"],
        "rsi_overbought": getattr(config, f"RSI_OVERBOUGHT_{mode}"),
        "vwap_zscore_thresh": params["vwap_zscore_thresh"],
    }
    config._MODE_TO_ASSET[mode] = mode
    config.ACTIVE_MODE = mode
    config.PLOT_RESULTS = False
    config.VERBOSE_SIGNALS = False
    config.POSITION_SIZING_MODE = "fixed"
    config.FIXED_POSITION_PCT = SIZING_PCT
    config.USE_ADAPTIVE_KELLY = False
    return mode


def _run(df: pd.DataFrame, ticker: str, params: dict, *, backtest_mode: str,
         slippage_pct) -> dict | None:
    """One offline backtest. Re-applies config every call (global state leaks
    between runs), silences stdout, never plots. Returns None on zero trades."""
    _apply_config(ticker, params)
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            r = run_backtest(df=df.copy(), target_gain_pct=params["target_gain_pct"],
                             stop_loss_pct=params["stop_loss_pct"], require_signals=1,
                             timeframe="hourly", plot=False, backtest_mode=backtest_mode,
                             slippage_pct=slippage_pct)
        except Exception:
            return None
    return r or None  # run_backtest returns {} on zero trades


# ── Candidate parameter resolution ──────────────────────────────────────────
def _load_sweep_best(ticker: str) -> dict | None:
    """Best swept params for a ticker (sweep_results_<T>.json), if present."""
    import json
    path = os.path.join(os.path.dirname(__file__), "..", f"sweep_results_{ticker.upper()}.json")
    if not os.path.exists(path):
        return None
    try:
        data = json.load(open(path))
        p = data["presets"]["best_overall"]["params"]
        return {
            "target_gain_pct": float(p["target_gain_pct"]),
            "stop_loss_pct": float(p["stop_loss_pct"]),
            "rsi_oversold": float(p["rsi_oversold"]),
            "vwap_zscore_thresh": float(p.get("vwap_zscore_thresh", 0.3)),
            "max_trade_bars": int(p.get("max_trade_bars", getattr(config, "MAX_TRADE_BARS", 8))),
        }
    except Exception:
        return None


def _candidate_params(ticker: str) -> dict:
    """The centre candidate: swept best if available, else the mode's config defaults."""
    best = _load_sweep_best(ticker)
    if best:
        return best
    mode = f"{ticker.upper()}_HOURLY"
    return {
        "target_gain_pct": float(getattr(config, f"TARGET_GAIN_PCT_{mode}", 0.010)),
        "stop_loss_pct": float(getattr(config, f"STOP_LOSS_PCT_{mode}", 0.005)),
        "rsi_oversold": float(getattr(config, f"RSI_OVERSOLD_{mode}", 70)),
        "vwap_zscore_thresh": float(getattr(config, f"VWAP_ZSCORE_THRESH_{mode}", 0.3)),
        "max_trade_bars": int(getattr(config, "MAX_TRADE_BARS", 8)),
    }


# ── Metric helpers ──────────────────────────────────────────────────────────
def _years(df: pd.DataFrame) -> float:
    n_days = (df.index[-1] - df.index[0]).days
    return n_days / 365.25 if n_days > 0 else 1.0


def _calmar(total_return: float, max_dd: float, years: float):
    """Annualized return / |max drawdown| — the risk-adjusted benchmark score.
    Floors |dd| so a ~zero-drawdown path yields a large finite number, not inf."""
    if not (isinstance(total_return, (int, float)) and isinstance(max_dd, (int, float))):
        return None
    ann = metrics.annualize_return(total_return, years)
    return ann / max(abs(max_dd), _DD_FLOOR)


def _benchmark_calmar(df: pd.DataFrame, initial: float = 100_000.0):
    """Buy & hold of the same instrument over the same span → (calmar, total, max_dd)."""
    close = df["close"]
    total = metrics.buy_hold_return(close)
    years = _years(df)
    bh_equity = (initial * (close / close.iloc[0])).reset_index(drop=True)
    max_dd = metrics.max_drawdown(bh_equity)
    return _calmar(total, max_dd, years), total, max_dd


def _perturb(center: dict) -> dict:
    """Build the neighbour value lists for each knob (deduped, centre removed)."""
    out = {}
    for knob, (kind, deltas) in STABILITY_GRID.items():
        c = center[knob]
        vals = []
        for d in deltas:
            if kind == "mult":
                v = round(c * d, 6)
            elif kind == "add":
                v = round(max(0.0, c + d), 4)
            else:  # add_int
                lo = 1 if knob in ("rsi_oversold", "max_trade_bars") else 0
                v = max(lo, int(round(c + d)))
                if knob == "rsi_oversold":
                    v = min(99, v)
            if v != c and v not in vals:
                vals.append(v)
        out[knob] = vals
    return out


# ── Per-candidate evaluation ────────────────────────────────────────────────
def evaluate_ticker(ticker: str, *, base_mode: str, n_folds: int, quick: bool,
                    thresholds: F.FunnelThresholds, generated_at: str) -> dict:
    """Run the full funnel for one ticker; return its survivor/rejection card dict."""
    path = os.path.join(CACHE_DIR, f"{ticker.upper()}_1h.csv")
    params = _candidate_params(ticker)
    family = "long_only_rsi_vwap_mr_hourly"
    sid = (f"{ticker.upper()}_HOURLY_rsi{params['rsi_oversold']:g}"
           f"_t{params['target_gain_pct']:g}_s{params['stop_loss_pct']:g}")

    # ── No offline data → honest REJECT, no backtests run (e.g. GDXU) ──
    if not os.path.exists(path):
        m = F.CandidateMetrics()
        verdict = F.FunnelVerdict(
            F.REJECT, [f"no cached offline data at data/cache/{ticker.upper()}_1h.csv "
                       f"— cannot validate without data"], [])
        return F.build_survivor_card(
            strategy_id=sid, ticker=ticker.upper(), strategy_family=family, params=params,
            train_period="n/a", oos_period="n/a",
            cost_assumptions={"note": "no data"}, metrics=m, verdict=verdict,
            generated_at=generated_at, mode=base_mode,
            extra={"data_status": "missing"})

    df = pd.read_csv(path, index_col=0, parse_dates=True)
    years = _years(df)
    base_cost = round_trip_cost_pct(estimate_spread(float(df["close"].median()), None),
                                    float(df["close"].median()))

    # ── Realistic full-sample run (instrument-derived 1× cost) ──
    res = _run(df, ticker, params, backtest_mode="realistic", slippage_pct=base_cost)
    realistic_sharpe = res["sharpe_ratio"] if res else None
    realistic_return = res["total_return"] if res else None
    total_trades = res["total_trades"] if res else 0
    trades_per_year = res["trades_per_year"] if res else None

    # ── Harsh full-sample run (5 bps preset + pessimistic ambiguity) ──
    res_h = _run(df, ticker, params, backtest_mode="harsh", slippage_pct=None)
    harsh_sharpe = res_h["sharpe_ratio"] if res_h else None
    harsh_return = res_h["total_return"] if res_h else None

    # ── Cost stress: realistic ambiguity, slippage = k × instrument cost ──
    cost_ret, cost_sh = {}, {}
    for k in (1, 2, 3):
        rk = res if k == 1 else _run(df, ticker, params, backtest_mode="realistic",
                                     slippage_pct=base_cost * k)
        cost_ret[k] = float(rk["total_return"]) if rk else 0.0
        cost_sh[k] = float(rk["sharpe_ratio"]) if rk else 0.0

    # ── Parameter stability: vary each knob, realistic mode, collect Sharpe ──
    stability = {}
    if not quick and res is not None:
        center_sh = realistic_sharpe
        for knob, vals in _perturb(params).items():
            neigh = []
            for v in vals:
                p2 = dict(params)
                p2[knob] = v
                rp = _run(df, ticker, p2, backtest_mode="realistic", slippage_pct=base_cost)
                neigh.append(float(rp["sharpe_ratio"]) if rp else 0.0)  # no trades ⇒ edge gone
            stability[knob] = {"center": float(center_sh) if center_sh is not None else None,
                               "neighbors": neigh, "values": vals}

    # ── Leak-free walk-forward (the canonical ctx-preferred OOS path) ──
    oos_sharpe = oos_return = oos_dd = oos_wr = None
    trades_per_window = None
    oos_period = "n/a"
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            wf, picks = leakfree_walkforward(df.copy(), ticker.upper(),
                                             objective="ev", n_folds=n_folds)
        trades_per_window = [p.get("oos_trades", 0) for p in picks]
        if "error" not in wf:
            oos_sharpe = wf["sharpe"]
            oos_return = wf["total_return_pct"] / 100.0
            oos_dd = wf["max_drawdown_pct"] / 100.0
            oos_wr = wf["win_rate_pct"] / 100.0
            oos_period = (f"leak-free walk-forward, {n_folds} expanding folds, "
                          f"~{wf.get('oos_span_months')}mo OOS, {wf.get('oos_trades')} OOS trades")
    except Exception as exc:
        oos_period = f"walk-forward failed: {exc}"

    # ── Uncertainty bands on the realistic full-sample per-trade returns ──
    #    (in-sample bootstrap: tests resampling robustness + P(loss); the leak-free
    #    OOS check above is the separate out-of-sample lens.)
    u_point = u_lo = u_hi = prob_below = None
    if res is not None and len(res.get("trade_returns", [])) > 0:
        rets = np.asarray(res["trade_returns"], dtype=float)
        tpy = float(trades_per_year) if trades_per_year else float(len(rets))
        sb = unc.sharpe_band(rets, tpy, seed=0)
        mc = unc.montecarlo_equity(SIZING_PCT * rets, seed=0)  # reflect 10% sizing
        u_point, u_lo, u_hi = sb.point, sb.lo, sb.hi
        prob_below = mc.prob_below_initial

    # ── Benchmark (buy & hold, Calmar over the full span) ──
    bench_calmar, bench_total, bench_dd = _benchmark_calmar(df)
    strat_calmar = _calmar(realistic_return, res["max_drawdown"], years) if res else None

    m = F.CandidateMetrics(
        total_trades=total_trades,
        trades_per_window=trades_per_window,
        oos_sharpe=oos_sharpe, oos_total_return=oos_return,
        oos_max_drawdown=oos_dd, oos_win_rate=oos_wr,
        realistic_sharpe=realistic_sharpe, realistic_total_return=realistic_return,
        harsh_sharpe=harsh_sharpe, harsh_total_return=harsh_return,
        cost_stress_return=cost_ret, cost_stress_sharpe=cost_sh,
        stability=stability or None,
        benchmark_metric="calmar",
        benchmark_score=bench_calmar, strategy_benchmark_score=strat_calmar,
        benchmark_total_return=bench_total, strategy_return_vs_benchmark=realistic_return,
        benchmark_max_drawdown=bench_dd,
        strategy_maxdd_vs_benchmark=(res["max_drawdown"] if res else None),
        uncertainty_sharpe_point=u_point, uncertainty_sharpe_lo=u_lo,
        uncertainty_sharpe_hi=u_hi, prob_below_initial=prob_below,
    )
    verdict = F.evaluate_candidate(m, thresholds)

    cost_assumptions = {
        "sizing": f"fixed_{SIZING_PCT:.0%}",
        "base_round_trip_cost_pct": round(base_cost, 6),
        "realistic_slippage_pct": round(base_cost, 6),
        "harsh_slippage_pct": HARSH_SLIPPAGE_PCT,
        "cost_stress_multiples": [1, 2, 3],
        "median_price": round(float(df["close"].median()), 2),
    }
    return F.build_survivor_card(
        strategy_id=sid, ticker=ticker.upper(), strategy_family=family, params=params,
        train_period=f"{df.index[0].date()} → {df.index[-1].date()} (full sample, in-sample)",
        oos_period=oos_period, cost_assumptions=cost_assumptions,
        metrics=m, verdict=verdict, generated_at=generated_at, mode=base_mode,
        extra={"trades_per_year": trades_per_year,
               "data_span_years": round(years, 2),
               "uncertainty_basis": "realistic_full_sample_per_trade_returns"})


# ── Output ──────────────────────────────────────────────────────────────────
def _write_cards(cards: list, out_dir: str, stamp: str) -> list:
    os.makedirs(out_dir, exist_ok=True)
    written = []
    for c in cards:
        base = os.path.join(out_dir, f"{c['ticker']}_{stamp}")
        with open(base + ".json", "w") as fh:
            fh.write(F.card_to_json(c))
        with open(base + ".md", "w") as fh:
            fh.write(F.card_to_markdown(c))
        written += [base + ".json", base + ".md"]
    # Run-level summary.
    summary_lines = [f"# Strategy funnel run — {stamp}", "",
                     "| Ticker | Verdict | OOS Sharpe | Realistic Sharpe | Trades | Top reason |",
                     "|---|---|---|---|---|---|"]
    for c in cards:
        mtr = c.get("metrics", {})
        reason = (c.get("reasons") or [""])[0]
        summary_lines.append(
            f"| {c['ticker']} | {c['verdict']} | {mtr.get('oos_sharpe')} | "
            f"{mtr.get('realistic_sharpe')} | {mtr.get('total_trades')} | {reason[:70]} |")
    summary_lines += ["", "_SHADOW = replay/paper-watch only (never auto-armed). "
                      "PASS still requires human review before any capital._"]
    spath = os.path.join(out_dir, f"summary_{stamp}.md")
    with open(spath, "w") as fh:
        fh.write("\n".join(summary_lines) + "\n")
    written.append(spath)
    return written


def _print_console(cards: list) -> None:
    badge = {"PASS": "PASS  ", "SHADOW": "SHADOW", "REJECT": "REJECT"}
    print("\n" + "=" * 72)
    print("  MONAD STRATEGY PROMOTION FUNNEL — offline, skeptical, never auto-arms")
    print("=" * 72)
    for c in cards:
        mtr = c.get("metrics", {})
        print(f"\n[{badge.get(c['verdict'], c['verdict'])}] {c['ticker']}  "
              f"({c.get('strategy_family')})")
        print(f"    OOS Sharpe={mtr.get('oos_sharpe')}  realistic Sharpe={mtr.get('realistic_sharpe')}  "
              f"harsh Sharpe={mtr.get('harsh_sharpe')}  trades={mtr.get('total_trades')}")
        for r in c.get("reasons", [])[:4]:
            print(f"      - {r}")
    n = {v: sum(1 for c in cards if c["verdict"] == v) for v in ("PASS", "SHADOW", "REJECT")}
    print("\n" + "-" * 72)
    print(f"  {n['PASS']} PASS   {n['SHADOW']} SHADOW   {n['REJECT']} REJECT")
    print("  Reminder: SHADOW/PASS = watch only. The funnel never arms live capital.")
    print("-" * 72)


def build_thresholds(args) -> F.FunnelThresholds:
    return F.FunnelThresholds(
        min_total_trades=args.min_trades,
        min_trades_per_window=args.min_trades_per_window,
        min_oos_sharpe=args.min_oos_sharpe,
        min_realistic_sharpe=args.min_realistic_sharpe,
    )


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tickers", nargs="+", required=True, help="e.g. QQQ TQQQ SOXL GDXU")
    ap.add_argument("--mode", default="realistic", choices=["realistic", "harsh"],
                    help="primary cost mode label for the card (gates always run both)")
    ap.add_argument("--folds", type=int, default=4, help="leak-free walk-forward OOS folds")
    ap.add_argument("--quick", action="store_true",
                    help="skip the parameter-stability perturbation loop (faster)")
    ap.add_argument("--out", default=DEFAULT_OUT, help="output dir for survivor cards")
    ap.add_argument("--min-trades", type=int, default=30)
    ap.add_argument("--min-trades-per-window", type=int, default=5)
    ap.add_argument("--min-oos-sharpe", type=float, default=0.5)
    ap.add_argument("--min-realistic-sharpe", type=float, default=0.5)
    args = ap.parse_args(argv)

    thresholds = build_thresholds(args)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    generated_at = datetime.now().isoformat(timespec="seconds")

    snap = _snapshot_config()
    cards = []
    try:
        for tk in args.tickers:
            print(f"  evaluating {tk.upper()} ...", flush=True)
            cards.append(evaluate_ticker(
                tk, base_mode=args.mode, n_folds=args.folds, quick=args.quick,
                thresholds=thresholds, generated_at=generated_at))
    finally:
        _restore_config(snap)

    written = _write_cards(cards, args.out, stamp)
    _print_console(cards)
    print(f"\n  cards written under {os.path.normpath(args.out)}/ ({len(written)} files)")
    return cards


if __name__ == "__main__":
    main()

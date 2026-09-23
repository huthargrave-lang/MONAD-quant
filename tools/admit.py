#!/usr/bin/env python3
"""
admit — the admission gate: the ONLY way a hypothesis becomes an "edge".

Deterministic by construction: no LLM judges anything here. An agent (or a person) can
propose, sweep and argue, but whether a pre-registered hypothesis is admitted is decided
by the chain below, from committed evidence, and the verdict is written to an immutable
record under docs/research/verdicts/<H>/.

Profile ``price_strategy`` (the hourly RSI/VWAP mean-reversion family), in order:

  registration   the frozen spec (src/research/prereg.py) loads and names a candidate
  code           the tree is clean and at a known commit: evidence must be replayable
  refutations    no unanswered objection (BLOCK); no upheld objection (REJECT)
  parity         the live bot decides like the backtest (tools/live_backtest_parity.py):
                 a backtest edge the bot cannot reproduce is not an edge it can trade
  development    the frozen candidate, re-run on the registered development window at
                 instrument cost, with at least min_trades trades
  deflation      its Deflated Sharpe against EVERY trial its family has recorded, by any
                 tool, is at least the registered threshold (src/research/deflation.py)
  cost_stress    still profitable at 2x cost
  benchmark      Calmar at least buy & hold's on the same bars
  forward        after registered_at + min_days: on bars that did not exist when the spec
                 was frozen, min_trades trades and P(forward Sharpe > 0) >= min_psr

Every backtest the gate runs is itself a counted trial in the family. Every stage runs
when it can, so the record says everything that is wrong, not only the first thing.
Verdict = worst stage outcome: REJECT > BLOCKED > PENDING > ADMIT.

Other profiles (event_study, allocation) are UNSUPPORTED until their holdouts exist; the
gate says so rather than admitting on a partial chain.

  venv/bin/python tools/admit.py H97            # evaluate, write the verdict record
  venv/bin/python tools/admit.py H97 --dry-run  # evaluate, write nothing but trials
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as _dt
import io
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd  # noqa: E402

from src.research import deflation, prereg, refutations, trials  # noqa: E402
from src.research import significance as sig  # noqa: E402
from src.research.backtest_trials import (MR_HOURLY_STRATEGY, data_spec, engine_spec,  # noqa: E402
                                          mr_hourly_family, record_backtest)

VERDICT_REL = Path("docs/research/verdicts")
VERDICT_DIR = Path(REPO) / VERDICT_REL

PASS, FAIL, BLOCK, PENDING, SKIP = "pass", "fail", "block", "pending", "skip"
ADMIT, REJECT, BLOCKED, PENDING_V, UNSUPPORTED = "ADMIT", "REJECT", "BLOCKED", "PENDING", "UNSUPPORTED"
CANDIDATE_KEYS = ("target_gain_pct", "stop_loss_pct", "rsi_oversold", "vwap_zscore_thresh",
                  "max_trade_bars")
COST_STRESS_MULTIPLE = 2
#: Bars of feature warm-up loaded before the forward window. Trades before
#: ``registered_at`` are discarded; these bars only let indicators settle.
FORWARD_WARMUP_DAYS = 60


@dataclass
class Stage:
    name: str
    outcome: str
    detail: str
    data: dict = field(default_factory=dict)


def _verdict(stages: list[Stage]) -> str:
    outcomes = {s.outcome for s in stages}
    if FAIL in outcomes:
        return REJECT
    if BLOCK in outcomes:
        return BLOCKED
    if PENDING in outcomes:
        return PENDING_V
    return ADMIT


def default_load_bars(symbol: str, start: str, end: str) -> pd.DataFrame:
    """Hourly regular-session bars, as sweep.py and the funnel use them."""
    from src.data.fetcher import fetch_yfinance

    with contextlib.redirect_stdout(io.StringIO()):
        df = fetch_yfinance(symbol=symbol, start=start, end=end, interval="1h")
    return df.between_time("09:30", "16:00")


def _utc_naive(df: pd.DataFrame) -> pd.DataFrame:
    """Bars indexed in naive UTC, the basis ``registered_at`` is compared on. A tz-aware
    index compared with a naive timestamp raises; one silently mixed would shift the
    forward boundary by the UTC offset."""
    if df is None or not len(df):
        return df
    idx = pd.DatetimeIndex(df.index)
    if idx.tz is not None:
        df = df.copy()
        df.index = idx.tz_convert("UTC").tz_localize(None)
    return df


def default_parity() -> dict:
    import live_backtest_parity

    return live_backtest_parity.census()


def _counted_backtest(df, ticker, params, cost, *, run, stage, evaluated_from=None):
    """One engine backtest of the frozen candidate, counted before it runs."""
    import strategy_funnel
    from src.backtest.runner import run_backtest

    mode = strategy_funnel._apply_config(ticker, params)
    key = f"{run.run_id}#{run.trials_begun}"
    trial = run.begin(
        params=engine_spec(mode, timeframe="hourly", target=params["target_gain_pct"],
                           stop=params["stop_loss_pct"], backtest_mode="realistic",
                           slippage_pct=cost),
        data=data_spec(df, ticker, evaluated_from), extra={"stage": stage})
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            r = run_backtest(df=df.copy(), target_gain_pct=params["target_gain_pct"],
                             stop_loss_pct=params["stop_loss_pct"], require_signals=1,
                             timeframe="hourly", plot=False, backtest_mode="realistic",
                             slippage_pct=cost)
        except Exception as exc:  # noqa: BLE001 — counted, then reported by the caller
            trial.fail(f"{type(exc).__name__}: {exc}")
            return key, None
    record_backtest(trial, r, evaluated_from=evaluated_from)
    return key, (r or None)


def evaluate(hypothesis: str, *, now: _dt.datetime | None = None,
             load_bars: Callable = default_load_bars, parity: Callable = default_parity,
             code: Callable = trials.code_state, prereg_dir=None,
             refutations_dir=None) -> dict:
    """Run the gate. Returns the verdict record (not yet written).

    There is deliberately no way to point the gate at another ledger: its trials land in
    the canonical one (tests/test_producer_ledger_wiring.py), and it deflates against it.
    """
    import strategy_funnel
    from src.optimization.sweep_costs import estimate_spread, round_trip_cost_pct

    now = now or _dt.datetime.now(_dt.timezone.utc)
    stages: list[Stage] = []
    record = {"schema": 1, "hypothesis": hypothesis,
              "evaluated_at": now.isoformat(timespec="seconds").replace("+00:00", "Z")}

    # ── registration ────────────────────────────────────────────────────────
    try:
        spec, spec_hash = prereg.load(hypothesis, prereg_dir=prereg_dir)
    except prereg.PreregError as exc:
        stages.append(Stage("registration", FAIL, str(exc)))
        return {**record, "verdict": REJECT, "stages": [asdict(s) for s in stages]}
    record.update(spec_hash=spec_hash, family=spec["family"], profile=spec["profile"])
    params = spec.get("params")
    if spec["profile"] != "price_strategy" or not spec["family"].startswith(MR_HOURLY_STRATEGY + ":"):
        stages.append(Stage("registration", BLOCK,
                            f"profile {spec['profile']!r} / family {spec['family']!r} has no "
                            f"admission chain yet (only hourly RSI/VWAP price strategies)"))
        return {**record, "verdict": UNSUPPORTED, "stages": [asdict(s) for s in stages]}
    if len(spec["universe"]) != 1:
        stages.append(Stage("registration", BLOCK, "multi-instrument universes are not supported yet"))
        return {**record, "verdict": UNSUPPORTED, "stages": [asdict(s) for s in stages]}
    if not isinstance(params, dict) or set(params) != set(CANDIDATE_KEYS):
        stages.append(Stage("registration", FAIL,
                            f"params must freeze exactly the candidate {list(CANDIDATE_KEYS)}; "
                            f"a registration without a frozen candidate cannot be admitted"))
        return {**record, "verdict": REJECT, "stages": [asdict(s) for s in stages]}
    ticker = spec["universe"][0]
    if spec["family"] != mr_hourly_family(ticker):
        stages.append(Stage("registration", FAIL,
                            f"family must be {mr_hourly_family(ticker)!r}, the one every tool "
                            f"records this strategy on {ticker} under; a private family would "
                            f"start the trial count from zero"))
        return {**record, "verdict": REJECT, "stages": [asdict(s) for s in stages]}
    stages.append(Stage("registration", PASS, f"frozen at {spec['registered_at']}"))

    # ── code ────────────────────────────────────────────────────────────────
    cs = code()
    record["code"] = cs
    if cs.get("sha") and cs.get("dirty") is False:
        stages.append(Stage("code", PASS, f"clean at {cs['sha'][:12]}"))
    else:
        stages.append(Stage("code", BLOCK, "the tree is dirty or unreadable; admission "
                            "evidence must be replayable from a commit", {"code": cs}))

    # ── refutations ─────────────────────────────────────────────────────────
    ref = refutations.status(hypothesis, refutations_dir)
    if ref["upheld"]:
        stages.append(Stage("refutations", FAIL, f"{len(ref['upheld'])} objection(s) upheld",
                            {"upheld": [o["id"] for o in ref["upheld"]]}))
    elif ref["open"]:
        stages.append(Stage("refutations", BLOCK, f"{len(ref['open'])} objection(s) unanswered",
                            {"open": [o["id"] for o in ref["open"]]}))
    else:
        stages.append(Stage("refutations", PASS, f"{len(ref['refuted'])} objection(s), all refuted"))

    # ── parity ──────────────────────────────────────────────────────────────
    census = parity()
    diverge = [r["dimension"] for r in census["rows"] if r["verdict"] == "DIVERGE"]
    stages.append(Stage("parity", BLOCK if diverge else PASS,
                        (f"backtest and live bot decide differently on: {', '.join(diverge)}"
                         if diverge else "no divergent decision input"),
                        {"counts": census["counts"]}))

    # ── backtests (all counted) ─────────────────────────────────────────────
    w = spec["development_window"]
    registered_at = pd.Timestamp(spec["registered_at"]).tz_convert(None)
    snap = strategy_funnel._snapshot_config()
    dev_key = dev = stress = fwd = None
    fwd_key = None
    forward_due = (pd.Timestamp(now).tz_convert(None) - registered_at).days >= spec["holdout"]["min_days"]
    try:
        with trials.open_run(producer="tools/admit.py", family=spec["family"],
                             hypothesis=hypothesis, context={"spec_hash": spec_hash}) as run:
            df = _utc_naive(load_bars(ticker, w["start"], w["end"]))
            if df is None or not len(df):
                raise RuntimeError(f"no bars for {ticker} over {w['start']}..{w['end']}")
            median = float(df["close"].median())
            cost = round_trip_cost_pct(estimate_spread(median, None), median)
            dev_key, dev = _counted_backtest(df, ticker, params, cost, run=run,
                                             stage="admission:development")
            _, stress = _counted_backtest(df, ticker, params, cost * COST_STRESS_MULTIPLE,
                                          run=run, stage=f"admission:cost_{COST_STRESS_MULTIPLE}x")
            if forward_due:
                start = (registered_at - pd.Timedelta(days=FORWARD_WARMUP_DAYS)).date().isoformat()
                fdf = _utc_naive(load_bars(ticker, start, pd.Timestamp(now).date().isoformat()))
                if fdf is not None and len(fdf):
                    fwd_key, fwd = _counted_backtest(fdf, ticker, params, cost, run=run,
                                                     stage="admission:forward",
                                                     evaluated_from=registered_at)
        record["ledger_run"] = run.run_id
    except Exception as exc:  # noqa: BLE001 — a gate that cannot measure must not admit
        stages.append(Stage("development", BLOCK, f"could not run the candidate: {exc}"))
        return {**record, "verdict": _verdict(stages), "stages": [asdict(s) for s in stages]}
    finally:
        strategy_funnel._restore_config(snap)

    # ── development ─────────────────────────────────────────────────────────
    n_dev = int(dev["total_trades"]) if dev else 0
    stages.append(Stage("development", PASS if n_dev >= spec["min_trades"] else FAIL,
                        f"{n_dev} trades (need {spec['min_trades']})",
                        {"trial": dev_key, "total_return": dev.get("total_return") if dev else None}))

    # ── deflation ───────────────────────────────────────────────────────────
    if dev and n_dev >= 2:
        try:
            d = deflation.deflate_candidate(dev_key, searched_before=spec["registered_at"])
            ok = d.result.dsr >= spec["threshold"]
            stages.append(Stage("deflation", PASS if ok else FAIL,
                                f"DSR {d.result.dsr:.4f} vs {spec['threshold']} "
                                f"(N_eff {d.n_trials:.2f} from {d.trials_recorded} trials "
                                f"recorded before registration)",
                                {"dsr": d.result.dsr, "sr0": d.result.sr0, "n_trials": d.n_trials,
                                 "trials_recorded": d.trials_recorded,
                                 "annualized_sharpe": d.annualized_sharpe}))
        except (ValueError, trials.LedgerError) as exc:
            stages.append(Stage("deflation", FAIL, f"cannot deflate: {exc}"))
    else:
        stages.append(Stage("deflation", FAIL, "no development trades to deflate"))

    # ── cost stress ─────────────────────────────────────────────────────────
    s_ret = float(stress["total_return"]) if stress else 0.0
    stages.append(Stage("cost_stress", PASS if s_ret > 0 else FAIL,
                        f"total return {s_ret:+.4f} at {COST_STRESS_MULTIPLE}x cost"))

    # ── benchmark ───────────────────────────────────────────────────────────
    if dev:
        strat = strategy_funnel._calmar(dev["total_return"], dev["max_drawdown"],
                                        strategy_funnel._years(df))
        bench, _, _ = strategy_funnel._benchmark_calmar(df)
        ok = strat is not None and bench is not None and strat >= bench
        stages.append(Stage("benchmark", PASS if ok else FAIL,
                            f"Calmar {strat} vs buy & hold {bench}",
                            {"strategy_calmar": strat, "buy_hold_calmar": bench}))
    else:
        stages.append(Stage("benchmark", FAIL, "no development result"))

    # ── forward ─────────────────────────────────────────────────────────────
    h = spec["holdout"]
    if not forward_due:
        due = registered_at + pd.Timedelta(days=h["min_days"])
        stages.append(Stage("forward", PENDING, f"forward window matures {due.date()}"))
    else:
        series = (fwd or {}).get("trade_returns") if fwd else None
        scored = bt_scored(series, registered_at)
        if len(scored) < h["min_trades"]:
            stages.append(Stage("forward", PENDING,
                                f"{len(scored)} forward trades (need {h['min_trades']})",
                                {"trial": fwd_key}))
        else:
            pnl = sig.active_span(sig.daily_pnl({"f": scored})["f"])
            try:
                m = sig.sharpe_moments(pnl)
                psr = sig.probabilistic_sharpe(m.sharpe, 0.0, n_obs=m.n_obs, skew=m.skew,
                                               kurtosis=m.kurtosis)
            except ValueError as exc:
                stages.append(Stage("forward", FAIL, f"forward returns are degenerate: {exc}"))
            else:
                stages.append(Stage("forward", PASS if psr >= h["min_psr"] else FAIL,
                                    f"P(forward Sharpe > 0) = {psr:.4f} vs {h['min_psr']} "
                                    f"over {len(scored)} trades",
                                    {"trial": fwd_key, "psr": psr}))

    return {**record, "verdict": _verdict(stages), "stages": [asdict(s) for s in stages]}


def bt_scored(series, evaluated_from) -> pd.Series:
    if series is None or not len(series):
        return pd.Series(dtype=float)
    return series[series.index >= pd.Timestamp(evaluated_from)]


def write_verdict(record: dict, verdict_dir: Path | None = None) -> Path:
    """Write the record once, immutably, as canonical JSON."""
    base = Path(verdict_dir) if verdict_dir is not None else VERDICT_DIR
    stamp = record["evaluated_at"].replace(":", "").replace("-", "")
    target = base / record["hypothesis"] / f"{stamp}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(trials.canonical_json(record, nonfinite="encode") + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    return target


def verify_history(base_ref: str, *, repo: Path = Path(REPO)) -> list[str]:
    """Verdict records on the deploy branch are never edited or deleted."""
    return trials.verify_history(base_ref, VERDICT_REL, repo=repo, what="verdict",
                                 rule=lambda r: "identical" if r.endswith(".json") else None)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("hypothesis", nargs="?")
    ap.add_argument("--dry-run", action="store_true", help="do not write the verdict record")
    ap.add_argument("--verify-history", metavar="REF",
                    help="check no verdict on REF's merge-base was edited or deleted, then exit")
    args = ap.parse_args(argv)
    if args.verify_history:
        problems = verify_history(args.verify_history)
        for p in problems:
            print(f"FAIL {p}")
        print(f"{len(problems)} problem(s)")
        return 1 if problems else 0
    if not args.hypothesis:
        ap.error("hypothesis is required")
    record = evaluate(args.hypothesis)
    for s in record["stages"]:
        print(f"  {s['outcome'].upper():8} {s['name']:<13} {s['detail']}")
    print(f"\n{record['hypothesis']}: {record['verdict']}")
    if not args.dry_run:
        path = write_verdict(record)
        print(f"verdict record -> {os.path.relpath(path, REPO)}")
        if record["verdict"] == ADMIT:
            print("\nCapture it in the web, citing this record:\n"
                  f"  venv/bin/python tools/note.py add --kind F --title \"{record['hypothesis']} "
                  f"admitted\" --body \"Verdict {os.path.relpath(path, REPO)}\" "
                  f"--link {record['hypothesis']}:supports")
    return 0 if record["verdict"] in (ADMIT, PENDING_V) else 1


if __name__ == "__main__":
    sys.exit(main())

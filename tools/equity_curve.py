"""Re-run ONE parameter set and emit its equity curve as JSON on stdout.

WHY THIS EXISTS
---------------
A sweep returns summary statistics per preset and nothing else — no per-bar series. So the
four-panel picture `main.py` writes to `backtest_results.png` (equity against buy-and-hold,
drawdown, monthly bars, exit mix) cannot be drawn from a sweep result at all: every one of
those panels needs the curve, and the curve is thrown away when the grid is scored.

`run_backtest()` already returns `equity_curve`, `monthly_returns` and `trades_df` — the data
was never missing, only discarded. So nothing in the engine changes. This runs the winning
preset once more, on the same data and the same cost model, and hands the series back as JSON
a browser can draw.

WHY A SEPARATE PROCESS
----------------------
Same reason the sweep is one: the research UI's venv is Python 3.9 and cannot import the
strategy engine (`src/strategy/sizing.py` annotates with `dict | None`). `sweep_runner` finds
an interpreter that can, and invokes this the same way — no `--apply`, closed stdin, arguments
matched rather than interpolated.

THE OUTPUT IS DELIBERATELY DOWNSAMPLED
--------------------------------------
An hourly backtest over two years is ~3,500 points per series. Three series of that is ~200KB
of JSON to draw a chart 900px wide, where at most 900 of those points can occupy distinct
pixels. `_thin()` keeps the shape — including every extreme, so a drawdown is never smoothed
away — and caps the payload. A chart that lies about the worst day to save bytes would be the
opposite of the point.
"""
import argparse
import contextlib
import io
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

MAX_POINTS = 900


def _thin(values, keep=MAX_POINTS):
    """Downsample to `keep` points while preserving every local extreme.

    Plain stride sampling can step straight over a crash: take every 4th point and a one-bar
    -20% spike vanishes. This walks in buckets and keeps the min AND max of each, so the
    drawdown a reader sees is the drawdown that happened.
    """
    n = len(values)
    if n <= keep:
        return [round(float(v), 2) for v in values]
    step = n / float(keep // 2)
    out, i = [], 0.0
    while i < n:
        chunk = values[int(i):max(int(i) + 1, int(i + step))]
        if len(chunk):
            out.append(round(float(min(chunk)), 2))
            if max(chunk) != min(chunk):
                out.append(round(float(max(chunk)), 2))
        i += step
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("ticker")
    ap.add_argument("--target", type=float, required=True)
    ap.add_argument("--stop", type=float, required=True)
    ap.add_argument("--rsi", type=int, required=True)
    ap.add_argument("--vwap", type=float, required=True)
    ap.add_argument("--start", default=None)
    ap.add_argument("--end", default=None)
    ap.add_argument("--mode", default="realistic")
    a = ap.parse_args()

    # Imported here, not at module scope: the import itself is what fails on an interpreter too
    # old for the engine, and a clean JSON error beats a traceback the browser cannot render.
    try:
        import datetime
        import pandas as pd
        import config
        from src.data.fetcher import fetch_yfinance
        from src.strategy.engine import build_features
        from src.backtest.runner import run_backtest
    except Exception as exc:  # noqa: BLE001 — reported, not swallowed
        print(json.dumps({"error": "could not import the strategy engine: %s" % exc}))
        return 1

    # KNOWN DUPLICATION, stated rather than hidden. `sweep.py:173` has `fetch_ticker_hourly`
    # doing exactly this — fetch hourly, keep regular session hours — and it cannot be imported
    # because sweep.py parses argv at module scope. The two must stay in step: a curve loaded
    # over different bars than the sweep scored would be a picture of a different backtest.
    # The right fix is lifting that loader into src/data/, which is a change to the sweep's own
    # entry path and wants its own sign-off.
    # yfinance serves at most 730 days of HOURLY data, so "two years" overshoots by the leap
    # day and returns nothing at all. 700 leaves room and still covers the sweep's usual span.
    end = a.end or datetime.date.today().isoformat()
    start = a.start or (pd.Timestamp(end) - pd.Timedelta(days=700)).date().isoformat()
    if (pd.Timestamp(end) - pd.Timestamp(start)).days > 729:
        print(json.dumps({"error":
            "hourly bars are only available for the last 730 days, and that window is %d. "
            "Pick a shorter one." % (pd.Timestamp(end) - pd.Timestamp(start)).days}))
        return 1

    try:
        # Everything the engine prints goes to stderr's bit bucket: stdout is the JSON channel
        # and one stray progress line would make the whole payload unparseable.
        with contextlib.redirect_stdout(io.StringIO()):
            df = fetch_yfinance(symbol=a.ticker, start=start, end=end, interval="1h")
            if df is None or not len(df):
                raise RuntimeError("no bars came back for %s over that window" % a.ticker)
            df = df.between_time("09:30", "16:00")
            df = build_features(df)
            for name, value in (("RSI_OVERSOLD", a.rsi), ("VWAP_ZSCORE_THRESH", a.vwap)):
                setattr(config, name, value)
            res = run_backtest(
                df=df.copy(), initial_capital=config.INITIAL_CAPITAL,
                target_gain_pct=a.target, stop_loss_pct=a.stop, require_signals=1,
                kelly_multiplier=config.KELLY_MULTIPLIER, timeframe="hourly",
                plot=False, backtest_mode=a.mode)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": str(exc)}))
        return 1

    if not res or "equity_curve" not in res:
        print(json.dumps({"error": "the backtest produced no trades at these parameters, so "
                                   "there is no curve to draw"}))
        return 0

    equity = list(res["equity_curve"])
    initial = float(config.INITIAL_CAPITAL)

    # Buy-and-hold on the SAME bars and the same starting capital, because an equity curve
    # with nothing to sit against invites the reader to supply their own benchmark.
    close = df["close"].astype(float)
    buyhold = (initial * (close / close.iloc[0])).tolist()

    # Drawdown from the model's own running peak — the panel main.py draws underneath.
    peak, dd = equity[0], []
    for v in equity:
        peak = max(peak, v)
        dd.append(round(((v - peak) / peak) * 100.0, 3))

    monthly = res.get("monthly_returns")
    months = []
    if monthly is not None and len(monthly):
        for idx, val in monthly.items():
            try:
                months.append({"label": str(idx)[:7], "pct": round(float(val) * 100.0, 3)})
            except (TypeError, ValueError):
                continue

    exits = {}
    tdf = res.get("trades_df")
    if tdf is not None and "exit_type" in getattr(tdf, "columns", []):
        exits = {str(k): int(v) for k, v in tdf["exit_type"].value_counts().items()}

    print(json.dumps({
        "ticker": a.ticker,
        "window": {"start": start, "end": end},
        "initial_capital": initial,
        "equity": _thin(equity),
        "buyhold": _thin(buyhold),
        "drawdown": _thin(dd),
        "final": round(float(equity[-1]), 2),
        "buyhold_final": round(float(buyhold[-1]), 2),
        "max_drawdown_pct": round(min(dd), 3) if dd else None,
        "monthly": months,
        "exits": exits,
        "bars": len(equity),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())

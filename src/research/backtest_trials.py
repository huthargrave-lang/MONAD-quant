"""
MONAD Quant — Recording a backtest result as a ledger trial.

Every producer that calls ``run_backtest`` (the sweep, walk-forward, the funnel)
turns its result into a trial outcome the same way, here, so a trial's metrics
mean the same thing whichever tool produced it. One definition, many callers:
a second copy of "what counts as a zero-trade result" is how two tools start
disagreeing about the same backtest.

``run_backtest`` has three result shapes, and each maps to one outcome:

  * ``{}`` / ``None``        — the engine produced no trades. That is a valid,
                               losing trial (``ok``, ``total_trades=0``), not an
                               error: it was tried, and it found nothing.
  * ``{"error": msg}``       — the backtest failed. ``error`` outcome.
  * a full result dict       — ``ok``, with the headline metrics and the per-trade
                               return series (indexed by trade timestamp), which
                               the significance kernel clusters for effective N.
"""
from __future__ import annotations

from typing import Any, Mapping

from src.research.trials import LedgerError, Trial

#: Headline metrics copied from a result into the outcome row. Keys absent from a
#: result are omitted rather than defaulted: a missing number is not a zero.
METRIC_KEYS = ("total_trades", "win_rate", "total_return", "sharpe_ratio",
               "max_drawdown", "trades_per_year", "avg_win_pct", "avg_loss_pct")


#: The strategy idea the engine tools (sweep.py, walkforward_eval, strategy_funnel,
#: main.py, walk_forward_optimize) all test: long-only RSI/VWAP mean reversion, per
#: timeframe and instrument. They share ONE family per (timeframe, instrument) because
#: a trial count split across tools undercounts the search behind any single result,
#: and undercounting is the failure the ledger exists to prevent. The hourly name
#: matches strategy_funnel's card ``strategy_family``.
MR_STRATEGY = "long_only_rsi_vwap_mr"
MR_HOURLY_STRATEGY = f"{MR_STRATEGY}_hourly"


def mr_family(symbol: str, timeframe: str = "hourly") -> str:
    return f"{MR_STRATEGY}_{timeframe}:{symbol.upper()}"


def mr_hourly_family(ticker: str) -> str:
    return mr_family(ticker, "hourly")


def family_members(records, family: str) -> list:
    """The trials that count toward ``family``: its label, OR (for an MR family) every
    hourly engine trial on the same symbol, whatever label it was recorded under.

    A family is otherwise just a string a producer is handed (``--family``), so a search
    run under a scratch label and registered under the real one would be invisible to the
    count (harness red-team, attack 4a). The engine spec is not a label: a trial whose
    data is ``SYMBOL`` and whose spec is an hourly engine run IS this strategy on SYMBOL.
    """
    prefix = f"{MR_HOURLY_STRATEGY}:"
    symbol = family[len(prefix):] if family.startswith(prefix) else None
    out = []
    for r in records:
        if r.family == family:
            out.append(r)
            continue
        if symbol is None:
            continue
        params = (r.spec or {}).get("params") or {}
        data = (r.spec or {}).get("data") or {}
        if (isinstance(params, dict) and params.get("timeframe") == "hourly" and "mode" in params
                and str(data.get("ticker") or "").upper() == symbol):
            out.append(r)
    return out


def engine_spec(mode: str, *, timeframe: str, target: float, stop: float,
                backtest_mode: str | None, slippage_pct: float | None,
                require_signals: int = 1, asset_key: str | None = None,
                settings: Mapping[str, Any] | None = None) -> dict:
    """Every engine setting a producer can vary, read from ``config`` NOW.

    The engine reads its parameters from module globals (``<PARAM>_<MODE>``,
    ``config.ASSETS[asset]``, ``MAX_TRADE_BARS``, the sizing and regime flags), and
    producers mutate them before a backtest. Reading them at intent time records what
    the engine will actually see, not what the caller meant to set. ``settings`` holds
    call arguments that are not config (trade-hour gates, Kelly overrides).
    """
    import config  # the engine's global parameter store; imported where it is read

    suffix = f"_{mode}"
    flags = ("MAX_TRADE_BARS", "USE_OPPOSING_SIGNAL_EXIT", "POSITION_SIZING_MODE",
             "FIXED_POSITION_PCT", "USE_ADAPTIVE_KELLY", "KELLY_MULTIPLIER", "INITIAL_CAPITAL",
             "USE_REGIME_FILTER", "USE_SLOPE_REGIME", "LONGS_ONLY", "BEAR_DEFENSIVE_LONGS",
             "BEAR_MAX_TRADE_BARS", "REQUIRE_SIGNALS")
    return {
        "mode": mode, "timeframe": timeframe,
        "target_gain_pct": target, "stop_loss_pct": stop,
        "backtest_mode": backtest_mode, "slippage_pct": slippage_pct,
        "require_signals": require_signals,
        "asset": dict(config.ASSETS.get(asset_key or mode, {})),
        "mode_constants": {k: getattr(config, k) for k in sorted(dir(config)) if k.endswith(suffix)},
        "config_flags": {k.lower(): getattr(config, k, None) for k in flags},
        "settings": dict(settings) if settings is not None else None,
    }


def data_spec(df, ticker: str | None, evaluated_from=None) -> dict:
    """What a trial ran on: the exact bars (content hash) and ``evaluated_from``.

    ``evaluated_from`` (inclusive) is where scoring began when the engine ran over more
    bars than the producer judged: the trial's recorded outcome covers ONLY trades at or
    after it. Earlier bars were feature warm-up or already-seen training data. Every
    producer must mean exactly this, so a holdout trial from sweep.py and an OOS trial
    from walkforward_eval are comparable rows.
    """
    from src.optimization.sweep_repro import data_fingerprint

    return {"ticker": ticker.upper() if ticker else None, "fingerprint": data_fingerprint(df),
            "evaluated_from": str(evaluated_from) if evaluated_from is not None else None}


def backtest_metrics(result: Mapping[str, Any] | None) -> dict:
    """The outcome metrics for a (non-error) backtest result."""
    if not result:
        return {"total_trades": 0}
    return {k: result[k] for k in METRIC_KEYS if k in result}


def scored_from(result: Mapping[str, Any] | None, evaluated_from) -> dict:
    """``result`` restricted to trades at or after ``evaluated_from``.

    Only the trade count, win rate and the return series survive the restriction: the
    engine's other headline numbers (Sharpe, drawdown, total return) describe the whole
    run, so carrying them onto the restricted outcome would mislabel them.
    """
    import pandas as pd

    series = (result or {}).get("trade_returns")
    if series is None or not len(series):
        return {"total_trades": 0}
    scored = series[series.index >= pd.Timestamp(evaluated_from)]
    out = {"total_trades": int(len(scored)), "trade_returns": scored}
    if len(scored):
        out["win_rate"] = float((scored > 0).mean())
    return out


def record_backtest(trial: Trial, result: Mapping[str, Any] | None, *,
                    evaluated_from=None) -> None:
    """Write ``result`` as ``trial``'s outcome (see the module docstring for the mapping).

    Pass ``evaluated_from`` when ``result`` is a raw engine run over more bars than the
    producer scores (see ``data_spec``); a producer that already restricted its result
    itself passes nothing.
    """
    if isinstance(result, Mapping) and "error" in result:
        trial.fail(str(result["error"]))
        return
    if evaluated_from is not None:
        result = scored_from(result, evaluated_from)
    returns = None
    if result:
        series = result.get("trade_returns")
        if series is not None and len(series):
            returns = series
    try:
        trial.complete(metrics=backtest_metrics(result), returns=returns)
    except LedgerError as exc:
        # A result the ledger cannot encode (a NaN trade return, an exotic type) is a
        # defect in the result, not a reason to lose the trial: it is still counted,
        # as an error that says why.
        trial.fail(f"unrecordable backtest result: {exc}")

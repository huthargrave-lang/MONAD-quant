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
                               Under ENGINE_VERSION 3 the result also carries its
                               trades' session marks, recorded as the named series
                               ``mtm_pnl``, ``exposure`` and ``instrument_return``
                               (gate rules v2 (iii)).
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


def _engine_version() -> int:
    from src.backtest.runner import ENGINE_VERSION
    return ENGINE_VERSION


#: The mark-to-market basis version recorded in each engine trial's spec.
MTM_BASIS_VERSION = 1

#: Families carry the engine version (".v2"): trials run on engines that executed
#: differently must never pool into one search count (decision-debate Q4).
MR_HOURLY_STRATEGY = f"{MR_STRATEGY}_hourly.v{_engine_version()}"


def mr_family(symbol: str, timeframe: str = "hourly") -> str:
    return f"{MR_STRATEGY}_{timeframe}.v{_engine_version()}:{symbol.upper()}"


def mr_hourly_family(ticker: str) -> str:
    return mr_family(ticker, "hourly")


def family_members(records, family: str) -> list:
    """The trials that count toward ``family``: its label, OR (for an MR family) every
    hourly engine trial on the same symbol, whatever label it was recorded under, OR (for
    a daily family) every trial of the same daily evaluator version
    (``daily_trials.daily_family_members``).

    A family is otherwise just a string a producer is handed (``--family``), so a search
    run under a scratch label and registered under the real one would be invisible to the
    count (harness red-team, attack 4a). The engine spec is not a label: a trial whose
    data is ``SYMBOL`` and whose spec is an hourly engine run IS this strategy on SYMBOL.
    """
    from src.research.daily_trials import daily_family_members, parse_family
    try:
        parse_family(family)
    except ValueError:
        pass
    else:
        return daily_family_members(records, family)
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
        engine = params.get("engine") if isinstance(params, dict) else None
        if (isinstance(params, dict) and params.get("timeframe") == "hourly" and "mode" in params
                and str(data.get("ticker") or "").upper() == symbol
                and isinstance(engine, dict) and engine.get("engine_version") == _engine_version()):
            out.append(r)
    return out


def lineage_members(records, family: str) -> list:
    """Every hourly engine trial on ``family``'s symbol recorded under an EARLIER engine
    version: the family's lineage. They never pool into the current family's statistics
    (they executed differently), but they are still search on the same strategy and
    symbol, and the v2 gate charges them in m (price trigger consensus 2026-10-06, R4): a
    version bump must never erase a search."""
    prefix = f"{MR_HOURLY_STRATEGY}:"
    if not family.startswith(prefix):
        return []
    symbol = family[len(prefix):]
    current = _engine_version()
    out = []
    for r in records:
        params = (r.spec or {}).get("params") or {}
        data = (r.spec or {}).get("data") or {}
        engine = params.get("engine") if isinstance(params, dict) else None
        version = engine.get("engine_version") if isinstance(engine, dict) else None
        old_label = (r.family.startswith(f"{MR_STRATEGY}_hourly") and r.family.endswith(f":{symbol}")
                     and r.family != family)
        is_engine_run = (isinstance(params, dict) and params.get("timeframe") == "hourly"
                         and "mode" in params and str(data.get("ticker") or "").upper() == symbol)
        if (is_engine_run and (version is None or version < current)) or \
                (old_label and not (isinstance(version, int) and version >= current)):
            out.append(r)
    return out


def engine_spec(mode: str, *, timeframe: str, target: float, stop: float,
                backtest_mode: str | None, slippage_pct: float | None,
                require_signals: int = 1, asset_key: str | None = None,
                settings: Mapping[str, Any] | None = None,
                max_trade_bars: int | None = None) -> dict:
    """Every engine setting a producer can vary, read from ``config`` NOW.

    The engine reads its parameters from module globals (``<PARAM>_<MODE>``,
    ``config.ASSETS[asset]``, ``MAX_TRADE_BARS``, the sizing and regime flags), and
    producers mutate them before a backtest. Reading them at intent time records what
    the engine will actually see, not what the caller meant to set. ``settings`` holds
    call arguments that are not config (trade-hour gates, Kelly overrides).

    ``engine`` is authoritative for execution semantics: the hold, regime gate and short
    suppression the engine WILL apply (``runner.engine_settings``, the same functions
    run_backtest calls) and the ENGINE_VERSION. Pass the ``max_trade_bars`` you pass to
    run_backtest (None when you let it resolve). Recording config intent instead let a
    spec say 8 bars while the engine held 10 (decision-debate Q4).
    """
    from src.backtest.runner import engine_settings

    import config  # the engine's global parameter store; imported where it is read

    suffix = f"_{mode}"
    # Config that shapes a run but is not resolved into ``engine`` below. The hold, the
    # regime gate and the long/short policy are deliberately NOT here: their resolved
    # values are in ``engine``, and a second, config-intent copy would contradict it.
    flags = ("USE_OPPOSING_SIGNAL_EXIT", "POSITION_SIZING_MODE", "FIXED_POSITION_PCT",
             "USE_ADAPTIVE_KELLY", "KELLY_MULTIPLIER", "INITIAL_CAPITAL", "USE_SLOPE_REGIME",
             "BEAR_DEFENSIVE_LONGS", "BEAR_MAX_TRADE_BARS", "REQUIRE_SIGNALS")
    return {
        "mode": mode, "timeframe": timeframe,
        "target_gain_pct": target, "stop_loss_pct": stop,
        "backtest_mode": backtest_mode, "slippage_pct": slippage_pct,
        # Upper-bound runs (target-first ambiguity, no slippage) count in a family's N
        # but can never be a candidate (ENGINE_VERSION 3; admission re-runs "realistic").
        "upper_bound": bool(backtest_mode == "upper_bound"),
        "require_signals": require_signals,
        "asset": dict(config.ASSETS.get(asset_key or mode, {})),
        "mode_constants": {k: getattr(config, k) for k in sorted(dir(config)) if k.endswith(suffix)},
        "config_flags": {k.lower(): getattr(config, k, None) for k in flags},
        "engine": engine_settings(mode, timeframe, max_trade_bars),
        # The mark-to-market basis the trial records (gate rules v2): 1 = close-exposure
        # marks (DEFLATION_RULE_QUESTION.md (iii)). A recording change, not an execution
        # change: it moves the hash, not the family (price trigger consensus R4).
        "mtm_basis": MTM_BASIS_VERSION,
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
    cut = pd.Timestamp(evaluated_from)
    scored = series[series.index >= cut]
    out = {"total_trades": int(len(scored)), "trade_returns": scored}
    marks, sessions = (result or {}).get("trade_marks"), (result or {}).get("sessions")
    if marks is not None and sessions is not None:
        from src.research.mark_to_market import session_dates
        cut_session = session_dates(pd.DatetimeIndex([cut]))[0]
        out["trade_marks"] = marks[pd.DatetimeIndex(marks["trade"]) >= cut] if len(marks) else marks
        out["sessions"] = pd.DatetimeIndex(sessions)[pd.DatetimeIndex(sessions) >= cut_session]
        ir = (result or {}).get("instrument_return")
        if ir is not None:
            out["instrument_return"] = ir.reindex(out["sessions"])
    if len(scored):
        out["win_rate"] = float((scored > 0).mean())
    return out


def daily_mtm_series(result: Mapping[str, Any]) -> dict | None:
    """``{"mtm_pnl", "exposure", "instrument_return"}`` on the result's session grid (gate
    rules v2 (iii)), or None when the engine did not mark its trades (pre-v3 results,
    test stand-ins). The instrument's own daily return travels with the trial so the
    gate and its verifier rebuild the active series from the ledger alone."""
    marks, sessions = result.get("trade_marks"), result.get("sessions")
    ir = result.get("instrument_return")
    if marks is None or sessions is None or ir is None or not len(sessions):
        return None
    import pandas as pd

    from src.research.mark_to_market import daily_series
    idx = pd.DatetimeIndex(sessions)
    pnl, exposure = daily_series(marks, idx)
    return {"mtm_pnl": pnl, "exposure": exposure,
            "instrument_return": ir.reindex(idx).fillna(0.0).astype(float)}


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
    named = None
    if result:
        series = result.get("trade_returns")
        if series is not None and len(series):
            returns = series
        named = daily_mtm_series(result)
    try:
        trial.complete(metrics=backtest_metrics(result), returns=returns, series=named)
    except LedgerError as exc:
        # A result the ledger cannot encode (a NaN trade return, an exotic type) is a
        # defect in the result, not a reason to lose the trial: it is still counted,
        # as an error that says why.
        trial.fail(f"unrecordable backtest result: {exc}")

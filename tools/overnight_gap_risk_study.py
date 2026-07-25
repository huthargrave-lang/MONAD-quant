#!/usr/bin/env python3
"""
Studies #16–69 research program — audit execution semantics, quantify
overnight gap risk, test mitigation trade-offs, validate the mechanism
across leveraged instruments and market regimes, measure entry-ordering
calibration sufficiency, resolve lower-timeframe ambiguity, test
calendar-known partial flattening, and measure clustered/volatility-conditioned
overnight risk.

This is a read-only research harness.  It does not import live.*, connect to
IBKR, or modify strategy/config code.  It reuses the current hourly signal
pipeline, then evaluates the SAME entries under two exit-fill assumptions:

  exact_stop:
      The current compute_trade_returns() convention.  A stop always fills at
      exactly the stop level (less configured slippage), even if a new session
      opens through it.

  gap_aware:
      If a bar opens beyond the stop, fill at that open.  Otherwise use the
      same exact intrabar stop/target assumptions as exact_stop.

The verdict-bearing replay is live-shaped: full regular-session bars in
America/New_York, the live signal flags (no hourly regime filter), one open
position at a time, bracket scanning beginning on the entry bar, and the live
10-bar cap.  A second overlapping/N+2 replay is cross-checked byte-for-byte
against compute_trade_returns() so the isolated fill-model delta is auditable.
An assumption waterfall and same-entry paired replay isolate the effect of
entry-bar bracket activation from the later overnight-gap fill effect.

Pinned data window: 2024-08-01 through 2026-07-22 (end is exclusive).
Yahoo data are cached outside the repository at
/tmp/monad_tqqq_full_session_1h.csv.

Reproduce:
  venv/bin/python tools/overnight_gap_risk_study.py --selfcheck
  venv/bin/python tools/overnight_gap_risk_study.py --json /tmp/gap-risk.json
  venv/bin/python tools/overnight_gap_risk_study.py --refresh
"""

import argparse
import hashlib
import json
import math
import os
import re
import sqlite3
import sys
import tempfile
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

import config  # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import data_cache  # noqa: E402  (required-artifact preflight)
from src.strategy.engine import (  # noqa: E402
    build_features,
    compute_trade_returns,
    generate_trades,
)


SYMBOL = "TQQQ"
START = "2024-08-01"
END = "2026-07-23"  # yfinance end is exclusive; pins the last bar to 2026-07-22
CACHE = "/tmp/monad_tqqq_full_session_1h.csv"
HOURLY_SOURCE_SHA256 = (
    "0290d6756e82376fc650bbb28d86e2a289eaf69c040b9de88dceb2daa9c5650b"
)
FIVE_MIN_CACHE = "/tmp/monad_tqqq_5m_panel.csv"
FIVE_MIN_START = "2026-05-25"
FIVE_MIN_AUDIT = os.path.join(
    REPO, "docs", "research", "data", "entry_bar_5m_ordering_2026.csv"
)
FIVE_MIN_SOURCE_SHA256 = (
    "3b6a91ebdc5b8b30dd51cb1f262dada5097819da8c98bfc79fbf2b7156845432"
)
ONE_MIN_AUDIT = os.path.join(
    REPO, "docs", "research", "data", "entry_bar_1m_resolution_2026.csv"
)
ONE_MIN_SOURCE_SHA256 = (
    "faf659ffd4add7e643e5eb321508dcb9f44ca39384e8d955fb2da812d4254576"
)
ONE_MIN_RAW_CACHE = "/tmp/monad_tqqq_1m_jul6_window.csv"
CORPORATE_ACTIONS_AUDIT = os.path.join(
    REPO, "docs", "research", "data", "tqqq_corporate_actions_2010_2026.csv"
)
CORPORATE_ACTIONS_RAW_CACHE = "/tmp/monad_tqqq_daily_actions.csv"
CORPORATE_ACTIONS_SOURCE_SHA256 = (
    "861f6206ab7a5df80e53129fb7c890e20e2d79b46ebff0e34122873f9c37ba87"
)
QQQ_DISTRIBUTIONS_AUDIT = os.path.join(
    REPO, "docs", "research", "data", "qqq_distributions_2010_2026.csv"
)
QQQ_ACTIONS_RAW_CACHE = "/tmp/monad_qqq_daily_actions.csv"
QQQ_ACTIONS_SOURCE_SHA256 = (
    "7969bc74f7b5c77a24b53c9bdd0a8f4da98d617331d6ccda75e324b671ecdb94"
)
QUOTE_STALENESS_AUDIT = os.path.join(
    REPO,
    "docs",
    "research",
    "data",
    "tqqq_quote_staleness_5m_summary_2026.json",
)
DAILY_CACHE = "/tmp/monad_gap_daily_panel.csv"
DAILY_SOURCE_SHA256 = (
    "53a86106ce43319c151412f4fe194b0a0c1e3a4c8376a8a202c7e3e392bd924b"
)
DAILY_START = "2010-02-12"  # TQQQ inception; common long-history anchor
DAILY_END = END
DAILY_TICKERS = ["SPY", "SSO", "UPRO", "QQQ", "QLD", "TQQQ", "SOXL", "TNA"]
TZ = "America/New_York"
WARMUP_BARS = 300
SLIPPAGE = 0.0002
POSITION_FRACTION = 0.10
VOL_THRESHOLDS = (0.125, 0.15, 0.175, 0.20, 0.225, 0.25, 0.30, 0.40, 0.50)


def _flatten_yfinance(raw: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """Normalize yfinance's version-dependent single/multi-index columns."""
    if isinstance(raw.columns, pd.MultiIndex):
        if symbol in raw.columns.get_level_values(-1):
            raw = raw.xs(symbol, axis=1, level=-1)
        else:
            raw.columns = raw.columns.get_level_values(0)
    raw.columns = [str(c).lower().replace(" ", "_") for c in raw.columns]
    return raw[["open", "high", "low", "close", "volume"]].copy()


def _to_eastern(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Keep the exchange clock explicit; never filter UTC hours as if they were ET."""
    idx = pd.DatetimeIndex(index)
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    return idx.tz_convert(TZ)


def load_hourly(refresh: bool = False, csv_path: Optional[str] = None) -> pd.DataFrame:
    """Load a pinned full-session hourly panel from CSV/cache/Yahoo."""
    path = csv_path or CACHE
    if os.path.exists(path) and not refresh:
        df = pd.read_csv(path, index_col=0, parse_dates=True)
    else:
        import yfinance as yf

        raw = yf.download(
            SYMBOL,
            start=START,
            end=END,
            interval="1h",
            auto_adjust=False,
            progress=False,
        )
        if raw.empty:
            raise RuntimeError("Yahoo Finance returned no hourly TQQQ bars")
        df = _flatten_yfinance(raw, SYMBOL)
        if csv_path is None:
            df.to_csv(CACHE)

    df.columns = [str(c).lower().replace(" ", "_") for c in df.columns]
    df = df[["open", "high", "low", "close", "volume"]].astype(float)
    df.index = _to_eastern(df.index)
    df = df[~df.index.duplicated(keep="last")].sort_index()
    df = df.loc[(df.index >= pd.Timestamp(START, tz=TZ))
                & (df.index < pd.Timestamp(END, tz=TZ))]

    # The study is specifically about full-session data.  Fail loudly if a
    # morning-only cache (the historical F13 failure mode) is supplied.
    bars_per_day = pd.Series(1, index=df.index).groupby(df.index.date).sum()
    if len(df) < 2500 or bars_per_day.median() < 6:
        raise RuntimeError(
            "Hourly input is not full-session data: "
            "n=%d, median bars/day=%.1f (need >=2500 and >=6)"
            % (len(df), float(bars_per_day.median()))
        )
    return df


def load_five_min(refresh: bool = False) -> Optional[pd.DataFrame]:
    """Pinned recent 5-minute panel used only to order dual-hit entry hours."""
    if os.path.exists(FIVE_MIN_CACHE) and not refresh:
        df = pd.read_csv(FIVE_MIN_CACHE, index_col=0, parse_dates=True)
    else:
        import yfinance as yf

        try:
            raw = yf.download(
                SYMBOL,
                start=FIVE_MIN_START,
                end=END,
                interval="5m",
                auto_adjust=False,
                progress=False,
            )
        except Exception:
            return None
        if raw.empty:
            # Yahoo's intraday retention window is rolling.  The durable
            # 19-event audit below preserves the result after raw expiry.
            return None
        df = _flatten_yfinance(raw, SYMBOL)
        df.to_csv(FIVE_MIN_CACHE)
    df.columns = [str(c).lower().replace(" ", "_") for c in df.columns]
    df = df[["open", "high", "low", "close", "volume"]].astype(float)
    df.index = _to_eastern(df.index)
    df = df[~df.index.duplicated(keep="last")].sort_index()
    return df.loc[
        (df.index >= pd.Timestamp(FIVE_MIN_START, tz=TZ))
        & (df.index < pd.Timestamp(END, tz=TZ))
        & (df.index.hour * 60 + df.index.minute >= 9 * 60 + 30)
        & (df.index.hour * 60 + df.index.minute < 16 * 60)
    ]


def signal_variant(
    features: pd.DataFrame,
    use_regime_filter: bool,
    allow_shorts: bool,
    trade_hours: Optional[Tuple[int, int]] = None,
) -> pd.DataFrame:
    """Generate a controlled signal variant from one shared feature panel."""
    mode = "%s_HOURLY" % SYMBOL
    out = generate_trades(
        features,
        require_signals=config.ASSETS[mode]["require_signals"],
        use_regime_filter=use_regime_filter,
        use_slope_regime=False,
        longs_only=False,
        trade_hours=trade_hours,
    )
    if not allow_shorts:
        out.loc[out["entry_signal"] < 0, "entry_signal"] = 0
    out.loc[out.index[:WARMUP_BARS], "entry_signal"] = 0
    return out


def signal_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Build the exact current LIVE hourly signal, with a stable warmup."""
    mode = "%s_HOURLY" % SYMBOL
    if getattr(config, "ACTIVE_MODE", None) != mode:
        raise RuntimeError(
            "This study is pinned to ACTIVE_MODE=%s; current=%r"
            % (mode, getattr(config, "ACTIVE_MODE", None))
        )
    features = build_features(df.copy(), timeframe="hourly")
    # live/signals.py returns both signs, but live/trader.py:568-575 applies a
    # second armed-path gate.  Mirror that gate without importing live.*.
    return signal_variant(
        features,
        use_regime_filter=False,
        allow_shorts=bool(getattr(config, "TRADER_ALLOW_SHORTS", False)),
        trade_hours=None,  # input is already regular-session-only
    )


def _prices(direction: int, entry: float, target: float, stop: float) -> Tuple[float, float]:
    if direction == 1:
        return entry * (1 + target), entry * (1 - stop)
    return entry * (1 - target), entry * (1 + stop)


def _gap_stop(direction: int, bar_open: float, stop_price: float) -> bool:
    return bar_open <= stop_price if direction == 1 else bar_open >= stop_price


def _bar_hits(
    direction: int, bar: pd.Series, target_price: float, stop_price: float
) -> Tuple[bool, bool]:
    if direction == 1:
        return bar["high"] >= target_price, bar["low"] <= stop_price
    return bar["low"] <= target_price, bar["high"] >= stop_price


def simulate(
    df: pd.DataFrame,
    target: float,
    stop: float,
    max_bars: int,
    gap_aware: bool,
    one_position: bool,
    scan_entry_bar: bool,
    flatten_eod: bool = False,
    slippage: float = SLIPPAGE,
    entry_bar_ambiguous_target_first: bool = False,
    flatten_before_gap_days: Optional[int] = None,
    flatten_before_dates: Optional[set] = None,
    session_close_prices: Optional[Dict[object, float]] = None,
    session_open_prices: Optional[Dict[object, float]] = None,
) -> pd.DataFrame:
    """Replay signal entries with enough provenance to audit gap-through exits."""
    rows: List[Dict[str, object]] = []
    entry_locs = np.flatnonzero(df["entry_signal"].to_numpy() != 0)
    next_eligible_signal_loc = 0

    for signal_loc in entry_locs:
        signal_loc = int(signal_loc)
        if one_position and signal_loc < next_eligible_signal_loc:
            continue
        entry_loc = signal_loc + 1
        if entry_loc >= len(df):
            continue

        direction = int(df["entry_signal"].iloc[signal_loc])
        entry_price = float(df["open"].iloc[entry_loc])
        target_price, stop_price = _prices(direction, entry_price, target, stop)
        scan_loc = entry_loc if scan_entry_bar else entry_loc + 1
        last_loc = min(scan_loc + max_bars, len(df))
        if scan_loc >= last_loc:
            continue

        exit_return = None
        exit_type = None
        exit_loc = None
        exit_price = None
        gap_through = False
        session_gap = False

        for loc in range(scan_loc, last_loc):
            bar = df.iloc[loc]
            is_session_gap = df.index[loc].date() != df.index[loc - 1].date()
            bar_open = float(bar["open"])
            if (
                session_open_prices is not None
                and is_session_gap
                and loc > entry_loc
            ):
                bar_open = float(
                    session_open_prices.get(df.index[loc].date(), bar_open)
                )
            opens_through_stop = _gap_stop(direction, bar_open, stop_price)

            calendar_gap_days = (
                (df.index[loc].date() - df.index[loc - 1].date()).days
                if is_session_gap else 0
            )
            calendar_flatten = bool(
                flatten_before_gap_days is not None
                and is_session_gap
                and loc > entry_loc
                and calendar_gap_days >= flatten_before_gap_days
            )
            next_session_date = df.index[loc].date()
            risk_flatten = bool(
                flatten_before_dates is not None
                and is_session_gap
                and loc > entry_loc
                and next_session_date in flatten_before_dates
            )
            if (
                (flatten_eod and is_session_gap and loc > entry_loc)
                or calendar_flatten
                or risk_flatten
            ):
                # The previous bar is the last regular-session bar.  This is
                # the explicit "do not carry risk overnight" counterfactual,
                # not an assertion that a MOC order fills exactly at the print.
                exit_loc = loc - 1
                prior_session = df.index[exit_loc].date()
                exit_price = float(
                    session_close_prices.get(
                        prior_session, float(df["close"].iloc[exit_loc])
                    )
                    if session_close_prices is not None
                    else float(df["close"].iloc[exit_loc])
                )
                exit_return = direction * (exit_price - entry_price) / entry_price
                if flatten_eod:
                    exit_type = "eod_flatten"
                elif calendar_flatten:
                    exit_type = "calendar_flatten"
                else:
                    exit_type = "risk_flatten"
                break

            if gap_aware and opens_through_stop:
                exit_price = bar_open
                exit_return = direction * (exit_price - entry_price) / entry_price
                exit_type = "overnight_gap_stop" if is_session_gap else "intraday_gap_stop"
                exit_loc = loc
                gap_through = True
                session_gap = is_session_gap
                break

            target_hit, stop_hit = _bar_hits(
                direction, bar, target_price=target_price, stop_price=stop_price
            )
            if target_hit and stop_hit:
                target_first = bool(
                    entry_bar_ambiguous_target_first and loc == entry_loc
                )
                exit_return = target if target_first else -stop
                exit_type = (
                    "ambiguous_entry_bar_target_first"
                    if target_first else "ambiguous_same_bar"
                )
                exit_price = target_price if target_first else stop_price
                exit_loc = loc
                # In the exact model, retain whether the observed open was
                # already through the stop so it pairs cleanly to gap_aware.
                gap_through = opens_through_stop
                session_gap = is_session_gap and opens_through_stop
                break
            if target_hit:
                exit_return = target
                exit_type = "target_hit"
                exit_price = target_price
                exit_loc = loc
                break
            if stop_hit:
                exit_return = -stop
                exit_type = "stop_hit"
                exit_price = stop_price
                exit_loc = loc
                gap_through = opens_through_stop
                session_gap = is_session_gap and opens_through_stop
                break

        if exit_return is None:
            exit_loc = last_loc - 1
            exit_price = float(df["close"].iloc[exit_loc])
            exit_return = direction * (exit_price - entry_price) / entry_price
            exit_type = "time_exit"

        exit_return -= slippage
        entry_ts = df.index[entry_loc]
        exit_ts = df.index[int(exit_loc)]
        rows.append(
            dict(
                signal_timestamp=df.index[signal_loc],
                entry_timestamp=entry_ts,
                exit_timestamp=exit_ts,
                direction=direction,
                entry_price=entry_price,
                exit_price=float(exit_price),
                return_=float(exit_return),
                exit_type=exit_type,
                held_overnight=entry_ts.date() != exit_ts.date(),
                gap_through_stop=bool(gap_through),
                overnight_gap_stop=bool(session_gap),
                signal_loc=signal_loc,
                exit_loc=int(exit_loc),
            )
        )
        if one_position:
            # A signal observed on the exit bar can be acted on at the next
            # bar, matching the completed-bar -> next-open convention.
            next_eligible_signal_loc = int(exit_loc)

    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.rename(columns={"return_": "return"})
    return out


def engine_crosscheck(df: pd.DataFrame, target: float, stop: float, max_bars: int) -> Dict[str, object]:
    """Prove the custom exact-stop/N+2 overlapping replay matches production."""
    prod = compute_trade_returns(
        df,
        target_gain_pct=target,
        stop_loss_pct=stop,
        max_trade_bars=max_bars,
        slippage_pct=SLIPPAGE,
        worst_case_ambiguity=True,
    ).reset_index(drop=True)
    ours = simulate(
        df,
        target=target,
        stop=stop,
        max_bars=max_bars,
        gap_aware=False,
        one_position=False,
        scan_entry_bar=False,
    ).reset_index(drop=True)
    same_n = len(prod) == len(ours)
    max_abs = (
        float(np.max(np.abs(prod["return"].to_numpy() - ours["return"].to_numpy())))
        if same_n and len(prod) else math.inf
    )
    same_types = same_n and prod["exit_type"].tolist() == ours["exit_type"].tolist()
    same_ts = same_n and pd.to_datetime(prod["timestamp"]).tolist() == \
        pd.to_datetime(ours["signal_timestamp"]).tolist()
    passed = bool(same_n and same_types and same_ts and max_abs < 1e-12)
    if not passed:
        raise AssertionError(
            "custom exact-stop replay does not match compute_trade_returns: "
            "n=%s types=%s ts=%s max_abs=%g" % (same_n, same_types, same_ts, max_abs)
        )
    return dict(
        passed=passed,
        n=len(prod),
        max_abs_return_diff=max_abs,
        same_exit_types=same_types,
        same_signal_timestamps=same_ts,
    )


def equity_metrics(trades: pd.DataFrame, position_fraction: float = POSITION_FRACTION) -> Dict[str, float]:
    r = trades["return"].to_numpy(dtype=float) * position_fraction
    eq = np.cumprod(1.0 + r)
    if len(eq) == 0:
        return dict(n=0, total_return_pct=0.0, max_drawdown_pct=0.0)
    dd = eq / np.maximum.accumulate(np.r_[1.0, eq])[-len(eq):] - 1.0
    return dict(
        n=int(len(r)),
        win_rate_pct=round(float(np.mean(r > 0) * 100), 2),
        mean_trade_bps=round(float(np.mean(r) * 10000), 3),
        total_return_pct=round(float((eq[-1] - 1) * 100), 4),
        max_drawdown_pct=round(float(np.min(dd) * 100), 4),
    )


def raw_overnight_gaps(df: pd.DataFrame) -> Dict[str, object]:
    """Describe all close-to-next-open gaps, independent of the strategy."""
    grouped = df.groupby(df.index.date)
    first = grouped.first()["open"]
    last = grouped.last()["close"]
    dates = list(first.index)
    gaps = []
    for i in range(1, len(dates)):
        gaps.append((dates[i], float(first.iloc[i] / last.iloc[i - 1] - 1.0)))
    vals = np.asarray([x[1] for x in gaps], dtype=float)
    worst = sorted(gaps, key=lambda x: x[1])[:10]
    return dict(
        n=int(len(vals)),
        mean_bps=round(float(vals.mean() * 10000), 2),
        median_bps=round(float(np.median(vals) * 10000), 2),
        pct_le_minus_0_5=round(float(np.mean(vals <= -0.005) * 100), 2),
        pct_le_minus_1=round(float(np.mean(vals <= -0.01) * 100), 2),
        pct_le_minus_2=round(float(np.mean(vals <= -0.02) * 100), 2),
        pct_le_minus_4=round(float(np.mean(vals <= -0.04) * 100), 2),
        pct_ge_plus_0_5=round(float(np.mean(vals >= 0.005) * 100), 2),
        pct_ge_plus_1=round(float(np.mean(vals >= 0.01) * 100), 2),
        pct_ge_plus_2=round(float(np.mean(vals >= 0.02) * 100), 2),
        pct_ge_plus_4=round(float(np.mean(vals >= 0.04) * 100), 2),
        worst=[
            dict(date=str(d), gap_pct=round(g * 100, 3))
            for d, g in worst
        ],
        best=[
            dict(date=str(d), gap_pct=round(g * 100, 3))
            for d, g in sorted(gaps, key=lambda x: x[1], reverse=True)[:10]
        ],
    )


def paired_summary(exact: pd.DataFrame, gap: pd.DataFrame) -> Dict[str, object]:
    if len(exact) != len(gap):
        raise AssertionError("paired replays produced different trade counts")
    if exact["signal_timestamp"].tolist() != gap["signal_timestamp"].tolist():
        raise AssertionError("paired replays diverged on entries")
    delta = gap["return"].to_numpy() - exact["return"].to_numpy()
    affected = np.flatnonzero(np.abs(delta) > 1e-12)
    stop_mask = exact["exit_type"].isin(["stop_hit", "ambiguous_same_bar"]).to_numpy()
    damage = -delta[affected] if len(affected) else np.asarray([], dtype=float)
    events = []
    for i in affected:
        events.append(
            dict(
                signal=str(gap.iloc[i]["signal_timestamp"]),
                entry=str(gap.iloc[i]["entry_timestamp"]),
                exit=str(gap.iloc[i]["exit_timestamp"]),
                direction=int(gap.iloc[i]["direction"]),
                entry_price=round(float(gap.iloc[i]["entry_price"]), 4),
                gap_fill=round(float(gap.iloc[i]["exit_price"]), 4),
                modeled_return_pct=round(float(exact.iloc[i]["return"] * 100), 3),
                gap_aware_return_pct=round(float(gap.iloc[i]["return"] * 100), 3),
                understatement_pp=round(float(-delta[i] * 100), 3),
                overnight=bool(gap.iloc[i]["overnight_gap_stop"]),
            )
        )
    by_direction = {}
    for direction, label in ((1, "long"), (-1, "short")):
        mask = exact["direction"].to_numpy() == direction
        idx = np.flatnonzero(mask & (np.abs(delta) > 1e-12))
        by_direction[label] = dict(
            trades=int(mask.sum()),
            held_overnight=int(exact.loc[mask, "held_overnight"].sum()),
            gap_affected=int(len(idx)),
            cumulative_trade_return_delta_pct=round(float(delta[idx].sum() * 100), 4),
        )
    exit_year = pd.DatetimeIndex(gap["exit_timestamp"]).year
    by_year = {}
    for year in sorted(set(exit_year)):
        mask = exit_year == year
        idx = np.flatnonzero(mask & (np.abs(delta) > 1e-12))
        by_year[str(year)] = dict(
            trades=int(mask.sum()),
            gap_affected=int(len(idx)),
            cumulative_trade_return_delta_pct=round(float(delta[idx].sum() * 100), 4),
        )
    return dict(
        exact=equity_metrics(exact),
        gap_aware=equity_metrics(gap),
        n_held_overnight=int(exact["held_overnight"].sum()),
        n_gap_affected=int(len(affected)),
        n_overnight_gap_stops=int(gap["overnight_gap_stop"].sum()),
        pct_overnight_holds_stopped_at_gap=round(
            float(len(affected) / max(1, exact["held_overnight"].sum()) * 100), 2
        ),
        n_modeled_stop_exits=int(stop_mask.sum()),
        calibrated_mean_stop_slippage_bps=round(
            float(-delta.sum() / max(1, stop_mask.sum()) * 10000), 3
        ),
        gap_damage_pp=dict(
            median=round(float(np.median(damage) * 100), 3) if len(damage) else 0.0,
            p90=round(float(np.percentile(damage, 90) * 100), 3) if len(damage) else 0.0,
            maximum=round(float(np.max(damage) * 100), 3) if len(damage) else 0.0,
        ),
        cumulative_trade_return_delta_pct=round(float(delta.sum() * 100), 4),
        fixed_10pct_capital_delta_pp=round(float(delta.sum() * POSITION_FRACTION * 100), 4),
        by_direction=by_direction,
        by_year=by_year,
        events=events,
    )


def _replay_row(trades: pd.DataFrame) -> Dict[str, object]:
    """Compact row for assumption/mitigation comparisons."""
    entry_bar_mask = (
        trades["exit_loc"].to_numpy(dtype=int)
        == trades["signal_loc"].to_numpy(dtype=int) + 1
    )
    row = dict(equity_metrics(trades))
    row.update(
        held_overnight=int(trades["held_overnight"].sum()),
        overnight_gap_stops=int(trades["overnight_gap_stop"].sum()),
        longs=int((trades["direction"] == 1).sum()),
        shorts=int((trades["direction"] == -1).sum()),
        entry_bar_exits=int(entry_bar_mask.sum()),
        entry_bar_exit_types={
            str(k): int(v)
            for k, v in trades.loc[entry_bar_mask, "exit_type"].value_counts().items()
        },
        exit_types={str(k): int(v) for k, v in trades["exit_type"].value_counts().items()},
    )
    return row


def _wilson_interval(successes: int, n: int) -> Tuple[float, float]:
    """95% Wilson score interval, avoiding a scipy dependency."""
    if n <= 0:
        return 0.0, 0.0
    z = 1.959963984540054
    p = successes / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    radius = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / denom
    return center - radius, center + radius


def _microstructure_ordering(
    ambiguous: pd.DataFrame, five_min: pd.DataFrame
) -> Dict[str, object]:
    """Use 5-minute sub-bars to order target/stop inside dual-hit hourly bars."""
    counts = dict(target_first=0, stop_first=0, unresolved_5m=0, missing=0)
    events = []
    for _, trade in ambiguous.iterrows():
        entry_ts = trade["entry_timestamp"]
        if entry_ts < five_min.index.min() or entry_ts > five_min.index.max():
            continue
        bars = five_min.loc[
            (five_min.index >= entry_ts)
            & (five_min.index < entry_ts + pd.Timedelta(hours=1))
        ]
        target_price, stop_price = _prices(
            int(trade["direction"]), float(trade["entry_price"]), 0.01, 0.005
        )
        outcome = "missing"
        for _, bar in bars.iterrows():
            target_hit, stop_hit = _bar_hits(
                int(trade["direction"]), bar, target_price, stop_price
            )
            if target_hit and stop_hit:
                outcome = "unresolved_5m"
                break
            if target_hit:
                outcome = "target_first"
                break
            if stop_hit:
                outcome = "stop_first"
                break
        counts[outcome] += 1
        events.append(dict(entry=str(entry_ts), outcome=outcome, sub_bars=int(len(bars))))
    durable = pd.read_csv(FIVE_MIN_AUDIT)
    durable_events = durable.to_dict("records")
    if events != durable_events:
        raise AssertionError(
            "5-minute reconstruction differs from durable ordering audit"
        )
    return _ordering_summary(
        events,
        coverage_start=str(five_min.index.min()),
        coverage_end=str(five_min.index.max()),
        n_five_min_bars=int(len(five_min)),
        source="reconstructed from cached/fresh 5-minute bars and matched durable audit",
    )


def _ordering_summary(
    events: List[Dict[str, object]],
    coverage_start: str,
    coverage_end: str,
    n_five_min_bars: int,
    source: str,
) -> Dict[str, object]:
    counts = dict(target_first=0, stop_first=0, unresolved_5m=0, missing=0)
    for event in events:
        counts[str(event["outcome"])] += 1
    resolved = counts["target_first"] + counts["stop_first"]
    lo, hi = _wilson_interval(counts["target_first"], resolved)
    return dict(
        source=source,
        source_panel_sha256=FIVE_MIN_SOURCE_SHA256,
        durable_audit=os.path.relpath(FIVE_MIN_AUDIT, REPO),
        coverage_start=coverage_start,
        coverage_end=coverage_end,
        n_five_min_bars=n_five_min_bars,
        n_hourly_ambiguous_in_coverage=int(sum(counts.values())),
        n_unique_event_dates=int(
            len({pd.Timestamp(event["entry"]).date() for event in events})
        ),
        counts=counts,
        n_resolved=int(resolved),
        target_first_pct_of_resolved=round(
            counts["target_first"] / max(1, resolved) * 100, 2
        ),
        target_first_wilson95_pct=[round(lo * 100, 2), round(hi * 100, 2)],
        events=events,
        interpretation=(
            "recent 5-minute evidence leans stop-first, but the small, clustered sample and "
            "remaining within-5-minute ambiguity are calibration evidence, not a full-history "
            "replacement for tick/order-event replay"
        ),
    )


def _durable_ordering_audit() -> Dict[str, object]:
    durable = pd.read_csv(FIVE_MIN_AUDIT)
    events = durable.to_dict("records")
    return _ordering_summary(
        events,
        coverage_start="2026-05-26 09:30:00-04:00",
        coverage_end="2026-07-22 15:55:00-04:00",
        n_five_min_bars=3120,
        source=(
            "durable derived-event fallback; raw Yahoo 5-minute retention window expired "
            "or data were unavailable"
        ),
    )


def _best_available_ordering(
    five_min_calibration: Dict[str, object]
) -> Dict[str, object]:
    """Apply durable one-minute resolutions to the five-minute event audit."""
    resolutions = pd.read_csv(ONE_MIN_AUDIT).to_dict("records")
    by_entry = {str(event["entry"]): dict(event) for event in five_min_calibration["events"]}
    applied = []
    for row in resolutions:
        entry = str(row["entry"])
        if entry not in by_entry:
            raise AssertionError("one-minute resolution is outside the five-minute audit")
        event = by_entry[entry]
        if event["outcome"] != row["five_min_outcome"]:
            raise AssertionError("one-minute resolution does not match five-minute outcome")
        if row["source_sha256"] != ONE_MIN_SOURCE_SHA256:
            raise AssertionError("one-minute source hash drift")
        event["five_min_outcome"] = event["outcome"]
        event["outcome"] = row["one_min_outcome"]
        event["resolution_interval"] = "1m"
        event["first_stop_minute_et"] = row["first_stop_minute_et"]
        event["first_target_minute_et"] = row["first_target_minute_et"]
        applied.append(
            dict(
                entry=entry,
                five_min_outcome=row["five_min_outcome"],
                one_min_outcome=row["one_min_outcome"],
                first_stop_minute_et=row["first_stop_minute_et"],
                first_target_minute_et=row["first_target_minute_et"],
            )
        )
    events = [by_entry[str(event["entry"])] for event in five_min_calibration["events"]]
    summary = _ordering_summary(
        events,
        coverage_start=five_min_calibration["coverage_start"],
        coverage_end=five_min_calibration["coverage_end"],
        n_five_min_bars=five_min_calibration["n_five_min_bars"],
        source=(
            five_min_calibration["source"]
            + "; augmented by durable one-minute resolution audit"
        ),
    )
    summary.update(
        raw_five_min_counts=five_min_calibration["counts"],
        one_min_resolutions=applied,
        one_min_source_panel_sha256=ONE_MIN_SOURCE_SHA256,
        one_min_durable_audit=os.path.relpath(ONE_MIN_AUDIT, REPO),
        remaining_unresolved_entries=[
            event["entry"]
            for event in events
            if event["outcome"] == "unresolved_5m"
        ],
        retention_note=(
            "Yahoo returned the July 6 one-minute window on 2026-07-23. "
            "June 23-24 were already outside its stated rolling 30-day range."
        ),
    )
    return summary


def _beta_binomial_pmf(n: int, alpha: float, beta: float) -> np.ndarray:
    """Exact beta-binomial predictive mass using only stdlib log-gamma."""
    log_norm = math.lgamma(alpha) + math.lgamma(beta) - math.lgamma(alpha + beta)
    logs = []
    for k in range(n + 1):
        log_choose = (
            math.lgamma(n + 1)
            - math.lgamma(k + 1)
            - math.lgamma(n - k + 1)
        )
        log_beta = (
            math.lgamma(k + alpha)
            + math.lgamma(n - k + beta)
            - math.lgamma(n + alpha + beta)
        )
        logs.append(log_choose + log_beta - log_norm)
    logs_arr = np.asarray(logs, dtype=float)
    mass = np.exp(logs_arr - logs_arr.max())
    return mass / mass.sum()


def _weighted_quantiles(
    values: np.ndarray, mass: np.ndarray, quantiles: Tuple[float, ...]
) -> List[float]:
    cdf = np.cumsum(mass)
    return [
        float(values[min(len(values) - 1, int(np.searchsorted(cdf, q)))])
        for q in quantiles
    ]


def _minimum_wilson_n_below(
    observed_rate: float, upper_threshold: float, max_n: int = 100000
) -> Optional[int]:
    """First n whose rounded-rate Wilson95 upper bound clears a threshold."""
    for n in range(10, max_n + 1):
        successes = int(round(observed_rate * n))
        _, upper = _wilson_interval(successes, n)
        if upper < upper_threshold:
            return n
    return None


def _minimum_wilson_n_separated(
    observed_rate: float, threshold: float, max_n: int = 100000
) -> Optional[int]:
    """First n whose Wilson95 interval lies wholly on the observed side."""
    for n in range(10, max_n + 1):
        successes = int(round(observed_rate * n))
        lower, upper = _wilson_interval(successes, n)
        if observed_rate < threshold and upper < threshold:
            return n
        if observed_rate > threshold and lower > threshold:
            return n
    return None


def _calibration_subset(
    calibration: Dict[str, object], entry_timestamps: set
) -> Dict[str, object]:
    events = [
        event
        for event in calibration["events"]
        if event["entry"] in entry_timestamps
    ]
    return _ordering_summary(
        events,
        coverage_start=calibration["coverage_start"],
        coverage_end=calibration["coverage_end"],
        n_five_min_bars=calibration["n_five_min_bars"],
        source=calibration["source"] + "; filtered to the one-position path",
    )


def _calibration_path_decision(
    immediate: pd.DataFrame,
    entry_mask: np.ndarray,
    calibration: Dict[str, object],
    path_label: str,
) -> Dict[str, object]:
    """Translate lower-timeframe ordering evidence into a decision threshold."""
    ambiguous_mask = entry_mask & (
        immediate["exit_type"].to_numpy() == "ambiguous_same_bar"
    )
    n_ambiguous = int(ambiguous_mask.sum())
    returns = immediate["return"].to_numpy(dtype=float)
    observed_ambiguous_returns = returns[ambiguous_mask]
    if not np.allclose(observed_ambiguous_returns, -0.005 - SLIPPAGE):
        raise AssertionError("unexpected conservative return on ambiguous entry bars")

    base_growth = float(np.prod(1.0 + returns * POSITION_FRACTION))
    stop_growth = 1.0 + (-0.005 - SLIPPAGE) * POSITION_FRACTION
    target_growth = 1.0 + (0.01 - SLIPPAGE) * POSITION_FRACTION
    ratio = target_growth / stop_growth
    terminal_by_target_count = np.asarray(
        [base_growth * ratio ** k - 1.0 for k in range(n_ambiguous + 1)],
        dtype=float,
    )
    break_even_count = next(
        k for k, value in enumerate(terminal_by_target_count) if value >= 0
    )
    break_even_rate = break_even_count / n_ambiguous

    counts = calibration["counts"]
    unresolved = int(counts["unresolved_5m"])
    scenarios = [
        ("exclude_unresolved", int(counts["target_first"]), int(counts["stop_first"])),
        (
            "unresolved_as_stop_first",
            int(counts["target_first"]),
            int(counts["stop_first"] + unresolved),
        ),
        (
            "unresolved_as_target_first",
            int(counts["target_first"] + unresolved),
            int(counts["stop_first"]),
        ),
    ]
    posterior_rows = []
    for label, successes, failures in scenarios:
        alpha, beta = successes + 0.5, failures + 0.5
        mass = _beta_binomial_pmf(n_ambiguous, alpha, beta)
        q = _weighted_quantiles(
            terminal_by_target_count, mass, (0.025, 0.5, 0.975)
        )
        posterior_rows.append(
            dict(
                scenario=label,
                resolved_target_first=successes,
                resolved_stop_first=failures,
                jeffreys_posterior_mean_target_first_pct=round(
                    alpha / (alpha + beta) * 100, 2
                ),
                predictive_probability_total_return_positive_pct=round(
                    float(mass[break_even_count:].sum() * 100), 2
                ),
                predictive_total_return_pct=dict(
                    p025=round(q[0] * 100, 3),
                    median=round(q[1] * 100, 3),
                    p975=round(q[2] * 100, 3),
                ),
            )
        )

    resolved = int(counts["target_first"] + counts["stop_first"])
    current_rate = counts["target_first"] / max(1, resolved)
    assumed_rates = sorted({0.20, 0.25, 0.30, round(current_rate, 6)})
    sample_size_rows = []
    for assumed_rate in assumed_rates:
        needed = _minimum_wilson_n_separated(assumed_rate, break_even_rate)
        sample_size_rows.append(
            dict(
                assumed_target_first_pct=round(assumed_rate * 100, 4),
                minimum_resolved_events_for_wilson95_interval_to_clear_break_even=needed,
            )
        )
    observed_needed = _minimum_wilson_n_separated(current_rate, break_even_rate)
    entry_times = pd.DatetimeIndex(immediate["entry_timestamp"])
    observed_years = max(
        (entry_times.max() - entry_times.min()).total_seconds()
        / (365.25 * 24 * 60 * 60),
        1 / 365.25,
    )
    ambiguous_per_year = n_ambiguous / max(observed_years, 1e-12)
    return dict(
        path=path_label,
        n_unknown_full_history_dual_hit_entries=n_ambiguous,
        minimum_target_first_count_for_nonnegative_terminal_return=break_even_count,
        break_even_target_first_pct=round(break_even_rate * 100, 3),
        current_resolved_five_min_events=resolved,
        current_resolved_target_first_events=int(counts["target_first"]),
        current_resolved_stop_first_events=int(counts["stop_first"]),
        current_unresolved_lower_timeframe_events=int(counts["unresolved_5m"]),
        current_resolved_target_first_pct=calibration[
            "target_first_pct_of_resolved"
        ],
        posterior_predictive_sensitivity=posterior_rows,
        value_of_information=(
            "If the currently observed %.2f%% target-first rate persisted, about %d "
            "resolved dual-hit events would be needed before a Wilson95 interval lay wholly "
            "on its side of the %.3f%% break-even rate—roughly %.1f years at this path's "
            "full-history ambiguous-event pace."
            % (
                current_rate * 100,
                observed_needed,
                break_even_rate * 100,
                observed_needed / max(ambiguous_per_year, 1e-12),
            )
        ),
        sample_size_sensitivity=sample_size_rows,
        assumptions=(
            "Beta-binomial rows use a Jeffreys prior and assume the recent resolved events "
            "are exchangeable with all 157 historical dual-hit entries. Terminal return "
            "depends only on target-first count, but drawdown depends on which dates resolve "
            "which way and is intentionally not inferred."
        ),
        decision_gap_pp=round((current_rate - break_even_rate) * 100, 3),
    )


def entry_bar_bracket_effect(
    sig: pd.DataFrame, five_min: Optional[pd.DataFrame] = None
) -> Dict[str, object]:
    """Pair identical entries to isolate N+2 versus entry-bar bracket scanning."""
    target, stop = 0.01, 0.005
    bars = int(getattr(config, "MAX_TRADE_BARS_LIVE", 10))
    delayed = simulate(
        sig, target, stop, bars,
        gap_aware=False, one_position=False, scan_entry_bar=False,
    ).reset_index(drop=True)
    immediate = simulate(
        sig, target, stop, bars,
        gap_aware=False, one_position=False, scan_entry_bar=True,
    ).reset_index(drop=True)
    immediate_target_first = simulate(
        sig, target, stop, bars,
        gap_aware=False, one_position=False, scan_entry_bar=True,
        entry_bar_ambiguous_target_first=True,
    ).reset_index(drop=True)
    if len(delayed) != len(immediate):
        raise AssertionError("entry-bar paired replays produced different trade counts")
    if delayed["signal_timestamp"].tolist() != immediate["signal_timestamp"].tolist():
        raise AssertionError("entry-bar paired replays diverged on entries")

    delta = immediate["return"].to_numpy() - delayed["return"].to_numpy()
    entry_mask = (
        immediate["exit_loc"].to_numpy(dtype=int)
        == immediate["signal_loc"].to_numpy(dtype=int) + 1
    )
    changed = np.abs(delta) > 1e-12
    transitions = {}
    paired = pd.DataFrame(
        {
            "delayed": delayed.loc[entry_mask, "exit_type"].to_numpy(),
            "immediate": immediate.loc[entry_mask, "exit_type"].to_numpy(),
        }
    )
    for (old, new), count in paired.value_counts().items():
        transitions["%s -> %s" % (old, new)] = int(count)
    result = dict(
        design=(
            "overlapping paired replay on identical long-only signals; exact fills in both "
            "arms; the sole change is first bracket scan N+2 versus entry bar N+1"
        ),
        delayed_n_plus_2=equity_metrics(delayed),
        immediate_entry_bar=equity_metrics(immediate),
        immediate_entry_bar_target_first_bound=equity_metrics(immediate_target_first),
        n_paired=int(len(immediate)),
        n_entry_bar_exits=int(entry_mask.sum()),
        pct_entry_bar_exits=round(float(entry_mask.mean() * 100), 2),
        n_return_changed=int(changed.sum()),
        entry_bar_exit_types={
            str(k): int(v)
            for k, v in immediate.loc[entry_mask, "exit_type"].value_counts().items()
        },
        entry_bar_transition_counts=transitions,
        entry_bar_immediate_mean_return_pct=round(
            float(immediate.loc[entry_mask, "return"].mean() * 100), 4
        ),
        same_entries_delayed_mean_return_pct=round(
            float(delayed.loc[entry_mask, "return"].mean() * 100), 4
        ),
        cumulative_trade_return_delta_pct=round(float(delta.sum() * 100), 4),
        fixed_10pct_first_order_delta_pp=round(
            float(delta.sum() * POSITION_FRACTION * 100), 4
        ),
        ordering_bound_total_return_pct=[
            equity_metrics(immediate)["total_return_pct"],
            equity_metrics(immediate_target_first)["total_return_pct"],
        ],
        ordering_bound_interpretation=(
            "the bounds straddle zero, so hourly OHLC establishes a material execution-model "
            "mismatch but cannot establish the return sign without lower-timeframe ordering data"
        ),
        caveat=(
            "hourly OHLC establishes that the threshold was crossed after the entry open, "
            "but cannot order target versus stop when both occur in that hour; those bars use "
            "the repository's conservative worst-case stop convention"
        ),
    )
    ambiguous = immediate.loc[
        entry_mask & (immediate["exit_type"] == "ambiguous_same_bar")
    ].copy()
    if five_min is not None:
        calibration = _microstructure_ordering(
            ambiguous, five_min
        )
    else:
        calibration = _durable_ordering_audit()
    result["five_min_ordering_calibration"] = calibration
    best_calibration = _best_available_ordering(calibration)
    result["best_available_ordering_calibration"] = best_calibration
    one_position_exact = simulate(
        sig, target, stop, bars,
        gap_aware=False, one_position=True, scan_entry_bar=True,
    ).reset_index(drop=True)
    one_position_gap = simulate(
        sig, target, stop, bars,
        gap_aware=True, one_position=True, scan_entry_bar=True,
    ).reset_index(drop=True)
    one_position_entry_mask = (
        one_position_exact["exit_loc"].to_numpy(dtype=int)
        == one_position_exact["signal_loc"].to_numpy(dtype=int) + 1
    )
    one_position_ambiguous_entries = {
        str(ts)
        for ts in one_position_exact.loc[
            one_position_entry_mask
            & (one_position_exact["exit_type"] == "ambiguous_same_bar"),
            "entry_timestamp",
        ]
    }
    one_position_calibration = _calibration_subset(
        best_calibration, one_position_ambiguous_entries
    )
    result["calibration_decision"] = dict(
        paired_overlap_diagnostic=_calibration_path_decision(
            immediate,
            entry_mask,
            best_calibration,
            "paired overlapping exact-stop diagnostic",
        ),
        one_position_exact=_calibration_path_decision(
            one_position_exact,
            one_position_entry_mask,
            one_position_calibration,
            "one-position exact-stop path",
        ),
        one_position_gap_aware=_calibration_path_decision(
            one_position_gap,
            one_position_entry_mask,
            one_position_calibration,
            "one-position open-aware gap path",
        ),
        decision=(
            "Entry ordering can plausibly change the sign of the exact-stop diagnostic, "
            "but the gap-aware live-shaped path requires 52.17% target-first. The best "
            "available lower-timeframe audit now includes one one-minute resolution in "
            "addition to the five-minute evidence. Posterior-predictive probabilities "
            "remain model-based sensitivities, not proof of negative alpha."
        ),
    )
    return result


def execution_waterfall(
    df: pd.DataFrame, five_min: Optional[pd.DataFrame] = None
) -> Dict[str, object]:
    """Cumulative decomposition from current runner semantics to live-shaped risk."""
    features_et = build_features(df.copy(), timeframe="hourly")
    # fetch_yfinance() strips tz after converting to UTC.  Reproduce the clock
    # that main.py's (9,16) entry filter currently sees without changing prices.
    features_utc = features_et.copy()
    features_utc.index = features_utc.index.tz_convert("UTC").tz_localize(None)

    runner_sig = signal_variant(
        features_utc, use_regime_filter=True, allow_shorts=True, trade_hours=(9, 16)
    )
    full_regime_sig = signal_variant(
        features_et, use_regime_filter=True, allow_shorts=True, trade_hours=(9, 16)
    )
    no_regime_sig = signal_variant(
        features_et, use_regime_filter=False, allow_shorts=True, trade_hours=(9, 16)
    )
    live_sig = signal_variant(
        features_et, use_regime_filter=False, allow_shorts=False, trade_hours=(9, 16)
    )

    specs = [
        (
            "0_current_runner_shape",
            runner_sig, int(getattr(config, "MAX_TRADE_BARS", 8)),
            False, False, False,
            "UTC-naive 9-16 gate + hourly regime ON + shorts + overlap + N+2 + exact stop",
        ),
        (
            "1_live_hold_cap",
            runner_sig, int(getattr(config, "MAX_TRADE_BARS_LIVE", 10)),
            False, False, False,
            "only change: 8 -> 10 bar cap",
        ),
        (
            "2_exchange_clock",
            full_regime_sig, int(getattr(config, "MAX_TRADE_BARS_LIVE", 10)),
            False, False, False,
            "only change: 9-16 interpreted in America/New_York (all RTH entry bars)",
        ),
        (
            "3_hourly_regime_off",
            no_regime_sig, int(getattr(config, "MAX_TRADE_BARS_LIVE", 10)),
            False, False, False,
            "only change: live's USE_REGIME_FILTER_HOURLY=False",
        ),
        (
            "4_live_short_gate",
            live_sig, int(getattr(config, "MAX_TRADE_BARS_LIVE", 10)),
            False, False, False,
            "only change: TRADER_ALLOW_SHORTS=False",
        ),
        (
            "5_one_position",
            live_sig, int(getattr(config, "MAX_TRADE_BARS_LIVE", 10)),
            True, False, False,
            "only change: one open position at a time",
        ),
        (
            "6_entry_bar_bracket",
            live_sig, int(getattr(config, "MAX_TRADE_BARS_LIVE", 10)),
            True, True, False,
            "only change: bracket active on entry bar (not N+2)",
        ),
        (
            "7_open_aware_stop",
            live_sig, int(getattr(config, "MAX_TRADE_BARS_LIVE", 10)),
            True, True, True,
            "only change: an open through stop fills at the open",
        ),
    ]
    rows = []
    for name, sig, bars, one_pos, entry_scan, gap_aware, change in specs:
        trades = simulate(
            sig, target=0.01, stop=0.005, max_bars=bars,
            gap_aware=gap_aware, one_position=one_pos, scan_entry_bar=entry_scan,
        )
        row = dict(step=name, change=change)
        row.update(_replay_row(trades))
        rows.append(row)
    return dict(
        accounting="all rows use fixed 10% sequential compounding for comparability; "
                   "overlapping rows are diagnostic signal-trade accounting, not deployable capital paths",
        entry_bar_paired_effect=entry_bar_bracket_effect(live_sig, five_min),
        rows=rows,
    )


def _cutoff_signal(sig: pd.DataFrame, cutoff_hour: int) -> pd.DataFrame:
    """Block a completed-bar signal at/after cutoff_hour ET."""
    out = sig.copy()
    out.loc[out.index.hour >= cutoff_hour, "entry_signal"] = 0
    return out


def gap_calendar_attribution(
    sig: pd.DataFrame, exact: pd.DataFrame, gap: pd.DataFrame
) -> Dict[str, object]:
    """Attribute paired gap damage to known session-calendar spacing."""
    if exact["signal_timestamp"].tolist() != gap["signal_timestamp"].tolist():
        raise AssertionError("gap attribution requires identical paired entries")
    delta = gap["return"].to_numpy() - exact["return"].to_numpy()
    affected = np.flatnonzero(np.abs(delta) > 1e-12)
    events = []
    for i in affected:
        loc = int(gap.iloc[i]["exit_loc"])
        calendar_days = (
            sig.index[loc].date() - sig.index[loc - 1].date()
        ).days
        events.append(
            dict(
                date=str(sig.index[loc].date()),
                open_weekday=sig.index[loc].day_name(),
                calendar_gap_days=int(calendar_days),
                damage_pp=round(float(-delta[i] * 100), 6),
            )
        )
    total = sum(event["damage_pp"] for event in events)
    by_days = {}
    for days in sorted({event["calendar_gap_days"] for event in events}):
        rows = [event for event in events if event["calendar_gap_days"] == days]
        damage = sum(row["damage_pp"] for row in rows)
        by_days[str(days)] = dict(
            events=int(len(rows)),
            cumulative_trade_damage_pp=round(damage, 4),
            damage_share_pct=round(damage / max(total, 1e-12) * 100, 2),
            median_damage_pp=round(float(np.median([r["damage_pp"] for r in rows])), 3),
            maximum_damage_pp=round(max(r["damage_pp"] for r in rows), 3),
        )
    by_weekday = {}
    for weekday in ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday"):
        rows = [event for event in events if event["open_weekday"] == weekday]
        if rows:
            damage = sum(row["damage_pp"] for row in rows)
            by_weekday[weekday] = dict(
                events=int(len(rows)),
                cumulative_trade_damage_pp=round(damage, 4),
                damage_share_pct=round(damage / max(total, 1e-12) * 100, 2),
            )
    ranked = sorted(events, key=lambda row: row["damage_pp"], reverse=True)
    concentration = {}
    for k in (1, 3, 5, 10):
        concentration["top_%d" % k] = round(
            sum(row["damage_pp"] for row in ranked[:k])
            / max(total, 1e-12)
            * 100,
            2,
        )
    return dict(
        total_events=int(len(events)),
        cumulative_trade_damage_pp=round(total, 4),
        by_calendar_gap_days=by_days,
        by_open_weekday=by_weekday,
        damage_concentration_pct=concentration,
        events=ranked,
    )


def mitigation_frontier(
    sig: pd.DataFrame,
    session_close_prices: Optional[Dict[object, float]] = None,
) -> Dict[str, object]:
    """Risk-control frontier; descriptive, explicitly not a return optimizer."""
    target, stop = 0.01, 0.005
    bars = int(getattr(config, "MAX_TRADE_BARS_LIVE", 10))
    baseline_exact = simulate(
        sig, target, stop, bars,
        gap_aware=False, one_position=True, scan_entry_bar=True,
    )
    baseline = simulate(
        sig, target, stop, bars,
        gap_aware=True, one_position=True, scan_entry_bar=True,
    )
    calendar_attribution = gap_calendar_attribution(sig, baseline_exact, baseline)
    base_row = _replay_row(baseline)
    rows = [
        dict(
            policy="hold_overnight",
            description="current behavior; no signal cutoff",
            **base_row,
        )
    ]
    for cutoff in (12, 13, 14, 15):
        trades = simulate(
            _cutoff_signal(sig, cutoff), target, stop, bars,
            gap_aware=True, one_position=True, scan_entry_bar=True,
        )
        row = _replay_row(trades)
        rows.append(
            dict(
                policy="block_signals_at_or_after_%02d00_ET" % cutoff,
                description="entry prevention only; existing positions may still cross the close",
                trades_retained_pct=round(row["n"] / max(1, base_row["n"]) * 100, 2),
                gap_reduction_pct=round(
                    (1 - row["overnight_gap_stops"]
                     / max(1, base_row["overnight_gap_stops"])) * 100, 2
                ),
                **row,
            )
        )
    for min_gap_days, label in (
        (4, "flatten_before_4plus_calendar_day_closure"),
        (3, "flatten_before_weekend_or_longer_closure"),
        (2, "flatten_before_any_nonconsecutive_session"),
    ):
        trades = simulate(
            sig, target, stop, bars,
            gap_aware=True, one_position=True, scan_entry_bar=True,
            flatten_before_gap_days=min_gap_days,
            session_close_prices=session_close_prices,
        )
        row = _replay_row(trades)
        calendar_exits = int((trades["exit_type"] == "calendar_flatten").sum())
        improvement_decimal = (
            row["total_return_pct"] - base_row["total_return_pct"]
        ) / 100.0
        rows.append(
            dict(
                policy=label,
                description=(
                    "calendar-known partial flatten; existing position closes before a "
                    "scheduled session gap of at least %d calendar days" % min_gap_days
                ),
                calendar_flatten_exits=calendar_exits,
                trades_retained_pct=round(row["n"] / max(1, base_row["n"]) * 100, 2),
                gap_reduction_pct=round(
                    (1 - row["overnight_gap_stops"]
                     / max(1, base_row["overnight_gap_stops"])) * 100, 2
                ),
                direct_gap_damage_share_targeted_pct=round(
                    sum(
                        event["damage_pp"]
                        for event in calendar_attribution["events"]
                        if event["calendar_gap_days"] >= min_gap_days
                    )
                    / max(
                        calendar_attribution["cumulative_trade_damage_pp"], 1e-12
                    )
                    * 100,
                    2,
                ),
                first_order_break_even_extra_cost_bps_per_calendar_exit=round(
                    improvement_decimal
                    / max(1, calendar_exits)
                    / POSITION_FRACTION
                    * 10000,
                    2,
                ),
                **row,
            )
        )
    eod = simulate(
        sig, target, stop, bars,
        gap_aware=True, one_position=True, scan_entry_bar=True, flatten_eod=True,
        session_close_prices=session_close_prices,
    )
    eod_row = _replay_row(eod)
    eod_improvement_decimal = (
        eod_row["total_return_pct"] - base_row["total_return_pct"]
    ) / 100.0
    n_eod_exits = int((eod["exit_type"] == "eod_flatten").sum())
    rows.append(
        dict(
            policy="flatten_end_of_day",
            description="close every surviving position at official daily close proxy",
            trades_retained_pct=round(eod_row["n"] / max(1, base_row["n"]) * 100, 2),
            gap_reduction_pct=100.0,
            eod_exits=n_eod_exits,
            first_order_break_even_extra_cost_bps_per_eod_exit=round(
                eod_improvement_decimal
                / max(1, n_eod_exits)
                / POSITION_FRACTION
                * 10000,
                2,
            ),
            **eod_row,
        )
    )
    for row in rows:
        if row["policy"] == "hold_overnight":
            row.update(
                gap_reduction_pct=0.0,
                maxdd_improvement_pp=0.0,
                total_return_delta_pp=0.0,
                risk_gate_pass=False,
            )
            continue
        dd_improvement = row["max_drawdown_pct"] - base_row["max_drawdown_pct"]
        return_delta = row["total_return_pct"] - base_row["total_return_pct"]
        row.update(
            maxdd_improvement_pp=round(dd_improvement, 4),
            total_return_delta_pp=round(return_delta, 4),
            risk_gate_pass=bool(
                row["gap_reduction_pct"] >= 50.0
                and dd_improvement >= 2.0
                and return_delta >= -1.0
            ),
        )
        if row["policy"].startswith("block_signals"):
            row["selection_warning"] = (
                "in-sample signal suppression changes the opportunity set and overlaps the "
                "known morning-only selection failure; do not interpret as validated alpha"
            )
        elif row["policy"] == "flatten_end_of_day":
            row["selection_warning"] = (
                "mechanism-pure risk control, but official daily close is only a MOC fill proxy and "
                "the incremental turnover/cost is not modeled"
            )
        else:
            row["selection_warning"] = (
                "calendar-known partial exposure removal, but the official close is a MOC fill "
                "proxy and later opportunity-set feedback remains in-sample"
            )

    # Risk-only stop surface.  Stops >= target are deliberately marked
    # non-production-valid; they answer whether width bounds the jump, not
    # whether that reward/risk is a sensible strategy.
    stop_rows = []
    for stop_pct in (0.0025, 0.005, 0.0075, 0.01, 0.015, 0.02, 0.03):
        exact = simulate(
            sig, target, stop_pct, bars,
            gap_aware=False, one_position=True, scan_entry_bar=True,
        )
        gap = simulate(
            sig, target, stop_pct, bars,
            gap_aware=True, one_position=True, scan_entry_bar=True,
        )
        ps = paired_summary(exact, gap)
        stop_rows.append(
            dict(
                stop_pct=round(stop_pct * 100, 2),
                production_valid=bool(stop_pct < target),
                trades=ps["exact"]["n"],
                held_overnight=ps["n_held_overnight"],
                gap_stops=ps["n_gap_affected"],
                exact_total_return_pct=ps["exact"]["total_return_pct"],
                gap_total_return_pct=ps["gap_aware"]["total_return_pct"],
                exact_maxdd_pct=ps["exact"]["max_drawdown_pct"],
                gap_maxdd_pct=ps["gap_aware"]["max_drawdown_pct"],
                fixed10_damage_pp=ps["fixed_10pct_capital_delta_pp"],
                conditional_gap_median_pp=ps["gap_damage_pp"]["median"],
                conditional_gap_max_pp=ps["gap_damage_pp"]["maximum"],
            )
        )

    # Calendar stability: no pooling can turn three periods into independent
    # regimes, but the sign and concentration of damage should be visible.
    exact = baseline_exact
    gap = simulate(
        sig, target, stop, bars,
        gap_aware=True, one_position=True, scan_entry_bar=True,
    )
    calendar = {}
    for year in (2024, 2025, 2026):
        em = pd.DatetimeIndex(exact["exit_timestamp"]).year == year
        gm = pd.DatetimeIndex(gap["exit_timestamp"]).year == year
        ex = exact.loc[em].reset_index(drop=True)
        ga = gap.loc[gm].reset_index(drop=True)
        calendar[str(year)] = dict(
            exact=equity_metrics(ex),
            gap_aware=equity_metrics(ga),
            gap_stops=int(ga["overnight_gap_stop"].sum()),
            held_overnight=int(ga["held_overnight"].sum()),
        )

    gap_events = gap[gap["overnight_gap_stop"]].copy()
    attribution = {}
    for hour, grp in gap_events.groupby(pd.DatetimeIndex(gap_events["entry_timestamp"]).hour):
        attribution[str(int(hour))] = int(len(grp))
    close_source_sensitivity = []
    if session_close_prices is not None:
        close_specs = [
            ("flatten_before_4plus_calendar_day_closure", False, 4),
            ("flatten_before_weekend_or_longer_closure", False, 3),
            ("flatten_before_any_nonconsecutive_session", False, 2),
            ("flatten_end_of_day", True, None),
        ]
        for policy, flatten_all, min_days in close_specs:
            hourly_proxy = simulate(
                sig, target, stop, bars,
                gap_aware=True, one_position=True, scan_entry_bar=True,
                flatten_eod=flatten_all,
                flatten_before_gap_days=min_days,
            )
            official_proxy = simulate(
                sig, target, stop, bars,
                gap_aware=True, one_position=True, scan_entry_bar=True,
                flatten_eod=flatten_all,
                flatten_before_gap_days=min_days,
                session_close_prices=session_close_prices,
            )
            hm, om = equity_metrics(hourly_proxy), equity_metrics(official_proxy)
            close_source_sensitivity.append(
                dict(
                    policy=policy,
                    last_hourly_bar=hm,
                    official_daily_close=om,
                    official_minus_hourly_total_return_pp=round(
                        om["total_return_pct"] - hm["total_return_pct"], 4
                    ),
                    official_minus_hourly_maxdd_pp=round(
                        om["max_drawdown_pct"] - hm["max_drawdown_pct"], 4
                    ),
                )
            )
    return dict(
        pre_registered_read=(
            "A mitigation is operationally interesting only if it removes >=50% of gap stops, "
            "improves maxDD by >=2pp, and does not reduce observed total return by >1pp versus "
            "the already-negative gap-aware baseline. This is a risk gate, not an alpha selection."
        ),
        decision_rule=(
            "Passing the risk gate is necessary, not sufficient. Prefer a policy that directly "
            "removes overnight exposure over an in-sample time cutoff that selects different trades."
        ),
        policy_rows=rows,
        stop_width_rows=stop_rows,
        calendar_slices=calendar,
        gap_events_by_entry_hour_et=attribution,
        calendar_gap_attribution=calendar_attribution,
        close_proxy_sensitivity=close_source_sensitivity,
    )


def load_daily_panel(refresh: bool = False) -> pd.DataFrame:
    """Pinned daily OHLC panel for long-history, cross-instrument gap evidence."""
    if os.path.exists(DAILY_CACHE) and not refresh:
        panel = pd.read_csv(DAILY_CACHE, index_col=0, parse_dates=True)
        return panel.sort_index()

    import yfinance as yf

    raw = yf.download(
        DAILY_TICKERS,
        start=DAILY_START,
        end=DAILY_END,
        interval="1d",
        auto_adjust=False,
        progress=False,
        group_by="column",
    )
    if raw.empty:
        raise RuntimeError("Yahoo Finance returned no long-history daily panel")
    parts = []
    for ticker in DAILY_TICKERS:
        one = _flatten_yfinance(raw, ticker)[["open", "close"]]
        one.columns = ["%s_open" % ticker, "%s_close" % ticker]
        parts.append(one)
    panel = pd.concat(parts, axis=1).sort_index()
    if panel.index.tz is not None:
        panel.index = panel.index.tz_convert(None)
    panel.to_csv(DAILY_CACHE)
    return panel


def _daily_gap(panel: pd.DataFrame, ticker: str) -> pd.Series:
    out = panel["%s_open" % ticker] / panel["%s_close" % ticker].shift(1) - 1.0
    return out.replace([np.inf, -np.inf], np.nan).dropna()


def _tail_stats(g: pd.Series) -> Dict[str, object]:
    x = g.to_numpy(dtype=float)
    k = max(1, int(math.ceil(len(x) * 0.01)))
    sx = np.sort(x)
    q = np.percentile(x, [0, 1, 5, 50, 95, 99, 100])
    return dict(
        n=int(len(x)),
        start=str(g.index[0].date()),
        end=str(g.index[-1].date()),
        worst_date=str(g.idxmin().date()),
        best_date=str(g.idxmax().date()),
        mean_bps=round(float(x.mean() * 10000), 2),
        q_min_pct=round(float(q[0] * 100), 3),
        q01_pct=round(float(q[1] * 100), 3),
        q05_pct=round(float(q[2] * 100), 3),
        median_pct=round(float(q[3] * 100), 3),
        q95_pct=round(float(q[4] * 100), 3),
        q99_pct=round(float(q[5] * 100), 3),
        q_max_pct=round(float(q[6] * 100), 3),
        expected_shortfall_1pct=round(float(sx[:k].mean() * 100), 3),
        down_0_5_pct=round(float(np.mean(x <= -0.005) * 100), 2),
        down_1_pct=round(float(np.mean(x <= -0.01) * 100), 2),
        down_2_pct=round(float(np.mean(x <= -0.02) * 100), 2),
        down_4_pct=round(float(np.mean(x <= -0.04) * 100), 2),
        down_8_pct=round(float(np.mean(x <= -0.08) * 100), 2),
        up_4_pct=round(float(np.mean(x >= 0.04) * 100), 2),
    )


def _pair_scaling(panel: pd.DataFrame, base: str, leveraged: str) -> Dict[str, object]:
    pair = pd.concat(
        [_daily_gap(panel, base).rename("base"), _daily_gap(panel, leveraged).rename("lev")],
        axis=1,
    ).dropna()
    x = pair["base"].to_numpy()
    y = pair["lev"].to_numpy()
    X = np.column_stack([np.ones(len(x)), x])
    alpha, beta = np.linalg.lstsq(X, y, rcond=None)[0]
    pred = alpha + beta * x
    resid = y - pred
    r2 = 1 - float(np.sum(resid ** 2) / np.sum((y - y.mean()) ** 2))
    return dict(
        base=base,
        leveraged=leveraged,
        n=int(len(pair)),
        alpha_bps=round(float(alpha * 10000), 3),
        beta=round(float(beta), 3),
        r2=round(r2, 4),
        median_abs_gap_ratio=round(
            float(np.median(np.abs(y)) / np.median(np.abs(x))), 3
        ),
        q01_loss_ratio=round(
            float(abs(np.percentile(y, 1)) / abs(np.percentile(x, 1))), 3
        ),
        residual_q01_pct=round(float(np.percentile(resid, 1) * 100), 3),
        residual_min_pct=round(float(resid.min() * 100), 3),
    )


def cross_instrument_history(panel: pd.DataFrame) -> Dict[str, object]:
    """Long-history evidence that jump risk scales with leverage, not this signal."""
    stats = {ticker: _tail_stats(_daily_gap(panel, ticker)) for ticker in DAILY_TICKERS}
    scaling = [
        _pair_scaling(panel, "SPY", "SSO"),
        _pair_scaling(panel, "SPY", "UPRO"),
        _pair_scaling(panel, "QQQ", "QLD"),
        _pair_scaling(panel, "QQQ", "TQQQ"),
    ]
    eras = {
        "covid_2020": ("2020-02-15", "2020-04-30"),
        "inflation_2022": ("2022-01-01", "2022-12-31"),
        "recent_2025_2026": ("2025-01-01", "2026-07-22"),
    }
    era_rows = {}
    for era, (start, end) in eras.items():
        era_rows[era] = {}
        for ticker in ("UPRO", "TQQQ", "SOXL", "TNA"):
            g = _daily_gap(panel, ticker).loc[start:end]
            era_rows[era][ticker] = dict(
                n=int(len(g)),
                worst_pct=round(float(g.min() * 100), 3),
                worst_date=str(g.idxmin().date()),
                down_2_count=int((g <= -0.02).sum()),
                down_4_count=int((g <= -0.04).sum()),
                expected_shortfall_5pct=round(
                    float(g.nsmallest(max(1, int(math.ceil(len(g) * 0.05)))).mean() * 100), 3
                ),
            )
    tqqq = stats["TQQQ"]
    position_rows = []
    for fraction in (0.02, 0.05, 0.10, 0.20):
        position_rows.append(
            dict(
                position_fraction_pct=round(fraction * 100, 1),
                account_q01_gap_pct=round(fraction * tqqq["q01_pct"], 3),
                account_expected_shortfall_1pct=round(
                    fraction * tqqq["expected_shortfall_1pct"], 3
                ),
                account_historical_worst_pct=round(
                    fraction * tqqq["q_min_pct"], 3
                ),
            )
        )
    cap_rows = []
    for account_budget_pct in (0.5, 1.0, 2.0):
        cap_rows.append(
            dict(
                account_loss_budget_pct=account_budget_pct,
                max_position_at_q01_pct=round(
                    account_budget_pct / abs(tqqq["q01_pct"]) * 100, 2
                ),
                max_position_at_es1_pct=round(
                    account_budget_pct
                    / abs(tqqq["expected_shortfall_1pct"])
                    * 100,
                    2,
                ),
                max_position_at_historical_worst_pct=round(
                    account_budget_pct / abs(tqqq["q_min_pct"]) * 100, 2
                ),
            )
        )
    return dict(
        construction=(
            "unconditional close-to-next-open gaps on split-adjusted Yahoo OHLC; "
            "describes instrument jump exposure, not strategy-conditioned loss probability"
        ),
        ticker_stats=stats,
        leverage_scaling=scaling,
        regime_slices=era_rows,
        tqqq_account_risk_translation=dict(
            position_rows=position_rows,
            historical_budget_caps=cap_rows,
            caveat=(
                "simple position_fraction × instrument_gap translation before spread, "
                "liquidity, and path effects; historical quantiles/minima are scenarios, "
                "not guaranteed loss limits or sizing recommendations"
            ),
        ),
    )


def _circular_block_mean_ci(
    values: np.ndarray, block: int = 20, n_boot: int = 5000
) -> List[float]:
    """Deterministic circular-block CI for a dependent event rate."""
    values = np.asarray(values, dtype=float)
    n = len(values)
    if n == 0:
        return [0.0, 0.0]
    rng = np.random.RandomState(0)
    offsets = np.arange(block)
    n_blocks = int(math.ceil(n / block))
    means = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        starts = rng.randint(0, n, size=n_blocks)
        idx = ((starts[:, None] + offsets[None, :]) % n).reshape(-1)[:n]
        means[i] = float(values[idx].mean())
    return [
        round(float(np.percentile(means, 2.5)) * 100, 3),
        round(float(np.percentile(means, 97.5)) * 100, 3),
    ]


def _lagged_qqq_volatility(
    panel: pd.DataFrame, window: int = 20
) -> pd.Series:
    """Annualized trailing QQQ volatility known before each next open."""
    dividends = _load_qqq_distributions().reindex(
        panel.index, fill_value=0.0
    )
    close_return = (
        (panel["QQQ_close"] + dividends)
        / panel["QQQ_close"].shift(1)
        - 1
    )
    return close_return.rolling(window).std(ddof=1).shift(1) * math.sqrt(252)


def gap_dependence_and_volatility(panel: pd.DataFrame) -> Dict[str, object]:
    """Measure serial clustering and a leak-free lagged-vol risk classifier."""
    gap = (panel["TQQQ_open"] / panel["TQQQ_close"].shift(1) - 1.0).rename("gap")
    lagged_vol = _lagged_qqq_volatility(panel).rename("lagged_qqq_vol20")
    frame = pd.concat([gap, lagged_vol], axis=1).dropna()
    severe = frame["gap"] <= -0.02
    half_stop = frame["gap"] <= -0.005

    severe_i = severe.astype(float)
    iid_lo, iid_hi = _wilson_interval(int(severe.sum()), int(len(severe)))
    prior_one = severe.shift(1, fill_value=False)
    prior_five = (
        severe.shift(1, fill_value=False)
        .rolling(5, min_periods=1)
        .max()
        .astype(bool)
    )

    def conditional_row(label: str, condition: pd.Series) -> Dict[str, object]:
        n_condition = int(condition.sum())
        probability = float(severe[condition].mean()) if n_condition else 0.0
        baseline = float(severe.mean())
        return dict(
            condition=label,
            conditioned_nights=n_condition,
            severe_gaps=int(severe[condition].sum()),
            conditional_probability_pct=round(probability * 100, 3),
            baseline_probability_pct=round(baseline * 100, 3),
            risk_ratio=round(probability / max(baseline, 1e-12), 3),
        )

    annual = []
    for year, grp in frame.groupby(frame.index.year):
        event = grp["gap"] <= -0.02
        annual.append(
            dict(
                year=int(year),
                nights=int(len(grp)),
                severe_gaps=int(event.sum()),
                severe_gap_rate_pct=round(float(event.mean()) * 100, 2),
                worst_gap_pct=round(float(grp["gap"].min()) * 100, 2),
                mean_lagged_vol_pct=round(
                    float(grp["lagged_qqq_vol20"].mean()) * 100, 2
                ),
            )
        )

    threshold_rows = []
    downside_excess = (-frame["gap"] - 0.005).clip(lower=0)
    for threshold in VOL_THRESHOLDS:
        flagged = frame["lagged_qqq_vol20"] >= threshold
        row = dict(
            lagged_qqq_vol_threshold_pct=round(threshold * 100, 1),
            nights_flagged=int(flagged.sum()),
            exposure_removed_pct=round(float(flagged.mean()) * 100, 2),
            half_stop_gaps_captured=int((flagged & half_stop).sum()),
            half_stop_gap_capture_pct=round(
                float((flagged & half_stop).sum()) / max(1, int(half_stop.sum())) * 100,
                2,
            ),
            severe_gaps_captured=int((flagged & severe).sum()),
            severe_gap_capture_pct=round(
                float((flagged & severe).sum()) / max(1, int(severe.sum())) * 100,
                2,
            ),
            downside_excess_captured_pct=round(
                float(downside_excess[flagged].sum())
                / max(float(downside_excess.sum()), 1e-12)
                * 100,
                2,
            ),
            flagged_worst_gap_pct=round(
                float(frame.loc[flagged, "gap"].min()) * 100, 2
            ) if flagged.any() else None,
            unflagged_worst_gap_pct=round(
                float(frame.loc[~flagged, "gap"].min()) * 100, 2
            ) if (~flagged).any() else None,
        )
        for label, start, end in (
            ("2010_2019", "2010-01-01", "2019-12-31"),
            ("2020_2026", "2020-01-01", "2026-12-31"),
        ):
            cut = frame.loc[start:end]
            cut_flagged = cut["lagged_qqq_vol20"] >= threshold
            cut_severe = cut["gap"] <= -0.02
            row[label] = dict(
                exposure_removed_pct=round(float(cut_flagged.mean()) * 100, 2),
                severe_gap_capture_pct=round(
                    float((cut_flagged & cut_severe).sum())
                    / max(1, int(cut_severe.sum()))
                    * 100,
                    2,
                ),
            )
        threshold_rows.append(row)

    rolling5 = severe_i.rolling(5).sum()
    rolling20 = severe_i.rolling(20).sum()
    rolling_gap5 = frame["gap"].rolling(5).sum()
    return dict(
        construction=(
            "TQQQ adjusted close-to-next-open gaps, with QQQ 20-session realized "
            "volatility shifted one session so every classifier value is known before "
            "the classified open; thresholds are a descriptive risk ROC, not alpha tuning"
        ),
        n_nights=int(len(frame)),
        severe_gap_definition_pct=-2.0,
        severe_gap_count=int(severe.sum()),
        severe_gap_rate_pct=round(float(severe.mean()) * 100, 3),
        severe_gap_rate_iid_wilson95_pct=[
            round(iid_lo * 100, 3), round(iid_hi * 100, 3)
        ],
        severe_gap_rate_block20_bootstrap95_pct=_circular_block_mean_ci(
            severe_i.to_numpy(), block=20, n_boot=5000
        ),
        serial_dependence=dict(
            severe_indicator_acf_lag1=round(float(severe_i.autocorr(1)), 4),
            severe_indicator_acf_lag5=round(float(severe_i.autocorr(5)), 4),
            absolute_gap_acf_lag1=round(float(frame["gap"].abs().autocorr(1)), 4),
            absolute_gap_acf_lag5=round(float(frame["gap"].abs().autocorr(5)), 4),
            conditional_rows=[
                conditional_row("previous night was <= -2%", prior_one),
                conditional_row("any of previous 5 nights was <= -2%", prior_five),
            ],
        ),
        cluster_extremes=dict(
            maximum_severe_gaps_in_5_sessions=int(rolling5.max()),
            five_session_cluster_end=str(rolling5.idxmax().date()),
            maximum_severe_gaps_in_20_sessions=int(rolling20.max()),
            twenty_session_cluster_end=str(rolling20.idxmax().date()),
            worst_five_session_sum_gap_pct=round(float(rolling_gap5.min()) * 100, 2),
            worst_five_session_sum_end=str(rolling_gap5.idxmin().date()),
        ),
        annual_rows=annual,
        lagged_volatility_threshold_rows=threshold_rows,
        caveat=(
            "Event dependence makes independent-binomial intuition optimistic. Volatility "
            "thresholds are evaluated on the same history, do not identify auction costs, "
            "and cannot guarantee that the next discontinuity occurs in a flagged regime."
        ),
    )


def volatility_conditioned_mitigation(
    sig: pd.DataFrame,
    daily_panel: pd.DataFrame,
    session_close_prices: Dict[object, float],
) -> Dict[str, object]:
    """Apply the lagged-vol classifier only as an overnight exposure control."""
    target, stop = 0.01, 0.005
    bars = int(getattr(config, "MAX_TRADE_BARS_LIVE", 10))
    baseline = simulate(
        sig, target, stop, bars,
        gap_aware=True, one_position=True, scan_entry_bar=True,
    )
    baseline_exact = simulate(
        sig, target, stop, bars,
        gap_aware=False, one_position=True, scan_entry_bar=True,
    )
    attribution = gap_calendar_attribution(sig, baseline_exact, baseline)
    base = _replay_row(baseline)
    lagged_vol = _lagged_qqq_volatility(daily_panel).dropna()
    rows = []
    for threshold in VOL_THRESHOLDS:
        flagged_dates = {
            idx.date() for idx, value in lagged_vol.items() if value >= threshold
        }
        trades = simulate(
            sig, target, stop, bars,
            gap_aware=True, one_position=True, scan_entry_bar=True,
            flatten_before_dates=flagged_dates,
            session_close_prices=session_close_prices,
        )
        replay = _replay_row(trades)
        exits = int((trades["exit_type"] == "risk_flatten").sum())
        gap_reduction = (
            1 - replay["overnight_gap_stops"]
            / max(1, base["overnight_gap_stops"])
        ) * 100
        dd_improvement = replay["max_drawdown_pct"] - base["max_drawdown_pct"]
        return_delta = replay["total_return_pct"] - base["total_return_pct"]
        targeted_events = [
            event for event in attribution["events"]
            if pd.Timestamp(event["date"]).date() in flagged_dates
        ]
        targeted_damage = sum(event["damage_pp"] for event in targeted_events)
        targeted_damage_sorted = sorted(
            (event["damage_pp"] for event in targeted_events), reverse=True
        )
        rows.append(
            dict(
                lagged_qqq_vol_threshold_pct=round(threshold * 100, 1),
                risk_flatten_exits=exits,
                gap_reduction_pct=round(gap_reduction, 2),
                maxdd_improvement_pp=round(dd_improvement, 4),
                total_return_delta_pp=round(return_delta, 4),
                directly_targeted_gap_events=len(targeted_events),
                directly_targeted_gap_damage_share_pct=round(
                    targeted_damage
                    / max(attribution["cumulative_trade_damage_pp"], 1e-12)
                    * 100,
                    2,
                ),
                top_targeted_event_share_of_targeted_damage_pct=round(
                    (targeted_damage_sorted[0] if targeted_damage_sorted else 0.0)
                    / max(targeted_damage, 1e-12)
                    * 100,
                    2,
                ),
                first_order_break_even_extra_cost_bps_per_exit=round(
                    (return_delta / 100)
                    / max(1, exits)
                    / POSITION_FRACTION
                    * 10000,
                    2,
                ),
                risk_gate_pass=bool(
                    gap_reduction >= 50
                    and dd_improvement >= 2
                    and return_delta >= -1
                ),
                **replay,
            )
        )
    return dict(
        pre_registered_read=(
            "A lagged-volatility control is interesting only if it removes >=50% of "
            "strategy gap stops, improves maxDD >=2pp, and does not reduce total return "
            ">1pp versus the negative gap-aware baseline. Passing is not production approval."
        ),
        baseline=base,
        policy_rows=rows,
        caveat=(
            "The predictor is leak-free but thresholds are same-sample descriptive. "
            "Flattening changes later opportunities and uses an official-close proxy."
        ),
    )


def _daily_account_log_returns(
    trades: pd.DataFrame, session_dates: pd.DatetimeIndex
) -> np.ndarray:
    """Align sequential trade wealth effects to exit sessions."""
    values = pd.Series(0.0, index=session_dates)
    for _, trade in trades.iterrows():
        day = pd.Timestamp(trade["exit_timestamp"]).tz_localize(None).normalize()
        if day in values.index:
            values.loc[day] += math.log1p(
                float(trade["return"]) * POSITION_FRACTION
            )
    return values.to_numpy(dtype=float)


def _circular_block_relative_wealth_ci(
    log_return_difference: np.ndarray,
    block: int,
    n_boot: int = 5000,
) -> List[float]:
    """Bootstrap a full-path relative-wealth effect from paired daily logs."""
    values = np.asarray(log_return_difference, dtype=float)
    if np.allclose(values, 0.0):
        return [0.0, 0.0]
    n = len(values)
    rng = np.random.RandomState(block)
    offsets = np.arange(block)
    n_blocks = int(math.ceil(n / block))
    results = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        starts = rng.randint(0, n, size=n_blocks)
        idx = ((starts[:, None] + offsets[None, :]) % n).reshape(-1)[:n]
        results[i] = math.expm1(float(values[idx].sum())) * 100
    return [
        round(float(np.percentile(results, 2.5)), 3),
        round(float(np.percentile(results, 97.5)), 3),
    ]


def _extra_exit_cost_metrics(
    trades: pd.DataFrame, exit_type: str, cost_bps: float
) -> Dict[str, float]:
    adjusted = trades.copy()
    mask = adjusted["exit_type"] == exit_type
    adjusted.loc[mask, "return"] = (
        adjusted.loc[mask, "return"].astype(float) - cost_bps / 10000
    )
    return equity_metrics(adjusted)


def mitigation_uncertainty_and_cost(
    sig: pd.DataFrame,
    daily_panel: pd.DataFrame,
    session_close_prices: Dict[object, float],
) -> Dict[str, object]:
    """Stress candidate flatten policies for dependence, costs, and selection."""
    target, stop = 0.01, 0.005
    bars = int(getattr(config, "MAX_TRADE_BARS_LIVE", 10))
    baseline = simulate(
        sig, target, stop, bars,
        gap_aware=True, one_position=True, scan_entry_bar=True,
    )
    lagged_vol = _lagged_qqq_volatility(daily_panel).dropna()
    vol15_dates = {idx.date() for idx, value in lagged_vol.items() if value >= 0.15}
    policies = [
        (
            "daily_flatten",
            "eod_flatten",
            simulate(
                sig, target, stop, bars,
                gap_aware=True, one_position=True, scan_entry_bar=True,
                flatten_eod=True, session_close_prices=session_close_prices,
            ),
        ),
        (
            "weekend_or_long_closure",
            "calendar_flatten",
            simulate(
                sig, target, stop, bars,
                gap_aware=True, one_position=True, scan_entry_bar=True,
                flatten_before_gap_days=3,
                session_close_prices=session_close_prices,
            ),
        ),
        (
            "lagged_qqq_vol20_at_least_15pct",
            "risk_flatten",
            simulate(
                sig, target, stop, bars,
                gap_aware=True, one_position=True, scan_entry_bar=True,
                flatten_before_dates=vol15_dates,
                session_close_prices=session_close_prices,
            ),
        ),
    ]
    session_dates = pd.DatetimeIndex(
        sorted({pd.Timestamp(ts).tz_localize(None).normalize() for ts in sig.index})
    )
    baseline_logs = _daily_account_log_returns(baseline, session_dates)
    baseline_metrics = equity_metrics(baseline)
    rows = []
    for name, exit_type, trades in policies:
        policy_logs = _daily_account_log_returns(trades, session_dates)
        diff = policy_logs - baseline_logs
        metrics = equity_metrics(trades)
        n_exits = int((trades["exit_type"] == exit_type).sum())
        annual_rows = []
        for year in sorted(set(session_dates.year)):
            mask = session_dates.year == year
            annual_rows.append(
                dict(
                    year=int(year),
                    baseline_total_return_pct=round(
                        math.expm1(float(baseline_logs[mask].sum())) * 100, 4
                    ),
                    policy_total_return_pct=round(
                        math.expm1(float(policy_logs[mask].sum())) * 100, 4
                    ),
                    relative_wealth_effect_pct=round(
                        math.expm1(float(diff[mask].sum())) * 100, 4
                    ),
                )
            )
        cost_rows = []
        for cost_bps in (0, 5, 10, 20, 40, 60, 80):
            cost_metrics = _extra_exit_cost_metrics(trades, exit_type, cost_bps)
            cost_rows.append(
                dict(
                    extra_cost_bps_per_flatten_exit=cost_bps,
                    total_return_pct=cost_metrics["total_return_pct"],
                    max_drawdown_pct=cost_metrics["max_drawdown_pct"],
                    total_return_delta_vs_baseline_pp=round(
                        cost_metrics["total_return_pct"]
                        - baseline_metrics["total_return_pct"],
                        4,
                    ),
                )
            )
        rows.append(
            dict(
                policy=name,
                flatten_exit_type=exit_type,
                flatten_exits=n_exits,
                total_return_pct=metrics["total_return_pct"],
                max_drawdown_pct=metrics["max_drawdown_pct"],
                total_return_delta_vs_baseline_pp=round(
                    metrics["total_return_pct"]
                    - baseline_metrics["total_return_pct"],
                    4,
                ),
                observed_relative_wealth_effect_pct=round(
                    math.expm1(float(diff.sum())) * 100, 4
                ),
                paired_daily_log_block_bootstrap_relative_wealth95_pct={
                    str(block): _circular_block_relative_wealth_ci(diff, block)
                    for block in (5, 20, 60)
                },
                calendar_slices=annual_rows,
                extra_cost_sensitivity=cost_rows,
            )
        )
    return dict(
        baseline=baseline_metrics,
        policy_rows=rows,
        interpretation=(
            "Bootstrap bands resample paired daily log-return differences and report "
            "relative wealth, not max-drawdown uncertainty. Extra cost is charged once "
            "per flatten exit at the instrument-return level before 10% position scaling."
        ),
        selection_warning=(
            "The 15% volatility threshold is the lower-turnover of two thresholds "
            "(12.5% and 15%) that passed the same-sample mitigation gate and is therefore "
            "a selected result. Its block "
            "bands and 2010-2019/2020-2026 classifier splits are stress tests, not OOS "
            "strategy validation."
        ),
    )


def _volatility_classifier_row(
    frame: pd.DataFrame, threshold: float
) -> Dict[str, object]:
    """Summarize a pre-open volatility flag against subsequent TQQQ gaps."""
    flagged = frame["lagged_vol"] >= threshold
    severe = frame["gap"] <= -0.02
    downside_excess = (-frame["gap"] - 0.005).clip(lower=0)
    return dict(
        nights=int(len(frame)),
        flagged_nights=int(flagged.sum()),
        exposure_removed_pct=round(float(flagged.mean()) * 100, 2),
        severe_gaps=int(severe.sum()),
        severe_gaps_captured=int((flagged & severe).sum()),
        severe_gap_capture_pct=round(
            float((flagged & severe).sum()) / max(1, int(severe.sum())) * 100,
            2,
        ),
        downside_excess_captured_pct=round(
            float(downside_excess[flagged].sum())
            / max(float(downside_excess.sum()), 1e-12)
            * 100,
            2,
        ),
        unflagged_worst_gap_pct=round(
            float(frame.loc[~flagged, "gap"].min()) * 100, 2
        ) if (~flagged).any() else None,
    )


def volatility_lookback_oos_study(
    sig: pd.DataFrame,
    daily_panel: pd.DataFrame,
    session_close_prices: Dict[object, float],
) -> Dict[str, object]:
    """Test whether a lagged-volatility rule survives lookback changes and an early split."""
    target, stop = 0.01, 0.005
    bars = int(getattr(config, "MAX_TRADE_BARS_LIVE", 10))
    baseline = simulate(
        sig, target, stop, bars,
        gap_aware=True, one_position=True, scan_entry_bar=True,
    )
    base = _replay_row(baseline)
    gap = (
        daily_panel["TQQQ_open"] / daily_panel["TQQQ_close"].shift(1) - 1.0
    ).rename("gap")
    candidate_thresholds = (0.10, 0.125, 0.15, 0.175, 0.20, 0.225, 0.25, 0.30)
    rows = []
    for window in (10, 20, 40, 60):
        lagged_vol = _lagged_qqq_volatility(
            daily_panel, window=window
        ).rename("lagged_vol")
        frame = pd.concat([gap, lagged_vol], axis=1).dropna()
        train = frame.loc["2010-01-01":"2019-12-31"]
        test = frame.loc["2020-01-01":"2026-12-31"]
        candidate_rows = [
            dict(
                threshold_pct=round(threshold * 100, 1),
                **_volatility_classifier_row(train, threshold),
            )
            for threshold in candidate_thresholds
        ]
        eligible = [
            row for row in candidate_rows
            if row["severe_gap_capture_pct"] >= 60.0
        ]
        if not eligible:
            raise AssertionError("candidate grid cannot meet training capture rule")
        selected = max(eligible, key=lambda row: row["threshold_pct"])
        threshold = float(selected["threshold_pct"]) / 100
        test_row = _volatility_classifier_row(test, threshold)
        flagged_dates = {
            idx.date()
            for idx, value in lagged_vol.dropna().items()
            if value >= threshold
        }
        trades = simulate(
            sig, target, stop, bars,
            gap_aware=True, one_position=True, scan_entry_bar=True,
            flatten_before_dates=flagged_dates,
            session_close_prices=session_close_prices,
        )
        replay = _replay_row(trades)
        exits = int((trades["exit_type"] == "risk_flatten").sum())
        gap_reduction = (
            1 - replay["overnight_gap_stops"]
            / max(1, base["overnight_gap_stops"])
        ) * 100
        return_delta = replay["total_return_pct"] - base["total_return_pct"]
        dd_improvement = replay["max_drawdown_pct"] - base["max_drawdown_pct"]
        rows.append(
            dict(
                lookback_sessions=window,
                training_selection_rule=(
                    "highest candidate threshold retaining >=60% capture of "
                    "TQQQ <=-2% gaps in 2010-2019"
                ),
                selected_threshold_pct=round(threshold * 100, 1),
                training_2010_2019=selected,
                classifier_test_2020_2026=test_row,
                strategy_2024_2026=dict(
                    risk_flatten_exits=exits,
                    gap_reduction_pct=round(gap_reduction, 2),
                    total_return_delta_pp=round(return_delta, 4),
                    maxdd_improvement_pp=round(dd_improvement, 4),
                    first_order_break_even_extra_cost_bps_per_exit=round(
                        (return_delta / 100)
                        / max(1, exits)
                        / POSITION_FRACTION
                        * 10000,
                        2,
                    ),
                    risk_gate_pass=bool(
                        gap_reduction >= 50
                        and dd_improvement >= 2
                        and return_delta >= -1
                    ),
                    **replay,
                ),
                training_candidate_rows=candidate_rows,
            )
        )
    return dict(
        design=(
            "For each lookback, choose the highest threshold from a fixed absolute "
            "grid that still captures >=60% of severe gaps in 2010-2019, then freeze "
            "it before measuring the classifier in 2020-2026. QQQ volatility is shifted "
            "one session and therefore known before the classified TQQQ open."
        ),
        baseline_strategy=base,
        lookback_rows=rows,
        caveat=(
            "The 2020-2026 instrument classifier slice is temporally held out from "
            "threshold selection. The lookback family and the 2024-2026 strategy "
            "application were nevertheless examined after Study 23, so this is a "
            "robustness/falsification test—not prospective strategy validation."
        ),
    )


def _binomial_upper_tail(n: int, k: int, probability: float) -> float:
    return float(
        sum(
            math.comb(n, j)
            * probability ** j
            * (1 - probability) ** (n - j)
            for j in range(k, n + 1)
        )
    )


def _fixed_horizon_binomial_design(
    null_probability: float,
    alternative_probability: float,
    power_target: float,
    alpha: float = 0.05,
) -> Dict[str, object]:
    """Smallest fixed horizon for a one-sided exact-binomial test."""
    for n in range(1, 5000):
        critical = next(
            (
                k for k in range(n + 1)
                if _binomial_upper_tail(n, k, null_probability) <= alpha
            ),
            None,
        )
        if critical is None:
            continue
        power = _binomial_upper_tail(n, critical, alternative_probability)
        if power >= power_target:
            return dict(
                event_horizon=n,
                minimum_captures_for_success=critical,
                minimum_observed_capture_pct=round(critical / n * 100, 2),
                exact_power_pct=round(power * 100, 2),
                alpha=alpha,
            )
    raise AssertionError("fixed-horizon search exceeded bound")


def forward_shadow_validation_design(
    sig: pd.DataFrame,
    daily_panel: pd.DataFrame,
    session_close_prices: Dict[object, float],
) -> Dict[str, object]:
    """Turn the selected volatility rule into falsifiable forward evidence gates."""
    target, stop = 0.01, 0.005
    bars = int(getattr(config, "MAX_TRADE_BARS_LIVE", 10))
    baseline = simulate(
        sig, target, stop, bars,
        gap_aware=True, one_position=True, scan_entry_bar=True,
    )
    vol20 = _lagged_qqq_volatility(daily_panel, window=20).dropna()
    flagged_dates = {
        idx.date() for idx, value in vol20.items() if value >= 0.15
    }
    policy = simulate(
        sig, target, stop, bars,
        gap_aware=True, one_position=True, scan_entry_bar=True,
        flatten_before_dates=flagged_dates,
        session_close_prices=session_close_prices,
    )
    base_gap_events = int((baseline["exit_type"] == "overnight_gap_stop").sum())
    remaining_gap_events = int((policy["exit_type"] == "overnight_gap_stop").sum())
    captured_gap_events = base_gap_events - remaining_gap_events
    observed_capture = captured_gap_events / max(1, base_gap_events)
    sample_years = (
        (pd.Timestamp(sig.index[-1]) - pd.Timestamp(sig.index[0])).days
        / 365.2425
    )
    strategy_event_rate = base_gap_events / sample_years
    flatten_exits = int((policy["exit_type"] == "risk_flatten").sum())
    flatten_exit_rate = flatten_exits / sample_years

    gap = (
        daily_panel["TQQQ_open"] / daily_panel["TQQQ_close"].shift(1) - 1
    ).rename("gap")
    classifier = pd.concat(
        [gap, vol20.rename("lagged_vol")], axis=1
    ).dropna()
    severe = classifier["gap"] <= -0.02
    captured = severe & (classifier["lagged_vol"] >= 0.15)
    severe_rate_per_year = int(severe.sum()) / (
        (classifier.index[-1] - classifier.index[0]).days / 365.2425
    )
    full_history_capture = float(captured.sum()) / max(1, int(severe.sum()))
    heldout = classifier.loc["2020-01-01":"2026-12-31"]
    heldout_severe = heldout["gap"] <= -0.02
    heldout_capture = float(
        (
            heldout_severe
            & (heldout["lagged_vol"] >= 0.15)
        ).sum()
    ) / max(1, int(heldout_severe.sum()))

    strategy_power = {
        str(int(power * 100)): _fixed_horizon_binomial_design(
            0.50, observed_capture, power
        )
        for power in (0.80, 0.90)
    }
    for design in strategy_power.values():
        design["expected_years_at_observed_event_rate"] = round(
            design["event_horizon"] / strategy_event_rate, 2
        )
    dependence_sensitivity = [
        dict(
            heuristic_design_effect=factor,
            inflated_strategy_event_horizon=int(
                math.ceil(strategy_power["80"]["event_horizon"] * factor)
            ),
            expected_years_at_observed_event_rate=round(
                math.ceil(strategy_power["80"]["event_horizon"] * factor)
                / strategy_event_rate,
                2,
            ),
        )
        for factor in (1.0, 1.25, 1.5, 2.0)
    ]
    classifier_design = _fixed_horizon_binomial_design(
        0.60, full_history_capture, 0.80
    )
    classifier_design["expected_years_at_historical_event_rate"] = round(
        classifier_design["event_horizon"] / severe_rate_per_year, 2
    )
    optimistic_classifier_design = _fixed_horizon_binomial_design(
        0.60, heldout_capture, 0.80
    )
    optimistic_classifier_design["expected_years_at_historical_event_rate"] = round(
        optimistic_classifier_design["event_horizon"] / severe_rate_per_year, 2
    )

    break_even_cost_bps = (
        (
            equity_metrics(policy)["total_return_pct"]
            - equity_metrics(baseline)["total_return_pct"]
        )
        / 100
        / max(1, flatten_exits)
        / POSITION_FRACTION
        * 10000
    )
    cost_rows = []
    for label, assumed_mean, assumed_std in (
        ("benign", 20.0, 25.0),
        ("moderate", 30.0, 50.0),
        ("adverse", 40.0, 100.0),
        ("near_budget", 50.0, 100.0),
    ):
        margin = break_even_cost_bps - assumed_mean
        model_n = (
            int(math.ceil((1.645 * assumed_std / margin) ** 2))
            if margin > 0 else None
        )
        fixed_n = max(30, model_n) if model_n is not None else None
        cost_rows.append(
            dict(
                scenario=label,
                assumed_mean_extra_cost_bps=assumed_mean,
                assumed_cost_std_bps=assumed_std,
                normal_approximation_n=model_n,
                fixed_minimum_exit_sample=fixed_n,
                expected_years_at_observed_exit_rate=(
                    round(fixed_n / flatten_exit_rate, 2)
                    if fixed_n is not None else None
                ),
            )
        )
    current_p_value = _binomial_upper_tail(
        base_gap_events, captured_gap_events, 0.50
    )
    return dict(
        frozen_candidate=dict(
            qqq_volatility_lookback_sessions=20,
            annualized_threshold_pct=15.0,
            decision_time=(
                "previous session close; classifier uses returns only through "
                "the session before the classified open"
            ),
        ),
        historical_inputs_not_forward_evidence=dict(
            strategy_gap_events=base_gap_events,
            strategy_events_captured=captured_gap_events,
            observed_strategy_capture_pct=round(observed_capture * 100, 2),
            one_sided_exact_p_value_vs_50pct=round(current_p_value, 4),
            strategy_gap_event_rate_per_year=round(strategy_event_rate, 2),
            flatten_exit_rate_per_year=round(flatten_exit_rate, 2),
            unconditional_severe_gap_rate_per_year=round(
                severe_rate_per_year, 2
            ),
            unconditional_full_history_capture_pct=round(
                full_history_capture * 100, 2
            ),
            heldout_2020_2026_capture_pct=round(
                heldout_capture * 100, 2
            ),
        ),
        fixed_horizon_gates=dict(
            primary_strategy_gap_capture=dict(
                null="capture probability <=50%",
                alternative=round(observed_capture, 6),
                designs=strategy_power,
                interpretation=(
                    "Decision-relevant but slow. Historical 21/34 is not significant "
                    "against 50%% (one-sided exact p=%.4f), and selected history cannot "
                    "be counted toward the new horizon." % current_p_value
                ),
                dependence_warning=(
                    "The exact-binomial design assumes independent capture events, while "
                    "Study 23 establishes clustered gaps and the volatility flag persists "
                    "across events. Treat 115 as an iid planning floor, not a guaranteed "
                    "horizon."
                ),
                heuristic_dependence_sensitivity=dependence_sensitivity,
            ),
            surrogate_unconditional_classifier=dict(
                null="capture probability <=60%",
                conservative_alternative=round(full_history_capture, 6),
                conservative_80pct_power_design=classifier_design,
                optimistic_alternative=round(heldout_capture, 6),
                optimistic_80pct_power_design=optimistic_classifier_design,
                interpretation=(
                    "Faster market-level falsification, but cannot substitute for "
                    "strategy-conditioned capture. Its exact-binomial horizon has the "
                    "same event-independence limitation."
                ),
            ),
            auction_cost=dict(
                first_order_break_even_extra_cost_bps=round(
                    break_even_cost_bps, 2
                ),
                one_sided_upper_mean_rule=(
                    "At a pre-fixed exit horizon, require the one-sided 95% upper "
                    "confidence bound for mean incremental all-in flatten cost to "
                    "remain below the break-even budget."
                ),
                scenario_rows=cost_rows,
                warning=(
                    "Normal calculations are planning scenarios, not evidence. Use "
                    "an observed paired fill-cost distribution and report tails, "
                    "rejects, partial fills, and deadline misses. IBKR says its paper "
                    "environment does not support Auction order types and simulates "
                    "fills from top of book, so paper fills cannot satisfy this gate."
                ),
            ),
        ),
        minimum_shadow_ledger_fields=[
            "decision timestamp and frozen lagged-volatility value",
            "position side/quantity and would-have-held stop",
            "intended MOC/LOC quantity, submission/cancel timestamps, and order IDs",
            "broker status sequence, reject/partial-fill state, and final quantity",
            "official close and paper-simulator response (operational evidence only)",
            "next official open and counterfactual hold outcome",
            "data revision/source identifier and immutable record hash",
        ],
        paper_execution_boundary=dict(
            ibkr_documentation=(
                "https://www.interactivebrokers.com/campus/glossary-terms/"
                "paper-trading-account/"
            ),
            documented_limits=(
                "IBKR Paper Trading has no support for Auction order types, has no "
                "execution or clearing ability, and simulates fills from top of book."
            ),
            consequence=(
                "A paper-only trial cannot estimate real MOC auction slippage or clear "
                "the 61.3bp all-in cost gate. It can validate signal timing, ledger "
                "completeness, API state handling for supported orders, and counterfactual "
                "next-open outcomes. Real-auction validation would require new authority "
                "and is outside this study and the protected live path."
            ),
        ),
        protocol=(
            "Phase A is no-order shadow logging and can falsify classifier behavior. "
            "An isolated paper API rehearsal would require separate approval and must not "
            "modify the protected live trader/config path, but paper auction fills are not "
            "execution-cost evidence. No success look before the fixed event/exit horizon. "
            "Operational safety failures may stop the trial immediately, but cannot count "
            "as efficacy."
        ),
        verdict=(
            "A one-year pilot can audit plumbing and proxy costs but is underpowered for "
            "the strategy endpoint. At the observed event rate, 80%% power against a 50%% "
            "capture null needs about %.1f years of entirely new strategy gap events "
            "under an iid planning assumption, and longer under clustered capture. "
            "Paper-only evidence cannot close the real-auction cost question."
            % strategy_power["80"]["expected_years_at_observed_event_rate"]
        ),
    )


def simple_risk_classifier_benchmarks(
    sig: pd.DataFrame,
    daily_panel: pd.DataFrame,
    session_close_prices: Dict[object, float],
) -> Dict[str, object]:
    """Benchmark lagged volatility against transparent recent-gap rules."""
    target, stop = 0.01, 0.005
    bars = int(getattr(config, "MAX_TRADE_BARS_LIVE", 10))
    baseline = simulate(
        sig, target, stop, bars,
        gap_aware=True, one_position=True, scan_entry_bar=True,
    )
    base = _replay_row(baseline)
    gap = (
        daily_panel["TQQQ_open"] / daily_panel["TQQQ_close"].shift(1) - 1
    ).rename("gap")
    vol20 = _lagged_qqq_volatility(daily_panel, window=20).rename("lagged_vol")
    frame = pd.concat([gap, vol20], axis=1).dropna()
    severe = frame["gap"] <= -0.02
    prior_severe = severe.shift(1, fill_value=False)
    policies = [
        (
            "lagged_qqq_vol20_at_least_15pct",
            frame["lagged_vol"] >= 0.15,
        )
    ]
    for window in (1, 2, 3, 5, 10, 20):
        policies.append(
            (
                "any_severe_tqqq_gap_in_prior_%d_sessions" % window,
                prior_severe.rolling(window, min_periods=1).max().astype(bool),
            )
        )
    downside_excess = (-frame["gap"] - 0.005).clip(lower=0)
    rows = []
    for name, flagged in policies:
        flagged = flagged.reindex(frame.index, fill_value=False)
        exposure = float(flagged.mean())
        event_capture = float((flagged & severe).sum()) / max(1, int(severe.sum()))
        flagged_dates = {idx.date() for idx, value in flagged.items() if value}
        trades = simulate(
            sig, target, stop, bars,
            gap_aware=True, one_position=True, scan_entry_bar=True,
            flatten_before_dates=flagged_dates,
            session_close_prices=session_close_prices,
        )
        replay = _replay_row(trades)
        exits = int((trades["exit_type"] == "risk_flatten").sum())
        gap_reduction = (
            1 - replay["overnight_gap_stops"]
            / max(1, base["overnight_gap_stops"])
        ) * 100
        return_delta = replay["total_return_pct"] - base["total_return_pct"]
        dd_improvement = replay["max_drawdown_pct"] - base["max_drawdown_pct"]
        rows.append(
            dict(
                policy=name,
                instrument_nights=int(len(frame)),
                exposure_removed_pct=round(exposure * 100, 2),
                severe_gap_capture_pct=round(event_capture * 100, 2),
                capture_lift_vs_random=round(
                    event_capture / max(exposure, 1e-12), 3
                ),
                severe_gap_precision_pct=round(
                    float(severe[flagged].mean()) * 100
                    if flagged.any() else 0.0,
                    2,
                ),
                downside_excess_captured_pct=round(
                    float(downside_excess[flagged].sum())
                    / max(float(downside_excess.sum()), 1e-12)
                    * 100,
                    2,
                ),
                strategy=dict(
                    risk_flatten_exits=exits,
                    gap_reduction_pct=round(gap_reduction, 2),
                    total_return_delta_pp=round(return_delta, 4),
                    maxdd_improvement_pp=round(dd_improvement, 4),
                    risk_gate_pass=bool(
                        gap_reduction >= 50
                        and dd_improvement >= 2
                        and return_delta >= -1
                    ),
                    **replay,
                ),
            )
        )
    return dict(
        design=(
            "Every flag is known before the classified open. Recent-gap controls "
            "activate for N sessions after a TQQQ <=-2% open; the volatility control "
            "uses lagged 20-session QQQ close volatility. Capture lift divides severe-"
            "gap capture by exposure removed, so random flags have expected lift 1."
        ),
        baseline_strategy=base,
        baseline_severe_gap_rate_pct=round(float(severe.mean()) * 100, 3),
        policy_rows=rows,
        caveat=(
            "These controls share one history and are not independent hypotheses. "
            "Recent-gap windows deliberately exploit the clustering documented in Study "
            "23; a similar lift would show concentration is not unique to volatility."
        ),
    )


def volatility_regime_stability(daily_panel: pd.DataFrame) -> Dict[str, object]:
    """Decompose the 15% volatility rule's capture into exposure and discrimination."""
    gap = (
        daily_panel["TQQQ_open"] / daily_panel["TQQQ_close"].shift(1) - 1
    ).rename("gap")
    vol20 = _lagged_qqq_volatility(daily_panel, window=20).rename("lagged_vol")
    frame = pd.concat([gap, vol20], axis=1).dropna()
    frame["severe"] = frame["gap"] <= -0.02
    frame["flagged"] = frame["lagged_vol"] >= 0.15
    frame["downside_excess"] = (-frame["gap"] - 0.005).clip(lower=0)

    def row(label: str, cut: pd.DataFrame) -> Dict[str, object]:
        exposure = float(cut["flagged"].mean())
        severe_count = int(cut["severe"].sum())
        capture = float(
            (cut["severe"] & cut["flagged"]).sum()
        ) / max(1, severe_count)
        return dict(
            period=label,
            nights=int(len(cut)),
            severe_gaps=severe_count,
            exposure_removed_pct=round(exposure * 100, 2),
            severe_gap_capture_pct=round(capture * 100, 2),
            capture_lift_vs_random=round(
                capture / max(exposure, 1e-12), 3
            ),
            flagged_severe_gap_precision_pct=round(
                float(cut.loc[cut["flagged"], "severe"].mean()) * 100
                if cut["flagged"].any() else 0.0,
                2,
            ),
            downside_excess_captured_pct=round(
                float(
                    cut.loc[cut["flagged"], "downside_excess"].sum()
                )
                / max(float(cut["downside_excess"].sum()), 1e-12)
                * 100,
                2,
            ),
        )

    annual_rows = [
        row(str(int(year)), cut)
        for year, cut in frame.groupby(frame.index.year)
    ]
    era_rows = [
        row("2010_2019", frame.loc["2010-01-01":"2019-12-31"]),
        row("2020_2026", frame.loc["2020-01-01":"2026-12-31"]),
        row("2021_2026_excluding_covid_year", frame.loc["2021-01-01":"2026-12-31"]),
    ]
    recent = frame.loc["2020-01-01":"2026-12-31"]
    leave_one_year_out = [
        row(
            "2020_2026_excluding_%d" % year,
            recent.loc[recent.index.year != year],
        )
        for year in range(2020, 2027)
    ]
    return dict(
        classifier="lagged QQQ 20-session annualized volatility >=15%",
        annual_rows=annual_rows,
        era_rows=era_rows,
        leave_one_recent_year_out=leave_one_year_out,
        interpretation=(
            "Capture is not discrimination: a rule flagging every night has 100% "
            "capture and lift 1. The annual lift exposes whether high raw capture comes "
            "from concentrating risk or simply remaining on through a whole regime."
        ),
        caveat=(
            "Annual cuts are descriptive and severe-event counts are small. Leave-one-"
            "year-out stability tests concentration in a single calendar year, not "
            "prospective transport to a new volatility regime."
        ),
    )


def _sha256_file(path: str) -> Optional[str]:
    if not os.path.exists(path):
        return None
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _input_manifest_row(
    name: str,
    path: str,
    expected_sha256: str,
    query: str,
    durable_derivative: Optional[str] = None,
) -> Dict[str, object]:
    observed = _sha256_file(path)
    size = os.path.getsize(path) if observed is not None else None
    line_count = None
    if observed is not None:
        with open(path, "rb") as fh:
            line_count = sum(1 for _ in fh)
    return dict(
        input=name,
        vendor="Yahoo Finance via yfinance",
        query=query,
        runtime_cache_path=path,
        expected_sha256=expected_sha256,
        observed_sha256=observed,
        byte_identical_to_study_snapshot=bool(observed == expected_sha256),
        bytes=size,
        physical_lines=line_count,
        durable_derivative=durable_derivative,
        raw_bytes_committed=False,
    )


def input_provenance_audit(hourly_path: str) -> Dict[str, object]:
    """Make cache dependence and reconstruction limits explicit."""
    rows = [
        _input_manifest_row(
            "TQQQ full-session hourly OHLCV",
            hourly_path,
            HOURLY_SOURCE_SHA256,
            "TQQQ 1h, 2024-08-01 through 2026-07-22, auto_adjust=False",
        ),
        _input_manifest_row(
            "TQQQ five-minute calibration OHLCV",
            FIVE_MIN_CACHE,
            FIVE_MIN_SOURCE_SHA256,
            "TQQQ 5m, 2026-05-25 through 2026-07-22, auto_adjust=False",
            os.path.relpath(FIVE_MIN_AUDIT, REPO),
        ),
        _input_manifest_row(
            "cross-instrument daily OHLC panel",
            DAILY_CACHE,
            DAILY_SOURCE_SHA256,
            (
                "SPY/SSO/UPRO/QQQ/QLD/TQQQ/SOXL/TNA 1d, "
                "2010-02-12 through 2026-07-22, auto_adjust=False"
            ),
        ),
        _input_manifest_row(
            "TQQQ July 6 one-minute recovery window",
            ONE_MIN_RAW_CACHE,
            ONE_MIN_SOURCE_SHA256,
            "TQQQ 1m, 2026-07-06 through 2026-07-08, auto_adjust=False",
            os.path.relpath(ONE_MIN_AUDIT, REPO),
        ),
        _input_manifest_row(
            "TQQQ daily corporate actions",
            CORPORATE_ACTIONS_RAW_CACHE,
            CORPORATE_ACTIONS_SOURCE_SHA256,
            (
                "TQQQ 1d actions=True, 2010-02-12 through 2026-07-22, "
                "auto_adjust=False"
            ),
            os.path.relpath(CORPORATE_ACTIONS_AUDIT, REPO),
        ),
        _input_manifest_row(
            "QQQ daily corporate actions",
            QQQ_ACTIONS_RAW_CACHE,
            QQQ_ACTIONS_SOURCE_SHA256,
            (
                "QQQ 1d actions=True, 2010-02-12 through 2026-07-22, "
                "auto_adjust=False"
            ),
            os.path.relpath(QQQ_DISTRIBUTIONS_AUDIT, REPO),
        ),
    ]
    matched = sum(row["byte_identical_to_study_snapshot"] for row in rows)
    return dict(
        cache_rows=rows,
        byte_identical_inputs_present="%d/%d" % (matched, len(rows)),
        reproducibility_class=(
            "exact while the six hashed runtime caches remain available; the repository "
            "alone preserves code, hashes, and lower-timeframe derived audits but not the "
            "hourly/daily raw vendor bytes"
        ),
        revision_policy=(
            "A refresh or vendor revision must receive a new hash and a result diff. "
            "Never silently call revised bytes the original pinned sample."
        ),
        limitation=(
            "Hashes prove identity of available bytes, not correctness, completeness, "
            "licensing, or future retrievability. The one-minute and five-minute Yahoo "
            "windows expire."
        ),
    )


def volatility_gap_severity_calibration(
    daily_panel: pd.DataFrame,
) -> Dict[str, object]:
    """Measure whether volatility concentrates ordinary or catastrophic gaps."""
    gap = (
        daily_panel["TQQQ_open"] / daily_panel["TQQQ_close"].shift(1) - 1
    ).rename("gap")
    vol20 = _lagged_qqq_volatility(daily_panel, window=20).rename("lagged_vol")
    frame = pd.concat([gap, vol20], axis=1).dropna()
    flagged = frame["lagged_vol"] >= 0.15
    exposure = float(flagged.mean())
    rows = []
    for threshold in (0.0025, 0.005, 0.01, 0.02, 0.04, 0.06, 0.08, 0.10):
        event = frame["gap"] <= -threshold
        n_events = int(event.sum())
        captured = int((event & flagged).sum())
        capture_rate = captured / max(1, n_events)
        rows.append(
            dict(
                gap_loss_threshold_pct=round(threshold * 100, 2),
                events=n_events,
                events_captured=captured,
                event_capture_pct=round(capture_rate * 100, 2),
                capture_lift_vs_random=round(
                    capture_rate / max(exposure, 1e-12), 3
                ),
                flagged_night_event_precision_pct=round(
                    float(event[flagged].mean()) * 100, 2
                ),
                unflagged_events=n_events - captured,
            )
        )
    flagged_gaps = frame.loc[flagged, "gap"]
    unflagged_gaps = frame.loc[~flagged, "gap"]
    return dict(
        classifier="lagged QQQ 20-session annualized volatility >=15%",
        exposure_removed_pct=round(exposure * 100, 2),
        severity_rows=rows,
        residual_unflagged_tail=dict(
            worst_gap_pct=round(float(unflagged_gaps.min()) * 100, 2),
            q01_gap_pct=round(float(unflagged_gaps.quantile(0.01)) * 100, 2),
            expected_shortfall_below_unflagged_q01_pct=round(
                float(
                    unflagged_gaps[
                        unflagged_gaps <= unflagged_gaps.quantile(0.01)
                    ].mean()
                ) * 100,
                2,
            ),
            current_10pct_position_historical_worst_account_pct=round(
                float(unflagged_gaps.min()) * POSITION_FRACTION * 100, 2
            ),
        ),
        flagged_tail=dict(
            worst_gap_pct=round(float(flagged_gaps.min()) * 100, 2),
            q01_gap_pct=round(float(flagged_gaps.quantile(0.01)) * 100, 2),
        ),
        interpretation=(
            "Capture lift should rise with severity if the rule is a catastrophic-"
            "tail state rather than a precise predictor of routine stop crossings. "
            "Residual unflagged extrema show why a filter is not a loss bound."
        ),
        caveat=(
            "Threshold rows are nested, dependent, and descriptive. Extreme rows have "
            "few observations, and historical unflagged minima do not cap future losses."
        ),
    )


def _load_corporate_actions() -> pd.DataFrame:
    actions = pd.read_csv(
        CORPORATE_ACTIONS_AUDIT, index_col="date", parse_dates=True
    ).sort_index()
    if int((actions["dividend_per_share"] > 0).sum()) != 21:
        raise AssertionError("corporate-action dividend audit drift")
    if int((actions["stock_split_ratio"] > 0).sum()) != 8:
        raise AssertionError("corporate-action split audit drift")
    return actions


def _load_qqq_distributions() -> pd.Series:
    audit = pd.read_csv(
        QQQ_DISTRIBUTIONS_AUDIT, index_col="date", parse_dates=True
    ).sort_index()
    dividends = audit["dividend_per_share"]
    if int((dividends > 0).sum()) != 69:
        raise AssertionError("QQQ distribution audit drift")
    return dividends


def _credit_earned_distributions(
    trades: pd.DataFrame, dividends: pd.Series
) -> Tuple[pd.DataFrame, List[Dict[str, object]]]:
    """Credit distributions earned by positions held before the ex-date."""
    adjusted = trades.copy()
    details: List[Dict[str, object]] = []
    positive = dividends[dividends > 0]
    for trade_idx, trade in adjusted.iterrows():
        entry_date = pd.Timestamp(trade["entry_timestamp"]).date()
        exit_date = pd.Timestamp(trade["exit_timestamp"]).date()
        earned = positive[
            (positive.index.date > entry_date)
            & (positive.index.date <= exit_date)
        ]
        if earned.empty:
            continue
        direction = int(trade["direction"])
        credit = (
            direction
            * float(earned.sum())
            / float(trade["entry_price"])
        )
        adjusted.at[trade_idx, "return"] = float(trade["return"]) + credit
        details.append(
            dict(
                entry_timestamp=str(trade["entry_timestamp"]),
                exit_timestamp=str(trade["exit_timestamp"]),
                exit_type=str(trade["exit_type"]),
                direction=direction,
                ex_dates=[str(idx.date()) for idx in earned.index],
                cash_per_share=round(float(earned.sum()), 6),
                trade_return_credit_bps=round(credit * 10000, 3),
            )
        )
    return adjusted, details


def corporate_action_gap_audit(
    sig: pd.DataFrame,
    daily_panel: pd.DataFrame,
    session_close_prices: Dict[object, float],
) -> Dict[str, object]:
    """Separate raw stop mechanics from dividend-inclusive wealth accounting."""
    actions = _load_corporate_actions()
    dividends = actions["dividend_per_share"].reindex(
        daily_panel.index, fill_value=0.0
    )
    prior_close = daily_panel["TQQQ_close"].shift(1)
    raw_gap = daily_panel["TQQQ_open"] / prior_close - 1
    wealth_gap = (
        daily_panel["TQQQ_open"] + dividends
    ) / prior_close - 1
    frame = pd.concat(
        [
            raw_gap.rename("raw_gap"),
            wealth_gap.rename("distribution_inclusive_gap"),
            dividends.rename("dividend"),
        ],
        axis=1,
    ).dropna()
    threshold_rows = []
    for threshold in (0.005, 0.01, 0.02, 0.04):
        raw_event = frame["raw_gap"] <= -threshold
        wealth_event = frame["distribution_inclusive_gap"] <= -threshold
        threshold_rows.append(
            dict(
                loss_threshold_pct=round(threshold * 100, 2),
                raw_price_events=int(raw_event.sum()),
                distribution_inclusive_events=int(wealth_event.sum()),
                classifications_removed_by_distribution=int(
                    (raw_event & ~wealth_event).sum()
                ),
                classifications_added_by_distribution=int(
                    (~raw_event & wealth_event).sum()
                ),
            )
        )
    ex_rows = []
    for idx, row in frame.loc[frame["dividend"] > 0].iterrows():
        dividend_yield = float(row["dividend"] / prior_close.loc[idx])
        ex_rows.append(
            dict(
                ex_date=str(idx.date()),
                dividend_per_share=round(float(row["dividend"]), 6),
                dividend_yield_vs_prior_close_pct=round(
                    dividend_yield * 100, 4
                ),
                raw_gap_pct=round(float(row["raw_gap"]) * 100, 4),
                distribution_inclusive_gap_pct=round(
                    float(row["distribution_inclusive_gap"]) * 100, 4
                ),
                raw_crosses_half_pct_stop=bool(row["raw_gap"] <= -0.005),
                inclusive_crosses_half_pct_stop=bool(
                    row["distribution_inclusive_gap"] <= -0.005
                ),
            )
        )

    target, stop = 0.01, 0.005
    bars = int(getattr(config, "MAX_TRADE_BARS_LIVE", 10))
    baseline = simulate(
        sig, target, stop, bars,
        gap_aware=True, one_position=True, scan_entry_bar=True,
    )
    baseline_adjusted, baseline_credits = _credit_earned_distributions(
        baseline, dividends
    )
    vol20 = _lagged_qqq_volatility(daily_panel, window=20).dropna()
    vol_dates = {idx.date() for idx, value in vol20.items() if value >= 0.15}
    vol_policy = simulate(
        sig, target, stop, bars,
        gap_aware=True, one_position=True, scan_entry_bar=True,
        flatten_before_dates=vol_dates,
        session_close_prices=session_close_prices,
    )
    vol_adjusted, vol_credits = _credit_earned_distributions(
        vol_policy, dividends
    )
    daily_policy = simulate(
        sig, target, stop, bars,
        gap_aware=True, one_position=True, scan_entry_bar=True,
        flatten_eod=True,
        session_close_prices=session_close_prices,
    )
    daily_adjusted, daily_credits = _credit_earned_distributions(
        daily_policy, dividends
    )

    def policy_row(
        name: str,
        raw_trades: pd.DataFrame,
        adjusted_trades: pd.DataFrame,
        credits: List[Dict[str, object]],
    ) -> Dict[str, object]:
        raw_metrics = equity_metrics(raw_trades)
        adjusted_metrics = equity_metrics(adjusted_trades)
        return dict(
            policy=name,
            raw_price_metrics=raw_metrics,
            distribution_inclusive_metrics=adjusted_metrics,
            total_return_correction_pp=round(
                adjusted_metrics["total_return_pct"]
                - raw_metrics["total_return_pct"],
                4,
            ),
            trades_earning_distributions=len(credits),
            distribution_credit_events=credits,
        )

    policy_rows = [
        policy_row(
            "hold_overnight_gap_aware",
            baseline,
            baseline_adjusted,
            baseline_credits,
        ),
        policy_row(
            "lagged_vol20_at_least_15pct_flatten",
            vol_policy,
            vol_adjusted,
            vol_credits,
        ),
        policy_row(
            "daily_flatten",
            daily_policy,
            daily_adjusted,
            daily_credits,
        ),
    ]
    adjusted_baseline_return = policy_rows[0][
        "distribution_inclusive_metrics"
    ]["total_return_pct"]
    for row in policy_rows[1:]:
        row["distribution_inclusive_return_delta_vs_hold_pp"] = round(
            row["distribution_inclusive_metrics"]["total_return_pct"]
            - adjusted_baseline_return,
            4,
        )
    baseline_gap_exdates = [
        detail for detail in baseline_credits
        if detail["exit_type"] == "overnight_gap_stop"
    ]
    return dict(
        construction=(
            "Raw opens determine whether an actual stop is crossed. Economic trade "
            "wealth separately credits cash distributions to positions entered before "
            "the ex-date and held through it; short positions would owe the cash."
        ),
        source=dict(
            actions="Yahoo Finance via yfinance actions=True, auto_adjust=False",
            raw_source_sha256=CORPORATE_ACTIONS_SOURCE_SHA256,
            durable_audit=os.path.relpath(CORPORATE_ACTIONS_AUDIT, REPO),
            official_crosscheck=(
                "ProShares reports TQQQ 2026-06-24 distribution $0.171229 "
                "versus Yahoo's rounded $0.171"
            ),
        ),
        n_dividend_dates=int((dividends > 0).sum()),
        n_split_dates=int((actions["stock_split_ratio"] > 0).sum()),
        threshold_rows=threshold_rows,
        ex_dividend_rows=ex_rows,
        policy_rows=policy_rows,
        baseline_gap_stops_on_distribution_ex_dates=len(baseline_gap_exdates),
        baseline_gap_stop_distribution_details=baseline_gap_exdates,
        verdict=(
            "Use raw prices for stop-trigger mechanics and distribution-inclusive "
            "returns for wealth. The audit measures whether omitting cash distributions "
            "changes any decision-relevant conclusion."
        ),
        caveat=(
            "Cash is credited without tax, payment-date delay, or reinvestment. Yahoo "
            "actions are a vendor source; the latest distribution is cross-checked to "
            "the sponsor, but the full historical action table is not independently "
            "reconciled to every sponsor notice."
        ),
    )


def session_open_validation(
    hourly: pd.DataFrame,
    sig: pd.DataFrame,
    daily_panel: pd.DataFrame,
) -> Dict[str, object]:
    """Validate first-hour gap fills against the vendor's daily-bar open."""
    hourly_open = hourly.groupby(hourly.index.date).first()["open"]
    hourly_open.index = pd.to_datetime(hourly_open.index)
    pair = pd.concat(
        [
            hourly_open.rename("first_hour_open"),
            daily_panel["TQQQ_open"].rename("daily_open"),
        ],
        axis=1,
    ).dropna()
    pair["difference_bps"] = (
        pair["first_hour_open"] / pair["daily_open"] - 1
    ) * 10000
    pair["absolute_difference_bps"] = pair["difference_bps"].abs()
    worst = pair.nlargest(10, "absolute_difference_bps")
    known_early_closes = {
        pd.Timestamp(value).date()
        for value in (
            "2024-11-29",
            "2024-12-24",
            "2025-07-03",
            "2025-11-28",
            "2025-12-24",
        )
    }
    quality_rows = []
    unexpected_partial_dates = []
    for session_date, cut in hourly.groupby(hourly.index.date):
        n_bars = int(len(cut))
        if n_bars == 7:
            continue
        expected_early_close = session_date in known_early_closes
        if not expected_early_close:
            unexpected_partial_dates.append(session_date)
        quality_rows.append(
            dict(
                date=str(session_date),
                bars=n_bars,
                first_bar_et=str(cut.index[0].time()),
                last_bar_et=str(cut.index[-1].time()),
                expected_early_close=expected_early_close,
            )
        )
    clean_pair = pair.loc[
        [idx.date() not in unexpected_partial_dates for idx in pair.index]
    ]

    daily_open_prices = {
        idx.date(): float(value)
        for idx, value in pair["daily_open"].items()
    }
    target, stop = 0.01, 0.005
    bars = int(getattr(config, "MAX_TRADE_BARS_LIVE", 10))
    hourly_trades = simulate(
        sig, target, stop, bars,
        gap_aware=True, one_position=True, scan_entry_bar=True,
    )
    daily_open_trades = simulate(
        sig, target, stop, bars,
        gap_aware=True, one_position=True, scan_entry_bar=True,
        session_open_prices=daily_open_prices,
    )
    if len(hourly_trades) != len(daily_open_trades):
        raise AssertionError("daily-open sensitivity changed trade count")
    changed = []
    for (_, hourly_trade), (_, daily_trade) in zip(
        hourly_trades.iterrows(), daily_open_trades.iterrows()
    ):
        if (
            hourly_trade["exit_type"] != daily_trade["exit_type"]
            or abs(
                float(hourly_trade["return"])
                - float(daily_trade["return"])
            ) > 1e-12
        ):
            changed.append(
                dict(
                    signal_timestamp=str(hourly_trade["signal_timestamp"]),
                    exit_timestamp=str(hourly_trade["exit_timestamp"]),
                    hourly_exit_type=str(hourly_trade["exit_type"]),
                    daily_open_exit_type=str(daily_trade["exit_type"]),
                    hourly_exit_price=round(
                        float(hourly_trade["exit_price"]), 6
                    ),
                    daily_open_exit_price=round(
                        float(daily_trade["exit_price"]), 6
                    ),
                    hourly_return_pct=round(
                        float(hourly_trade["return"]) * 100, 4
                    ),
                    daily_open_return_pct=round(
                        float(daily_trade["return"]) * 100, 4
                    ),
                    difference_bps=round(
                        (
                            float(daily_trade["return"])
                            - float(hourly_trade["return"])
                        ) * 10000,
                        3,
                    ),
                )
            )
    hourly_metrics = equity_metrics(hourly_trades)
    daily_metrics = equity_metrics(daily_open_trades)
    clean_hourly = hourly.loc[
        [
            idx.date() not in unexpected_partial_dates
            for idx in hourly.index
        ]
    ]
    clean_sig = signal_frame(clean_hourly)
    clean_trades = simulate(
        clean_sig, target, stop, bars,
        gap_aware=True, one_position=True, scan_entry_bar=True,
    )
    clean_metrics = equity_metrics(clean_trades)
    return dict(
        construction=(
            "Pair each regular session's first 09:30 hourly-bar open with Yahoo's "
            "daily-bar TQQQ open. For the strategy sensitivity, keep entries/signals "
            "fixed and substitute the daily open only when an already-open position "
            "crosses into a new session."
        ),
        n_sessions=int(len(pair)),
        median_abs_difference_bps=round(
            float(pair["absolute_difference_bps"].median()), 4
        ),
        p95_abs_difference_bps=round(
            float(pair["absolute_difference_bps"].quantile(0.95)), 4
        ),
        maximum_abs_difference_bps=round(
            float(pair["absolute_difference_bps"].max()), 4
        ),
        pct_abs_difference_gt_1bps=round(
            float((pair["absolute_difference_bps"] > 1).mean()) * 100, 3
        ),
        pct_abs_difference_gt_5bps=round(
            float((pair["absolute_difference_bps"] > 5).mean()) * 100, 3
        ),
        pct_abs_difference_gt_10bps=round(
            float((pair["absolute_difference_bps"] > 10).mean()) * 100, 3
        ),
        excluding_unexpected_partial_sessions=dict(
            n_sessions=int(len(clean_pair)),
            median_abs_difference_bps=round(
                float(clean_pair["absolute_difference_bps"].median()), 4
            ),
            p95_abs_difference_bps=round(
                float(clean_pair["absolute_difference_bps"].quantile(0.95)), 4
            ),
            maximum_abs_difference_bps=round(
                float(clean_pair["absolute_difference_bps"].max()), 4
            ),
        ),
        session_completeness=dict(
            expected_bars_full_session=7,
            expected_bars_early_close=3,
            non_seven_bar_rows=quality_rows,
            unexpected_partial_session_dates=[
                str(value) for value in unexpected_partial_dates
            ],
            defect_recomputed_strategy_metrics=clean_metrics,
            defect_exclusion_total_return_delta_pp=round(
                clean_metrics["total_return_pct"]
                - hourly_metrics["total_return_pct"],
                4,
            ),
            defect_exclusion_maxdd_delta_pp=round(
                clean_metrics["max_drawdown_pct"]
                - hourly_metrics["max_drawdown_pct"],
                4,
            ),
        ),
        worst_rows=[
            dict(
                date=str(idx.date()),
                first_hour_open=round(float(row["first_hour_open"]), 6),
                daily_open=round(float(row["daily_open"]), 6),
                difference_bps=round(float(row["difference_bps"]), 4),
            )
            for idx, row in worst.iterrows()
        ],
        strategy_sensitivity=dict(
            first_hour_open_metrics=hourly_metrics,
            daily_bar_open_metrics=daily_metrics,
            total_return_delta_pp=round(
                daily_metrics["total_return_pct"]
                - hourly_metrics["total_return_pct"],
                4,
            ),
            maxdd_delta_pp=round(
                daily_metrics["max_drawdown_pct"]
                - hourly_metrics["max_drawdown_pct"],
                4,
            ),
            changed_trades=len(changed),
            changed_trade_rows=changed,
        ),
        caveat=(
            "Both series come from Yahoo and are not independent vendor confirmation. "
            "The daily Feb 2 open is independently visible in public historical tables, "
            "but the broad test isolates serialization/interval consistency, not auction "
            "prints, spread, latency, or executable liquidity. Dropping defective sessions "
            "also changes feature history and is only a sensitivity."
        ),
    )


def corrected_execution_ledger(
    hourly: pd.DataFrame,
    sig: pd.DataFrame,
    daily_panel: pd.DataFrame,
    session_close_prices: Dict[object, float],
) -> Dict[str, object]:
    """Consolidate source and wealth corrections into one decision baseline."""
    target, stop = 0.01, 0.005
    bars = int(getattr(config, "MAX_TRADE_BARS_LIVE", 10))
    daily_open_prices = {
        idx.date(): float(value)
        for idx, value in daily_panel["TQQQ_open"].dropna().items()
    }
    actions = _load_corporate_actions()
    dividends = actions["dividend_per_share"].reindex(
        daily_panel.index, fill_value=0.0
    )
    vol20 = _lagged_qqq_volatility(daily_panel, window=20).dropna()
    vol_dates = {idx.date() for idx, value in vol20.items() if value >= 0.15}

    def replay(
        signal: pd.DataFrame,
        use_daily_open: bool,
        policy: str,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, List[Dict[str, object]]]:
        kwargs: Dict[str, object] = {}
        if use_daily_open:
            kwargs["session_open_prices"] = daily_open_prices
        if policy == "vol20_at_least_15pct":
            kwargs["flatten_before_dates"] = vol_dates
            kwargs["session_close_prices"] = session_close_prices
        elif policy == "daily_flatten":
            kwargs["flatten_eod"] = True
            kwargs["session_close_prices"] = session_close_prices
        raw = simulate(
            signal, target, stop, bars,
            gap_aware=True, one_position=True, scan_entry_bar=True,
            **kwargs,
        )
        inclusive, credits = _credit_earned_distributions(raw, dividends)
        return raw, inclusive, credits

    hold_hourly, hold_hourly_cash, hourly_credits = replay(
        sig, False, "hold_overnight"
    )
    hold_daily, hold_daily_cash, daily_credits = replay(
        sig, True, "hold_overnight"
    )
    legacy_metrics = equity_metrics(hold_hourly)
    hourly_cash_metrics = equity_metrics(hold_hourly_cash)
    daily_metrics = equity_metrics(hold_daily)
    joint_metrics = equity_metrics(hold_daily_cash)
    dividend_delta = (
        hourly_cash_metrics["total_return_pct"]
        - legacy_metrics["total_return_pct"]
    )
    open_delta = (
        daily_metrics["total_return_pct"]
        - legacy_metrics["total_return_pct"]
    )
    joint_delta = (
        joint_metrics["total_return_pct"]
        - legacy_metrics["total_return_pct"]
    )

    unexpected_partial_dates = {
        pd.Timestamp("2026-01-30").date(),
        pd.Timestamp("2026-02-02").date(),
    }
    clean_hourly = hourly.loc[
        [idx.date() not in unexpected_partial_dates for idx in hourly.index]
    ]
    clean_sig = signal_frame(clean_hourly)
    _, clean_joint, clean_credits = replay(
        clean_sig, True, "hold_overnight"
    )

    ladder = [
        dict(
            accounting="legacy_first_hour_open_raw_price",
            metrics=legacy_metrics,
            delta_vs_legacy_pp=0.0,
            n_distribution_credits=0,
        ),
        dict(
            accounting="first_hour_open_distribution_inclusive",
            metrics=hourly_cash_metrics,
            delta_vs_legacy_pp=round(dividend_delta, 4),
            n_distribution_credits=len(hourly_credits),
        ),
        dict(
            accounting="daily_bar_open_raw_price",
            metrics=daily_metrics,
            delta_vs_legacy_pp=round(open_delta, 4),
            n_distribution_credits=0,
        ),
        dict(
            accounting="daily_bar_open_distribution_inclusive",
            metrics=joint_metrics,
            delta_vs_legacy_pp=round(joint_delta, 4),
            n_distribution_credits=len(daily_credits),
        ),
        dict(
            accounting="daily_bar_open_distribution_inclusive_exclude_two_partial_sessions",
            metrics=equity_metrics(clean_joint),
            delta_vs_legacy_pp=round(
                equity_metrics(clean_joint)["total_return_pct"]
                - legacy_metrics["total_return_pct"],
                4,
            ),
            n_distribution_credits=len(clean_credits),
        ),
    ]

    corrected_policy_trades = {
        "hold_overnight": (hold_daily, hold_daily_cash, daily_credits),
        "vol20_at_least_15pct": replay(
            sig, True, "vol20_at_least_15pct"
        ),
        "daily_flatten": replay(sig, True, "daily_flatten"),
    }
    baseline_gaps = int(hold_daily["overnight_gap_stop"].sum())
    baseline_metrics = joint_metrics
    policy_rows = []
    for policy, (raw, inclusive, credits) in corrected_policy_trades.items():
        metrics = equity_metrics(inclusive)
        gap_stops = int(raw["overnight_gap_stop"].sum())
        if policy == "vol20_at_least_15pct":
            exits = int((raw["exit_type"] == "risk_flatten").sum())
        elif policy == "daily_flatten":
            exits = int((raw["exit_type"] == "eod_flatten").sum())
        else:
            exits = 0
        return_delta = (
            metrics["total_return_pct"] - baseline_metrics["total_return_pct"]
        )
        dd_improvement = (
            metrics["max_drawdown_pct"]
            - baseline_metrics["max_drawdown_pct"]
        )
        gap_reduction = (
            (1 - gap_stops / max(1, baseline_gaps)) * 100
            if policy != "hold_overnight" else 0.0
        )
        break_even = (
            (return_delta / 100)
            / exits
            / POSITION_FRACTION
            * 10000
            if exits else None
        )
        policy_rows.append(
            dict(
                policy=policy,
                metrics=metrics,
                raw_price_metrics=equity_metrics(raw),
                held_overnight=int(raw["held_overnight"].sum()),
                overnight_gap_stops=gap_stops,
                flatten_exits=exits,
                distribution_credit_events=len(credits),
                gap_reduction_pct=round(gap_reduction, 2),
                maxdd_improvement_vs_hold_pp=round(dd_improvement, 4),
                total_return_delta_vs_hold_pp=round(return_delta, 4),
                first_order_break_even_extra_cost_bps_per_exit=(
                    round(break_even, 2) if break_even is not None else None
                ),
                risk_gate_pass=bool(
                    policy != "hold_overnight"
                    and gap_reduction >= 50
                    and dd_improvement >= 2
                    and return_delta >= -1
                ),
            )
        )

    return dict(
        authoritative_convention=(
            "Use the daily raw open for held-position gap-fill mechanics, the official "
            "daily close only as a flatten counterfactual proxy, and credit cash "
            "distributions separately to positions that earned them."
        ),
        correction_ladder=ladder,
        correction_decomposition_pp=dict(
            dividend_only=round(dividend_delta, 4),
            daily_open_only=round(open_delta, 4),
            joint=round(joint_delta, 4),
            compounding_interaction=round(
                joint_delta - dividend_delta - open_delta, 4
            ),
        ),
        corrected_policy_rows=policy_rows,
        decision=(
            "The corrected hold path remains negative. Both mitigation policies still "
            "pass the descriptive risk gate, but neither is approved: vol20 is selected "
            "in-sample and both require real closing-auction cost evidence."
        ),
        caveat=(
            "The daily open and hourly bars share a vendor. Defect exclusion changes "
            "signals and sample size, so it is a sensitivity rather than the primary "
            "baseline. Distribution credits omit taxes, payment delay, and reinvestment."
        ),
    )


def close_proxy_policy_sensitivity(
    hourly: pd.DataFrame,
    sig: pd.DataFrame,
    daily_panel: pd.DataFrame,
) -> Dict[str, object]:
    """Test mitigation policy conclusions under two closing-price proxies."""
    target, stop = 0.01, 0.005
    bars = int(getattr(config, "MAX_TRADE_BARS_LIVE", 10))
    daily_open_prices = {
        idx.date(): float(value)
        for idx, value in daily_panel["TQQQ_open"].dropna().items()
    }
    official_close_prices = {
        idx.date(): float(value)
        for idx, value in daily_panel["TQQQ_close"].dropna().items()
    }
    last_hourly_close_prices = {
        session_date: float(cut.iloc[-1]["close"])
        for session_date, cut in hourly.groupby(hourly.index.date)
    }
    actions = _load_corporate_actions()
    dividends = actions["dividend_per_share"].reindex(
        daily_panel.index, fill_value=0.0
    )
    vol20 = _lagged_qqq_volatility(daily_panel, window=20).dropna()
    vol_dates = {idx.date() for idx, value in vol20.items() if value >= 0.15}

    hold_raw = simulate(
        sig, target, stop, bars,
        gap_aware=True, one_position=True, scan_entry_bar=True,
        session_open_prices=daily_open_prices,
    )
    hold, _ = _credit_earned_distributions(hold_raw, dividends)
    hold_metrics = equity_metrics(hold)
    policy_rows = []
    for policy in ("vol20_at_least_15pct", "daily_flatten"):
        common: Dict[str, object] = dict(
            session_open_prices=daily_open_prices,
        )
        if policy == "vol20_at_least_15pct":
            common["flatten_before_dates"] = vol_dates
            flatten_type = "risk_flatten"
        else:
            common["flatten_eod"] = True
            flatten_type = "eod_flatten"
        raw_by_proxy = {}
        adjusted_by_proxy = {}
        for proxy, close_prices in (
            ("official_daily_close", official_close_prices),
            ("last_hourly_close", last_hourly_close_prices),
        ):
            raw = simulate(
                sig, target, stop, bars,
                gap_aware=True, one_position=True, scan_entry_bar=True,
                session_close_prices=close_prices,
                **common,
            )
            adjusted, _ = _credit_earned_distributions(raw, dividends)
            raw_by_proxy[proxy] = raw
            adjusted_by_proxy[proxy] = adjusted
        official = adjusted_by_proxy["official_daily_close"]
        hourly_proxy = adjusted_by_proxy["last_hourly_close"]
        if (
            official["signal_timestamp"].tolist()
            != hourly_proxy["signal_timestamp"].tolist()
            or official["exit_type"].tolist()
            != hourly_proxy["exit_type"].tolist()
        ):
            raise AssertionError("close proxy changed policy trade path")
        flatten_mask = raw_by_proxy["official_daily_close"][
            "exit_type"
        ] == flatten_type
        trade_return_diff_bps = (
            official.loc[flatten_mask, "return"].to_numpy(dtype=float)
            - hourly_proxy.loc[flatten_mask, "return"].to_numpy(dtype=float)
        ) * 10000
        official_metrics = equity_metrics(official)
        hourly_metrics = equity_metrics(hourly_proxy)
        exits = int(flatten_mask.sum())

        def cost_ceiling(metrics: Dict[str, float]) -> float:
            return (
                (
                    metrics["total_return_pct"]
                    - hold_metrics["total_return_pct"]
                )
                / 100
                / max(1, exits)
                / POSITION_FRACTION
                * 10000
            )

        official_delta = (
            official_metrics["total_return_pct"]
            - hold_metrics["total_return_pct"]
        )
        hourly_delta = (
            hourly_metrics["total_return_pct"]
            - hold_metrics["total_return_pct"]
        )
        official_dd = (
            official_metrics["max_drawdown_pct"]
            - hold_metrics["max_drawdown_pct"]
        )
        hourly_dd = (
            hourly_metrics["max_drawdown_pct"]
            - hold_metrics["max_drawdown_pct"]
        )
        policy_rows.append(
            dict(
                policy=policy,
                flatten_exits=exits,
                official_daily_close_metrics=official_metrics,
                last_hourly_close_metrics=hourly_metrics,
                official_minus_hourly_total_return_pp=round(
                    official_metrics["total_return_pct"]
                    - hourly_metrics["total_return_pct"],
                    4,
                ),
                official_minus_hourly_maxdd_pp=round(
                    official_metrics["max_drawdown_pct"]
                    - hourly_metrics["max_drawdown_pct"],
                    4,
                ),
                flattened_trade_return_difference_bps=dict(
                    mean_signed=round(
                        float(np.mean(trade_return_diff_bps)), 3
                    ),
                    median_signed=round(
                        float(np.median(trade_return_diff_bps)), 3
                    ),
                    median_absolute=round(
                        float(np.median(np.abs(trade_return_diff_bps))), 3
                    ),
                    p95_absolute=round(
                        float(np.percentile(
                            np.abs(trade_return_diff_bps), 95
                        )),
                        3,
                    ),
                    maximum_absolute=round(
                        float(np.max(np.abs(trade_return_diff_bps))), 3
                    ),
                ),
                official_daily_close_delta_vs_hold_pp=round(
                    official_delta, 4
                ),
                last_hourly_close_delta_vs_hold_pp=round(
                    hourly_delta, 4
                ),
                official_daily_close_cost_ceiling_bps=round(
                    cost_ceiling(official_metrics), 2
                ),
                last_hourly_close_cost_ceiling_bps=round(
                    cost_ceiling(hourly_metrics), 2
                ),
                official_daily_close_risk_gate_pass=bool(
                    official_dd >= 2 and official_delta >= -1
                    and int(raw_by_proxy["official_daily_close"][
                        "overnight_gap_stop"
                    ].sum()) <= int(hold_raw["overnight_gap_stop"].sum()) / 2
                ),
                last_hourly_close_risk_gate_pass=bool(
                    hourly_dd >= 2 and hourly_delta >= -1
                    and int(raw_by_proxy["last_hourly_close"][
                        "overnight_gap_stop"
                    ].sum()) <= int(hold_raw["overnight_gap_stop"].sum()) / 2
                ),
            )
        )
    return dict(
        corrected_hold_metrics=hold_metrics,
        policy_rows=policy_rows,
        interpretation=(
            "The official daily close is the preferred vendor proxy, but policy "
            "conclusions must survive the last-hourly-close alternative. Agreement "
            "does not validate actual MOC execution."
        ),
        caveat=(
            "Both proxies are Yahoo prints. Neither contains auction imbalance, spread, "
            "latency, fees, market impact, or a broker fill; cost ceilings remain the "
            "decision boundary."
        ),
    )


def closing_auction_evidence_protocol(
    hourly: pd.DataFrame,
    close_proxy: Dict[str, object],
) -> Dict[str, object]:
    """Freeze the evidence needed to test real closing-auction cost."""
    sample_years = (
        hourly.index[-1].date() - hourly.index[0].date()
    ).days / 365.2425

    def zero_breach_upper95(n: int) -> float:
        return (1.0 - 0.05 ** (1.0 / n)) * 100

    horizon_rows = []
    for row in close_proxy["policy_rows"]:
        exits = int(row["flatten_exits"])
        annual_rate = exits / sample_years
        conservative_ceiling = float(
            row["last_hourly_close_cost_ceiling_bps"]
        )
        horizon_rows.append(
            dict(
                policy=row["policy"],
                historical_proxy_exits=exits,
                observed_exit_rate_per_year=round(annual_rate, 2),
                conservative_break_even_cost_ceiling_bps=conservative_ceiling,
                fixed_minimum_intended_auction_events=60,
                expected_years_to_60_at_observed_rate=round(
                    60 / annual_rate, 2
                ),
                zero_operational_failures_one_sided_95_upper_rate_pct=round(
                    zero_breach_upper95(60), 3
                ),
            )
        )
    fee_per_share = 0.0016
    fee_scale_rows = []
    for reference_price in (40.0, 60.0, 80.0):
        fee_bps = fee_per_share / reference_price * 10000
        fee_scale_rows.append(
            dict(
                reference_price=reference_price,
                exchange_fee_usd_per_share=fee_per_share,
                exchange_fee_bps=round(fee_bps, 4),
                share_of_vol15_61_40bp_ceiling_pct=round(
                    fee_bps / 61.40 * 100, 3
                ),
                share_of_daily_34_62bp_ceiling_pct=round(
                    fee_bps / 34.62 * 100, 3
                ),
            )
        )
    return dict(
        scope=(
            "Evidence specification only. MONAD remains PAPER ONLY and this harness "
            "must not submit or simulate-live MOC orders."
        ),
        exchange_facts=dict(
            primary_listing="Nasdaq-listed TQQQ",
            moc_acceptance_cutoff_regular_session_et="15:55:00",
            cancel_or_modify_lock_regular_session_et="15:50:00",
            closing_cross_regular_session_et="16:00:00",
            early_close_noii_et="12:55:00",
            early_close_cross_et="13:00:00",
            noii_access=(
                "Subscription data via Nasdaq TotalView, DataStore, distributors, "
                "or service bureaus"
            ),
            moc_execution_guaranteed=False,
            ibkr_smart_route_destination=(
                "Primary listing exchange for MOC orders"
            ),
            paper_limitation=(
                "IBKR paper accounts do not support Auction orders"
            ),
            current_ibkr_nasdaq_moc_exchange_fee_usd_per_share=0.0016,
            standard_cross_price_identity=(
                "Every order executed in the Nasdaq Closing Cross executes at "
                "the single Cross price; for a Nasdaq-listed security with a "
                "qualifying Cross, that price is the NOCP."
            ),
            etp_nocp_exception=(
                "If a Nasdaq-listed ETP has no Closing Cross or the Cross is "
                "less than one round lot, Nasdaq uses a 15:58:00-15:59:55 "
                "time-weighted NBBO midpoint as NOCP."
            ),
        ),
        primary_sources=[
            "https://www.nasdaqtrader.com/Trader.aspx?id=OpenClose",
            "https://www.nasdaqtrader.com/content/productsservices/Trading/ClosingCrossfaq.pdf",
            "https://www.nasdaqtrader.com/content/productsservices/trading/crosses/openclose_faqs.pdf",
            "https://www.nasdaqtrader.com/trader.aspx?id=Calendar",
            "https://www.interactivebrokers.com/campus/ibkr-api-page/order-types/",
            "https://www.interactivebrokers.com/campus/glossary-terms/paper-trading-account/",
            "https://investors.interactivebrokers.com/en/trading/ordertypes.php",
            "https://investors.interactivebrokers.com/en/index.php?f=936",
            "https://www.nasdaq.com/market-activity/etf/tqqq/historical-nocp",
            "https://listingcenter.nasdaq.com/rulebook/nasdaq/rules/Nasdaq%20Equity%204",
        ],
        required_event_fields=[
            "pseudonymous_trial_event_id (never broker account id)",
            "exchange_session_date and early_close_flag",
            "frozen_policy_version and pre-close decision timestamp ET",
            "position_direction, shares, and pre-order position snapshot",
            "order type, TIF, route, submit timestamp, broker acknowledgement",
            "order status transitions, rejects, cancels, and reason codes",
            "fill timestamps, quantities, prices, commissions, and fees",
            "Nasdaq Official Closing Price (NOCP)",
            "NOCP method: qualifying Closing Cross, T-WAM ETP fallback, halt, or contingency",
            "Closing Cross total shares and whether at least one round lot executed",
            "15:49:xx bid, ask, sizes, and source",
            "NOII paired shares, imbalance side/size, reference and indicative prices if licensed",
            "corporate action and market-halt flags",
        ],
        endpoint_correction=(
            "For a standard qualifying Nasdaq Closing Cross, fill-minus-NOCP is "
            "a reconciliation identity, not a random implementation-shortfall "
            "sample. Observable incremental cost is commissions plus fees. The "
            "unobservable component is the order's own effect on the counterfactual "
            "NOCP that would have formed without it."
        ),
        all_in_cost_definition=(
            "Standard Cross: (commissions + fees)/notional*10,000, with fill "
            "VWAP required to reconcile to the Cross/NOCP price. T-WAM, halt, "
            "contingency, partial, rejected, and unfilled events are reported "
            "separately and never silently discarded. Self-impact is not "
            "identified by fill-minus-published-NOCP."
        ),
        fixed_operational_gate=dict(
            minimum_intended_events=60,
            data_completeness_pct=100.0,
            permitted_rejects_or_unfilled_events=0,
            consequence=(
                "With zero operational failures among 60 intended events, the "
                "one-sided exact 95% upper bound on reject/unfilled probability "
                "is 4.87%. The denominator is all intended events, not only fills."
            ),
            rejection_rules=[
                "any missing required field or hidden account identifier",
                "any broker reject/unfilled flatten",
                "standard-Cross fill that does not reconcile to the Cross price",
                "fees plus commissions above the conservative policy ceiling",
                "T-WAM/halt/contingency event pooled with standard Cross events",
                "policy logic or threshold changed before the fixed horizon",
            ],
        ),
        self_impact_limit=(
            "Published NOCP already contains the submitted MOC order, so comparing "
            "its fill with that NOCP cannot estimate self-impact. Record order "
            "shares, paired shares, imbalance, and indicative-price changes; do "
            "not claim causal market-impact approval without an independent design."
        ),
        fee_scale_rows=fee_scale_rows,
        horizon_rows=horizon_rows,
        decision=(
            "The 60-event horizon is an operational reliability gate, not a "
            "fill-versus-NOCP cost experiment. MONAD paper can validate logging "
            "only; it cannot observe Auction routing, rejection, or self-impact."
        ),
    )


def closing_auction_runtime_readiness_audit() -> Dict[str, object]:
    """Read-only static audit of the current trader's MOC implementation gaps."""
    relative_paths = [
        "live/trader.py",
        "live/broker.py",
        "live/signals.py",
        "ops/systemd/monad-trader.timer",
    ]
    sources = {}
    source_hashes = {}
    for relative_path in relative_paths:
        absolute_path = os.path.join(REPO, relative_path)
        with open(absolute_path, "rb") as fh:
            raw = fh.read()
        sources[relative_path] = raw.decode("utf-8")
        source_hashes[relative_path] = hashlib.sha256(raw).hexdigest()

    trader = sources["live/trader.py"]
    broker = sources["live/broker.py"]
    signals = sources["live/signals.py"]
    timer = sources["ops/systemd/monad-trader.timer"]
    all_live = "\n".join((trader, broker, signals))

    checks = dict(
        scheduler_has_1532_cycle=(
            'hour="9-15"' in trader and 'minute="32"' in trader
        ),
        scheduler_weekdays_only=('day_of_week="mon-fri"' in trader),
        market_hours_hardcodes_1600=(
            "market_close = et_now.replace(hour=16" in trader
        ),
        service_starts_0922_et=(
            "09:22:00 America/New_York" in timer
        ),
        signal_fetches_hourly_yfinance=(
            'interval="1h"' in signals and "fetch_yfinance" in signals
        ),
        signal_drops_less_than_60_minute_bar=(
            "last_bar_age < pd.Timedelta(minutes=60)" in signals
        ),
        close_path_uses_market_order=(
            "close_order = MarketOrder(close_action, qty)" in broker
        ),
        moc_order_constructor_present=(
            "MarketOnCloseOrder" in all_live
            or 'orderType = "MOC"' in all_live
            or "orderType = 'MOC'" in all_live
        ),
        moc_cutoff_deadline_guard_present=(
            "15:55" in all_live or "moc_cutoff" in all_live.lower()
        ),
        exchange_calendar_or_early_close_guard_present=(
            "exchange_calendar" in all_live.lower()
            or "early_close" in all_live.lower()
        ),
        selected_vol20_policy_present=(
            "vol20" in all_live.lower()
            or (
                "QQQ" in all_live
                and "rolling(20)" in all_live
            )
        ),
        nocp_or_noii_capture_present=(
            "NOCP" in all_live or "NOII" in all_live
        ),
        position_bar_count_increment_is_cycle_based=(
            "bar_count = state.increment_bar_count()" in trader
        ),
        explicit_last_processed_bar_dedup_guard_present=(
            "last_processed_bar" in trader
            or "processed_bar_time" in trader
        ),
    )

    return dict(
        scope=(
            "Read-only static audit. No live, broker, signal, order, or "
            "configuration path is modified."
        ),
        audited_source_sha256=source_hashes,
        nominal_clock=dict(
            final_regular_session_cycle_et="15:32:00",
            nasdaq_cancel_or_modify_lock_et="15:50:00",
            nasdaq_moc_acceptance_cutoff_et="15:55:00",
            minutes_from_cycle_to_cancel_lock=18,
            minutes_from_cycle_to_acceptance_cutoff=23,
            interpretation=(
                "A nominal regular-session clock slot exists, but there is no "
                "deadline guard and the cycle first fetches data/reconciles state."
            ),
        ),
        completed_bar_semantics=dict(
            at_1532_et=(
                "A Yahoo bar timestamped 15:30 is less than 60 minutes old and "
                "is explicitly dropped as incomplete; the latest usable hourly "
                "bar is normally the 14:30-15:30 interval."
            ),
            selected_vol20_implication=(
                "Study #37's selected vol20 state uses QQQ observations through "
                "t-1 and does not require the current session's close, but that "
                "policy is not implemented in the live signal adapter."
            ),
        ),
        early_close_exposure=dict(
            official_close_et="13:00:00",
            last_nominal_pre_close_cycle_et="12:32:00",
            scheduler_post_close_cycles_et=["13:32:00", "14:32:00", "15:32:00"],
            current_guard=(
                "Weekday plus hard-coded 09:30-16:00 ET; it does not consult "
                "an exchange holiday/early-close calendar."
            ),
            consequence=(
                "On a weekday 13:00 early close, the current guard can admit "
                "three scheduled cycles after the exchange close. A fresh 12:30 "
                "bar can pass staleness checks at 13:32, so freshness alone is "
                "not an early-close safety control."
            ),
        ),
        current_capabilities=checks,
        readiness_matrix=[
            dict(
                requirement="pre-cutoff nominal scheduling slot",
                current_status="PARTIAL",
                evidence="15:32 ET cycle leaves 18/23 nominal minutes",
            ),
            dict(
                requirement="frozen t-1 vol20 decision",
                current_status="ABSENT",
                evidence="live signal adapter implements hourly TQQQ strategy only",
            ),
            dict(
                requirement="MOC order type and primary-exchange workflow",
                current_status="ABSENT",
                evidence="existing close path submits a SMART MarketOrder",
            ),
            dict(
                requirement="cutoff/deadline fail-closed guard",
                current_status="ABSENT",
                evidence="no 15:50/15:55 deadline check in live code",
            ),
            dict(
                requirement="holiday and early-close calendar",
                current_status="ABSENT",
                evidence="weekday guard hard-codes 09:30-16:00 ET",
            ),
            dict(
                requirement="NOCP/NOII and auction-status evidence schema",
                current_status="ABSENT",
                evidence="no NOCP or NOII capture in live code",
            ),
            dict(
                requirement="auction behavior in paper",
                current_status="UNTESTABLE",
                evidence="IBKR paper does not support Auction orders",
            ),
        ],
        decision=(
            "NOT READY: a nominal 15:32 slot exists, but the selected policy, "
            "MOC order path, deadline guard, exchange calendar, and auction "
            "telemetry are absent. The hard-coded regular-session guard also "
            "admits post-close cycles on early-close weekdays. This is a "
            "research finding, not authorization to change protected code."
        ),
    )


def exchange_calendar_closed_cycle_audit(
    runtime_audit: Dict[str, object],
) -> Dict[str, object]:
    """Quantify jobs admitted on official 2026 closed/early-close weekdays."""
    fully_closed_weekdays_2026 = [
        "2026-01-01",
        "2026-01-19",
        "2026-02-16",
        "2026-04-03",
        "2026-05-25",
        "2026-06-19",
        "2026-07-03",
        "2026-09-07",
        "2026-11-26",
        "2026-12-25",
    ]
    early_close_weekdays_2026 = [
        "2026-11-27",
        "2026-12-24",
    ]
    scheduled_cycles_per_weekday = 7
    post_early_close_cycles_per_day = 3
    closed_day_cycles = (
        len(fully_closed_weekdays_2026) * scheduled_cycles_per_weekday
    )
    post_early_close_cycles = (
        len(early_close_weekdays_2026) * post_early_close_cycles_per_day
    )
    max_staleness_hours = int(
        getattr(config, "LIVE_MAX_BAR_STALENESS_HOURS", 120)
    )
    checks = runtime_audit["current_capabilities"]
    return dict(
        scope=(
            "Calendar/scheduler exposure count only. It does not assert that "
            "an order was submitted or filled on any historical holiday."
        ),
        official_calendar_source=(
            "https://www.nasdaqtrader.com/trader.aspx?id=Calendar"
        ),
        fully_closed_weekdays_2026=fully_closed_weekdays_2026,
        early_close_weekdays_2026=early_close_weekdays_2026,
        schedule_math=dict(
            configured_cycles_per_weekday=scheduled_cycles_per_weekday,
            admitted_cycles_on_fully_closed_weekdays=closed_day_cycles,
            post_close_cycles_per_early_close_weekday=(
                post_early_close_cycles_per_day
            ),
            admitted_post_close_early_close_cycles=post_early_close_cycles,
            total_off_exchange_calendar_cycles=(
                closed_day_cycles + post_early_close_cycles
            ),
        ),
        stale_data_interaction=dict(
            configured_max_bar_staleness_hours=max_staleness_hours,
            longest_typical_holiday_gap_is_below_limit=True,
            implication=(
                "Prior-session hourly data can remain admissible throughout a "
                "weekday market holiday; freshness does not suppress the jobs."
            ),
        ),
        repeated_state_transition_risk=dict(
            position_bar_count_increment_is_cycle_based=bool(
                checks["position_bar_count_increment_is_cycle_based"]
            ),
            explicit_last_processed_bar_dedup_guard_present=bool(
                checks[
                    "explicit_last_processed_bar_dedup_guard_present"
                ]
            ),
            full_holiday_max_same_bar_position_count_increments=7,
            early_close_post_close_position_count_increments=3,
            early_close_generic_minimum_duplicate_final_bar_increments=2,
            consequence=(
                "With an open position, every admitted cycle increments the "
                "holding-bar counter before software exits. A full holiday can "
                "therefore add seven counts from one prior-session bar; an early "
                "close can add three after 13:00, with at least two duplicates "
                "under generic hourly semantics. The pinned replay separately "
                "finds that all three reuse its 11:30 final bar. This can advance "
                "or trigger a max-bar close while the exchange is shut."
            ),
        ),
        flat_state_risk=(
            "When flat, the same prior-session signal can be evaluated repeatedly "
            "on a closed market because no last-processed-bar dedup gate exists."
        ),
        decision=(
            "FAIL-CLOSED CALENDAR GAP: the 2026 weekday-only schedule admits "
            "70 cycles on ten fully closed Nasdaq days plus six post-close cycles "
            "on two 13:00 closes. The count is deterministic schedule exposure, "
            "not evidence of 76 orders. An exchange-session calendar and "
            "idempotent bar-time gate are prerequisites for safe runtime behavior."
        ),
    )


def pinned_calendar_misfire_materiality(
    sig: pd.DataFrame,
    clean_trades: pd.DataFrame,
) -> Dict[str, object]:
    """Replay official closed/short dates against causal signals and clean state."""
    fully_closed_dates = [
        "2024-09-02",
        "2024-11-28",
        "2024-12-25",
        "2025-01-01",
        "2025-01-09",
        "2025-01-20",
        "2025-02-17",
        "2025-04-18",
        "2025-05-26",
        "2025-06-19",
        "2025-07-04",
        "2025-09-01",
        "2025-11-27",
        "2025-12-25",
        "2026-01-01",
        "2026-01-19",
        "2026-02-16",
        "2026-04-03",
        "2026-05-25",
        "2026-06-19",
        "2026-07-03",
    ]
    early_close_dates = [
        "2024-11-29",
        "2024-12-24",
        "2025-07-03",
        "2025-11-28",
        "2025-12-24",
    ]
    rows = []

    def clean_position_open(at: pd.Timestamp) -> bool:
        return bool(
            (
                (clean_trades["entry_timestamp"] < at)
                & (clean_trades["exit_timestamp"] >= at)
            ).any()
        )

    for date_text in fully_closed_dates:
        date_value = pd.Timestamp(date_text).date()
        prior = sig.index[sig.index.date < date_value]
        if prior.empty:
            raise RuntimeError(
                "no prior signal bar for closed date %s" % date_text
            )
        reused_bar = prior[-1]
        signal = int(sig.loc[reused_bar, "entry_signal"])
        baseline_open = clean_position_open(
            pd.Timestamp(date_text + " 12:00", tz=TZ)
        )
        rows.append(
            dict(
                exchange_date=date_text,
                session_status="fully_closed",
                admitted_off_calendar_cycles=7,
                reused_bar_timestamp=str(reused_bar),
                reused_entry_signal=signal,
                clean_baseline_position_open=baseline_open,
                clean_baseline_flat_with_nonzero_signal=bool(
                    not baseline_open and signal != 0
                ),
                baseline_open_cycle_exposure=7 if baseline_open else 0,
                frozen_flat_nonzero_cycle_upper_bound=(
                    7 if not baseline_open and signal != 0 else 0
                ),
            )
        )

    for date_text in early_close_dates:
        date_value = pd.Timestamp(date_text).date()
        session_index = sig.index[sig.index.date == date_value]
        if session_index.empty:
            raise RuntimeError(
                "no signal bars for early close %s" % date_text
            )
        reused_bar = session_index[-1]
        signal = int(sig.loc[reused_bar, "entry_signal"])
        baseline_open = clean_position_open(
            pd.Timestamp(date_text + " 13:32", tz=TZ)
        )
        rows.append(
            dict(
                exchange_date=date_text,
                session_status="early_close_1300",
                admitted_off_calendar_cycles=3,
                session_hourly_bars=int(len(session_index)),
                reused_bar_timestamp=str(reused_bar),
                reused_entry_signal=signal,
                final_bar_processable_at_1232=bool(
                    reused_bar.hour == 11 and reused_bar.minute == 30
                ),
                post_close_cycles_reusing_1232_bar=(
                    3
                    if reused_bar.hour == 11 and reused_bar.minute == 30
                    else 2
                ),
                clean_baseline_position_open=baseline_open,
                clean_baseline_flat_with_nonzero_signal=bool(
                    not baseline_open and signal != 0
                ),
                baseline_open_cycle_exposure=3 if baseline_open else 0,
                frozen_flat_nonzero_cycle_upper_bound=(
                    3 if not baseline_open and signal != 0 else 0
                ),
            )
        )

    closed_rows = [
        row for row in rows if row["session_status"] == "fully_closed"
    ]
    early_rows = [
        row
        for row in rows
        if row["session_status"] == "early_close_1300"
    ]
    total_cycles = sum(row["admitted_off_calendar_cycles"] for row in rows)
    baseline_open_cycles = sum(
        row["baseline_open_cycle_exposure"] for row in rows
    )
    frozen_flat_signal_cycles = sum(
        row["frozen_flat_nonzero_cycle_upper_bound"] for row in rows
    )
    return dict(
        scope=(
            "Structural replay on the clean counterfactual path, not observed "
            "Pi state, orders, acknowledgements, or fills. Misfire state changes "
            "would alter later cycles, so cycle exposures are not additive orders."
        ),
        calendar_sources=[
            "https://www.nasdaqtrader.com/content/technicalsupport/2024tradingcalendar.pdf",
            "https://www.nasdaqtrader.com/content/technicalsupport/2025tradingcalendar.pdf",
            "https://www.nasdaqtrader.com/trader.aspx?id=Calendar",
            "https://nasdaqtrader.com/TraderNews.aspx?id=ECA2024-632",
        ],
        pinned_window=dict(
            start=str(sig.index[0]),
            end=str(sig.index[-1]),
            fully_closed_weekdays=len(closed_rows),
            early_close_weekdays=len(early_rows),
            admitted_off_calendar_cycles=total_cycles,
        ),
        materiality=dict(
            full_holidays_with_nonzero_reused_signal=sum(
                row["reused_entry_signal"] != 0 for row in closed_rows
            ),
            early_closes_with_nonzero_reused_signal=sum(
                row["reused_entry_signal"] != 0 for row in early_rows
            ),
            full_holidays_clean_baseline_position_open=sum(
                row["clean_baseline_position_open"] for row in closed_rows
            ),
            early_closes_clean_baseline_position_open=sum(
                row["clean_baseline_position_open"] for row in early_rows
            ),
            clean_baseline_open_cycle_exposure=baseline_open_cycles,
            dates_clean_flat_with_nonzero_signal=sum(
                row["clean_baseline_flat_with_nonzero_signal"]
                for row in rows
            ),
            frozen_clean_flat_nonzero_cycle_upper_bound=(
                frozen_flat_signal_cycles
            ),
            early_close_sessions_with_three_hourly_bars=sum(
                row["session_hourly_bars"] == 3 for row in early_rows
            ),
            early_close_post_close_cycles_reusing_1232_bar=sum(
                row["post_close_cycles_reusing_1232_bar"]
                for row in early_rows
            ),
        ),
        event_rows=rows,
        endpoint_limits=[
            "The clean trade path is a counterfactual reference, not historical live state.",
            "A first misfire can change position state, so later cycles are exposures, not independent attempts.",
            "A nonzero signal is necessary but not sufficient for an order: reconciliation, sizing, and broker checks still apply.",
            "No conclusion is drawn about broker acceptance, queueing, rejection, or fill outside regular hours.",
        ],
        decision=(
            "The calendar gap is decision-material in the pinned sample: 162 "
            "off-calendar jobs, 65 clean-baseline-open cycle exposures, and nine "
            "dates that were clean-flat with a nonzero reused signal. All five "
            "early-close sessions have three Yahoo hourly bars ending 11:30, so "
            "all 15 post-close jobs reuse the bar already processable at 12:32. "
            "These are structural opportunities for state mutation, not observed orders."
        ),
    )


def sanitized_holiday_runtime_evidence() -> Dict[str, object]:
    """Audit committed sanitized live records for observed holiday cycles."""
    archive_dir = os.path.join(
        REPO,
        "data",
        "live_runs",
        "archive_2026-06-18_pre_clean_run",
    )
    names = [
        "metadata.json",
        "signal_history.jsonl",
        "monitor_events.jsonl",
        "trades.jsonl",
    ]
    file_hashes = {}
    for name in names:
        with open(os.path.join(archive_dir, name), "rb") as fh:
            raw = fh.read()
        file_hashes[name] = hashlib.sha256(raw).hexdigest()

    with open(os.path.join(archive_dir, "metadata.json")) as fh:
        metadata = json.load(fh)

    def load_jsonl(name: str) -> List[Dict[str, object]]:
        rows = []
        with open(os.path.join(archive_dir, name)) as fh:
            for line in fh:
                if line.strip():
                    rows.append(json.loads(line))
        return rows

    def et_timestamp(value: str) -> pd.Timestamp:
        timestamp = pd.Timestamp(value)
        if timestamp.tzinfo is None:
            timestamp = timestamp.tz_localize("UTC")
        return timestamp.tz_convert(TZ)

    signals = load_jsonl("signal_history.jsonl")
    events = load_jsonl("monitor_events.jsonl")
    trades = load_jsonl("trades.jsonl")

    signal_slots: Dict[str, List[Dict[str, object]]] = {}
    for row in signals:
        slot = str(et_timestamp(str(row["updated_at"])).floor("min"))
        signal_slots.setdefault(slot, []).append(row)
    multiplicity: Dict[str, int] = {}
    for rows in signal_slots.values():
        key = str(len(rows))
        multiplicity[key] = multiplicity.get(key, 0) + 1
    duplicate_slots = [
        (slot, rows)
        for slot, rows in signal_slots.items()
        if len(rows) > 1
    ]
    payload_fields = [
        "signal",
        "bar_time",
        "bar_close",
        "rsi",
        "vwap_zscore",
        "momentum_signal",
        "volume_signal",
    ]
    duplicate_same_payload = 0
    for _, rows in duplicate_slots:
        payloads = {
            tuple(row.get(field) for field in payload_fields)
            for row in rows
        }
        duplicate_same_payload += int(len(payloads) == 1)

    monitor_slots: Dict[str, List[Dict[str, object]]] = {}
    for row in events:
        slot = str(et_timestamp(str(row["event_time"])).floor("min"))
        monitor_slots.setdefault(slot, []).append(row)
    extra_identical_monitor_events = 0
    for rows in monitor_slots.values():
        counts: Dict[Tuple[object, ...], int] = {}
        for row in rows:
            key = (row["level"], row["category"], row["message"])
            counts[key] = counts.get(key, 0) + 1
        extra_identical_monitor_events += sum(
            count - 1 for count in counts.values() if count > 1
        )

    holiday_dates = ["2026-04-03", "2026-05-25"]
    holiday_rows = []
    for date_text in holiday_dates:
        date_value = pd.Timestamp(date_text).date()
        holiday_signals = [
            row
            for row in signals
            if et_timestamp(str(row["updated_at"])).date() == date_value
        ]
        holiday_events = [
            row
            for row in events
            if et_timestamp(str(row["event_time"])).date() == date_value
        ]
        slots = sorted(
            {
                str(et_timestamp(str(row["updated_at"])).floor("min"))
                for row in holiday_signals
            }
        )
        trade_endpoints = 0
        for trade in trades:
            for field in ("entry_time", "exit_time"):
                value = trade.get(field)
                if (
                    value
                    and et_timestamp(str(value)).date() == date_value
                ):
                    trade_endpoints += 1
        connection_failures = [
            row
            for row in holiday_events
            if "Connect call failed" in str(row["message"])
            and "7497" in str(row["message"])
        ]
        holiday_rows.append(
            dict(
                exchange_date=date_text,
                observed_signal_rows=len(holiday_signals),
                unique_scheduled_minute_slots=len(slots),
                rows_per_observed_slot=sorted(
                    {
                        sum(
                            str(
                                et_timestamp(
                                    str(other["updated_at"])
                                ).floor("min")
                            )
                            == slot
                            for other in holiday_signals
                        )
                        for slot in slots
                    }
                ),
                observed_slots_et=slots,
                raw_reused_bar_times=sorted(
                    {str(row["bar_time"]) for row in holiday_signals}
                ),
                observed_signals=sorted(
                    {int(row["signal"]) for row in holiday_signals}
                ),
                monitor_event_rows=len(holiday_events),
                paper_7497_connection_failures=len(
                    connection_failures
                ),
                trade_entry_or_exit_endpoints=trade_endpoints,
            )
        )

    return dict(
        scope=(
            "Observed committed sanitized records from one historical Pi archive. "
            "They prove cycle/log activity, not the complete process history, "
            "broker orders, fills, or current-development runtime behavior."
        ),
        archive=dict(
            archive_id=metadata["archive_id"],
            export_time_utc=metadata["export_time_utc"],
            git_branch=metadata["git_branch"],
            git_commit=metadata["git_commit"],
            source_database_sha256=metadata["source_database_sha256"],
            row_counts=metadata["row_counts"],
            timestamp_ranges=metadata["timestamp_ranges"],
            audited_file_sha256=file_hashes,
        ),
        coverage=dict(
            official_fully_closed_dates_inside_signal_history=[
                "2026-04-03",
                "2026-05-25",
            ],
            early_close_dates_inside_signal_history=[],
            limitation=(
                "Only two official closures and no early close fall inside "
                "the committed signal-history coverage."
            ),
        ),
        holiday_rows=holiday_rows,
        duplicate_writer_diagnostic=dict(
            signal_rows=len(signals),
            unique_signal_minute_slots=len(signal_slots),
            slot_multiplicity=multiplicity,
            double_written_slots=len(duplicate_slots),
            first_double_written_slot_et=duplicate_slots[0][0],
            last_double_written_slot_et=duplicate_slots[-1][0],
            double_written_slots_with_identical_payload=(
                duplicate_same_payload
            ),
            double_written_slots_with_divergent_payload=(
                len(duplicate_slots) - duplicate_same_payload
            ),
            extra_identical_monitor_events=extra_identical_monitor_events,
            interpretation=(
                "The archive contains two signal-history writes in 210 minute "
                "slots. Archived source has one save call and one history insert "
                "per cycle, so this is consistent with duplicate invocations or "
                "writers, but the export alone does not identify the process cause."
            ),
        ),
        decision=(
            "The calendar defect occurred operationally in the archived run: "
            "Good Friday logged 8 signal rows across 4 slots and Memorial Day "
            "14 across all 7 slots, always reusing one prior-session bar. Every "
            "holiday cycle then failed to connect to paper port 7497 and no trade "
            "endpoint was recorded. The gateway outage prevented downstream "
            "behavior by circumstance, not by an exchange-calendar guard. Every "
            "observed holiday slot was double-written, exposing a separate "
            "historical duplicate-invocation/writer issue."
        ),
    )


def historical_duplicate_writer_forensics() -> Dict[str, object]:
    """Quantify decision and order-path ambiguity in paired archive writes."""
    archive_dir = os.path.join(
        REPO,
        "data",
        "live_runs",
        "archive_2026-06-18_pre_clean_run",
    )

    def load_jsonl(name: str) -> List[Dict[str, object]]:
        rows = []
        with open(os.path.join(archive_dir, name)) as fh:
            for line in fh:
                if line.strip():
                    rows.append(json.loads(line))
        return rows

    def et_timestamp(value: str) -> pd.Timestamp:
        timestamp = pd.Timestamp(value)
        if timestamp.tzinfo is None:
            timestamp = timestamp.tz_localize("UTC")
        return timestamp.tz_convert(TZ)

    def minute_slot(value: str) -> str:
        return str(et_timestamp(value).floor("min"))

    signals = load_jsonl("signal_history.jsonl")
    events = load_jsonl("monitor_events.jsonl")
    trades = load_jsonl("trades.jsonl")

    signal_slots: Dict[str, List[Dict[str, object]]] = {}
    for row in signals:
        signal_slots.setdefault(
            minute_slot(str(row["updated_at"])), []
        ).append(row)
    pairs = [
        (
            slot,
            sorted(rows, key=lambda row: str(row["updated_at"])),
        )
        for slot, rows in sorted(signal_slots.items())
        if len(rows) == 2
    ]

    bar_delta_minutes: Dict[str, int] = {}
    signal_pair_matrix: Dict[str, int] = {}
    write_separations = []
    signal_disagreements = 0
    long_eligibility_disagreements = 0
    flat_versus_directional = 0
    opposite_direction = 0
    identical_bar_slots = []
    for slot, rows in pairs:
        first, second = rows
        first_bar = pd.Timestamp(str(first["bar_time"]))
        second_bar = pd.Timestamp(str(second["bar_time"]))
        delta = str(
            int(abs((second_bar - first_bar).total_seconds()) // 60)
        )
        bar_delta_minutes[delta] = bar_delta_minutes.get(delta, 0) + 1
        transition = "%d->%d" % (
            int(first["signal"]),
            int(second["signal"]),
        )
        signal_pair_matrix[transition] = (
            signal_pair_matrix.get(transition, 0) + 1
        )
        write_separations.append(
            abs(
                (
                    pd.Timestamp(str(second["updated_at"]))
                    - pd.Timestamp(str(first["updated_at"]))
                ).total_seconds()
            )
        )
        first_signal = int(first["signal"])
        second_signal = int(second["signal"])
        signal_disagreements += int(first_signal != second_signal)
        long_eligibility_disagreements += int(
            (first_signal == 1) != (second_signal == 1)
        )
        flat_versus_directional += int(
            first_signal != second_signal
            and 0 in (first_signal, second_signal)
        )
        opposite_direction += int(
            first_signal * second_signal == -1
        )
        if first_bar == second_bar:
            identical_bar_slots.append(slot)

    entry_slots: Dict[str, List[Dict[str, object]]] = {}
    for row in events:
        if row.get("category") == "entry":
            entry_slots.setdefault(
                minute_slot(str(row["event_time"])), []
            ).append(row)
    trade_entry_slots: Dict[str, List[Dict[str, object]]] = {}
    for row in trades:
        if row.get("entry_time"):
            trade_entry_slots.setdefault(
                minute_slot(str(row["entry_time"])), []
            ).append(row)

    paired_disagreement_slots = {
        slot
        for slot, rows in pairs
        if int(rows[0]["signal"]) != int(rows[1]["signal"])
    }
    paired_long_eligibility_disagreement_slots = {
        slot
        for slot, rows in pairs
        if (
            (int(rows[0]["signal"]) == 1)
            != (int(rows[1]["signal"]) == 1)
        )
    }

    double_entry_rows = []
    first_path_total_shares = 0
    first_path_total_logged_notional = 0.0
    later_state_matches = 0
    for slot, rows in sorted(entry_slots.items()):
        if len(rows) != 2:
            continue
        ordered = sorted(rows, key=lambda row: str(row["event_time"]))
        parsed = []
        for row in ordered:
            match = re.search(
                r"(?:LONG |SHORT )?(\d+) TQQQ @ ([0-9.]+)",
                str(row["message"]),
            )
            if match is None:
                raise AssertionError(
                    "Unparseable archived entry event: %r"
                    % row["message"]
                )
            parsed.append(
                dict(
                    qty=int(match.group(1)),
                    logged_price=float(match.group(2)),
                    event_time=str(row["event_time"]),
                )
            )
        recorded = trade_entry_slots.get(slot, [])
        matches_later = (
            len(recorded) == 1
            and int(recorded[0]["qty"]) == parsed[1]["qty"]
            and abs(
                (
                    et_timestamp(str(recorded[0]["entry_time"]))
                    - et_timestamp(parsed[1]["event_time"])
                ).total_seconds()
            )
            < 1.0
        )
        later_state_matches += int(matches_later)
        first_path_total_shares += parsed[0]["qty"]
        first_path_total_logged_notional += (
            parsed[0]["qty"] * parsed[0]["logged_price"]
        )
        double_entry_rows.append(
            dict(
                slot_et=slot,
                seconds_between_success_events=round(
                    (
                        et_timestamp(parsed[1]["event_time"])
                        - et_timestamp(parsed[0]["event_time"])
                    ).total_seconds(),
                    6,
                ),
                first=parsed[0],
                second=parsed[1],
                one_trade_row_in_slot=len(recorded) == 1,
                trade_row_matches_later_state=matches_later,
            )
        )

    return dict(
        scope=(
            "Forensic accounting of the committed sanitized archive. "
            "Application success-path events prove bracket-submission code "
            "ran, but do not prove broker acceptance, fills, or final exposure."
        ),
        paired_signal_writes=dict(
            paired_minute_slots=len(pairs),
            paired_exchange_dates=len(
                {pd.Timestamp(slot).date().isoformat() for slot, _ in pairs}
            ),
            max_write_separation_seconds=round(
                max(write_separations), 6
            ),
            median_write_separation_seconds=round(
                float(np.median(write_separations)), 6
            ),
            identical_bar_slots=len(identical_bar_slots),
            divergent_bar_slots=len(pairs) - len(identical_bar_slots),
            absolute_bar_delta_minutes=dict(
                sorted(bar_delta_minutes.items(), key=lambda item: int(item[0]))
            ),
            signal_pair_matrix=dict(sorted(signal_pair_matrix.items())),
            same_final_signal=len(pairs) - signal_disagreements,
            different_final_signal=signal_disagreements,
            flat_versus_directional_signal=flat_versus_directional,
            opposite_direction_signal=opposite_direction,
            long_eligibility_disagreements_with_shorts_disabled=(
                long_eligibility_disagreements
            ),
            disagreement_slots_with_entry_success_event=sum(
                slot in entry_slots for slot in paired_disagreement_slots
            ),
            long_eligibility_disagreement_slots_with_entry_success_event=sum(
                slot in entry_slots
                for slot in paired_long_eligibility_disagreement_slots
            ),
        ),
        entry_path=dict(
            entry_event_rows=sum(len(rows) for rows in entry_slots.values()),
            unique_entry_minute_slots=len(entry_slots),
            single_entry_event_slots=sum(
                len(rows) == 1 for rows in entry_slots.values()
            ),
            double_entry_event_slots=len(double_entry_rows),
            extra_success_path_entry_events=len(double_entry_rows),
            extra_success_path_rate_per_unique_entry_slot=round(
                len(double_entry_rows) / len(entry_slots), 6
            ),
            double_entry_rows=double_entry_rows,
            double_slots_with_one_trade_row=sum(
                row["one_trade_row_in_slot"] for row in double_entry_rows
            ),
            trade_rows_matching_later_state=later_state_matches,
            first_success_path_total_shares_across_seven_episodes=(
                first_path_total_shares
            ),
            first_success_path_total_logged_notional_across_episodes=round(
                first_path_total_logged_notional, 2
            ),
            additional_bracket_submission_paths=(
                len(double_entry_rows)
            ),
            additional_ib_placeOrder_calls=(
                3 * len(double_entry_rows)
            ),
            source_semantics=(
                "At archived commit b37a8a8, place_bracket_order calls "
                "ib.placeOrder once for each of parent, take-profit, and stop "
                "before returning. The trader then replaces the single local "
                "position row and emits the entry event. It does not wait for "
                "parent fill or broker acceptance before that success event."
            ),
        ),
        limitations=[
            (
                "The archive has no broker order-status or execution ledger, "
                "so 14 success events in seven slots do not establish 14 "
                "accepted or filled parent orders."
            ),
            (
                "Summed shares/notional span seven separate episodes and are "
                "not simultaneous portfolio exposure."
            ),
            (
                "No process IDs, launch environment, or service-manager state "
                "survives, so the writer count and launcher identity remain "
                "unidentified."
            ),
        ],
        decision=(
            "The duplicate history was decision-relevant, not cosmetic: 69/210 "
            "paired slots disagree on the three-way signal and 58/210 disagree "
            "on long-entry eligibility under the archived shorts-disabled "
            "configuration. Seven of 65 unique entry minutes contain two "
            "success-path events, proving seven extra bracket-submission code "
            "paths (21 additional ib.placeOrder calls) while all seven local "
            "trade rows retain only the later state. Broker acceptance and "
            "fills remain unproven without an order/execution ledger."
        ),
    )


def live_bar_completion_timezone_audit(
    duplicate_forensics: Dict[str, object],
) -> Dict[str, object]:
    """Audit the UTC-naive versus host-local bar-completion decision."""
    source_paths = [
        "src/data/fetcher.py",
        "live/signals.py",
        "ops/systemd/monad-trader.service",
        "OPERATIONS.md",
    ]
    source_hashes = {}
    source_text = {}
    for relative in source_paths:
        path = os.path.join(REPO, relative)
        with open(path, "rb") as fh:
            raw = fh.read()
        source_hashes[relative] = hashlib.sha256(raw).hexdigest()
        source_text[relative] = raw.decode("utf-8")

    required_source_tokens = {
        "src/data/fetcher.py": [
            "df.index = df.index.tz_convert(None)",
        ],
        "live/signals.py": [
            "if df.index.tz is None:",
            "now_utc = pd.Timestamp.now()",
            "dropped_incomplete = last_bar_age < pd.Timedelta(minutes=60)",
            "now_for_check = pd.Timestamp.now(tz=\"UTC\") if result.index.tz is not None else pd.Timestamp.now()",
        ],
        "ops/systemd/monad-trader.service": [
            "Environment=TZ=America/New_York",
        ],
        "OPERATIONS.md": [
            "Pi clock is **Europe/London**",
        ],
    }
    token_audit = {}
    for path, tokens in required_source_tokens.items():
        token_audit[path] = {
            token: token in source_text[path] for token in tokens
        }

    actual_utc = pd.Timestamp("2026-03-31 14:32:00")
    previous_completed = pd.Timestamp("2026-03-31 13:30:00")
    current_incomplete = pd.Timestamp("2026-03-31 14:30:00")
    one_bar_older = pd.Timestamp("2026-03-31 12:30:00")
    environments = [
        ("UTC", 0),
        ("Europe/London BST", 60),
        ("America/New_York EDT", -240),
    ]
    controlled_cases = []
    for environment, offset_minutes in environments:
        local_naive_now = actual_utc + pd.Timedelta(minutes=offset_minutes)
        for api_tail in ("includes_current", "omits_current"):
            if api_tail == "includes_current":
                raw_tail = [previous_completed, current_incomplete]
            else:
                raw_tail = [one_bar_older, previous_completed]
            apparent_age = local_naive_now - raw_tail[-1]
            drops_tail = apparent_age < pd.Timedelta(minutes=60)
            selected = raw_tail[-2] if drops_tail else raw_tail[-1]
            controlled_cases.append(
                dict(
                    host_environment=environment,
                    host_utc_offset_minutes=offset_minutes,
                    api_tail=api_tail,
                    local_naive_now=str(local_naive_now),
                    raw_last_bar_utc_naive=str(raw_tail[-1]),
                    apparent_age_minutes=round(
                        apparent_age.total_seconds() / 60.0, 3
                    ),
                    drops_raw_tail=drops_tail,
                    selected_bar_utc_naive=str(selected),
                    correct_completed_bar=selected == previous_completed,
                    failure_mode=(
                        None
                        if selected == previous_completed
                        else (
                            "accepts_incomplete_current_bar"
                            if selected == current_incomplete
                            else "drops_completed_bar_and_lags_one_extra_hour"
                        )
                    ),
                )
            )

    pair = duplicate_forensics["paired_signal_writes"]
    absolute_deltas = pair["absolute_bar_delta_minutes"]
    expected_divergent_delta_counts = {
        "60": 168,
        "1080": 23,
        "3960": 4,
        "5400": 2,
    }
    identical_breakdown = {
        "pre_bst_regular_slots_2026_03_26": 2,
        "good_friday_closed_slots_2026_04_03": 4,
        "memorial_day_closed_slots_2026_05_25": 7,
    }

    return dict(
        scope=(
            "Read-only source audit plus a fixed-clock decision table and "
            "a historical DST/holiday natural experiment. No protected "
            "runtime, signal, config, or service file was changed."
        ),
        current_source_sha256=source_hashes,
        source_contract_tokens=token_audit,
        external_primary_sources={
            "pandas_tz_convert_none": (
                "https://pandas.pydata.org/pandas-docs/stable/"
                "reference/api/pandas.DatetimeIndex.tz_convert.html"
            ),
            "pandas_timestamp_now": (
                "https://pandas.pydata.org/pandas-docs/stable/"
                "reference/api/pandas.Timestamp.now.html"
            ),
            "uk_2026_clock_change": (
                "https://www.gov.uk/when-do-the-clocks-change"
            ),
        },
        fixed_clock_case=dict(
            actual_utc=str(actual_utc),
            intended_previous_completed_bar=str(previous_completed),
            current_incomplete_bar=str(current_incomplete),
            cases=controlled_cases,
            interpretation=(
                "UTC-naive bar labels are compared with host-local naive now. "
                "At the same instant, UTC selects the completed bar regardless "
                "of whether the vendor includes its current tail; London BST "
                "can accept the two-minute-old current bar, while New York EDT "
                "can discard a completed bar when the current tail is absent."
            ),
        ),
        staleness_guard_true_age_boundary_hours={
            "UTC": 120,
            "Europe/London_BST": 119,
            "America/New_York_EDT": 124,
            "America/New_York_EST": 125,
        },
        historical_natural_experiment=dict(
            uk_bst_started="2026-03-29",
            paired_slots=pair["paired_minute_slots"],
            identical_bar_slots=pair["identical_bar_slots"],
            identical_bar_slot_breakdown=identical_breakdown,
            divergent_bar_slots=pair["divergent_bar_slots"],
            observed_divergent_absolute_bar_delta_minutes={
                key: absolute_deltas.get(key, 0)
                for key in expected_divergent_delta_counts
            },
            expected_divergent_absolute_bar_delta_minutes=(
                expected_divergent_delta_counts
            ),
            exact_structural_match=(
                pair["identical_bar_slots"] == sum(
                    identical_breakdown.values()
                )
                and pair["divergent_bar_slots"]
                == sum(expected_divergent_delta_counts.values())
                and all(
                    absolute_deltas.get(key, 0) == value
                    for key, value in expected_divergent_delta_counts.items()
                )
            ),
            interpretation=(
                "The two pre-BST regular slots and eleven closed-holiday slots "
                "agree. Every other paired slot differs by exactly the expected "
                "distance between the in-progress session bar and the previous "
                "completed bar: one hour intraday, 18 hours overnight, 66 over "
                "a weekend, or 90 over Memorial Day. This is a strong natural-"
                "experiment signature of host-local/UTC-naive tail selection."
            ),
        ),
        limitations=[
            (
                "The archive does not contain raw yfinance responses, process "
                "TZ values, or process IDs; the historical mechanism is an "
                "inference from an exact structured pattern, not a recovered "
                "per-process trace."
            ),
            (
                "The systemd TZ setting changes the failure mode but does not "
                "make the comparison timezone-correct. Manual launches on the "
                "Europe/London host remain environment-dependent."
            ),
        ],
        decision=(
            "Current live bar completion is environment-dependent and therefore "
            "not runtime-ready: fetch_yfinance stores UTC-naive labels, while "
            "live/signals compares them with host-local naive time. The archived "
            "DST natural experiment matches this mechanism exactly and links it "
            "to 69 signal disagreements and 58 long-eligibility disagreements. "
            "The systemd America/New_York override prevents the London-BST form "
            "only when the vendor includes the current tail; if the tail is "
            "absent it can discard the last completed bar, and it understates "
            "true staleness by four or five hours."
        ),
    )


def archived_incomplete_bar_materiality() -> Dict[str, object]:
    """Measure how often archived cycles used an in-progress hourly bar."""
    archive_dir = os.path.join(
        REPO,
        "data",
        "live_runs",
        "archive_2026-06-18_pre_clean_run",
    )

    def load_jsonl(name: str) -> List[Dict[str, object]]:
        rows = []
        with open(os.path.join(archive_dir, name)) as fh:
            for line in fh:
                if line.strip():
                    rows.append(json.loads(line))
        return rows

    def utc_timestamp(value: str) -> pd.Timestamp:
        timestamp = pd.Timestamp(value)
        if timestamp.tzinfo is None:
            timestamp = timestamp.tz_localize("UTC")
        return timestamp.tz_convert("UTC")

    def et_timestamp(value: str) -> pd.Timestamp:
        return utc_timestamp(value).tz_convert(TZ)

    def minute_slot(value: str) -> str:
        return str(et_timestamp(value).floor("min"))

    def true_bar_age_minutes(row: Dict[str, object]) -> float:
        observation = utc_timestamp(str(row["updated_at"]))
        bar_start = utc_timestamp(str(row["bar_time"]))
        return float((observation - bar_start).total_seconds() / 60.0)

    signals = load_jsonl("signal_history.jsonl")
    events = load_jsonl("monitor_events.jsonl")
    trades = load_jsonl("trades.jsonl")
    ages = [true_bar_age_minutes(row) for row in signals]
    incomplete_rows = [
        row
        for row in signals
        if true_bar_age_minutes(row) < 60.0
    ]

    signal_slots: Dict[str, List[Dict[str, object]]] = {}
    for row in signals:
        signal_slots.setdefault(
            minute_slot(str(row["updated_at"])), []
        ).append(row)
    entry_slots: Dict[str, List[Dict[str, object]]] = {}
    for row in events:
        if row.get("category") == "entry":
            entry_slots.setdefault(
                minute_slot(str(row["event_time"])), []
            ).append(row)
    trade_slots: Dict[str, List[Dict[str, object]]] = {}
    for row in trades:
        if row.get("entry_time"):
            trade_slots.setdefault(
                minute_slot(str(row["entry_time"])), []
            ).append(row)

    entry_slot_classes: Dict[str, int] = {}
    entry_event_classes: Dict[str, int] = {}
    strict_incomplete_entry_slots = []
    for slot, entry_rows in sorted(entry_slots.items()):
        rows = signal_slots.get(slot, [])
        if not rows:
            classification = "no_signal_history_same_slot"
        elif len(rows) == 1:
            classification = (
                "single_incomplete"
                if true_bar_age_minutes(rows[0]) < 60.0
                else "single_completed"
            )
        elif len(rows) == 2:
            long_rows = [
                row for row in rows if int(row["signal"]) == 1
            ]
            if not long_rows:
                classification = "paired_no_long"
            elif len(long_rows) == 1:
                classification = (
                    "paired_only_long_incomplete"
                    if true_bar_age_minutes(long_rows[0]) < 60.0
                    else "paired_only_long_completed"
                )
            else:
                incomplete_longs = sum(
                    true_bar_age_minutes(row) < 60.0
                    for row in long_rows
                )
                classification = (
                    "paired_both_long_%dincomplete"
                    % incomplete_longs
                )
        else:
            classification = "unexpected_multiplicity"
        entry_slot_classes[classification] = (
            entry_slot_classes.get(classification, 0) + 1
        )
        entry_event_classes[classification] = (
            entry_event_classes.get(classification, 0)
            + len(entry_rows)
        )
        if classification in (
            "single_incomplete",
            "paired_only_long_incomplete",
        ):
            strict_incomplete_entry_slots.append(slot)

    strict_trades = [
        trade_slots[slot][0]
        for slot in strict_incomplete_entry_slots
        if len(trade_slots.get(slot, [])) == 1
    ]
    confirmed_exit_types = {"bracket_exit", "stop_hit"}
    all_confirmed = [
        row for row in trades if row["exit_type"] in confirmed_exit_types
    ]
    strict_confirmed = [
        row
        for row in strict_trades
        if row["exit_type"] in confirmed_exit_types
    ]
    strict_slots = set(strict_incomplete_entry_slots)
    other_confirmed = [
        row
        for row in all_confirmed
        if minute_slot(str(row["entry_time"])) not in strict_slots
    ]

    def compounded_return(rows: List[Dict[str, object]]) -> float:
        wealth = 1.0
        for row in rows:
            wealth *= 1.0 + float(row["return_pct"])
        return wealth - 1.0

    rounded_age_counts: Dict[str, int] = {}
    for age in ages:
        key = str(int(round(age)))
        rounded_age_counts[key] = rounded_age_counts.get(key, 0) + 1
    incomplete_signal_counts: Dict[str, int] = {}
    incomplete_hour_counts: Dict[str, int] = {}
    for row in incomplete_rows:
        signal_key = str(int(row["signal"]))
        incomplete_signal_counts[signal_key] = (
            incomplete_signal_counts.get(signal_key, 0) + 1
        )
        hour_key = str(et_timestamp(str(row["updated_at"])).hour)
        incomplete_hour_counts[hour_key] = (
            incomplete_hour_counts.get(hour_key, 0) + 1
        )

    single_write_rows = [
        rows[0] for rows in signal_slots.values() if len(rows) == 1
    ]
    paired_rows = [
        row
        for rows in signal_slots.values()
        if len(rows) == 2
        for row in rows
    ]
    incomplete_dates = sorted(
        {
            et_timestamp(str(row["updated_at"])).date().isoformat()
            for row in incomplete_rows
        }
    )

    return dict(
        scope=(
            "Observed sanitized runtime records. A bar is classified as "
            "in-progress when the true UTC observation is less than 60 minutes "
            "after its UTC-naive hourly start label. This identifies the "
            "information set, not broker acceptance or fill."
        ),
        signal_rows=dict(
            total=len(signals),
            incomplete=len(incomplete_rows),
            incomplete_pct=round(
                100.0 * len(incomplete_rows) / len(signals), 3
            ),
            completed_or_older=len(signals) - len(incomplete_rows),
            negative_true_ages=sum(age < 0.0 for age in ages),
            incomplete_true_age_minutes=dict(
                minimum=round(
                    min(true_bar_age_minutes(row) for row in incomplete_rows),
                    6,
                ),
                median=round(
                    float(
                        np.median(
                            [
                                true_bar_age_minutes(row)
                                for row in incomplete_rows
                            ]
                        )
                    ),
                    6,
                ),
                maximum=round(
                    max(true_bar_age_minutes(row) for row in incomplete_rows),
                    6,
                ),
            ),
            rounded_true_age_minutes_histogram=dict(
                sorted(
                    rounded_age_counts.items(),
                    key=lambda item: int(item[0]),
                )
            ),
            incomplete_signal_counts=dict(
                sorted(incomplete_signal_counts.items())
            ),
            incomplete_rows_by_cycle_hour_et=dict(
                sorted(
                    incomplete_hour_counts.items(),
                    key=lambda item: int(item[0]),
                )
            ),
            incomplete_exchange_dates=len(incomplete_dates),
            first_incomplete_exchange_date=incomplete_dates[0],
            last_incomplete_exchange_date=incomplete_dates[-1],
            single_write_rows=len(single_write_rows),
            incomplete_single_write_rows=sum(
                true_bar_age_minutes(row) < 60.0
                for row in single_write_rows
            ),
            paired_rows=len(paired_rows),
            incomplete_paired_rows=sum(
                true_bar_age_minutes(row) < 60.0
                for row in paired_rows
            ),
        ),
        conservative_entry_attribution=dict(
            rule=(
                "Count a slot only when it has one incomplete signal row, or "
                "when a pair has exactly one long signal and that unique long "
                "is incomplete. Paired both-long slots remain ambiguous."
            ),
            unique_entry_slots=len(entry_slots),
            entry_event_rows=sum(
                len(rows) for rows in entry_slots.values()
            ),
            entry_slot_classes=dict(sorted(entry_slot_classes.items())),
            entry_event_classes=dict(sorted(entry_event_classes.items())),
            strict_incomplete_entry_slots=len(
                strict_incomplete_entry_slots
            ),
            strict_min_share_of_unique_entry_slots_pct=round(
                100.0
                * len(strict_incomplete_entry_slots)
                / len(entry_slots),
                3,
            ),
            strict_incomplete_entry_events=(
                entry_event_classes.get("single_incomplete", 0)
                + entry_event_classes.get(
                    "paired_only_long_incomplete", 0
                )
            ),
            strict_min_share_of_entry_event_rows_pct=round(
                100.0
                * (
                    entry_event_classes.get("single_incomplete", 0)
                    + entry_event_classes.get(
                        "paired_only_long_incomplete", 0
                    )
                )
                / sum(len(rows) for rows in entry_slots.values()),
                3,
            ),
            strict_slots_with_one_local_trade_row=len(strict_trades),
        ),
        local_trade_accounting=dict(
            strict_incomplete_attributed_trade_rows=len(strict_trades),
            strict_incomplete_exit_types=dict(
                sorted(
                    {
                        exit_type: sum(
                            row["exit_type"] == exit_type
                            for row in strict_trades
                        )
                        for exit_type in {
                            row["exit_type"] for row in strict_trades
                        }
                    }.items()
                )
            ),
            archive_confirmed_definition=(
                "bracket_exit plus stop_hit, matching the archive's "
                "fill-quality split; local categories are not a broker ledger"
            ),
            all_archive_confirmed_trade_rows=len(all_confirmed),
            all_archive_confirmed_compounded_return_pct=round(
                100.0 * compounded_return(all_confirmed), 6
            ),
            strict_incomplete_archive_confirmed_rows=len(strict_confirmed),
            strict_incomplete_archive_confirmed_compounded_return_pct=round(
                100.0 * compounded_return(strict_confirmed), 6
            ),
            remaining_confirmed_or_ambiguous_rows=len(other_confirmed),
            remaining_confirmed_or_ambiguous_compounded_return_pct=round(
                100.0 * compounded_return(other_confirmed), 6
            ),
            interpretation=(
                "This is a descriptive partition, not an additive or causal "
                "PnL attribution. The remainder includes completed, ambiguous "
                "both-long, and unmatched entry information sets."
            ),
        ),
        limitations=[
            (
                "Hourly labels are treated as bar starts. The final regular "
                "15:30 bar is only 30 minutes long, but an observation at 15:32 "
                "is still unambiguously in progress."
            ),
            (
                "The strict entry lower bound excludes paired both-long slots "
                "because the archive has no cycle or PID key joining signal "
                "and entry rows."
            ),
            (
                "A local trade row can include inferred or estimated exits and "
                "does not prove broker acceptance, execution, or quantity."
            ),
        ],
        decision=(
            "The timezone defect materially contaminated the historical paper "
            "run: 297/543 signal rows (54.7%) were recorded about two minutes "
            "into an hourly bar, including 100/123 single-write rows. A strict "
            "join identifies at least 40/65 unique entry minutes (61.5%) and "
            "40/72 entry events (55.6%) whose only actionable information set "
            "was incomplete. All 40 became local trade rows; 33 are in the "
            "archive-confirmed bucket. Historical live PnL therefore is not a "
            "clean completed-bar validation sample, even though its overall "
            "verdict remains flat."
        ),
    )


def trader_singleton_launch_safety_audit() -> Dict[str, object]:
    """Audit launch ownership and construct a current-code duplicate-entry race.

    This is a static, read-only source audit.  The interleaving is a
    constructive reachability proof: it shows a path current controls do not
    exclude, not that the current deployment has followed that path.
    """
    source_paths = [
        "AGENTS.md",
        "README.md",
        "OPERATIONS.md",
        "ops/preflight_trader_start.sh",
        "ops/start_trader.sh",
        "ops/systemd/monad-trader.service",
        "live/trader.py",
        "live/broker.py",
        "live/state.py",
        "config_modules/live.py",
    ]
    source_text: Dict[str, str] = {}
    source_hashes: Dict[str, str] = {}
    for relative in source_paths:
        path = os.path.join(REPO, relative)
        with open(path, "rb") as fh:
            raw = fh.read()
        source_hashes[relative] = hashlib.sha256(raw).hexdigest()
        source_text[relative] = raw.decode("utf-8")

    required_tokens = {
        "AGENTS.md": [
            "**PAPER ONLY.**",
            "live port **7496 must never be used**",
        ],
        "README.md": [
            "python -m live.trader",
            "python -m live.trader --live",
            "the trader\ncan never run from an unreviewed branch",
        ],
        "ops/preflight_trader_start.sh": [
            'pgrep -f "[-]m live.trader"',
            "Runs ALL 10 checks",
        ],
        "ops/start_trader.sh": [
            'if [ "$EXEC_MODE" = 1 ]',
            'exec "$REPO/venv/bin/python" -m live.trader',
            "sudo systemctl start monad-trader.service",
        ],
        "ops/systemd/monad-trader.service": [
            "ExecStartPre=/home/hudson/MONAD-quant/ops/preflight_trader_start.sh",
            "ExecStart=/home/hudson/MONAD-quant/ops/start_trader.sh --exec",
            "Restart=no",
        ],
        "live/trader.py": [
            "position = state.get_position()",
            "broker_pos = broker.get_open_position(config.LIVE_SYMBOL)",
            "state.open_position(",
            "max_instances=1",
            "if args.live:",
            "config.LIVE_PAPER_MODE = False",
            "if args.once:",
            "on_bar()",
        ],
        "live/broker.py": [
            "client_id = config.IBKR_CLIENT_ID",
            "max_retries = 3",
            "ib.connect(host, port, clientId=client_id)",
            "ib.placeOrder(contract, order)",
            "open_orders = ib.openOrders()",
        ],
        "live/state.py": [
            "conn = sqlite3.connect(_DB_PATH)",
            "CREATE TABLE IF NOT EXISTS signal_history",
            'conn.execute("DELETE FROM position")',
            '"INSERT INTO position',
        ],
        "config_modules/live.py": [
            "IBKR_CLIENT_ID     = 1",
        ],
    }
    token_audit = {
        path: {
            token: token in source_text[path]
            for token in tokens
        }
        for path, tokens in required_tokens.items()
    }

    lock_tokens = (
        "flock",
        "fcntl.flock",
        "portalocker",
        "FileLock",
        "PIDFile=",
        "RuntimeDirectory=",
    )
    ownership_sources = "\n".join(
        source_text[path]
        for path in (
            "ops/preflight_trader_start.sh",
            "ops/start_trader.sh",
            "ops/systemd/monad-trader.service",
            "live/trader.py",
            "live/state.py",
        )
    )
    present_lock_tokens = [
        token for token in lock_tokens if token in ownership_sources
    ]

    launch_paths = [
        dict(
            path="systemd timer/service",
            command="monad-trader.service",
            full_ten_check_preflight=True,
            paper_only_guard=True,
            named_service_unit_scope=True,
            process_duplicate_observation=True,
            scheduled_market_hours_wrapper=True,
            cross_process_atomic_lock=False,
            bar_cycle_idempotency_key=False,
            notes=(
                "Safest declared path: the named unit runs all ten checks, "
                "then the guarded starter. Repo code still has no ownership "
                "primitive shared with processes launched outside the unit."
            ),
        ),
        dict(
            path="guarded manual default",
            command="ops/start_trader.sh",
            full_ten_check_preflight=True,
            paper_only_guard=True,
            named_service_unit_scope=True,
            process_duplicate_observation=True,
            scheduled_market_hours_wrapper=True,
            cross_process_atomic_lock=False,
            bar_cycle_idempotency_key=False,
            notes=(
                "Routes to systemctl; the service, not the shell wrapper, "
                "supplies the ten-check preflight."
            ),
        ),
        dict(
            path="foreground starter bypass",
            command="ops/start_trader.sh --exec",
            full_ten_check_preflight=False,
            paper_only_guard=True,
            named_service_unit_scope=False,
            process_duplicate_observation=False,
            scheduled_market_hours_wrapper=True,
            cross_process_atomic_lock=False,
            bar_cycle_idempotency_key=False,
            notes=(
                "Direct invocation performs only the paper-config and paper-"
                "port checks before exec; it does not establish that ExecStartPre "
                "ran."
            ),
        ),
        dict(
            path="direct module paper scheduler",
            command="python -m live.trader",
            full_ten_check_preflight=False,
            paper_only_guard="default_only",
            named_service_unit_scope=False,
            process_duplicate_observation=False,
            scheduled_market_hours_wrapper=True,
            cross_process_atomic_lock=False,
            bar_cycle_idempotency_key=False,
            notes=(
                "Documented quick-start path bypasses branch, port-7496-closed, "
                "account-flat, health, writable-state, and duplicate checks."
            ),
        ),
        dict(
            path="direct one-shot paper",
            command="python -m live.trader --once",
            full_ten_check_preflight=False,
            paper_only_guard="default_only",
            named_service_unit_scope=False,
            process_duplicate_observation=False,
            scheduled_market_hours_wrapper=False,
            cross_process_atomic_lock=False,
            bar_cycle_idempotency_key=False,
            notes=(
                "--once calls on_bar directly, bypassing the scheduler's "
                "weekday and 09:30-16:00 wrapper."
            ),
        ),
        dict(
            path="direct live-money CLI",
            command="python -m live.trader --live",
            full_ten_check_preflight=False,
            paper_only_guard=False,
            named_service_unit_scope=False,
            process_duplicate_observation=False,
            scheduled_market_hours_wrapper=True,
            cross_process_atomic_lock=False,
            bar_cycle_idempotency_key=False,
            notes=(
                "The CLI explicitly flips LIVE_PAPER_MODE false and selects "
                "the live port, contradicting the repository agent guardrail."
            ),
        ),
    ]

    pgrep_interleaving = [
        "P1 runs preflight check 7; no matching process exists, so it passes.",
        "Before P1 execs, P2 runs the same pgrep; it also passes.",
        "P1 execs python -m live.trader.",
        "P2 execs python -m live.trader.",
        (
            "Both processes now own independent in-memory schedulers; "
            "max_instances=1 constrains each scheduler separately."
        ),
    ]
    entry_interleaving = [
        "P1 and P2 receive the same scheduled cycle and each computes a signal.",
        "P1 reads state.get_position() == None.",
        "P2 reads state.get_position() == None before either local write.",
        "P1 connects with clientId 1 and verifies broker position is flat.",
        (
            "P2's same-clientId connection conflicts and enters the built-in "
            "2/4/6-second retry sequence."
        ),
        (
            "P1 submits parent/TP/SL, writes its local position row, completes "
            "the cycle, and disconnects."
        ),
        "P2 later connects on a retry; it does not reread local state.",
        (
            "If P1's parent is still working but unfilled, IBKR positions can "
            "still be flat; the entry guard does not inspect working orders."
        ),
        "P2 submits a second bracket and DELETE+INSERT replaces P1's local row.",
    ]

    controls = {
        "managed_unit_path": dict(
            present=True,
            scope=(
                "Serializes starts addressed to the named service unit; it "
                "does not own or exclude a separately launched process."
            ),
        ),
        "preflight_pgrep": dict(
            present=True,
            atomic=False,
            limitation=(
                "Observation and exec are separate operations; the pattern "
                "also covers only the -m live.trader command form."
            ),
        ),
        "apscheduler_max_instances": dict(
            present=True,
            value=1,
            scope="one job within one scheduler instance",
        ),
        "fixed_ibkr_client_id": dict(
            present=True,
            value=1,
            useful_failure_modes=[
                "second client exhausts retries and aborts the cycle",
                "second client connects later and sees an already-filled position",
            ],
            residual=(
                "The trader disconnects after every cycle and retries client-ID "
                "conflicts. A later connection can proceed; the entry guard "
                "checks positions, not a still-working parent order."
            ),
        ),
        "sqlite": dict(
            present=True,
            write_serialization=True,
            business_check_to_act_atomic=False,
            position_uniqueness_constraint=_derived_control(
                source_text["live/state.py"],
                ("CREATE UNIQUE INDEX", "UNIQUE (", "UNIQUE(")),
            signal_bar_uniqueness_constraint=_derived_control(
                source_text["live/state.py"],
                ("CREATE UNIQUE INDEX", "UNIQUE (", "UNIQUE(")),
            limitation=(
                "The state read, broker checks, three external order submissions, "
                "and DELETE+INSERT state write are not one transaction."
            ),
        ),
        "cross_process_ownership_lock": dict(
            present=bool(present_lock_tokens),
            matched_tokens=present_lock_tokens,
        ),
        "entry_open_order_idempotency_guard": dict(
            present=False,
            limitation=(
                "openOrders is used by the close/cancel path, not before a new "
                "entry; no durable intent key binds symbol+bar+direction."
            ),
        ),
    }

    return dict(
        scope=(
            "Read-only static audit of every repository-declared launch path, "
            "scheduler ownership, IBKR connection scope, and SQLite state "
            "boundary. No live process was started and no protected file was "
            "changed."
        ),
        current_source_sha256=source_hashes,
        source_contract_tokens=token_audit,
        external_primary_sources={
            "apscheduler_user_guide": (
                "https://apscheduler.readthedocs.io/en/3.x/userguide.html"
                "#limiting-the-number-of-concurrently-executing-instances-of-a-job"
            ),
            "sqlite_transactions": (
                "https://www.sqlite.org/lang_transaction.html"
            ),
            "ibkr_connectivity_client_id": (
                "https://interactivebrokers.github.io/tws-api/connection.html"
            ),
            "systemd_service": (
                "https://www.freedesktop.org/software/systemd/man/latest/"
                "systemd.service.html"
            ),
        },
        launch_path_matrix=launch_paths,
        control_inventory=controls,
        constructive_interleavings=dict(
            preflight_check_to_exec=pgrep_interleaving,
            flat_check_to_bracket_submission=entry_interleaving,
            reachable_duplicate_bracket_path=True,
            necessary_residual_condition=(
                "The second cycle connects after the first disconnect but "
                "before the first parent becomes a visible broker position."
            ),
            falsifiers=[
                (
                    "Constrain every launch to the one named service unit and "
                    "demonstrate direct invocations are mechanically rejected."
                ),
                (
                    "Acquire one shared nonblocking OS/process lock before any "
                    "startup side effect and hold it for process lifetime."
                ),
                (
                    "Atomically claim a durable symbol+bar+direction intent "
                    "before broker submission, and reconcile working orders "
                    "before any retry."
                ),
                (
                    "Show from a broker order ledger that a working parent is "
                    "always visible as a position before any later client-ID "
                    "retry can pass the entry guard."
                ),
            ],
        ),
        policy_and_documentation_conflicts=[
            (
                "AGENTS.md says PAPER ONLY and port 7496 must never be used, "
                "while the CLI and README explicitly expose --live."
            ),
            (
                "README says the trader can never run from an unreviewed "
                "branch, but its documented direct module command never runs "
                "the branch preflight."
            ),
            (
                "The start_trader --exec path is safe only under the service's "
                "ExecStartPre sequencing; direct invocation cannot prove that "
                "precondition."
            ),
        ],
        historical_relevance=(
            "Study 48 observed seven double success-path entry minutes in the "
            "old archive. This audit does not attribute them to current code; "
            "it shows the current repository still lacks an end-to-end proof "
            "that application ownership and per-bar order intent are unique."
        ),
        limitations=[
            (
                "This is a reachability audit, not a runtime experiment. It "
                "does not start the trader, connect to IBKR, or submit orders."
            ),
            (
                "A normal systemd-only deployment is materially safer than "
                "the constructed direct-launch race; host policy, permissions, "
                "or operator discipline outside the repository may further "
                "restrict bypass paths."
            ),
            (
                "Same-client-ID rejection and the broker-position reconciliation "
                "guard often fail safe. The residual duplicate path requires "
                "timing plus a still-working/unfilled first parent."
            ),
            (
                "No current broker order/execution ledger is available, so the "
                "frequency of the residual condition is unidentified."
            ),
        ],
        decision=(
            "The current managed service path is substantially safer than the "
            "historical deployment, but exactly-once ownership is not proved. "
            "Five controls are narrower than the required boundary: pgrep is "
            "check-then-exec, max_instances is per scheduler, clientId 1 is "
            "connection-scoped and retried, SQLite serializes writes rather "
            "than the broker check-to-act sequence, and the entry guard checks "
            "positions rather than working orders. Documented/direct launch "
            "paths bypass the service preflight; --once bypasses market hours; "
            "--live contradicts PAPER ONLY. Treat singleton and per-bar order "
            "intent as unresolved operational risks, not as explanations of "
            "the seven historical double entries."
        ),
    )


def entry_acknowledgement_and_basis_audit() -> Dict[str, object]:
    """Audit what an entry success event and recorded entry basis prove."""
    source_paths = [
        "live/broker.py",
        "live/trader.py",
        "live/state.py",
        "tests/test_broker.py",
        "tests/test_execution_model.py",
        "requirements.txt",
        "tools/live_backtest_reconciliation_study.py",
    ]
    source_text: Dict[str, str] = {}
    source_hashes: Dict[str, str] = {}
    for relative in source_paths:
        path = os.path.join(REPO, relative)
        with open(path, "rb") as fh:
            raw = fh.read()
        source_hashes[relative] = hashlib.sha256(raw).hexdigest()
        source_text[relative] = raw.decode("utf-8")

    required_tokens = {
        "live/broker.py": [
            "def place_bracket_order(",
            "live_price = get_tradeable_price(symbol)",
            "bracket = ib.bracketOrder(",
            "for order in bracket:",
            "ib.placeOrder(contract, order)",
            '"fill_basis": float(live_price)',
        ],
        "live/trader.py": [
            'entry_price = result["fill_basis"]',
            "state.open_position(",
            'log.info(f"ENTRY placed:',
            'entry_event = f"Entry placed:',
        ],
        "live/state.py": [
            "bracket_order_id TEXT NOT NULL",
            "entry_price      REAL NOT NULL",
        ],
        "tests/test_broker.py": [
            "self.assertEqual(ib.placeOrder.call_count, 3)",
            '"fill_basis": 100.0',
        ],
        "tests/test_execution_model.py": [
            "entry_price should be fill_basis",
            "fill_basis = 80.50",
        ],
        "requirements.txt": [
            "ib-insync==0.9.86",
        ],
        "tools/live_backtest_reconciliation_study.py": [
            'LIVE_TRADES = "data/live_runs/pi_export_2026-06-26/trades.jsonl"',
            'CONFIRMED = {"bracket_exit", "stop_hit"}',
        ],
    }
    token_audit = {
        path: {
            token: token in source_text[path]
            for token in tokens
        }
        for path, tokens in required_tokens.items()
    }

    bracket_match = re.search(
        r"^def place_bracket_order\b.*?(?=^def\s)",
        source_text["live/broker.py"],
        flags=re.MULTILINE | re.DOTALL,
    )
    if bracket_match is None:
        raise AssertionError("could not isolate place_bracket_order")
    bracket_source = bracket_match.group(0)
    acknowledgement_terms = [
        "orderStatus",
        ".fills",
        "waitUntil",
        "filledEvent",
        "statusEvent",
        "execDetails",
        "openOrders",
        "reqOpenOrders",
        "reqAllOpenOrders",
        "permId",
    ]
    acknowledgement_term_presence = {
        term: term in bracket_source for term in acknowledgement_terms
    }

    state_entry_fields = [
        "entry_time",
        "entry_price",
        "qty",
        "bracket_order_id",
        "bar_count",
        "status",
        "estimated_exit_price",
        "target_price",
        "stop_price",
        "direction",
    ]
    missing_entry_evidence_fields = [
        "entry_fill_price",
        "entry_fill_time",
        "entry_execution_id",
        "parent_perm_id",
        "parent_order_status",
        "entry_fill_source",
        "signal_bar_time_or_cycle_id",
    ]

    archive_path = os.path.join(
        REPO,
        "data",
        "live_runs",
        "archive_2026-06-18_pre_clean_run",
        "trades.jsonl",
    )
    with open(archive_path) as fh:
        archive_rows = [
            json.loads(line) for line in fh if line.strip()
        ]
    project_exit_confirmed = [
        row
        for row in archive_rows
        if row["exit_type"] in {"bracket_exit", "stop_hit"}
    ]

    def recorded_entry_basis(row: Dict[str, object]) -> float:
        return float(row["exit_price"]) / (
            1.0 + float(row["return_pct"])
        )

    identity_error = max(
        abs(
            float(row["exit_price"]) / recorded_entry_basis(row)
            - 1.0
            - float(row["return_pct"])
        )
        for row in project_exit_confirmed
    )

    def repriced_compounded_pct(entry_slippage_bps: float) -> float:
        adverse = entry_slippage_bps / 10000.0
        wealth = 1.0
        for row in project_exit_confirmed:
            basis = recorded_entry_basis(row)
            adjusted_return = (
                float(row["exit_price"])
                / (basis * (1.0 + adverse))
                - 1.0
            )
            wealth *= 1.0 + adjusted_return
        return 100.0 * (wealth - 1.0)

    slippage_grid_bps = [-10, -5, -2, -1, -0.5, 0, 0.25, 0.5, 1, 2, 5, 10]
    slippage_sensitivity = [
        dict(
            uniform_entry_slippage_bps=float(bps),
            compounded_return_pct=round(
                repriced_compounded_pct(float(bps)), 6
            ),
        )
        for bps in slippage_grid_bps
    ]
    lower, upper = 0.0, 10.0
    if not (
        repriced_compounded_pct(lower) > 0.0
        and repriced_compounded_pct(upper) < 0.0
    ):
        raise AssertionError("entry-slippage break-even is not bracketed")
    for _ in range(80):
        midpoint = (lower + upper) / 2.0
        if repriced_compounded_pct(midpoint) > 0.0:
            lower = midpoint
        else:
            upper = midpoint
    break_even_bps = (lower + upper) / 2.0

    study10_input = os.path.join(
        REPO,
        "data",
        "live_runs",
        "pi_export_2026-06-26",
        "trades.jsonl",
    )

    return dict(
        scope=(
            "Read-only audit of current entry submission and local persistence, "
            "plus a deterministic sensitivity reprice of the sanitized archive's "
            "project-classified bracket_exit/stop_hit rows. No broker connection "
            "was made and no protected file was changed."
        ),
        current_source_sha256=source_hashes,
        source_contract_tokens=token_audit,
        external_primary_sources={
            "ibkr_bracket_transmit": (
                "https://interactivebrokers.github.io/tws-api/"
                "bracket_order.html"
            ),
            "ibkr_order_submission_and_status": (
                "https://interactivebrokers.github.io/tws-api/"
                "order_submission.html"
            ),
            "ibkr_open_order_recovery": (
                "https://interactivebrokers.github.io/tws-api/"
                "open_orders.html"
            ),
            "ibkr_automated_system_monitoring": (
                "https://interactivebrokers.github.io/tws-api/"
                "automated_considerations.html"
            ),
        },
        dependency_contract=dict(
            pinned_ib_insync_version="0.9.86",
            bracket_protocol=[
                "parent limit order: transmit=False",
                "take-profit child: transmit=False",
                "stop-loss child: transmit=True",
                (
                    "placing the final child asks TWS to transmit the parent "
                    "and both children together"
                ),
            ],
            place_order_return_semantics=(
                "ib_insync 0.9.86 placeOrder returns a live Trade immediately "
                "with initial PendingSubmit state for a new order; later status "
                "and fill events update that object."
            ),
        ),
        current_entry_path=dict(
            application_place_order_calls=3,
            place_order_return_values_retained=0,
            acknowledgement_term_presence=(
                acknowledgement_term_presence
            ),
            acknowledgement_checks=sum(
                acknowledgement_term_presence.values()
            ),
            returned_fill_basis_source="pre-submission broker quote",
            actual_entry_fill_observed=False,
            actual_entry_fill_waited_for=False,
            broker_acceptance_observed=False,
            working_orders_reconciled_before_local_success=False,
            local_state_written_after_submission_return=True,
            local_entry_event_written_after_state=True,
            local_state_fields=state_entry_fields,
            missing_entry_evidence_fields=missing_entry_evidence_fields,
        ),
        evidence_ladder=[
            dict(
                stage="tradeable quote obtained",
                current_evidence=True,
                proof="get_tradeable_price returns live_price",
            ),
            dict(
                stage="three API submission calls returned",
                current_evidence=True,
                proof=(
                    "the function reaches its return only after the three-call "
                    "loop completes without raising"
                ),
            ),
            dict(
                stage="TWS openOrder/orderStatus acknowledgement",
                current_evidence=False,
                proof="returned Trade objects are discarded",
            ),
            dict(
                stage="IB server/destination acceptance",
                current_evidence=False,
                proof="no accepted-state or error callback is persisted",
            ),
            dict(
                stage="parent execution and actual entry price",
                current_evidence=False,
                proof="no execDetails/fills wait or entry execution field",
            ),
            dict(
                stage="local position row",
                current_evidence=True,
                proof="state.open_position records quote basis and parent order ID",
            ),
            dict(
                stage="local ENTRY placed event",
                current_evidence=True,
                proof="event is emitted after the local row, not after broker ack",
            ),
        ],
        crash_cutpoints=[
            dict(
                cut="before final stop-child placeOrder",
                broker_possibility=(
                    "parent/TP can exist untransmitted in the current TWS session"
                ),
                local_position=False,
                local_entry_event=False,
            ),
            dict(
                cut="after final transmit call, before local state",
                broker_possibility=(
                    "full bracket can be transmitted, working, rejected, or filled"
                ),
                local_position=False,
                local_entry_event=False,
            ),
            dict(
                cut="after local state, before entry event",
                broker_possibility="same unresolved broker outcomes",
                local_position=True,
                local_entry_event=False,
            ),
            dict(
                cut="after entry event, before alert",
                broker_possibility="same unresolved broker outcomes",
                local_position=True,
                local_entry_event=True,
            ),
        ],
        restart_reconciliation_gap=dict(
            account_flat_preflight_checks_positions_not_working_orders=True,
            entry_guard_checks_positions_not_working_orders=True,
            same_client_id_can_retrieve_active_orders=True,
            current_startup_requests_or_persists_active_entry_orders=False,
            consequence=(
                "A transmitted but unfilled parent can coexist with a flat "
                "account and absent local state after a crash. Current startup "
                "does not reconcile that working order before a later entry."
            ),
        ),
        archive_entry_basis_sensitivity=dict(
            classification=(
                "project exit-confirmed: bracket_exit plus stop_hit; this is "
                "not an independent broker-ledger validation"
            ),
            rows=len(project_exit_confirmed),
            direction_assumption=(
                "long-only, matching the archived shorts-disabled configuration; "
                "the sanitized trade rows do not carry direction"
            ),
            entry_basis_reconstruction=(
                "recorded_entry_basis = exit_price / (1 + recorded return)"
            ),
            maximum_return_identity_error=identity_error,
            recorded_compounded_return_pct=round(
                repriced_compounded_pct(0.0), 6
            ),
            uniform_entry_slippage_sensitivity=slippage_sensitivity,
            adverse_entry_slippage_break_even_bps=round(
                break_even_bps, 6
            ),
            interpretation=(
                "Only 0.435bp of uniform adverse entry-basis error changes the "
                "47-row archive partition's +0.2047% sign. This does not estimate "
                "actual slippage; it demonstrates that the already-flat point "
                "result cannot validate an entry edge without executions."
            ),
        ),
        prior_study_reproducibility=dict(
            original_study10_declared_input=(
                "data/live_runs/pi_export_2026-06-26/trades.jsonl"
            ),
            input_present_in_current_checkout=os.path.exists(study10_input),
            consequence=(
                "The older 51-row +1.55% result cannot be entry-repriced from "
                "this checkout. Its qualitative flat verdict remains consistent "
                "with the current 47-row archive, but 'CONFIRMED' must be read "
                "as exit-classified/exit-confirmed, not fully fill-confirmed."
            ),
        ),
        test_gap=dict(
            current_unit_test_proves=[
                "three placeOrder calls occur",
                "quote-derived prices and returned dictionary shape",
                "quote-derived fill_basis is written to state",
            ],
            current_unit_test_does_not_prove=[
                "TWS acknowledgement",
                "broker or destination acceptance",
                "parent fill",
                "actual entry price",
                "crash/restart working-order reconciliation",
            ],
        ),
        limitations=[
            (
                "No order-status, open-order, or entry-execution ledger survives "
                "in the sanitized archive, so actual entry slippage and rejection "
                "rates are unidentified."
            ),
            (
                "The archive sensitivity applies a uniform hypothetical basis "
                "shift to long trades. It is a sign-fragility calculation, not "
                "an execution-cost estimate."
            ),
            (
                "The current broker library may receive asynchronous callbacks "
                "in memory after placeOrder, but the entry function neither waits "
                "for nor persists them before declaring local success."
            ),
            (
                "The 47-row archive differs from Study 10's now-absent 51-row "
                "input, so no numerical revision of the +1.55% result is claimed."
            ),
        ],
        decision=(
            "Current 'Bracket order placed' and 'ENTRY placed' records prove "
            "that three application submission calls returned and local state "
            "was written; they do not prove TWS acknowledgement, destination "
            "acceptance, or an entry fill. fill_basis is a pre-submission quote, "
            "not an execution. The 47-row project exit-confirmed archive is "
            "+0.2047% at that basis and crosses zero with only 0.435bp uniform "
            "adverse entry error, so it remains flat but is not a fully "
            "fill-confirmed edge sample. Entry evidence should be described as "
            "exit-confirmed only until parent status, permId, execution price/"
            "time, and restart open-order reconciliation are durably captured."
        ),
    )


def volatility_distribution_audit(
    sig: pd.DataFrame,
    daily_panel: pd.DataFrame,
) -> Dict[str, object]:
    """Test whether QQQ ex-dividend returns drive the vol20 classifier."""
    qqq_dividends = _load_qqq_distributions().reindex(
        daily_panel.index, fill_value=0.0
    )
    qqq_close = daily_panel["QQQ_close"]
    raw_return = qqq_close.pct_change()
    distribution_return = (
        (qqq_close + qqq_dividends) / qqq_close.shift(1) - 1
    )
    raw_vol = (
        raw_return.rolling(20).std(ddof=1).shift(1) * math.sqrt(252)
    )
    distribution_vol = (
        distribution_return.rolling(20).std(ddof=1).shift(1)
        * math.sqrt(252)
    )
    pair = pd.concat(
        [
            raw_vol.rename("raw_close_vol20"),
            distribution_vol.rename("distribution_inclusive_vol20"),
        ],
        axis=1,
    ).dropna()
    pair["difference"] = (
        pair["distribution_inclusive_vol20"] - pair["raw_close_vol20"]
    )
    raw_flag = pair["raw_close_vol20"] >= 0.15
    distribution_flag = pair["distribution_inclusive_vol20"] >= 0.15
    flipped = pair.loc[raw_flag != distribution_flag]

    tqqq_gap = (
        daily_panel["TQQQ_open"]
        / daily_panel["TQQQ_close"].shift(1)
        - 1
    ).reindex(pair.index)
    severe = tqqq_gap <= -0.02

    tqqq_actions = _load_corporate_actions()
    tqqq_dividends = tqqq_actions["dividend_per_share"].reindex(
        daily_panel.index, fill_value=0.0
    )
    daily_open_prices = {
        idx.date(): float(value)
        for idx, value in daily_panel["TQQQ_open"].dropna().items()
    }
    daily_close_prices = {
        idx.date(): float(value)
        for idx, value in daily_panel["TQQQ_close"].dropna().items()
    }
    target, stop = 0.01, 0.005
    bars = int(getattr(config, "MAX_TRADE_BARS_LIVE", 10))
    hold_raw = simulate(
        sig, target, stop, bars,
        gap_aware=True, one_position=True, scan_entry_bar=True,
        session_open_prices=daily_open_prices,
    )
    hold, _ = _credit_earned_distributions(
        hold_raw, tqqq_dividends
    )
    hold_metrics = equity_metrics(hold)

    def classifier_row(
        label: str,
        flag: pd.Series,
    ) -> Dict[str, object]:
        dates = {idx.date() for idx in flag.index[flag]}
        raw = simulate(
            sig, target, stop, bars,
            gap_aware=True, one_position=True, scan_entry_bar=True,
            flatten_before_dates=dates,
            session_close_prices=daily_close_prices,
            session_open_prices=daily_open_prices,
        )
        adjusted, _ = _credit_earned_distributions(
            raw, tqqq_dividends
        )
        metrics = equity_metrics(adjusted)
        exits = int((raw["exit_type"] == "risk_flatten").sum())
        gaps = int(raw["overnight_gap_stop"].sum())
        baseline_gaps = int(hold_raw["overnight_gap_stop"].sum())
        return_delta = (
            metrics["total_return_pct"] - hold_metrics["total_return_pct"]
        )
        dd_improvement = (
            metrics["max_drawdown_pct"]
            - hold_metrics["max_drawdown_pct"]
        )
        gap_reduction = (1 - gaps / max(1, baseline_gaps)) * 100
        return dict(
            classifier=label,
            nights_flagged=int(flag.sum()),
            exposure_removed_pct=round(float(flag.mean()) * 100, 3),
            severe_gap_capture_pct=round(
                float((flag & severe).sum())
                / max(1, int(severe.sum()))
                * 100,
                3,
            ),
            risk_flatten_exits=exits,
            overnight_gap_stops=gaps,
            gap_reduction_pct=round(gap_reduction, 2),
            metrics=metrics,
            total_return_delta_vs_hold_pp=round(return_delta, 4),
            maxdd_improvement_vs_hold_pp=round(dd_improvement, 4),
            first_order_break_even_extra_cost_bps_per_exit=round(
                (return_delta / 100)
                / max(1, exits)
                / POSITION_FRACTION
                * 10000,
                2,
            ),
            risk_gate_pass=bool(
                gap_reduction >= 50
                and dd_improvement >= 2
                and return_delta >= -1
            ),
        )

    return dict(
        source=dict(
            qqq_action_dates=int((qqq_dividends > 0).sum()),
            raw_source_sha256=QQQ_ACTIONS_SOURCE_SHA256,
            durable_audit=os.path.relpath(QQQ_DISTRIBUTIONS_AUDIT, REPO),
            sponsor_crosscheck=(
                "Invesco reports 2025-06-23 QQQ distribution $0.59111; "
                "Yahoo records rounded $0.591"
            ),
        ),
        volatility_difference=dict(
            n_sessions=int(len(pair)),
            mean_signed_annualized_vol_pp=round(
                float(pair["difference"].mean()) * 100, 5
            ),
            median_absolute_annualized_vol_pp=round(
                float(pair["difference"].abs().median()) * 100, 5
            ),
            p95_absolute_annualized_vol_pp=round(
                float(pair["difference"].abs().quantile(0.95)) * 100, 5
            ),
            maximum_absolute_annualized_vol_pp=round(
                float(pair["difference"].abs().max()) * 100, 5
            ),
        ),
        threshold_classification=dict(
            raw_flagged_nights=int(raw_flag.sum()),
            distribution_inclusive_flagged_nights=int(
                distribution_flag.sum()
            ),
            flipped_nights=int(len(flipped)),
            raw_only_nights=int((raw_flag & ~distribution_flag).sum()),
            distribution_only_nights=int(
                (~raw_flag & distribution_flag).sum()
            ),
            flipped_rows=[
                dict(
                    date=str(idx.date()),
                    raw_close_vol20_pct=round(
                        float(row["raw_close_vol20"]) * 100, 4
                    ),
                    distribution_inclusive_vol20_pct=round(
                        float(
                            row["distribution_inclusive_vol20"]
                        ) * 100,
                        4,
                    ),
                )
                for idx, row in flipped.iterrows()
            ],
        ),
        policy_rows=[
            classifier_row("raw_close_vol20", raw_flag),
            classifier_row(
                "distribution_inclusive_vol20", distribution_flag
            ),
        ],
        corrected_hold_metrics=hold_metrics,
        decision=(
            "Use distribution-inclusive QQQ returns for the volatility state. "
            "The audit determines whether that economically correct convention "
            "changes the selected policy conclusion."
        ),
        caveat=(
            "Yahoo distributions are rounded vendor data; one recent amount is "
            "sponsor-cross-checked. Cash addition closely approximates adjusted-close "
            "returns but omits tax and reinvestment timing, which are immaterial to "
            "this daily volatility-state audit."
        ),
    )


def volatility_decision_time_audit(
    sig: pd.DataFrame,
    daily_panel: pd.DataFrame,
) -> Dict[str, object]:
    """Prove classifier availability before the MOC lock and expose lookahead."""
    window = 20
    dividends = _load_qqq_distributions().reindex(
        daily_panel.index, fill_value=0.0
    )
    total_return = (
        (daily_panel["QQQ_close"] + dividends)
        / daily_panel["QQQ_close"].shift(1)
        - 1
    )
    correct = _lagged_qqq_volatility(
        daily_panel, window=window
    ).dropna()
    manual_values = []
    for idx in correct.index:
        loc = int(daily_panel.index.get_loc(idx))
        cut = total_return.iloc[loc - window:loc]
        manual_values.append(float(cut.std(ddof=1) * math.sqrt(252)))
    manual = pd.Series(manual_values, index=correct.index)
    max_recompute_diff = float((manual - correct).abs().max())
    if max_recompute_diff > 1e-12:
        raise AssertionError("lagged volatility fails truncated recomputation")

    lookahead = (
        total_return.rolling(window).std(ddof=1) * math.sqrt(252)
    ).reindex(correct.index)
    correct_flag = correct >= 0.15
    lookahead_flag = lookahead >= 0.15
    all_flips = correct_flag != lookahead_flag
    strategy_start = pd.Timestamp(sig.index[0].date())
    strategy_end = pd.Timestamp(sig.index[-1].date())
    strategy_mask = (
        (correct.index >= strategy_start)
        & (correct.index <= strategy_end)
    )
    strategy_flips = all_flips & strategy_mask
    margin = (correct - 0.15).abs()

    tqqq_actions = _load_corporate_actions()
    tqqq_dividends = tqqq_actions["dividend_per_share"].reindex(
        daily_panel.index, fill_value=0.0
    )
    opens = {
        idx.date(): float(value)
        for idx, value in daily_panel["TQQQ_open"].dropna().items()
    }
    closes = {
        idx.date(): float(value)
        for idx, value in daily_panel["TQQQ_close"].dropna().items()
    }
    target, stop = 0.01, 0.005
    bars = int(getattr(config, "MAX_TRADE_BARS_LIVE", 10))
    hold_raw = simulate(
        sig, target, stop, bars,
        gap_aware=True, one_position=True, scan_entry_bar=True,
        session_open_prices=opens,
    )
    hold, _ = _credit_earned_distributions(
        hold_raw, tqqq_dividends
    )
    hold_metrics = equity_metrics(hold)

    def policy_row(label: str, flags: pd.Series) -> Dict[str, object]:
        dates = {idx.date() for idx in flags.index[flags]}
        raw = simulate(
            sig, target, stop, bars,
            gap_aware=True, one_position=True, scan_entry_bar=True,
            flatten_before_dates=dates,
            session_close_prices=closes,
            session_open_prices=opens,
        )
        adjusted, _ = _credit_earned_distributions(
            raw, tqqq_dividends
        )
        metrics = equity_metrics(adjusted)
        exits = int((raw["exit_type"] == "risk_flatten").sum())
        return dict(
            classifier=label,
            risk_flatten_exits=exits,
            overnight_gap_stops=int(raw["overnight_gap_stop"].sum()),
            metrics=metrics,
            total_return_delta_vs_hold_pp=round(
                metrics["total_return_pct"]
                - hold_metrics["total_return_pct"],
                4,
            ),
            first_order_break_even_extra_cost_bps_per_exit=round(
                (
                    (
                        metrics["total_return_pct"]
                        - hold_metrics["total_return_pct"]
                    )
                    / 100
                    / max(1, exits)
                    / POSITION_FRACTION
                    * 10000
                ),
                2,
            ),
        )

    margin_rows = []
    for distance_pp in (0.10, 0.25, 0.50, 1.00):
        close_to_threshold = margin <= distance_pp / 100
        margin_rows.append(
            dict(
                distance_from_threshold_pp=distance_pp,
                all_history_nights=int(close_to_threshold.sum()),
                strategy_window_nights=int(
                    (close_to_threshold & strategy_mask).sum()
                ),
            )
        )
    return dict(
        construction=(
            "For session t, recompute vol20 from exactly the 20 QQQ total-return "
            "observations ending at t-1. Compare with the tempting unshifted series "
            "that includes t's official close, unavailable before the MOC cutoff."
        ),
        truncated_recompute=dict(
            sessions_checked=int(len(correct)),
            maximum_absolute_difference=max_recompute_diff,
            passed=bool(max_recompute_diff <= 1e-12),
            latest_required_input_for_session_t="QQQ official close and distribution at t-1",
            decision_available_before_session_t_open=True,
        ),
        threshold_margin_rows=margin_rows,
        unshifted_lookahead=dict(
            all_history_threshold_flips=int(all_flips.sum()),
            strategy_window_threshold_flips=int(strategy_flips.sum()),
            correct_flagged_strategy_nights=int(
                (correct_flag & strategy_mask).sum()
            ),
            lookahead_flagged_strategy_nights=int(
                (lookahead_flag & strategy_mask).sum()
            ),
            flipped_strategy_rows=[
                dict(
                    date=str(idx.date()),
                    lagged_vol20_pct=round(float(correct.loc[idx]) * 100, 4),
                    unshifted_vol20_pct=round(
                        float(lookahead.loc[idx]) * 100, 4
                    ),
                )
                for idx in correct.index[strategy_flips]
            ],
        ),
        policy_rows=[
            policy_row("lagged_decision_feasible", correct_flag),
            policy_row("unshifted_close_lookahead", lookahead_flag),
        ],
        corrected_hold_metrics=hold_metrics,
        decision=(
            "Freeze the classifier from t-1 data before session t begins. Never "
            "substitute the current session's official close into a policy that must "
            "be committed before the Closing Cross."
        ),
        caveat=(
            "Vendor publication and ingestion latency still need paper-shadow logging. "
            "The proof establishes data chronology in the research panel, not runtime "
            "availability or successful auction submission."
        ),
    )


def local_volatility_threshold_robustness(
    sig: pd.DataFrame,
    daily_panel: pd.DataFrame,
) -> Dict[str, object]:
    """Stress the selected 15% threshold locally without re-optimizing it."""
    thresholds = tuple(value / 10000 for value in range(1400, 1601, 25))
    vol20 = _lagged_qqq_volatility(daily_panel, window=20).dropna()
    tqqq_actions = _load_corporate_actions()
    dividends = tqqq_actions["dividend_per_share"].reindex(
        daily_panel.index, fill_value=0.0
    )
    opens = {
        idx.date(): float(value)
        for idx, value in daily_panel["TQQQ_open"].dropna().items()
    }
    closes = {
        idx.date(): float(value)
        for idx, value in daily_panel["TQQQ_close"].dropna().items()
    }
    target, stop = 0.01, 0.005
    bars = int(getattr(config, "MAX_TRADE_BARS_LIVE", 10))
    hold_raw = simulate(
        sig, target, stop, bars,
        gap_aware=True, one_position=True, scan_entry_bar=True,
        session_open_prices=opens,
    )
    hold, _ = _credit_earned_distributions(hold_raw, dividends)
    hold_metrics = equity_metrics(hold)
    baseline_gaps = int(hold_raw["overnight_gap_stop"].sum())
    rows = []
    for threshold in thresholds:
        flag = vol20 >= threshold
        dates = {idx.date() for idx in flag.index[flag]}
        raw = simulate(
            sig, target, stop, bars,
            gap_aware=True, one_position=True, scan_entry_bar=True,
            flatten_before_dates=dates,
            session_close_prices=closes,
            session_open_prices=opens,
        )
        adjusted, _ = _credit_earned_distributions(raw, dividends)
        metrics = equity_metrics(adjusted)
        exits = int((raw["exit_type"] == "risk_flatten").sum())
        gaps = int(raw["overnight_gap_stop"].sum())
        gap_reduction = (1 - gaps / max(1, baseline_gaps)) * 100
        return_delta = (
            metrics["total_return_pct"] - hold_metrics["total_return_pct"]
        )
        dd_improvement = (
            metrics["max_drawdown_pct"] - hold_metrics["max_drawdown_pct"]
        )
        rows.append(
            dict(
                threshold_pct=round(threshold * 100, 2),
                nights_flagged=int(flag.sum()),
                exposure_removed_pct=round(float(flag.mean()) * 100, 3),
                risk_flatten_exits=exits,
                overnight_gap_stops=gaps,
                gap_reduction_pct=round(gap_reduction, 2),
                metrics=metrics,
                total_return_delta_vs_hold_pp=round(return_delta, 4),
                maxdd_improvement_vs_hold_pp=round(dd_improvement, 4),
                first_order_break_even_extra_cost_bps_per_exit=round(
                    (return_delta / 100)
                    / max(1, exits)
                    / POSITION_FRACTION
                    * 10000,
                    2,
                ),
                risk_gate_pass=bool(
                    gap_reduction >= 50
                    and dd_improvement >= 2
                    and return_delta >= -1
                ),
            )
        )
    return dict(
        grid_definition=(
            "Symmetric 14.00%-16.00% grid in 0.25pp steps around the already "
            "selected 15% threshold. Robustness stress only; no row is eligible "
            "to replace the frozen forward hypothesis."
        ),
        corrected_hold_metrics=hold_metrics,
        threshold_rows=rows,
        stability_summary=dict(
            thresholds_tested=len(rows),
            risk_gate_pass_count=sum(row["risk_gate_pass"] for row in rows),
            total_return_range_pct=[
                min(row["metrics"]["total_return_pct"] for row in rows),
                max(row["metrics"]["total_return_pct"] for row in rows),
            ],
            max_drawdown_range_pct=[
                min(row["metrics"]["max_drawdown_pct"] for row in rows),
                max(row["metrics"]["max_drawdown_pct"] for row in rows),
            ],
            flatten_exit_range=[
                min(row["risk_flatten_exits"] for row in rows),
                max(row["risk_flatten_exits"] for row in rows),
            ],
            remaining_gap_stop_range=[
                min(row["overnight_gap_stops"] for row in rows),
                max(row["overnight_gap_stops"] for row in rows),
            ],
            cost_ceiling_range_bps=[
                min(
                    row[
                        "first_order_break_even_extra_cost_bps_per_exit"
                    ]
                    for row in rows
                ),
                max(
                    row[
                        "first_order_break_even_extra_cost_bps_per_exit"
                    ]
                    for row in rows
                ),
            ],
        ),
        decision=(
            "A local plateau supports threshold robustness only if every symmetric "
            "neighbor preserves the descriptive gate. It cannot undo post-selection "
            "or replace the fixed forward test."
        ),
    )


def mitigation_path_decomposition(
    sig: pd.DataFrame,
    daily_panel: pd.DataFrame,
) -> Dict[str, object]:
    """Separate direct same-cohort flatten effects from opportunity-path drift."""
    tqqq_actions = _load_corporate_actions()
    dividends = tqqq_actions["dividend_per_share"].reindex(
        daily_panel.index, fill_value=0.0
    )
    opens = {
        idx.date(): float(value)
        for idx, value in daily_panel["TQQQ_open"].dropna().items()
    }
    closes = {
        idx.date(): float(value)
        for idx, value in daily_panel["TQQQ_close"].dropna().items()
    }
    vol20 = _lagged_qqq_volatility(daily_panel).dropna()
    vol_dates = {idx.date() for idx in vol20.index[vol20 >= 0.15]}
    target, stop = 0.01, 0.005
    bars = int(getattr(config, "MAX_TRADE_BARS_LIVE", 10))
    baseline_raw = simulate(
        sig, target, stop, bars,
        gap_aware=True, one_position=True, scan_entry_bar=True,
        session_open_prices=opens,
    )
    baseline, _ = _credit_earned_distributions(
        baseline_raw, dividends
    )
    baseline_metrics = equity_metrics(baseline)
    session_dates = pd.DatetimeIndex(
        sorted(
            {
                pd.Timestamp(ts).tz_localize(None).normalize()
                for ts in sig.index
            }
        )
    )
    baseline_logs = _daily_account_log_returns(
        baseline, session_dates
    )

    def fixed_cohort(
        policy: str,
        flagged_dates: set,
    ) -> Tuple[pd.DataFrame, int]:
        out = baseline_raw.copy()
        flatten_count = 0
        for trade_idx, trade in out.iterrows():
            entry_loc = int(trade["signal_loc"]) + 1
            original_exit_loc = int(trade["exit_loc"])
            for loc in range(entry_loc + 1, original_exit_loc + 1):
                if sig.index[loc].date() == sig.index[loc - 1].date():
                    continue
                next_date = sig.index[loc].date()
                should_flatten = (
                    policy == "daily_flatten"
                    or next_date in flagged_dates
                )
                if not should_flatten:
                    continue
                exit_loc = loc - 1
                prior_date = sig.index[exit_loc].date()
                exit_price = closes.get(
                    prior_date, float(sig["close"].iloc[exit_loc])
                )
                new_return = (
                    int(trade["direction"])
                    * (exit_price - float(trade["entry_price"]))
                    / float(trade["entry_price"])
                    - SLIPPAGE
                )
                out.at[trade_idx, "exit_timestamp"] = sig.index[exit_loc]
                out.at[trade_idx, "exit_price"] = exit_price
                out.at[trade_idx, "return"] = new_return
                out.at[trade_idx, "exit_type"] = (
                    "fixed_cohort_%s" % policy
                )
                out.at[trade_idx, "held_overnight"] = (
                    pd.Timestamp(trade["entry_timestamp"]).date()
                    != sig.index[exit_loc].date()
                )
                out.at[trade_idx, "gap_through_stop"] = False
                out.at[trade_idx, "overnight_gap_stop"] = False
                out.at[trade_idx, "exit_loc"] = exit_loc
                flatten_count += 1
                break
        adjusted, _ = _credit_earned_distributions(out, dividends)
        return adjusted, flatten_count

    rows = []
    for policy, dates in (
        ("vol20_at_least_15pct", vol_dates),
        ("daily_flatten", set()),
    ):
        fixed, fixed_exits = fixed_cohort(policy, dates)
        kwargs: Dict[str, object] = dict(
            session_close_prices=closes,
            session_open_prices=opens,
        )
        if policy == "daily_flatten":
            kwargs["flatten_eod"] = True
            dynamic_exit_type = "eod_flatten"
        else:
            kwargs["flatten_before_dates"] = dates
            dynamic_exit_type = "risk_flatten"
        dynamic_raw = simulate(
            sig, target, stop, bars,
            gap_aware=True, one_position=True, scan_entry_bar=True,
            **kwargs,
        )
        dynamic, _ = _credit_earned_distributions(
            dynamic_raw, dividends
        )
        fixed_metrics = equity_metrics(fixed)
        dynamic_metrics = equity_metrics(dynamic)
        fixed_logs = _daily_account_log_returns(fixed, session_dates)
        fixed_log_difference = fixed_logs - baseline_logs
        fixed_annual_rows = []
        for year in sorted(set(session_dates.year)):
            year_mask = session_dates.year == year
            fixed_annual_rows.append(
                dict(
                    year=int(year),
                    relative_wealth_effect_pct=round(
                        math.expm1(
                            float(fixed_log_difference[year_mask].sum())
                        )
                        * 100,
                        4,
                    ),
                )
            )
        trade_delta = (
            fixed["return"].to_numpy(dtype=float)
            - baseline["return"].to_numpy(dtype=float)
        )
        changed_idx = np.flatnonzero(np.abs(trade_delta) > 1e-12)
        contribution_rows = []
        for position in changed_idx:
            temp = fixed.copy()
            temp.at[position, "return"] = baseline.at[position, "return"]
            without = equity_metrics(temp)
            contribution_rows.append(
                dict(
                    trade_index=int(position),
                    signal_timestamp=str(
                        baseline.iloc[position]["signal_timestamp"]
                    ),
                    baseline_exit_timestamp=str(
                        baseline.iloc[position]["exit_timestamp"]
                    ),
                    fixed_exit_timestamp=str(
                        fixed.iloc[position]["exit_timestamp"]
                    ),
                    baseline_exit_type=str(
                        baseline.iloc[position]["exit_type"]
                    ),
                    fixed_exit_type=str(
                        fixed.iloc[position]["exit_type"]
                    ),
                    trade_return_delta_bps=round(
                        float(trade_delta[position]) * 10000, 3
                    ),
                    leave_one_out_account_contribution_pp=round(
                        fixed_metrics["total_return_pct"]
                        - without["total_return_pct"],
                        6,
                    ),
                )
            )
        ranked_positive = sorted(
            (
                row for row in contribution_rows
                if row["leave_one_out_account_contribution_pp"] > 0
            ),
            key=lambda row: row[
                "leave_one_out_account_contribution_pp"
            ],
            reverse=True,
        )
        removal_rows = []
        for k in (1, 3, 5, 10):
            chosen = ranked_positive[:k]
            temp = fixed.copy()
            for item in chosen:
                position = item["trade_index"]
                temp.at[position, "return"] = baseline.at[
                    position, "return"
                ]
            remaining_delta = (
                equity_metrics(temp)["total_return_pct"]
                - baseline_metrics["total_return_pct"]
            )
            removal_rows.append(
                dict(
                    top_k=k,
                    available_positive_events=len(chosen),
                    remaining_fixed_cohort_delta_pp=round(
                        remaining_delta, 4
                    ),
                    retained_share_of_direct_delta_pct=round(
                        remaining_delta
                        / max(
                            fixed_metrics["total_return_pct"]
                            - baseline_metrics["total_return_pct"],
                            1e-12,
                        )
                        * 100,
                        2,
                    ),
                )
            )
        by_year = []
        baseline_exit_year = pd.DatetimeIndex(
            baseline["exit_timestamp"]
        ).year
        for year in sorted(set(baseline_exit_year[changed_idx])):
            mask = changed_idx[
                baseline_exit_year[changed_idx] == year
            ]
            by_year.append(
                dict(
                    year=int(year),
                    changed_trades=int(len(mask)),
                    positive_trades=int((trade_delta[mask] > 0).sum()),
                    negative_trades=int((trade_delta[mask] < 0).sum()),
                    net_trade_return_delta_pp=round(
                        float(trade_delta[mask].sum()) * 100, 4
                    ),
                )
            )
        by_exit_type = []
        changed_exit_types = baseline.iloc[changed_idx][
            "exit_type"
        ].astype(str)
        for exit_type in sorted(set(changed_exit_types)):
            positions = changed_idx[
                changed_exit_types.to_numpy() == exit_type
            ]
            by_exit_type.append(
                dict(
                    baseline_exit_type=exit_type,
                    changed_trades=int(len(positions)),
                    positive_changes=int(
                        (trade_delta[positions] > 0).sum()
                    ),
                    negative_changes=int(
                        (trade_delta[positions] < 0).sum()
                    ),
                    net_trade_return_delta_pp=round(
                        float(trade_delta[positions].sum()) * 100, 4
                    ),
                    mean_trade_return_delta_bps=round(
                        float(trade_delta[positions].mean()) * 10000, 3
                    ),
                )
            )
        n_positive = int((trade_delta > 1e-12).sum())
        n_changed = int(len(changed_idx))
        favorable_wilson = _wilson_interval(n_positive, n_changed)
        baseline_signals = set(
            str(value) for value in baseline_raw["signal_timestamp"]
        )
        dynamic_signals = set(
            str(value) for value in dynamic_raw["signal_timestamp"]
        )
        direct_delta = (
            fixed_metrics["total_return_pct"]
            - baseline_metrics["total_return_pct"]
        )
        dynamic_delta = (
            dynamic_metrics["total_return_pct"]
            - baseline_metrics["total_return_pct"]
        )
        rows.append(
            dict(
                policy=policy,
                baseline_cohort_trades=int(len(baseline)),
                fixed_cohort_flatten_exits=fixed_exits,
                fixed_cohort_metrics=fixed_metrics,
                dynamic_policy_trades=int(len(dynamic)),
                dynamic_flatten_exits=int(
                    (dynamic_raw["exit_type"] == dynamic_exit_type).sum()
                ),
                dynamic_metrics=dynamic_metrics,
                common_signal_entries=len(
                    baseline_signals & dynamic_signals
                ),
                dynamic_only_signal_entries=len(
                    dynamic_signals - baseline_signals
                ),
                baseline_only_signal_entries=len(
                    baseline_signals - dynamic_signals
                ),
                fixed_cohort_total_return_delta_vs_hold_pp=round(
                    direct_delta, 4
                ),
                fixed_cohort_observed_relative_wealth_effect_pct=round(
                    math.expm1(float(fixed_log_difference.sum())) * 100,
                    4,
                ),
                fixed_cohort_paired_daily_log_block_bootstrap_relative_wealth95_pct={
                    str(block): _circular_block_relative_wealth_ci(
                        fixed_log_difference, block
                    )
                    for block in (5, 20, 60)
                },
                fixed_cohort_annual_relative_wealth_rows=fixed_annual_rows,
                fixed_cohort_first_order_break_even_extra_cost_bps_per_exit=round(
                    (direct_delta / 100)
                    / max(1, fixed_exits)
                    / POSITION_FRACTION
                    * 10000,
                    2,
                ),
                dynamic_total_return_delta_vs_hold_pp=round(
                    dynamic_delta, 4
                ),
                opportunity_path_increment_pp=round(
                    dynamic_metrics["total_return_pct"]
                    - fixed_metrics["total_return_pct"],
                    4,
                ),
                direct_effect_share_of_dynamic_delta_pct=round(
                    direct_delta / max(dynamic_delta, 1e-12) * 100, 2
                ),
                direct_effect_concentration=dict(
                    changed_trades=int(len(changed_idx)),
                    positive_changes=int((trade_delta > 1e-12).sum()),
                    negative_changes=int((trade_delta < -1e-12).sum()),
                    gross_positive_trade_delta_pp=round(
                        float(trade_delta[trade_delta > 0].sum()) * 100,
                        4,
                    ),
                    gross_negative_trade_delta_pp=round(
                        float(trade_delta[trade_delta < 0].sum()) * 100,
                        4,
                    ),
                    net_trade_delta_pp=round(
                        float(trade_delta.sum()) * 100, 4
                    ),
                    top_positive_events=ranked_positive[:10],
                    top_event_removal_rows=removal_rows,
                    by_baseline_exit_year=by_year,
                    by_baseline_exit_type=by_exit_type,
                    favorable_intervention_rate=dict(
                        favorable=n_positive,
                        unfavorable=int(
                            (trade_delta < -1e-12).sum()
                        ),
                        rate_pct=round(
                            n_positive / max(1, n_changed) * 100, 2
                        ),
                        wilson95_pct=[
                            round(favorable_wilson[0] * 100, 2),
                            round(favorable_wilson[1] * 100, 2),
                        ],
                        one_sided_exact_p_value_vs_50pct=round(
                            _binomial_upper_tail(
                                n_changed, n_positive, 0.50
                            ),
                            6,
                        ),
                    ),
                    avoided_baseline_overnight_gap_stops=int(
                        (
                            baseline.iloc[changed_idx]["exit_type"]
                            == "overnight_gap_stop"
                        ).sum()
                    ),
                    median_changed_trade_delta_bps=round(
                        float(np.median(trade_delta[changed_idx]))
                        * 10000,
                        3,
                    ),
                ),
            )
        )
    return dict(
        construction=(
            "Fixed-cohort rows apply the earlier close only to the 1,117 baseline "
            "trades and preserve every baseline entry. Dynamic rows rerun the normal "
            "one-position engine, so earlier exits may admit different future signals."
        ),
        baseline_metrics=baseline_metrics,
        policy_rows=rows,
        interpretation=(
            "The fixed-cohort delta is the direct loss-avoidance effect on known "
            "baseline opportunities. The residual dynamic-minus-fixed increment is "
            "path replacement, not clean mitigation alpha."
        ),
        caveat=(
            "Sequential compounding makes percentage-point components descriptive "
            "rather than an exact additive P&L attribution. Fixed-cohort replay also "
            "holds later baseline entries constant even though an actual account path "
            "would change after an earlier exit."
        ),
    )


def session_close_validation(
    hourly: pd.DataFrame, daily_panel: pd.DataFrame
) -> Dict[str, object]:
    """Compare the vendor's final hourly print with its official daily close."""
    hourly_close = hourly.groupby(hourly.index.date).last()["close"]
    hourly_close.index = pd.to_datetime(hourly_close.index)
    pair = pd.concat(
        [
            hourly_close.rename("last_hourly_close"),
            daily_panel["TQQQ_close"].rename("official_daily_close"),
        ],
        axis=1,
    ).dropna()
    diff_bps = (pair["last_hourly_close"] / pair["official_daily_close"] - 1.0) * 10000
    abs_diff = diff_bps.abs()
    worst_idx = abs_diff.nlargest(10).index
    return dict(
        n_sessions=int(len(pair)),
        mean_signed_diff_bps=round(float(diff_bps.mean()), 3),
        median_signed_diff_bps=round(float(diff_bps.median()), 3),
        median_abs_diff_bps=round(float(abs_diff.median()), 3),
        p95_abs_diff_bps=round(float(np.percentile(abs_diff, 95)), 3),
        p99_abs_diff_bps=round(float(np.percentile(abs_diff, 99)), 3),
        maximum_abs_diff_bps=round(float(abs_diff.max()), 3),
        pct_abs_diff_gt_5bps=round(float(np.mean(abs_diff > 5) * 100), 2),
        pct_abs_diff_gt_10bps=round(float(np.mean(abs_diff > 10) * 100), 2),
        worst=[
            dict(
                date=str(idx.date()),
                last_hourly_close=round(float(pair.loc[idx, "last_hourly_close"]), 4),
                official_daily_close=round(
                    float(pair.loc[idx, "official_daily_close"]), 4
                ),
                signed_diff_bps=round(float(diff_bps.loc[idx]), 3),
            )
            for idx in worst_idx
        ],
        decision=(
            "Use the official daily close as the MOC counterfactual proxy and retain the "
            "last-hourly-bar replay only as sensitivity; neither is an actual auction fill."
        ),
    )


def unfilled_parent_phantom_trade_audit() -> Dict[str, object]:
    """Trace a locally recorded but unfilled/rejected entry through reconcile."""
    source_paths = [
        "live/trader.py",
        "live/broker.py",
        "live/state.py",
        "tests/test_trader_reconcile.py",
    ]
    archive_root = os.path.join(
        REPO,
        "data",
        "live_runs",
        "archive_2026-06-18_pre_clean_run",
    )
    archive_paths = {
        name: os.path.join(archive_root, name)
        for name in ("metadata.json", "monitor_events.jsonl", "trades.jsonl")
    }
    source_text: Dict[str, str] = {}
    source_hashes: Dict[str, str] = {}
    for relative in source_paths:
        path = os.path.join(REPO, relative)
        with open(path, "rb") as fh:
            raw = fh.read()
        source_hashes[relative] = hashlib.sha256(raw).hexdigest()
        source_text[relative] = raw.decode("utf-8")
    archive_hashes = {}
    for name, path in archive_paths.items():
        with open(path, "rb") as fh:
            archive_hashes[name] = hashlib.sha256(fh.read()).hexdigest()

    required_tokens = {
        "live/trader.py": [
            'entry_price = result["fill_basis"]',
            "state.open_position(",
            "broker_pos = broker.get_open_position(position.symbol)",
            'if broker_pos is None or broker_pos["qty"] == 0:',
            "fill = broker.get_bracket_fill(",
            "exit_price, exit_type = _infer_bracket_exit(position, ref_price)",
            "state.close_position(return_pct=ret, exit_type=exit_type,",
            'exit_action = f"exit_{exit_type}_inferred"',
            "# Fall through to entry check",
        ],
        "live/broker.py": [
            "def get_open_position(symbol: str) -> dict | None:",
            "positions = ib.positions()",
            "def get_bracket_fill(",
        ],
        "live/state.py": [
            "def open_position(",
            "def close_position(",
        ],
    }
    token_audit = {
        path: {token: token in source_text[path] for token in tokens}
        for path, tokens in required_tokens.items()
    }
    if not all(
        present
        for path_checks in token_audit.values()
        for present in path_checks.values()
    ):
        raise AssertionError("current reconciliation contract changed")

    infer_match = re.search(
        r"^def _infer_bracket_exit\b.*?(?=^def\s)",
        source_text["live/trader.py"],
        flags=re.MULTILINE | re.DOTALL,
    )
    if infer_match is None:
        raise AssertionError("could not isolate _infer_bracket_exit")
    infer_source = infer_match.group(0)
    unknown_outcomes = [
        token
        for token in ("unknown", "unverified", "pending_close")
        if token in infer_source
    ]
    terminal_return_count = len(
        re.findall(
            r"^\s*return\s+.+,\s*[\"'](?:target_hit|stop_hit)[\"']",
            infer_source,
            flags=re.MULTILINE,
        )
    )

    with open(archive_paths["metadata.json"]) as fh:
        metadata = json.load(fh)
    with open(archive_paths["monitor_events.jsonl"]) as fh:
        events = [json.loads(line) for line in fh if line.strip()]
    with open(archive_paths["trades.jsonl"]) as fh:
        trades = [json.loads(line) for line in fh if line.strip()]

    warning_pattern = re.compile(
        r"Fill data unavailable — inferred (target_hit|stop_hit) "
        r"@ ([0-9]+(?:\.[0-9]+)?) \| ret=([+-][0-9.]+)% "
        r"\(inferred from TP/SL prices, not actual fill\)"
    )
    warnings = []
    for event in events:
        match = warning_pattern.fullmatch(str(event.get("message", "")))
        if match:
            warnings.append(
                dict(
                    event_id=int(event["id"]),
                    event_time=str(event["event_time"]),
                    exit_type=match.group(1),
                    exit_price=float(match.group(2)),
                    return_pct=float(match.group(3)) / 100.0,
                )
            )

    joined_warning_rows = []
    for warning in warnings:
        candidates = []
        warning_time = pd.to_datetime(warning["event_time"], utc=True)
        for index, trade in enumerate(trades):
            delta_seconds = abs(
                (
                    pd.to_datetime(trade["exit_time"], utc=True)
                    - warning_time
                ).total_seconds()
            )
            if (
                trade["exit_type"] == warning["exit_type"]
                and abs(
                    float(trade["exit_price"])
                    - float(warning["exit_price"])
                ) <= 0.005
                and delta_seconds <= 120
            ):
                candidates.append((delta_seconds, index, trade))
        if len(candidates) != 1:
            raise AssertionError(
                "inference warning did not join uniquely to a trade"
            )
        delta_seconds, index, trade = candidates[0]
        joined_warning_rows.append(
            dict(
                warning_event_id=warning["event_id"],
                warning_time=warning["event_time"],
                trade_row_number=index + 1,
                entry_time=trade["entry_time"],
                exit_time=trade["exit_time"],
                exit_type=trade["exit_type"],
                exit_price=float(trade["exit_price"]),
                return_pct=float(trade["return_pct"]),
                bars_held=int(trade["bars_held"]),
                join_delta_seconds=round(delta_seconds, 6),
            )
        )

    unique_rows: Dict[int, Dict[str, object]] = {}
    for row in joined_warning_rows:
        unique_rows.setdefault(int(row["trade_row_number"]), row)
    inferred_trades = [unique_rows[key] for key in sorted(unique_rows)]
    inferred_row_numbers = set(unique_rows)
    target_rows = [
        (index + 1, row)
        for index, row in enumerate(trades)
        if row["exit_type"] == "target_hit"
    ]
    unmatched_target_rows = [
        dict(trade_row_number=index, **row)
        for index, row in target_rows
        if index not in inferred_row_numbers
    ]

    same_cycle_entries = [
        event
        for event in events
        if event.get("category") == "entry"
        and "back-to-back after exit_target_hit_inferred"
        in str(event.get("message", ""))
    ]
    inferred_factor = math.prod(
        1.0 + float(row["return_pct"]) for row in inferred_trades
    )
    all_factor = math.prod(
        1.0 + float(row["return_pct"]) for row in trades
    )
    without_inferred_factor = all_factor / inferred_factor
    inferred_compounded_pct = (inferred_factor - 1.0) * 100.0
    all_compounded_pct = (all_factor - 1.0) * 100.0
    without_inferred_pct = (without_inferred_factor - 1.0) * 100.0
    all_exit_counts = {
        exit_type: sum(
            row["exit_type"] == exit_type for row in trades
        )
        for exit_type in sorted({row["exit_type"] for row in trades})
    }
    project_exit_confirmed = [
        row
        for row in trades
        if row["exit_type"] in {"bracket_exit", "stop_hit"}
    ]
    if len(warnings) != 6 or len(inferred_trades) != 5:
        raise AssertionError("sanitized inference count changed")
    if len(target_rows) != 6 or len(unmatched_target_rows) != 1:
        raise AssertionError("target-hit archive partition changed")
    if len(same_cycle_entries) != 3:
        raise AssertionError("same-cycle inferred re-entry count changed")
    if any(row["exit_type"] != "target_hit" for row in inferred_trades):
        raise AssertionError("archive contains a non-target inferred closure")

    return dict(
        scope=(
            "Read-only control-flow and sanitized-archive audit. It constructs "
            "the unfilled/rejected-parent state as a reachability case; it does "
            "not claim the historical rows were unfilled parents."
        ),
        current_source_sha256=source_hashes,
        archive_sha256=archive_hashes,
        archive_identity=dict(
            archive_id=metadata["archive_id"],
            source_database_sha256=metadata["source_database_sha256"],
            git_commit=metadata["git_commit"],
            row_counts=metadata["row_counts"],
        ),
        source_contract_tokens=token_audit,
        current_control_flow=dict(
            entry_success_can_precede_parent_acknowledgement=True,
            locally_open_position_can_coexist_with_broker_flat=True,
            broker_flat_observation_source="IB positions only",
            active_or_working_parent_checked=False,
            parent_reject_status_checked=False,
            parent_execution_checked=False,
            missing_bracket_fill_falls_through_to_inference=True,
            inference_terminal_return_count=terminal_return_count,
            inference_unknown_or_unverified_outcomes=unknown_outcomes,
            local_position_closed_after_inference=True,
            same_cycle_entry_evaluation_after_inference=True,
        ),
        constructive_reachability=[
            "The three application placeOrder calls return without a durable acknowledgement or execution.",
            "The quote-derived local position is committed and ENTRY placed is emitted.",
            "The parent remains unfilled, is held, or is rejected; the account position is therefore flat.",
            "On the next cycle get_open_position observes no TQQQ shares.",
            "get_bracket_fill returns no child execution.",
            "_infer_bracket_exit nevertheless selects TP or SL and state.close_position records a return.",
            "The cycle can then evaluate and submit another entry.",
        ],
        alternative_explanations_for_same_observation=[
            (
                "The parent really filled and a child really exited, but the "
                "execution was no longer returned after reconnect."
            ),
            (
                "The position was closed manually or by another order while "
                "the stored bracket execution was unavailable."
            ),
            (
                "The parent never filled, was rejected, remained working, or "
                "was cancelled; no economic trade occurred."
            ),
        ],
        archive_inference_join=dict(
            inference_warning_events=len(warnings),
            unique_local_trade_rows=len(inferred_trades),
            duplicate_warning_events=len(warnings) - len(inferred_trades),
            all_inferred_exit_types=sorted(
                {row["exit_type"] for row in inferred_trades}
            ),
            inferred_rows=inferred_trades,
            target_hit_rows=len(target_rows),
            target_hit_rows_explicitly_inferred=len(inferred_trades),
            target_hit_rows_not_joined_to_warning=len(
                unmatched_target_rows
            ),
            unmatched_target_rows=unmatched_target_rows,
            explicit_same_cycle_reentries_after_inference=len(
                same_cycle_entries
            ),
            same_cycle_reentry_event_ids=[
                int(event["id"]) for event in same_cycle_entries
            ],
        ),
        accounting_materiality=dict(
            all_archive_rows=len(trades),
            all_archive_exit_type_counts=all_exit_counts,
            inferred_rows_compounded_return_pct=round(
                inferred_compounded_pct, 6
            ),
            all_archive_compounded_return_pct=round(
                all_compounded_pct, 6
            ),
            all_archive_compounded_return_without_inferred_rows_pct=round(
                without_inferred_pct, 6
            ),
            endpoint_return_difference_pp=round(
                all_compounded_pct - without_inferred_pct, 6
            ),
            interpretation=(
                "Removing the five factors is a ledger attribution only. It "
                "does not reconstruct the counterfactual path because later "
                "entries and sizing may depend on each closure."
            ),
        ),
        prior_result_robustness=dict(
            project_exit_confirmed_definition=(
                "bracket_exit plus stop_hit"
            ),
            project_exit_confirmed_rows=len(project_exit_confirmed),
            explicitly_inferred_rows_inside_that_bucket=0,
            consequence=(
                "Study 52's 47-row +0.204664% quote-basis sensitivity is "
                "numerically unchanged by these five target_hit rows."
            ),
        ),
        external_primary_sources={
            "current_ibkr_tws_api_documentation": (
                "https://ibkrcampus.com/campus/ibkr-api-page/twsapi-doc/"
            ),
            "ibkr_positions": (
                "https://interactivebrokers.github.io/tws-api/positions.html"
            ),
            "ibkr_open_orders": (
                "https://interactivebrokers.github.io/tws-api/open_orders.html"
            ),
            "ibkr_executions": (
                "https://interactivebrokers.github.io/tws-api/"
                "executions_commissions.html"
            ),
        },
        falsification_gate=[
            (
                "Persist parent permId, accepted/rejected status, executions, "
                "and child IDs before treating a local entry as economic."
            ),
            (
                "When positions are flat, reconcile active orders and complete "
                "executions by permanent identifiers before inferring an exit."
            ),
            (
                "Use an explicit unverified state when neither an entry nor "
                "exit execution can be proved; do not force TP/SL classification."
            ),
            (
                "Replay crash/reject/held/unfilled/partial-fill cases in an "
                "isolated paper harness before any protected-path change."
            ),
        ],
        decision=(
            "A phantom round trip is reachable in current code: a locally "
            "recorded but economically unfilled parent can later be converted "
            "into a TP/SL trade solely because positions are flat and no child "
            "fill is found. The archive proves five unique inferred target-hit "
            "rows and three immediate re-entry events, not that those parents "
            "were unfilled. Classify all five as execution-unverified. They "
            "compound to +5.120432% as a standalone ledger slice and account "
            "for a 6.595908 pp endpoint difference when their factors are removed, "
            "but Study 52's 47-row exit-confirmed flat result excludes them and "
            "is unchanged."
        ),
    )


def bracket_fill_identity_and_retention_audit() -> Dict[str, object]:
    """Audit whether recovered bracket fills have durable identity and VWAP."""
    source_paths = [
        "live/broker.py",
        "live/state.py",
        "tests/test_broker.py",
    ]
    source_text: Dict[str, str] = {}
    source_hashes: Dict[str, str] = {}
    for relative in source_paths:
        path = os.path.join(REPO, relative)
        with open(path, "rb") as fh:
            raw = fh.read()
        source_hashes[relative] = hashlib.sha256(raw).hexdigest()
        source_text[relative] = raw.decode("utf-8")

    fill_match = re.search(
        r"^def get_bracket_fill\b.*?(?=^def\s)",
        source_text["live/broker.py"],
        flags=re.MULTILINE | re.DOTALL,
    )
    if fill_match is None:
        raise AssertionError("could not isolate get_bracket_fill")
    fill_source = fill_match.group(0)
    required_tokens = [
        "last_fill = trade.fills[-1]",
        "exec_.orderId in (parent_id + 1, parent_id + 2)",
        "if is_child and exec_.side == exit_side and exec_.shares > 0:",
        "exec_filter = ExecutionFilter(time=since)",
        "hist_fills = ib.reqExecutions(exec_filter)",
        '"fill_price": float(fill_price)',
    ]
    if not all(token in fill_source for token in required_tokens):
        raise AssertionError("fill-recovery source contract changed")

    identity_fields = [
        "contract.symbol",
        "contract.conId",
        "execution.permId",
        "execution.execId",
        "execution.acctNumber",
        "execution.clientId",
        "execution.cumQty",
        "execution.avgPrice",
    ]
    identity_presence = {
        field: field in fill_source for field in identity_fields
    }
    returned_fields = sorted(
        set(
            re.findall(
                r'[\"\\\']([a-z_]+)[\"\\\']\s*:',
                fill_source,
            )
        )
    )

    phantom = unfilled_parent_phantom_trade_audit()
    inferred_rows = phantom["archive_inference_join"]["inferred_rows"]
    cross_utc_date = [
        row
        for row in inferred_rows
        if pd.to_datetime(row["entry_time"], utc=True).date()
        < pd.to_datetime(row["warning_time"], utc=True).date()
    ]

    synthetic_fills = [(60.0, 100.0), (40.0, 101.0)]
    total_shares = sum(shares for shares, _ in synthetic_fills)
    vwap = sum(
        shares * price for shares, price in synthetic_fills
    ) / total_shares
    last_price = synthetic_fills[-1][1]
    first_price = synthetic_fills[0][1]

    return dict(
        scope=(
            "Read-only source, test, and archive-timing audit. No broker "
            "connection is made; the partial-fill example is synthetic."
        ),
        current_source_sha256=source_hashes,
        current_recovery_tiers=[
            dict(
                tier="ib.trades current-session objects",
                match="child order.parentId equals stored API parent ID",
                selected_execution="last fill on first matching child Trade",
                symbol_checked=False,
                permanent_id_checked=False,
                execution_id_persisted=False,
                volume_weighted_price=False,
            ),
            dict(
                tier="ib.fills synchronized cache",
                match=(
                    "known child API order ID or parent+1/+2, exit side, "
                    "positive shares"
                ),
                selected_execution="first matching Fill",
                symbol_checked=False,
                permanent_id_checked=False,
                execution_id_persisted=False,
                volume_weighted_price=False,
            ),
            dict(
                tier="reqExecutions fallback",
                match="parent+1/+2 API order ID, exit side, positive shares",
                selected_execution="first matching historical Fill",
                symbol_checked=False,
                permanent_id_checked=False,
                execution_id_persisted=False,
                volume_weighted_price=False,
            ),
        ],
        source_identity_field_presence=identity_presence,
        returned_fields=returned_fields,
        durable_state_fields=dict(
            stores_parent_api_order_id=True,
            stores_parent_perm_id=False,
            stores_child_api_or_perm_ids=False,
            stores_exit_execution_id=False,
            stores_exit_shares_or_cumulative_qty=False,
            stores_exit_vwap=False,
        ),
        retention_contract=dict(
            code_claim="historical fills up to 7 days",
            requested_filter_days=7,
            ib_gateway_default_and_limit=(
                "executions since midnight; unlike TWS, Gateway cannot change "
                "the Trade Log setting to extend retrieval"
            ),
            consequence=(
                "The seven-day timestamp does not make prior-day executions "
                "available from IB Gateway. Cross-midnight reconciliation can "
                "still return no execution by design."
            ),
        ),
        archive_timing=dict(
            inferred_unique_rows=len(inferred_rows),
            entry_on_prior_utc_date=len(cross_utc_date),
            entry_same_utc_date=len(inferred_rows) - len(cross_utc_date),
            prior_date_trade_row_numbers=[
                int(row["trade_row_number"]) for row in cross_utc_date
            ],
            interpretation=(
                "Four of five execution-unverified inferred closures begin on "
                "a prior UTC date. This is consistent with the Gateway "
                "retention limitation, but does not prove when or whether an "
                "entry/exit execution occurred."
            ),
        ),
        synthetic_partial_fill_price_case=dict(
            fills=[
                dict(shares=shares, price=price)
                for shares, price in synthetic_fills
            ],
            correct_vwap=vwap,
            tier1_last_fill_price=last_price,
            tier1_error_bps=round(
                (last_price / vwap - 1.0) * 10000, 6
            ),
            tier2_or_3_first_fill_price=first_price,
            tier2_or_3_error_bps=round(
                (first_price / vwap - 1.0) * 10000, 6
            ),
            caveat=(
                "Illustrative arithmetic only; it proves the selection rule "
                "is not a VWAP aggregator, not the size of historical error."
            ),
        ),
        current_test_boundary=dict(
            single_fill_tier1_cases=2,
            single_fill_tier2_cases=2,
            single_fill_tier3_cases=1,
            multiple_partial_fill_vwap_case=False,
            wrong_symbol_same_order_id_case=False,
            permanent_id_mismatch_case=False,
            execution_id_deduplication_case=False,
            gateway_prior_day_retention_case=False,
        ),
        external_primary_sources={
            "current_ibkr_order_and_execution_docs": (
                "https://ibkrcampus.com/campus/ibkr-api-page/twsapi-doc/"
            ),
            "ibkr_execution_retention": (
                "https://interactivebrokers.github.io/tws-api/"
                "executions_commissions.html"
            ),
        },
        falsification_gate=[
            (
                "Persist parent/child permIds and entry/exit execIds, contract "
                "identity, shares, cumulative quantity, and broker average price."
            ),
            (
                "Aggregate partial executions by permanent order identity and "
                "execution ID; reconcile quantity to the economic position."
            ),
            (
                "Treat Gateway prior-day execution recovery as unavailable "
                "unless an independently durable local execution ledger exists."
            ),
            (
                "Test wrong-symbol/order-number collisions, multiple partials, "
                "duplicates, reconnects, and midnight/weekend boundaries."
            ),
        ],
        decision=(
            "The current recovered exit price is not durably attributable or "
            "partial-fill-safe. All three tiers ultimately rely on client API "
            "order IDs (two use parent+1/+2 arithmetic), omit symbol/permId/"
            "execId/quantity reconciliation, and return one execution price "
            "instead of VWAP. The advertised seven-day reqExecutions fallback "
            "does not hold for IB Gateway, which is limited to executions "
            "since midnight. Four of five archived inference rows cross a UTC "
            "date boundary, consistent with this deterministic retention gap "
            "but not proof of a real fill. Therefore even 'retrieved fill' "
            "means project-matched execution, not a durable end-to-end ledger."
        ),
    )


def concurrent_close_idempotency_audit() -> Dict[str, object]:
    """Prove whether two stale readers can record the same local close twice."""
    source_paths = [
        "live/state.py",
        "live/trader.py",
        "tests/test_state.py",
        "tests/test_trader_flow.py",
    ]
    source_text: Dict[str, str] = {}
    source_hashes: Dict[str, str] = {}
    for relative in source_paths:
        path = os.path.join(REPO, relative)
        with open(path, "rb") as fh:
            raw = fh.read()
        source_hashes[relative] = hashlib.sha256(raw).hexdigest()
        source_text[relative] = raw.decode("utf-8")

    required_tokens = {
        "live/state.py": [
            "def _conn() -> sqlite3.Connection:",
            "conn = sqlite3.connect(_DB_PATH)",
            "def close_position(",
            'pos = conn.execute("SELECT * FROM position LIMIT 1").fetchone()',
            "INSERT INTO trades (",
            'conn.execute("DELETE FROM position")',
            "def finalize_pending_close(",
        ],
        "live/trader.py": [
            "state.close_position(return_pct=ret, exit_type=exit_type,",
            'exit_action = f"exit_{exit_type}_inferred"',
            "# Fall through to entry check",
        ],
    }
    token_audit = {
        path: {token: token in source_text[path] for token in tokens}
        for path, tokens in required_tokens.items()
    }
    if not all(
        present
        for checks in token_audit.values()
        for present in checks.values()
    ):
        raise AssertionError("close-position source contract changed")

    fd, db_path = tempfile.mkstemp(
        prefix="monad-close-race-", suffix=".sqlite"
    )
    os.close(fd)
    try:
        setup = sqlite3.connect(db_path)
        setup.executescript(
            """
            CREATE TABLE position (
                entry_time TEXT, symbol TEXT, qty INTEGER, bar_count INTEGER,
                bracket_order_id TEXT
            );
            CREATE TABLE trades (
                entry_time TEXT, exit_time TEXT, return_pct REAL,
                exit_type TEXT, exit_price REAL, symbol TEXT,
                qty INTEGER, bars_held INTEGER, writer TEXT
            );
            INSERT INTO position VALUES (
                '2026-05-05T18:32:30+00:00', 'TQQQ', 152, 2, '100'
            );
            """
        )
        setup.commit()
        setup.close()

        conn_a = sqlite3.connect(db_path)
        conn_b = sqlite3.connect(db_path)
        stale_a = conn_a.execute(
            "SELECT * FROM position LIMIT 1"
        ).fetchone()
        a_in_transaction_after_select = conn_a.in_transaction
        stale_b = conn_b.execute(
            "SELECT * FROM position LIMIT 1"
        ).fetchone()
        b_in_transaction_after_select = conn_b.in_transaction

        def close_cached(
            conn: sqlite3.Connection,
            pos: Tuple[object, ...],
            writer: str,
        ) -> None:
            conn.execute(
                """
                INSERT INTO trades VALUES (
                    ?, '2026-05-06T13:32:13+00:00', 0.010044313146233273,
                    'target_hit', 68.38, ?, ?, ?, ?
                )
                """,
                (pos[0], pos[1], pos[2], pos[3], writer),
            )
            conn.execute("DELETE FROM position")
            conn.commit()

        close_cached(conn_a, stale_a, "A")
        close_cached(conn_b, stale_b, "B")
        conn_a.close()
        conn_b.close()

        check = sqlite3.connect(db_path)
        trade_rows = check.execute(
            "SELECT writer FROM trades ORDER BY rowid"
        ).fetchall()
        remaining_positions = check.execute(
            "SELECT COUNT(*) FROM position"
        ).fetchone()[0]
        check.close()
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)

    phantom = unfilled_parent_phantom_trade_audit()
    inferred = phantom["archive_inference_join"]
    materiality = phantom["accounting_materiality"]
    may6 = next(
        row
        for row in inferred["inferred_rows"]
        if int(row["trade_row_number"]) == 45
    )
    original_factor = 1.0 + materiality[
        "all_archive_compounded_return_pct"
    ] / 100.0
    duplicate_endpoint_pct = (
        original_factor * (1.0 + float(may6["return_pct"])) - 1.0
    ) * 100.0

    trades_schema = re.search(
        r"CREATE TABLE IF NOT EXISTS trades\s*\((.*?)\);",
        source_text["live/state.py"],
        flags=re.DOTALL,
    )
    if trades_schema is None:
        raise AssertionError("could not isolate trades schema")
    schema_text = trades_schema.group(1)

    return dict(
        scope=(
            "Read-only source/archive audit plus a deterministic temporary "
            "SQLite interleaving that mirrors the current SELECT-then-DML "
            "shape. It does not import live.state or touch state.db."
        ),
        current_source_sha256=source_hashes,
        source_contract_tokens=token_audit,
        transaction_contract=dict(
            sqlite_connect_arguments="database path only",
            python_driver_mode=(
                "legacy transaction control with default deferred DML"
            ),
            connection_context_manager_opens_transaction=False,
            select_implicitly_opened_driver_transaction=False,
            first_transactional_statement="INSERT INTO trades",
            select_and_insert_share_one_explicit_transaction=False,
            begin_immediate_present=_derived_control(
                source_text["live/state.py"],
                ("BEGIN IMMEDIATE", "begin immediate", "isolation_level='IMMEDIATE'")),
            compare_and_swap_delete_present=False,
            close_returns_success_status=False,
            trades_unique_lifecycle_constraint=bool(
                re.search(r"\bUNIQUE\b", schema_text, flags=re.IGNORECASE)
            ),
        ),
        deterministic_two_reader_interleaving=dict(
            schedule=[
                "A SELECTs the position and caches the row",
                "B SELECTs the same position and caches the row",
                "A INSERTs its trade, DELETEs position, and commits",
                "B INSERTs from its stale row, DELETEs zero rows, and commits",
            ],
            connection_a_in_transaction_after_select=(
                a_in_transaction_after_select
            ),
            connection_b_in_transaction_after_select=(
                b_in_transaction_after_select
            ),
            recorded_trade_rows=len(trade_rows),
            recorded_writers=[row[0] for row in trade_rows],
            remaining_position_rows=int(remaining_positions),
            duplicate_close_reachable=len(trade_rows) == 2,
        ),
        caller_side_effect_contract=dict(
            no_position_and_success_both_return_none=True,
            caller_checks_close_result=False,
            caller_after_close_actions=[
                "sync account/mark",
                "log summary",
                "send exit alert",
                "set exit_action",
                "evaluate same-cycle entry",
            ],
            consequence=(
                "Even a losing close caller cannot distinguish no-op from "
                "success and can continue with duplicate alerts/re-entry logic."
            ),
        ),
        archive_natural_experiment=dict(
            inference_warning_events=inferred["inference_warning_events"],
            unique_inferred_trade_rows=inferred["unique_local_trade_rows"],
            duplicate_warning_events=inferred["duplicate_warning_events"],
            may6_warning_events=2,
            may6_local_trade_rows=1,
            observed_interpretation=(
                "Two archived writers reached the May 6 inference warning, "
                "but only one local trade row exists. That observed schedule "
                "collapsed locally; it does not prove the schema is idempotent."
            ),
        ),
        duplicate_factor_sensitivity=dict(
            may6_recorded_return_pct=round(
                float(may6["return_pct"]) * 100.0, 6
            ),
            original_all_archive_compounded_return_pct=round(
                materiality["all_archive_compounded_return_pct"], 6
            ),
            with_one_duplicate_may6_factor_pct=round(
                duplicate_endpoint_pct, 6
            ),
            endpoint_increase_pp=round(
                duplicate_endpoint_pct
                - materiality["all_archive_compounded_return_pct"],
                6,
            ),
            caveat=(
                "Ledger-factor sensitivity only; a real duplicate cycle could "
                "also change broker exposure and later path."
            ),
        ),
        current_test_boundary=dict(
            sequential_close_success=True,
            sequential_no_position_noop=True,
            two_connection_stale_reader_close=False,
            close_result_gates_caller_side_effects=False,
            unique_lifecycle_constraint=False,
        ),
        external_primary_sources={
            "python_sqlite_transaction_control": (
                "https://docs.python.org/3/library/sqlite3.html"
            ),
            "sqlite_transactions": (
                "https://www.sqlite.org/lang_transaction.html"
            ),
            "sqlite_isolation": "https://www.sqlite.org/isolation.html",
        },
        falsification_gate=[
            (
                "Give every economic lifecycle a unique durable intent/order "
                "key and enforce it in the closed-trade schema."
            ),
            (
                "Acquire write ownership before reading (for example an "
                "explicit immediate transaction) or atomically claim the row "
                "with a conditional DELETE/UPDATE and inspect affected rows."
            ),
            (
                "Return a typed close outcome; only the winning caller may "
                "emit alerts, mark an exit action, or evaluate re-entry."
            ),
            (
                "Test two connections at staged SELECT/INSERT/DELETE cutpoints "
                "for open, inferred close, pending close, and time exit."
            ),
        ],
        decision=(
            "SQLite serializes each write transaction but does not make the "
            "current SELECT-then-INSERT lifecycle claim idempotent. Under "
            "Python's current legacy transaction mode, the context manager "
            "does not open a transaction and SELECT is outside the implicit "
            "DML transaction. Two connections can cache the same position, "
            "then sequentially commit two trade rows; the schema has no unique "
            "lifecycle key. Separately, close_position returns None for both "
            "success and no-position, so a losing caller still performs exit "
            "side effects and can re-enter. The May 6 archive happened to "
            "record one row after two warnings; that is an observed collapse, "
            "not a concurrency guarantee."
        ),
    )


def cross_generation_close_reentry_audit() -> Dict[str, object]:
    """Prove whether an old cycle can close and delete a newer position row."""
    source_paths = [
        "live/state.py",
        "live/trader.py",
        "tests/test_state.py",
        "tests/test_trader_flow.py",
    ]
    source_text: Dict[str, str] = {}
    source_hashes: Dict[str, str] = {}
    for relative in source_paths:
        path = os.path.join(REPO, relative)
        with open(path, "rb") as fh:
            raw = fh.read()
        source_hashes[relative] = hashlib.sha256(raw).hexdigest()
        source_text[relative] = raw.decode("utf-8")

    required_tokens = {
        "live/state.py": [
            "def close_position(return_pct: float, exit_type: str,",
            'pos = conn.execute("SELECT * FROM position LIMIT 1").fetchone()',
            'conn.execute("DELETE FROM position")',
            "def open_position(symbol: str, entry_price: float, qty: int,",
            'conn.execute("DELETE FROM position")',
            '"INSERT INTO position',
            "_emit_exit_event(pos, exit_type, exit_price, return_pct)",
        ],
        "live/trader.py": [
            "position = state.get_position()",
            "broker.get_bracket_fill(position.bracket_order_id",
            "state.close_position(return_pct=ret, exit_type=exit_type,",
            "state.open_position(",
            "alerts.alert_exit(",
        ],
    }
    token_audit = {
        path: {token: token in source_text[path] for token in tokens}
        for path, tokens in required_tokens.items()
    }
    if not all(
        present
        for checks in token_audit.values()
        for present in checks.values()
    ):
        raise AssertionError("cross-generation source contract changed")

    position_schema = re.search(
        r"CREATE TABLE IF NOT EXISTS position\s*\((.*?)\);",
        source_text["live/state.py"],
        flags=re.DOTALL,
    )
    trades_schema = re.search(
        r"CREATE TABLE IF NOT EXISTS trades\s*\((.*?)\);",
        source_text["live/state.py"],
        flags=re.DOTALL,
    )
    if position_schema is None or trades_schema is None:
        raise AssertionError("could not isolate position/trades schemas")
    position_schema_text = position_schema.group(1)
    trades_schema_text = trades_schema.group(1)

    fd, db_path = tempfile.mkstemp(
        prefix="monad-cross-generation-", suffix=".sqlite"
    )
    os.close(fd)
    try:
        setup = sqlite3.connect(db_path)
        setup.row_factory = sqlite3.Row
        setup.executescript(
            """
            CREATE TABLE position (
                symbol TEXT, entry_time TEXT, entry_price REAL, qty INTEGER,
                bracket_order_id TEXT, bar_count INTEGER, status TEXT,
                direction TEXT
            );
            CREATE TABLE trades (
                entry_time TEXT, exit_time TEXT, return_pct REAL,
                exit_type TEXT, exit_price REAL, symbol TEXT, qty INTEGER,
                bars_held INTEGER, selected_bracket_id TEXT,
                expected_bracket_id TEXT, writer TEXT
            );
            INSERT INTO position VALUES (
                'TQQQ', '2026-07-24T13:32:00+00:00', 100.0, 100,
                '100', 1, 'open', 'long'
            );
            """
        )
        setup.commit()
        stale_cycle = dict(
            setup.execute(
                "SELECT * FROM position LIMIT 1"
            ).fetchone()
        )
        setup.close()

        def implementation_shaped_close(
            writer: str,
            expected_bracket_id: str,
            return_pct: float,
            exit_price: float,
        ) -> Dict[str, object]:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            selected = conn.execute(
                "SELECT * FROM position LIMIT 1"
            ).fetchone()
            if selected is None:
                conn.close()
                return {"selected": None, "deleted_rows": 0}
            conn.execute(
                """
                INSERT INTO trades VALUES (
                    ?, '2026-07-24T14:32:10+00:00', ?, 'target_hit',
                    ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    selected["entry_time"],
                    return_pct,
                    exit_price,
                    selected["symbol"],
                    selected["qty"],
                    selected["bar_count"],
                    selected["bracket_order_id"],
                    expected_bracket_id,
                    writer,
                ),
            )
            delete_cursor = conn.execute("DELETE FROM position")
            deleted_rows = delete_cursor.rowcount
            conn.commit()
            result = {
                "selected": dict(selected),
                "deleted_rows": int(deleted_rows),
            }
            conn.close()
            return result

        first_close = implementation_shaped_close(
            writer="cycle_A_old_close",
            expected_bracket_id=stale_cycle["bracket_order_id"],
            return_pct=0.01,
            exit_price=101.0,
        )

        reentry = sqlite3.connect(db_path)
        reentry.execute("DELETE FROM position")
        reentry.execute(
            """
            INSERT INTO position VALUES (
                'TQQQ', '2026-07-24T14:32:05+00:00', 200.0, 50,
                '200', 0, 'open', 'long'
            )
            """
        )
        reentry.commit()
        reentry.close()

        stale_exit_return = (
            101.0 / float(stale_cycle["entry_price"]) - 1.0
        )
        second_close = implementation_shaped_close(
            writer="cycle_B_stale_old_evidence",
            expected_bracket_id=stale_cycle["bracket_order_id"],
            return_pct=stale_exit_return,
            exit_price=101.0,
        )

        check = sqlite3.connect(db_path)
        check.row_factory = sqlite3.Row
        trade_rows = [
            dict(row)
            for row in check.execute(
                "SELECT * FROM trades ORDER BY rowid"
            ).fetchall()
        ]
        remaining_positions = int(
            check.execute(
                "SELECT COUNT(*) FROM position"
            ).fetchone()[0]
        )
        check.close()
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)

    crossed = trade_rows[-1]
    selected_entry_price = float(
        second_close["selected"]["entry_price"]
    )
    implied_selected_generation_return = (
        float(crossed["exit_price"]) / selected_entry_price - 1.0
    )
    return_discrepancy_pp = (
        float(crossed["return_pct"])
        - implied_selected_generation_return
    ) * 100.0

    archive_dir = os.path.join(
        REPO,
        "data",
        "live_runs",
        "archive_2026-06-18_pre_clean_run",
    )

    def load_jsonl(name: str) -> List[Dict[str, object]]:
        rows = []
        with open(os.path.join(archive_dir, name)) as fh:
            for line in fh:
                if line.strip():
                    rows.append(json.loads(line))
        return rows

    archive_events = load_jsonl("monitor_events.jsonl")
    archive_trades = load_jsonl("trades.jsonl")
    entry_events = [
        row for row in archive_events
        if row.get("category") == "entry"
    ]
    duplicate_forensics = historical_duplicate_writer_forensics()
    double_rows = duplicate_forensics["entry_path"]["double_entry_rows"]
    double_success_events = 2 * len(double_rows)
    events_with_parent_identity = sum(
        bool(
            re.search(
                r"\b(?:order|parent|bracket)[ _-]?id\s*[=:]\s*\d+",
                str(row.get("message", "")),
                flags=re.IGNORECASE,
            )
        )
        for row in entry_events
        if any(
            str(row.get("event_time")) == str(event["event_time"])
            for pair in double_rows
            for event in (pair["first"], pair["second"])
        )
    )
    trade_fields = sorted(
        {key for row in archive_trades for key in row}
    )
    position_fields = sorted(
        token.split()[0]
        for token in position_schema_text.split(",")
        if token.strip()
    )
    trades_fields = sorted(
        token.split()[0]
        for token in trades_schema_text.split(",")
        if token.strip()
    )
    mismatched_qty_pairs = sum(
        row["first"]["qty"] != row["second"]["qty"]
        for row in double_rows
    )

    close_signature = re.search(
        r"def close_position\((.*?)\)\s*->",
        source_text["live/state.py"],
        flags=re.DOTALL,
    )
    if close_signature is None:
        raise AssertionError("could not isolate close_position signature")
    close_parameters = close_signature.group(1)

    return dict(
        scope=(
            "Read-only source/archive audit plus a deterministic temporary "
            "SQLite cut-point experiment. It does not import live.state, "
            "touch state.db, start a trader, or contact IBKR."
        ),
        current_source_sha256=source_hashes,
        source_contract_tokens=token_audit,
        generation_identity_contract=dict(
            position_fields=position_fields,
            trades_fields=trades_fields,
            position_primary_key=bool(
                re.search(
                    r"\bPRIMARY\s+KEY\b",
                    position_schema_text,
                    flags=re.IGNORECASE,
                )
            ),
            position_unique_constraint=bool(
                re.search(
                    r"\bUNIQUE\b",
                    position_schema_text,
                    flags=re.IGNORECASE,
                )
            ),
            bracket_order_id_present_only_while_position_open=(
                "bracket_order_id" in position_fields
                and "bracket_order_id" not in trades_fields
            ),
            close_accepts_expected_bracket_or_lifecycle_id=(
                "bracket_order_id" in close_parameters
                or "lifecycle" in close_parameters
                or "position_id" in close_parameters
            ),
            close_delete_is_generation_conditional=_derived_control(
                source_text["live/state.py"],
                ("DELETE FROM position WHERE generation",
                 "WHERE generation = ?", "AND generation = ?")),
            close_checks_delete_rowcount=_derived_control(
                source_text["live/state.py"],
                (".rowcount", "rowcount ==", "rowcount !=")),
            trade_retains_bracket_or_lifecycle_id=(
                "bracket_order_id" in trades_fields
                or any("lifecycle" in field for field in trades_fields)
                or "position_id" in trades_fields
            ),
        ),
        deterministic_cross_generation_interleaving=dict(
            schedule=[
                "Cycle B caches generation 100 and resolves its old exit evidence",
                "Cycle A closes generation 100",
                "Cycle A submits/re-enters and persists generation 200",
                (
                    "Cycle B calls close_position with generation-100 return/"
                    "price, but close_position independently SELECTs generation 200"
                ),
                (
                    "Cycle B records generation-200 metadata with generation-100 "
                    "exit economics, then unconditionally deletes generation 200"
                ),
            ],
            stale_cycle_bracket_id=stale_cycle["bracket_order_id"],
            first_close_selected_bracket_id=(
                first_close["selected"]["bracket_order_id"]
            ),
            new_position_bracket_id=(
                second_close["selected"]["bracket_order_id"]
            ),
            stale_close_expected_bracket_id=(
                crossed["expected_bracket_id"]
            ),
            stale_close_selected_bracket_id=(
                crossed["selected_bracket_id"]
            ),
            generation_mismatch=(
                crossed["expected_bracket_id"]
                != crossed["selected_bracket_id"]
            ),
            stale_close_deleted_new_position_rows=(
                second_close["deleted_rows"]
            ),
            remaining_position_rows=remaining_positions,
            recorded_trade_rows=len(trade_rows),
            crossed_trade_record=dict(
                entry_time=crossed["entry_time"],
                qty=crossed["qty"],
                recorded_return_pct=round(
                    float(crossed["return_pct"]) * 100.0, 6
                ),
                exit_price=float(crossed["exit_price"]),
                return_implied_by_selected_generation_pct=round(
                    implied_selected_generation_return * 100.0, 6
                ),
                return_discrepancy_pp=round(
                    return_discrepancy_pp, 6
                ),
            ),
            reachability_proved=(
                crossed["expected_bracket_id"] == "100"
                and crossed["selected_bracket_id"] == "200"
                and second_close["deleted_rows"] == 1
                and remaining_positions == 0
            ),
        ),
        side_effect_split_brain=dict(
            state_exit_event_uses_freshly_selected_position=True,
            caller_exit_alert_uses_cycle_cached_position=True,
            shared_expected_generation_check=False,
            consequence=(
                "One application close can emit state/event metadata for the "
                "new generation while the caller alert describes the stale "
                "generation and both use stale exit economics."
            ),
        ),
        archive_observability=dict(
            historical_double_entry_minutes=len(double_rows),
            double_success_events=double_success_events,
            double_pairs_with_different_qty=mismatched_qty_pairs,
            double_success_events_with_parent_order_identity=(
                events_with_parent_identity
            ),
            trades_export_fields=trade_fields,
            trades_export_retains_bracket_order_id=(
                "bracket_order_id" in trade_fields
            ),
            interpretation=(
                "The archive proves overwrite-shaped duplicate entry events "
                "and later-state retention, but cannot test cross-generation "
                "closure because neither those entry events nor closed-trade "
                "rows preserve parent/lifecycle identity."
            ),
        ),
        broker_recovery_consequences=[
            (
                "If generation 200 filled, the next local-flat/broker-long "
                "check can block new entry as a desync, but local state no "
                "longer identifies the bracket to manage."
            ),
            (
                "If generation 200 remains working and unfilled, broker "
                "positions can still look flat and the current entry guard "
                "does not inspect working orders."
            ),
            (
                "SQLite rollback cannot undo the already-submitted external "
                "broker bracket."
            ),
        ],
        current_test_boundary=dict(
            sequential_open_close_paths=True,
            concurrent_double_close_now_proved_by_study55=True,
            staged_old_close_then_new_open_then_stale_close=False,
            generation_mismatch_noop_assertion=False,
            broker_identity_retained_after_close=False,
        ),
        external_primary_sources={
            "python_sqlite_transactions_and_rowcount": (
                "https://docs.python.org/3/library/sqlite3.html"
            ),
            "sqlite_transactions": (
                "https://www.sqlite.org/lang_transaction.html"
            ),
            "ibkr_order_status_identity": (
                "https://ibkrcampus.com/campus/ibkr-api-page/twsapi-doc/"
            ),
            "ibkr_execution_identity": (
                "https://ibkrcampus.com/campus/ibkr-api-page/twsapi-ref/"
            ),
        },
        falsification_gate=[
            (
                "Create a durable lifecycle/position ID before broker "
                "submission and persist it with client order ID, permId, and "
                "execution IDs through open, close, events, and exports."
            ),
            (
                "Require close/finalize calls to carry the expected lifecycle "
                "ID; atomically claim exactly that row and reject a mismatch."
            ),
            (
                "Insert the closed trade and DELETE ... WHERE lifecycle_id = ? "
                "in one write-owned transaction, enforce a unique closed "
                "lifecycle ID, and require affected-row count == 1."
            ),
            (
                "Gate alerts, account sync, exit_action, and re-entry on a "
                "typed winning-close result."
            ),
            (
                "Stage two cycles at old-close/new-open/stale-close cutpoints "
                "and prove the stale call neither records nor deletes the new "
                "generation."
            ),
        ],
        limitations=[
            (
                "The experiment proves source-level reachability, not that "
                "the archived or current deployment experienced this schedule."
            ),
            (
                "The 50.5 percentage-point return mismatch is deliberately "
                "large synthetic evidence of field mixing, not an estimate "
                "of historical PnL error."
            ),
            (
                "A filled new broker position is likely to trigger the next "
                "cycle's desync block; that contains further entries but does "
                "not reconstruct the deleted lifecycle."
            ),
        ],
        decision=(
            "The local lifecycle has no generation-safe close. A cycle resolves "
            "broker exit evidence against its cached Position, but close_position "
            "takes only economics, independently selects whichever row exists "
            "then, and DELETEs without an identity predicate. The deterministic "
            "cut-point therefore attaches generation-100 exit data to "
            "generation-200 metadata and deletes generation 200. The archive's "
            "seven overwrite-shaped entry pairs cannot confirm or refute this "
            "race because zero of their 14 success events and no trade row "
            "retain parent/lifecycle identity. Treat local-flat as potentially "
            "lossy state, not proof that the latest broker lifecycle ended."
        ),
    )


def quote_anchored_bracket_geometry_audit() -> Dict[str, object]:
    """Quantify fill-relative bracket and bar-close sizing deformation."""
    source_paths = [
        "config.py",
        "live/broker.py",
        "live/trader.py",
        "live/state.py",
        "tests/test_broker.py",
        "tests/test_trader_flow.py",
        "tests/test_state.py",
    ]
    source_text: Dict[str, str] = {}
    source_hashes: Dict[str, str] = {}
    for relative in source_paths:
        path = os.path.join(REPO, relative)
        with open(path, "rb") as fh:
            raw = fh.read()
        source_hashes[relative] = hashlib.sha256(raw).hexdigest()
        source_text[relative] = raw.decode("utf-8")

    required_tokens = {
        "live/broker.py": [
            "target_price = round(live_price * (1 + target_pct), 2)",
            "stop_price   = round(live_price * (1 - stop_pct), 2)",
            "limit_price  = round(live_price * 1.005, 2)",
            '"fill_basis": float(live_price)',
        ],
        "live/trader.py": [
            'bar_close = sig_info["bar_close"]',
            'qty = int(sizing["position_dollars"] / bar_close)',
            "result = broker.place_bracket_order(",
            'entry_price = result["fill_basis"]',
        ],
        "live/state.py": [
            "position_pct = 0.10",
            "position_dollars = capital * position_pct",
        ],
        "tests/test_broker.py": [
            'limitPrice=100.5',
            '"target_price": 101.0, "stop_price": 99.5',
        ],
    }
    token_audit = {
        path: {token: token in source_text[path] for token in tokens}
        for path, tokens in required_tokens.items()
    }
    if not all(
        present
        for checks in token_audit.values()
        for present in checks.values()
    ):
        raise AssertionError("quote-geometry source contract changed")

    mode = config.ASSETS["TQQQ_HOURLY"]
    target_pct = float(mode["target_gain_pct"])
    stop_pct = float(mode["stop_loss_pct"])
    parent_limit_offset = 0.005
    position_fraction = 0.10
    if (
        target_pct != 0.01
        or stop_pct != 0.005
        or config.LIVE_SYMBOL != "TQQQ"
    ):
        raise AssertionError("current TQQQ bracket config changed")

    analytic_long_target = (
        (1.0 + target_pct) / (1.0 + parent_limit_offset) - 1.0
    )
    analytic_long_stop = (
        (1.0 - stop_pct) / (1.0 + parent_limit_offset) - 1.0
    )
    analytic_short_target = (
        1.0 - (1.0 - target_pct) / (1.0 - parent_limit_offset)
    )
    analytic_short_stop = (
        (1.0 + stop_pct) / (1.0 - parent_limit_offset) - 1.0
    )

    archive_dir = os.path.join(
        REPO,
        "data",
        "live_runs",
        "archive_2026-06-18_pre_clean_run",
    )

    def load_jsonl(name: str) -> List[Dict[str, object]]:
        rows = []
        with open(os.path.join(archive_dir, name)) as fh:
            for line in fh:
                if line.strip():
                    rows.append(json.loads(line))
        return rows

    signals = load_jsonl("signal_history.jsonl")
    events = load_jsonl("monitor_events.jsonl")
    entry_events = [
        row for row in events if row.get("category") == "entry"
    ]

    def minute_slot(value: str) -> str:
        timestamp = pd.Timestamp(value)
        if timestamp.tzinfo is None:
            timestamp = timestamp.tz_localize("UTC")
        return timestamp.floor("min").isoformat()

    signal_slots: Dict[str, List[Dict[str, object]]] = {}
    for row in signals:
        signal_slots.setdefault(
            minute_slot(str(row["updated_at"])), []
        ).append(row)
    entry_slots: Dict[str, List[Dict[str, object]]] = {}
    for row in entry_events:
        entry_slots.setdefault(
            minute_slot(str(row["event_time"])), []
        ).append(row)

    parsed_entries = []
    for row in entry_events:
        match = re.search(
            r"(?:LONG |SHORT )?(\d+) TQQQ @ ([0-9.]+)",
            str(row["message"]),
        )
        if match is None:
            raise AssertionError(
                "Unparseable archived entry event: %r" % row["message"]
            )
        quote = float(match.group(2))
        limit_price = round(
            quote * (1.0 + parent_limit_offset), 2
        )
        target_price = round(quote * (1.0 + target_pct), 2)
        stop_price = round(quote * (1.0 - stop_pct), 2)
        fill_relative_target = target_price / limit_price - 1.0
        fill_relative_stop = stop_price / limit_price - 1.0
        parsed_entries.append(
            dict(
                event_time=str(row["event_time"]),
                qty=int(match.group(1)),
                quote=quote,
                parent_limit=limit_price,
                target_price=target_price,
                stop_price=stop_price,
                worst_permitted_fill_target_pct=(
                    fill_relative_target * 100.0
                ),
                worst_permitted_fill_stop_pct=(
                    fill_relative_stop * 100.0
                ),
                worst_permitted_fill_reward_risk=(
                    fill_relative_target / abs(fill_relative_stop)
                ),
            )
        )

    strict_pairs = []
    unresolved_slots = []
    parsed_by_time = {
        row["event_time"]: row for row in parsed_entries
    }
    for slot, slot_entries in sorted(entry_slots.items()):
        ordered_entries = sorted(
            slot_entries, key=lambda row: str(row["event_time"])
        )
        actionable_signals = sorted(
            [
                row for row in signal_slots.get(slot, [])
                if int(row["signal"]) == 1
            ],
            key=lambda row: str(row["updated_at"]),
        )
        if len(ordered_entries) != len(actionable_signals):
            unresolved_slots.append(
                dict(
                    slot_utc=slot,
                    entry_events=len(ordered_entries),
                    actionable_signal_rows=len(actionable_signals),
                    all_signal_rows=len(signal_slots.get(slot, [])),
                    reason=(
                        "without a cycle ID, unequal event/actionable-signal "
                        "counts do not support a one-to-one sizing-bar join"
                    ),
                )
            )
            continue
        for event, signal in zip(ordered_entries, actionable_signals):
            parsed = parsed_by_time[str(event["event_time"])]
            qty = int(parsed["qty"])
            quote = float(parsed["quote"])
            bar_close = float(signal["bar_close"])
            parent_limit = float(parsed["parent_limit"])
            # qty = floor(planned_dollars / bar_close), therefore:
            # qty*bar_close <= planned_dollars < (qty+1)*bar_close.
            quote_plan_lower = (
                qty * quote / ((qty + 1) * bar_close)
            )
            quote_plan_upper = quote / bar_close
            limit_plan_lower = (
                qty * parent_limit / ((qty + 1) * bar_close)
            )
            limit_plan_upper = parent_limit / bar_close
            strict_pairs.append(
                dict(
                    slot_utc=slot,
                    event_time=str(event["event_time"]),
                    signal_time=str(signal["updated_at"]),
                    signal_bar_time=str(signal["bar_time"]),
                    qty=qty,
                    quote=quote,
                    bar_close=bar_close,
                    parent_limit=parent_limit,
                    quote_to_bar_bps=(
                        (quote / bar_close - 1.0) * 10000.0
                    ),
                    parent_limit_to_bar_bps=(
                        (parent_limit / bar_close - 1.0) * 10000.0
                    ),
                    quote_allocation_fraction_of_plan_interval=[
                        quote_plan_lower,
                        quote_plan_upper,
                    ],
                    parent_limit_allocation_fraction_of_plan_interval=[
                        limit_plan_lower,
                        limit_plan_upper,
                    ],
                )
            )

    def summary(values: List[float], scale: float = 1.0) -> Dict[str, float]:
        array = np.asarray(values, dtype=float) * scale
        return dict(
            min=round(float(np.min(array)), 6),
            median=round(float(np.median(array)), 6),
            max=round(float(np.max(array)), 6),
        )

    target_values = [
        row["worst_permitted_fill_target_pct"]
        for row in parsed_entries
    ]
    stop_values = [
        row["worst_permitted_fill_stop_pct"]
        for row in parsed_entries
    ]
    reward_risk_values = [
        row["worst_permitted_fill_reward_risk"]
        for row in parsed_entries
    ]
    quote_to_bar_values = [
        row["quote_to_bar_bps"] for row in strict_pairs
    ]
    limit_to_bar_values = [
        row["parent_limit_to_bar_bps"] for row in strict_pairs
    ]
    quote_lower = [
        row["quote_allocation_fraction_of_plan_interval"][0]
        for row in strict_pairs
    ]
    quote_upper = [
        row["quote_allocation_fraction_of_plan_interval"][1]
        for row in strict_pairs
    ]
    limit_lower = [
        row["parent_limit_allocation_fraction_of_plan_interval"][0]
        for row in strict_pairs
    ]
    limit_upper = [
        row["parent_limit_allocation_fraction_of_plan_interval"][1]
        for row in strict_pairs
    ]
    max_limit_pair = max(
        strict_pairs,
        key=lambda row: row[
            "parent_limit_allocation_fraction_of_plan_interval"
        ][1],
    )
    max_limit_interval = max_limit_pair[
        "parent_limit_allocation_fraction_of_plan_interval"
    ]

    return dict(
        scope=(
            "Read-only current-source algebra plus a conservative join of "
            "sanitized application success events to actionable signal rows. "
            "No live module is imported, no broker is contacted, and no "
            "historical fill is inferred."
        ),
        current_source_sha256=source_hashes,
        source_contract_tokens=token_audit,
        current_formula_contract=dict(
            symbol=config.LIVE_SYMBOL,
            shorts_enabled=bool(config.TRADER_ALLOW_SHORTS),
            planned_position_fraction_pct=position_fraction * 100.0,
            quantity_basis="floor(planned dollars / signal bar close)",
            bracket_price_basis="pre-submission live quote",
            stored_entry_basis="same pre-submission live quote",
            parent_type="limit",
            parent_limit_offset_pct=parent_limit_offset * 100.0,
            target_from_quote_pct=target_pct * 100.0,
            stop_from_quote_pct=stop_pct * 100.0,
            post_fill_reanchor_present=False,
            actual_entry_fill_persisted=False,
            post_fill_quantity_resize_present=False,
        ),
        no_rounding_fill_relative_bounds=dict(
            at_quote=dict(
                target_pct=target_pct * 100.0,
                stop_pct=-stop_pct * 100.0,
                reward_risk=target_pct / stop_pct,
            ),
            long_at_parent_limit=dict(
                target_pct=round(
                    analytic_long_target * 100.0, 6
                ),
                stop_pct=round(
                    analytic_long_stop * 100.0, 6
                ),
                reward_risk=round(
                    analytic_long_target / abs(analytic_long_stop), 6
                ),
            ),
            short_at_parent_limit=dict(
                target_pct=round(
                    analytic_short_target * 100.0, 6
                ),
                stop_pct=round(
                    -analytic_short_stop * 100.0, 6
                ),
                reward_risk=round(
                    analytic_short_target / analytic_short_stop, 6
                ),
                relevance=(
                    "algebraic symmetry only; current TQQQ shorts are disabled"
                ),
            ),
            interpretation=(
                "At the least favorable permitted parent-limit fill, the "
                "quote-anchored 1.0%/0.5% target/stop becomes approximately "
                "0.5%/1.0% relative to fill, inverting reward:risk from 2 to 0.5."
            ),
        ),
        archived_quote_distribution_geometry=dict(
            application_success_events=len(parsed_entries),
            current_geometry_applied_not_historical_fill_reconstruction=True,
            quote_range=summary(
                [row["quote"] for row in parsed_entries]
            ),
            parent_limit_fill_relative_target_pct=summary(target_values),
            parent_limit_fill_relative_stop_pct=summary(stop_values),
            parent_limit_fill_reward_risk=summary(reward_risk_values),
            rows=parsed_entries,
        ),
        strict_archive_sizing_join=dict(
            method=(
                "Within each UTC minute, sort entry events and signal rows; "
                "retain only slots where the number of entry events equals "
                "the number of actionable long-signal rows, then pair in order."
            ),
            matched_entry_events=len(strict_pairs),
            all_entry_events=len(parsed_entries),
            unresolved_entry_events=(
                len(parsed_entries) - len(strict_pairs)
            ),
            unresolved_slots=unresolved_slots,
            quote_to_signal_bar_bps=summary(quote_to_bar_values),
            parent_limit_to_signal_bar_bps=summary(
                limit_to_bar_values
            ),
            quote_allocation_fraction_of_plan=dict(
                lower_endpoint=summary(quote_lower),
                upper_endpoint=summary(quote_upper),
                definitely_above_plan=sum(value > 1.0 for value in quote_lower),
                possibly_above_plan=sum(value > 1.0 for value in quote_upper),
            ),
            parent_limit_allocation_fraction_of_plan=dict(
                lower_endpoint=summary(limit_lower),
                upper_endpoint=summary(limit_upper),
                definitely_above_plan=sum(value > 1.0 for value in limit_lower),
                possibly_above_plan=sum(value > 1.0 for value in limit_upper),
            ),
            maximum_parent_limit_case=dict(
                event_time=max_limit_pair["event_time"],
                signal_bar_time=max_limit_pair["signal_bar_time"],
                qty=max_limit_pair["qty"],
                signal_bar_close=max_limit_pair["bar_close"],
                quote=max_limit_pair["quote"],
                parent_limit=max_limit_pair["parent_limit"],
                allocation_fraction_of_plan_interval=[
                    round(value, 9) for value in max_limit_interval
                ],
                implied_account_allocation_pct_interval=[
                    round(value * position_fraction * 100.0, 6)
                    for value in max_limit_interval
                ],
            ),
            rows=strict_pairs,
            caveat=(
                "These are quote/limit bounds against the archived sizing "
                "basis. Actual parent fills are absent and may be better than "
                "the limit; six events lack an unambiguous same-minute "
                "actionable-signal join."
            ),
        ),
        current_test_boundary=dict(
            exact_quote_derived_order_prices=True,
            fixed_position_plan=True,
            fill_relative_target_stop_geometry=False,
            actual_fill_reanchor=False,
            bar_close_to_fill_allocation_bound=False,
            archived_cycle_keyed_sizing_join=False,
        ),
        external_primary_sources={
            "ibkr_limit_order": (
                "https://ibkrcampus.com/campus/glossary-terms/limit-order/"
            ),
            "ibkr_bracket_orders": (
                "https://ibkrcampus.com/campus/ibkr-api-page/order-types/"
                "#bracket-orders"
            ),
            "ibkr_order_status_and_fill_fields": (
                "https://ibkrcampus.com/campus/ibkr-api-page/twsapi-doc/"
            ),
        },
        falsification_gate=[
            (
                "Persist the actual parent fill price, time, cumulative "
                "quantity, permId, and execution IDs before treating entry "
                "geometry as known."
            ),
            (
                "Define whether target/stop distances are quote-anchored or "
                "fill-anchored, and test partial fills plus penny rounding."
            ),
            (
                "Size from a broker-verifiable entry basis or enforce an "
                "explicit maximum notional; reconcile actual filled quantity "
                "and notional against the plan."
            ),
            (
                "Retain a cycle/lifecycle ID joining signal bar, sizing plan, "
                "quote, limit, order status, fills, and closed trade."
            ),
        ],
        limitations=[
            (
                "A limit is a worst permitted buy price, not an observed fill; "
                "price improvement can make realized geometry less deformed."
            ),
            (
                "Applying today's 1.0%/0.5% formula to archived quote values "
                "is a rounding and scale audit, not historical order reconstruction."
            ),
            (
                "The strict archive join excludes six events rather than "
                "guessing across duplicate/missing cycle evidence."
            ),
            (
                "Stop orders can gap beyond their trigger; the approximately "
                "1% fill-relative stop here is only the trigger geometry, not "
                "a loss bound."
            ),
        ],
        decision=(
            "The advertised 1.0% target and 0.5% stop describe distances from "
            "a pre-submission quote, not the unobserved parent fill. At the "
            "current buy-limit cap, exact no-rounding geometry becomes "
            "+0.497512%/-0.995025% and reward:risk falls from 2.0 to 0.5. "
            "Across 72 archived quote values, penny rounding leaves medians "
            "of +0.497791%/-0.998129%. A strict 66-event sizing join shows the "
            "parent-limit upper envelope spans -141.121 to +382.687bp versus "
            "the signal-bar basis; the maximum case permits roughly "
            "10.344%-10.383% of equity against a 10% plan. These are admissible "
            "bounds, not realized slippage. Name the parameters quote-anchored "
            "and require fill-relative risk/notional reconciliation."
        ),
    )


def partial_fill_force_close_quantity_audit() -> Dict[str, object]:
    """Audit partial-parent and cancel-before-close quantity invariants."""
    source_paths = [
        "live/broker.py",
        "live/trader.py",
        "live/state.py",
        "tests/test_broker.py",
        "tests/test_trader_flow.py",
        "tests/test_software_take_profit.py",
    ]
    source_text: Dict[str, str] = {}
    source_hashes: Dict[str, str] = {}
    for relative in source_paths:
        path = os.path.join(REPO, relative)
        with open(path, "rb") as fh:
            raw = fh.read()
        source_hashes[relative] = hashlib.sha256(raw).hexdigest()
        source_text[relative] = raw.decode("utf-8")

    required_tokens = {
        "live/broker.py": [
            "def cancel_and_close(symbol: str, bracket_order_id: str, qty: int,",
            "if getattr(order, \"parentId\", None) == parent_id:",
            "ib.cancelOrder(order)",
            'close_order = MarketOrder(close_action, qty)',
            "trade = ib.placeOrder(contract, close_order)",
            "def get_open_position(symbol: str) -> dict | None:",
            '"qty":          int(pos.position)',
        ],
        "live/trader.py": [
            'if broker_pos is None or broker_pos["qty"] == 0:',
            "position.symbol, position.bracket_order_id, position.qty,",
            'exit_action = "exit_software_stop"',
            'exit_action = "exit_software_take_profit"',
            'exit_action = "exit_time_exit"',
        ],
        "tests/test_broker.py": [
            'MO.assert_called_once_with("SELL", 10)',
            'MO.assert_called_once_with("BUY", 5)',
        ],
    }
    token_audit = {
        path: {token: token in source_text[path] for token in tokens}
        for path, tokens in required_tokens.items()
    }
    if not all(
        present
        for checks in token_audit.values()
        for present in checks.values()
    ):
        raise AssertionError("partial-fill source contract changed")

    cancel_block = re.search(
        r"^def cancel_and_close\b.*?(?=^def\s)",
        source_text["live/broker.py"],
        flags=re.DOTALL | re.MULTILINE,
    )
    if cancel_block is None:
        raise AssertionError("could not isolate cancel_and_close")
    cancel_source = cancel_block.group(0)

    cancellation_confirmation_tokens = {
        token: token in cancel_source
        for token in (
            "PendingCancel",
            "cancelledEvent",
            "statusEvent",
            "isDone",
            "orderStatus",
            "waitOnUpdate",
            "remaining",
        )
    }
    quantity_reconciliation_tokens = {
        token: token in cancel_source
        for token in (
            "get_open_position",
            "positions()",
            "avgFillPrice",
            "filled",
            "remaining",
            "execDetails",
        )
    }
    force_close_calls = [
        match.group(0)
        for match in re.finditer(
            r"broker\.cancel_and_close\((.*?)\)",
            source_text["live/trader.py"],
            flags=re.DOTALL,
        )
    ]

    requested_qty = 100
    partial_fill_rows = []
    for actual_filled_qty in (1, 25, 50, 75, 99, 100):
        long_final_qty = actual_filled_qty - requested_qty
        short_final_qty = -actual_filled_qty + requested_qty
        partial_fill_rows.append(
            dict(
                requested_qty=requested_qty,
                actual_parent_filled_qty=actual_filled_qty,
                local_recorded_qty=requested_qty,
                forced_close_qty=requested_qty,
                long_final_signed_qty=long_final_qty,
                short_final_signed_qty=short_final_qty,
                opposite_position_abs_qty=(
                    requested_qty - actual_filled_qty
                ),
                close_size_excess_vs_actual_pct=round(
                    (
                        requested_qty / actual_filled_qty - 1.0
                    ) * 100.0,
                    6,
                ),
            )
        )

    cancel_race_rows = []
    for child_fill_after_cancel_request in (0, 25, 100):
        cancel_race_rows.append(
            dict(
                initial_long_qty=requested_qty,
                market_close_sell_qty=requested_qty,
                child_sell_fill_after_cancel_request=(
                    child_fill_after_cancel_request
                ),
                final_signed_qty=(
                    requested_qty
                    - requested_qty
                    - child_fill_after_cancel_request
                ),
                opposite_short_qty=child_fill_after_cancel_request,
            )
        )

    archive_dir = os.path.join(
        REPO,
        "data",
        "live_runs",
        "archive_2026-06-18_pre_clean_run",
    )

    def load_jsonl(name: str) -> List[Dict[str, object]]:
        rows = []
        with open(os.path.join(archive_dir, name)) as fh:
            for line in fh:
                if line.strip():
                    rows.append(json.loads(line))
        return rows

    archive_events = load_jsonl("monitor_events.jsonl")
    archive_trades = load_jsonl("trades.jsonl")
    entry_events = [
        row for row in archive_events
        if row.get("category") == "entry"
    ]
    entry_quantities = []
    for row in entry_events:
        match = re.search(
            r"(?:LONG |SHORT )?(\d+) TQQQ @ ([0-9.]+)",
            str(row["message"]),
        )
        if match is None:
            raise AssertionError(
                "Unparseable archived entry event: %r" % row["message"]
            )
        entry_quantities.append(int(match.group(1)))

    archive_text = "\n".join(
        json.dumps(row, sort_keys=True)
        for row in archive_events + archive_trades
    )
    partial_identity_patterns = {
        pattern: len(
            re.findall(pattern, archive_text, flags=re.IGNORECASE)
        )
        for pattern in (
            r"partial",
            r"remaining",
            r"avgfill",
            r"filled[_ ]?qty",
            r"cumqty",
        )
    }
    half_fill_opposite_quantities = [
        qty - max(1, int(math.floor(qty * 0.5)))
        for qty in entry_quantities
    ]

    return dict(
        scope=(
            "Read-only source/archive audit plus deterministic signed-quantity "
            "arithmetic. No live module is imported, no order is submitted or "
            "cancelled, and no historical partial fill is inferred."
        ),
        current_source_sha256=source_hashes,
        source_contract_tokens=token_audit,
        current_quantity_contract=dict(
            local_position_qty_source="requested bracket quantity",
            local_write_waits_for_parent_fill=False,
            broker_position_qty_available=True,
            broker_nonzero_test_only=True,
            broker_vs_local_quantity_equality_check=False,
            broker_vs_local_direction_check=False,
            broker_avg_price_used_for_management=False,
            force_close_call_count=len(force_close_calls),
            force_close_calls_all_use_local_position_qty=all(
                "position.qty" in call for call in force_close_calls
            ),
            force_close_paths=[
                "software stop",
                "software take profit",
                "time exit",
            ],
        ),
        attached_order_partial_fill_contract=dict(
            official_child_activation=(
                "attached children remain on hold until the parent is "
                "completely filled"
            ),
            partial_parent_exposure_protected_by_children=False,
            software_check_frequency="once per admitted trader cycle",
            current_parent_remainder_cancelled_by_force_close=False,
            reason=(
                "cancel_and_close cancels only orders whose parentId equals "
                "the parent ID; the partially filled parent itself has "
                "orderId == parent ID and parentId 0."
            ),
        ),
        deterministic_partial_fill_overshoot=dict(
            schedule=[
                "application requests and locally records 100 shares",
                "parent fills F shares where 0 < F < 100",
                "broker position F is nonzero, so reconciliation treats the local position as open",
                "a software or time exit calls cancel_and_close with local qty 100",
                "market close sends 100 shares, leaving signed position F-100 for a long",
            ],
            rows=partial_fill_rows,
            fifty_share_example=dict(
                actual_long_before_close=50,
                market_sell=100,
                final_signed_position=-50,
                outcome="opposite short position",
            ),
            reachability_proved=(
                next(
                    row for row in partial_fill_rows
                    if row["actual_parent_filled_qty"] == 50
                )["long_final_signed_qty"]
                == -50
            ),
        ),
        cancellation_acknowledgement_race=dict(
            cancellation_confirmation_field_presence=(
                cancellation_confirmation_tokens
            ),
            confirmation_fields_present=sum(
                cancellation_confirmation_tokens.values()
            ),
            quantity_reconciliation_field_presence=(
                quantity_reconciliation_tokens
            ),
            quantity_fields_present=sum(
                quantity_reconciliation_tokens.values()
            ),
            market_close_submitted_immediately_after_cancel_requests=True,
            rows=cancel_race_rows,
            consequence=(
                "PendingCancel is not confirmed cancellation. If a child "
                "SELL fills after the request while the full market SELL also "
                "fills, the child quantity becomes an opposite short."
            ),
        ),
        archive_observability=dict(
            entry_success_events=len(entry_events),
            requested_qty_range=dict(
                min=min(entry_quantities),
                median=float(np.median(entry_quantities)),
                max=max(entry_quantities),
            ),
            closed_trade_rows=len(archive_trades),
            partial_quantity_identity_pattern_counts=(
                partial_identity_patterns
            ),
            actual_parent_filled_quantity_retained=False,
            parent_remaining_quantity_retained=False,
            cancellation_status_retained=False,
            hypothetical_half_fill_opposite_qty_range=dict(
                min=min(half_fill_opposite_quantities),
                median=float(np.median(half_fill_opposite_quantities)),
                max=max(half_fill_opposite_quantities),
            ),
            caveat=(
                "The half-fill range scales the reachable arithmetic over "
                "archived requested quantities; it is not evidence that any "
                "historical parent partially filled."
            ),
        ),
        next_cycle_containment=dict(
            filled_opposite_position_visible=(
                "local-flat/broker-nonzero entry guard should block a later entry"
            ),
            limitation=(
                "Detection occurs after the overshoot and does not flatten or "
                "reconstruct it. A still-working parent remainder can continue "
                "changing exposure after the local close."
            ),
        ),
        current_test_boundary=dict(
            exact_requested_long_close_quantity=True,
            exact_requested_short_close_quantity=True,
            partial_parent_vs_local_quantity=False,
            parent_remainder_cancel_and_confirm=False,
            child_cancel_ack_before_market_close=False,
            post_close_broker_flat_assertion=False,
            opposite_position_regression=False,
        ),
        external_primary_sources={
            "ibkr_order_status_and_attached_orders": (
                "https://interactivebrokers.github.io/tws-api/"
                "order_submission.html"
            ),
            "ibkr_open_order_recovery": (
                "https://interactivebrokers.github.io/tws-api/"
                "open_orders.html"
            ),
            "ibkr_bracket_transmission": (
                "https://ibkrcampus.com/campus/ibkr-api-page/order-types/"
                "#bracket-orders"
            ),
        },
        falsification_gate=[
            (
                "Persist parent filled, remaining, average fill price, status, "
                "permId, and per-execution quantities under one lifecycle ID."
            ),
            (
                "On every management cycle, compare signed broker quantity "
                "and direction with local state; mismatch must enter a typed "
                "reconciliation state rather than normal holding logic."
            ),
            (
                "Cancel the parent remainder and both children, wait for "
                "confirmed terminal states, then derive close quantity from a "
                "fresh signed broker position."
            ),
            (
                "After the close fill, verify broker quantity is exactly zero; "
                "if not, reconcile the residual without deleting lifecycle identity."
            ),
            (
                "Test partial fills and child-fill-during-cancel schedules for "
                "longs and shorts, including reconnect and DAY-parent expiry."
            ),
        ],
        limitations=[
            (
                "TQQQ is usually liquid and a marketable 0.5%-through limit may "
                "often fill completely; frequency is unidentified without "
                "retained parent status/executions."
            ),
            (
                "The deterministic 100-share and archive half-fill cases are "
                "counterexamples and scale diagnostics, not incident estimates."
            ),
            (
                "Actual broker order handling can change exposure as parent, "
                "child, and market-close executions interleave; the tables show "
                "specific reachable schedules, not every possible terminal state."
            ),
        ],
        decision=(
            "The force-close path is not quantity-safe. Local state records the "
            "requested parent quantity before execution; any nonzero broker "
            "quantity is accepted as open; all three force-close paths submit "
            "the full local quantity. A 50/100 parent fill therefore makes the "
            "market close SELL 100 and leaves short 50. Attached children are "
            "officially held until complete parent fill, and the parent remainder "
            "itself is not cancelled by the child-only loop. Independently, child "
            "cancel requests are not confirmed before the market close, so a "
            "late child fill can also create opposite exposure. The archive "
            "retains zero partial/status fields, so historical frequency is "
            "unidentified. Force-close size must come from a fresh signed broker "
            "position after terminal cancellation acknowledgements, followed by "
            "an explicit broker-flat assertion."
        ),
    )


def force_close_completion_and_vwap_audit() -> Dict[str, object]:
    """Audit whether one observed execution proves a force close complete."""
    source_paths = [
        "live/broker.py",
        "live/trader.py",
        "live/state.py",
        "tests/test_broker.py",
        "tests/test_trader_flow.py",
    ]
    source_text: Dict[str, str] = {}
    source_hashes: Dict[str, str] = {}
    for relative in source_paths:
        path = os.path.join(REPO, relative)
        with open(path, "rb") as fh:
            raw = fh.read()
        source_hashes[relative] = hashlib.sha256(raw).hexdigest()
        source_text[relative] = raw.decode("utf-8")

    required_tokens = {
        "live/broker.py": [
            "for _ in range(20):",
            "if trade.fills:",
            "last_fill = trade.fills[-1]",
            'return {"fill_price": fill_price, "fill_time": fill_time}',
            "return None",
        ],
        "live/trader.py": [
            "close_fill = broker.cancel_and_close(",
            'exit_price = close_fill["fill_price"]',
            "state.close_position(return_pct=ret, exit_type=\"stop_hit\"",
            "state.close_position(return_pct=ret, exit_type=\"target_hit\"",
            "state.close_position(return_pct=ret, exit_type=\"time_exit\"",
        ],
        "live/state.py": [
            "def mark_pending_close(estimated_exit_price: float = None)",
            "def finalize_pending_close(return_pct: float, exit_type: str,",
            'conn.execute("DELETE FROM position")',
        ],
        "tests/test_broker.py": [
            "trade.fills = [_fill(_exec(price=101.23",
            "trade.fills = []  # never fills",
            "self.assertIsNone(broker.cancel_and_close",
        ],
    }
    token_audit = {
        path: {token: token in source_text[path] for token in tokens}
        for path, tokens in required_tokens.items()
    }
    if not all(
        present
        for checks in token_audit.values()
        for present in checks.values()
    ):
        raise AssertionError("force-close completion source contract changed")

    cancel_block = re.search(
        r"^def cancel_and_close\b.*?(?=^def\s)",
        source_text["live/broker.py"],
        flags=re.DOTALL | re.MULTILINE,
    )
    if cancel_block is None:
        raise AssertionError("could not isolate cancel_and_close")
    cancel_source = cancel_block.group(0)

    completion_field_presence = {
        token: token in cancel_source
        for token in (
            "orderStatus",
            "isDone",
            "remaining",
            "avgFillPrice",
            "cumQty",
            "execution.shares",
            "waitUntil",
            "filledEvent",
        )
    }
    returned_fields = re.findall(
        r'"([a-z_]+)"\s*:',
        re.search(
            r"return \{([^}]+)\}",
            cancel_source,
            flags=re.DOTALL,
        ).group(1),
    )

    requested_close_qty = 100
    first_execution_qty = 60
    first_execution_price = 100.0
    later_execution_qty = 40
    later_execution_price = 101.0
    correct_vwap = (
        first_execution_qty * first_execution_price
        + later_execution_qty * later_execution_price
    ) / requested_close_qty
    first_only_error_bps = (
        first_execution_price / correct_vwap - 1.0
    ) * 10000.0
    last_component_error_bps = (
        later_execution_price / correct_vwap - 1.0
    ) * 10000.0

    archive_dir = os.path.join(
        REPO,
        "data",
        "live_runs",
        "archive_2026-06-18_pre_clean_run",
    )

    def load_jsonl(name: str) -> List[Dict[str, object]]:
        rows = []
        with open(os.path.join(archive_dir, name)) as fh:
            for line in fh:
                if line.strip():
                    rows.append(json.loads(line))
        return rows

    archive_events = load_jsonl("monitor_events.jsonl")
    archive_trades = load_jsonl("trades.jsonl")
    timeout_events = [
        row for row in archive_events
        if "fill unavailable" in str(row.get("message", "")).lower()
        and row.get("category") == "time_exit"
    ]
    time_exit_rows = [
        row for row in archive_trades
        if row.get("exit_type") == "time_exit"
    ]
    software_stop_events = [
        row for row in archive_events
        if row.get("category") == "stop"
        and "forcing close" in str(row.get("message", "")).lower()
    ]
    archive_text = "\n".join(
        json.dumps(row, sort_keys=True)
        for row in archive_events + archive_trades
    )
    completion_identity_patterns = {
        pattern: len(re.findall(pattern, archive_text, flags=re.IGNORECASE))
        for pattern in (
            r"remaining",
            r"avgfill",
            r"cumqty",
            r"execid",
            r"orderstatus",
        )
    }

    state_source = source_text["live/state.py"]
    pending_close_callers = {
        "mark_pending_close": len(
            re.findall(r"\bmark_pending_close\(", source_text["live/trader.py"])
        ),
        "finalize_pending_close": len(
            re.findall(
                r"\bfinalize_pending_close\(",
                source_text["live/trader.py"],
            )
        ),
    }
    pending_close_available = all(
        token in state_source
        for token in ("def mark_pending_close", "def finalize_pending_close")
    )

    return dict(
        scope=(
            "Read-only source/archive audit plus deterministic execution "
            "arithmetic. No live module is imported, no broker is contacted, "
            "and no order or protected path is changed."
        ),
        current_source_sha256=source_hashes,
        source_contract_tokens=token_audit,
        current_completion_contract=dict(
            poll_seconds=10.0,
            success_predicate="trade.fills is nonempty",
            completion_field_presence=completion_field_presence,
            completion_fields_present=sum(
                completion_field_presence.values()
            ),
            returned_fields=returned_fields,
            returned_quantity=False,
            returned_remaining=False,
            returned_status=False,
            returned_order_identity=False,
            post_close_broker_position_check=False,
            caller_deletes_local_position_after_nonempty_fill=True,
            caller_deletes_local_position_after_timeout=True,
        ),
        deterministic_first_partial_execution=dict(
            schedule=[
                "broker position is long 100 and a market SELL 100 is submitted",
                "the first execution reports 60 shares at 100 while 40 remain",
                "trade.fills becomes nonempty, so cancel_and_close returns immediately",
                "the caller records local quantity 100 as closed and deletes the position",
            ],
            requested_close_qty=requested_close_qty,
            observed_execution_qty=first_execution_qty,
            broker_status_at_return=dict(
                status="Submitted",
                filled=first_execution_qty,
                remaining=requested_close_qty - first_execution_qty,
                avg_fill_price=first_execution_price,
            ),
            current_return=dict(
                fill_price=first_execution_price,
                filled_qty_omitted=True,
                remaining_qty_omitted=True,
            ),
            final_signed_broker_qty_if_no_later_fill=(
                requested_close_qty - first_execution_qty
            ),
            local_position_rows_after_caller=0,
            local_trade_qty_recorded=requested_close_qty,
            residual_exposure_hidden_by_local_flat=True,
            reachability_proved=(
                requested_close_qty - first_execution_qty == 40
            ),
        ),
        multi_execution_price_accounting=dict(
            executions=[
                dict(qty=first_execution_qty, price=first_execution_price),
                dict(qty=later_execution_qty, price=later_execution_price),
            ],
            correct_vwap=round(correct_vwap, 6),
            if_first_poll_sees_only_first_execution=dict(
                returned_price=first_execution_price,
                error_vs_vwap_bps=round(first_only_error_bps, 6),
                completion_not_proved=True,
            ),
            if_first_poll_sees_both_executions=dict(
                returned_price=later_execution_price,
                error_vs_vwap_bps=round(last_component_error_bps, 6),
                completion_not_proved_by_predicate=True,
            ),
            point=(
                "The same nonempty-list predicate can return before completion "
                "or, when complete, substitute one component price for VWAP."
            ),
        ),
        timeout_branch=dict(
            behavior=(
                "After 20 polls, cancel_and_close returns None without checking "
                "whether the market order remains working or cancelling it."
            ),
            caller_behavior=(
                "All three force-close callers substitute a mark/reference price "
                "and call close_position, deleting local lifecycle state."
            ),
            later_fill_risk=(
                "The untracked market order may execute after local deletion; "
                "the archive cannot distinguish callback delay, later fill, "
                "rejection, cancellation, or no execution."
            ),
            pending_close_state_available=pending_close_available,
            pending_close_trader_call_counts=pending_close_callers,
            force_close_timeout_uses_pending_close=False,
        ),
        archive_observability=dict(
            time_exit_trade_rows=len(time_exit_rows),
            explicit_time_exit_fill_unavailable_events=len(timeout_events),
            software_stop_force_close_events=len(software_stop_events),
            minimum_identifiable_force_close_attempts=(
                len(time_exit_rows) + len(software_stop_events)
            ),
            completion_identity_pattern_counts=(
                completion_identity_patterns
            ),
            full_close_quantity_retained=False,
            residual_broker_position_retained=False,
            caveat=(
                "The four timeout warnings prove missing fill evidence at the "
                "10-second boundary, not that the market orders failed to fill "
                "or left residual exposure."
            ),
        ),
        current_test_boundary=dict(
            any_fill_returns_price=True,
            no_fill_returns_none=True,
            partial_fill_must_remain_pending=False,
            full_quantity_completion_required=False,
            multi_execution_vwap=False,
            timeout_preserves_local_position=False,
            later_fill_after_timeout=False,
            post_close_exact_flat_assertion=False,
        ),
        external_primary_sources={
            "ibkr_order_status": (
                "https://interactivebrokers.github.io/tws-api/"
                "order_submission.html"
            ),
            "ibkr_execution_details": (
                "https://interactivebrokers.github.io/tws-api/"
                "executions_commissions.html"
            ),
            "ibkr_execution_fields": (
                "https://interactivebrokers.github.io/tws-api/"
                "classIBApi_1_1Execution.html"
            ),
            "ibkr_current_api_docs": (
                "https://ibkrcampus.com/campus/ibkr-api-page/twsapi-doc/"
            ),
        },
        falsification_gate=[
            (
                "Treat the close as complete only when cumulative execution "
                "quantity equals the intended residual, remaining is zero, "
                "and a fresh signed broker-position query confirms exact flat."
            ),
            (
                "Aggregate executions by durable order/lifecycle identity and "
                "compute quantity-weighted price; retain execId, shares, cumQty, "
                "avgPrice, permId, status, and remaining."
            ),
            (
                "On timeout, retain the lifecycle as pending_close and keep "
                "blocking entries while reconciling the still-live close order; "
                "never translate missing callback evidence into local flatness."
            ),
            (
                "Add deterministic tests for first partial execution, two-price "
                "completion, delayed execution after timeout, rejection, and "
                "long/short residuals."
            ),
        ],
        limitations=[
            (
                "The 60/40 execution schedule proves a reachable state-machine "
                "error, not its frequency in liquid TQQQ."
            ),
            (
                "A normal market order often fills rapidly; latency and partial "
                "fills still require completion semantics because safety cannot "
                "depend on the usual case."
            ),
            (
                "Archive timeout warnings do not reveal whether the order "
                "executed, whether only the callback was delayed, or what "
                "quantity and VWAP ultimately resulted."
            ),
        ],
        decision=(
            "Force-close completion is not proved. The adapter returns as soon "
            "as any execution appears, omits filled/remaining/status/identity, "
            "and reports the last component price rather than VWAP. A 60-share "
            "first fill of SELL 100 therefore lets callers delete a 100-share "
            "local position while 40 shares remain long. If both 60@100 and "
            "40@101 are already visible, it records 101 instead of the 100.40 "
            "VWAP. The timeout branch is more concrete historically: four of "
            "nine archived time exits explicitly lacked fill evidence after "
            "10 seconds, yet callers still estimated PnL and deleted state "
            "without cancelling or reconciling the market order. Historical "
            "residual frequency is unidentified. Require cumulative completion, "
            "VWAP, pending-close retention on uncertainty, and broker-flat proof."
        ),
    )


def unresolved_close_back_to_back_reentry_audit() -> Dict[str, object]:
    """Audit same-cycle entry while prior close orders are nonterminal."""
    source_paths = [
        "live/broker.py",
        "live/trader.py",
        "live/state.py",
        "tests/test_trader_flow.py",
        "tests/test_trader_reconcile.py",
    ]
    source_text: Dict[str, str] = {}
    source_hashes: Dict[str, str] = {}
    for relative in source_paths:
        path = os.path.join(REPO, relative)
        with open(path, "rb") as fh:
            raw = fh.read()
        source_hashes[relative] = hashlib.sha256(raw).hexdigest()
        source_text[relative] = raw.decode("utf-8")

    required_tokens = {
        "live/trader.py": [
            '# Fall through to entry check',
            'exit_action = "exit_software_stop"',
            'exit_action = "exit_time_exit"',
            "broker_pos = broker.get_open_position(config.LIVE_SYMBOL)",
            "result = broker.place_bracket_order(",
            "back-to-back after {exit_action}",
        ],
        "live/broker.py": [
            "ib.cancelOrder(order)",
            "trade = ib.placeOrder(contract, close_order)",
            "if trade.fills:",
            "return None",
        ],
        "tests/test_trader_flow.py": [
            "def test_back_to_back_entry_after_exit(self):",
            "mbroker.get_open_position.return_value = None",
            'self.assertEqual(result, "exit_target_hit_then_entry")',
            "mbroker.place_bracket_order.assert_called_once()",
        ],
    }
    token_audit = {
        path: {token: token in source_text[path] for token in tokens}
        for path, tokens in required_tokens.items()
    }
    if not all(
        present
        for checks in token_audit.values()
        for present in checks.values()
    ):
        raise AssertionError("back-to-back re-entry source contract changed")

    entry_block_match = re.search(
        r"# ── Check for new entry signal.*?(?=^def _signed_return)",
        source_text["live/trader.py"],
        flags=re.DOTALL | re.MULTILINE,
    )
    if entry_block_match is None:
        raise AssertionError("could not isolate trader entry block")
    entry_block = entry_block_match.group(0)
    working_order_guard_presence = {
        token: token in entry_block
        for token in (
            "openOrders",
            "openTrades",
            "reqOpenOrders",
            "reqAllOpenOrders",
            "orderStatus",
            "remaining",
            "permId",
            "orderRef",
        )
    }

    old_qty = 100
    new_qty = 100
    old_child_fill = 100
    late_close_fill_rows = []
    for late_close_fill in (0, 25, 40, 100):
        broker_after_new_entry = (
            -old_qty
            + old_child_fill
            + new_qty
            - late_close_fill
        )
        late_close_fill_rows.append(
            dict(
                initial_old_long_qty=old_qty,
                old_child_sell_fill=old_child_fill,
                broker_qty_at_reentry_guard=0,
                new_parent_buy_fill=new_qty,
                late_old_market_close_sell_fill=late_close_fill,
                final_signed_broker_qty=broker_after_new_entry,
                local_recorded_new_qty=new_qty,
                broker_minus_local_qty=broker_after_new_entry - new_qty,
            )
        )

    archive_dir = os.path.join(
        REPO,
        "data",
        "live_runs",
        "archive_2026-06-18_pre_clean_run",
    )

    def load_jsonl(name: str) -> List[Dict[str, object]]:
        rows = []
        with open(os.path.join(archive_dir, name)) as fh:
            for line in fh:
                if line.strip():
                    rows.append(json.loads(line))
        return rows

    archive_events = load_jsonl("monitor_events.jsonl")
    archive_trades = load_jsonl("trades.jsonl")
    back_to_back_entries = [
        row for row in archive_events
        if row.get("category") == "entry"
        and "back-to-back after " in str(row.get("message", ""))
    ]
    back_to_back_by_action: Dict[str, int] = {}
    for row in back_to_back_entries:
        match = re.search(
            r"back-to-back after ([^)]+)",
            str(row["message"]),
        )
        if match is None:
            raise AssertionError(
                "Unparseable back-to-back event: %r" % row["message"]
            )
        action = match.group(1)
        back_to_back_by_action[action] = (
            back_to_back_by_action.get(action, 0) + 1
        )

    timeout_events = [
        row for row in archive_events
        if row.get("category") == "time_exit"
        and "fill unavailable" in str(row.get("message", "")).lower()
    ]
    timeout_to_reentry = []
    for timeout in timeout_events:
        timeout_time = pd.Timestamp(timeout["event_time"])
        candidates = []
        for entry in back_to_back_entries:
            entry_time = pd.Timestamp(entry["event_time"])
            delta = (entry_time - timeout_time).total_seconds()
            if (
                0.0 <= delta <= 120.0
                and "back-to-back after exit_time_exit"
                in str(entry["message"])
            ):
                candidates.append((delta, entry))
        if candidates:
            delta, entry = min(candidates, key=lambda item: item[0])
            qty_match = re.search(
                r"(?:LONG |SHORT )?(\d+) TQQQ",
                str(entry["message"]),
            )
            timeout_to_reentry.append(
                dict(
                    timeout_event_id=int(timeout["id"]),
                    entry_event_id=int(entry["id"]),
                    seconds_between=round(float(delta), 6),
                    requested_new_entry_qty=(
                        int(qty_match.group(1))
                        if qty_match is not None else None
                    ),
                    application_entry_message=entry["message"],
                )
            )

    archive_text = "\n".join(
        json.dumps(row, sort_keys=True)
        for row in archive_events + archive_trades
    )
    order_terminal_identity_patterns = {
        pattern: len(re.findall(pattern, archive_text, flags=re.IGNORECASE))
        for pattern in (
            r"remaining",
            r"orderstatus",
            r"permId",
            r"execId",
            r"cancelled",
        )
    }

    return dict(
        scope=(
            "Read-only source/archive audit plus deterministic signed-position "
            "interleaving. No live module is imported, no broker is contacted, "
            "and no protected path is modified."
        ),
        current_source_sha256=source_hashes,
        source_contract_tokens=token_audit,
        current_reentry_contract=dict(
            force_close_paths_fall_through_same_cycle=True,
            entry_broker_position_guard=True,
            entry_guard_condition="current broker position is flat",
            entry_working_order_guard_presence=working_order_guard_presence,
            entry_working_order_fields_present=sum(
                working_order_guard_presence.values()
            ),
            check_position_and_submit_atomic=False,
            old_close_order_terminal_required=False,
            old_children_terminal_required=False,
            prior_lifecycle_identity_propagated_to_entry=False,
        ),
        deterministic_nonterminal_close_collision=dict(
            schedule=[
                "old lifecycle is long 100 with child SELL orders",
                "time/software exit requests child cancellation and submits market SELL 100",
                "no close fill callback arrives in 10 seconds, so the caller deletes local state",
                "an old child SELL 100 fills while cancellation is unresolved, making broker position flat",
                "the entry guard sees flat but does not inspect working orders",
                "a new parent BUY 100 fills and local state records the new lifecycle",
                "the still-working old market SELL later executes against the new exposure",
            ],
            rows=late_close_fill_rows,
            full_late_close_example=next(
                row for row in late_close_fill_rows
                if row["late_old_market_close_sell_fill"] == 100
            ),
            reachability_proved=(
                next(
                    row for row in late_close_fill_rows
                    if row["late_old_market_close_sell_fill"] == 100
                )["final_signed_broker_qty"]
                == 0
            ),
            outcome=(
                "The broker can be flat while local state says the new "
                "100-share long exists and its new bracket remains working."
            ),
        ),
        archive_observability=dict(
            all_back_to_back_application_entries=len(
                back_to_back_entries
            ),
            back_to_back_by_exit_action=dict(
                sorted(back_to_back_by_action.items())
            ),
            explicit_time_exit_fill_unavailable_events=len(timeout_events),
            fill_unavailable_then_back_to_back_entries=len(
                timeout_to_reentry
            ),
            timeout_to_reentry_rows=timeout_to_reentry,
            order_terminal_identity_pattern_counts=(
                order_terminal_identity_patterns
            ),
            broker_acceptance_or_new_entry_fill_proved=False,
            old_close_still_working_proved=False,
            caveat=(
                "The two joined pairs prove that the application submitted a "
                "new bracket after timeout evidence was missing and a broker-flat "
                "guard passed. They do not prove the old close remained working "
                "or that either new parent was accepted or filled."
            ),
        ),
        current_test_boundary=dict(
            back_to_back_after_terminal_bracket_fill=True,
            broker_flat_position_guard=True,
            outstanding_old_close_order=False,
            pending_child_cancellation=False,
            timeout_then_reentry=False,
            late_old_fill_after_new_parent=False,
            atomic_lifecycle_handoff=False,
        ),
        external_primary_sources={
            "ibkr_active_order_recovery": (
                "https://interactivebrokers.github.io/tws-api/"
                "open_orders.html"
            ),
            "ibkr_order_status_and_cancellation": (
                "https://interactivebrokers.github.io/tws-api/"
                "order_submission.html"
            ),
            "ibkr_execution_details": (
                "https://interactivebrokers.github.io/tws-api/"
                "executions_commissions.html"
            ),
        },
        falsification_gate=[
            (
                "After any exit submission, retain the lifecycle in pending_close "
                "until parent, children, and explicit close orders are all "
                "terminal and cumulative executions reconcile."
            ),
            (
                "Before re-entry, require exact broker flatness and zero active "
                "orders/execution remainder for the symbol/lifecycle, using "
                "durable permId/orderRef rather than client order arithmetic."
            ),
            (
                "Make lifecycle retirement and successor intent an atomic "
                "state transition; do not allow a new generation while prior "
                "orders can still mutate symbol exposure."
            ),
            (
                "Test child-fill-during-cancel, close timeout, flat snapshot, "
                "new parent submission, and late old-close execution schedules."
            ),
        ],
        limitations=[
            (
                "The deterministic schedule is a reachability counterexample, "
                "not evidence that either archived old close remained working."
            ),
            (
                "ENTRY placed is application-level submission evidence only; "
                "the archive does not establish acceptance or a new parent fill."
            ),
            (
                "A broker-flat position snapshot is valuable defense in depth; "
                "the defect is that it is neither an order-terminal check nor "
                "atomic with the successor submission."
            ),
        ],
        decision=(
            "A flat broker-position snapshot is insufficient for same-cycle "
            "re-entry while old orders are nonterminal. The force-close paths "
            "fall through to an entry guard that checks positions but zero "
            "working-order fields. A reachable schedule lets an old child flatten "
            "the account, the new parent establish 100 shares, and the still-live "
            "old market SELL erase that new exposure while local state remains "
            "long 100. The archive makes the boundary operationally relevant: "
            "32 back-to-back application entries exist, including two placed "
            "about 14 seconds after explicit time-exit fill-unavailable warnings. "
            "Those pairs do not prove a late old fill. Require terminal prior "
            "orders, reconciled executions, and atomic lifecycle handoff before "
            "a successor entry."
        ),
    )


def broker_account_scope_audit() -> Dict[str, object]:
    """Audit account/model identity across sizing, positions, and orders."""
    source_paths = [
        "live/broker.py",
        "live/trader.py",
        "live/state.py",
        "config.py",
        "config_modules/base.py",
        "config_modules/live.py",
        "tests/test_broker.py",
        "tests/test_trader_reconcile.py",
    ]
    source_text: Dict[str, str] = {}
    source_hashes: Dict[str, str] = {}
    for relative in source_paths:
        path = os.path.join(REPO, relative)
        with open(path, "rb") as fh:
            raw = fh.read()
        source_hashes[relative] = hashlib.sha256(raw).hexdigest()
        source_text[relative] = raw.decode("utf-8")

    required_tokens = {
        "live/broker.py": [
            "summary = ib.accountSummary()",
            'if item.tag in ("NetLiquidation", "TotalCashValue", "BuyingPower"):',
            "values[item.tag] = float(item.value)",
            "positions = ib.positions()",
            "if pos.contract.symbol == symbol:",
            '"qty":          int(pos.position)',
            "bracket = ib.bracketOrder(",
            "close_order = MarketOrder(close_action, qty)",
        ],
        "live/trader.py": [
            "account = broker.get_account()",
            "capital = account.equity",
            "sizing = state.get_position_plan(capital)",
            "broker_pos = broker.get_open_position(config.LIVE_SYMBOL)",
        ],
        "tests/test_broker.py": [
            "def test_get_open_position_match(self):",
            "def test_get_account_parses_summary(self):",
        ],
    }
    token_audit = {
        path: {token: token in source_text[path] for token in tokens}
        for path, tokens in required_tokens.items()
    }
    if not all(
        present
        for checks in token_audit.values()
        for present in checks.values()
    ):
        raise AssertionError("broker account-scope source contract changed")

    broker_source = source_text["live/broker.py"]
    config_source = "\n".join(
        source_text[path]
        for path in (
            "config.py",
            "config_modules/base.py",
            "config_modules/live.py",
        )
    )
    account_scope_tokens = {
        "configured_account_code": bool(
            re.search(
                r"\b(?:IBKR_|LIVE_)?ACCOUNT(?:_ID|_CODE)?\b\s*=",
                config_source,
            )
        ),
        "configured_model_code": bool(
            re.search(r"\bMODEL_CODE\b\s*=", config_source)
        ),
        "connection_account_argument": "account=" in re.search(
            r"^def _ensure_connected\b.*?(?=^def\s)",
            broker_source,
            flags=re.DOTALL | re.MULTILINE,
        ).group(0),
        "account_summary_item_account_filter": "item.account" in re.search(
            r"^def get_account\b.*?(?=^def\s)",
            broker_source,
            flags=re.DOTALL | re.MULTILINE,
        ).group(0),
        "account_summary_currency_filter": "item.currency" in re.search(
            r"^def get_account\b.*?(?=^def\s)",
            broker_source,
            flags=re.DOTALL | re.MULTILINE,
        ).group(0),
        "position_account_filter": "pos.account" in re.search(
            r"^def get_open_position\b.*",
            broker_source,
            flags=re.DOTALL | re.MULTILINE,
        ).group(0),
        "position_model_filter": "modelCode" in re.search(
            r"^def get_open_position\b.*",
            broker_source,
            flags=re.DOTALL | re.MULTILINE,
        ).group(0),
        "position_contract_id_filter": "conId" in re.search(
            r"^def get_open_position\b.*",
            broker_source,
            flags=re.DOTALL | re.MULTILINE,
        ).group(0),
        "order_account_assignment": bool(
            re.search(r"\.account\s*=", broker_source)
        ),
        "order_model_assignment": bool(
            re.search(r"\.modelCode\s*=", broker_source)
        ),
    }

    account_a = dict(
        label="account_A",
        net_liquidation=100000.0,
        cash=50000.0,
        buying_power=200000.0,
    )
    account_b = dict(
        label="account_B",
        net_liquidation=1000000.0,
        cash=500000.0,
        buying_power=2000000.0,
    )

    def current_summary(rows: List[Dict[str, object]]) -> Dict[str, float]:
        values: Dict[str, float] = {}
        for row in rows:
            if row["tag"] in (
                "NetLiquidation",
                "TotalCashValue",
                "BuyingPower",
            ):
                values[str(row["tag"])] = float(row["value"])
        return dict(
            equity=values.get("NetLiquidation", 0.0),
            cash=values.get("TotalCashValue", 0.0),
            buying_power=values.get("BuyingPower", 0.0),
        )

    def summary_rows(account: Dict[str, object]) -> List[Dict[str, object]]:
        return [
            dict(
                account=account["label"],
                currency="USD",
                tag="NetLiquidation",
                value=account["net_liquidation"],
            ),
            dict(
                account=account["label"],
                currency="USD",
                tag="TotalCashValue",
                value=account["cash"],
            ),
            dict(
                account=account["label"],
                currency="USD",
                tag="BuyingPower",
                value=account["buying_power"],
            ),
        ]

    summary_a_then_b = current_summary(
        summary_rows(account_a) + summary_rows(account_b)
    )
    summary_b_then_a = current_summary(
        summary_rows(account_b) + summary_rows(account_a)
    )
    signal_price = 100.0
    selected_qty_a_then_b = int(
        summary_a_then_b["equity"] * 0.10 / signal_price
    )
    selected_qty_b_then_a = int(
        summary_b_then_a["equity"] * 0.10 / signal_price
    )
    intended_a_qty = int(
        float(account_a["net_liquidation"]) * 0.10 / signal_price
    )

    positions = [
        dict(
            account="account_A",
            model="",
            symbol="TQQQ",
            con_id=111,
            qty=100,
            avg_cost=80.0,
        ),
        dict(
            account="account_B",
            model="",
            symbol="TQQQ",
            con_id=111,
            qty=-40,
            avg_cost=82.0,
        ),
    ]

    def current_first_position(
        rows: List[Dict[str, object]],
    ) -> Optional[Dict[str, object]]:
        for row in rows:
            if row["symbol"] == "TQQQ":
                return dict(
                    qty=int(row["qty"]),
                    avg_price=float(row["avg_cost"]),
                    market_value=float(row["qty"] * row["avg_cost"]),
                )
        return None

    first_a = current_first_position(positions)
    first_b = current_first_position(list(reversed(positions)))

    archive_dir = os.path.join(
        REPO,
        "data",
        "live_runs",
        "archive_2026-06-18_pre_clean_run",
    )
    archive_files = [
        "monitor_events.jsonl",
        "trades.jsonl",
        "position_snapshot.json",
        "account_snapshot.json",
        "metadata.json",
    ]
    archive_text_parts = []
    for name in archive_files:
        with open(os.path.join(archive_dir, name)) as fh:
            archive_text_parts.append(fh.read())
    archive_text = "\n".join(archive_text_parts)
    archive_scope_patterns = {
        pattern: len(re.findall(pattern, archive_text, flags=re.IGNORECASE))
        for pattern in (
            r'"account(?:_id|_code)?"',
            r'"model(?:_code)?"',
            r'"con_?id"',
            r'"perm_?id"',
        )
    }

    return dict(
        scope=(
            "Read-only source/archive audit plus deterministic mock account "
            "ordering. Synthetic account labels are placeholders, not real "
            "account IDs. No live module is imported, broker contacted, order "
            "submitted, secret read, or protected path modified."
        ),
        current_source_sha256=source_hashes,
        source_contract_tokens=token_audit,
        current_identity_contract=dict(
            account_scope_tokens=account_scope_tokens,
            account_scope_fields_present=sum(
                account_scope_tokens.values()
            ),
            account_summary_selection="last row per tag wins",
            position_selection="first row whose contract.symbol matches",
            explicit_order_destination=False,
            state_position_retains_account=False,
            state_trade_retains_account=False,
            monitor_events_retain_account=False,
        ),
        deterministic_account_summary_ordering=dict(
            synthetic_accounts=[account_a, account_b],
            a_then_b_selected=summary_a_then_b,
            b_then_a_selected=summary_b_then_a,
            result_depends_on_callback_order=(
                summary_a_then_b != summary_b_then_a
            ),
            sizing_case=dict(
                signal_price=signal_price,
                intended_destination_assumption=(
                    "If the broker routes the unscoped order to account_A"
                ),
                intended_account_a_qty=intended_a_qty,
                a_then_b_selected_qty=selected_qty_a_then_b,
                b_then_a_selected_qty=selected_qty_b_then_a,
                maximum_qty_multiple_vs_account_a=round(
                    selected_qty_a_then_b / intended_a_qty,
                    6,
                ),
                maximum_notional_pct_of_account_a=round(
                    (
                        selected_qty_a_then_b * signal_price
                        / float(account_a["net_liquidation"])
                    ) * 100.0,
                    6,
                ),
                caveat=(
                    "This conditional scale counterexample does not identify "
                    "the current Gateway account structure or actual destination."
                ),
            ),
        ),
        deterministic_position_ordering=dict(
            synthetic_positions=positions,
            a_first_result=first_a,
            b_first_result=first_b,
            result_depends_on_callback_order=first_a != first_b,
            direction_can_flip=(first_a["qty"] > 0 and first_b["qty"] < 0),
            account_identity_returned=False,
            model_identity_returned=False,
            contract_identity_returned=False,
            consequence=(
                "The same broker holdings can be reported as long 100 or "
                "short 40 solely from row order, without telling the caller "
                "which account supplied the result."
            ),
        ),
        archive_observability=dict(
            inspected_files=archive_files,
            account_model_identity_pattern_counts=archive_scope_patterns,
            account_or_model_scope_retained=False,
            current_gateway_managed_account_count_known=False,
            caveat=(
                "Sanitization correctly excludes account identifiers. Their "
                "absence means this repository cannot determine whether the "
                "multi-account condition occurred historically."
            ),
        ),
        current_test_boundary=dict(
            one_position_row=True,
            one_value_per_account_summary_tag=True,
            multiple_accounts_different_order=False,
            account_currency_filter=False,
            model_specific_position=False,
            explicit_order_destination=False,
            state_to_execution_account_identity=False,
        ),
        external_primary_sources={
            "ibkr_account_updates_multi": (
                "https://interactivebrokers.github.io/tws-api/"
                "account_updates.html"
            ),
            "ibkr_account_and_position_callback_identity": (
                "https://interactivebrokers.github.io/tws-api/"
                "interfaceIBApi_1_1EWrapper.html"
            ),
            "ibkr_model_portfolios": (
                "https://interactivebrokers.github.io/tws-api/"
                "model_portfolios.html"
            ),
            "ibkr_position_multi": (
                "https://interactivebrokers.github.io/tws-api/"
                "classIBApi_1_1EClientSocket.html"
            ),
        },
        falsification_gate=[
            (
                "Configure one explicit paper account and optional model code "
                "outside source control; fail closed unless Gateway managed "
                "accounts exactly match the authorized identity."
            ),
            (
                "Filter account values by account, currency, and model; reject "
                "duplicates/missing tags rather than allowing callback order "
                "to select sizing capital."
            ),
            (
                "Filter positions by account/model and qualified contract "
                "identity, aggregate only when that is the declared policy, "
                "and return the identity with every reconciliation result."
            ),
            (
                "Set account/model on parent, children, and forced-close orders; "
                "persist the same scope through lifecycle, execution, state, "
                "events, and sanitized hashed pseudonyms."
            ),
            (
                "Test two-account opposite TQQQ positions and callback-order "
                "permutations, including a tenfold equity difference."
            ),
        ],
        limitations=[
            (
                "A normal individual paper login may expose exactly one account, "
                "in which case the counterexample is dormant."
            ),
            (
                "The study intentionally does not inspect credentials, account "
                "IDs, Gateway UI state, or any unsanitized operational database."
            ),
            (
                "The tenfold sizing case is conditional arithmetic, not a claim "
                "about current capital, holdings, or order routing."
            ),
        ],
        decision=(
            "Broker account identity is an implicit environmental assumption, "
            "not an enforced invariant. Account summary drops account/currency "
            "and uses last-row-wins tags; position reconciliation drops account, "
            "model, and contract ID and returns the first symbol match; orders "
            "set no destination; state retains none. With synthetic 100k and "
            "1m accounts, callback order alone changes sizing from 100 to 1000 "
            "shares at $100; if the unscoped order routes to the 100k account, "
            "that is 100% rather than 10% notional. Opposite TQQQ positions can "
            "likewise report long 100 or short 40 by row order. The repository "
            "cannot tell whether this condition exists because sanitized records "
            "correctly omit account IDs. Enforce one authorized pseudonymous "
            "account/model identity end to end and fail closed on ambiguity."
        ),
    )


def duplicate_writer_hold_counter_materiality() -> Dict[str, object]:
    """Measure duplicate-cycle compression of the archived holding counter."""
    source_paths = [
        "live/state.py",
        "live/trader.py",
        "tests/test_state.py",
        "tests/test_trader_flow.py",
    ]
    source_text: Dict[str, str] = {}
    source_hashes: Dict[str, str] = {}
    for relative in source_paths:
        path = os.path.join(REPO, relative)
        with open(path, "rb") as fh:
            raw = fh.read()
        source_hashes[relative] = hashlib.sha256(raw).hexdigest()
        source_text[relative] = raw.decode("utf-8")

    required_tokens = {
        "live/state.py": [
            "def increment_bar_count() -> int:",
            "UPDATE position SET bar_count = bar_count + 1",
            "SELECT bar_count FROM position LIMIT 1",
        ],
        "live/trader.py": [
            "bar_count = state.increment_bar_count()",
            "elif bar_count >= config.MAX_TRADE_BARS_LIVE:",
            'exit_action = "exit_time_exit"',
        ],
        "tests/test_trader_flow.py": [
            "mstate.increment_bar_count.return_value = 3",
            "mstate.increment_bar_count.return_value = 10",
        ],
    }
    token_audit = {
        path: {token: token in source_text[path] for token in tokens}
        for path, tokens in required_tokens.items()
    }
    if not all(
        present
        for checks in token_audit.values()
        for present in checks.values()
    ):
        raise AssertionError("holding-counter source contract changed")

    with tempfile.TemporaryDirectory(
        prefix="monad_duplicate_bar_counter_"
    ) as tmp_dir:
        db_path = os.path.join(tmp_dir, "counter.db")
        seed = sqlite3.connect(db_path)
        seed.execute(
            "CREATE TABLE position (id INTEGER PRIMARY KEY, bar_count INTEGER)"
        )
        seed.execute("INSERT INTO position VALUES (1, 0)")
        seed.commit()
        seed.close()

        writer_a = sqlite3.connect(db_path)
        writer_b = sqlite3.connect(db_path)
        writer_a.execute(
            "UPDATE position SET bar_count = bar_count + 1"
        )
        writer_a.commit()
        after_a = int(
            writer_a.execute(
                "SELECT bar_count FROM position"
            ).fetchone()[0]
        )
        writer_b.execute(
            "UPDATE position SET bar_count = bar_count + 1"
        )
        writer_b.commit()
        after_b = int(
            writer_b.execute(
                "SELECT bar_count FROM position"
            ).fetchone()[0]
        )
        writer_a.close()
        writer_b.close()

    archive_dir = os.path.join(
        REPO,
        "data",
        "live_runs",
        "archive_2026-06-18_pre_clean_run",
    )

    def load_jsonl(name: str) -> List[Dict[str, object]]:
        rows = []
        with open(os.path.join(archive_dir, name)) as fh:
            for line in fh:
                if line.strip():
                    rows.append(json.loads(line))
        return rows

    with open(os.path.join(archive_dir, "metadata.json")) as fh:
        metadata = json.load(fh)
    archive_trades = load_jsonl("trades.jsonl")
    signal_history = load_jsonl("signal_history.jsonl")
    time_exit_trades = [
        row for row in archive_trades
        if row.get("exit_type") == "time_exit"
    ]

    interval_rows = []
    for trade in time_exit_trades:
        entry_time = pd.Timestamp(trade["entry_time"])
        exit_time = pd.Timestamp(trade["exit_time"])
        interval_signals = [
            row for row in signal_history
            if (
                pd.Timestamp(row["updated_at"]) > entry_time
                and pd.Timestamp(row["updated_at"]) <= exit_time
            )
        ]
        slot_counts: Dict[str, int] = {}
        for row in interval_signals:
            slot = pd.Timestamp(row["updated_at"]).floor("min").isoformat()
            slot_counts[slot] = slot_counts.get(slot, 0) + 1
        distinct_slots = len(slot_counts)
        signal_rows = len(interval_signals)
        bars_held = int(trade["bars_held"])
        exact_double_attribution = (
            signal_rows == bars_held
            and distinct_slots * 2 == signal_rows
            and all(count == 2 for count in slot_counts.values())
        )
        interval_rows.append(
            dict(
                entry_time=trade["entry_time"],
                exit_time=trade["exit_time"],
                wall_clock_hours=round(
                    (exit_time - entry_time).total_seconds() / 3600.0,
                    6,
                ),
                recorded_bars_held=bars_held,
                signal_history_rows=signal_rows,
                distinct_cycle_minute_slots=distinct_slots,
                writes_per_slot=sorted(slot_counts.values()),
                nominal_to_distinct_slot_ratio=round(
                    bars_held / distinct_slots, 6
                ) if distinct_slots else None,
                exact_two_writes_per_slot=(
                    bool(slot_counts)
                    and all(
                        count == 2 for count in slot_counts.values()
                    )
                ),
                strict_exact_double_attribution=(
                    exact_double_attribution
                ),
                compressed_below_ten_distinct_slots=distinct_slots < bars_held,
                return_pct=round(
                    float(trade["return_pct"]) * 100.0, 6
                ),
            )
        )

    strict_rows = [
        row for row in interval_rows
        if row["strict_exact_double_attribution"]
    ]
    compressed_rows = [
        row for row in interval_rows
        if row["compressed_below_ten_distinct_slots"]
    ]
    exact_half_rows = [
        row for row in interval_rows
        if (
            row["recorded_bars_held"] == 10
            and row["distinct_cycle_minute_slots"] == 5
            and row["strict_exact_double_attribution"]
        )
    ]

    return dict(
        scope=(
            "Read-only source/sanitized-archive audit plus temporary SQLite "
            "increment proof. No live module is imported, no broker is contacted, "
            "and no protected path or operational database is modified."
        ),
        current_source_sha256=source_hashes,
        source_contract_tokens=token_audit,
        archived_source_identity=dict(
            archive_id=metadata["archive_id"],
            git_branch=metadata["git_branch"],
            git_commit=metadata["git_commit"],
            note=(
                "Study 48 previously verified the archived code at this commit; "
                "the increment/check tokens remain identical in current source."
            ),
        ),
        counter_contract=dict(
            initial_bar_count=0,
            increment_granularity="one per admitted trader invocation",
            distinct_bar_or_cycle_identity_required=False,
            atomic_symbol_bar_claim=False,
            exit_threshold=10,
            duplicate_writers_same_logical_slot_count_twice=True,
        ),
        deterministic_two_writer_increment=dict(
            initial_bar_count=0,
            after_writer_a=after_a,
            after_writer_b=after_b,
            logical_cycle_slots=1,
            recorded_bar_count=after_b,
            inflation_factor=round(after_b / 1.0, 6),
            reachability_proved=(after_a == 1 and after_b == 2),
        ),
        archived_time_exit_intervals=dict(
            rows=interval_rows,
            time_exit_trades=len(interval_rows),
            all_recorded_at_ten_bars=all(
                row["recorded_bars_held"] == 10
                for row in interval_rows
            ),
            compressed_below_ten_distinct_slots=len(compressed_rows),
            at_most_six_distinct_slots=sum(
                row["distinct_cycle_minute_slots"] <= 6
                for row in interval_rows
            ),
            strict_exact_double_intervals=len(strict_rows),
            exact_five_slot_half_holds=len(exact_half_rows),
            distinct_slot_counts=[
                row["distinct_cycle_minute_slots"]
                for row in interval_rows
            ],
            median_distinct_cycle_slots=float(
                np.median(
                    [
                        row["distinct_cycle_minute_slots"]
                        for row in interval_rows
                    ]
                )
            ),
            strict_wall_clock_hours=dict(
                min=round(
                    min(row["wall_clock_hours"] for row in strict_rows),
                    6,
                ),
                median=round(
                    float(
                        np.median(
                            [
                                row["wall_clock_hours"]
                                for row in strict_rows
                            ]
                        )
                    ),
                    6,
                ),
                max=round(
                    max(row["wall_clock_hours"] for row in strict_rows),
                    6,
                ),
            ),
            all_time_exit_returns_positive=all(
                row["return_pct"] > 0 for row in interval_rows
            ),
            causal_pnl_effect_identified=False,
            attribution_rule=(
                "Strict only when the interval has exactly ten signal-history "
                "rows, exactly five distinct minute slots, every slot has two "
                "writes, and the trade records bars_held=10."
            ),
        ),
        interpretation=dict(
            observed=(
                "Seven of nine time exits have an exact 10 counter increments "
                "mapped to five double-written cycle minutes; eight of nine "
                "reach bar 10 in fewer than ten distinct archived slots."
            ),
            not_identified=(
                "What the position would have returned after ten unique bars, "
                "because it might have hit a bracket boundary before then."
            ),
            distinction=(
                "The study proves holding-clock compression in local state, "
                "not duplicate broker orders or a counterfactual PnL sign."
            ),
        ),
        current_test_boundary=dict(
            one_increment_returns_value=True,
            threshold_ten_triggers_time_exit=True,
            two_writers_same_bar=False,
            distinct_bar_idempotency=False,
            archive_counter_reconstruction=False,
        ),
        falsification_gate=[
            (
                "Persist one canonical exchange bar/session-cycle ID on the "
                "position and increment only through a conditional update when "
                "the incoming completed-bar ID is strictly newer."
            ),
            (
                "Make symbol+lifecycle+bar transition unique so concurrent "
                "writers cannot both claim the same holding observation."
            ),
            (
                "Define MAX_TRADE_BARS as distinct completed bars rather than "
                "process invocations and test duplicate/retry/holiday schedules."
            ),
            (
                "For historical materiality, obtain broker/order evidence or "
                "replay lower-timeframe prices before assigning a PnL delta to "
                "the extra five bars."
            ),
        ],
        limitations=[
            (
                "Signal-history writes identify trader invocations but do not "
                "carry PID/cycle IDs; the strict rule avoids intervals with any "
                "extra or missing writes."
            ),
            (
                "All nine recorded time exits were profitable, but that does "
                "not reveal whether a ten-unique-bar hold would improve or worsen "
                "them because TP/SL execution is path-dependent."
            ),
            (
                "Current singleton preflight was added after the archive and "
                "reduces recurrence, but still does not make the counter itself "
                "bar-idempotent."
            ),
        ],
        decision=(
            "The historical duplicate writer materially compressed holding "
            "duration. bar_count increments once per trader invocation with no "
            "bar identity; two writers therefore turn one logical cycle into two "
            "bars. In the sanitized archive, all nine time exits record bar 10; "
            "seven map exactly to ten signal writes across five minute slots, "
            "each slot written twice, and eight exit in fewer than ten distinct "
            "slots. This proves premature local time-exit triggering relative "
            "to ten unique cycles, not its PnL effect. Replace invocation counting "
            "with a unique lifecycle+completed-bar transition."
        ),
    )


def broker_quote_field_precedence_audit(
    five_min: Optional[pd.DataFrame],
) -> Dict[str, object]:
    """Audit whether quote selection proves a current executable price."""
    source_paths = [
        "live/broker.py",
        "requirements.txt",
        "tests/test_broker.py",
    ]
    source_text: Dict[str, str] = {}
    source_hashes: Dict[str, str] = {}
    for relative in source_paths:
        path = os.path.join(REPO, relative)
        with open(path, "rb") as fh:
            raw = fh.read()
        source_hashes[relative] = hashlib.sha256(raw).hexdigest()
        source_text[relative] = raw.decode("utf-8")

    required_tokens = {
        "live/broker.py": [
            "def get_tradeable_price(symbol: str) -> float:",
            'for attr in ("last", "close", "bid", "ask"):',
            "mp = ticker.marketPrice()",
            "ib.reqMarketDataType(3)",
            "[delayed] = ib.reqTickers(contract)",
            "ib.reqMarketDataType(1)",
            "limit_price  = round(live_price * 1.005, 2)",
            "stop_price   = round(live_price * (1 - stop_pct), 2)",
        ],
        "requirements.txt": ["ib-insync==0.9.86"],
        "tests/test_broker.py": [
            'mock.patch.object(broker, "get_tradeable_price", return_value=100.0)',
            "def test_no_tradeable_price_returns_none(self):",
        ],
    }
    token_audit = {
        path: {token: token in source_text[path] for token in tokens}
        for path, tokens in required_tokens.items()
    }
    if not all(
        present
        for checks in token_audit.values()
        for present in checks.values()
    ):
        raise AssertionError("broker quote-selection source contract changed")

    price_match = re.search(
        r"^def get_tradeable_price\b.*?(?=^def\s)",
        source_text["live/broker.py"],
        flags=re.MULTILINE | re.DOTALL,
    )
    if price_match is None:
        raise AssertionError("could not isolate get_tradeable_price")
    price_source = price_match.group(0)

    def valid(value: object) -> bool:
        try:
            return (
                value is not None
                and math.isfinite(float(value))
                and float(value) > 0
            )
        except (TypeError, ValueError):
            return False

    def current_selector(
        fields: Dict[str, object],
    ) -> Dict[str, object]:
        for field in ("last", "close", "bid", "ask"):
            value = fields.get(field)
            if valid(value):
                return dict(field=field, price=float(value))
        market_price = fields.get("market_price")
        if valid(market_price):
            return dict(field="marketPrice", price=float(market_price))
        return dict(field=None, price=None)

    def dependency_market_price(
        fields: Dict[str, object],
    ) -> float:
        bid = float(fields["bid"])
        ask = float(fields["ask"])
        last_value = fields.get("last")
        has_bid_ask = (
            valid(bid)
            and valid(ask)
            and float(fields.get("bid_size", 0)) > 0
            and float(fields.get("ask_size", 0)) > 0
        )
        if has_bid_ask:
            if (
                valid(last_value)
                and bid <= float(last_value) <= ask
            ):
                return float(last_value)
            return (bid + ask) / 2.0
        return (
            float(last_value)
            if valid(last_value)
            else float("nan")
        )

    scenario_fields = {
        "prior_close_preempts_current_spread": dict(
            last=None,
            close=100.0,
            bid=109.9,
            ask=110.1,
            bid_size=100,
            ask_size=100,
            market_price=110.0,
        ),
        "high_out_of_spread_last_preempts_midpoint": dict(
            last=120.0,
            close=100.0,
            bid=109.9,
            ask=110.1,
            bid_size=100,
            ask_size=100,
            market_price=110.0,
        ),
        "low_out_of_spread_last_preempts_midpoint": dict(
            last=100.0,
            close=95.0,
            bid=109.9,
            ask=110.1,
            bid_size=100,
            ask_size=100,
            market_price=110.0,
        ),
    }

    deterministic_rows = []
    for name, fields in scenario_fields.items():
        selected = current_selector(fields)
        quote = float(selected["price"])
        midpoint = dependency_market_price(fields)
        long_parent = round(quote * 1.005, 2)
        long_target = round(quote * 1.01, 2)
        long_stop = round(quote * 0.995, 2)
        short_parent = round(quote * 0.995, 2)
        short_target = round(quote * 0.99, 2)
        short_stop = round(quote * 1.005, 2)
        deterministic_rows.append(
            dict(
                scenario=name,
                fields=fields,
                selected_field=selected["field"],
                selected_price=quote,
                dependency_market_price=midpoint,
                selected_minus_market_price_bps=round(
                    (quote / midpoint - 1.0) * 10000.0,
                    6,
                ),
                long=dict(
                    parent_limit=long_parent,
                    target=long_target,
                    stop=long_stop,
                    parent_limit_minus_ask_bps=round(
                        (
                            long_parent / float(fields["ask"])
                            - 1.0
                        ) * 10000.0,
                        6,
                    ),
                    parent_marketable_at_ask=(
                        long_parent >= float(fields["ask"])
                    ),
                    stop_already_crossed_at_midpoint=(
                        midpoint <= long_stop
                    ),
                    stop_minus_midpoint_bps=round(
                        (long_stop / midpoint - 1.0) * 10000.0,
                        6,
                    ),
                ),
                short=dict(
                    parent_limit=short_parent,
                    target=short_target,
                    stop=short_stop,
                    parent_marketable_at_bid=(
                        short_parent <= float(fields["bid"])
                    ),
                    stop_already_crossed_at_midpoint=(
                        midpoint >= short_stop
                    ),
                    stop_minus_midpoint_bps=round(
                        (short_stop / midpoint - 1.0) * 10000.0,
                        6,
                    ),
                ),
            )
        )

    with open(QUOTE_STALENESS_AUDIT) as fh:
        durable = json.load(fh)

    def lag_row(
        panel: pd.DataFrame,
        minutes: int,
    ) -> Dict[str, object]:
        close = panel["close"].astype(float)
        future = close.reindex(
            close.index + pd.Timedelta(minutes=minutes)
        )
        future.index = close.index
        returns = (future / close - 1.0).dropna()
        absolute = returns.abs()
        return dict(
            minutes=minutes,
            pairs=int(len(returns)),
            mean_bps=round(float(returns.mean() * 10000.0), 6),
            median_abs_bps=round(
                float(absolute.median() * 10000.0), 6
            ),
            p90_abs_bps=round(
                float(absolute.quantile(0.90) * 10000.0), 6
            ),
            p95_abs_bps=round(
                float(absolute.quantile(0.95) * 10000.0), 6
            ),
            p99_abs_bps=round(
                float(absolute.quantile(0.99) * 10000.0), 6
            ),
            maximum_abs_bps=round(
                float(absolute.max() * 10000.0), 6
            ),
            moves_up_over_50bps=int((returns > 0.005).sum()),
            moves_down_over_50bps=int((returns < -0.005).sum()),
            moves_abs_over_50bps=int((absolute > 0.005).sum()),
            pct_abs_over_50bps=round(
                float((absolute > 0.005).mean() * 100.0), 6
            ),
            minimum_move_pct=round(
                float(returns.min() * 100.0), 6
            ),
            maximum_move_pct=round(
                float(returns.max() * 100.0), 6
            ),
            minimum_start_time=returns.idxmin().isoformat(),
            maximum_start_time=returns.idxmax().isoformat(),
        )

    def prior_close_cycle_row(
        panel: pd.DataFrame,
    ) -> Dict[str, object]:
        local = panel.copy()
        local.index = local.index.tz_convert(TZ)
        local["session"] = local.index.date
        session_close = local.groupby("session")["close"].last()
        prior_close = session_close.shift(1)
        local["prior_close"] = [
            prior_close.get(session, np.nan)
            for session in local["session"]
        ]
        returns = (
            local["open"].astype(float)
            / local["prior_close"].astype(float)
            - 1.0
        ).dropna()
        returns = returns.loc[returns.index.minute == 30]
        absolute = returns.abs()
        return dict(
            pairs=int(len(returns)),
            moves_up_over_50bps=int((returns > 0.005).sum()),
            moves_down_over_50bps=int((returns < -0.005).sum()),
            moves_abs_over_50bps=int((absolute > 0.005).sum()),
            pct_abs_over_50bps=round(
                float((absolute > 0.005).mean() * 100.0), 6
            ),
            median_abs_bps=round(
                float(absolute.median() * 10000.0), 6
            ),
            p90_abs_bps=round(
                float(absolute.quantile(0.90) * 10000.0), 6
            ),
            minimum_move_pct=round(
                float(returns.min() * 100.0), 6
            ),
            maximum_move_pct=round(
                float(returns.max() * 100.0), 6
            ),
        )

    def archive_overlap(
        panel: pd.DataFrame,
    ) -> Dict[str, object]:
        archive_path = os.path.join(
            REPO,
            "data",
            "live_runs",
            "archive_2026-06-18_pre_clean_run",
            "monitor_events.jsonl",
        )
        with open(archive_path) as fh:
            events = [
                json.loads(line) for line in fh if line.strip()
            ]
        rows = []
        for event in events:
            match = re.search(
                r"Entry placed:.*@ ([0-9]+(?:\.[0-9]+)?)",
                str(event.get("message", "")),
            )
            if match is None:
                continue
            event_time = pd.Timestamp(event["event_time"]).tz_convert("UTC")
            slot = event_time.floor("5min")
            if slot not in panel.index:
                continue
            quote = float(match.group(1))
            bar = panel.loc[slot]
            prior_15 = panel.loc[
                slot - pd.Timedelta(minutes=15)
            ]
            prior_20 = panel.loc[
                slot - pd.Timedelta(minutes=20)
            ]
            parent_limit = round(quote * 1.005, 2)
            rows.append(
                dict(
                    event_time=event["event_time"],
                    quote=quote,
                    bar_time=slot.isoformat(),
                    current_bar_open=round(float(bar["open"]), 6),
                    quote_vs_current_bar_open_bps=round(
                        (
                            quote / float(bar["open"]) - 1.0
                        ) * 10000.0,
                        6,
                    ),
                    quote_in_current_5m_range=bool(
                        float(bar["low"])
                        <= quote
                        <= float(bar["high"])
                    ),
                    quote_in_15m_ago_range=bool(
                        float(prior_15["low"])
                        <= quote
                        <= float(prior_15["high"])
                    ),
                    quote_in_20m_ago_range=bool(
                        float(prior_20["low"])
                        <= quote
                        <= float(prior_20["high"])
                    ),
                    long_parent_limit=parent_limit,
                    parent_limit_minus_bar_open_bps=round(
                        (
                            parent_limit / float(bar["open"])
                            - 1.0
                        ) * 10000.0,
                        6,
                    ),
                    parent_marketable_on_bar_open_proxy=bool(
                        parent_limit >= float(bar["open"])
                    ),
                )
            )
        return dict(
            matched_entry_events=len(rows),
            quote_in_current_5m_range=sum(
                row["quote_in_current_5m_range"] for row in rows
            ),
            quote_in_15m_ago_range=sum(
                row["quote_in_15m_ago_range"] for row in rows
            ),
            quote_in_20m_ago_range=sum(
                row["quote_in_20m_ago_range"] for row in rows
            ),
            long_parent_marketable_on_bar_open_proxy=sum(
                row["parent_marketable_on_bar_open_proxy"]
                for row in rows
            ),
            rows=rows,
            interpretation=(
                "All three quotes are compatible with the 15-minute-ago "
                "bar range, but compatibility does not identify quote age "
                "or field; one is also in the contemporaneous bar range and "
                "one in the 20-minute-ago range."
            ),
        )

    raw_sha = _sha256_file(FIVE_MIN_CACHE)
    used_durable_fallback = five_min is None
    if five_min is not None:
        if raw_sha != FIVE_MIN_SOURCE_SHA256:
            raise AssertionError("five-minute source hash changed")
        panel = five_min.copy()
        panel.index = panel.index.tz_convert("UTC")
        calculated_lags = {
            "15": lag_row(panel, 15),
            "20": lag_row(panel, 20),
        }
        calculated_prior = prior_close_cycle_row(panel)
        calculated_overlap = archive_overlap(panel)
        if calculated_lags != durable["lag_windows"]:
            raise AssertionError("durable lag-window summary drifted")
        if calculated_prior != durable[
            "prior_close_hourly_cycle_proxy"
        ]:
            raise AssertionError("durable prior-close summary drifted")
        if calculated_overlap != durable["archive_entry_overlap"]:
            raise AssertionError("durable archive-overlap summary drifted")

    lag_windows = durable["lag_windows"]
    prior_close = durable["prior_close_hourly_cycle_proxy"]
    archived_overlap = durable["archive_entry_overlap"]
    long_15_boundary = (
        lag_windows["15"]["moves_abs_over_50bps"]
        / lag_windows["15"]["pairs"]
        * 100.0
    )
    long_20_boundary = (
        lag_windows["20"]["moves_abs_over_50bps"]
        / lag_windows["20"]["pairs"]
        * 100.0
    )

    return dict(
        scope=(
            "Read-only source, dependency-contract, pinned five-minute, and "
            "sanitized-archive audit. No live module is imported, broker "
            "contacted, order submitted, or protected path changed."
        ),
        current_source_sha256=source_hashes,
        source_contract_tokens=token_audit,
        current_selection_contract=dict(
            live_field_precedence=["last", "close", "bid", "ask"],
            delayed_field_precedence=["last", "close", "bid", "ask"],
            close_preempts_available_bid_ask=True,
            positive_last_preempts_market_price=True,
            last_timestamp_checked=False,
            ticker_snapshot_time_checked=(
                "ticker.time" in price_source
            ),
            bid_ask_sizes_checked=(
                "bidSize" in price_source
                or "askSize" in price_source
            ),
            halted_state_checked="halted" in price_source,
            market_data_type_callback_checked=(
                ".marketDataType" in price_source
            ),
            delayed_data_accepted_for_order_placement=True,
            snapshot_sleep_after_blocking_return_count=len(
                re.findall(
                    r"reqTickers\(contract\)\s*\n\s*ib\.sleep\(2\)",
                    price_source,
                )
            ),
            selected_field_or_data_type_persisted=False,
        ),
        dependency_contract=dict(
            pinned_ib_insync_version="0.9.86",
            req_tickers_is_blocking_snapshot=True,
            snapshot_ends_before_return=True,
            market_price_rule=(
                "last only when within a valid positive-size bid/ask; "
                "otherwise midpoint; last only when no valid spread"
            ),
            current_code_reaches_market_price_only_when_last_close_bid_ask_all_invalid=(
                True
            ),
        ),
        deterministic_precedence_counterexamples=dict(
            rows=deterministic_rows,
            close_case_selected_price=deterministic_rows[0][
                "selected_price"
            ],
            close_case_market_price=deterministic_rows[0][
                "dependency_market_price"
            ],
            close_case_long_parent_below_ask_bps=round(
                -deterministic_rows[0]["long"][
                    "parent_limit_minus_ask_bps"
                ],
                6,
            ),
            high_last_case_long_stop_already_crossed=(
                deterministic_rows[1]["long"][
                    "stop_already_crossed_at_midpoint"
                ]
            ),
            high_last_case_long_stop_above_midpoint_bps=(
                deterministic_rows[1]["long"][
                    "stop_minus_midpoint_bps"
                ]
            ),
            low_last_case_short_stop_already_crossed=(
                deterministic_rows[2]["short"][
                    "stop_already_crossed_at_midpoint"
                ]
            ),
        ),
        pinned_five_min_materiality=dict(
            durable_summary=os.path.relpath(
                QUOTE_STALENESS_AUDIT, REPO
            ),
            source=durable["source"],
            observed_runtime_cache_sha256=raw_sha,
            used_durable_fallback=used_durable_fallback,
            lag_windows=lag_windows,
            current_long_boundary_interpretation=dict(
                threshold_bps=50.0,
                fifteen_minute_pct_parent_or_stop_geometry_crossed=round(
                    long_15_boundary, 6
                ),
                twenty_minute_pct_parent_or_stop_geometry_crossed=round(
                    long_20_boundary, 6
                ),
                rule=(
                    "A >+0.5% move can leave the stale-quote buy limit "
                    "below the current market; a <-0.5% move can place "
                    "the stale-quote sell stop above the current market."
                ),
            ),
            prior_close_hourly_cycle_proxy=prior_close,
            caveat=(
                "Five-minute OHLC closes/opens are coarse price proxies, "
                "not IBKR snapshots, spreads, executions, or future rates."
            ),
        ),
        archive_observability=dict(
            **archived_overlap,
            selected_quote_field_retained=False,
            market_data_type_retained=False,
            quote_timestamp_retained=False,
            exact_quote_age_identified=False,
            actual_entry_fill_retained=False,
        ),
        current_test_boundary=dict(
            direct_price_selector_invocation=False,
            close_with_valid_bid_ask=False,
            last_outside_spread=False,
            delayed_type_confirmation=False,
            quote_timestamp_age=False,
            stale_quote_order_geometry=False,
            place_bracket_math_with_mocked_quote=True,
        ),
        external_primary_sources={
            "ibkr_current_tws_api_documentation": (
                "https://ibkrcampus.com/campus/ibkr-api-page/"
                "twsapi-doc/"
            ),
            "ibkr_tick_types": (
                "https://interactivebrokers.github.io/tws-api/"
                "tick_types.html"
            ),
            "ibkr_market_data_types": (
                "https://interactivebrokers.github.io/tws-api/"
                "market_data_type.html"
            ),
            "ibkr_snapshot_requests": (
                "https://interactivebrokers.github.io/tws-api/"
                "md_request.html"
            ),
            "ib_insync_req_tickers_source": (
                "https://ib-insync.readthedocs.io/_modules/"
                "ib_insync/ib.html"
            ),
            "ib_insync_market_price_source": (
                "https://ib-insync.readthedocs.io/_modules/"
                "ib_insync/ticker.html"
            ),
        },
        falsification_gate=[
            (
                "Require the callback-confirmed market-data type and reject "
                "delayed/frozen data for order construction unless a separately "
                "approved bounded policy exists."
            ),
            (
                "Require a timestamped current bid/ask with positive sizes and "
                "an age/spread bound; use side-aware ask for buys and bid for "
                "sells rather than prior close or unconstrained last."
            ),
            (
                "Reject last outside the valid spread and never let prior close "
                "preempt a valid current spread."
            ),
            (
                "Persist quote field, data type, source timestamp, bid/ask/size, "
                "request time, and eventual execution identity for calibration."
            ),
            (
                "Test absent last plus valid spread, out-of-spread last, delayed "
                "callbacks, no permissions, halts, closed sessions, and the "
                "0.5% parent/stop boundary."
            ),
        ],
        limitations=[
            (
                "Deterministic scenarios prove reachable selection and order "
                "geometry, not that a particular archived order used that field."
            ),
            (
                "The recent five-minute panel spans 2026-05-26 through "
                "2026-07-22 and is descriptive, not a future probability model."
            ),
            (
                "Archive overlap has only three entry events in panel coverage; "
                "range compatibility cannot identify whether the source was live, "
                "delayed, last, close, bid, or ask."
            ),
            (
                "Marketability and immediate stop activation are order-book and "
                "venue outcomes; OHLC and midpoint comparisons are explicit "
                "geometry proxies, not execution claims."
            ),
        ],
        decision=(
            "get_tradeable_price does not establish a current executable price. "
            "It accepts the first positive last/close/bid/ask, so prior-day close "
            "can beat a current spread and an out-of-spread last can beat "
            "ib_insync's bid/ask-aware midpoint. It then explicitly accepts "
            "15-20-minute delayed data without retaining type or timestamp. In "
            "the pinned recent TQQQ panel, absolute 15/20-minute close moves exceed "
            "the 0.5% parent/stop offset in 32.13%/36.49% of exact pairs; prior "
            "close differs from hourly-cycle bar open by over 0.5% in 248/273 "
            "cases. Those are coarse stress frequencies, not incident rates. "
            "Require timestamped side-aware live spread evidence and fail closed "
            "on prior-close, delayed, or out-of-spread-last selection."
        ),
    )


def entry_snapshot_latency_audit() -> Dict[str, object]:
    """Measure decision-to-application-entry delay and snapshot duplication."""
    source_paths = [
        "live/broker.py",
        "live/trader.py",
        "requirements.txt",
        "tests/test_broker.py",
        "tests/test_trader_flow.py",
    ]
    source_text: Dict[str, str] = {}
    source_hashes: Dict[str, str] = {}
    for relative in source_paths:
        path = os.path.join(REPO, relative)
        with open(path, "rb") as fh:
            raw = fh.read()
        source_hashes[relative] = hashlib.sha256(raw).hexdigest()
        source_text[relative] = raw.decode("utf-8")

    required_tokens = {
        "live/broker.py": [
            "[ticker] = ib.reqTickers(contract)",
            "[delayed] = ib.reqTickers(contract)",
            "ib.sleep(2)",
            "live_price = get_tradeable_price(symbol)",
        ],
        "live/trader.py": [
            "state.save_signal_snapshot(",
            "if exit_action is None:",
            "_sync_account_and_mark(bar_close=bar_close_fallback)",
            "result = broker.place_bracket_order(",
            'state.add_monitor_event("INFO", "entry", entry_event)',
        ],
        "requirements.txt": ["ib-insync==0.9.86"],
    }
    token_audit = {
        path: {token: token in source_text[path] for token in tokens}
        for path, tokens in required_tokens.items()
    }
    if not all(
        present
        for checks in token_audit.values()
        for present in checks.values()
    ):
        raise AssertionError("entry snapshot-latency source contract changed")

    broker_source = source_text["live/broker.py"]
    trader_source = source_text["live/trader.py"]
    price_match = re.search(
        r"^def get_tradeable_price\b.*?(?=^def\s)",
        broker_source,
        flags=re.MULTILINE | re.DOTALL,
    )
    sync_match = re.search(
        r"^def _sync_account_and_mark\b.*?(?=^def\s)",
        trader_source,
        flags=re.MULTILINE | re.DOTALL,
    )
    resolve_match = re.search(
        r"^def _resolve_mark_price\b.*?(?=^def\s)",
        trader_source,
        flags=re.MULTILINE | re.DOTALL,
    )
    bracket_match = re.search(
        r"^def place_bracket_order\b.*?(?=^def\s)",
        broker_source,
        flags=re.MULTILINE | re.DOTALL,
    )
    if any(
        match is None
        for match in (
            price_match,
            sync_match,
            resolve_match,
            bracket_match,
        )
    ):
        raise AssertionError("could not isolate latency source functions")
    price_source = price_match.group(0)
    sync_source = sync_match.group(0)
    resolve_source = resolve_match.group(0)
    bracket_source = bracket_match.group(0)

    archive_dir = os.path.join(
        REPO,
        "data",
        "live_runs",
        "archive_2026-06-18_pre_clean_run",
    )
    with open(os.path.join(archive_dir, "metadata.json")) as fh:
        metadata = json.load(fh)
    with open(os.path.join(archive_dir, "monitor_events.jsonl")) as fh:
        monitor_events = [
            json.loads(line) for line in fh if line.strip()
        ]
    with open(os.path.join(archive_dir, "signal_history.jsonl")) as fh:
        signal_history = [
            json.loads(line) for line in fh if line.strip()
        ]

    entry_events = [
        event for event in monitor_events
        if "Entry placed:" in str(event.get("message", ""))
    ]
    event_rows = []
    for event in entry_events:
        event_time = pd.Timestamp(event["event_time"])
        schedule_anchor = (
            event_time.floor("h") + pd.Timedelta(minutes=32)
        )
        same_minute_signals = [
            pd.Timestamp(row["updated_at"])
            for row in signal_history
            if (
                pd.Timestamp(row["updated_at"]) <= event_time
                and pd.Timestamp(row["updated_at"]).floor("min")
                == event_time.floor("min")
            )
        ]
        event_rows.append(
            dict(
                event_time=event["event_time"],
                schedule_anchor=schedule_anchor.isoformat(),
                seconds_after_schedule=round(
                    (event_time - schedule_anchor).total_seconds(), 6
                ),
                back_to_back="back-to-back" in event["message"],
                same_minute_signal_candidates=len(same_minute_signals),
                signal_to_entry_lower_seconds=(
                    round(
                        (
                            event_time - max(same_minute_signals)
                        ).total_seconds(),
                        6,
                    )
                    if same_minute_signals else None
                ),
                signal_to_entry_upper_seconds=(
                    round(
                        (
                            event_time - min(same_minute_signals)
                        ).total_seconds(),
                        6,
                    )
                    if same_minute_signals else None
                ),
            )
        )

    def distribution(values: List[float]) -> Dict[str, object]:
        array = np.asarray(values, dtype=float)
        return dict(
            n=int(len(array)),
            min=round(float(np.min(array)), 6),
            p25=round(float(np.quantile(array, 0.25)), 6),
            median=round(float(np.median(array)), 6),
            p75=round(float(np.quantile(array, 0.75)), 6),
            p90=round(float(np.quantile(array, 0.90)), 6),
            p95=round(float(np.quantile(array, 0.95)), 6),
            max=round(float(np.max(array)), 6),
            at_least_20_seconds=int((array >= 20).sum()),
            at_least_30_seconds=int((array >= 30).sum()),
            at_least_40_seconds=int((array >= 40).sum()),
            at_least_50_seconds=int((array >= 50).sum()),
        )

    schedule_values = [
        float(row["seconds_after_schedule"]) for row in event_rows
    ]
    strict_rows = [
        row for row in event_rows
        if row["same_minute_signal_candidates"] > 0
    ]
    lower_values = [
        float(row["signal_to_entry_lower_seconds"])
        for row in strict_rows
    ]
    upper_values = [
        float(row["signal_to_entry_upper_seconds"])
        for row in strict_rows
    ]
    event_slots: Dict[str, int] = {}
    for event in entry_events:
        slot = pd.Timestamp(event["event_time"]).floor("min").isoformat()
        event_slots[slot] = event_slots.get(slot, 0) + 1

    current_archived_hashes = {
        "live/broker.py": (
            "492ea965e052780745926e6bcf00984ef2fc8be9b4905f00ef8b4456cb68bcef"
        ),
        "live/trader.py": (
            "59dfd80451093a3d79d74c3b12b21be53ab66489bc11529496d7bdbd814772ed"
        ),
    }

    return dict(
        scope=(
            "Read-only current-source and sanitized-archive timing audit. "
            "No live module is imported, broker contacted, order submitted, "
            "or protected path changed."
        ),
        current_source_sha256=source_hashes,
        source_contract_tokens=token_audit,
        archived_source_identity=dict(
            archive_id=metadata["archive_id"],
            git_branch=metadata["git_branch"],
            git_commit=metadata["git_commit"],
            verified_source_sha256=current_archived_hashes,
            current_broker_and_trader_byte_match_archive=all(
                source_hashes[path] == expected
                for path, expected in current_archived_hashes.items()
            ),
            verification_note=(
                "Study 48 verified the archived commit; git-show hashes for "
                "broker/trader are embedded and checked against current bytes."
            ),
        ),
        current_latency_contract=dict(
            signal_persisted_before_entry_checks=True,
            mark_sync_calls_resolve_mark_price=(
                "_resolve_mark_price" in sync_source
            ),
            mark_resolution_calls_get_tradeable_price=(
                "get_tradeable_price" in resolve_source
            ),
            order_path_calls_get_tradeable_price=(
                "get_tradeable_price" in bracket_source
            ),
            separate_mark_and_order_snapshots_on_entry=True,
            minimum_snapshot_requests_per_entry=2,
            maximum_snapshot_requests_per_entry_if_both_live_attempts_fall_back=4,
            explicit_sleep_seconds_live_success_path=4,
            explicit_sleep_seconds_full_delayed_fallback_path=12,
            quote_snapshot_requests_share_one_result=False,
            signal_revalidated_after_quote_wait=False,
            entry_deadline_or_max_latency_guard=False,
            snapshot_request_count_in_price_function=len(
                re.findall(r"reqTickers\(contract\)", price_source)
            ),
            two_second_sleep_count_in_price_function=len(
                re.findall(r"ib\.sleep\(2\)", price_source)
            ),
            endpoint=(
                "application Entry placed event after three placeOrder calls "
                "and local state write; not broker acceptance or execution"
            ),
        ),
        archived_timing=dict(
            entry_events=len(entry_events),
            unique_entry_minute_slots=len(event_slots),
            double_entry_minute_slots=sum(
                count == 2 for count in event_slots.values()
            ),
            event_minutes=sorted(
                {
                    pd.Timestamp(event["event_time"]).minute
                    for event in entry_events
                }
            ),
            schedule_to_application_entry_seconds=distribution(
                schedule_values
            ),
            strict_same_minute_signal_joins=len(strict_rows),
            spillover_entry_events=len(entry_events) - len(strict_rows),
            signal_to_entry_lower_bound_seconds=distribution(lower_values),
            signal_to_entry_upper_bound_seconds=distribution(upper_values),
            maximum_duplicate_signal_attribution_span_seconds=round(
                max(
                    upper - lower
                    for upper, lower in zip(
                        upper_values, lower_values
                    )
                ),
                6,
            ),
            rows=event_rows,
            interpretation=(
                "All 72 application entry events occur 14.377-62.949 seconds "
                "after the nominal :32 schedule anchor. Seventy have a same-"
                "minute prior signal record; duplicate-writer ambiguity changes "
                "their bounds by at most 1.966 seconds. Two events spill into "
                ":33 and are excluded from the strict signal join."
            ),
        ),
        external_primary_sources={
            "ibkr_snapshot_request": (
                "https://interactivebrokers.github.io/tws-api/"
                "md_request.html"
            ),
            "ib_insync_blocking_snapshot_source": (
                "https://ib-insync.readthedocs.io/_modules/"
                "ib_insync/ib.html"
            ),
        },
        current_test_boundary=dict(
            snapshot_request_latency=False,
            repeated_mark_and_order_snapshot=False,
            maximum_entry_latency=False,
            signal_revalidation_after_wait=False,
            entry_event_is_application_only=True,
        ),
        falsification_gate=[
            (
                "Timestamp every signal decision, quote request/callback, "
                "selection, order submission, acknowledgement, and execution "
                "under one cycle/lifecycle ID."
            ),
            (
                "Eliminate the pre-entry mark snapshot or explicitly reuse one "
                "validated side-aware snapshot within a strict age bound."
            ),
            (
                "Set a maximum decision-to-submit deadline and recompute/reject "
                "the signal when the deadline is crossed."
            ),
            (
                "Test live-success, delayed fallback, timeout, duplicate writer, "
                "same-cycle re-entry, and minute-boundary schedules."
            ),
        ],
        limitations=[
            (
                "Schedule-to-event latency includes signal work, broker position "
                "and account calls, qualification, snapshots, sleeps, submissions, "
                "and local writes; the archive cannot causally apportion it."
            ),
            (
                "The endpoint is application success, not broker acceptance or "
                "fill, so economic entry latency is at least as unidentified."
            ),
            (
                "A quote acquired near the end of the path is newer than the "
                "signal decision; total cycle age must not be misreported as "
                "quote age."
            ),
        ],
        decision=(
            "Entry is a multi-snapshot workflow with no latency deadline. Every "
            "entry path obtains one broker quote for account marking and a "
            "separate quote for bracket construction; live success requires at "
            "least two blocking snapshots and four explicit sleep seconds, while "
            "full delayed fallback can issue four snapshots and sleep twelve "
            "seconds. The archive's byte-matching source records 72 application "
            "entries 14.377-62.949 seconds after the :32 anchor (median 20.292; "
            "22 at least 30 seconds). This does not isolate snapshot causality or "
            "prove fills. Remove redundant requests, impose a decision-to-submit "
            "deadline, and persist the full signal-quote-order timing chain."
        ),
    )


def market_data_provenance_label_audit() -> Dict[str, object]:
    """Trace a delayed broker scalar through risk logic and the dashboard."""
    source_paths = [
        "live/broker.py",
        "live/trader.py",
        "live/state.py",
        "live/dashboard.py",
        "live/templates/dashboard.html",
        "tests/test_broker.py",
        "tests/test_trader_flow.py",
        "tests/test_software_take_profit.py",
    ]
    source_text: Dict[str, str] = {}
    source_hashes: Dict[str, str] = {}
    for relative in source_paths:
        path = os.path.join(REPO, relative)
        with open(path, "rb") as fh:
            raw = fh.read()
        source_hashes[relative] = hashlib.sha256(raw).hexdigest()
        source_text[relative] = raw.decode("utf-8")

    required_tokens = {
        "live/broker.py": [
            "[delayed] = ib.reqTickers(contract)",
            "return float(p)",
        ],
        "live/trader.py": [
            "price = broker.get_tradeable_price(symbol)",
            'return price, "live"',
            'return price, "delayed"',
            'return bar_close, "last_close"',
            "mark_time = datetime.now(timezone.utc).isoformat() if mark_price else None",
            "stop_hit = mark_price is not None",
        ],
        "live/state.py": [
            "mark_source = excluded.mark_source",
            "mark_time = excluded.mark_time",
        ],
        "live/dashboard.py": [
            'mark_source = ms or "live"',
            '"unrealized_pct": unrealized_pct',
        ],
        "live/templates/dashboard.html": [
            "position.mark_source == 'live'",
            "color:var(--green)",
        ],
    }
    token_audit = {
        path: {token: token in source_text[path] for token in tokens}
        for path, tokens in required_tokens.items()
    }
    if not all(
        present
        for checks in token_audit.values()
        for present in checks.values()
    ):
        raise AssertionError("market-data provenance source contract changed")

    def isolate(path: str, name: str) -> str:
        match = re.search(
            rf"^def {name}\b.*?(?=^def\s|\Z)",
            source_text[path],
            flags=re.MULTILINE | re.DOTALL,
        )
        if match is None:
            raise AssertionError(f"could not isolate {path}:{name}")
        return match.group(0)

    resolve_source = isolate("live/trader.py", "_resolve_mark_price")
    on_bar_source = isolate("live/trader.py", "_on_bar_inner")
    save_source = isolate("live/state.py", "save_account_snapshot")

    archive_path = os.path.join(
        REPO,
        "data",
        "live_runs",
        "archive_2026-06-18_pre_clean_run",
        "account_snapshot.json",
    )
    with open(archive_path) as fh:
        archived_rows = json.load(fh)
    if isinstance(archived_rows, dict):
        archived_rows = [archived_rows]
    archive_sources: Dict[str, int] = {}
    for row in archived_rows:
        source = str(row.get("mark_source"))
        archive_sources[source] = archive_sources.get(source, 0) + 1

    # Both upstream states are identical at the scalar-only resolver boundary.
    scalar = 100.0
    indistinguishable_rows = [
        dict(
            upstream_market_data_type=data_type,
            broker_return_value=scalar,
            resolver_return=[scalar, "live"],
            persisted_mark_source="live",
            dashboard_badge="live/green",
        )
        for data_type in (
            "real_time",
            "delayed_15_to_20_minutes",
        )
    ]
    test_text = "\n".join(
        (
            source_text["tests/test_trader_flow.py"],
            source_text["tests/test_software_take_profit.py"],
        )
    )
    mocked_resolver_labels = re.findall(
        r"_resolve_mark_price[^\n]{0,100}return_value=\([^,]+,\s*[\"']([^\"']+)",
        test_text,
    )

    return dict(
        scope=(
            "Read-only current-source, deterministic interface, test, and "
            "sanitized-archive audit. No live module is imported, broker "
            "contacted, order submitted, database opened, or protected path "
            "changed."
        ),
        current_source_sha256=source_hashes,
        source_contract_tokens=token_audit,
        provenance_contract=dict(
            broker_return_shape="price scalar only",
            delayed_branch_returns_same_shape_as_live_branch=True,
            resolver_can_distinguish_live_from_delayed=False,
            broker_success_always_labeled_live=(
                'return price, "live"' in resolve_source
            ),
            yfinance_fallback_labeled_delayed=(
                'return price, "delayed"' in resolve_source
            ),
            bar_fallback_labeled_last_close=(
                'return bar_close, "last_close"' in resolve_source
            ),
            selected_quote_field_retained=False,
            market_data_type_retained=False,
            source_quote_timestamp_retained=False,
            mark_time_semantics="local post-resolution wall-clock time",
            mark_time_is_source_quote_time=False,
            saved_columns=["mark_price", "mark_source", "mark_time"],
            saved_value_is_overwritten_singleton=(
                "ON CONFLICT(id) DO UPDATE" in save_source
            ),
        ),
        deterministic_indistinguishability=dict(
            input_rows=indistinguishable_rows,
            same_downstream_record=True,
            false_live_label_reachable=True,
            proof=(
                "get_tradeable_price returns only a float from both live and "
                "delayed branches; _resolve_mark_price maps every successful "
                "float to (price, 'live')."
            ),
        ),
        downstream_materiality=dict(
            account_snapshot_persists_label=("mark_source" in save_source),
            dashboard_missing_source_defaults_to_live=(
                'mark_source = ms or "live"'
                in source_text["live/dashboard.py"]
            ),
            dashboard_live_badge_is_green=True,
            dashboard_unrealized_pnl_uses_mark=True,
            software_stop_uses_resolved_mark=(
                "_resolve_mark_price(" in on_bar_source
                and "stop_hit = mark_price is not None" in on_bar_source
            ),
            software_take_profit_uses_resolved_mark=(
                "target_hit_sw = use_sw_tp" in on_bar_source
            ),
            logged_stop_source_can_be_false_live=True,
            note=(
                "This proves provenance misclassification. Study 63 separately "
                "bounds stale-price geometry; it does not prove an archived "
                "software exit was caused by delayed data."
            ),
        ),
        archive_observability=dict(
            artifact=os.path.relpath(archive_path, REPO),
            exported_rows=len(archived_rows),
            mark_source_counts=archive_sources,
            source_quote_timestamp_present=sum(
                row.get("source_quote_timestamp") is not None
                for row in archived_rows
            ),
            market_data_type_present=sum(
                row.get("market_data_type") is not None
                for row in archived_rows
            ),
            selected_quote_field_present=sum(
                row.get("selected_quote_field") is not None
                for row in archived_rows
            ),
            delayed_incident_rate_identified=False,
            interpretation=(
                "The singleton says 'live', but the interface cannot establish "
                "that provenance and prior rows were overwritten. It supports "
                "reachability, not incident frequency."
            ),
        ),
        current_test_boundary=dict(
            direct_resolver_invocations=len(
                re.findall(r"\b_resolve_mark_price\(", test_text)
            ),
            mocked_resolver_source_labels=sorted(set(mocked_resolver_labels)),
            delayed_broker_result_propagates_as_delayed=False,
            missing_persisted_source_defaults_to_unknown=False,
            source_timestamp_semantics_tested=False,
            dashboard_false_live_badge_tested=False,
        ),
        falsification_gate=[
            (
                "Return a typed quote object from the broker with data type, "
                "selected field, source timestamp, request time, bid/ask and "
                "sizes; never infer provenance from scalar success."
            ),
            (
                "Preserve those fields through state and monitoring, label "
                "unknown as unknown, and derive freshness from source time."
            ),
            (
                "Fail closed or use an explicitly approved bounded fallback for "
                "software risk triggers; test live, delayed, frozen, prior-close, "
                "missing-label, stale-time, and out-of-spread cases."
            ),
            (
                "Retain append-only per-cycle quote provenance so delayed-data "
                "frequency and risk-trigger association can be calibrated."
            ),
        ],
        limitations=[
            (
                "This is a deterministic interface/source proof, not evidence "
                "that IBKR returned delayed data in any particular cycle."
            ),
            (
                "The archive exports one overwritten account singleton, not a "
                "time series, so it cannot estimate false-live incidence."
            ),
            (
                "A delayed value may coincide with current price; provenance "
                "failure and price error are separate claims."
            ),
        ],
        decision=(
            "The 'live' mark label is not evidence of real-time market data. "
            "Real-time and delayed broker branches collapse to the same float, "
            "and _resolve_mark_price labels every successful float 'live'; "
            "state persists it, the dashboard renders it green, and the same "
            "resolver feeds software stop/take-profit checks. mark_time records "
            "local resolution time, not quote time. The sole archive snapshot "
            "has no type, field, or source timestamp, so incidence is unknown. "
            "Treat current live-mark percentages and green badges as "
            "uncalibrated until provenance is typed and timestamped end to end."
        ),
    )


def software_risk_trigger_outcome_audit() -> Dict[str, object]:
    """Join software-stop trigger evidence to retained close outcomes."""
    source_paths = [
        "live/trader.py",
        "live/broker.py",
        "live/state.py",
        "tests/test_software_take_profit.py",
        "tests/test_trader_flow.py",
    ]
    source_text = {}
    source_hashes = {}
    for relative in source_paths:
        raw = open(os.path.join(REPO, relative), "rb").read()
        source_hashes[relative] = hashlib.sha256(raw).hexdigest()
        source_text[relative] = raw.decode("utf-8")
    required = {
        "live/trader.py": [
            "stop_hit = mark_price is not None",
            "target_hit_sw = use_sw_tp",
            "close_fill = broker.cancel_and_close(",
            'state.close_position(return_pct=ret, exit_type="stop_hit"',
        ],
        "live/broker.py": ["def cancel_and_close("],
    }
    token_audit = {
        path: {token: token in source_text[path] for token in tokens}
        for path, tokens in required.items()
    }
    if not all(
        value for row in token_audit.values() for value in row.values()
    ):
        raise AssertionError("software risk-trigger contract changed")

    archive = os.path.join(
        REPO, "data", "live_runs",
        "archive_2026-06-18_pre_clean_run",
    )
    with open(os.path.join(archive, "monitor_events.jsonl")) as fh:
        events = [json.loads(line) for line in fh if line.strip()]
    with open(os.path.join(archive, "trades.jsonl")) as fh:
        trades = [json.loads(line) for line in fh if line.strip()]
    trigger_pattern = re.compile(
        r"SOFTWARE STOP triggered: mark=(?P<mark>[0-9.]+) "
        r"\((?P<source>[^)]+)\) breached stop=(?P<stop>[0-9.]+)"
    )
    triggers = []
    for event in events:
        match = trigger_pattern.search(str(event.get("message", "")))
        if match:
            mark = float(match.group("mark"))
            stop = float(match.group("stop"))
            triggers.append(
                dict(
                    event_time=event["event_time"],
                    mark=mark,
                    source_label=match.group("source"),
                    stop=stop,
                    breach_margin_bps=round(
                        (stop / mark - 1.0) * 10000.0, 6
                    ),
                )
            )
    stop_trades = [
        row for row in trades if row.get("exit_type") == "stop_hit"
    ]
    primary = []
    duplicate = []
    for trigger in triggers:
        event_time = pd.Timestamp(trigger["event_time"]).tz_convert(None)
        deltas = []
        for row in stop_trades:
            trade_time = pd.Timestamp(row["exit_time"])
            if trade_time.tzinfo is not None:
                trade_time = trade_time.tz_convert(None)
            deltas.append(((trade_time - event_time).total_seconds(), row))
        following = [
            (delta, row) for delta, row in deltas
            if 0 <= delta <= 5
        ]
        if following:
            delta, row = min(following, key=lambda item: item[0])
            primary.append(
                dict(
                    **trigger,
                    seconds_to_recorded_close=round(delta, 6),
                    recorded_exit_time=row["exit_time"],
                    recorded_exit_price=float(row["exit_price"]),
                    recorded_return_pct=round(
                        float(row["return_pct"]) * 100.0, 6
                    ),
                    recorded_exit_beyond_stop=(
                        float(row["exit_price"]) <= trigger["stop"]
                    ),
                )
            )
        else:
            prior = [
                (-delta, row) for delta, row in deltas
                if -60 <= delta < 0
            ]
            if prior:
                elapsed, row = min(prior, key=lambda item: item[0])
                duplicate.append(
                    dict(
                        **trigger,
                        seconds_after_prior_recorded_close=round(
                            elapsed, 6
                        ),
                        prior_recorded_exit_time=row["exit_time"],
                    )
                )
    if len(primary) + len(duplicate) != len(triggers):
        raise AssertionError("unclassified software-stop trigger")

    unique_margins = np.asarray(
        [row["breach_margin_bps"] for row in primary], dtype=float
    )
    all_margins = np.asarray(
        [row["breach_margin_bps"] for row in triggers], dtype=float
    )
    test_text = "\n".join(
        (
            source_text["tests/test_software_take_profit.py"],
            source_text["tests/test_trader_flow.py"],
        )
    )
    return dict(
        scope=(
            "Read-only source and sanitized-archive join. No live module is "
            "imported, broker contacted, order submitted, database opened, or "
            "protected path changed."
        ),
        current_source_sha256=source_hashes,
        source_contract_tokens=token_audit,
        current_trigger_contract=dict(
            stop_uses_any_non_null_resolved_mark=True,
            source_allowlist_or_age_gate=False,
            take_profit_uses_same_unqualified_mark=True,
            trigger_calls_market_force_close_before_local_close=True,
            source_label_is_diagnostic_only=True,
        ),
        archived_trigger_evidence=dict(
            trigger_events=len(triggers),
            unique_primary_close_joins=len(primary),
            duplicate_post_close_triggers=len(duplicate),
            source_label_counts={
                source: sum(
                    row["source_label"] == source for row in triggers
                )
                for source in sorted(
                    {row["source_label"] for row in triggers}
                )
            },
            unique_breach_margin_bps=dict(
                min=round(float(unique_margins.min()), 6),
                median=round(float(np.median(unique_margins)), 6),
                max=round(float(unique_margins.max()), 6),
            ),
            all_event_breach_margin_bps=dict(
                min=round(float(all_margins.min()), 6),
                median=round(float(np.median(all_margins)), 6),
                max=round(float(all_margins.max()), 6),
            ),
            primary_rows=primary,
            duplicate_rows=duplicate,
            unique_recorded_exits_beyond_stop=sum(
                row["recorded_exit_beyond_stop"] for row in primary
            ),
            all_unique_recorded_exits_beyond_stop=all(
                row["recorded_exit_beyond_stop"] for row in primary
            ),
            false_trigger_observed_in_retained_exit_prices=False,
        ),
        interpretation_boundary=dict(
            recorded_close_component_is_execution_evidence=True,
            recorded_close_proves_original_mark_provenance=False,
            durable_order_execution_identity_complete=False,
            duplicate_trigger_second_order_outcome_known=False,
            conclusion=(
                "The retained close components support an economically breached "
                "stop for all four unique joined exits, so this archive does not "
                "show a false software stop. It does not validate the source "
                "labels or rule out an unretained second close."
            ),
        ),
        current_test_boundary=dict(
            tests_mock_resolver_as_live=(
                'return_value=(mark, "live")' in test_text
            ),
            delayed_source_rejected=False,
            last_close_source_rejected=False,
            stale_source_time_rejected=False,
            duplicate_trigger_after_close_tested=False,
        ),
        falsification_gate=[
            (
                "Gate software triggers on the typed, timestamped, side-aware "
                "quote contract from Study 65, with explicit allowed sources."
            ),
            (
                "Require a lifecycle claim before force close and make duplicate "
                "writers observe a terminal/claimed lifecycle before any order."
            ),
            (
                "Persist trigger quote provenance plus close order/execution "
                "identity and verify exact broker flatness."
            ),
            (
                "Test stale/delayed/prior-close false breaches, true breaches, "
                "two-writer triggers, partial closes, and late fills."
            ),
        ],
        limitations=[
            (
                "The four recorded exit prices are retained execution components, "
                "not identity-complete cumulative VWAPs or broker-flat proofs."
            ),
            (
                "No archived source quote timestamp/type/field exists, so trigger "
                "provenance and false-trigger incidence remain unidentified."
            ),
            (
                "The two later trigger events prove duplicate decision execution, "
                "not that a second close order filled."
            ),
        ],
        decision=(
            "Software stop and take-profit logic accept any non-null resolved "
            "mark without source or age qualification. The archive contains six "
            "software-stop triggers, all labeled live but provenance-unverified: "
            "four join within 1.1 seconds to unique recorded stop exits and all "
            "four exit components remain beyond the stop, so no false trigger is "
            "observed in retained prices. Two additional writers triggered again "
            "22-23 seconds after the prior close record, exposing a separate "
            "duplicate-force-close boundary. Preserve quote and execution "
            "identity, gate provenance, and claim the lifecycle before ordering."
        ),
    )


def software_risk_fallback_freshness_audit(
    hourly: pd.DataFrame,
) -> Dict[str, object]:
    """Audit daily-close fallback freshness and archived trigger materiality."""
    source_paths = [
        "live/broker.py",
        "live/trader.py",
        "src/data/fetcher.py",
        "requirements.txt",
        "tests/test_fetcher.py",
        "tests/test_software_take_profit.py",
        "tests/test_trader_flow.py",
    ]
    source_text = {}
    source_hashes = {}
    for relative in source_paths:
        raw = open(os.path.join(REPO, relative), "rb").read()
        source_hashes[relative] = hashlib.sha256(raw).hexdigest()
        source_text[relative] = raw.decode("utf-8")
    required = {
        "live/broker.py": [
            'fetch_yfinance(symbol, start=start, end=end, interval="1d")',
            'price = float(hist["close"].iloc[-1])',
        ],
        "live/trader.py": [
            "price = _yfinance_fallback(symbol)",
            'return price, "delayed"',
            'return bar_close, "last_close"',
            "stop_hit = mark_price is not None",
        ],
        "src/data/fetcher.py": [
            "for attempt in range(max_retries):",
            "wait = 2 ** (attempt + 1)",
            "ticker.history(start=start, end=end, interval=interval)",
        ],
        "requirements.txt": ["yfinance==1.2.0"],
    }
    token_audit = {
        path: {token: token in source_text[path] for token in tokens}
        for path, tokens in required.items()
    }
    if not all(
        value for row in token_audit.values() for value in row.values()
    ):
        raise AssertionError("software fallback-freshness contract changed")

    observed_hourly_hash = _sha256_file(CACHE)
    if observed_hourly_hash != HOURLY_SOURCE_SHA256:
        raise AssertionError("hourly source hash changed")
    panel = hourly.copy()
    panel.index = panel.index.tz_convert("UTC").tz_localize(None)
    daily_closes = panel["close"].groupby(panel.index.date).last()
    session_dates = list(daily_closes.index)
    prior_close = {
        session_dates[i]: float(daily_closes.iloc[i - 1])
        for i in range(1, len(session_dates))
    }

    archive = os.path.join(
        REPO, "data", "live_runs",
        "archive_2026-06-18_pre_clean_run",
    )
    with open(os.path.join(archive, "trades.jsonl")) as fh:
        trades = [json.loads(line) for line in fh if line.strip()]
    with open(os.path.join(archive, "signal_history.jsonl")) as fh:
        signals = [json.loads(line) for line in fh if line.strip()]

    candidates = []
    exposed_trades = set()
    for trade_index, trade in enumerate(trades):
        exit_price = trade.get("exit_price")
        if exit_price is None:
            continue
        recorded_return = float(trade["return_pct"])
        if abs(1.0 + recorded_return) < 1e-12:
            continue
        # Historical state omitted entry price from the closed-trade export.
        # Reconstruct its recorded basis algebraically; this is not a fill claim.
        entry_basis = float(exit_price) / (1.0 + recorded_return)
        stop = round(entry_basis * 0.995, 2)
        target = round(entry_basis * 1.01, 2)
        entry_time = pd.Timestamp(trade["entry_time"])
        exit_time = pd.Timestamp(trade["exit_time"])
        if entry_time.tzinfo is not None:
            entry_time = entry_time.tz_convert(None)
        if exit_time.tzinfo is not None:
            exit_time = exit_time.tz_convert(None)
        for signal in signals:
            signal_time = pd.Timestamp(signal["updated_at"])
            if signal_time.tzinfo is not None:
                signal_time = signal_time.tz_convert(None)
            bar_close = signal.get("bar_close")
            if not (
                entry_time < signal_time < exit_time
                and signal_time.date() in prior_close
                and bar_close is not None
            ):
                continue
            exposed_trades.add(trade_index)
            previous = prior_close[signal_time.date()]
            current_proxy = float(bar_close)
            candidates.append(
                dict(
                    trade_index=trade_index,
                    cycle_slot=signal_time.floor("min").isoformat(),
                    prior_session_close=previous,
                    current_signal_bar_close=current_proxy,
                    recorded_entry_basis=entry_basis,
                    stop=stop,
                    target=target,
                    prior_close_only_false_stop=(
                        previous <= stop < current_proxy
                    ),
                    prior_close_only_false_take_profit=(
                        previous >= target > current_proxy
                    ),
                )
            )

    by_slot: Dict[Tuple[int, str], Dict[str, object]] = {}
    for row in candidates:
        key = (row["trade_index"], row["cycle_slot"])
        slot = by_slot.setdefault(
            key,
            dict(
                trade_index=row["trade_index"],
                cycle_slot=row["cycle_slot"],
                false_stop_states=set(),
                false_take_profit_states=set(),
            ),
        )
        slot["false_stop_states"].add(
            row["prior_close_only_false_stop"]
        )
        slot["false_take_profit_states"].add(
            row["prior_close_only_false_take_profit"]
        )

    def slot_summary(field: str) -> Dict[str, object]:
        strict = [
            row for row in by_slot.values()
            if row[field] == {True}
        ]
        possible = [
            row for row in by_slot.values()
            if True in row[field]
        ]
        conflicts = [
            row for row in by_slot.values()
            if row[field] == {True, False}
        ]
        return dict(
            strict_slots=len(strict),
            possible_slots=len(possible),
            duplicate_writer_ambiguous_slots=len(conflicts),
            strict_pct_of_evaluable_slots=round(
                len(strict) / len(by_slot) * 100.0, 6
            ),
            possible_pct_of_evaluable_slots=round(
                len(possible) / len(by_slot) * 100.0, 6
            ),
            strict_affected_trades=len(
                {row["trade_index"] for row in strict}
            ),
            possible_affected_trades=len(
                {row["trade_index"] for row in possible}
            ),
        )

    tests = "\n".join(
        (
            source_text["tests/test_fetcher.py"],
            source_text["tests/test_software_take_profit.py"],
            source_text["tests/test_trader_flow.py"],
        )
    )
    return dict(
        scope=(
            "Read-only current-source, pinned-hourly, and sanitized-archive "
            "counterfactual audit. No live module is imported, network called, "
            "broker contacted, order submitted, database opened, or protected "
            "path changed."
        ),
        current_source_sha256=source_hashes,
        source_contract_tokens=token_audit,
        pinned_hourly_sha256=observed_hourly_hash,
        current_fallback_contract=dict(
            broker_live_then_delayed_explicit_sleep_seconds=6,
            yfinance_interval="1d",
            yfinance_window_calendar_days=5,
            last_row_index_or_age_checked=False,
            current_session_row_required=False,
            selected_value="last returned daily close",
            source_label="delayed",
            yfinance_max_attempts=4,
            yfinance_explicit_backoff_seconds_before_final_attempt=14,
            full_path_explicit_sleep_and_backoff_seconds=20,
            request_duration_additional_and_unbounded_by_cycle_deadline=True,
            bar_close_used_if_yfinance_fails=True,
            software_trigger_source_or_age_gate=False,
        ),
        archived_prior_close_counterfactual=dict(
            endpoint=(
                "At each archived in-position signal cycle, replace the "
                "resolved mark with the prior session's pinned hourly close; "
                "compare against the contemporaneous archived signal bar close."
            ),
            recorded_trades=len(trades),
            trades_with_evaluable_cycles=len(exposed_trades),
            raw_candidate_rows=len(candidates),
            unique_trade_cycle_slots=len(by_slot),
            false_stop=slot_summary("false_stop_states"),
            false_take_profit=slot_summary(
                "false_take_profit_states"
            ),
            entry_basis=(
                "reconstructed as exit_price/(1+recorded_return); recorded "
                "quote basis, not actual fill"
            ),
            prior_close_source=(
                "last pinned full-session hourly close on the previous "
                "observed session"
            ),
            current_price_proxy="archived signal_history.bar_close",
            actual_yfinance_fallback_incidents_observed=0,
        ),
        current_test_boundary=dict(
            fetch_retry_and_ohlc_validation_tested=True,
            fallback_last_row_date_or_age_tested=False,
            resolver_yfinance_branch_directly_tested=False,
            prior_close_false_stop_rejection_tested=False,
            prior_close_false_take_profit_rejection_tested=False,
            fallback_total_latency_deadline_tested=False,
            relevant_token_presence=(
                "fetch_yfinance" in tests
                and "_resolve_mark_price" in tests
            ),
        ),
        external_primary_sources={
            "yfinance_documentation": (
                "https://ranaroussi.github.io/yfinance/index.html"
            ),
            "yfinance_history_parameters": (
                "https://ranaroussi.github.io/yfinance/reference/"
                "yfinance.price_history.html"
            ),
            "yfinance_download_parameters": (
                "https://ranaroussi.github.io/yfinance/reference/"
                "yfinance.functions.html"
            ),
        },
        falsification_gate=[
            (
                "Do not use a daily historical close for intraday software "
                "risk triggers; require typed side-aware broker evidence within "
                "a strict source-age bound."
            ),
            (
                "If a fallback is deliberately allowed, verify the returned "
                "row timestamp/session and carry it through the trigger record."
            ),
            (
                "Impose one end-to-end trigger-decision deadline covering broker "
                "snapshots, provider requests, retry sleeps, and close submission."
            ),
            (
                "Test prior-session rows, current partial daily rows, holidays, "
                "network retry exhaustion, duplicate writers, and true/false "
                "stop and take-profit boundaries."
            ),
        ],
        limitations=[
            (
                "This counterfactual proves material exposure if yfinance's last "
                "row is the prior session; it does not estimate how often the "
                "provider actually returned that state."
            ),
            (
                "Archived bar_close is a coarse signal-data proxy, not a "
                "side-executable quote; three stop slots are duplicate-writer "
                "ambiguous and are reported as strict/possible bounds."
            ),
            (
                "Historical entry basis is algebraically reconstructed from "
                "recorded return and exit price and inherits their execution "
                "identity limitations."
            ),
            (
                "The official yfinance project says it is unaffiliated with "
                "Yahoo and intended for research/educational use; this audit "
                "does not interpret provider terms or authorize deployment use."
            ),
        ],
        decision=(
            "After broker-price failure, software risk logic can act on the last "
            "daily yfinance close without checking its row date, session, or age. "
            "The path can spend six explicit broker-snapshot seconds plus fourteen "
            "retry-backoff seconds before request duration, with no cycle deadline. "
            "Under the explicit prior-session-row counterfactual, 62-65 of 160 "
            "archived trade-cycle slots (38.75%-40.63%) would falsely satisfy the "
            "long stop while the archived signal bar close would not; 17/160 "
            "(10.63%) would falsely satisfy take-profit. This is conditional "
            "materiality, not observed fallback incidence. Exclude daily closes "
            "from intraday triggers or enforce typed source-time freshness."
        ),
    )


def duplicate_bar_fallback_trigger_divergence_audit() -> Dict[str, object]:
    """Measure paired-writer bar-close disagreement at software-risk bounds."""
    source_paths = [
        "live/signals.py",
        "live/trader.py",
        "live/state.py",
        "tests/test_live_signals.py",
        "tests/test_software_take_profit.py",
        "tests/test_trader_flow.py",
    ]
    source_text = {}
    source_hashes = {}
    for relative in source_paths:
        raw = open(os.path.join(REPO, relative), "rb").read()
        source_hashes[relative] = hashlib.sha256(raw).hexdigest()
        source_text[relative] = raw.decode("utf-8")
    required = {
        "live/trader.py": [
            'bar_close_fallback = sig_info.get("bar_close")',
            'return bar_close, "last_close"',
            "stop_hit = mark_price is not None",
            "target_hit_sw = use_sw_tp",
        ],
        "live/state.py": [
            "INSERT INTO signal_history",
            "bar_close",
        ],
        "live/signals.py": [
            'bar_close = float(last_row["close"])',
            '"bar_close": bar_close',
            '"bar_time": last_bar_time',
        ],
    }
    token_audit = {
        path: {token: token in source_text[path] for token in tokens}
        for path, tokens in required.items()
    }
    if not all(
        value for row in token_audit.values() for value in row.values()
    ):
        raise AssertionError("duplicate bar-fallback contract changed")

    archive = os.path.join(
        REPO, "data", "live_runs",
        "archive_2026-06-18_pre_clean_run",
    )
    with open(os.path.join(archive, "trades.jsonl")) as fh:
        trades = [json.loads(line) for line in fh if line.strip()]
    with open(os.path.join(archive, "signal_history.jsonl")) as fh:
        signals = [json.loads(line) for line in fh if line.strip()]
    with open(os.path.join(archive, "monitor_events.jsonl")) as fh:
        events = [json.loads(line) for line in fh if line.strip()]

    slots: Dict[Tuple[int, str], Dict[str, object]] = {}
    raw_rows = 0
    for trade_index, trade in enumerate(trades):
        exit_price = trade.get("exit_price")
        if exit_price is None:
            continue
        entry_basis = float(exit_price) / (
            1.0 + float(trade["return_pct"])
        )
        stop = round(entry_basis * 0.995, 2)
        target = round(entry_basis * 1.01, 2)
        entry_time = pd.Timestamp(trade["entry_time"])
        exit_time = pd.Timestamp(trade["exit_time"])
        if entry_time.tzinfo is not None:
            entry_time = entry_time.tz_convert(None)
        if exit_time.tzinfo is not None:
            exit_time = exit_time.tz_convert(None)
        for signal in signals:
            update = pd.Timestamp(signal["updated_at"])
            if update.tzinfo is not None:
                update = update.tz_convert(None)
            if not (
                entry_time < update < exit_time
                and signal.get("bar_close") is not None
            ):
                continue
            raw_rows += 1
            key = (trade_index, update.floor("min").isoformat())
            slot = slots.setdefault(
                key,
                dict(
                    trade_index=trade_index,
                    cycle_slot=key[1],
                    recorded_entry_basis=entry_basis,
                    stop=stop,
                    target=target,
                    rows=[],
                ),
            )
            slot["rows"].append(
                dict(
                    updated_at=signal["updated_at"],
                    bar_time=signal["bar_time"],
                    bar_close=float(signal["bar_close"]),
                )
            )

    divergence_rows = []
    for slot in slots.values():
        closes = [row["bar_close"] for row in slot["rows"]]
        if len(closes) < 2:
            continue
        stop_states = {
            close <= slot["stop"] for close in closes
        }
        target_states = {
            close >= slot["target"] for close in closes
        }
        kinds = []
        if stop_states == {True, False}:
            kinds.append("stop")
        if target_states == {True, False}:
            kinds.append("take_profit")
        if not kinds:
            continue
        update_times = [
            pd.Timestamp(row["updated_at"]) for row in slot["rows"]
        ]
        bar_times = [
            pd.Timestamp(row["bar_time"]) for row in slot["rows"]
        ]
        cycle_time = pd.Timestamp(slot["cycle_slot"])
        divergence_rows.append(
            dict(
                **slot,
                divergent_decisions=kinds,
                writer_update_span_seconds=round(
                    (max(update_times) - min(update_times)).total_seconds(),
                    6,
                ),
                distinct_bar_times=len(set(bar_times)),
                crosses_session_date=(
                    len({value.date() for value in bar_times}) > 1
                ),
                includes_cycle_in_progress_bar=any(
                    value.floor("h") == cycle_time.floor("h")
                    for value in bar_times
                ),
                includes_older_bar=any(
                    value.floor("h") < cycle_time.floor("h")
                    for value in bar_times
                ),
            )
        )

    spans = np.asarray(
        [row["writer_update_span_seconds"] for row in divergence_rows],
        dtype=float,
    )
    stop_rows = [
        row for row in divergence_rows
        if "stop" in row["divergent_decisions"]
    ]
    target_rows = [
        row for row in divergence_rows
        if "take_profit" in row["divergent_decisions"]
    ]
    monitor_sources = re.findall(
        r"SOFTWARE (?:STOP|TAKE-PROFIT) triggered: "
        r"mark=[0-9.]+ \(([^)]+)\)",
        "\n".join(str(event.get("message", "")) for event in events),
    )
    test_text = "\n".join(
        (
            source_text["tests/test_live_signals.py"],
            source_text["tests/test_software_take_profit.py"],
            source_text["tests/test_trader_flow.py"],
        )
    )
    return dict(
        scope=(
            "Read-only current-source and sanitized-archive decision-boundary "
            "audit. No live module is imported, network called, broker "
            "contacted, order submitted, database opened, or protected path "
            "changed."
        ),
        current_source_sha256=source_hashes,
        source_contract_tokens=token_audit,
        current_fallback_contract=dict(
            same_cycle_signal_bar_close_used_after_broker_and_yfinance_failure=True,
            bar_timestamp_or_completion_revalidated_at_trigger=False,
            source_or_age_gate=False,
            lifecycle_or_cycle_claim_before_force_close=False,
            risk_decision_identity_persisted=False,
        ),
        archived_divergence=dict(
            recorded_trades=len(trades),
            raw_in_position_signal_rows=raw_rows,
            unique_trade_cycle_slots=len(slots),
            multi_writer_slots=sum(
                len(slot["rows"]) > 1 for slot in slots.values()
            ),
            divergent_slots=len(divergence_rows),
            stop_divergent_slots=len(stop_rows),
            take_profit_divergent_slots=len(target_rows),
            divergent_trades=len(
                {row["trade_index"] for row in divergence_rows}
            ),
            divergent_pct_of_all_slots=round(
                len(divergence_rows) / len(slots) * 100.0, 6
            ),
            divergent_pct_of_multi_writer_slots=round(
                len(divergence_rows)
                / sum(len(slot["rows"]) > 1 for slot in slots.values())
                * 100.0,
                6,
            ),
            writer_update_span_seconds=dict(
                min=round(float(spans.min()), 6),
                median=round(float(np.median(spans)), 6),
                max=round(float(spans.max()), 6),
            ),
            cross_session_date_slots=sum(
                row["crosses_session_date"] for row in divergence_rows
            ),
            all_include_in_progress_and_older_bar=all(
                row["includes_cycle_in_progress_bar"]
                and row["includes_older_bar"]
                for row in divergence_rows
            ),
            rows=divergence_rows,
            observed_software_trigger_source_counts={
                source: monitor_sources.count(source)
                for source in sorted(set(monitor_sources))
            },
            observed_last_close_trigger_incidents=monitor_sources.count(
                "last_close"
            ),
        ),
        deterministic_two_writer_consequence=dict(
            writer_below_boundary="force close",
            writer_above_boundary="hold",
            decision_ordering_nondeterministic=True,
            second_writer_can_use_cached_position_after_first_close=True,
            historical_external_order_outcome_identified=False,
        ),
        current_test_boundary=dict(
            incomplete_bar_selection_tested=True,
            software_trigger_tests_mock_source_live=(
                'return_value=(mark, "live")' in test_text
            ),
            last_close_trigger_branch_tested=False,
            paired_writer_boundary_straddle_tested=False,
            atomic_lifecycle_claim_tested=False,
        ),
        falsification_gate=[
            (
                "Select one exchange-time completed bar deterministically and "
                "carry its timestamp/completion proof into the fallback object."
            ),
            (
                "Atomically claim lifecycle+cycle ownership before any software "
                "risk action; later writers must observe claimed/terminal state."
            ),
            (
                "Persist trigger decision, source bar, lifecycle, close order, "
                "execution identity, and exact-flat result under one ID."
            ),
            (
                "Test current-tail present/absent, host timezones, paired writers, "
                "boundary straddles, broker/yfinance failure, and late fills."
            ),
        ],
        limitations=[
            (
                "Divergence proves different decisions if both writers reach the "
                "bar-close fallback; the archive records zero last_close-labeled "
                "software triggers and therefore no realized incident."
            ),
            (
                "Recorded entry basis is reconstructed from retained return and "
                "exit price and inherits their execution-identity limitations."
            ),
            (
                "The current-hour bar is classified as in progress from its "
                "timestamp relative to the :32 cycle, not from vendor callback "
                "metadata retained at runtime."
            ),
        ],
        decision=(
            "The final bar-close fallback is not deterministic across the "
            "historical duplicate writers. Among 167 archived in-position "
            "trade-cycle slots, 114 contain multiple writer values; five paired "
            "values straddle the stop and five straddle take-profit, affecting "
            "nine trades. Every divergent slot mixes the cycle's in-progress bar "
            "with an older bar; nine cross a session date. Writers disagree "
            "within 0.000125-2.112320 seconds. No last_close-labeled software "
            "trigger is retained, so this is a concrete decision fork, not an "
            "incident claim. Require one completed-bar identity and one atomic "
            "lifecycle owner before forcing an exit."
        ),
    )


def broker_connection_exception_fallback_audit() -> Dict[str, object]:
    """Audit connection exceptions that bypass price and risk fallbacks."""
    source_paths = [
        "live/broker.py",
        "live/trader.py",
        "tests/test_broker.py",
        "tests/test_trader_flow.py",
    ]
    source_text = {}
    source_hashes = {}
    for relative in source_paths:
        raw = open(os.path.join(REPO, relative), "rb").read()
        source_hashes[relative] = hashlib.sha256(raw).hexdigest()
        source_text[relative] = raw.decode("utf-8")
    required = {
        "live/broker.py": [
            "for attempt in range(max_retries + 1):",
            "wait = 2 * (attempt + 1)",
            "else:\n                raise",
            "ib = _ensure_connected()",
        ],
        "live/trader.py": [
            "except RuntimeError:",
            "broker_pos = broker.get_open_position(position.symbol)",
            "bar_count = state.increment_bar_count()",
            "mark_price, mark_source = _resolve_mark_price(",
        ],
    }
    token_audit = {
        path: {token: token in source_text[path] for token in tokens}
        for path, tokens in required.items()
    }
    if not all(
        value for row in token_audit.values() for value in row.values()
    ):
        raise AssertionError("connection exception-fallback contract changed")

    archive = os.path.join(
        REPO, "data", "live_runs",
        "archive_2026-06-18_pre_clean_run",
    )
    with open(os.path.join(archive, "monitor_events.jsonl")) as fh:
        events = [json.loads(line) for line in fh if line.strip()]
    with open(os.path.join(archive, "trades.jsonl")) as fh:
        trades = [json.loads(line) for line in fh if line.strip()]

    failures = []
    for event in events:
        message = str(event.get("message", ""))
        if not (
            "Unhandled on_bar exception:" in message
            and "Connect call failed" in message
        ):
            continue
        event_time = pd.Timestamp(event["event_time"])
        if event_time.tzinfo is not None:
            event_time = event_time.tz_convert(None)
        open_trade_indexes = []
        for trade_index, trade in enumerate(trades):
            entry = pd.Timestamp(trade["entry_time"])
            exit_ = pd.Timestamp(trade["exit_time"])
            if entry.tzinfo is not None:
                entry = entry.tz_convert(None)
            if exit_.tzinfo is not None:
                exit_ = exit_.tz_convert(None)
            if entry < event_time < exit_:
                open_trade_indexes.append(trade_index)
        anchor = event_time.floor("h") + pd.Timedelta(minutes=32)
        failures.append(
            dict(
                event_time=event["event_time"],
                cycle_slot=event_time.floor("min").isoformat(),
                seconds_after_schedule=round(
                    (event_time - anchor).total_seconds(), 6
                ),
                exception_type_explicit=(
                    "ConnectionRefusedError:" in message
                ),
                open_trade_indexes=open_trade_indexes,
            )
        )
    slot_counts: Dict[str, int] = {}
    for row in failures:
        slot_counts[row["cycle_slot"]] = (
            slot_counts.get(row["cycle_slot"], 0) + 1
        )
    position_rows = [
        row for row in failures if row["open_trade_indexes"]
    ]
    offsets = np.asarray(
        [row["seconds_after_schedule"] for row in failures],
        dtype=float,
    )
    test_text = "\n".join(
        (
            source_text["tests/test_broker.py"],
            source_text["tests/test_trader_flow.py"],
        )
    )
    return dict(
        scope=(
            "Read-only current-source and sanitized-archive exception audit. "
            "No live module is imported, network called, broker contacted, "
            "order submitted, database opened, or protected path changed."
        ),
        current_source_sha256=source_hashes,
        source_contract_tokens=token_audit,
        current_exception_contract=dict(
            ensure_connected_attempts=4,
            ensure_connected_explicit_retry_wait_seconds=12,
            final_connect_exception_reraised_original_type=True,
            get_tradeable_price_calls_ensure_connected_before_market_data_try=True,
            resolver_catches_runtime_error_only=True,
            connection_refused_is_runtime_error=False,
            connection_refused_reaches_yfinance_fallback=False,
            open_position_reconciliation_occurs_before_bar_increment=True,
            open_position_reconciliation_occurs_before_software_risk_check=True,
            connection_failure_aborts_holding_age_and_software_risk_cycle=True,
        ),
        deterministic_exception_matrix=[
            dict(
                upstream_exception="RuntimeError(no broker price)",
                resolver_outcome="yfinance then bar-close fallback",
            ),
            dict(
                upstream_exception="ConnectionRefusedError",
                resolver_outcome="propagates; no price fallback",
            ),
            dict(
                upstream_exception="OSError/TimeoutError from connect",
                resolver_outcome="propagates unless subclassed/wrapped elsewhere",
            ),
        ],
        archived_connection_failures=dict(
            events=len(failures),
            unique_cycle_slots=len(slot_counts),
            paired_writer_slots=sum(
                value == 2 for value in slot_counts.values()
            ),
            maximum_events_per_slot=max(slot_counts.values()),
            events_while_position_open=len(position_rows),
            unique_position_open_cycle_slots=len(
                {row["cycle_slot"] for row in position_rows}
            ),
            affected_position_lifecycles=len(
                {
                    index
                    for row in position_rows
                    for index in row["open_trade_indexes"]
                }
            ),
            explicit_typed_connection_refused_events=sum(
                row["exception_type_explicit"] for row in failures
            ),
            legacy_untyped_connection_refused_events=sum(
                not row["exception_type_explicit"] for row in failures
            ),
            seconds_after_schedule=dict(
                min=round(float(offsets.min()), 6),
                median=round(float(np.median(offsets)), 6),
                max=round(float(offsets.max()), 6),
            ),
            rows=failures,
            exact_call_site_identified_from_archive=False,
            causal_pnl_or_missed_exit_effect_identified=False,
        ),
        current_test_boundary=dict(
            no_price_runtime_error_fallback_tested=(
                'side_effect=RuntimeError("no price")' in test_text
            ),
            connection_refused_resolver_fallback_tested=False,
            open_position_connection_failure_tested=False,
            holding_counter_not_advanced_on_failure_tested=False,
            risk_check_missed_on_failure_tested=False,
        ),
        falsification_gate=[
            (
                "Normalize broker-availability failures into a typed result "
                "rather than relying on an exception-class allowlist."
            ),
            (
                "Separate broker reconciliation availability from mark fallback "
                "and persist a missed-risk-check event when either is unavailable."
            ),
            (
                "Define whether holding age advances on a missed cycle using one "
                "completed-bar identity, not process success or invocation count."
            ),
            (
                "Test connection refused, timeout, DNS/socket errors, qualification "
                "failure, no-price RuntimeError, open positions, paired writers, "
                "recovery, and deadline exhaustion."
            ),
        ],
        limitations=[
            (
                "The archive retains exception text but no stack trace, so an "
                "individual event cannot be assigned to get_open_position versus "
                "another _ensure_connected caller."
            ),
            (
                "Position-open joins use local recorded lifecycle times and do "
                "not prove the broker position or protective order state."
            ),
            (
                "A missed software-risk cycle is not necessarily an economic loss "
                "because the broker bracket may remain protective; PnL and missed "
                "exit effects are unidentified."
            ),
        ],
        decision=(
            "The fallback chain handles 'no broker price' RuntimeError but not "
            "broker connection failure. _ensure_connected re-raises the original "
            "ConnectionRefusedError after four attempts and twelve explicit wait "
            "seconds; get_tradeable_price calls it outside the market-data try, "
            "and _resolve_mark_price catches only RuntimeError. More importantly, "
            "open-position reconciliation calls the same connection boundary "
            "before bar-count and software-risk logic. The archive directly "
            "records 46 such cycle aborts across 24 slots, 22 paired; 33 events "
            "and 17 slots occur while three local position lifecycles are open. "
            "Offsets of 12.247-12.628 seconds corroborate retry exhaustion. "
            "Normalize availability failures and explicitly record/reconcile "
            "missed risk cycles; economic effect remains unidentified."
        ),
    )


def july_live_case(df: pd.DataFrame) -> Dict[str, object]:
    """Market-data cross-check of F47's known 2026-07-06/07 live fill."""
    entry = 76.61
    stop = entry * (1 - 0.005)
    day = df.loc["2026-07-07"]
    if day.empty:
        raise RuntimeError("pinned dataset does not contain the 2026-07-07 session")
    open_px = float(day.iloc[0]["open"])
    modeled = -0.005 - SLIPPAGE
    gap_aware = (open_px - entry) / entry - SLIPPAGE
    observed_fill = 73.54
    observed = observed_fill / entry - 1.0
    return dict(
        entry=entry,
        stop_price=round(stop, 4),
        first_hour_open=round(open_px, 4),
        modeled_return_pct=round(modeled * 100, 3),
        gap_aware_hourly_open_return_pct=round(gap_aware * 100, 3),
        observed_live_fill=observed_fill,
        observed_live_return_pct=round(observed * 100, 3),
        open_vs_observed_fill_bps=round((open_px / observed_fill - 1) * 10000, 2),
    )


def run(refresh: bool = False, csv_path: Optional[str] = None) -> Dict[str, object]:
    df = load_hourly(refresh=refresh, csv_path=csv_path)
    sig = signal_frame(df)
    five_min = load_five_min(refresh=refresh)
    daily_panel = load_daily_panel(refresh=refresh)
    session_close_prices = {
        idx.date(): float(value)
        for idx, value in daily_panel["TQQQ_close"].dropna().items()
    }
    mode = config.ASSETS["TQQQ_HOURLY"]
    target = float(mode["target_gain_pct"])
    stop = float(mode["stop_loss_pct"])
    max_bars = int(getattr(config, "MAX_TRADE_BARS_LIVE", 10))

    cross = engine_crosscheck(sig, target=target, stop=stop, max_bars=max_bars)
    exact = simulate(
        sig, target, stop, max_bars,
        gap_aware=False, one_position=True, scan_entry_bar=True,
    )
    gap = simulate(
        sig, target, stop, max_bars,
        gap_aware=True, one_position=True, scan_entry_bar=True,
    )
    exact_target_first = simulate(
        sig, target, stop, max_bars,
        gap_aware=False, one_position=True, scan_entry_bar=True,
        entry_bar_ambiguous_target_first=True,
    )
    gap_target_first = simulate(
        sig, target, stop, max_bars,
        gap_aware=True, one_position=True, scan_entry_bar=True,
        entry_bar_ambiguous_target_first=True,
    )
    eod = simulate(
        sig, target, stop, max_bars,
        gap_aware=True, one_position=True, scan_entry_bar=True, flatten_eod=True,
        session_close_prices=session_close_prices,
    )
    eod_hourly_proxy = simulate(
        sig, target, stop, max_bars,
        gap_aware=True, one_position=True, scan_entry_bar=True, flatten_eod=True,
    )
    sensitivity = {}
    for bars in (8, 10):
        ex = simulate(
            sig, target, stop, bars,
            gap_aware=False, one_position=True, scan_entry_bar=True,
        )
        ga = simulate(
            sig, target, stop, bars,
            gap_aware=True, one_position=True, scan_entry_bar=True,
        )
        ps = paired_summary(ex, ga)
        sensitivity[str(bars)] = dict(
            trades=ps["exact"]["n"],
            held_overnight=ps["n_held_overnight"],
            gap_affected=ps["n_gap_affected"],
            fixed_10pct_capital_delta_pp=ps["fixed_10pct_capital_delta_pp"],
            exact_total_return_pct=ps["exact"]["total_return_pct"],
            gap_total_return_pct=ps["gap_aware"]["total_return_pct"],
            exact_max_drawdown_pct=ps["exact"]["max_drawdown_pct"],
            gap_max_drawdown_pct=ps["gap_aware"]["max_drawdown_pct"],
        )
    eod_metrics = equity_metrics(eod)
    gap_metrics = equity_metrics(gap)
    bars_per_day = pd.Series(1, index=df.index).groupby(df.index.date).sum()
    gap_pair = paired_summary(exact, gap)
    target_first_gap_pair = paired_summary(exact_target_first, gap_target_first)
    close_proxy = close_proxy_policy_sensitivity(df, sig, daily_panel)
    auction_runtime = closing_auction_runtime_readiness_audit()
    duplicate_forensics = historical_duplicate_writer_forensics()
    bar_timezone_audit = live_bar_completion_timezone_audit(
        duplicate_forensics
    )
    return dict(
        study=(
            "execution semantics, overnight gap risk, lower-timeframe calibration, "
            "mitigation, clustered tails, and leveraged-ETF history"
        ),
        data=dict(
            symbol=SYMBOL,
            start=str(df.index[0]),
            end=str(df.index[-1]),
            bars=int(len(df)),
            sessions=int(len(bars_per_day)),
            median_bars_per_session=float(bars_per_day.median()),
            timezone=TZ,
        ),
        config=dict(
            target_pct=target * 100,
            stop_pct=stop * 100,
            max_trade_bars=max_bars,
            slippage_bps=SLIPPAGE * 10000,
            position_fraction_pct=POSITION_FRACTION * 100,
            require_signals=int(mode["require_signals"]),
            allow_shorts=bool(getattr(config, "TRADER_ALLOW_SHORTS", False)),
        ),
        signal_candidates=int((sig["entry_signal"] != 0).sum()),
        engine_crosscheck=cross,
        raw_overnight_gaps=raw_overnight_gaps(df),
        execution_waterfall=execution_waterfall(df, five_min),
        live_shaped_replay=gap_pair,
        gap_effect_ordering_sensitivity=dict(
            conservative_stop_first=dict(
                exact_total_return_pct=gap_pair["exact"]["total_return_pct"],
                gap_total_return_pct=gap_pair["gap_aware"]["total_return_pct"],
                gap_affected=gap_pair["n_gap_affected"],
                fixed_10pct_capital_delta_pp=gap_pair["fixed_10pct_capital_delta_pp"],
            ),
            optimistic_entry_target_first=dict(
                exact_total_return_pct=target_first_gap_pair["exact"]["total_return_pct"],
                gap_total_return_pct=target_first_gap_pair["gap_aware"]["total_return_pct"],
                gap_affected=target_first_gap_pair["n_gap_affected"],
                fixed_10pct_capital_delta_pp=target_first_gap_pair[
                    "fixed_10pct_capital_delta_pp"
                ],
            ),
            finding=(
                "absolute strategy return is ordering-sensitive, but the paired overnight-gap "
                "damage and all 34 affected entries are invariant because dual-hit exits occur "
                "on the same entry bar under either ordering convention"
            ),
        ),
        mitigation_frontier=mitigation_frontier(sig, session_close_prices),
        session_close_validation=session_close_validation(df, daily_panel),
        end_of_day_flatten_counterfactual=dict(
            metrics=eod_metrics,
            fill_proxy="official daily close",
            n_eod_exits=int((eod["exit_type"] == "eod_flatten").sum()),
            versus_gap_aware_total_return_pp=round(
                eod_metrics["total_return_pct"] - gap_metrics["total_return_pct"], 4
            ),
            versus_gap_aware_maxdd_pp=round(
                eod_metrics["max_drawdown_pct"] - gap_metrics["max_drawdown_pct"], 4
            ),
            last_hourly_close_sensitivity=equity_metrics(eod_hourly_proxy),
        ),
        max_bar_sensitivity=sensitivity,
        cross_instrument_history=cross_instrument_history(daily_panel),
        gap_dependence_and_volatility=gap_dependence_and_volatility(daily_panel),
        volatility_conditioned_mitigation=volatility_conditioned_mitigation(
            sig, daily_panel, session_close_prices
        ),
        mitigation_uncertainty_and_cost=mitigation_uncertainty_and_cost(
            sig, daily_panel, session_close_prices
        ),
        volatility_lookback_oos_study=volatility_lookback_oos_study(
            sig, daily_panel, session_close_prices
        ),
        forward_shadow_validation_design=forward_shadow_validation_design(
            sig, daily_panel, session_close_prices
        ),
        simple_risk_classifier_benchmarks=simple_risk_classifier_benchmarks(
            sig, daily_panel, session_close_prices
        ),
        volatility_regime_stability=volatility_regime_stability(daily_panel),
        input_provenance_audit=input_provenance_audit(csv_path or CACHE),
        volatility_gap_severity_calibration=volatility_gap_severity_calibration(
            daily_panel
        ),
        corporate_action_gap_audit=corporate_action_gap_audit(
            sig, daily_panel, session_close_prices
        ),
        session_open_validation=session_open_validation(df, sig, daily_panel),
        corrected_execution_ledger=corrected_execution_ledger(
            df, sig, daily_panel, session_close_prices
        ),
        close_proxy_policy_sensitivity=close_proxy,
        closing_auction_evidence_protocol=closing_auction_evidence_protocol(
            df, close_proxy
        ),
        closing_auction_runtime_readiness_audit=auction_runtime,
        exchange_calendar_closed_cycle_audit=(
            exchange_calendar_closed_cycle_audit(auction_runtime)
        ),
        pinned_calendar_misfire_materiality=(
            pinned_calendar_misfire_materiality(sig, gap)
        ),
        sanitized_holiday_runtime_evidence=(
            sanitized_holiday_runtime_evidence()
        ),
        historical_duplicate_writer_forensics=(
            duplicate_forensics
        ),
        live_bar_completion_timezone_audit=(
            bar_timezone_audit
        ),
        archived_incomplete_bar_materiality=(
            archived_incomplete_bar_materiality()
        ),
        trader_singleton_launch_safety_audit=(
            trader_singleton_launch_safety_audit()
        ),
        entry_acknowledgement_and_basis_audit=(
            entry_acknowledgement_and_basis_audit()
        ),
        unfilled_parent_phantom_trade_audit=(
            unfilled_parent_phantom_trade_audit()
        ),
        bracket_fill_identity_and_retention_audit=(
            bracket_fill_identity_and_retention_audit()
        ),
        concurrent_close_idempotency_audit=(
            concurrent_close_idempotency_audit()
        ),
        cross_generation_close_reentry_audit=(
            cross_generation_close_reentry_audit()
        ),
        quote_anchored_bracket_geometry_audit=(
            quote_anchored_bracket_geometry_audit()
        ),
        partial_fill_force_close_quantity_audit=(
            partial_fill_force_close_quantity_audit()
        ),
        force_close_completion_and_vwap_audit=(
            force_close_completion_and_vwap_audit()
        ),
        unresolved_close_back_to_back_reentry_audit=(
            unresolved_close_back_to_back_reentry_audit()
        ),
        broker_account_scope_audit=broker_account_scope_audit(),
        duplicate_writer_hold_counter_materiality=(
            duplicate_writer_hold_counter_materiality()
        ),
        broker_quote_field_precedence_audit=(
            broker_quote_field_precedence_audit(five_min)
        ),
        entry_snapshot_latency_audit=entry_snapshot_latency_audit(),
        market_data_provenance_label_audit=(
            market_data_provenance_label_audit()
        ),
        software_risk_trigger_outcome_audit=(
            software_risk_trigger_outcome_audit()
        ),
        software_risk_fallback_freshness_audit=(
            software_risk_fallback_freshness_audit(df)
        ),
        duplicate_bar_fallback_trigger_divergence_audit=(
            duplicate_bar_fallback_trigger_divergence_audit()
        ),
        broker_connection_exception_fallback_audit=(
            broker_connection_exception_fallback_audit()
        ),
        volatility_distribution_audit=volatility_distribution_audit(
            sig, daily_panel
        ),
        volatility_decision_time_audit=volatility_decision_time_audit(
            sig, daily_panel
        ),
        local_volatility_threshold_robustness=(
            local_volatility_threshold_robustness(sig, daily_panel)
        ),
        mitigation_path_decomposition=mitigation_path_decomposition(
            sig, daily_panel
        ),
        july_live_case=july_live_case(df),
    )


def required_artifacts():
    """Every committed fixture this study reads, with its declared SHA-256.

    These are NOT caches: they cannot be refetched offline, and four of them were
    silently dropped from the repo by a blanket `*.csv` .gitignore rule. They are
    the sole evidence behind roughly a third of RESEARCH_WEB.md.
    """
    return [
        (FIVE_MIN_AUDIT, "5-minute entry-bar ordering audit", FIVE_MIN_SOURCE_SHA256),
        (ONE_MIN_AUDIT, "1-minute entry-bar resolution audit", ONE_MIN_SOURCE_SHA256),
        (CORPORATE_ACTIONS_AUDIT, "TQQQ corporate actions 2010-2026",
         CORPORATE_ACTIONS_SOURCE_SHA256),
        (QQQ_DISTRIBUTIONS_AUDIT, "QQQ distributions 2010-2026",
         QQQ_ACTIONS_SOURCE_SHA256),
        (QUOTE_STALENESS_AUDIT, "TQQQ 5m quote-staleness summary", None),
    ]


def _derived_control(source: str, tokens) -> Dict[str, object]:
    """Presence of a safety control, DERIVED from source rather than asserted.

    WHY THIS EXISTS (RESEARCH_WEB.md F155). The audits in this module conclude that
    various live-safety controls are ABSENT, and they protect those conclusions with
    substring tokens that cite the *buggy* code. That makes every such tripwire
    one-directional: it fires when the evidence is deleted, and stays silent when the
    bug is FIXED. Measured by implementing three remediations these audits' own
    `falsification_gate` fields demand and diffing all 4,470 output leaves -- 18
    changed, 15 of them an echoed sha256, and ZERO of the 313 `False` absence claims
    flipped. A future engineer could do exactly what the gates ask and still get a
    green "control absent" report.

    A flag built from this helper flips the moment the control appears in the source,
    so the audit agrees with the engineer who fixed it.

    Deliberate error direction: tokens are matched against the whole source file
    rather than a narrowly-scoped schema block, so an unrelated occurrence can read
    as `present`. That over-approximation errs toward INVALIDATING the absence
    finding, which is the safe direction -- a false "present" prompts a human to
    re-examine, while a false "absent" silently perpetuates a stale claim.
    """
    matched = sorted(t for t in tokens if t in source)
    return {"present": bool(matched), "matched_tokens": matched}


def preflight_artifacts() -> None:
    """Report EVERY missing fixture at once, instead of dying on the first.

    Before this, `--selfcheck` raised a bare FileNotFoundError naming one file,
    so the gap was discovered one artifact per run with no hint that the files
    were never committed rather than merely deleted.
    """
    missing = data_cache.missing_artifacts(required_artifacts())
    if missing:
        raise SystemExit(
            data_cache.format_missing_artifacts(missing, repo_relative_to=REPO))


def run_source_audits() -> int:
    """Run every zero-argument source audit and report. Returns a process exit code.

    WHY THIS ENTRYPOINT EXISTS. The documented way in was `--selfcheck`, which dies
    immediately on four never-committed CSVs. That made the whole module look
    unreproducible offline — but the ~17 source audits behind F86-F104 read only
    `live/**` source text and need no market data at all. They were runnable the
    whole time; the entrypoint hid it. Measured: 17 of 18 complete in about two
    seconds total.

    A caveat these audits carry, worth knowing before trusting a green run: their
    tripwires are ONE-DIRECTIONAL. Each cites a substring of the buggy code, so it
    fires when the evidence is deleted and stays silent when the bug is REPAIRED.
    A green pass here means "the cited source still reads as it did", not "the
    safety controls are still absent".
    """
    import inspect as _inspect

    names = sorted(
        n for n in globals()
        if n.endswith("_audit") and callable(globals()[n])
        and not [p for p in _inspect.signature(globals()[n]).parameters.values()
                 if p.default is _inspect.Parameter.empty]
    )
    ok, failed = 0, []
    for name in names:
        try:
            globals()[name]()
            ok += 1
            print("  ok    %s" % name)
        except AssertionError as exc:
            failed.append(name)
            print("  FAIL  %s  (source contract changed: %s)" % (name, str(exc)[:70]))
        except Exception as exc:  # missing artifact, not a contract breach
            failed.append(name)
            print("  skip  %s  (%s: %s)" % (name, type(exc).__name__, str(exc)[:60]))
    print("\n%d/%d source audits ran offline" % (ok, len(names)))
    print("NOTE: a green run means the cited source is unchanged, NOT that the "
          "safety controls are still absent — these tripwires are one-directional.")
    return 0 if not failed else 1


def selfcheck() -> None:
    """Synthetic proof: a 0.5% modeled stop becomes the next-session open."""
    preflight_artifacts()
    idx = pd.DatetimeIndex(
        [
            "2026-01-05 14:30",
            "2026-01-05 15:30",
            "2026-01-06 09:30",
            "2026-01-06 10:30",
        ],
        tz=TZ,
    )
    d = pd.DataFrame(
        dict(
            open=[100.0, 100.0, 94.0, 94.5],
            high=[100.2, 100.2, 95.0, 95.0],
            low=[99.8, 99.8, 93.5, 94.0],
            close=[100.0, 100.0, 94.5, 94.7],
            volume=[1, 1, 1, 1],
            entry_signal=[1, 0, 0, 0],
        ),
        index=idx,
    )
    exact = simulate(
        d, 0.01, 0.005, 3,
        gap_aware=False, one_position=True, scan_entry_bar=True, slippage=0.0,
    )
    gap = simulate(
        d, 0.01, 0.005, 3,
        gap_aware=True, one_position=True, scan_entry_bar=True, slippage=0.0,
    )
    assert len(exact) == len(gap) == 1
    assert abs(float(exact.iloc[0]["return"]) - -0.005) < 1e-12
    assert abs(float(gap.iloc[0]["return"]) - -0.06) < 1e-12
    assert gap.iloc[0]["exit_type"] == "overnight_gap_stop"
    assert bool(gap.iloc[0]["overnight_gap_stop"])
    daily_open_gap = simulate(
        d, 0.01, 0.005, 3,
        gap_aware=True, one_position=True, scan_entry_bar=True, slippage=0.0,
        session_open_prices={pd.Timestamp("2026-01-06").date(): 93.0},
    )
    assert abs(float(daily_open_gap.iloc[0]["return"]) - -0.07) < 1e-12
    eod = simulate(
        d, 0.01, 0.005, 3,
        gap_aware=True, one_position=True, scan_entry_bar=True,
        flatten_eod=True, slippage=0.0,
    )
    assert eod.iloc[0]["exit_type"] == "eod_flatten"
    assert abs(float(eod.iloc[0]["return"])) < 1e-12
    cut = _cutoff_signal(d, 14)
    assert int((cut["entry_signal"] != 0).sum()) == 0

    # A synthetic 3x panel must recover beta=3 exactly.
    didx = pd.date_range("2026-01-01", periods=20, freq="B")
    base_gap = np.linspace(-0.02, 0.02, len(didx))
    pnl = pd.DataFrame(index=didx)
    pnl["SPY_close"] = 100.0
    pnl["SPY_open"] = 100.0 * (1 + base_gap)
    pnl["UPRO_close"] = 50.0
    pnl["UPRO_open"] = 50.0 * (1 + 3 * base_gap)
    scale = _pair_scaling(pnl, "SPY", "UPRO")
    assert abs(scale["beta"] - 3.0) < 1e-12
    assert abs(scale["r2"] - 1.0) < 1e-12
    audit = _durable_ordering_audit()
    assert audit["counts"] == {
        "target_first": 5,
        "stop_first": 11,
        "unresolved_5m": 3,
        "missing": 0,
    }
    assert audit["n_hourly_ambiguous_in_coverage"] == 19
    best_audit = _best_available_ordering(audit)
    assert best_audit["counts"] == {
        "target_first": 5,
        "stop_first": 12,
        "unresolved_5m": 2,
        "missing": 0,
    }
    assert best_audit["remaining_unresolved_entries"] == [
        "2026-06-23 09:30:00-04:00",
        "2026-06-24 09:30:00-04:00",
    ]
    actions = _load_corporate_actions()
    assert int((actions["dividend_per_share"] > 0).sum()) == 21
    assert int((_load_qqq_distributions() > 0).sum()) == 69
    credited, credit_rows = _credit_earned_distributions(
        gap, pd.Series([0.10], index=pd.DatetimeIndex(["2026-01-06"]))
    )
    assert len(credit_rows) == 1
    assert abs(
        float(credited.iloc[0]["return"])
        - float(gap.iloc[0]["return"])
        - 0.001
    ) < 1e-12
    mass = _beta_binomial_pmf(157, 5.5, 11.5)
    assert abs(float(mass.sum()) - 1.0) < 1e-12
    assert _minimum_wilson_n_below(0.3125, 53 / 157) == 1339
    design = _fixed_horizon_binomial_design(0.50, 21 / 34, 0.80)
    assert design["event_horizon"] == 115
    assert design["minimum_captures_for_success"] == 67
    assert abs(_binomial_upper_tail(34, 21, 0.50) - 0.1147405065) < 1e-10

    weekend = d.copy()
    weekend.index = pd.DatetimeIndex(
        [
            "2026-01-09 14:30",
            "2026-01-09 15:30",
            "2026-01-12 09:30",
            "2026-01-12 10:30",
        ],
        tz=TZ,
    )
    calendar_exit = simulate(
        weekend, 0.01, 0.005, 3,
        gap_aware=True, one_position=True, scan_entry_bar=True,
        flatten_before_gap_days=3, slippage=0.0,
    )
    assert calendar_exit.iloc[0]["exit_type"] == "calendar_flatten"
    assert abs(float(calendar_exit.iloc[0]["return"])) < 1e-12
    risk_exit = simulate(
        weekend, 0.01, 0.005, 3,
        gap_aware=True, one_position=True, scan_entry_bar=True,
        flatten_before_dates={pd.Timestamp("2026-01-12").date()},
        slippage=0.0,
    )
    assert risk_exit.iloc[0]["exit_type"] == "risk_flatten"
    assert abs(float(risk_exit.iloc[0]["return"])) < 1e-12

    # A position entered at a session open must never be "flattened" at the
    # previous session's close before it exists.
    opening_entry = pd.DataFrame(
        dict(
            open=[100.0, 100.0, 100.0, 94.0, 94.5],
            high=[100.2, 100.2, 100.2, 95.0, 95.0],
            low=[99.8, 99.8, 99.8, 93.5, 94.0],
            close=[100.0, 100.0, 100.0, 94.5, 94.7],
            volume=[1, 1, 1, 1, 1],
            entry_signal=[1, 0, 0, 0, 0],
        ),
        index=pd.DatetimeIndex(
            [
                "2026-01-09 15:30",
                "2026-01-12 09:30",
                "2026-01-12 15:30",
                "2026-01-13 09:30",
                "2026-01-13 10:30",
            ],
            tz=TZ,
        ),
    )
    opening_flatten = simulate(
        opening_entry, 0.20, 0.20, 4,
        gap_aware=True, one_position=True, scan_entry_bar=True,
        flatten_eod=True, slippage=0.0,
    )
    assert opening_flatten.iloc[0]["entry_timestamp"] == opening_entry.index[1]
    assert opening_flatten.iloc[0]["exit_timestamp"] == opening_entry.index[2]
    assert opening_flatten.iloc[0]["exit_type"] == "eod_flatten"

    duplicate = historical_duplicate_writer_forensics()
    assert duplicate["paired_signal_writes"]["paired_minute_slots"] == 210
    assert duplicate["paired_signal_writes"]["different_final_signal"] == 69
    assert (
        duplicate["paired_signal_writes"][
            "long_eligibility_disagreements_with_shorts_disabled"
        ]
        == 58
    )
    assert duplicate["entry_path"]["double_entry_event_slots"] == 7
    assert duplicate["entry_path"]["additional_ib_placeOrder_calls"] == 21
    assert duplicate["entry_path"]["trade_rows_matching_later_state"] == 7
    bar_timezone = live_bar_completion_timezone_audit(duplicate)
    assert bar_timezone["historical_natural_experiment"][
        "exact_structural_match"
    ]
    assert all(
        all(results.values())
        for results in bar_timezone["source_contract_tokens"].values()
    )
    controlled = {
        (row["host_environment"], row["api_tail"]): row
        for row in bar_timezone["fixed_clock_case"]["cases"]
    }
    assert controlled[("UTC", "includes_current")]["correct_completed_bar"]
    assert controlled[("UTC", "omits_current")]["correct_completed_bar"]
    assert (
        controlled[("Europe/London BST", "includes_current")][
            "failure_mode"
        ]
        == "accepts_incomplete_current_bar"
    )
    assert (
        controlled[("America/New_York EDT", "omits_current")][
            "failure_mode"
        ]
        == "drops_completed_bar_and_lags_one_extra_hour"
    )
    incomplete = archived_incomplete_bar_materiality()
    assert incomplete["signal_rows"]["incomplete"] == 297
    assert incomplete["signal_rows"]["incomplete_single_write_rows"] == 100
    assert incomplete["conservative_entry_attribution"][
        "strict_incomplete_entry_slots"
    ] == 40
    assert incomplete["conservative_entry_attribution"][
        "strict_slots_with_one_local_trade_row"
    ] == 40
    assert incomplete["local_trade_accounting"][
        "strict_incomplete_archive_confirmed_rows"
    ] == 33
    singleton = trader_singleton_launch_safety_audit()
    assert all(
        all(results.values())
        for results in singleton["source_contract_tokens"].values()
    )
    assert not singleton["control_inventory"][
        "cross_process_ownership_lock"
    ]["present"]
    assert not singleton["control_inventory"][
        "sqlite"
    ]["business_check_to_act_atomic"]
    assert singleton["constructive_interleavings"][
        "reachable_duplicate_bracket_path"
    ]
    path_by_name = {
        row["path"]: row for row in singleton["launch_path_matrix"]
    }
    assert path_by_name["systemd timer/service"][
        "full_ten_check_preflight"
    ]
    assert not path_by_name["foreground starter bypass"][
        "full_ten_check_preflight"
    ]
    assert not path_by_name["direct one-shot paper"][
        "scheduled_market_hours_wrapper"
    ]
    assert not path_by_name["direct live-money CLI"][
        "paper_only_guard"
    ]
    entry_ack = entry_acknowledgement_and_basis_audit()
    assert all(
        all(results.values())
        for results in entry_ack["source_contract_tokens"].values()
    )
    assert entry_ack["current_entry_path"][
        "application_place_order_calls"
    ] == 3
    assert entry_ack["current_entry_path"][
        "acknowledgement_checks"
    ] == 0
    assert not entry_ack["current_entry_path"][
        "actual_entry_fill_observed"
    ]
    assert entry_ack["archive_entry_basis_sensitivity"]["rows"] == 47
    assert abs(
        entry_ack["archive_entry_basis_sensitivity"][
            "recorded_compounded_return_pct"
        ]
        - 0.204664
    ) < 1e-6
    assert abs(
        entry_ack["archive_entry_basis_sensitivity"][
            "adverse_entry_slippage_break_even_bps"
        ]
        - 0.435020
    ) < 1e-6
    assert not entry_ack["prior_study_reproducibility"][
        "input_present_in_current_checkout"
    ]
    phantom = unfilled_parent_phantom_trade_audit()
    assert all(
        all(results.values())
        for results in phantom["source_contract_tokens"].values()
    )
    assert phantom["current_control_flow"][
        "inference_unknown_or_unverified_outcomes"
    ] == []
    assert phantom["archive_inference_join"][
        "inference_warning_events"
    ] == 6
    assert phantom["archive_inference_join"][
        "unique_local_trade_rows"
    ] == 5
    assert phantom["archive_inference_join"][
        "duplicate_warning_events"
    ] == 1
    assert phantom["archive_inference_join"][
        "explicit_same_cycle_reentries_after_inference"
    ] == 3
    assert abs(
        phantom["accounting_materiality"][
            "inferred_rows_compounded_return_pct"
        ]
        - 5.120432
    ) < 1e-6
    assert phantom["prior_result_robustness"][
        "explicitly_inferred_rows_inside_that_bucket"
    ] == 0
    fill_identity = bracket_fill_identity_and_retention_audit()
    assert not any(
        fill_identity["source_identity_field_presence"].values()
    )
    assert fill_identity["returned_fields"] == [
        "exit_type", "fill_price", "fill_time"
    ]
    assert fill_identity["archive_timing"][
        "entry_on_prior_utc_date"
    ] == 4
    assert abs(
        fill_identity["synthetic_partial_fill_price_case"][
            "correct_vwap"
        ]
        - 100.4
    ) < 1e-12
    close_race = concurrent_close_idempotency_audit()
    assert close_race["deterministic_two_reader_interleaving"][
        "duplicate_close_reachable"
    ]
    assert close_race["deterministic_two_reader_interleaving"][
        "recorded_trade_rows"
    ] == 2
    assert not close_race["transaction_contract"][
        "trades_unique_lifecycle_constraint"
    ]
    assert abs(
        close_race["duplicate_factor_sensitivity"][
            "endpoint_increase_pp"
        ]
        - 1.360114
    ) < 1e-6
    cross_generation = cross_generation_close_reentry_audit()
    assert cross_generation[
        "deterministic_cross_generation_interleaving"
    ]["reachability_proved"]
    assert cross_generation[
        "deterministic_cross_generation_interleaving"
    ]["stale_close_selected_bracket_id"] == "200"
    assert cross_generation[
        "deterministic_cross_generation_interleaving"
    ]["remaining_position_rows"] == 0
    assert abs(
        cross_generation[
            "deterministic_cross_generation_interleaving"
        ]["crossed_trade_record"]["return_discrepancy_pp"]
        - 50.5
    ) < 1e-12
    assert cross_generation["archive_observability"][
        "double_success_events"
    ] == 14
    assert cross_generation["archive_observability"][
        "double_success_events_with_parent_order_identity"
    ] == 0
    geometry = quote_anchored_bracket_geometry_audit()
    assert abs(
        geometry["no_rounding_fill_relative_bounds"][
            "long_at_parent_limit"
        ]["target_pct"]
        - 0.497512
    ) < 1e-6
    assert abs(
        geometry["no_rounding_fill_relative_bounds"][
            "long_at_parent_limit"
        ]["stop_pct"]
        + 0.995025
    ) < 1e-6
    assert geometry["strict_archive_sizing_join"][
        "matched_entry_events"
    ] == 66
    assert geometry["strict_archive_sizing_join"][
        "unresolved_entry_events"
    ] == 6
    assert abs(
        geometry["strict_archive_sizing_join"][
            "maximum_parent_limit_case"
        ]["implied_account_allocation_pct_interval"][1]
        - 10.382687
    ) < 1e-6
    partial_qty = partial_fill_force_close_quantity_audit()
    assert partial_qty["current_quantity_contract"][
        "force_close_call_count"
    ] == 3
    assert partial_qty["current_quantity_contract"][
        "force_close_calls_all_use_local_position_qty"
    ]
    assert partial_qty["deterministic_partial_fill_overshoot"][
        "reachability_proved"
    ]
    assert partial_qty["deterministic_partial_fill_overshoot"][
        "fifty_share_example"
    ]["final_signed_position"] == -50
    assert partial_qty["cancellation_acknowledgement_race"][
        "confirmation_fields_present"
    ] == 0
    assert partial_qty["archive_observability"][
        "hypothetical_half_fill_opposite_qty_range"
    ] == {"min": 55, "median": 84.0, "max": 135}
    close_completion = force_close_completion_and_vwap_audit()
    assert close_completion["current_completion_contract"][
        "completion_fields_present"
    ] == 0
    assert close_completion["deterministic_first_partial_execution"][
        "reachability_proved"
    ]
    assert close_completion["deterministic_first_partial_execution"][
        "final_signed_broker_qty_if_no_later_fill"
    ] == 40
    assert close_completion["multi_execution_price_accounting"][
        "correct_vwap"
    ] == 100.4
    assert close_completion["archive_observability"][
        "explicit_time_exit_fill_unavailable_events"
    ] == 4
    assert close_completion["timeout_branch"][
        "pending_close_trader_call_counts"
    ]["mark_pending_close"] == 0
    reentry_race = unresolved_close_back_to_back_reentry_audit()
    assert reentry_race["current_reentry_contract"][
        "entry_working_order_fields_present"
    ] == 0
    assert reentry_race["deterministic_nonterminal_close_collision"][
        "reachability_proved"
    ]
    assert reentry_race["deterministic_nonterminal_close_collision"][
        "full_late_close_example"
    ]["final_signed_broker_qty"] == 0
    assert reentry_race["archive_observability"][
        "all_back_to_back_application_entries"
    ] == 32
    assert reentry_race["archive_observability"][
        "fill_unavailable_then_back_to_back_entries"
    ] == 2
    account_scope = broker_account_scope_audit()
    assert account_scope["current_identity_contract"][
        "account_scope_fields_present"
    ] == 0
    assert account_scope["deterministic_account_summary_ordering"][
        "result_depends_on_callback_order"
    ]
    assert account_scope["deterministic_account_summary_ordering"][
        "sizing_case"
    ]["maximum_qty_multiple_vs_account_a"] == 10.0
    assert account_scope["deterministic_position_ordering"][
        "direction_can_flip"
    ]
    assert account_scope["archive_observability"][
        "account_model_identity_pattern_counts"
    ] == {
        '"account(?:_id|_code)?"': 0,
        '"model(?:_code)?"': 0,
        '"con_?id"': 0,
        '"perm_?id"': 0,
    }
    hold_counter = duplicate_writer_hold_counter_materiality()
    assert hold_counter["deterministic_two_writer_increment"][
        "reachability_proved"
    ]
    assert hold_counter["archived_time_exit_intervals"][
        "time_exit_trades"
    ] == 9
    assert hold_counter["archived_time_exit_intervals"][
        "strict_exact_double_intervals"
    ] == 7
    assert hold_counter["archived_time_exit_intervals"][
        "exact_five_slot_half_holds"
    ] == 7
    assert hold_counter["archived_time_exit_intervals"][
        "compressed_below_ten_distinct_slots"
    ] == 8
    quote_precedence = broker_quote_field_precedence_audit(
        load_five_min(refresh=False)
    )
    assert quote_precedence["current_selection_contract"][
        "snapshot_sleep_after_blocking_return_count"
    ] == 2
    assert quote_precedence[
        "deterministic_precedence_counterexamples"
    ]["close_case_long_parent_below_ask_bps"] == 871.934605
    assert quote_precedence[
        "deterministic_precedence_counterexamples"
    ]["high_last_case_long_stop_already_crossed"]
    assert quote_precedence["pinned_five_min_materiality"][
        "lag_windows"
    ]["15"]["moves_abs_over_50bps"] == 964
    assert quote_precedence["pinned_five_min_materiality"][
        "prior_close_hourly_cycle_proxy"
    ]["moves_abs_over_50bps"] == 248
    assert quote_precedence["archive_observability"][
        "matched_entry_events"
    ] == 3
    snapshot_latency = entry_snapshot_latency_audit()
    assert snapshot_latency["archived_source_identity"][
        "current_broker_and_trader_byte_match_archive"
    ]
    assert snapshot_latency["current_latency_contract"][
        "minimum_snapshot_requests_per_entry"
    ] == 2
    assert snapshot_latency["archived_timing"]["entry_events"] == 72
    assert snapshot_latency["archived_timing"][
        "strict_same_minute_signal_joins"
    ] == 70
    assert snapshot_latency["archived_timing"][
        "schedule_to_application_entry_seconds"
    ]["at_least_30_seconds"] == 22
    provenance_label = market_data_provenance_label_audit()
    assert provenance_label["deterministic_indistinguishability"][
        "false_live_label_reachable"
    ]
    assert provenance_label["provenance_contract"][
        "mark_time_is_source_quote_time"
    ] is False
    assert provenance_label["downstream_materiality"][
        "software_stop_uses_resolved_mark"
    ]
    assert provenance_label["archive_observability"][
        "delayed_incident_rate_identified"
    ] is False
    software_trigger = software_risk_trigger_outcome_audit()
    assert software_trigger["archived_trigger_evidence"][
        "trigger_events"
    ] == 6
    assert software_trigger["archived_trigger_evidence"][
        "unique_primary_close_joins"
    ] == 4
    assert software_trigger["archived_trigger_evidence"][
        "duplicate_post_close_triggers"
    ] == 2
    assert software_trigger["archived_trigger_evidence"][
        "all_unique_recorded_exits_beyond_stop"
    ]
    fallback_freshness = software_risk_fallback_freshness_audit(
        load_hourly(refresh=False)
    )
    assert fallback_freshness["current_fallback_contract"][
        "full_path_explicit_sleep_and_backoff_seconds"
    ] == 20
    assert fallback_freshness[
        "archived_prior_close_counterfactual"
    ]["unique_trade_cycle_slots"] == 160
    assert fallback_freshness[
        "archived_prior_close_counterfactual"
    ]["false_stop"]["strict_slots"] == 62
    assert fallback_freshness[
        "archived_prior_close_counterfactual"
    ]["false_take_profit"]["strict_slots"] == 17
    bar_divergence = duplicate_bar_fallback_trigger_divergence_audit()
    assert bar_divergence["archived_divergence"][
        "multi_writer_slots"
    ] == 114
    assert bar_divergence["archived_divergence"][
        "stop_divergent_slots"
    ] == 5
    assert bar_divergence["archived_divergence"][
        "take_profit_divergent_slots"
    ] == 5
    assert bar_divergence["archived_divergence"][
        "observed_last_close_trigger_incidents"
    ] == 0
    connection_fallback = broker_connection_exception_fallback_audit()
    assert connection_fallback["archived_connection_failures"][
        "events"
    ] == 46
    assert connection_fallback["archived_connection_failures"][
        "unique_position_open_cycle_slots"
    ] == 17
    assert connection_fallback["current_exception_contract"][
        "connection_refused_reaches_yfinance_fallback"
    ] is False


def _print(result: Dict[str, object]) -> None:
    d = result["data"]
    c = result["config"]
    r = result["raw_overnight_gaps"]
    p = result["live_shaped_replay"]
    eod = result["end_of_day_flatten_counterfactual"]
    wf = result["execution_waterfall"]
    mf = result["mitigation_frontier"]
    cv = result["session_close_validation"]
    hist = result["cross_instrument_history"]
    dep = result["gap_dependence_and_volatility"]
    vm = result["volatility_conditioned_mitigation"]
    robust = result["mitigation_uncertainty_and_cost"]
    lookback = result["volatility_lookback_oos_study"]
    forward = result["forward_shadow_validation_design"]
    simple = result["simple_risk_classifier_benchmarks"]
    stability = result["volatility_regime_stability"]
    provenance = result["input_provenance_audit"]
    severity = result["volatility_gap_severity_calibration"]
    actions = result["corporate_action_gap_audit"]
    open_validation = result["session_open_validation"]
    ledger = result["corrected_execution_ledger"]
    close_policy = result["close_proxy_policy_sensitivity"]
    auction_protocol = result["closing_auction_evidence_protocol"]
    auction_runtime = result["closing_auction_runtime_readiness_audit"]
    calendar_cycles = result["exchange_calendar_closed_cycle_audit"]
    calendar_materiality = result["pinned_calendar_misfire_materiality"]
    holiday_evidence = result["sanitized_holiday_runtime_evidence"]
    duplicate_forensics = result["historical_duplicate_writer_forensics"]
    bar_timezone = result["live_bar_completion_timezone_audit"]
    incomplete_materiality = result[
        "archived_incomplete_bar_materiality"
    ]
    singleton_audit = result[
        "trader_singleton_launch_safety_audit"
    ]
    entry_ack = result[
        "entry_acknowledgement_and_basis_audit"
    ]
    phantom = result[
        "unfilled_parent_phantom_trade_audit"
    ]
    fill_identity = result[
        "bracket_fill_identity_and_retention_audit"
    ]
    close_race = result[
        "concurrent_close_idempotency_audit"
    ]
    cross_generation = result[
        "cross_generation_close_reentry_audit"
    ]
    geometry = result[
        "quote_anchored_bracket_geometry_audit"
    ]
    partial_qty = result[
        "partial_fill_force_close_quantity_audit"
    ]
    close_completion = result[
        "force_close_completion_and_vwap_audit"
    ]
    reentry_race = result[
        "unresolved_close_back_to_back_reentry_audit"
    ]
    account_scope = result["broker_account_scope_audit"]
    hold_counter = result[
        "duplicate_writer_hold_counter_materiality"
    ]
    quote_precedence = result[
        "broker_quote_field_precedence_audit"
    ]
    snapshot_latency = result["entry_snapshot_latency_audit"]
    provenance_label = result["market_data_provenance_label_audit"]
    software_trigger = result["software_risk_trigger_outcome_audit"]
    fallback_freshness = result[
        "software_risk_fallback_freshness_audit"
    ]
    bar_divergence = result[
        "duplicate_bar_fallback_trigger_divergence_audit"
    ]
    connection_fallback = result[
        "broker_connection_exception_fallback_audit"
    ]
    vol_distribution = result["volatility_distribution_audit"]
    vol_timing = result["volatility_decision_time_audit"]
    local_threshold = result["local_volatility_threshold_robustness"]
    path_decomposition = result["mitigation_path_decomposition"]
    j = result["july_live_case"]
    print("=" * 104)
    print("STUDIES #16–69 — TQQQ EXECUTION, GAP RISK, MITIGATION, AND HISTORY")
    print("=" * 104)
    print(
        "Data: {bars} full-session hourly bars / {sessions} sessions, "
        "{start} -> {end} ({timezone}; median {median_bars_per_session:.0f} bars/day)"
        .format(**d)
    )
    print(
        "Live shape: target={target_pct:.2f}% stop={stop_pct:.2f}% "
        "cap={max_trade_bars} bars position={position_fraction_pct:.0f}% "
        "slippage={slippage_bps:.0f}bps allow_shorts={allow_shorts}".format(**c)
    )
    print(
        "Engine cross-check: PASS, n={n}, max |return diff|={max_abs_return_diff:.1e}"
        .format(**result["engine_crosscheck"])
    )
    print()
    print("PART A — EXECUTION-ASSUMPTION WATERFALL (FIXED-10% NORMALIZATION)")
    print("  %-25s %6s %7s %7s %7s %6s %6s" %
          ("step", "trades", "long", "short", "total%", "maxDD", "gaps"))
    for row in wf["rows"]:
        print(
            "  %-25s %6d %7d %7d %+7.2f %+6.2f %6d"
            % (
                row["step"], row["n"], row["longs"], row["shorts"],
                row["total_return_pct"], row["max_drawdown_pct"],
                row["overnight_gap_stops"],
            )
        )
    print("  note: " + wf["accounting"])
    eb = wf["entry_bar_paired_effect"]
    cal = eb["five_min_ordering_calibration"]
    best_cal = eb["best_available_ordering_calibration"]
    print(
        "  paired entry-bar audit: %d/%d exit in entry hour; delayed N+2 %.2f%%, "
        "immediate ordering bound %.2f%% to %.2f%%"
        % (
            eb["n_entry_bar_exits"], eb["n_paired"],
            eb["delayed_n_plus_2"]["total_return_pct"],
            eb["ordering_bound_total_return_pct"][0],
            eb["ordering_bound_total_return_pct"][1],
        )
    )
    print(
        "  5m calibration: target first %d, stop first %d, unresolved %d "
        "(target-first Wilson95 %.1f%%–%.1f%%)"
        % (
            cal["counts"]["target_first"], cal["counts"]["stop_first"],
            cal["counts"]["unresolved_5m"],
            cal["target_first_wilson95_pct"][0],
            cal["target_first_wilson95_pct"][1],
        )
    )
    print(
        "  best available (+%d one-minute resolution): target first %d, "
        "stop first %d, unresolved %d (target-first Wilson95 %.1f%%–%.1f%%)"
        % (
            len(best_cal["one_min_resolutions"]),
            best_cal["counts"]["target_first"],
            best_cal["counts"]["stop_first"],
            best_cal["counts"]["unresolved_5m"],
            best_cal["target_first_wilson95_pct"][0],
            best_cal["target_first_wilson95_pct"][1],
        )
    )
    decisions = eb["calibration_decision"]
    decision = decisions["paired_overlap_diagnostic"]
    posterior = {
        row["scenario"]: row
        for row in decision["posterior_predictive_sensitivity"]
    }
    print(
        "  calibration decision: need %d/%d target-first (%.2f%%) to break even; "
        "%d/%d resolved gives %.1f%% predictive P(total>0), sensitivity %.1f%%–%.1f%%"
        % (
            decision["minimum_target_first_count_for_nonnegative_terminal_return"],
            decision["n_unknown_full_history_dual_hit_entries"],
            decision["break_even_target_first_pct"],
            decision["current_resolved_target_first_events"],
            decision["current_resolved_five_min_events"],
            posterior["exclude_unresolved"][
                "predictive_probability_total_return_positive_pct"
            ],
            posterior["unresolved_as_stop_first"][
                "predictive_probability_total_return_positive_pct"
            ],
            posterior["unresolved_as_target_first"][
                "predictive_probability_total_return_positive_pct"
            ],
        )
    )
    live_gap_decision = decisions["one_position_gap_aware"]
    live_gap_posterior = {
        row["scenario"]: row
        for row in live_gap_decision["posterior_predictive_sensitivity"]
    }
    print(
        "  gap-aware one-position decision: need %d/%d target-first (%.2f%%) vs "
        "%d/%d observed; predictive P(total>0) %.1f%%, unresolved sensitivity %.1f%%–%.1f%%"
        % (
            live_gap_decision[
                "minimum_target_first_count_for_nonnegative_terminal_return"
            ],
            live_gap_decision["n_unknown_full_history_dual_hit_entries"],
            live_gap_decision["break_even_target_first_pct"],
            live_gap_decision["current_resolved_target_first_events"],
            live_gap_decision["current_resolved_five_min_events"],
            live_gap_posterior["exclude_unresolved"][
                "predictive_probability_total_return_positive_pct"
            ],
            live_gap_posterior["unresolved_as_stop_first"][
                "predictive_probability_total_return_positive_pct"
            ],
            live_gap_posterior["unresolved_as_target_first"][
                "predictive_probability_total_return_positive_pct"
            ],
        )
    )
    print()
    print("PART B — CURRENT-LIVE GAP MEASUREMENT")
    print("RAW CLOSE->NEXT-OPEN TQQQ GAPS")
    print(
        "  n={n}  mean={mean_bps:+.1f}bps  median={median_bps:+.1f}bps  "
        "<=-0.5%: {pct_le_minus_0_5:.1f}%  <=-1%: {pct_le_minus_1:.1f}%  "
        "<=-2%: {pct_le_minus_2:.1f}%  <=-4%: {pct_le_minus_4:.1f}%".format(**r)
    )
    print("  worst: " + ", ".join("%s %+.2f%%" % (x["date"], x["gap_pct"]) for x in r["worst"][:5]))
    print(
        "  upside tail (short risk): >=+0.5% {pct_ge_plus_0_5:.1f}%  "
        ">=+1% {pct_ge_plus_1:.1f}%  >=+2% {pct_ge_plus_2:.1f}%  "
        ">=+4% {pct_ge_plus_4:.1f}%".format(**r)
    )
    print("  best:  " + ", ".join("%s %+.2f%%" % (x["date"], x["gap_pct"]) for x in r["best"][:5]))
    print()
    print("LIVE-SHAPED ONE-POSITION REPLAY")
    print(
        "  trades={n} held_overnight={held} gap-affected={ga} overnight-gap-stops={ogs}"
        .format(
            n=p["exact"]["n"],
            held=p["n_held_overnight"],
            ga=p["n_gap_affected"],
            ogs=p["n_overnight_gap_stops"],
        )
    )
    print(
        "  exact-stop: total={total_return_pct:+.3f}% maxDD={max_drawdown_pct:+.3f}% "
        "WR={win_rate_pct:.1f}%".format(**p["exact"])
    )
    print(
        "  gap-aware: total={total_return_pct:+.3f}% maxDD={max_drawdown_pct:+.3f}% "
        "WR={win_rate_pct:.1f}%".format(**p["gap_aware"])
    )
    print(
        "  observed fill-model damage: {trade:+.3f}pp of gross trade returns; "
        "{capital:+.3f}pp at fixed 10% sizing".format(
            trade=p["cumulative_trade_return_delta_pct"],
            capital=p["fixed_10pct_capital_delta_pp"],
        )
    )
    print(
        "  {nstop} modeled stop exits -> mean-matching constant stop penalty "
        "{mean:.1f}bps; actual gap damage median={median:.2f}pp "
        "p90={p90:.2f}pp max={maximum:.2f}pp".format(
            nstop=p["n_modeled_stop_exits"],
            mean=p["calibrated_mean_stop_slippage_bps"],
            **p["gap_damage_pp"]
        )
    )
    print(
        "  direction: long {long[gap_affected]}/{long[trades]} gaps, "
        "{long[cumulative_trade_return_delta_pct]:+.2f}pp damage; "
        "short {short[gap_affected]}/{short[trades]} gaps, "
        "{short[cumulative_trade_return_delta_pct]:+.2f}pp damage"
        .format(**p["by_direction"])
    )
    for e in sorted(p["events"], key=lambda x: x["understatement_pp"], reverse=True)[:10]:
        print(
            "    {exit}: entry {entry_price:.2f} -> gap fill {gap_fill:.2f}; "
            "modeled {modeled_return_pct:+.2f}% vs gap-aware "
            "{gap_aware_return_pct:+.2f}% ({understatement_pp:.2f}pp understated)"
            .format(**e)
        )
    print(
        "  EOD-flatten counterfactual: exits={n}; total={total:+.3f}% "
        "(vs gap-aware {dret:+.3f}pp), maxDD={dd:+.3f}% "
        "(improvement {ddd:+.3f}pp)".format(
            n=eod["n_eod_exits"],
            total=eod["metrics"]["total_return_pct"],
            dret=eod["versus_gap_aware_total_return_pp"],
            dd=eod["metrics"]["max_drawdown_pct"],
            ddd=eod["versus_gap_aware_maxdd_pp"],
        )
    )
    print(
        "  max-bars sensitivity: "
        + "; ".join(
            "%s bars: gaps=%d, fixed-10%% damage=%+.2fpp, total %.2f%%->%.2f%%"
            % (
                bars,
                row["gap_affected"],
                row["fixed_10pct_capital_delta_pp"],
                row["exact_total_return_pct"],
                row["gap_total_return_pct"],
            )
            for bars, row in result["max_bar_sensitivity"].items()
        )
    )
    print()
    print("PART C — MITIGATION FRONTIER (DESCRIPTIVE, NOT PARAMETER SELECTION)")
    print("  %-36s %6s %7s %7s %7s %6s %5s" %
          ("policy", "trades", "total%", "maxDD", "heldON", "gaps", "gate"))
    for row in mf["policy_rows"]:
        print(
            "  %-36s %6d %+7.2f %+7.2f %7d %6d %5s"
            % (
                row["policy"], row["n"], row["total_return_pct"],
                row["max_drawdown_pct"], row["held_overnight"],
                row["overnight_gap_stops"],
                "PASS" if row["risk_gate_pass"] else "—",
            )
        )
    print("  stop-width risk surface (target fixed 1%; >=1% is stress-only):")
    print("    %6s %6s %6s %8s %8s %8s %8s" %
          ("stop%", "valid", "gaps", "exact%", "gap%", "damage", "maxGap"))
    for row in mf["stop_width_rows"]:
        print(
            "    %6.2f %6s %6d %+8.2f %+8.2f %+8.2f %8.2f"
            % (
                row["stop_pct"], str(row["production_valid"]),
                row["gap_stops"], row["exact_total_return_pct"],
                row["gap_total_return_pct"], row["fixed10_damage_pp"],
                row["conditional_gap_max_pp"],
            )
        )
    print("  calendar slices:")
    for year, row in mf["calendar_slices"].items():
        print(
            "    %s: holds=%d gaps=%d total %.2f%% -> %.2f%%, maxDD %.2f%% -> %.2f%%"
            % (
                year, row["held_overnight"], row["gap_stops"],
                row["exact"]["total_return_pct"], row["gap_aware"]["total_return_pct"],
                row["exact"]["max_drawdown_pct"], row["gap_aware"]["max_drawdown_pct"],
            )
        )
    print("  gap events by entry hour ET: " + json.dumps(mf["gap_events_by_entry_hour_et"], sort_keys=True))
    cg = mf["calendar_gap_attribution"]
    long_gap_events = sum(
        row["events"]
        for days, row in cg["by_calendar_gap_days"].items()
        if int(days) >= 3
    )
    long_gap_damage = sum(
        row["cumulative_trade_damage_pp"]
        for days, row in cg["by_calendar_gap_days"].items()
        if int(days) >= 3
    )
    print(
        "  weekend/long-closure attribution: %d/%d events, %.2f/%.2fpp damage "
        "(%.1f%%); top-5 events carry %.1f%%"
        % (
            long_gap_events, cg["total_events"], long_gap_damage,
            cg["cumulative_trade_damage_pp"],
            long_gap_damage / cg["cumulative_trade_damage_pp"] * 100,
            cg["damage_concentration_pct"]["top_5"],
        )
    )
    eod_policy = next(
        row for row in mf["policy_rows"] if row["policy"] == "flatten_end_of_day"
    )
    print(
        "  EOD first-order extra-cost break-even: %.1fbps per EOD exit across %d exits"
        % (
            eod_policy["first_order_break_even_extra_cost_bps_per_eod_exit"],
            eod_policy["eod_exits"],
        )
    )
    print(
        "  close-source audit (%d sessions): median |hourly-daily| %.2fbps, "
        "p95 %.2fbps, max %.2fbps, >5bps %.2f%%"
        % (
            cv["n_sessions"],
            cv["median_abs_diff_bps"],
            cv["p95_abs_diff_bps"],
            cv["maximum_abs_diff_bps"],
            cv["pct_abs_diff_gt_5bps"],
        )
    )
    print()
    print("KNOWN JULY LIVE CASE (F47) — independent market-data cross-check")
    print(
        "  entry={entry:.2f} stop={stop_price:.2f}; first-hour open={first_hour_open:.2f}; "
        "modeled={modeled_return_pct:+.2f}% gap-aware={gap_aware_hourly_open_return_pct:+.2f}% "
        "observed fill={observed_live_fill:.2f} ({observed_live_return_pct:+.2f}%); "
        "hourly-open vs fill={open_vs_observed_fill_bps:+.1f}bps".format(**j)
    )
    print()
    print("PART D — 2010-2026 CROSS-INSTRUMENT OVERNIGHT GAP HISTORY")
    print("  %-6s %6s %8s %8s %8s %8s %8s %12s" %
          ("ticker", "n", "q01%", "ES1%", "<=-.5%", "<=-2%", "worst%", "worst date"))
    for ticker in DAILY_TICKERS:
        row = hist["ticker_stats"][ticker]
        print(
            "  %-6s %6d %+8.2f %+8.2f %8.2f %8.2f %+8.2f %12s"
            % (
                ticker, row["n"], row["q01_pct"], row["expected_shortfall_1pct"],
                row["down_0_5_pct"], row["down_2_pct"], row["q_min_pct"],
                row["worst_date"],
            )
        )
    print("  leverage scaling (leveraged gap = alpha + beta * underlying gap):")
    for row in hist["leverage_scaling"]:
        print(
            "    %s/%s: beta=%.2f R2=%.3f median|gap|x=%.2f q01-loss-x=%.2f "
            "residual-min=%+.2f%%"
            % (
                row["leveraged"], row["base"], row["beta"], row["r2"],
                row["median_abs_gap_ratio"], row["q01_loss_ratio"],
                row["residual_min_pct"],
            )
        )
    risk10 = next(
        row
        for row in hist["tqqq_account_risk_translation"]["position_rows"]
        if row["position_fraction_pct"] == 10.0
    )
    print(
        "  10%% TQQQ position -> account gap stress: q01=%+.2f%%, ES1=%+.2f%%, "
        "historical worst=%+.2f%%"
        % (
            risk10["account_q01_gap_pct"],
            risk10["account_expected_shortfall_1pct"],
            risk10["account_historical_worst_pct"],
        )
    )
    print()
    print("PART E — GAP DEPENDENCE AND LAGGED-VOLATILITY RISK CONTROL")
    serial = dep["serial_dependence"]
    print(
        "  <=-2%% gaps: %d/%d = %.2f%%; iid Wilson95 %.2f%%–%.2f%%; "
        "block20 bootstrap95 %.2f%%–%.2f%%"
        % (
            dep["severe_gap_count"], dep["n_nights"], dep["severe_gap_rate_pct"],
            dep["severe_gap_rate_iid_wilson95_pct"][0],
            dep["severe_gap_rate_iid_wilson95_pct"][1],
            dep["severe_gap_rate_block20_bootstrap95_pct"][0],
            dep["severe_gap_rate_block20_bootstrap95_pct"][1],
        )
    )
    for row in serial["conditional_rows"]:
        print(
            "  after %-39s: %.2f%% (%d/%d), %.2fx baseline"
            % (
                row["condition"], row["conditional_probability_pct"],
                row["severe_gaps"], row["conditioned_nights"], row["risk_ratio"],
            )
        )
    clusters = dep["cluster_extremes"]
    print(
        "  clusters: max %d severe gaps/5 sessions, %d/20; "
        "worst five-session summed gap %.2f%% ending %s"
        % (
            clusters["maximum_severe_gaps_in_5_sessions"],
            clusters["maximum_severe_gaps_in_20_sessions"],
            clusters["worst_five_session_sum_gap_pct"],
            clusters["worst_five_session_sum_end"],
        )
    )
    print("  strategy-conditioned lagged-volatility flatten:")
    print("    %6s %6s %7s %8s %8s %7s %5s" %
          ("vol>=", "exits", "gaps-", "total%", "maxDD", "costbp", "gate"))
    for row in vm["policy_rows"]:
        print(
            "    %5.1f%% %6d %6.1f%% %+8.2f %+8.2f %7.1f %5s"
            % (
                row["lagged_qqq_vol_threshold_pct"],
                row["risk_flatten_exits"],
                row["gap_reduction_pct"],
                row["total_return_pct"],
                row["max_drawdown_pct"],
                row["first_order_break_even_extra_cost_bps_per_exit"],
                "PASS" if row["risk_gate_pass"] else "—",
            )
        )
    print()
    print("PART F — MITIGATION DEPENDENCE AND EXTRA-COST STRESS")
    for row in robust["policy_rows"]:
        ci20 = row[
            "paired_daily_log_block_bootstrap_relative_wealth95_pct"
        ]["20"]
        cost40 = next(
            cost for cost in row["extra_cost_sensitivity"]
            if cost["extra_cost_bps_per_flatten_exit"] == 40
        )
        print(
            "  %-34s exits=%3d delta=%+5.2fpp relative-wealth block20 CI "
            "[%+5.2f,%+5.2f]%%; delta @40bps=%+5.2fpp"
            % (
                row["policy"], row["flatten_exits"],
                row["total_return_delta_vs_baseline_pp"],
                ci20[0], ci20[1],
                cost40["total_return_delta_vs_baseline_pp"],
            )
        )
    print()
    print("PART G — LAGGED-VOLATILITY LOOKBACK / EARLY-SPLIT FALSIFICATION")
    print("  %8s %8s %10s %10s %7s %8s %8s %5s" %
          ("lookback", "chosen", "train cap", "test cap", "exits", "gaps-", "total%", "gate"))
    for row in lookback["lookback_rows"]:
        strategy = row["strategy_2024_2026"]
        print(
            "  %7dd %7.1f%% %9.1f%% %9.1f%% %7d %7.1f%% %+8.2f %5s"
            % (
                row["lookback_sessions"],
                row["selected_threshold_pct"],
                row["training_2010_2019"]["severe_gap_capture_pct"],
                row["classifier_test_2020_2026"]["severe_gap_capture_pct"],
                strategy["risk_flatten_exits"],
                strategy["gap_reduction_pct"],
                strategy["total_return_pct"],
                "PASS" if strategy["risk_gate_pass"] else "—",
            )
        )
    print()
    print("PART H — FORWARD PAPER-SHADOW EVIDENCE HORIZONS")
    primary80 = forward["fixed_horizon_gates"][
        "primary_strategy_gap_capture"
    ]["designs"]["80"]
    surrogate = forward["fixed_horizon_gates"][
        "surrogate_unconditional_classifier"
    ]["conservative_80pct_power_design"]
    print(
        "  strategy capture: historical 21/34 (one-sided p=%.4f vs 50%%); "
        "new fixed horizon %d events, need >=%d captures for 80%% power "
        "(~%.2f years at observed rate)"
        % (
            forward["historical_inputs_not_forward_evidence"][
                "one_sided_exact_p_value_vs_50pct"
            ],
            primary80["event_horizon"],
            primary80["minimum_captures_for_success"],
            primary80["expected_years_at_observed_event_rate"],
        )
    )
    print(
        "  unconditional classifier surrogate: %d severe gaps, need >=%d captures "
        "(~%.2f years); cannot substitute for strategy endpoint"
        % (
            surrogate["event_horizon"],
            surrogate["minimum_captures_for_success"],
            surrogate["expected_years_at_historical_event_rate"],
        )
    )
    dependence = forward["fixed_horizon_gates"][
        "primary_strategy_gap_capture"
    ]["heuristic_dependence_sensitivity"]
    print(
        "  clustering sensitivity (heuristic design effect 1.25/1.5/2.0): "
        "%s"
        % ", ".join(
            "%d events / %.2fyr"
            % (
                row["inflated_strategy_event_horizon"],
                row["expected_years_at_observed_event_rate"],
            )
            for row in dependence[1:]
        )
    )
    print(
        "  auction-cost break-even: %.1fbps/flatten; planning horizons by cost "
        "scenario: %s"
        % (
            forward["fixed_horizon_gates"]["auction_cost"][
                "first_order_break_even_extra_cost_bps"
            ],
            ", ".join(
                "%s=%s exits"
                % (row["scenario"], row["fixed_minimum_exit_sample"])
                for row in forward["fixed_horizon_gates"]["auction_cost"][
                    "scenario_rows"
                ]
            ),
        )
    )
    print()
    print("PART I — SIMPLE RISK-CLASSIFIER BENCHMARKS")
    print("  %-42s %8s %8s %6s %6s %7s %5s" %
          ("policy", "exposure", "capture", "lift", "exits", "gaps-", "gate"))
    for row in simple["policy_rows"]:
        strategy = row["strategy"]
        print(
            "  %-42s %7.1f%% %7.1f%% %6.2f %6d %6.1f%% %5s"
            % (
                row["policy"],
                row["exposure_removed_pct"],
                row["severe_gap_capture_pct"],
                row["capture_lift_vs_random"],
                strategy["risk_flatten_exits"],
                strategy["gap_reduction_pct"],
                "PASS" if strategy["risk_gate_pass"] else "—",
            )
        )
    print()
    print("PART J — VOLATILITY CLASSIFIER ANNUAL REGIME STABILITY")
    print("  %6s %6s %7s %8s %6s %8s" %
          ("year", "gaps", "exposure", "capture", "lift", "precision"))
    for row in stability["annual_rows"]:
        print(
            "  %6s %6d %6.1f%% %7.1f%% %6.2f %7.1f%%"
            % (
                row["period"],
                row["severe_gaps"],
                row["exposure_removed_pct"],
                row["severe_gap_capture_pct"],
                row["capture_lift_vs_random"],
                row["flagged_severe_gap_precision_pct"],
            )
        )
    print()
    print("PART K — INPUT PROVENANCE / RECONSTRUCTION AUDIT")
    print("  hashed study inputs present and byte-identical: %s" %
          provenance["byte_identical_inputs_present"])
    for row in provenance["cache_rows"]:
        print(
            "  %-43s %7s %9s  %s"
            % (
                row["input"],
                "MATCH" if row["byte_identical_to_study_snapshot"] else "MISSING/DRIFT",
                ("%dkB" % (row["bytes"] // 1024))
                if row["bytes"] is not None else "—",
                row["observed_sha256"][:12]
                if row["observed_sha256"] else "no bytes",
            )
        )
    print()
    print("PART L — VOLATILITY CAPTURE BY GAP SEVERITY")
    print("  %10s %7s %8s %7s %9s" %
          ("loss >=", "events", "capture", "lift", "unflagged"))
    for row in severity["severity_rows"]:
        print(
            "  %9.2f%% %7d %7.1f%% %7.2f %9d"
            % (
                row["gap_loss_threshold_pct"],
                row["events"],
                row["event_capture_pct"],
                row["capture_lift_vs_random"],
                row["unflagged_events"],
            )
        )
    residual = severity["residual_unflagged_tail"]
    print(
        "  residual unflagged tail: q01=%+.2f%% ES1=%+.2f%% worst=%+.2f%% "
        "(%+.2f%% account at 10%% position)"
        % (
            residual["q01_gap_pct"],
            residual["expected_shortfall_below_unflagged_q01_pct"],
            residual["worst_gap_pct"],
            residual["current_10pct_position_historical_worst_account_pct"],
        )
    )
    print()
    print("PART M — CORPORATE-ACTION / EX-DIVIDEND AUDIT")
    print(
        "  actions: %d distribution dates, %d split dates; baseline gap stops "
        "on distribution ex-dates=%d"
        % (
            actions["n_dividend_dates"],
            actions["n_split_dates"],
            actions["baseline_gap_stops_on_distribution_ex_dates"],
        )
    )
    print("  %8s %9s %11s %8s" %
          ("loss >=", "raw gaps", "with cash", "removed"))
    for row in actions["threshold_rows"]:
        print(
            "  %7.2f%% %9d %11d %8d"
            % (
                row["loss_threshold_pct"],
                row["raw_price_events"],
                row["distribution_inclusive_events"],
                row["classifications_removed_by_distribution"],
            )
        )
    for row in actions["policy_rows"]:
        adjusted = row["distribution_inclusive_metrics"]
        delta = row.get("distribution_inclusive_return_delta_vs_hold_pp")
        print(
            "  %-36s credits=%2d correction=%+.4fpp total=%+.4f%%%s"
            % (
                row["policy"],
                row["trades_earning_distributions"],
                row["total_return_correction_pp"],
                adjusted["total_return_pct"],
                (
                    " delta-vs-hold=%+.4fpp" % delta
                    if delta is not None else ""
                ),
            )
        )
    print()
    print("PART N — FIRST-HOUR OPEN VS DAILY-BAR OPEN")
    sensitivity = open_validation["strategy_sensitivity"]
    print(
        "  %d sessions: median |diff| %.4fbps, p95 %.4fbps, max %.4fbps; "
        ">1bp %.2f%%, >5bp %.2f%%"
        % (
            open_validation["n_sessions"],
            open_validation["median_abs_difference_bps"],
            open_validation["p95_abs_difference_bps"],
            open_validation["maximum_abs_difference_bps"],
            open_validation["pct_abs_difference_gt_1bps"],
            open_validation["pct_abs_difference_gt_5bps"],
        )
    )
    print(
        "  daily-open replay: changed trades=%d total delta=%+.4fpp "
        "maxDD delta=%+.4fpp"
        % (
            sensitivity["changed_trades"],
            sensitivity["total_return_delta_pp"],
            sensitivity["maxdd_delta_pp"],
        )
    )
    completeness = open_validation["session_completeness"]
    print(
        "  unexpected partial sessions: %s; exclude-and-recompute total "
        "delta=%+.4fpp maxDD delta=%+.4fpp"
        % (
            ", ".join(
                completeness["unexpected_partial_session_dates"]
            ),
            completeness["defect_exclusion_total_return_delta_pp"],
            completeness["defect_exclusion_maxdd_delta_pp"],
        )
    )
    print()
    print("PART O — CONSOLIDATED CORRECTED EXECUTION LEDGER")
    for row in ledger["correction_ladder"]:
        metrics = row["metrics"]
        print(
            "  %-62s n=%4d total=%+.4f%% maxDD=%+.4f%% delta=%+.4fpp"
            % (
                row["accounting"],
                metrics["n"],
                metrics["total_return_pct"],
                metrics["max_drawdown_pct"],
                row["delta_vs_legacy_pp"],
            )
        )
    print("  corrected policy frontier:")
    for row in ledger["corrected_policy_rows"]:
        metrics = row["metrics"]
        print(
            "    %-27s total=%+.4f%% maxDD=%+.4f%% gaps=%2d exits=%3d "
            "delta=%+.4fpp cost=%s gate=%s"
            % (
                row["policy"],
                metrics["total_return_pct"],
                metrics["max_drawdown_pct"],
                row["overnight_gap_stops"],
                row["flatten_exits"],
                row["total_return_delta_vs_hold_pp"],
                (
                    "%.2fbp"
                    % row["first_order_break_even_extra_cost_bps_per_exit"]
                    if row["first_order_break_even_extra_cost_bps_per_exit"]
                    is not None else "—"
                ),
                "PASS" if row["risk_gate_pass"] else "—",
            )
        )
    print()
    print("PART P — MITIGATION CLOSE-PROXY SENSITIVITY")
    for row in close_policy["policy_rows"]:
        official = row["official_daily_close_metrics"]
        hourly_proxy = row["last_hourly_close_metrics"]
        fill_diff = row["flattened_trade_return_difference_bps"]
        print(
            "  %-27s official=%+.4f%% hourly=%+.4f%% delta=%+.4fpp "
            "median|trade diff|=%.2fbp p95=%.2fbp cost %.2f/%.2fbp gate=%s/%s"
            % (
                row["policy"],
                official["total_return_pct"],
                hourly_proxy["total_return_pct"],
                row["official_minus_hourly_total_return_pp"],
                fill_diff["median_absolute"],
                fill_diff["p95_absolute"],
                row["official_daily_close_cost_ceiling_bps"],
                row["last_hourly_close_cost_ceiling_bps"],
                (
                    "PASS"
                    if row["official_daily_close_risk_gate_pass"] else "—"
                ),
                (
                    "PASS"
                    if row["last_hourly_close_risk_gate_pass"] else "—"
                ),
            )
        )
    print()
    print("PART Q — REAL CLOSING-AUCTION OPERATIONAL GATE (SPECIFICATION ONLY)")
    for row in auction_protocol["horizon_rows"]:
        print(
            "  %-27s ceiling=%6.2fbp intended events=%d horizon=%.2fyr; "
            "0 failures => one-sided upper rate %.2f%%"
            % (
                row["policy"],
                row["conservative_break_even_cost_ceiling_bps"],
                row["fixed_minimum_intended_auction_events"],
                row["expected_years_to_60_at_observed_rate"],
                row[
                    "zero_operational_failures_one_sided_95_upper_rate_pct"
                ],
            )
        )
    print(
        "  standard Cross fill=Cross price=NOCP; fee at $60=%.4fbp "
        "(%.3f%% of vol15 ceiling); self-impact remains unidentified"
        % (
            auction_protocol["fee_scale_rows"][1]["exchange_fee_bps"],
            auction_protocol["fee_scale_rows"][1][
                "share_of_vol15_61_40bp_ceiling_pct"
            ],
        )
    )
    print("  " + auction_protocol["decision"])
    print()
    print("PART R — QQQ DISTRIBUTION CONTAMINATION OF VOL20")
    vd = vol_distribution["volatility_difference"]
    tc = vol_distribution["threshold_classification"]
    print(
        "  69 distributions; median |vol diff|=%.5fpp, p95=%.5fpp, "
        "max=%.5fpp; threshold flips=%d (%d raw-only, %d cash-only)"
        % (
            vd["median_absolute_annualized_vol_pp"],
            vd["p95_absolute_annualized_vol_pp"],
            vd["maximum_absolute_annualized_vol_pp"],
            tc["flipped_nights"],
            tc["raw_only_nights"],
            tc["distribution_only_nights"],
        )
    )
    for row in vol_distribution["policy_rows"]:
        metrics = row["metrics"]
        print(
            "  %-35s nights=%4d exits=%3d gaps=%2d total=%+.4f%% "
            "maxDD=%+.4f%% cost=%6.2fbp gate=%s"
            % (
                row["classifier"],
                row["nights_flagged"],
                row["risk_flatten_exits"],
                row["overnight_gap_stops"],
                metrics["total_return_pct"],
                metrics["max_drawdown_pct"],
                row[
                    "first_order_break_even_extra_cost_bps_per_exit"
                ],
                "PASS" if row["risk_gate_pass"] else "—",
            )
        )
    print()
    print("PART S — VOL20 DECISION-TIME / LOOKAHEAD AUDIT")
    recompute = vol_timing["truncated_recompute"]
    lookahead = vol_timing["unshifted_lookahead"]
    print(
        "  truncated recomputation: %d sessions, max diff=%.1e, %s; "
        "unshifted threshold flips=%d history/%d strategy-window"
        % (
            recompute["sessions_checked"],
            recompute["maximum_absolute_difference"],
            "PASS" if recompute["passed"] else "FAIL",
            lookahead["all_history_threshold_flips"],
            lookahead["strategy_window_threshold_flips"],
        )
    )
    for row in vol_timing["policy_rows"]:
        metrics = row["metrics"]
        print(
            "  %-31s exits=%3d gaps=%2d total=%+.4f%% maxDD=%+.4f%% "
            "cost=%6.2fbp"
            % (
                row["classifier"],
                row["risk_flatten_exits"],
                row["overnight_gap_stops"],
                metrics["total_return_pct"],
                metrics["max_drawdown_pct"],
                row[
                    "first_order_break_even_extra_cost_bps_per_exit"
                ],
            )
        )
    print()
    print("PART T — LOCAL VOL20 THRESHOLD ROBUSTNESS (NOT SELECTION)")
    for row in local_threshold["threshold_rows"]:
        metrics = row["metrics"]
        print(
            "  %5.2f%% nights=%4d exits=%3d gaps=%2d total=%+.4f%% "
            "maxDD=%+.4f%% cost=%6.2fbp gate=%s"
            % (
                row["threshold_pct"],
                row["nights_flagged"],
                row["risk_flatten_exits"],
                row["overnight_gap_stops"],
                metrics["total_return_pct"],
                metrics["max_drawdown_pct"],
                row[
                    "first_order_break_even_extra_cost_bps_per_exit"
                ],
                "PASS" if row["risk_gate_pass"] else "—",
            )
        )
    print()
    print("PART U — DIRECT MITIGATION VS OPPORTUNITY-PATH REPLACEMENT")
    for row in path_decomposition["policy_rows"]:
        fixed = row["fixed_cohort_metrics"]
        dynamic = row["dynamic_metrics"]
        print(
            "  %-27s fixed n=%4d total=%+.4f%% delta=%+.4fpp; "
            "dynamic n=%4d total=%+.4f%% delta=%+.4fpp; path=%+.4fpp "
            "entries common/new/lost=%d/%d/%d"
            % (
                row["policy"],
                fixed["n"],
                fixed["total_return_pct"],
                row["fixed_cohort_total_return_delta_vs_hold_pp"],
                dynamic["n"],
                dynamic["total_return_pct"],
                row["dynamic_total_return_delta_vs_hold_pp"],
                row["opportunity_path_increment_pp"],
                row["common_signal_entries"],
                row["dynamic_only_signal_entries"],
                row["baseline_only_signal_entries"],
            )
        )
    print()
    print("PART V — DIRECT-BENEFIT EVENT CONCENTRATION")
    for row in path_decomposition["policy_rows"]:
        concentration = row["direct_effect_concentration"]
        removal = {
            item["top_k"]: item
            for item in concentration["top_event_removal_rows"]
        }
        print(
            "  %-27s changed=%3d +/−=%d/%d gross=%+.2f/%+.2fpp; "
            "remove top1 retains %.1f%%, top5 retains %.1f%%"
            % (
                row["policy"],
                concentration["changed_trades"],
                concentration["positive_changes"],
                concentration["negative_changes"],
                concentration["gross_positive_trade_delta_pp"],
                concentration["gross_negative_trade_delta_pp"],
                removal[1]["retained_share_of_direct_delta_pct"],
                removal[5]["retained_share_of_direct_delta_pct"],
            )
        )
    print()
    print("PART W — FIXED-COHORT DIRECT-EFFECT DEPENDENCE STRESS")
    for row in path_decomposition["policy_rows"]:
        ci = row[
            "fixed_cohort_paired_daily_log_block_bootstrap_relative_wealth95_pct"
        ]
        print(
            "  %-27s observed relative wealth=%+.4f%% CI5=[%+.3f,%+.3f] "
            "CI20=[%+.3f,%+.3f] CI60=[%+.3f,%+.3f] cost=%6.2fbp"
            % (
                row["policy"],
                row[
                    "fixed_cohort_observed_relative_wealth_effect_pct"
                ],
                ci["5"][0],
                ci["5"][1],
                ci["20"][0],
                ci["20"][1],
                ci["60"][0],
                ci["60"][1],
                row[
                    "fixed_cohort_first_order_break_even_extra_cost_bps_per_exit"
                ],
            )
        )
    print()
    print("PART X — FIXED-COHORT INTERVENTION OUTCOME ANATOMY")
    for row in path_decomposition["policy_rows"]:
        concentration = row["direct_effect_concentration"]
        favorable = concentration["favorable_intervention_rate"]
        print(
            "  %-27s avoided gap stops=%2d; favorable=%d/%d %.1f%% "
            "Wilson95 %.1f-%.1f%% p(vs50)=%.4f median delta=%+.2fbp"
            % (
                row["policy"],
                concentration["avoided_baseline_overnight_gap_stops"],
                favorable["favorable"],
                favorable["favorable"] + favorable["unfavorable"],
                favorable["rate_pct"],
                favorable["wilson95_pct"][0],
                favorable["wilson95_pct"][1],
                favorable["one_sided_exact_p_value_vs_50pct"],
                concentration["median_changed_trade_delta_bps"],
            )
        )
    print()
    print("PART Y — CURRENT CLOSING-AUCTION RUNTIME READINESS (READ-ONLY)")
    clock = auction_runtime["nominal_clock"]
    print(
        "  nominal final cycle=%s; %d min to cancel lock / %d min to "
        "acceptance cutoff"
        % (
            clock["final_regular_session_cycle_et"],
            clock["minutes_from_cycle_to_cancel_lock"],
            clock["minutes_from_cycle_to_acceptance_cutoff"],
        )
    )
    for row in auction_runtime["readiness_matrix"]:
        print(
            "  %-49s %-10s %s"
            % (
                row["requirement"],
                row["current_status"],
                row["evidence"],
            )
        )
    early = auction_runtime["early_close_exposure"]
    print(
        "  early close=%s; current scheduler can still fire %s"
        % (
            early["official_close_et"],
            ", ".join(early["scheduler_post_close_cycles_et"]),
        )
    )
    print("  " + auction_runtime["decision"])
    print()
    print("PART Z — 2026 CLOSED/SHORT SESSION SCHEDULER EXPOSURE")
    schedule_math = calendar_cycles["schedule_math"]
    repeated = calendar_cycles["repeated_state_transition_risk"]
    print(
        "  fully closed weekdays=%d x %d cycles = %d admitted jobs"
        % (
            len(calendar_cycles["fully_closed_weekdays_2026"]),
            schedule_math["configured_cycles_per_weekday"],
            schedule_math["admitted_cycles_on_fully_closed_weekdays"],
        )
    )
    print(
        "  early closes=%d x %d post-close cycles = %d admitted jobs; "
        "2026 total off-exchange-calendar cycles=%d"
        % (
            len(calendar_cycles["early_close_weekdays_2026"]),
            schedule_math["post_close_cycles_per_early_close_weekday"],
            schedule_math["admitted_post_close_early_close_cycles"],
            schedule_math["total_off_exchange_calendar_cycles"],
        )
    )
    print(
        "  staleness limit=%dh; holiday same-bar count increments up to %d; "
        "early-close post-close increments=%d (generic duplicate minimum=%d; "
        "pinned replay=%d)"
        % (
            calendar_cycles["stale_data_interaction"][
                "configured_max_bar_staleness_hours"
            ],
            repeated["full_holiday_max_same_bar_position_count_increments"],
            repeated["early_close_post_close_position_count_increments"],
            repeated[
                "early_close_generic_minimum_duplicate_final_bar_increments"
            ],
            calendar_materiality["materiality"][
                "early_close_post_close_cycles_reusing_1232_bar"
            ] // len(calendar_materiality["event_rows"][-5:]),
        )
    )
    print("  " + calendar_cycles["decision"])
    print()
    print("PART AA — PINNED CALENDAR-MISFIRE MATERIALITY REPLAY")
    window = calendar_materiality["pinned_window"]
    materiality = calendar_materiality["materiality"]
    print(
        "  %d full holidays + %d early closes; admitted off-calendar "
        "cycles=%d"
        % (
            window["fully_closed_weekdays"],
            window["early_close_weekdays"],
            window["admitted_off_calendar_cycles"],
        )
    )
    print(
        "  nonzero reused signal: %d full holidays / %d early closes; "
        "clean baseline open: %d / %d"
        % (
            materiality["full_holidays_with_nonzero_reused_signal"],
            materiality["early_closes_with_nonzero_reused_signal"],
            materiality["full_holidays_clean_baseline_position_open"],
            materiality["early_closes_clean_baseline_position_open"],
        )
    )
    print(
        "  clean-baseline-open cycle exposure=%d; clean-flat+signal "
        "dates=%d (frozen-state cycle upper bound=%d)"
        % (
            materiality["clean_baseline_open_cycle_exposure"],
            materiality["dates_clean_flat_with_nonzero_signal"],
            materiality[
                "frozen_clean_flat_nonzero_cycle_upper_bound"
            ],
        )
    )
    print(
        "  early sessions with 3 bars=%d/5; post-close jobs reusing the "
        "12:32-processable final bar=%d/15"
        % (
            materiality[
                "early_close_sessions_with_three_hourly_bars"
            ],
            materiality[
                "early_close_post_close_cycles_reusing_1232_bar"
            ],
        )
    )
    print("  " + calendar_materiality["decision"])
    print()
    print("PART AB — SANITIZED OBSERVED HOLIDAY RUNTIME EVIDENCE")
    for row in holiday_evidence["holiday_rows"]:
        print(
            "  %s signal rows=%d / slots=%d multiplicity=%s signal=%s "
            "paper-connect-failures=%d trade endpoints=%d"
            % (
                row["exchange_date"],
                row["observed_signal_rows"],
                row["unique_scheduled_minute_slots"],
                row["rows_per_observed_slot"],
                row["observed_signals"],
                row["paper_7497_connection_failures"],
                row["trade_entry_or_exit_endpoints"],
            )
        )
    duplicate = holiday_evidence["duplicate_writer_diagnostic"]
    print(
        "  archive-wide signal rows=%d / unique minute slots=%d; "
        "double-written slots=%d (%d identical payload, %d divergent)"
        % (
            duplicate["signal_rows"],
            duplicate["unique_signal_minute_slots"],
            duplicate["double_written_slots"],
            duplicate[
                "double_written_slots_with_identical_payload"
            ],
            duplicate[
                "double_written_slots_with_divergent_payload"
            ],
        )
    )
    print("  " + holiday_evidence["decision"])
    print()
    print("PART AC — HISTORICAL DUPLICATE-WRITER ORDER-PATH FORENSICS")
    paired = duplicate_forensics["paired_signal_writes"]
    entry_path = duplicate_forensics["entry_path"]
    print(
        "  paired slots=%d across %d dates; bar mismatch=%d; "
        "signal disagreement=%d; long-eligibility disagreement=%d"
        % (
            paired["paired_minute_slots"],
            paired["paired_exchange_dates"],
            paired["divergent_bar_slots"],
            paired["different_final_signal"],
            paired[
                "long_eligibility_disagreements_with_shorts_disabled"
            ],
        )
    )
    print(
        "  entry events=%d / unique slots=%d; double-success slots=%d; "
        "later local state retained=%d/%d"
        % (
            entry_path["entry_event_rows"],
            entry_path["unique_entry_minute_slots"],
            entry_path["double_entry_event_slots"],
            entry_path["trade_rows_matching_later_state"],
            entry_path["double_entry_event_slots"],
        )
    )
    print(
        "  extra bracket paths=%d -> additional ib.placeOrder calls=%d "
        "(acceptance/fill unproven)"
        % (
            entry_path["additional_bracket_submission_paths"],
            entry_path["additional_ib_placeOrder_calls"],
        )
    )
    print("  " + duplicate_forensics["decision"])
    print()
    print("PART AD — LIVE BAR-COMPLETION TIMEZONE AUDIT")
    natural = bar_timezone["historical_natural_experiment"]
    fixed = bar_timezone["fixed_clock_case"]
    for row in fixed["cases"]:
        print(
            "  %-24s %-16s age=%7.1fmin selected=%s correct=%s"
            % (
                row["host_environment"],
                row["api_tail"],
                row["apparent_age_minutes"],
                row["selected_bar_utc_naive"],
                row["correct_completed_bar"],
            )
        )
    print(
        "  DST natural experiment: exact_structural_match=%s; "
        "identical=%d divergent=%d"
        % (
            natural["exact_structural_match"],
            natural["identical_bar_slots"],
            natural["divergent_bar_slots"],
        )
    )
    print("  " + bar_timezone["decision"])
    print()
    print("PART AE — ARCHIVED INCOMPLETE-BAR MATERIALITY")
    incomplete_signals = incomplete_materiality["signal_rows"]
    entry_attribution = incomplete_materiality[
        "conservative_entry_attribution"
    ]
    trade_accounting = incomplete_materiality[
        "local_trade_accounting"
    ]
    print(
        "  incomplete signal rows=%d/%d (%.1f%%), about %.3fmin old; "
        "single-write incomplete=%d/%d"
        % (
            incomplete_signals["incomplete"],
            incomplete_signals["total"],
            incomplete_signals["incomplete_pct"],
            incomplete_signals[
                "incomplete_true_age_minutes"
            ]["median"],
            incomplete_signals["incomplete_single_write_rows"],
            incomplete_signals["single_write_rows"],
        )
    )
    print(
        "  strict incomplete attribution: entry slots=%d/%d (%.1f%%), "
        "entry events=%d/%d (%.1f%%), local trade rows=%d"
        % (
            entry_attribution["strict_incomplete_entry_slots"],
            entry_attribution["unique_entry_slots"],
            entry_attribution[
                "strict_min_share_of_unique_entry_slots_pct"
            ],
            entry_attribution["strict_incomplete_entry_events"],
            entry_attribution["entry_event_rows"],
            entry_attribution[
                "strict_min_share_of_entry_event_rows_pct"
            ],
            entry_attribution["strict_slots_with_one_local_trade_row"],
        )
    )
    print(
        "  archive-confirmed partition: all=%d (%+.4f%%), strict "
        "incomplete=%d (%+.4f%%), remainder=%d (%+.4f%%)"
        % (
            trade_accounting["all_archive_confirmed_trade_rows"],
            trade_accounting[
                "all_archive_confirmed_compounded_return_pct"
            ],
            trade_accounting[
                "strict_incomplete_archive_confirmed_rows"
            ],
            trade_accounting[
                "strict_incomplete_archive_confirmed_compounded_return_pct"
            ],
            trade_accounting["remaining_confirmed_or_ambiguous_rows"],
            trade_accounting[
                "remaining_confirmed_or_ambiguous_compounded_return_pct"
            ],
        )
    )
    print("  " + incomplete_materiality["decision"])
    print()
    print("PART AF — TRADER SINGLETON AND LAUNCH-SAFETY AUDIT")
    for row in singleton_audit["launch_path_matrix"]:
        print(
            "  %-29s preflight=%-5s unit=%-5s market_guard=%-5s "
            "atomic_lock=%-5s"
            % (
                row["path"],
                str(row["full_ten_check_preflight"]),
                str(row["named_service_unit_scope"]),
                str(row["scheduled_market_hours_wrapper"]),
                str(row["cross_process_atomic_lock"]),
            )
        )
    inventory = singleton_audit["control_inventory"]
    print(
        "  controls: pgrep_atomic=%s max_instances_scope=%s "
        "client_id=%d sqlite_check_to_act_atomic=%s"
        % (
            inventory["preflight_pgrep"]["atomic"],
            inventory["apscheduler_max_instances"]["scope"],
            inventory["fixed_ibkr_client_id"]["value"],
            inventory["sqlite"]["business_check_to_act_atomic"],
        )
    )
    interleaving = singleton_audit["constructive_interleavings"]
    print(
        "  duplicate bracket path reachable=%s; residual=%s"
        % (
            interleaving["reachable_duplicate_bracket_path"],
            interleaving["necessary_residual_condition"],
        )
    )
    print("  " + singleton_audit["decision"])
    print()
    print("PART AG — ENTRY ACKNOWLEDGEMENT AND BASIS AUDIT")
    entry_path = entry_ack["current_entry_path"]
    print(
        "  submission calls=%d retained Trade objects=%d ack checks=%d; "
        "actual fill observed=%s"
        % (
            entry_path["application_place_order_calls"],
            entry_path["place_order_return_values_retained"],
            entry_path["acknowledgement_checks"],
            entry_path["actual_entry_fill_observed"],
        )
    )
    archive_basis = entry_ack["archive_entry_basis_sensitivity"]
    print(
        "  project exit-confirmed archive=%d rows, recorded=%+.6f%%; "
        "uniform adverse entry-basis break-even=%.6fbp"
        % (
            archive_basis["rows"],
            archive_basis["recorded_compounded_return_pct"],
            archive_basis["adverse_entry_slippage_break_even_bps"],
        )
    )
    for row in archive_basis["uniform_entry_slippage_sensitivity"]:
        print(
            "    entry basis %+6.2fbp -> compounded %+.6f%%"
            % (
                row["uniform_entry_slippage_bps"],
                row["compounded_return_pct"],
            )
        )
    print(
        "  prior 51-row study input present=%s"
        % entry_ack["prior_study_reproducibility"][
            "input_present_in_current_checkout"
        ]
    )
    print("  " + entry_ack["decision"])
    print()
    print("PART AH — UNFILLED-PARENT / PHANTOM-TRADE AUDIT")
    flow = phantom["current_control_flow"]
    archive_join = phantom["archive_inference_join"]
    materiality = phantom["accounting_materiality"]
    print(
        "  active-order check=%s parent-ack check=%s unknown inference state=%s; "
        "terminal TP/SL returns=%d"
        % (
            flow["active_or_working_parent_checked"],
            flow["parent_reject_status_checked"],
            bool(flow["inference_unknown_or_unverified_outcomes"]),
            flow["inference_terminal_return_count"],
        )
    )
    print(
        "  archive warnings=%d -> unique inferred rows=%d "
        "(duplicate warnings=%d); same-cycle reentries=%d"
        % (
            archive_join["inference_warning_events"],
            archive_join["unique_local_trade_rows"],
            archive_join["duplicate_warning_events"],
            archive_join["explicit_same_cycle_reentries_after_inference"],
        )
    )
    print(
        "  inferred slice=%+.6f%%; all archive=%+.6f%%; without those "
        "factors=%+.6f%% (endpoint difference=%+.6fpp)"
        % (
            materiality["inferred_rows_compounded_return_pct"],
            materiality["all_archive_compounded_return_pct"],
            materiality[
                "all_archive_compounded_return_without_inferred_rows_pct"
            ],
            materiality["endpoint_return_difference_pp"],
        )
    )
    print("  " + phantom["decision"])
    print()
    print("PART AI — BRACKET-FILL IDENTITY AND RETENTION AUDIT")
    timing = fill_identity["archive_timing"]
    partial = fill_identity["synthetic_partial_fill_price_case"]
    print(
        "  durable identity fields present=%d/%d; returned fields=%s"
        % (
            sum(fill_identity[
                "source_identity_field_presence"
            ].values()),
            len(fill_identity["source_identity_field_presence"]),
            ",".join(fill_identity["returned_fields"]),
        )
    )
    print(
        "  Gateway retrieval=%s; inferred rows crossing UTC date=%d/%d"
        % (
            fill_identity["retention_contract"][
                "ib_gateway_default_and_limit"
            ],
            timing["entry_on_prior_utc_date"],
            timing["inferred_unique_rows"],
        )
    )
    print(
        "  synthetic 60@100 + 40@101: VWAP=%.2f, tier1 error=%+.3fbp, "
        "tier2/3 error=%+.3fbp"
        % (
            partial["correct_vwap"],
            partial["tier1_error_bps"],
            partial["tier2_or_3_error_bps"],
        )
    )
    print("  " + fill_identity["decision"])
    print()
    print("PART AJ — CONCURRENT CLOSE IDEMPOTENCY AUDIT")
    interleaving = close_race[
        "deterministic_two_reader_interleaving"
    ]
    close_tx = close_race["transaction_contract"]
    duplicate = close_race["duplicate_factor_sensitivity"]
    print(
        "  SELECT transaction A/B=%s/%s; unique lifecycle=%s; "
        "recorded rows=%d writers=%s"
        % (
            interleaving[
                "connection_a_in_transaction_after_select"
            ],
            interleaving[
                "connection_b_in_transaction_after_select"
            ],
            close_tx["trades_unique_lifecycle_constraint"],
            interleaving["recorded_trade_rows"],
            ",".join(interleaving["recorded_writers"]),
        )
    )
    print(
        "  observed May6 warnings/trades=2/1; hypothetical duplicate factor "
        "moves endpoint %+.6f%% -> %+.6f%% (%+.6fpp)"
        % (
            duplicate["original_all_archive_compounded_return_pct"],
            duplicate["with_one_duplicate_may6_factor_pct"],
            duplicate["endpoint_increase_pp"],
        )
    )
    print("  " + close_race["decision"])
    print()
    print("PART AK — CROSS-GENERATION CLOSE/RE-ENTRY AUDIT")
    cross = cross_generation[
        "deterministic_cross_generation_interleaving"
    ]
    archive = cross_generation["archive_observability"]
    print(
        "  expected/selected bracket=%s/%s; deleted-new-row=%d; "
        "remaining positions=%d; reachable=%s"
        % (
            cross["stale_close_expected_bracket_id"],
            cross["stale_close_selected_bracket_id"],
            cross["stale_close_deleted_new_position_rows"],
            cross["remaining_position_rows"],
            cross["reachability_proved"],
        )
    )
    print(
        "  crossed record return=%+.2f%% vs selected-generation implied=%+.2f%% "
        "(field-mix discrepancy=%+.2fpp)"
        % (
            cross["crossed_trade_record"]["recorded_return_pct"],
            cross["crossed_trade_record"][
                "return_implied_by_selected_generation_pct"
            ],
            cross["crossed_trade_record"]["return_discrepancy_pp"],
        )
    )
    print(
        "  archive double-entry success events with parent identity=%d/%d; "
        "trade export retains bracket ID=%s"
        % (
            archive["double_success_events_with_parent_order_identity"],
            archive["double_success_events"],
            archive["trades_export_retains_bracket_order_id"],
        )
    )
    print("  " + cross_generation["decision"])
    print()
    print("PART AL — QUOTE-ANCHORED BRACKET GEOMETRY AUDIT")
    analytic = geometry["no_rounding_fill_relative_bounds"]
    rounded = geometry["archived_quote_distribution_geometry"]
    sizing_join = geometry["strict_archive_sizing_join"]
    maximum = sizing_join["maximum_parent_limit_case"]
    print(
        "  quote geometry target/stop/R:R=%+.3f%%/%+.3f%%/%.2f; "
        "at buy-limit cap=%+.6f%%/%+.6f%%/%.2f"
        % (
            analytic["at_quote"]["target_pct"],
            analytic["at_quote"]["stop_pct"],
            analytic["at_quote"]["reward_risk"],
            analytic["long_at_parent_limit"]["target_pct"],
            analytic["long_at_parent_limit"]["stop_pct"],
            analytic["long_at_parent_limit"]["reward_risk"],
        )
    )
    print(
        "  archived quote scale n=%d; rounded fill-cap medians "
        "target=%+.6f%% stop=%+.6f%% R:R=%.3f"
        % (
            rounded["application_success_events"],
            rounded["parent_limit_fill_relative_target_pct"]["median"],
            rounded["parent_limit_fill_relative_stop_pct"]["median"],
            rounded["parent_limit_fill_reward_risk"]["median"],
        )
    )
    print(
        "  strict sizing joins=%d/%d; limit-vs-bar range=%+.3f to %+.3fbp; "
        "max account allocation=%.6f%% to %.6f%%"
        % (
            sizing_join["matched_entry_events"],
            sizing_join["all_entry_events"],
            sizing_join["parent_limit_to_signal_bar_bps"]["min"],
            sizing_join["parent_limit_to_signal_bar_bps"]["max"],
            maximum["implied_account_allocation_pct_interval"][0],
            maximum["implied_account_allocation_pct_interval"][1],
        )
    )
    print("  " + geometry["decision"])
    print()
    print("PART AM — PARTIAL-FILL FORCE-CLOSE QUANTITY AUDIT")
    qty_contract = partial_qty["current_quantity_contract"]
    partial = partial_qty["deterministic_partial_fill_overshoot"]
    cancel_race = partial_qty["cancellation_acknowledgement_race"]
    archive_qty = partial_qty["archive_observability"]
    print(
        "  force-close paths=%d; all use local requested qty=%s; "
        "broker/local equality check=%s"
        % (
            qty_contract["force_close_call_count"],
            qty_contract["force_close_calls_all_use_local_position_qty"],
            qty_contract["broker_vs_local_quantity_equality_check"],
        )
    )
    fifty = partial["fifty_share_example"]
    print(
        "  50/100 parent fill + SELL %d -> final signed qty=%d (%s); "
        "parent remainder cancelled=%s"
        % (
            fifty["market_sell"],
            fifty["final_signed_position"],
            fifty["outcome"],
            partial_qty["attached_order_partial_fill_contract"][
                "current_parent_remainder_cancelled_by_force_close"
            ],
        )
    )
    print(
        "  cancel-confirmation fields=%d; hypothetical archive half-fill "
        "opposite qty min/median/max=%d/%.1f/%d"
        % (
            cancel_race["confirmation_fields_present"],
            archive_qty["hypothetical_half_fill_opposite_qty_range"]["min"],
            archive_qty["hypothetical_half_fill_opposite_qty_range"]["median"],
            archive_qty["hypothetical_half_fill_opposite_qty_range"]["max"],
        )
    )
    print("  " + partial_qty["decision"])
    print()
    print("PART AN — FORCE-CLOSE COMPLETION AND VWAP AUDIT")
    completion_contract = close_completion["current_completion_contract"]
    first_partial = close_completion[
        "deterministic_first_partial_execution"
    ]
    price_case = close_completion["multi_execution_price_accounting"]
    timeout_archive = close_completion["archive_observability"]
    print(
        "  success predicate=%s; completion fields=%d; returned fields=%s"
        % (
            completion_contract["success_predicate"],
            completion_contract["completion_fields_present"],
            ",".join(completion_contract["returned_fields"]),
        )
    )
    print(
        "  SELL %d first execution=%d -> residual long=%d; local rows=%d; "
        "hidden=%s"
        % (
            first_partial["requested_close_qty"],
            first_partial["observed_execution_qty"],
            first_partial["final_signed_broker_qty_if_no_later_fill"],
            first_partial["local_position_rows_after_caller"],
            first_partial["residual_exposure_hidden_by_local_flat"],
        )
    )
    print(
        "  60@100 + 40@101 VWAP=%.2f; first-only/last-component errors="
        "%+.3f/%+.3fbp; archive time-exit timeouts=%d/%d"
        % (
            price_case["correct_vwap"],
            price_case["if_first_poll_sees_only_first_execution"][
                "error_vs_vwap_bps"
            ],
            price_case["if_first_poll_sees_both_executions"][
                "error_vs_vwap_bps"
            ],
            timeout_archive["explicit_time_exit_fill_unavailable_events"],
            timeout_archive["time_exit_trade_rows"],
        )
    )
    print("  " + close_completion["decision"])
    print()
    print("PART AO — UNRESOLVED-CLOSE BACK-TO-BACK RE-ENTRY AUDIT")
    reentry_contract = reentry_race["current_reentry_contract"]
    collision = reentry_race[
        "deterministic_nonterminal_close_collision"
    ]
    reentry_archive = reentry_race["archive_observability"]
    collision_full = collision["full_late_close_example"]
    print(
        "  broker-position guard=%s; working-order fields=%d; "
        "prior close/children terminal=%s/%s"
        % (
            reentry_contract["entry_broker_position_guard"],
            reentry_contract["entry_working_order_fields_present"],
            reentry_contract["old_close_order_terminal_required"],
            reentry_contract["old_children_terminal_required"],
        )
    )
    print(
        "  old child flattens, new BUY %d, late old SELL %d -> broker=%d "
        "vs local=%d"
        % (
            collision_full["new_parent_buy_fill"],
            collision_full["late_old_market_close_sell_fill"],
            collision_full["final_signed_broker_qty"],
            collision_full["local_recorded_new_qty"],
        )
    )
    print(
        "  archive back-to-back entries=%d; explicit timeout->reentry pairs=%d; "
        "deltas=%s"
        % (
            reentry_archive["all_back_to_back_application_entries"],
            reentry_archive["fill_unavailable_then_back_to_back_entries"],
            ",".join(
                "%.3fs" % row["seconds_between"]
                for row in reentry_archive["timeout_to_reentry_rows"]
            ),
        )
    )
    print("  " + reentry_race["decision"])
    print()
    print("PART AP — BROKER ACCOUNT/MODEL SCOPE AUDIT")
    identity_contract = account_scope["current_identity_contract"]
    summary_order = account_scope[
        "deterministic_account_summary_ordering"
    ]
    position_order = account_scope["deterministic_position_ordering"]
    sizing_case = summary_order["sizing_case"]
    print(
        "  account/model scope fields=%d; summary=%s; position=%s; "
        "explicit order destination=%s"
        % (
            identity_contract["account_scope_fields_present"],
            identity_contract["account_summary_selection"],
            identity_contract["position_selection"],
            identity_contract["explicit_order_destination"],
        )
    )
    print(
        "  synthetic 100k/1m callback order -> qty=%d/%d at $%.0f; "
        "conditional max=%.1fx / %.1f%% of account_A"
        % (
            sizing_case["b_then_a_selected_qty"],
            sizing_case["a_then_b_selected_qty"],
            sizing_case["signal_price"],
            sizing_case["maximum_qty_multiple_vs_account_a"],
            sizing_case["maximum_notional_pct_of_account_a"],
        )
    )
    print(
        "  same two positions report qty=%+d or %+d by row order; "
        "direction flip=%s"
        % (
            position_order["a_first_result"]["qty"],
            position_order["b_first_result"]["qty"],
            position_order["direction_can_flip"],
        )
    )
    print("  " + account_scope["decision"])
    print()
    print("PART AQ — DUPLICATE-WRITER HOLD-COUNTER MATERIALITY")
    deterministic_counter = hold_counter[
        "deterministic_two_writer_increment"
    ]
    archived_counter = hold_counter[
        "archived_time_exit_intervals"
    ]
    print(
        "  one logical slot, writers A/B -> counter=%d/%d; inflation=%.1fx"
        % (
            deterministic_counter["after_writer_a"],
            deterministic_counter["after_writer_b"],
            deterministic_counter["inflation_factor"],
        )
    )
    print(
        "  archive time exits=%d; <10 distinct slots=%d; strict exact "
        "double=%d; exact five-slot holds=%d"
        % (
            archived_counter["time_exit_trades"],
            archived_counter["compressed_below_ten_distinct_slots"],
            archived_counter["strict_exact_double_intervals"],
            archived_counter["exact_five_slot_half_holds"],
        )
    )
    print(
        "  distinct-slot counts=%s; strict wall-hours min/median/max="
        "%.2f/%.2f/%.2f; causal PnL identified=%s"
        % (
            ",".join(
                str(value)
                for value in archived_counter["distinct_slot_counts"]
            ),
            archived_counter["strict_wall_clock_hours"]["min"],
            archived_counter["strict_wall_clock_hours"]["median"],
            archived_counter["strict_wall_clock_hours"]["max"],
            archived_counter["causal_pnl_effect_identified"],
        )
    )
    print("  " + hold_counter["decision"])
    print()
    print("PART AR — BROKER QUOTE-FIELD PRECEDENCE AND STALENESS")
    selection = quote_precedence["current_selection_contract"]
    deterministic_quote = quote_precedence[
        "deterministic_precedence_counterexamples"
    ]
    quote_panel = quote_precedence["pinned_five_min_materiality"]
    lag_15 = quote_panel["lag_windows"]["15"]
    lag_20 = quote_panel["lag_windows"]["20"]
    prior_close = quote_panel["prior_close_hourly_cycle_proxy"]
    archive_quote = quote_precedence["archive_observability"]
    print(
        "  precedence=%s; timestamp/type/size checks=%s/%s/%s; "
        "delayed accepted=%s"
        % (
            ">".join(selection["live_field_precedence"]),
            selection["last_timestamp_checked"],
            selection["market_data_type_callback_checked"],
            selection["bid_ask_sizes_checked"],
            selection["delayed_data_accepted_for_order_placement"],
        )
    )
    print(
        "  close=100 with 109.90/110.10 spread -> selected %.2f, "
        "buy limit %.2fbp below ask; high-last stop crossed=%s"
        % (
            deterministic_quote["close_case_selected_price"],
            deterministic_quote[
                "close_case_long_parent_below_ask_bps"
            ],
            deterministic_quote[
                "high_last_case_long_stop_already_crossed"
            ],
        )
    )
    print(
        "  pinned 15m/20m |move|>50bp: %d/%d (%.2f%%), "
        "%d/%d (%.2f%%); p90 |move| %.2f/%.2fbp"
        % (
            lag_15["moves_abs_over_50bps"],
            lag_15["pairs"],
            lag_15["pct_abs_over_50bps"],
            lag_20["moves_abs_over_50bps"],
            lag_20["pairs"],
            lag_20["pct_abs_over_50bps"],
            lag_15["p90_abs_bps"],
            lag_20["p90_abs_bps"],
        )
    )
    print(
        "  prior-close hourly proxy >50bp: %d/%d (%.2f%%); "
        "archive overlap=%d, quote source identified=%s"
        % (
            prior_close["moves_abs_over_50bps"],
            prior_close["pairs"],
            prior_close["pct_abs_over_50bps"],
            archive_quote["matched_entry_events"],
            archive_quote["exact_quote_age_identified"],
        )
    )
    print("  " + quote_precedence["decision"])
    print()
    print("PART AS — ENTRY SNAPSHOT LATENCY")
    latency_contract = snapshot_latency["current_latency_contract"]
    archived_latency = snapshot_latency["archived_timing"]
    schedule_latency = archived_latency[
        "schedule_to_application_entry_seconds"
    ]
    print(
        "  snapshots/entry min/max=%d/%d; explicit sleeps live/delayed=%ds/%ds; "
        "deadline=%s"
        % (
            latency_contract["minimum_snapshot_requests_per_entry"],
            latency_contract[
                "maximum_snapshot_requests_per_entry_if_both_live_attempts_fall_back"
            ],
            latency_contract["explicit_sleep_seconds_live_success_path"],
            latency_contract[
                "explicit_sleep_seconds_full_delayed_fallback_path"
            ],
            latency_contract["entry_deadline_or_max_latency_guard"],
        )
    )
    print(
        "  archive application entries=%d; schedule->event min/median/p90/max="
        "%.3f/%.3f/%.3f/%.3fs; >=30s=%d"
        % (
            archived_latency["entry_events"],
            schedule_latency["min"],
            schedule_latency["median"],
            schedule_latency["p90"],
            schedule_latency["max"],
            schedule_latency["at_least_30_seconds"],
        )
    )
    print(
        "  strict signal joins=%d; spillovers=%d; duplicate attribution max="
        "%.3fs; source byte-match=%s"
        % (
            archived_latency["strict_same_minute_signal_joins"],
            archived_latency["spillover_entry_events"],
            archived_latency[
                "maximum_duplicate_signal_attribution_span_seconds"
            ],
            snapshot_latency["archived_source_identity"][
                "current_broker_and_trader_byte_match_archive"
            ],
        )
    )
    print("  " + snapshot_latency["decision"])
    print()
    print("PART AT — MARKET-DATA PROVENANCE LABEL INTEGRITY")
    provenance = provenance_label["provenance_contract"]
    archive_provenance = provenance_label["archive_observability"]
    downstream = provenance_label["downstream_materiality"]
    print(
        "  broker return=%s; resolver distinguishes live/delayed=%s; "
        "false-live label reachable=%s"
        % (
            provenance["broker_return_shape"],
            provenance["resolver_can_distinguish_live_from_delayed"],
            provenance_label["deterministic_indistinguishability"][
                "false_live_label_reachable"
            ],
        )
    )
    print(
        "  mark_time is source time=%s; dashboard green=%s; "
        "software stop/TP consume mark=%s/%s"
        % (
            provenance["mark_time_is_source_quote_time"],
            downstream["dashboard_live_badge_is_green"],
            downstream["software_stop_uses_resolved_mark"],
            downstream["software_take_profit_uses_resolved_mark"],
        )
    )
    print(
        "  archive singleton rows=%d sources=%s; type/field/source-time=%d/%d/%d; "
        "incident rate identified=%s"
        % (
            archive_provenance["exported_rows"],
            json.dumps(
                archive_provenance["mark_source_counts"],
                sort_keys=True,
            ),
            archive_provenance["market_data_type_present"],
            archive_provenance["selected_quote_field_present"],
            archive_provenance["source_quote_timestamp_present"],
            archive_provenance["delayed_incident_rate_identified"],
        )
    )
    print("  " + provenance_label["decision"])
    print()
    print("PART AU — SOFTWARE RISK-TRIGGER OUTCOME AUDIT")
    trigger_archive = software_trigger["archived_trigger_evidence"]
    trigger_contract = software_trigger["current_trigger_contract"]
    margins = trigger_archive["unique_breach_margin_bps"]
    print(
        "  source/age gate=%s; trigger events=%d; unique joins=%d; "
        "duplicate post-close triggers=%d"
        % (
            trigger_contract["source_allowlist_or_age_gate"],
            trigger_archive["trigger_events"],
            trigger_archive["unique_primary_close_joins"],
            trigger_archive["duplicate_post_close_triggers"],
        )
    )
    print(
        "  source labels=%s; unique breach margin min/median/max="
        "%.2f/%.2f/%.2fbp"
        % (
            json.dumps(
                trigger_archive["source_label_counts"],
                sort_keys=True,
            ),
            margins["min"],
            margins["median"],
            margins["max"],
        )
    )
    print(
        "  retained exits beyond stop=%d/%d; false trigger observed=%s"
        % (
            trigger_archive["unique_recorded_exits_beyond_stop"],
            trigger_archive["unique_primary_close_joins"],
            trigger_archive["false_trigger_observed_in_retained_exit_prices"],
        )
    )
    print("  " + software_trigger["decision"])
    print()
    print("PART AV — SOFTWARE RISK FALLBACK FRESHNESS")
    fallback_contract = fallback_freshness[
        "current_fallback_contract"
    ]
    fallback_archive = fallback_freshness[
        "archived_prior_close_counterfactual"
    ]
    false_stop = fallback_archive["false_stop"]
    false_target = fallback_archive["false_take_profit"]
    print(
        "  daily row age checked=%s; current session required=%s; "
        "explicit broker+retry waits=%ds; deadline=%s"
        % (
            fallback_contract["last_row_index_or_age_checked"],
            fallback_contract["current_session_row_required"],
            fallback_contract[
                "full_path_explicit_sleep_and_backoff_seconds"
            ],
            not fallback_contract[
                "request_duration_additional_and_unbounded_by_cycle_deadline"
            ],
        )
    )
    print(
        "  archived evaluable trade-cycle slots=%d; prior-close false-stop "
        "strict/possible=%d/%d (%.2f%%/%.2f%%)"
        % (
            fallback_archive["unique_trade_cycle_slots"],
            false_stop["strict_slots"],
            false_stop["possible_slots"],
            false_stop["strict_pct_of_evaluable_slots"],
            false_stop["possible_pct_of_evaluable_slots"],
        )
    )
    print(
        "  prior-close false-TP=%d (%.2f%%); actual fallback incidents=%d"
        % (
            false_target["strict_slots"],
            false_target["strict_pct_of_evaluable_slots"],
            fallback_archive[
                "actual_yfinance_fallback_incidents_observed"
            ],
        )
    )
    print("  " + fallback_freshness["decision"])
    print()
    print("PART AW — DUPLICATE BAR-FALLBACK TRIGGER DIVERGENCE")
    divergence = bar_divergence["archived_divergence"]
    span = divergence["writer_update_span_seconds"]
    print(
        "  in-position slots=%d; multi-writer=%d; divergent=%d (%.2f%% "
        "of multi-writer)"
        % (
            divergence["unique_trade_cycle_slots"],
            divergence["multi_writer_slots"],
            divergence["divergent_slots"],
            divergence["divergent_pct_of_multi_writer_slots"],
        )
    )
    print(
        "  stop/TP forks=%d/%d across %d trades; cross-session=%d; "
        "in-progress+older in every fork=%s"
        % (
            divergence["stop_divergent_slots"],
            divergence["take_profit_divergent_slots"],
            divergence["divergent_trades"],
            divergence["cross_session_date_slots"],
            divergence["all_include_in_progress_and_older_bar"],
        )
    )
    print(
        "  writer span min/median/max=%.6f/%.6f/%.6fs; observed "
        "last_close incidents=%d"
        % (
            span["min"],
            span["median"],
            span["max"],
            divergence["observed_last_close_trigger_incidents"],
        )
    )
    print("  " + bar_divergence["decision"])
    print()
    print("PART AX — BROKER CONNECTION EXCEPTION FALLBACK")
    connection_contract = connection_fallback[
        "current_exception_contract"
    ]
    connection_archive = connection_fallback[
        "archived_connection_failures"
    ]
    connection_offset = connection_archive["seconds_after_schedule"]
    print(
        "  attempts=%d explicit waits=%ds; resolver catches RuntimeError only=%s; "
        "ConnectionRefused reaches fallback=%s"
        % (
            connection_contract["ensure_connected_attempts"],
            connection_contract[
                "ensure_connected_explicit_retry_wait_seconds"
            ],
            connection_contract["resolver_catches_runtime_error_only"],
            connection_contract[
                "connection_refused_reaches_yfinance_fallback"
            ],
        )
    )
    print(
        "  archive aborts=%d/%d slots; paired=%d; position-open events/slots/"
        "lifecycles=%d/%d/%d"
        % (
            connection_archive["events"],
            connection_archive["unique_cycle_slots"],
            connection_archive["paired_writer_slots"],
            connection_archive["events_while_position_open"],
            connection_archive["unique_position_open_cycle_slots"],
            connection_archive["affected_position_lifecycles"],
        )
    )
    print(
        "  schedule offset min/median/max=%.3f/%.3f/%.3fs; causal PnL=%s"
        % (
            connection_offset["min"],
            connection_offset["median"],
            connection_offset["max"],
            connection_archive[
                "causal_pnl_or_missed_exit_effect_identified"
            ],
        )
    )
    print("  " + connection_fallback["decision"])
    print("=" * 104)


def main() -> None:
    ap = argparse.ArgumentParser(description="Study TQQQ overnight gap-through-stop risk")
    ap.add_argument("--refresh", action="store_true", help="refresh the pinned Yahoo hourly cache")
    ap.add_argument("--csv", help="use a caller-supplied full-session hourly CSV")
    ap.add_argument("--json", metavar="PATH", help="write full machine-readable results")
    ap.add_argument("--selfcheck", action="store_true", help="run synthetic gap-fill checks first")
    ap.add_argument("--audits", action="store_true",
                    help="run ONLY the offline source audits (no market data needed)")
    args = ap.parse_args()
    if args.audits:
        raise SystemExit(run_source_audits())
    if args.selfcheck:
        selfcheck()
        print("[selfcheck PASS]")
    result = run(refresh=args.refresh, csv_path=args.csv)
    _print(result)
    if args.json:
        with open(args.json, "w") as fh:
            json.dump(result, fh, indent=2)
        print("[wrote %s]" % args.json)


if __name__ == "__main__":
    main()

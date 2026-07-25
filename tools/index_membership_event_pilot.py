#!/usr/bin/env python3
"""Small, explicit index-membership event-window pilot.

This is not a strategy backtest. It measures two preregistered recent batches—a
March 2026 S&P 500 pilot and a December 2025 Nasdaq-100 replication—so the wider
IX-00 study can validate its event clock, security identity handling, outcome
definitions, and cross-provider stability before attempting a historical panel.

Raw Yahoo data are not written to the repository.  The emitted JSON contains
derived event-window measurements, a fingerprint of the normalized input
slice, retrieval metadata, and loud small-sample limitations.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import sys
from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional, Sequence

import pandas as pd


@dataclass(frozen=True)
class EventSecurity:
    event_symbol: str
    provider_symbol: str
    action: str
    transition: str
    exclusion_reason: Optional[str] = None


@dataclass(frozen=True)
class EventBatch:
    batch_id: str
    artifact: str
    provider: str
    source_url: str
    announcement_source_at: str
    announcement_time_quality: str
    first_tradable_session: str
    implementation_session: str
    implementation_time_quality: str
    effective_session: str
    benchmark: str
    default_start: str
    default_end: str
    securities: Sequence[EventSecurity]
    excluded_securities: Sequence[EventSecurity] = ()


SP500_MARCH_2026_SECURITIES: Sequence[EventSecurity] = (
    EventSecurity("VRT", "VRT", "addition", "direct_entry"),
    EventSecurity("LITE", "LITE", "addition", "family_up_migration"),
    EventSecurity("COHR", "COHR", "addition", "family_up_migration"),
    # EchoStar changed SATS -> ECHO on 2026-06-24 without a CUSIP change.
    EventSecurity("SATS", "ECHO", "addition", "family_up_migration"),
    EventSecurity("MTCH", "MTCH", "deletion", "family_down_migration"),
    EventSecurity("MOH", "MOH", "deletion", "family_down_migration"),
    EventSecurity("LW", "LW", "deletion", "family_down_migration"),
    EventSecurity("PAYC", "PAYC", "deletion", "family_down_migration"),
)

NDX_DECEMBER_2025_SECURITIES: Sequence[EventSecurity] = (
    EventSecurity("ALNY", "ALNY", "addition", "direct_entry"),
    EventSecurity("FER", "FER", "addition", "direct_entry"),
    EventSecurity("INSM", "INSM", "addition", "direct_entry"),
    EventSecurity("MPWR", "MPWR", "addition", "direct_entry"),
    EventSecurity("STX", "STX", "addition", "direct_entry"),
    EventSecurity("WDC", "WDC", "addition", "direct_entry"),
    EventSecurity("BIIB", "BIIB", "deletion", "direct_exit"),
    EventSecurity("CDW", "CDW", "deletion", "direct_exit"),
    EventSecurity("GFS", "GFS", "deletion", "direct_exit"),
    EventSecurity("LULU", "LULU", "deletion", "direct_exit"),
    EventSecurity("ON", "ON", "deletion", "direct_exit"),
    EventSecurity("TTD", "TTD", "deletion", "direct_exit"),
)

NDX_DECEMBER_2024_SECURITIES: Sequence[EventSecurity] = (
    EventSecurity("PLTR", "PLTR", "addition", "direct_entry"),
    EventSecurity("MSTR", "MSTR", "addition", "direct_entry"),
    EventSecurity("AXON", "AXON", "addition", "direct_entry"),
    EventSecurity("ILMN", "ILMN", "deletion", "direct_exit"),
    EventSecurity("SMCI", "SMCI", "deletion", "direct_exit"),
    EventSecurity("MRNA", "MRNA", "deletion", "direct_exit"),
)

NDX_DECEMBER_2022_SECURITIES: Sequence[EventSecurity] = (
    EventSecurity("CSGP", "CSGP", "addition", "direct_entry"),
    EventSecurity("RIVN", "RIVN", "addition", "direct_entry"),
    EventSecurity("WBD", "WBD", "addition", "direct_entry"),
    EventSecurity("GFS", "GFS", "addition", "direct_entry"),
    EventSecurity("BKR", "BKR", "addition", "direct_entry"),
    EventSecurity("FANG", "FANG", "addition", "direct_entry"),
    EventSecurity("VRSN", "VRSN", "deletion", "direct_exit"),
    EventSecurity("SWKS", "SWKS", "deletion", "direct_exit"),
    EventSecurity("BIDU", "BIDU", "deletion", "direct_exit"),
    EventSecurity("MTCH", "MTCH", "deletion", "direct_exit"),
    EventSecurity("DOCU", "DOCU", "deletion", "direct_exit"),
    EventSecurity("NTES", "NTES", "deletion", "direct_exit"),
)

NDX_DECEMBER_2023_REVISION_SECURITIES: Sequence[EventSecurity] = (
    EventSecurity("TTWO", "TTWO", "addition", "corporate_action_replacement"),
)

BATCHES = {
    "sp500-2026-03": EventBatch(
        batch_id="sp500-2026-03",
        artifact="IX-00 March 2026 S&P 500 event-window pilot",
        provider="S&P Dow Jones Indices",
        source_url="https://www.spglobal.com/spdji/en/documents/indexnews/announcements/20260306-1482263/1482263_march2026rebalance1546.pdf",
        announcement_source_at="2026-03-06",
        announcement_time_quality="date_only",
        first_tradable_session="2026-03-09",
        implementation_session="2026-03-20",
        implementation_time_quality="inferred_prior_close_from_effective_pre_open",
        effective_session="2026-03-23",
        benchmark="SPY",
        default_start="2026-02-20",
        default_end="2026-07-24",
        securities=SP500_MARCH_2026_SECURITIES,
    ),
    "ndx-2022-12": EventBatch(
        batch_id="ndx-2022-12",
        artifact="IX-00 December 2022 Nasdaq-100 event-window replication",
        provider="Nasdaq Global Indexes",
        source_url="https://www.nasdaq.com/press-release/annual-changes-to-the-nasdaq-100-index-2022-12-09",
        announcement_source_at="2022-12-09T20:00:00-05:00",
        announcement_time_quality="exact_after_hours",
        first_tradable_session="2022-12-12",
        implementation_session="2022-12-16",
        implementation_time_quality="inferred_prior_close_from_effective_pre_open",
        effective_session="2022-12-19",
        benchmark="QQQ",
        default_start="2022-11-15",
        default_end="2023-04-01",
        securities=NDX_DECEMBER_2022_SECURITIES,
        excluded_securities=(
            EventSecurity("SPLK", "SPLK", "deletion", "direct_exit"),
        ),
    ),
    "ndx-2023-12-update": EventBatch(
        batch_id="ndx-2023-12-update",
        artifact="IX-01 December 2023 Nasdaq-100 revision event-window diagnostic",
        provider="Nasdaq Global Indexes",
        source_url="https://www.nasdaq.com/press-release/update%3A-annual-changes-to-the-nasdaq-100r-index-2023-12-12",
        announcement_source_at="2023-12-12T18:00:00-05:00",
        announcement_time_quality="exact_after_hours",
        first_tradable_session="2023-12-13",
        implementation_session="2023-12-15",
        implementation_time_quality="inferred_prior_close_from_effective_pre_open",
        effective_session="2023-12-18",
        benchmark="QQQ",
        default_start="2023-11-15",
        default_end="2024-04-01",
        securities=NDX_DECEMBER_2023_REVISION_SECURITIES,
        excluded_securities=(
            # SGEN ceased to be an ordinary tradable equity when Pfizer's cash
            # merger became effective on 2023-12-14. A cash-consideration
            # endpoint belongs in a corporate-action outcome model, not in the
            # continuing-equity return calculator below.
            EventSecurity(
                "SGEN",
                "SGEN",
                "deletion",
                "corporate_action_replacement",
                "cash merger became effective 2023-12-14; evaluate $229 consideration "
                "and last tradable session instead of a continuing-equity return",
            ),
        ),
    ),
    "ndx-2024-12": EventBatch(
        batch_id="ndx-2024-12",
        artifact="IX-00 December 2024 Nasdaq-100 event-window replication",
        provider="Nasdaq Global Indexes",
        source_url="https://www.nasdaq.com/press-release/annual-changes-nasdaq-100-indexr-2024-12-13",
        announcement_source_at="2024-12-13T20:00:00-05:00",
        announcement_time_quality="exact_after_hours",
        first_tradable_session="2024-12-16",
        implementation_session="2024-12-20",
        implementation_time_quality="inferred_prior_close_from_effective_pre_open",
        effective_session="2024-12-23",
        benchmark="QQQ",
        default_start="2024-11-20",
        default_end="2025-04-01",
        securities=NDX_DECEMBER_2024_SECURITIES,
    ),
    "ndx-2025-12": EventBatch(
        batch_id="ndx-2025-12",
        artifact="IX-00 December 2025 Nasdaq-100 event-window replication",
        provider="Nasdaq Global Indexes",
        source_url="https://www.nasdaq.com/press-release/annual-changes-nasdaq-100-indexr-2025-12-13",
        announcement_source_at="2025-12-12T20:00:00-05:00",
        announcement_time_quality="exact_after_hours",
        first_tradable_session="2025-12-15",
        implementation_session="2025-12-19",
        implementation_time_quality="inferred_prior_close_from_effective_pre_open",
        effective_session="2025-12-22",
        benchmark="QQQ",
        default_start="2025-11-20",
        default_end="2026-04-01",
        securities=NDX_DECEMBER_2025_SECURITIES,
    ),
}

DEFAULT_BATCH = BATCHES["sp500-2026-03"]

# Compatibility aliases keep the original pilot's public test surface stable.
ANNOUNCEMENT_DATE = DEFAULT_BATCH.announcement_source_at
FIRST_TRADABLE_SESSION = DEFAULT_BATCH.first_tradable_session
IMPLEMENTATION_SESSION = DEFAULT_BATCH.implementation_session
EFFECTIVE_SESSION = DEFAULT_BATCH.effective_session
BENCHMARK = DEFAULT_BATCH.benchmark
SECURITIES = DEFAULT_BATCH.securities


def _finite(value: float) -> float:
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"non-finite value: {value}")
    return value


def adjusted_open(frame: pd.DataFrame) -> pd.Series:
    """Return split/dividend-adjusted opens on the Adj Close scale."""
    ratio = frame["Adj Close"] / frame["Close"]
    return frame["Open"] * ratio


def relative_return(asset_return: float, benchmark_return: float) -> float:
    """Compounded relative return, not the small-return arithmetic shortcut."""
    return (1.0 + asset_return) / (1.0 + benchmark_return) - 1.0


def nth_session_on_or_after(index: pd.DatetimeIndex, date: str, n: int) -> pd.Timestamp:
    """The nth observed session on/after date, with n=1 meaning that date/session."""
    eligible = index[index >= pd.Timestamp(date)]
    if len(eligible) < n:
        raise ValueError(f"need {n} sessions on/after {date}; found {len(eligible)}")
    return eligible[n - 1]


def _window_return(
    frame: pd.DataFrame,
    start_date: str,
    start_field: str,
    end_date: pd.Timestamp,
    end_field: str,
) -> float:
    start = frame.loc[pd.Timestamp(start_date), start_field]
    end = frame.loc[end_date, end_field]
    return _finite(end / start - 1.0)


def _security_metrics(
    frame: pd.DataFrame,
    benchmark: pd.DataFrame,
    security: EventSecurity,
    batch: EventBatch,
) -> Dict[str, object]:
    asset = frame.xs(security.provider_symbol, axis=1, level="Ticker").copy()
    bench = benchmark.copy()
    asset["Adj Open"] = adjusted_open(asset)
    bench["Adj Open"] = adjusted_open(bench)

    required = [
        pd.Timestamp(batch.announcement_source_at).tz_localize(None).normalize(),
        pd.Timestamp(batch.first_tradable_session),
        pd.Timestamp(batch.implementation_session),
        pd.Timestamp(batch.effective_session),
    ]
    missing = [x.strftime("%Y-%m-%d") for x in required if x not in asset.index]
    if missing:
        raise ValueError(f"{security.event_symbol}: missing required sessions {missing}")

    horizons = {
        "post_implementation_1_session": nth_session_on_or_after(
            asset.index, batch.effective_session, 1
        ),
        "post_implementation_5_sessions": nth_session_on_or_after(
            asset.index, batch.effective_session, 5
        ),
        "post_implementation_20_sessions": nth_session_on_or_after(
            asset.index, batch.effective_session, 20
        ),
        "post_implementation_60_sessions": nth_session_on_or_after(
            asset.index, batch.effective_session, 60
        ),
    }

    windows = {
        "announcement_to_first_open": (
            pd.Timestamp(batch.announcement_source_at)
            .tz_localize(None)
            .strftime("%Y-%m-%d"),
            "Adj Close",
            pd.Timestamp(batch.first_tradable_session),
            "Adj Open",
        ),
        "first_open_to_implementation_close": (
            batch.first_tradable_session,
            "Adj Open",
            pd.Timestamp(batch.implementation_session),
            "Adj Close",
        ),
        "implementation_close_to_effective_open": (
            batch.implementation_session,
            "Adj Close",
            pd.Timestamp(batch.effective_session),
            "Adj Open",
        ),
    }
    for name, horizon_date in horizons.items():
        windows[name] = (
            batch.implementation_session,
            "Adj Close",
            horizon_date,
            "Adj Close",
        )

    metrics: Dict[str, float] = {}
    for name, (start_date, start_field, end_date, end_field) in windows.items():
        asset_ret = _window_return(asset, start_date, start_field, end_date, end_field)
        bench_ret = _window_return(bench, start_date, start_field, end_date, end_field)
        metrics[name + "_raw"] = asset_ret
        metrics[name + "_benchmark"] = bench_ret
        metrics[name + "_relative"] = relative_return(asset_ret, bench_ret)

    prior = asset.loc[
        asset.index < pd.Timestamp(batch.implementation_session), "Volume"
    ].tail(20)
    if len(prior) != 20 or prior.median() <= 0:
        raise ValueError(f"{security.event_symbol}: incomplete 20-session volume baseline")
    implementation_volume = _finite(
        asset.loc[pd.Timestamp(batch.implementation_session), "Volume"]
    )
    metrics["implementation_volume_ratio_to_prior_20d_median"] = _finite(
        implementation_volume / prior.median()
    )

    return {
        "event_symbol": security.event_symbol,
        "provider_symbol": security.provider_symbol,
        "action": security.action,
        "transition": security.transition,
        "horizon_dates": {
            key: value.strftime("%Y-%m-%d") for key, value in horizons.items()
        },
        "metrics": metrics,
    }


def _mean(values: Iterable[float]) -> float:
    vals = list(values)
    if not vals:
        raise ValueError("cannot average empty group")
    return _finite(sum(vals) / len(vals))


def summarize_groups(rows: Sequence[Mapping[str, object]]) -> Dict[str, object]:
    metric_names = sorted(rows[0]["metrics"])
    definitions = {
        "additions": lambda row: row["action"] == "addition",
        "deletions": lambda row: row["action"] == "deletion",
        "direct_entries": lambda row: row["transition"] == "direct_entry",
        "direct_exits": lambda row: row["transition"] == "direct_exit",
        "family_up_migrations": lambda row: row["transition"] == "family_up_migration",
        "family_down_migrations": lambda row: row["transition"] == "family_down_migration",
    }
    out: Dict[str, object] = {}
    for name, include in definitions.items():
        selected = [row for row in rows if include(row)]
        if not selected:
            out[name] = {"n": 0, "means": {}}
            continue
        out[name] = {
            "n": len(selected),
            "means": {
                metric: _mean(float(row["metrics"][metric]) for row in selected)
                for metric in metric_names
            },
        }
    return out


def normalized_input_fingerprint(
    frame: pd.DataFrame, numeric_round_decimals: Optional[int] = None
) -> str:
    """Fingerprint the exact normalized vendor snapshot.

    This is intentionally exact. Consecutive Yahoo downloads have shown insignificant
    adjusted-price float jitter, so this hash may change even when study conclusions
    reproduce. Decision-level stability is captured separately below.
    """
    normalized = frame.sort_index().sort_index(axis=1)
    if numeric_round_decimals is not None:
        normalized = normalized.round(numeric_round_decimals)
    hashed = pd.util.hash_pandas_object(normalized, index=True).values.tobytes()
    return hashlib.sha256(hashed).hexdigest()


def derived_result_fingerprint(
    rows: Sequence[Mapping[str, object]],
    batch: EventBatch,
) -> str:
    """Hash exactly the evidence precision displayed by the study."""

    def displayed_metric(name: str, value: object) -> float:
        numeric = float(value)
        if name == "implementation_volume_ratio_to_prior_20d_median":
            return round(numeric, 2)
        return round(numeric * 100.0, 2)

    payload = {
        "batch_id": batch.batch_id,
        "official_source": batch.source_url,
        "event_clock": {
            "announcement_source_at": batch.announcement_source_at,
            "first_tradable_session": batch.first_tradable_session,
            "implementation_session": batch.implementation_session,
            "effective_session": batch.effective_session,
        },
        "excluded_securities": [
            {
                "event_symbol": security.event_symbol,
                "provider_symbol": security.provider_symbol,
                "action": security.action,
                "transition": security.transition,
                **(
                    {"exclusion_reason": security.exclusion_reason}
                    if security.exclusion_reason
                    else {}
                ),
            }
            for security in batch.excluded_securities
        ],
        "securities": [
            {
                "event_symbol": row["event_symbol"],
                "provider_symbol": row["provider_symbol"],
                "action": row["action"],
                "transition": row["transition"],
                "metrics": {
                    key: displayed_metric(key, value)
                    for key, value in sorted(row["metrics"].items())
                },
            }
            for row in rows
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def analyze(
    frame: pd.DataFrame,
    retrieved_at: str,
    batch: EventBatch = DEFAULT_BATCH,
) -> Dict[str, object]:
    if not isinstance(frame.columns, pd.MultiIndex):
        raise ValueError("expected yfinance-style MultiIndex columns")
    required_symbols = {s.provider_symbol for s in batch.securities} | {batch.benchmark}
    present = set(frame.columns.get_level_values("Ticker"))
    missing = sorted(required_symbols - present)
    if missing:
        raise ValueError(f"missing provider symbols: {missing}")

    benchmark = frame.xs(batch.benchmark, axis=1, level="Ticker").copy()
    rows = [
        _security_metrics(frame, benchmark, security, batch)
        for security in batch.securities
    ]
    return {
        "artifact": batch.artifact,
        "batch_id": batch.batch_id,
        "official_source": batch.source_url,
        "schema_version": 1,
        "status": (
            "descriptive partial-coverage pilot; barred from pooled directional inference"
            if batch.excluded_securities
            else "descriptive source-contract pilot; no predictive edge claimed"
        ),
        "retrieved_at_utc": retrieved_at,
        "provider": "Yahoo Finance via yfinance",
        "provider_version": None,
        "raw_data_committed": False,
        "normalized_input_sha256": normalized_input_fingerprint(frame),
        "derived_result_sha256": derived_result_fingerprint(rows, batch),
        "fingerprint_contract": {
            "input_hash": "exact sorted normalized vendor frame; may expose provider revision or float jitter",
            "derived_hash_returns": "percentage points rounded to 2 decimals",
            "derived_hash_volume_ratio": "multiple rounded to 2 decimals",
            "reason": "separate exact snapshot provenance from decision-level reproducibility",
        },
        "event_clock": {
            "announcement_source_at": batch.announcement_source_at,
            "announcement_time_quality": batch.announcement_time_quality,
            "historical_tradable_policy": "next regular-session open",
            "first_tradable_session": batch.first_tradable_session,
            "implementation_session_close": batch.implementation_session,
            "implementation_time_quality": batch.implementation_time_quality,
            "effective_session_open": batch.effective_session,
        },
        "coverage": {
            "analyzed": len(batch.securities),
            "official_events": len(batch.securities) + len(batch.excluded_securities),
            "complete": not batch.excluded_securities,
        },
        "excluded_securities": [
            {
                "event_symbol": security.event_symbol,
                "provider_symbol": security.provider_symbol,
                "action": security.action,
                "transition": security.transition,
                "reason": security.exclusion_reason
                or "historical rows unavailable from the pilot's current free provider",
            }
            for security in batch.excluded_securities
        ],
        "securities": rows,
        "groups": summarize_groups(rows),
        "limitations": [
            f"one {len(batch.securities)}-security batch; group means are descriptive and receive no p-values",
            "the primary tradable clock is the next regular-session open; exact timestamps remain separate from daily prices",
            "Yahoo Finance is a convenient validation source, not the production market-data authority",
            "daily OHLCV cannot identify closing-auction imbalance, spread, or auction-only volume",
            "provider_symbol is not durable security identity; production joins require time-bounded identifiers",
            "transition labels come from the official announcement and require historical family membership validation at scale",
            *(
                [
                    f"{len(batch.excluded_securities)} official event(s) are excluded for provider-history failure; this batch is incomplete and barred from pooled directional inference"
                ]
                if batch.excluded_securities
                else []
            ),
        ],
    }


def fetch_prices(
    batch: EventBatch, start: str, end: str
) -> tuple[pd.DataFrame, str, str]:
    import yfinance as yf

    symbols = sorted({s.provider_symbol for s in batch.securities} | {batch.benchmark})
    yf.set_tz_cache_location("/tmp/monad-ix-yf-cache")
    retrieved_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    frame = yf.download(
        symbols,
        start=start,
        end=end,
        auto_adjust=False,
        actions=True,
        progress=False,
        threads=False,
    )
    if frame.empty:
        raise RuntimeError("price download returned no rows")
    return frame, retrieved_at, yf.__version__


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", choices=sorted(BATCHES), default=DEFAULT_BATCH.batch_id)
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="omit per-security rows while retaining clocks, groups, hashes, and caveats",
    )
    parser.add_argument(
        "--fingerprint-only",
        action="store_true",
        help="emit only batch, retrieval, provider, and fingerprint metadata",
    )
    args = parser.parse_args(argv)
    batch = BATCHES[args.batch]
    start = args.start or batch.default_start
    end = args.end or batch.default_end
    frame, retrieved_at, provider_version = fetch_prices(batch, start, end)
    result = analyze(frame, retrieved_at, batch)
    result["provider_version"] = provider_version
    if args.fingerprint_only:
        result = {
            key: result[key]
            for key in (
                "batch_id",
                "retrieved_at_utc",
                "provider",
                "provider_version",
                "normalized_input_sha256",
                "derived_result_sha256",
                "fingerprint_contract",
            )
        }
    elif args.summary_only:
        result.pop("securities")
    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

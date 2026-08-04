#!/usr/bin/env python3
"""Freeze 424B5 \"at-the-market\" discovery and an optional SPY-relative price pilot.

DI-01 phrase hits are not confirmed ATM takedowns. The price pilot is descriptive
on a capped newest-biased EFTS slice with Yahoo charts — not a tradable edge.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
import sqlite3
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import mean, median
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


REPO = Path(__file__).resolve().parents[1]
DEFAULT_SPEC = REPO / "docs" / "research" / "data" / "atm_424b5_spec.json"
DEFAULT_OUTPUT = (
    REPO / "docs" / "research" / "data" / "atm_424b5_discovery.json"
)
DEFAULT_CORRECTED_OUTPUT = (
    REPO / "docs/research/data/atm_financing_pressure_corrected_2024q1.json"
)
DEFAULT_LEDGER_SEED = REPO / "docs/research/data/atm_fp01_gold_seed.json"
DEFAULT_LEDGER_OUTPUT = REPO / "docs/research/data/atm_fp01_gold_ledger.json"
DEFAULT_LEDGER_DB = Path(tempfile.gettempdir()) / "monad-atm-fp01.sqlite3"
DEFAULT_SEARCH_RESPONSE = Path(
    "/private/tmp/monad-atm-pilot/search-424b5-atm-2024q1.json"
)
DEFAULT_BUNDLE = Path("/private/tmp/monad-atm-pilot")
SCHEMA_VERSION = 1
FINANCING_HORIZONS = (1, 5, 10, 20, 60)
TICKER_RE = re.compile(r"\(([A-Z][A-Z0-9.\-]{0,6})(?:,|\))")
ATM_LEDGER_ASSERTION_TYPES = {"program_status", "remaining_capacity_usd"}
ATM_LEDGER_STATUS_VALUES = {"active", "suspended", "exhausted", "terminated"}


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def sha256(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Mapping[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("{} must contain a JSON object".format(path))
    return value


def parse_ticker(display_name: str) -> Optional[str]:
    match = TICKER_RE.search(display_name or "")
    if not match:
        return None
    ticker = match.group(1)
    if ticker.endswith("W") or ticker.endswith("WT"):
        return None
    return ticker


def collapse_submissions(
    response: Mapping[str, object],
) -> Dict[str, Dict[str, object]]:
    hits = response.get("hits", {}).get("hits", [])
    submissions: Dict[str, Dict[str, object]] = {}
    for hit in hits:
        source = hit.get("_source", {})
        accession = source.get("adsh")
        if not accession:
            raise ValueError("search hit missing accession")
        names = list(source.get("display_names", []))
        current = submissions.setdefault(
            accession,
            {
                "accession": accession,
                "ciks": list(source.get("ciks", [])),
                "file_date": source.get("file_date"),
                "form": source.get("form"),
                "display_names": names,
                "parsed_ticker": parse_ticker(names[0] if names else ""),
                "matched_documents": 0,
            },
        )
        current["matched_documents"] += 1
    return submissions


def chart_closes(path: Path) -> Dict[str, float]:
    payload = load_json(path)
    result = payload.get("chart", {}).get("result")
    if not result:
        return {}
    row = result[0]
    out: Dict[str, float] = {}
    for ts, close in zip(
        row.get("timestamp") or [],
        row.get("indicators", {}).get("quote", [{}])[0].get("close") or [],
    ):
        if close is None:
            continue
        day = datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d")
        out[day] = float(close)
    return out


def forward_window(
    days: Sequence[str],
    file_date: str,
    horizon: int,
    max_entry_lag_days: int = 7,
) -> Optional[Tuple[str, str]]:
    """Return a conservative post-filing window only when coverage is contiguous.

    A historical price cache that starts months after ``file_date`` must not silently
    turn its first available observation into the event entry.  Seven calendar days
    permits ordinary weekends and long market holidays while rejecting stale caches.
    """
    start_idx = None
    for i, day in enumerate(days):
        if day > file_date:
            start_idx = i
            break
    if start_idx is None:
        return None
    end_idx = start_idx + horizon - 1
    if end_idx >= len(days):
        return None
    entry = datetime.strptime(days[start_idx], "%Y-%m-%d").date()
    event = datetime.strptime(file_date, "%Y-%m-%d").date()
    if (entry - event).days > max_entry_lag_days:
        return None
    return days[start_idx], days[end_idx]


def price_pilot(
    submissions: Mapping[str, Mapping[str, object]],
    bundle: Path,
    horizons: Sequence[int] = (10, 20),
) -> Dict[str, object]:
    spy_path = bundle / "SPY_chart.json"
    spy = chart_closes(spy_path) if spy_path.is_file() else {}
    rows: List[Dict[str, object]] = []
    for row in submissions.values():
        ticker = row.get("parsed_ticker")
        file_date = row.get("file_date")
        if not ticker or not file_date:
            continue
        path = bundle / "{}_chart.json".format(ticker)
        if not path.is_file() or path.stat().st_size < 200:
            continue
        px = chart_closes(path)
        if len(px) < 40:
            continue
        days = sorted(px)
        out: Dict[str, object] = {
            "ticker": ticker,
            "accession": row["accession"],
            "file_date": file_date,
        }
        ok = False
        for horizon in horizons:
            pair = forward_window(days, str(file_date), int(horizon))
            if not pair:
                continue
            d0, d1 = pair
            ret = px[d1] / px[d0] - 1.0
            out["entry_date"] = d0
            out["ret_{}d".format(horizon)] = round(ret, 4)
            if d0 in spy and d1 in spy:
                spy_ret = spy[d1] / spy[d0] - 1.0
                out["spy_{}d".format(horizon)] = round(spy_ret, 4)
                out["xs_{}d".format(horizon)] = round(ret - spy_ret, 4)
            ok = True
        if ok:
            rows.append(out)
    xs10 = [r["xs_10d"] for r in rows if "xs_10d" in r]
    xs20 = [r["xs_20d"] for r in rows if "xs_20d" in r]
    summary = {
        "n_events_with_price": len(rows),
        "median_xs_10d": round(median(xs10), 4) if xs10 else None,
        "mean_xs_10d": round(mean(xs10), 4) if xs10 else None,
        "frac_negative_xs_10d": round(
            sum(1 for x in xs10 if x < 0) / len(xs10), 4
        )
        if xs10
        else None,
        "median_xs_20d": round(median(xs20), 4) if xs20 else None,
        "descriptive_only": True,
        "caveat": (
            "phrase hit != ATM takedown; capped newest-biased slice; "
            "microcaps dominate; no costs"
        ),
    }
    return {"summary": summary, "rows": rows}


def episode_events(
    submissions: Iterable[Mapping[str, object]], gap_days: int = 30
) -> List[Dict[str, object]]:
    """Collapse clustered supplements for one ticker into program episodes."""
    candidates = sorted(
        (
            {
                "ticker": str(row["parsed_ticker"]),
                "file_date": str(row["file_date"]),
                "accession": str(row["accession"]),
                "ciks": list(row.get("ciks", [])),
            }
            for row in submissions
            if row.get("parsed_ticker") and row.get("file_date")
        ),
        key=lambda row: (row["ticker"], row["file_date"], row["accession"]),
    )
    retained: List[Dict[str, object]] = []
    last: Dict[str, date] = {}
    for row in candidates:
        event = date.fromisoformat(str(row["file_date"]))
        prior = last.get(str(row["ticker"]))
        if prior is not None and (event - prior).days <= gap_days:
            continue
        retained.append(row)
        last[str(row["ticker"])] = event
    return retained


def _clean_series(series) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for stamp, value in series.dropna().items():
        day = stamp.date().isoformat() if hasattr(stamp, "date") else str(stamp)[:10]
        out[day] = float(value)
    return out


def download_adjusted_closes(
    tickers: Sequence[str], start: str, end: str, chunk_size: int = 25
) -> Tuple[Dict[str, Dict[str, float]], str]:
    """Download split/dividend-adjusted closes and hash the used price panel."""
    import yfinance as yf

    symbols = sorted(set(tickers) | {"SPY"})
    closes: Dict[str, Dict[str, float]] = {}
    for offset in range(0, len(symbols), chunk_size):
        chunk = symbols[offset : offset + chunk_size]
        frame = yf.download(
            chunk,
            start=start,
            end=end,
            auto_adjust=True,
            actions=False,
            progress=False,
            threads=True,
            group_by="ticker",
        )
        if frame.empty:
            continue
        if len(chunk) == 1:
            closes[chunk[0]] = _clean_series(frame["Close"])
            continue
        for ticker in chunk:
            try:
                closes[ticker] = _clean_series(frame[ticker]["Close"])
            except (KeyError, TypeError):
                continue
    panel = {ticker: rows for ticker, rows in sorted(closes.items()) if rows}
    return panel, sha256(panel)


def financing_pressure_event_return(
    event: Mapping[str, object],
    prices: Mapping[str, Mapping[str, float]],
    horizons: Sequence[int] = FINANCING_HORIZONS,
    max_entry_lag_days: int = 7,
) -> Optional[Dict[str, object]]:
    """Measure from the first post-filing close and reject stale price coverage."""
    ticker = str(event["ticker"])
    stock = prices.get(ticker, {})
    spy = prices.get("SPY", {})
    days = sorted(stock)
    event_day = date.fromisoformat(str(event["file_date"]))
    start_idx = next((i for i, day in enumerate(days) if day > str(event_day)), None)
    if start_idx is None:
        return None
    entry_day = date.fromisoformat(days[start_idx])
    if (entry_day - event_day).days > max_entry_lag_days:
        return None
    entry_key = entry_day.isoformat()
    if entry_key not in spy:
        return None
    row: Dict[str, object] = dict(event)
    row["entry_date"] = entry_key
    row["entry_lag_calendar_days"] = (entry_day - event_day).days
    for horizon in horizons:
        end_idx = start_idx + int(horizon)
        if end_idx >= len(days):
            continue
        end = days[end_idx]
        if end not in spy:
            continue
        stock_return = stock[end] / stock[entry_key] - 1.0
        spy_return = spy[end] / spy[entry_key] - 1.0
        row[f"end_{horizon}d"] = end
        row[f"ret_{horizon}d"] = round(stock_return, 6)
        row[f"spy_{horizon}d"] = round(spy_return, 6)
        row[f"xs_{horizon}d"] = round(stock_return - spy_return, 6)
    return row if any(f"xs_{h}d" in row for h in horizons) else None


def bootstrap_median_ci(
    values: Sequence[float], seed: int = 253204, draws: int = 5000
) -> Optional[List[float]]:
    if not values:
        return None
    rng = random.Random(seed)
    samples = sorted(
        median([rng.choice(values) for _ in values]) for _ in range(draws)
    )
    lo = samples[int(0.025 * (draws - 1))]
    hi = samples[int(0.975 * (draws - 1))]
    return [round(float(lo), 6), round(float(hi), 6)]


def wilson_interval(negative: int, total: int) -> Optional[List[float]]:
    if total <= 0:
        return None
    z = 1.959963984540054
    p = negative / total
    denom = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    half = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denom
    return [round(centre - half, 6), round(centre + half, 6)]


def summarize_financing_pressure(
    rows: Sequence[Mapping[str, object]],
) -> Dict[str, object]:
    horizons: Dict[str, object] = {}
    for horizon in FINANCING_HORIZONS:
        key = f"xs_{horizon}d"
        values = [float(row[key]) for row in rows if key in row]
        if not values:
            continue
        negative = sum(value < 0 for value in values)
        horizons[str(horizon)] = {
            "n": len(values),
            "median_spy_excess": round(median(values), 6),
            "median_bootstrap_95pct": bootstrap_median_ci(values),
            "mean_spy_excess": round(mean(values), 6),
            "fraction_negative": round(negative / len(values), 6),
            "fraction_negative_wilson_95pct": wilson_interval(negative, len(values)),
        }
    return {
        "priced_episodes": len(rows),
        "max_entry_lag_calendar_days": max(
            (int(row["entry_lag_calendar_days"]) for row in rows), default=None
        ),
        "horizons": horizons,
    }


def build_financing_pressure_artifact(
    discovery_path: Path,
    prices: Mapping[str, Mapping[str, float]],
    price_panel_sha256: str,
) -> Dict[str, object]:
    discovery = load_json(discovery_path)
    events = episode_events(discovery.get("submissions", []))
    rows = [financing_pressure_event_return(event, prices) for event in events]
    priced = sorted(
        (row for row in rows if row is not None),
        key=lambda row: (row["file_date"], row["ticker"]),
    )
    artifact: Dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "study_id": "ATM-FP-01",
        "source_discovery_sha256": file_sha256(discovery_path),
        "price_panel_sha256": price_panel_sha256,
        "source_class": "424B5_phrase_hit",
        "confirmed_atm_program": False,
        "confirmed_atm_sales": False,
        "outcome_role": "corrected_descriptive_price_audit",
        "clock": {
            "source": "SEC file_date; accepted-at absent",
            "entry": "first adjusted close strictly after file_date",
            "max_entry_lag_calendar_days": 7,
        },
        "episode_policy": "first ticker event after a gap greater than 30 days",
        "input_unique_submissions": len(discovery.get("submissions", [])),
        "candidate_episodes": len(events),
        "summary": summarize_financing_pressure(priced),
        "rows": priced,
        "caveats": [
            "phrase hit is neither a reviewed ATM program nor evidence of shares sold",
            "first 100 of 463 Q1 hits is capped and search-order biased",
            "ticker mapping is parsed from current display names and is not a security master",
            "Yahoo adjusted history is convenient discovery data, not licensed production data",
            "SPY excess does not control size, industry, cash burn, volatility, or issuance propensity",
        ],
    }
    artifact["artifact_sha256"] = sha256(artifact)
    return artifact


def _parse_ledger_date(value: object, field: str) -> date:
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError(f"{field}: invalid ISO date {value!r}") from exc


def _parse_ledger_datetime(value: object, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError(f"{field}: invalid ISO datetime {value!r}") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field}: timezone offset required")
    return parsed


def validate_atm_ledger_seed(seed: Mapping[str, object]) -> None:
    """Validate reviewed facts and enforce outcome-clock leakage barriers."""
    if seed.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported ATM ledger schema_version")
    if seed.get("raw_documents_committed") is not False:
        raise ValueError("raw_documents_committed must be false")
    if not str(seed.get("fixture_id", "")).strip():
        raise ValueError("fixture_id is required")
    _parse_ledger_datetime(seed.get("reviewed_at"), "reviewed_at")

    issuers = list(seed.get("issuers", []))
    sources = list(seed.get("sources", []))
    programs = list(seed.get("programs", []))
    assertions = list(seed.get("assertions", []))
    labels = list(seed.get("utilization_labels", []))
    collections = [
        ("issuer", issuers, "issuer_id"),
        ("source", sources, "source_id"),
        ("program", programs, "program_id"),
        ("assertion", assertions, "assertion_id"),
        ("label", labels, "label_id"),
    ]
    for kind, rows, key in collections:
        ids = [str(row.get(key, "")) for row in rows]
        if not rows or any(not value for value in ids):
            raise ValueError(f"ATM ledger requires non-empty {kind} records with {key}")
        if len(ids) != len(set(ids)):
            raise ValueError(f"duplicate {key}")

    issuer_by_id = {str(row["issuer_id"]): row for row in issuers}
    source_by_id = {str(row["source_id"]): row for row in sources}
    program_by_id = {str(row["program_id"]): row for row in programs}

    for issuer in issuers:
        cik = str(issuer.get("cik", ""))
        if not re.fullmatch(r"\d{10}", cik):
            raise ValueError(f"{issuer['issuer_id']}: CIK must be ten digits")
        for field in ("name", "security_id", "ticker", "identity_quality"):
            if not str(issuer.get(field, "")).strip():
                raise ValueError(f"{issuer['issuer_id']}: missing {field}")

    for source in sources:
        source_id = str(source["source_id"])
        accession = str(source.get("accession", ""))
        if not re.fullmatch(r"\d{10}-\d{2}-\d{6}", accession):
            raise ValueError(f"{source_id}: invalid accession")
        if accession.replace("-", "") not in str(source.get("document_url", "")):
            raise ValueError(f"{source_id}: accession absent from document_url")
        filed = _parse_ledger_date(source.get("file_date"), f"{source_id}.file_date")
        tradable = _parse_ledger_datetime(
            source.get("conservative_tradable_at"),
            f"{source_id}.conservative_tradable_at",
        )
        quality = source.get("source_time_quality")
        accepted = source.get("accepted_at")
        if quality == "edgar_acceptance_exact":
            accepted_dt = _parse_ledger_datetime(accepted, f"{source_id}.accepted_at")
            if tradable <= accepted_dt:
                raise ValueError(f"{source_id}: tradable clock must follow acceptance")
        elif quality == "file_date_only":
            if accepted is not None:
                raise ValueError(f"{source_id}: date-only source cannot claim accepted_at")
            if tradable.date() <= filed:
                raise ValueError(f"{source_id}: date-only source must trade next day or later")
        else:
            raise ValueError(f"{source_id}: unsupported source_time_quality")
        if not str(source.get("reviewed_excerpt", "")).strip():
            raise ValueError(f"{source_id}: reviewed_excerpt required")
        if source.get("raw_content_hash_validated") is not False:
            raise ValueError(f"{source_id}: raw hash validation must stay false")

    for program in programs:
        program_id = str(program["program_id"])
        issuer_id = str(program.get("issuer_id", ""))
        if issuer_id not in issuer_by_id:
            raise ValueError(f"{program_id}: unknown issuer")
        agreement = program.get("agreement_date")
        if agreement is not None:
            _parse_ledger_date(agreement, f"{program_id}.agreement_date")
        capacity = program.get("initial_capacity_usd")
        if capacity is not None and float(capacity) < 0:
            raise ValueError(f"{program_id}: negative initial capacity")
        prior_id = program.get("supersedes_program_id")
        if prior_id is not None:
            if prior_id not in program_by_id or prior_id == program_id:
                raise ValueError(f"{program_id}: invalid supersedes_program_id")
            if program_by_id[prior_id]["issuer_id"] != issuer_id:
                raise ValueError(f"{program_id}: cannot supersede another issuer")

    for assertion in assertions:
        assertion_id = str(assertion["assertion_id"])
        if assertion.get("program_id") not in program_by_id:
            raise ValueError(f"{assertion_id}: unknown program")
        if assertion.get("source_id") not in source_by_id:
            raise ValueError(f"{assertion_id}: unknown source")
        kind = assertion.get("assertion_type")
        if kind not in ATM_LEDGER_ASSERTION_TYPES:
            raise ValueError(f"{assertion_id}: unsupported assertion_type")
        _parse_ledger_date(assertion.get("effective_on"), f"{assertion_id}.effective_on")
        if kind == "program_status" and assertion.get("value") not in ATM_LEDGER_STATUS_VALUES:
            raise ValueError(f"{assertion_id}: invalid program status")
        if kind == "remaining_capacity_usd" and float(assertion.get("value", -1)) < 0:
            raise ValueError(f"{assertion_id}: negative remaining capacity")

    for label in labels:
        label_id = str(label["label_id"])
        if label.get("program_id") not in program_by_id:
            raise ValueError(f"{label_id}: unknown program")
        source_id = str(label.get("source_id", ""))
        if source_id not in source_by_id:
            raise ValueError(f"{label_id}: unknown source")
        start = _parse_ledger_date(label.get("period_start"), f"{label_id}.period_start")
        end = _parse_ledger_date(label.get("period_end"), f"{label_id}.period_end")
        if start > end:
            raise ValueError(f"{label_id}: period_start after period_end")
        if end >= _parse_ledger_date(source_by_id[source_id]["file_date"], source_id):
            raise ValueError(f"{label_id}: label must be disclosed after period end")
        if label.get("label_scope") not in {"period", "cumulative"}:
            raise ValueError(f"{label_id}: invalid label_scope")
        if label.get("predictive_features_allowed") is not False:
            raise ValueError(f"{label_id}: outcome cannot be a predictive feature")
        if label.get("quarter_trainable") is True and label.get("label_scope") != "period":
            raise ValueError(f"{label_id}: cumulative label cannot train a quarter model")
        for field in (
            "shares_sold",
            "gross_proceeds_usd",
            "net_proceeds_usd",
            "weighted_average_price_usd",
            "remaining_capacity_usd",
        ):
            value = label.get(field)
            if value is not None and float(value) < 0:
                raise ValueError(f"{label_id}: negative {field}")


def build_atm_ledger_artifact(seed: Mapping[str, object]) -> Dict[str, object]:
    validate_atm_ledger_seed(seed)
    sources = []
    source_by_id: Dict[str, Mapping[str, object]] = {}
    for row in seed["sources"]:
        source = dict(row)
        source["reviewed_excerpt_sha256"] = sha256(source["reviewed_excerpt"])
        sources.append(source)
        source_by_id[str(source["source_id"])] = source
    labels = []
    for row in seed["utilization_labels"]:
        label = dict(row)
        source = source_by_id[str(label["source_id"])]
        label["label_available_at"] = source["conservative_tradable_at"]
        label["interval_censored"] = True
        labels.append(label)
    artifact: Dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "artifact_id": seed["fixture_id"],
        "research_status": seed["research_status"],
        "reviewed_at": seed["reviewed_at"],
        "raw_documents_committed": False,
        "training_features_built": False,
        "issuers": list(seed["issuers"]),
        "sources": sources,
        "programs": list(seed["programs"]),
        "assertions": list(seed["assertions"]),
        "utilization_labels": labels,
        "summary": {
            "issuer_count": len(seed["issuers"]),
            "source_count": len(sources),
            "program_count": len(seed["programs"]),
            "assertion_count": len(seed["assertions"]),
            "utilization_label_count": len(labels),
            "quarter_trainable_label_count": sum(
                row["quarter_trainable"] is True for row in labels
            ),
            "positive_period_labels": sum(
                row["label_scope"] == "period" and row["shares_sold"] > 0
                for row in labels
            ),
            "zero_period_labels": sum(
                row["label_scope"] == "period" and row["shares_sold"] == 0
                for row in labels
            ),
            "cumulative_labels_quarantined": sum(
                row["label_scope"] == "cumulative"
                and row["quarter_trainable"] is False
                for row in labels
            ),
            "exact_acceptance_clocks": sum(
                row["source_time_quality"] == "edgar_acceptance_exact"
                for row in sources
            ),
            "date_only_clocks": sum(
                row["source_time_quality"] == "file_date_only" for row in sources
            ),
        },
    }
    artifact["artifact_sha256"] = sha256(artifact)
    return artifact


ATM_LEDGER_SQL = """
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = DELETE;
PRAGMA synchronous = FULL;
CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL) STRICT;
CREATE TABLE issuers (
    issuer_id TEXT PRIMARY KEY, cik TEXT NOT NULL, name TEXT NOT NULL,
    security_id TEXT NOT NULL, ticker TEXT NOT NULL, identity_quality TEXT NOT NULL
) STRICT;
CREATE TABLE sources (
    source_id TEXT PRIMARY KEY, accession TEXT NOT NULL, form TEXT NOT NULL,
    document_url TEXT NOT NULL, file_date TEXT NOT NULL, accepted_at TEXT,
    source_time_quality TEXT NOT NULL, conservative_tradable_at TEXT NOT NULL,
    reviewed_excerpt_sha256 TEXT NOT NULL, raw_content_hash_validated INTEGER NOT NULL
) STRICT;
CREATE TABLE programs (
    program_id TEXT PRIMARY KEY, issuer_id TEXT NOT NULL REFERENCES issuers(issuer_id),
    agent TEXT, agreement_date TEXT, agreement_date_quality TEXT NOT NULL,
    initial_capacity_usd REAL, ib6_limited INTEGER,
    supersedes_program_id TEXT REFERENCES programs(program_id)
) STRICT;
CREATE TABLE assertions (
    assertion_id TEXT PRIMARY KEY,
    program_id TEXT NOT NULL REFERENCES programs(program_id),
    source_id TEXT NOT NULL REFERENCES sources(source_id),
    assertion_type TEXT NOT NULL, effective_on TEXT NOT NULL, value_json TEXT NOT NULL
) STRICT;
CREATE TABLE utilization_labels (
    label_id TEXT PRIMARY KEY,
    program_id TEXT NOT NULL REFERENCES programs(program_id),
    source_id TEXT NOT NULL REFERENCES sources(source_id),
    period_start TEXT NOT NULL, period_end TEXT NOT NULL, label_scope TEXT NOT NULL,
    shares_sold INTEGER NOT NULL, gross_proceeds_usd REAL, net_proceeds_usd REAL,
    weighted_average_price_usd REAL, remaining_capacity_usd REAL,
    label_available_at TEXT NOT NULL, interval_censored INTEGER NOT NULL,
    quarter_trainable INTEGER NOT NULL, predictive_features_allowed INTEGER NOT NULL
) STRICT;
CREATE VIEW latest_program_status AS
WITH ranked AS (
    SELECT a.*, ROW_NUMBER() OVER (
        PARTITION BY program_id ORDER BY effective_on DESC, assertion_id DESC
    ) AS rank
    FROM assertions a WHERE assertion_type = 'program_status'
)
SELECT program_id, source_id, effective_on, value_json AS status_json
FROM ranked WHERE rank = 1;
CREATE VIEW quarter_label_outcomes AS
SELECT label_id, program_id, period_start, period_end, shares_sold,
       net_proceeds_usd, label_available_at
FROM utilization_labels
WHERE quarter_trainable = 1 AND label_scope = 'period';
"""


def build_atm_ledger_db(artifact: Mapping[str, object], path: Path) -> None:
    """Build a disposable SQLite read model; the reviewed JSON stays authoritative."""
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing ledger DB: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    try:
        con.executescript(ATM_LEDGER_SQL)
        con.executemany(
            "INSERT INTO metadata(key, value) VALUES (?, ?)",
            [
                ("artifact_id", str(artifact["artifact_id"])),
                ("artifact_sha256", str(artifact["artifact_sha256"])),
                ("authoritative_store", "reviewed_json_fixture"),
            ],
        )
        for row in artifact["issuers"]:
            con.execute(
                "INSERT INTO issuers VALUES (?, ?, ?, ?, ?, ?)",
                (
                    row["issuer_id"], row["cik"], row["name"], row["security_id"],
                    row["ticker"], row["identity_quality"],
                ),
            )
        for row in artifact["sources"]:
            con.execute(
                "INSERT INTO sources VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    row["source_id"], row["accession"], row["form"],
                    row["document_url"], row["file_date"], row["accepted_at"],
                    row["source_time_quality"], row["conservative_tradable_at"],
                    row["reviewed_excerpt_sha256"],
                    int(row["raw_content_hash_validated"]),
                ),
            )
        for row in artifact["programs"]:
            con.execute(
                "INSERT INTO programs VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    row["program_id"], row["issuer_id"], row["agent"],
                    row["agreement_date"], row["agreement_date_quality"],
                    row["initial_capacity_usd"],
                    None if row["ib6_limited"] is None else int(row["ib6_limited"]),
                    row["supersedes_program_id"],
                ),
            )
        for row in artifact["assertions"]:
            con.execute(
                "INSERT INTO assertions VALUES (?, ?, ?, ?, ?, ?)",
                (
                    row["assertion_id"], row["program_id"], row["source_id"],
                    row["assertion_type"], row["effective_on"],
                    json.dumps(row["value"], sort_keys=True),
                ),
            )
        for row in artifact["utilization_labels"]:
            con.execute(
                "INSERT INTO utilization_labels VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    row["label_id"], row["program_id"], row["source_id"],
                    row["period_start"], row["period_end"], row["label_scope"],
                    row["shares_sold"], row["gross_proceeds_usd"],
                    row["net_proceeds_usd"], row["weighted_average_price_usd"],
                    row["remaining_capacity_usd"], row["label_available_at"],
                    int(row["interval_censored"]), int(row["quarter_trainable"]),
                    int(row["predictive_features_allowed"]),
                ),
            )
        con.commit()
    finally:
        con.close()


def build_artifact(
    response_path: Path,
    spec: Mapping[str, object],
    bundle: Optional[Path] = None,
) -> Dict[str, object]:
    if int(spec.get("schema_version", -1)) != SCHEMA_VERSION:
        raise ValueError("unsupported schema_version")
    search = spec["search"]
    raw_sha = file_sha256(response_path)
    expected = search.get("response_sha256")
    if expected and expected != raw_sha:
        raise ValueError(
            "sha256 mismatch: got {} expected {}".format(raw_sha, expected)
        )
    response = load_json(response_path)
    submissions = collapse_submissions(response)
    with_ticker = sum(
        1 for row in submissions.values() if row.get("parsed_ticker")
    )
    artifact: Dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "spec_id": spec["spec_id"],
        "lab_id": "DI-01",
        "outcomes_assigned": False,
        "confirmed_atm_takedown": False,
        "raw_documents_committed": bool(spec.get("raw_documents_committed", False)),
        "search": {
            "endpoint": search["endpoint"],
            "query": search.get("query"),
            "forms": list(search["forms"]),
            "start_date": search["start_date"],
            "end_date": search["end_date"],
            "sampling": search.get("sampling"),
            "index_total": search.get("index_total"),
            "response_sha256": raw_sha,
            "bias_note": search.get("bias_note"),
        },
        "summary": {
            "fetched_document_hits": len(response.get("hits", {}).get("hits", [])),
            "unique_submissions": len(submissions),
            "submissions_with_parsed_ticker": with_ticker,
            "discovery_frame_not_reviewed_cohort": True,
            "phrase_hit_not_takedown_event": True,
        },
        "submissions": sorted(
            submissions.values(), key=lambda row: row["accession"]
        ),
    }
    if bundle is not None and bundle.is_dir():
        artifact["price_pilot"] = price_pilot(submissions, bundle)
    artifact["artifact_sha256"] = sha256(
        {k: v for k, v in artifact.items() if k != "artifact_sha256"}
    )
    return artifact


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--response", type=Path, default=DEFAULT_SEARCH_RESPONSE)
    parser.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--no-price", action="store_true")
    parser.add_argument(
        "--financing-pressure",
        action="store_true",
        help="build the corrected event-time financing-pressure audit",
    )
    parser.add_argument("--discovery", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--corrected-output", type=Path, default=DEFAULT_CORRECTED_OUTPUT)
    parser.add_argument(
        "--build-ledger",
        action="store_true",
        help="validate the reviewed FP-01 seed and build JSON/SQLite projections",
    )
    parser.add_argument("--ledger-seed", type=Path, default=DEFAULT_LEDGER_SEED)
    parser.add_argument("--ledger-output", type=Path, default=DEFAULT_LEDGER_OUTPUT)
    parser.add_argument("--ledger-db", type=Path, default=DEFAULT_LEDGER_DB)
    args = parser.parse_args(argv)
    if args.build_ledger:
        ledger = build_atm_ledger_artifact(load_json(args.ledger_seed))
        args.ledger_output.parent.mkdir(parents=True, exist_ok=True)
        with args.ledger_output.open("w", encoding="utf-8") as handle:
            json.dump(ledger, handle, indent=2, sort_keys=True)
            handle.write("\n")
        build_atm_ledger_db(ledger, args.ledger_db)
        print(
            json.dumps(
                {
                    "output": str(args.ledger_output),
                    "sqlite": str(args.ledger_db),
                    **ledger["summary"],
                },
                indent=2,
            )
        )
        return 0
    if args.financing_pressure:
        discovery = load_json(args.discovery)
        events = episode_events(discovery.get("submissions", []))
        dates = [date.fromisoformat(str(event["file_date"])) for event in events]
        start = (min(dates) - timedelta(days=10)).isoformat()
        end = (max(dates) + timedelta(days=120)).isoformat()
        prices, panel_hash = download_adjusted_closes(
            [str(event["ticker"]) for event in events], start, end
        )
        corrected = build_financing_pressure_artifact(
            args.discovery, prices, panel_hash
        )
        corrected["retrieved_at"] = datetime.now(timezone.utc).isoformat()
        corrected["artifact_sha256"] = sha256(
            {key: value for key, value in corrected.items() if key != "artifact_sha256"}
        )
        args.corrected_output.parent.mkdir(parents=True, exist_ok=True)
        with args.corrected_output.open("w", encoding="utf-8") as handle:
            json.dump(corrected, handle, indent=2, sort_keys=True)
            handle.write("\n")
        print(
            json.dumps(
                {"output": str(args.corrected_output), **corrected["summary"]},
                indent=2,
            )
        )
        return 0
    spec = load_json(args.spec)
    bundle = None if args.no_price else args.bundle
    artifact = build_artifact(args.response, spec, bundle=bundle)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        json.dump(artifact, handle, indent=2, sort_keys=True)
        handle.write("\n")
    payload = {
        "output": str(args.output),
        "unique_submissions": artifact["summary"]["unique_submissions"],
        "artifact_sha256": artifact["artifact_sha256"],
    }
    if "price_pilot" in artifact:
        payload["price_pilot_summary"] = artifact["price_pilot"]["summary"]
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

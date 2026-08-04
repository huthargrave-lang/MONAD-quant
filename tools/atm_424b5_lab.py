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
DEFAULT_SEARCH_RESPONSE = Path(
    "/private/tmp/monad-atm-pilot/search-424b5-atm-2024q1.json"
)
DEFAULT_BUNDLE = Path("/private/tmp/monad-atm-pilot")
SCHEMA_VERSION = 1
FINANCING_HORIZONS = (1, 5, 10, 20, 60)
TICKER_RE = re.compile(r"\(([A-Z][A-Z0-9.\-]{0,6})(?:,|\))")


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
    args = parser.parse_args(argv)
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

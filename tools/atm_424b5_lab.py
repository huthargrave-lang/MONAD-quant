#!/usr/bin/env python3
"""Freeze 424B5 \"at-the-market\" discovery and an optional SPY-relative price pilot.

DI-01 phrase hits are not confirmed ATM takedowns. The price pilot is descriptive
on a capped newest-biased EFTS slice with Yahoo charts — not a tradable edge.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Dict, List, Mapping, Optional, Sequence, Tuple


REPO = Path(__file__).resolve().parents[1]
DEFAULT_SPEC = REPO / "docs" / "research" / "data" / "atm_424b5_spec.json"
DEFAULT_OUTPUT = (
    REPO / "docs" / "research" / "data" / "atm_424b5_discovery.json"
)
DEFAULT_SEARCH_RESPONSE = Path(
    "/private/tmp/monad-atm-pilot/search-424b5-atm-2024q1.json"
)
DEFAULT_BUNDLE = Path("/private/tmp/monad-atm-pilot")
SCHEMA_VERSION = 1
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
    days: Sequence[str], file_date: str, horizon: int
) -> Optional[Tuple[str, str]]:
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
    args = parser.parse_args(argv)
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

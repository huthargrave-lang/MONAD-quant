#!/usr/bin/env python3
"""Market-implied close-probability proxy for cash merger deals.

Implements the CA-ANNOUNCE baseline-ladder step 0 for pure-cash consideration:

    p_proxy = clip((price - downside) / (cash - downside), 0, 1)

Optional simple discounting uses expected calendar days to close. This is a
published-assumption proxy, not a true risk-neutral probability. Stock/mixed
deals are rejected until successor-value marking is added.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
from typing import Dict, Mapping, Optional, Sequence


REPO = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = (
    REPO / "docs" / "research" / "data" / "ca_announce_market_implied_fixture.json"
)
DEFAULT_OUTPUT = (
    REPO / "docs" / "research" / "data" / "ca_announce_market_implied_seed.json"
)
SCHEMA_VERSION = 1


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def sha256(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def load_json(path: Path) -> Mapping[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("{} must contain a JSON object".format(path))
    return value


def clip01(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def market_implied_cash_probability(
    price: float,
    cash: float,
    downside: float,
    *,
    expected_days_to_close: Optional[float] = None,
    annual_discount_rate: float = 0.05,
) -> Dict[str, float]:
    if cash <= downside:
        raise ValueError("cash consideration must exceed downside")
    if price < 0 or cash <= 0 or downside < 0:
        raise ValueError("prices/consideration/downside must be non-negative")
    undiscounted = clip01((price - downside) / (cash - downside))
    if expected_days_to_close is None:
        return {
            "p_close_proxy": undiscounted,
            "gross_spread": (cash - price) / cash,
            "downside_to_break": (price - downside) / price if price else 0.0,
            "discount_factor": 1.0,
        }
    if expected_days_to_close < 0:
        raise ValueError("expected_days_to_close cannot be negative")
    discount = math.exp(
        -annual_discount_rate * (expected_days_to_close / 365.0)
    )
    discounted_cash = cash * discount
    if discounted_cash <= downside:
        raise ValueError("discounted cash must exceed downside")
    discounted = clip01((price - downside) / (discounted_cash - downside))
    return {
        "p_close_proxy": discounted,
        "p_close_proxy_undiscounted": undiscounted,
        "gross_spread": (cash - price) / cash,
        "downside_to_break": (price - downside) / price if price else 0.0,
        "discount_factor": discount,
        "discounted_cash": discounted_cash,
    }


def validate_fixture(fixture: Mapping[str, object]) -> None:
    if fixture.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported fixture schema_version")
    if fixture.get("price_source") != "transformed_fixture_not_live_feed":
        raise ValueError("price_source must declare transformed fixture")
    snapshots = fixture.get("snapshots")
    if not isinstance(snapshots, list) or not snapshots:
        raise ValueError("snapshots missing")
    ids = [row.get("snapshot_id") for row in snapshots]
    if None in ids or len(set(ids)) != len(ids):
        raise ValueError("snapshot_id values must be unique")


def build_artifact(fixture: Mapping[str, object]) -> Dict[str, object]:
    validate_fixture(fixture)
    rows = []
    for snapshot in fixture["snapshots"]:
        if snapshot.get("consideration_family") != "cash":
            raise ValueError(
                "{}: only cash deals supported in v1".format(
                    snapshot.get("snapshot_id")
                )
            )
        metrics = market_implied_cash_probability(
            float(snapshot["target_price"]),
            float(snapshot["cash_usd_per_share"]),
            float(snapshot["downside_usd_per_share"]),
            expected_days_to_close=snapshot.get("expected_days_to_close"),
            annual_discount_rate=float(
                snapshot.get("annual_discount_rate", 0.05)
            ),
        )
        rows.append(
            {
                "snapshot_id": snapshot["snapshot_id"],
                "deal_id": snapshot["deal_id"],
                "as_of": snapshot["as_of"],
                "target_symbol": snapshot.get("target_symbol"),
                "target_price": snapshot["target_price"],
                "cash_usd_per_share": snapshot["cash_usd_per_share"],
                "downside_usd_per_share": snapshot["downside_usd_per_share"],
                "expected_days_to_close": snapshot.get(
                    "expected_days_to_close"
                ),
                "annual_discount_rate": snapshot.get(
                    "annual_discount_rate", 0.05
                ),
                "assumptions": snapshot.get("assumptions", []),
                "metrics": metrics,
                "is_probability_truth": False,
                "predictive_for_outcome": False,
            }
        )
    artifact = {
        "schema_version": SCHEMA_VERSION,
        "artifact_id": fixture["fixture_id"],
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "research_status": "cash_market_implied_proxy_seed_not_calibrated_model",
        "price_source": fixture["price_source"],
        "raw_market_data_committed": False,
        "snapshots": rows,
        "summary": {
            "snapshot_count": len(rows),
            "deal_ids": sorted({row["deal_id"] for row in rows}),
            "mean_p_close_proxy": sum(
                row["metrics"]["p_close_proxy"] for row in rows
            )
            / float(len(rows)),
            "proxy_not_true_probability": True,
            "stock_and_mixed_deals_unsupported": True,
        },
    }
    artifact["snapshots_sha256"] = sha256(rows)
    validate_artifact(artifact)
    return artifact


def validate_artifact(artifact: Mapping[str, object]) -> None:
    if artifact.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported artifact schema_version")
    snapshots = artifact.get("snapshots")
    if not isinstance(snapshots, list) or not snapshots:
        raise ValueError("artifact snapshots missing")
    for row in snapshots:
        if row.get("is_probability_truth") is not False:
            raise ValueError("proxy cannot claim probability truth")
        if row.get("predictive_for_outcome") is not False:
            raise ValueError("baseline snapshot cannot be an outcome label")
        p = float(row["metrics"]["p_close_proxy"])
        if p < 0.0 or p > 1.0:
            raise ValueError("p_close_proxy out of range")
    if artifact.get("snapshots_sha256") != sha256(snapshots):
        raise ValueError("snapshots hash mismatch")


def write_json_atomic(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    temporary.replace(path)


def command_build(args: argparse.Namespace) -> None:
    artifact = build_artifact(load_json(args.fixture))
    write_json_atomic(args.output, artifact)
    print(json.dumps(artifact["summary"], indent=2))
    print("wrote {}".format(args.output))


def command_summary(args: argparse.Namespace) -> None:
    artifact = load_json(args.input)
    validate_artifact(artifact)
    print(json.dumps(artifact["summary"], indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build", help="build proxy seed")
    build.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    build.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    build.set_defaults(func=command_build)
    summary = subparsers.add_parser("summary", help="validate proxy seed")
    summary.add_argument("--input", type=Path, default=DEFAULT_OUTPUT)
    summary.set_defaults(func=command_summary)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()

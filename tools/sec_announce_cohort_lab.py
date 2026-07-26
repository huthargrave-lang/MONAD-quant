#!/usr/bin/env python3
"""Freeze and validate an announcement-time, right-censored deal cohort.

CA-FAILFRAME starts from termination language and therefore cannot estimate
failure rates. This lab builds the complementary frame: deals enter at their
announcement observation clock, carry append-only terms/conditions, and resolve
into one of three holder-outcome classes or remain right-censored at a fixed
horizon.

The committed seed is a reviewed schema pilot reused from CA-00/CA-01/CA-FAILFRAME
transformed facts. It is not a population estimate and does not claim predictive
edge. Raw SEC bytes stay outside the repository.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence


REPO = Path(__file__).resolve().parents[1]
DEFAULT_SPEC = (
    REPO / "docs" / "research" / "data" / "ca_announce_cohort_spec.json"
)
DEFAULT_OUTPUT = (
    REPO / "docs" / "research" / "data" / "ca_announce_cohort_seed.json"
)
SCHEMA_VERSION = 1
OUTCOME_CLASSES = {
    "close_as_announced",
    "higher_bid",
    "negative_termination",
    "censored",
}
STRATA = {
    "classic_public_target",
    "spac",
    "going_private",
    "fund",
    "other",
}
TIME_QUALITIES = {
    "edgar_acceptance_exact",
    "filing_date_only",
    "date_confirmed_manual_review",
}


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


def parse_iso_date(value: object, field: str) -> dt.date:
    try:
        return dt.date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError("{}: invalid date {!r}".format(field, value)) from exc


def parse_iso_datetime(value: object, field: str) -> dt.datetime:
    try:
        return dt.datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError(
            "{}: invalid datetime {!r}".format(field, value)
        ) from exc


def require_nonempty_str(mapping: Mapping[str, object], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError("{} must be a non-empty string".format(key))
    return value


def validate_spec(spec: Mapping[str, object]) -> None:
    if spec.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported spec schema_version")
    if spec.get("raw_documents_committed") is not False:
        raise ValueError("raw_documents_committed must be false")
    if spec.get("predictive_features_allowed") is not False:
        raise ValueError("outcome labels cannot be predictive features")
    if not isinstance(spec.get("spec_id"), str) or not spec["spec_id"]:
        raise ValueError("spec_id missing")
    censor_on = parse_iso_date(spec.get("censor_on"), "censor_on")
    cohort = spec.get("cohort")
    if not isinstance(cohort, dict):
        raise ValueError("cohort metadata must be an object")
    parse_iso_date(cohort.get("announcement_start"), "announcement_start")
    parse_iso_date(cohort.get("announcement_end"), "announcement_end")
    deals = spec.get("deals")
    if not isinstance(deals, list) or not deals:
        raise ValueError("deals must be a non-empty list")
    deal_ids = [deal.get("deal_id") for deal in deals]
    if None in deal_ids or len(set(deal_ids)) != len(deal_ids):
        raise ValueError("deal_ids must be unique")
    for deal in deals:
        if not isinstance(deal, dict):
            raise ValueError("each deal must be an object")
        deal_id = require_nonempty_str(deal, "deal_id")
        require_nonempty_str(deal, "target_name")
        require_nonempty_str(deal, "acquirer_name")
        require_nonempty_str(deal, "target_cik")
        stratum = deal.get("stratum")
        if stratum not in STRATA:
            raise ValueError("{}: unexpected stratum".format(deal_id))
        announced_on = parse_iso_date(deal.get("announced_on"), deal_id)
        announcement_start = parse_iso_date(
            cohort["announcement_start"], "announcement_start"
        )
        announcement_end = parse_iso_date(
            cohort["announcement_end"], "announcement_end"
        )
        if not announcement_start <= announced_on <= announcement_end:
            raise ValueError(
                "{}: announced_on outside cohort window".format(deal_id)
            )
        announcement = deal.get("announcement")
        if not isinstance(announcement, dict):
            raise ValueError("{}: announcement block missing".format(deal_id))
        observed_at = parse_iso_datetime(
            announcement.get("observed_at"),
            "{}:announcement.observed_at".format(deal_id),
        )
        quality = announcement.get("observation_time_quality")
        if quality not in TIME_QUALITIES:
            raise ValueError(
                "{}: bad announcement time quality".format(deal_id)
            )
        if observed_at.date() < announced_on:
            raise ValueError(
                "{}: announcement observation predates announced_on".format(
                    deal_id
                )
            )
        if quality == "edgar_acceptance_exact":
            if not announcement.get("accession"):
                raise ValueError(
                    "{}: exact clock requires accession".format(deal_id)
                )
        terms = deal.get("announcement_terms")
        if not isinstance(terms, dict) or not terms:
            raise ValueError("{}: announcement_terms missing".format(deal_id))
        if "consideration_family" not in terms:
            raise ValueError(
                "{}: consideration_family missing".format(deal_id)
            )
        conditions = deal.get("conditions")
        if not isinstance(conditions, dict):
            raise ValueError("{}: conditions missing".format(deal_id))
        outcome = deal.get("outcome")
        if outcome not in OUTCOME_CLASSES:
            raise ValueError("{}: unexpected outcome".format(deal_id))
        resolution = deal.get("resolution")
        if not isinstance(resolution, dict):
            raise ValueError("{}: resolution block missing".format(deal_id))
        if outcome == "censored":
            if resolution.get("resolved_on") is not None:
                raise ValueError(
                    "{}: censored deals cannot have resolved_on".format(
                        deal_id
                    )
                )
            if resolution.get("resolved_observed_at") is not None:
                raise ValueError(
                    "{}: censored deals cannot have resolve clock".format(
                        deal_id
                    )
                )
        else:
            resolved_on = parse_iso_date(
                resolution.get("resolved_on"),
                "{}:resolved_on".format(deal_id),
            )
            if resolved_on > censor_on:
                raise ValueError(
                    "{}: resolved after censor_on; mark censored instead".format(
                        deal_id
                    )
                )
            if resolved_on < announced_on:
                raise ValueError(
                    "{}: resolved_on before announced_on".format(deal_id)
                )
            resolved_observed = resolution.get("resolved_observed_at")
            if resolved_observed is not None:
                resolved_dt = parse_iso_datetime(
                    resolved_observed,
                    "{}:resolved_observed_at".format(deal_id),
                )
                if resolved_dt < observed_at:
                    raise ValueError(
                        "{}: resolve observation before announcement".format(
                            deal_id
                        )
                    )
            if not resolution.get("outcome_source_accession") and not (
                resolution.get("outcome_source_url")
            ):
                raise ValueError(
                    "{}: resolved deal needs outcome source".format(deal_id)
                )
            if outcome == "higher_bid" and not resolution.get(
                "next_counterparty"
            ):
                raise ValueError(
                    "{}: higher_bid needs next_counterparty".format(deal_id)
                )
        if deal.get("predictive_for_outcome") is not False:
            raise ValueError(
                "{}: outcome labels cannot be predictive features".format(
                    deal_id
                )
            )
        parent_nodes = deal.get("reuses_research_nodes")
        if not isinstance(parent_nodes, list) or not parent_nodes:
            raise ValueError(
                "{}: must cite parent research nodes".format(deal_id)
            )


def days_between(start: dt.date, end: dt.date) -> int:
    return (end - start).days


def build_deal_record(
    deal: Mapping[str, object],
    censor_on: dt.date,
) -> Dict[str, object]:
    announced_on = parse_iso_date(deal["announced_on"], "announced_on")
    announcement = deal["announcement"]
    observed_at = parse_iso_datetime(
        announcement["observed_at"], "observed_at"
    )
    outcome = deal["outcome"]
    resolution = deal["resolution"]
    if outcome == "censored":
        resolved_on = None
        time_to_event_days = days_between(announced_on, censor_on)
        event_observed = False
    else:
        resolved_on = parse_iso_date(resolution["resolved_on"], "resolved_on")
        time_to_event_days = days_between(announced_on, resolved_on)
        event_observed = True
    record = {
        "deal_id": deal["deal_id"],
        "target_name": deal["target_name"],
        "acquirer_name": deal["acquirer_name"],
        "target_cik": deal["target_cik"],
        "acquirer_cik": deal.get("acquirer_cik"),
        "event_symbol": deal.get("event_symbol"),
        "stratum": deal["stratum"],
        "announced_on": announced_on.isoformat(),
        "announcement": {
            "observed_at": announcement["observed_at"],
            "observation_time_quality": announcement[
                "observation_time_quality"
            ],
            "accession": announcement.get("accession"),
            "form": announcement.get("form"),
            "source_url": announcement.get("source_url"),
            "calendar_day_lag_from_announced_on": days_between(
                announced_on, observed_at.date()
            ),
        },
        "announcement_terms": deal["announcement_terms"],
        "conditions": deal["conditions"],
        "outcome": outcome,
        "resolution": {
            "resolved_on": (
                None if resolved_on is None else resolved_on.isoformat()
            ),
            "resolved_observed_at": resolution.get("resolved_observed_at"),
            "outcome_source_accession": resolution.get(
                "outcome_source_accession"
            ),
            "outcome_source_url": resolution.get("outcome_source_url"),
            "next_counterparty": resolution.get("next_counterparty"),
            "notes": resolution.get("notes"),
        },
        "censor_on": censor_on.isoformat(),
        "survival": {
            "event_observed": event_observed,
            "time_to_event_or_censor_days": time_to_event_days,
            "right_censored": outcome == "censored",
        },
        "reuses_research_nodes": list(deal["reuses_research_nodes"]),
        "predictive_for_outcome": False,
        "label_only": True,
    }
    return record


def summarize(deals: Sequence[Mapping[str, object]]) -> Dict[str, object]:
    outcomes = Counter(deal["outcome"] for deal in deals)
    strata = Counter(deal["stratum"] for deal in deals)
    qualities = Counter(
        deal["announcement"]["observation_time_quality"] for deal in deals
    )
    durations = [
        int(deal["survival"]["time_to_event_or_censor_days"]) for deal in deals
    ]
    exact_announce = sum(
        deal["announcement"]["observation_time_quality"]
        == "edgar_acceptance_exact"
        for deal in deals
    )
    return {
        "deal_count": len(deals),
        "outcome_counts": dict(sorted(outcomes.items())),
        "stratum_counts": dict(sorted(strata.items())),
        "announcement_time_qualities": dict(sorted(qualities.items())),
        "exact_announcement_clocks": exact_announce,
        "right_censored_deals": outcomes.get("censored", 0),
        "three_class_resolved_deals": sum(
            outcomes.get(name, 0)
            for name in (
                "close_as_announced",
                "higher_bid",
                "negative_termination",
            )
        ),
        "median_time_to_event_or_censor_days": sorted(durations)[
            len(durations) // 2
        ],
        "max_time_to_event_or_censor_days": max(durations),
        "schema_seed_not_population": True,
        "includes_higher_bid_as_distinct_from_negative_termination": (
            outcomes.get("higher_bid", 0) > 0
            and outcomes.get("negative_termination", 0) > 0
        ),
        "zero_censored_blocks_survival_claim": outcomes.get("censored", 0)
        == 0,
    }


def build_artifact(spec: Mapping[str, object]) -> Dict[str, object]:
    validate_spec(spec)
    censor_on = parse_iso_date(spec["censor_on"], "censor_on")
    deals = [
        build_deal_record(deal, censor_on)
        for deal in sorted(spec["deals"], key=lambda item: item["deal_id"])
    ]
    artifact: Dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "artifact_id": spec["spec_id"],
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "research_status": (
            "reviewed_announcement_schema_seed_not_population"
        ),
        "censor_on": censor_on.isoformat(),
        "cohort": spec["cohort"],
        "review_spec_id": spec["spec_id"],
        "raw_documents_committed": False,
        "predictive_features_allowed": False,
        "baseline_ladder_ready": False,
        "market_implied_baseline_included": False,
        "parent_docs": list(spec.get("parent_docs", [])),
        "deals": deals,
    }
    artifact["summary"] = summarize(deals)
    artifact["deals_sha256"] = sha256(deals)
    validate_artifact(artifact)
    return artifact


def validate_artifact(artifact: Mapping[str, object]) -> None:
    if artifact.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported artifact schema_version")
    if artifact.get("raw_documents_committed") is not False:
        raise ValueError("raw_documents_committed must be false")
    if artifact.get("predictive_features_allowed") is not False:
        raise ValueError("outcome labels cannot be predictive features")
    if artifact.get("market_implied_baseline_included") is not False:
        raise ValueError("market-implied baseline not part of this seed")
    if artifact.get("baseline_ladder_ready") is not False:
        raise ValueError("baseline ladder is not ready on schema seed alone")
    deals = artifact.get("deals")
    if not isinstance(deals, list) or not deals:
        raise ValueError("artifact must contain deals")
    if len({deal.get("deal_id") for deal in deals}) != len(deals):
        raise ValueError("duplicate deal_id")
    censor_on = parse_iso_date(artifact.get("censor_on"), "censor_on")
    for deal in deals:
        if deal.get("predictive_for_outcome") is not False:
            raise ValueError("outcome labels cannot predict themselves")
        if deal.get("label_only") is not True:
            raise ValueError("deal records must be label-only")
        if deal.get("outcome") not in OUTCOME_CLASSES:
            raise ValueError("unexpected outcome in artifact")
        if deal["censor_on"] != censor_on.isoformat():
            raise ValueError("deal censor_on mismatch")
        survival = deal.get("survival")
        if not isinstance(survival, dict):
            raise ValueError("survival block missing")
        if deal["outcome"] == "censored":
            if survival.get("event_observed") is not False:
                raise ValueError("censored deal marked event_observed")
            if survival.get("right_censored") is not True:
                raise ValueError("censored deal missing right_censored")
        else:
            if survival.get("event_observed") is not True:
                raise ValueError("resolved deal missing event_observed")
            if survival.get("right_censored") is not False:
                raise ValueError("resolved deal marked right_censored")
        announcement = deal["announcement"]
        if int(announcement["calendar_day_lag_from_announced_on"]) < 0:
            raise ValueError("negative announcement calendar-day lag")
    if artifact.get("summary") != summarize(deals):
        raise ValueError("artifact summary mismatch")
    if artifact.get("deals_sha256") != sha256(deals):
        raise ValueError("deals hash mismatch")


def write_json_atomic(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    temporary.replace(path)


def command_build(args: argparse.Namespace) -> None:
    artifact = build_artifact(load_json(args.spec))
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
    build = subparsers.add_parser(
        "build", help="build the announcement-time cohort seed"
    )
    build.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    build.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    build.set_defaults(func=command_build)
    summary = subparsers.add_parser(
        "summary", help="validate and summarize the frozen artifact"
    )
    summary.add_argument("--input", type=Path, default=DEFAULT_OUTPUT)
    summary.set_defaults(func=command_summary)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()

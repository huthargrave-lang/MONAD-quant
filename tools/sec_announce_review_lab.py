#!/usr/bin/env python3
"""Build a clock-joined announcement review cohort from the frozen POP frame.

Takes the January discovery artifact plus a review classification spec, joins
data.sec.gov acceptance clocks already embedded in the spec, applies the fixed
censor date, and emits a deal-level cohort that can include right-censored
observations. Raw EDGAR bytes are not required and are not committed.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Dict, Mapping, Optional, Sequence


REPO = Path(__file__).resolve().parents[1]
DEFAULT_DISCOVERY = (
    REPO / "docs" / "research" / "data" / "ca_announce_population_discovery.json"
)
DEFAULT_SPEC = (
    REPO / "docs" / "research" / "data" / "ca_announce_population_review_spec.json"
)
DEFAULT_OUTPUT = (
    REPO / "docs" / "research" / "data" / "ca_announce_population_reviewed.json"
)
SCHEMA_VERSION = 1
OUTCOMES = {
    "close_as_announced",
    "higher_bid",
    "negative_termination",
    "censored",
}
ROLES = {"primary", "counterparty_duplicate", "excluded"}


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


def parse_date(value: object, field: str) -> dt.date:
    try:
        return dt.date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError("{}: bad date {!r}".format(field, value)) from exc


def parse_dt(value: object, field: str) -> dt.datetime:
    try:
        return dt.datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError("{}: bad datetime {!r}".format(field, value)) from exc


def validate_inputs(
    discovery: Mapping[str, object],
    spec: Mapping[str, object],
) -> None:
    if discovery.get("artifact_id") != spec.get("parent_discovery_id"):
        raise ValueError("review spec parent_discovery_id mismatch")
    if discovery.get("outcomes_assigned") is not False:
        raise ValueError("discovery must not assign outcomes")
    if spec.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported review schema_version")
    censor_on = parse_date(spec.get("censor_on"), "censor_on")
    early = parse_date(spec.get("early_censor_on"), "early_censor_on")
    if early >= censor_on:
        raise ValueError("early_censor_on must precede censor_on")
    submissions = {
        row["accession"]: row for row in discovery["submissions"]
    }
    seen = set()
    for row in spec["classifications"]:
        role = row.get("role")
        if role not in ROLES:
            raise ValueError("unexpected role {!r}".format(role))
        accession = row.get("accession")
        if accession in seen:
            raise ValueError("duplicate classification accession")
        seen.add(accession)
        if accession not in submissions:
            raise ValueError(
                "{}: not in discovery submissions".format(accession)
            )
        if role == "primary":
            if row.get("outcome") not in OUTCOMES:
                raise ValueError("{}: bad outcome".format(accession))
            if not row.get("deal_id"):
                raise ValueError("{}: primary needs deal_id".format(accession))
            if not row.get("announcement_accepted_at"):
                raise ValueError("{}: missing announcement clock".format(
                    accession
                ))
            parse_dt(row["announcement_accepted_at"], accession)
            if row["outcome"] == "censored":
                if row.get("resolved_on") is not None:
                    raise ValueError("{}: censored has resolved_on".format(
                        accession
                    ))
            else:
                resolved = parse_date(row.get("resolved_on"), accession)
                if resolved > censor_on:
                    raise ValueError(
                        "{}: resolved after censor; mark censored".format(
                            accession
                        )
                    )
                if not row.get("resolution_signal_accession"):
                    raise ValueError(
                        "{}: resolved deal needs resolution signal".format(
                            accession
                        )
                    )
        elif role == "excluded":
            if row.get("deal_id") is not None:
                raise ValueError("excluded row cannot have deal_id")
            if not row.get("exclusion_reason"):
                raise ValueError("excluded row needs exclusion_reason")
        elif role == "counterparty_duplicate":
            if not row.get("deal_id"):
                raise ValueError("counterparty needs deal_id")


def build_artifact(
    discovery: Mapping[str, object],
    spec: Mapping[str, object],
) -> Dict[str, object]:
    validate_inputs(discovery, spec)
    censor_on = parse_date(spec["censor_on"], "censor_on")
    early_censor_on = parse_date(spec["early_censor_on"], "early_censor_on")
    submissions = {
        row["accession"]: row for row in discovery["submissions"]
    }
    sources = []
    deals_by_id: Dict[str, Dict[str, object]] = {}
    for row in spec["classifications"]:
        sub = submissions[row["accession"]]
        source = {
            "accession": row["accession"],
            "file_date": sub["file_date"],
            "form": sub["form"],
            "ciks": sub["ciks"],
            "display_names": sub["display_names"],
            "items": sub["items"],
            "has_item_1_01": sub["has_item_1_01"],
            "review_role": row["role"],
            "deal_id": row.get("deal_id"),
            "exclusion_reason": row.get("exclusion_reason"),
            "announcement_accepted_at": row.get("announcement_accepted_at"),
            "matched_documents": sub["matched_documents"],
        }
        sources.append(source)
        if row["role"] != "primary":
            continue
        announced_on = parse_dt(
            row["announcement_accepted_at"], row["accession"]
        ).date()
        outcome = row["outcome"]
        if outcome == "censored":
            resolved_on = None
            event_observed = False
            tte = (censor_on - announced_on).days
            open_at_early = True
        else:
            resolved_on = parse_date(row["resolved_on"], row["deal_id"])
            event_observed = True
            tte = (resolved_on - announced_on).days
            open_at_early = resolved_on > early_censor_on
        deals_by_id[row["deal_id"]] = {
            "deal_id": row["deal_id"],
            "target_name": row["target_name"],
            "acquirer_name": row.get("acquirer_name"),
            "stratum": row["stratum"],
            "primary_accession": row["accession"],
            "announced_on": announced_on.isoformat(),
            "announcement_accepted_at": row["announcement_accepted_at"],
            "announcement_time_quality": "edgar_acceptance_exact",
            "outcome": outcome,
            "resolved_on": (
                None if resolved_on is None else resolved_on.isoformat()
            ),
            "resolution_signal_accession": row.get(
                "resolution_signal_accession"
            ),
            "resolution_signal_kind": row.get("resolution_signal_kind"),
            "censor_on": censor_on.isoformat(),
            "survival": {
                "event_observed": event_observed,
                "right_censored": outcome == "censored",
                "time_to_event_or_censor_days": tte,
                "open_at_early_censor": open_at_early,
            },
            "notes": row.get("notes"),
            "raw_content_hash_validated": False,
            "predictive_for_outcome": False,
            "label_only": True,
        }

    deals = [deals_by_id[key] for key in sorted(deals_by_id)]
    role_counts = Counter(source["review_role"] for source in sources)
    outcome_counts = Counter(deal["outcome"] for deal in deals)
    summary = {
        "classified_submissions": len(sources),
        "submission_roles": dict(sorted(role_counts.items())),
        "deal_count": len(deals),
        "outcome_counts": dict(sorted(outcome_counts.items())),
        "right_censored_deals": outcome_counts.get("censored", 0),
        "exact_announcement_clocks": sum(
            deal["announcement_time_quality"] == "edgar_acceptance_exact"
            for deal in deals
        ),
        "open_at_early_censor": sum(
            deal["survival"]["open_at_early_censor"] for deal in deals
        ),
        "raw_content_hash_validated": False,
        "includes_right_censored_observations": outcome_counts.get("censored", 0)
        > 0,
        "zero_censored_blocks_survival_claim": outcome_counts.get("censored", 0)
        == 0,
    }
    artifact = {
        "schema_version": SCHEMA_VERSION,
        "artifact_id": spec["spec_id"],
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "research_status": spec["research_status"],
        "parent_discovery_id": spec["parent_discovery_id"],
        "censor_on": censor_on.isoformat(),
        "early_censor_on": early_censor_on.isoformat(),
        "raw_documents_committed": False,
        "predictive_features_allowed": False,
        "sources": sources,
        "deals": deals,
        "summary": summary,
    }
    artifact["sources_sha256"] = sha256(sources)
    artifact["deals_sha256"] = sha256(deals)
    validate_artifact(artifact)
    return artifact


def validate_artifact(artifact: Mapping[str, object]) -> None:
    if artifact.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported artifact schema_version")
    if artifact.get("raw_documents_committed") is not False:
        raise ValueError("raw_documents_committed must be false")
    if artifact.get("predictive_features_allowed") is not False:
        raise ValueError("labels cannot be predictive features")
    deals = artifact["deals"]
    if len({deal["deal_id"] for deal in deals}) != len(deals):
        raise ValueError("duplicate deal_id")
    for deal in deals:
        if deal.get("predictive_for_outcome") is not False:
            raise ValueError("outcome cannot predict itself")
        if deal.get("raw_content_hash_validated") is not False:
            raise ValueError("raw hash validation must stay false here")
        if deal["outcome"] == "censored":
            if deal["survival"]["right_censored"] is not True:
                raise ValueError("censored deal missing right_censored")
            if deal["survival"]["event_observed"] is not False:
                raise ValueError("censored deal marked event_observed")
        else:
            if deal["survival"]["event_observed"] is not True:
                raise ValueError("resolved deal missing event_observed")
    if artifact.get("sources_sha256") != sha256(artifact["sources"]):
        raise ValueError("sources hash mismatch")
    if artifact.get("deals_sha256") != sha256(deals):
        raise ValueError("deals hash mismatch")
    # recompute summary checks for censored flag consistency
    censored = sum(deal["outcome"] == "censored" for deal in deals)
    if artifact["summary"]["right_censored_deals"] != censored:
        raise ValueError("censored summary mismatch")
    if artifact["summary"]["zero_censored_blocks_survival_claim"] != (
        censored == 0
    ):
        raise ValueError("zero_censored flag mismatch")


def write_json_atomic(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    temporary.replace(path)


def command_build(args: argparse.Namespace) -> None:
    artifact = build_artifact(
        load_json(args.discovery), load_json(args.spec)
    )
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
    build = subparsers.add_parser("build", help="build reviewed cohort")
    build.add_argument("--discovery", type=Path, default=DEFAULT_DISCOVERY)
    build.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    build.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    build.set_defaults(func=command_build)
    summary = subparsers.add_parser("summary", help="validate reviewed cohort")
    summary.add_argument("--input", type=Path, default=DEFAULT_OUTPUT)
    summary.set_defaults(func=command_summary)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()

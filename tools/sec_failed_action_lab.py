#!/usr/bin/env python3
"""Freeze and review a query-conditioned 2023 failed-merger seed.

The SEC full-text search response is treated as a discovery frame, not a
population estimate.  Document hits are collapsed to submissions, every hit is
classified as a primary deal source, duplicate/counterparty source, or
exclusion, and primary sources are validated against exact SEC submission
bytes.  Outcome terms are label-only and cannot enter predictive features.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import re
from collections import Counter
from pathlib import Path
from typing import Dict, Mapping, Optional, Sequence


REPO = Path(__file__).resolve().parents[1]
DEFAULT_SPEC = (
    REPO / "docs" / "research" / "data" / "ca_failframe_review_spec.json"
)
DEFAULT_OUTPUT = (
    REPO / "docs" / "research" / "data" / "ca_failframe_reviewed_seed.json"
)
DEFAULT_SEARCH_RESPONSE = Path(
    "/private/tmp/monad-merger-termination-search.json"
)
DEFAULT_RAW_CACHE = Path("/private/tmp/monad-sec-failed-actions-2023")
SCHEMA_VERSION = 1
ALLOWED_ROLES = {
    "primary",
    "counterparty_duplicate",
    "amendment_duplicate",
    "excluded",
}


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


def normalized_submission_text(payload: bytes) -> str:
    raw = payload.decode("latin-1", errors="replace")
    without_tags = re.sub(r"<[^>]+>", " ", raw)
    return re.sub(
        r"\s+", " ", html.unescape(without_tags)
    ).strip().lower()


def parse_source(payload: bytes, expected_accession: str) -> Dict[str, str]:
    raw = payload.decode("latin-1", errors="replace")
    accession_match = re.search(
        r"ACCESSION NUMBER:\s*(\d{10}-\d{2}-\d{6})", raw
    )
    if not accession_match or accession_match.group(1) != expected_accession:
        raise ValueError(
            "{}: source accession mismatch".format(expected_accession)
        )
    accepted_match = re.search(r"<ACCEPTANCE-DATETIME>(\d{14})", raw)
    if not accepted_match:
        raise ValueError(
            "{}: missing acceptance datetime".format(expected_accession)
        )
    naive = dt.datetime.strptime(accepted_match.group(1), "%Y%m%d%H%M%S")
    try:
        from zoneinfo import ZoneInfo

        accepted = naive.replace(tzinfo=ZoneInfo("America/New_York"))
    except ImportError:  # pragma: no cover
        accepted = naive
    return {
        "accession": expected_accession,
        "accepted_at": accepted.isoformat(),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def unique_search_submissions(
    response: Mapping[str, object],
) -> Dict[str, Dict[str, object]]:
    hits = response.get("hits", {}).get("hits", [])
    submissions: Dict[str, Dict[str, object]] = {}
    for hit in hits:
        source = hit.get("_source", {})
        accession = source.get("adsh")
        if not accession:
            raise ValueError("search hit missing accession")
        current = submissions.setdefault(
            accession,
            {
                "accession": accession,
                "ciks": list(source.get("ciks", [])),
                "file_date": source.get("file_date"),
                "form": source.get("form"),
                "display_names": list(source.get("display_names", [])),
                "matched_documents": 0,
            },
        )
        if (
            current["ciks"] != list(source.get("ciks", []))
            or current["file_date"] != source.get("file_date")
            or current["form"] != source.get("form")
        ):
            raise ValueError(
                "{}: inconsistent search hit metadata".format(accession)
            )
        current["matched_documents"] += 1
    return submissions


def validate_spec(spec: Mapping[str, object]) -> None:
    if spec.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported spec schema_version")
    if spec.get("raw_documents_committed") is not False:
        raise ValueError("raw_documents_committed must be false")
    search = spec.get("search")
    if not isinstance(search, dict):
        raise ValueError("search spec must be an object")
    if search.get("expected_document_hits") != 31:
        raise ValueError("expected_document_hits changed")
    if search.get("expected_unique_submissions") != 23:
        raise ValueError("expected_unique_submissions changed")
    classifications = spec.get("classifications")
    if not isinstance(classifications, list) or len(classifications) != 23:
        raise ValueError("classifications must contain 23 submissions")
    accessions = [item.get("accession") for item in classifications]
    if None in accessions or len(set(accessions)) != len(accessions):
        raise ValueError("classification accessions must be unique")
    role_counts = Counter(item.get("role") for item in classifications)
    if set(role_counts) - ALLOWED_ROLES:
        raise ValueError("unexpected classification role")
    if role_counts != Counter(
        {
            "primary": 14,
            "excluded": 5,
            "counterparty_duplicate": 3,
            "amendment_duplicate": 1,
        }
    ):
        raise ValueError("classification strata changed")
    deals = spec.get("deals")
    if not isinstance(deals, list) or len(deals) != 14:
        raise ValueError("deals must contain 14 reviewed terminations")
    deal_ids = [deal.get("deal_id") for deal in deals]
    if None in deal_ids or len(set(deal_ids)) != len(deal_ids):
        raise ValueError("deal_ids must be unique")
    primary_by_deal = {
        item.get("deal_id"): item["accession"]
        for item in classifications
        if item["role"] == "primary"
    }
    if set(primary_by_deal) != set(deal_ids):
        raise ValueError("every deal needs exactly one primary classification")
    for deal in deals:
        if deal.get("primary_accession") != primary_by_deal[deal["deal_id"]]:
            raise ValueError(
                "{}: primary accession mismatch".format(deal["deal_id"])
            )
        dt.date.fromisoformat(str(deal.get("event_on")))
        markers = deal.get("required_markers")
        if not isinstance(markers, list) or not markers:
            raise ValueError("{}: required markers missing".format(
                deal["deal_id"]
            ))
        if not deal.get("reason_family"):
            raise ValueError("{}: reason_family missing".format(
                deal["deal_id"]
            ))
        if not isinstance(deal.get("termination_terms"), dict):
            raise ValueError("{}: termination_terms missing".format(
                deal["deal_id"]
            ))
    for item in classifications:
        if item["role"] == "excluded":
            if not item.get("exclusion_reason") or item.get("deal_id"):
                raise ValueError("excluded source needs only exclusion_reason")
        elif not item.get("deal_id"):
            raise ValueError("included source needs deal_id")


def filing_url(cik: str, accession: str) -> str:
    short_cik = str(int(cik))
    return (
        "https://www.sec.gov/Archives/edgar/data/{}/{}/{}.txt".format(
            short_cik, accession.replace("-", ""), accession
        )
    )


def summarize(
    sources: Sequence[Mapping[str, object]],
    deals: Sequence[Mapping[str, object]],
) -> Dict[str, object]:
    role_counts = Counter(source["review_role"] for source in sources)
    day_lags = Counter(deal["source_calendar_day_lag"] for deal in deals)
    reason_counts = Counter(deal["reason_family"] for deal in deals)
    return {
        "search_document_hits": sum(
            int(source["matched_documents"]) for source in sources
        ),
        "unique_submissions": len(sources),
        "reviewed_unique_deals": len(deals),
        "submission_roles": dict(sorted(role_counts.items())),
        "reason_families": dict(sorted(reason_counts.items())),
        "source_calendar_day_lags": {
            str(key): value for key, value in sorted(day_lags.items())
        },
        "same_day_primary_sources": day_lags.get(0, 0),
        "later_primary_sources": sum(
            count for lag, count in day_lags.items() if lag > 0
        ),
        "spac_deadline_liquidation_reason_deals": sum(
            "spac" in deal["reason_family"] for deal in deals
        ),
        "explicit_regulatory_or_market_reason": sum(
            deal["reason_family"]
            in {
                "regulatory_timing_uncertainty",
                "regulatory_no_clear_path",
                "market_conditions_and_regulatory_delay",
                "challenging_bank_market",
            }
            for deal in deals
        ),
        "query_conditioned_not_population": True,
    }


def build_artifact(
    response_path: Path,
    raw_cache: Path,
    spec: Mapping[str, object],
) -> Dict[str, object]:
    validate_spec(spec)
    if file_sha256(response_path) != spec["search"]["response_sha256"]:
        raise ValueError("SEC search response sha256 mismatch")
    response = load_json(response_path)
    total = response.get("hits", {}).get("total", {}).get("value")
    if total != spec["search"]["expected_document_hits"]:
        raise ValueError("SEC search total changed")
    submissions = unique_search_submissions(response)
    if len(submissions) != spec["search"]["expected_unique_submissions"]:
        raise ValueError("SEC unique submission count changed")
    classifications = {
        item["accession"]: item for item in spec["classifications"]
    }
    if set(submissions) != set(classifications):
        raise ValueError("search accessions and classifications differ")
    deals_by_id = {deal["deal_id"]: deal for deal in spec["deals"]}

    sources = []
    parsed_by_accession = {}
    text_by_accession = {}
    for accession in sorted(submissions):
        meta = submissions[accession]
        path = raw_cache / (accession + ".txt")
        if not path.is_file():
            raise ValueError("{}: raw SEC source missing".format(path))
        payload = path.read_bytes()
        parsed = parse_source(payload, accession)
        parsed_by_accession[accession] = parsed
        text_by_accession[accession] = normalized_submission_text(payload)
        classification = classifications[accession]
        ciks = meta["ciks"]
        if not ciks:
            raise ValueError("{}: search source has no CIK".format(accession))
        source = {
            "accession": accession,
            "accepted_at": parsed["accepted_at"],
            "file_date": meta["file_date"],
            "form": meta["form"],
            "ciks": ciks,
            "display_names": meta["display_names"],
            "matched_documents": meta["matched_documents"],
            "review_role": classification["role"],
            "deal_id": classification.get("deal_id"),
            "exclusion_reason": classification.get("exclusion_reason"),
            "source_url": filing_url(ciks[0], accession),
            "source_sha256": parsed["sha256"],
            "raw_document_committed": False,
        }
        sources.append(source)

    deals = []
    for deal_id in sorted(deals_by_id):
        spec_deal = deals_by_id[deal_id]
        accession = spec_deal["primary_accession"]
        text = text_by_accession[accession]
        for marker in spec_deal["required_markers"]:
            if marker.lower() not in text:
                raise ValueError(
                    "{}: required marker absent: {!r}".format(
                        deal_id, marker
                    )
                )
        parsed = parsed_by_accession[accession]
        accepted_date = dt.datetime.fromisoformat(
            parsed["accepted_at"]
        ).date()
        event_on = dt.date.fromisoformat(spec_deal["event_on"])
        if accepted_date < event_on:
            raise ValueError("{}: source predates asserted event".format(
                deal_id
            ))
        deal_sources = [
            source["accession"]
            for source in sources
            if source.get("deal_id") == deal_id
        ]
        deals.append(
            {
                "deal_id": deal_id,
                "target_or_subject": spec_deal["target_or_subject"],
                "other_party": spec_deal["other_party"],
                "outcome": "merger_agreement_terminated",
                "event_on": spec_deal["event_on"],
                "event_time_quality": "date_only",
                "reason_family": spec_deal["reason_family"],
                "termination_terms": spec_deal["termination_terms"],
                "primary_accession": accession,
                "primary_accepted_at": parsed["accepted_at"],
                "source_calendar_day_lag": (
                    accepted_date - event_on
                ).days,
                "source_accessions": sorted(deal_sources),
                "source_markers_validated": True,
                "predictive_for_outcome": False,
            }
        )

    artifact: Dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "artifact_id": "ca-failframe-2023-mutual-termination-seed-v1",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "research_status": "reviewed_query_seed_not_failure_population",
        "search": {
            "endpoint": spec["search"]["endpoint"],
            "query": spec["search"]["query"],
            "start_date": spec["search"]["start_date"],
            "end_date": spec["search"]["end_date"],
            "forms": spec["search"]["forms"],
            "response_sha256": spec["search"]["response_sha256"],
            "raw_response_committed": False,
        },
        "review_spec_id": spec["spec_id"],
        "raw_documents_committed": False,
        "predictive_features_allowed": False,
        "sources": sources,
        "deals": deals,
    }
    artifact["summary"] = summarize(sources, deals)
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
        raise ValueError("failure outcomes cannot be predictive features")
    sources = artifact.get("sources")
    deals = artifact.get("deals")
    if not isinstance(sources, list) or len(sources) != 23:
        raise ValueError("artifact must contain 23 reviewed submissions")
    if not isinstance(deals, list) or len(deals) != 14:
        raise ValueError("artifact must contain 14 unique deals")
    if len({source.get("accession") for source in sources}) != len(sources):
        raise ValueError("duplicate source accession")
    if len({deal.get("deal_id") for deal in deals}) != len(deals):
        raise ValueError("duplicate deal_id")
    for source in sources:
        if source.get("raw_document_committed") is not False:
            raise ValueError("raw SEC submissions cannot be committed")
    for deal in deals:
        if deal.get("predictive_for_outcome") is not False:
            raise ValueError("failure label cannot predict itself")
        if deal.get("source_markers_validated") is not True:
            raise ValueError("deal markers must be validated")
        if deal.get("outcome") != "merger_agreement_terminated":
            raise ValueError("unexpected deal outcome")
        if int(deal.get("source_calendar_day_lag", -1)) < 0:
            raise ValueError("negative source calendar-day lag")
    if artifact.get("summary") != summarize(sources, deals):
        raise ValueError("artifact summary mismatch")
    if artifact.get("sources_sha256") != sha256(sources):
        raise ValueError("sources hash mismatch")
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
    artifact = build_artifact(
        args.search_response, args.raw_cache, load_json(args.spec)
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
    build = subparsers.add_parser(
        "build", help="build the reviewed failed-action seed"
    )
    build.add_argument(
        "--search-response", type=Path, default=DEFAULT_SEARCH_RESPONSE
    )
    build.add_argument("--raw-cache", type=Path, default=DEFAULT_RAW_CACHE)
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

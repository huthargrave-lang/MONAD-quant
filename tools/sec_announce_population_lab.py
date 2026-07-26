#!/usr/bin/env python3
"""Freeze an announcement-time SEC search into a discovery population frame.

CA-ANNOUNCE-POP starts from contemporaneous \"entered into an Agreement and Plan
of Merger\" language rather than termination phrases. Document hits collapse to
submissions. Item codes and SPAC-ish heuristics are discovery tags only — they
are not deal outcomes and do not create predictive labels.

Raw EFTS responses stay outside the repository; only the hashed discovery
manifest is committed.
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
    REPO / "docs" / "research" / "data" / "ca_announce_population_spec.json"
)
DEFAULT_OUTPUT = (
    REPO / "docs" / "research" / "data" / "ca_announce_population_discovery.json"
)
DEFAULT_SEARCH_RESPONSE = Path(
    "/private/tmp/monad-merger-announcement-search-2023-01.json"
)
SCHEMA_VERSION = 1
SPAC_SIC = {"6770"}


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


def looks_spacish(names: Sequence[str], sics: Sequence[str]) -> bool:
    if any(str(sic) in SPAC_SIC for sic in sics):
        return True
    needles = (
        "acquisition corp",
        "acquisition corporation",
        "acquisition co",
        "blank check",
        "capital corp",
        "capital corporation",
        "spac",
    )
    joined = " ".join(names).lower()
    return any(needle in joined for needle in needles)


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
        current = submissions.setdefault(
            accession,
            {
                "accession": accession,
                "ciks": list(source.get("ciks", [])),
                "file_date": source.get("file_date"),
                "form": source.get("form"),
                "display_names": list(source.get("display_names", [])),
                "items": [],
                "sics": [],
                "matched_documents": 0,
                "file_types": {},
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
        file_type = source.get("file_type") or "unknown"
        current["file_types"][file_type] = (
            int(current["file_types"].get(file_type, 0)) + 1
        )
        for item in source.get("items") or []:
            if item not in current["items"]:
                current["items"].append(item)
        for sic in source.get("sics") or []:
            text = str(sic)
            if text not in current["sics"]:
                current["sics"].append(text)
    for current in submissions.values():
        current["items"] = sorted(current["items"])
        current["sics"] = sorted(current["sics"])
        current["file_types"] = dict(sorted(current["file_types"].items()))
        current["has_item_1_01"] = "1.01" in current["items"]
        current["has_item_1_02"] = "1.02" in current["items"]
        current["spacish_heuristic"] = looks_spacish(
            current["display_names"], current["sics"]
        )
        current["discovery_role"] = "unreviewed_candidate"
        current["outcome_assigned"] = False
    return submissions


def validate_spec(spec: Mapping[str, object]) -> None:
    if spec.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported spec schema_version")
    if spec.get("raw_documents_committed") is not False:
        raise ValueError("raw_documents_committed must be false")
    if spec.get("outcomes_assigned") is not False:
        raise ValueError("population discovery must not assign outcomes")
    search = spec.get("search")
    if not isinstance(search, dict):
        raise ValueError("search block missing")
    for key in (
        "endpoint",
        "query",
        "start_date",
        "end_date",
        "forms",
        "expected_document_hits",
        "expected_unique_submissions",
        "response_sha256",
    ):
        if key not in search:
            raise ValueError("search.{} missing".format(key))
    dt.date.fromisoformat(str(search["start_date"]))
    dt.date.fromisoformat(str(search["end_date"]))


def summarize(submissions: Sequence[Mapping[str, object]]) -> Dict[str, object]:
    item_counts = Counter()
    for submission in submissions:
        for item in submission["items"]:
            item_counts[item] += 1
    return {
        "search_document_hits": sum(
            int(submission["matched_documents"]) for submission in submissions
        ),
        "unique_submissions": len(submissions),
        "submissions_with_item_1_01": sum(
            bool(submission["has_item_1_01"]) for submission in submissions
        ),
        "submissions_with_item_1_02": sum(
            bool(submission["has_item_1_02"]) for submission in submissions
        ),
        "submissions_with_both_1_01_and_1_02": sum(
            submission["has_item_1_01"] and submission["has_item_1_02"]
            for submission in submissions
        ),
        "spacish_heuristic_submissions": sum(
            bool(submission["spacish_heuristic"]) for submission in submissions
        ),
        "classicish_heuristic_submissions": sum(
            (not submission["spacish_heuristic"]) and submission["has_item_1_01"]
            for submission in submissions
        ),
        "item_code_submission_counts": dict(sorted(item_counts.items())),
        "outcomes_assigned": False,
        "discovery_frame_not_reviewed_cohort": True,
        "right_censor_population_still_open": True,
    }


def build_artifact(
    response_path: Path,
    spec: Mapping[str, object],
) -> Dict[str, object]:
    validate_spec(spec)
    if file_sha256(response_path) != spec["search"]["response_sha256"]:
        raise ValueError("SEC search response sha256 mismatch")
    response = load_json(response_path)
    total = response.get("hits", {}).get("total", {}).get("value")
    if total != spec["search"]["expected_document_hits"]:
        raise ValueError("SEC search total changed")
    submissions_map = collapse_submissions(response)
    if len(submissions_map) != spec["search"]["expected_unique_submissions"]:
        raise ValueError("SEC unique submission count changed")
    submissions = [
        submissions_map[key] for key in sorted(submissions_map)
    ]
    artifact: Dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "artifact_id": spec["spec_id"],
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "research_status": (
            "frozen_announcement_search_discovery_frame_not_reviewed_cohort"
        ),
        "search": {
            "endpoint": spec["search"]["endpoint"],
            "query": spec["search"]["query"],
            "start_date": spec["search"]["start_date"],
            "end_date": spec["search"]["end_date"],
            "forms": spec["search"]["forms"],
            "response_sha256": spec["search"]["response_sha256"],
            "raw_response_committed": False,
        },
        "censor_on": spec.get("censor_on"),
        "raw_documents_committed": False,
        "outcomes_assigned": False,
        "predictive_features_allowed": False,
        "submissions": submissions,
    }
    artifact["summary"] = summarize(submissions)
    artifact["submissions_sha256"] = sha256(submissions)
    validate_artifact(artifact)
    return artifact


def validate_artifact(artifact: Mapping[str, object]) -> None:
    if artifact.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported artifact schema_version")
    if artifact.get("raw_documents_committed") is not False:
        raise ValueError("raw_documents_committed must be false")
    if artifact.get("outcomes_assigned") is not False:
        raise ValueError("discovery artifact cannot assign outcomes")
    if artifact.get("predictive_features_allowed") is not False:
        raise ValueError("discovery tags are not predictive features")
    submissions = artifact.get("submissions")
    if not isinstance(submissions, list) or not submissions:
        raise ValueError("artifact must contain submissions")
    if len({row.get("accession") for row in submissions}) != len(submissions):
        raise ValueError("duplicate accession")
    for row in submissions:
        if row.get("outcome_assigned") is not False:
            raise ValueError("submission outcome_assigned must be false")
        if row.get("discovery_role") != "unreviewed_candidate":
            raise ValueError("unexpected discovery_role")
        if int(row.get("matched_documents", 0)) < 1:
            raise ValueError("submission missing matched documents")
    if artifact.get("summary") != summarize(submissions):
        raise ValueError("artifact summary mismatch")
    if artifact.get("submissions_sha256") != sha256(submissions):
        raise ValueError("submissions hash mismatch")


def write_json_atomic(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    temporary.replace(path)


def command_build(args: argparse.Namespace) -> None:
    artifact = build_artifact(args.search_response, load_json(args.spec))
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
        "build", help="build announcement-search discovery frame"
    )
    build.add_argument(
        "--search-response", type=Path, default=DEFAULT_SEARCH_RESPONSE
    )
    build.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    build.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    build.set_defaults(func=command_build)
    summary = subparsers.add_parser(
        "summary", help="validate and summarize discovery artifact"
    )
    summary.add_argument("--input", type=Path, default=DEFAULT_OUTPUT)
    summary.set_defaults(func=command_summary)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()

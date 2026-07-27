#!/usr/bin/env python3
"""Freeze a Form 4 EFTS discovery frame without claiming insider-cluster labels.

FORM4-POP is metadata-only: document hits collapse to submissions. Raw archives
bytes are often 403; transaction-code parsing stays blocked until raw XML is
available. Day-sliced caps avoid newest-day bias from a flat ``from=0`` window.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Dict, Mapping, Sequence


REPO = Path(__file__).resolve().parents[1]
DEFAULT_SPEC = REPO / "docs" / "research" / "data" / "form4_population_spec.json"
DEFAULT_OUTPUT = (
    REPO / "docs" / "research" / "data" / "form4_population_discovery.json"
)
DEFAULT_SEARCH_RESPONSE = Path(
    "/private/tmp/monad-form4-pilot/search-day-sliced-2024-06-03_07.json"
)
SCHEMA_VERSION = 1


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
    return submissions


def build_artifact(
    response_path: Path, spec: Mapping[str, object]
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
    by_day = Counter(row["file_date"] for row in submissions.values())
    index_totals = search.get("index_totals_by_day") or {}
    artifact = {
        "schema_version": SCHEMA_VERSION,
        "spec_id": spec["spec_id"],
        "lab_id": "FORM4-POP",
        "outcomes_assigned": False,
        "transaction_codes_parsed": False,
        "raw_documents_committed": bool(spec.get("raw_documents_committed", False)),
        "search": {
            "endpoint": search["endpoint"],
            "forms": list(search["forms"]),
            "start_date": search["start_date"],
            "end_date": search["end_date"],
            "sampling": search.get("sampling"),
            "query_note": search.get(
                "query_note",
                "forms=4 only; q=* returns 0 hits on efts",
            ),
            "index_totals_by_day": index_totals,
            "index_total_sum": search.get("index_total_sum"),
            "response_sha256": raw_sha,
            "archives_raw_status": search.get("archives_raw_status"),
        },
        "summary": {
            "fetched_document_hits": len(response.get("hits", {}).get("hits", [])),
            "unique_submissions": len(submissions),
            "submissions_by_file_date": dict(sorted(by_day.items())),
            "discovery_frame_not_reviewed_cohort": True,
            "open_market_cluster_labels_not_assigned": True,
            "bias_note": search.get("bias_note"),
        },
        "submissions": sorted(
            submissions.values(), key=lambda row: row["accession"]
        ),
    }
    artifact["artifact_sha256"] = sha256(
        {k: v for k, v in artifact.items() if k != "artifact_sha256"}
    )
    return artifact


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--response", type=Path, default=DEFAULT_SEARCH_RESPONSE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    spec = load_json(args.spec)
    artifact = build_artifact(args.response, spec)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        json.dump(artifact, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "unique_submissions": artifact["summary"]["unique_submissions"],
                "fetched_document_hits": artifact["summary"][
                    "fetched_document_hits"
                ],
                "artifact_sha256": artifact["artifact_sha256"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

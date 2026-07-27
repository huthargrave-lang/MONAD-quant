#!/usr/bin/env python3
"""Freeze NT 10-K / NT 10-Q discovery frames without distress outcome labels.

LF-01 (late-filer) starts as a form-filter population. Newest-first year caps
are seasonally biased (March 10-K deadline cluster). Month-sliced samples are
discovery aids, not full cohorts. Outcomes (delist, −20d return) stay unassigned
until tickers and tradable clocks are reviewed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Dict, Mapping, Sequence


REPO = Path(__file__).resolve().parents[1]
DEFAULT_SPEC = REPO / "docs" / "research" / "data" / "nt_late_filer_spec.json"
DEFAULT_OUTPUT = (
    REPO / "docs" / "research" / "data" / "nt_late_filer_discovery.json"
)
DEFAULT_SEARCH_RESPONSE = Path(
    "/private/tmp/monad-nt-pilot/search-nt10k-2023-month-sliced.json"
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
    by_month = Counter(
        (row["file_date"] or "")[:7] for row in submissions.values()
    )
    forms = Counter(row["form"] for row in submissions.values())
    artifact = {
        "schema_version": SCHEMA_VERSION,
        "spec_id": spec["spec_id"],
        "lab_id": "LF-01",
        "outcomes_assigned": False,
        "raw_documents_committed": bool(spec.get("raw_documents_committed", False)),
        "search": {
            "endpoint": search["endpoint"],
            "forms": list(search["forms"]),
            "sampling": search.get("sampling"),
            "months": search.get("months"),
            "index_year_total_from_full_search": search.get(
                "index_year_total_from_full_search"
            ),
            "response_sha256": raw_sha,
            "bias_note": search.get("bias_note"),
        },
        "summary": {
            "fetched_document_hits": len(response.get("hits", {}).get("hits", [])),
            "unique_submissions": len(submissions),
            "submissions_by_month": dict(sorted(by_month.items())),
            "forms": dict(forms),
            "discovery_frame_not_reviewed_cohort": True,
            "distress_outcomes_not_assigned": True,
            "structural_note": (
                "NT 10-K filings cluster on the annual deadline (March); "
                "year-level newest-first caps over-weight Dec microcaps"
            ),
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
                "by_month": artifact["summary"]["submissions_by_month"],
                "artifact_sha256": artifact["artifact_sha256"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

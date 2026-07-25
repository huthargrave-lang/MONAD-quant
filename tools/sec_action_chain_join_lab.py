#!/usr/bin/env python3
"""Discover point-in-time issuer filings around frozen Form 25 events.

CA-CLOCK100B begins with the common-equity subset of CA-CLOCK100.  This tool
uses adjacent SEC quarterly master indexes to build a deterministic candidate
manifest for issuer/exchange action-chain joins.  Discovery is intentionally
broader than 8-K: foreign issuers, funds, tender offers, and reporting
termination use different form families.

The candidate manifest is a discovery artifact, not an outcome label.  A form's
presence, title, or date never establishes completion, consideration, failure,
or terminal value without content-level evidence.
"""
from __future__ import annotations

import argparse
import datetime as dt
import decimal
import gzip
import hashlib
import html
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


REPO = Path(__file__).resolve().parents[1]
DEFAULT_POPULATION = (
    REPO
    / "docs"
    / "research"
    / "data"
    / "ca_clock100_form25_2023.json"
)
DEFAULT_OUTPUT = (
    REPO
    / "docs"
    / "research"
    / "data"
    / "ca_clock100b_candidate_manifest.json"
)
DEFAULT_EVIDENCE_OUTPUT = (
    REPO
    / "docs"
    / "research"
    / "data"
    / "ca_clock100b_evidence_manifest.json"
)
DEFAULT_REVIEW_SPEC = (
    REPO
    / "docs"
    / "research"
    / "data"
    / "ca_clock100c_review_spec.json"
)
DEFAULT_REVIEWED_OUTPUT = (
    REPO
    / "docs"
    / "research"
    / "data"
    / "ca_clock100c_reviewed_seed.json"
)
DEFAULT_DIVERSE_REVIEW_SPEC = (
    REPO
    / "docs"
    / "research"
    / "data"
    / "ca_noncash_review_spec.json"
)
DEFAULT_DIVERSE_REVIEWED_OUTPUT = (
    REPO
    / "docs"
    / "research"
    / "data"
    / "ca_noncash_reviewed_seed.json"
)
DEFAULT_USER_AGENT = "MONAD Quant research contact research@example.com"
SCHEMA_VERSION = 1
SEC_ARCHIVES = "https://www.sec.gov/Archives/"
RELEVANT_FORMS = {
    "8-K",
    "8-K/A",
    "6-K",
    "6-K/A",
    "15-12B",
    "15-12G",
    "15-15D",
    "15F-12B",
    "15F-12G",
    "15F-15D",
    "N-CSR",
    "N-CSRS",
    "N-LIQUID",
    "N-CEN",
    "DEFA14A",
    "DEF 14A",
    "SC TO-T",
    "SC TO-T/A",
    "SC 14D9",
    "SC 14D9/A",
    "425",
}
FORM_PRIORITY = {
    "8-K": 100,
    "8-K/A": 95,
    "6-K": 90,
    "6-K/A": 85,
    "N-LIQUID": 80,
    "N-CSR": 75,
    "N-CSRS": 70,
    "SC 14D9": 65,
    "SC 14D9/A": 64,
    "SC TO-T": 63,
    "SC TO-T/A": 62,
    "DEFA14A": 55,
    "DEF 14A": 50,
    "425": 40,
    "15-12B": 35,
    "15-12G": 35,
    "15-15D": 35,
    "15F-12B": 35,
    "15F-12G": 35,
    "15F-15D": 35,
    "N-CEN": 20,
}
TERM_PATTERNS = {
    "completion_language": (
        r"\bconsummated\b",
        r"\bcompleted (?:the |its )?(?:merger|acquisition|transaction)\b",
        r"\bmerger (?:was completed|became effective)\b",
    ),
    "holder_conversion_language": (
        r"\bconverted into the right to receive\b",
        r"\bentitled to receive\b",
    ),
    "cash_language": (
        r"\bcash consideration\b",
        r"\bin cash,? without interest\b",
        r"\bcash per share\b",
    ),
    "stock_or_successor_language": (
        r"\bexchange ratio\b",
        r"\bsuccessor issuer\b",
        r"\bshares of (?:the )?surviving\b",
        r"\bnewly issued shares\b",
    ),
    "bankruptcy_language": (
        r"\bchapter 11\b",
        r"\bbankruptcy code\b",
        r"\bdebtor(?:s)? in possession\b",
    ),
    "liquidation_language": (
        r"\bplan of liquidation\b",
        r"\bliquidat(?:e|ed|ion|ing)\b",
        r"\bdissolution\b",
    ),
    "listing_transfer_language": (
        r"\btransfer(?:red|ring)? (?:its |the )?listing\b",
        r"\bprimary listing\b",
        r"\bcommence trading on\b",
    ),
    "failure_or_termination_language": (
        r"\btermination of the merger agreement\b",
        r"\bmerger agreement (?:was|has been) terminated\b",
        r"\bfailed to consummate\b",
    ),
    "zero_value_language": (
        r"\bwithout consideration\b",
        r"\bhave no value\b",
        r"\bno recovery\b",
    ),
}
MATERIAL_FLAGS = {
    "completion_language",
    "holder_conversion_language",
    "bankruptcy_language",
    "listing_transfer_language",
    "failure_or_termination_language",
    "zero_value_language",
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


def accession_from_archive_path(path: str) -> str:
    return Path(path).name.removesuffix(".txt")


def filing_url(archive_path: str) -> str:
    parts = archive_path.split("/")
    if len(parts) != 4 or parts[:2] != ["edgar", "data"]:
        raise ValueError("invalid EDGAR archive path: {!r}".format(archive_path))
    cik = str(int(parts[2]))
    accession = accession_from_archive_path(archive_path)
    return "{}edgar/data/{}/{}/{}.txt".format(
        SEC_ARCHIVES, cik, accession.replace("-", ""), accession
    )


def iter_master_rows(
    paths: Sequence[Path], target_ciks: Iterable[str]
) -> Iterable[Dict[str, str]]:
    targets = {str(value).zfill(10) for value in target_ciks}
    for path in paths:
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "rt", encoding="latin-1", errors="replace") as handle:
            for line in handle:
                parts = line.rstrip("\r\n").split("|")
                if len(parts) != 5:
                    continue
                cik, company_name, form_type, filed_on, archive_path = parts
                padded = cik.zfill(10)
                if padded not in targets:
                    continue
                try:
                    dt.date.fromisoformat(filed_on)
                except ValueError:
                    continue
                yield {
                    "issuer_cik": padded,
                    "company_name_index": company_name.strip(),
                    "form_type": form_type.strip(),
                    "filed_on": filed_on,
                    "archive_path": archive_path,
                    "accession": accession_from_archive_path(archive_path),
                    "submission_url": filing_url(archive_path),
                }


def candidate_score(form_type: str, day_offset: int) -> int:
    """Rank content candidates while preserving every discovered row."""
    return FORM_PRIORITY.get(form_type, 0) * 1000 - abs(day_offset)


def discover_candidates(
    population: Mapping[str, object],
    master_paths: Sequence[Path],
    before_days: int = 60,
    after_days: int = 30,
) -> Dict[str, object]:
    seeds = [
        item
        for item in population["sample"]
        if item["security_family"] == "common_equity"
    ]
    seed_by_cik = {str(item["issuer_cik"]): item for item in seeds}
    rows_by_cik: Dict[str, List[Dict[str, str]]] = {
        cik: [] for cik in seed_by_cik
    }
    for row in iter_master_rows(master_paths, seed_by_cik):
        rows_by_cik[row["issuer_cik"]].append(row)

    chains = []
    for seed in sorted(
        seeds, key=lambda item: (item["filed_on"], item["accession"])
    ):
        event_date = dt.date.fromisoformat(str(seed["filed_on"]))
        candidates = []
        for row in rows_by_cik[str(seed["issuer_cik"])]:
            if row["accession"] == seed["accession"]:
                continue
            filed_date = dt.date.fromisoformat(row["filed_on"])
            offset = (filed_date - event_date).days
            if not (-before_days <= offset <= after_days):
                continue
            if row["form_type"] not in RELEVANT_FORMS:
                continue
            item = dict(row)
            item["calendar_day_offset_from_form25"] = offset
            item["candidate_score"] = candidate_score(
                row["form_type"], offset
            )
            item["content_review_required"] = True
            candidates.append(item)
        candidates.sort(
            key=lambda item: (
                -int(item["candidate_score"]),
                abs(int(item["calendar_day_offset_from_form25"])),
                str(item["filed_on"]),
                str(item["accession"]),
            )
        )
        chains.append(
            {
                "chain_id": "ca-clock100b:" + str(seed["accession"]),
                "issuer_cik": seed["issuer_cik"],
                "issuer_name": seed["issuer_name"],
                "form25_accession": seed["accession"],
                "form25_filed_on": seed["filed_on"],
                "form25_accepted_at": seed["accepted_at"],
                "exchange_name": seed["exchange_name"],
                "rule_family": seed["rule_family"],
                "reason_family_heuristic": seed["reason_family"],
                "candidate_count": len(candidates),
                "candidate_forms": dict(
                    sorted(
                        Counter(
                            item["form_type"] for item in candidates
                        ).items()
                    )
                ),
                "candidates": candidates,
                "outcome_status": "unreviewed",
                "outcome_label": None,
            }
        )
    manifest: Dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "manifest_id": "ca-clock100b-common-equity-candidates-v1",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "research_status": "candidate_discovery_not_outcome_labels",
        "population_fixture_id": population["fixture_id"],
        "population_sample_sha256": population["sample_sha256"],
        "window": {
            "before_days": before_days,
            "after_days": after_days,
        },
        "source_indexes": [
            {
                "path_basename": path.name,
                "sha256": file_sha256(path),
                "raw_index_committed": False,
            }
            for path in master_paths
        ],
        "raw_documents_committed": False,
        "chains": chains,
    }
    manifest["summary"] = summarize(manifest)
    manifest["chains_sha256"] = sha256(chains)
    return manifest


def summarize(manifest: Mapping[str, object]) -> Dict[str, object]:
    chains = manifest["chains"]
    form_counts = Counter()
    chains_with_forms = Counter()
    for chain in chains:
        forms = set()
        for candidate in chain["candidates"]:
            form = candidate["form_type"]
            form_counts[form] += 1
            forms.add(form)
        for form in forms:
            chains_with_forms[form] += 1
    return {
        "seed_chains": len(chains),
        "chains_with_any_candidate": sum(
            bool(chain["candidates"]) for chain in chains
        ),
        "chains_without_candidates": sum(
            not chain["candidates"] for chain in chains
        ),
        "candidate_filings": sum(
            len(chain["candidates"]) for chain in chains
        ),
        "candidate_filings_by_form": dict(sorted(form_counts.items())),
        "chains_with_form": dict(sorted(chains_with_forms.items())),
    }


def validate_manifest(manifest: Mapping[str, object]) -> None:
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported schema_version")
    if manifest.get("raw_documents_committed") is not False:
        raise ValueError("raw_documents_committed must be false")
    chains = manifest.get("chains")
    if not isinstance(chains, list) or not chains:
        raise ValueError("chains must be non-empty")
    chain_ids = [chain["chain_id"] for chain in chains]
    if len(set(chain_ids)) != len(chain_ids):
        raise ValueError("duplicate chain_id")
    accessions = [chain["form25_accession"] for chain in chains]
    if len(set(accessions)) != len(accessions):
        raise ValueError("duplicate Form 25 accession")
    for chain in chains:
        if chain["outcome_status"] != "unreviewed":
            raise ValueError("discovery manifest cannot assert an outcome")
        if chain["outcome_label"] is not None:
            raise ValueError("discovery manifest outcome_label must be null")
        if chain["candidate_count"] != len(chain["candidates"]):
            raise ValueError("{}: candidate_count mismatch".format(
                chain["chain_id"]
            ))
        for candidate in chain["candidates"]:
            if candidate["content_review_required"] is not True:
                raise ValueError("candidate content review cannot be waived")
            if candidate["form_type"] not in RELEVANT_FORMS:
                raise ValueError("unexpected candidate form")
    if manifest.get("summary") != summarize(manifest):
        raise ValueError("summary mismatch")
    if manifest.get("chains_sha256") != sha256(chains):
        raise ValueError("chains hash mismatch")


def select_content_candidates(
    chain: Mapping[str, object], per_chain: int = 8
) -> List[Dict[str, object]]:
    """Select content for review without using future outcome labels."""
    candidates = list(chain["candidates"])
    selected = []
    seen = set()

    def add(item: Mapping[str, object]) -> None:
        accession = str(item["accession"])
        if accession not in seen and len(selected) < per_chain:
            selected.append(dict(item))
            seen.add(accession)

    # Same/next-day issuer reports are the strongest clock join.
    for item in candidates:
        if (
            abs(int(item["calendar_day_offset_from_form25"])) <= 1
            and item["form_type"]
            in {"8-K", "8-K/A", "6-K", "6-K/A", "N-LIQUID", "N-CSR"}
        ):
            add(item)
    # Preserve the highest-ranked candidate even when no same-day report exists.
    if candidates:
        add(candidates[0])
    # Completion often follows an approval filing. Preserve the nearest primary
    # issuer report on each side of Form 25 so proximity scoring cannot select
    # only the pre-event report.
    primary_forms = {"8-K", "8-K/A", "6-K", "6-K/A", "N-LIQUID", "N-CSR", "N-CSRS"}
    for direction in (-1, 1):
        directional = [
            item
            for item in candidates
            if item["form_type"] in primary_forms
            and (
                int(item["calendar_day_offset_from_form25"]) < 0
                if direction < 0
                else int(item["calendar_day_offset_from_form25"]) > 0
            )
        ]
        if directional:
            directional.sort(
                key=lambda item: (
                    abs(int(item["calendar_day_offset_from_form25"])),
                    -FORM_PRIORITY.get(str(item["form_type"]), 0),
                    str(item["accession"]),
                )
            )
            add(directional[0])
    # A later Form 15 is a separate reporting-state assertion.
    for item in sorted(
        candidates,
        key=lambda value: (
            abs(int(value["calendar_day_offset_from_form25"])),
            str(value["accession"]),
        ),
    ):
        if str(item["form_type"]).startswith(("15-", "15F-")):
            add(item)
            break
    # Tender/fund documents can carry terms missing from an 8-K/6-K.
    for family in (
        {"SC 14D9", "SC 14D9/A", "SC TO-T", "SC TO-T/A"},
        {"N-LIQUID", "N-CSR", "N-CSRS"},
    ):
        for item in candidates:
            if item["form_type"] in family:
                add(item)
                break
    return selected


def fetch_with_cache(
    url: str,
    cache_path: Path,
    user_agent: str,
    min_interval: float,
    retries: int = 4,
) -> bytes:
    if cache_path.exists():
        return cache_path.read_bytes()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(retries):
        try:
            request = Request(url, headers={"User-Agent": user_agent})
            with urlopen(request, timeout=30) as response:
                payload = response.read()
            cache_path.write_bytes(payload)
            time.sleep(min_interval)
            return payload
        except (HTTPError, URLError) as exc:
            if attempt + 1 == retries:
                raise RuntimeError(
                    "failed to fetch {}: {}".format(url, exc)
                )
            time.sleep(max(min_interval, 2 ** attempt))
    raise AssertionError("unreachable")


def normalized_submission_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def parse_submission_evidence(
    payload: bytes, expected_accession: str
) -> Dict[str, object]:
    source_sha = hashlib.sha256(payload).hexdigest()
    raw = payload.decode("latin-1", errors="replace")
    accession_match = re.search(
        r"ACCESSION NUMBER:\s*(\d{10}-\d{2}-\d{6})", raw
    )
    if not accession_match:
        accession_match = re.search(
            r"<SEC-DOCUMENT>(\d{10}-\d{2}-\d{6})\.txt", raw
        )
    if not accession_match or accession_match.group(1) != expected_accession:
        raise ValueError(
            "{}: submission accession mismatch".format(expected_accession)
        )
    accepted_match = re.search(r"<ACCEPTANCE-DATETIME>(\d{14})", raw)
    if not accepted_match:
        raise ValueError(
            "{}: missing acceptance datetime".format(expected_accession)
        )
    naive = dt.datetime.strptime(accepted_match.group(1), "%Y%m%d%H%M%S")
    # SEC documents the header acceptance time as Eastern.
    try:
        from zoneinfo import ZoneInfo

        accepted = naive.replace(tzinfo=ZoneInfo("America/New_York"))
    except ImportError:  # pragma: no cover - Python 3.9+ in supported runtime
        accepted = naive
    text = normalized_submission_text(raw).lower()
    flags = {}
    matched_phrases = {}
    for family, patterns in TERM_PATTERNS.items():
        matches = []
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                matches.append(match.group(0))
        flags[family] = bool(matches)
        matched_phrases[family] = sorted(set(matches))
    cash_amounts = sorted(
        {
            match.group(1).replace(",", "")
            for match in re.finditer(
                r"\$\s*([0-9]{1,4}(?:,[0-9]{3})*(?:\.[0-9]{1,4})?)"
                r"\s+(?:in cash\s+)?per (?:common |ordinary )?share",
                text,
            )
        },
        key=lambda value: float(value),
    )
    return {
        "accepted_at": accepted.isoformat(),
        "decision_clock": "accepted_at",
        "observation_time_quality": "exact_sec_acceptance_second",
        "term_flags": flags,
        "matched_phrases": matched_phrases,
        "cash_per_share_candidates": cash_amounts,
        "normalized_text_length": len(text),
        "source_sha256": source_sha,
        "raw_document_committed": False,
    }


def primary_material_source_candidate(
    form25_accepted_at: str,
    sources: Sequence[Mapping[str, object]],
) -> Optional[Dict[str, object]]:
    material = [
        source
        for source in sources
        if any(
            source["term_flags"].get(flag, False)
            for flag in MATERIAL_FLAGS
        )
    ]
    form25_clock = dt.datetime.fromisoformat(form25_accepted_at)
    material.sort(
        key=lambda source: (
            abs(
                (
                    dt.datetime.fromisoformat(str(source["accepted_at"]))
                    - form25_clock
                ).total_seconds()
            ),
            -FORM_PRIORITY.get(str(source["form_type"]), 0),
            str(source["accession"]),
        )
    )
    if not material:
        return None
    source = material[0]
    delta_seconds = int(
        (
            dt.datetime.fromisoformat(str(source["accepted_at"]))
            - form25_clock
        ).total_seconds()
    )
    return {
        "accession": source["accession"],
        "form_type": source["form_type"],
        "accepted_at": source["accepted_at"],
        "issuer_minus_exchange_seconds": delta_seconds,
        "order": (
            "issuer_source_before_exchange"
            if delta_seconds < 0
            else (
                "exchange_before_issuer_source"
                if delta_seconds > 0
                else "same_second"
            )
        ),
        "term_flags": source["term_flags"],
        "candidate_not_outcome_confirmation": True,
    }


def build_evidence_manifest(
    discovery: Mapping[str, object],
    cache_dir: Path,
    user_agent: str,
    min_interval: float,
    per_chain: int,
) -> Dict[str, object]:
    validate_manifest(discovery)
    chains = []
    for chain in discovery["chains"]:
        sources = []
        for candidate in select_content_candidates(chain, per_chain):
            cache_path = cache_dir / (str(candidate["accession"]) + ".txt")
            payload = fetch_with_cache(
                str(candidate["submission_url"]),
                cache_path,
                user_agent,
                min_interval,
            )
            evidence = dict(candidate)
            evidence.update(
                parse_submission_evidence(
                    payload, str(candidate["accession"])
                )
            )
            sources.append(evidence)
        item = {
            key: chain[key]
            for key in (
                "chain_id",
                "issuer_cik",
                "issuer_name",
                "form25_accession",
                "form25_filed_on",
                "form25_accepted_at",
                "exchange_name",
                "rule_family",
                "reason_family_heuristic",
            )
        }
        item["review_sources"] = sources
        item["review_source_count"] = len(sources)
        item["primary_material_source_candidate"] = (
            primary_material_source_candidate(
                str(chain["form25_accepted_at"]), sources
            )
        )
        item["outcome_status"] = "unreviewed"
        item["outcome_label"] = None
        chains.append(item)
    manifest: Dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "manifest_id": "ca-clock100b-content-evidence-v1",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "research_status": "content_evidence_not_outcome_labels",
        "discovery_manifest_id": discovery["manifest_id"],
        "discovery_chains_sha256": discovery["chains_sha256"],
        "raw_documents_committed": False,
        "selection": {
            "per_chain_cap": per_chain,
            "uses_future_outcome_labels": False,
        },
        "chains": chains,
    }
    flag_counts = Counter()
    order_counts = Counter()
    near_order_counts = Counter()
    deltas = []
    near_deltas = []
    for chain in chains:
        for source in chain["review_sources"]:
            for flag, present in source["term_flags"].items():
                if present:
                    flag_counts[flag] += 1
        primary = chain["primary_material_source_candidate"]
        if primary:
            order_counts[primary["order"]] += 1
            deltas.append(primary["issuer_minus_exchange_seconds"])
            if abs(primary["issuer_minus_exchange_seconds"]) <= 36 * 3600:
                near_order_counts[primary["order"]] += 1
                near_deltas.append(primary["issuer_minus_exchange_seconds"])
    manifest["summary"] = {
        "seed_chains": len(chains),
        "chains_with_review_sources": sum(
            bool(chain["review_sources"]) for chain in chains
        ),
        "chains_without_review_sources": sum(
            not chain["review_sources"] for chain in chains
        ),
        "review_sources": sum(
            len(chain["review_sources"]) for chain in chains
        ),
        "source_term_flag_counts": dict(sorted(flag_counts.items())),
        "chains_with_primary_material_source_candidate": len(deltas),
        "primary_material_source_order": dict(sorted(order_counts.items())),
        "issuer_minus_exchange_seconds": {
            "minimum": min(deltas) if deltas else None,
            "maximum": max(deltas) if deltas else None,
        },
        "near_clock_material_sources_36h": {
            "chains": len(near_deltas),
            "order": dict(sorted(near_order_counts.items())),
            "minimum_seconds": min(near_deltas) if near_deltas else None,
            "maximum_seconds": max(near_deltas) if near_deltas else None,
        },
    }
    manifest["chains_sha256"] = sha256(chains)
    return manifest


def validate_evidence_manifest(manifest: Mapping[str, object]) -> None:
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported schema_version")
    if manifest.get("raw_documents_committed") is not False:
        raise ValueError("raw_documents_committed must be false")
    chains = manifest.get("chains")
    if not isinstance(chains, list) or not chains:
        raise ValueError("chains must be non-empty")
    for chain in chains:
        if chain["outcome_status"] != "unreviewed":
            raise ValueError("evidence manifest cannot assert an outcome")
        if chain["outcome_label"] is not None:
            raise ValueError("evidence manifest outcome_label must be null")
        if chain["review_source_count"] != len(chain["review_sources"]):
            raise ValueError("review source count mismatch")
        primary = chain.get("primary_material_source_candidate")
        if primary and primary.get("candidate_not_outcome_confirmation") is not True:
            raise ValueError("primary material source must remain a candidate")
        for source in chain["review_sources"]:
            if source["raw_document_committed"] is not False:
                raise ValueError("raw content cannot be committed")
    if manifest.get("chains_sha256") != sha256(chains):
        raise ValueError("chains hash mismatch")


def build_reviewed_fixture(
    evidence: Mapping[str, object], spec: Mapping[str, object]
) -> Dict[str, object]:
    validate_evidence_manifest(evidence)
    if spec.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("review spec schema_version mismatch")
    if spec.get("review_method") != "manual_content_review":
        raise ValueError("review_method must be manual_content_review")
    entries = spec.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("review entries must be non-empty")
    chain_by_form25 = {
        str(chain["form25_accession"]): chain
        for chain in evidence["chains"]
    }
    reviewed = []
    seen_form25 = set()
    seen_evidence = set()
    for entry in entries:
        form25_accession = str(entry["form25_accession"])
        evidence_accession = str(entry["evidence_accession"])
        if form25_accession in seen_form25:
            raise ValueError("duplicate reviewed Form 25 accession")
        if evidence_accession in seen_evidence:
            raise ValueError("duplicate reviewed evidence accession")
        seen_form25.add(form25_accession)
        seen_evidence.add(evidence_accession)
        chain = chain_by_form25.get(form25_accession)
        if chain is None:
            raise ValueError(
                "reviewed Form 25 absent from evidence: {}".format(
                    form25_accession
                )
            )
        sources = {
            str(source["accession"]): source
            for source in chain["review_sources"]
        }
        source = sources.get(evidence_accession)
        if source is None:
            raise ValueError(
                "{}: evidence accession not harvested".format(
                    evidence_accession
                )
            )
        if entry.get("outcome_type") != "fixed_cash_merger":
            raise ValueError("reviewed seed currently accepts fixed cash only")
        if entry.get("rights_outcome") != "cash_right_fixed":
            raise ValueError("fixed cash review requires cash_right_fixed")
        consideration = entry.get("consideration")
        if not isinstance(consideration, dict):
            raise ValueError("consideration is required")
        if consideration.get("currency") != "USD":
            raise ValueError("reviewed seed currency must be USD")
        try:
            cash = decimal.Decimal(str(consideration["cash_per_share"]))
        except (decimal.InvalidOperation, KeyError) as exc:
            raise ValueError("invalid cash_per_share") from exc
        if not cash.is_finite() or cash <= 0:
            raise ValueError("cash_per_share must be positive and finite")
        if consideration.get("contingent") is not False:
            raise ValueError("fixed cash reviewed seed cannot be contingent")
        claim = str(entry.get("claim", "")).strip()
        if not claim or len(claim) > 500:
            raise ValueError("review claim must be 1-500 characters")
        if not source["term_flags"].get("holder_conversion_language"):
            raise ValueError(
                "{}: source lacks holder-conversion language".format(
                    evidence_accession
                )
            )
        form25_clock = dt.datetime.fromisoformat(
            str(chain["form25_accepted_at"])
        )
        source_clock = dt.datetime.fromisoformat(str(source["accepted_at"]))
        delta_seconds = int((source_clock - form25_clock).total_seconds())
        reviewed.append(
            {
                "review_id": "ca-clock100c:" + form25_accession,
                "issuer_cik": chain["issuer_cik"],
                "issuer_name": chain["issuer_name"],
                "form25_accession": form25_accession,
                "form25_accepted_at": chain["form25_accepted_at"],
                "exchange_name": chain["exchange_name"],
                "evidence_accession": evidence_accession,
                "evidence_form_type": source["form_type"],
                "evidence_accepted_at": source["accepted_at"],
                "evidence_url": source["submission_url"],
                "evidence_source_sha256": source["source_sha256"],
                "issuer_minus_exchange_seconds": delta_seconds,
                "source_order": (
                    "issuer_source_before_exchange"
                    if delta_seconds < 0
                    else (
                        "exchange_before_issuer_source"
                        if delta_seconds > 0
                        else "same_second"
                    )
                ),
                "outcome_type": entry["outcome_type"],
                "rights_outcome": entry["rights_outcome"],
                "consideration": {
                    "currency": "USD",
                    "cash_per_share": format(cash, "f"),
                    "contingent": False,
                },
                "claim": claim,
                "review_method": "manual_content_review",
                "observation_clock": "evidence_accepted_at",
                "predictive_for_outcome": False,
                "raw_document_committed": False,
            }
        )
    reviewed.sort(key=lambda item: item["form25_accepted_at"])
    order = Counter(item["source_order"] for item in reviewed)
    near = [
        item
        for item in reviewed
        if abs(int(item["issuer_minus_exchange_seconds"])) <= 36 * 3600
    ]
    near_order = Counter(item["source_order"] for item in near)
    cash_values = [
        decimal.Decimal(item["consideration"]["cash_per_share"])
        for item in reviewed
    ]
    fixture: Dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "fixture_id": "ca-clock100c-reviewed-fixed-cash-seed-v1",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "research_status": "reviewed_seed_not_outcome_balanced",
        "evidence_manifest_id": evidence["manifest_id"],
        "evidence_chains_sha256": evidence["chains_sha256"],
        "review_spec_sha256": sha256(spec),
        "raw_documents_committed": False,
        "reviewed_chains": reviewed,
        "summary": {
            "reviewed_chains": len(reviewed),
            "outcome_type": {"fixed_cash_merger": len(reviewed)},
            "source_order": dict(sorted(order.items())),
            "near_clock_36h": {
                "chains": len(near),
                "source_order": dict(sorted(near_order.items())),
            },
            "cash_per_share_usd": {
                "minimum": format(min(cash_values), "f"),
                "maximum": format(max(cash_values), "f"),
            },
        },
    }
    fixture["reviewed_chains_sha256"] = sha256(reviewed)
    return fixture


def validate_reviewed_fixture(fixture: Mapping[str, object]) -> None:
    if fixture.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("reviewed fixture schema_version mismatch")
    if fixture.get("raw_documents_committed") is not False:
        raise ValueError("raw_documents_committed must be false")
    chains = fixture.get("reviewed_chains")
    if not isinstance(chains, list) or not chains:
        raise ValueError("reviewed_chains must be non-empty")
    if len({item["review_id"] for item in chains}) != len(chains):
        raise ValueError("duplicate review_id")
    if any(item["predictive_for_outcome"] is not False for item in chains):
        raise ValueError("reviewed outcomes cannot be predictive features")
    if any(item["raw_document_committed"] is not False for item in chains):
        raise ValueError("raw reviewed source cannot be committed")
    if fixture.get("reviewed_chains_sha256") != sha256(chains):
        raise ValueError("reviewed chains hash mismatch")
    order = Counter(item["source_order"] for item in chains)
    near = [
        item
        for item in chains
        if abs(int(item["issuer_minus_exchange_seconds"])) <= 36 * 3600
    ]
    near_order = Counter(item["source_order"] for item in near)
    cash_values = [
        decimal.Decimal(item["consideration"]["cash_per_share"])
        for item in chains
    ]
    expected = {
        "reviewed_chains": len(chains),
        "outcome_type": {"fixed_cash_merger": len(chains)},
        "source_order": dict(sorted(order.items())),
        "near_clock_36h": {
            "chains": len(near),
            "source_order": dict(sorted(near_order.items())),
        },
        "cash_per_share_usd": {
            "minimum": format(min(cash_values), "f"),
            "maximum": format(max(cash_values), "f"),
        },
    }
    if fixture.get("summary") != expected:
        raise ValueError("reviewed summary mismatch")


def build_diverse_reviewed_fixture(
    evidence: Mapping[str, object], spec: Mapping[str, object]
) -> Dict[str, object]:
    """Promote manually reviewed non-fixed-cash rights without flattening legs."""
    validate_evidence_manifest(evidence)
    if spec.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("diverse review spec schema_version mismatch")
    if spec.get("review_method") != "manual_content_review":
        raise ValueError("review_method must be manual_content_review")
    allowed = {
        "successor_equity_conversion",
        "fixed_cash_plus_cvr",
        "bankruptcy_zero_confirmed",
        "bankruptcy_unresolved_at_source",
    }
    chain_by_form25 = {
        str(chain["form25_accession"]): chain
        for chain in evidence["chains"]
    }
    reviewed = []
    for entry in spec.get("entries", []):
        form25_accession = str(entry["form25_accession"])
        evidence_accession = str(entry["evidence_accession"])
        chain = chain_by_form25.get(form25_accession)
        if chain is None:
            raise ValueError("diverse review Form 25 absent from evidence")
        source = next(
            (
                item
                for item in chain["review_sources"]
                if item["accession"] == evidence_accession
            ),
            None,
        )
        if source is None:
            raise ValueError(
                "{}: diverse evidence accession not harvested".format(
                    evidence_accession
                )
            )
        outcome_type = str(entry["outcome_type"])
        if outcome_type not in allowed:
            raise ValueError("unsupported diverse outcome_type")
        terms = entry.get("terms")
        if not isinstance(terms, dict):
            raise ValueError("diverse review terms required")
        if outcome_type == "successor_equity_conversion":
            if entry.get("rights_outcome") != "successor_security":
                raise ValueError("successor conversion requires successor_security")
            for key in (
                "successor_issuer",
                "successor_security",
                "old_units",
                "new_units",
            ):
                if not str(terms.get(key, "")).strip():
                    raise ValueError("successor terms missing {}".format(key))
            old_units = decimal.Decimal(str(terms["old_units"]))
            new_units = decimal.Decimal(str(terms["new_units"]))
            if old_units <= 0 or new_units <= 0:
                raise ValueError("successor ratios must be positive")
            if not (
                source["term_flags"].get("stock_or_successor_language")
                or source["term_flags"].get("listing_transfer_language")
                or source["term_flags"].get("holder_conversion_language")
            ):
                raise ValueError("successor source lacks conversion language")
        elif outcome_type == "fixed_cash_plus_cvr":
            if entry.get("rights_outcome") != "cash_plus_contingent_right":
                raise ValueError("CVR review requires cash_plus_contingent_right")
            cash = decimal.Decimal(str(terms.get("cash_per_share")))
            cvr = decimal.Decimal(str(terms.get("cvr_per_share")))
            if cash <= 0 or cvr <= 0 or terms.get("currency") != "USD":
                raise ValueError("invalid cash plus CVR terms")
            if not source["term_flags"].get("holder_conversion_language"):
                raise ValueError("CVR source lacks holder conversion")
        elif outcome_type == "bankruptcy_zero_confirmed":
            if entry.get("rights_outcome") != "zero_recovery_confirmed":
                raise ValueError("zero review requires zero_recovery_confirmed")
            if terms != {"currency": "USD", "terminal_value": "0.00"}:
                raise ValueError("zero review requires explicit USD 0.00")
            if not (
                source["term_flags"].get("bankruptcy_language")
                and source["term_flags"].get("zero_value_language")
            ):
                raise ValueError("zero review lacks bankruptcy/no-recovery evidence")
        elif outcome_type == "bankruptcy_unresolved_at_source":
            if entry.get("rights_outcome") != "unresolved":
                raise ValueError("unresolved review requires unresolved rights")
            if terms != {"terminal_value": None}:
                raise ValueError("unresolved review cannot invent terminal value")
            if not source["term_flags"].get("bankruptcy_language"):
                raise ValueError("unresolved review lacks bankruptcy evidence")
        claim = str(entry.get("claim", "")).strip()
        if not claim or len(claim) > 500:
            raise ValueError("diverse review claim must be 1-500 characters")
        form25_clock = dt.datetime.fromisoformat(
            str(chain["form25_accepted_at"])
        )
        source_clock = dt.datetime.fromisoformat(str(source["accepted_at"]))
        delta = int((source_clock - form25_clock).total_seconds())
        reviewed.append(
            {
                "review_id": "ca-noncash:" + form25_accession,
                "issuer_cik": chain["issuer_cik"],
                "issuer_name": chain["issuer_name"],
                "form25_accession": form25_accession,
                "form25_accepted_at": chain["form25_accepted_at"],
                "exchange_name": chain["exchange_name"],
                "evidence_accession": evidence_accession,
                "evidence_form_type": source["form_type"],
                "evidence_accepted_at": source["accepted_at"],
                "evidence_url": source["submission_url"],
                "evidence_source_sha256": source["source_sha256"],
                "issuer_minus_exchange_seconds": delta,
                "source_order": (
                    "issuer_source_before_exchange"
                    if delta < 0
                    else (
                        "exchange_before_issuer_source"
                        if delta > 0
                        else "same_second"
                    )
                ),
                "outcome_type": outcome_type,
                "rights_outcome": entry["rights_outcome"],
                "terms": terms,
                "claim": claim,
                "review_method": "manual_content_review",
                "observation_clock": "evidence_accepted_at",
                "predictive_for_outcome": False,
                "raw_document_committed": False,
            }
        )
    if not reviewed:
        raise ValueError("diverse review entries must be non-empty")
    if len({item["review_id"] for item in reviewed}) != len(reviewed):
        raise ValueError("duplicate diverse review chain")
    reviewed.sort(key=lambda item: item["form25_accepted_at"])
    fixture: Dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "fixture_id": "ca-noncash-reviewed-seed-v1",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "research_status": "reviewed_diverse_seed_not_population_panel",
        "evidence_manifest_id": evidence["manifest_id"],
        "evidence_chains_sha256": evidence["chains_sha256"],
        "review_spec_sha256": sha256(spec),
        "raw_documents_committed": False,
        "reviewed_chains": reviewed,
        "summary": {
            "reviewed_chains": len(reviewed),
            "outcome_type": dict(
                sorted(Counter(item["outcome_type"] for item in reviewed).items())
            ),
            "source_order": dict(
                sorted(Counter(item["source_order"] for item in reviewed).items())
            ),
        },
    }
    fixture["reviewed_chains_sha256"] = sha256(reviewed)
    return fixture


def validate_diverse_reviewed_fixture(fixture: Mapping[str, object]) -> None:
    if fixture.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("diverse fixture schema_version mismatch")
    if fixture.get("raw_documents_committed") is not False:
        raise ValueError("raw_documents_committed must be false")
    chains = fixture.get("reviewed_chains")
    if not isinstance(chains, list) or not chains:
        raise ValueError("diverse reviewed_chains must be non-empty")
    if any(item["predictive_for_outcome"] is not False for item in chains):
        raise ValueError("diverse outcomes cannot be predictive")
    if fixture.get("reviewed_chains_sha256") != sha256(chains):
        raise ValueError("diverse chains hash mismatch")
    expected = {
        "reviewed_chains": len(chains),
        "outcome_type": dict(
            sorted(Counter(item["outcome_type"] for item in chains).items())
        ),
        "source_order": dict(
            sorted(Counter(item["source_order"] for item in chains).items())
        ),
    }
    if fixture.get("summary") != expected:
        raise ValueError("diverse summary mismatch")


def command_build(args: argparse.Namespace) -> None:
    population = json.loads(
        Path(args.population).read_text(encoding="utf-8")
    )
    manifest = discover_candidates(
        population,
        [Path(value).resolve() for value in args.index],
        before_days=args.before_days,
        after_days=args.after_days,
    )
    validate_manifest(manifest)
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        "wrote {} chains and {} candidate filings to {}".format(
            manifest["summary"]["seed_chains"],
            manifest["summary"]["candidate_filings"],
            output,
        )
    )


def command_summary(args: argparse.Namespace) -> None:
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    validate_manifest(manifest)
    print(json.dumps(manifest["summary"], indent=2, sort_keys=True))


def command_harvest(args: argparse.Namespace) -> None:
    discovery = json.loads(
        Path(args.manifest).read_text(encoding="utf-8")
    )
    evidence = build_evidence_manifest(
        discovery,
        Path(args.cache_dir).resolve(),
        args.user_agent,
        args.min_interval,
        args.per_chain,
    )
    validate_evidence_manifest(evidence)
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(evidence, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        "wrote {} review sources across {} chains to {}".format(
            evidence["summary"]["review_sources"],
            evidence["summary"]["seed_chains"],
            output,
        )
    )


def command_build_reviewed(args: argparse.Namespace) -> None:
    evidence = json.loads(
        Path(args.evidence).read_text(encoding="utf-8")
    )
    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    fixture = build_reviewed_fixture(evidence, spec)
    validate_reviewed_fixture(fixture)
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(fixture, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        "wrote {} reviewed fixed-cash chains to {}".format(
            fixture["summary"]["reviewed_chains"], output
        )
    )


def command_build_diverse_reviewed(args: argparse.Namespace) -> None:
    evidence = json.loads(
        Path(args.evidence).read_text(encoding="utf-8")
    )
    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    fixture = build_diverse_reviewed_fixture(evidence, spec)
    validate_diverse_reviewed_fixture(fixture)
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(fixture, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        "wrote {} reviewed non-cash/diverse chains to {}".format(
            fixture["summary"]["reviewed_chains"], output
        )
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--population", default=str(DEFAULT_POPULATION))
    build.add_argument("--index", action="append", required=True)
    build.add_argument("--before-days", type=int, default=60)
    build.add_argument("--after-days", type=int, default=30)
    build.add_argument("--output", default=str(DEFAULT_OUTPUT))
    build.set_defaults(func=command_build)
    summary = sub.add_parser("summary")
    summary.add_argument("--manifest", default=str(DEFAULT_OUTPUT))
    summary.set_defaults(func=command_summary)
    harvest = sub.add_parser("harvest")
    harvest.add_argument("--manifest", default=str(DEFAULT_OUTPUT))
    harvest.add_argument("--cache-dir", required=True)
    harvest.add_argument("--output", default=str(DEFAULT_EVIDENCE_OUTPUT))
    harvest.add_argument("--per-chain", type=int, default=8)
    harvest.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    harvest.add_argument("--min-interval", type=float, default=0.12)
    harvest.set_defaults(func=command_harvest)
    reviewed = sub.add_parser("build-reviewed")
    reviewed.add_argument("--evidence", default=str(DEFAULT_EVIDENCE_OUTPUT))
    reviewed.add_argument("--spec", default=str(DEFAULT_REVIEW_SPEC))
    reviewed.add_argument("--output", default=str(DEFAULT_REVIEWED_OUTPUT))
    reviewed.set_defaults(func=command_build_reviewed)
    diverse = sub.add_parser("build-diverse-reviewed")
    diverse.add_argument("--evidence", default=str(DEFAULT_EVIDENCE_OUTPUT))
    diverse.add_argument("--spec", default=str(DEFAULT_DIVERSE_REVIEW_SPEC))
    diverse.add_argument(
        "--output", default=str(DEFAULT_DIVERSE_REVIEWED_OUTPUT)
    )
    diverse.set_defaults(func=command_build_diverse_reviewed)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except (OSError, RuntimeError, ValueError) as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Freeze and inspect a point-in-time SEC Form 25-NSE population.

The tool treats SEC quarterly master indexes as the complete sampling frame,
then enriches a deterministic, quarter-stratified sample from submission
texts.  Raw index and filing files belong in a cache outside the repository;
the committed artifact contains only transformed metadata and hashes.

This is research infrastructure, not a trading strategy.  In particular,
Form 25 is a listing/registration event and is not itself an issuer-outcome
label.
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import html
import json
import os
import re
import sqlite3
import statistics
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


_TOOLS = str(Path(__file__).resolve().parent)
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)
import ui_tokens  # noqa: E402  — the one palette; see F231

REPO = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    REPO
    / "docs"
    / "research"
    / "data"
    / "ca_clock100_form25_2023.json"
)
DEFAULT_DB = Path(tempfile.gettempdir()) / "monad-sec-form25-population.sqlite3"
SEC_ARCHIVES = "https://www.sec.gov/Archives/"
DEFAULT_USER_AGENT = (
    "MONAD Quant research contact research@example.com"
)
SCHEMA_VERSION = 1
SEED = "MONAD-CA-CLOCK100-v1"
EASTERN = ZoneInfo("America/New_York")
ACCESSION_RE = re.compile(r"^\d{10}-\d{2}-\d{6}$")
TAG_RE_TEMPLATE = r"<{tag}>\s*(.*?)\s*</{tag}>"
EXCHANGE_NAME_RE = re.compile(
    r"(STOCK\s+(?:EXCHANGE|MARKET)|^NYSE\b|^CBOE\b.*\bEXCHANGE\b)",
    flags=re.IGNORECASE,
)


DB_SCHEMA = """
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = DELETE;
PRAGMA synchronous = FULL;

CREATE TABLE metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
) STRICT;

CREATE TABLE filings (
    accession TEXT PRIMARY KEY,
    issuer_cik TEXT NOT NULL,
    issuer_name TEXT NOT NULL,
    exchange_filer_cik TEXT NOT NULL,
    exchange_name TEXT NOT NULL,
    filed_on TEXT NOT NULL,
    quarter TEXT NOT NULL,
    archive_path TEXT NOT NULL,
    sampled INTEGER NOT NULL CHECK (sampled IN (0, 1)),
    accepted_at TEXT,
    accepted_at_utc TEXT,
    market_window_eastern TEXT,
    security_description TEXT,
    security_family TEXT,
    rule_provision TEXT,
    rule_family TEXT,
    reason_family TEXT,
    reason_exhibit_informative INTEGER
        CHECK (reason_exhibit_informative IS NULL OR
               reason_exhibit_informative IN (0, 1)),
    submission_url TEXT,
    source_sha256 TEXT
) STRICT;

CREATE INDEX filings_exchange_idx ON filings(exchange_name, filed_on);
CREATE INDEX filings_issuer_idx ON filings(issuer_cik, filed_on);
CREATE INDEX filings_sample_idx ON filings(sampled, security_family, rule_family);

CREATE VIRTUAL TABLE filing_search USING fts5(
    accession UNINDEXED,
    issuer_name,
    exchange_name,
    security_description,
    tokenize = 'unicode61'
);

CREATE TRIGGER filings_no_update
BEFORE UPDATE ON filings
BEGIN
    SELECT RAISE(ABORT, 'population projection is append-only');
END;

CREATE TRIGGER filings_no_delete
BEFORE DELETE ON filings
BEGIN
    SELECT RAISE(ABORT, 'population projection cannot delete rows');
END;
"""


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


def is_within(path: Path, parent: Path) -> bool:
    try:
        return os.path.commonpath(
            [str(path.resolve()), str(parent.resolve())]
        ) == str(parent.resolve())
    except ValueError:
        return False


def accession_from_path(path: str) -> str:
    accession = Path(path).name.removesuffix(".txt")
    if not ACCESSION_RE.fullmatch(accession):
        raise ValueError("invalid accession path: {!r}".format(path))
    return accession


def submission_url(entry: Mapping[str, object]) -> str:
    accession = str(entry["accession"])
    cik = str(int(str(entry["exchange_filer_cik"])))
    directory = accession.replace("-", "")
    return "{}edgar/data/{}/{}/{}.txt".format(
        SEC_ARCHIVES, cik, directory, accession
    )


def parse_master_index(path: Path, quarter: str) -> List[Dict[str, object]]:
    """Return unique 25-NSE filings from one official master index.

    The master index normally emits two rows per accession: one under the
    exchange filer and one under the subject issuer.  A small, explicit
    exchange-name lexicon resolves the roles.  The accession prefix is not a
    safe role key: some NYSE-family submissions use a parent CIK accession.
    """
    opener = gzip.open if path.suffix == ".gz" else open
    raw_rows: List[Dict[str, str]] = []
    with opener(path, "rt", encoding="latin-1", errors="replace") as handle:
        for line in handle:
            if "|25-NSE|" not in line:
                continue
            parts = line.rstrip("\r\n").split("|")
            if len(parts) != 5 or parts[2] != "25-NSE":
                continue
            cik, issuer_name, form_type, filed_on, archive_path = parts
            accession = accession_from_path(archive_path)
            raw_rows.append(
                {
                    "cik": cik.zfill(10),
                    "name": issuer_name.strip(),
                    "filed_on": filed_on,
                    "accession": accession,
                    "archive_path": archive_path,
                }
            )
    if not raw_rows:
        raise ValueError("{}: no 25-NSE rows".format(path))
    grouped: Dict[str, List[Dict[str, str]]] = {}
    for row in raw_rows:
        grouped.setdefault(row["accession"], []).append(row)
    rows: List[Dict[str, object]] = []
    for accession, members in sorted(grouped.items()):
        unique_members = {
            (item["cik"], item["name"], item["archive_path"]): item
            for item in members
        }
        filer = [
            item for item in unique_members.values()
            if EXCHANGE_NAME_RE.search(item["name"])
        ]
        subject = [
            item for item in unique_members.values()
            if not EXCHANGE_NAME_RE.search(item["name"])
        ]
        if len(filer) != 1 or len(subject) != 1:
            raise ValueError(
                "{}: expected one filer and one subject index row; got "
                "{} filer and {} subject".format(
                    accession, len(filer), len(subject)
                )
            )
        if filer[0]["filed_on"] != subject[0]["filed_on"]:
            raise ValueError("{}: inconsistent filed dates".format(accession))
        rows.append(
            {
                "issuer_cik": subject[0]["cik"],
                "issuer_name_index": subject[0]["name"],
                "exchange_filer_cik": filer[0]["cik"],
                "exchange_filer_name_index": filer[0]["name"],
                "form_type": "25-NSE",
                "filed_on": subject[0]["filed_on"],
                "quarter": quarter,
                "accession": accession,
                "archive_path": filer[0]["archive_path"],
                "master_index_rows_collapsed": len(members),
                "identity_resolution": "exchange_name_lexicon_v1",
            }
        )
    return rows


def deterministic_sample(
    rows: Sequence[Mapping[str, object]],
    per_quarter: int,
    seed: str = SEED,
) -> List[Dict[str, object]]:
    """Select an exactly reproducible sample without depending on input order."""
    grouped: Dict[str, List[Mapping[str, object]]] = {}
    for row in rows:
        grouped.setdefault(str(row["quarter"]), []).append(row)
    selected: List[Dict[str, object]] = []
    for quarter in sorted(grouped):
        ranked = sorted(
            grouped[quarter],
            key=lambda item: (
                hashlib.sha256(
                    "{}|{}".format(seed, item["accession"]).encode("utf-8")
                ).hexdigest(),
                str(item["accession"]),
            ),
        )
        if len(ranked) < per_quarter:
            raise ValueError(
                "{} has {} rows, fewer than requested {}".format(
                    quarter, len(ranked), per_quarter
                )
            )
        for rank, row in enumerate(ranked[:per_quarter], 1):
            item = dict(row)
            item["sample_rank_in_quarter"] = rank
            item["sample_score_sha256"] = hashlib.sha256(
                "{}|{}".format(seed, item["accession"]).encode("utf-8")
            ).hexdigest()
            selected.append(item)
    return selected


def extract_tag(text: str, tag: str) -> Optional[str]:
    match = re.search(
        TAG_RE_TEMPLATE.format(tag=re.escape(tag)),
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return html.unescape(match.group(1).strip()) if match else None


def document_sections(text: str) -> Iterable[Tuple[str, str, str]]:
    for match in re.finditer(
        r"<DOCUMENT>(.*?)</DOCUMENT>", text, flags=re.IGNORECASE | re.DOTALL
    ):
        body = match.group(1)
        doc_type = re.search(r"<TYPE>\s*([^\r\n<]+)", body, re.IGNORECASE)
        filename = re.search(
            r"<FILENAME>\s*([^\r\n<]+)", body, re.IGNORECASE
        )
        text_match = re.search(
            r"<TEXT>(.*?)</TEXT>", body, re.IGNORECASE | re.DOTALL
        )
        yield (
            doc_type.group(1).strip() if doc_type else "",
            filename.group(1).strip() if filename else "",
            text_match.group(1).strip() if text_match else "",
        )


def plain_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def classify_security(description: str) -> str:
    value = description.lower()
    has_discrete_right = bool(
        re.fullmatch(r"\s*rights?\s*", value)
        or re.search(r"(?:,|;|\band\b)\s+rights?\b", value)
    )
    if (
        re.search(r"\bwarrants?\b", value)
        or re.search(r"\bunits?\b", value)
        or has_discrete_right
    ):
        return "warrant_right_or_unit"
    if any(
        token in value
        for token in ("note", "bond", "debenture", "debt", "certificate")
    ):
        return "debt_or_note"
    if "preferred" in value:
        return "preferred_equity"
    if any(token in value for token in ("common", "ordinary", "share")):
        return "common_equity"
    return "other_or_unknown"


def classify_rule(rule: str) -> str:
    compact = re.sub(r"\s+", "", rule.lower())
    for suffix in ("(a)(1)", "(a)(2)", "(a)(3)", "(b)"):
        if suffix in compact:
            return suffix.strip("()").replace(")(", "_")
    return "other_or_unknown"


def classify_reason(reason: str) -> str:
    value = reason.lower()
    if any(
        token in value
        for token in (
            "merger",
            "acquisition",
            "business combination",
            "scheme of arrangement",
        )
    ):
        return "merger_or_acquisition"
    if any(
        token in value
        for token in (
            "bankrupt",
            "chapter 11",
            "liquidat",
            "financially",
            "public interest",
            "protection of investors",
        )
    ):
        return "distress_or_compliance"
    if any(
        token in value
        for token in ("redeemed", "maturity", "retirement", "paid at maturity")
    ):
        return "redemption_or_maturity"
    if any(token in value for token in ("transfer", "listed on", "new exchange")):
        return "listing_transfer"
    return "other_or_unclassified"


def market_window(local_time: dt.time) -> str:
    value = (local_time.hour, local_time.minute, local_time.second)
    if value < (9, 30, 0):
        return "pre_open"
    if value < (16, 0, 0):
        return "regular_session"
    return "post_close"


def parse_submission(
    text: str, expected: Mapping[str, object]
) -> Dict[str, object]:
    accepted_match = re.search(r"<ACCEPTANCE-DATETIME>(\d{14})", text)
    if not accepted_match:
        raise ValueError("{}: missing acceptance datetime".format(
            expected["accession"]
        ))
    naive = dt.datetime.strptime(accepted_match.group(1), "%Y%m%d%H%M%S")
    accepted = naive.replace(tzinfo=EASTERN)

    primary = ""
    reason = ""
    reason_filename = ""
    for doc_type, filename, body in document_sections(text):
        if doc_type.upper() == "25-NSE":
            primary = body
        elif doc_type.upper() == "EX-99.25":
            candidate = plain_text(body)
            if len(candidate) > len(reason):
                reason = candidate
                reason_filename = filename
    if not primary:
        raise ValueError("{}: missing 25-NSE primary document".format(
            expected["accession"]
        ))

    issuer_cik = (extract_tag(primary, "cik") or "").zfill(10)
    issuer_block = re.search(
        r"<issuer>(.*?)</issuer>", primary, re.IGNORECASE | re.DOTALL
    )
    exchange_block = re.search(
        r"<exchange>(.*?)</exchange>", primary, re.IGNORECASE | re.DOTALL
    )
    if issuer_block:
        issuer_cik = (extract_tag(issuer_block.group(1), "cik") or "").zfill(10)
        issuer_name = extract_tag(issuer_block.group(1), "entityName") or ""
    else:
        issuer_name = ""
    if exchange_block:
        exchange_cik = (
            extract_tag(exchange_block.group(1), "cik") or ""
        ).zfill(10)
        exchange_name = (
            extract_tag(exchange_block.group(1), "entityName") or ""
        )
    else:
        exchange_cik = ""
        exchange_name = ""

    description = extract_tag(primary, "descriptionClassSecurity") or ""
    rule = extract_tag(primary, "ruleProvision") or ""
    signature_date = extract_tag(primary, "signatureDate")
    minimal_reason = reason.lower().strip(" .:-") in {
        "",
        "form 25",
        "form25",
        "form 25 notification",
    }
    expected_cik = str(expected["issuer_cik"]).zfill(10)
    if issuer_cik != expected_cik:
        raise ValueError(
            "{}: subject CIK mismatch {} != {}".format(
                expected["accession"], issuer_cik, expected_cik
            )
        )

    return {
        "accepted_at": accepted.isoformat(),
        "accepted_at_utc": accepted.astimezone(dt.timezone.utc).isoformat(),
        "decision_clock": "accepted_at",
        "observation_time_quality": "exact_sec_acceptance_second",
        "market_window_eastern": market_window(accepted.time()),
        "issuer_cik": issuer_cik,
        "issuer_name": issuer_name,
        "exchange_cik": exchange_cik,
        "exchange_name": exchange_name,
        "security_description": description,
        "security_family": classify_security(description),
        "rule_provision": rule,
        "rule_family": classify_rule(rule),
        "signature_date": signature_date,
        "reason_exhibit_present": bool(reason),
        "reason_exhibit_informative": bool(reason) and not minimal_reason,
        "reason_exhibit_filename": reason_filename,
        "reason_family": (
            classify_reason(reason)
            if reason and not minimal_reason
            else "not_informative"
        ),
        "reason_text_sha256": hashlib.sha256(
            reason.encode("utf-8")
        ).hexdigest(),
        "reason_text_length": len(reason),
        "raw_document_committed": False,
    }


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
            request = Request(
                url,
                headers={
                    "User-Agent": user_agent,
                },
            )
            with urlopen(request, timeout=30) as response:
                payload = response.read()
            cache_path.write_bytes(payload)
            time.sleep(min_interval)
            return payload
        except (HTTPError, URLError) as exc:
            if attempt + 1 == retries:
                raise RuntimeError("failed to fetch {}: {}".format(url, exc))
            time.sleep(max(min_interval, 2 ** attempt))
    raise AssertionError("unreachable")


def summarize_records(
    census: Sequence[Mapping[str, object]],
    sample: Sequence[Mapping[str, object]],
) -> Dict[str, object]:
    def counts(key: str) -> Dict[str, int]:
        return dict(
            sorted(Counter(str(item[key]) for item in sample).items())
        )

    issuer_counts = Counter(str(item["issuer_cik"]) for item in census)
    issuer_names = {
        str(item["issuer_cik"]): str(item["issuer_name_index"])
        for item in census
    }
    signature_lags = []
    for item in sample:
        signature = item.get("signature_date")
        if signature:
            accepted_date = dt.datetime.fromisoformat(
                str(item["accepted_at"])
            ).date()
            signature_lags.append(
                (accepted_date - dt.date.fromisoformat(str(signature))).days
            )
    timestamps = Counter(str(item["accepted_at"]) for item in sample)
    minute_counts = Counter(
        dt.datetime.fromisoformat(str(item["accepted_at"])).strftime("%H:%M")
        for item in sample
    )

    def cross_tab(row_key: str, column_key: str) -> Dict[str, Dict[str, int]]:
        result: Dict[str, Counter] = {}
        for item in sample:
            result.setdefault(str(item[row_key]), Counter())[
                str(item[column_key])
            ] += 1
        return {
            key: dict(sorted(value.items()))
            for key, value in sorted(result.items())
        }

    repeated = [
        {
            "issuer_cik": cik,
            "issuer_name_index": issuer_names[cik],
            "filings": count,
        }
        for cik, count in issuer_counts.items()
        if count > 1
    ]
    repeated.sort(
        key=lambda item: (
            -int(item["filings"]),
            str(item["issuer_name_index"]),
            str(item["issuer_cik"]),
        )
    )
    signature_summary = {
        "available": len(signature_lags),
        "missing": len(sample) - len(signature_lags),
        "minimum": min(signature_lags) if signature_lags else None,
        "median": statistics.median(signature_lags)
        if signature_lags
        else None,
        "maximum": max(signature_lags) if signature_lags else None,
        "negative_lag_records": sum(value < 0 for value in signature_lags),
    }
    informative_by_exchange = {}
    for exchange in sorted({str(item["exchange_name"]) for item in sample}):
        members = [
            item for item in sample if str(item["exchange_name"]) == exchange
        ]
        informative_by_exchange[exchange] = {
            "informative": sum(
                bool(item["reason_exhibit_informative"]) for item in members
            ),
            "total": len(members),
        }
    return {
        "raw_master_index_rows": sum(
            int(item.get("master_index_rows_collapsed", 2))
            for item in census
        ),
        "census_rows": len(census),
        "sample_rows": len(sample),
        "unique_census_issuers": len(
            {str(item["issuer_cik"]) for item in census}
        ),
        "unique_sample_issuers": len(
            {str(item["issuer_cik"]) for item in sample}
        ),
        "census_by_quarter": dict(
            sorted(Counter(str(item["quarter"]) for item in census).items())
        ),
        "census_by_exchange": dict(
            sorted(
                Counter(
                    str(item["exchange_filer_name_index"]) for item in census
                ).items()
            )
        ),
        "census_issuers_with_multiple_filings": sum(
            count > 1 for count in issuer_counts.values()
        ),
        "top_repeat_issuers": repeated[:15],
        "sample_by_quarter": counts("quarter"),
        "market_window_eastern": counts("market_window_eastern"),
        "security_family": counts("security_family"),
        "rule_family": counts("rule_family"),
        "reason_family": counts("reason_family"),
        "exchange_name": counts("exchange_name"),
        "informative_reason_exhibits": sum(
            bool(item["reason_exhibit_informative"]) for item in sample
        ),
        "informative_reason_by_exchange": informative_by_exchange,
        "exchange_by_market_window": cross_tab(
            "exchange_name", "market_window_eastern"
        ),
        "rule_by_reason_family": cross_tab("rule_family", "reason_family"),
        "signature_to_acceptance_calendar_days": signature_summary,
        "filed_date_acceptance_date_mismatches": sum(
            str(item["filed_on"])
            != dt.datetime.fromisoformat(str(item["accepted_at"]))
            .date()
            .isoformat()
            for item in sample
        ),
        "duplicate_exact_acceptance_timestamps": {
            "clusters": sum(count > 1 for count in timestamps.values()),
            "records_in_clusters": sum(
                count for count in timestamps.values() if count > 1
            ),
            "maximum_cluster_size": max(timestamps.values())
            if timestamps
            else 0,
        },
        "top_acceptance_minutes_eastern": [
            {"minute": minute, "filings": count}
            for minute, count in sorted(
                minute_counts.items(), key=lambda item: (-item[1], item[0])
            )[:10]
        ],
    }


def build_artifact(
    index_paths: Sequence[Path],
    quarters: Sequence[str],
    cache_dir: Path,
    per_quarter: int,
    user_agent: str,
    min_interval: float,
) -> Dict[str, object]:
    if len(index_paths) != len(quarters):
        raise ValueError("index paths and quarters must have equal length")
    census: List[Dict[str, object]] = []
    sources = []
    for path, quarter in zip(index_paths, quarters):
        rows = parse_master_index(path, quarter)
        census.extend(rows)
        sources.append(
            {
                "quarter": quarter,
                "index_url": (
                    "https://www.sec.gov/Archives/edgar/full-index/"
                    "{}/QTR{}/master.gz".format(quarter[:4], quarter[-1])
                ),
                "local_file_sha256": file_sha256(path),
                "rows_25_nse": len(rows),
                "raw_index_committed": False,
            }
        )
    census.sort(key=lambda item: (str(item["filed_on"]), str(item["accession"])))
    selected = deterministic_sample(census, per_quarter)
    enriched: List[Dict[str, object]] = []
    for position, row in enumerate(selected, 1):
        url = submission_url(row)
        cache_path = cache_dir / (str(row["accession"]) + ".txt")
        payload = fetch_with_cache(
            url, cache_path, user_agent, min_interval=min_interval
        )
        text = payload.decode("latin-1", errors="replace")
        parsed = parse_submission(text, row)
        item = dict(row)
        item.update(parsed)
        item["submission_url"] = url
        item["source_sha256"] = hashlib.sha256(payload).hexdigest()
        item["sample_position"] = position
        enriched.append(item)

    enriched.sort(
        key=lambda item: (str(item["accepted_at"]), str(item["accession"]))
    )
    census_manifest = [
        {
            "issuer_cik": item["issuer_cik"],
            "issuer_name_index": item["issuer_name_index"],
            "exchange_filer_cik": item["exchange_filer_cik"],
            "exchange_filer_name_index": item["exchange_filer_name_index"],
            "filed_on": item["filed_on"],
            "quarter": item["quarter"],
            "accession": item["accession"],
            "archive_path": item["archive_path"],
        }
        for item in census
    ]
    artifact: Dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "fixture_id": "ca-clock100-form25-nse-2023-v1",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "research_status": "descriptive_sampling_frame_not_alpha_evidence",
        "decision_clock": "accepted_at",
        "sampling": {
            "frame": "all SEC master-index 25-NSE rows for 2023",
            "method": "lowest SHA-256 ranks within each quarter",
            "seed": SEED,
            "per_quarter": per_quarter,
            "replacement": False,
        },
        "source_indexes": sources,
        "raw_documents_committed": False,
        "census_manifest": census_manifest,
        "sample": enriched,
    }
    artifact["summary"] = summarize_records(census_manifest, enriched)
    artifact["census_manifest_sha256"] = sha256(census_manifest)
    artifact["sample_sha256"] = sha256(enriched)
    return artifact


def validate_artifact(artifact: Mapping[str, object]) -> None:
    if artifact.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported schema_version")
    if artifact.get("raw_documents_committed") is not False:
        raise ValueError("raw_documents_committed must be false")
    census = artifact.get("census_manifest")
    sample = artifact.get("sample")
    if not isinstance(census, list) or not census:
        raise ValueError("census_manifest must be non-empty")
    if not isinstance(sample, list) or not sample:
        raise ValueError("sample must be non-empty")
    if len({item["accession"] for item in census}) != len(census):
        raise ValueError("duplicate census accession")
    if len({item["accession"] for item in sample}) != len(sample):
        raise ValueError("duplicate sample accession")
    census_accessions = {item["accession"] for item in census}
    for item in sample:
        if item["accession"] not in census_accessions:
            raise ValueError("sample accession absent from census")
        if item["decision_clock"] != "accepted_at":
            raise ValueError("sample decision_clock must be accepted_at")
        if item["raw_document_committed"] is not False:
            raise ValueError("raw sample document cannot be committed")
        accepted = dt.datetime.fromisoformat(str(item["accepted_at"]))
        if accepted.tzinfo is None:
            raise ValueError("accepted_at requires a timezone offset")
    if artifact.get("census_manifest_sha256") != sha256(census):
        raise ValueError("census manifest hash mismatch")
    if artifact.get("sample_sha256") != sha256(sample):
        raise ValueError("sample hash mismatch")
    expected = summarize_records(census, sample)
    if artifact.get("summary") != expected:
        raise ValueError("summary mismatch")


def build_database(artifact: Mapping[str, object], output: Path) -> None:
    """Atomically build a disposable SQLite projection outside the repository."""
    validate_artifact(artifact)
    output = output.resolve()
    if is_within(output, REPO):
        raise ValueError("SQLite projections must remain outside the repository")
    output.parent.mkdir(parents=True, exist_ok=True)
    temp_handle = tempfile.NamedTemporaryFile(
        prefix="." + output.name + ".",
        suffix=".tmp",
        dir=str(output.parent),
        delete=False,
    )
    temp_handle.close()
    temporary = Path(temp_handle.name)
    sample_by_accession = {
        str(item["accession"]): item for item in artifact["sample"]
    }
    try:
        connection = sqlite3.connect(str(temporary))
        try:
            connection.executescript(DB_SCHEMA)
            metadata = {
                "schema_version": str(artifact["schema_version"]),
                "fixture_id": str(artifact["fixture_id"]),
                "generated_at": str(artifact["generated_at"]),
                "census_manifest_sha256": str(
                    artifact["census_manifest_sha256"]
                ),
                "sample_sha256": str(artifact["sample_sha256"]),
                "summary_json": json.dumps(
                    artifact["summary"], separators=(",", ":")
                ),
            }
            connection.executemany(
                "INSERT INTO metadata(key, value) VALUES (?, ?)",
                sorted(metadata.items()),
            )
            for census in artifact["census_manifest"]:
                sample = sample_by_accession.get(str(census["accession"]))
                row = {
                    "accession": census["accession"],
                    "issuer_cik": census["issuer_cik"],
                    "issuer_name": census["issuer_name_index"],
                    "exchange_filer_cik": census["exchange_filer_cik"],
                    "exchange_name": census["exchange_filer_name_index"],
                    "filed_on": census["filed_on"],
                    "quarter": census["quarter"],
                    "archive_path": census["archive_path"],
                    "sampled": int(sample is not None),
                    "accepted_at": sample.get("accepted_at") if sample else None,
                    "accepted_at_utc": (
                        sample.get("accepted_at_utc") if sample else None
                    ),
                    "market_window_eastern": (
                        sample.get("market_window_eastern")
                        if sample
                        else None
                    ),
                    "security_description": (
                        sample.get("security_description") if sample else None
                    ),
                    "security_family": (
                        sample.get("security_family") if sample else None
                    ),
                    "rule_provision": (
                        sample.get("rule_provision") if sample else None
                    ),
                    "rule_family": (
                        sample.get("rule_family") if sample else None
                    ),
                    "reason_family": (
                        sample.get("reason_family") if sample else None
                    ),
                    "reason_exhibit_informative": (
                        int(bool(sample["reason_exhibit_informative"]))
                        if sample
                        else None
                    ),
                    "submission_url": (
                        sample.get("submission_url") if sample else None
                    ),
                    "source_sha256": (
                        sample.get("source_sha256") if sample else None
                    ),
                }
                columns = list(row)
                connection.execute(
                    "INSERT INTO filings ({}) VALUES ({})".format(
                        ",".join(columns),
                        ",".join("?" for _ in columns),
                    ),
                    [row[column] for column in columns],
                )
                connection.execute(
                    "INSERT INTO filing_search("
                    "accession, issuer_name, exchange_name, "
                    "security_description) VALUES (?, ?, ?, ?)",
                    (
                        row["accession"],
                        row["issuer_name"],
                        row["exchange_name"],
                        row["security_description"] or "",
                    ),
                )
            connection.commit()
            integrity = connection.execute(
                "PRAGMA integrity_check"
            ).fetchone()[0]
            if integrity != "ok":
                raise sqlite3.DatabaseError(
                    "integrity_check failed: {}".format(integrity)
                )
        finally:
            connection.close()
        os.replace(str(temporary), str(output))
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _readonly_connection(path: Path) -> sqlite3.Connection:
    resolved = path.resolve()
    if not resolved.exists():
        raise OSError("database does not exist: {}".format(resolved))
    connection = sqlite3.connect(
        "file:{}?mode=ro&immutable=1".format(resolved),
        uri=True,
    )
    connection.row_factory = sqlite3.Row
    return connection


def population_payload(
    database: Path,
    filters: Optional[Mapping[str, str]] = None,
    limit: int = 100,
) -> Dict[str, object]:
    """Read a filtered payload without granting a write-capable connection."""
    selected = dict(filters or {})
    limit = max(1, min(int(limit), 200))
    clauses = []
    values: List[object] = []
    exact_fields = {
        "quarter": "quarter",
        "exchange": "exchange_name",
        "window": "market_window_eastern",
        "security": "security_family",
        "rule": "rule_family",
        "reason": "reason_family",
    }
    for key, column in exact_fields.items():
        value = selected.get(key)
        if value:
            clauses.append("{} = ?".format(column))
            values.append(value)
    sampled = selected.get("sampled")
    if sampled in {"yes", "no"}:
        clauses.append("sampled = ?")
        values.append(1 if sampled == "yes" else 0)
    informative = selected.get("informative")
    if informative in {"yes", "no"}:
        clauses.append("reason_exhibit_informative = ?")
        values.append(1 if informative == "yes" else 0)
    elif informative == "unknown":
        clauses.append("reason_exhibit_informative IS NULL")
    query = selected.get("q", "").strip()
    if query:
        like = "%" + query.lower() + "%"
        clauses.append(
            "(lower(accession) LIKE ? OR lower(issuer_name) LIKE ? OR "
            "lower(exchange_name) LIKE ? OR "
            "lower(coalesce(security_description, '')) LIKE ?)"
        )
        values.extend([like, like, like, like])
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    connection = _readonly_connection(database)
    try:
        metadata = {
            row["key"]: row["value"]
            for row in connection.execute("SELECT key, value FROM metadata")
        }
        total = connection.execute(
            "SELECT count(*) FROM filings" + where, values
        ).fetchone()[0]
        rows = [
            dict(row)
            for row in connection.execute(
                "SELECT * FROM filings"
                + where
                + " ORDER BY filed_on DESC, accession DESC LIMIT ?",
                values + [limit],
            )
        ]
        option_columns = {
            "quarter": "quarter",
            "exchange": "exchange_name",
            "window": "market_window_eastern",
            "security": "security_family",
            "rule": "rule_family",
            "reason": "reason_family",
        }
        options = {}
        for key, column in option_columns.items():
            options[key] = [
                row[0]
                for row in connection.execute(
                    "SELECT DISTINCT {} FROM filings WHERE {} IS NOT NULL "
                    "ORDER BY {}".format(column, column, column)
                )
            ]
        return {
            "fixture_id": metadata["fixture_id"],
            "summary": json.loads(metadata["summary_json"]),
            "filters": selected,
            "options": options,
            "total_matches": total,
            "limit": limit,
            "rows": rows,
            "read_only": True,
        }
    finally:
        connection.close()


def render_population_html(payload: Mapping[str, object]) -> str:
    filters = payload["filters"]
    options = payload["options"]

    def esc(value: object) -> str:
        return html.escape(str(value), quote=True)

    def select(name: str, label: str) -> str:
        current = str(filters.get(name, ""))
        choices = ['<option value="">all</option>']
        for value in options[name]:
            selected = " selected" if str(value) == current else ""
            choices.append(
                '<option value="{}"{}>{}</option>'.format(
                    esc(value), selected, esc(value)
                )
            )
        return (
            '<label>{}<select name="{}">{}</select></label>'.format(
                esc(label), esc(name), "".join(choices)
            )
        )

    rows = []
    for item in payload["rows"]:
        accession = esc(item["accession"])
        source = (
            '<a href="{}" rel="noreferrer">{}</a>'.format(
                esc(item["submission_url"]), accession
            )
            if item["submission_url"]
            else accession
        )
        rows.append(
            "<tr>"
            "<td>{}</td><td>{}</td><td>{}</td><td>{}</td>"
            "<td>{}</td><td>{}</td><td>{}</td><td>{}</td>"
            "<td>{}</td></tr>".format(
                esc(item["filed_on"]),
                source,
                esc(item["issuer_name"]),
                esc(item["exchange_name"]),
                "yes" if item["sampled"] else "no",
                esc(item["market_window_eastern"] or "—"),
                esc(item["security_family"] or "—"),
                esc(item["rule_family"] or "—"),
                esc(item["reason_family"] or "—"),
            )
        )
    summary = payload["summary"]
    return """{head}
<body>
<div class="masthead"><div class="inner"><h1>SEC Form 25-NSE population</h1>
<div class="muted">Read-only SQLite projection · transformed official metadata ·
not a return signal</div><a href="/">← context map</a></div></div>
<div class="wrap"><div class="cards">
<div class="card"><b>{census}</b><span class="muted">unique accessions</span></div>
<div class="card"><b>{issuers}</b><span class="muted">subject issuers</span></div>
<div class="card"><b>{sample}</b><span class="muted">content-enriched sample</span></div>
<div class="card"><b>{matches}</b><span class="muted">current matches</span></div>
</div>
<form method="get">
<label>search<input name="q" value="{q}" placeholder="issuer, accession, security"></label>
{quarter}{exchange}{window}{security}{rule}{reason}
<label>sampled<select name="sampled">
<option value="">all</option><option value="yes"{sample_yes}>yes</option>
<option value="no"{sample_no}>no</option></select></label>
<label>informative reason<select name="informative">
<option value="">all</option><option value="yes"{info_yes}>yes</option>
<option value="no"{info_no}>no</option>
<option value="unknown"{info_unknown}>unknown</option></select></label>
<button>filter</button><a href="/form25-population">reset</a></form>
<p class="muted">Showing at most {limit} rows. Detailed timing/rule/reason fields
exist only for the frozen 100-filing sample.</p>
<div class="table"><table><thead><tr><th>filed</th><th>accession</th>
<th>subject issuer</th><th>exchange</th><th>sampled</th><th>window</th>
<th>security</th><th>rule</th><th>reason</th></tr></thead>
<tbody>{rows}</tbody></table></div></div></body></html>""".format(
        head=ui_tokens.document_head(
            "SEC Form 25 population", "1500px",
            # This page is a wide filterable grid, the only surface with a sticky
            # header row; `th` needs a solid ground to scroll under, which the shared
            # sheet already gives it, plus the stickiness itself.
            extra_css="th{position:sticky;top:0;z-index:1}"
                      "td,th{white-space:nowrap}"
                      ".table{max-height:70vh;overflow:auto;border:1px solid var(--rule);"
                      "border-radius:9px;background:var(--surface);margin-top:14px}"),
        census=esc(summary["census_rows"]),
        issuers=esc(summary["unique_census_issuers"]),
        sample=esc(summary["sample_rows"]),
        matches=esc(payload["total_matches"]),
        q=esc(filters.get("q", "")),
        quarter=select("quarter", "quarter"),
        exchange=select("exchange", "exchange"),
        window=select("window", "market window"),
        security=select("security", "security"),
        rule=select("rule", "rule"),
        reason=select("reason", "reason"),
        sample_yes=" selected" if filters.get("sampled") == "yes" else "",
        sample_no=" selected" if filters.get("sampled") == "no" else "",
        info_yes=" selected" if filters.get("informative") == "yes" else "",
        info_no=" selected" if filters.get("informative") == "no" else "",
        info_unknown=(
            " selected" if filters.get("informative") == "unknown" else ""
        ),
        limit=esc(payload["limit"]),
        rows="".join(rows),
    )


def command_build(args: argparse.Namespace) -> None:
    paths = [Path(value).resolve() for value in args.index]
    artifact = build_artifact(
        index_paths=paths,
        quarters=args.quarter,
        cache_dir=Path(args.cache_dir).resolve(),
        per_quarter=args.per_quarter,
        user_agent=args.user_agent,
        min_interval=args.min_interval,
    )
    validate_artifact(artifact)
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(artifact, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        "wrote {} census rows and {} sample rows to {}".format(
            artifact["summary"]["census_rows"],
            artifact["summary"]["sample_rows"],
            output,
        )
    )


def command_summary(args: argparse.Namespace) -> None:
    artifact = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
    validate_artifact(artifact)
    print(json.dumps(artifact["summary"], indent=2, sort_keys=True))


def command_build_db(args: argparse.Namespace) -> None:
    artifact = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
    output = Path(args.database).resolve()
    build_database(artifact, output)
    print("wrote read-only population projection to {}".format(output))


def command_query(args: argparse.Namespace) -> None:
    filters = {
        key: value
        for key, value in {
            "q": args.q,
            "quarter": args.quarter,
            "exchange": args.exchange,
            "window": args.window,
            "security": args.security,
            "rule": args.rule,
            "reason": args.reason,
            "sampled": args.sampled,
            "informative": args.informative,
        }.items()
        if value
    }
    payload = population_payload(Path(args.database), filters, args.limit)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def _add_query_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--database", default=str(DEFAULT_DB))
    parser.add_argument("--q")
    parser.add_argument("--quarter")
    parser.add_argument("--exchange")
    parser.add_argument("--window")
    parser.add_argument("--security")
    parser.add_argument("--rule")
    parser.add_argument("--reason")
    parser.add_argument("--sampled", choices=("yes", "no"))
    parser.add_argument("--informative", choices=("yes", "no", "unknown"))
    parser.add_argument("--limit", type=int, default=100)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="build a transformed population fixture")
    build.add_argument("--index", action="append", required=True)
    build.add_argument("--quarter", action="append", required=True)
    build.add_argument("--cache-dir", required=True)
    build.add_argument("--output", default=str(DEFAULT_OUTPUT))
    build.add_argument("--per-quarter", type=int, default=25)
    build.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    build.add_argument("--min-interval", type=float, default=0.12)
    build.set_defaults(func=command_build)

    summary = sub.add_parser("summary", help="validate and summarize a fixture")
    summary.add_argument("--fixture", default=str(DEFAULT_OUTPUT))
    summary.set_defaults(func=command_summary)

    build_db = sub.add_parser(
        "build-db", help="build a disposable SQLite read projection"
    )
    build_db.add_argument("--fixture", default=str(DEFAULT_OUTPUT))
    build_db.add_argument("--database", default=str(DEFAULT_DB))
    build_db.set_defaults(func=command_build_db)

    query = sub.add_parser("query", help="query the SQLite projection")
    _add_query_arguments(query)
    query.set_defaults(func=command_query)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except (OSError, RuntimeError, ValueError) as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

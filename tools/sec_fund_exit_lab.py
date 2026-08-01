#!/usr/bin/env python3
"""Promote the five structurally missing CA-CLOCK100B fund exits.

Fund exits do not share the corporate 8-K/6-K evidence graph.  This tool joins
the frozen Form 25 population and missing-candidate manifest to manually
reviewed fund and exchange submissions, validates exact source bytes and
acceptance clocks, and emits rights-aware labels.

The output is outcome evidence, never a predictive feature table.  In
particular, a scheduled cash-at-NAV right is not promoted to a confirmed cash
payment, and a liquidating-trust unit is not flattened into its initial NAV.
"""
from __future__ import annotations

import argparse
import datetime as dt
import decimal
import hashlib
import html
import json
import re
from collections import Counter
from pathlib import Path
from typing import Dict, Mapping, Optional, Sequence


REPO = Path(__file__).resolve().parents[1]
DEFAULT_POPULATION = (
    REPO / "docs" / "research" / "data" / "ca_clock100_form25_2023.json"
)
DEFAULT_CANDIDATES = (
    REPO / "docs" / "research" / "data" / "ca_clock100b_candidate_manifest.json"
)
DEFAULT_SPEC = (
    REPO / "docs" / "research" / "data" / "ca_fund_review_spec.json"
)
DEFAULT_OUTPUT = (
    REPO / "docs" / "research" / "data" / "ca_fund_reviewed_seed.json"
)
DEFAULT_FORM25_CACHE = Path("/private/tmp/monad-sec-form25-2023")
DEFAULT_FUND_CACHE = Path("/private/tmp/monad-sec-fund-exit-2023")
SCHEMA_VERSION = 1
EXPECTED_OUTCOMES = {
    "nav_ratio_successor_fund",
    "completed_cash_plus_liquidating_trust",
    "scheduled_cash_at_nav_liquidation",
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
    if not accession_match:
        accession_match = re.search(
            r"<SEC-DOCUMENT>(\d{10}-\d{2}-\d{6})\.txt", raw
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
    except ImportError:  # pragma: no cover - supported runtime is Python 3.9+
        accepted = naive
    return {
        "accession": expected_accession,
        "accepted_at": accepted.isoformat(),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def load_json(path: Path) -> Mapping[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("{} must contain a JSON object".format(path))
    return value


def parse_decimal(value: object, label: str) -> decimal.Decimal:
    try:
        parsed = decimal.Decimal(str(value))
    except decimal.InvalidOperation as exc:
        raise ValueError("{} must be numeric".format(label)) from exc
    if not parsed.is_finite():
        raise ValueError("{} must be finite".format(label))
    return parsed


def validate_case_semantics(case: Mapping[str, object]) -> None:
    outcome = case.get("outcome_type")
    if outcome not in EXPECTED_OUTCOMES:
        raise ValueError("unexpected fund outcome_type: {!r}".format(outcome))
    rights = case.get("rights")
    if not isinstance(rights, dict):
        raise ValueError("{}: rights must be an object".format(
            case.get("form25_accession")
        ))
    if outcome == "nav_ratio_successor_fund":
        if parse_decimal(rights.get("old_units"), "old_units") <= 0:
            raise ValueError("successor old_units must be positive")
        if parse_decimal(
            rights.get("successor_units"), "successor_units"
        ) <= 0:
            raise ValueError("successor_units must be positive")
        if not rights.get("successor_name") or not rights.get(
            "successor_ticker"
        ):
            raise ValueError("successor identity is required")
        if rights.get("cash_amount_usd") is not None:
            raise ValueError("successor ratio cannot invent cash value")
    elif outcome == "completed_cash_plus_liquidating_trust":
        cash = parse_decimal(
            rights.get("cash_amount_usd"), "cash_amount_usd"
        )
        trust_units = parse_decimal(
            rights.get("liquidating_trust_units"),
            "liquidating_trust_units",
        )
        trust_nav = parse_decimal(
            rights.get("trust_initial_nav_usd"), "trust_initial_nav_usd"
        )
        combined = parse_decimal(
            rights.get("combined_value_at_close_usd"),
            "combined_value_at_close_usd",
        )
        if min(cash, trust_units, trust_nav, combined) <= 0:
            raise ValueError("liquidation legs must be positive")
        if cash + trust_units * trust_nav != combined:
            raise ValueError("cash and trust legs do not reconcile")
        if rights.get("trust_final_cash_timing") != "unresolved":
            raise ValueError("liquidating-trust final timing must stay unresolved")
    elif outcome == "scheduled_cash_at_nav_liquidation":
        if rights.get("cash_formula") != "net_asset_value_of_shares":
            raise ValueError("ETF liquidation must retain the NAV formula")
        if rights.get("cash_amount_usd") is not None:
            raise ValueError("scheduled NAV cash amount must remain null")
        if (
            rights.get("payment_confirmation")
            != "not_established_by_selected_source"
        ):
            raise ValueError("scheduled payment cannot be marked confirmed")


def validate_spec(spec: Mapping[str, object]) -> None:
    if spec.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported spec schema_version")
    if spec.get("raw_documents_committed") is not False:
        raise ValueError("raw_documents_committed must be false")
    cases = spec.get("cases")
    if not isinstance(cases, list) or len(cases) != 5:
        raise ValueError("fund review spec must contain exactly five cases")
    accessions = [case.get("form25_accession") for case in cases]
    if None in accessions or len(set(accessions)) != len(accessions):
        raise ValueError("Form 25 accessions must be unique and non-null")
    outcome_counts = Counter(case.get("outcome_type") for case in cases)
    if outcome_counts != Counter(
        {
            "nav_ratio_successor_fund": 3,
            "completed_cash_plus_liquidating_trust": 1,
            "scheduled_cash_at_nav_liquidation": 1,
        }
    ):
        raise ValueError("fund review spec outcome strata changed")
    for case in cases:
        source = case.get("source")
        if not isinstance(source, dict):
            raise ValueError("case source must be an object")
        if source.get("cache_family") not in {"form25", "fund"}:
            raise ValueError("unexpected source cache_family")
        markers = source.get("required_markers")
        if not isinstance(markers, list) or not markers:
            raise ValueError("source required_markers must be non-empty")
        if any(not isinstance(marker, str) or not marker for marker in markers):
            raise ValueError("source markers must be non-empty strings")
        if case.get("manual_claim") in {None, ""}:
            raise ValueError("manual_claim is required")
        validate_case_semantics(case)


def source_cache_path(
    source: Mapping[str, object],
    form25_cache: Path,
    fund_cache: Path,
) -> Path:
    root = (
        form25_cache
        if source["cache_family"] == "form25"
        else fund_cache
    )
    return root / (str(source["accession"]) + ".txt")


def source_order(
    source_accession: str,
    source_at: dt.datetime,
    form25_accession: str,
    form25_at: dt.datetime,
) -> str:
    if source_accession == form25_accession:
        return "exchange_source"
    if source_at < form25_at:
        return "issuer_source_before_exchange"
    return "exchange_before_issuer_source"


def summarize_rows(rows: Sequence[Mapping[str, object]]) -> Dict[str, object]:
    return {
        "reviewed_cases": len(rows),
        "outcomes": dict(
            sorted(Counter(row["outcome_type"] for row in rows).items())
        ),
        "fund_structures": dict(
            sorted(Counter(row["fund_structure"] for row in rows).items())
        ),
        "source_order": dict(
            sorted(Counter(row["source_order"] for row in rows).items())
        ),
        "exchange_source_labels": sum(
            row["source_order"] == "exchange_source" for row in rows
        ),
        "issuer_source_labels": sum(
            row["source_order"] != "exchange_source" for row in rows
        ),
        "source_internal_date_conflicts": sum(
            row["effective_date_status"]
            == "rights_date_supported_but_legal_date_text_conflicts"
            for row in rows
        ),
        "scheduled_payment_unconfirmed": sum(
            row["outcome_type"] == "scheduled_cash_at_nav_liquidation"
            for row in rows
        ),
        "liquidating_trust_final_value_unresolved": sum(
            row["outcome_type"]
            == "completed_cash_plus_liquidating_trust"
            for row in rows
        ),
    }


def build_artifact(
    population: Mapping[str, object],
    candidates: Mapping[str, object],
    spec: Mapping[str, object],
    form25_cache: Path,
    fund_cache: Path,
) -> Dict[str, object]:
    validate_spec(spec)
    population_rows = {
        item["accession"]: item for item in population.get("sample", [])
    }
    missing_chains = {
        chain["form25_accession"]: chain
        for chain in candidates.get("chains", [])
        if not chain.get("candidates")
    }
    spec_accessions = {
        case["form25_accession"] for case in spec["cases"]
    }
    if spec_accessions != set(missing_chains):
        raise ValueError(
            "review spec must match the complete missing-candidate fund set"
        )

    rows = []
    for case in sorted(
        spec["cases"], key=lambda item: (item["effective_on"], item["ticker"])
    ):
        form25_accession = str(case["form25_accession"])
        population_row = population_rows.get(form25_accession)
        if population_row is None:
            raise ValueError(
                "{}: absent from frozen population sample".format(
                    form25_accession
                )
            )
        if population_row["issuer_cik"] != case["issuer_cik"]:
            raise ValueError(
                "{}: issuer CIK mismatch".format(form25_accession)
            )
        chain = missing_chains[form25_accession]
        if chain.get("candidate_count") != 0:
            raise ValueError(
                "{}: candidate_count must be zero".format(form25_accession)
            )
        source = case["source"]
        path = source_cache_path(source, form25_cache, fund_cache)
        if not path.is_file():
            raise ValueError("{}: source cache missing".format(path))
        payload = path.read_bytes()
        parsed = parse_source(payload, str(source["accession"]))
        for field in ("accepted_at", "sha256"):
            if parsed[field] != source[field]:
                raise ValueError(
                    "{}: source {} mismatch".format(
                        source["accession"], field
                    )
                )
        text = normalized_submission_text(payload)
        for marker in source["required_markers"]:
            if marker.lower() not in text:
                raise ValueError(
                    "{}: required source marker absent: {!r}".format(
                        source["accession"], marker
                    )
                )
        source_at = dt.datetime.fromisoformat(parsed["accepted_at"])
        form25_at = dt.datetime.fromisoformat(
            str(population_row["accepted_at"])
        )
        delta = int((source_at - form25_at).total_seconds())
        rows.append(
            {
                "chain_id": "ca-fund:" + form25_accession,
                "form25_accession": form25_accession,
                "issuer_cik": case["issuer_cik"],
                "issuer_name": population_row["issuer_name"],
                "ticker": case["ticker"],
                "fund_structure": case["fund_structure"],
                "outcome_type": case["outcome_type"],
                "label_status": (
                    "scheduled_right_not_payment_confirmed"
                    if case["outcome_type"]
                    == "scheduled_cash_at_nav_liquidation"
                    else "manually_reviewed"
                ),
                "effective_on": case["effective_on"],
                "effective_date_status": case["effective_date_status"],
                "form25_accepted_at": population_row["accepted_at"],
                "source_accession": source["accession"],
                "source_accepted_at": parsed["accepted_at"],
                "source_clock_delta_seconds_from_form25": delta,
                "source_order": source_order(
                    str(source["accession"]),
                    source_at,
                    form25_accession,
                    form25_at,
                ),
                "source_role": source["role"],
                "source_url": source["submission_url"],
                "source_sha256": parsed["sha256"],
                "source_markers_validated": True,
                "rights": case["rights"],
                "manual_claim": case["manual_claim"],
                "predictive_for_outcome": False,
                "raw_document_committed": False,
            }
        )

    artifact: Dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "artifact_id": "ca-fund-five-missing-reviewed-v1",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "research_status": "reviewed_rights_labels_not_price_or_alpha_evidence",
        "population_fixture_id": population.get("fixture_id"),
        "population_sample_sha256": population.get("sample_sha256"),
        "candidate_manifest_id": candidates.get("manifest_id"),
        "candidate_chains_sha256": candidates.get("chains_sha256"),
        "review_spec_id": spec.get("spec_id"),
        "raw_documents_committed": False,
        "predictive_features_allowed": False,
        "rows": rows,
    }
    artifact["summary"] = summarize_rows(rows)
    artifact["rows_sha256"] = sha256(rows)
    validate_artifact(artifact)
    return artifact


def validate_artifact(artifact: Mapping[str, object]) -> None:
    if artifact.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported artifact schema_version")
    if artifact.get("raw_documents_committed") is not False:
        raise ValueError("raw_documents_committed must be false")
    if artifact.get("predictive_features_allowed") is not False:
        raise ValueError("fund outcome labels cannot be predictive features")
    rows = artifact.get("rows")
    if not isinstance(rows, list) or len(rows) != 5:
        raise ValueError("reviewed fund artifact must contain five rows")
    if len({row.get("chain_id") for row in rows}) != len(rows):
        raise ValueError("duplicate fund chain_id")
    for row in rows:
        if row.get("predictive_for_outcome") is not False:
            raise ValueError("outcome label cannot predict itself")
        if row.get("raw_document_committed") is not False:
            raise ValueError("raw source cannot be committed")
        if row.get("source_markers_validated") is not True:
            raise ValueError("source markers must be validated")
        validate_case_semantics(row)
        if (
            row["outcome_type"] == "scheduled_cash_at_nav_liquidation"
            and row.get("label_status")
            != "scheduled_right_not_payment_confirmed"
        ):
            raise ValueError("scheduled cash right cannot be completed")
    if artifact.get("summary") != summarize_rows(rows):
        raise ValueError("fund artifact summary mismatch")
    if artifact.get("rows_sha256") != sha256(rows):
        raise ValueError("fund artifact rows hash mismatch")


def write_json_atomic(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    temporary.replace(path)


def command_build(args: argparse.Namespace) -> None:
    artifact = build_artifact(
        load_json(args.population),
        load_json(args.candidates),
        load_json(args.spec),
        args.form25_cache,
        args.fund_cache,
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
        "build", help="build the reviewed five-fund rights artifact"
    )
    build.add_argument("--population", type=Path, default=DEFAULT_POPULATION)
    build.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    build.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    build.add_argument("--form25-cache", type=Path, default=DEFAULT_FORM25_CACHE)
    build.add_argument("--fund-cache", type=Path, default=DEFAULT_FUND_CACHE)
    build.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    build.set_defaults(func=command_build)

    summary = subparsers.add_parser(
        "summary", help="validate and summarize an existing artifact"
    )
    summary.add_argument("--input", type=Path, default=DEFAULT_OUTPUT)
    summary.set_defaults(func=command_summary)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()

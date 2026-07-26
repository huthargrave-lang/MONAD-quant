#!/usr/bin/env python3
"""Extract structured rhetoric deltas between successive deal filings.

CA-RHETORIC step 0: given an ordered chain of SEC submission texts, count
presence/absence flips for a frozen phrase family (closing window, certainty,
regulatory, financing, litigation, board recommendation, unknowns). This is a
transparent baseline for later embeddings — not a sentiment score and not an
alpha claim.

Raw filings remain outside the repository; tests use synthetic payloads.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import re
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple


REPO = Path(__file__).resolve().parents[1]
DEFAULT_SPEC = (
    REPO / "docs" / "research" / "data" / "ca_rhetoric_delta_spec.json"
)
DEFAULT_OUTPUT = (
    REPO / "docs" / "research" / "data" / "ca_rhetoric_delta_seed.json"
)
SCHEMA_VERSION = 1

PHRASE_FAMILIES: Dict[str, Tuple[str, ...]] = {
    "closing_window": (
        r"outside date",
        r"end date",
        r"expected to close",
        r"anticipated to close",
    ),
    "certainty": (
        r"confident",
        r"highly confident",
        r"no assurance",
        r"cannot be assured",
        r"subject to.*conditions",
    ),
    "regulatory": (
        r"antitrust",
        r"hart-scott-rodino",
        r"\bhsr\b",
        r"second request",
        r"regulatory approval",
        r"competition.?law",
    ),
    "financing": (
        r"financing condition",
        r"debt commitment",
        r"equity commitment",
        r"financing not a condition",
    ),
    "litigation": (
        r"litigation",
        r"lawsuit",
        r"complaint was filed",
        r"preliminary injunction",
    ),
    "board_recommendation": (
        r"board.*recommends",
        r"recommendation of the board",
        r"withdraw.*recommendation",
        r"change in recommendation",
    ),
    "explicit_unknowns": (
        r"unable to predict",
        r"timing.*uncertain",
        r"no clear path",
        r"uncertainty as to when",
    ),
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


def normalized_text(payload: bytes) -> str:
    raw = payload.decode("latin-1", errors="replace")
    without_tags = re.sub(r"<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", html.unescape(without_tags)).strip().lower()


def family_hits(text: str) -> Dict[str, List[str]]:
    hits: Dict[str, List[str]] = {}
    for family, patterns in PHRASE_FAMILIES.items():
        matched = []
        for pattern in patterns:
            if re.search(pattern, text, flags=re.I):
                matched.append(pattern)
        hits[family] = matched
    return hits


def presence_vector(hits: Mapping[str, Sequence[str]]) -> Dict[str, bool]:
    return {family: bool(values) for family, values in hits.items()}


def delta_vector(
    before: Mapping[str, bool],
    after: Mapping[str, bool],
) -> Dict[str, str]:
    out = {}
    for family in PHRASE_FAMILIES:
        left = before[family]
        right = after[family]
        if left == right:
            out[family] = "unchanged"
        elif right and not left:
            out[family] = "appeared"
        elif left and not right:
            out[family] = "disappeared"
        else:  # pragma: no cover - boolean exhaustive
            out[family] = "unchanged"
    return out


def validate_spec(spec: Mapping[str, object]) -> None:
    if spec.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported spec schema_version")
    chains = spec.get("chains")
    if not isinstance(chains, list) or not chains:
        raise ValueError("chains missing")
    for chain in chains:
        filings = chain.get("filings")
        if not isinstance(filings, list) or len(filings) < 2:
            raise ValueError(
                "{}: need at least two filings".format(chain.get("chain_id"))
            )


def build_artifact(
    spec: Mapping[str, object],
    raw_cache: Path,
) -> Dict[str, object]:
    validate_spec(spec)
    chains_out = []
    for chain in spec["chains"]:
        filings_out = []
        previous_presence = None
        previous_accession = None
        for filing in chain["filings"]:
            accession = filing["accession"]
            if filing.get("inline_text") is not None:
                payload = str(filing["inline_text"]).encode("latin-1")
            else:
                path = raw_cache / (accession + ".txt")
                if not path.is_file():
                    raise ValueError("{}: raw filing missing".format(path))
                payload = path.read_bytes()
            text = normalized_text(payload)
            for marker in filing.get("required_markers", []):
                if marker.lower() not in text:
                    raise ValueError(
                        "{}: required marker absent: {!r}".format(
                            accession, marker
                        )
                    )
            hits = family_hits(text)
            presence = presence_vector(hits)
            record = {
                "accession": accession,
                "observed_at": filing.get("observed_at"),
                "role": filing.get("role"),
                "family_hits": hits,
                "presence": presence,
                "delta_from_previous": (
                    None
                    if previous_presence is None
                    else delta_vector(previous_presence, presence)
                ),
                "previous_accession": previous_accession,
            }
            filings_out.append(record)
            previous_presence = presence
            previous_accession = accession
        deltas = [
            filing["delta_from_previous"]
            for filing in filings_out
            if filing["delta_from_previous"] is not None
        ]
        changed = sum(
            1
            for delta in deltas
            for state in delta.values()
            if state != "unchanged"
        )
        chains_out.append(
            {
                "chain_id": chain["chain_id"],
                "deal_id": chain.get("deal_id"),
                "filings": filings_out,
                "summary": {
                    "filing_count": len(filings_out),
                    "delta_steps": len(deltas),
                    "family_state_changes": changed,
                },
            }
        )
    artifact = {
        "schema_version": SCHEMA_VERSION,
        "artifact_id": spec["spec_id"],
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "research_status": (
            "transparent_rhetoric_delta_seed_not_predictive_model"
        ),
        "phrase_families": {
            key: list(value) for key, value in PHRASE_FAMILIES.items()
        },
        "raw_documents_committed": False,
        "predictive_features_allowed": False,
        "chains": chains_out,
        "summary": {
            "chain_count": len(chains_out),
            "total_family_state_changes": sum(
                chain["summary"]["family_state_changes"] for chain in chains_out
            ),
            "transparent_baseline_only": True,
            "embedding_branch_not_run": True,
        },
    }
    artifact["chains_sha256"] = sha256(chains_out)
    validate_artifact(artifact)
    return artifact


def validate_artifact(artifact: Mapping[str, object]) -> None:
    if artifact.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported artifact schema_version")
    if artifact.get("raw_documents_committed") is not False:
        raise ValueError("raw_documents_committed must be false")
    if artifact.get("predictive_features_allowed") is not False:
        raise ValueError("rhetoric deltas are not outcome labels")
    if artifact.get("chains_sha256") != sha256(artifact["chains"]):
        raise ValueError("chains hash mismatch")


def write_json_atomic(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    temporary.replace(path)


def command_build(args: argparse.Namespace) -> None:
    artifact = build_artifact(load_json(args.spec), args.raw_cache)
    write_json_atomic(args.output, artifact)
    print(json.dumps(artifact["summary"], indent=2))
    print("wrote {}".format(args.output))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build", help="build rhetoric delta seed")
    build.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    build.add_argument(
        "--raw-cache",
        type=Path,
        default=Path("/private/tmp/monad-sec-rhetoric-delta"),
    )
    build.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    build.set_defaults(func=command_build)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()

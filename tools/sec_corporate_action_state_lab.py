#!/usr/bin/env python3
"""Build and query a point-in-time SEC corporate-action state vector.

The committed JSON fixture contains transformed official facts.  Raw filings
remain at SEC.gov and the generated SQLite projection must remain outside the
repository.  ``observed_at`` is the decision clock; ``effective_on`` and
``effective_at`` describe when the underlying event took effect.  A later
confirmation is never backdated into an earlier knowledge snapshot.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import os
import re
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence
from urllib.parse import quote


_TOOLS = str(Path(__file__).resolve().parent)
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)
import ui_tokens  # noqa: E402  — the one palette; see F231

REPO = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = (
    REPO / "docs" / "research" / "data" / "ca01_sec_state_machine_fixture.json"
)
DEFAULT_DB = Path(tempfile.gettempdir()) / "monad-sec-action-states.sqlite3"
SCHEMA_VERSION = 1
DIMENSIONS = {
    "transaction",
    "listing",
    "reporting",
    "security_rights",
    "bankruptcy",
    "disclosure",
}
KNOWLEDGE_ROLES = {
    "predictive_status",
    "post_effective_confirmation",
    "outcome_label",
    "administrative_status",
}
ACCESSION_RE = re.compile(r"^\d{10}-\d{2}-\d{6}$")


SCHEMA = """
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = DELETE;
PRAGMA synchronous = FULL;

CREATE TABLE metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
) STRICT;

CREATE TABLE action_chains (
    chain_id TEXT PRIMARY KEY,
    issuer_cik TEXT NOT NULL,
    issuer_name TEXT NOT NULL,
    event_symbol TEXT NOT NULL,
    action_family TEXT NOT NULL,
    outcome_action_id TEXT NOT NULL
) STRICT;

CREATE TABLE sources (
    source_id TEXT PRIMARY KEY,
    accession TEXT NOT NULL,
    source_form TEXT NOT NULL,
    source_actor TEXT NOT NULL,
    document_url TEXT NOT NULL,
    filing_index_url TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    observation_time_quality TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    raw_document_committed INTEGER NOT NULL
        CHECK (raw_document_committed IN (0, 1))
) STRICT;

CREATE TABLE state_assertions (
    assertion_id TEXT PRIMARY KEY,
    chain_id TEXT NOT NULL REFERENCES action_chains(chain_id),
    ordinal INTEGER NOT NULL CHECK (ordinal > 0),
    dimension TEXT NOT NULL CHECK (
        dimension IN (
            'transaction', 'listing', 'reporting', 'security_rights',
            'bankruptcy', 'disclosure'
        )
    ),
    state_value TEXT NOT NULL,
    effective_on TEXT NOT NULL,
    effective_at TEXT,
    effective_time_quality TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    observed_epoch REAL NOT NULL,
    observation_time_quality TEXT NOT NULL,
    knowledge_role TEXT NOT NULL CHECK (
        knowledge_role IN (
            'predictive_status', 'post_effective_confirmation',
            'outcome_label', 'administrative_status'
        )
    ),
    predictive_for_downstream_transition INTEGER NOT NULL
        CHECK (predictive_for_downstream_transition IN (0, 1)),
    source_id TEXT NOT NULL REFERENCES sources(source_id),
    claim TEXT NOT NULL,
    calendar_day_lag INTEGER NOT NULL,
    intraday_lag_seconds REAL,
    assertion_sha256 TEXT NOT NULL,
    UNIQUE (chain_id, ordinal)
) STRICT;

CREATE VIRTUAL TABLE state_search USING fts5(
    assertion_id UNINDEXED,
    chain_id UNINDEXED,
    event_symbol,
    issuer_name,
    dimension,
    state_value,
    claim,
    tokenize = 'unicode61'
);

CREATE TRIGGER state_assertions_no_update
BEFORE UPDATE ON state_assertions
BEGIN
    SELECT RAISE(ABORT, 'state assertions are append-only');
END;

CREATE TRIGGER state_assertions_no_delete
BEFORE DELETE ON state_assertions
BEGIN
    SELECT RAISE(ABORT, 'state assertions cannot be deleted');
END;
"""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _is_within(path: Path, parent: Path) -> bool:
    try:
        return os.path.commonpath(
            [str(path.resolve()), str(parent.resolve())]
        ) == str(parent.resolve())
    except ValueError:
        return False


def _parse_timestamp(value: str, field: str) -> dt.datetime:
    try:
        parsed = dt.datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field}: invalid ISO timestamp {value!r}") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field}: timezone offset required")
    return parsed


def _parse_as_of(value: Optional[str]) -> Optional[dt.datetime]:
    if value is None:
        return None
    return _parse_timestamp(value, "as_of")


def _source_id(source: Mapping[str, object]) -> str:
    document_key = hashlib.sha256(
        str(source["document_url"]).encode("utf-8")
    ).hexdigest()[:12]
    return "sec:" + str(source["accession"]) + ":" + document_key


def _iter_assertions(fixture: Mapping[str, object]):
    for chain in fixture["chains"]:
        for assertion in chain["assertions"]:
            yield chain, assertion


def validate_fixture(fixture: Mapping[str, object]) -> None:
    if fixture.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {SCHEMA_VERSION}")
    if not str(fixture.get("fixture_id", "")).strip():
        raise ValueError("fixture_id is required")
    if fixture.get("raw_documents_committed") is not False:
        raise ValueError("raw_documents_committed must be false")
    policy = fixture.get("clock_policy")
    if not isinstance(policy, dict) or policy.get("decision_clock") != "observed_at":
        raise ValueError("clock_policy.decision_clock must be observed_at")
    chains = fixture.get("chains")
    if not isinstance(chains, list) or not chains:
        raise ValueError("chains must be a non-empty list")

    chain_ids = set()
    assertion_ids = set()
    source_facts: Dict[object, object] = {}
    for chain in chains:
        required_chain = {
            "chain_id",
            "issuer_cik",
            "issuer_name",
            "event_symbol",
            "action_family",
            "outcome_action_id",
            "assertions",
        }
        missing = sorted(required_chain - set(chain))
        if missing:
            raise ValueError(f"chain missing fields: {missing}")
        chain_id = str(chain["chain_id"])
        if chain_id in chain_ids:
            raise ValueError(f"duplicate chain_id: {chain_id}")
        chain_ids.add(chain_id)
        cik = str(chain["issuer_cik"])
        if len(cik) != 10 or not cik.isdigit():
            raise ValueError(f"{chain_id}: issuer_cik must be ten digits")
        assertions = chain["assertions"]
        if not isinstance(assertions, list) or not assertions:
            raise ValueError(f"{chain_id}: assertions required")
        ordinals = [item.get("ordinal") for item in assertions]
        if ordinals != list(range(1, len(assertions) + 1)):
            raise ValueError(f"{chain_id}: ordinals must be contiguous from one")

        previous_observed = None
        for assertion in assertions:
            required = {
                "assertion_id",
                "ordinal",
                "dimension",
                "state_value",
                "effective_on",
                "effective_at",
                "effective_time_quality",
                "observed_at",
                "observation_time_quality",
                "knowledge_role",
                "predictive_for_downstream_transition",
                "source",
                "claim",
            }
            missing = sorted(required - set(assertion))
            if missing:
                raise ValueError(f"{chain_id}: assertion missing fields: {missing}")
            assertion_id = str(assertion["assertion_id"])
            if assertion_id in assertion_ids:
                raise ValueError(f"duplicate assertion_id: {assertion_id}")
            assertion_ids.add(assertion_id)
            if assertion["dimension"] not in DIMENSIONS:
                raise ValueError(f"{assertion_id}: invalid dimension")
            if assertion["knowledge_role"] not in KNOWLEDGE_ROLES:
                raise ValueError(f"{assertion_id}: invalid knowledge_role")
            predictive = assertion["predictive_for_downstream_transition"]
            if not isinstance(predictive, bool):
                raise ValueError(f"{assertion_id}: predictive flag must be boolean")
            if predictive and assertion["knowledge_role"] != "predictive_status":
                raise ValueError(
                    f"{assertion_id}: only predictive_status may predict downstream"
                )
            if not str(assertion["state_value"]).strip():
                raise ValueError(f"{assertion_id}: state_value required")
            if not str(assertion["claim"]).strip():
                raise ValueError(f"{assertion_id}: claim required")

            try:
                effective_on = dt.date.fromisoformat(assertion["effective_on"])
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"{assertion_id}: effective_on must be an ISO date"
                ) from exc
            effective_at = assertion["effective_at"]
            if effective_at is not None:
                parsed_effective = _parse_timestamp(
                    effective_at, f"{assertion_id}.effective_at"
                )
                if parsed_effective.date() != effective_on:
                    raise ValueError(
                        f"{assertion_id}: effective_at date must match effective_on"
                    )
            observed = _parse_timestamp(
                assertion["observed_at"], f"{assertion_id}.observed_at"
            )
            if previous_observed is not None and observed < previous_observed:
                raise ValueError(
                    f"{chain_id}: assertions must be ordered by observed_at"
                )
            previous_observed = observed

            source = assertion["source"]
            required_source = {
                "accession",
                "form",
                "actor",
                "document_url",
                "filing_index_url",
                "raw_document_committed",
            }
            missing = sorted(required_source - set(source))
            if missing:
                raise ValueError(f"{assertion_id}: source missing fields: {missing}")
            if not ACCESSION_RE.fullmatch(str(source["accession"])):
                raise ValueError(f"{assertion_id}: invalid SEC accession")
            for url_field in ("document_url", "filing_index_url"):
                if not str(source[url_field]).startswith("https://www.sec.gov/"):
                    raise ValueError(f"{assertion_id}: source must be official SEC URL")
            if source["raw_document_committed"] is not False:
                raise ValueError(f"{assertion_id}: raw documents cannot be committed")
            if assertion["state_value"].startswith("form25") and not str(
                source["form"]
            ).startswith("25"):
                raise ValueError(f"{assertion_id}: Form 25 state needs Form 25 source")
            if assertion["state_value"].startswith("form15") and not str(
                source["form"]
            ).startswith("15"):
                raise ValueError(f"{assertion_id}: Form 15 state needs Form 15 source")

            source_fact = {
                **source,
                "observed_at": assertion["observed_at"],
                "observation_time_quality": assertion[
                    "observation_time_quality"
                ],
            }
            source_key = (
                str(source["accession"]),
                str(source["document_url"]),
            )
            existing = source_facts.get(source_key)
            if existing is not None and existing != source_fact:
                raise ValueError(
                    f"{assertion_id}: conflicting metadata for source document"
                )
            source_facts[source_key] = source_fact


def load_fixture(path: Path = DEFAULT_FIXTURE) -> Mapping[str, object]:
    fixture = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_fixture(fixture)
    return fixture


def assertion_lag(assertion: Mapping[str, object]) -> Dict[str, object]:
    observed = _parse_timestamp(assertion["observed_at"], "observed_at")
    effective_on = dt.date.fromisoformat(assertion["effective_on"])
    intraday = None
    if assertion["effective_at"] is not None:
        effective = _parse_timestamp(assertion["effective_at"], "effective_at")
        intraday = (observed - effective).total_seconds()
    return {
        "calendar_day_lag": (observed.date() - effective_on).days,
        "intraday_lag_seconds": intraday,
    }


def _assertion_mode(assertion: Mapping[str, object]) -> str:
    value = str(assertion["state_value"])
    if any(token in value for token in ("_scheduled", "_expected", "_requested")):
        return "scheduled_transition"
    return "state"


def _effective_by(
    assertion: Mapping[str, object], cutoff: Optional[dt.datetime]
) -> bool:
    if cutoff is None:
        return True
    if assertion["effective_at"] is not None:
        return _parse_timestamp(assertion["effective_at"], "effective_at") <= cutoff
    # A date-only filing does not establish an intraday clock.  On that date,
    # wait until the next calendar day rather than inventing a midnight event.
    return dt.date.fromisoformat(assertion["effective_on"]) < cutoff.date()


def _materialize_vectors(
    timeline: Sequence[Mapping[str, object]],
    cutoff: Optional[dt.datetime],
) -> Dict[str, object]:
    knowledge = {}
    effective = {}
    schedules = []
    for assertion in timeline:
        dimension = str(assertion["dimension"])
        compact = {
            "state_value": assertion["state_value"],
            "assertion_id": assertion["assertion_id"],
            "effective_on": assertion["effective_on"],
            "observed_at": assertion["observed_at"],
            "knowledge_role": assertion["knowledge_role"],
        }
        knowledge[dimension] = compact
        if _assertion_mode(assertion) == "scheduled_transition":
            if cutoff is None:
                schedule_status = "recorded_schedule"
            elif _effective_by(assertion, cutoff):
                schedule_status = "past_due_requires_confirmation"
            else:
                schedule_status = "future"
            schedules.append({**compact, "dimension": dimension, "status": schedule_status})
        elif _effective_by(assertion, cutoff):
            effective[dimension] = compact
    return {
        "knowledge_vector": dict(sorted(knowledge.items())),
        "effective_state_vector": dict(sorted(effective.items())),
        "scheduled_transitions": schedules,
    }


def fixture_summary(fixture: Mapping[str, object]) -> Dict[str, object]:
    role_counts: Dict[str, int] = {}
    dimension_counts: Dict[str, int] = {}
    lags = []
    for _, assertion in _iter_assertions(fixture):
        role = str(assertion["knowledge_role"])
        dimension = str(assertion["dimension"])
        role_counts[role] = role_counts.get(role, 0) + 1
        dimension_counts[dimension] = dimension_counts.get(dimension, 0) + 1
        lags.append(assertion_lag(assertion)["calendar_day_lag"])
    return {
        "fixture_id": fixture["fixture_id"],
        "chain_count": len(fixture["chains"]),
        "assertion_count": sum(
            len(chain["assertions"]) for chain in fixture["chains"]
        ),
        "role_counts": dict(sorted(role_counts.items())),
        "dimension_counts": dict(sorted(dimension_counts.items())),
        "post_effective_observation_count": sum(lag > 0 for lag in lags),
        "max_calendar_day_confirmation_lag": max(lags),
    }


def _find_chain(
    fixture: Mapping[str, object], chain_id: str
) -> Mapping[str, object]:
    for chain in fixture["chains"]:
        if chain["chain_id"] == chain_id:
            return chain
    raise KeyError(chain_id)


def materialize_state(
    fixture: Mapping[str, object],
    chain_id: str,
    as_of: Optional[str] = None,
) -> Dict[str, object]:
    chain = _find_chain(fixture, chain_id)
    cutoff = _parse_as_of(as_of)
    visible = []
    for assertion in chain["assertions"]:
        observed = _parse_timestamp(assertion["observed_at"], "observed_at")
        if cutoff is None or observed <= cutoff:
            row = dict(assertion)
            row["lag"] = assertion_lag(assertion)
            visible.append(row)
    vectors = _materialize_vectors(visible, cutoff)
    return {
        "chain_id": chain_id,
        "event_symbol": chain["event_symbol"],
        "issuer_name": chain["issuer_name"],
        "as_of": as_of,
        "visible_assertion_count": len(visible),
        "state_vector": vectors["effective_state_vector"],
        **vectors,
        "timeline": visible,
    }


def _insert_fixture(
    con: sqlite3.Connection, fixture: Mapping[str, object]
) -> None:
    sources = {}
    pending_assertions = []
    for chain in fixture["chains"]:
        con.execute(
            "INSERT INTO action_chains VALUES (?, ?, ?, ?, ?, ?)",
            (
                chain["chain_id"],
                chain["issuer_cik"],
                chain["issuer_name"],
                chain["event_symbol"],
                chain["action_family"],
                chain["outcome_action_id"],
            ),
        )
        for assertion in chain["assertions"]:
            source = assertion["source"]
            source_id = _source_id(source)
            source_row = (
                source_id,
                source["accession"],
                source["form"],
                source["actor"],
                source["document_url"],
                source["filing_index_url"],
                assertion["observed_at"],
                assertion["observation_time_quality"],
                _sha256(
                    {
                        **source,
                        "observed_at": assertion["observed_at"],
                        "observation_time_quality": assertion[
                            "observation_time_quality"
                        ],
                    }
                ),
                0,
            )
            existing = sources.get(source_id)
            if existing is not None and existing != source_row:
                raise ValueError(f"conflicting source row: {source_id}")
            sources[source_id] = source_row
            pending_assertions.append((chain, assertion, source_id))
    con.executemany(
        "INSERT INTO sources VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        sources.values(),
    )
    for chain, assertion, source_id in pending_assertions:
        lag = assertion_lag(assertion)
        assertion_fact = {
            "chain_id": chain["chain_id"],
            **assertion,
        }
        con.execute(
            """
            INSERT INTO state_assertions VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                assertion["assertion_id"],
                chain["chain_id"],
                assertion["ordinal"],
                assertion["dimension"],
                assertion["state_value"],
                assertion["effective_on"],
                assertion["effective_at"],
                assertion["effective_time_quality"],
                assertion["observed_at"],
                _parse_timestamp(
                    assertion["observed_at"], "observed_at"
                ).timestamp(),
                assertion["observation_time_quality"],
                assertion["knowledge_role"],
                int(assertion["predictive_for_downstream_transition"]),
                source_id,
                assertion["claim"],
                lag["calendar_day_lag"],
                lag["intraday_lag_seconds"],
                _sha256(assertion_fact),
            ),
        )
        con.execute(
            "INSERT INTO state_search VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                assertion["assertion_id"],
                chain["chain_id"],
                chain["event_symbol"],
                chain["issuer_name"],
                assertion["dimension"],
                assertion["state_value"],
                assertion["claim"],
            ),
        )


def build_database(
    db_path: Path = DEFAULT_DB,
    fixture_path: Path = DEFAULT_FIXTURE,
) -> Path:
    db_path = Path(db_path).resolve()
    if _is_within(db_path, REPO):
        raise ValueError("refusing to build a raw SQLite database inside the repository")
    fixture = load_fixture(Path(fixture_path))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=db_path.name + ".", suffix=".tmp", dir=str(db_path.parent)
    )
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        con = sqlite3.connect(str(temp_path))
        try:
            con.executescript(SCHEMA)
            con.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            con.executemany(
                "INSERT INTO metadata VALUES (?, ?)",
                [
                    ("schema_version", str(SCHEMA_VERSION)),
                    ("fixture_id", str(fixture["fixture_id"])),
                    ("fixture_sha256", _sha256(fixture)),
                    ("database_role", "disposable point-in-time read projection"),
                    ("decision_clock", "observed_at"),
                    ("raw_documents_committed", "false"),
                ],
            )
            _insert_fixture(con, fixture)
            con.commit()
            violations = con.execute("PRAGMA foreign_key_check").fetchall()
            if violations:
                raise sqlite3.IntegrityError(
                    f"foreign-key violations: {violations}"
                )
        finally:
            con.close()
        os.replace(str(temp_path), str(db_path))
    finally:
        if temp_path.exists():
            temp_path.unlink()
    return db_path


def _connect_readonly(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{Path(db_path).resolve()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def ledger_payload(
    db_path: Path = DEFAULT_DB,
    chain_id: Optional[str] = None,
    as_of: Optional[str] = None,
) -> Dict[str, object]:
    cutoff = _parse_as_of(as_of)
    cutoff_epoch = cutoff.timestamp() if cutoff is not None else None
    con = _connect_readonly(db_path)
    try:
        base = {
            "schema_version": int(con.execute("PRAGMA user_version").fetchone()[0]),
            "database_role": con.execute(
                "SELECT value FROM metadata WHERE key='database_role'"
            ).fetchone()[0],
            "decision_clock": "observed_at",
            "chains": [
                dict(row)
                for row in con.execute(
                    """
                    SELECT c.chain_id, c.event_symbol, c.issuer_name,
                           c.action_family, count(a.assertion_id) assertion_count,
                           count(DISTINCT a.dimension) dimension_count,
                           min(a.observed_at) first_observed_at,
                           max(a.observed_at) last_observed_at,
                           max(a.calendar_day_lag) max_calendar_day_lag
                    FROM action_chains c
                    JOIN state_assertions a ON a.chain_id = c.chain_id
                    GROUP BY c.chain_id
                    ORDER BY first_observed_at, c.chain_id
                    """
                )
            ],
        }
        if chain_id is None:
            return base
        chain = con.execute(
            "SELECT * FROM action_chains WHERE chain_id = ?", (chain_id,)
        ).fetchone()
        if chain is None:
            raise KeyError(chain_id)
        query = """
            SELECT a.*, s.accession, s.source_form, s.source_actor,
                   s.document_url, s.filing_index_url,
                   s.raw_document_committed
            FROM state_assertions a
            JOIN sources s ON s.source_id = a.source_id
            WHERE a.chain_id = ?
        """
        params: List[object] = [chain_id]
        if cutoff_epoch is not None:
            query += " AND a.observed_epoch <= ?"
            params.append(cutoff_epoch)
        query += " ORDER BY a.ordinal"
        timeline = [dict(row) for row in con.execute(query, params)]
        vectors = _materialize_vectors(timeline, cutoff)
        base["detail"] = {
            **dict(chain),
            "as_of": as_of,
            "visible_assertion_count": len(timeline),
            "state_vector": vectors["effective_state_vector"],
            **vectors,
            "timeline": timeline,
        }
        return base
    finally:
        con.close()


def render_html(payload: Mapping[str, object]) -> str:
    chain_rows = []
    for chain in payload["chains"]:
        encoded = quote(chain["chain_id"], safe="")
        chain_rows.append(
            "<tr>"
            f"<td><a href=\"/corporate-action-states?id={encoded}\">"
            f"{html.escape(chain['event_symbol'])}</a></td>"
            f"<td>{html.escape(chain['action_family'])}</td>"
            f"<td>{chain['assertion_count']}</td>"
            f"<td>{chain['dimension_count']}</td>"
            f"<td>{html.escape(chain['first_observed_at'])}</td>"
            f"<td>{html.escape(chain['last_observed_at'])}</td>"
            "</tr>"
        )
    detail_html = ""
    if payload.get("detail"):
        detail = payload["detail"]
        vector = "".join(
            "<tr>"
            f"<td>{html.escape(dimension)}</td>"
            f"<td>{html.escape(state['state_value'])}</td>"
            f"<td>{html.escape(state['observed_at'])}</td>"
            "</tr>"
            for dimension, state in detail["state_vector"].items()
        )
        timeline = "".join(
            "<tr>"
            f"<td>{row['ordinal']}</td>"
            f"<td>{html.escape(row['observed_at'])}</td>"
            f"<td>{html.escape(row['effective_on'])}</td>"
            f"<td>{html.escape(row['dimension'])}</td>"
            f"<td>{html.escape(row['state_value'])}</td>"
            f"<td>{html.escape(row['knowledge_role'])}</td>"
            f"<td><a href=\"{html.escape(row['document_url'])}\">SEC</a></td>"
            "</tr>"
            for row in detail["timeline"]
        )
        as_of = detail["as_of"] or "latest"
        detail_html = (
            f"<section><h2>{html.escape(detail['event_symbol'])} state vector</h2>"
            f"<p>As of {html.escape(as_of)} · "
            f"{detail['visible_assertion_count']} visible assertions.</p>"
            "<table><thead><tr><th>Dimension</th><th>State</th>"
            f"<th>Observed</th></tr></thead><tbody>{vector}</tbody></table></section>"
            "<section><h2>Observation-ordered timeline</h2>"
            "<table><thead><tr><th>#</th><th>Observed</th><th>Effective</th>"
            "<th>Dimension</th><th>State</th><th>Role</th><th>Source</th>"
            f"</tr></thead><tbody>{timeline}</tbody></table></section>"
        )
    return f"""{ui_tokens.document_head("MONAD SEC action states", "1250px")}
<body><div class="wrap"><h1>SEC corporate-action state machine</h1>
<p class="note">Point-in-time rule: facts enter the state vector at EDGAR
acceptance, never at a retroactively reported effective date. This is transformed
official evidence, not a trading signal or proof of investor ingestion.</p>
<section><div class="table"><table><thead><tr><th>Symbol</th><th>Family</th>
<th>Assertions</th><th>Dimensions</th><th>First observed</th><th>Last observed</th>
</tr></thead><tbody>{''.join(chain_rows)}</tbody></table></div></section>{detail_html}
</div></body></html>"""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build", help="build disposable SQLite projection")
    build.add_argument("--db", type=Path, default=DEFAULT_DB)
    summary = sub.add_parser("summary", help="summarize fixture or database")
    summary.add_argument("--db", type=Path)
    summary.add_argument("--id")
    summary.add_argument("--as-of")
    snapshot = sub.add_parser("snapshot", help="materialize fixture state as-of")
    snapshot.add_argument("--id", required=True)
    snapshot.add_argument("--as-of")
    html_parser = sub.add_parser("html", help="render database browser HTML")
    html_parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    html_parser.add_argument("--id")
    html_parser.add_argument("--as-of")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "build":
        path = build_database(args.db, args.fixture)
        print(json.dumps({"database": str(path), **fixture_summary(load_fixture(args.fixture))}, indent=2))
        return 0
    if args.command == "summary":
        payload = (
            ledger_payload(args.db, args.id, args.as_of)
            if args.db
            else fixture_summary(load_fixture(args.fixture))
        )
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    if args.command == "snapshot":
        print(
            json.dumps(
                materialize_state(load_fixture(args.fixture), args.id, args.as_of),
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if args.command == "html":
        print(render_html(ledger_payload(args.db, args.id, args.as_of)))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())

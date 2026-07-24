#!/usr/bin/env python3
"""Validate, project, value, and audit corporate-action outcome facts.

The versioned JSON fixture is authoritative. SQLite is a disposable read model
and must remain outside the repository. The tool models investor wealth through
fixed-cash mergers, stock mergers, spinoffs, cancellations, and ticker changes;
it never invents a continuing-equity return for a security that ceased trading.

Raw SEC documents and raw market-data panels are not committed. The optional
coverage command retains only transformed coverage metadata and fingerprints.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import math
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Callable, Dict, List, Mapping, Optional, Sequence


REPO = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = (
    REPO / "docs" / "research" / "data" / "ca00_corporate_action_fixture.json"
)
DEFAULT_DB = Path(tempfile.gettempdir()) / "monad-corporate-actions.sqlite3"
SCHEMA_VERSION = 1
ACTION_TYPES = {
    "cash_merger",
    "stock_merger",
    "spinoff",
    "bankruptcy_cancellation",
    "ticker_change",
}
LABEL_TYPES = {
    "terminal_cash_value",
    "successor_security_value",
    "retained_parent_plus_distributed_security",
    "canceled_security_rights_pending_distribution_review",
    "terminal_zero_value_confirmed_no_consideration",
    "identity_continuity",
}


SCHEMA = """
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = DELETE;
PRAGMA synchronous = FULL;

CREATE TABLE metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
) STRICT;

CREATE TABLE securities (
    security_id TEXT PRIMARY KEY,
    issuer_cik TEXT NOT NULL,
    security_name TEXT NOT NULL,
    identity_quality TEXT NOT NULL
) STRICT;

CREATE TABLE sources (
    source_id TEXT PRIMARY KEY,
    source_url TEXT NOT NULL,
    accession TEXT NOT NULL,
    source_time TEXT NOT NULL,
    source_time_quality TEXT NOT NULL,
    source_role TEXT NOT NULL,
    evidence_sha256 TEXT NOT NULL,
    raw_document_committed INTEGER NOT NULL
        CHECK (raw_document_committed IN (0, 1))
) STRICT;

CREATE TABLE corporate_actions (
    logical_action_id TEXT PRIMARY KEY,
    action_type TEXT NOT NULL CHECK (
        action_type IN (
            'cash_merger', 'stock_merger', 'spinoff',
            'bankruptcy_cancellation', 'ticker_change'
        )
    ),
    subject_security_id TEXT NOT NULL REFERENCES securities(security_id),
    event_symbol TEXT NOT NULL,
    source_id TEXT NOT NULL REFERENCES sources(source_id),
    effective_time TEXT NOT NULL,
    effective_time_quality TEXT NOT NULL,
    last_regular_trading_session TEXT,
    label_type TEXT NOT NULL,
    outcome_formula TEXT NOT NULL,
    post_effective_return_policy TEXT NOT NULL,
    value_completeness TEXT NOT NULL,
    terms_json TEXT NOT NULL
) STRICT;

CREATE TABLE consideration_legs (
    logical_action_id TEXT NOT NULL
        REFERENCES corporate_actions(logical_action_id),
    leg_ordinal INTEGER NOT NULL CHECK (leg_ordinal > 0),
    leg_type TEXT NOT NULL CHECK (
        leg_type IN (
            'cash', 'successor_stock', 'retained_parent',
            'distributed_security', 'identity_continuity',
            'cancellation_rights'
        )
    ),
    security_id TEXT REFERENCES securities(security_id),
    symbol TEXT,
    units_per_subject_share REAL,
    cash_usd_per_subject_share REAL,
    leg_status TEXT NOT NULL,
    PRIMARY KEY (logical_action_id, leg_ordinal)
) STRICT;

CREATE TABLE provider_queries (
    logical_action_id TEXT NOT NULL
        REFERENCES corporate_actions(logical_action_id),
    role TEXT NOT NULL,
    candidate_symbols_json TEXT NOT NULL,
    required_session TEXT NOT NULL,
    PRIMARY KEY (logical_action_id, role)
) STRICT;

CREATE VIRTUAL TABLE corporate_action_search USING fts5(
    logical_action_id UNINDEXED,
    event_symbol,
    security_name,
    action_type,
    label_type,
    outcome_formula,
    tokenize = 'unicode61'
);

CREATE TRIGGER corporate_actions_no_update
BEFORE UPDATE ON corporate_actions
BEGIN
    SELECT RAISE(ABORT, 'corporate actions are append-only');
END;

CREATE TRIGGER corporate_actions_no_delete
BEFORE DELETE ON corporate_actions
BEGIN
    SELECT RAISE(ABORT, 'corporate actions cannot be deleted');
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


def _validate_temporal(value: str, quality: str, field: str) -> None:
    if "date_only" in quality or "date_confirmed" in quality:
        try:
            dt.date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"{field}: expected ISO date, got {value!r}") from exc
        return
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            f"{field}: expected timezone-aware ISO timestamp, got {value!r}"
        ) from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field}: timezone offset required")


def validate_fixture(fixture: Mapping[str, object]) -> None:
    if fixture.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {SCHEMA_VERSION}")
    if not str(fixture.get("fixture_id", "")).strip():
        raise ValueError("fixture_id is required")
    if fixture.get("raw_documents_committed") is not False:
        raise ValueError("raw_documents_committed must be false")
    actions = fixture.get("actions")
    if not isinstance(actions, list) or not actions:
        raise ValueError("actions must be a non-empty list")

    seen_actions = set()
    for action in actions:
        required = {
            "logical_action_id",
            "action_type",
            "subject",
            "source",
            "effective_time",
            "effective_time_quality",
            "last_regular_trading_session",
            "terms",
            "outcome_model",
            "provider_queries",
        }
        missing = sorted(required - set(action))
        if missing:
            raise ValueError(f"action missing fields: {missing}")
        action_id = str(action["logical_action_id"])
        if action_id in seen_actions:
            raise ValueError(f"duplicate logical_action_id: {action_id}")
        seen_actions.add(action_id)
        action_type = action["action_type"]
        if action_type not in ACTION_TYPES:
            raise ValueError(f"{action_id}: invalid action_type {action_type!r}")

        subject = action["subject"]
        for field in (
            "security_id",
            "issuer_cik",
            "security_name",
            "event_symbol",
            "identity_quality",
        ):
            if not str(subject.get(field, "")).strip():
                raise ValueError(f"{action_id}: subject.{field} is required")
        if not (
            len(subject["issuer_cik"]) == 10
            and str(subject["issuer_cik"]).isdigit()
        ):
            raise ValueError(f"{action_id}: issuer_cik must be ten digits")

        source = action["source"]
        for field in (
            "url",
            "accession",
            "source_time",
            "source_time_quality",
            "source_role",
        ):
            if not str(source.get(field, "")).strip():
                raise ValueError(f"{action_id}: source.{field} is required")
        if not str(source["url"]).startswith("https://www.sec.gov/"):
            raise ValueError(f"{action_id}: source must be an official SEC URL")
        if source.get("raw_document_committed") is not False:
            raise ValueError(f"{action_id}: raw source documents must not be committed")
        _validate_temporal(
            source["source_time"], source["source_time_quality"], "source_time"
        )
        _validate_temporal(
            action["effective_time"],
            action["effective_time_quality"],
            "effective_time",
        )
        last_session = action["last_regular_trading_session"]
        if last_session is not None:
            dt.date.fromisoformat(last_session)

        model = action["outcome_model"]
        if model.get("label_type") not in LABEL_TYPES:
            raise ValueError(f"{action_id}: invalid label_type")
        for field in (
            "formula",
            "post_effective_return_policy",
            "value_completeness",
        ):
            if not str(model.get(field, "")).strip():
                raise ValueError(f"{action_id}: outcome_model.{field} required")

        terms = action["terms"]
        if action_type == "cash_merger":
            cash = terms.get("cash_usd_per_share")
            if not isinstance(cash, (int, float)) or cash <= 0:
                raise ValueError(f"{action_id}: positive cash consideration required")
        elif action_type == "stock_merger":
            ratio = terms.get("successor_shares_per_subject_share")
            if not isinstance(ratio, (int, float)) or ratio <= 0:
                raise ValueError(f"{action_id}: positive successor ratio required")
            if not terms.get("successor_security_id"):
                raise ValueError(f"{action_id}: successor security required")
        elif action_type == "spinoff":
            ratio = terms.get("distributed_shares_per_subject_share")
            if terms.get("parent_continues") is not True or not ratio or ratio <= 0:
                raise ValueError(
                    f"{action_id}: continuing parent and positive distribution required"
                )
        elif action_type == "bankruptcy_cancellation":
            if terms.get("security_rights_canceled") is not True:
                raise ValueError(f"{action_id}: cancellation must be explicit")
            explicit_zero = (
                terms.get("equity_canceled_without_consideration") is True
                and terms.get("issuer_stated_no_value") is True
                and terms.get("cash_usd_per_share") == 0
            )
            if explicit_zero and (
                model["label_type"]
                != "terminal_zero_value_confirmed_no_consideration"
                or model["value_completeness"]
                != "complete_for_numeric_terminal_value"
            ):
                raise ValueError(
                    f"{action_id}: explicit zero evidence needs a complete zero label"
                )
            if not explicit_zero and (
                model["value_completeness"]
                != "insufficient_for_numeric_terminal_value"
            ):
                raise ValueError(
                    f"{action_id}: cancellation alone cannot infer a numeric zero"
                )
        elif action_type == "ticker_change":
            if (
                not terms.get("old_symbol")
                or not terms.get("new_symbol")
                or terms.get("cusip_unchanged") is not True
            ):
                raise ValueError(
                    f"{action_id}: ticker continuity requires both symbols and unchanged CUSIP"
                )

        queries = action["provider_queries"]
        if not isinstance(queries, list) or not queries:
            raise ValueError(f"{action_id}: provider queries required")
        seen_roles = set()
        for query in queries:
            role = str(query.get("role", ""))
            symbols = query.get("symbols")
            if not role or role in seen_roles:
                raise ValueError(f"{action_id}: provider query roles must be unique")
            seen_roles.add(role)
            if not isinstance(symbols, list) or not symbols:
                raise ValueError(f"{action_id}:{role}: candidate symbols required")
            dt.date.fromisoformat(query["required_session"])


def load_fixture(path: Path = DEFAULT_FIXTURE) -> Mapping[str, object]:
    fixture = json.loads(path.read_text(encoding="utf-8"))
    validate_fixture(fixture)
    return fixture


def _source_id(action: Mapping[str, object]) -> str:
    return "sec:" + str(action["source"]["accession"])


def _security_rows(action: Mapping[str, object]) -> List[Dict[str, str]]:
    subject = action["subject"]
    rows = [
        {
            "security_id": subject["security_id"],
            "issuer_cik": subject["issuer_cik"],
            "security_name": subject["security_name"],
            "identity_quality": subject["identity_quality"],
        }
    ]
    terms = action["terms"]
    if action["action_type"] == "stock_merger":
        rows.append(
            {
                "security_id": terms["successor_security_id"],
                "issuer_cik": terms["successor_security_id"].split(":")[1],
                "security_name": terms["successor_symbol"] + " successor common stock",
                "identity_quality": "cik_scoped_common_pending_security_master",
            }
        )
    elif action["action_type"] == "spinoff":
        rows.append(
            {
                "security_id": terms["distributed_security_id"],
                "issuer_cik": terms["distributed_security_id"].split(":")[1],
                "security_name": terms["distributed_symbol"] + " distributed common stock",
                "identity_quality": "cik_scoped_common_pending_security_master",
            }
        )
    return rows


def consideration_legs(action: Mapping[str, object]) -> List[Dict[str, object]]:
    action_type = action["action_type"]
    terms = action["terms"]
    subject = action["subject"]
    if action_type == "cash_merger":
        return [
            {
                "leg_type": "cash",
                "security_id": None,
                "symbol": None,
                "units": None,
                "cash": float(terms["cash_usd_per_share"]),
                "status": "fixed",
            }
        ]
    if action_type == "stock_merger":
        return [
            {
                "leg_type": "successor_stock",
                "security_id": terms["successor_security_id"],
                "symbol": terms["successor_symbol"],
                "units": float(terms["successor_shares_per_subject_share"]),
                "cash": None,
                "status": "fixed_ratio",
            }
        ]
    if action_type == "spinoff":
        return [
            {
                "leg_type": "retained_parent",
                "security_id": subject["security_id"],
                "symbol": subject["event_symbol"],
                "units": 1.0,
                "cash": None,
                "status": "continues",
            },
            {
                "leg_type": "distributed_security",
                "security_id": terms["distributed_security_id"],
                "symbol": terms["distributed_symbol"],
                "units": float(terms["distributed_shares_per_subject_share"]),
                "cash": None,
                "status": "fixed_ratio",
            },
        ]
    if action_type == "ticker_change":
        return [
            {
                "leg_type": "identity_continuity",
                "security_id": subject["security_id"],
                "symbol": terms["new_symbol"],
                "units": 1.0,
                "cash": None,
                "status": "same_security",
            }
        ]
    return [
        {
            "leg_type": "cancellation_rights",
            "security_id": None,
            "symbol": None,
            "units": None,
            "cash": (
                0.0
                if terms.get("equity_canceled_without_consideration") is True
                and terms.get("issuer_stated_no_value") is True
                else None
            ),
            "status": (
                "zero_consideration_confirmed"
                if terms.get("equity_canceled_without_consideration") is True
                and terms.get("issuer_stated_no_value") is True
                else "distribution_review_required"
            ),
        }
    ]


def resolve_terminal_value(
    action: Mapping[str, object],
    prices_by_security_id: Mapping[str, float],
) -> Dict[str, object]:
    """Resolve per-subject-share wealth from official consideration legs."""
    components = []
    total = 0.0
    unresolved = []
    for leg in consideration_legs(action):
        if leg["leg_type"] == "cash":
            value = float(leg["cash"])
        elif leg["leg_type"] == "cancellation_rights":
            if leg["status"] == "zero_consideration_confirmed":
                value = 0.0
            else:
                unresolved.append("confirmed plan distribution rights not reviewed")
                continue
        else:
            security_id = str(leg["security_id"])
            if security_id not in prices_by_security_id:
                unresolved.append("missing price for " + security_id)
                continue
            price = float(prices_by_security_id[security_id])
            if not math.isfinite(price) or price < 0:
                raise ValueError(f"invalid price for {security_id}: {price}")
            value = float(leg["units"]) * price
        total += value
        components.append(
            {
                "leg_type": leg["leg_type"],
                "security_id": leg["security_id"],
                "units_per_subject_share": leg["units"],
                "value_usd_per_subject_share": value,
            }
        )
    return {
        "logical_action_id": action["logical_action_id"],
        "label_type": action["outcome_model"]["label_type"],
        "status": "resolved" if not unresolved else "unresolved",
        "terminal_value_usd_per_subject_share": total if not unresolved else None,
        "components": components,
        "unresolved": unresolved,
        "formula": action["outcome_model"]["formula"],
    }


def resolve_terminal_return(
    action: Mapping[str, object],
    pre_effective_price: float,
    prices_by_security_id: Mapping[str, float],
) -> Dict[str, object]:
    if not math.isfinite(float(pre_effective_price)) or pre_effective_price <= 0:
        raise ValueError("pre_effective_price must be finite and positive")
    result = resolve_terminal_value(action, prices_by_security_id)
    result["pre_effective_price"] = float(pre_effective_price)
    if result["status"] == "resolved":
        result["terminal_return"] = (
            result["terminal_value_usd_per_subject_share"]
            / float(pre_effective_price)
            - 1.0
        )
    else:
        result["terminal_return"] = None
    return result


def _insert_fixture(
    con: sqlite3.Connection, fixture: Mapping[str, object]
) -> None:
    securities = {}
    for action in fixture["actions"]:
        for row in _security_rows(action):
            existing = securities.get(row["security_id"])
            if existing is not None and existing != row:
                raise ValueError(f"conflicting security row: {row['security_id']}")
            securities[row["security_id"]] = row
    con.executemany(
        "INSERT INTO securities VALUES (?, ?, ?, ?)",
        [
            (
                row["security_id"],
                row["issuer_cik"],
                row["security_name"],
                row["identity_quality"],
            )
            for row in securities.values()
        ],
    )

    for action in fixture["actions"]:
        source = action["source"]
        source_id = _source_id(action)
        source_fact = {
            "accession": source["accession"],
            "source_time": source["source_time"],
            "source_role": source["source_role"],
            "logical_action_id": action["logical_action_id"],
            "terms": action["terms"],
        }
        con.execute(
            "INSERT INTO sources VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                source_id,
                source["url"],
                source["accession"],
                source["source_time"],
                source["source_time_quality"],
                source["source_role"],
                _sha256(source_fact),
                0,
            ),
        )
        model = action["outcome_model"]
        con.execute(
            "INSERT INTO corporate_actions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                action["logical_action_id"],
                action["action_type"],
                action["subject"]["security_id"],
                action["subject"]["event_symbol"],
                source_id,
                action["effective_time"],
                action["effective_time_quality"],
                action["last_regular_trading_session"],
                model["label_type"],
                model["formula"],
                model["post_effective_return_policy"],
                model["value_completeness"],
                json.dumps(
                    action["terms"], sort_keys=True, separators=(",", ":")
                ),
            ),
        )
        for ordinal, leg in enumerate(consideration_legs(action), 1):
            con.execute(
                "INSERT INTO consideration_legs VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    action["logical_action_id"],
                    ordinal,
                    leg["leg_type"],
                    leg["security_id"],
                    leg["symbol"],
                    leg["units"],
                    leg["cash"],
                    leg["status"],
                ),
            )
        for query in action["provider_queries"]:
            con.execute(
                "INSERT INTO provider_queries VALUES (?, ?, ?, ?)",
                (
                    action["logical_action_id"],
                    query["role"],
                    json.dumps(query["symbols"], separators=(",", ":")),
                    query["required_session"],
                ),
            )
        con.execute(
            "INSERT INTO corporate_action_search VALUES (?, ?, ?, ?, ?, ?)",
            (
                action["logical_action_id"],
                action["subject"]["event_symbol"],
                action["subject"]["security_name"],
                action["action_type"],
                model["label_type"],
                model["formula"],
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
                    ("database_role", "disposable read projection"),
                    ("journal_mode_policy", "DELETE; WAL intentionally disabled"),
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
    con = sqlite3.connect(
        f"file:{Path(db_path).resolve()}?mode=ro", uri=True
    )
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def ledger_payload(
    db_path: Path = DEFAULT_DB, logical_action_id: Optional[str] = None
) -> Dict[str, object]:
    con = _connect_readonly(db_path)
    try:
        base = {
            "schema_version": int(
                con.execute("PRAGMA user_version").fetchone()[0]
            ),
            "database_role": con.execute(
                "SELECT value FROM metadata WHERE key='database_role'"
            ).fetchone()[0],
            "actions": [
                dict(row)
                for row in con.execute(
                    """
                    SELECT
                        ca.logical_action_id,
                        ca.action_type,
                        ca.event_symbol,
                        s.security_name,
                        ca.effective_time,
                        ca.label_type,
                        ca.value_completeness,
                        src.source_url,
                        src.source_time,
                        src.source_time_quality
                    FROM corporate_actions ca
                    JOIN securities s
                      ON s.security_id = ca.subject_security_id
                    JOIN sources src ON src.source_id = ca.source_id
                    ORDER BY ca.effective_time, ca.logical_action_id
                    """
                )
            ],
        }
        if logical_action_id is None:
            return base
        row = con.execute(
            """
            SELECT ca.*, s.security_name, s.issuer_cik, s.identity_quality,
                   src.source_url, src.accession, src.source_time,
                   src.source_time_quality, src.source_role,
                   src.evidence_sha256, src.raw_document_committed
            FROM corporate_actions ca
            JOIN securities s ON s.security_id = ca.subject_security_id
            JOIN sources src ON src.source_id = ca.source_id
            WHERE ca.logical_action_id = ?
            """,
            (logical_action_id,),
        ).fetchone()
        if row is None:
            raise KeyError(logical_action_id)
        detail = dict(row)
        detail["terms"] = json.loads(detail.pop("terms_json"))
        detail["legs"] = [
            dict(leg)
            for leg in con.execute(
                """
                SELECT leg_ordinal, leg_type, security_id, symbol,
                       units_per_subject_share, cash_usd_per_subject_share,
                       leg_status
                FROM consideration_legs
                WHERE logical_action_id = ?
                ORDER BY leg_ordinal
                """,
                (logical_action_id,),
            )
        ]
        detail["provider_queries"] = [
            {
                **dict(query),
                "candidate_symbols": json.loads(
                    query["candidate_symbols_json"]
                ),
            }
            for query in con.execute(
                """
                SELECT role, candidate_symbols_json, required_session
                FROM provider_queries
                WHERE logical_action_id = ?
                ORDER BY role
                """,
                (logical_action_id,),
            )
        ]
        for query in detail["provider_queries"]:
            query.pop("candidate_symbols_json")
        base["detail"] = detail
        return base
    finally:
        con.close()


def render_html(payload: Mapping[str, object]) -> str:
    action_rows = []
    for action in payload["actions"]:
        action_rows.append(
            "<tr>"
            f"<td><a href=\"/corporate-actions?id={html.escape(action['logical_action_id'])}\">"
            f"{html.escape(action['event_symbol'])}</a></td>"
            f"<td>{html.escape(action['action_type'])}</td>"
            f"<td>{html.escape(action['effective_time'])}</td>"
            f"<td>{html.escape(action['label_type'])}</td>"
            f"<td>{html.escape(action['value_completeness'])}</td>"
            "</tr>"
        )
    detail_html = ""
    if payload.get("detail"):
        detail = payload["detail"]
        legs = "".join(
            "<tr>"
            f"<td>{html.escape(leg['leg_type'])}</td>"
            f"<td>{html.escape(str(leg['symbol'] or '—'))}</td>"
            f"<td>{html.escape(str(leg['units_per_subject_share'] if leg['units_per_subject_share'] is not None else '—'))}</td>"
            f"<td>{html.escape(str(leg['cash_usd_per_subject_share'] if leg['cash_usd_per_subject_share'] is not None else '—'))}</td>"
            "</tr>"
            for leg in detail["legs"]
        )
        detail_html = (
            f"<section><h2>{html.escape(detail['event_symbol'])} · "
            f"{html.escape(detail['action_type'])}</h2>"
            f"<p>{html.escape(detail['outcome_formula'])}</p>"
            f"<p><a href=\"{html.escape(detail['source_url'])}\">official source</a> · "
            f"{html.escape(detail['source_time'])} "
            f"({html.escape(detail['source_time_quality'])})</p>"
            "<table><thead><tr><th>Leg</th><th>Symbol</th><th>Units</th>"
            f"<th>Cash USD</th></tr></thead><tbody>{legs}</tbody></table></section>"
        )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport"
content="width=device-width,initial-scale=1"><title>MONAD corporate actions</title>
<style>
body{{max-width:1100px;margin:32px auto;padding:0 18px;background:#080b12;color:#edf2ff;
font:14px system-ui,sans-serif}}a{{color:#85b7eb}}section{{background:#101622;
border:1px solid #263043;border-radius:10px;padding:14px;margin:12px 0}}
h1,h2{{margin:0 0 8px}}p{{color:#aebbd0}}table{{width:100%;border-collapse:collapse}}
th,td{{text-align:left;padding:7px;border-bottom:1px solid #263043}}
.note{{padding:10px;border-left:3px solid #fac775;color:#c8d1e2}}
</style></head><body><h1>Corporate-action outcome ledger</h1>
<p class="note">Outcome labels, not a trading signal. Versioned fixtures remain
authoritative; raw SEC documents and vendor price panels are not published.</p>
<section><table><thead><tr><th>Symbol</th><th>Action</th><th>Effective</th>
<th>Outcome label</th><th>Completeness</th></tr></thead>
<tbody>{''.join(action_rows)}</tbody></table></section>{detail_html}
</body></html>"""


def _default_downloader(symbol: str, start: str, end: str):
    import yfinance as yf

    yf.set_tz_cache_location("/tmp/monad-ca-yf-cache")
    return yf.download(
        symbol,
        start=start,
        end=end,
        auto_adjust=False,
        actions=True,
        progress=False,
        threads=False,
    )


def _frame_fingerprint(frame) -> str:
    import pandas as pd

    normalized = frame.sort_index().sort_index(axis=1)
    hashed = pd.util.hash_pandas_object(
        normalized, index=True
    ).values.tobytes()
    return hashlib.sha256(hashed).hexdigest()


def _valid_frame_rows(frame):
    if frame is None or frame.empty:
        return frame
    return frame.dropna(how="all")


def audit_provider_coverage(
    fixture: Mapping[str, object],
    downloader: Optional[Callable[[str, str, str], object]] = None,
) -> Dict[str, object]:
    """Check whether a current free provider can satisfy each outcome price role."""
    downloader = downloader or _default_downloader
    actions_out = []
    all_queries = 0
    resolved_queries = 0
    for action in fixture["actions"]:
        query_rows = []
        for query in action["provider_queries"]:
            all_queries += 1
            required = dt.date.fromisoformat(query["required_session"])
            start = (required - dt.timedelta(days=12)).isoformat()
            end = (required + dt.timedelta(days=13)).isoformat()
            attempts = []
            selected = None
            for symbol in query["symbols"]:
                try:
                    frame = _valid_frame_rows(downloader(symbol, start, end))
                    row_count = 0 if frame is None else len(frame)
                    sessions = (
                        set(frame.index.strftime("%Y-%m-%d"))
                        if row_count
                        else set()
                    )
                    has_required = query["required_session"] in sessions
                    attempt = {
                        "symbol": symbol,
                        "rows": row_count,
                        "first_session": (
                            frame.index.min().strftime("%Y-%m-%d")
                            if row_count
                            else None
                        ),
                        "last_session": (
                            frame.index.max().strftime("%Y-%m-%d")
                            if row_count
                            else None
                        ),
                        "required_session_present": has_required,
                        "normalized_input_sha256": (
                            _frame_fingerprint(frame) if row_count else None
                        ),
                        "error": None,
                    }
                except Exception as exc:
                    attempt = {
                        "symbol": symbol,
                        "rows": 0,
                        "first_session": None,
                        "last_session": None,
                        "required_session_present": False,
                        "normalized_input_sha256": None,
                        "error": type(exc).__name__ + ": " + str(exc)[:200],
                    }
                attempts.append(attempt)
                if attempt["required_session_present"]:
                    selected = symbol
                    break
            if selected is not None:
                resolved_queries += 1
            query_rows.append(
                {
                    "role": query["role"],
                    "required_session": query["required_session"],
                    "resolved": selected is not None,
                    "selected_symbol": selected,
                    "attempts": attempts,
                }
            )
        actions_out.append(
            {
                "logical_action_id": action["logical_action_id"],
                "event_symbol": action["subject"]["event_symbol"],
                "action_type": action["action_type"],
                "roles_required": len(query_rows),
                "roles_resolved": sum(row["resolved"] for row in query_rows),
                "complete": all(row["resolved"] for row in query_rows),
                "queries": query_rows,
            }
        )
    decision_payload = [
        {
            "logical_action_id": action["logical_action_id"],
            "queries": [
                {
                    "role": query["role"],
                    "required_session": query["required_session"],
                    "resolved": query["resolved"],
                    "selected_symbol": query["selected_symbol"],
                }
                for query in action["queries"]
            ],
        }
        for action in actions_out
    ]
    return {
        "artifact": "CA-00 free-provider inactive-security coverage audit",
        "schema_version": 1,
        "fixture_id": fixture["fixture_id"],
        "retrieved_at_utc": dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat(),
        "provider": "Yahoo Finance via yfinance",
        "raw_data_committed": False,
        "required_price_roles": all_queries,
        "resolved_price_roles": resolved_queries,
        "role_coverage_rate": (
            resolved_queries / all_queries if all_queries else None
        ),
        "actions_complete": sum(row["complete"] for row in actions_out),
        "actions_total": len(actions_out),
        "coverage_decision_sha256": _sha256(decision_payload),
        "actions": actions_out,
        "limitations": [
            "availability from one free current-symbol provider is not proof that a security never traded",
            "coverage metadata do not establish price correctness, corporate-action adjustment correctness, or redistribution rights",
            "exact vendor fingerprints may change across refreshes without changing coverage",
            "a missing old ticker requires a rights-cleared inactive-security source or a retained historical snapshot",
        ],
    }


def _fixture_action(
    fixture: Mapping[str, object], logical_action_id: str
) -> Mapping[str, object]:
    for action in fixture["actions"]:
        if action["logical_action_id"] == logical_action_id:
            return action
    raise KeyError(logical_action_id)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build")
    build.add_argument("--db", type=Path, default=DEFAULT_DB)
    build.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)

    summary = sub.add_parser("summary")
    summary.add_argument("--db", type=Path, default=DEFAULT_DB)
    summary.add_argument("--id")

    outcome = sub.add_parser("outcome")
    outcome.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    outcome.add_argument("--id", required=True)
    outcome.add_argument("--pre-price", type=float)
    outcome.add_argument(
        "--price",
        action="append",
        default=[],
        metavar="SECURITY_ID=PRICE",
    )

    coverage = sub.add_parser("coverage")
    coverage.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    coverage.add_argument(
        "--summary-only",
        action="store_true",
        help="omit attempt-level hashes while retaining role decisions",
    )

    page = sub.add_parser("html")
    page.add_argument("--db", type=Path, default=DEFAULT_DB)
    page.add_argument("--id")

    args = parser.parse_args(argv)
    if args.command == "build":
        path = build_database(args.db, args.fixture)
        print(path)
        return 0
    if args.command == "summary":
        print(json.dumps(ledger_payload(args.db, args.id), indent=2, sort_keys=True))
        return 0
    if args.command == "coverage":
        result = audit_provider_coverage(load_fixture(args.fixture))
        if args.summary_only:
            result["actions"] = [
                {
                    "logical_action_id": action["logical_action_id"],
                    "event_symbol": action["event_symbol"],
                    "action_type": action["action_type"],
                    "roles_required": action["roles_required"],
                    "roles_resolved": action["roles_resolved"],
                    "complete": action["complete"],
                    "queries": [
                        {
                            "role": query["role"],
                            "required_session": query["required_session"],
                            "resolved": query["resolved"],
                            "selected_symbol": query["selected_symbol"],
                        }
                        for query in action["queries"]
                    ],
                }
                for action in result["actions"]
            ]
        print(
            json.dumps(
                result,
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if args.command == "html":
        print(render_html(ledger_payload(args.db, args.id)))
        return 0
    fixture = load_fixture(args.fixture)
    action = _fixture_action(fixture, args.id)
    prices: Dict[str, float] = {}
    for item in args.price:
        security_id, sep, value = item.rpartition("=")
        if not sep or not security_id:
            parser.error("--price must be SECURITY_ID=PRICE")
        prices[security_id] = float(value)
    result = (
        resolve_terminal_return(action, args.pre_price, prices)
        if args.pre_price is not None
        else resolve_terminal_value(action, prices)
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())

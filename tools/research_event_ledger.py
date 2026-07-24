#!/usr/bin/env python3
"""Build and query MONAD's disposable, revision-aware research-event ledger.

Versioned JSON fixtures are authoritative. The SQLite file is a rebuildable read
model and MUST live outside the repository (default: /tmp). Event knowledge is
append-only: later revisions add or supersede event versions; they never update an
older fact in place.

The schema also reserves a quarantined suggestion inbox. This tool intentionally
does not expose a public suggestion writer. Anonymous writes, rate limiting, and
moderation require a separate deployment/security decision.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence


REPO = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = (
    REPO / "docs" / "research" / "data" / "ix00_ndx_2023_revision_fixture.json"
)
DEFAULT_DB = Path(tempfile.gettempdir()) / "monad-research-events.sqlite3"
SCHEMA_VERSION = 1


SCHEMA = """
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = DELETE;
PRAGMA synchronous = FULL;

CREATE TABLE metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
) STRICT;

CREATE TABLE batches (
    batch_id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    index_name TEXT NOT NULL,
    index_symbol TEXT NOT NULL,
    implementation_session TEXT NOT NULL,
    implementation_time_quality TEXT NOT NULL,
    effective_session TEXT NOT NULL,
    rights_tier TEXT NOT NULL,
    fixture_id TEXT NOT NULL,
    fixture_sha256 TEXT NOT NULL
) STRICT;

CREATE TABLE source_documents (
    source_id TEXT PRIMARY KEY,
    source_url TEXT NOT NULL,
    published_at TEXT NOT NULL,
    source_time_quality TEXT NOT NULL,
    evidence_sha256 TEXT NOT NULL,
    hash_scope TEXT NOT NULL,
    raw_document_committed INTEGER NOT NULL DEFAULT 0
        CHECK (raw_document_committed IN (0, 1))
) STRICT;

CREATE TABLE revisions (
    revision_id TEXT PRIMARY KEY,
    batch_id TEXT NOT NULL REFERENCES batches(batch_id),
    ordinal INTEGER NOT NULL CHECK (ordinal > 0),
    revision_kind TEXT NOT NULL,
    published_at TEXT NOT NULL,
    first_tradable_at TEXT NOT NULL,
    source_id TEXT NOT NULL REFERENCES source_documents(source_id),
    supersedes_revision_id TEXT REFERENCES revisions(revision_id),
    UNIQUE (batch_id, ordinal)
) STRICT;

CREATE TABLE securities (
    security_id TEXT PRIMARY KEY,
    security_name TEXT NOT NULL,
    identity_quality TEXT NOT NULL
) STRICT;

CREATE TABLE security_symbols (
    security_id TEXT NOT NULL REFERENCES securities(security_id),
    symbol TEXT NOT NULL,
    venue TEXT NOT NULL DEFAULT 'NASDAQ',
    valid_from TEXT NOT NULL DEFAULT '',
    valid_to TEXT,
    PRIMARY KEY (security_id, symbol, valid_from)
) STRICT;

CREATE TABLE membership_event_versions (
    event_version_id TEXT PRIMARY KEY,
    logical_event_id TEXT NOT NULL,
    revision_id TEXT NOT NULL REFERENCES revisions(revision_id),
    security_id TEXT NOT NULL REFERENCES securities(security_id),
    announced_symbol TEXT NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('addition', 'deletion')),
    transition_type TEXT NOT NULL,
    operation TEXT NOT NULL CHECK (operation IN ('assert', 'retract')),
    reason_code TEXT NOT NULL,
    supersedes_event_version_id TEXT
        REFERENCES membership_event_versions(event_version_id),
    UNIQUE (logical_event_id, revision_id)
) STRICT;

CREATE INDEX event_versions_revision_idx
    ON membership_event_versions(revision_id);
CREATE INDEX event_versions_security_idx
    ON membership_event_versions(security_id);

CREATE VIRTUAL TABLE event_search USING fts5(
    event_version_id UNINDEXED,
    batch_id UNINDEXED,
    symbol,
    security_name,
    action,
    transition_type,
    reason_code,
    tokenize = 'unicode61'
);

CREATE TABLE suggestions (
    suggestion_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    title TEXT NOT NULL CHECK (length(title) BETWEEN 8 AND 160),
    body TEXT NOT NULL CHECK (length(body) BETWEEN 20 AND 4000),
    submitter_hash TEXT,
    moderation_state TEXT NOT NULL DEFAULT 'pending'
        CHECK (moderation_state IN ('pending', 'accepted', 'rejected', 'spam')),
    converted_graph_id TEXT,
    CHECK (converted_graph_id IS NULL OR converted_graph_id GLOB '[FHED][0-9]*')
) STRICT;

CREATE TABLE suggestion_events (
    suggestion_event_id TEXT PRIMARY KEY,
    suggestion_id TEXT NOT NULL REFERENCES suggestions(suggestion_id),
    sequence INTEGER NOT NULL CHECK (sequence > 0),
    event_type TEXT NOT NULL
        CHECK (event_type IN ('submitted', 'accepted', 'rejected', 'marked_spam', 'converted')),
    actor TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    UNIQUE (suggestion_id, sequence)
) STRICT;

CREATE TRIGGER suggestions_no_update
BEFORE UPDATE ON suggestions
BEGIN
    SELECT RAISE(ABORT, 'suggestions are append-only; record a suggestion_event');
END;

CREATE TRIGGER suggestions_no_delete
BEFORE DELETE ON suggestions
BEGIN
    SELECT RAISE(ABORT, 'suggestions cannot be deleted from the audit ledger');
END;

CREATE TRIGGER suggestion_events_no_update
BEFORE UPDATE ON suggestion_events
BEGIN
    SELECT RAISE(ABORT, 'suggestion_events are append-only');
END;

CREATE TRIGGER suggestion_events_no_delete
BEFORE DELETE ON suggestion_events
BEGIN
    SELECT RAISE(ABORT, 'suggestion_events cannot be deleted');
END;

CREATE VIEW latest_membership_events AS
WITH ranked AS (
    SELECT
        ev.*,
        r.batch_id,
        r.ordinal,
        ROW_NUMBER() OVER (
            PARTITION BY ev.logical_event_id
            ORDER BY r.ordinal DESC, ev.event_version_id DESC
        ) AS version_rank
    FROM membership_event_versions ev
    JOIN revisions r ON r.revision_id = ev.revision_id
)
SELECT *
FROM ranked
WHERE version_rank = 1 AND operation = 'assert';
"""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _parse_timestamp(value: str, field: str) -> dt.datetime:
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field}: invalid ISO timestamp {value!r}") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field}: timezone offset required")
    return parsed


def _is_within(path: Path, parent: Path) -> bool:
    try:
        return os.path.commonpath([str(path.resolve()), str(parent.resolve())]) == str(
            parent.resolve()
        )
    except ValueError:
        return False


def validate_fixture(fixture: Mapping[str, object]) -> None:
    if fixture.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            f"fixture schema_version must be {SCHEMA_VERSION}, got "
            f"{fixture.get('schema_version')!r}"
        )
    if not str(fixture.get("fixture_id", "")).strip():
        raise ValueError("fixture_id is required")
    batch = fixture.get("batch")
    revisions = fixture.get("revisions")
    if not isinstance(batch, dict) or not isinstance(revisions, list) or not revisions:
        raise ValueError("fixture requires batch object and non-empty revisions array")

    required_batch = {
        "batch_id",
        "provider",
        "index_name",
        "index_symbol",
        "implementation_session",
        "implementation_time_quality",
        "effective_session",
        "rights_tier",
    }
    missing_batch = sorted(required_batch - set(batch))
    if missing_batch:
        raise ValueError(f"batch missing fields: {missing_batch}")

    seen_revision_ids = set()
    seen_ordinals = set()
    seen_version_pairs = set()
    last_published: Optional[dt.datetime] = None
    for revision in revisions:
        if not isinstance(revision, dict):
            raise ValueError("each revision must be an object")
        required_revision = {
            "revision_id",
            "ordinal",
            "revision_kind",
            "published_at",
            "first_tradable_at",
            "source_url",
            "source_time_quality",
            "hash_scope",
            "events",
        }
        missing = sorted(required_revision - set(revision))
        if missing:
            raise ValueError(f"revision missing fields: {missing}")
        revision_id = str(revision["revision_id"])
        ordinal = int(revision["ordinal"])
        if revision_id in seen_revision_ids or ordinal in seen_ordinals:
            raise ValueError("revision_id and ordinal must be unique")
        seen_revision_ids.add(revision_id)
        seen_ordinals.add(ordinal)
        published = _parse_timestamp(str(revision["published_at"]), "published_at")
        first_tradable = _parse_timestamp(
            str(revision["first_tradable_at"]), "first_tradable_at"
        )
        if first_tradable <= published:
            raise ValueError(f"{revision_id}: first_tradable_at must follow publication")
        if last_published is not None and published <= last_published:
            raise ValueError("revision publication order must increase")
        last_published = published
        supersedes = revision.get("supersedes_revision_id")
        if supersedes is not None and supersedes not in seen_revision_ids:
            raise ValueError(
                f"{revision_id}: supersedes_revision_id must reference an earlier revision"
            )
        events = revision["events"]
        if not isinstance(events, list) or not events:
            raise ValueError(f"{revision_id}: events must be non-empty")
        for event in events:
            required_event = {
                "logical_event_id",
                "security_id",
                "security_name",
                "identity_quality",
                "announced_symbol",
                "action",
                "transition_type",
                "operation",
                "reason_code",
            }
            missing_event = sorted(required_event - set(event))
            if missing_event:
                raise ValueError(f"{revision_id}: event missing {missing_event}")
            if event["action"] not in {"addition", "deletion"}:
                raise ValueError(f"{revision_id}: invalid action {event['action']!r}")
            if event["operation"] not in {"assert", "retract"}:
                raise ValueError(
                    f"{revision_id}: invalid operation {event['operation']!r}"
                )
            pair = (event["logical_event_id"], revision_id)
            if pair in seen_version_pairs:
                raise ValueError(f"duplicate event version pair {pair}")
            seen_version_pairs.add(pair)

    if seen_ordinals != set(range(1, len(revisions) + 1)):
        raise ValueError("revision ordinals must be contiguous from 1")


def load_fixture(path: Path) -> Mapping[str, object]:
    fixture = json.loads(path.read_text(encoding="utf-8"))
    validate_fixture(fixture)
    return fixture


def _connect(path: Path, readonly: bool = False) -> sqlite3.Connection:
    if readonly:
        uri = f"file:{path.resolve()}?mode=ro"
        con = sqlite3.connect(uri, uri=True)
    else:
        con = sqlite3.connect(str(path))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def _insert_fixture(con: sqlite3.Connection, fixture: Mapping[str, object]) -> None:
    batch = fixture["batch"]
    fixture_sha = _sha256(fixture)
    con.execute(
        """
        INSERT INTO batches VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            batch["batch_id"],
            batch["provider"],
            batch["index_name"],
            batch["index_symbol"],
            batch["implementation_session"],
            batch["implementation_time_quality"],
            batch["effective_session"],
            batch["rights_tier"],
            fixture["fixture_id"],
            fixture_sha,
        ),
    )

    for revision in fixture["revisions"]:
        source_id = f"source:{revision['revision_id']}"
        evidence_sha = _sha256(
            {
                "published_at": revision["published_at"],
                "source_url": revision["source_url"],
                "events": revision["events"],
            }
        )
        con.execute(
            """
            INSERT INTO source_documents(
                source_id, source_url, published_at, source_time_quality,
                evidence_sha256, hash_scope, raw_document_committed
            ) VALUES (?, ?, ?, ?, ?, ?, 0)
            """,
            (
                source_id,
                revision["source_url"],
                revision["published_at"],
                revision["source_time_quality"],
                evidence_sha,
                revision["hash_scope"],
            ),
        )
        con.execute(
            """
            INSERT INTO revisions(
                revision_id, batch_id, ordinal, revision_kind, published_at,
                first_tradable_at, source_id, supersedes_revision_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                revision["revision_id"],
                batch["batch_id"],
                revision["ordinal"],
                revision["revision_kind"],
                revision["published_at"],
                revision["first_tradable_at"],
                source_id,
                revision.get("supersedes_revision_id"),
            ),
        )
        for sequence, event in enumerate(revision["events"], start=1):
            con.execute(
                """
                INSERT INTO securities(security_id, security_name, identity_quality)
                VALUES (?, ?, ?)
                ON CONFLICT(security_id) DO NOTHING
                """,
                (
                    event["security_id"],
                    event["security_name"],
                    event["identity_quality"],
                ),
            )
            con.execute(
                """
                INSERT INTO security_symbols(
                    security_id, symbol, venue, valid_from, valid_to
                ) VALUES (?, ?, 'NASDAQ', '', NULL)
                ON CONFLICT DO NOTHING
                """,
                (event["security_id"], event["announced_symbol"]),
            )
            version_id = f"{revision['revision_id']}:v{sequence:03d}"
            con.execute(
                """
                INSERT INTO membership_event_versions(
                    event_version_id, logical_event_id, revision_id, security_id,
                    announced_symbol, action, transition_type, operation, reason_code,
                    supersedes_event_version_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    version_id,
                    event["logical_event_id"],
                    revision["revision_id"],
                    event["security_id"],
                    event["announced_symbol"],
                    event["action"],
                    event["transition_type"],
                    event["operation"],
                    event["reason_code"],
                    event.get("supersedes_event_version_id"),
                ),
            )
            con.execute(
                """
                INSERT INTO event_search VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    version_id,
                    batch["batch_id"],
                    event["announced_symbol"],
                    event["security_name"],
                    event["action"],
                    event["transition_type"],
                    event["reason_code"],
                ),
            )


def build_database(db_path: Path, fixture_paths: Sequence[Path]) -> Path:
    target = db_path.expanduser().resolve()
    if _is_within(target, REPO):
        raise ValueError(
            "refusing to create a SQLite database inside the repository; "
            "use /tmp or another runtime-data directory"
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent)
    )
    os.close(fd)
    temp_path = Path(temporary)
    try:
        con = _connect(temp_path)
        try:
            con.executescript(SCHEMA)
            con.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            fixtures = [load_fixture(path) for path in fixture_paths]
            for fixture in fixtures:
                _insert_fixture(con, fixture)
            built_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
            con.executemany(
                "INSERT INTO metadata(key, value) VALUES (?, ?)",
                [
                    ("schema_version", str(SCHEMA_VERSION)),
                    ("built_at_utc", built_at),
                    ("fixture_count", str(len(fixtures))),
                    ("journal_mode_policy", "DELETE; WAL intentionally disabled"),
                ],
            )
            con.commit()
            violations = list(con.execute("PRAGMA foreign_key_check"))
            if violations:
                raise ValueError(f"foreign-key violations: {violations}")
        finally:
            con.close()
        os.replace(str(temp_path), str(target))
    except Exception:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass
        raise
    return target


def list_batches(db_path: Path) -> List[Dict[str, object]]:
    con = _connect(db_path, readonly=True)
    try:
        rows = con.execute(
            """
            SELECT
                b.*,
                COUNT(DISTINCT r.revision_id) AS revision_count,
                COUNT(ev.event_version_id) AS event_version_count
            FROM batches b
            JOIN revisions r ON r.batch_id = b.batch_id
            JOIN membership_event_versions ev ON ev.revision_id = r.revision_id
            GROUP BY b.batch_id
            ORDER BY b.effective_session, b.batch_id
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        con.close()


def revision_timeline(db_path: Path, batch_id: str) -> List[Dict[str, object]]:
    con = _connect(db_path, readonly=True)
    try:
        revisions = con.execute(
            """
            SELECT
                r.*, s.source_url, s.source_time_quality, s.evidence_sha256,
                s.hash_scope, s.raw_document_committed
            FROM revisions r
            JOIN source_documents s ON s.source_id = r.source_id
            WHERE r.batch_id = ?
            ORDER BY r.ordinal
            """,
            (batch_id,),
        ).fetchall()
        out = []
        for revision in revisions:
            item = dict(revision)
            events = con.execute(
                """
                SELECT
                    ev.event_version_id, ev.logical_event_id, ev.announced_symbol,
                    sec.security_name, sec.identity_quality, ev.action,
                    ev.transition_type, ev.operation, ev.reason_code
                FROM membership_event_versions ev
                JOIN securities sec ON sec.security_id = ev.security_id
                WHERE ev.revision_id = ?
                ORDER BY ev.action, ev.announced_symbol
                """,
                (revision["revision_id"],),
            ).fetchall()
            item["introduced_events"] = [dict(row) for row in events]
            out.append(item)
        return out
    finally:
        con.close()


def events_as_of(
    db_path: Path, batch_id: str, revision_id: Optional[str] = None
) -> Dict[str, object]:
    con = _connect(db_path, readonly=True)
    try:
        if revision_id is None:
            revision = con.execute(
                """
                SELECT * FROM revisions
                WHERE batch_id = ?
                ORDER BY ordinal DESC LIMIT 1
                """,
                (batch_id,),
            ).fetchone()
        else:
            revision = con.execute(
                """
                SELECT * FROM revisions
                WHERE batch_id = ? AND revision_id = ?
                """,
                (batch_id, revision_id),
            ).fetchone()
        if revision is None:
            raise KeyError(f"unknown batch/revision: {batch_id}/{revision_id or 'latest'}")
        rows = con.execute(
            """
            WITH eligible AS (
                SELECT
                    ev.*, sec.security_name, sec.identity_quality, r.ordinal,
                    ROW_NUMBER() OVER (
                        PARTITION BY ev.logical_event_id
                        ORDER BY r.ordinal DESC, ev.event_version_id DESC
                    ) AS version_rank
                FROM membership_event_versions ev
                JOIN revisions r ON r.revision_id = ev.revision_id
                JOIN securities sec ON sec.security_id = ev.security_id
                WHERE r.batch_id = ? AND r.ordinal <= ?
            )
            SELECT
                event_version_id, logical_event_id, revision_id, security_id,
                security_name, identity_quality, announced_symbol, action,
                transition_type, reason_code
            FROM eligible
            WHERE version_rank = 1 AND operation = 'assert'
            ORDER BY action, announced_symbol
            """,
            (batch_id, revision["ordinal"]),
        ).fetchall()
        return {
            "batch_id": batch_id,
            "as_of_revision_id": revision["revision_id"],
            "as_of_ordinal": revision["ordinal"],
            "published_at": revision["published_at"],
            "first_tradable_at": revision["first_tradable_at"],
            "events": [dict(row) for row in rows],
        }
    finally:
        con.close()


def ledger_payload(
    db_path: Path,
    batch_id: Optional[str] = None,
    revision_id: Optional[str] = None,
) -> Dict[str, object]:
    batches = list_batches(db_path)
    payload: Dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "database_role": "disposable projection; versioned fixtures are authoritative",
        "batches": batches,
    }
    if batch_id is not None:
        payload["timeline"] = revision_timeline(db_path, batch_id)
        payload["as_of"] = events_as_of(db_path, batch_id, revision_id)
    return payload


def render_events_html(payload: Mapping[str, object]) -> str:
    def esc(value: object) -> str:
        return html.escape(str(value), quote=True)

    batch_sections = []
    for batch in payload.get("batches", []):
        batch_sections.append(
            "<article><h2>{}</h2><p>{} · {} revisions · {} event versions · "
            "implementation {} · effective {}</p></article>".format(
                esc(batch["batch_id"]),
                esc(batch["index_name"]),
                esc(batch["revision_count"]),
                esc(batch["event_version_count"]),
                esc(batch["implementation_session"]),
                esc(batch["effective_session"]),
            )
        )
    timeline_sections = []
    for revision in payload.get("timeline", []):
        rows = "".join(
            "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                esc(event["announced_symbol"]),
                esc(event["action"]),
                esc(event["transition_type"]),
                esc(event["reason_code"]),
            )
            for event in revision["introduced_events"]
        )
        timeline_sections.append(
            "<section><h3>Revision {} · {}</h3><p>Published {} · tradable {} · "
            "<a href=\"{}\">source</a></p><table><thead><tr><th>Symbol</th>"
            "<th>Action</th><th>Transition</th><th>Reason</th></tr></thead>"
            "<tbody>{}</tbody></table></section>".format(
                esc(revision["ordinal"]),
                esc(revision["revision_kind"]),
                esc(revision["published_at"]),
                esc(revision["first_tradable_at"]),
                esc(revision["source_url"]),
                rows,
            )
        )
    as_of = payload.get("as_of")
    as_of_html = ""
    if as_of:
        rows = "".join(
            "<tr><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                esc(event["announced_symbol"]),
                esc(event["action"]),
                esc(event["revision_id"]),
            )
            for event in as_of["events"]
        )
        as_of_html = (
            "<section><h2>Knowledge as of {}</h2><table><thead><tr><th>Symbol</th>"
            "<th>Action</th><th>First asserted in</th></tr></thead><tbody>{}</tbody>"
            "</table></section>"
        ).format(esc(as_of["as_of_revision_id"]), rows)
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport"
content="width=device-width,initial-scale=1"><title>MONAD research events</title>
<style>
body{{max-width:1100px;margin:32px auto;padding:0 18px;background:#080b12;color:#edf2ff;
font:14px system-ui,sans-serif}}a{{color:#85b7eb}}article,section{{background:#101622;
border:1px solid #263043;border-radius:10px;padding:14px;margin:12px 0}}
h1,h2,h3{{margin:0 0 8px}}p{{color:#aebbd0}}table{{width:100%;border-collapse:collapse}}
th,td{{text-align:left;padding:7px;border-bottom:1px solid #263043}}
code{{color:#fac775}}.note{{padding:10px;border-left:3px solid #fac775;color:#c8d1e2}}
</style></head><body><h1>MONAD research-event ledger</h1>
<p class="note">Disposable SQLite projection. Versioned fixtures remain authoritative;
licensed source documents and raw databases are not published.</p>{}{}{}
</body></html>""".format(
        "".join(batch_sections), "".join(timeline_sections), as_of_html
    )


def _json_print(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--db", type=Path, default=DEFAULT_DB)
    build.add_argument(
        "--fixture", type=Path, action="append", default=None,
        help="versioned fixture; repeat for several (default: 2023 Nasdaq revision)",
    )
    for name in ("summary", "timeline", "as-of", "html"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--db", type=Path, default=DEFAULT_DB)
        if name in {"timeline", "as-of", "html"}:
            cmd.add_argument("--batch", default="ndx-2023-12")
        if name in {"as-of", "html"}:
            cmd.add_argument("--revision")
    args = parser.parse_args(argv)

    if args.command == "build":
        fixtures = args.fixture or [DEFAULT_FIXTURE]
        path = build_database(args.db, fixtures)
        print(path)
    elif args.command == "summary":
        _json_print(ledger_payload(args.db))
    elif args.command == "timeline":
        _json_print(revision_timeline(args.db, args.batch))
    elif args.command == "as-of":
        _json_print(events_as_of(args.db, args.batch, args.revision))
    elif args.command == "html":
        print(
            render_events_html(
                ledger_payload(args.db, args.batch, args.revision)
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

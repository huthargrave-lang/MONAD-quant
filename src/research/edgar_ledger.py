"""
MONAD Quant — the EDGAR ledger: an accession-scoped, append-only record of SEC 10-K/10-Q
submissions and their SGML headers, written where EDGAR is reachable (GitHub Actions),
verified like every other append-only store in src/research/, and frozen into
content-addressed extracts a study can cite (docs/EDGAR_LEDGER.md; the debate record is
docs/research/EDGAR_LEDGER_QUESTION.md; FD-00 is docs/research/FD00_sec_filing_delta_lab.md).

What it holds, per ET business day, on the ``edgar-ledger`` git branch:

  rows/YYYY-MM.jsonl     prefix-only   ``filing`` / ``revision`` / ``seal`` rows (by index day)
  inputs/YYYY-MM.jsonl   prefix-only   one line per fetched URL: status, bytes, sha256, when
  probe/PROBE-*.jsonl    identical     the Step-0 probe (P0 runner, P1 header, P2 FSDS)
  fsds/sub-YYYYqN.jsonl.gz identical   Financial Statement Data Sets ``sub.txt`` extract
  README.md              editable      a copy of docs/EDGAR_LEDGER.md at bootstrap

No filing body and no raw index or header bytes are committed: every row names a public URL
and the sha-256 of the bytes it saw, so a reader can re-fetch and re-hash. Header fields are
WHITELISTED (acceptance, filed, date-as-of-change, period, private-to-public, release date,
and the role blocks' CIK, name and SIC); addresses, phone numbers and tax ids are on a
DENYLIST the verifier enforces on every key of every row.

The clock. ``tradable_time`` is PT-01's "one function, one consumer": FD-00's historical
daily default (``FD00:127``): the first regular-session open strictly after the acceptance,
except a premarket acceptance (before 09:30 ET on a session day) trades at that day's open.
``clock_class`` is the fixture enum (``second`` | ``legacy_midnight_display`` |
``not_public_event_time`` | null); a private-to-public release never uses its original
acceptance. The eight FD-00 fixtures run through this parser in tests/test_edgar_ledger.py.

Fail-closed. ``daily`` and ``fsds`` refuse to run until a committed ``probe_summary`` with
P0 = PASS and a header source decided by P1 exists on the branch; the only pre-probe write is
the bootstrap README. ``freeze`` enumerates every ET weekday of its window and refuses one
with no seal, an incomplete seal, or a header-coverage ratio under 0.95 unless told
``allow_partial`` — which is then written into the manifest with ``partial_days[]`` and
``missing_seal_days[]``.

Fair access. Every request carries the ``SEC_USER_AGENT`` contact (refused without an ``@``
or at an RFC 2606 reserved domain), is spaced at least ``MIN_INTERVAL`` seconds from the
last, and retries with bounded backoff. All network goes through ``Fetcher`` with an
injectable ``get`` (the bdc_text_nav pattern), so every test here is offline.

Stdlib only at runtime; ``trials.verify_history`` and ``data_store.write`` are the shared
append-only and content-addressed primitives.
"""
from __future__ import annotations

import csv
import datetime as _dt
import gzip
import hashlib
import io
import json
import os
import re
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, NamedTuple
from zoneinfo import ZoneInfo

from src.research import data_store, nyse_calendar, trials
from src.research.trials import LedgerError, canonical_json

# ── constants ────────────────────────────────────────────────────────────────
SCHEMA_VERSION = 1
PARSER_VERSION = "edgar_ledger.v1"
TZ_RULE = "America/New_York#v1"
EASTERN = ZoneInfo("America/New_York")
PREFIX = "EDGARLEDGER"
FSDS_PREFIX = "EDGARFSDS"
LEDGER_REL = Path("data/edgar_ledger")
LEDGER_DIR_ENV = "MONAD_EDGAR_LEDGER_DIR"
BRANCH = "edgar-ledger"

#: SEC asks for a declared agent and caps access at ten requests a second; the collector
#: is "materially slower than the cap" (FD00:85-89). Four other fetchers space at 0.12 s.
MIN_INTERVAL = 0.25
MAX_RETRIES = 3
BACKOFF_BASE_S = 1.0
BACKOFF_CAP_S = 8.0
TXT_RANGE_BYTES = 65535
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
#: Statuses that mean the runner itself is refused (P0): never retried, always recorded.
RUNNER_REFUSED = frozenset({403, 429})

ARCHIVES = "https://www.sec.gov/Archives/"
FULL_INDEX_URL = ARCHIVES + "edgar/full-index/{year}/QTR{q}/form.idx"
DAILY_INDEX_URL = ARCHIVES + "edgar/daily-index/{year}/QTR{q}/form.{ymd}.idx"
HDR_URL = ARCHIVES + "edgar/data/{cik}/{acc_nodash}/{accession}.hdr.sgml"
TXT_URL = ARCHIVES + "edgar/data/{cik}/{acc_nodash}/{accession}.txt"
FSDS_URL = "https://www.sec.gov/files/dera/data/financial-statement-data-sets/{year}q{q}.zip"

PROBE_SEED = "MONAD-EDGAR-PROBE-v1"
PROBE_VERSION = "probe.v1"
DAILY_CAP = 10

ALLOWLIST = ("10-K", "10-K/A", "10-Q", "10-Q/A", "10-KT", "10-KT/A", "10-QT", "10-QT/A")
ORIGINAL_FORMS = frozenset({"10-K", "10-Q"})

#: RFC 2606 reserved names: a contact there reaches nobody, which is not a contact.
RESERVED_DOMAINS = ("example.com", "example.org", "example.net")
RESERVED_TLDS = (".example", ".test", ".invalid", ".localhost")

#: Probe thresholds (docs/research/EDGAR_LEDGER_QUESTION.md, P0-P2).
P1_STATUS_SHARE = 0.95
P1_PARSE_SHARE = 0.99
P2_SECOND_SHARE = 0.99
COVERAGE_SHARE = 0.95
FREEZE_MIN_HDR_SHARE = 0.95
BOUNDARY_BUSINESS_DAYS = 2
FSDS_REQUIRED_COLUMNS = ("adsh", "cik", "form", "period", "filed", "accepted", "prevrpt",
                         "nciks", "aciks", "afs", "fy", "fp", "sic")
FSDS_COLUMNS = ("adsh", "cik", "name", "former", "changed", "sic", "afs", "fye", "form", "period",
                "fy", "fp", "filed", "accepted", "prevrpt", "nciks", "aciks", "instance")

# ── schema ───────────────────────────────────────────────────────────────────
#: Round-1 row (d) with the round-2 changes: ``co_registrant_ciks`` (O7), the fixture
#: ``clock_class`` enum (O5), ``hdr_source`` per row (O1), plus ``index_day`` and ``run_id``
#: so seals and freezes can address a day and a run.
FILING_FIELDS = (
    "kind", "ledger_version", "parser_version", "accession", "submitter_cik_prefix",
    "issuer_cik", "issuer_name", "sic", "roles", "co_registrant_ciks",
    "form", "form_base", "is_amendment", "filed", "period",
    "accepted_raw", "tz_rule", "accepted_at_utc",
    "date_as_of_change", "dissemination_kind", "public_release_date",
    "clock_class", "market_phase", "tradable_policy_daily", "tradable_session", "quality_flags",
    "idx_source", "idx_sha256", "hdr_source", "hdr_sha256", "hdr_bytes", "fetched_at",
    "revision_id", "index_day", "run_id",
)
REVISION_EXTRA_FIELDS = ("supersedes_hdr_sha256", "revision_kind")
REVISION_FIELDS = FILING_FIELDS + REVISION_EXTRA_FIELDS
SEAL_FIELDS = ("kind", "day", "idx_rows", "accessions", "hdr_ok", "hdr_failed", "complete",
               "run_id", "hdr_source", "idx_sha256", "lines_sha256", "at_utc")
INPUT_FIELDS = ("kind", "url", "status", "bytes", "sha256", "fetched_at", "run_id", "purpose", "range")
ROLE_FIELDS = ("role", "cik", "name", "sic")
ROW_FIELDS = {"filing": FILING_FIELDS, "revision": REVISION_FIELDS, "seal": SEAL_FIELDS}
PROBE_KINDS = frozenset({"probe_request", "probe_header", "probe_fsds", "probe_summary"})
CLOCK_CLASSES = frozenset({"second", "legacy_midnight_display", "not_public_event_time"})
MAX_ROW_BYTES = 4096

#: Header keys that must never reach a row (O8). Matched on the normalized SGML key and on
#: every emitted row key (lowercase). FSDS: ``ein`` and the ``*ba`` / ``*ma`` address columns.
DENY_KEY_PATTERNS = tuple(re.compile(p, re.I) for p in (
    r"address", r"street", r"^city", r"^zip", r"phone", r"^irs", r"^ein$", r"^ba[sp]", r"^mas",
    r"^(stpr|city|zip|country)(ba|ma)$", r"^(ba|ma)(s[12]|ph)$",
))
SGML_HEADER_KEYS = {
    "ACCESSION NUMBER": "accession",
    "CONFORMED SUBMISSION TYPE": "form",
    "CONFORMED PERIOD OF REPORT": "period",
    "FILED AS OF DATE": "filed",
    "DATE AS OF CHANGE": "date_as_of_change",
    "ACCEPTANCE-DATETIME": "accepted_raw",
    "PRIVATE-TO-PUBLIC": "private_to_public",
    "PUBLIC-REL-DATE": "public_release_date",
}
SGML_TOP_BLOCKS = {"FILER": "filer", "SUBJECT COMPANY": "subject_company", "FILED BY": "filed_by",
                   "ISSUER": "issuer", "REPORTING-OWNER": "reporting_owner",
                   "REPORTING OWNER": "reporting_owner", "DEPOSITOR": "depositor",
                   "SECURITIZER": "securitizer", "UNDERWRITER": "underwriter"}
SGML_COMPANY_KEYS = {"COMPANY CONFORMED NAME": "name", "CENTRAL INDEX KEY": "cik",
                     "STANDARD INDUSTRIAL CLASSIFICATION": "sic"}

FREEZE_COLUMNS = FILING_FIELDS + REVISION_EXTRA_FIELDS
FSDS_FREEZE_COLUMNS = FSDS_COLUMNS + ("accepted_raw", "accepted_at_utc", "clock_class", "market_phase",
                                      "tradable_policy_daily", "tradable_session", "quality_flags",
                                      "form_base", "is_amendment", "transition", "quarter")

_ACCESSION_RE = re.compile(r"^\d{10}-\d{2}-\d{6}$")
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_IDX_LINE = re.compile(
    r"^(?P<form>\S.*?)\s{2,}(?P<name>\S.*?)\s{2,}(?P<cik>\d{1,10})\s{2,}"
    r"(?P<filed>\d{4}-\d{2}-\d{2})\s{2,}(?P<path>edgar/data/\d+/(?P<acc>\d{10}-\d{2}-\d{6})\.txt)\s*$")
_SGML_TAG = re.compile(r"^<([A-Za-z0-9-]+)>(.*)$")
_SIC_CODE = re.compile(r"\[(\d{4})\]")
_FSDS_ACCEPTED = re.compile(r"^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2})(?:\.\d+)?$")
_ROWS_SHARD = re.compile(r"^\d{4}-\d{2}\.jsonl$")
_PROBE_FILE = re.compile(r"^PROBE-\d{8}T\d{6}Z-run[0-9A-Za-z_-]+\.jsonl$")
_FSDS_FILE = re.compile(r"^sub-\d{4}q[1-4]\.jsonl\.gz$")


class EdgarLedgerError(LedgerError):
    """A refused run: no passing probe, a bad user agent, a partial freeze, a schema breach."""


# ── small helpers ────────────────────────────────────────────────────────────
def utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def today_et() -> _dt.date:
    return _dt.datetime.now(EASTERN).date()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_quarter(text: str) -> tuple[int, int]:
    m = re.fullmatch(r"(\d{4})[Qq]([1-4])", (text or "").strip())
    if not m:
        raise EdgarLedgerError(f"quarter must look like 2024Q1, got {text!r}")
    return int(m.group(1)), int(m.group(2))


def quarter_of(day: _dt.date) -> tuple[int, int]:
    return day.year, (day.month - 1) // 3 + 1


def quarter_days(year: int, q: int) -> tuple[_dt.date, _dt.date]:
    start = _dt.date(year, 3 * (q - 1) + 1, 1)
    end = (_dt.date(year + (q == 4), (3 * q) % 12 + 1, 1) - _dt.timedelta(days=1))
    return start, end


def weekdays(start: _dt.date, end: _dt.date) -> list[_dt.date]:
    """ET weekdays (Mon-Fri) in [start, end]. EDGAR's day is a federal business day, so a
    federal holiday simply has an empty index: a seal with zero accessions, not a gap."""
    out, d = [], start
    while d <= end:
        if d.weekday() < 5:
            out.append(d)
        d += _dt.timedelta(days=1)
    return out


def boundary_days(year: int, q: int, n: int = BOUNDARY_BUSINESS_DAYS) -> frozenset:
    """The quarter's first and last ``n`` business days: a zip quarter and an index quarter
    can straddle a rollover, so these are excluded from the coverage denominator."""
    days = weekdays(*quarter_days(year, q))
    return frozenset(days[:n] + days[-n:])


def _iso_date(text: str | None) -> str | None:
    """``YYYYMMDD`` or ``YYYY-MM-DD`` -> ISO date, else None."""
    if not text:
        return None
    t = text.strip()
    if re.fullmatch(r"\d{8}", t):
        try:
            return _dt.date(int(t[:4]), int(t[4:6]), int(t[6:])).isoformat()
        except ValueError:
            return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", t):
        try:
            _dt.date.fromisoformat(t)
            return t
        except ValueError:
            return None
    return None


def _pad_cik(text: str | None) -> str | None:
    t = (text or "").strip()
    return t.zfill(10) if t.isdigit() else None


def deterministic_sample(accessions: Iterable[str], n: int, seed: str = PROBE_SEED) -> list[str]:
    """Exactly reproducible, independent of input order (the form25 lab's rule)."""
    ranked = sorted(set(accessions), key=lambda a: (sha256_bytes(f"{seed}|{a}".encode()), a))
    return ranked[:n]


# ── user agent and fetching ──────────────────────────────────────────────────
def user_agent(value: str | None = None) -> str:
    """The declared SEC contact: ``SEC_USER_AGENT`` (or ``value``), with an ``@`` and a
    domain that can receive mail. Reserved names (RFC 2606) are refused, so the pattern's
    own placeholder cannot leak into a run."""
    ua = (os.environ.get("SEC_USER_AGENT", "") if value is None else value).strip()
    if "@" not in ua:
        raise EdgarLedgerError("set SEC_USER_AGENT to 'name you@your-domain' (SEC fair-access policy)")
    domain = ua.rsplit("@", 1)[1].split()[0].lower().rstrip(".,;)>]")
    if not domain or domain in RESERVED_DOMAINS or domain.endswith(tuple("." + d for d in RESERVED_DOMAINS)) \
            or domain.endswith(RESERVED_TLDS):
        raise EdgarLedgerError(f"SEC_USER_AGENT contact domain {domain!r} is a reserved name; "
                               f"use 'name you@your-domain'")
    return ua


class Response(NamedTuple):
    status: int
    body: bytes
    headers: dict


def _urllib_get(url: str, headers: Mapping[str, str], timeout: float = 90) -> Response:
    req = urllib.request.Request(url, headers=dict(headers))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
            return Response(r.status, r.read(), {k.lower(): v for k, v in r.headers.items()})
    except urllib.error.HTTPError as e:
        try:
            body = e.read()
        except Exception:  # pragma: no cover - defensive
            body = b""
        return Response(e.code, body, {k.lower(): v for k, v in (e.headers or {}).items()})
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return Response(0, str(e).encode(), {})


class Fetcher:
    """Every SEC request: declared agent, ``min_interval`` spacing, bounded backoff on
    transient statuses, and an ``inputs`` line per request through ``on_input``. ``get`` is
    injectable so tests never touch the network; ``sleep``/``clock`` likewise."""

    def __init__(self, *, get: Callable[..., Response] | None = None, agent: str | None = None,
                 min_interval: float = MIN_INTERVAL, sleep=time.sleep, clock=time.monotonic,
                 max_retries: int = MAX_RETRIES, on_input=None, run_id: str = ""):
        if min_interval < 0.2:
            raise EdgarLedgerError("min_interval below 0.2 s is faster than this collector allows")
        self.agent = agent if agent is not None else user_agent()
        self._get = get or _urllib_get
        self.min_interval = min_interval
        self._sleep, self._clock = sleep, clock
        self.max_retries = max_retries
        self.on_input = on_input
        self.run_id = run_id
        self._last: float | None = None
        self.requests = 0

    def _pace(self):
        if self._last is not None:
            wait = self.min_interval - (self._clock() - self._last)
            if wait > 0:
                self._sleep(wait)
        self._last = self._clock()

    def fetch(self, url: str, *, range_bytes: int | None = None, purpose: str = "") -> Response:
        headers = {"User-Agent": self.agent, "Accept-Encoding": "identity"}
        if range_bytes is not None:
            headers["Range"] = f"bytes=0-{range_bytes}"
        resp = Response(0, b"", {})
        for attempt in range(self.max_retries + 1):
            self._pace()
            self.requests += 1
            resp = self._get(url, headers)
            if resp.status in RUNNER_REFUSED or not (resp.status in RETRY_STATUSES or resp.status == 0):
                break
            if attempt < self.max_retries:
                self._sleep(min(BACKOFF_BASE_S * 2 ** attempt, BACKOFF_CAP_S))
        if self.on_input is not None:
            self.on_input({"kind": "input", "url": url, "status": resp.status, "bytes": len(resp.body),
                           "sha256": sha256_bytes(resp.body), "fetched_at": utc_now(),
                           "run_id": self.run_id, "purpose": purpose,
                           "range": None if range_bytes is None else f"bytes=0-{range_bytes}"})
        return resp


# ── parsers ──────────────────────────────────────────────────────────────────
def parse_form_idx(data: bytes, allowlist: Iterable[str] = ALLOWLIST) -> dict:
    """``form.idx`` (full or daily) -> ``{accession: {form, filed, filer_ciks[], filer_names[],
    path, index_rows}}``: ONE entry per accession, every filer row kept (the index emits a
    row per filer CIK, so a co-registrant filing is several rows; CA-CLOCK100 collapsed
    2,282 rows to 1,141 accessions). Rows whose form is outside ``allowlist`` are dropped."""
    allowed = set(allowlist)
    text = data.decode("latin-1")
    out: dict[str, dict] = {}
    started = False
    for line in text.splitlines():
        if not started:
            if re.match(r"^-{10,}\s*$", line):
                started = True
            continue
        m = _IDX_LINE.match(line)
        if not m:
            continue
        form = m.group("form").strip()
        if form not in allowed:
            continue
        acc = m.group("acc")
        cik = m.group("cik").zfill(10)
        entry = out.setdefault(acc, {"form": form, "filed": m.group("filed"), "filer_ciks": [],
                                     "filer_names": [], "path": m.group("path"), "index_rows": 0})
        entry["index_rows"] += 1
        if cik not in entry["filer_ciks"]:
            entry["filer_ciks"].append(cik)
            entry["filer_names"].append(m.group("name").strip())
    return out


def _normalize_key(key: str) -> str:
    return re.sub(r"\s+", " ", key.strip().upper().replace("_", " "))


def denylisted_key(key: str) -> bool:
    k = key.strip().lower().replace(" ", "_")
    return any(p.search(k) for p in DENY_KEY_PATTERNS)


def parse_sgml_header(data: bytes) -> dict:
    """The whitelisted fields of an SGML submission header (``<accession>.hdr.sgml`` or the top
    of the ``.txt`` submission): ``accession``, ``form``, ``period``, ``filed``,
    ``date_as_of_change``, ``accepted_raw`` (``YYYY-MM-DD HH:MM:SS``, ET as displayed),
    ``dissemination_kind``, ``public_release_date`` and ``roles`` (one per FILER / SUBJECT
    COMPANY / FILED BY ... block: ``role``, ``cik``, ``name``, ``sic``). Addresses, phones and
    tax ids are never read into the result; unknown keys are dropped, not kept."""
    text = data.decode("latin-1", errors="replace")
    out: dict[str, Any] = {"accession": None, "form": None, "period": None, "filed": None,
                           "date_as_of_change": None, "accepted_raw": None,
                           "dissemination_kind": "PUBLIC", "public_release_date": None, "roles": []}
    top_role: dict | None = None
    sub_block: str | None = None
    seen_header = False
    for raw in text.splitlines():
        s = raw.strip()
        if not s:
            continue
        if s.upper().startswith("</SEC-HEADER>"):
            break
        tag = _SGML_TAG.match(s)
        if tag:
            name, value = _normalize_key(tag.group(1)).replace(" ", "-"), tag.group(2).strip()
            if name == "SEC-HEADER":
                seen_header = True
                continue
            if name == "ACCEPTANCE-DATETIME":
                out["accepted_raw"] = _acceptance(value)
            elif name == "PRIVATE-TO-PUBLIC":
                out["dissemination_kind"] = "PRIVATE-TO-PUBLIC"
            elif name == "PUBLIC-REL-DATE":
                out["public_release_date"] = _iso_date(value)
            continue
        if ":" not in s:
            continue
        key, _, value = s.partition(":")
        key, value = _normalize_key(key), value.strip()
        if value == "":
            if key in SGML_TOP_BLOCKS:
                top_role = {"role": SGML_TOP_BLOCKS[key], "cik": None, "name": None, "sic": None}
                out["roles"].append(top_role)
                sub_block = None
            else:
                sub_block = key
            continue
        if denylisted_key(key):
            continue
        hyph = key.replace(" ", "-")
        if top_role is None:
            field = SGML_HEADER_KEYS.get(key) or SGML_HEADER_KEYS.get(hyph)
            if field == "accepted_raw":
                out["accepted_raw"] = _acceptance(value)
            elif field == "private_to_public":
                out["dissemination_kind"] = "PRIVATE-TO-PUBLIC"
            elif field in ("period", "filed", "date_as_of_change", "public_release_date"):
                out[field] = _iso_date(value)
            elif field == "accession":
                out["accession"] = value if _ACCESSION_RE.match(value) else None
            elif field == "form":
                out["form"] = value
            continue
        if sub_block == "COMPANY DATA" and key in SGML_COMPANY_KEYS:
            field = SGML_COMPANY_KEYS[key]
            if field == "cik":
                top_role["cik"] = _pad_cik(value)
            elif field == "sic":
                m = _SIC_CODE.search(value)
                top_role["sic"] = m.group(1) if m else None
            else:
                top_role["name"] = value[:200]
    out["seen_header"] = seen_header
    return out


def _acceptance(value: str) -> str | None:
    m = re.search(r"(\d{14})", value or "")
    if not m:
        return None
    d = m.group(1)
    try:
        _dt.datetime.strptime(d, "%Y%m%d%H%M%S")
    except ValueError:
        return None
    return f"{d[:4]}-{d[4:6]}-{d[6:8]} {d[8:10]}:{d[10:12]}:{d[12:14]}"


def header_facts(data: bytes) -> dict:
    """The probe's three parse facts, computed and discarded (no header text is stored)."""
    h = parse_sgml_header(data)
    return {"has_14digit_acceptance": h["accepted_raw"] is not None,
            "filer_blocks": sum(1 for r in h["roles"] if r["role"] == "filer"),
            "has_filed_as_of_date": h["filed"] is not None}


def parse_fsds_sub(text: str, required_cols: Iterable[str] = FSDS_REQUIRED_COLUMNS,
                   allowlist: Iterable[str] = ALLOWLIST, columns: Iterable[str] = FSDS_COLUMNS) -> list[dict]:
    """FSDS ``sub.txt`` (tab-separated, header row) -> allowlisted-form rows holding only the
    whitelisted ``columns``. Fails CLOSED: a required column missing from the header is an
    error, not an empty field. ``ein`` and the ``*ba``/``*ma`` address columns are never read."""
    lines = text.splitlines()
    if not lines:
        raise EdgarLedgerError("sub.txt is empty")
    header = lines[0].rstrip("\r").split("\t")
    missing = [c for c in required_cols if c not in header]
    if missing:
        raise EdgarLedgerError(f"sub.txt lacks required column(s) {missing}; observed {header}")
    keep = [c for c in columns if c in header]
    deny = [c for c in keep if denylisted_key(c)]
    if deny:
        raise EdgarLedgerError(f"whitelist names denylisted column(s) {deny}")
    pos = {c: header.index(c) for c in keep}
    allowed = set(allowlist)
    out = []
    for line in lines[1:]:
        if not line.strip():
            continue
        cells = line.rstrip("\r").split("\t")
        if len(cells) < len(header):
            cells += [""] * (len(header) - len(cells))
        form = cells[pos["form"]].strip() if "form" in pos else ""
        if form not in allowed:
            continue
        out.append({c: cells[pos[c]].strip() for c in keep})
    return out


def fsds_accepted_raw(value: str) -> str | None:
    m = _FSDS_ACCEPTED.match((value or "").strip())
    return f"{m.group(1)} {m.group(2)}" if m else None


# ── the clock (PT-01's one function) ─────────────────────────────────────────
class Clock(NamedTuple):
    clock_class: str | None
    market_phase: str
    tradable_policy_daily: str
    flags: list
    tradable_session: str | None
    accepted_at_utc: str | None


POLICY_AFTER_FILING_DATE = "next regular-session open after filing date"
POLICY_AFTER_PUBLIC_RELEASE = ("next regular-session open after public release unless "
                               "dissemination time is recovered")
ROLLOVER_TIME = _dt.time(17, 30)
REGULAR_OPEN = _dt.time(9, 30)
REGULAR_CLOSE = _dt.time(16, 0)


def _next_session(after: _dt.date) -> _dt.date:
    d = after + _dt.timedelta(days=1)
    while not nyse_calendar.is_session(d):
        d += _dt.timedelta(days=1)
    return d


def _boundary_flags(accepted_date: _dt.date, session: _dt.date) -> list[str]:
    flags, d = [], accepted_date + _dt.timedelta(days=1)
    while d <= session:
        if d.weekday() >= 5 and "weekend_boundary" not in flags:
            flags.append("weekend_boundary")
        elif d.weekday() < 5 and not nyse_calendar.is_session(d) and d != session \
                and "holiday_boundary" not in flags:
            flags.append("holiday_boundary")
        d += _dt.timedelta(days=1)
    return flags


def tradable_time(filing: Mapping[str, Any]) -> Clock:
    """FD-00's historical daily clock for one filing (``accepted_raw`` ET, ``filed``, ``form``,
    ``dissemination_kind``, ``public_release_date``, ``accession``, ``issuer_cik``):

    * ``second``: the first regular-session open strictly after acceptance; a premarket
      acceptance (before 09:30 ET on a session day) trades at that day's open.
    * ``legacy_midnight_display`` (``00:00:00``): the display is not an acceptance time; the
      policy is the next session after the filing date and intraday use is ineligible.
    * ``not_public_event_time`` (PRIVATE-TO-PUBLIC): the original acceptance must not be
      used; the policy follows the public release date, date-only.
    * no acceptance at all: as legacy, flagged ``acceptance_missing``.

    Flags: ``filing_date_rollover`` (filed != acceptance date), ``weekend_boundary``,
    ``holiday_boundary``, ``after_regular_close``, ``amendment``, ``private_to_public``,
    ``public_time_date_only``, ``legacy_time_unresolved``, ``acceptance_missing``,
    ``third_party_filer_or_agent_accession`` (accession prefix is not the issuer CIK).
    """
    flags: list[str] = []
    form = filing.get("form") or ""
    if form.endswith("/A"):
        flags.append("amendment")
    acc, issuer = filing.get("accession"), filing.get("issuer_cik")
    if acc and issuer and acc[:10] != str(issuer).zfill(10):
        flags.append("third_party_filer_or_agent_accession")
    filed = _iso_date(filing.get("filed"))
    accepted_raw = filing.get("accepted_raw")
    accepted = None
    if accepted_raw:
        try:
            accepted = _dt.datetime.strptime(accepted_raw, "%Y-%m-%d %H:%M:%S").replace(tzinfo=EASTERN)
        except ValueError:
            accepted = None
    accepted_at_utc = (accepted.astimezone(_dt.timezone.utc).isoformat(timespec="seconds")
                       .replace("+00:00", "Z") if accepted else None)
    if accepted and filed and accepted.date().isoformat() != filed:
        flags.append("filing_date_rollover")

    if filing.get("dissemination_kind") == "PRIVATE-TO-PUBLIC":
        flags += ["private_to_public", "public_time_date_only"]
        release = _iso_date(filing.get("public_release_date"))
        session = _next_session(_dt.date.fromisoformat(release)).isoformat() if release else None
        return Clock("not_public_event_time", "unknown_on_public_release", POLICY_AFTER_PUBLIC_RELEASE,
                     flags, session, accepted_at_utc)
    if accepted is None:
        flags.append("acceptance_missing")
        session = _next_session(_dt.date.fromisoformat(filed)).isoformat() if filed else None
        return Clock(None, "unknown", POLICY_AFTER_FILING_DATE, flags, session, None)
    if accepted.time() == _dt.time(0, 0, 0):
        flags.append("legacy_time_unresolved")
        base = filed or accepted.date().isoformat()
        session = _next_session(_dt.date.fromisoformat(base)).isoformat()
        return Clock("legacy_midnight_display", "unknown", POLICY_AFTER_FILING_DATE, flags, session,
                     accepted_at_utc)

    t, day = accepted.time(), accepted.date()
    if t < REGULAR_OPEN:
        phase = "premarket"
        session = day if nyse_calendar.is_session(day) else _next_session(day)
    else:
        session = _next_session(day)
        if t < REGULAR_CLOSE:
            phase = "regular_session"
        elif t < ROLLOVER_TIME:
            phase = "after_regular_close"
            flags.append("after_regular_close")
        else:
            phase = "late_evening_friday" if day.weekday() == 4 else "late_evening"
    flags += _boundary_flags(day, session)
    return Clock("second", phase, f"{session.isoformat()} regular-session open", flags,
                 session.isoformat(), accepted_at_utc)


# ── rows ─────────────────────────────────────────────────────────────────────
def filing_row(header: Mapping[str, Any], *, accession: str, index_entry: Mapping[str, Any],
               index_day: str, idx_source: str, idx_sha256: str, hdr_source: str, hdr_sha256: str,
               hdr_bytes: int, fetched_at: str, run_id: str, revision_id: int = 0) -> dict:
    """One ``filing`` row from a parsed header and its index entry. ``issuer_cik`` is the
    first FILER block (the accession prefix is a submitter, never identity — FD00:180-195);
    further FILER blocks are ``co_registrant_ciks``. The clock fields are computed here and
    recomputed by the verifier (FD00:279)."""
    roles = [dict(r) for r in header.get("roles", [])]
    filers = [r["cik"] for r in roles if r["role"] == "filer" and r.get("cik")]
    if not filers:
        filers = list(index_entry.get("filer_ciks") or [])
    issuer_cik = filers[0] if filers else None
    issuer = next((r for r in roles if r["role"] == "filer" and r.get("cik") == issuer_cik), None)
    form = header.get("form") or index_entry.get("form")
    row = {
        "kind": "filing", "ledger_version": SCHEMA_VERSION, "parser_version": PARSER_VERSION,
        "accession": accession, "submitter_cik_prefix": accession[:10],
        "issuer_cik": issuer_cik,
        "issuer_name": (issuer or {}).get("name") or (index_entry.get("filer_names") or [None])[0],
        "sic": (issuer or {}).get("sic"),
        "roles": [{k: r.get(k) for k in ROLE_FIELDS} for r in roles],
        "co_registrant_ciks": filers[1:],
        "form": form, "form_base": (form or "").split("/")[0] or None,
        "is_amendment": bool(form and form.endswith("/A")),
        "filed": header.get("filed") or _iso_date(index_entry.get("filed")),
        "period": header.get("period"),
        "accepted_raw": header.get("accepted_raw"), "tz_rule": TZ_RULE, "accepted_at_utc": None,
        "date_as_of_change": header.get("date_as_of_change"),
        "dissemination_kind": header.get("dissemination_kind") or "PUBLIC",
        "public_release_date": header.get("public_release_date"),
        "clock_class": None, "market_phase": None, "tradable_policy_daily": None,
        "tradable_session": None, "quality_flags": [],
        "idx_source": idx_source, "idx_sha256": idx_sha256, "hdr_source": hdr_source,
        "hdr_sha256": hdr_sha256, "hdr_bytes": int(hdr_bytes), "fetched_at": fetched_at,
        "revision_id": int(revision_id), "index_day": index_day, "run_id": run_id,
    }
    return apply_clock(row)


def apply_clock(row: dict) -> dict:
    c = tradable_time(row)
    row.update({"clock_class": c.clock_class, "market_phase": c.market_phase,
                "tradable_policy_daily": c.tradable_policy_daily, "tradable_session": c.tradable_session,
                "quality_flags": list(c.flags), "accepted_at_utc": c.accepted_at_utc})
    return row


def revision_row(previous: Mapping[str, Any], new: Mapping[str, Any] | None, *, revision_id: int,
                 revision_kind: str, run_id: str, fetched_at: str, idx_source: str, idx_sha256: str) -> dict:
    """A correction is a NEW row (``kind=revision``), never an edit: ``header_changed`` carries
    the re-parsed header and names the sha it supersedes; ``removed_from_index`` repeats the
    last known fields with the header fields nulled."""
    if revision_kind == "header_changed":
        if new is None:
            raise EdgarLedgerError("header_changed needs the new row")
        row = dict(new)
    else:
        row = dict(previous)
        for k in ("accepted_raw", "accepted_at_utc", "hdr_sha256", "hdr_bytes", "date_as_of_change"):
            row[k] = None
        row["hdr_bytes"] = 0
        row["hdr_sha256"] = None
    row.update({"kind": "revision", "revision_id": int(revision_id), "run_id": run_id,
                "fetched_at": fetched_at, "idx_source": idx_source, "idx_sha256": idx_sha256,
                "supersedes_hdr_sha256": previous.get("hdr_sha256"), "revision_kind": revision_kind})
    return apply_clock(row)


def seal_row(day: str, *, idx_rows: int, accessions: int, hdr_ok: int, hdr_failed: int, run_id: str,
             hdr_source: str | None, idx_sha256: str | None, lines_sha256: str) -> dict:
    return {"kind": "seal", "day": day, "idx_rows": int(idx_rows), "accessions": int(accessions),
            "hdr_ok": int(hdr_ok), "hdr_failed": int(hdr_failed), "complete": hdr_failed == 0,
            "run_id": run_id, "hdr_source": hdr_source, "idx_sha256": idx_sha256,
            "lines_sha256": lines_sha256, "at_utc": utc_now()}


def row_line(row: Mapping[str, Any]) -> str:
    return canonical_json(row) + "\n"


def lines_digest(lines: Iterable[str]) -> str:
    h = hashlib.sha256()
    for ln in lines:
        h.update(ln.encode("utf-8"))
    return h.hexdigest()


# ── the store on disk ────────────────────────────────────────────────────────
class Store:
    """The ledger directory (``data/edgar_ledger`` on the branch, or any directory given):
    reading shards, appending rows, and the seal/day bookkeeping the daily job resumes from."""

    def __init__(self, root: Path | str):
        self.root = Path(root)

    @property
    def rows_dir(self):
        return self.root / "rows"

    @property
    def inputs_dir(self):
        return self.root / "inputs"

    @property
    def probe_dir(self):
        return self.root / "probe"

    @property
    def fsds_dir(self):
        return self.root / "fsds"

    def rows(self) -> list[dict]:
        """Every row of every rows shard, shard by name then line order."""
        out = []
        if self.rows_dir.is_dir():
            for shard in sorted(self.rows_dir.glob("*.jsonl")):
                with shard.open(encoding="utf-8") as fh:
                    for ln in fh:
                        if ln.strip():
                            out.append(json.loads(ln))
        return out

    def inputs(self) -> list[dict]:
        out = []
        if self.inputs_dir.is_dir():
            for shard in sorted(self.inputs_dir.glob("*.jsonl")):
                with shard.open(encoding="utf-8") as fh:
                    out += [json.loads(ln) for ln in fh if ln.strip()]
        return out

    def append(self, subdir: str, month: str, rows: Iterable[Mapping[str, Any]]) -> Path:
        d = self.root / subdir
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"{month}.jsonl"
        with path.open("a", encoding="utf-8") as fh:
            for r in rows:
                fh.write(row_line(r))
        return path

    def append_rows(self, rows: Iterable[Mapping[str, Any]]) -> None:
        by_month: dict[str, list] = {}
        for r in rows:
            day = r["day"] if r["kind"] == "seal" else r["index_day"]
            by_month.setdefault(day[:7], []).append(r)
        for month, group in sorted(by_month.items()):
            self.append("rows", month, group)

    def append_inputs(self, rows: Iterable[Mapping[str, Any]]) -> None:
        by_month: dict[str, list] = {}
        for r in rows:
            by_month.setdefault(r["fetched_at"][:7], []).append(r)
        for month, group in sorted(by_month.items()):
            self.append("inputs", month, group)

    def seals(self) -> dict[str, dict]:
        """The LAST seal per day (a day re-run after a partial seal gets a new seal)."""
        out: dict[str, dict] = {}
        for r in self.rows():
            if r.get("kind") == "seal":
                out[r["day"]] = r
        return out

    def last_complete_seal(self) -> _dt.date | None:
        days = [d for d, s in self.seals().items() if s.get("complete")]
        return _dt.date.fromisoformat(max(days)) if days else None

    def accession_index(self) -> dict[str, dict]:
        """``{accession: {"shas": {hdr_sha256,...}, "last": row, "revisions": n}}`` over filing
        and revision rows, in ledger order."""
        idx: dict[str, dict] = {}
        for r in self.rows():
            if r.get("kind") not in ("filing", "revision"):
                continue
            e = idx.setdefault(r["accession"], {"shas": set(), "last": None, "revisions": -1})
            if r.get("hdr_sha256"):
                e["shas"].add(r["hdr_sha256"])
            e["last"] = r
            e["revisions"] = max(e["revisions"], int(r.get("revision_id", 0)))
        return idx

    def day_lines_digest(self, day: str) -> str:
        """sha-256 of the filing/revision lines for ``day`` present before its seal is
        written (invariant 5: a seal hashes its day's lines)."""
        shard = self.rows_dir / f"{day[:7]}.jsonl"
        lines = []
        if shard.is_file():
            with shard.open(encoding="utf-8") as fh:
                for ln in fh:
                    if ln.strip():
                        r = json.loads(ln)
                        if r.get("kind") in ("filing", "revision") and r.get("index_day") == day:
                            lines.append(row_line(r))
        return lines_digest(lines)

    def probe_files(self, *, require_committed: bool = True) -> list[Path]:
        """Probe files on disk; with ``require_committed`` only those git tracks (the daily
        job trusts a probe that is on the branch, not one written in its own run)."""
        if not self.probe_dir.is_dir():
            return []
        files = sorted(self.probe_dir.glob("PROBE-*.jsonl"))
        if not require_committed:
            return files
        top = trials._git(self.root, "rev-parse", "--show-toplevel")
        if top.returncode != 0:
            return []
        repo = Path(top.stdout.decode().strip())
        tracked = trials._git(repo, "ls-files", "-z", "--", str(self.probe_dir.resolve().relative_to(repo.resolve())))
        names = {Path(p).name for p in tracked.stdout.decode().split("\0") if p}
        return [f for f in files if f.name in names]

    def passing_probe(self, *, require_committed: bool = True) -> dict | None:
        """The newest ``probe_summary`` with P0 = PASS and a decided header source, else None."""
        best = None
        for f in self.probe_files(require_committed=require_committed):
            with f.open(encoding="utf-8") as fh:
                for ln in fh:
                    if not ln.strip():
                        continue
                    r = json.loads(ln)
                    if r.get("kind") == "probe_summary" and probe_passes(r):
                        best = r
        return best


def probe_passes(summary: Mapping[str, Any]) -> bool:
    return (summary.get("p0", {}).get("status") == "PASS"
            and summary.get("hdr_source") in ("hdr_sgml", "txt_range"))


# ── planning and the daily job ───────────────────────────────────────────────
def plan_days(last_complete_seal: _dt.date | None, today: _dt.date, cap: int = DAILY_CAP,
              first_day: _dt.date | None = None) -> list[_dt.date]:
    """ET weekdays after the last complete seal and before ``today`` (yesterday's index is
    final by 07:17 UTC), oldest first, at most ``cap``; the remainder rolls forward and
    ``verify --report-gaps`` lists it. With no seal yet, start at ``first_day`` (default
    yesterday: no backfill in v1)."""
    yesterday = today - _dt.timedelta(days=1)
    if last_complete_seal is not None:
        start = last_complete_seal + _dt.timedelta(days=1)
    else:
        start = first_day or yesterday
    if start > yesterday:
        return []
    return weekdays(start, yesterday)[:cap]


def header_url(hdr_source: str, accession: str, cik: str) -> str:
    acc_nodash = accession.replace("-", "")
    cik_int = str(int(cik))
    tpl = HDR_URL if hdr_source == "hdr_sgml" else TXT_URL
    return tpl.format(cik=cik_int, acc_nodash=acc_nodash, accession=accession)


def fetch_header(fetcher: Fetcher, hdr_source: str, accession: str, cik: str, *, purpose: str) -> Response:
    url = header_url(hdr_source, accession, cik)
    rng = TXT_RANGE_BYTES if hdr_source == "txt_range" else None
    return fetcher.fetch(url, range_bytes=rng, purpose=purpose)


def process_day(store: Store, fetcher: Fetcher, day: _dt.date, *, hdr_source: str, run_id: str,
                refetch: bool = False) -> dict:
    """One ET business day: fetch its daily form index, fetch the header of every allowlisted
    accession not yet recorded, append ``filing`` rows (or ``revision`` rows when a recorded
    accession's header hash changed), then a ``seal`` row. Resumable: a re-run of a partial
    day fetches only what has no row (all of them with ``refetch``), and appends only
    ``(accession, hdr_sha256)`` pairs that are new."""
    year, q = quarter_of(day)
    url = DAILY_INDEX_URL.format(year=year, q=q, ymd=day.strftime("%Y%m%d"))
    resp = fetcher.fetch(url, purpose=f"daily-index {day.isoformat()}")
    day_s = day.isoformat()
    if resp.status in RUNNER_REFUSED:
        raise EdgarLedgerError(f"runner refused ({resp.status}) fetching {url}")
    if resp.status == 404:
        entries, idx_sha = {}, None
    elif resp.status == 200:
        entries, idx_sha = parse_form_idx(resp.body), sha256_bytes(resp.body)
    else:
        raise EdgarLedgerError(f"daily index {url} returned {resp.status}")
    known = store.accession_index()
    new_rows: list[dict] = []
    ok = failed = 0
    for acc in sorted(entries):
        entry = entries[acc]
        prev = known.get(acc)
        if prev is not None and prev["last"].get("hdr_sha256") and not refetch:
            ok += 1
            continue
        cik = entry["filer_ciks"][0] if entry["filer_ciks"] else acc[:10]
        h = fetch_header(fetcher, hdr_source, acc, cik, purpose=f"header {acc}")
        if h.status in RUNNER_REFUSED:
            raise EdgarLedgerError(f"runner refused ({h.status}) fetching {acc}")
        if h.status not in (200, 206) or not h.body:
            failed += 1
            continue
        header = parse_sgml_header(h.body)
        if header["accepted_raw"] is None and header["accession"] is None:
            failed += 1
            continue
        sha = sha256_bytes(h.body)
        row = filing_row(header, accession=acc, index_entry=entry, index_day=day_s, idx_source=url,
                         idx_sha256=idx_sha, hdr_source=hdr_source, hdr_sha256=sha, hdr_bytes=len(h.body),
                         fetched_at=utc_now(), run_id=run_id)
        if prev is not None:
            if sha in prev["shas"]:
                ok += 1
                continue
            row = revision_row(prev["last"], row, revision_id=prev["revisions"] + 1,
                               revision_kind="header_changed", run_id=run_id, fetched_at=row["fetched_at"],
                               idx_source=url, idx_sha256=idx_sha)
        new_rows.append(row)
        ok += 1
    store.append_rows(new_rows)
    seal = seal_row(day_s, idx_rows=sum(e["index_rows"] for e in entries.values()), accessions=len(entries),
                    hdr_ok=ok, hdr_failed=failed, run_id=run_id, hdr_source=hdr_source, idx_sha256=idx_sha,
                    lines_sha256=store.day_lines_digest(day_s))
    store.append_rows([seal])
    return {"day": day_s, "rows": len(new_rows), "seal": seal, "idx_status": resp.status}


def run_daily(store: Store, fetcher: Fetcher, *, today: _dt.date | None = None, cap: int = DAILY_CAP,
              run_id: str, first_day: _dt.date | None = None, require_committed: bool = True) -> dict:
    """The scheduled job. Writes NOTHING without a committed passing probe; otherwise every
    pending day since the last complete seal, capped."""
    probe = store.passing_probe(require_committed=require_committed)
    if probe is None:
        return {"status": "no_passing_probe", "days": []}
    today = today or today_et()
    days = plan_days(store.last_complete_seal(), today, cap=cap, first_day=first_day)
    done = [process_day(store, fetcher, d, hdr_source=probe["hdr_source"], run_id=run_id) for d in days]
    pending = len(weekdays(days[-1] + _dt.timedelta(days=1), today - _dt.timedelta(days=1))) if days else 0
    return {"status": "ok", "days": done, "hdr_source": probe["hdr_source"], "rolled_forward": pending}


def run_sweep(store: Store, fetcher: Fetcher, quarter: str, *, run_id: str,
              require_committed: bool = True) -> dict:
    """Monthly: re-read the quarter's REBUILT full index (rebuilt weekly to incorporate later
    corrections or deletions, FD00:170-178) and append ``revision`` rows for recorded
    accessions whose header hash changed or that vanished from the index; accessions new to
    the index get ``filing`` rows. Never edits."""
    probe = store.passing_probe(require_committed=require_committed)
    if probe is None:
        raise EdgarLedgerError("no committed passing probe on the branch; sweep refuses to run")
    hdr_source = probe["hdr_source"]
    year, q = parse_quarter(quarter)
    url = FULL_INDEX_URL.format(year=year, q=q)
    resp = fetcher.fetch(url, purpose=f"full-index {quarter}")
    if resp.status != 200:
        raise EdgarLedgerError(f"full index {url} returned {resp.status}")
    idx_sha = sha256_bytes(resp.body)
    entries = parse_form_idx(resp.body)
    start, end = quarter_days(year, q)
    known = store.accession_index()
    in_quarter = {a: e for a, e in known.items()
                  if e["last"].get("index_day") and start.isoformat() <= e["last"]["index_day"] <= end.isoformat()}
    new_rows: list[dict] = []
    now = utc_now()
    for acc, entry in sorted(entries.items()):
        prev = known.get(acc)
        cik = entry["filer_ciks"][0] if entry["filer_ciks"] else acc[:10]
        h = fetch_header(fetcher, hdr_source, acc, cik, purpose=f"sweep header {acc}")
        if h.status in RUNNER_REFUSED:
            raise EdgarLedgerError(f"runner refused ({h.status}) fetching {acc}")
        if h.status not in (200, 206) or not h.body:
            continue
        sha = sha256_bytes(h.body)
        if prev is not None and sha in prev["shas"]:
            continue
        header = parse_sgml_header(h.body)
        day = prev["last"]["index_day"] if prev is not None else (_iso_date(entry["filed"]) or start.isoformat())
        row = filing_row(header, accession=acc, index_entry=entry, index_day=day, idx_source=url,
                         idx_sha256=idx_sha, hdr_source=hdr_source, hdr_sha256=sha, hdr_bytes=len(h.body),
                         fetched_at=now, run_id=run_id)
        if prev is not None:
            row = revision_row(prev["last"], row, revision_id=prev["revisions"] + 1, revision_kind="header_changed",
                               run_id=run_id, fetched_at=now, idx_source=url, idx_sha256=idx_sha)
        new_rows.append(row)
    for acc, e in sorted(in_quarter.items()):
        if acc not in entries and e["last"].get("revision_kind") != "removed_from_index":
            new_rows.append(revision_row(e["last"], None, revision_id=e["revisions"] + 1,
                                         revision_kind="removed_from_index", run_id=run_id, fetched_at=now,
                                         idx_source=url, idx_sha256=idx_sha))
    store.append_rows(new_rows)
    return {"status": "ok", "quarter": quarter, "rows": len(new_rows), "index_accessions": len(entries)}


# ── the probe (Step 0) ───────────────────────────────────────────────────────
def _share(num: int, den: int) -> float | None:
    return None if den == 0 else round(num / den, 4)


def run_probe(store: Store, fetcher: Fetcher, quarter: str, n: int, *, run_id: str,
              fsds_extract_limit: int | None = None) -> tuple[Path, dict]:
    """Step 0: one full index, a deterministic sample of ``n`` accessions' headers (``.hdr.sgml``,
    falling back to a 64 KiB range of the ``.txt``), and one FSDS zip streamed and measured.
    No header text is stored. Writes ONE frozen probe file and returns its summary."""
    year, q = parse_quarter(quarter)
    requests: list[dict] = []
    headers: list[dict] = []
    bounds = boundary_days(year, q)

    def record(url, resp, rng=None):
        requests.append({"kind": "probe_request", "url": url, "status": resp.status, "bytes": len(resp.body),
                         "sha256": sha256_bytes(resp.body), "fetched_at": utc_now(), "range": rng})

    idx_url = FULL_INDEX_URL.format(year=year, q=q)
    idx = fetcher.fetch(idx_url, purpose=f"probe full-index {quarter}")
    record(idx_url, idx)
    entries = parse_form_idx(idx.body) if idx.status == 200 else {}
    sample = deterministic_sample(entries, n)
    for acc in sample:
        e = entries[acc]
        cik = e["filer_ciks"][0] if e["filer_ciks"] else acc[:10]
        row = {"kind": "probe_header", "accession": acc, "form": e["form"], "filed": e["filed"],
               "filer_cik": cik, "boundary_day": _dt.date.fromisoformat(e["filed"]) in bounds}
        if idx.status in RUNNER_REFUSED:
            headers.append(row)
            continue
        for src, key in (("hdr_sgml", "hdr"), ("txt_range", "txt")):
            r = fetch_header(fetcher, src, acc, cik, purpose=f"probe {src} {acc}")
            record(header_url(src, acc, cik), r, f"bytes=0-{TXT_RANGE_BYTES}" if src == "txt_range" else None)
            facts = header_facts(r.body) if r.status in (200, 206) and r.body else \
                {"has_14digit_acceptance": False, "filer_blocks": 0, "has_filed_as_of_date": False}
            row.update({f"{key}_status": r.status, f"{key}_bytes": len(r.body),
                        f"{key}_sha256": sha256_bytes(r.body) if r.body else None,
                        f"{key}_has_14digit_acceptance": facts["has_14digit_acceptance"],
                        f"{key}_filer_blocks": facts["filer_blocks"],
                        f"{key}_has_filed_as_of_date": facts["has_filed_as_of_date"]})
            if r.status in RUNNER_REFUSED or (src == "hdr_sgml" and r.status == 200 and facts["has_14digit_acceptance"]):
                break
        headers.append(row)

    fsds_url = FSDS_URL.format(year=year, q=q)
    z = fetcher.fetch(fsds_url, purpose=f"probe fsds {quarter}")
    record(fsds_url, z)
    fsds = probe_fsds_row(z, fsds_url, sample_entries={a: entries[a] for a in sample}, bounds=bounds,
                          extract_limit=fsds_extract_limit)
    rows = requests + headers + [fsds]
    summary = probe_verdict(rows, quarter=quarter, n_requested=n, run_id=run_id)
    rows.append(summary)
    store.probe_dir.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = store.probe_dir / f"PROBE-{stamp}-run{run_id}.jsonl"
    data_store.write_exclusive(path, "".join(row_line(r) for r in rows).encode("utf-8"))
    return path, summary


def probe_fsds_row(resp: Response, url: str, *, sample_entries: Mapping[str, Mapping], bounds: frozenset,
                   extract_limit: int | None = None) -> dict:
    """What one FSDS quarterly zip looks like, measured and discarded: members, ``sub.txt``'s
    columns and row count, acceptance precision, ``prevrpt`` values, form counts, and the
    coverage of the probe sample by ``adsh`` — originals and amendments separately,
    quarter-boundary accessions excluded from the denominator."""
    row: dict[str, Any] = {"kind": "probe_fsds", "url": url, "status": resp.status, "bytes": len(resp.body),
                           "content_length": resp.headers.get("content-length"),
                           "sha256": sha256_bytes(resp.body) if resp.body else None, "members": [],
                           "sub_present": False, "sub_columns": [], "sub_rows": 0,
                           "accepted_second_share": None, "prevrpt_values": [], "form_counts": {},
                           "coverage": {}, "extract_gz_bytes": None, "error": None}
    if resp.status != 200 or not resp.body:
        return row
    try:
        with zipfile.ZipFile(io.BytesIO(resp.body)) as zf:
            row["members"] = [{"name": i.filename, "size": i.file_size} for i in zf.infolist()]
            if "sub.txt" not in zf.namelist():
                return row
            text = zf.read("sub.txt").decode("latin-1")
    except zipfile.BadZipFile as e:
        row["error"] = f"bad zip: {e}"
        return row
    row["sub_present"] = True
    lines = text.splitlines()
    header = lines[0].rstrip("\r").split("\t") if lines else []
    row["sub_columns"] = header
    pos = {c: i for i, c in enumerate(header)}
    sub_rows = [ln.rstrip("\r").split("\t") for ln in lines[1:] if ln.strip()]
    row["sub_rows"] = len(sub_rows)
    forms: dict[str, int] = {}
    prevrpt: set = set()
    seconds = 0
    adsh: set = set()
    for cells in sub_rows:
        f = cells[pos["form"]] if "form" in pos and pos["form"] < len(cells) else ""
        forms[f] = forms.get(f, 0) + 1
        if "prevrpt" in pos and pos["prevrpt"] < len(cells):
            prevrpt.add(cells[pos["prevrpt"]])
        if "accepted" in pos and pos["accepted"] < len(cells) and fsds_accepted_raw(cells[pos["accepted"]]):
            seconds += 1
        if "adsh" in pos and pos["adsh"] < len(cells):
            adsh.add(cells[pos["adsh"]].strip())
    row["form_counts"] = dict(sorted(forms.items(), key=lambda kv: -kv[1])[:40])
    row["prevrpt_values"] = sorted(prevrpt)
    row["accepted_second_share"] = _share(seconds, len(sub_rows))
    row["coverage"] = coverage_split(sample_entries, adsh, bounds)
    if "form" in pos:
        try:
            extract = parse_fsds_sub(text)
            payload = "".join(row_line(r) for r in extract).encode("utf-8")
            row["extract_gz_bytes"] = len(data_store.gzip_bytes(payload))
            row["extract_rows"] = len(extract)
        except EdgarLedgerError as e:
            row["error"] = str(e)
    return row


def coverage_split(sample_entries: Mapping[str, Mapping], adsh: set, bounds: frozenset) -> dict:
    """Coverage of the probe sample by FSDS ``adsh``: ``originals`` (10-K, 10-Q: the gate),
    ``amendments`` (reported, scopes H52-lite), ``by_form``; boundary-day accessions are
    counted separately and left out of every denominator."""
    out = {"originals": {"found": 0, "total": 0}, "amendments": {"found": 0, "total": 0},
           "by_form": {}, "boundary_excluded": 0}
    for acc, e in sample_entries.items():
        if _dt.date.fromisoformat(e["filed"]) in bounds:
            out["boundary_excluded"] += 1
            continue
        found = acc in adsh
        form = e["form"]
        bucket = "originals" if form in ORIGINAL_FORMS else "amendments"
        out[bucket]["total"] += 1
        out[bucket]["found"] += found
        bf = out["by_form"].setdefault(form, {"found": 0, "total": 0})
        bf["total"] += 1
        bf["found"] += found
    for k in ("originals", "amendments"):
        out[k]["share"] = _share(out[k]["found"], out[k]["total"])
    return out


def probe_verdict(rows: Iterable[Mapping[str, Any]], *, quarter: str | None = None, n_requested: int | None = None,
                  run_id: str = "") -> dict:
    """P0 runner (zero 403/429), P1 header source (``hdr_sgml`` on >= 95% 200s with a 14-digit
    acceptance and a FILER block on >= 99% of those, else the same on the ``.txt`` range, else
    FAIL_HEADER), P2 FSDS (zip 200, ``sub.txt`` with the required columns, acceptance to the
    second on >= 99%; coverage of ORIGINAL 10-K/10-Q accessions >= 95% makes FSDS the S1'
    frame, otherwise facts only; amendment coverage is reported, never gating)."""
    rows = list(rows)
    requests = [r for r in rows if r.get("kind") == "probe_request"]
    headers = [r for r in rows if r.get("kind") == "probe_header"]
    fsds = next((r for r in rows if r.get("kind") == "probe_fsds"), None)
    codes: dict[str, int] = {}
    for r in requests:
        codes[str(r.get("status"))] = codes.get(str(r.get("status")), 0) + 1
    refused = sum(codes.get(str(c), 0) for c in RUNNER_REFUSED)
    p0 = {"status": "FAIL_RUNNER" if refused else "PASS", "requests": len(requests), "refused": refused, "codes": codes}

    def source_shares(key):
        n = len(headers)
        ok = [h for h in headers if h.get(f"{key}_status") in (200, 206)]
        parsed = [h for h in ok if h.get(f"{key}_has_14digit_acceptance") and (h.get(f"{key}_filer_blocks") or 0) >= 1]
        return _share(len(ok), n), _share(len(parsed), len(ok))

    hdr_200, hdr_parse = source_shares("hdr")
    txt_200, txt_parse = source_shares("txt")
    hdr_source = None
    if headers and (hdr_200 or 0) >= P1_STATUS_SHARE and (hdr_parse or 0) >= P1_PARSE_SHARE:
        hdr_source = "hdr_sgml"
    elif headers and (txt_200 or 0) >= P1_STATUS_SHARE and (txt_parse or 0) >= P1_PARSE_SHARE:
        hdr_source = "txt_range"
    p1 = {"status": "PASS" if hdr_source else "FAIL_HEADER", "sampled": len(headers), "hdr_source": hdr_source,
          "hdr_sgml_200_share": hdr_200, "hdr_sgml_parse_share": hdr_parse,
          "txt_range_200_share": txt_200, "txt_range_parse_share": txt_parse}

    p2: dict[str, Any] = {"status": "FAIL_FSDS", "fsds_slice": False, "fsds_role": None,
                          "coverage_originals": None, "coverage_amendments": None,
                          "accepted_second_share": None, "missing_columns": list(FSDS_REQUIRED_COLUMNS),
                          "extract_gz_bytes": None}
    if fsds is not None:
        missing = [c for c in FSDS_REQUIRED_COLUMNS if c not in (fsds.get("sub_columns") or [])]
        p2.update({"missing_columns": missing, "accepted_second_share": fsds.get("accepted_second_share"),
                   "extract_gz_bytes": fsds.get("extract_gz_bytes")})
        cov = fsds.get("coverage") or {}
        p2["coverage_originals"] = (cov.get("originals") or {}).get("share")
        p2["coverage_amendments"] = (cov.get("amendments") or {}).get("share")
        if fsds.get("status") == 200 and fsds.get("sub_present") and not missing \
                and (fsds.get("accepted_second_share") or 0) >= P2_SECOND_SHARE:
            p2["status"], p2["fsds_slice"] = "PASS", True
            orig = p2["coverage_originals"]
            p2["fsds_role"] = "facts_and_s1prime_frame" if orig is not None and orig >= COVERAGE_SHARE else "facts_only"
    if p0["status"] != "PASS":
        verdict = "FAIL_RUNNER"
    elif hdr_source == "hdr_sgml":
        verdict = "PASS"
    elif hdr_source == "txt_range":
        verdict = "PASS_TXT_RANGE"
    else:
        verdict = "FAIL_HEADER"
    return {"kind": "probe_summary", "probe_version": PROBE_VERSION, "quarter": quarter,
            "n_requested": n_requested, "n_sampled": len(headers), "p0": p0, "p1": p1, "p2": p2,
            "verdict": verdict, "hdr_source": hdr_source if p0["status"] == "PASS" else None,
            "at_utc": utc_now(), "run_id": run_id}


# ── FSDS slice ───────────────────────────────────────────────────────────────
def fsds_rows(sub_text: str, quarter: str) -> list[dict]:
    """Whitelisted ``sub.txt`` rows of the allowlisted forms plus the derived clock fields
    (10-KT/10-QT kept and flagged ``transition``)."""
    out = []
    for r in parse_fsds_sub(sub_text):
        form = r.get("form") or ""
        base = form.split("/")[0]
        row = {c: r.get(c) for c in FSDS_COLUMNS}
        row.update({"accepted_raw": fsds_accepted_raw(r.get("accepted", "")), "filed": _iso_date(r.get("filed")) or r.get("filed"),
                    "period": _iso_date(r.get("period")) or r.get("period"), "form_base": base,
                    "is_amendment": form.endswith("/A"), "transition": base.endswith("T"), "quarter": quarter,
                    "accession": r.get("adsh"), "issuer_cik": _pad_cik(r.get("cik")), "dissemination_kind": "PUBLIC"})
        c = tradable_time(row)
        row.update({"accepted_at_utc": c.accepted_at_utc, "clock_class": c.clock_class, "market_phase": c.market_phase,
                    "tradable_policy_daily": c.tradable_policy_daily, "tradable_session": c.tradable_session,
                    "quality_flags": list(c.flags)})
        for k in ("accession", "issuer_cik", "dissemination_kind"):
            row.pop(k)
        out.append(row)
    return out


def run_fsds(store: Store, fetcher: Fetcher, quarter: str, *, run_id: str, require_committed: bool = True) -> dict:
    """Slice 1: fetch one FSDS quarterly zip (not committed; one ``inputs`` line), extract
    ``sub.txt`` and freeze ``fsds/sub-YYYYqN.jsonl.gz`` once (identical rule). Refuses
    without a committed passing probe whose P2 admits the slice."""
    probe = store.passing_probe(require_committed=require_committed)
    if probe is None:
        raise EdgarLedgerError("no committed passing probe on the branch; fsds refuses to run")
    if not probe.get("p2", {}).get("fsds_slice"):
        raise EdgarLedgerError("the committed probe's P2 did not admit the FSDS slice")
    year, q = parse_quarter(quarter)
    target = store.fsds_dir / f"sub-{year}q{q}.jsonl.gz"
    if target.exists():
        return {"status": "exists", "path": str(target)}
    url = FSDS_URL.format(year=year, q=q)
    resp = fetcher.fetch(url, purpose=f"fsds {quarter}")
    if resp.status != 200:
        raise EdgarLedgerError(f"{url} returned {resp.status}")
    with zipfile.ZipFile(io.BytesIO(resp.body)) as zf:
        text = zf.read("sub.txt").decode("latin-1")
    rows = fsds_rows(text, f"{year}Q{q}")
    payload = "".join(row_line(r) for r in rows).encode("utf-8")
    store.fsds_dir.mkdir(parents=True, exist_ok=True)
    data_store.write_exclusive(target, data_store.gzip_bytes(payload))
    return {"status": "ok", "path": str(target), "rows": len(rows), "zip_sha256": sha256_bytes(resp.body)}


# ── verification ─────────────────────────────────────────────────────────────
def history_rule(rel: str) -> str | None:
    """``rows/*.jsonl``, ``inputs/*.jsonl`` may only grow; ``probe/*`` and ``fsds/*.jsonl.gz``
    never change; README and anything else is ordinary text."""
    p = Path(rel)
    parts = p.parts
    if "rows" in parts or "inputs" in parts:
        return "prefix" if p.suffix == ".jsonl" else None
    if "probe" in parts or "fsds" in parts:
        return "identical"
    return None


def verify_history(base_ref: str, *, repo: Path, rel_dir: Path = LEDGER_REL) -> list[str]:
    return trials.verify_history(base_ref, rel_dir, rule=history_rule, repo=repo, what="ledger file")


def _deny_keys(obj: Any, path: str = "") -> list[str]:
    bad = []
    if isinstance(obj, Mapping):
        for k, v in obj.items():
            if denylisted_key(str(k)):
                bad.append(f"{path}{k}")
            bad += _deny_keys(v, f"{path}{k}.")
    elif isinstance(obj, list):
        for v in obj:
            bad += _deny_keys(v, path)
    return bad


def verify_shards(root: Path | str) -> list[str]:
    """Every shard parses and every row keeps the schema: known kinds, exactly the schema's
    keys, no denylisted key anywhere, rows under 4 KiB, accession identity, shard month
    matching ``index_day``, ``(accession, revision_id)`` unique with the filing row first,
    the clock recomputed from stored fields equal to the stored clock (FD00:279), every cited
    sha-256 in an ``inputs`` line, each seal hashing its day's lines, probe files with one
    summary, FSDS files holding only whitelisted columns."""
    store = Store(root)
    problems: list[str] = []
    root = store.root
    if not root.is_dir():
        return []
    expected_name = {"rows": _ROWS_SHARD, "inputs": _ROWS_SHARD, "probe": _PROBE_FILE, "fsds": _FSDS_FILE}
    for p in sorted(root.rglob("*")):
        if p.is_dir() or p.name == "README.md":
            continue
        rel = p.relative_to(root).as_posix()
        pattern = expected_name.get(p.parent.name) if p.parent.parent == root else None
        if pattern is None or not pattern.match(p.name):
            problems.append(f"{rel}: not a ledger file (unexpected name or place)")
    input_shas: set[str] = set()
    for shard in sorted(store.inputs_dir.glob("*.jsonl")) if store.inputs_dir.is_dir() else []:
        for i, r in _lines(shard, problems):
            if set(r) != set(INPUT_FIELDS):
                problems.append(f"inputs/{shard.name}:{i}: keys {sorted(set(r) ^ set(INPUT_FIELDS))} differ from schema")
            if not isinstance(r.get("sha256"), str) or not _SHA_RE.match(r["sha256"]):
                problems.append(f"inputs/{shard.name}:{i}: bad sha256")
            else:
                input_shas.add(r["sha256"])
            if r.get("fetched_at", "")[:7] != shard.stem:
                problems.append(f"inputs/{shard.name}:{i}: fetched_at {r.get('fetched_at')} outside shard month")
    seen: dict[tuple, str] = {}
    filing_seen: set[str] = set()
    for shard in sorted(store.rows_dir.glob("*.jsonl")) if store.rows_dir.is_dir() else []:
        day_lines: dict[str, list[str]] = {}
        for i, r in _lines(shard, problems):
            where = f"rows/{shard.name}:{i}"
            kind = r.get("kind")
            if kind not in ROW_FIELDS:
                problems.append(f"{where}: unknown kind {kind!r}")
                continue
            if set(r) != set(ROW_FIELDS[kind]):
                problems.append(f"{where}: keys {sorted(set(r) ^ set(ROW_FIELDS[kind]))} differ from the {kind} schema")
            bad = _deny_keys(r)
            if bad:
                problems.append(f"{where}: denylisted key(s) {bad}")
            if len(row_line(r).encode("utf-8")) > MAX_ROW_BYTES:
                problems.append(f"{where}: row exceeds {MAX_ROW_BYTES} bytes (a body, not a header)")
            if kind == "seal":
                if r.get("day", "")[:7] != shard.stem:
                    problems.append(f"{where}: seal day {r.get('day')} outside shard month")
                if r.get("lines_sha256") != lines_digest(day_lines.get(r.get("day"), [])):
                    problems.append(f"{where}: seal lines_sha256 does not hash the day's lines")
                if r.get("idx_sha256") and r["idx_sha256"] not in input_shas:
                    problems.append(f"{where}: idx_sha256 has no inputs line")
                continue
            acc = r.get("accession")
            if not isinstance(acc, str) or not _ACCESSION_RE.match(acc):
                problems.append(f"{where}: bad accession {acc!r}")
                continue
            if r.get("index_day", "")[:7] != shard.stem:
                problems.append(f"{where}: index_day {r.get('index_day')} outside shard month")
            key = (acc, r.get("revision_id"))
            if key in seen:
                problems.append(f"{where}: ({acc}, {r.get('revision_id')}) repeats {seen[key]}")
            seen[key] = where
            if kind == "filing":
                if r.get("revision_id") != 0:
                    problems.append(f"{where}: a filing row has revision_id {r.get('revision_id')}")
                filing_seen.add(acc)
            elif acc not in filing_seen:
                problems.append(f"{where}: revision of {acc} precedes its filing row")
            if r.get("clock_class") not in CLOCK_CLASSES and r.get("clock_class") is not None:
                problems.append(f"{where}: clock_class {r.get('clock_class')!r} outside the fixture enum")
            c = tradable_time(r)
            stored = (r.get("clock_class"), r.get("market_phase"), r.get("tradable_policy_daily"), r.get("tradable_session"))
            if stored != (c.clock_class, c.market_phase, c.tradable_policy_daily, c.tradable_session):
                problems.append(f"{where}: stored clock {stored} is not the recomputed {tuple(c[:3]) + (c.tradable_session,)}")
            for k in ("hdr_sha256", "idx_sha256"):
                v = r.get(k)
                if v is not None and (not isinstance(v, str) or not _SHA_RE.match(v)):
                    problems.append(f"{where}: bad {k}")
                elif v is not None and v not in input_shas:
                    problems.append(f"{where}: {k} has no inputs line")
            day_lines.setdefault(r.get("index_day"), []).append(row_line(r))
    for f in sorted(store.probe_dir.glob("*")) if store.probe_dir.is_dir() else []:
        kinds = []
        for i, r in _lines(f, problems):
            kinds.append(r.get("kind"))
            if r.get("kind") not in PROBE_KINDS:
                problems.append(f"probe/{f.name}:{i}: unknown kind {r.get('kind')!r}")
            bad = _deny_keys(r)
            if bad:
                problems.append(f"probe/{f.name}:{i}: denylisted key(s) {bad}")
            if any(k in r for k in ("body", "text", "header_text")):
                problems.append(f"probe/{f.name}:{i}: a probe row carries header text")
        if kinds.count("probe_summary") != 1:
            problems.append(f"probe/{f.name}: {kinds.count('probe_summary')} probe_summary rows (need exactly one)")
    for f in sorted(store.fsds_dir.glob("*.jsonl.gz")) if store.fsds_dir.is_dir() else []:
        try:
            text = gzip.decompress(f.read_bytes()).decode("utf-8")
        except (OSError, EOFError) as e:
            problems.append(f"fsds/{f.name}: unreadable ({e})")
            continue
        allowed = set(FSDS_FREEZE_COLUMNS)
        for i, ln in enumerate(text.splitlines(), 1):
            try:
                r = json.loads(ln)
            except json.JSONDecodeError:
                problems.append(f"fsds/{f.name}:{i}: not JSON")
                continue
            extra = set(r) - allowed
            if extra:
                problems.append(f"fsds/{f.name}:{i}: keys outside the FSDS whitelist {sorted(extra)}")
            bad = _deny_keys(r)
            if bad:
                problems.append(f"fsds/{f.name}:{i}: denylisted key(s) {bad}")
    return problems


def _lines(path: Path, problems: list[str]):
    with path.open(encoding="utf-8") as fh:
        for i, ln in enumerate(fh, 1):
            if not ln.strip():
                continue
            try:
                r = json.loads(ln)
            except json.JSONDecodeError:
                problems.append(f"{path.parent.name}/{path.name}:{i}: not JSON")
                continue
            if not isinstance(r, dict):
                problems.append(f"{path.parent.name}/{path.name}:{i}: not an object")
                continue
            yield i, r


def day_status(seals: Mapping[str, Mapping], day: _dt.date) -> str:
    """``missing`` (no seal), ``partial`` (incomplete, or header coverage under 0.95) or ``ok``."""
    s = seals.get(day.isoformat())
    if s is None:
        return "missing"
    acc = s.get("accessions") or 0
    if not s.get("complete") or (acc and (s.get("hdr_ok") or 0) / acc < FREEZE_MIN_HDR_SHARE):
        return "partial"
    return "ok"


def report_gaps(store: Store, *, today: _dt.date | None = None, require_committed: bool = True) -> dict:
    """What ``verify --report-gaps`` prints: weekdays with no seal or a partial seal between
    the first sealed day and yesterday, and how many weekdays have passed without a passing
    probe (the silent-green the daily job's exit 0 would otherwise hide)."""
    today = today or today_et()
    yesterday = today - _dt.timedelta(days=1)
    seals = store.seals()
    out: dict[str, Any] = {"first_day": None, "missing_seal_days": [], "partial_days": [], "probe_less_days": 0,
                           "passing_probe": None}
    probe = store.passing_probe(require_committed=require_committed)
    if probe is not None:
        out["passing_probe"] = {"quarter": probe.get("quarter"), "verdict": probe.get("verdict"),
                                "hdr_source": probe.get("hdr_source"), "at_utc": probe.get("at_utc")}
    files = store.probe_files(require_committed=require_committed)
    if probe is None:
        since = None
        if files:
            m = re.match(r"PROBE-(\d{8})T", files[0].name)
            since = _dt.date(int(m.group(1)[:4]), int(m.group(1)[4:6]), int(m.group(1)[6:])) if m else None
        if since is not None and since <= yesterday:
            out["probe_less_days"] = len(weekdays(since, yesterday))
    if seals:
        first = _dt.date.fromisoformat(min(seals))
        out["first_day"] = first.isoformat()
        for d in weekdays(first, yesterday):
            st = day_status(seals, d)
            if st == "missing":
                out["missing_seal_days"].append(d.isoformat())
            elif st == "partial":
                out["partial_days"].append(d.isoformat())
    return out


# ── freeze ───────────────────────────────────────────────────────────────────
def _csv_cell(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (list, dict)):
        return canonical_json(v)
    return str(v)


def freeze(store: Store, start: _dt.date, end: _dt.date, *, allow_partial: bool = False,
           data_dir: Path | None = None, ledger_head: str | None = None) -> tuple[str, dict]:
    """Freeze the filing/revision rows whose ``index_day`` is in [start, end] as
    ``EDGARLEDGER-<sha>.csv.gz`` through ``data_store.write`` (public: SEC is not a restricted
    vendor) with a manifest. Every ET weekday of the window must carry a complete seal with
    header coverage >= 0.95; otherwise the freeze is refused unless ``allow_partial``, which is
    recorded in the manifest beside ``partial_days[]`` and ``missing_seal_days[]``."""
    if end < start:
        raise EdgarLedgerError("freeze window end precedes start")
    seals = store.seals()
    partial, missing = [], []
    for d in weekdays(start, end):
        st = day_status(seals, d)
        if st == "missing":
            missing.append(d.isoformat())
        elif st == "partial":
            partial.append(d.isoformat())
    if (partial or missing) and not allow_partial:
        raise EdgarLedgerError(f"freeze refused: {len(missing)} weekday(s) without a seal {missing[:5]}, "
                               f"{len(partial)} partial day(s) {partial[:5]}; pass allow_partial to record them")
    rows = [r for r in store.rows() if r.get("kind") in ("filing", "revision")
            and start.isoformat() <= r.get("index_day", "") <= end.isoformat()]
    rows.sort(key=lambda r: (r["index_day"], r["accession"], int(r.get("revision_id", 0))))
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(FREEZE_COLUMNS)
    for r in rows:
        w.writerow([_csv_cell(r.get(c)) for c in FREEZE_COLUMNS])
    data = buf.getvalue().encode("utf-8")
    manifest = {
        "schema_version": SCHEMA_VERSION, "prefix": PREFIX, "sha": sha256_bytes(data),
        "vintage": utc_now()[:10], "fetched_at": utc_now(),
        "source": "SEC EDGAR daily and full indexes and SGML submission headers (www.sec.gov/Archives), "
                  "via the edgar-ledger branch",
        "window": {"from": start.isoformat(), "to": end.isoformat()},
        "rows": len(rows), "filing_rows": sum(r["kind"] == "filing" for r in rows),
        "revision_rows": sum(r["kind"] == "revision" for r in rows),
        "weekdays": len(weekdays(start, end)), "sealed_days": len(weekdays(start, end)) - len(missing),
        "partial_days": partial, "missing_seal_days": missing, "allow_partial": bool(allow_partial),
        "coverage_rule": {"min_hdr_ok_share": FREEZE_MIN_HDR_SHARE, "complete_seal_required": True,
                          "gate": "FD00:265-267"},
        "hdr_sources": sorted({r.get("hdr_source") for r in rows if r.get("hdr_source")}),
        "columns": list(FREEZE_COLUMNS), "ledger_head": ledger_head, "tz_rule": TZ_RULE,
        "parser_version": PARSER_VERSION,
    }
    return _write_frozen(PREFIX, data, manifest, data_dir)


def freeze_fsds(store: Store, quarters: Iterable[str], *, data_dir: Path | None = None,
                ledger_head: str | None = None) -> tuple[str, dict]:
    """Freeze the FSDS extracts of ``quarters`` as ``EDGARFSDS-<sha>.csv.gz`` with a manifest
    naming each branch file's sha-256. Refuses a quarter the branch does not hold."""
    rows, files = [], []
    for qtext in quarters:
        year, q = parse_quarter(qtext)
        path = store.fsds_dir / f"sub-{year}q{q}.jsonl.gz"
        if not path.is_file():
            raise EdgarLedgerError(f"no FSDS extract for {year}Q{q} on the branch ({path.name})")
        raw = path.read_bytes()
        files.append({"file": path.name, "sha256": sha256_bytes(raw)})
        rows += [json.loads(ln) for ln in gzip.decompress(raw).decode("utf-8").splitlines() if ln.strip()]
    rows.sort(key=lambda r: (r.get("quarter", ""), r.get("adsh", "")))
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(FSDS_FREEZE_COLUMNS)
    for r in rows:
        w.writerow([_csv_cell(r.get(c)) for c in FSDS_FREEZE_COLUMNS])
    data = buf.getvalue().encode("utf-8")
    manifest = {"schema_version": SCHEMA_VERSION, "prefix": FSDS_PREFIX, "sha": sha256_bytes(data),
                "vintage": utc_now()[:10], "fetched_at": utc_now(),
                "source": "SEC Financial Statement Data Sets, sub.txt (www.sec.gov/dera), via the edgar-ledger branch",
                "sources": files, "rows": len(rows), "quarters": sorted({r.get("quarter") for r in rows}),
                "columns": list(FSDS_FREEZE_COLUMNS), "ledger_head": ledger_head, "tz_rule": TZ_RULE,
                "parser_version": PARSER_VERSION,
                "tier": "filing-specific extracted XBRL (FD00:221): derived, not raw"}
    return _write_frozen(FSDS_PREFIX, data, manifest, data_dir)


def _write_frozen(prefix: str, data: bytes, manifest: dict, data_dir: Path | None) -> tuple[str, dict]:
    sha = manifest["sha"]
    keep_private = data_store.must_be_private(data_store.sources_of(manifest))
    if keep_private:  # pragma: no cover - SEC is never restricted; kept for the policy's shape
        manifest["observations"] = data_store.private_record(sha)
    base = data_store.write_stores(data_dir).manifests
    data_store.write(prefix, data, private=keep_private, data_dir=data_dir,
                     vendors=data_store.manifest_restricted_vendors(manifest))
    data_store.write_manifest(base / f"{prefix}-{sha}.json", manifest,
                              serialize=lambda m: canonical_json(m) + "\n")
    return sha, manifest

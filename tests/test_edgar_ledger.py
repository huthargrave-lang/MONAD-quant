"""
The EDGAR ledger (src/research/edgar_ledger.py, tools/edgar_ledger.py), offline: every SEC
format is a fixture here, because the sandbox cannot reach sec.gov and the first real fetch
happens on GitHub Actions. What these guards hold shut (docs/research/EDGAR_LEDGER_QUESTION.md):

  * the eight FD-00 clock fixtures run through the PRODUCTION parser (PT-01's one consumer);
  * the F163 rollover bracket: a 17:30:14 acceptance with same-day `filed` is not a rollover;
  * one accession, however many index rows or FILER blocks: `issuer_cik` + `co_registrant_ciks`;
  * addresses, phones and tax ids never reach a row, and the verifier refuses a stray key;
  * a correction is a new `revision` row (changed header hash), an identical hash is nothing;
  * resume from the last complete seal, capped; a day with no seal refuses to freeze;
  * append-only history in a real git repository; probe verdict branches; FSDS fail-closed;
  * the user-agent and rate guards; the bootstrap README-only path.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import gzip
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
for _p in (str(REPO), str(REPO / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from src.research import edgar_ledger as el  # noqa: E402
from src.research import data_store  # noqa: E402
import edgar_ledger as cli  # noqa: E402

FIXTURES = REPO / "docs" / "research" / "data" / "fd00_sec_event_clock_fixtures_2026.json"
UA = "MONAD research test hud@monad-quant.org"


# ── fixtures ─────────────────────────────────────────────────────────────────
def _ymd(iso: str | None) -> str:
    return iso.replace("-", "") if iso else ""


def _block(kind: str, name: str, cik: str, sic: str | None, form: str, addresses: bool) -> list[str]:
    lines = [f"{kind}:", "", "\tCOMPANY DATA:\t", f"\t\tCOMPANY CONFORMED NAME:\t\t\t{name}",
             f"\t\tCENTRAL INDEX KEY:\t\t\t{cik}"]
    if sic:
        lines.append(f"\t\tSTANDARD INDUSTRIAL CLASSIFICATION:\tSERVICES-PREPACKAGED SOFTWARE [{sic}]")
    lines += ["\t\tIRS NUMBER:\t\t\t\t942404110", "\t\tSTATE OF INCORPORATION:\t\t\tDE",
              "\t\tFISCAL YEAR END:\t\t\t0930", "", "\tFILING VALUES:", f"\t\tFORM TYPE:\t\t{form}",
              "\t\tSEC ACT:\t\t1934 Act", "\t\tSEC FILE NUMBER:\t001-36743", "\t\tFILM NUMBER:\t\t26877079", ""]
    if addresses:
        lines += ["\tBUSINESS ADDRESS:\t", "\t\tSTREET 1:\t\tONE APPLE PARK WAY", "\t\tCITY:\t\t\tCUPERTINO",
                  "\t\tSTATE:\t\t\tCA", "\t\tZIP:\t\t\t95014", "\t\tBUSINESS PHONE:\t\t(408) 996-1010", "",
                  "\tMAIL ADDRESS:\t", "\t\tSTREET 1:\t\tONE APPLE PARK WAY", "\t\tCITY:\t\t\tCUPERTINO",
                  "\t\tSTATE:\t\t\tCA", "\t\tZIP:\t\t\t95014", ""]
    return lines


def sgml(accession: str, form: str, accepted_raw: str | None, filed: str, *, period: str | None = None,
         filers=(("Apple Inc.", "0000320193", "3571"),), subjects=(), public_release: str | None = None,
         date_as_of_change: str | None = None, addresses: bool = True) -> bytes:
    """A synthesized SGML submission header shaped like `<accession>.hdr.sgml`."""
    lines = [f"<SEC-HEADER>{accession}.hdr.sgml : {_ymd(filed)}"]
    if accepted_raw:
        lines.append(f"<ACCEPTANCE-DATETIME>{accepted_raw.replace('-', '').replace(':', '').replace(' ', '')}")
    if public_release:
        lines += ["<PRIVATE-TO-PUBLIC>", f"PUBLIC-REL-DATE:\t{_ymd(public_release)}"]
    lines += [f"ACCESSION NUMBER:\t\t{accession}", f"CONFORMED SUBMISSION TYPE:\t{form}",
              "PUBLIC DOCUMENT COUNT:\t\t7"]
    if period:
        lines.append(f"CONFORMED PERIOD OF REPORT:\t{_ymd(period)}")
    lines.append(f"FILED AS OF DATE:\t\t{_ymd(filed)}")
    lines.append(f"DATE AS OF CHANGE:\t\t{_ymd(date_as_of_change or filed)}")
    lines.append("")
    for name, cik, sic in filers:
        lines += _block("FILER", name, cik, sic, form, addresses)
    for name, cik, sic in subjects:
        lines += _block("SUBJECT COMPANY", name, cik, sic, form, addresses)
    lines.append("</SEC-HEADER>")
    return "\n".join(lines).encode("latin-1")


IDX_HEADER = ("Description:           Master Index of EDGAR Dissemination Feed by Form Type\n"
              "Last Data Received:    March 31, 2024\nComments:              webmaster@sec.gov\n"
              "Anonymous FTP:         ftp://ftp.sec.gov/edgar/\n \n \n"
              "Form Type   Company Name                                                  CIK         Date Filed  File Name\n"
              + "-" * 141 + "\n")


def idx_line(form: str, name: str, cik: str, filed: str, accession: str) -> str:
    return f"{form:<12}{name:<62}{int(cik):<12}{filed:<12}edgar/data/{int(cik)}/{accession}.txt\n"


def form_idx(rows) -> bytes:
    return (IDX_HEADER + "".join(idx_line(*r) for r in rows)).encode("latin-1")


SUB_HEADER = ("adsh\tcik\tname\tsic\tcountryba\tstprba\tcityba\tzipba\tbas1\tbas2\tbaph\tcountryma\tstprma\tcityma\t"
              "zipma\tmas1\tmas2\tcountryinc\tstprinc\tein\tformer\tchanged\tafs\twksi\tfye\tform\tperiod\tfy\tfp\t"
              "filed\taccepted\tprevrpt\tdetail\tinstance\tnciks\taciks")


def sub_row(adsh, cik, form, period, filed, accepted, *, afs="1-LAF", prevrpt="0", name="APPLE INC"):
    cells = {c: "" for c in SUB_HEADER.split("\t")}
    cells.update({"adsh": adsh, "cik": str(int(cik)), "name": name, "sic": "3571", "countryba": "US", "stprba": "CA",
                  "cityba": "CUPERTINO", "zipba": "95014", "bas1": "ONE APPLE PARK WAY", "baph": "4089961010",
                  "ein": "942404110", "afs": afs, "wksi": "1", "fye": "0930", "form": form, "period": period,
                  "fy": period[:4], "fp": "Q1", "filed": filed, "accepted": accepted, "prevrpt": prevrpt,
                  "detail": "1", "instance": f"{adsh}.xml", "nciks": "1", "aciks": ""})
    return "\t".join(cells[c] for c in SUB_HEADER.split("\t"))


def fsds_zip(sub_text: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("readme.htm", "<html/>")
        zf.writestr("sub.txt", sub_text)
        zf.writestr("num.txt", "adsh\ttag\n")
    return buf.getvalue()


class FakeGet:
    """`get(url, headers)` from a url -> (status, body) table; records every call."""

    def __init__(self, table=None, default=(404, b"not found")):
        self.table = dict(table or {})
        self.default = default
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, url, headers):
        self.calls.append((url, dict(headers)))
        status, body = self.table.get(url, self.default)
        if callable(body):
            body = body()
        return el.Response(status, body, {"content-length": str(len(body))})


def fetcher(get, **kw) -> el.Fetcher:
    """Spacing and backoff sleep through a recorder, so tests are instant."""
    kw.setdefault("sleep", lambda s: None)
    return el.Fetcher(get=get, agent=UA, **kw)


ACC_A, CIK_A = "0000320193-26-000013", "0000320193"
ACC_B, CIK_B = "0001652044-26-000048", "0001652044"
ACC_C, CIK_C = "0001437749-26-020535", "0001019034"
DAY = dt.date(2026, 5, 1)  # a Friday


def day_table(day: dt.date, rows, headers: dict, hdr_source="hdr_sgml") -> dict:
    """The daily index URL and header URLs for `day`, as a FakeGet table."""
    y, q = el.quarter_of(day)
    table = {el.DAILY_INDEX_URL.format(year=y, q=q, ymd=day.strftime("%Y%m%d")): (200, form_idx(rows))}
    for acc, (cik, body) in headers.items():
        table[el.header_url(hdr_source, acc, cik)] = (200, body)
    return table


def passing_summary(**over) -> dict:
    s = {"kind": "probe_summary", "probe_version": el.PROBE_VERSION, "quarter": "2024Q1", "n_requested": 3,
         "n_sampled": 3, "p0": {"status": "PASS", "requests": 9, "refused": 0, "codes": {"200": 9}},
         "p1": {"status": "PASS", "sampled": 3, "hdr_source": "hdr_sgml", "hdr_sgml_200_share": 1.0,
                "hdr_sgml_parse_share": 1.0, "txt_range_200_share": None, "txt_range_parse_share": None},
         "p2": {"status": "PASS", "fsds_slice": True, "fsds_role": "facts_and_s1prime_frame",
                "coverage_originals": 1.0, "coverage_amendments": None, "accepted_second_share": 1.0,
                "missing_columns": [], "extract_gz_bytes": 100},
         "verdict": "PASS", "hdr_source": "hdr_sgml", "at_utc": "2026-10-29T00:00:00Z", "run_id": "1"}
    s.update(over)
    return s


def write_probe(store: el.Store, summary: dict) -> Path:
    store.probe_dir.mkdir(parents=True, exist_ok=True)
    path = store.probe_dir / "PROBE-20261029T000000Z-run1.jsonl"
    rows = [{"kind": "probe_request", "url": "u", "status": 200, "bytes": 1, "sha256": "0" * 64,
             "fetched_at": "2026-10-29T00:00:00Z", "range": None}, summary]
    path.write_text("".join(el.row_line(r) for r in rows), encoding="utf-8")
    return path


def git(repo: Path, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


# ── the clock, on FD-00's fixtures ───────────────────────────────────────────
class ClockFixturesTests(unittest.TestCase):
    """The production parser is PT-01's one consumer of the FD-00 contract."""

    @classmethod
    def setUpClass(cls):
        cls.fixtures = json.loads(FIXTURES.read_text(encoding="utf-8"))["fixtures"]

    def test_the_fixture_file_has_eight_entries_seven_timestamped(self):
        self.assertEqual(len(self.fixtures), 8)
        self.assertEqual(sum(1 for f in self.fixtures if f["accepted_raw"]), 7)

    def row_for(self, fx) -> dict:
        header = parse(fx)
        entry = {"form": fx["form"], "filed": fx["filing_date"], "filer_ciks": [fx["issuer_cik"]],
                 "filer_names": [fx["entity_name"]], "path": "p", "index_rows": 1}
        return el.filing_row(header, accession=fx["accession"], index_entry=entry, index_day=fx["filing_date"],
                             idx_source="idx", idx_sha256="a" * 64, hdr_source="hdr_sgml", hdr_sha256="b" * 64,
                             hdr_bytes=10, fetched_at="2026-10-29T00:00:00Z", run_id="t")

    def test_every_timestamped_fixture_reaches_its_expected_phase_quality_and_policy(self):
        vocab = {"filing_date_rollover", "weekend_boundary", "holiday_boundary", "after_regular_close", "amendment",
                 "private_to_public", "public_time_date_only", "legacy_time_unresolved", "acceptance_missing",
                 "third_party_filer_or_agent_accession"}
        for fx in self.fixtures:
            if not fx["accepted_raw"]:
                continue
            with self.subTest(fixture=fx["id"]):
                row = self.row_for(fx)
                exp = fx["expected"]
                self.assertEqual(row["market_phase"], exp["market_phase"])
                if "acceptance_time_quality" in exp:
                    self.assertEqual(row["clock_class"], exp["acceptance_time_quality"])
                else:
                    self.assertIn(row["clock_class"], el.CLOCK_CLASSES | {None})
                if "daily_research_tradable_policy" in exp:
                    self.assertEqual(row["tradable_policy_daily"], exp["daily_research_tradable_policy"])
                self.assertTrue(set(exp["flags"]) & vocab <= set(row["quality_flags"]),
                                (exp["flags"], row["quality_flags"]))
                self.assertEqual(row["accepted_raw"], fx["accepted_raw"])
                self.assertEqual(row["issuer_cik"], fx["issuer_cik"])
                self.assertEqual(row["filed"], fx["filing_date"])
                if exp.get("accession_prefix_equals_issuer_cik") is False:
                    self.assertNotEqual(row["submitter_cik_prefix"], row["issuer_cik"])
                    self.assertIn("third_party_filer_or_agent_accession", row["quality_flags"])
                if exp.get("original_acceptance_must_not_be_used"):
                    self.assertEqual(row["dissemination_kind"], "PRIVATE-TO-PUBLIC")
                    self.assertEqual(row["public_release_date"], fx["public_release_date"])
                    self.assertEqual(row["tradable_session"], "2025-04-02")

    def test_the_eighth_fixture_is_a_contract_a_correction_is_a_new_revision_row(self):
        fx = next(f for f in self.fixtures if f["id"] == "post_acceptance_correction_contract")
        self.assertTrue(fx["expected"]["correction_is_new_revision"])
        prev = self.row_for(self.fixtures[0])
        new = dict(prev, hdr_sha256="c" * 64, accepted_raw="2026-05-01 06:02:00")
        rev = el.revision_row(prev, el.apply_clock(new), revision_id=1, revision_kind="header_changed", run_id="t2",
                              fetched_at="2026-10-30T00:00:00Z", idx_source="idx2", idx_sha256="d" * 64)
        self.assertEqual((rev["kind"], rev["revision_id"], rev["supersedes_hdr_sha256"]), ("revision", 1, "b" * 64))
        self.assertEqual(set(rev), set(el.REVISION_FIELDS))
        # the original row is untouched: a correction never edits
        self.assertEqual(prev["hdr_sha256"], "b" * 64)
        self.assertEqual(prev["kind"], "filing")

    def test_f163_rollover_bracket_17_30_14_same_day_filed_is_not_a_rollover(self):
        """F163: EDGAR's acceptance-to-filed rollover is bracketed in (17:30:14, 17:47:43]; a
        filing accepted at 17:30:14 still received a same-day filed. `filed` is read, never
        inferred, so the parser must accept both sides of the bracket without complaint."""
        same = el.tradable_time({"accession": ACC_A, "form": "8-K", "accepted_raw": "2025-03-13 17:30:14",
                                 "filed": "2025-03-13", "issuer_cik": CIK_A})
        self.assertNotIn("filing_date_rollover", same.flags)
        self.assertEqual((same.market_phase, same.tradable_session), ("late_evening", "2025-03-14"))
        rolled = el.tradable_time({"accession": ACC_A, "form": "8-K", "accepted_raw": "2025-03-13 17:47:44",
                                   "filed": "2025-03-14", "issuer_cik": CIK_A})
        self.assertIn("filing_date_rollover", rolled.flags)
        self.assertEqual(rolled.tradable_session, "2025-03-14")
        self.assertEqual(rolled.tradable_policy_daily, same.tradable_policy_daily)

    def test_regular_session_acceptance_trades_at_the_next_open_and_a_holiday_is_flagged(self):
        c = el.tradable_time({"accession": ACC_A, "form": "10-Q", "accepted_raw": "2026-07-02 11:00:00",
                              "filed": "2026-07-02", "issuer_cik": CIK_A})  # Thu before July 4 (Fri observed holiday)
        self.assertEqual((c.market_phase, c.tradable_session), ("regular_session", "2026-07-06"))
        self.assertIn("holiday_boundary", c.flags)
        self.assertIn("weekend_boundary", c.flags)

    def test_missing_acceptance_falls_back_to_the_filing_date_and_says_so(self):
        c = el.tradable_time({"accession": ACC_A, "form": "10-K", "accepted_raw": None, "filed": "2026-05-01",
                              "issuer_cik": CIK_A})
        self.assertEqual((c.clock_class, c.market_phase, c.tradable_policy_daily),
                         (None, "unknown", el.POLICY_AFTER_FILING_DATE))
        self.assertIn("acceptance_missing", c.flags)
        self.assertEqual(c.tradable_session, "2026-05-04")


def parse(fx) -> dict:
    return el.parse_sgml_header(sgml(fx["accession"], fx["form"], fx["accepted_raw"], fx["filing_date"],
                                     period=fx.get("period_of_report"),
                                     filers=((fx["entity_name"], fx["issuer_cik"], "7370"),),
                                     public_release=fx.get("public_release_date")))


# ── parsers ──────────────────────────────────────────────────────────────────
class IndexParserTests(unittest.TestCase):
    def test_two_index_rows_for_one_accession_collapse_to_one_entry_with_both_ciks(self):
        rows = [("10-K", "ALPHABET INC.", CIK_B, "2026-04-30", ACC_B),
                ("10-K", "XXVI HOLDINGS INC", "0001646972", "2026-04-30", ACC_B),
                ("10-Q", "APPLE INC", CIK_A, "2026-05-01", ACC_A),
                ("8-K", "APPLE INC", CIK_A, "2026-05-01", "0000320193-26-000014"),
                ("10-KT", "BIO KEY INTERNATIONAL INC", CIK_C, "2026-06-15", ACC_C),
                ("NT 10-K", "LATE FILER CORP", "0000001750", "2026-06-15", "0000001750-26-000001")]
        out = el.parse_form_idx(form_idx(rows))
        self.assertEqual(sorted(out), sorted([ACC_A, ACC_B, ACC_C]))
        self.assertEqual(out[ACC_B]["filer_ciks"], [CIK_B, "0001646972"])
        self.assertEqual(out[ACC_B]["index_rows"], 2)
        self.assertEqual(out[ACC_B]["filer_names"], ["ALPHABET INC.", "XXVI HOLDINGS INC"])
        self.assertEqual(out[ACC_A]["path"], f"edgar/data/{int(CIK_A)}/{ACC_A}.txt")
        self.assertEqual(out[ACC_C]["form"], "10-KT")

    def test_an_index_without_the_dashed_separator_yields_nothing(self):
        self.assertEqual(el.parse_form_idx(b"garbage\n10-K  X  1  2026-01-01  edgar/data/1/0000000001-26-000001.txt\n"), {})

    def test_deterministic_sample_is_order_independent_and_pinned_to_the_seed(self):
        accs = [f"{i:010d}-26-{i:06d}" for i in range(1, 50)]
        a = el.deterministic_sample(accs, 10)
        b = el.deterministic_sample(list(reversed(accs)), 10)
        self.assertEqual(a, b)
        self.assertEqual(len(a), 10)
        self.assertEqual(el.PROBE_SEED, "MONAD-EDGAR-PROBE-v1")
        self.assertEqual(len(el.deterministic_sample(accs[:3], 10)), 3)


class HeaderParserTests(unittest.TestCase):
    def test_filer_and_subject_blocks_become_roles_and_two_filers_become_co_registrants(self):
        data = sgml(ACC_B, "10-K", "2026-04-29 21:02:11", "2026-04-30", period="2026-03-31",
                    filers=(("Alphabet Inc.", CIK_B, "7370"), ("XXVI Holdings Inc.", "0001646972", "6770")),
                    subjects=(("Nasdaq Stock Market LLC", "0001353283", None),))
        h = el.parse_sgml_header(data)
        self.assertEqual([r["role"] for r in h["roles"]], ["filer", "filer", "subject_company"])
        self.assertEqual(h["roles"][2]["cik"], "0001353283")
        self.assertEqual((h["accepted_raw"], h["filed"], h["period"], h["form"]),
                         ("2026-04-29 21:02:11", "2026-04-30", "2026-03-31", "10-K"))
        row = el.filing_row(h, accession=ACC_B, index_entry={"form": "10-K", "filed": "2026-04-30",
                                                            "filer_ciks": [CIK_B], "filer_names": ["ALPHABET"]},
                            index_day="2026-04-30", idx_source="i", idx_sha256="a" * 64, hdr_source="hdr_sgml",
                            hdr_sha256="b" * 64, hdr_bytes=len(data), fetched_at="2026-10-29T00:00:00Z", run_id="t")
        self.assertEqual((row["issuer_cik"], row["issuer_name"], row["sic"]), (CIK_B, "Alphabet Inc.", "7370"))
        self.assertEqual(row["co_registrant_ciks"], ["0001646972"])
        self.assertEqual(set(row), set(el.FILING_FIELDS))
        self.assertEqual(row["submitter_cik_prefix"], "0001652044")

    def test_denylisted_header_fields_never_reach_the_row(self):
        data = sgml(ACC_A, "10-Q", "2026-05-01 06:01:00", "2026-05-01")
        self.assertIn(b"BUSINESS PHONE", data)
        self.assertIn(b"IRS NUMBER", data)
        h = el.parse_sgml_header(data)
        row = el.filing_row(h, accession=ACC_A, index_entry={"form": "10-Q", "filed": "2026-05-01",
                                                            "filer_ciks": [CIK_A], "filer_names": ["APPLE"]},
                            index_day="2026-05-01", idx_source="i", idx_sha256="a" * 64, hdr_source="hdr_sgml",
                            hdr_sha256="b" * 64, hdr_bytes=1, fetched_at="2026-10-29T00:00:00Z", run_id="t")
        flat = json.dumps(row)
        for leak in ("APPLE PARK", "CUPERTINO", "95014", "996-1010", "942404110", "ADDRESS", "PHONE", "IRS"):
            self.assertNotIn(leak, flat)
        self.assertEqual(el._deny_keys(row), [])
        for key in ("business_phone", "irs_number", "street_1", "zipba", "ein", "bas1", "cityma", "mail_address"):
            self.assertTrue(el.denylisted_key(key), key)
        for key in el.FILING_FIELDS + el.REVISION_EXTRA_FIELDS + el.SEAL_FIELDS + el.FSDS_FREEZE_COLUMNS:
            self.assertFalse(el.denylisted_key(key), key)

    def test_private_to_public_header_is_not_a_public_event_time(self):
        h = el.parse_sgml_header(sgml("0000950123-24-007245", "DRS/A", "2024-08-06 17:21:53", "2024-08-06",
                                      public_release="2025-04-01"))
        self.assertEqual((h["dissemination_kind"], h["public_release_date"]), ("PRIVATE-TO-PUBLIC", "2025-04-01"))

    def test_header_facts_for_the_probe_store_no_text(self):
        facts = el.header_facts(sgml(ACC_A, "10-Q", "2026-05-01 06:01:00", "2026-05-01"))
        self.assertEqual(facts, {"has_14digit_acceptance": True, "filer_blocks": 1, "has_filed_as_of_date": True})
        self.assertEqual(el.header_facts(b"<html>404</html>"),
                         {"has_14digit_acceptance": False, "filer_blocks": 0, "has_filed_as_of_date": False})


class FsdsParserTests(unittest.TestCase):
    def test_a_missing_required_column_fails_closed(self):
        text = SUB_HEADER.replace("\taccepted", "\tacc") + "\n"
        with self.assertRaises(el.EdgarLedgerError) as err:
            el.parse_fsds_sub(text)
        self.assertIn("accepted", str(err.exception))

    def test_only_whitelisted_columns_of_allowlisted_forms_survive(self):
        text = "\n".join([SUB_HEADER,
                          sub_row(ACC_A, CIK_A, "10-Q", "20260328", "20260501", "2026-05-01 06:01:00.0"),
                          sub_row("0000320193-26-000014", CIK_A, "8-K", "20260501", "20260501", "2026-05-01 16:55:58.0"),
                          sub_row(ACC_C, CIK_C, "10-KT", "20251231", "20260615", "2026-06-12 19:31:12.0", afs="5-SML")])
        rows = el.parse_fsds_sub(text)
        self.assertEqual([r["adsh"] for r in rows], [ACC_A, ACC_C])
        self.assertEqual(set(rows[0]), set(el.FSDS_COLUMNS))
        for bad in ("ein", "bas1", "baph", "cityba", "zipma", "stprma"):
            self.assertNotIn(bad, rows[0])
        derived = el.fsds_rows(text, "2026Q2")
        self.assertEqual(set(derived[0]), set(el.FSDS_FREEZE_COLUMNS))
        self.assertEqual((derived[0]["accepted_raw"], derived[0]["clock_class"], derived[0]["market_phase"]),
                         ("2026-05-01 06:01:00", "second", "premarket"))
        self.assertEqual((derived[1]["transition"], derived[1]["afs"], derived[1]["filed"]), (True, "5-SML", "2026-06-15"))
        self.assertIsNone(el.fsds_accepted_raw("2026-05-01"))


# ── guards ───────────────────────────────────────────────────────────────────
class GuardTests(unittest.TestCase):
    def test_user_agent_needs_a_contact_at_a_real_domain(self):
        self.assertEqual(el.user_agent(UA), UA)
        for bad in ("MONAD Quant research", "research research@example.com", "x a@sub.example.org",
                    "x a@example.net", "x a@foo.test", "x a@host.invalid", "x a@me.localhost"):
            with self.subTest(ua=bad), self.assertRaises(el.EdgarLedgerError):
                el.user_agent(bad)
        with self.assertRaises(el.EdgarLedgerError) as err:
            el.user_agent("MONAD")
        self.assertIn("you@your-domain", str(err.exception))

    def test_the_bdc_text_nav_hint_is_no_longer_a_reserved_domain_the_guard_would_reject(self):
        src = (REPO / "src" / "research" / "bdc_text_nav.py").read_text(encoding="utf-8")
        self.assertNotIn("contact@example.com", src)
        self.assertIn("you@your-domain", src)

    def test_min_interval_is_pinned_at_or_above_0_2_s(self):
        self.assertGreaterEqual(el.MIN_INTERVAL, 0.2)
        with self.assertRaises(el.EdgarLedgerError):
            el.Fetcher(get=FakeGet(), agent=UA, min_interval=0.1)

    def test_requests_are_spaced_and_carry_the_declared_agent(self):
        sleeps, t = [], [0.0]

        def clock():
            t[0] += 0.001
            return t[0]

        get = FakeGet({"u1": (200, b"a"), "u2": (200, b"b")})
        f = el.Fetcher(get=get, agent=UA, sleep=sleeps.append, clock=clock)
        f.fetch("u1")
        f.fetch("u2")
        self.assertTrue(sleeps and sleeps[0] >= el.MIN_INTERVAL - 0.01)
        self.assertEqual(get.calls[0][1]["User-Agent"], UA)
        f.fetch("u1", range_bytes=el.TXT_RANGE_BYTES)
        self.assertEqual(get.calls[-1][1]["Range"], f"bytes=0-{el.TXT_RANGE_BYTES}")

    def test_backoff_is_bounded_and_a_403_or_429_is_never_retried(self):
        sleeps = []
        get = FakeGet({"u": (503, b"")})
        f = el.Fetcher(get=get, agent=UA, sleep=sleeps.append, clock=lambda: 0.0)
        r = f.fetch("u")
        self.assertEqual((r.status, len(get.calls)), (503, el.MAX_RETRIES + 1))
        self.assertTrue(all(s <= el.BACKOFF_CAP_S for s in sleeps))
        for code in (403, 429):
            get = FakeGet({"u": (code, b"")})
            inputs = []
            f = el.Fetcher(get=get, agent=UA, sleep=lambda s: None, on_input=inputs.append)
            self.assertEqual(f.fetch("u").status, code)
            self.assertEqual(len(get.calls), 1)
            self.assertEqual(set(inputs[0]), set(el.INPUT_FIELDS))


# ── the probe ────────────────────────────────────────────────────────────────
def probe_rows(n=20, hdr_status=200, txt_status=None, parse_ok=True, request_statuses=(200,), fsds=None):
    rows = [{"kind": "probe_request", "url": f"u{i}", "status": s, "bytes": 1, "sha256": "0" * 64,
             "fetched_at": "t", "range": None} for i, s in enumerate(request_statuses)]
    for i in range(n):
        r = {"kind": "probe_header", "accession": f"{i:010d}-24-000001", "form": "10-K", "filed": "2024-02-15",
             "filer_cik": f"{i:010d}", "boundary_day": False, "hdr_status": hdr_status,
             "hdr_has_14digit_acceptance": parse_ok, "hdr_filer_blocks": 1 if parse_ok else 0,
             "hdr_has_filed_as_of_date": parse_ok}
        if txt_status is not None:
            r.update({"txt_status": txt_status, "txt_has_14digit_acceptance": parse_ok,
                      "txt_filer_blocks": 1 if parse_ok else 0, "txt_has_filed_as_of_date": parse_ok})
        rows.append(r)
    if fsds is not None:
        rows.append(fsds)
    return rows


def fsds_probe(coverage_orig=1.0, coverage_amend=0.3, second=1.0, columns=SUB_HEADER.split("\t"), status=200):
    return {"kind": "probe_fsds", "url": "z", "status": status, "bytes": 10, "content_length": "10", "sha256": "0" * 64,
            "members": [{"name": "sub.txt", "size": 1}], "sub_present": True, "sub_columns": list(columns),
            "sub_rows": 100, "accepted_second_share": second, "prevrpt_values": ["0", "1"], "form_counts": {"10-K": 50},
            "coverage": {"originals": {"found": 1, "total": 1, "share": coverage_orig},
                         "amendments": {"found": 1, "total": 3, "share": coverage_amend}, "by_form": {},
                         "boundary_excluded": 0}, "extract_gz_bytes": 1000, "error": None}


class ProbeVerdictTests(unittest.TestCase):
    def test_pass_hdr_sgml(self):
        s = el.probe_verdict(probe_rows(fsds=fsds_probe()), quarter="2024Q1", n_requested=20)
        self.assertEqual((s["verdict"], s["hdr_source"], s["p0"]["status"]), ("PASS", "hdr_sgml", "PASS"))
        self.assertEqual(s["p2"]["fsds_role"], "facts_and_s1prime_frame")
        self.assertTrue(el.probe_passes(s))
        self.assertEqual(s["p2"]["coverage_amendments"], 0.3)

    def test_one_404_in_twenty_still_passes_at_exactly_95_percent(self):
        rows = probe_rows(fsds=fsds_probe())
        rows[-2]["hdr_status"] = 404
        self.assertEqual(el.probe_verdict(rows)["hdr_source"], "hdr_sgml")
        rows[-3]["hdr_status"] = 404
        self.assertEqual(el.probe_verdict(rows)["verdict"], "FAIL_HEADER")

    def test_pass_txt_range_when_hdr_sgml_is_absent(self):
        s = el.probe_verdict(probe_rows(hdr_status=404, txt_status=206, fsds=fsds_probe()))
        self.assertEqual((s["verdict"], s["hdr_source"]), ("PASS_TXT_RANGE", "txt_range"))
        self.assertTrue(el.probe_passes(s))

    def test_fail_runner_on_any_403_or_429_overrides_everything(self):
        for code in (403, 429):
            s = el.probe_verdict(probe_rows(request_statuses=(200, code), fsds=fsds_probe()))
            self.assertEqual((s["verdict"], s["hdr_source"], s["p0"]["refused"]), ("FAIL_RUNNER", None, 1))
            self.assertFalse(el.probe_passes(s))

    def test_fail_header_when_neither_source_parses(self):
        s = el.probe_verdict(probe_rows(parse_ok=False, txt_status=206, fsds=fsds_probe()))
        self.assertEqual(s["verdict"], "FAIL_HEADER")
        self.assertFalse(el.probe_passes(s))
        self.assertEqual(el.probe_verdict([])["verdict"], "FAIL_HEADER")

    def test_the_coverage_rule_gates_on_originals_only_and_amendments_merely_report(self):
        s = el.probe_verdict(probe_rows(fsds=fsds_probe(coverage_orig=0.9, coverage_amend=1.0)))
        self.assertEqual((s["p2"]["status"], s["p2"]["fsds_slice"], s["p2"]["fsds_role"]), ("PASS", True, "facts_only"))
        s = el.probe_verdict(probe_rows(fsds=fsds_probe(coverage_orig=0.95, coverage_amend=0.0)))
        self.assertEqual(s["p2"]["fsds_role"], "facts_and_s1prime_frame")

    def test_p2_fails_on_a_missing_column_or_date_only_acceptance(self):
        cols = [c for c in SUB_HEADER.split("\t") if c != "prevrpt"]
        s = el.probe_verdict(probe_rows(fsds=fsds_probe(columns=cols)))
        self.assertEqual((s["p2"]["status"], s["p2"]["missing_columns"], s["verdict"]), ("FAIL_FSDS", ["prevrpt"], "PASS"))
        s = el.probe_verdict(probe_rows(fsds=fsds_probe(second=0.5)))
        self.assertFalse(s["p2"]["fsds_slice"])

    def test_boundary_accessions_leave_every_denominator(self):
        bounds = el.boundary_days(2024, 1)
        self.assertEqual(sorted(d.isoformat() for d in bounds), ["2024-01-01", "2024-01-02", "2024-03-28", "2024-03-29"])
        entries = {"a": {"form": "10-K", "filed": "2024-01-02"}, "b": {"form": "10-K", "filed": "2024-02-15"},
                   "c": {"form": "10-Q", "filed": "2024-03-29"}, "d": {"form": "10-K/A", "filed": "2024-02-20"}}
        cov = el.coverage_split(entries, {"a", "b"}, bounds)
        self.assertEqual(cov["boundary_excluded"], 2)
        self.assertEqual(cov["originals"], {"found": 1, "total": 1, "share": 1.0})
        self.assertEqual(cov["amendments"], {"found": 0, "total": 1, "share": 0.0})


class ProbeRunTests(unittest.TestCase):
    """The whole Step 0 against a fake SEC: one index, sampled headers, one FSDS zip."""

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.store = el.Store(Path(self.td.name) / "data" / "edgar_ledger")
        rows = [("10-K", "ALPHABET INC.", CIK_B, "2024-02-15", ACC_B), ("10-Q", "APPLE INC", CIK_A, "2024-02-02", ACC_A),
                ("10-K/A", "BIO KEY", CIK_C, "2024-01-02", ACC_C)]
        sub = "\n".join([SUB_HEADER, sub_row(ACC_B, CIK_B, "10-K", "20231231", "20240215", "2024-02-14 21:02:11.0"),
                         sub_row(ACC_A, CIK_A, "10-Q", "20231230", "20240202", "2024-02-02 06:01:00.0")])
        table = {el.FULL_INDEX_URL.format(year=2024, q=1): (200, form_idx(rows)),
                 el.header_url("hdr_sgml", ACC_B, CIK_B): (200, sgml(ACC_B, "10-K", "2024-02-14 21:02:11", "2024-02-15")),
                 el.header_url("hdr_sgml", ACC_A, CIK_A): (200, sgml(ACC_A, "10-Q", "2024-02-02 06:01:00", "2024-02-02")),
                 el.header_url("txt_range", ACC_C, CIK_C): (206, sgml(ACC_C, "10-K/A", "2024-01-02 16:10:41", "2024-01-02")),
                 el.FSDS_URL.format(year=2024, q=1): (200, fsds_zip(sub))}
        self.get = FakeGet(table)

    def tearDown(self):
        self.td.cleanup()

    def test_probe_writes_one_frozen_file_with_a_summary_and_no_header_text(self):
        inputs = []
        f = fetcher(self.get, on_input=inputs.append, run_id="7")
        path, summary = el.run_probe(self.store, f, "2024Q1", 500, run_id="7")
        self.assertRegex(path.name, r"^PROBE-\d{8}T\d{6}Z-run7\.jsonl$")
        self.assertEqual(summary["n_sampled"], 3)
        # 2 of 3 hdr.sgml 200 = 0.67 < 0.95; txt fallback only tried for the failed one -> FAIL_HEADER
        self.assertEqual(summary["verdict"], "FAIL_HEADER")
        self.assertEqual(summary["p0"]["status"], "PASS")
        self.assertTrue(summary["p2"]["fsds_slice"])
        cov = summary["p2"]
        self.assertEqual(cov["coverage_originals"], 1.0)      # ACC_C (10-K/A, boundary day) excluded
        self.assertIsNone(cov["coverage_amendments"])
        self.assertIsInstance(cov["extract_gz_bytes"], int)
        text = path.read_text(encoding="utf-8")
        self.assertNotIn("ACCEPTANCE-DATETIME", text)
        self.assertNotIn("APPLE PARK", text)
        kinds = [json.loads(ln)["kind"] for ln in text.splitlines()]
        self.assertEqual(kinds.count("probe_summary"), 1)
        self.assertTrue(set(kinds) <= el.PROBE_KINDS)
        self.store.append_inputs(inputs)
        self.assertEqual(el.verify_shards(self.store.root), [])
        # a probe is written once: identical rule
        with self.assertRaises(FileExistsError):
            data_store.write_exclusive(path, b"x")

    def test_a_refused_runner_is_a_row_not_a_crash(self):
        self.get.table[el.FULL_INDEX_URL.format(year=2024, q=1)] = (403, b"forbidden")
        path, summary = el.run_probe(self.store, fetcher(self.get), "2024Q1", 500, run_id="8")
        self.assertEqual((summary["verdict"], summary["hdr_source"]), ("FAIL_RUNNER", None))
        self.assertFalse(el.probe_passes(summary))


# ── the store: daily, resume, revisions, seals ───────────────────────────────
class DailyTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.store = el.Store(Path(self.td.name) / "data" / "edgar_ledger")
        self.hdr_a = sgml(ACC_A, "10-Q", "2026-05-01 06:01:00", "2026-05-01", period="2026-03-28")
        self.hdr_b = sgml(ACC_B, "10-K", "2026-04-30 21:02:11", "2026-05-01", period="2026-03-31",
                          filers=(("Alphabet Inc.", CIK_B, "7370"),))
        self.rows = [("10-Q", "APPLE INC", CIK_A, "2026-05-01", ACC_A), ("10-K", "ALPHABET INC.", CIK_B, "2026-05-01", ACC_B),
                     ("8-K", "APPLE INC", CIK_A, "2026-05-01", "0000320193-26-000099")]
        self.get = FakeGet(day_table(DAY, self.rows, {ACC_A: (CIK_A, self.hdr_a), ACC_B: (CIK_B, self.hdr_b)}))

    def tearDown(self):
        self.td.cleanup()

    def run_daily(self, today, **kw):
        inputs = []
        f = fetcher(self.get, on_input=inputs.append, run_id=kw.pop("run_id", "r1"))
        out = el.run_daily(self.store, f, today=today, run_id=f.run_id, require_committed=False, **kw)
        self.store.append_inputs(inputs)
        return out

    def test_without_a_passing_probe_nothing_is_written(self):
        out = self.run_daily(DAY + dt.timedelta(days=1))
        self.assertEqual(out["status"], "no_passing_probe")
        self.assertFalse(self.store.rows_dir.exists())
        self.assertEqual(self.get.calls, [])

    def test_a_day_yields_filing_rows_a_complete_seal_and_a_verifiable_store(self):
        write_probe(self.store, passing_summary())
        out = self.run_daily(DAY + dt.timedelta(days=1), first_day=DAY)
        self.assertEqual([d["day"] for d in out["days"]], [DAY.isoformat()])
        rows = self.store.rows()
        self.assertEqual([r["kind"] for r in rows], ["filing", "filing", "seal"])
        seal = rows[-1]
        self.assertEqual({k: seal[k] for k in ("idx_rows", "accessions", "hdr_ok", "hdr_failed", "complete")},
                         {"idx_rows": 2, "accessions": 2, "hdr_ok": 2, "hdr_failed": 0, "complete": True})
        self.assertEqual(set(seal), set(el.SEAL_FIELDS))
        by_acc = {r["accession"]: r for r in rows[:2]}
        self.assertEqual(by_acc[ACC_A]["market_phase"], "premarket")
        self.assertEqual(by_acc[ACC_B]["quality_flags"], ["filing_date_rollover"])
        self.assertEqual(by_acc[ACC_B]["hdr_source"], "hdr_sgml")
        self.assertEqual(by_acc[ACC_B]["index_day"], "2026-05-01")
        self.assertEqual(el.verify_shards(self.store.root), [])
        self.assertEqual(self.store.last_complete_seal(), DAY)

    def test_resume_from_a_partial_seal_fetches_only_what_is_missing(self):
        write_probe(self.store, passing_summary())
        self.get.table[el.header_url("hdr_sgml", ACC_B, CIK_B)] = (500, b"")
        out = self.run_daily(DAY + dt.timedelta(days=1), first_day=DAY)
        seal = out["days"][0]["seal"]
        self.assertEqual((seal["hdr_ok"], seal["hdr_failed"], seal["complete"]), (1, 1, False))
        self.assertIsNone(self.store.last_complete_seal())
        self.get.table[el.header_url("hdr_sgml", ACC_B, CIK_B)] = (200, self.hdr_b)
        calls_before = len(self.get.calls)
        out = self.run_daily(DAY + dt.timedelta(days=1), first_day=DAY, run_id="r2")
        urls = [u for u, _ in self.get.calls[calls_before:]]
        self.assertNotIn(el.header_url("hdr_sgml", ACC_A, CIK_A), urls)   # already recorded: not refetched
        self.assertIn(el.header_url("hdr_sgml", ACC_B, CIK_B), urls)
        kinds = [r["kind"] for r in self.store.rows()]
        self.assertEqual(kinds, ["filing", "seal", "filing", "seal"])
        self.assertTrue(out["days"][0]["seal"]["complete"])
        self.assertEqual(self.store.last_complete_seal(), DAY)
        self.assertEqual(el.verify_shards(self.store.root), [])

    def test_rerunning_a_day_appends_only_new_accession_sha_pairs_a_changed_header_is_a_revision(self):
        write_probe(self.store, passing_summary())
        self.run_daily(DAY + dt.timedelta(days=1), first_day=DAY)
        f = fetcher(self.get, run_id="again")
        el.process_day(self.store, f, DAY, hdr_source="hdr_sgml", run_id="again", refetch=True)
        kinds = [r["kind"] for r in self.store.rows()]
        self.assertEqual(kinds, ["filing", "filing", "seal", "seal"])   # same bytes: nothing but a seal
        changed = sgml(ACC_B, "10-K", "2026-04-30 21:02:11", "2026-05-01", period="2026-03-31",
                       filers=(("Alphabet Inc.", CIK_B, "7370"),), date_as_of_change="2026-05-04")
        self.get.table[el.header_url("hdr_sgml", ACC_B, CIK_B)] = (200, changed)
        inputs = []
        f = fetcher(self.get, on_input=inputs.append, run_id="r3")
        el.process_day(self.store, f, DAY, hdr_source="hdr_sgml", run_id="r3", refetch=True)
        self.store.append_inputs(inputs)
        rows = self.store.rows()
        rev = [r for r in rows if r["kind"] == "revision"]
        self.assertEqual(len(rev), 1)
        self.assertEqual((rev[0]["accession"], rev[0]["revision_id"], rev[0]["revision_kind"]), (ACC_B, 1, "header_changed"))
        self.assertEqual(rev[0]["supersedes_hdr_sha256"], el.sha256_bytes(self.hdr_b))
        self.assertEqual(rev[0]["hdr_sha256"], el.sha256_bytes(changed))
        self.assertEqual(rev[0]["date_as_of_change"], "2026-05-04")
        self.assertEqual(el.verify_shards(self.store.root), [])

    def test_the_cap_rolls_the_remainder_forward(self):
        write_probe(self.store, passing_summary())
        y, q = el.quarter_of(DAY)
        for d in el.weekdays(DAY, DAY + dt.timedelta(days=30)):
            self.get.table.setdefault(el.DAILY_INDEX_URL.format(year=y, q=q, ymd=d.strftime("%Y%m%d")), (404, b""))
        today = DAY + dt.timedelta(days=30)
        total = len(el.weekdays(DAY, today - dt.timedelta(days=1)))
        self.assertGreater(total, 2 * el.DAILY_CAP)
        out = self.run_daily(today, first_day=DAY)
        self.assertEqual((len(out["days"]), out["rolled_forward"]), (el.DAILY_CAP, total - el.DAILY_CAP))
        seals = self.store.seals()
        self.assertEqual(len(seals), el.DAILY_CAP)
        empty = seals[(DAY + dt.timedelta(days=3)).isoformat()]        # Monday: 404 index
        self.assertEqual((empty["accessions"], empty["complete"], empty["idx_sha256"]), (0, True, None))
        out = self.run_daily(today, run_id="r2")                       # resumes after the last complete seal
        self.assertEqual((len(out["days"]), out["rolled_forward"]), (el.DAILY_CAP, total - 2 * el.DAILY_CAP))
        self.assertEqual(out["days"][0]["day"], el.weekdays(DAY, today)[el.DAILY_CAP].isoformat())
        self.assertEqual(el.verify_shards(self.store.root), [])

    def test_a_refused_runner_stops_the_day(self):
        write_probe(self.store, passing_summary())
        self.get.table[el.header_url("hdr_sgml", ACC_A, CIK_A)] = (403, b"")
        with self.assertRaises(el.EdgarLedgerError):
            self.run_daily(DAY + dt.timedelta(days=1), first_day=DAY)


class PlanDaysTests(unittest.TestCase):
    def test_resumes_after_the_last_complete_seal_weekdays_only_capped_at_ten(self):
        days = el.plan_days(dt.date(2026, 10, 9), dt.date(2026, 10, 29))   # Fri seal, Thu today
        self.assertEqual(len(days), 10)
        self.assertEqual((days[0], days[-1]), (dt.date(2026, 10, 12), dt.date(2026, 10, 23)))
        self.assertTrue(all(d.weekday() < 5 for d in days))
        self.assertEqual(el.plan_days(dt.date(2026, 10, 9), dt.date(2026, 10, 29), cap=3),
                         [dt.date(2026, 10, 12), dt.date(2026, 10, 13), dt.date(2026, 10, 14)])

    def test_without_a_seal_it_starts_yesterday_and_a_weekend_yields_nothing(self):
        self.assertEqual(el.plan_days(None, dt.date(2026, 10, 29)), [dt.date(2026, 10, 28)])
        self.assertEqual(el.plan_days(None, dt.date(2026, 10, 26)), [])          # Monday: Sunday has no index
        self.assertEqual(el.plan_days(None, dt.date(2026, 10, 29), first_day=dt.date(2026, 10, 26)),
                         [dt.date(2026, 10, 26), dt.date(2026, 10, 27), dt.date(2026, 10, 28)])
        self.assertEqual(el.plan_days(dt.date(2026, 10, 28), dt.date(2026, 10, 29)), [])


# ── freeze ───────────────────────────────────────────────────────────────────
class FreezeTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        root = Path(self.td.name)
        self.store = el.Store(root / "ledger")
        self.data_dir = root / "data"
        self.store.rows_dir.mkdir(parents=True)
        self.inputs = []
        self.rows = []
        for i, day in enumerate(el.weekdays(dt.date(2026, 5, 4), dt.date(2026, 5, 8))):   # Mon..Fri
            acc = f"{i + 1:010d}-26-000001"
            hdr = sgml(acc, "10-Q", f"2026-05-0{day.day} 16:10:41", day.isoformat(), filers=(("X", f"{i + 1:010d}", "7370"),))
            sha = el.sha256_bytes(hdr)
            self.inputs.append({"kind": "input", "url": "u", "status": 200, "bytes": 1, "sha256": sha,
                                "fetched_at": "2026-05-09T00:00:00Z", "run_id": "r", "purpose": "p", "range": None})
            row = el.filing_row(el.parse_sgml_header(hdr), accession=acc, index_entry={"form": "10-Q", "filed": day.isoformat(),
                                "filer_ciks": [f"{i + 1:010d}"], "filer_names": ["X"]}, index_day=day.isoformat(),
                                idx_source="i", idx_sha256=None, hdr_source="hdr_sgml", hdr_sha256=sha, hdr_bytes=1,
                                fetched_at="2026-05-09T00:00:00Z", run_id="r")
            self.rows.append(row)
        self.store.append_rows(self.rows)
        self.store.append_inputs(self.inputs)
        self.seal_days = {}

    def tearDown(self):
        self.td.cleanup()

    def seal(self, day: str, **over):
        kw = {"idx_rows": 1, "accessions": 1, "hdr_ok": 1, "hdr_failed": 0, "run_id": "r", "hdr_source": "hdr_sgml",
              "idx_sha256": None, "lines_sha256": self.store.day_lines_digest(day)}
        complete = over.pop("complete", None)
        kw.update(over)
        s = el.seal_row(day, **kw)
        if complete is not None:
            s["complete"] = complete          # a hand-crafted inconsistency the gate must still catch
        self.store.append_rows([s])

    def test_a_weekday_without_a_seal_refuses_to_freeze_unless_allow_partial_records_it(self):
        for d in ("2026-05-04", "2026-05-05", "2026-05-07", "2026-05-08"):
            self.seal(d)
        with self.assertRaises(el.EdgarLedgerError) as err:
            el.freeze(self.store, dt.date(2026, 5, 4), dt.date(2026, 5, 8), data_dir=self.data_dir)
        self.assertIn("2026-05-06", str(err.exception))
        self.assertEqual(sorted(self.data_dir.glob("*")) if self.data_dir.exists() else [], [])
        sha, manifest = el.freeze(self.store, dt.date(2026, 5, 4), dt.date(2026, 5, 8), allow_partial=True,
                                  data_dir=self.data_dir)
        self.assertEqual(manifest["missing_seal_days"], ["2026-05-06"])
        self.assertEqual(manifest["partial_days"], [])
        self.assertTrue(manifest["allow_partial"])
        self.assertEqual((manifest["rows"], manifest["weekdays"], manifest["sealed_days"]), (5, 5, 4))
        csv_gz = self.data_dir / f"EDGARLEDGER-{sha}.csv.gz"
        self.assertTrue(csv_gz.is_file())
        self.assertIsNone(data_store.verify_file(csv_gz))
        stored = json.loads((self.data_dir / f"EDGARLEDGER-{sha}.json").read_text(encoding="utf-8"))
        self.assertNotIn("observations", stored)            # SEC: public, committed beside the manifest
        header = gzip.decompress(csv_gz.read_bytes()).decode().splitlines()[0]
        self.assertEqual(header, ",".join(el.FREEZE_COLUMNS))
        self.assertEqual(data_store.read("EDGARLEDGER", sha, data_dir=self.data_dir)[:10], b"kind,ledge")

    def test_an_incomplete_seal_or_low_coverage_is_partial(self):
        for d in ("2026-05-04", "2026-05-05", "2026-05-06", "2026-05-07", "2026-05-08"):
            self.seal(d)
        self.seal("2026-05-05", hdr_ok=0, hdr_failed=1)                       # the LAST seal of a day counts
        self.seal("2026-05-07", accessions=100, hdr_ok=94, hdr_failed=0, complete=True)   # 0.94 < 0.95
        with self.assertRaises(el.EdgarLedgerError):
            el.freeze(self.store, dt.date(2026, 5, 4), dt.date(2026, 5, 8), data_dir=self.data_dir)
        _, manifest = el.freeze(self.store, dt.date(2026, 5, 4), dt.date(2026, 5, 8), allow_partial=True,
                                data_dir=self.data_dir)
        self.assertEqual(manifest["partial_days"], ["2026-05-05", "2026-05-07"])
        self.assertEqual(manifest["missing_seal_days"], [])
        self.assertEqual(manifest["coverage_rule"]["min_hdr_ok_share"], 0.95)

    def test_a_fully_sealed_window_freezes_without_flags_and_is_idempotent(self):
        for d in ("2026-05-04", "2026-05-05", "2026-05-06", "2026-05-07", "2026-05-08"):
            self.seal(d)
        sha1, m1 = el.freeze(self.store, dt.date(2026, 5, 4), dt.date(2026, 5, 8), data_dir=self.data_dir)
        sha2, _ = el.freeze(self.store, dt.date(2026, 5, 4), dt.date(2026, 5, 8), data_dir=self.data_dir)
        self.assertEqual(sha1, sha2)
        self.assertEqual((m1["partial_days"], m1["missing_seal_days"], m1["allow_partial"]), ([], [], False))
        self.assertEqual(el.verify_shards(self.store.root), [])
        gaps = el.report_gaps(self.store, today=dt.date(2026, 5, 12), require_committed=False)
        self.assertEqual((gaps["missing_seal_days"], gaps["partial_days"]), (["2026-05-11"], []))

    def test_freeze_fsds_names_each_branch_file_by_sha(self):
        self.store.fsds_dir.mkdir()
        rows = el.fsds_rows("\n".join([SUB_HEADER, sub_row(ACC_A, CIK_A, "10-Q", "20260328", "20260501",
                                                           "2026-05-01 06:01:00.0")]), "2026Q2")
        payload = "".join(el.row_line(r) for r in rows).encode()
        (self.store.fsds_dir / "sub-2026q2.jsonl.gz").write_bytes(data_store.gzip_bytes(payload))
        sha, manifest = el.freeze_fsds(self.store, ["2026Q2"], data_dir=self.data_dir)
        self.assertTrue((self.data_dir / f"EDGARFSDS-{sha}.csv.gz").is_file())
        self.assertEqual(manifest["sources"][0]["file"], "sub-2026q2.jsonl.gz")
        self.assertEqual(manifest["rows"], 1)
        with self.assertRaises(el.EdgarLedgerError):
            el.freeze_fsds(self.store, ["2025Q4"], data_dir=self.data_dir)
        self.assertEqual(el.verify_shards(self.store.root), [])


# ── the verifier ─────────────────────────────────────────────────────────────
class VerifyShardsTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.store = el.Store(Path(self.td.name) / "edgar_ledger")
        hdr = sgml(ACC_A, "10-Q", "2026-05-01 06:01:00", "2026-05-01")
        self.sha = el.sha256_bytes(hdr)
        self.row = el.filing_row(el.parse_sgml_header(hdr), accession=ACC_A, index_entry={"form": "10-Q", "filed": "2026-05-01",
                                 "filer_ciks": [CIK_A], "filer_names": ["APPLE"]}, index_day="2026-05-01", idx_source="i",
                                 idx_sha256=None, hdr_source="hdr_sgml", hdr_sha256=self.sha, hdr_bytes=1,
                                 fetched_at="2026-05-02T00:00:00Z", run_id="r")
        self.store.append_rows([self.row])
        self.store.append_inputs([{"kind": "input", "url": "u", "status": 200, "bytes": 1, "sha256": self.sha,
                                   "fetched_at": "2026-05-02T00:00:00Z", "run_id": "r", "purpose": "p", "range": None}])

    def tearDown(self):
        self.td.cleanup()

    def shard(self):
        return self.store.rows_dir / "2026-05.jsonl"

    def test_a_clean_store_and_an_absent_store_pass(self):
        self.assertEqual(el.verify_shards(self.store.root), [])
        self.assertEqual(el.verify_shards(Path(self.td.name) / "nowhere"), [])

    def test_an_unknown_or_denylisted_key_is_refused(self):
        bad = dict(self.row, business_phone="650-253-0000")
        self.shard().write_text(el.row_line(bad), encoding="utf-8")
        problems = el.verify_shards(self.store.root)
        self.assertTrue(any("differ from the filing schema" in p for p in problems))
        self.assertTrue(any("denylisted" in p for p in problems))

    def test_a_stored_clock_that_disagrees_with_the_recomputation_is_refused(self):
        bad = dict(self.row, market_phase="late_evening")
        self.shard().write_text(el.row_line(bad), encoding="utf-8")
        self.assertTrue(any("recomputed" in p for p in el.verify_shards(self.store.root)))

    def test_a_cited_sha_without_an_inputs_line_and_a_misplaced_row_are_refused(self):
        bad = dict(self.row, hdr_sha256="f" * 64)
        self.shard().write_text(el.row_line(bad), encoding="utf-8")
        self.assertTrue(any("no inputs line" in p for p in el.verify_shards(self.store.root)))
        (self.store.rows_dir / "2026-06.jsonl").write_text(el.row_line(self.row), encoding="utf-8")
        self.assertTrue(any("outside shard month" in p for p in el.verify_shards(self.store.root)))
        (self.store.root / "notes.txt").write_text("x")
        self.assertTrue(any("not a ledger file" in p for p in el.verify_shards(self.store.root)))

    def test_a_revision_before_its_filing_row_and_a_duplicate_identity_are_refused(self):
        rev = el.revision_row(self.row, dict(self.row), revision_id=1, revision_kind="header_changed", run_id="r",
                              fetched_at="2026-05-02T00:00:00Z", idx_source="i", idx_sha256=None)
        self.shard().write_text(el.row_line(rev) + el.row_line(self.row) + el.row_line(self.row), encoding="utf-8")
        problems = el.verify_shards(self.store.root)
        self.assertTrue(any("precedes its filing row" in p for p in problems))
        self.assertTrue(any("repeats" in p for p in problems))

    def test_a_seal_must_hash_its_days_lines_and_a_probe_file_exactly_one_summary(self):
        seal = el.seal_row("2026-05-01", idx_rows=1, accessions=1, hdr_ok=1, hdr_failed=0, run_id="r", hdr_source="hdr_sgml",
                           idx_sha256=None, lines_sha256="0" * 64)
        self.store.append_rows([seal])
        self.assertTrue(any("lines_sha256" in p for p in el.verify_shards(self.store.root)))
        path = write_probe(self.store, passing_summary())
        path.write_text(path.read_text() + el.row_line(passing_summary()), encoding="utf-8")
        self.assertTrue(any("probe_summary rows" in p for p in el.verify_shards(self.store.root)))

    def test_rows_stay_under_4_kib(self):
        self.assertLess(len(el.row_line(self.row).encode()), el.MAX_ROW_BYTES)
        fat = dict(self.row, issuer_name="x" * 5000)
        self.shard().write_text(el.row_line(fat), encoding="utf-8")
        self.assertTrue(any("exceeds" in p for p in el.verify_shards(self.store.root)))


class AppendOnlyHistoryTests(unittest.TestCase):
    """Mirrors tests/test_trial_ledger.py's TestAppendOnlyHistory on the ledger's own rules."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        git(self.repo, "init", "-q", "-b", "base")
        git(self.repo, "config", "user.email", "t@example.com")
        git(self.repo, "config", "user.name", "t")
        self.store = el.Store(self.repo / el.LEDGER_REL)
        self.store.rows_dir.mkdir(parents=True)
        self.shard = self.store.rows_dir / "2026-05.jsonl"
        self.shard.write_text('{"kind":"seal","day":"2026-05-01"}\n', encoding="utf-8")
        self.probe = write_probe(self.store, passing_summary())
        (self.repo / "README.md").write_text("v1\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "base")
        git(self.repo, "checkout", "-q", "-b", "work")

    def tearDown(self):
        self._tmp.cleanup()

    def check(self):
        return el.verify_history("base", repo=self.repo)

    def test_untouched_and_appended_pass(self):
        self.assertEqual(self.check(), [])
        with self.shard.open("a") as fh:
            fh.write('{"kind":"seal","day":"2026-05-04"}\n')
        (self.store.rows_dir / "2026-06.jsonl").write_text("{}\n")
        self.assertEqual(self.check(), [])

    def test_edit_delete_and_rewrite_are_violations(self):
        self.shard.write_text(self.shard.read_text().replace("05-01", "05-02"))
        self.assertTrue(any("rewritten" in p for p in self.check()))
        self.shard.write_text("")
        self.assertTrue(any("rewritten" in p for p in self.check()))
        self.shard.unlink()
        self.assertTrue(any("deleted" in p for p in self.check()))

    def test_a_probe_file_may_never_change_but_the_readme_may(self):
        self.probe.write_text(self.probe.read_text() + "\n")
        self.assertTrue(any("changed" in p and "probe" in p for p in self.check()))
        self.probe.write_text(self.probe.read_text()[:-1])
        (self.repo / "README.md").write_text("rewritten\n")
        self.assertEqual(self.check(), [])

    def test_committed_then_rewritten_on_the_branch_is_caught(self):
        with self.shard.open("a") as fh:
            fh.write('{"kind":"seal","day":"2026-05-05"}\n')
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "append")
        self.shard.write_text(self.shard.read_text().replace("05-05", "05-06"))
        self.assertTrue(any("rewritten" in p for p in self.check()))

    def test_a_missing_ref_fails_loudly_the_bootstrap_case(self):
        """Condition 1: this is why the branch-creating run must not pass --against."""
        problems = el.verify_history("origin/edgar-ledger", repo=self.repo)
        self.assertEqual(len(problems), 1)
        self.assertIn("cannot resolve merge-base", problems[0])

    def test_only_a_committed_probe_counts(self):
        store = el.Store(self.repo / el.LEDGER_REL)
        self.assertIsNotNone(store.passing_probe())
        untracked = store.probe_dir / "PROBE-20261030T000000Z-run2.jsonl"
        untracked.write_text(el.row_line(passing_summary(hdr_source="txt_range", verdict="PASS_TXT_RANGE")))
        self.assertEqual(store.passing_probe()["hdr_source"], "hdr_sgml")
        self.assertEqual(store.passing_probe(require_committed=False)["hdr_source"], "txt_range")
        git(self.repo, "add", "-A")
        self.assertEqual(store.passing_probe()["hdr_source"], "txt_range")


# ── the command line ─────────────────────────────────────────────────────────
@contextlib.contextmanager
def captured():
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        yield buf


class CliTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)
        self.ledger = self.root / "ledger" / "data" / "edgar_ledger"
        self._env = dict(os.environ)
        os.environ["SEC_USER_AGENT"] = UA
        os.environ.pop(el.LEDGER_DIR_ENV, None)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)
        self.td.cleanup()

    def test_verify_on_the_bootstrap_layout_passes_without_against(self):
        """The branch-creating run: README only, no data directory, shard checks only."""
        (self.root / "ledger").mkdir(parents=True)
        (self.root / "ledger" / "README.md").write_text("readme\n")
        with captured() as out:
            rc = cli.main(["--ledger", str(self.ledger), "verify"])
        self.assertEqual(rc, 0)
        self.assertIn("0 problem(s)", out.getvalue())

    def test_daily_without_a_probe_is_a_warning_and_exit_0_fsds_refuses_with_exit_2(self):
        with captured() as out:
            rc = cli.main(["--ledger", str(self.ledger), "daily", "--uncommitted-probe-ok"], get=FakeGet())
        self.assertEqual(rc, 0)
        self.assertIn("::warning::", out.getvalue())
        self.assertFalse(self.ledger.exists())
        with captured() as out:
            rc = cli.main(["--ledger", str(self.ledger), "fsds", "--quarter", "2024Q1", "--uncommitted-probe-ok"], get=FakeGet())
        self.assertEqual(rc, 2)
        self.assertIn("REFUSED", out.getvalue())

    def test_a_committed_probe_is_required_by_default(self):
        git(self.root, "init", "-q", "-b", "edgar-ledger")
        store = el.Store(self.ledger)
        write_probe(store, passing_summary())
        with captured() as out:
            rc = cli.main(["--ledger", str(self.ledger), "daily", "--today", "2026-05-02"], get=FakeGet())
        self.assertEqual((rc, "::warning::" in out.getvalue()), (0, True))
        self.assertFalse(store.rows_dir.exists())

    def test_daily_then_verify_against_then_freeze_through_the_cli(self):
        git(self.root, "init", "-q", "-b", "edgar-ledger")
        git(self.root, "config", "user.email", "t@example.com")
        git(self.root, "config", "user.name", "t")
        store = el.Store(self.ledger)
        write_probe(store, passing_summary())
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "probe")
        hdr_a = sgml(ACC_A, "10-Q", "2026-05-01 06:01:00", "2026-05-01")
        get = FakeGet(day_table(DAY, [("10-Q", "APPLE INC", CIK_A, "2026-05-01", ACC_A)], {ACC_A: (CIK_A, hdr_a)}))
        with captured() as out:
            rc = cli.main(["--ledger", str(self.ledger), "daily", "--today", "2026-05-02", "--first-day", "2026-05-01"], get=get)
        self.assertEqual(rc, 0, out.getvalue())
        self.assertIn("complete True", out.getvalue())
        with captured() as out:
            rc = cli.main(["--ledger", str(self.ledger), "verify", "--against", "HEAD", "--report-gaps", "--today", "2026-05-02"])
        self.assertEqual(rc, 0, out.getvalue())
        self.assertIn('"missing_seal_days": []', out.getvalue())
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "day")
        shard = store.rows_dir / "2026-05.jsonl"
        shard.write_text(shard.read_text().replace("06:01:00", "06:01:01"))
        with captured() as out:
            rc = cli.main(["--ledger", str(self.ledger), "verify", "--against", "HEAD~1"])
        self.assertEqual(rc, 1)
        self.assertIn("FAIL", out.getvalue())
        git(self.root, "checkout", "-q", "--", str(shard))
        data_dir = self.root / "frozen"
        with captured() as out:
            rc = cli.main(["--ledger", str(self.ledger), "freeze", "--from", "2026-04-27", "--to", "2026-05-01",
                           "--data-dir", str(data_dir)])
        self.assertEqual(rc, 2)
        self.assertIn("REFUSED", out.getvalue())
        with captured() as out:
            rc = cli.main(["--ledger", str(self.ledger), "freeze", "--from", "2026-05-01", "--to", "2026-05-01",
                           "--data-dir", str(data_dir)])
        self.assertEqual(rc, 0, out.getvalue())
        self.assertIn("EDGARLEDGER-", out.getvalue())
        self.assertEqual(len(list(data_dir.glob("EDGARLEDGER-*.csv.gz"))), 1)

    def test_fsds_through_the_cli_writes_once(self):
        store = el.Store(self.ledger)
        write_probe(store, passing_summary())
        sub = "\n".join([SUB_HEADER, sub_row(ACC_A, CIK_A, "10-Q", "20231230", "20240202", "2024-02-02 06:01:00.0")])
        get = FakeGet({el.FSDS_URL.format(year=2024, q=1): (200, fsds_zip(sub))})
        with captured() as out:
            rc = cli.main(["--ledger", str(self.ledger), "fsds", "--quarter", "2024Q1", "--uncommitted-probe-ok"], get=get)
        self.assertEqual(rc, 0, out.getvalue())
        target = store.fsds_dir / "sub-2024q1.jsonl.gz"
        self.assertTrue(target.is_file())
        rows = [json.loads(ln) for ln in gzip.decompress(target.read_bytes()).decode().splitlines()]
        self.assertEqual((len(rows), rows[0]["adsh"], rows[0]["market_phase"]), (1, ACC_A, "premarket"))
        with captured() as out:
            cli.main(["--ledger", str(self.ledger), "fsds", "--quarter", "2024Q1", "--uncommitted-probe-ok"], get=get)
        self.assertIn('"exists"', out.getvalue())
        self.assertEqual(el.verify_shards(store.root), [])
        self.assertEqual(len(store.inputs()), 1)

    def test_the_schema_constants_are_what_the_debate_fixed(self):
        """Pins against drift: the fixture enum, the seal fields, the allowlist, the thresholds."""
        self.assertEqual(el.CLOCK_CLASSES, {"second", "legacy_midnight_display", "not_public_event_time"})
        for f in ("day", "idx_rows", "accessions", "hdr_ok", "hdr_failed", "complete", "run_id"):
            self.assertIn(f, el.SEAL_FIELDS)
        for f in ("co_registrant_ciks", "hdr_source", "clock_class", "issuer_cik", "submitter_cik_prefix"):
            self.assertIn(f, el.FILING_FIELDS)
        self.assertEqual(el.ALLOWLIST[:4], ("10-K", "10-K/A", "10-Q", "10-Q/A"))
        self.assertEqual((el.P1_STATUS_SHARE, el.P1_PARSE_SHARE, el.P2_SECOND_SHARE, el.COVERAGE_SHARE,
                          el.FREEZE_MIN_HDR_SHARE, el.DAILY_CAP), (0.95, 0.99, 0.99, 0.95, 0.95, 10))
        self.assertEqual(el.ORIGINAL_FORMS, {"10-K", "10-Q"})
        self.assertEqual(el.history_rule("data/edgar_ledger/rows/2026-05.jsonl"), "prefix")
        self.assertEqual(el.history_rule("data/edgar_ledger/inputs/2026-05.jsonl"), "prefix")
        self.assertEqual(el.history_rule("data/edgar_ledger/probe/PROBE-x.jsonl"), "identical")
        self.assertEqual(el.history_rule("data/edgar_ledger/fsds/sub-2024q1.jsonl.gz"), "identical")
        self.assertIsNone(el.history_rule("README.md"))


if __name__ == "__main__":
    unittest.main()

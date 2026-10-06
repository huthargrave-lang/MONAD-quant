"""
MONAD Quant — BDC NAV per share before XBRL: read from the original 10-Q/10-K documents.

Business development companies were not required to tag their financial statements in
XBRL until 2022 (the 2020 closed-end fund offering reform), so every pre-2022 value in
companyfacts is a comparative filed in 2022 or later: not point in time. The original
filings are on EDGAR, and each one's statement of assets and liabilities states net asset
value per share for its period end. This module reads it from there:

* ``filings(cik)``: every original 10-Q and 10-K (no amendments) with its filing date,
  report date and primary document, from the submissions API (recent and paged history).
* ``extract_nav(html)``: the first table row labelled net asset value (or net assets) per
  share, its first number: the balance-sheet value for the filing's own period end.
* An observation is (report date, NAV, filing date); it is KNOWN the day after filing,
  as in bdc_data.

Validation (``validate``): on filings that also carry tagged us-gaap NetAssetValuePerShare
(2022 onward) the extracted value must equal the tag for its period end to the cent.
The extractor is only trusted on the pre-XBRL era if it reproduces the tagged era.

SEC's fair-access policy asks for a contact in the User-Agent; it is read from the
``SEC_USER_AGENT`` environment variable and never stored in the repository.
"""
from __future__ import annotations

import html as _html
import json
import os
import re
import time
import urllib.request
from typing import Callable

SUBMISSIONS = "https://data.sec.gov/submissions/{}"
ARCHIVE = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}"
PAUSE = 0.12
MAX_BYTES = 20_000_000
FORMS = ("10-Q", "10-K")

#: The label must START the cell: "net asset value per share", "net assets per common
#: share", "... at end of period". Rows that merely mention it ("10% premium to net asset
#: value per share", "(decrease) increase in net assets per share") are other tables, and
#: "at beginning of" rows hold the prior period (validation on the tagged era, 2026-10-06).
_LABEL = re.compile(r"^\W*net\s+assets?\s+(?:value\s+)?per\s+(?:common\s+)?share", re.I)
_NOT_CURRENT = re.compile(r"beginning\s+of", re.I)
_NUM = re.compile(r"(?<![\d.])\(?\$?\s*(\d{1,3}(?:,\d{3})*|\d+)\.(\d{2,4})\)?")
_ROW_END = re.compile(r"</tr\s*>", re.I)
_CELL_END = re.compile(r"</t[dh]\s*>", re.I)
_TAG = re.compile(r"<[^>]+>")


def user_agent() -> str:
    ua = os.environ.get("SEC_USER_AGENT", "").strip()
    if "@" not in ua:
        raise RuntimeError("set SEC_USER_AGENT to 'name contact@example.com' (SEC fair-access policy)")
    return ua


def _get(url: str, *, max_bytes: int | None = None) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": user_agent(),
                                               "Accept-Encoding": "identity"})
    with urllib.request.urlopen(req, timeout=90) as r:  # noqa: S310
        return r.read(max_bytes) if max_bytes else r.read()


def filings(cik: int, *, get: Callable[..., bytes] = _get) -> list[dict]:
    """Original 10-Q/10-K filings, oldest first: accession, filed, report_date, form, doc."""
    first = json.loads(get(SUBMISSIONS.format(f"CIK{cik:010d}.json")))
    pages = [first["filings"]["recent"]]
    for f in first["filings"].get("files", []):
        time.sleep(PAUSE)
        pages.append(json.loads(get(SUBMISSIONS.format(f["name"]))))
    out = []
    for p in pages:
        for acc, form, filed, rep, doc in zip(p["accessionNumber"], p["form"], p["filingDate"],
                                              p["reportDate"], p["primaryDocument"]):
            if form in FORMS and rep and doc:
                out.append({"accession": acc, "form": form, "filed": filed, "report_date": rep,
                            "doc": doc})
    return sorted(out, key=lambda r: (r["filed"], r["accession"]))


def _rows(text: str):
    for raw in _ROW_END.split(text):
        cells = [_html.unescape(_TAG.sub(" ", c)).replace("\xa0", " ") for c in _CELL_END.split(raw)]
        cells = [re.sub(r"\s+", " ", c).strip() for c in cells]
        yield [c for c in cells if c]


_TABLE_END = re.compile(r"</table\s*>", re.I)
_BALANCE_ROW = re.compile(r"^\W*total\s+(?:liabilities|net\s+assets)\b", re.I)


def _row_values(cells: list[str]) -> list[float]:
    """The NAV-per-share values in a labelled row, in column order ([] if not such a row)."""
    if not cells or not _LABEL.search(cells[0]) or _NOT_CURRENT.search(cells[0]) \
            or len(cells[0]) > 120:
        return []
    out = []
    for c in cells[1:]:
        m = _NUM.search(c)
        if m and "(" not in c:
            v = float(m.group(1).replace(",", "") + "." + m.group(2))
            if 0.5 <= v <= 1000:
                out.append(v)
    return out


def extract_balance_row(doc: str) -> list[float]:
    """Every value of the row ``extract_nav`` reads: [this period, prior period, ...]. In a
    balance sheet the second column is the prior fiscal year end, which the pre-2022
    comparative cross-check compares with that year end's own filing."""
    fallback = []
    for table in _TABLE_END.split(doc):
        rows = list(_rows(table))
        is_balance = any(r and _BALANCE_ROW.search(r[0]) for r in rows)
        for cells in rows:
            vals = _row_values(cells)
            if not vals:
                continue
            if is_balance:
                return vals
            if not fallback:
                fallback = vals
    return fallback


def extract_nav(doc: str) -> float | None:
    """The balance-sheet NAV per share: the first NAV-per-share row, and its first number
    (the filing's own period), inside the first table that is a statement of assets and
    liabilities (it has a "total liabilities" or "total net assets" row). Falls back to the
    first NAV-per-share row anywhere. None if no such row parses.

    The table test excludes example tables (a 10-K's hypothetical "sales below NAV"
    dilution table states NAV per share as $10.00) and highlights tables."""
    vals = extract_balance_row(doc)
    return vals[0] if vals else None


def nav_observations(cik: int, *, get: Callable[..., bytes] = _get,
                     since: str = "2010-01-01", until: str = "9999-12-31") -> tuple[list[dict], list[dict]]:
    """(observations, failures) for one filer's original 10-Q/10-K in [since, until]."""
    obs, fails = [], []
    for f in filings(cik, get=get):
        if not (since <= f["filed"] <= until):
            continue
        acc = f["accession"].replace("-", "")
        time.sleep(PAUSE)
        try:
            doc = get(ARCHIVE.format(cik=cik, acc=acc, doc=f["doc"]), max_bytes=MAX_BYTES)
            vals = extract_balance_row(doc.decode("utf-8", errors="replace"))
            nav = vals[0] if vals else None
        except Exception as exc:  # noqa: BLE001 — recorded, the filing is skipped
            fails.append({**f, "error": f"{type(exc).__name__}: {exc}"})
            continue
        if nav is None:
            fails.append({**f, "error": "no NAV-per-share row"})
            continue
        obs.append({**f, "nav": nav, "prior": vals[1] if len(vals) > 1 else None})
    return obs, fails


TEXT_SOURCE = ("original 10-Q/10-K filings, statement of assets and liabilities "
               "(src/research/bdc_text_nav.py)")


def first_per_period(obs: list[dict]) -> list[dict]:
    """The first original filing reporting each period end (later ones are comparatives
    or restatements, known later)."""
    first = {}
    for o in sorted(obs, key=lambda o: (o["filed"], o["accession"])):
        first.setdefault(o["report_date"], o)
    return sorted(first.values(), key=lambda o: o["report_date"])


def tagged_navs(facts: dict) -> dict:
    """{period end: (value, filed)} of the first-filed us-gaap NetAssetValuePerShare in a
    10-Q/10-K, from a companyfacts document."""
    units = facts.get("facts", {}).get("us-gaap", {}).get("NetAssetValuePerShare", {}).get("units", {})
    out = {}
    for v in units.get("USD/shares", []):
        if v.get("form") in FORMS and v.get("val") is not None:
            if v["end"] not in out or v["filed"] < out[v["end"]][1]:
                out[v["end"]] = (float(v["val"]), v["filed"])
    return out


def validate(extracted: dict, tagged: dict, *, tolerance: float = 0.01) -> dict:
    """Agreement of extracted NAVs with tagged ones on shared period ends.

    ``extracted`` and ``tagged`` map ticker -> {period end: value}. Returns the counts and
    every disagreement, for the precondition in docs/research/BDC_PREPERIOD_TEST.md."""
    compared, agree, bad, filers = 0, 0, [], set()
    for tk, ext in extracted.items():
        for end, v in ext.items():
            if end in tagged.get(tk, {}):
                compared += 1
                filers.add(tk)
                tv = tagged[tk][end]
                if abs(v - tv) <= tolerance + 1e-9:
                    agree += 1
                else:
                    bad.append({"ticker": tk, "period_end": end, "extracted": v, "tagged": tv})
    return {"compared": compared, "agree": agree, "filers": len(filers),
            "share": agree / compared if compared else 0.0, "disagreements": bad}


#: Ratios that a share split or reverse split produces between a value and its restated
#: comparative (the cross-check excludes these and lists them).
SPLIT_RATIOS = (2, 3, 4, 5, 8, 10, 15, 20)


def comparative_cross_check(obs: list[dict], *, before: str, tolerance: float = 0.01) -> dict:
    """Pre-XBRL check of the extractor (BDC_PREPERIOD_TEST.md, amendment 1): each fiscal
    year-end NAV a 10-K reports (period end before ``before``) against the prior-period
    column of the NEXT original filing, whose balance sheet compares with that year end.
    Pairs whose ratio is a split ratio are excluded and listed."""
    ordered = sorted(obs, key=lambda o: (o["filed"], o["accession"]))
    compared, agree, bad, splits = 0, 0, [], []
    for i, o in enumerate(ordered):
        if o["form"] != "10-K" or o["report_date"] >= before:
            continue
        nxt = next((n for n in ordered[i + 1:] if n["filed"] > o["filed"]), None)
        if nxt is None or nxt.get("prior") is None:
            continue
        ratio = max(o["nav"], nxt["prior"]) / min(o["nav"], nxt["prior"])
        if any(abs(ratio - k) <= 0.02 * k for k in SPLIT_RATIOS):
            splits.append({"period_end": o["report_date"], "value": o["nav"], "next_prior": nxt["prior"]})
            continue
        compared += 1
        if abs(o["nav"] - nxt["prior"]) <= tolerance + 1e-9:
            agree += 1
        else:
            bad.append({"period_end": o["report_date"], "value": o["nav"], "next_prior": nxt["prior"],
                        "next_filed": nxt["filed"]})
    return {"compared": compared, "agree": agree, "disagreements": bad, "splits": splits}

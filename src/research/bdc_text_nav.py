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

_LABEL = re.compile(r"net\s+asset\s+value\s+per\s+(?:common\s+)?share|net\s+assets\s+per\s+(?:common\s+)?share",
                    re.I)
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


def extract_nav(doc: str) -> float | None:
    """The balance-sheet NAV per share: the first table row whose label names it, and the
    first number in that row (the filing's own period). None if no such row parses."""
    for cells in _rows(doc):
        if not cells or not _LABEL.search(cells[0]) or len(cells[0]) > 120:
            continue
        for c in cells[1:]:
            m = _NUM.search(c)
            if m and "(" not in c:
                v = float(m.group(1).replace(",", "") + "." + m.group(2))
                if 0.5 <= v <= 1000:
                    return v
    return None


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
            nav = extract_nav(doc.decode("utf-8", errors="replace"))
        except Exception as exc:  # noqa: BLE001 — recorded, the filing is skipped
            fails.append({**f, "error": f"{type(exc).__name__}: {exc}"})
            continue
        if nav is None:
            fails.append({**f, "error": "no NAV-per-share row"})
            continue
        obs.append({**f, "nav": nav})
    return obs, fails

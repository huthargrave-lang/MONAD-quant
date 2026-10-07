"""
MONAD Quant — company-stated GAAP book value per common share for mortgage REITs, read
from original filings (docs/research/MREIT_DISCOUNT_TEST_V2.md; v1's XBRL derivation
missed series-tagged preferred stock).

Every rule here is the frozen protocol's:

* sources: original 10-Q/10-K primary documents, and 8-K earnings-release exhibits (99);
* label: "book value per common share" / "book value per share", rejecting labels that
  also say tangible, adjusted, economic, excluding, diluted, non-GAAP, pro forma or
  estimated;
* value: in a table row, the first dollar amount after the label; in prose, the first
  dollar amount within 120 characters after it; (0, 500] only;
* period: a 10-Q/10-K's report date; an 8-K's latest calendar quarter end before its
  filing date, if filed within 75 days of it;
* known: the earliest filing stating a value for the period, the day after its date;
* the first accepted occurrence in document order is the filing's value.
"""
from __future__ import annotations

import datetime as _dt
import html as _html
import json
import re
import time
from typing import Callable

from src.research.bdc_text_nav import ARCHIVE, PAUSE, SUBMISSIONS, _get

LABEL = re.compile(r"book\s+value\s+per\s+(?:common\s+)?share", re.I)
REJECT = re.compile(r"tangible|adjusted|economic|excluding|diluted|non[-\s]?gaap|pro\s+forma|estimated", re.I)
DOLLAR = re.compile(r"\$\s*(\d{1,3}(?:,\d{3})*|\d+)\.(\d{2,4})")
NUMBER = re.compile(r"(?<![\d.])(\d{1,3}(?:,\d{3})*|\d+)\.(\d{2,4})(?![\d])")
PROSE_WINDOW = 120
EIGHT_K_MAX_DAYS = 75
MAX_BYTES = 20_000_000

_TABLE = re.compile(r"<table\b.*?</table\s*>", re.I | re.S)
_ROW_END = re.compile(r"</tr\s*>", re.I)
_CELL_END = re.compile(r"</t[dh]\s*>", re.I)
_TAG = re.compile(r"<[^>]+>")


def _text(fragment: str) -> str:
    t = _html.unescape(_TAG.sub(" ", fragment)).replace("\xa0", " ")
    return re.sub(r"\s+", " ", t).strip()


def _num(m) -> float:
    return float(m.group(1).replace(",", "") + "." + m.group(2))


def _from_row(cells: list[str]) -> float | None:
    if not cells or not LABEL.search(cells[0]) or REJECT.search(cells[0]):
        return None
    for c in cells[1:]:
        m = DOLLAR.search(c) or NUMBER.search(c)
        if m and "(" not in c:
            v = _num(m)
            return v if 0 < v <= 500 else None
    return None


def _from_prose(text: str) -> float | None:
    for m in LABEL.finditer(text):
        start = max(text.rfind(".", 0, m.start()), text.rfind(";", 0, m.start())) + 1
        label = text[start:m.end()]
        if REJECT.search(label):
            continue
        d = DOLLAR.search(text, m.end(), m.end() + PROSE_WINDOW)
        if d:
            v = _num(d)
            if 0 < v <= 500:
                return v
    return None


def extract(doc: str) -> float | None:
    """The first accepted book value per common share in document order (tables and the
    prose between them)."""
    pos = 0
    for tm in _TABLE.finditer(doc):
        v = _from_prose(_text(doc[pos:tm.start()]))
        if v is not None:
            return v
        for raw in _ROW_END.split(tm.group(0)):
            cells = [c for c in (_text(x) for x in _CELL_END.split(raw)) if c]
            v = _from_row(cells)
            if v is not None:
                return v
        pos = tm.end()
    return _from_prose(_text(doc[pos:]))


def quarter_end_before(day: _dt.date) -> _dt.date:
    q = (day.month - 1) // 3
    if q == 0:
        return _dt.date(day.year - 1, 12, 31)
    month = 3 * q
    return _dt.date(day.year, month, {3: 31, 6: 30, 9: 30}[month])


def filings(cik: int, *, get: Callable[..., bytes] = _get) -> list[dict]:
    """Original 10-Q/10-K and Item 2.02 8-K filings, oldest first, with the period each
    would state (protocol period rule; 8-Ks too late after their quarter are dropped)."""
    first = json.loads(get(SUBMISSIONS.format(f"CIK{cik:010d}.json")))
    pages = [first["filings"]["recent"]]
    for f in first["filings"].get("files", []):
        time.sleep(PAUSE)
        pages.append(json.loads(get(SUBMISSIONS.format(f["name"]))))
    out = []
    for p in pages:
        items = p.get("items") or [""] * len(p["accessionNumber"])
        for acc, form, filed, rep, doc, it in zip(p["accessionNumber"], p["form"], p["filingDate"],
                                                  p["reportDate"], p["primaryDocument"], items):
            if form in ("10-Q", "10-K") and rep and doc:
                out.append({"accession": acc, "form": form, "filed": filed, "period": rep, "doc": doc})
            elif form == "8-K" and "2.02" in (it or ""):
                fd = _dt.date.fromisoformat(filed)
                qe = quarter_end_before(fd)
                if (fd - qe).days <= EIGHT_K_MAX_DAYS:
                    out.append({"accession": acc, "form": form, "filed": filed,
                                "period": qe.isoformat(), "doc": None})
    return sorted(out, key=lambda r: (r["filed"], r["accession"]))


def _exhibits(cik: int, acc: str, get) -> list[str]:
    idx = json.loads(get(ARCHIVE.format(cik=cik, acc=acc, doc="index.json")))
    names = [i["name"] for i in idx.get("directory", {}).get("item", [])]
    return [n for n in names if re.search(r"ex(?:hibit)?[-_]?99", n, re.I) and n.lower().endswith((".htm", ".html", ".txt"))]


def observations(cik: int, *, get: Callable[..., bytes] = _get, since: str = "2011-01-01"
                 ) -> tuple[list[dict], list[dict]]:
    """(per-filing accepted values, failures) for one filer."""
    obs, fails = [], []
    for f in filings(cik, get=get):
        if f["filed"] < since:
            continue
        acc = f["accession"].replace("-", "")
        try:
            docs = [f["doc"]] if f["doc"] else _exhibits(cik, acc, get)
            time.sleep(PAUSE)
            value = None
            for d in docs:
                raw = get(ARCHIVE.format(cik=cik, acc=acc, doc=d), max_bytes=MAX_BYTES)
                time.sleep(PAUSE)
                value = extract(raw.decode("utf-8", errors="replace"))
                if value is not None:
                    break
        except Exception as exc:  # noqa: BLE001 — recorded; the filing is skipped
            fails.append({**f, "error": f"{type(exc).__name__}: {exc}"})
            continue
        if value is None:
            fails.append({**f, "error": "no accepted book value per common share"})
        else:
            obs.append({**f, "bv": value})
    return obs, fails


def first_statement(obs: list[dict]) -> list[dict]:
    """Per period, the earliest filing stating a value (protocol known-date rule)."""
    first = {}
    for o in sorted(obs, key=lambda o: (o["filed"], o["accession"])):
        first.setdefault(o["period"], o)
    return sorted(first.values(), key=lambda o: o["period"])

"""
MONAD Quant — Treasury coupon auctions, as a dated fixture with provenance.

Lou, Yan & Zhang (2013, "Anticipated and Repeated Shocks in Liquid Markets", RFS) found
Treasury prices fall in the days before a coupon auction, as dealers make room for the new
supply, and recover after it. A strategy may act on an auction only once it is ANNOUNCED:
each record carries TreasuryDirect's ``announcementDate``, and the tilt class refuses to
hold a pre-auction position decided before that date.

Source: TreasuryDirect's securities search web service (``TA_WS/securities/search``,
JSON), every Note and Bond auction, with each page's sha256 recorded. Reopenings are
auctions too (new supply), so they are kept. TIPS and FRNs are excluded: their buyers and
hedges differ from nominal coupons'.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import urllib.request
from pathlib import Path
from typing import Callable

from src.research.trials import REPO, LedgerError, canonical_json

FIXTURE = REPO / "docs/research/data/treasury_coupon_auctions.json"
#: The ``search`` endpoint filtered by auction date. (``auctioned`` ignores its page
#: number, so paging through it repeats the newest page forever; probed 2026-10-06.)
API = "https://www.treasurydirect.gov/TA_WS/securities/search"
NOMINAL_TERMS = {"2-Year", "3-Year", "5-Year", "7-Year", "10-Year", "20-Year", "30-Year"}


class AuctionError(LedgerError):
    pass


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research; MONAD-quant)"})
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 — fixed https host
        return resp.read()


def _original_term(term: str) -> str | None:
    """The nominal tenor a security belongs to: '10-Year' -> '10-Year'; a reopening's
    remaining term '9-Year 10-Month' -> '10-Year' (the smallest nominal tenor at least as
    long as the remaining term). None for anything that is not a nominal coupon term."""
    import re
    m = re.fullmatch(r"(\d+)-Year(?:\s+(\d+)-Month)?", term.strip())
    if not m:
        return None
    years = int(m.group(1)) + (int(m.group(2)) / 12 if m.group(2) else 0)
    for t in sorted(NOMINAL_TERMS, key=lambda x: int(x.split("-")[0])):
        if int(t.split("-")[0]) >= years - 1e-9:
            return t
    return None


def parse(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        if r.get("securityType") not in ("Note", "Bond"):
            continue
        if (r.get("tips") == "Yes" or r.get("floatingRate") == "Yes"
                or "TIPS" in (r.get("type") or "") or "FRN" in (r.get("type") or "")):
            continue
        term = _original_term(r.get("securityTerm") or "")
        if term is None:
            continue
        auction = (r.get("auctionDate") or "")[:10]
        announced = (r.get("announcementDate") or "")[:10]
        if not auction or not announced:
            raise AuctionError(f"auction {r.get('cusip')} lacks an auction or announcement date")
        if announced > auction:
            raise AuctionError(f"auction {r.get('cusip')} announced after it was held")
        out.append({"cusip": r["cusip"], "term": term, "auction": auction, "announced": announced,
                    "reopening": r.get("reopening") == "Yes"})
    return out


def build(first_year: int, last_year: int | None = None, *,
          fetcher: Callable[[str], bytes] = fetch) -> dict:
    """Every nominal coupon auction from ``first_year`` through ``last_year`` (default:
    this year), one search request per security type per year."""
    last_year = last_year or _dt.date.today().year
    pages, rows = [], []
    for year in range(first_year, last_year + 1):
        for kind in ("Note", "Bond"):
            url = (f"{API}?format=json&type={kind}&dateFieldName=auctionDate"
                   f"&startDate={year}-01-01&endDate={year}-12-31")
            raw = fetcher(url)
            pages.append({"url": url, "sha256": hashlib.sha256(raw).hexdigest()})
            rows += json.loads(raw)
    auctions = {a["cusip"] + a["auction"]: a for a in parse(rows)}
    records = sorted(auctions.values(), key=lambda a: (a["auction"], a["term"]))
    if not records:
        raise AuctionError("no coupon auctions parsed")
    fetched_at = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    return {"schema_version": 1, "source": "TreasuryDirect TA_WS securities/search (auctionDate)",
            "pages": pages, "fetched_at": fetched_at, "vintage": fetched_at[:10],
            "auctions": records}


def write_fixture(record: dict, path: Path = FIXTURE) -> None:
    path.write_text(canonical_json(record) + "\n", encoding="utf-8")


def auctions(path: Path = FIXTURE) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["auctions"]

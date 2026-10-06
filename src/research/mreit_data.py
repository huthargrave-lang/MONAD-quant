"""
MONAD Quant — Mortgage REIT book value per common share from SEC XBRL, point in time.

A second disjoint test of the CEF discount mechanism (H404701/H404702): mortgage REITs
trade around book value per common share the way closed-end funds trade around NAV. Their
book is mostly marked-to-market securities. They are operating companies, so unlike BDCs
(bdc_data) they have filed XBRL since 2011, and the point-in-time history is about 15 years.

Universe (``build_universe``), frozen 2026-10-06 before any mREIT price was loaded:
* a filer that, in any quarterly instant frame 2012-2026, reported us-gaap
  SecuritiesSoldUnderAgreementsToRepurchase of at least 25% of its us-gaap Assets (repo
  funding is the mortgage REIT's structure; equity REITs do not use it);
* SIC code 6798 (real estate investment trusts) in data.sec.gov submissions;
* exchange-listed today with a COMMON ticker (the first without a "-" class suffix); a
  filer whose only listed securities are preferred shares is excluded, since its book
  value per common share has no traded price. Survivorship: listed today only.

Book value per common share (``bv_history``), one observation per period end:
    (StockholdersEquity - preferred) / CommonStockSharesOutstanding
where preferred is PreferredStockLiquidationPreferenceValue if reported for that period
end, else PreferredStockValue, else 0. Every input must come from the SAME 10-Q/10-K
filing (the same accession) that first reports the period end. The observation is known
the day after that filing's date. Values outside (0, 500] are dropped as malformed.
"""
from __future__ import annotations

import datetime as _dt
import json
import time
import xml.etree.ElementTree as ET
from typing import Callable

from src.research.bdc_text_nav import _get as _get_bytes

API = "https://data.sec.gov/api/xbrl/"
SUBMISSIONS = "https://data.sec.gov/submissions/CIK{:010d}.json"
LISTED_EXCHANGES = {"Nasdaq", "NYSE", "NYSE MKT", "NYSE American"}
REPO_SHARE = 0.25
REIT_SIC = "6798"
PAUSE = 0.12
FORMS = ("10-Q", "10-K")


def _get(url: str) -> dict:
    return json.loads(_get_bytes(url))


def build_universe(*, get: Callable[[str], dict] = _get, first_year: int = 2012,
                   last_year: int | None = None) -> list[dict]:
    last_year = last_year or _dt.date.today().year
    names = {}
    for y in range(first_year, last_year + 1):
        for q in (1, 2, 3, 4):
            period = f"CY{y}Q{q}I"
            try:
                repo = get(f"{API}frames/us-gaap/SecuritiesSoldUnderAgreementsToRepurchase/USD/{period}.json")
                time.sleep(PAUSE)
                assets = get(f"{API}frames/us-gaap/Assets/USD/{period}.json")
                time.sleep(PAUSE)
            except Exception:  # noqa: BLE001 — a frame that does not exist yet
                continue
            total = {r["cik"]: r["val"] for r in assets.get("data", [])}
            for r in repo.get("data", []):
                a = total.get(r["cik"])
                if a and a > 0 and r["val"] / a >= REPO_SHARE:
                    names[r["cik"]] = r["entityName"]
    out = []
    for cik in sorted(names):
        try:
            sub = get(SUBMISSIONS.format(cik))
        except Exception:  # noqa: BLE001
            continue
        time.sleep(PAUSE)
        common = [t for t in (sub.get("tickers") or []) if "-" not in t]
        if not common or not set(sub.get("exchanges") or []) & LISTED_EXCHANGES:
            continue
        if str(sub.get("sic") or "") != REIT_SIC:
            continue
        out.append({"cik": cik, "ticker": common[0], "name": names[cik]})
    return out


def _by_accession(facts: dict, concept: str, unit: str) -> dict:
    """{(accession, period end): value} for 10-Q/10-K facts of one concept."""
    vals = facts.get("facts", {}).get("us-gaap", {}).get(concept, {}).get("units", {}).get(unit, [])
    out = {}
    for v in vals:
        if v.get("form") in FORMS and v.get("val") is not None:
            out.setdefault((v["accn"], v["end"]), (float(v["val"]), v["filed"]))
    return out


def bv_history(facts: dict) -> list[dict]:
    """Book value per common share per period end, from the first filing reporting it
    with equity and shares both present (see the module docstring)."""
    equity = _by_accession(facts, "StockholdersEquity", "USD")
    shares = _by_accession(facts, "CommonStockSharesOutstanding", "shares")
    pref_liq = _by_accession(facts, "PreferredStockLiquidationPreferenceValue", "USD")
    pref_val = _by_accession(facts, "PreferredStockValue", "USD")
    first = {}
    for key, (eq, filed) in equity.items():
        if key not in shares:
            continue
        acc, end = key
        sh = shares[key][0]
        if sh <= 0:
            continue
        pref = pref_liq.get(key, pref_val.get(key, (0.0, None)))[0]
        bv = (eq - pref) / sh
        if not (0 < bv <= 500):
            continue
        if end not in first or filed < first[end]["filed"]:
            first[end] = {"end": end, "bv": bv, "filed": filed, "accession": acc,
                          "equity": eq, "preferred": pref, "shares": sh}
    return sorted(first.values(), key=lambda r: r["end"])


# ── Correction round (MREIT_DISCOUNT_TEST.md, amendment 1): the filing's full XBRL ─────
# companyfacts carries only non-dimensional facts, and most mREITs tag preferred stock per
# series (StatementClassOfStockAxis), so the preferred deduction above often read 0 (the
# hand audit: 10 of 30 off by more than 2%). The instance document of each filing holds
# every fact, dimensional ones included.

ARCHIVE_DIR = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/"
#: Preferred concepts in order of preference. The first with any value at the period end
#: is used: its non-dimensional total if tagged, else the sum over class-of-stock members.
PREFERRED_CONCEPTS = ("PreferredStockLiquidationPreferenceValue", "PreferredStockValue",
                      "PreferredStockValueOutstanding",
                      "PreferredStockIncludingAdditionalPaidInCapitalNetOfDiscount",
                      "PreferredStockIncludingAdditionalPaidInCapital",
                      "ConvertiblePreferredStockNonredeemableOrRedeemableIssuerOptionValue")
CLASS_AXIS = "StatementClassOfStockAxis"
#: A balance-sheet share count this many times the cover-page count is a scale error in
#: the tag (thousands reported as units); it is rescaled. Outside both bands, dropped.
SCALE_BAND = (500.0, 2000.0)
AGREE_BAND = (0.5, 2.0)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def instance_name(index: dict) -> str | None:
    """The filing's XBRL instance document from its index.json listing."""
    names = [i["name"] for i in index.get("directory", {}).get("item", [])]
    inline = [n for n in names if n.endswith("_htm.xml")]
    if inline:
        return inline[0]
    plain = [n for n in names if n.endswith(".xml") and not n.startswith("FilingSummary")
             and not any(n.endswith(x) for x in ("_cal.xml", "_def.xml", "_lab.xml", "_pre.xml"))]
    return plain[0] if plain else None


def parse_instance(doc: bytes, end: str) -> dict:
    """Equity, preferred (and which concept), common shares and cover-page shares at the
    instant ``end`` from an XBRL instance document."""
    root = ET.fromstring(doc)
    contexts = {}
    for ctx in root.iter():
        if _local(ctx.tag) != "context":
            continue
        instant = next((e.text for e in ctx.iter() if _local(e.tag) == "instant"), None)
        dims = [(e.get("dimension", "").split(":")[-1], (e.text or "").strip())
                for e in ctx.iter() if _local(e.tag) == "explicitMember"]
        contexts[ctx.get("id")] = (instant, dims)
    facts = {}
    for el in root.iter():
        ref = el.get("contextRef")
        if ref is None or el.text is None or el.get("{http://www.w3.org/2001/XMLSchema-instance}nil") == "true":
            continue
        try:
            val = float(el.text.strip().replace(",", ""))
        except ValueError:
            continue
        facts.setdefault(_local(el.tag), []).append((contexts.get(ref, (None, [])), val))

    def total(concept, *, any_instant=False):
        vals = facts.get(concept, [])
        plain = [v for (inst, dims), v in vals if not dims and (any_instant or inst == end)]
        if plain:
            return plain[0]
        members = {}
        for (inst, dims), v in vals:
            if (any_instant or inst == end) and len(dims) == 1 and dims[0][0] == CLASS_AXIS:
                members.setdefault(dims[0][1], v)
        return sum(members.values()) if members else None

    pref, source = 0.0, None
    for c in PREFERRED_CONCEPTS:
        v = total(c)
        if v is not None:
            pref, source = v, c
            break
    cover = [v for (inst, dims), v in facts.get("EntityCommonStockSharesOutstanding", []) if not dims]
    return {"equity": total("StockholdersEquity"), "preferred": pref, "preferred_concept": source,
            "shares": total("CommonStockSharesOutstanding"),
            "cover_shares": sum(cover) if cover else None}


def bv_from_instance(parsed: dict) -> tuple[float | None, str]:
    """(book value per common share, note). The share count is checked against the cover
    page: a 500-2000x excess is rescaled by 1000, anything else outside 0.5-2x is dropped."""
    eq, sh, cover = parsed["equity"], parsed["shares"], parsed["cover_shares"]
    if eq is None or not sh or sh <= 0:
        return None, "missing equity or shares"
    note = ""
    if cover:
        ratio = sh / cover
        if SCALE_BAND[0] <= ratio <= SCALE_BAND[1]:
            sh, note = sh / 1000.0, "shares rescaled /1000 against the cover page"
        elif not (AGREE_BAND[0] <= ratio <= AGREE_BAND[1]):
            return None, f"shares {sh:.0f} disagree with the cover page {cover:.0f}"
    bv = (eq - parsed["preferred"]) / sh
    return (bv, note) if 0 < bv <= 500 else (None, f"implausible book value {bv:.4f}")

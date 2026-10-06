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

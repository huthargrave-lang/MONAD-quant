#!/usr/bin/env python3
"""stock_screener — preset-driven fundamental screens over a hand-coded liquid universe.

The screener is deliberately NOT one strict filter. It is a set of PRESETS — buttons in
the UI — each of which is a declarative rule list over one shared metric snapshot:

    low_pe_high_growth · low_pe_high_dividend · safety_low_debt · high_ai_exposure
    low_ai_exposure · ai_shadow_debt · most_volatile · most_active · sovereign_ledger
    · chaos_hedges

The last two surface the Sovereign Ledger research program (PR #56): Book I
critical-minerals sovereignty names and the liquid tickers of Book II's Chaos
Buckets. The BOOKS are the source of truth — S.P.A.R.K. scores, bucket definitions,
shock matrices all live in docs/research/SOVEREIGN_LEDGER_*.md; this module carries
only tickers plus an editorial `bucket` tag, the same shape as the AI-exposure tag.

Design rules, in line with the rest of this repo:

  * DATA AND PRESENTATION ARE SPLIT. This module holds the universe, the metrics and
    the preset rules, and emits NO HTML — the page lives in `tools/research_ui.py`
    (`/screen`), so the surface census there stays complete without registering a new
    surface file.
  * THE SNAPSHOT IS A CACHE, NOT A LIVE CALL. `fetch` pulls fundamentals once via
    yfinance and writes `data/screener/fundamentals.json`; every read path (CLI table,
    UI page) renders from that file and says so. A missing snapshot renders as an
    instruction to fetch, never as an empty universe (the absence-flag family:
    F155/F159/F188/F204). This repo is often run network-blocked, so the UI must not
    depend on a fetch succeeding at request time.
  * PRESETS ARE DECLARATIVE, so a test can enumerate them and check every rule names a
    real metric — a preset that silently filters on a typo'd key is the failure mode.
  * AI-exposure tags are EDITORIAL: a hand-coded judgment of how much of the business
    rides on AI demand ("high"), touches it ("medium"), or is largely orthogonal to it
    ("low"). They are data to be edited, not scraped truth.
  * AI shadow-debt buckets are ALSO EDITORIAL: they flag names whose AI-infra funding
    may sit in SPVs / project finance / off-balance-sheet structures (or feed that
    buildout). yfinance `debtToEquity` is ON-balance-sheet only — the lens exists
    because that number is incomplete for risk assessment. Study objects, not signals.

Units (normalised in `_normalise_row`, asserted nowhere else):
  * `dividend_yield`, `earnings_growth`, `revenue_growth`, `profit_margin`,
    `range_52w_pct` are FRACTIONS (0.03 = 3%). Prefer `dividendRate`/`price` (or
    trailing rate), then `trailingAnnualDividendYield` (already a fraction). Yahoo's
    `dividendYield` is percent points (0.35 = 0.35%, 6.2 = 6.2%) — always /100 when
    used as fallback. The old ">0.5 ⇒ percent points" heuristic left AAPL/NVDA/etc.
    showing 35–47% yields.
  * `debt_to_equity` stays in yfinance's percent points (95.0 = 0.95x equity).
  * `pe` prefers trailing, falls back to forward; non-positive P/E is stored as None
    (loss-makers have no meaningful P/E, and a preset that asks for one skips them).

Usage:
    venv/bin/python tools/stock_screener.py fetch            # write the snapshot
    venv/bin/python tools/stock_screener.py list             # show the presets
    venv/bin/python tools/stock_screener.py show most_active # one preset as a table
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAPSHOT_PATH = os.path.join(REPO, "data", "screener", "fundamentals.json")

# ─────────────────────────────────────────────────────────────────────────────
# 1. Universe — liquid US large/mid caps across sectors, with editorial AI tags.
#    (ticker, name, sector, ai_exposure[, chaos_bucket])
#    The optional 5th element ties a name to a Sovereign Ledger chaos bucket
#    (Book II, docs/research/SOVEREIGN_LEDGER_CHAOS_BUCKETS_2026.md). Liquid
#    US-listed stocks only — the watchlist's futures, foreign listings and ETFs
#    stay in the docs, since this screener runs on per-company fundamentals.
# ─────────────────────────────────────────────────────────────────────────────
UNIVERSE = [
    # Megacap tech / semis — the AI-demand complex
    ("NVDA", "NVIDIA", "Technology", "high"),
    ("AMD", "AMD", "Technology", "high"),
    ("AVGO", "Broadcom", "Technology", "high"),
    ("TSM", "TSMC", "Technology", "high"),
    ("MU", "Micron", "Technology", "high"),
    ("INTC", "Intel", "Technology", "high"),
    ("ANET", "Arista Networks", "Technology", "high"),
    ("DELL", "Dell Technologies", "Technology", "high"),
    ("SMCI", "Super Micro", "Technology", "high"),
    ("MSFT", "Microsoft", "Technology", "high"),
    ("GOOGL", "Alphabet", "Communication Services", "high"),
    ("META", "Meta Platforms", "Communication Services", "high"),
    ("AMZN", "Amazon", "Consumer Cyclical", "high"),
    ("ORCL", "Oracle", "Technology", "high"),
    ("PLTR", "Palantir", "Technology", "high"),
    ("NOW", "ServiceNow", "Technology", "high"),
    ("CRM", "Salesforce", "Technology", "medium"),
    ("ADBE", "Adobe", "Technology", "medium"),
    ("PANW", "Palo Alto Networks", "Technology", "medium", "cyber/space"),
    ("QCOM", "Qualcomm", "Technology", "medium"),
    ("TXN", "Texas Instruments", "Technology", "medium"),
    ("IBM", "IBM", "Technology", "medium"),
    ("ACN", "Accenture", "Technology", "medium"),
    ("AAPL", "Apple", "Technology", "medium"),
    ("TSLA", "Tesla", "Consumer Cyclical", "medium"),
    ("NFLX", "Netflix", "Communication Services", "medium"),
    ("UBER", "Uber", "Technology", "medium"),
    ("SHOP", "Shopify", "Technology", "medium"),
    # Financials
    ("JPM", "JPMorgan Chase", "Financial Services", "low"),
    ("BAC", "Bank of America", "Financial Services", "low"),
    ("WFC", "Wells Fargo", "Financial Services", "low"),
    ("GS", "Goldman Sachs", "Financial Services", "low"),
    ("V", "Visa", "Financial Services", "low"),
    ("MA", "Mastercard", "Financial Services", "low"),
    ("BRK-B", "Berkshire Hathaway", "Financial Services", "low"),
    # Healthcare
    ("JNJ", "Johnson & Johnson", "Healthcare", "low"),
    ("UNH", "UnitedHealth", "Healthcare", "low"),
    ("PFE", "Pfizer", "Healthcare", "low"),
    ("MRK", "Merck", "Healthcare", "low"),
    ("ABBV", "AbbVie", "Healthcare", "low"),
    ("LLY", "Eli Lilly", "Healthcare", "low"),
    ("CVS", "CVS Health", "Healthcare", "low"),
    # Consumer staples / defensive
    ("PG", "Procter & Gamble", "Consumer Defensive", "low"),
    ("KO", "Coca-Cola", "Consumer Defensive", "low"),
    ("PEP", "PepsiCo", "Consumer Defensive", "low"),
    ("WMT", "Walmart", "Consumer Defensive", "low"),
    ("COST", "Costco", "Consumer Defensive", "low"),
    ("CL", "Colgate-Palmolive", "Consumer Defensive", "low"),
    ("KMB", "Kimberly-Clark", "Consumer Defensive", "low"),
    ("GIS", "General Mills", "Consumer Defensive", "low"),
    ("KHC", "Kraft Heinz", "Consumer Defensive", "low"),
    ("MO", "Altria", "Consumer Defensive", "low"),
    ("PM", "Philip Morris", "Consumer Defensive", "low"),
    # Consumer cyclical / retail
    ("MCD", "McDonald's", "Consumer Cyclical", "low"),
    ("SBUX", "Starbucks", "Consumer Cyclical", "low"),
    ("NKE", "Nike", "Consumer Cyclical", "low"),
    ("HD", "Home Depot", "Consumer Cyclical", "low"),
    ("LOW", "Lowe's", "Consumer Cyclical", "low"),
    ("TGT", "Target", "Consumer Defensive", "low"),
    ("DIS", "Disney", "Communication Services", "low"),
    # Energy
    ("XOM", "Exxon Mobil", "Energy", "low", "oil shock"),
    ("CVX", "Chevron", "Energy", "low", "oil shock"),
    ("COP", "ConocoPhillips", "Energy", "low", "oil shock"),
    # Utilities / telecom / REIT
    ("NEE", "NextEra Energy", "Utilities", "low"),
    ("SO", "Southern Company", "Utilities", "low"),
    ("DUK", "Duke Energy", "Utilities", "low"),
    ("T", "AT&T", "Communication Services", "low"),
    ("VZ", "Verizon", "Communication Services", "low"),
    ("O", "Realty Income", "Real Estate", "low"),
    # Industrials / autos
    ("CAT", "Caterpillar", "Industrials", "low"),
    ("DE", "Deere", "Industrials", "low"),
    ("UNP", "Union Pacific", "Industrials", "low"),
    ("GE", "GE Aerospace", "Industrials", "low"),
    ("BA", "Boeing", "Industrials", "low", "naval"),
    ("LMT", "Lockheed Martin", "Industrials", "low", "defense US"),
    ("RTX", "RTX", "Industrials", "low", "defense US"),
    ("F", "Ford", "Consumer Cyclical", "low"),
    ("GM", "General Motors", "Consumer Cyclical", "low"),
    # ── Sovereign Ledger (PR #56) — Book I sovereignty names (bucket 11) and the
    #    liquid stock legs of Book II's chaos buckets. Bucket tags are editorial and
    #    re-scored in the Books, not here.
    ("MP", "MP Materials", "Basic Materials", "low", "wartime elements"),
    ("UUUU", "Energy Fuels", "Energy", "low", "wartime elements"),
    ("LEU", "Centrus Energy", "Energy", "low", "wartime elements"),
    ("LAC", "Lithium Americas", "Basic Materials", "low", "wartime elements"),
    ("UAMY", "US Antimony", "Basic Materials", "low", "wartime elements"),
    ("USAR", "USA Rare Earth", "Basic Materials", "low", "wartime elements"),
    ("AREC", "American Resources", "Basic Materials", "low", "wartime elements"),
    ("NB", "NioCorp", "Basic Materials", "low", "wartime elements"),
    ("NOC", "Northrop Grumman", "Industrials", "low", "defense US"),
    ("GD", "General Dynamics", "Industrials", "low", "defense US"),
    ("AVAV", "AeroVironment", "Industrials", "low", "drones"),
    ("KTOS", "Kratos Defense", "Industrials", "low", "drones"),
    ("HII", "Huntington Ingalls", "Industrials", "low", "naval"),
    ("BAESY", "BAE Systems ADR", "Industrials", "low", "EU defense"),
    ("NEM", "Newmont", "Basic Materials", "low", "gold"),
    ("AEM", "Agnico Eagle", "Basic Materials", "low", "gold"),
    ("GOLD", "Barrick Gold", "Basic Materials", "low", "gold"),
    ("CCJ", "Cameco", "Energy", "low", "uranium"),
    ("UEC", "Uranium Energy", "Energy", "low", "uranium"),
    ("FCX", "Freeport-McMoRan", "Basic Materials", "low", "copper/grid"),
    ("SCCO", "Southern Copper", "Basic Materials", "low", "copper/grid"),
    ("PAAS", "Pan American Silver", "Basic Materials", "low", "silver"),
    ("LNG", "Cheniere Energy", "Energy", "low", "LNG"),
    ("FRO", "Frontline", "Energy", "low", "tankers"),
    ("STNG", "Scorpio Tankers", "Energy", "low", "tankers"),
    ("VLO", "Valero", "Energy", "low", "refiners"),
    ("MPC", "Marathon Petroleum", "Energy", "low", "refiners"),
    ("PSX", "Phillips 66", "Energy", "low", "refiners"),
    ("CF", "CF Industries", "Basic Materials", "low", "fertilizer"),
    ("NTR", "Nutrien", "Basic Materials", "low", "fertilizer"),
    ("MOS", "Mosaic", "Basic Materials", "low", "fertilizer"),
    ("NUE", "Nucor", "Basic Materials", "low", "steel"),
    ("STLD", "Steel Dynamics", "Basic Materials", "low", "steel"),
    ("CLF", "Cleveland-Cliffs", "Basic Materials", "low", "steel"),
    ("ADM", "Archer-Daniels-Midland", "Consumer Defensive", "low", "softs"),
    ("VST", "Vistra", "Utilities", "medium", "grid/power"),
    ("CEG", "Constellation Energy", "Utilities", "medium", "grid/power"),
    ("GEV", "GE Vernova", "Industrials", "medium", "grid/power"),
    ("PWR", "Quanta Services", "Industrials", "low", "grid/power"),
    ("ETN", "Eaton", "Industrials", "medium", "grid/power"),
    ("VRT", "Vertiv", "Industrials", "high", "grid/power"),
    ("AMAT", "Applied Materials", "Technology", "high", "chip equipment"),
    ("LRCX", "Lam Research", "Technology", "high", "chip equipment"),
    ("KLAC", "KLA", "Technology", "high", "chip equipment"),
    ("ASML", "ASML ADR", "Technology", "high", "chip equipment"),
]

AI_TAGS = ("high", "medium", "low")

#: Legal chaos-bucket tags — the liquid-stock subset of Book II's 20 buckets plus
#: "wartime elements" (bucket 11), which doubles as the Book I sovereignty set.
#: Definitions and shock matrices live in the Sovereign Ledger docs, not here.
CHAOS_BUCKETS = (
    "wartime elements", "oil shock", "defense US", "drones", "naval", "EU defense",
    "gold", "uranium", "copper/grid", "silver", "LNG", "tankers", "refiners",
    "fertilizer", "steel", "softs", "grid/power", "chip equipment", "cyber/space",
)

#: Editorial AI-infra financing risk buckets. Not scraped: filings/SPV detail is not in
#: the yfinance snapshot. Tags flag WHERE to look, not a measured notional.
#:   spv_sponsor   — hyperscaler / platform that can park project debt in SPVs
#:                   (Meta Project Beignet is the public archetype)
#:   capex_burn    — AI-native spenders whose cash is being drained by infra buildout
#:   supply_chain  — chips / servers / equipment feeding the buildout (demand risk)
#:   grid_power    — power / cooling / electrical (the grid leg of the four-legged bet)
SHADOW_DEBT_BUCKETS = ("spv_sponsor", "capex_burn", "supply_chain", "grid_power")

SHADOW_DEBT_LABELS = {
    "spv_sponsor": "SPV sponsor",
    "capex_burn": "Capex burn",
    "supply_chain": "Supply chain",
    "grid_power": "Grid / power",
}

SHADOW_DEBT_BLURBS = {
    "spv_sponsor": "May keep data-center / project liabilities in SPVs below consolidation "
                   "thresholds — on-BS debt understates exposure.",
    "capex_burn": "AI infra capex is consuming cash reserves; leverage may rise even when "
                  "reported D/E still looks tame.",
    "supply_chain": "Sells into the buildout — less SPV sponsor risk, high cyclical demand "
                    "risk if financing stalls.",
    "grid_power": "Power / electrical capacity is one leg of the AI financing bet; grid "
                  "constraints bind the whole stack.",
}

#: How badly a bucket compromises the REPORTED debt/equity number. This is an ORDINAL
#: editorial judgement, deliberately not a notional: the repo has no free source for SPV
#: debt outstanding (see docs/research/OFF_BALANCE_SHEET_DEBT_QUANT_2026.md), and
#: inventing "+60 D/E points" would be fabricating the very figure the lens exists to say
#: is missing. Sponsors rank highest because they are the party whose own statements omit
#: the project debt; a supplier selling into the buildout carries demand risk, not an
#: off-balance-sheet leg of its own.
SHADOW_DEBT_SEVERITY = {
    "spv_sponsor": "high",
    "capex_burn": "high",
    "grid_power": "medium",
    "supply_chain": "low",
}

#: Ordinal form so a preset can gate on it. 0 means "carries no tag on THIS editorial
#: list" — it is not evidence that a company has no off-balance-sheet exposure, and no
#: rule here may be read as certifying one.
SHADOW_SEVERITY_RANK = {None: 0, "low": 1, "medium": 2, "high": 3}

#: ticker → shadow-debt bucket. Hyperscalers tagged spv_sponsor on industry practice
#: (Meta's Louisiana SPV is documented; peers are standardizing similar structures).
SHADOW_DEBT = {
    "META": "spv_sponsor",
    "MSFT": "spv_sponsor",
    "GOOGL": "spv_sponsor",
    "AMZN": "spv_sponsor",
    "ORCL": "spv_sponsor",
    "NVDA": "supply_chain",
    "AMD": "supply_chain",
    "AVGO": "supply_chain",
    "TSM": "supply_chain",
    "MU": "supply_chain",
    "INTC": "supply_chain",
    "ANET": "supply_chain",
    "DELL": "supply_chain",
    "SMCI": "supply_chain",
    "AMAT": "supply_chain",
    "LRCX": "supply_chain",
    "KLAC": "supply_chain",
    "ASML": "supply_chain",
    "PLTR": "capex_burn",
    "NOW": "capex_burn",
    "CEG": "grid_power",
    "VST": "grid_power",
    "VRT": "grid_power",
    "GEV": "grid_power",
    "ETN": "grid_power",
    "PWR": "grid_power",
}


def universe_rows():
    """[(ticker, name, sector, ai, bucket)] — entries may omit the bucket."""
    out = []
    for entry in UNIVERSE:
        ticker, name, sector, ai = entry[:4]
        out.append((ticker, name, sector, ai, entry[4] if len(entry) > 4 else None))
    return out


def validate_universe():
    """Raise on a duplicate ticker, unknown AI tag, or typo'd bucket — a bucket that
    matches no preset would silently vanish from the sovereign lenses."""
    seen = set()
    for ticker, _name, _sector, ai, bucket in universe_rows():
        if ticker in seen:
            raise ValueError("duplicate ticker {!r}".format(ticker))
        seen.add(ticker)
        if ai not in AI_TAGS:
            raise ValueError("{}: unknown ai tag {!r}".format(ticker, ai))
        if bucket is not None and bucket not in CHAOS_BUCKETS:
            raise ValueError("{}: unknown chaos bucket {!r}".format(ticker, bucket))
    for ticker, tag in SHADOW_DEBT.items():
        if ticker not in seen:
            raise ValueError("SHADOW_DEBT ticker {!r} not in UNIVERSE".format(ticker))
        if tag not in SHADOW_DEBT_BUCKETS:
            raise ValueError("{}: unknown shadow-debt bucket {!r}".format(ticker, tag))


validate_universe()

#: Metric keys every snapshot row carries (value: float or None). A preset rule may
#: only name one of these — enforced by `validate_presets()` and the guard test.
METRIC_KEYS = (
    "price", "market_cap", "pe", "earnings_growth", "revenue_growth", "growth",
    "dividend_yield", "debt_to_equity", "beta", "avg_volume", "dollar_volume",
    "range_52w_pct", "profit_margin", "shadow_severity_rank",
)

# ─────────────────────────────────────────────────────────────────────────────
# 2. Presets — each one button in the UI. Declarative so tests can check them.
#
#    require: [(metric, op, value)]  — op in < <= > >= ==; a row missing the metric
#             fails the rule (counted separately as "no data", never silently shown).
#    rank:    (metric, "asc"|"desc") — display order, best first.
#    top:     optional cap on matches (for pure leaderboards like most_active).
#    x/y:     (metric, axis label[, "log"]) for the dot plot.
# ─────────────────────────────────────────────────────────────────────────────
PRESETS = {
    "low_pe_high_growth": {
        "title": "Low P/E · high growth",
        "blurb": "Earnings growing ≥10% y/y on a trailing P/E of 25 or less — growth "
                 "that the market has not fully re-priced.",
        "require": [("pe", "<=", 25.0), ("growth", ">=", 0.10)],
        "rank": ("growth", "desc"),
        "x": ("pe", "P/E (trailing, forward fallback)"),
        "y": ("growth", "earnings growth y/y (revenue fallback)"),
    },
    "low_pe_high_dividend": {
        "title": "Low P/E · high dividend",
        "blurb": "Income screen: P/E of 18 or less paying at least a 3% yield.",
        "require": [("pe", "<=", 18.0), ("dividend_yield", ">=", 0.03)],
        "rank": ("dividend_yield", "desc"),
        "x": ("pe", "P/E (trailing, forward fallback)"),
        "y": ("dividend_yield", "dividend yield"),
    },
    "safety_low_debt": {
        "title": "Safety · low debt",
        "blurb": "Balance-sheet screen: debt under 80% of equity, beta under 0.9, and "
                 "a real profit margin — the sit-through-a-storm cohort. Names carrying "
                 "a high-severity AI shadow-debt tag are excluded even when their "
                 "reported D/E is low, because for those names the reported figure is "
                 "known to omit a financing leg (see the AI shadow-debt lens).",
        "require": [("debt_to_equity", "<=", 80.0), ("beta", "<=", 0.9),
                    ("profit_margin", ">=", 0.08),
                    ("shadow_severity_rank", "<=", 2)],
        "rank": ("debt_to_equity", "asc"),
        "x": ("debt_to_equity", "debt / equity (%)"),
        "y": ("beta", "beta vs S&P 500"),
    },
    "high_ai_exposure": {
        "title": "High AI exposure",
        "blurb": "Editorial tag: businesses whose demand is driven by the AI buildout "
                 "(chips, hyperscalers, AI-native software). Matches draw as buckets — "
                 "pair with the AI shadow-debt lens for off-balance-sheet financing risk.",
        "require": [("ai", "==", "high")],
        "rank": ("growth", "desc"),
        "x": ("pe", "P/E (trailing, forward fallback)"),
        "y": ("growth", "earnings growth y/y (revenue fallback)"),
        "mark": "bucket",
    },
    "ai_shadow_debt": {
        "title": "AI shadow debt",
        "blurb": "Editorial risk buckets for AI-infra financing that may sit off the "
                 "primary balance sheet (SPVs / project finance). On-BS debt/equity from "
                 "yfinance is plotted on the x-axis — it is the VISIBLE leg only. Tags "
                 "are study objects (Meta Beignet-class structures), not measured "
                 "notionals and not live-bot signals. See docs/research/"
                 "AI_SHADOW_DEBT_LENS_2026.md.",
        "require": [("shadow_debt", "!=", None)],
        "rank": ("debt_to_equity", "desc"),
        "x": ("debt_to_equity", "on-BS debt / equity (%)"),
        "y": ("growth", "earnings growth y/y (revenue fallback)"),
        "mark": "bucket",
    },
    "low_ai_exposure": {
        "title": "Low AI exposure",
        "blurb": "Editorial tag: businesses largely orthogonal to the AI trade — "
                 "staples, energy, utilities, banks, healthcare.",
        "require": [("ai", "==", "low")],
        "rank": ("dividend_yield", "desc"),
        "x": ("pe", "P/E (trailing, forward fallback)"),
        "y": ("dividend_yield", "dividend yield"),
    },
    "most_volatile": {
        "title": "Most volatile",
        "blurb": "Beta of 1.3+ against the S&P 500, widest 52-week ranges first — "
                 "where the daily moves are.",
        "require": [("beta", ">=", 1.3)],
        "rank": ("beta", "desc"),
        "x": ("beta", "beta vs S&P 500"),
        "y": ("range_52w_pct", "52-week range / price"),
    },
    "most_active": {
        "title": "Most active",
        "blurb": "Top 15 by average daily dollar volume — where the trading is.",
        "require": [],
        "rank": ("dollar_volume", "desc"),
        "top": 15,
        "x": ("dollar_volume", "avg daily dollar volume", "log"),
        "y": ("range_52w_pct", "52-week range / price"),
    },
    "sovereign_ledger": {
        "title": "Sovereign Ledger",
        "blurb": "Book I sovereignty names — chokepoint mineral + allied feedstock + "
                 "government scaffolding (the USAR pattern). S.P.A.R.K. scores and "
                 "binaries live in docs/research/SOVEREIGN_LEDGER_2026.md; re-score "
                 "there, not here. Study objects, not signals.",
        "require": [("bucket", "==", "wartime elements")],
        "rank": ("dollar_volume", "desc"),
        "x": ("dollar_volume", "avg daily dollar volume", "log"),
        "y": ("range_52w_pct", "52-week range / price"),
    },
    "chaos_hedges": {
        "title": "Chaos hedges",
        "blurb": "Liquid stock legs of Book II's Chaos Buckets — defense, energy "
                 "shocks, gold, uranium, copper, grid. Safe haven ≠ war hedge: see "
                 "docs/research/SOVEREIGN_LEDGER_CHAOS_BUCKETS_2026.md for clocks "
                 "and the shock matrix. Study objects, not signals.",
        "require": [("bucket", "!=", None)],
        "rank": ("dollar_volume", "desc"),
        "x": ("dollar_volume", "avg daily dollar volume", "log"),
        "y": ("range_52w_pct", "52-week range / price"),
    },
}

_OPS = {
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
}

#: Editorial tag metrics: absence is a valid value (untagged), not missing data —
#: rules on these never send a row to the "no data" bin.
CATEGORICAL = ("ai", "bucket", "shadow_debt", "shadow_severity")


def validate_presets():
    """Raise if any preset rule/rank/axis names an unknown metric or op — the silent
    failure this prevents is a typo'd key filtering every row to zero."""
    legal = set(METRIC_KEYS) | set(CATEGORICAL)
    for key, p in PRESETS.items():
        for metric, op, _value in p["require"]:
            if metric not in legal:
                raise ValueError("{}: rule on unknown metric {!r}".format(key, metric))
            if op not in _OPS:
                raise ValueError("{}: unknown op {!r}".format(key, op))
        rank_metric, direction = p["rank"]
        if rank_metric not in legal or direction not in ("asc", "desc"):
            raise ValueError("{}: bad rank {!r}".format(key, p["rank"]))
        for axis in ("x", "y"):
            if p[axis][0] not in legal:
                raise ValueError("{}: {} axis on unknown metric {!r}".format(
                    key, axis, p[axis][0]))


validate_presets()


# ─────────────────────────────────────────────────────────────────────────────
# 3. Snapshot: fetch (network, yfinance) / load (stdlib only).
# ─────────────────────────────────────────────────────────────────────────────
def _num(value):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _dividend_yield_fraction(info, price):
    """Return dividend yield as a fraction (0.03 = 3%), or None if unknown.

    Yahoo's `dividendYield` is percent points (0.35 = 0.35%). Prefer rate/price or
    `trailingAnnualDividendYield` (already a fraction) so low-yield names are not
    shown as 35%+.
    """
    rate = _num(info.get("dividendRate"))
    if rate is None:
        rate = _num(info.get("trailingAnnualDividendRate"))
    if rate is not None and price and price > 0 and rate >= 0:
        return rate / price
    tady = _num(info.get("trailingAnnualDividendYield"))
    if tady is not None and tady >= 0:
        # Rare vendors ship this as percent points too (e.g. 2.64); fractions stay.
        return tady / 100.0 if tady > 1.0 else tady
    raw = _num(info.get("dividendYield"))
    if raw is None or raw < 0:
        return None
    return raw / 100.0


def _normalise_row(ticker, name, sector, ai, info, bucket=None):
    price = _num(info.get("currentPrice")) or _num(info.get("regularMarketPrice"))
    pe = _num(info.get("trailingPE"))
    if pe is None or pe <= 0:
        pe = _num(info.get("forwardPE"))
    if pe is not None and pe <= 0:
        pe = None
    dy = _dividend_yield_fraction(info, price)
    eg = _num(info.get("earningsGrowth"))
    rg = _num(info.get("revenueGrowth"))
    avg_vol = _num(info.get("averageVolume"))
    hi = _num(info.get("fiftyTwoWeekHigh"))
    lo = _num(info.get("fiftyTwoWeekLow"))
    rng = ((hi - lo) / price) if (hi is not None and lo is not None and price) else None
    return {
        "ticker": ticker, "name": name, "sector": sector, "ai": ai,
        "bucket": bucket,
        "price": price,
        "market_cap": _num(info.get("marketCap")),
        "pe": pe,
        "earnings_growth": eg,
        "revenue_growth": rg,
        "growth": eg if eg is not None else rg,
        "dividend_yield": dy if dy is not None else 0.0,   # no dividend = 0, not unknown
        "debt_to_equity": _num(info.get("debtToEquity")),
        "beta": _num(info.get("beta")),
        "avg_volume": avg_vol,
        "dollar_volume": (avg_vol * price) if (avg_vol and price) else None,
        "range_52w_pct": rng,
        "profit_margin": _num(info.get("profitMargins")),
    }


def fetch_snapshot(out_path=SNAPSHOT_PATH):
    """Pull fundamentals for the whole universe via yfinance and write the snapshot.
    Needs network; per-ticker failures are recorded, never fatal."""
    import yfinance as yf   # deferred: every read path must work without it
    rows, errors = [], {}
    for ticker, name, sector, ai, bucket in universe_rows():
        try:
            info = yf.Ticker(ticker).info or {}
            row = enrich_row(_normalise_row(ticker, name, sector, ai, info, bucket))
            rows.append(row)
        except Exception as exc:               # noqa: BLE001 — record and continue
            errors[ticker] = str(exc)
    snapshot = {
        "as_of": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "yfinance Ticker.info",
        "universe_size": len(UNIVERSE),
        "errors": errors,
        "rows": rows,
    }
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(snapshot, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return snapshot



def enrich_row(row):
    """Join editorial shadow-debt tags onto a snapshot row (works on old caches)."""
    out = dict(row)
    tag = SHADOW_DEBT.get(out.get("ticker"))
    out["shadow_debt"] = tag
    out["shadow_severity"] = SHADOW_DEBT_SEVERITY.get(tag)
    out["shadow_severity_rank"] = SHADOW_SEVERITY_RANK[out["shadow_severity"]]
    return out


def enrich_rows(rows):
    return [enrich_row(r) for r in rows]


def load_snapshot(path=None):
    """The cached snapshot, or None — the caller renders the absence, not this module.
    `SNAPSHOT_PATH` is resolved at call time so tests can point it elsewhere."""
    if path is None:
        path = SNAPSHOT_PATH
    try:
        with open(path, encoding="utf-8") as fh:
            snap = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(snap.get("rows"), list):
        return None
    snap = dict(snap)
    snap["rows"] = enrich_rows(snap["rows"])
    return snap


# ─────────────────────────────────────────────────────────────────────────────
# 4. Applying a preset.
# ─────────────────────────────────────────────────────────────────────────────
def apply_preset(rows, preset_key):
    """(matches, no_data) — matches rank-ordered best first; no_data lists rows that
    could not be screened because a required metric is missing (reported, not hidden)."""
    p = PRESETS[preset_key]
    matches, no_data = [], []
    for row in rows:
        # The shadow fields are DERIVED from the editorial tag table, never fetched, so a
        # row that predates them is stale rather than missing data — deriving it here
        # keeps an old cache (or a hand-built row) from being reported as unscreenable.
        if row.get("shadow_severity_rank") is None:
            row = enrich_row(row)
        missing = [m for m, _op, _v in p["require"]
                   if m not in CATEGORICAL and row.get(m) is None]
        if missing:
            no_data.append((row, missing))
            continue
        if all(_OPS[op](row.get(m), v) for m, op, v in p["require"]):
            matches.append(row)
    rank_metric, direction = p["rank"]
    matches.sort(key=lambda r: (r.get(rank_metric) is None,
                                (r.get(rank_metric) or 0.0)
                                * (-1 if direction == "desc" else 1)))
    top = p.get("top")
    return (matches[:top] if top else matches), no_data


# ─────────────────────────────────────────────────────────────────────────────
# 5. CLI.
# ─────────────────────────────────────────────────────────────────────────────
def fmt_metric(row, metric):
    v = row.get(metric)
    if v is None:
        return "—"
    if metric in ("dividend_yield", "earnings_growth", "revenue_growth", "growth",
                  "profit_margin", "range_52w_pct"):
        return "{:.1%}".format(v)
    if metric in ("dollar_volume", "market_cap", "avg_volume"):
        return "{:.1f}B".format(v / 1e9) if v >= 1e9 else "{:.0f}M".format(v / 1e6)
    return "{:.2f}".format(v)


#: Daily closes per ticker. A SEPARATE file from the fundamentals snapshot on purpose:
#: prices are ~130 numbers a name and churn every session, while fundamentals are a
#: handful of slow-moving fields — bundling them would rewrite the whole snapshot daily
#: and make a fundamentals fetch fail whenever Yahoo throttles the price endpoint.
PRICES_PATH = os.path.join(REPO, "data", "screener", "prices.json")

#: ~6 months of sessions. Long enough to read a trend, short enough that the whole
#: universe still fits in a page payload without becoming the page's dominant weight.
PRICE_BARS = 126


def fetch_prices(out_path=PRICES_PATH, bars=PRICE_BARS):
    """Daily closes for the universe, batched. Needs network.

    Closes only, rounded to cents: the screener plots an indexed line, so OHLCV would be
    an order of magnitude more payload for detail nothing on the page reads."""
    import yfinance as yf   # deferred: every read path must work without it

    tickers = [t for t, *_ in UNIVERSE]
    frame = yf.download(tickers, period="1y", interval="1d",
                        auto_adjust=True, progress=False, threads=True)
    closes = frame["Close"] if "Close" in frame else frame
    series, errors = {}, {}
    for ticker in tickers:
        try:
            col = closes[ticker] if ticker in getattr(closes, "columns", []) else None
            if col is None:
                errors[ticker] = "no column in the download"
                continue
            vals = [round(float(v), 2) for v in col.tolist()[-bars:]
                    if v == v and v is not None]      # v != v filters NaN
            if len(vals) < 2:
                errors[ticker] = "fewer than two closes returned"
                continue
            series[ticker] = vals
        except Exception as exc:                       # noqa: BLE001 — record, continue
            errors[ticker] = str(exc)
    payload = {
        "as_of": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "yfinance daily closes, auto-adjusted",
        "bars": bars,
        "errors": errors,
        "series": series,
    }
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, sort_keys=True)
        fh.write("\n")
    return payload


def load_prices(path=None):
    """The cached closes, or None. Absence is the caller's to render, as with the
    fundamentals snapshot — a missing price file is not an empty market."""
    if path is None:
        path = PRICES_PATH
    try:
        with open(path, encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(payload.get("series"), dict):
        return None
    return payload


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd")
    f = sub.add_parser("fetch", help="fetch fundamentals and write the snapshot")
    f.add_argument("--out", default=SNAPSHOT_PATH)
    p = sub.add_parser("prices", help="fetch daily closes for the universe")
    p.add_argument("--out", default=PRICES_PATH)
    p.add_argument("--bars", type=int, default=PRICE_BARS)
    sub.add_parser("list", help="list the presets")
    s = sub.add_parser("show", help="apply one preset to the cached snapshot")
    s.add_argument("preset", choices=sorted(PRESETS))
    s.add_argument("--snapshot", default=SNAPSHOT_PATH)
    args = ap.parse_args(argv)

    if args.cmd == "fetch":
        snap = fetch_snapshot(args.out)
        print("wrote {} — {} rows, {} errors".format(
            args.out, len(snap["rows"]), len(snap["errors"])))
        for tk, err in snap["errors"].items():
            print("  {}: {}".format(tk, err))
        return 0
    if args.cmd == "prices":
        payload = fetch_prices(args.out, args.bars)
        print("wrote {} — {} series, {} errors".format(
            args.out, len(payload["series"]), len(payload["errors"])))
        for tk, err in list(payload["errors"].items())[:10]:
            print("  {}: {}".format(tk, err))
        return 0
    if args.cmd == "list":
        for key in PRESETS:
            p = PRESETS[key]
            print("{:<22} {}".format(key, p["title"]))
            print("{:<22} {}".format("", p["blurb"]))
        return 0
    if args.cmd == "show":
        snap = load_snapshot(args.snapshot)
        if snap is None:
            print("no snapshot at {} — run: python tools/stock_screener.py fetch"
                  .format(args.snapshot))
            return 1
        p = PRESETS[args.preset]
        matches, no_data = apply_preset(snap["rows"], args.preset)
        cols = ["pe", "growth", "dividend_yield", "debt_to_equity", "beta",
                "dollar_volume"]
        print("{}  ({} of {} match · snapshot {})".format(
            p["title"], len(matches), len(snap["rows"]), snap.get("as_of", "?")))
        hdr = "{:<7}{:<22}".format("TKR", "name") + "".join(
            "{:>14}".format(c) for c in cols)
        print(hdr)
        print("-" * len(hdr))
        for row in matches:
            print("{:<7}{:<22}".format(row["ticker"], row["name"][:21]) + "".join(
                "{:>14}".format(fmt_metric(row, c)) for c in cols))
        if no_data:
            print("\n{} rows not screenable (missing metrics): {}".format(
                len(no_data), ", ".join(r["ticker"] for r, _m in no_data)))
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())

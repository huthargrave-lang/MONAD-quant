#!/usr/bin/env python3
"""stock_screener — preset-driven fundamental screens over a hand-coded liquid universe.

The screener is deliberately NOT one strict filter. It is a set of PRESETS — buttons in
the UI — each of which is a declarative rule list over one shared metric snapshot:

    low_pe_high_growth · low_pe_high_dividend · safety_low_debt · high_ai_exposure
    low_ai_exposure · most_volatile · most_active · sovereign_ledger · chaos_hedges

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

Units (normalised in `_normalise_row`, asserted nowhere else):
  * `dividend_yield`, `earnings_growth`, `revenue_growth`, `profit_margin`,
    `range_52w_pct` are FRACTIONS (0.03 = 3%). yfinance has shipped `dividendYield`
    both as a fraction (0.03) and as percent points (3.0) across versions; values
    above 0.5 are treated as percent points — no common stock yields 50%.
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


validate_universe()

#: Metric keys every snapshot row carries (value: float or None). A preset rule may
#: only name one of these — enforced by `validate_presets()` and the guard test.
METRIC_KEYS = (
    "price", "market_cap", "pe", "earnings_growth", "revenue_growth", "growth",
    "dividend_yield", "debt_to_equity", "beta", "avg_volume", "dollar_volume",
    "range_52w_pct", "profit_margin",
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
                 "a real profit margin — the sit-through-a-storm cohort.",
        "require": [("debt_to_equity", "<=", 80.0), ("beta", "<=", 0.9),
                    ("profit_margin", ">=", 0.08)],
        "rank": ("debt_to_equity", "asc"),
        "x": ("debt_to_equity", "debt / equity (%)"),
        "y": ("beta", "beta vs S&P 500"),
    },
    "high_ai_exposure": {
        "title": "High AI exposure",
        "blurb": "Editorial tag: businesses whose demand is driven by the AI buildout "
                 "(chips, hyperscalers, AI-native software).",
        "require": [("ai", "==", "high")],
        "rank": ("growth", "desc"),
        "x": ("pe", "P/E (trailing, forward fallback)"),
        "y": ("growth", "earnings growth y/y (revenue fallback)"),
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
CATEGORICAL = ("ai", "bucket")


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


def _normalise_row(ticker, name, sector, ai, info, bucket=None):
    price = _num(info.get("currentPrice")) or _num(info.get("regularMarketPrice"))
    pe = _num(info.get("trailingPE"))
    if pe is None or pe <= 0:
        pe = _num(info.get("forwardPE"))
    if pe is not None and pe <= 0:
        pe = None
    dy = _num(info.get("dividendYield"))
    if dy is not None and dy > 0.5:      # percent-points variant of yfinance
        dy = dy / 100.0
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
            rows.append(_normalise_row(ticker, name, sector, ai, info, bucket))
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
    return snap if isinstance(snap.get("rows"), list) else None


# ─────────────────────────────────────────────────────────────────────────────
# 4. Applying a preset.
# ─────────────────────────────────────────────────────────────────────────────
def apply_preset(rows, preset_key):
    """(matches, no_data) — matches rank-ordered best first; no_data lists rows that
    could not be screened because a required metric is missing (reported, not hidden)."""
    p = PRESETS[preset_key]
    matches, no_data = [], []
    for row in rows:
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


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd")
    f = sub.add_parser("fetch", help="fetch fundamentals and write the snapshot")
    f.add_argument("--out", default=SNAPSHOT_PATH)
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

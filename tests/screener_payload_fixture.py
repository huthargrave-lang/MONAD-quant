"""A screener payload built from AUTHORED rows, for the shape contracts.

Three tests asserted the payload's SHAPE — which fields survive the join onto a row, and
which universe the price series are keyed on — by reading whatever the last fetch happened
to leave on disk. They could not run in CI at all: `data/screener/fundamentals.json` and
`data/screener/prices.json` are gitignored (`.gitignore` calls them regenerable caches, and
the test workflow deliberately does not fetch), so `rows` came back empty and the tests
failed on `rows[0]` and on a coverage ratio of 0. A suite that is permanently red for a
missing artifact stops being read.

Shape is decided by code, not by what a vendor returned this morning, so it is provable
from authored rows. What this does NOT do is stub the loaders: the snapshots are written to
a temp directory and the module-level paths are repointed, through the seam
`stock_screener.load_snapshot` documents for exactly this purpose ("resolved at call time so
tests can point it elsewhere"). The real load path therefore still runs — including
`enrich_rows`, which is what performs the editorial shadow-debt join that one of the three
tests exists to protect. Stubbing `load_snapshot` would have skipped it and the test would
have proved nothing.

The FIELD NAMES below are the fundamentals snapshot's own, as written by
`tools/stock_screener.py`. The VALUES are chosen here. Nothing is read back out of the
implementation under test to build an expectation.
"""
import contextlib
import json
import os
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (REPO, os.path.join(REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import research_ui           # noqa: E402
import screener_lab          # noqa: E402
import sovereign_buckets     # noqa: E402
import stock_screener        # noqa: E402

#: A tagged name and an untagged one. META is in `stock_screener.SHADOW_DEBT`; the join
#: that reads that table is the thing being protected, so a fixture of untagged names only
#: would let a broken join pass with everything at the `None -> 0` default.
TAGGED_TICKER = "META"
UNTAGGED_TICKER = "XOM"

#: A bucket constituent deliberately ABSENT from the rows below. `price_history` is keyed on
#: the union of the screened rows and `sovereign_buckets.all_tickers()`, and this name is
#: what makes the union observable: if the union were narrowed to the rows, its series would
#: stop travelling and nothing else in the fixture would notice.
BUCKET_ONLY_TICKER = "FRO"

FUND_ROWS = [
    {"ticker": TAGGED_TICKER, "name": "Meta Platforms", "sector": "Communication Services",
     "pe": 24.5, "growth": 0.21, "earnings_growth": 0.19, "revenue_growth": 0.16,
     "dividend_yield": 0.004, "debt_to_equity": 28.1, "beta": 1.21,
     "market_cap": 1.28e12, "dollar_volume": 9.4e9, "avg_volume": 1.6e7,
     "price": 512.4, "profit_margin": 0.34, "range_52w_pct": 0.72,
     "ai": "high", "bucket": "ai"},
    {"ticker": UNTAGGED_TICKER, "name": "Exxon Mobil", "sector": "Energy",
     "pe": 13.2, "growth": 0.04, "earnings_growth": 0.03, "revenue_growth": 0.02,
     "dividend_yield": 0.033, "debt_to_equity": 19.4, "beta": 0.86,
     "market_cap": 4.6e11, "dollar_volume": 1.1e9, "avg_volume": 1.4e7,
     "price": 118.7, "profit_margin": 0.11, "range_52w_pct": 0.44,
     "ai": "low", "bucket": "oil shock"},
]

#: Two closes per name is enough: nothing here asserts a return, only that the series
#: travelled and against which universe it was keyed.
_SERIES = [100.0, 101.5]


def _price_series():
    return {TAGGED_TICKER: list(_SERIES),
            UNTAGGED_TICKER: list(_SERIES),
            BUCKET_ONLY_TICKER: list(_SERIES)}


@contextlib.contextmanager
def authored_snapshots(fund_rows=None, price_series=None, with_prices=True):
    """Point the screener loaders at authored snapshots for the duration of the block.

    Sentiment is forced absent rather than left to whatever is on disk, so the payload is
    identical on a developer machine that has a tone cache and in CI, which does not. The
    payload's own fallback (`elif sent and sent.get("rows")`) means an accidental real tone
    snapshot could otherwise supply rows this fixture never authored.
    """
    fund_rows = FUND_ROWS if fund_rows is None else fund_rows
    series = _price_series() if price_series is None else price_series
    real = (stock_screener.SNAPSHOT_PATH, stock_screener.PRICES_PATH,
            screener_lab.load_snapshot)
    with tempfile.TemporaryDirectory() as tmp:
        fund_path = os.path.join(tmp, "fundamentals.json")
        with open(fund_path, "w", encoding="utf-8") as fh:
            json.dump({"as_of": "2026-08-11T00:00:00Z", "source": "authored fixture",
                       "universe_size": len(fund_rows), "errors": [],
                       "rows": fund_rows}, fh)
        price_path = os.path.join(tmp, "prices.json")
        with open(price_path, "w", encoding="utf-8") as fh:
            json.dump({"as_of": "2026-08-11T00:00:00Z", "source": "authored fixture",
                       "bars": len(_SERIES), "delisted": {}, "errors": [],
                       "series": series}, fh)
        stock_screener.SNAPSHOT_PATH = fund_path
        stock_screener.PRICES_PATH = price_path if with_prices else os.path.join(tmp, "none")
        screener_lab.load_snapshot = lambda *a, **k: None
        try:
            yield
        finally:
            (stock_screener.SNAPSHOT_PATH, stock_screener.PRICES_PATH,
             screener_lab.load_snapshot) = real


def authored_payload(**kw):
    with authored_snapshots(**kw):
        return research_ui._screener_combined_draft_payload()

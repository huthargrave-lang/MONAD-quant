"""Guards for tools/stock_screener.py and the /screen page in tools/research_ui.py.

The failure modes these hold shut:
  * a preset rule naming a typo'd metric filters every row to zero SILENTLY;
  * a missing snapshot rendering as an empty universe instead of an absence panel;
  * rows missing a required metric being dropped without being reported;
  * the two yfinance dividendYield conventions (fraction vs percent points) drifting
    apart across snapshot versions.
"""
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (REPO, os.path.join(REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import stock_screener as sc  # noqa: E402


def _row(**over):
    base = {
        "ticker": "TST", "name": "Test Co", "sector": "Technology", "ai": "low",
        "price": 100.0, "market_cap": 1e11, "pe": 15.0, "earnings_growth": 0.20,
        "revenue_growth": 0.10, "growth": 0.20, "dividend_yield": 0.02,
        "debt_to_equity": 50.0, "beta": 1.0, "avg_volume": 1e7,
        "dollar_volume": 1e9, "range_52w_pct": 0.3, "profit_margin": 0.15,
    }
    base.update(over)
    return base


class PresetDefinitionTests(unittest.TestCase):
    def test_every_preset_validates(self):
        sc.validate_presets()   # raises on a typo'd metric, op, rank or axis

    def test_every_rule_metric_is_a_real_snapshot_key(self):
        legal = set(sc.METRIC_KEYS) | set(sc.CATEGORICAL)
        for key, preset in sc.PRESETS.items():
            for metric, _op, _v in preset["require"]:
                self.assertIn(metric, legal, key)
            self.assertIn(preset["rank"][0], legal, key)
            self.assertIn(preset["x"][0], legal, key)
            self.assertIn(preset["y"][0], legal, key)

    def test_the_user_requested_lenses_all_exist(self):
        for key in ("low_pe_high_growth", "low_pe_high_dividend", "safety_low_debt",
                    "high_ai_exposure", "low_ai_exposure", "most_volatile",
                    "most_active", "sovereign_ledger", "chaos_hedges"):
            self.assertIn(key, sc.PRESETS)

    def test_the_sovereign_lenses_defer_to_the_books(self):
        """The docs are the source of truth; the lens must say so on its face."""
        for key in ("sovereign_ledger", "chaos_hedges"):
            self.assertIn("docs/research/SOVEREIGN_LEDGER", sc.PRESETS[key]["blurb"])
            self.assertIn("not signals", sc.PRESETS[key]["blurb"])

    def test_every_universe_entry_carries_legal_tags(self):
        sc.validate_universe()   # duplicate ticker, unknown ai tag, typo'd bucket

    def test_universe_tickers_are_unique(self):
        tickers = [t for t, *_ in sc.UNIVERSE]
        self.assertEqual(len(tickers), len(set(tickers)))

    def test_both_ai_poles_are_populated(self):
        tags = {ai for _t, _n, _s, ai, _b in sc.universe_rows()}
        self.assertIn("high", tags)
        self.assertIn("low", tags)

    def test_the_book_one_sovereignty_names_are_all_tagged(self):
        """The Book I set from docs/research/SOVEREIGN_LEDGER_WATCHLIST_2026.md
        (PR #56) IS the "wartime elements" bucket — a dropped name would silently
        vanish from the sovereign_ledger lens."""
        tagged = {t for t, _n, _s, _a, b in sc.universe_rows()
                  if b == "wartime elements"}
        self.assertEqual(tagged, {"MP", "UUUU", "LEU", "LAC", "UAMY", "USAR",
                                  "AREC", "NB"})

    def test_every_bucket_tag_is_a_declared_bucket(self):
        for t, _n, _s, _a, b in sc.universe_rows():
            if b is not None:
                self.assertIn(b, sc.CHAOS_BUCKETS, t)


class ApplyPresetTests(unittest.TestCase):
    def test_matches_pass_every_rule(self):
        rows = [_row(ticker="A", pe=10.0, growth=0.30),
                _row(ticker="B", pe=40.0, growth=0.30),   # fails pe
                _row(ticker="C", pe=10.0, growth=0.02)]   # fails growth
        matches, no_data = sc.apply_preset(rows, "low_pe_high_growth")
        self.assertEqual([r["ticker"] for r in matches], ["A"])
        self.assertEqual(no_data, [])

    def test_a_missing_metric_is_reported_not_hidden(self):
        rows = [_row(ticker="A"), _row(ticker="B", pe=None)]
        matches, no_data = sc.apply_preset(rows, "low_pe_high_growth")
        self.assertEqual([r["ticker"] for r in matches], ["A"])
        self.assertEqual([(r["ticker"], m) for r, m in no_data], [("B", ["pe"])])

    def test_ranking_is_best_first(self):
        rows = [_row(ticker="A", dividend_yield=0.04, pe=10),
                _row(ticker="B", dividend_yield=0.08, pe=10)]
        matches, _ = sc.apply_preset(rows, "low_pe_high_dividend")
        self.assertEqual([r["ticker"] for r in matches], ["B", "A"])

    def test_most_active_caps_at_its_top_n(self):
        rows = [_row(ticker="T{}".format(i), dollar_volume=float(i)) for i in range(40)]
        matches, _ = sc.apply_preset(rows, "most_active")
        self.assertEqual(len(matches), sc.PRESETS["most_active"]["top"])
        self.assertEqual(matches[0]["ticker"], "T39")

    def test_ai_presets_split_on_the_editorial_tag(self):
        rows = [_row(ticker="HI", ai="high"), _row(ticker="LO", ai="low"),
                _row(ticker="MID", ai="medium")]
        hi, _ = sc.apply_preset(rows, "high_ai_exposure")
        lo, _ = sc.apply_preset(rows, "low_ai_exposure")
        self.assertEqual([r["ticker"] for r in hi], ["HI"])
        self.assertEqual([r["ticker"] for r in lo], ["LO"])

    def test_sovereign_ledger_is_exactly_the_wartime_bucket(self):
        rows = [_row(ticker="MP", bucket="wartime elements", dollar_volume=2e8),
                _row(ticker="NEM", bucket="gold", dollar_volume=9e8),
                _row(ticker="AAPL", bucket=None)]
        matches, no_data = sc.apply_preset(rows, "sovereign_ledger")
        self.assertEqual([r["ticker"] for r in matches], ["MP"])
        self.assertEqual(no_data, [])

    def test_chaos_hedges_takes_every_tagged_row_and_no_untagged_one(self):
        rows = [_row(ticker="MP", bucket="wartime elements", dollar_volume=2e8),
                _row(ticker="NEM", bucket="gold", dollar_volume=9e8),
                _row(ticker="AAPL", bucket=None, dollar_volume=5e10)]
        matches, no_data = sc.apply_preset(rows, "chaos_hedges")
        self.assertEqual([r["ticker"] for r in matches], ["NEM", "MP"])  # $vol rank
        self.assertEqual(no_data, [])

    def test_an_untagged_row_is_not_reported_as_missing_data(self):
        """bucket is categorical: absence means untagged, never 'no data'."""
        matches, no_data = sc.apply_preset([_row(ticker="AAPL")], "chaos_hedges")
        self.assertEqual(matches, [])
        self.assertEqual(no_data, [])


class NormalisationTests(unittest.TestCase):
    def test_percent_points_dividend_yield_is_normalised_to_a_fraction(self):
        row = sc._normalise_row("T", "T", "S", "low", {"dividendYield": 8.0})
        self.assertAlmostEqual(row["dividend_yield"], 0.08)

    def test_fraction_dividend_yield_is_kept(self):
        row = sc._normalise_row("T", "T", "S", "low", {"dividendYield": 0.08})
        self.assertAlmostEqual(row["dividend_yield"], 0.08)

    def test_no_dividend_reads_as_zero_not_unknown(self):
        row = sc._normalise_row("T", "T", "S", "low", {})
        self.assertEqual(row["dividend_yield"], 0.0)

    def test_pe_falls_back_to_forward_and_rejects_nonpositive(self):
        self.assertEqual(sc._normalise_row("T", "T", "S", "low",
                                           {"forwardPE": 12.0})["pe"], 12.0)
        self.assertIsNone(sc._normalise_row("T", "T", "S", "low",
                                            {"trailingPE": -5.0})["pe"])

    def test_growth_prefers_earnings_then_revenue(self):
        row = sc._normalise_row("T", "T", "S", "low",
                                {"earningsGrowth": 0.2, "revenueGrowth": 0.1})
        self.assertEqual(row["growth"], 0.2)
        row = sc._normalise_row("T", "T", "S", "low", {"revenueGrowth": 0.1})
        self.assertEqual(row["growth"], 0.1)


class ScreenPageTests(unittest.TestCase):
    """The /screen page through the pure route table — no socket, no snapshot writes
    outside a temp dir."""

    def setUp(self):
        import tools.research_ui as ru
        self.ru = ru

    def test_missing_snapshot_renders_an_absence_panel_not_an_empty_screen(self):
        import tempfile
        from unittest import mock
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(sc, "SNAPSHOT_PATH",
                                   os.path.join(td, "none.json")):
                code, body, _ct = self.ru.route("/lenses", {}, {})
        self.assertEqual(code, 200)
        self.assertIn("No snapshot fetched", body)
        self.assertIn("stock_screener.py fetch", body)

    def test_every_preset_button_is_on_the_page(self):
        code, body, _ct = self.ru.route("/lenses", {}, {})
        self.assertEqual(code, 200)
        for key, preset in sc.PRESETS.items():
            self.assertIn('href="/lenses?preset={}"'.format(key), body)

    def test_an_unknown_preset_falls_back_rather_than_erroring(self):
        code, _body, _ct = self.ru.route("/lenses", {"preset": "nope"}, {})
        self.assertEqual(code, 200)

    def test_a_populated_snapshot_draws_matches_in_accent_over_muted_context(self):
        import json
        import tempfile
        from unittest import mock
        rows = [_row(ticker="AAA", pe=10.0, growth=0.30),
                _row(ticker="BBB", pe=50.0, growth=0.30),
                _row(ticker="CCC", pe=12.0, growth=0.20),
                _row(ticker="DDD", pe=60.0, growth=0.01)]
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "snap.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"as_of": "TEST", "source": "synthetic", "rows": rows}, fh)
            with mock.patch.object(sc, "SNAPSHOT_PATH", path):
                code, body, _ct = self.ru.route(
                    "/lenses", {"preset": "low_pe_high_growth"}, {})
        self.assertEqual(code, 200)
        self.assertEqual(body.count('fill="var(--accent)"'), 2)     # AAA, CCC
        self.assertEqual(body.count('fill="var(--axis)"'), 2)       # BBB, DDD muted
        self.assertIn("data/screener/fundamentals.json", body)      # provenance line

    def test_the_api_returns_the_same_matches_as_the_page(self):
        import json
        import tempfile
        from unittest import mock
        rows = [_row(ticker="AAA", pe=10.0, growth=0.30),
                _row(ticker="BBB", pe=50.0, growth=0.30)]
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "snap.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"as_of": "TEST", "source": "synthetic", "rows": rows}, fh)
            with mock.patch.object(sc, "SNAPSHOT_PATH", path):
                code, body, _ct = self.ru.route(
                    "/api/screen", {"preset": "low_pe_high_growth"}, {})
        self.assertEqual(code, 200)
        payload = json.loads(body)
        self.assertEqual([r["ticker"] for r in payload["matches"]], ["AAA"])

    def test_the_screener_module_emits_no_html_so_the_census_stays_complete(self):
        with open(os.path.join(REPO, "tools", "stock_screener.py"),
                  encoding="utf-8") as fh:
            source = fh.read()
        self.assertNotIn("<html", source.lower())
        self.assertNotIn("<style>", source.lower())


if __name__ == "__main__":
    unittest.main()

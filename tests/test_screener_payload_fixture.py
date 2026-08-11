"""The authored-snapshot fixture has to be hermetic, or the tests it feeds are worthless.

Two failure modes, both silent, both of which would make the three CI-safe screener tests
pass for the wrong reason on a developer machine and only there:

  * **Fallback.** If the fixture did not fully displace the real snapshots, a machine with a
    populated `data/screener/` would feed those rows in instead. The tests would pass, and
    they would be measuring the cache again — the exact dependency they were rewritten to
    remove, restored invisibly.
  * **Leak.** The fixture repoints module-level paths. If it failed to restore them, every
    later test in the same process would read a temp directory that no longer exists, and
    the failures would surface far from the cause.

Both are asserted here rather than trusted, because both are invisible in CI: with no
snapshots on disk there is nothing to fall back TO, so CI cannot detect either one.
"""
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (REPO, os.path.join(REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import screener_lab  # noqa: E402
import stock_screener  # noqa: E402
from tests import screener_payload_fixture as fx  # noqa: E402


class TheFixtureDisplacesTheRealSnapshots(unittest.TestCase):
    def test_the_rows_are_exactly_the_authored_ones(self):
        """The load-bearing property. On a machine with a real fundamentals cache this
        fails the moment the fixture stops displacing it; in CI it is trivially true, which
        is why it must be asserted on the machines where it is not."""
        payload = fx.authored_payload()
        self.assertEqual([r["tk"] for r in payload["rows"]],
                         [r["ticker"] for r in fx.FUND_ROWS])

    def test_sentiment_is_forced_absent_rather_than_left_to_disk(self):
        """The payload falls back to tone rows when fundamentals are empty, so a real tone
        cache could otherwise supply names this fixture never authored."""
        payload = fx.authored_payload()
        self.assertFalse(payload["has_sentiment"])
        self.assertIsNone(payload["sentiment_built"])

    def test_the_price_history_holds_only_authored_series(self):
        payload = fx.authored_payload()
        self.assertEqual(sorted(payload["price_history"]),
                         sorted([fx.TAGGED_TICKER, fx.UNTAGGED_TICKER,
                                 fx.BUCKET_ONLY_TICKER]))

    def test_an_absent_price_cache_yields_no_series_rather_than_a_fallback(self):
        """`with_prices=False` points the loader at a path that does not exist — the CI
        condition for the price cache. The payload must report emptiness, not reach for
        the real file."""
        payload = fx.authored_payload(with_prices=False)
        self.assertEqual(payload["price_history"], {})
        self.assertIsNone(payload["price_as_of"])


class TheFixtureRestoresWhatItRepointed(unittest.TestCase):
    def test_the_module_paths_come_back(self):
        before = (stock_screener.SNAPSHOT_PATH, stock_screener.PRICES_PATH,
                  screener_lab.load_snapshot)
        with fx.authored_snapshots():
            self.assertNotEqual(stock_screener.SNAPSHOT_PATH, before[0],
                                "the fixture never repointed the fundamentals path, so it "
                                "is reading whatever is on disk")
        self.assertEqual((stock_screener.SNAPSHOT_PATH, stock_screener.PRICES_PATH,
                          screener_lab.load_snapshot), before)

    def test_the_paths_come_back_even_when_the_block_raises(self):
        before = stock_screener.SNAPSHOT_PATH
        with self.assertRaises(RuntimeError):
            with fx.authored_snapshots():
                raise RuntimeError("boom")
        self.assertEqual(stock_screener.SNAPSHOT_PATH, before,
                         "a failing test would leave every later one reading a deleted "
                         "temp directory")


class TheAuthoredRowsExerciseWhatTheyClaimTo(unittest.TestCase):
    def test_one_name_is_tagged_and_one_is_not(self):
        """The severity-rank test distinguishes them, so a fixture where both were tagged
        the same way would let a flattened join pass."""
        self.assertIn(fx.TAGGED_TICKER, stock_screener.SHADOW_DEBT)
        self.assertNotIn(fx.UNTAGGED_TICKER, stock_screener.SHADOW_DEBT)

    def test_the_bucket_only_name_really_is_bucket_only(self):
        """It is what makes the row/bucket union observable."""
        import sovereign_buckets as sb
        self.assertIn(fx.BUCKET_ONLY_TICKER, set(sb.all_tickers()))
        self.assertNotIn(fx.BUCKET_ONLY_TICKER,
                         {r["ticker"] for r in fx.FUND_ROWS})


if __name__ == "__main__":
    unittest.main()

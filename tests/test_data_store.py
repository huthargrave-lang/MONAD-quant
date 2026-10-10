"""
The research data store (src/research/data_store.py): restricted vendors' observations
default to the private store for every writer, every loader reads the private store, a
restricted file cannot be written where git would publish it, and a data set built after
the change never shows up as PUBLIC-RESTRICTED in tools/data_inventory.py.
(docs/research/data/README.md; docs/research/DATA_REDISTRIBUTION_AUDIT.md, option A.)
"""
import gzip
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

import data_inventory as inv  # noqa: E402

from src.research import bdc_data, cef_data, daily_data, data_store  # noqa: E402
from src.research import deletion_classes, earnings_data, futures_panel, insider_data  # noqa: E402
from src.research import spinoff_classes  # noqa: E402
from src.research.data_store import SnapshotError  # noqa: E402

DATES = pd.bdate_range("2012-01-02", periods=daily_data.MIN_SESSIONS + 10)


def _asset(seed, start=0):
    rng = np.random.default_rng(seed)
    close = 50 * np.exp(np.cumsum(rng.normal(0, 0.01, len(DATES))))
    opens = np.r_[close[0], close[:-1]] * np.exp(rng.normal(0, 0.004, len(DATES)))
    return pd.DataFrame({"Open": opens, "Close": close, "Dividends": 0.0, "Capital Gains": 0.0,
                         "Stock Splits": 0.0}, index=DATES).iloc[start:]


def _fetchers():
    panel = {"AAA": _asset(1), "BBB": _asset(2, start=30)}
    cash = pd.Series(2.0, index=DATES)
    return dict(fetch_asset=lambda s, a, b: panel[s], fetch_cash=lambda a, b: cash,
                fetch_check=lambda a, b: cash + 0.01)


def _nav_frames():
    idx = pd.to_datetime(["2015-01-02", "2015-01-09"])
    price = pd.DataFrame({"A": [10.0, 10.5], "B": [5.0, np.nan]}, index=idx)
    return {"price": price, "nav": price * 1.1}


def _futures_fetch(symbol, start, end):
    return pd.Series(np.linspace(50, 60, 30), index=pd.bdate_range("2015-01-02", periods=30))


class Policy(unittest.TestCase):
    def test_restricted_vendors_are_named_from_sources_of_any_shape(self):
        self.assertEqual(data_store.restricted_vendors("yfinance 1.2.0 history"), ["Yahoo"])
        self.assertEqual(data_store.restricted_vendors({"prices": "yfinance", "cash": "FRED DTB3",
                                                        "check": "CEFConnect weekly"}),
                         ["CEFConnect/Morningstar", "Yahoo"])
        self.assertEqual(data_store.restricted_vendors("SEC XBRL frames"), [])
        self.assertEqual(data_store.restricted_vendors(
            {"per_asset": {"GOLD": "Deutsche Bundesbank, source: Frankfurt Stock Exchange"}}),
            ["Frankfurt Stock Exchange (via Bundesbank)"])

    def test_a_manifest_with_both_source_fields_is_judged_on_both(self):
        both = {"source": "CEFConnect pricinghistory", "sources": [{"file": "2024q1.zip"}]}
        self.assertEqual(data_store.manifest_restricted_vendors(both), ["CEFConnect/Morningstar"])
        self.assertEqual(data_store.sources_of({"source": "x"}), "x")
        self.assertEqual(data_store.sources_of({}), "")

    def test_private_is_decided_by_the_vendor_and_cannot_be_overridden_to_public(self):
        self.assertTrue(data_store.must_be_private("yfinance"))
        self.assertFalse(data_store.must_be_private("SEC EDGAR"))
        self.assertTrue(data_store.must_be_private("SEC EDGAR", True))
        with self.assertRaises(SnapshotError):
            data_store.must_be_private("Yahoo ^GSPC", False)

    def test_the_committed_store_pairs_only_with_the_private_store_its_readers_search(self):
        st = data_store.stores()
        self.assertEqual(st.search, [data_store.DATA_DIR, data_store.PRIVATE_DATA_DIR])
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(data_store.stores(td).search, [Path(td)])
            self.assertEqual(data_store.stores(td, td + "/p").search, [Path(td), Path(td + "/p")])
            with self.assertRaises(SnapshotError):
                data_store.write_stores(None, td)
        self.assertEqual(data_store.write_stores(None, data_store.PRIVATE_DATA_DIR).private,
                         data_store.PRIVATE_DATA_DIR)


class RefusePublication(unittest.TestCase):
    """The last line of defence: whatever the arguments, restricted bytes never land in a
    path git would commit."""

    def test_the_committed_store_is_refused(self):
        with self.assertRaises(SnapshotError) as err:
            data_store.refuse_publication(data_store.DATA_DIR / f"DS-{'0' * 64}.csv.gz", ["Yahoo"])
        self.assertIn("committed store", str(err.exception))

    def test_a_tracked_or_unignored_repository_path_is_refused(self):
        with self.assertRaises(SnapshotError) as err:
            data_store.refuse_publication(REPO / "docs" / "research" / f"FUT-{'0' * 64}.csv.gz")
        self.assertIn("not git-ignored", str(err.exception))

    def test_the_private_store_a_gitignored_cache_and_a_temp_dir_are_allowed(self):
        name = f"DS-{'0' * 64}.csv.gz"
        data_store.refuse_publication(data_store.PRIVATE_DATA_DIR / name)
        data_store.refuse_publication(REPO / "local_logs" / "forward_data" / name)
        with tempfile.TemporaryDirectory() as td:
            data_store.refuse_publication(Path(td) / name)

    def test_writers_cannot_be_pointed_at_the_committed_store(self):
        with self.assertRaises(SnapshotError):
            data_store.write("FUT", b"date,symbol,close\n", private=True,
                             data_dir=data_store.DATA_DIR,
                             private_dir=data_store.DATA_DIR)


class WritersDefaultToPrivate(unittest.TestCase):
    """A manifest naming Yahoo/yfinance or CEFConnect records private observations, and the
    csv.gz is in the private store, not beside the manifest: for every restricted writer."""

    def setUp(self):
        self._tds = [tempfile.TemporaryDirectory() for _ in range(2)]
        self.pub, self.priv = (Path(t.name) for t in self._tds)

    def tearDown(self):
        for t in self._tds:
            t.cleanup()

    def assert_private(self, prefix, sha):
        manifest = json.loads((self.pub / f"{prefix}-{sha}.json").read_text(encoding="utf-8"))
        self.assertTrue(data_store.manifest_restricted_vendors(manifest), manifest)
        self.assertEqual(manifest["observations"], data_store.private_record(sha))
        self.assertFalse((self.pub / f"{prefix}-{sha}.csv.gz").exists())
        self.assertIsNone(data_store.verify_file(self.priv / f"{prefix}-{sha}.csv.gz"))

    def test_a_yahoo_snapshot_is_private_by_default(self):
        sha = daily_data.build_snapshot(["AAA", "BBB"], "2012-01-01", "2016-12-31",
                                        data_dir=self.pub, private_dir=self.priv, **_fetchers())
        self.assert_private("DS", sha)
        snap = daily_data.load_snapshot(sha, data_dir=self.pub, private_dir=self.priv)
        self.assertEqual(snap.assets, ("AAA", "BBB"))

    def test_a_yahoo_snapshot_cannot_be_forced_public(self):
        with self.assertRaises(SnapshotError):
            daily_data.build_snapshot(["AAA", "BBB"], "2012-01-01", "2016-12-31", private=False,
                                      data_dir=self.pub, private_dir=self.priv, **_fetchers())
        self.assertEqual(list(self.pub.iterdir()) + list(self.priv.iterdir()), [])

    def test_a_cefconnect_panel_is_private(self):
        sha = cef_data.write_panel(_nav_frames(), {"category": {"A": "x", "B": "y"}},
                                   data_dir=self.pub, private_dir=self.priv)
        self.assert_private("CEFNAV", sha)
        panel = cef_data.load_panel(sha, data_dir=self.pub, private_dir=self.priv)
        self.assertAlmostEqual(float(panel.discount.loc["2015-01-09", "A"]), 1 / 1.1 - 1, places=12)

    def test_a_yahoo_futures_panel_is_private_and_its_manifest_is_written_once(self):
        sha = futures_panel.build(["CL=F"], "2015-01-01", "2016-01-01", fetch=_futures_fetch,
                                  data_dir=self.pub, private_dir=self.priv)
        self.assert_private("FUT", sha)
        first = (self.pub / f"FUT-{sha}.json").read_bytes()
        again = futures_panel.build(["CL=F"], "2015-01-01", "2016-01-01", fetch=_futures_fetch,
                                    data_dir=self.pub, private_dir=self.priv)
        self.assertEqual(again, sha)
        self.assertEqual((self.pub / f"FUT-{sha}.json").read_bytes(), first)
        self.assertAlmostEqual(futures_panel.load(sha, data_dir=self.pub,
                                                  private_dir=self.priv).close["CL=F"].iloc[-1], 60.0)

    def test_sec_panels_stay_public(self):
        rows = [("AAA", "2020-03-31", 10.5, "2020-05-01", "2020-05-02")]
        sha = bdc_data.write_panel(rows, {}, data_dir=self.pub)
        manifest = json.loads((self.pub / f"BDCNAV-{sha}.json").read_text(encoding="utf-8"))
        self.assertNotIn("observations", manifest)
        self.assertTrue((self.pub / f"BDCNAV-{sha}.csv.gz").exists())
        sha = earnings_data.write([("AAA", "2020-05-01")], {}, data_dir=self.pub)
        self.assertTrue((self.pub / f"EARNDATES-{sha}.csv.gz").exists())
        ev = pd.DataFrame({"ticker": ["AAA"], "known": ["2020-05-02"]})
        sha = insider_data.write(ev, {"sources": [{"file": "2020q2_form345.zip"}]}, data_dir=self.pub)
        self.assertTrue((self.pub / f"INSIDER-{sha}.csv.gz").exists())

    def test_nothing_built_after_the_change_is_public_restricted(self):
        """tools/data_inventory.py over a store built only by today's writers: zero
        PUBLIC-RESTRICTED, and every restricted data set present in the private store."""
        daily_data.build_snapshot(["AAA", "BBB"], "2012-01-01", "2016-12-31",
                                  data_dir=self.pub, private_dir=self.priv, **_fetchers())
        cef_data.write_panel(_nav_frames(), {"category": {}}, data_dir=self.pub, private_dir=self.priv)
        futures_panel.build(["CL=F"], "2015-01-01", "2016-01-01", fetch=_futures_fetch,
                            data_dir=self.pub, private_dir=self.priv)
        bdc_data.write_panel([("AAA", "2020-03-31", 10.5, "2020-05-01", "2020-05-02")], {},
                             data_dir=self.pub)
        rows = inv.inventory(self.pub, records=[], store=self.priv)
        s = inv.summary(rows)
        self.assertEqual(s["restricted_public_data_sets"], 0, rows)
        self.assertEqual((s["private_data_sets"], s["private_present"]), (3, 3))
        self.assertEqual(s["private_but_committed"], 0)
        self.assertTrue(inv.verify_store(self.pub, self.priv).ok)

    def test_a_scratch_store_keeps_everything_together(self):
        """A caller passing only its own data_dir (tests, local_logs/forward_data) gets
        the observations beside the manifest, and reads them back from there."""
        sha = cef_data.write_panel(_nav_frames(), {"category": {}}, data_dir=self.pub)
        self.assertTrue((self.pub / f"CEFNAV-{sha}.csv.gz").exists())
        self.assertIn("observations", json.loads((self.pub / f"CEFNAV-{sha}.json").read_text()))
        cef_data.load_panel(sha, data_dir=self.pub)


class EveryLoaderReadsThePrivateStore(unittest.TestCase):
    """Whatever the prefix, a data set whose observations are private loads through its
    normal loader, verified; a missing one names the private store and how to restore it."""

    def put(self, pub, priv, prefix, data, manifest=None):
        sha, _ = data_store.write(prefix, data, private=True, data_dir=pub, private_dir=priv)
        man = {"sha": sha, "source": "test", "observations": data_store.private_record(sha),
               **(manifest or {})}
        (pub / f"{prefix}-{sha}.json").write_text(json.dumps(man), encoding="utf-8")
        return sha

    def test_each_prefix(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            pub, priv = Path(a), Path(b)
            nav = bdc_data.encode([("AAA", "2020-03-31", 10.5, "2020-05-01", "2020-05-02")])
            cases = {
                "BDCNAV": (nav, lambda s: bdc_data.load_panel(s, data_dir=pub, private_dir=priv)),
                "MREITBV": (nav, lambda s: bdc_data.load_panel(s, data_dir=pub, prefix="MREITBV",
                                                               private_dir=priv)),
                "EARNDATES": (earnings_data.encode([("AAA", "2020-05-01")]),
                              lambda s: earnings_data.load(s, data_dir=pub, private_dir=priv)),
                "INSIDER": (b"ticker,known\nAAA,2020-05-02\n",
                            lambda s: insider_data.load(s, data_dir=pub, private_dir=priv)),
                "SPINEVENTS": (spinoff_classes.encode([("AAA", "1", "2020-01-02")]),
                               lambda s: spinoff_classes.load_events(s, data_dir=pub, private_dir=priv)),
                "IDXDEL": (deletion_classes.encode([("AAA", "2020-01-02")]),
                           lambda s: deletion_classes.load_events(s, data_dir=pub, private_dir=priv)),
                "CEFNAV": (cef_data.encode_csv(_nav_frames()),
                           lambda s: cef_data.load_panel(s, data_dir=pub, private_dir=priv)),
                "FUT": (b"date,symbol,close\n2015-01-02,CL=F,50.0\n",
                        lambda s: futures_panel.load(s, data_dir=pub, private_dir=priv)),
            }
            for prefix, (data, load) in cases.items():
                with self.subTest(prefix=prefix):
                    sha = self.put(pub, priv, prefix, data)
                    self.assertIsNotNone(load(sha))
                    path = priv / f"{prefix}-{sha}.csv.gz"
                    path.write_bytes(gzip.compress(data + b"x\n"))
                    with self.assertRaises(SnapshotError):
                        load(sha)
                    path.unlink()
                    with self.assertRaises(SnapshotError) as err:
                        load(sha)
                    self.assertIn("private", str(err.exception))
                    self.assertIn("data_inventory.py import", str(err.exception))

    def test_a_snapshot_loads_from_the_private_store(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            pub, priv = Path(a), Path(b)
            sha = daily_data.build_snapshot(["AAA", "BBB"], "2012-01-01", "2016-12-31",
                                            data_dir=pub, private_dir=priv, **_fetchers())
            self.assertEqual(daily_data.load_snapshot(sha, data_dir=pub, private_dir=priv).sha, sha)

    def test_an_existing_file_that_does_not_verify_is_refused_not_kept(self):
        with tempfile.TemporaryDirectory() as td:
            data = b"date,symbol,close\n2015-01-02,CL=F,50.0\n"
            sha, path = data_store.write("FUT", data, private=False, data_dir=td)
            path.write_bytes(gzip.compress(b"other\n"))
            with self.assertRaises(SnapshotError):
                data_store.write("FUT", data, private=False, data_dir=td)


if __name__ == "__main__":
    unittest.main()

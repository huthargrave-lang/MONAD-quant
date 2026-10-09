"""The forward watch (src/research/forward_watch.py): the record is exact (it reproduces the
counted search's series), chained and tamper-evident, books late revisions as corrections,
refuses an unattested engine change, and decides by the pre-stated sequential rule."""
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from src.research import allocation_stats as stats  # noqa: E402
from src.research import commodity_classes as cc  # noqa: E402
from src.research import daily_data  # noqa: E402
from src.research import forward_watch as fw  # noqa: E402
from src.research import trials  # noqa: E402
from src.research.daily_data import Snapshot  # noqa: E402
from src.research.daily_strategy import evaluate_daily  # noqa: E402
from src.strategy.counted import uncounted  # noqa: E402

EVAL = {"theta1": 0.3, "alpha": 0.05, "beta": 0.2}


def spec_for(pairs, weights, anchor, **kw):
    return {"watch": "HTEST", "claim": "test", "status": "forward watch; not an admission candidate",
            "pairs": [list(p) for p in pairs], "pair_weights": list(weights), "stress_multiple": 2.0,
            "anchor_session": str(pd.Timestamp(anchor).date()), "snapshot_start": "2015-01-01",
            "replay_from": kw.pop("replay_from", "2015-01-01"),
            "evaluation": EVAL, "evaluator_sources": list(fw.EVALUATOR_SOURCES),
            "evaluator_sha256": fw.evaluator_sha256(), "void_conditions": ["index change"],
            "window_opens": "first session after the spec reaches the deploy branch", **kw}


FULL = 1000


def market(n=420, seed=3, dist_on=None):
    """The first ``n`` sessions of one fixed synthetic market, so a longer market extends a
    shorter one exactly (only a deliberate ``dist_on`` revises the past)."""
    dates = pd.bdate_range("2015-01-02", periods=FULL)
    rng = np.random.default_rng(seed)
    cols = ["SPY", "GDX", "GLD", "SIL", "SLV"]
    close = pd.DataFrame({c: 30 * np.exp(np.cumsum(rng.normal(0, 0.012, FULL))) for c in cols}, index=dates)
    opens = close.shift(1).fillna(close.iloc[0]) * np.exp(rng.normal(0, 0.003, (FULL, len(cols))))
    dates, close, opens = dates[:n], close.iloc[:n], opens.iloc[:n]
    dist = close * 0.0
    if dist_on is not None:
        dist.loc[dates[dist_on], "GDX"] = 0.5
    return Snapshot(sha=f"m{seed}{dist_on}".ljust(64, "0"), dates=dates, assets=tuple(cols), open=opens,
                    close=close, dist=dist, dtb3=pd.Series(1.5, index=dates), manifest={})


class Ledgered(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.patch = mock.patch.object(trials, "LEDGER_DIR", self.dir / "ledger")
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self._tmp.cleanup()

    def freeze(self, spec):
        return fw.freeze(spec, watch_dir=self.dir / "w", check_web=False, now="2026-10-09T00:00:00Z")

    def run_(self):
        return trials.open_run(producer=fw.PRODUCER, family="forward_watch.HTEST.v1")


class Exactness(Ledgered):
    def test_the_daily_chained_record_equals_one_evaluation(self):
        snap = market()
        spec = spec_for([("GDX", "GLD"), ("SIL", "SLV")], [0.5, 0.5], snap.dates[0])
        self.freeze(spec)
        start = cc.ratio_start(snap, "GDX", "GLD", floor=snap.dates[0])
        with self.run_() as run:
            fw.write_genesis("HTEST", snap, start, run=run, watch_dir=self.dir / "w")
            fw.log_sessions("HTEST", snap, run=run, watch_dir=self.dir / "w")
        rows = [r for _b, r in fw.read("HTEST", self.dir / "w")]
        logged = pd.Series({pd.Timestamp(r["session"]): r["active"]["1x"]["pairs"]["GDX/GLD"]
                            for r in rows if r["kind"] == "session"})
        with uncounted("unit test: the full-window evaluation the watch must reproduce"):
            a = evaluate_daily(cc.decide_ratio(snap, cc.ratio_point("GDX", "GLD")), snap, start=start).returns
            b = evaluate_daily(cc.decide_ratio(snap, cc.ratio_reference("GDX", "GLD")), snap, start=start).returns
        expected = (a - b).iloc[1:]
        np.testing.assert_allclose(logged.to_numpy(), expected.reindex(logged.index).to_numpy(), atol=1e-12)
        sess = [r for r in rows if r["kind"] == "session"]
        self.assertTrue(all(r["catch_up"] for r in sess))
        self.assertEqual(fw.verify("HTEST", self.dir / "w"), [])

    def test_decisions_read_no_data_after_their_session(self):
        snap = market()
        for kind in ("tilt", "bench"):
            for k in (150, 233, 301):
                d = snap.dates[k]
                full = fw.decisions(snap, ("SIL", "SLV"), kind, d, k)
                cut = fw.decisions(stats.masked_after(snap, d), ("SIL", "SLV"), kind, d, k)
                self.assertEqual(full, cut)


class RecordedSeries(Ledgered):
    """The record reproduces the counted 2016-2026 searches exactly (real snapshots;
    skipped, with the reason, when their observations are not on this machine)."""

    def _recorded(self, domain, snapshot):
        import domain_search
        from src.research.backtest_trials import family_members
        from src.research.daily_domains import DOMAINS
        from src.research.daily_trials import family_name, stored_returns
        d = DOMAINS[domain]
        ctx = d.load({"snapshot": snapshot})
        start, end = d.window(ctx)
        data = ctx.data_spec(start, end)
        self.patch.stop()                                      # read the real ledger
        try:
            recs = list(trials.iter_trials())
        finally:
            self.patch.start()
        fam = domain_search.latest(family_members(recs, family_name(d.name)), data, start, end)
        ref = domain_search.latest(family_members(recs, family_name(d.name, reference=True)), data, start, end)
        (rec,), (ref_rec,) = fam.values(), ref.values()
        self.patch.stop()
        try:
            series = trials.load_returns([rec, ref_rec])
        finally:
            self.patch.start()
        return ctx.snap, start, stored_returns(series[rec.key]) - stored_returns(series[ref_rec.key])

    def check(self, domain, snapshot, pair):
        try:
            snap, start, recorded = self._recorded(domain, snapshot)
        except daily_data.SnapshotError as exc:
            self.skipTest(f"observations not on this machine (private store): {exc}")
        spec = spec_for([pair], [1.0], snap.dates[0], replay_from="2016-01-01")
        self.freeze(spec)
        with self.run_() as run:
            fw.write_genesis("HTEST", snap, start, run=run, watch_dir=self.dir / "w")
            fw.log_sessions("HTEST", snap, run=run, watch_dir=self.dir / "w")
        rows = [r for _b, r in fw.read("HTEST", self.dir / "w") if r["kind"] == "session"]
        logged = pd.Series({pd.Timestamp(r["session"]): r["active"]["1x"]["active"] for r in rows})
        np.testing.assert_allclose(logged.to_numpy(), recorded.reindex(logged.index).to_numpy(), atol=1e-12)

    def test_sil_slv(self):
        self.check("silver_miner_ratio", "33bafcfd05e348e11eb5a1e9c719c1365d87530670348e34211cad7e116fd035",
                   ("SIL", "SLV"))

    def test_gdx_gld(self):
        self.check("miner_metal_ratio", "6f18a1b701ffd141cc54f9413c822b8f7698a0ce597be63f5fb7fd6e1506ae5b",
                   ("GDX", "GLD"))


class TamperEvidence(Ledgered):
    def logged(self, n_extra=0):
        snap = market(n=330)
        spec = spec_for([("GDX", "GLD"), ("SIL", "SLV")], [0.5, 0.5], snap.dates[0])
        self.freeze(spec)
        with self.run_() as run:
            fw.write_genesis("HTEST", snap, snap.dates[300], run=run, watch_dir=self.dir / "w")
            fw.log_sessions("HTEST", snap, run=run, watch_dir=self.dir / "w")
        return fw.log_path("HTEST", self.dir / "w")

    def lines(self, path):
        return path.read_bytes().splitlines(keepends=True)

    def test_an_edited_line_breaks_the_chain(self):
        p = self.logged()
        ls = self.lines(p)
        row = json.loads(ls[5])
        row["active"]["1x"]["active"] += 0.01
        ls[5] = (json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n").encode()
        p.write_bytes(b"".join(ls))
        self.assertTrue(any("chain broken" in x for x in fw.verify("HTEST", self.dir / "w")))

    def test_reordering_and_gaps_are_caught(self):
        p = self.logged()
        ls = self.lines(p)
        p.write_bytes(b"".join(ls[:4] + [ls[5], ls[4]] + ls[6:]))
        probs = fw.verify("HTEST", self.dir / "w")
        self.assertTrue(any("chain broken" in x for x in probs))
        p.write_bytes(b"".join(ls[:4] + ls[5:]))
        probs = fw.verify("HTEST", self.dir / "w")
        self.assertTrue(any("does not follow" in x for x in probs))

    def test_a_changed_spec_and_a_line_after_void_are_caught(self):
        p = self.logged()
        spec_file = fw.spec_path("HTEST", self.dir / "w")
        spec_file.write_bytes(spec_file.read_bytes().replace(b'"claim":"test"', b'"claim":"edited"'))
        self.assertTrue(any("different spec" in x for x in fw.verify("HTEST", self.dir / "w")))

    def test_nothing_may_follow_a_void_and_logging_refuses(self):
        self.logged()
        _spec, h = fw.load("HTEST", self.dir / "w")
        fw.append("HTEST", {"kind": "void", "reason": "index change"}, spec_hash=h, watch_dir=self.dir / "w")
        with self.run_() as run, self.assertRaises(fw.WatchError):
            fw.log_sessions("HTEST", market(n=331), run=run, watch_dir=self.dir / "w")
        fw.append("HTEST", {"kind": "window_open", "opens_at_session": "2016-01-01"}, spec_hash=h,
                  watch_dir=self.dir / "w")
        self.assertTrue(any("after the watch was voided" in x for x in fw.verify("HTEST", self.dir / "w")))

    def test_an_unattested_engine_change_stops_logging(self):
        self.logged()
        with self.run_() as run, self.assertRaises(fw.WatchError):
            fw.log_sessions("HTEST", market(n=331), run=run, watch_dir=self.dir / "w", current_evaluator="0" * 64)
        _spec, h = fw.load("HTEST", self.dir / "w")
        fw.append("HTEST", {"kind": "evaluator_change", "evaluator_sha256": "0" * 64, "reason": "test",
                            "attested_by_tests": "tests/test_forward_watch.py passed"},
                  spec_hash=h, watch_dir=self.dir / "w")
        with self.run_() as run:
            out = fw.log_sessions("HTEST", market(n=331), run=run, watch_dir=self.dir / "w",
                                  current_evaluator="0" * 64)
        self.assertEqual([r["kind"] for r in out], ["session"])


class Corrections(Ledgered):
    def test_a_late_distribution_is_booked_as_a_correction_and_counted(self):
        before = market(n=330)
        spec = spec_for([("GDX", "GLD"), ("SIL", "SLV")], [0.5, 0.5], before.dates[0])
        self.freeze(spec)
        with self.run_() as run:
            fw.write_genesis("HTEST", before, before.dates[300], run=run, watch_dir=self.dir / "w")
            fw.log_sessions("HTEST", before, run=run, watch_dir=self.dir / "w", opens_at=str(before.dates[301].date()))
        revised = market(n=331, dist_on=320)                    # GDX distribution booked late
        with self.run_() as run:
            out = fw.log_sessions("HTEST", revised, run=run, watch_dir=self.dir / "w")
        kinds = [r["kind"] for r in out]
        self.assertEqual(kinds, ["correction", "session"])
        corr = out[0]
        self.assertEqual(corr["session"], str(revised.dates[320].date()))
        self.assertNotEqual(corr["delta"]["1x"], 0.0)
        rows = fw.read("HTEST", self.dir / "w")
        logged = {r["session"]: r["active"]["1x"]["active"] for _b, r in rows if r["kind"] == "session"}
        self.assertEqual(fw.verify("HTEST", self.dir / "w"), [])
        with self.run_() as run:                                 # nothing new: no second correction
            self.assertEqual(fw.log_sessions("HTEST", revised, run=run, watch_dir=self.dir / "w"), [])
        self.assertIn(str(revised.dates[320].date()), logged)


class Decision(unittest.TestCase):
    SPEC = {"evaluation": EVAL, "stress_multiple": 2.0}

    def test_boundaries_match_the_ruling(self):
        for years, up, lo in ((5, 2.00, -0.89), (10, 1.07, -0.37), (20, 0.61, -0.11)):
            u, low = fw.boundaries(self.SPEC, years)
            self.assertAlmostEqual(u, up, places=2)
            self.assertAlmostEqual(low, lo, places=2)

    def test_error_rates_by_seeded_monte_carlo(self):
        """Anniversary checks, 20 years: promote under H0 rare (< 2%); close under H1
        uncommon (< 12%); under H1 promotion by year 20 near the ruling's 10%."""
        rng = np.random.default_rng(20261009)
        paths, years = 4000, 20

        def rates(true_sharpe):
            promote = close = 0
            # annual Sharpe `true_sharpe`: daily mean / daily sd = true_sharpe / sqrt(252)
            daily = rng.normal(true_sharpe / 252, 1 / math.sqrt(252), (paths, 252 * years))
            for p in range(paths):
                x = daily[p]
                for y in range(1, years + 1):
                    s = x[: 252 * y]
                    sh = s.mean() / s.std(ddof=1) * math.sqrt(252)
                    up, lo = fw.boundaries(self.SPEC, y)
                    if sh >= up:
                        promote += 1
                        break
                    if sh <= lo:
                        close += 1
                        break
            return promote / paths, close / paths

        p0, c0 = rates(0.0)
        p1, c1 = rates(0.3)
        self.assertLess(p0, 0.02)
        self.assertLess(c1, 0.12)
        self.assertGreater(c0, 0.25)
        self.assertTrue(0.04 < p1 < 0.18, p1)

    def test_decide_counts_only_the_window_and_applies_corrections(self):
        idx = pd.bdate_range("2027-01-01", periods=600)
        rng = np.random.default_rng(1)
        rows = [(b"", {"kind": "genesis"}), (b"", {"kind": "window_open", "opens_at_session": str(idx[100].date())})]
        for d in idx:
            a = float(rng.normal(0.0004, 0.004))
            rows.append((b"", {"kind": "session", "session": str(d.date()),
                               "active": {"1x": {"active": a}, "2x": {"active": a - 1e-5}}}))
        reps = fw.decide(self.SPEC, rows)
        self.assertEqual(reps[0]["anniversary"], 1)
        self.assertAlmostEqual(reps[0]["years"], 253 / 252, places=1)
        self.assertEqual([r["verdict"] for r in reps][-1] in ("continue", "promote", "close"), True)
        void = rows + [(b"", {"kind": "void", "reason": "GDX index change"})]
        self.assertEqual(fw.decide(self.SPEC, void)[0]["verdict"], "VOID")


if __name__ == "__main__":
    unittest.main()


class WindowOpening(unittest.TestCase):
    def test_the_window_opens_at_the_first_session_after_the_spec_reached_the_branch(self):
        import forward_watch as tool
        snap = market(n=30)
        with mock.patch.object(tool, "spec_reached", return_value=pd.Timestamp(snap.dates[10]) + pd.Timedelta(hours=20)):
            self.assertEqual(tool.opens_at("HTEST", snap, "origin/development"), str(snap.dates[11].date()))
        with mock.patch.object(tool, "spec_reached", return_value=None):
            self.assertIsNone(tool.opens_at("HTEST", snap, "origin/development"))

    def test_history_rules_freeze_specs_and_let_logs_only_grow(self):
        import forward_watch as tool
        self.assertEqual(tool._history_rule("docs/research/forward_watch/H1.json"), "identical")
        self.assertEqual(tool._history_rule("docs/research/forward_watch/H1.jsonl"), "prefix")
        self.assertIsNone(tool._history_rule("docs/research/forward_watch/README.md"))

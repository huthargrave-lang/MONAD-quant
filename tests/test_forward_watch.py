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


class SnapshotStore(unittest.TestCase):
    """A watch snapshot lives in the shared store like every data set a trial cites: the
    manifest beside the others, the vendor observations only in the private store."""

    def test_manifest_committed_observations_private(self):
        from tests.test_daily_data import DATES, asset
        cols = ["SPY", "GDX", "GLD", "SIL", "SLV"]
        panel = {c: asset(k + 1) for k, c in enumerate(cols)}
        cash = pd.Series(2.0, index=DATES)
        fetch = dict(fetch_asset=lambda s, a, b: panel[s], fetch_cash=lambda a, b: cash,
                     fetch_check=lambda a, b: cash + 0.01)
        spec = spec_for([("GDX", "GLD"), ("SIL", "SLV")], [0.5, 0.5], DATES[0])
        with tempfile.TemporaryDirectory() as pub, tempfile.TemporaryDirectory() as priv:
            sha = fw.build_snapshot(spec, str(DATES[-1].date()), data_dir=Path(pub),
                                    private_dir=Path(priv), **fetch)
            self.assertTrue((Path(pub) / f"DS-{sha}.json").exists())
            self.assertFalse((Path(pub) / f"DS-{sha}.csv.gz").exists())
            self.assertTrue((Path(priv) / f"DS-{sha}.csv.gz").exists())
            snap = fw.load_snapshot(sha, data_dir=Path(pub), private_dir=Path(priv))
            self.assertEqual(snap.manifest["observations"]["csv_sha256"], sha)
            self.assertEqual(set(snap.assets), set(cols))


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
    SPEC = {"evaluation": {**EVAL, "first_decisive_anniversary": 1}, "stress_multiple": 2.0}

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

    def rows_for(self, means, opened_at=100, days=None, seed=1):
        idx = pd.bdate_range("2027-01-01", periods=days or len(means))
        rows = [(b"", {"kind": "genesis"}), (b"", {"kind": "window_open", "opens_at_session": str(idx[opened_at].date())})]
        rng = np.random.default_rng(seed)
        for d, m in zip(idx, means):
            a = float(rng.normal(m, 0.004))
            rows.append((b"", {"kind": "session", "session": str(d.date()),
                               "active": {"1x": {"active": a}, "2x": {"active": a - 1e-5}}}))
        return rows, idx

    def test_the_first_decisive_anniversary_follows_the_frozen_wording(self):
        h0 = {"evaluation": {**EVAL, "checks": "on anniversaries of the window's opening only; the first (365 "
                                               "days) decides nothing by itself"}}
        h1 = {"evaluation": {**EVAL, "checks": "on anniversaries of the window's opening only; readings in "
                                               "years 1-3 change nothing"}}
        self.assertEqual((fw.first_decisive_anniversary(h0), fw.first_decisive_anniversary(h1)), (2, 4))
        with self.assertRaises(fw.WatchError):
            fw.first_decisive_anniversary({"evaluation": EVAL})

    def test_readings_before_the_first_decisive_anniversary_never_close(self):
        rows, _ = self.rows_for([-0.004] * 1400)            # a terrible record
        spec = {"evaluation": {**EVAL, "first_decisive_anniversary": 4}, "stress_multiple": 2.0}
        reps = fw.decide(spec, rows)
        self.assertTrue(all(r["verdict"] == "continue" for r in reps if r["anniversary"] < 4))
        self.assertFalse(any(r["decisive"] for r in reps if r["anniversary"] < 4))

    def test_the_own_promote_is_not_terminal_and_the_close_is(self):
        rows, _ = self.rows_for([0.002] * 2200)             # a strong record: promotes early
        reps = fw.decide(self.SPEC, rows)
        promoted = [r["anniversary"] for r in reps if r["verdict"] == "promote"]
        self.assertTrue(promoted)
        self.assertGreater(reps[-1]["anniversary"], promoted[0])   # reports continue after it
        rows, _ = self.rows_for([-0.003] * 2200)
        reps = fw.decide(self.SPEC, rows)
        self.assertEqual(reps[-1]["verdict"], "close")
        self.assertEqual(sum(r["verdict"] == "close" for r in reps), 1)

    def test_an_anniversary_is_computed_once_settled_and_a_late_correction_cannot_rewrite_it(self):
        rows, idx = self.rows_for([0.0004] * 600)
        cut = pd.Timestamp(idx[100]) + pd.DateOffset(years=1)
        settled = [r for r in fw.decide(self.SPEC, rows)]
        self.assertEqual(len(settled), 1)
        late = rows + [(b"", {"kind": "correction", "session": str(idx[150].date()),
                              "delta": {"1x": 0.5, "2x": 0.5}})]
        self.assertEqual(fw.decide(self.SPEC, late)[0]["sharpe"], settled[0]["sharpe"])
        n_before = sum(1 for _b, r in rows if r["kind"] == "session" and pd.Timestamp(r["session"]) <= cut)
        early = rows[: 2 + n_before + fw.ANNIVERSARY_SETTLE - 1]
        self.assertEqual(fw.decide(self.SPEC, early), [])                 # not settled yet

    def test_conditions_turn_a_promote_into_continue_or_close(self):
        rows, _ = self.rows_for([0.002] * 900)
        cont = fw.decide(self.SPEC, rows, conditions=lambda cut: {"continue": ["episodes 12 < 20"], "close": None})
        self.assertNotIn("promote", [r["verdict"] for r in cont])
        closed = fw.decide(self.SPEC, rows, conditions=lambda cut: {"continue": [], "close": "long leg <= 0"})
        self.assertEqual(closed[-1]["verdict"], "close")

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
        out = fw.decide(self.SPEC, void)
        self.assertEqual(out[-1]["verdict"], "VOID")
        self.assertEqual(out[:-1], reps)          # a VOID does not erase the anniversaries before it
        self.assertEqual(fw.decide(self.SPEC, rows[:1] + [(b"", {"kind": "void", "reason": "x"})])[-1]["verdict"],
                         "VOID")


if __name__ == "__main__":
    unittest.main()


class CommittedRecords(unittest.TestCase):
    """The committed logs and the route policy, as they are in the repository."""

    def test_every_committed_line_reserialises_byte_identically(self):
        from src.research.trials import canonical_json
        for path in sorted(fw.WATCH_DIR.glob("*.jsonl")):
            for i, raw in enumerate(path.read_bytes().splitlines(), 1):
                if not raw:
                    continue
                row = json.loads(raw)
                with self.subTest(log=path.name, line=i):
                    self.assertEqual(canonical_json(row).encode("utf-8"), raw)
                    for name, book in (row.get("books") or {}).items():
                        self.assertEqual(fw.Book.from_json(book).to_json(), book)

    def test_the_route_policy_is_frozen_and_counts_every_watch(self):
        import forward_watch as tool
        policy = json.loads(fw.POLICY.read_text(encoding="utf-8"))
        self.assertIn("ever frozen", policy["m"])
        self.assertEqual(tool._history_rule(fw.POLICY.relative_to(REPO).as_posix()), "identical")
        ids = fw.watches_ever_frozen()
        self.assertIn("H366200", ids)
        self.assertNotIn("route", ids)
        spec = {"evaluation": EVAL}
        self.assertAlmostEqual(fw.route_boundary(spec, 1), math.log(0.8 / 0.05))
        self.assertAlmostEqual(fw.route_boundary(spec, 3), math.log(3 * 0.8 / 0.05))


class WindowOpening(unittest.TestCase):
    def test_the_window_opens_at_the_first_session_after_the_spec_reached_the_branch(self):
        import forward_watch as tool
        snap = market(n=30)
        with mock.patch.object(tool, "spec_reached", return_value=pd.Timestamp(snap.dates[10]) + pd.Timedelta(hours=20)):
            self.assertEqual(tool.opens_at("HTEST", snap, "origin/development"), str(snap.dates[11].date()))
        with mock.patch.object(tool, "spec_reached", return_value=None):
            self.assertIsNone(tool.opens_at("HTEST", snap, "origin/development"))

    def test_a_spec_reaches_the_branch_when_it_is_merged_not_when_it_was_committed(self):
        import os
        import subprocess
        import forward_watch as tool
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)

            def git(*args, date="2026-01-01T00:00:00Z"):
                env = {**os.environ, "GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date,
                       "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                       "GIT_COMMITTER_EMAIL": "t@t"}
                subprocess.run(["git", *args], cwd=repo, env=env, check=True, capture_output=True)
            git("init", "-q", "-b", "dev")
            (repo / "a.txt").write_text("a")
            git("add", "a.txt")
            git("commit", "-q", "-m", "base")
            git("checkout", "-q", "-b", "feature")
            (repo / "w").mkdir()
            (repo / "w" / "H1.json").write_text("{}")
            git("add", "w/H1.json")
            git("commit", "-q", "-m", "freeze", date="2026-02-01T00:00:00Z")
            git("checkout", "-q", "dev")
            self.assertIsNone(tool.reached("w/H1.json", "dev", repo=repo))
            git("merge", "-q", "--no-ff", "-m", "merge", "feature", date="2026-03-15T12:00:00Z")
            self.assertEqual(tool.reached("w/H1.json", "dev", repo=repo), pd.Timestamp("2026-03-15 12:00:00"))
            git("checkout", "-q", "-b", "ff", "dev")
            (repo / "w" / "H2.json").write_text("{}")
            git("add", "w/H2.json")
            git("commit", "-q", "-m", "direct", date="2026-04-01T00:00:00Z")
            self.assertEqual(tool.reached("w/H2.json", "ff", repo=repo), pd.Timestamp("2026-04-01"))

    def test_history_rules_freeze_specs_and_let_logs_only_grow(self):
        import forward_watch as tool
        self.assertEqual(tool._history_rule("docs/research/forward_watch/H1.json"), "identical")
        self.assertEqual(tool._history_rule("docs/research/forward_watch/H1.jsonl"), "prefix")
        self.assertIsNone(tool._history_rule("docs/research/forward_watch/README.md"))


# ── the domain-rule watch (H366201, docs/research/METAL_TRUST_FORWARD_WATCH.md) ──────
MT_SNAPSHOT = "6edd69e3d7d513eb79d542637e7f2b00776ea9e10b303cdb05c118e2236923c1"
MT_PANEL = "fd7099e252ccd34aec6829b5617dface66318c8a3756808d95c4a21d6b19b35f"
#: The ledger's returns shas of the recorded F366202 books (trials 9488e29b, 5c567742,
#: 6adb2bed, eb8af984); the Ledgered tests run on a scratch ledger, so they are pinned here
#: and checked against the real ledger by test_the_pinned_shas_are_the_ledgers.
MT_RECORDED = {"tilt:1x": "0753d45abbdc9bb443eda598fdd23795af33d75153d4db5733773b5dd234d089",
               "bench:1x": "87f6fb605bd0ff862ec48bb434def08f77cd026ec6be178b09f18f29824cecf6",
               "tilt:2x": "b3a8a80ac0689d11e5c5b648919011e61327407f2bbc163230736b936bf20c54",
               "bench:2x": "4206e9fa5eb3f24f2f8388fa5fccd3b118dc23a8eec5cfd4be48e05f0624c6ed"}
MT_TRIALS = {"tilt:1x": "TR-20261008T185930Z-9488e29b#0", "bench:1x": "TR-20261008T185928Z-5c567742#0",
             "tilt:2x": "TR-20261008T185937Z-6adb2bed#0", "bench:2x": "TR-20261008T185936Z-eb8af984#0"}


def mt_data():
    """The frozen F366202 data, or skip with the reason (option A: private observations)."""
    from src.research import cef_data
    try:
        return daily_data.load_snapshot(MT_SNAPSHOT), cef_data.load_panel(MT_PANEL)
    except Exception as exc:  # noqa: BLE001
        raise unittest.SkipTest(f"the frozen F366202 data are not on this machine ({exc})")


def mt_spec(snap, **over):
    from src.research import metal_trust_classes as mt
    spec = {
        "watch": "HMT", "claim": "test", "status": "forward watch; not an admission candidate",
        "domain_rule": {"domain": "metal_trust_discount", "point": mt.grid()[0], "reference": mt.REFERENCE,
                        "assets": ["GLD", "PHYS", "PSLV", "SLV"], "trusts": ["PHYS", "PSLV"]},
        "stress_multiple": 2.0, "anchor_session": "2009-01-02", "snapshot_start": "2009-01-01",
        "snapshot_universe": list(snap.assets), "replay_from": "2011-10-24", "genesis_session": "2026-10-02",
        "genesis_data": {"snapshot": MT_SNAPSHOT, "nav_panel": MT_PANEL},
        "recorded": dict(MT_RECORDED),
        "session_dates_sha256": fw.session_dates_sha256(snap, "2026-10-02"),
        "identity": {}, "nav_source": "test", "evaluation": EVAL,
        "evaluator_sources": ["src/research/daily_strategy.py", "src/research/forward_watch.py",
                              "src/research/metal_trust_classes.py"],
        "evaluator_sha256": "", "void_conditions": ["x"], "window_opens": "test"}
    spec.update(over)
    spec["session_dates_sha256"] = fw.session_dates_sha256(snap, spec["genesis_session"])
    spec["evaluator_sha256"] = fw.spec_evaluator_sha256(spec)
    return spec


class GenesisReproduction(unittest.TestCase):
    def test_the_genesis_reproduces_the_four_recorded_books(self):
        """Within 1e-12 of the ledger's recorded series (the real H366201 genesis also
        matched every returns sha bit for bit on the recording environment; another
        numpy build can differ in the last bits, so the cross-environment test compares
        values)."""
        snap, panel = mt_data()
        spec = mt_spec(snap, watch="HTEST")
        recs = [r for r in trials.iter_trials() if r.key in MT_TRIALS.values()]
        loaded = trials.load_returns(recs)
        with uncounted("unit test: the genesis replay of the recorded F366202 books"):
            books, series, _state = fw.genesis_books_domain(spec, snap, panel, pd.Timestamp("2026-10-02"))
        for name, key in MT_TRIALS.items():
            rec = loaded[key]
            got = series[name]
            self.assertEqual(len(got), len(rec), name)
            np.testing.assert_allclose(got.to_numpy(), np.asarray(rec, dtype=float), atol=1e-12, err_msg=name)
        self.assertTrue(all(b.leg == "close" for b in books.values()))


class DomainWatch(Ledgered):
    def test_a_genesis_that_does_not_reproduce_its_recorded_books_is_refused(self):
        snap, panel = mt_data()
        self.freeze(mt_spec(snap, watch="HTEST", recorded={n: "0" * 64 for n in MT_RECORDED}))
        with self.run_() as run, self.assertRaises(fw.WatchError):
            fw.write_genesis_domain("HTEST", snap, panel, run=run, watch_dir=self.dir / "w")
        self.assertEqual(fw.read("HTEST", self.dir / "w"), [])

    def test_the_daily_chained_record_equals_one_evaluation(self):
        """Genesis inside the frozen window, then every later session logged one by one on
        the same data and vintage: the logged active equals one full evaluation."""
        import dataclasses
        from src.research.daily_domains import DOMAINS, Context
        snap, panel = mt_data()
        early = dataclasses.replace(panel, manifest={**panel.manifest, "fetched_at": "2011-01-01T00:00:00Z"})
        genesis = "2026-03-31"
        dom = DOMAINS["metal_trust_discount"]
        ctx = Context(snap=snap, panel=panel)
        spec = mt_spec(snap, watch="HTEST", genesis_session=genesis)
        full = {}
        with uncounted("unit test: the full-window evaluation the watch must reproduce"):
            for name, _p, kind, mult in fw.book_names(spec):
                r = evaluate_daily(dom.decide(ctx, fw.rule_point(spec, kind)), snap,
                                   start=pd.Timestamp("2011-10-24"), cost_multiple=mult, tiers=dom.tiers(ctx))
                full[name] = r.returns
        spec["recorded"] = {n: fw.returns_sha256(r.loc[:genesis]) for n, r in full.items()}
        self.freeze(spec)
        with self.run_() as run:
            fw.write_genesis_domain("HTEST", snap, early, run=run, watch_dir=self.dir / "w")
            fw.log_sessions_domain("HTEST", snap, lambda sha: early, run=run, watch_dir=self.dir / "w")
        rows = [r for _b, r in fw.read("HTEST", self.dir / "w")]
        sess = [r for r in rows if r["kind"] == "session"]
        logged = pd.Series({pd.Timestamp(r["session"]): r["active"]["1x"]["active"] for r in sess})
        expected = (full["tilt:1x"] - full["bench:1x"]).loc[logged.index]
        np.testing.assert_allclose(logged.to_numpy(), expected.to_numpy(), atol=1e-12)
        stressed = pd.Series({pd.Timestamp(r["session"]): r["active"]["2x"]["active"] for r in sess})
        np.testing.assert_allclose(stressed.to_numpy(), (full["tilt:2x"] - full["bench:2x"]).loc[logged.index],
                                   atol=1e-12)
        self.assertEqual(sess[-1]["session"], "2026-10-02")
        self.assertEqual(fw.verify("HTEST", self.dir / "w"), [])

    def test_a_two_fund_panel_decides_exactly_as_the_full_panel(self):
        from src.research import cef_data
        from src.research import metal_trust_classes as mt
        snap, panel = mt_data()
        frames = {"price": panel.price[["PHYS", "PSLV"]], "nav": panel.nav[["PHYS", "PSLV"]]}
        with tempfile.TemporaryDirectory() as td:
            kw = {"data_dir": Path(td)}
            try:
                sha = cef_data.write_panel(frames, {"category": {}}, private_dir=Path(td), **kw)
                two = cef_data.load_panel(sha, private_dir=Path(td), **kw)
            except TypeError:                                   # a branch without the private store
                sha = cef_data.write_panel(frames, {"category": {}}, **kw)
                two = cef_data.load_panel(sha, **kw)
        point = mt.grid()[0]
        pd.testing.assert_frame_equal(mt.weights(snap, two, point), mt.weights(snap, panel, point))
        self.assertEqual(mt.scoring_start(snap, two), mt.scoring_start(snap, panel))
        until = pd.Timestamp("2026-10-02")
        self.assertEqual(mt.carried_genesis(two, point, until), mt.carried_genesis(panel, point, until))


class DomainPieces(unittest.TestCase):
    def test_the_pinned_shas_are_the_ledgers(self):
        recs = {r.key: r for r in trials.iter_trials() if r.key in MT_TRIALS.values()}
        self.assertEqual({n: recs[k].returns_sha for n, k in MT_TRIALS.items()}, MT_RECORDED)

    def test_a_close_leg_book_round_trips_and_an_open_one_keeps_the_legacy_form(self):
        from src.research.daily_strategy import BookState
        st = BookState(session="2026-10-02", tranches=({"holdings": {"A": 0.5}, "cash": 0.5},))
        close = fw.Book(state=st, pending={3: {"A": 0.25}}, leg="close")
        self.assertEqual(close.to_json()["leg"], "close")
        self.assertEqual(fw.Book.from_json(close.to_json()), close)
        opened = fw.Book(state=st, pending={3: {"A": 0.25}})
        self.assertNotIn("leg", opened.to_json())
        self.assertEqual(fw.Book.from_json(opened.to_json()).leg, "open")

    def test_a_session_reads_only_a_vintage_fetched_before_it_executed(self):
        rows = [(b"", {"kind": "genesis", "vintage": {"nav_panel": "v0", "fetched_at": "2026-10-06T01:00:00Z"}}),
                (b"", {"kind": "vintage", "nav_panel": "v1", "fetched_at": "2026-10-09T21:30:00Z"}),
                (b"", {"kind": "vintage", "nav_panel": "v2", "fetched_at": "2026-10-12T22:00:00Z"})]
        self.assertEqual(fw.vintage_for(rows, pd.Timestamp("2026-10-07"))[1], "v0")
        self.assertEqual(fw.vintage_for(rows, pd.Timestamp("2026-10-09"))[1], "v0")   # fetched after that close
        self.assertEqual(fw.vintage_for(rows, pd.Timestamp("2026-10-12"))[1], "v1")
        self.assertEqual(fw.vintage_for(rows, pd.Timestamp("2026-10-20"))[1], "v2")
        with self.assertRaises(fw.WatchError):
            fw.vintage_for(rows, pd.Timestamp("2026-10-05"))

    def test_a_revised_already_stepped_observation_is_reported_not_stepped(self):
        from src.research.cef_data import NavPanel
        idx = pd.to_datetime(["2026-09-11", "2026-09-18", "2026-09-25"])
        old = NavPanel(sha="o", price=pd.DataFrame({"PHYS": [10.0, 10.1, 10.2]}, index=idx),
                       nav=pd.DataFrame({"PHYS": [10.5, 10.6, 10.7]}, index=idx), category={}, manifest={})
        new_nav = old.nav.copy()
        new_nav.loc["2026-09-18", "PHYS"] = 10.65
        new = NavPanel(sha="n", price=old.price, nav=new_nav, category={}, manifest={})
        spec = {"domain_rule": {"trusts": ["PHYS"]}}
        state = {"PHYS": {"state": 0.5, "obs": "2026-09-18", "z": 0.0}}
        out = fw.nav_revisions(spec, old, new, state)
        self.assertEqual([(r["trust"], r["date"]) for r in out], [("PHYS", "2026-09-18")])
        new_nav2 = old.nav.copy()
        new_nav2.loc["2026-09-25", "PHYS"] = 9.0                  # not yet stepped: no revision
        self.assertEqual(fw.nav_revisions(spec, old, NavPanel(sha="m", price=old.price, nav=new_nav2,
                                                              category={}, manifest={}), state), [])

    def test_a_domain_spec_must_name_its_rule_and_every_recorded_book(self):
        errs = fw.validate({"domain_rule": {}})
        self.assertTrue(any("missing" in e for e in errs))
        snap_like = type("S", (), {"assets": ("SPY",)})()
        from src.research import metal_trust_classes as mt
        spec = {k: "x" for k in fw.REQUIRED_DOMAIN}
        spec.update({"domain_rule": {"domain": "metal_trust_discount", "point": mt.grid()[0],
                                     "reference": mt.REFERENCE, "assets": [], "trusts": []},
                     "stress_multiple": 2.0, "evaluation": EVAL, "status": "not an admission candidate",
                     "recorded": {"tilt:1x": "a"}})
        self.assertIn("recorded must give a returns sha for every book", fw.validate(spec))
        self.assertIsNotNone(snap_like)


class DomainReport(unittest.TestCase):
    def rows(self, states, opened):
        """A genesis, a window opening, and session lines with the given carried states."""
        d = pd.bdate_range("2027-01-04", periods=len(states))
        rows = [(b"", {"kind": "genesis", "session": "2027-01-01",
                       "rule_state": {"PHYS": {"state": states[0]}, "PSLV": {"state": 0.5}}})]
        rows.append((b"", {"kind": "window_open", "opens_at_session": str(d[opened].date())}))
        for i, s in enumerate(states):
            rows.append((b"", {"kind": "session", "session": str(d[i].date()),
                               "rule_state": {"PHYS": {"state": s}, "PSLV": {"state": 0.5}},
                               "read_states": {"PHYS": s, "PSLV": 0.5},
                               "active": {"1x": {"active": 0.001 * (1 if s == 1.0 else -1)}}}))
        return rows, d

    def test_episodes_count_departures_inside_the_window_and_not_the_carried_in_state(self):
        from src.research import metal_trust_classes as mt
        states = [1.0, 1.0, 0.5, 0.5, 1.0, 1.0, 0.5, 0.0, 0.0, 0.5]
        rows, d = self.rows(states, opened=0)
        close = pd.DataFrame({a: 10 * np.exp(np.cumsum(np.full(len(d), 0.001 if a == "PHYS" else 0.0)))
                              for a in ("SPY", "PHYS", "GLD", "PSLV", "SLV")}, index=d)
        snap = Snapshot(sha="s" * 64, dates=d, assets=tuple(close.columns), open=close, close=close,
                        dist=close * 0.0, dtb3=pd.Series(1.0, index=d), manifest={})
        spec = {"domain_rule": {"point": mt.grid()[0]}}
        out = fw.legs_and_episodes(spec, rows, snap)
        self.assertEqual(out["episodes"], 2)                 # 0.5 -> 1.0 and 0.5 -> 0.0; the start is carried in
        self.assertGreater(out["long_leg"], 0.0)            # PHYS out-earns GLD while held above neutral

    def test_atm_windows_and_the_issuance_split(self):
        filings = [{"form": "F-10", "filed": "2027-01-04"}, {"form": "SUPPL", "filed": "2027-01-06"},
                   {"form": "424B5", "filed": "2026-01-01"}]
        self.assertEqual(fw.atm_windows(filings), [("2027-01-06", "2029-02-04")])
        rows, d = self.rows([1.0] * 10, opened=0)
        split = fw.issuance_split(rows, fw.atm_windows(filings))
        self.assertAlmostEqual(split["inside_share"], 0.8)
        self.assertFalse(split["degenerate"])
        self.assertTrue(fw.issuance_split(rows, [])["degenerate"])


class DomainConditions(unittest.TestCase):
    def test_the_episode_threshold_follows_the_frozen_wording(self):
        spec = {"evaluation": {"corroboration": ["the promote boundary is crossed",
                                                 "at least 20 forward episodes (departures from neutral)"]}}
        self.assertEqual(fw.episode_threshold(spec), 20)
        self.assertEqual(fw.episode_threshold({"evaluation": {"min_episodes": 7}}), 7)
        with self.assertRaises(fw.WatchError):
            fw.episode_threshold({"evaluation": {"corroboration": []}})


class FrozenSpecsReadAsWritten(unittest.TestCase):
    def test_h366200_first_decides_at_its_second_anniversary(self):
        spec, _h = fw.load("H366200")
        self.assertEqual(fw.first_decisive_anniversary(spec), 2)


class H366201ReadsAsWritten(unittest.TestCase):
    def test_h366201_first_decides_at_its_fourth_anniversary_and_needs_20_episodes(self):
        spec, _h = fw.load("H366201")
        self.assertEqual(fw.first_decisive_anniversary(spec), 4)
        self.assertEqual(fw.episode_threshold(spec), 20)

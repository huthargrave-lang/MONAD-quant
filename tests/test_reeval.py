"""
Tests for the pre-gate re-evaluation of existing Findings (src/research/reeval.py,
tools/reevaluate_web.py).

Pinned: the tiers route each node correctly, market claims lead the queue, a decision
removes a node from it, and a positive edge claim cannot be waved through: it must be
admitted (citing a verdict), reproduced (citing a ledger run), narrowed, or labelled
unadmitted_historical.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.research import reeval  # noqa: E402

NODES = {
    "F1": {"title": "Sharpe 3 on TQQQ", "body": "An edge of +2%/mo.", "status": "current"},
    "F2": {"title": "Old claim", "body": "Sharpe 9", "status": "superseded"},
    "F3": {"title": "Parser handles minus signs", "body": "see [[E4]]", "status": "current",
           "has_evidenced_by": True},
    "F4": {"title": "A bare assertion", "body": "no citation at all", "status": "current"},
    "F5": {"title": "Guarded code claim", "body": "the gate fails closed", "status": "current"},
    "F6": {"title": "Another drawdown claim", "body": "max drawdown -1%", "status": "current"},
    "H1": {"title": "not a finding", "body": "Sharpe", "status": "current"},
}


class Tiers(unittest.TestCase):
    def test_each_tier(self):
        t = reeval.classify(NODES, decided={}, guarded={"F5"})
        self.assertEqual(t, {"F1": "market", "F2": "settled", "F3": "traceable",
                             "F4": "unverified", "F5": "guarded", "F6": "market"})

    def test_queue_puts_market_claims_first_and_skips_the_rest(self):
        t = reeval.classify(NODES, decided={}, guarded={"F5"})
        self.assertEqual(reeval.queue(t), ["F1", "F6", "F4"])

    def test_a_decision_takes_a_node_off_the_queue(self):
        t = reeval.classify(NODES, decided={"F1": {}}, guarded=set())
        self.assertEqual(t["F1"], "decided")
        self.assertNotIn("F1", reeval.queue(t))

    def test_guard_detection_reads_test_names(self):
        with tempfile.TemporaryDirectory() as td:
            for name in ("test_f260_recompute_audit.py", "test_h24_h25_stop.py",
                         "test_f19_exit_lever_bridge.py", "test_f12_f13_fetch.py", "test_misc.py"):
                (Path(td) / name).write_text("class T:\n    def test_it(self):\n        assert True\n")
            self.assertEqual(reeval.guarded_ids(Path(td)), {"F260", "F19", "F12", "F13"})

    def test_an_empty_guard_file_guards_nothing(self):
        """Red-team attack 9/9d: an empty file, or a test asserting nothing, used to move a
        finding out of the queue."""
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "test_f24_placeholder.py").write_text("# TODO\n")
            (Path(td) / "test_f1_trivial.py").write_text("def test_f1():\n    pass\n")
            self.assertEqual(reeval.guarded_ids(Path(td)), set())

    def test_cli_refuses_a_citation_that_does_not_verify(self):
        sys.path.insert(0, str(REPO / "tools"))
        import reevaluate_web
        problems = reevaluate_web.citation_problems(
            {"node": "F1", "action": "admitted", "evidence": "docs/research/verdicts/H1/none.json"})
        self.assertTrue(problems)


class Decisions(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def decide(self, node="F1", **kw):
        args = dict(classification="positive_edge", action="unadmitted_historical",
                    evidence="predates the gate; no ledger run exists", by="agent-1")
        args.update(kw)
        return reeval.decide(node, directory=self.dir, nodes=NODES, **args)

    def test_positive_edge_cannot_be_closed_with_no_action(self):
        with self.assertRaises(reeval.ReevalError):
            self.decide(action="no_action")

    def test_admitted_must_cite_a_real_admit_and_reproduced_a_real_run(self):
        """Red-team attack 9: citations used to be checked for shape, not existence."""
        from unittest import mock
        from src.research import trials
        root = Path(self._tmp.name) / "repo"
        verdicts = root / "docs/research/verdicts/H9"
        verdicts.mkdir(parents=True)
        (verdicts / "a.json").write_text('{"verdict": "ADMIT"}')
        (verdicts / "r.json").write_text('{"verdict": "REJECT"}')
        ledger = root / "trials"
        ledger.mkdir()
        (ledger / "TR-20260922T170000Z-ab12cd34.jsonl").write_text("")
        with mock.patch.object(reeval, "REPO", root), mock.patch.object(trials, "LEDGER_DIR", ledger):
            with self.assertRaises(reeval.ReevalError):
                self.decide(action="admitted", evidence="trust me, it was admitted")
            with self.assertRaises(reeval.ReevalError):
                self.decide(action="admitted", evidence="docs/research/verdicts/H9/missing.json")
            with self.assertRaises(reeval.ReevalError):
                self.decide(action="admitted", evidence="docs/research/verdicts/H9/r.json")
            self.decide(action="admitted", evidence="docs/research/verdicts/H9/a.json")
            with self.assertRaises(reeval.ReevalError):
                self.decide(node="F6", action="reproduced", evidence="TR-20990101T000000Z-deadbeef")
            self.decide(node="F6", action="reproduced",
                        evidence="reproduced in TR-20260922T170000Z-ab12cd34")

    def test_only_findings_in_the_web(self):
        with self.assertRaises(reeval.ReevalError):
            self.decide(node="H1")
        with self.assertRaises(reeval.ReevalError):
            self.decide(node="F999")

    def test_latest_decision_wins_and_log_only_grows(self):
        self.decide(classification="negative_or_method", action="no_action",
                    evidence="denies an edge; see E23 reasoning")
        self.decide()
        self.assertEqual(reeval.decisions(self.dir)["F1"]["classification"], "positive_edge")
        self.assertEqual(len((self.dir / reeval.DECISIONS).read_text().splitlines()), 2)

    def test_history_is_append_only(self):
        repo = Path(self._tmp.name) / "repo"
        repo.mkdir()
        git = lambda *a: subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True)
        git("init", "-q", "-b", "base")
        git("config", "user.email", "t@e.com")
        git("config", "user.name", "t")
        d = repo / reeval.REEVAL_REL
        reeval.decide("F1", classification="positive_edge", action="unadmitted_historical",
                      evidence="predates the gate entirely", by="a", directory=d, nodes=NODES)
        git("add", "-A")
        git("commit", "-q", "-m", "d")
        git("checkout", "-q", "-b", "work")
        self.assertEqual(reeval.verify_history("base", repo=repo), [])
        (d / reeval.DECISIONS).write_text("")
        self.assertTrue(reeval.verify_history("base", repo=repo))


class TheRealWeb(unittest.TestCase):
    def test_every_current_finding_gets_exactly_one_tier(self):
        t = reeval.classify()
        self.assertTrue(t)
        self.assertTrue(set(t.values()) <= set(reeval.TIERS))
        self.assertTrue(all(k.startswith("F") for k in t))


if __name__ == "__main__":
    unittest.main()

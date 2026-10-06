"""
Tests for the refutation log (src/research/refutations.py, tools/refute.py).

An objection must be checkable, must stay on record, and can be answered exactly once,
either refuted (with evidence) or upheld. The admission gate reads ``status``: open
objections block, upheld ones reject (see tests/test_admit.py).
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from src.research import refutations as R  # noqa: E402
import refute  # noqa: E402  (tools/refute.py)


class Log(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def obj(self, claim="fills at the signal bar close", by="refuter-1"):
        return R.object_to("H5", claim=claim, evidence="src/strategy/engine.py:390",
                           by=by, directory=self.dir)

    def test_objection_is_open_until_answered(self):
        o = self.obj()
        self.assertEqual([e["id"] for e in R.status("H5", self.dir)["open"]], [o["id"]])
        R.resolve("H5", o["id"], outcome="refuted", evidence="tests/test_fill_model.py pins next-bar fill",
                  by="author", directory=self.dir)
        st = R.status("H5", self.dir)
        self.assertEqual((len(st["open"]), len(st["refuted"])), (0, 1))

    def test_answered_once_only(self):
        o = self.obj()
        R.resolve("H5", o["id"], outcome="upheld", evidence="replay shows the look-ahead",
                  by="refuter-2", directory=self.dir)
        with self.assertRaises(R.RefutationError):
            R.resolve("H5", o["id"], outcome="refuted", evidence="changed my mind entirely",
                      by="author", directory=self.dir)

    def test_the_objector_cannot_answer_their_own_objection(self):
        o = self.obj(by="Refuter-1")
        with self.assertRaises(R.RefutationError):
            R.resolve("H5", o["id"], outcome="refuted", evidence="it is fine, trust the code",
                      by=" refuter-1 ", directory=self.dir)

    def test_ids_are_sequential_and_rows_accumulate(self):
        a, b = self.obj(), self.obj(claim="cost model ignores the spread")
        self.assertEqual((a["id"], b["id"]), ("O1", "O2"))
        self.assertEqual(len(R.entries("H5", self.dir)), 2)

    def test_uncheckable_input_is_refused(self):
        with self.assertRaises(R.RefutationError):
            R.object_to("H5", claim="bad", evidence="src/x.py:1", by="r", directory=self.dir)
        with self.assertRaises(R.RefutationError):
            R.object_to("H5", claim="a real specific claim", evidence="trust me", by="r",
                        directory=self.dir)
        with self.assertRaises(R.RefutationError):
            R.object_to("H5", claim="a real specific claim", evidence="src/x.py:1", by=" ",
                        directory=self.dir)
        with self.assertRaises(R.RefutationError):
            R.resolve("H5", "O99", outcome="refuted", evidence="nothing to resolve here",
                      by="a", directory=self.dir)
        with self.assertRaises(R.RefutationError):
            R.object_to("F5", claim="a real specific claim", evidence="src/x.py:1", by="r",
                        directory=self.dir)

    def test_cli_round_trip(self):
        orig = R.REFUTATIONS_DIR
        R.REFUTATIONS_DIR = self.dir
        try:
            self.assertEqual(refute.main(["object", "H5", "--claim", "entry uses future VWAP",
                                          "--evidence", "src/signals/volume.py:40", "--by", "r1"]), 0)
            self.assertEqual(refute.main(["resolve", "H5", "O1", "--outcome", "refuted",
                                          "--evidence", "vwap is shift(1): volume.py:44", "--by", "a"]), 0)
            self.assertEqual(refute.main(["status", "H5"]), 0)
            self.assertEqual(refute.main(["resolve", "H5", "O1", "--outcome", "upheld",
                                          "--evidence", "second answer attempt", "--by", "a"]), 1)
        finally:
            R.REFUTATIONS_DIR = orig


class History(unittest.TestCase):
    def test_logs_only_grow(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            git = lambda *a: subprocess.run(["git", "-C", td, *a], check=True, capture_output=True)
            git("init", "-q", "-b", "base")
            git("config", "user.email", "t@e.com")
            git("config", "user.name", "t")
            d = repo / R.REFUTATIONS_REL
            o = R.object_to("H5", claim="fills at the signal bar close",
                            evidence="engine.py:390", by="r1", directory=d)
            git("add", "-A")
            git("commit", "-q", "-m", "o")
            git("checkout", "-q", "-b", "work")
            R.resolve("H5", o["id"], outcome="upheld", evidence="replay confirms it",
                      by="r2", directory=d)
            self.assertEqual(R.verify_history("base", repo=repo), [])  # appending is fine
            (d / "H5.jsonl").write_text("")
            self.assertTrue(R.verify_history("base", repo=repo))  # erasing is not


if __name__ == "__main__":
    unittest.main()

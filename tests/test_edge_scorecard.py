"""
tools/edge_scorecard.py joins ledger, registrations, refutations and verdicts. Pins that
the join is right (trials counted before registration only, the LATEST verdict wins,
objections tallied) and that it refuses to score over an invalid ledger.
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

import admit  # noqa: E402
import edge_scorecard  # noqa: E402
from src.research import prereg, refutations, trials  # noqa: E402
sys.path.insert(0, str(REPO / "tests"))
from test_admit import _spec  # noqa: E402  (one spec fixture, shared)


class Scorecard(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        d = Path(self._tmp.name)
        self._orig = (trials.LEDGER_DIR, prereg.PREREG_DIR, refutations.REFUTATIONS_DIR,
                      admit.VERDICT_DIR)
        trials.LEDGER_DIR, prereg.PREREG_DIR = d / "t", d / "p"
        refutations.REFUTATIONS_DIR, admit.VERDICT_DIR = d / "r", d / "v"

    def tearDown(self):
        (trials.LEDGER_DIR, prereg.PREREG_DIR, refutations.REFUTATIONS_DIR,
         admit.VERDICT_DIR) = self._orig
        self._tmp.cleanup()

    def _trials(self, n, at):
        with mock.patch("src.research.trials._now", return_value=at):
            with trials.open_run(producer="sweep.py", family=_spec()["family"]) as run:
                for i in range(n):
                    run.begin(params={"i": i}).complete(metrics={})

    def test_join(self):
        self._trials(5, "2021-06-01T00:00:00.000000Z")
        prereg.register(_spec(), check_web=False, now="2021-07-02T00:00:00Z")
        self._trials(3, "2021-08-01T00:00:00.000000Z")  # after registration: not its search
        refutations.object_to("H9100", claim="a checkable objection text", evidence="file.py:12",
                              by="refuter")
        for at, v, outcome in (("2021-10-01T00:00:00Z", "PENDING", "pending"),
                               ("2021-12-01T00:00:00Z", "REJECT", "fail")):
            admit.write_verdict({"hypothesis": "H9100", "evaluated_at": at, "verdict": v,
                                 "stages": [{"name": "forward", "outcome": outcome,
                                             "detail": "", "data": {}}]})
        card = edge_scorecard.scorecard()
        row = card["hypotheses"][0]
        self.assertEqual(row["trials_before_registration"], 5)
        self.assertEqual(row["verdict"], "REJECT")
        self.assertEqual(row["objections"]["open"], 1)
        self.assertEqual(card["totals"]["trials_recorded"], 8)
        self.assertIsNone(card["totals"]["trials_per_admission"])
        self.assertEqual(edge_scorecard.main([]), 0)

    def test_a_forged_admit_is_shown_as_invalid_not_counted(self):
        """Red-team attack 7b: a hand-written ADMIT file used to count as admitted."""
        prereg.register(_spec(), check_web=False, now="2021-07-02T00:00:00Z")
        admit.write_verdict({"hypothesis": "H9100", "evaluated_at": "2021-12-01T00:00:00Z",
                             "verdict": "ADMIT", "stages": [
                                 {"name": n, "outcome": "pass", "detail": "", "data": {}}
                                 for n in admit.ADMIT_CHAIN]})
        card = edge_scorecard.scorecard()
        self.assertEqual(card["hypotheses"][0]["verdict"], "INVALID RECORD")
        self.assertEqual(card["totals"]["admitted"], 0)

    def test_refuses_an_invalid_ledger(self):
        self._trials(2, "2021-06-01T00:00:00.000000Z")
        shard = next(trials.LEDGER_DIR.glob("TR-*.jsonl"))
        shard.write_text(shard.read_text().replace('"i":1', '"i":7'))
        self.assertEqual(edge_scorecard.main([]), 1)


if __name__ == "__main__":
    unittest.main()

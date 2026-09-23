"""
Tests for pre-registration (src/research/prereg.py, tools/prereg.py).

A registration is only worth anything if it cannot be loosened, overwritten or edited
after the evidence arrives, and if the trials it is judged by cannot be relabelled out
of its family. Each of those is pinned here.
"""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from src.research import prereg, trials  # noqa: E402
import prereg as prereg_cli  # noqa: E402  (tools/prereg.py)

SPEC = {
    "hypothesis": "H9001",
    "family": "long_only_rsi_vwap_mr_hourly:TQQQ",
    "claim": "Hourly RSI/VWAP dips on TQQQ mean-revert enough to beat costs after the search.",
    "profile": "price_strategy",
    "universe": ["TQQQ"],
    "development_window": {"start": "2024-01-01", "end": "2026-01-01"},
    "metric": "deflated_sharpe",
    "threshold": 0.95,
    "min_trades": 30,
    "holdout": {"kind": "forward_paper", "min_days": 90, "min_trades": 30, "min_psr": 0.8},
    "cost_model": {"round_trip_cost_pct": 0.0007},
}


def _spec(**changes):
    s = copy.deepcopy(SPEC)
    s.update(changes)
    return s


class Validation(unittest.TestCase):
    def test_the_reference_spec_is_valid(self):
        self.assertEqual(prereg.validate(SPEC), [])

    def test_no_bar_below_the_repo_floor(self):
        self.assertTrue(prereg.validate(_spec(threshold=0.9)))
        self.assertTrue(prereg.validate(_spec(min_trades=10)))
        self.assertTrue(prereg.validate(_spec(holdout={"kind": "forward_paper", "min_days": 10,
                                                       "min_trades": 5, "min_psr": 0.8})))
        self.assertTrue(prereg.validate(_spec(holdout={"kind": "forward_paper", "min_days": 90,
                                                       "min_trades": 30, "min_psr": 0.5})))

    def test_profile_decides_the_holdout(self):
        self.assertTrue(prereg.validate(_spec(holdout={"kind": "sealed_issuers", "vault": "v1"})))
        ok = prereg.validate(_spec(profile="event_study",
                                   holdout={"kind": "sealed_issuers", "vault": "v1"}))
        self.assertEqual(ok, [])
        self.assertTrue(prereg.validate(_spec(profile="event_study")))

    def test_missing_and_unknown_fields(self):
        s = _spec()
        del s["claim"]
        self.assertTrue(prereg.validate(s))
        self.assertTrue(prereg.validate(_spec(sneaky=1)))

    def test_bad_window_and_ids(self):
        self.assertTrue(prereg.validate(_spec(development_window={"start": "2026-01-01",
                                                                  "end": "2024-01-01"})))
        self.assertTrue(prereg.validate(_spec(hypothesis="F3")))
        self.assertTrue(prereg.validate(_spec(family="has space")))


class Registration(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_register_then_load_round_trips_with_a_stable_hash(self):
        path, h = prereg.register(SPEC, prereg_dir=self.dir, check_web=False,
                                  now="2026-09-22T00:00:00Z")
        record, h2 = prereg.load("H9001", prereg_dir=self.dir)
        self.assertEqual(h, h2)
        self.assertEqual(record["registered_at"], "2026-09-22T00:00:00Z")
        self.assertIn("sha", record["registered_from"])

    def test_development_evidence_must_predate_registration(self):
        with self.assertRaises(prereg.PreregError):
            prereg.register(SPEC, prereg_dir=self.dir, check_web=False, now="2025-06-01T00:00:00Z")

    def test_never_overwrites(self):
        prereg.register(SPEC, prereg_dir=self.dir, check_web=False)
        with self.assertRaises(prereg.PreregError):
            prereg.register(_spec(threshold=0.99), prereg_dir=self.dir, check_web=False)

    def test_hand_edit_is_detected(self):
        path, _ = prereg.register(SPEC, prereg_dir=self.dir, check_web=False)
        record = json.loads(path.read_text())
        record["threshold"] = 0.5
        path.write_text(json.dumps(record, indent=2))
        with self.assertRaises(prereg.PreregError):
            prereg.load("H9001", prereg_dir=self.dir)

    def test_hypothesis_must_exist_and_be_current_in_the_web(self):
        with self.assertRaises(prereg.PreregError):
            prereg.register(_spec(hypothesis="H999999"), prereg_dir=self.dir)
        with self.assertRaises(prereg.PreregError):  # H62 is superseded in the web
            prereg.register(_spec(hypothesis="H62"), prereg_dir=self.dir)
        prereg.register(_spec(hypothesis="H1"), prereg_dir=self.dir)  # current

    def test_cli_is_dry_run_by_default(self):
        spec_file = self.dir / "spec.json"
        spec_file.write_text(json.dumps(_spec(hypothesis="H1")))
        orig = prereg.PREREG_DIR
        prereg.PREREG_DIR = self.dir / "prereg"
        try:
            self.assertEqual(prereg_cli.main(["register", str(spec_file)]), 0)
            self.assertFalse((self.dir / "prereg").exists())
            self.assertEqual(prereg_cli.main(["register", str(spec_file), "--commit"]), 0)
            self.assertTrue((self.dir / "prereg" / "H1.json").exists())
            self.assertEqual(prereg_cli.main(["verify"]), 0)
        finally:
            prereg.PREREG_DIR = orig


class LedgerRespectsTheRegistration(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self._orig = prereg.PREREG_DIR
        prereg.PREREG_DIR = self.dir / "prereg"
        prereg.register(SPEC, check_web=False)

    def tearDown(self):
        prereg.PREREG_DIR = self._orig
        self._tmp.cleanup()

    def test_trials_cannot_be_relabelled_out_of_the_registered_family(self):
        with self.assertRaises(trials.LedgerError):
            trials.open_run(producer="t", family="fresh:TQQQ", hypothesis="H9001",
                            ledger_dir=self.dir / "trials")
        with trials.open_run(producer="t", family=SPEC["family"], hypothesis="H9001",
                             ledger_dir=self.dir / "trials"):
            pass


class History(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        for args in (["init", "-q", "-b", "base"], ["config", "user.email", "t@e.com"],
                     ["config", "user.name", "t"]):
            self.git(*args)
        self.path, _ = prereg.register(SPEC, prereg_dir=self.repo / prereg.PREREG_REL,
                                       check_web=False)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "reg")
        self.git("checkout", "-q", "-b", "work")

    def tearDown(self):
        self._tmp.cleanup()

    def git(self, *args):
        subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True)

    def test_untouched_passes_edit_and_delete_fail(self):
        self.assertEqual(prereg.verify_history("base", repo=self.repo), [])
        self.path.write_text(self.path.read_text().replace("0.95", "0.99"))
        self.assertTrue(prereg.verify_history("base", repo=self.repo))
        self.path.unlink()
        self.assertTrue(any("deleted" in p for p in prereg.verify_history("base", repo=self.repo)))


if __name__ == "__main__":
    unittest.main()

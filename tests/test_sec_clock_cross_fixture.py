"""Do the corpus's two independent SEC clock fixtures agree?

The repo carries two SEC event-clock artifacts built for different purposes, from
different form families, at different times:

* `fd00_sec_event_clock_fixtures_2026.json` — FD-00's **stated contract**: eight
  hand-authored expectations about how acceptance time maps to filing date and market
  phase, covering 10-K/10-Q edge cases.
* `ca_clock100b_evidence_manifest.json` — CA-CLOCK100B's **measured data**: 111 real
  filings with exact SEC acceptance seconds and their actual `filed_on`.

Neither references the other. That makes them a mutual check: a contract nobody
measured against, and a measurement nobody compared to the contract. This file does
the comparison, so a future edit to either is caught by the other.

**What the comparison found.** All seven timestamped FD-00 fixtures are consistent
with the rollover bracket measured from the CA data — `(17:30:14, 17:47:43]` (F163).
But FD-00's fixture is *named* `after_1730_filing_date_rollover`, encoding a 17:30
boundary, and the measured data contains a filing **accepted at 17:30:14 that still
received a same-day `filed_on`**. Both are true at once only because the 17:30 cutoff
bites on **submission**, while `accepted_raw` records **acceptance** — which is exactly
the distinction FD-00's own `acceptance_is_not_public_availability` policy warns about,
and which matters to anyone keying events off `accepted_raw`.

The eighth FD-00 fixture is deliberately excluded: `post_acceptance_correction_contract`
carries null timestamps because it asserts a policy, not an event. An earlier reading
of this file flagged its missing `market_phase` as a schema defect; it is not one.
"""
import datetime as dt
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs" / "research" / "data"
FD00 = DATA / "fd00_sec_event_clock_fixtures_2026.json"
CA = DATA / "ca_clock100b_evidence_manifest.json"

ROLLOVER_FLAG = "filing_date_rollover"


def _measured_bracket():
    """(latest same-day acceptance, earliest next-day acceptance) from real filings."""
    manifest = json.loads(CA.read_text(encoding="utf-8"))
    same_day, next_day = [], []
    for chain in manifest["chains"]:
        rows = [(chain["form25_accepted_at"], chain["form25_filed_on"])]
        rows += [(s["accepted_at"], s["filed_on"]) for s in chain["review_sources"]
                 if s.get("accepted_at") and s.get("filed_on")]
        for accepted, filed in rows:
            stamp = dt.datetime.fromisoformat(accepted)
            (same_day if stamp.date().isoformat() == filed else next_day).append(
                stamp.time())
    return max(same_day), min(t for t in next_day)


def _timestamped_fd00():
    fixtures = json.loads(FD00.read_text(encoding="utf-8"))["fixtures"]
    return [f for f in fixtures if f.get("accepted_raw")]


class MeasuredBracketTests(unittest.TestCase):
    def test_the_bracket_is_narrow_and_in_the_evening(self):
        latest_same, earliest_next = _measured_bracket()
        self.assertEqual(latest_same, dt.time(17, 30, 14))
        self.assertEqual(earliest_next, dt.time(17, 47, 43))

    def test_a_filing_accepted_after_1730_still_got_a_same_day_date(self):
        """The detail that makes the acceptance/submission distinction load-bearing."""
        latest_same, _ = _measured_bracket()
        self.assertGreater(
            latest_same, dt.time(17, 30, 0),
            "no same-day acceptance after 17:30 remains in the data — the "
            "acceptance-is-not-submission point loses its worked example; re-verify "
            "F163 before citing it.")


class FD00AgreesWithTheMeasuredDataTests(unittest.TestCase):
    """Bidirectional: an edit to EITHER artifact that breaks agreement fails here."""

    def setUp(self):
        self.latest_same, self.earliest_next = _measured_bracket()

    def test_every_timestamped_fixture_is_consistent_with_the_bracket(self):
        conflicts = []
        for fixture in _timestamped_fd00():
            stamp = dt.datetime.fromisoformat(fixture["accepted_raw"])
            if stamp.time() == dt.time(0, 0, 0):
                continue  # legacy midnight display is explicitly "time unresolved"
            rolls = ROLLOVER_FLAG in fixture["expected"].get("flags", [])
            if stamp.time() > self.earliest_next and not rolls:
                conflicts.append((fixture["id"], "should roll but does not"))
            if stamp.time() <= self.latest_same and rolls:
                conflicts.append((fixture["id"], "rolls but is inside same-day range"))
        self.assertEqual(
            conflicts, [],
            "FD-00's stated contract now disagrees with the rollover measured from "
            "real filings in ca_clock100b: {}. One of the two artifacts changed; "
            "reconcile them rather than editing this test.".format(conflicts))

    def test_the_fixture_set_still_covers_both_sides_of_the_boundary(self):
        """A one-sided fixture set would pass the check above vacuously."""
        times = [dt.datetime.fromisoformat(f["accepted_raw"]).time()
                 for f in _timestamped_fd00()]
        self.assertTrue(any(t > self.earliest_next for t in times),
                        "no FD-00 fixture lands after the rollover boundary")
        self.assertTrue(any(dt.time(0, 0, 1) < t <= self.latest_same for t in times),
                        "no FD-00 fixture lands before the rollover boundary")


class FixtureShapeTests(unittest.TestCase):
    def test_the_contract_only_fixture_is_recognised_as_such(self):
        """Not a schema defect: it asserts a policy, so it has no event time."""
        fixtures = json.loads(FD00.read_text(encoding="utf-8"))["fixtures"]
        contract_only = [f for f in fixtures if not f.get("accepted_raw")]
        self.assertEqual(len(contract_only), 1)
        self.assertEqual(contract_only[0]["id"], "post_acceptance_correction_contract")
        self.assertNotIn("market_phase", contract_only[0]["expected"])

    def test_fd00_still_declares_acceptance_is_not_public_availability(self):
        """The policy that reconciles the 17:30 name with the 17:30:14 measurement."""
        policy = json.loads(FD00.read_text(encoding="utf-8"))["clock_policy"]
        self.assertTrue(policy.get("acceptance_is_not_public_availability"))


if __name__ == "__main__":
    unittest.main()

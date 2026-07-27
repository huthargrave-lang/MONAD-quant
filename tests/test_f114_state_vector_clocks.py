"""F114's clock figures, recomputed — and the half of the cost it does not state.

F114 was flagged uncited: ten figures, zero reachable documents. All of them recompute
from `docs/research/data/ca01_sec_state_machine_fixture.json`, so — as with F111 — the
gap was a citation path, not missing evidence.
`docs/research/CA01_state_vector_clock_separation.md` now records it.

**The figures.** TWTR's exchange Form 25-NSE precedes the issuer completion 8-K by
**11:51:17**; ATVI's issuer completion precedes the exchange Form 25-NSE by **00:26:14**;
BBBY's suspension is confirmed **68 calendar days** after it took effect; 27 assertions
across 3 chains and 6 dimensions. Every one reproduces exactly from `observed_at`.

**The addition.** F114 says an effective-date join "leaks information". Across all 27
assertions the error runs in *both* directions: 7 assertions would appear before their
source existed (leak, up to 68 days), and **4 would be hidden despite already being
filed** (suppression, 8-11 days early) — scheduled removals and an expected cancellation
that were public one to two weeks ahead.

That second half fails differently. A leak inflates results and gets caught by ordinary
suspicion of a good number. A suppression removes information the market genuinely had,
makes a strategy look worse than it was, and produces no symptom at all. Both hit
`predictive_status` assertions, so neither is confined to retrospective bookkeeping.

The tests below assert the census in both directions, so neither half can drift out.
"""
import datetime as dt
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "docs" / "research" / "data" / "ca01_sec_state_machine_fixture.json"
DOC = ROOT / "docs" / "research" / "CA01_state_vector_clock_separation.md"
WEB = ROOT / "RESEARCH_WEB.md"

TWTR = "cash-merger:TWTR:2022-10-27"
ATVI = "cash-merger:ATVI:2023-10-13"
BBBY = "bankruptcy-cancellation:BBBYQ:2023-09-29"


def fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def chain(cid):
    return next(c for c in fixture()["chains"] if c["chain_id"] == cid)


def observed(cid, state):
    a = next(a for a in chain(cid)["assertions"] if a["state_value"] == state)
    return dt.datetime.fromisoformat(a["observed_at"])


def census():
    """(leaks, suppressions, same_day) as lists of (symbol, state, days, role)."""
    leaks, supp, same = [], [], []
    for c in fixture()["chains"]:
        for a in c["assertions"]:
            days = (dt.datetime.fromisoformat(a["observed_at"]).date()
                    - dt.date.fromisoformat(a["effective_on"])).days
            row = (c["event_symbol"], a["state_value"], days, a.get("knowledge_role"))
            (leaks if days > 0 else supp if days < 0 else same).append(row)
    return leaks, supp, same


def f114_body():
    text = WEB.read_text(encoding="utf-8")
    start = text.index("### F114 ")
    return text[start:text.index("\n### ", start + 5)]


class TheStatedFiguresRecomputeTests(unittest.TestCase):
    def test_the_twitter_gap_is_11_51_17(self):
        gap = observed(TWTR, "issuer_completion_8k_filed") - observed(TWTR, "form25_nse_filed")
        self.assertEqual(
            gap, dt.timedelta(hours=11, minutes=51, seconds=17),
            "the TWTR Form25 -> 8-K gap changed to {} — F114 states 11:51:17".format(gap))
        self.assertGreater(gap.total_seconds(), 0,
                           "the exchange filing no longer precedes the issuer's")

    def test_the_activision_gap_is_26_14_and_points_the_OTHER_way(self):
        gap = observed(ATVI, "form25_nse_filed") - observed(ATVI, "completed")
        self.assertEqual(gap, dt.timedelta(minutes=26, seconds=14),
                         "the ATVI completion -> Form25 gap changed to {}".format(gap))
        self.assertGreater(gap.total_seconds(), 0)

    def test_the_two_chains_order_their_sources_OPPOSITELY(self):
        """The reversal is the whole reason the state-vector model exists. If both
        chains ever agree, a single canonical source order becomes defensible and
        F114's central claim is stale."""
        twtr_exchange_first = (observed(TWTR, "issuer_completion_8k_filed")
                               > observed(TWTR, "form25_nse_filed"))
        atvi_exchange_first = (observed(ATVI, "completed")
                               > observed(ATVI, "form25_nse_filed"))
        self.assertTrue(twtr_exchange_first)
        self.assertFalse(atvi_exchange_first)
        self.assertNotEqual(
            twtr_exchange_first, atvi_exchange_first,
            "both cash-merger chains now file in the same order — 'source order is not "
            "universal' would no longer be demonstrated by this fixture")

    def test_the_bbby_confirmation_lag_is_68_calendar_days(self):
        a = next(x for x in chain(BBBY)["assertions"]
                 if x["state_value"] == "trading_suspended")
        lag = (dt.datetime.fromisoformat(a["observed_at"]).date()
               - dt.date.fromisoformat(a["effective_on"])).days
        self.assertEqual(lag, 68, "BBBY's suspension confirmation lag is now {}".format(lag))
        self.assertEqual(a["knowledge_role"], "post_effective_confirmation",
                         "the retrospective confirmation lost its knowledge_role, which "
                         "is what stops it being used as a forward-looking feature")

    def test_the_shape_counts(self):
        f = fixture()
        self.assertEqual(len(f["chains"]), 3)
        self.assertEqual(sum(len(c["assertions"]) for c in f["chains"]), 27)
        dims = {a["dimension"] for c in f["chains"] for a in c["assertions"]}
        self.assertEqual(dims, {"transaction", "listing", "reporting", "security_rights",
                                "bankruptcy", "disclosure"})

    def test_the_node_states_these_numbers(self):
        body = f114_body()
        for token in ("11:51:17", "26:14", "68 calendar days"):
            self.assertIn(token, body,
                          "F114 no longer states {!r} — the binding above is stale"
                          .format(token))


class AnEffectiveDateJoinFailsInBOTHDirectionsTests(unittest.TestCase):
    """The half F114 does not state."""

    @classmethod
    def setUpClass(cls):
        cls.leaks, cls.supp, cls.same = census()

    def test_the_census_partitions_all_27(self):
        self.assertEqual(len(self.leaks) + len(self.supp) + len(self.same), 27)

    def test_seven_assertions_would_LEAK(self):
        self.assertEqual(
            len(self.leaks), 7,
            "the leak count changed to {} — recount before citing the doc"
            .format(len(self.leaks)))
        self.assertEqual(max(r[2] for r in self.leaks), 68)

    def test_four_assertions_would_be_SUPPRESSED(self):
        """Filed ahead of their effective date, so an effective-date join hides a fact
        the market already had. This is the silent failure."""
        self.assertEqual(
            len(self.supp), 4,
            "the suppression count changed to {} — this is the half that fails without "
            "a symptom, so it must stay measured".format(len(self.supp)))
        self.assertLessEqual(min(r[2] for r in self.supp), -8,
                             "the earliest forward filing is no longer at least 8 days "
                             "ahead of its effective date")

    def test_both_failure_modes_hit_PREDICTIVE_assertions(self):
        """Otherwise both could be dismissed as retrospective bookkeeping."""
        for label, rows in (("leak", self.leaks), ("suppression", self.supp)):
            roles = {r[3] for r in rows}
            self.assertIn(
                "predictive_status", roles,
                "no {} now touches a predictive_status assertion, so the failure could "
                "be confined to bookkeeping — re-read the doc".format(label))

    def test_the_same_day_majority_is_why_the_bug_survives(self):
        """16 of 27 are same-day, so an effective-date join looks right most of the
        time — which is exactly how it stays in a pipeline."""
        self.assertGreater(len(self.same), len(self.leaks) + len(self.supp))


class TheDocumentRecordsItTests(unittest.TestCase):
    def test_the_doc_exists_and_cites_the_fixture(self):
        self.assertTrue(DOC.exists())
        self.assertIn("ca01_sec_state_machine_fixture.json",
                      DOC.read_text(encoding="utf-8"))

    def test_the_doc_keeps_the_limits_visible(self):
        # whitespace-normalised: a line wrap must not break a content assertion
        text = re.sub(r"\s+", " ", DOC.read_text(encoding="utf-8")).lower()
        for phrase in ("not population evidence", "deliberately unrepresentative",
                       "raw_documents_committed", "market_access_policy"):
            self.assertIn(phrase, text,
                          "the write-up dropped {!r}; three hand-picked chains must not "
                          "start reading like a survey".format(phrase))

    def test_the_doc_and_the_fixture_agree_on_the_census(self):
        """Binds the doc's table to the data, so the prose cannot drift."""
        text = DOC.read_text(encoding="utf-8")
        leaks, supp, same = census()
        self.assertTrue(re.search(r"\|\s*7\s*\|", text), "the doc's leak count is not 7")
        self.assertTrue(re.search(r"\|\s*4\s*\|", text), "the doc's suppression count is not 4")
        self.assertTrue(re.search(r"\|\s*16\s*\|", text), "the doc's same-day count is not 16")
        self.assertEqual((len(leaks), len(supp), len(same)), (7, 4, 16))


if __name__ == "__main__":
    unittest.main()

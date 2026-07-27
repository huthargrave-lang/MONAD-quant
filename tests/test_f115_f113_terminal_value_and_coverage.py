"""F115 and F113: the zero-value rule, the coverage audit, and a validator walk-around.

Both nodes were flagged uncited. As with F111 and F114 the evidence was committed — every
figure re-derives from `ca00_corporate_action_fixture.json` and
`ca00_free_provider_coverage.json`. `docs/research/CA00_terminal_value_and_coverage.md`
records it. Checking F115 turned up a real inconsistency, fixed here.

**The zero-value rule.** `validate_fixture` gates an explicit zero on three facts:
`equity_canceled_without_consideration`, `issuer_stated_no_value`, and
`cash_usd_per_share == 0`. Without all three, a numeric zero raises. BBBYQ's September 29
effective-date 8-K (accepted 16:23:06 ET) supplies all three, which is why — and only why
— BBBYQ common resolves to 0.00 USD.

**The walk-around.** `consideration_legs` checked only the first TWO conditions. An action
recording "cancelled without consideration, issuer states no value" alongside a *non-zero*
`cash_usd_per_share` resolved to 0.00 with `status: resolved`, while `validate_fixture`
rejected the same action. No committed result was affected — `load_fixture` always
validates — but a caller building an action dict and calling `resolve_terminal_value`
directly walked straight past the rule. The two predicates are now identical, and
`test_the_validator_and_resolver_agree_on_the_SAME_conjunction` fails if they drift again.

A resolver more permissive than its validator is a validator that can be walked around.

**The remaining sharp edge**, recorded rather than changed: when resolution refuses, the
output still echoes the action's `label_type` and `formula`, so an unresolved action can
carry `terminal_zero_value_confirmed_no_consideration`. Whether the resolver should
recompute or echo the label is a design question, so it is asserted as-is.

**Coverage.** 7 of 12 price roles, 3 of 8 complete actions, both re-derived from the
per-action rows, with an identical decision fingerprint across two refreshes. The failures
are not random: all four fixed-cash mergers fail on the subject's last pre-effective
session, and the surviving successor resolves while the acquired subject does not.
"""
import copy
import json
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.corporate_action_outcome_lab import (  # noqa: E402
    consideration_legs, load_fixture, resolve_terminal_value, validate_fixture,
)

DATA = ROOT / "docs" / "research" / "data"
DOC = ROOT / "docs" / "research" / "CA00_terminal_value_and_coverage.md"
COVERAGE = DATA / "ca00_free_provider_coverage.json"
STATE = DATA / "ca01_sec_state_machine_fixture.json"


def coverage():
    return json.loads(COVERAGE.read_text(encoding="utf-8"))


def bbbyq():
    return next(a for a in load_fixture()["actions"]
                if a["subject"]["event_symbol"] == "BBBYQ")


class TheZeroValueRuleTests(unittest.TestCase):
    def test_bbbyq_resolves_to_exactly_zero(self):
        got = resolve_terminal_value(bbbyq(), {})
        self.assertEqual(got["status"], "resolved")
        self.assertEqual(got["terminal_value_usd_per_subject_share"], 0.0)
        self.assertEqual(got["label_type"],
                         "terminal_zero_value_confirmed_no_consideration")

    def test_it_rests_on_the_effective_date_filing_accepted_at_16_23_06(self):
        self.assertEqual(bbbyq()["source"]["source_time"], "2023-09-29T16:23:06-04:00")
        self.assertEqual(bbbyq()["source"]["source_role"],
                         "effective_date_outcome_confirmation")

    def test_the_same_timestamp_appears_in_the_CA01_state_fixture(self):
        """Cross-artifact agreement: two fixtures built for different purposes must
        not disagree about when the effective-date filing was accepted."""
        chains = json.loads(STATE.read_text(encoding="utf-8"))["chains"]
        chain = next(c for c in chains if c["event_symbol"] == "BBBYQ")
        eff = next(a for a in chain["assertions"] if a["state_value"] == "plan_effective")
        self.assertEqual(eff["observed_at"], bbbyq()["source"]["source_time"],
                         "CA-00 and CA-01 now disagree about the BBBYQ effective-date "
                         "filing's acceptance time — reconcile them")

    def test_removing_ANY_of_the_three_facts_refuses_the_zero(self):
        fixture = load_fixture()
        for field in ("equity_canceled_without_consideration", "issuer_stated_no_value"):
            action = copy.deepcopy(bbbyq())
            action["terms"][field] = False
            with self.subTest(field=field):
                with self.assertRaises(ValueError,
                                       msg="{} is no longer required for a numeric zero"
                                           .format(field)):
                    validate_fixture({**fixture, "actions": [action]})
                self.assertIsNone(
                    resolve_terminal_value(action, {})[
                        "terminal_value_usd_per_subject_share"],
                    "resolution still produced a number without {}".format(field))

    def test_a_NONZERO_cash_amount_also_refuses_the_zero(self):
        """The third condition — the one the resolver used to ignore."""
        action = copy.deepcopy(bbbyq())
        action["terms"]["cash_usd_per_share"] = 0.5
        with self.assertRaises(ValueError):
            validate_fixture({**load_fixture(), "actions": [action]})
        got = resolve_terminal_value(action, {})
        self.assertEqual(
            got["status"], "unresolved",
            "an action stating no value while recording a non-zero cash amount resolves "
            "to a number again — the resolver has drifted back off the validator's rule")
        self.assertIsNone(got["terminal_value_usd_per_subject_share"])


class TheValidatorAndResolverAgreeTests(unittest.TestCase):
    """The general property, asserted directly rather than case by case."""

    def test_the_validator_and_resolver_agree_on_the_SAME_conjunction(self):
        fixture = load_fixture()
        base = bbbyq()
        fields = ("equity_canceled_without_consideration", "issuer_stated_no_value",
                  "cash_usd_per_share")
        overrides = {"equity_canceled_without_consideration": False,
                     "issuer_stated_no_value": False,
                     "cash_usd_per_share": 0.5}
        for field in fields:
            action = copy.deepcopy(base)
            action["terms"][field] = overrides[field]
            try:
                validate_fixture({**fixture, "actions": [action]})
                validator_accepts = True
            except ValueError:
                validator_accepts = False
            resolver_zeroes = (consideration_legs(action)[0]["status"]
                               == "zero_consideration_confirmed")
            self.assertEqual(
                validator_accepts, resolver_zeroes,
                "dropping {!r}: validate_fixture accepts={} but the resolver confirms "
                "zero={}. A resolver more permissive than its validator is a validator "
                "that can be walked around.".format(field, validator_accepts,
                                                    resolver_zeroes))

    def test_the_committed_action_satisfies_all_three(self):
        """Otherwise the agreement above is being tested on a degenerate case."""
        terms = bbbyq()["terms"]
        self.assertTrue(terms["equity_canceled_without_consideration"])
        self.assertTrue(terms["issuer_stated_no_value"])
        self.assertEqual(terms["cash_usd_per_share"], 0)


class TheUnresolvedLabelSharpEdgeTests(unittest.TestCase):
    """Recorded, not changed — whether to recompute or echo the label is a design call."""

    def test_an_unresolved_action_still_carries_the_confirmed_zero_label(self):
        action = copy.deepcopy(bbbyq())
        action["terms"]["issuer_stated_no_value"] = False
        got = resolve_terminal_value(action, {})
        self.assertEqual(got["status"], "unresolved")
        self.assertEqual(
            got["label_type"], "terminal_zero_value_confirmed_no_consideration",
            "the resolver now recomputes label_type instead of echoing it — that closes "
            "the sharp edge documented in CA00_terminal_value_and_coverage.md; update "
            "the doc rather than deleting this test")
        self.assertIn("0.0 USD", got["formula"])


class TheCoverageAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cov = coverage()
        cls.rows = cls.cov["action_decisions"]

    def test_the_headline_figures_rederive_from_the_rows(self):
        required = sum(r["roles_required"] for r in self.rows)
        resolved = sum(r["roles_resolved"] for r in self.rows)
        complete = sum(1 for r in self.rows if r["complete"])
        self.assertEqual((resolved, required), (7, 12))
        self.assertEqual(self.cov["resolved_price_roles"], resolved)
        self.assertEqual(self.cov["required_price_roles"], required)
        self.assertEqual((complete, len(self.rows)), (3, 8))
        self.assertEqual(self.cov["actions_complete"], complete)
        self.assertAlmostEqual(self.cov["role_coverage_rate"], resolved / required,
                               places=12)

    def test_the_two_refreshes_produced_the_same_decision_fingerprint(self):
        shas = self.cov["paired_coverage_decision_sha256"]
        self.assertEqual(len(set(shas)), 1,
                         "the paired coverage decisions now differ — the audit is no "
                         "longer decision-stable")
        self.assertTrue(shas[0].startswith("171209f5") and shas[0].endswith("b43fcf"),
                        "F113 cites 171209f5...b43fcf; the fingerprint is now " + shas[0])

    def test_every_fixed_cash_merger_fails_on_the_SAME_leg(self):
        """The failure is structural, not random attrition."""
        mergers = [r for r in self.rows if r["action_type"] == "cash_merger"]
        self.assertEqual(len(mergers), 4)
        for r in mergers:
            self.assertFalse(r["complete"])
            self.assertEqual(
                r["missing"], ["subject_pre_effective"],
                "{} now fails on a different leg — the 'current-symbol data select "
                "against acquired predecessors' reading depends on the failures being "
                "the subject's last pre-effective session".format(r["event_symbol"]))

    def test_the_surviving_successor_resolves_while_the_acquired_subject_does_not(self):
        xlnx = next(r for r in self.rows if r["event_symbol"] == "XLNX")
        self.assertIn("successor_first_effective:AMD", xlnx["resolved"])
        self.assertIn("subject_pre_effective", xlnx["missing"])

    def test_the_two_near_misses_are_recorded_as_ALIASING(self):
        """BBBY-for-BBBYQ and META-for-FB: the fix is symbol aliases, not a new vendor."""
        findings = " ".join(self.cov["findings"])
        self.assertIn("BBBY", findings)
        self.assertIn("META", findings)
        self.assertIn("alias", findings.lower())


class TheDocumentRecordsItTests(unittest.TestCase):
    def test_the_doc_exists_and_cites_both_artifacts(self):
        text = DOC.read_text(encoding="utf-8")
        for name in ("ca00_corporate_action_fixture", "ca00_free_provider_coverage",
                     "171209f5"):
            self.assertIn(name, text)

    def test_the_doc_keeps_the_limits_and_the_unfixed_edge_visible(self):
        import re
        text = re.sub(r"\s+", " ", DOC.read_text(encoding="utf-8")).lower()
        for phrase in ("no price-correctness claim", "not proof that a security never traded",
                       "remaining sharp edge", "plan distribution rights remain"):
            self.assertIn(phrase, text,
                          "the write-up dropped {!r}".format(phrase))


if __name__ == "__main__":
    unittest.main()

"""H38: the router's real defect was false positives, not missing synonyms.

Study: `docs/research/CTX_route_vocabulary_audit.md`. Harness: `ctx route --audit`.

H38 (DP-14) asks to "generate realistic task phrasings, measure the miss rate, add
synonyms". Doing that surfaced a worse failure first.

**Measured against language the routing table was not authored against** — 400 recent
commit subjects and 420 research-web node titles, both written for other purposes — the
miss rate was **20%** and **25%**.

**But the router also answered nonsense.** Of 12 off-domain English sentences with
nothing to do with this project, **5 routed**. "add the flour slowly while whisking the
eggs" scored 3 on param/sweep/backtest — higher than most real queries. The cause: a
multi-word key fired on ANY one of its tokens, so `on_bar` matched every sentence
containing "on", `why did it exit` matched every sentence containing "it", and `add
ticker` matched "add". A confident wrong READ list is worse than no route, so this is
the error direction that mattered.

**Fix.** A key now matches only when EVERY one of its informative tokens is present,
stopwords dropped first. Dropping stopwords before the all-tokens rule is what keeps
`not running` firing on "running" and `why did it exit` firing on "exit" while neither
fires on an unrelated sentence containing "not" or "it".

**Then the synonyms.** The largest remaining miss cluster was one whole area with no
routing rule at all: the context/epistemic layer this project runs on — capture,
supersede, guard, backlog, drift, uncited. Synonyms alone could not reach it; it needed
a rule. With the rule plus 24 synonyms the miss rate is **12%** and **15%**.

`daily` and `hourly` were tried as synonyms and removed: the stemmer takes "hourly" to
"hour", so "trains leave every hour" routed to backtest/strategy. That is the same
false-positive class the fix exists to remove, and two extra percentage points of recall
is not worth reintroducing it.

Guarded in both directions: the miss rate must not regress, the false-positive count must
not grow, and a set of real task phrasings must keep reaching the right area. The
negative controls are the non-vacuity check — a router that answers everything would fail
here even with a perfect miss rate.
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import ctx  # noqa: E402

MAP = json.loads((ROOT / "context_map.json").read_text(encoding="utf-8"))


def top_hits(query):
    scored = ctx._route_rules(query.lower())
    return set(scored[0][1]) if scored else set()


def routes_to_file(query, needle):
    """True when any of the top three rules would send a reader to `needle`."""
    for _, _, rule in ctx._route_rules(query.lower())[:3]:
        if any(needle in target for target in rule["read"]):
            return True
    return False


class StopwordsAreNotRoutingSignalTests(unittest.TestCase):
    def test_a_multi_word_key_needs_all_its_informative_tokens(self):
        self.assertEqual(ctx._key_tokens("why did it exit"), ["exit"])
        self.assertEqual(ctx._key_tokens("on_bar"), ["bar"])
        self.assertEqual(ctx._key_tokens("add ticker"), ["add", "ticker"])

    def test_a_key_made_only_of_stopwords_keeps_them(self):
        """Otherwise it would match every query, which is the bug inverted."""
        self.assertEqual(ctx._key_tokens("what is"), ["what", "is"])

    def test_the_stopword_list_covers_the_words_that_caused_the_false_positives(self):
        for word in ("on", "it", "not", "did", "why", "what", "how"):
            self.assertIn(
                word, ctx._ROUTE_STOPWORDS,
                "{!r} left the routing stopword list — check whether a multi-word key "
                "starts matching on it again".format(word))

    def test_stopword_bearing_concepts_still_fire_on_their_content_word(self):
        self.assertIn("exit", top_hits("why did the bot exit early"))
        self.assertTrue(
            {"running", "status"} & top_hits("is the live bot running right now"),
            "'not running' no longer expands from the word 'running' — the "
            "stopword-drop-then-require-all rule has regressed to require-all")


class TheRouterDoesNotAnswerNonsenseTests(unittest.TestCase):
    """The non-vacuity half: recall means nothing without this."""

    def test_at_most_one_off_domain_sentence_routes(self):
        routed = [q for q in ctx.ROUTE_NEGATIVE_CONTROLS if ctx._route_rules(q)]
        self.assertLessEqual(
            len(routed), 1,
            "{} of {} off-domain sentences now route ({}) — a routing key has become "
            "a common English word again".format(
                len(routed), len(ctx.ROUTE_NEGATIVE_CONTROLS), routed))

    def test_the_one_survivor_is_a_genuine_domain_word(self):
        """`return` is a real keyword; the collision is inherent, not a matching bug."""
        routed = [q for q in ctx.ROUTE_NEGATIVE_CONTROLS if ctx._route_rules(q)]
        for query in routed:
            self.assertIn(
                "return", query,
                "a NEW off-domain sentence routes ({!r}) — investigate which key "
                "matched before accepting it".format(query))

    def test_the_controls_are_still_genuinely_off_domain(self):
        """Non-vacuity for the non-vacuity check."""
        self.assertGreaterEqual(len(ctx.ROUTE_NEGATIVE_CONTROLS), 10)
        for query in ctx.ROUTE_NEGATIVE_CONTROLS:
            self.assertNotIn("trade", query)
            self.assertNotIn("backtest", query)


class TheMissRateIsMeasuredAndBoundedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = ctx.route_audit()

    def test_both_corpora_are_large_enough_to_measure(self):
        for name in ("commit subjects", "web node titles"):
            self.assertGreater(
                self.report[name]["n"], 150,
                "the {} corpus shrank to {} — the miss rate below is noisy".format(
                    name, self.report[name]["n"]))

    def test_the_miss_rate_stays_under_a_fifth(self):
        for name in ("commit subjects", "web node titles"):
            rate = self.report[name]["miss_rate"]
            self.assertLess(
                rate, 0.20,
                "{} miss rate rose to {:.0%} — it was 12%/15% after H38's fix, and "
                "20%/25% before it. New vocabulary has outrun the routing table; run "
                "`ctx route --audit` and add synonyms.".format(name, rate))

    def test_the_miss_rate_is_not_zero(self):
        """A router that matches everything has a 0% miss rate and no value."""
        total = sum(self.report[n]["missed"] for n in
                    ("commit subjects", "web node titles"))
        self.assertGreater(
            total, 0,
            "nothing misses any more — check the keys have not become so loose that "
            "every query matches something")

    def test_the_audit_reports_synonym_candidates(self):
        self.assertTrue(self.report["unrouted_vocabulary"],
                        "the audit no longer surfaces unrouted vocabulary, which is "
                        "the part that tells a maintainer what to add next")


class RealTaskPhrasingsReachTheRightAreaTests(unittest.TestCase):
    """Authored by me, so this measures self-consistency — stated, not hidden. The
    corpus-level numbers above are the evidence that does not depend on my labels."""

    CASES = [
        ("why did the bot exit the position early", "live/trader.py"),
        ("how are fills reconciled with the broker", "live/broker.py"),
        ("the gateway keeps disconnecting", "live/broker.py"),
        ("what does the dashboard equity curve read from", "live/dashboard.py"),
        ("how do I add a new ticker to the sweep", "config.py"),
        ("where is the stop loss set", "live/trader.py"),
        ("capture a finding in the research web", "RESEARCH_WEB.md"),
        ("write a bidirectional guard test", "AGENT_INDEX.md"),
        ("what should i work on next", "tools/research_backlog.py"),
        ("supersede a stale node", "RESEARCH_WEB.md"),
        ("check the walk forward out-of-sample results", "walk_forward.py"),
        ("what tables are in the state db", "live/state.py"),
    ]

    def test_each_phrasing_reaches_a_file_a_maintainer_would_want(self):
        for query, needle in self.CASES:
            self.assertTrue(
                routes_to_file(query, needle),
                "{!r} no longer routes to anything containing {!r} — top hits were "
                "{}".format(query, needle, sorted(top_hits(query))))


class TheContextLayerHasItsOwnRuleTests(unittest.TestCase):
    def test_a_rule_points_at_the_epistemic_tooling(self):
        targets = [t for rule in MAP["routing"] for t in rule["read"]]
        for needle in ("tools/note.py", "tools/research_backlog.py", "AGENT_INDEX.md"):
            self.assertTrue(
                any(needle in t for t in targets),
                "no routing rule sends a reader to {} — the largest unrouted cluster "
                "was exactly this area".format(needle))

    def test_the_rule_warns_against_editing_a_guard_to_pass(self):
        avoid = [a for rule in MAP["routing"] for a in rule["avoid"]]
        self.assertTrue(
            any("supersede" in a for a in avoid),
            "the routing table no longer warns against editing a guard test instead of "
            "superseding the node — that is the project's central discipline")

    def test_the_edit_policy_deny_list_was_not_touched(self):
        """context_map.json is self-fenced; routing maintenance must not widen access."""
        deny = MAP["edit_policy"]["deny"]
        for path in ("live/", "config.py", "context_map.json", ".env"):
            self.assertIn(
                path, deny,
                "{} left the edit-policy deny list — routing maintenance must never "
                "change the fence".format(path))


if __name__ == "__main__":
    unittest.main()

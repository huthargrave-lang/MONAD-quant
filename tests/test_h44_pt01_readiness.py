"""H44's first gate fails on two specific grounds — and the hard half is already built.

Study: `docs/research/PT01_substrate_readiness.md`.

H44 proposes a point-in-time event/outcome ledger with nine components and sets PT-01 as
its first gate: adversarial SEC acceptance fixtures plus source-specific tradable-time
rules, passing on *exact point-in-time reconstruction and deterministic labels*.

Scored across the 27 committed artifacts under `docs/research/data/`, on schema **keys**:

    revision / vintage identity   24        multi-horizon labels     6
    payload hashes                18        rights metadata          4
    source timestamp               8        durable entity identity  2
    first-seen timestamp           7        trial registry           1
    conservative tradable time     6

**No artifact carries all nine; the best is 6**, reached by the four IX-00 index-event
batches. So the gate's pass condition cannot be evaluated on any single record.

**And the tradable-time rules have no consumer.** FD-00 froze eight of them in
`fd00_sec_event_clock_fixtures_2026.json`; the only file in the repository that reads it
is a *test*. Nothing under `src/`, no tool. There is no function that takes a filing and
returns its conservative tradable time — the rules exist as assertions about a fixture,
the same dead-wiring family as F26 and F176.

The shape of the table is the useful half: vintage identity on 24 of 27 and payload hashes
on 18 is real discipline, and it is why the IX-00 and CA-00 reconciliations work at all.
So H44 is re-scoped rather than retired.

Guards below are bidirectional. They fail if the substrate REGRESSES (provenance coverage
drops), and they fail if it ADVANCES past the finding (an artifact reaches 9/9, entity
identity or the trial registry becomes common, or the clock rules gain a production
consumer) — each with a message saying to re-run the audit and supersede, because a gate
that quietly starts passing is as stale as one that quietly starts failing.
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs" / "research" / "data"
DOC = ROOT / "docs" / "research" / "PT01_substrate_readiness.md"
FD00 = "fd00_sec_event_clock_fixtures_2026.json"

# Matched against schema KEYS, with word boundaries. Scoring raw TEXT reported three
# extra trial-registry artifacts, all of which matched "Industrial" — a company name.
FIELD_CLASSES = {
    "entity_identity": r"\b(provider_symbol|cusip\w*|identity_note|entity_id|figi)\b",
    "source_time": r"\b(announcement_source_at|accepted\w*|source_at|filed_at|acceptance\w*)\b",
    "first_seen": r"\b(first_seen|observed_at|retrieved_at\w*)\b",
    "tradable_time": r"\b(first_tradable\w*|tradable\w*)\b",
    "revision_vintage": r"\b(revisions?|vintage|schema_version)\b",
    "payload_hash": r"\b(\w*sha256\w*|payload_hash|content_hash)\b",
    "rights": r"\b(rights_tier|rights|redistribut\w*|licen[cs]\w*)\b",
    "labels": r"(post_implementation_|\bhorizons?\b|_relative\b)",
    "trial_registry": r"\b(trial\w*|preregist\w*|registry)\b",
}
COMPILED = {k: re.compile(v, re.I) for k, v in FIELD_CLASSES.items()}


def schema_keys(obj, out=None):
    out = set() if out is None else out
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.add(k)
            schema_keys(v, out)
    elif isinstance(obj, list):
        for v in obj:
            schema_keys(v, out)
    return out


def score_artifacts():
    scored = {}
    for path in sorted(DATA.glob("*.json")):
        keys = " ".join(sorted(schema_keys(json.loads(path.read_text(encoding="utf-8")))))
        scored[path.name] = {k for k, rx in COMPILED.items() if rx.search(keys)}
    return scored


class TheGateCannotBeEvaluatedOnAnyRecordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scored = score_artifacts()

    def test_the_corpus_is_big_enough_to_audit(self):
        self.assertGreaterEqual(
            len(self.scored), 20,
            "fewer than 20 committed artifacts — the coverage counts below are noise")

    def test_no_artifact_carries_the_full_field_set(self):
        complete = [n for n, have in self.scored.items() if len(have) == len(COMPILED)]
        self.assertEqual(
            complete, [],
            "{} now satisfies all nine PT-01 field classes — the gate may be passable; "
            "re-run the audit in docs/research/PT01_substrate_readiness.md and "
            "supersede the finding".format(complete))

    def test_the_best_artifact_reaches_six(self):
        best = max(len(h) for h in self.scored.values())
        self.assertEqual(
            best, 6,
            "the best artifact now scores {} of 9 (was 6) — the readiness table is "
            "stale; re-measure".format(best))

    def test_the_leaders_are_the_index_event_batches(self):
        leaders = {n for n, h in self.scored.items() if len(h) == 6}
        self.assertTrue(
            all(n.startswith("ix00_") for n in leaders),
            "a non-IX-00 artifact reached the top score ({}) — the study attributes "
            "the lead to the index-event batches".format(sorted(leaders)))


class ProvenanceIsBuiltAndIdentityIsNotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        scored = score_artifacts()
        cls.n = len(scored)
        cls.coverage = {k: sum(1 for h in scored.values() if k in h) for k in COMPILED}

    def test_vintage_identity_is_near_universal(self):
        self.assertGreaterEqual(
            self.coverage["revision_vintage"], self.n - 5,
            "revision/vintage coverage fell to {}/{} — the one part of H44's substrate "
            "that IS built is regressing".format(
                self.coverage["revision_vintage"], self.n))

    def test_payload_hashes_are_common(self):
        self.assertGreater(
            self.coverage["payload_hash"], self.n // 2,
            "payload-hash coverage fell below half ({}/{})".format(
                self.coverage["payload_hash"], self.n))

    def test_entity_identity_is_rare(self):
        self.assertLessEqual(
            self.coverage["entity_identity"], 5,
            "durable entity identity is now on {}/{} artifacts — H44's first re-scoped "
            "step is progressing; re-measure and supersede".format(
                self.coverage["entity_identity"], self.n))

    def test_a_trial_registry_barely_exists(self):
        self.assertLessEqual(
            self.coverage["trial_registry"], 3,
            "a trial registry now appears on {}/{} artifacts — the 'did the "
            "preregistered claim hold' query may be answerable; re-measure".format(
                self.coverage["trial_registry"], self.n))

    def test_the_one_registry_artifact_is_the_lead_lag_summary(self):
        scored = score_artifacts()
        carriers = sorted(n for n, h in scored.items() if "trial_registry" in h)
        self.assertEqual(carriers, ["pn00_daily_lead_lag_summary_2026.json"],
                         "the trial-registry carrier set changed: {}".format(carriers))


class TheClockRulesHaveNoProductionConsumerTests(unittest.TestCase):
    def test_the_fixture_exists(self):
        self.assertTrue((DATA / FD00).exists(),
                        "FD-00's clock fixtures are gone — PT-01 lost its input")

    def test_it_encodes_several_distinct_rules(self):
        payload = json.loads((DATA / FD00).read_text(encoding="utf-8"))
        keys = schema_keys(payload)
        self.assertGreater(len(keys), 10,
                           "the clock fixture shrank — re-read what PT-01 still has")

    def test_nothing_under_src_reads_it(self):
        readers = [p.relative_to(ROOT).as_posix() for p in (ROOT / "src").rglob("*.py")
                   if FD00 in p.read_text(encoding="utf-8")
                   or "sec_event_clock" in p.read_text(encoding="utf-8")]
        self.assertEqual(
            readers, [],
            "src/ now reads the clock fixtures ({}) — the tradable-time rules gained a "
            "production consumer, which is PT-01's first re-scoped step. Re-run the "
            "audit and supersede.".format(readers))

    def test_no_tool_reads_it_either(self):
        readers = [p.name for p in (ROOT / "tools").glob("*.py")
                   if FD00 in p.read_text(encoding="utf-8")]
        self.assertEqual(
            readers, [],
            "a tool now consumes the clock fixtures ({}) — same as above".format(readers))

    def test_only_a_test_reads_it(self):
        """The precise claim: the rules exist as assertions, not as behaviour.

        This file is excluded from its own census — it names the fixture in order to
        assert who reads it, and a detector that counts itself reports presence for
        the act of looking. Fifth instance of that class in this codebase.
        """
        readers = sorted(p.name for p in (ROOT / "tests").glob("*.py")
                         if p.name != Path(__file__).name
                         and FD00 in p.read_text(encoding="utf-8"))
        self.assertEqual(
            readers, ["test_sec_clock_cross_fixture.py"],
            "the set of files reading FD-00's fixtures changed: {}".format(readers))

    def test_there_is_no_tradable_time_function_anywhere(self):
        hits = []
        for area in ("src", "tools"):
            for path in (ROOT / area).rglob("*.py"):
                if re.search(r"def \w*tradable_time\w*\(", path.read_text(encoding="utf-8")):
                    hits.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(
            hits, [],
            "a tradable-time function exists now ({}) — PT-01's missing parser was "
            "built; re-evaluate the gate".format(hits))


class TheStudyRecordsTheVerdictTests(unittest.TestCase):
    def test_it_names_the_two_grounds_for_failure(self):
        text = DOC.read_text(encoding="utf-8")
        self.assertIn("6 of 9", text)
        self.assertIn("no consumer", text.lower())

    def test_it_re_scopes_rather_than_retires(self):
        text = DOC.read_text(encoding="utf-8")
        self.assertIn("re-scope", text.lower())
        self.assertIn("H44", text)

    def test_h44_is_still_open(self):
        web = (ROOT / "RESEARCH_WEB.md").read_text(encoding="utf-8")
        start = web.index("### H44 ")
        body = web[start:web.index("\n### ", start + 5)]
        self.assertNotIn(
            "status: superseded", body,
            "H44 was superseded — if the gate now passes, retire this whole file "
            "rather than leaving a guard for a closed question")


if __name__ == "__main__":
    unittest.main()

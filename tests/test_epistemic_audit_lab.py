"""Tests for the EPI-00 epistemic audit lab.

Covers web parsing, reliance-vs-citation edge semantics, the exact Poisson rate
interval (a regression guard — the bounds were inverted in first draft), the
backfill-vs-in-vivo revision classification exercised against a real temporary git
history, cycle detection, evidence-traversability classification, and the power
statement. Structural assertions only against the live web, so the tests do not
break as the web grows. Stdlib only, offline.
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "epistemic_audit_lab", ROOT / "tools" / "epistemic_audit_lab.py"
)
LAB = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = LAB
SPEC.loader.exec_module(LAB)


SYNTHETIC_WEB = """# Web

## Findings

### F1 — first claim
Body of one. Evidence: [[E1|evidenced_by]]. Also [[F2|relates]].

### F2 — second claim
Builds on the first: [[F1|builds_on]]. Mentions [[E1]] without typing it.

### F3 — third claim
<!-- status: superseded; by: F2; reason: reversed; at: 2026-01-05 -->
Refuted claim that relies on [[F1|refines]].

### F4 — unevidenced claim
No experiment here at all, but [[F1|supports]].

## Experiments

### E1 — the experiment
Produces [[F1|produces]].
"""


class ParsingTests(unittest.TestCase):
    def setUp(self):
        self.nodes = LAB.parse_web(SYNTHETIC_WEB)

    def test_parses_all_nodes(self):
        self.assertEqual(set(self.nodes), {"F1", "F2", "F3", "F4", "E1"})

    def test_titles_and_kinds(self):
        self.assertEqual(self.nodes["F1"]["title"], "first claim")
        self.assertEqual(self.nodes["E1"]["kind"], "E")

    def test_supersession_metadata(self):
        f3 = self.nodes["F3"]
        self.assertEqual(f3["status"], "superseded")
        self.assertEqual(f3["superseded_by"], "F2")
        self.assertEqual(f3["supersession_reason"], "reversed")

    def test_current_nodes_have_current_status(self):
        self.assertEqual(self.nodes["F1"]["status"], "current")

    def test_evidence_flags_distinguish_typed_from_untyped(self):
        self.assertTrue(self.nodes["F1"]["has_evidenced_by"])
        self.assertFalse(self.nodes["F2"]["has_evidenced_by"])
        self.assertTrue(self.nodes["F2"]["cites_experiment"])  # untyped [[E1]]
        self.assertFalse(self.nodes["F4"]["cites_experiment"])

    def test_untyped_links_are_cue_classified_like_ctx(self):
        """SCHEMA §5: an untyped [[ID]] is cue-classified from the preceding prose
        and only DEFAULTS to `relates`. Penalising 'Source: [[E6]]' as a non-evidence
        link was a real defect in the first draft."""
        nodes = LAB.parse_web("### F9 — x\nSource: [[E6]].\n")
        self.assertEqual(nodes["F9"]["edges"], [("E6", "evidenced_by")])
        self.assertTrue(nodes["F9"]["has_resolved_evidence"])

    def test_untyped_link_without_a_cue_falls_back_to_relates(self):
        nodes = LAB.parse_web("### F9 — x\nSee also [[F1]].\n")
        self.assertEqual(nodes["F9"]["edges"], [("F1", "relates")])

    def test_duplicate_node_ids_are_counted_not_silently_dropped(self):
        nodes = LAB.parse_web("### F1 — one\nbody\n\n### F1 — two\nother\n")
        self.assertEqual(nodes["F1"]["duplicate_count"], 2)
        self.assertEqual(LAB.duplicate_node_ids(nodes), ["F1"])

    def test_footer_and_status_stamps_are_parsed(self):
        nodes = LAB.parse_web(
            "### F1 — x\n<!-- status: superseded; by: F2; reason: r; at: 2026-07-24 -->\n"
            "body\n_— captured dev@abc123, 2026-07-23_\n")
        self.assertEqual(nodes["F1"]["footer_date"], "2026-07-23")
        self.assertEqual(nodes["F1"]["status_at"], "2026-07-24")


class EdgeSemanticsTests(unittest.TestCase):
    def setUp(self):
        self.nodes = LAB.parse_web(SYNTHETIC_WEB)
        self.depends, self.rdepends, self.cites = LAB.parse_edges(self.nodes)

    def test_only_reliance_edges_create_dependencies(self):
        # F1 cites F2 via `relates`, which must NOT create a dependency.
        self.assertNotIn("F2", self.depends.get("F1", set()))
        # F2 builds_on F1 -> dependency.
        self.assertIn("F1", self.depends["F2"])

    def test_citations_include_untyped_and_relates(self):
        self.assertIn("F2", self.cites["F1"])
        self.assertIn("E1", self.cites["F2"])

    def test_reverse_dependency_index(self):
        self.assertEqual(self.rdepends["F1"], {"F2", "F3", "F4"})

    def test_self_citation_ignored(self):
        nodes = LAB.parse_web("### F9 — self\nSee [[F9|builds_on]].\n")
        depends, _r, _c = LAB.parse_edges(nodes)
        self.assertEqual(depends.get("F9", set()), set())


class PoissonIntervalTests(unittest.TestCase):
    """Regression guard: the first draft had the Gamma quantile targets swapped,
    producing ci_low > ci_high. These are published exact Poisson bounds."""

    def test_one_event(self):
        ci = LAB.poisson_ci(1, 1.0)
        self.assertAlmostEqual(ci["ci95_low"], 0.0253, places=3)
        self.assertAlmostEqual(ci["ci95_high"], 5.5716, places=3)

    def test_five_events(self):
        ci = LAB.poisson_ci(5, 1.0)
        self.assertAlmostEqual(ci["ci95_low"], 1.623, places=2)
        self.assertAlmostEqual(ci["ci95_high"], 11.668, places=2)

    def test_zero_events(self):
        ci = LAB.poisson_ci(0, 1.0)
        self.assertEqual(ci["ci95_low"], 0.0)
        self.assertAlmostEqual(ci["ci95_high"], 3.689, places=2)

    def test_bounds_ordered_and_bracket_the_point(self):
        for k in (0, 1, 2, 7, 20, 100, 400):
            ci = LAB.poisson_ci(k, 100.0)
            self.assertLessEqual(ci["ci95_low"], ci["rate"], k)
            self.assertLessEqual(ci["rate"], ci["ci95_high"], k)

    def test_large_k_fails_loudly_instead_of_returning_a_broken_interval(self):
        """The Poisson series underflows above k~745; it must raise rather than
        silently return an interval that does not bracket the point estimate."""
        with self.assertRaisesRegex(ValueError, "lost precision"):
            LAB.poisson_ci(1000, 1.0)

    def test_exposure_scales_rate(self):
        a = LAB.poisson_ci(4, 10.0)
        b = LAB.poisson_ci(4, 20.0)
        self.assertAlmostEqual(a["rate"], 2 * b["rate"])

    def test_zero_exposure_is_undefined_not_a_crash(self):
        ci = LAB.poisson_ci(3, 0.0)
        self.assertIsNone(ci["rate"])


def _git(args, cwd):
    env = dict(os.environ)
    env.update({
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
    })
    subprocess.run(["git"] + args, cwd=cwd, check=True, env=env,
                   capture_output=True, text=True)


class LifecycleTests(unittest.TestCase):
    """Build a real 3-commit git history and assert the revision classification."""

    def _repo(self, tmp):
        repo = Path(tmp)
        _git(["init", "-q"], repo)
        web = repo / "RESEARCH_WEB.md"

        # commit 0: A and B born; B is born ALREADY superseded (backfill).
        web.write_text(
            "### F1 — a\nalive claim\n\n"
            "### F2 — b\n<!-- status: superseded; by: F1; reason: reversed -->\n"
            "born dead\n",
            encoding="utf-8")
        _git(["add", "."], repo)
        _git(["commit", "-q", "-m", "c0", "--date=2026-01-01T00:00:00"], repo)

        # commit 1: C born, still alive.
        web.write_text(web.read_text(encoding="utf-8") + "\n### F3 — c\nlater claim\n",
                       encoding="utf-8")
        _git(["add", "."], repo)
        _git(["commit", "-q", "-m", "c1", "--date=2026-01-05T00:00:00"], repo)

        # commit 2: A superseded LATER than birth -> a genuine in-vivo revision.
        text = web.read_text(encoding="utf-8").replace(
            "### F1 — a\nalive claim",
            "### F1 — a\n<!-- status: superseded; by: F3; reason: reversed -->\nalive claim")
        web.write_text(text, encoding="utf-8")
        _git(["add", "."], repo)
        _git(["commit", "-q", "-m", "c2", "--date=2026-01-11T00:00:00"], repo)
        return repo

    def test_classifies_backfill_vs_in_vivo(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = self._repo(tmp)
            life = LAB.node_lifecycles(repo)
        # F2 is tombstoned in the FIRST observed commit, so both its birth and its
        # refutation precede the window: unobservable, NOT provably bookkeeping.
        self.assertEqual(life["F2"]["revision_class"], "truncated_unknown")
        self.assertEqual(life["F1"]["revision_class"], "in_vivo")
        self.assertEqual(life["F3"]["revision_class"], "alive")

    def test_left_truncated_tombstone_is_not_called_backfill(self):
        """Regression: the first draft labelled every same-commit tombstone
        'backfill / never a live belief'. For nodes already dead in the first
        observed commit that is an unsupportable claim about unobservable history."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = self._repo(tmp)
            life = LAB.node_lifecycles(repo)
        self.assertTrue(life["F2"]["left_truncated"])
        self.assertNotEqual(life["F2"]["revision_class"], "backfill")

    def test_truncated_unknown_excluded_from_numerator_and_denominator(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = self._repo(tmp)
            rev = LAB.revision_analysis(LAB.node_lifecycles(repo))
        self.assertEqual(rev["truncated_unknown_ids"], ["F2"])
        # F1 (10 days) + F3 (6 days); F2 contributes nothing either way.
        self.assertEqual(rev["exposure_node_days"], 16.0)
        self.assertEqual(rev["in_vivo_events"], 1)

    def test_hazard_sensitivity_brackets_the_truncated_ambiguity(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = self._repo(tmp)
            rev = LAB.revision_analysis(LAB.node_lifecycles(repo))
        s = rev["hazard_sensitivity"]
        self.assertEqual(s["events_excluding_truncated"], 1)
        self.assertEqual(s["events_including_truncated_as_revisions"], 2)
        self.assertLess(s["p_365d_low_case"], s["p_365d_high_case"])

    def test_stamped_clock_recovers_a_same_commit_revision(self):
        """A node captured on the 23rd and superseded on the 24th is a genuine
        revision even when both land in one commit — note.py's own stamps are a
        finer clock than the commit that happens to carry the node."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _git(["init", "-q"], repo)
            web = repo / "RESEARCH_WEB.md"
            web.write_text("### F1 — seed\nbase\n_— captured dev@a, 2026-07-01_\n",
                           encoding="utf-8")
            _git(["add", "."], repo)
            _git(["commit", "-q", "-m", "c0", "--date=2026-07-01T00:00:00"], repo)
            web.write_text(
                web.read_text(encoding="utf-8") +
                "\n### F2 — born and killed in one commit, but stamps differ\n"
                "<!-- status: superseded; by: F1; reason: reversed; at: 2026-07-24 -->\n"
                "body\n_— captured dev@b, 2026-07-23_\n",
                encoding="utf-8")
            _git(["add", "."], repo)
            _git(["commit", "-q", "-m", "c1", "--date=2026-07-24T00:00:00"], repo)
            life = LAB.node_lifecycles(repo)
        self.assertEqual(life["F2"]["revision_class"], "in_vivo")
        self.assertEqual(life["F2"]["birth_date"], "2026-07-23")
        self.assertEqual(life["F2"]["death_date"], "2026-07-24")

    def test_first_commit_nodes_are_left_truncated(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = self._repo(tmp)
            life = LAB.node_lifecycles(repo)
        self.assertTrue(life["F1"]["left_truncated"])
        self.assertFalse(life["F3"]["left_truncated"])

    def test_revision_analysis_excludes_unobservable_nodes_from_exposure(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = self._repo(tmp)
            life = LAB.node_lifecycles(repo)
            rev = LAB.revision_analysis(life)
        self.assertEqual(rev["in_vivo_events"], 1)
        self.assertEqual(rev["revision_classes"]["truncated_unknown"], 1)
        # F1 lived 2026-01-01 -> 2026-01-11 = 10 days; F3 2026-01-05 -> 2026-01-11 = 6.
        # F2 (tombstoned in the first observed commit) contributes nothing.
        self.assertEqual(rev["exposure_node_days"], 16.0)

    def test_naive_rate_exceeds_in_vivo_evidence(self):
        """The naive proportion counts backfill; the honest event count does not."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = self._repo(tmp)
            rev = LAB.revision_analysis(LAB.node_lifecycles(repo))
        naive_events = rev["naive_supersession_rate"] * rev["n_nodes"]
        self.assertEqual(naive_events, 2)
        self.assertEqual(rev["in_vivo_events"], 1)

    def test_horizon_probabilities_carry_an_interval(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = self._repo(tmp)
            rev = LAB.revision_analysis(LAB.node_lifecycles(repo))
        h = rev["implied_revision_probability"]["p_revised_by_90d"]
        self.assertLessEqual(h["ci95_low"], h["point"])
        self.assertLessEqual(h["point"], h["ci95_high"])


class CycleTests(unittest.TestCase):
    def test_detects_a_reliance_cycle(self):
        text = ("### F1 — a\nrelies [[F2|builds_on]].\n\n"
                "### F2 — b\nrelies [[F1|refines]].\n")
        nodes = LAB.parse_web(text)
        depends, _r, _c = LAB.parse_edges(nodes)
        cycles = LAB.find_cycles(depends, sorted(nodes))
        self.assertTrue(cycles)

    def test_acyclic_graph_has_no_cycles(self):
        nodes = LAB.parse_web(SYNTHETIC_WEB)
        depends, _r, _c = LAB.parse_edges(nodes)
        self.assertEqual(LAB.find_cycles(depends, sorted(nodes)), [])


class GraphAndRiskTests(unittest.TestCase):
    def setUp(self):
        self.nodes = LAB.parse_web(SYNTHETIC_WEB)
        self.graph = LAB.graph_analysis(self.nodes)

    def test_blast_radius_counts_transitive_dependents(self):
        # F2, F3, F4 all rely on F1 directly; none rely on each other.
        self.assertEqual(self.graph["blast_radius"]["F1"], 3)
        self.assertEqual(self.graph["blast_radius"]["F4"], 0)

    def test_reliance_edges_fewer_than_citations(self):
        self.assertLess(self.graph["reliance_edges"], self.graph["citation_edges"])

    def _life(self):
        return {n: {"id": n, "birth_index": 0, "birth_date": "2026-01-01",
                    "death_index": None, "observed_commits": 1,
                    "last_observed_date": "2026-01-02", "left_truncated": True,
                    "revision_class": "alive", "kind": n[0]}
                for n in self.nodes}

    def test_evidence_link_levels(self):
        risk = LAB.risk_analysis(self.nodes, self._life(), self.graph, top=10)
        by_id = {r["id"]: r for r in risk["ranked"]}
        self.assertEqual(by_id["F1"]["evidence_link"], "linked")   # typed
        # F2 says "Mentions [[E1]] without typing it" — no evidence cue precedes
        # the link, so it correctly stays un-resolved rather than being credited.
        self.assertEqual(by_id["F2"]["evidence_link"], "cited_not_evidence_typed")
        self.assertEqual(by_id["F4"]["evidence_link"], "no_direct_link")
        self.assertEqual(by_id["E1"]["evidence_link"], "n/a")

    def test_corroborated_only_level(self):
        """A Finding with no Experiment of its own but an incoming `supports` from
        an evidenced node is materially better off than an orphan."""
        text = ("### F1 — claim\nno experiment here\n\n"
                "### F2 — replication\nConfirms [[F1|supports]]. [[E1|evidenced_by]]\n\n"
                "### E1 — exp\nrun\n")
        nodes = LAB.parse_web(text)
        graph = LAB.graph_analysis(nodes)
        life = {n: {"id": n, "birth_index": 0, "birth_date": "2026-01-01",
                    "death_index": None, "observed_commits": 1,
                    "last_observed_date": "2026-01-02", "left_truncated": True,
                    "revision_class": "alive", "kind": n[0]} for n in nodes}
        risk = LAB.risk_analysis(nodes, life, graph, top=10)
        row = {r["id"]: r for r in risk["ranked"]}["F1"]
        self.assertEqual(row["evidence_link"], "corroborated_only")
        self.assertEqual(row["corroborated_by"], ["F2"])

    def test_scoring_string_documents_every_emitted_level(self):
        risk = LAB.risk_analysis(self.nodes, self._life(), self.graph, top=50)
        for row in risk["ranked"]:
            self.assertIn(str(row["evidence_link"]), risk["scoring"])

    def test_superseded_nodes_excluded_from_risk(self):
        life = {n: {"id": n, "birth_index": 0, "birth_date": "2026-01-01",
                    "death_index": None, "observed_commits": 1,
                    "last_observed_date": "2026-01-02", "left_truncated": True,
                    "revision_class": "alive", "kind": n[0]}
                for n in self.nodes}
        risk = LAB.risk_analysis(self.nodes, life, self.graph, top=10)
        self.assertNotIn("F3", {r["id"] for r in risk["ranked"]})


class PowerTests(unittest.TestCase):
    def test_no_events_is_not_modellable(self):
        self.assertEqual(LAB.reversal_power(0, 300)["verdict"], "no_events")

    def test_verdict_is_a_real_tri_state_not_a_falsy_none(self):
        """Regression: `detectable` used to be False-or-None and never True, so a
        consumer branching on it could not distinguish 0 events from 40."""
        verdicts = {k: LAB.reversal_power(k, 300)["verdict"] for k in (0, 1, 40)}
        self.assertEqual(verdicts[0], "no_events")
        self.assertEqual(verdicts[1], "no_feasible_signature")
        self.assertEqual(verdicts[40], "detectable")

    def test_all_branches_return_the_same_key_set(self):
        keys = [set(LAB.reversal_power(k, 300)) for k in (0, 1, 40)]
        self.assertEqual(keys[0], keys[1])
        self.assertEqual(keys[1], keys[2])

    def test_infeasible_mde_is_flagged_not_reported_as_a_number(self):
        """At tiny event counts the MDE exceeds the largest difference any two-arm
        split could produce, so no signature is detectable at all."""
        result = LAB.reversal_power(2, 186)
        self.assertGreater(result["min_detectable_rate_difference"],
                           result["max_feasible_rate_difference"])
        self.assertEqual(result["verdict"], "no_feasible_signature")

    def test_normal_approximation_validity_is_reported(self):
        self.assertFalse(LAB.reversal_power(2, 186)["normal_approximation_valid"])
        self.assertTrue(LAB.reversal_power(200, 1000)["normal_approximation_valid"])

    def test_relative_mde_improves_as_events_accumulate(self):
        self.assertGreater(
            LAB.reversal_power(2, 300)["mde_as_multiple_of_base_rate"],
            LAB.reversal_power(40, 300)["mde_as_multiple_of_base_rate"],
        )


class ProductionWebTests(unittest.TestCase):
    """Structural assertions only, so growth of the real web cannot break these."""

    def setUp(self):
        self.nodes = LAB.parse_web(LAB.WEB.read_text(encoding="utf-8"))

    def test_production_web_parses_a_substantial_graph(self):
        self.assertGreater(len(self.nodes), 100)
        kinds = {n[0] for n in self.nodes}
        self.assertTrue({"F", "E", "H", "D"} <= kinds)

    def test_every_node_id_is_wellformed(self):
        for node_id in self.nodes:
            self.assertRegex(node_id, r"^[EFHD]\d+$")

    def test_reliance_graph_is_a_strict_subset_of_citations(self):
        graph = LAB.graph_analysis(self.nodes)
        self.assertLess(graph["reliance_edges"], graph["citation_edges"])

    def test_report_runs_end_to_end_and_is_json_serialisable(self):
        report = LAB.full_report()
        json.dumps(report, default=str)
        self.assertIn("revision", report)
        self.assertIn("risk", report)
        self.assertGreaterEqual(len(report["limitations"]), 3)

    def test_report_declares_repo_provenance(self):
        """A shallow clone makes every historical figure a checkout artifact; the
        report must say so rather than presenting the window as project history."""
        report = LAB.full_report()
        prov = report["repo_provenance"]
        self.assertIn("shallow_clone", prov)
        if prov["shallow_clone"]:
            self.assertTrue(prov["warning"])
            self.assertFalse(prov["history_is_complete"])
            self.assertTrue(any("SHALLOW" in str(x) for x in report["limitations"]))

    def test_report_corpus_is_internally_consistent(self):
        """graph/risk and lifecycle must describe the SAME node set, with any
        uncommitted nodes surfaced rather than silently dropped from the ranking."""
        report = LAB.full_report()
        self.assertEqual(report["graph"]["n_nodes"], report["revision"]["n_nodes"])
        self.assertIn("uncommitted_nodes", report)

    def test_retired_node_ids_are_surfaced_not_silently_dropped(self):
        """History can hold ids the web no longer has — a deletion, or a renumber
        resolving a merge collision. Dropping them silently would inflate every
        per-node exposure rate by dead ids; keeping them would make `graph` (HEAD)
        and `revision` (all commits) describe different corpora. The report does
        neither: it drops them from the analysis and lists them."""
        report = LAB.full_report()
        self.assertIn("retired_nodes", report)
        retired = report["retired_nodes"]
        self.assertIsInstance(retired, list)
        head = set(LAB.parse_web(
            (LAB.REPO / "RESEARCH_WEB.md").read_text(encoding="utf-8")))
        for node_id in retired:
            self.assertNotIn(
                node_id, head,
                "{} is listed as retired but is present in the web".format(node_id))

    def test_retired_ids_do_not_reach_the_revision_denominator(self):
        """Non-vacuity for the fix: the count must exclude them, not merely name
        them. Only meaningful while some id is actually retired."""
        report = LAB.full_report()
        if not report["retired_nodes"]:
            self.skipTest("no retired ids in this history — nothing to exclude")
        self.assertEqual(
            report["graph"]["n_nodes"], report["revision"]["n_nodes"],
            "retired ids are back in the revision denominator")

    def test_integrity_checks_catch_supersedes_without_tombstone(self):
        nodes = LAB.parse_web(
            "### F1 — new\nSUPERSEDES [[F2|supersedes]].\n\n"
            "### F2 — old\nno tombstone here\n")
        checks = LAB.integrity_checks(nodes)
        self.assertEqual(checks["supersedes_edge_without_tombstone"], ["F2"])

    def test_only_declared_supersessions_count_not_cue_inferred(self):
        """ctx's cue table maps prose like 'reversal' to `supersedes`. An inferred
        edge is not the author declaring a supersession, so it must not raise an
        integrity violation (this produced false positives on F10 and F22)."""
        nodes = LAB.parse_web("### F1 — a\nThis reversal of [[F2]] is discussed.\n\n"
                              "### F2 — b\nno tombstone\n")
        self.assertIn(("F2", "supersedes"), nodes["F1"]["edges"])      # inferred
        self.assertEqual(nodes["F1"]["explicit_edges"], [])            # not declared
        self.assertEqual(
            LAB.integrity_checks(nodes)["supersedes_edge_without_tombstone"], [])

    def test_out_of_vocabulary_edge_types_are_reported(self):
        nodes = LAB.parse_web("### F1 — a\nSee [[F2|extends]].\n\n### F2 — b\nx\n")
        checks = LAB.integrity_checks(nodes)
        self.assertEqual(checks["out_of_vocabulary_edge_types"],
                         ["F1 -[extends]-> F2"])

    def test_explicit_type_beats_a_cue_inferred_duplicate(self):
        """SCHEMA calls the trailing `Links:` line the authoritative echo of typed
        edges, so an explicit type must win over prose inference for the same target."""
        nodes = LAB.parse_web(
            "### F1 — a\nBuilds on [[F2]].\nLinks: [[F2|relates]].\n\n### F2 — b\nx\n")
        self.assertEqual(nodes["F1"]["edges"], [("F2", "relates")])

    def test_classifier_matches_the_canonical_ctx_reader_on_the_real_web(self):
        """Single source of truth: a hand-written cue copy drifted from ctx.py and
        silently corrupted the reliance graph. Assert byte-for-byte agreement."""
        import ctx as CTX
        ctx_nodes, _ = CTX._parse_web()
        mine = LAB.parse_web(LAB.WEB.read_text(encoding="utf-8"))
        self.assertEqual(set(ctx_nodes), set(mine))
        for node_id, node in ctx_nodes.items():
            self.assertEqual(
                {(e["target"], e["type"]) for e in node["edges"]},
                set(mine[node_id]["edges"]),
                "edge disagreement with ctx.py at {}".format(node_id),
            )

    def test_report_refuses_to_write_inside_the_repo(self):
        with self.assertRaisesRegex(ValueError, "refusing to write"):
            LAB._write_json_atomic(ROOT / "should_not_exist.json", {"a": 1})


if __name__ == "__main__":
    unittest.main()

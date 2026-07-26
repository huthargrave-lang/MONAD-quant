"""Seven UI surfaces, five grounds, one theme-aware page — and a node view that admits
when a chart does not apply.

Tool: `tools/research_ui.py`. Study: `docs/research/UI_surface_unification.md`.

Before `research_ui.py` this repository had six HTML surfaces and nothing shared between
them: four distinct page grounds, five independently-authored CSS blocks, no page
answering `prefers-color-scheme`, and one page fetching d3 from a CDN it cannot always
reach (F216). The three `#080b12` lab pages look alike because they were copied, not
because they share anything — whitespace-normalised they are now three different strings
of 444, 463 and 476 characters. That is the same defect the config census (F226/F227) and
the column census (F228) found one layer down: several paths holding one fact, with
nothing keeping them in step.

The server does not rewrite those surfaces. It mounts them — `ctx.py`'s four database
route adapters are called unchanged — under one shell that owns the palette, and it
measures the fragmentation from source so the number cannot rot.

THE NODE VIEW IS THE SUBSTANTIVE PART, and its rule is that a rendering must be earned:
each of the six chart patterns is gated by a predicate over data the node ACTUALLY has —
its cited artifacts, the tables in its study doc, the numeric bounds in its guard tests.
A pattern that cannot be drawn prints why in place of drawing itself. Silently omitting
it would read as "this node has no such data" when the truth is usually "this pattern
does not apply to this kind of node" (the absence-flag family, F155/F159/F188/F204).

Three defects were found by rendering the thing and looking at it, and each is guarded
below because each would silently return:

* `config_reachability.json` carries `dead_to_shipping: 29`, which is not a class — it is
  `tests-only` (8) plus `unreferenced` (21). Drawn as a segment of a 100% bar it
  double-counts 29 of 203 constants. `_derived_keys` detects and drops it, and requires
  all summands to be non-zero so a class of size 2 cannot "explain" itself as 0 + 2 and
  vanish from its own census.
* The parity guard bounds `share` twice — `< 0.02` at 0.8%/bar and `> 0.05` at 0.15%/bar,
  the second existing to prove the first is not vacuous. Keyed on expression text those
  merge into a band whose floor sits ABOVE its ceiling, and the strip drew it backwards.
  An inverted band means two conditions, not a range.
* Row labels came from whichever JSON key sorted first, which for the parity census is
  `backtest` — so every row was labelled with one of the two values being compared
  instead of with the dimension being compared.

Guards below fail in BOTH directions. They fail if the fragmentation gets worse (a sixth
ground, a fourth copy of the lab stylesheet, a new surface nobody censused) and they fail
if it gets BETTER (a second theme-aware page, a second surface adopting the tokens) —
because a census that quietly starts passing is as stale as one that quietly starts
failing. Fix the surface, then supersede the finding; do not edit the number here.
"""
import json
import re
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import research_ui as ui  # noqa: E402

DATA = ROOT / "docs" / "research" / "data"
HEX = re.compile(r"#[0-9a-fA-F]{6}\b")


class TheSurfaceCensusIsCompleteTests(unittest.TestCase):
    """The census must cover every HTML-emitting file, or its counts are decoration."""

    @classmethod
    def setUpClass(cls):
        cls.census = ui.surface_census()
        cls.by_path = {r["path"]: r for r in cls.census["surfaces"]}

    def test_it_censuses_every_html_emitting_file(self):
        found = set()
        for area in ("tools", "live"):
            for path in (ROOT / area).rglob("*"):
                if path.suffix not in (".py", ".html") or not path.is_file():
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
                if "<style>" in text or "<!doctype" in text.lower():
                    found.add(path.relative_to(ROOT).as_posix())
        missed = sorted(found - set(self.by_path))
        self.assertEqual(
            missed, [],
            "these files emit HTML and are not in research_ui.SURFACES: {} — add them, "
            "because an uncensused surface is exactly how the count stops meaning "
            "anything".format(missed))

    def test_every_listed_surface_still_exists(self):
        for rel, _role, _entry, _served in ui.SURFACES:
            self.assertTrue((ROOT / rel).exists(),
                            "{} is in SURFACES but gone from disk".format(rel))
        self.assertEqual(len(self.census["surfaces"]), len(ui.SURFACES))

    def test_the_ground_count_has_not_grown(self):
        self.assertLessEqual(
            self.census["counts"]["grounds"], 5,
            "a sixth distinct page ground appeared — a new surface invented its own "
            "palette instead of using /static/ui.css")

    def test_the_ground_count_has_not_shrunk_either(self):
        self.assertGreaterEqual(
            self.census["counts"]["grounds"], 5,
            "distinct grounds fell below 5 — surfaces are converging, which is GOOD "
            "news. Re-run `python3 tools/research_ui.py surfaces`, update "
            "docs/research/UI_surface_unification.md and supersede the finding")

    def test_exactly_one_surface_is_theme_aware(self):
        aware = [r["path"] for r in self.census["surfaces"] if r["theme_aware"]]
        self.assertEqual(
            aware, [ui.SELF_REL],
            "the set of theme-aware surfaces changed to {} — if another page learned to "
            "answer prefers-color-scheme that is a real fix; record it and "
            "supersede".format(aware))

    def test_exactly_one_surface_shares_the_tokens(self):
        sharing = [r["path"] for r in self.census["surfaces"] if r["shares_tokens"]]
        self.assertEqual(
            sharing, [ui.SELF_REL],
            "surfaces referencing {} changed to {} — adoption is the point, so this "
            "failing upward means the study needs re-measuring".format(
                ui.TOKENS_HREF, sharing))

    def test_one_surface_still_needs_an_external_host(self):
        """F216: `ctx graph` pulls d3 from a CDN this repo often cannot reach."""
        external = {r["path"]: r["external_hosts"] for r in self.census["surfaces"]
                    if r["external_hosts"]}
        self.assertEqual(
            external, {"tools/ctx.py": ["cdnjs.cloudflare.com"]},
            "the set of surfaces with external dependencies changed: {}".format(external))

    def test_the_lab_stylesheet_is_three_drifted_copies(self):
        variants = ui.css_block_variants()
        files = sorted(f for group in variants.values() for f in group)
        self.assertEqual(len(files), 3, "the #080b12 family changed size: {}".format(files))
        self.assertEqual(
            len(variants), 3,
            "the three copied lab stylesheets are now {} distinct string(s), not 3. One "
            "means they were unified (good — supersede); more means the drift "
            "grew".format(len(variants)))

    def test_the_live_dashboard_is_fenced_and_never_imported(self):
        source = (ROOT / "tools" / "research_ui.py").read_text(encoding="utf-8")
        self.assertNotIn("import fastapi", source)
        self.assertNotIn("from live", source)
        self.assertFalse(self.by_path["live/templates/dashboard.html"]["served_here"])

    def test_luminance_decides_the_theme_not_a_hand_written_label(self):
        """Non-vacuity: the derivation must actually separate the surfaces."""
        self.assertGreater(ui.relative_luminance("#f5f7fa"), 0.5)
        self.assertLess(ui.relative_luminance("#080b12"), 0.5)
        dark = [r for r in self.census["surfaces"] if r["themes"] == ["dark"]]
        light = [r for r in self.census["surfaces"] if r["themes"] == ["light"]]
        self.assertTrue(dark and light,
                        "every surface landed in one theme bucket — the derivation is "
                        "not discriminating and the column means nothing")


class TheRendererPredicatesAreRealPredicatesTests(unittest.TestCase):
    """A gate that always opens is not a gate; one that never opens is dead code."""

    @classmethod
    def setUpClass(cls):
        cls.nodes = sorted(ui.corpus().nodes)
        cls.contexts = [ui.node_context(n) for n in cls.nodes]

    def test_the_keys_are_unique(self):
        self.assertEqual(len(ui.RENDERER_KEYS), len(set(ui.RENDERER_KEYS)))
        self.assertEqual(len(ui.RENDERERS), 6)

    def test_every_renderer_applies_somewhere(self):
        for renderer in ui.RENDERERS:
            hits = sum(1 for c in self.contexts if renderer["unavailable"](c) is None)
            self.assertGreater(
                hits, 0,
                "renderer '{}' applies to no node in the whole web — it is dead code, "
                "or its predicate is wrong".format(renderer["key"]))

    def test_every_renderer_except_provenance_declines_somewhere(self):
        for renderer in ui.RENDERERS:
            misses = sum(1 for c in self.contexts
                         if renderer["unavailable"](c) is not None)
            if renderer["key"] == "provenance":
                self.assertEqual(
                    misses, 0,
                    "provenance stopped applying to every node — it is the one rendering "
                    "that must always work")
            else:
                self.assertGreater(
                    misses, 0,
                    "renderer '{}' applies to EVERY node — a predicate that never "
                    "declines is not gating anything".format(renderer["key"]))

    def test_a_declined_renderer_always_states_a_reason(self):
        for c in self.contexts:
            for renderer, reason in ui.applicable(c):
                if reason is not None:
                    self.assertIsInstance(reason, str)
                    self.assertGreater(
                        len(reason), 20,
                        "renderer '{}' declined {} without saying why — a chart that "
                        "omits itself silently reads as 'no such data'".format(
                            renderer["key"], c["id"]))

    def test_most_nodes_support_more_than_provenance_alone(self):
        """If almost nothing but provenance ever applied, the view would be pointless."""
        rich = [c["id"] for c in self.contexts if len(ui.applicable_keys(c)) >= 3]
        self.assertGreater(
            len(rich), 40,
            "only {} nodes support three or more renderings — the node view has become "
            "a provenance viewer".format(len(rich)))

    def test_every_applying_renderer_emits_parseable_markup(self):
        sample = [ui.node_context(n) for n in
                  ("F229", "F230", "F226", "F228", "F211", "F17", "D6", "H44")]
        for c in sample:
            for renderer, reason in ui.applicable(c):
                if reason is not None:
                    continue
                out = renderer["render"](c)
                self.assertTrue(out.strip(), "{}/{} rendered nothing".format(
                    c["id"], renderer["key"]))
                for svg in re.findall(r"<svg.*?</svg>", out, re.S):
                    ET.fromstring(svg)          # raises on malformed SVG


class TheKnownBindingsTests(unittest.TestCase):
    """The specific claims the study makes about specific nodes."""

    def test_f229_supports_five_of_six(self):
        keys = ui.applicable_keys(ui.node_context("F229"))
        self.assertEqual(
            sorted(keys),
            ["bounds", "provenance", "reachability", "threshold", "verdict"],
            "F229's rendering set changed to {} — the parity census is the worked "
            "example for four of the six patterns".format(sorted(keys)))

    def test_f230_binds_its_study_through_the_reverse_citation(self):
        """The direction that matters: the doc names the node, not the other way."""
        c = ui.node_context("F230")
        self.assertIn("docs/research/LIVE_backtest_parity_census.md", c["docs"])
        self.assertNotIn(
            "docs/research/LIVE_backtest_parity_census.md", c["body"],
            "F230's body now names its own study — the reverse-citation path this index "
            "exists for is no longer exercised by this node; pick another example")
        self.assertIn("threshold", ui.applicable_keys(c))

    def test_the_threshold_sweep_spans_more_than_a_decade_so_log_engages(self):
        _table, xs, _ys, _c = ui._threshold_table(ui.node_context("F230"))
        self.assertGreater(
            max(xs) / min(xs), 10,
            "the sigma sweep no longer spans a decade, so the log x-scale silently "
            "reverts to linear — re-check that the low-sigma points stay separable")

    def test_the_verdict_rows_are_labelled_by_dimension(self):
        label, rows, source = ui._verdict_rows(ui.node_context("F229"))
        self.assertEqual(label, "verdict")
        self.assertIn("live_backtest_parity.json", source)
        names = [r[0] for r in rows]
        self.assertIn("entry regime gate", names,
                      "parity rows are no longer labelled by `dimension` — check "
                      "_NAME_KEYS, or rows are being labelled by a compared VALUE")

    def test_the_spread_plot_has_a_categorical_axis_not_a_numeric_one(self):
        table, labels, vals, _c = ui._spread_table(ui.node_context("F211"))
        self.assertIsNotNone(table)
        self.assertEqual(len(labels), len(vals))
        self.assertIsNone(ui.as_number(labels[0]),
                          "the spread plot's first column parses as a number — that is "
                          "a threshold sweep, and the two renderings would collide")


class TheDerivedTotalIsNotDrawnAsAClassTests(unittest.TestCase):
    """`dead_to_shipping` is `tests-only` + `unreferenced`, not a fifth class."""

    def test_the_config_census_derived_total_is_detected(self):
        counts = json.loads((DATA / "config_reachability.json").read_text(
            encoding="utf-8"))["counts"]
        self.assertIn("dead_to_shipping", counts)
        self.assertEqual(counts["dead_to_shipping"],
                         counts["tests-only"] + counts["unreferenced"])
        self.assertIn(
            "dead_to_shipping", ui._derived_keys(counts),
            "the derived total is no longer detected — drawing it as a segment "
            "double-counts {} of the constants".format(counts["dead_to_shipping"]))

    def test_it_does_not_fire_on_the_parity_tally(self):
        """The false positive it must not have: COINCIDENT(2) == AGREE(0) + DORMANT(2)."""
        counts = json.loads((DATA / "live_backtest_parity.json").read_text(
            encoding="utf-8"))["counts"]
        self.assertEqual(counts["AGREE"], 0)
        self.assertEqual(
            ui._derived_keys(counts), {},
            "a real class was dropped as 'derived' — zero-valued summands are back, and "
            "any class equal to another can now explain itself away")

    def test_the_column_census_has_no_derived_total(self):
        counts = json.loads((DATA / "column_reachability.json").read_text(
            encoding="utf-8"))["counts"]
        self.assertEqual(ui._derived_keys(counts), {})

    def test_the_drawn_partition_sums_to_the_real_population(self):
        c = ui.node_context("F226")
        _path, items, derived = ui._counts_artifact(c)
        self.assertIn("dead_to_shipping", derived)
        self.assertEqual(sum(v for _k, v in items), 203,
                         "the config partition no longer sums to the 203 constants F226 "
                         "measured")


class TheRatchetExtractionTests(unittest.TestCase):
    def test_a_floor_above_its_ceiling_is_not_a_ratchet(self):
        bounds = [
            {"expr": "share", "op": "<", "value": 0.02, "test": "t.py", "func": "a"},
            {"expr": "share", "op": ">", "value": 0.05, "test": "t.py", "func": "b"},
        ]
        rats, used = ui.ratchets(bounds)
        self.assertEqual(
            rats, [],
            "an inverted band is being drawn as a ratchet again — those are two bounds "
            "under two different conditions, not a range")
        self.assertEqual(used, 0)

    def test_a_genuine_pair_is_a_ratchet(self):
        bounds = [
            {"expr": "n", "op": "≥", "value": 26, "test": "t.py", "func": "a"},
            {"expr": "n", "op": "≤", "value": 29, "test": "t.py", "func": "b"},
        ]
        rats, used = ui.ratchets(bounds)
        self.assertEqual(len(rats), 1)
        self.assertEqual((rats[0]["floor"], rats[0]["ceiling"]), (26, 29))
        self.assertEqual(used, 2)

    def test_the_parity_guard_still_contains_the_conditional_pair(self):
        """Non-vacuity: the inverted case must exist in the real corpus, not just here."""
        bounds = ui.guard_bounds("tests/test_live_backtest_parity.py")
        share = [b for b in bounds if b["expr"] == "share"]
        ops = {b["op"] for b in share}
        self.assertTrue(
            {"<", ">"} <= ops,
            "test_live_backtest_parity.py no longer bounds `share` in both directions — "
            "the worked example for conditional-vs-ratchet is gone; find another or "
            "retire the distinction")

    def test_bounds_are_read_from_the_ast_not_from_prose(self):
        bounds = ui.guard_bounds("tests/test_live_backtest_parity.py")
        exprs = {b["expr"] for b in bounds}
        self.assertIn("getattr(config, 'MAX_TRADE_BARS', None)", exprs)
        self.assertTrue(any(b["value"] == 8 for b in bounds))
        self.assertTrue(any(b["value"] == 10 for b in bounds))


class TheRollupExclusionTests(unittest.TestCase):
    """A file about many nodes is a source for none of them."""

    @classmethod
    def setUpClass(cls):
        cls.rollups = dict(ui.corpus().rollups())

    def test_the_obvious_roll_ups_are_excluded(self):
        for rel in ("docs/research/README.md",
                    "docs/research/EPI00_epistemic_audit.md"):
            self.assertIn(rel, self.rollups,
                          "{} is no longer excluded — its tables can now be drawn as "
                          "any node it happens to mention".format(rel))

    def test_a_single_subject_study_is_not_excluded(self):
        self.assertNotIn(
            "docs/research/LIVE_backtest_parity_census.md", self.rollups,
            "the parity census was classified as a roll-up — the cutoff is too tight "
            "and F229/F230 just lost their evidence")

    def test_the_cutoff_still_separates_the_two_populations(self):
        self.assertEqual(ui.ROLLUP_CITATION_LIMIT, 8)
        self.assertGreater(
            min(self.rollups.values()), ui.ROLLUP_CITATION_LIMIT,
            "an excluded file cites fewer nodes than the limit — the filter is not "
            "doing what it says")

    def test_the_exclusion_list_has_not_run_away(self):
        self.assertLessEqual(
            len(self.rollups), 30,
            "{} files are now excluded as roll-ups — either the corpus changed shape or "
            "the cutoff is swallowing real studies".format(len(self.rollups)))

    def test_no_node_loses_every_source_to_the_filter(self):
        starved = [n for n in ("F226", "F228", "F229", "F230", "F211")
                   if not ui.node_context(n)["docs"]]
        self.assertEqual(starved, [], "these nodes lost their study doc: {}".format(
            starved))


class TheRouteTableTests(unittest.TestCase):
    """`route` is pure over its arguments, so the whole server is testable unbound."""

    def test_the_core_pages_render(self):
        for path in ("/", "/web", "/surfaces", "/node/F229", "/health",
                     ui.TOKENS_HREF, "/api/surfaces", "/api/node/F230"):
            code, body, ctype = ui.route(path, {}, {})
            self.assertEqual(code, 200, "{} returned {}".format(path, code))
            self.assertTrue(body)
            self.assertTrue(ctype)

    def test_an_unknown_node_is_a_404_not_a_blank_page(self):
        code, body, _ct = ui.route("/node/F99999", {}, {})
        self.assertEqual(code, 404)
        self.assertIn("F99999", body)

    def test_an_unmounted_database_says_how_to_mount_it(self):
        code, body, _ct = ui.route("/events", {}, {})
        self.assertEqual(code, 503)
        self.assertIn("--event-db", body,
                      "the unmounted-view message no longer names the flag that mounts "
                      "it — an empty view that does not say why is the absence bug")

    def test_a_mounted_view_reaches_ctx_rather_than_a_second_implementation(self):
        """The point of the server: it owns no copy of these adapters."""
        source = (ROOT / "tools" / "research_ui.py").read_text(encoding="utf-8")
        for name in ("_event_ledger_response", "_corporate_action_response",
                     "_corporate_action_state_response", "_form25_population_response"):
            self.assertIn("ctx." + name, source)
            self.assertNotIn("def " + name, source,
                             "research_ui defines its own {} — that is a second copy of "
                             "a route adapter, the exact defect this server was built "
                             "to stop repeating".format(name))

    def test_every_page_wears_the_shared_stylesheet(self):
        for path in ("/", "/web", "/surfaces", "/node/F229"):
            _code, body, _ct = ui.route(path, {}, {})
            self.assertIn(ui.TOKENS_HREF, body,
                          "{} does not link the shared stylesheet".format(path))

    def test_pages_carry_no_hard_coded_colour(self):
        """Every colour must come from a token, or the token system is decorative.

        `/surfaces` is exempt and only `/surfaces`: it prints each surface's measured
        ground as a swatch, so the hexes on that page are the DATA, not styling.
        """
        for path in ("/", "/web", "/node/F229"):
            _code, body, _ct = ui.route(path, {}, {})
            found = sorted(set(HEX.findall(body)))
            self.assertEqual(
                found, [],
                "{} emits literal colour(s) {} — route them through /static/ui.css "
                "so the palette stays in one place".format(path, found))

    def test_the_filters_survive_a_round_trip(self):
        _code, body, _ct = ui.route("/web", {"kind": "H", "status": "current"}, {})
        self.assertIn("<option value=\"H\" selected>", body)
        _code2, body2, _ct2 = ui.route("/web", {"q": "zzzznomatch"}, {})
        self.assertIn("0 shown", body2)


if __name__ == "__main__":
    unittest.main()

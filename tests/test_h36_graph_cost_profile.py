"""H36 proposes caching 2% of the cost, and its estimate is 2.3x stale.

H36 asks for "an mtime/git-sha-invalidated cache or a `ctx graph --json` sidecar that can
NEVER serve stale epistemic data", naming `_manifest`, `_parse_web` and "impact/graph/
health/frontier re-walk the AST every call (~0.5s for a full graph build)". Measured on
the current repo (415 web nodes), the cost is almost entirely somewhere else:

    component                                  cost      H36's treatment
    _manifest()                               0.3 ms    named first
    _parse_web()                             23.5 ms    named second
    build_graph(include_code=False)          26.8 ms    —
    build_graph(include_code=True)         1161.3 ms    a subordinate clause
    _first_party_modules()                    1.7 ms    —

`cmd_health` takes ~1240 ms, of which web parsing is **47 ms — 4%**. The code-side AST
walk is **43x** the epistemic graph and ~98% of the total. So the two things H36 names as
caching targets are worth about 2% between them.

H36's own figure is stale too: "~0.5s for a full graph build" is now **1.16 s**, having
grown with the repo. Stale in the direction of *understating* the cost, which matters
because "current cost is modest" is the stated reason it is low priority.

**And the safety argument inverts the proposal.** H36's constraint — never serve stale
epistemic data — is exactly right, and it applies to the *cheap* half. This project's
discipline is that a guard fails when a claim stops being true; a cached research web
would let a guard pass against data that no longer exists. Meanwhile the code AST is
derived purely from file contents, is trivially mtime-invalidated, and is 98% of the cost.

So the remedy should be the other way round from how H36 states it: **never cache the
epistemic layer — the saving is negligible and the risk is categorical — and cache the
code AST, where the cost actually is.**

Nothing is implemented here. H36 says "low priority — correctness first", and after this
measurement that judgement stands; what changes is *which* thing would be cached if anyone
did. Timings are wall-clock on this machine and will vary; the guard asserts the *ratios*,
which are what the argument rests on.
"""
import io
import sys
import time
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import ctx  # noqa: E402


def median_ms(fn, n=3):
    """Median of n runs, so one scheduler hiccup does not decide a ratio."""
    samples = []
    for _ in range(n):
        start = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - start) * 1000)
    return sorted(samples)[len(samples) // 2]


class TheEpistemicLayerIsCheapTests(unittest.TestCase):
    def test_parsing_the_web_is_tens_of_milliseconds(self):
        cost = median_ms(ctx._parse_web)
        self.assertLess(
            cost, 250,
            "parsing the research web now costs {:.0f} ms — it has become worth "
            "caching, which would reopen H36's proposal as stated".format(cost))

    def test_the_manifest_read_is_negligible(self):
        self.assertLess(median_ms(ctx._manifest, 5), 20)

    def test_the_web_is_large_enough_for_the_measurement_to_mean_something(self):
        nodes, _ = ctx._parse_web()
        self.assertGreater(
            len(nodes), 300,
            "the web shrank below 300 nodes — the 'cheap even at this size' claim "
            "needs re-measuring")


class TheCodeWalkIsTheCostTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.idea_only = median_ms(lambda: ctx.build_graph(include_code=False))
        cls.with_code = median_ms(lambda: ctx.build_graph(include_code=True))

    def test_including_code_is_an_order_of_magnitude_more(self):
        ratio = self.with_code / self.idea_only
        self.assertGreater(
            ratio, 8.0,
            "the code-side walk is no longer dominant ({:.1f}x the idea graph) — H36's "
            "targets may now be worth caching after all".format(ratio))

    def test_the_module_listing_is_not_what_costs(self):
        """So the expense is the per-module AST parse, not finding the files."""
        listing = median_ms(lambda: ctx._first_party_modules(include_tests=False))
        self.assertLess(
            listing, self.with_code / 10,
            "listing modules is now a large share of the walk — the cacheable unit "
            "would be different")

    def test_health_spends_almost_all_its_time_outside_the_web(self):
        calls = {"n": 0}
        original = ctx._parse_web

        def counting():
            calls["n"] += 1
            return original()

        ctx._parse_web = counting
        try:
            start = time.perf_counter()
            with redirect_stdout(io.StringIO()):
                ctx.cmd_health(types.SimpleNamespace())
            total = (time.perf_counter() - start) * 1000
        finally:
            ctx._parse_web = original
        web_share = calls["n"] * median_ms(ctx._parse_web) / total
        self.assertGreater(calls["n"], 0, "cmd_health no longer parses the web at all")
        self.assertLess(
            web_share, 0.25,
            "web parsing is now {:.0%} of cmd_health — if it passed 25%, caching it "
            "would start to matter".format(web_share))


class H36sOwnEstimateIsStaleTests(unittest.TestCase):
    def test_the_full_graph_build_exceeds_the_recorded_half_second(self):
        cost = median_ms(lambda: ctx.build_graph(include_code=True))
        self.assertGreater(
            cost, 500,
            "the full graph build is back under H36's recorded ~0.5s ({:.0f} ms) — its "
            "estimate is no longer stale; drop this assertion".format(cost))

    def test_the_node_still_records_that_estimate(self):
        web = (ROOT / "RESEARCH_WEB.md").read_text(encoding="utf-8")
        start = web.index("### H36 ")
        body = web[start:web.index("\n### ", start + 5)]
        self.assertIn(
            "~0.5s for a full graph build", body,
            "H36's estimate was updated — good; re-measure and retire this test")
        self.assertIn("current cost is modest", body,
                      "H36 no longer justifies its low priority by the cost being "
                      "modest, which is the claim the measurement bears on")


class TheSafetyArgumentInvertsTheProposalTests(unittest.TestCase):
    """Why the cheap half is the half that must never be cached."""

    def test_the_web_is_the_data_guards_are_asserted_against(self):
        nodes, _ = ctx._parse_web()
        self.assertIn("F208", nodes, "the newest findings are read from the live web")
        superseded = [k for k, n in nodes.items() if ctx._is_superseded(n)]
        self.assertTrue(
            superseded,
            "no node is superseded — the staleness a cache could freeze would have "
            "no worked example")

    def test_ctx_currently_caches_nothing(self):
        source = (ROOT / "tools" / "ctx.py").read_text(encoding="utf-8")
        for token in ("lru_cache", "functools.cache", "_CACHE ="):
            self.assertNotIn(
                token, source,
                "ctx.py now caches something ({!r}) — check it is the code walk and "
                "not the epistemic layer".format(token))

    def test_the_code_side_is_derived_purely_from_file_contents(self):
        """Which is what makes mtime invalidation sound for it and not for the web."""
        source = (ROOT / "tools" / "ctx.py").read_text(encoding="utf-8")
        self.assertIn("def _first_party_modules(", source)
        self.assertIn("ast.parse", source,
                      "the code side no longer parses ASTs — re-derive what would be "
                      "cached")


if __name__ == "__main__":
    unittest.main()

"""H40: don't embed the served map in the trading dashboard — it loads a CDN script.

Study: `docs/research/CTX_served_map_exposure.md`.

H40 proposes adding a `/context` route to `live/dashboard.py` (port 8000) so the context
map appears alongside the trading monitor, noting `live/` is edit-fenced, and offers a
"cheaper alternative: just iframe/link to `ctx serve`".

Auditing what would be embedded settled it. `ctx serve` and `ctx graph --html` emit the
same page, and that page contains exactly one external reference:

    <script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js"></script>

with **no `integrity` attribute**. Three consequences, in the order they matter:

1. **Embedding it would put third-party script on the trading host's origin.** The
   dashboard is served by the armed paper-trading deployment. An iframe is better than a
   route (separate origin) but a `<script>` pulled into the dashboard page itself is not.
   `ctx serve` deliberately runs on its own port for exactly this reason.
2. **It contradicts the layer's stated design.** F27 records the context layer as a
   "stdlib, read-only, CI-guarded ctx CLI **by design**". Everything else in it is
   dependency-free; the served map is the single exception, and it is undocumented.
3. **It fails silently offline.** This repo is routinely run network-blocked. The page
   rendered its whole chrome — header, legend, controls — over an empty canvas, which
   reads as "the graph has no nodes" rather than "the layout library never loaded". Same
   absence-flag family as F155/F159/F188/F204.

**RESOLVED 2026-08-07 by vendoring.** d3 7.8.5 now ships inline from
`tools/vendor/d3.v7.8.5.min.js`, so the served page has *zero* external origins. That
disposes of all three consequences at once: nothing third-party executes on any origin, the
"dependency-free by design" claim in F27 is true again with no exception, and the offline
case cannot arise because there is nothing to fetch. The missing `integrity` hash — recorded
above as the one thing NOT fixed — is moot: SRI protects a fetch, and there is no fetch.

The four guards that pinned the CDN in place were left asserting it afterwards, so they
failed for eight commits saying, correctly, "the d3 CDN reference is gone... supersede this
finding". This file is that supersession. They are **inverted**, not deleted: the property
worth guarding did not disappear when the dependency did, it flipped. "Exactly one external
origin, and here is which" becomes "no external origins at all", which is a strictly stronger
invariant and the one that makes embedding safe.

The fail-loud check is kept and re-aimed. d3 can still fail to evaluate — a truncated vendor
file, a CSP that blocks inline script — and an empty canvas under a fully-drawn chrome still
reads as "this graph has no nodes". What changed is the *cause* the banner may name: telling
a reader to check their network would now send them after a problem that cannot exist.

Verdict on H40: the stated blocker is **gone**. Embedding the map in the dashboard is no
longer a dependency question. The fence on `live/` is unrelated to it and still holds, which
the last class here still checks.
"""
import inspect
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import ctx  # noqa: E402

PAGE = ctx._GRAPH_HTML
EXTERNAL = re.compile(r"""(?:src|href)=["'](https?://[^"']+)["']""")


class TheServedPageHasNoExternalDependencyTests(unittest.TestCase):
    def test_it_reaches_no_external_origin_at_all(self):
        origins = {re.match(r"https?://[^/]+", u).group(0)
                   for u in EXTERNAL.findall(PAGE)}
        self.assertEqual(
            origins, set(),
            "the served map grew {} external origin(s): {}. Every one of them runs script "
            "or styles in the viewer's browser, and this page is linked from a trading "
            "host — vendor it under tools/vendor/ instead, the way d3 is".format(
                len(origins), sorted(origins)))

    def test_d3_is_vendored_into_the_page_rather_than_fetched(self):
        """The inverse of the guard this replaced. Without the body actually inlined, "no
        external origins" would also be true of a page that had simply lost its graph."""
        self.assertNotIn("cdnjs.cloudflare.com", PAGE)
        self.assertIn("d3.v7.8.5.min.js", inspect.getsource(ctx._d3_source),
                      "the vendored d3 file is no longer named in _d3_source")
        self.assertTrue((ROOT / "tools" / "vendor" / "d3.v7.8.5.min.js").is_file(),
                        "the vendored d3 file is gone from the repo")
        # PAGE is the TEMPLATE, which carries the `__D3__` placeholder rather than d3 itself;
        # asserting a byte size against it would be asserting against the wrong artifact.
        # What the viewer receives is the rendered page, so that is what gets measured.
        self.assertIn("__D3__", PAGE, "the d3 injection point is gone from the template")
        d3 = ctx._d3_source()
        self.assertGreater(
            len(d3), 200_000,
            "the vendored d3 is only {} bytes — the real minified 7.8.5 is ~280KB, so this "
            "is a truncated or placeholder file and the map would render an empty canvas "
            "under a full chrome".format(len(d3)))
        self.assertNotIn("__D3__", d3)

    def test_subresource_integrity_is_moot_and_no_script_src_survives(self):
        """SRI protects a fetch. There is no fetch, so the thing to guard is that no
        `<script src=…>` comes back at all — an SRI-less one would be the old exposure and
        an SRI-bearing one would be a new fetch nobody decided to make."""
        self.assertEqual(
            re.findall(r"<script[^>]+\bsrc=", PAGE), [],
            "the served map loads an external script again")


class ThePageFailsLoudWhenTheCdnIsUnreachableTests(unittest.TestCase):
    def test_the_script_checks_that_d3_loaded(self):
        self.assertIn(
            "typeof d3 === 'undefined'", PAGE,
            "the d3-load check was removed — an offline viewer sees a fully-rendered "
            "page over an empty canvas and reads it as 'no nodes'")

    def test_the_banner_names_the_cause_not_just_the_symptom(self):
        """It must no longer blame the network — there is nothing to fetch, so sending the
        reader to check their connection points them at a problem that cannot exist. The
        actionable statement now is that the library is bundled, so a failure here is the
        page's own, and that the node data IS present so the reader knows what they are
        NOT looking at."""
        self.assertIn('id="offline"', PAGE)
        banner = PAGE.split('id="offline"')[1][:600]
        self.assertNotIn("cdnjs", banner)
        self.assertIn("bundled", banner)
        self.assertIn("not a network problem", banner)

    def test_the_check_runs_before_the_data_is_used(self):
        guard = PAGE.index("typeof d3 === 'undefined'")
        data = PAGE.index("const D=__DATA__")
        self.assertLess(
            guard, data,
            "the d3 guard now runs after the graph data is bound — it would throw "
            "before it could show the banner")

    def test_the_canvas_is_hidden_so_empty_is_never_shown_as_success(self):
        block = PAGE[PAGE.index("typeof d3 === 'undefined'"):][:400]
        self.assertIn("wrap", block)
        self.assertIn("none", block)


class TheServerItselfIsAFixedRouteAllowlistTests(unittest.TestCase):
    """The reason a LINK is acceptable even though embedding is not."""

    @classmethod
    def setUpClass(cls):
        cls.source = ctx.cmd_serve.__doc__ or ""
        import inspect
        cls.body = inspect.getsource(ctx.cmd_serve)

    def test_it_serves_no_file_from_disk(self):
        for token in ("SimpleHTTPRequestHandler", "open(self.path", "send_file",
                      "translate_path"):
            self.assertNotIn(
                token, self.body,
                "ctx serve now has a filesystem path ({}) — it was a fixed-route "
                "allowlist, which is what made a link to it safe".format(token))

    def test_every_route_is_an_explicit_literal(self):
        paths = set(re.findall(r'path (?:==|in) \(?["\']([^"\']+)', self.body))
        self.assertIn("/health", paths)
        self.assertTrue(paths, "no literal routes found — the handler was restructured")

    def test_unknown_paths_are_refused(self):
        self.assertIn("404", self.body)

    def test_it_only_answers_get(self):
        self.assertIn("def do_GET", self.body)
        for verb in ("do_POST", "do_PUT", "do_DELETE"):
            self.assertNotIn(
                verb, self.body,
                "ctx serve now handles {} — it was read-only, and read-only is the "
                "premise of every claim in this file".format(verb))


class TheDashboardWasNotTouchedTests(unittest.TestCase):
    def test_no_context_route_was_added_to_the_fenced_dashboard(self):
        dash = (ROOT / "live" / "dashboard.py").read_text(encoding="utf-8")
        self.assertNotIn(
            "/context", dash,
            "a /context route appeared in the fenced dashboard — H40 was implemented; "
            "confirm d3 was vendored first, then supersede this finding")

    def test_the_dashboard_is_still_fenced(self):
        import json
        policy = json.loads((ROOT / "context_map.json").read_text("utf-8"))["edit_policy"]
        self.assertIn("live/", policy["deny"])


if __name__ == "__main__":
    unittest.main()

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

Fixed here: (3), which needs no network — the page now checks `typeof d3` and shows a
banner naming the CDN and the likely cause. **Not** fixed: the missing `integrity` hash.
Adding SRI requires the real digest for that exact file, the CDN is unreachable from this
environment, and a fabricated hash would *block* the script and break the page for
everyone. That is recorded as the next action, not guessed at.

Verdict on H40: **retire as stated.** Keep the map on its own port. If anyone does want it
in the dashboard, vendoring d3 is a prerequisite, not a detail — and the fence should hold
until then.

Guards below are bidirectional: they fail if the CDN dependency disappears (good news —
retire the finding), if the fail-loud check is removed, and if the served page grows any
*additional* external origin.
"""
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import ctx  # noqa: E402

PAGE = ctx._GRAPH_HTML
EXTERNAL = re.compile(r"""(?:src|href)=["'](https?://[^"']+)["']""")


class TheServedPageHasExactlyOneExternalDependencyTests(unittest.TestCase):
    def test_it_is_the_d3_cdn_and_nothing_else(self):
        origins = {re.match(r"https?://[^/]+", u).group(0)
                   for u in EXTERNAL.findall(PAGE)}
        self.assertEqual(
            origins, {"https://cdnjs.cloudflare.com"},
            "the served map's external origins changed to {} — every one of them runs "
            "script or styles in the viewer's browser; re-audit before embedding "
            "anything anywhere".format(sorted(origins)))

    def test_the_dependency_is_still_d3(self):
        urls = EXTERNAL.findall(PAGE)
        self.assertTrue(
            any("d3" in u for u in urls),
            "the d3 CDN reference is gone. If d3 was vendored or dropped, H40's blocker "
            "is resolved — supersede this finding and re-open the embedding question.")

    def test_there_is_still_no_subresource_integrity(self):
        """Pinned so the day someone adds it, this test says so rather than staying quiet."""
        script = [l for l in PAGE.splitlines() if "cdnjs.cloudflare.com" in l]
        self.assertTrue(script)
        self.assertNotIn(
            "integrity=", script[0],
            "an integrity hash was added — verify it against the real file, then delete "
            "this assertion and update docs/research/CTX_served_map_exposure.md")


class ThePageFailsLoudWhenTheCdnIsUnreachableTests(unittest.TestCase):
    def test_the_script_checks_that_d3_loaded(self):
        self.assertIn(
            "typeof d3 === 'undefined'", PAGE,
            "the d3-load check was removed — an offline viewer sees a fully-rendered "
            "page over an empty canvas and reads it as 'no nodes'")

    def test_the_banner_names_the_cause_not_just_the_symptom(self):
        self.assertIn('id="offline"', PAGE)
        self.assertIn("cdnjs.cloudflare.com", PAGE.split('id="offline"')[1][:600],
                      "the offline banner no longer names the host it failed to reach, "
                      "which is the only actionable part of the message")

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

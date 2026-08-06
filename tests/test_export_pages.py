"""Guards for tools/export_pages.py and the GitHub Pages workflow.

The failure modes these hold shut:
  * an exported page still linking a server route ("/screen?preset=…"), which on
    GitHub Pages is a silent 404;
  * the footer keeping the server's "rendered … at request time" claim on a page
    that is actually a frozen snapshot;
  * the workflow drifting away from the export script it exists to run;
  * anything under live/** leaking into the published site.
"""
import os
import re
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (REPO, os.path.join(REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import export_pages  # noqa: E402
import stock_screener as sc  # noqa: E402


class ExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.td = tempfile.TemporaryDirectory()
        cls.written = export_pages.export(cls.td.name)
        cls.pages = {}
        for name in cls.written:
            if name.endswith(".html"):
                with open(os.path.join(cls.td.name, name), encoding="utf-8") as fh:
                    cls.pages[name] = fh.read()

    @classmethod
    def tearDownClass(cls):
        cls.td.cleanup()

    def test_every_preset_gets_a_page_plus_index_map_and_css(self):
        expected = {"index.html", "map.html", os.path.join("static", "ui.css")}
        expected |= {"screen-{}.html".format(k) for k in sc.PRESETS}
        self.assertEqual(set(self.written), expected)

    def test_no_page_still_links_a_server_route(self):
        for name, text in self.pages.items():
            if name == "map.html":
                continue    # self-contained, no internal routes by construction
            self.assertEqual(re.findall(r'href="/[^"]*"', text), [], name)

    def test_preset_buttons_link_the_static_files(self):
        text = self.pages["screen-low_pe_high_growth.html"]
        for key in sc.PRESETS:
            self.assertIn('href="screen-{}.html"'.format(key), text)

    def test_the_index_is_the_chaos_screener(self):
        self.assertIn("bucketGrid", self.pages["index.html"])
        self.assertIn("Mock prices", self.pages["index.html"])   # demo data stays labeled

    def test_the_footer_tells_the_truth_about_being_a_snapshot(self):
        for name, text in self.pages.items():
            if name == "map.html":
                continue
            self.assertNotIn("at request time", text, name)
            self.assertIn("static snapshot built", text, name)

    def test_nothing_from_live_is_published(self):
        """The fence is about FILES and data, not mentions: research prose freely
        cites `live/state.db` by name (that text is already public in the repo), but
        no file under live/** may be exported and the export must import nothing
        from live (so it cannot read broker state even by accident)."""
        self.assertFalse(any(n.startswith("live") for n in self.written))
        with open(os.path.join(REPO, "tools", "export_pages.py"),
                  encoding="utf-8") as fh:
            source = fh.read()
        self.assertNotIn("import live", source)
        self.assertNotIn("from live", source)

    def test_missing_snapshot_exports_the_absence_panel_not_an_empty_table(self):
        if sc.load_snapshot() is None:
            self.assertIn("No snapshot fetched",
                          self.pages["screen-low_pe_high_growth.html"])


class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(REPO, ".github", "workflows", "pages.yml"),
                  encoding="utf-8") as fh:
            cls.wf = fh.read()

    def test_it_runs_the_export_script_this_suite_tests(self):
        self.assertIn("python tools/export_pages.py --out _site", self.wf)
        self.assertIn("path: _site", self.wf)

    def test_the_fetch_is_best_effort_so_a_yahoo_outage_cannot_block_publishing(self):
        fetch = self.wf.index("stock_screener.py fetch")
        block = self.wf[max(0, fetch - 400):fetch]
        self.assertIn("continue-on-error: true", block)

    def test_it_deploys_from_the_default_branch_and_refreshes_on_a_schedule(self):
        self.assertIn("branches: [development]", self.wf)
        self.assertIn("schedule:", self.wf)
        self.assertIn("workflow_dispatch:", self.wf)

    def test_it_has_exactly_the_pages_permissions_and_no_write_to_contents(self):
        self.assertIn("contents: read", self.wf)
        self.assertIn("pages: write", self.wf)
        self.assertIn("id-token: write", self.wf)
        self.assertNotIn("contents: write", self.wf)


if __name__ == "__main__":
    unittest.main()

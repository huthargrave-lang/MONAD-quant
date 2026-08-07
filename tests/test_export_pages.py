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
import research_ui  # noqa: E402
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

    def test_every_preset_gets_a_page_plus_the_surfaces_the_rail_offers(self):
        expected = {"index.html", "lenses.html", "buckets.html", "recommend.html",
                    "overview.html", "web.html", "web-groups.html", "surfaces.html",
                    "map.html", os.path.join("static", "ui.css")}
        expected |= {"screen-{}.html".format(k) for k in sc.PRESETS}
        nodes = {n for n in self.written if n.startswith("node-")}
        self.assertTrue(nodes, "the research web must be drillable, not a contents page")
        self.assertEqual(set(self.written) - nodes, expected)

    def test_the_published_rail_matches_the_servers_views(self):
        """A published site that lists different views from the app it was built from
        reads as a different application. The one deliberate omission is Mounted data:
        those views need optional SQLite mounts that cannot exist on a static host."""
        import research_ui  # noqa: PLC0415 — test-local, keeps module import cheap
        served = [label for _href, label in research_ui._nav_view_items()]
        published = [label for _href, label, _key in export_pages._STATIC_VIEWS]
        self.assertEqual(served, published)
        for page in ("index.html", "overview.html", "web.html"):
            self.assertNotIn("no db", self.pages[page], page)

    def test_no_page_still_links_a_server_route(self):
        for name, text in self.pages.items():
            if name == "map.html":
                continue    # self-contained, no internal routes by construction
            self.assertEqual(re.findall(r'href="/[^"]*"', text), [], name)

    def test_preset_buttons_link_the_static_files(self):
        text = self.pages["screen-low_pe_high_growth.html"]
        for key in sc.PRESETS:
            self.assertIn('href="screen-{}.html"'.format(key), text)

    def test_the_index_is_the_combined_screener_with_its_data_baked_in(self):
        """The server injects the snapshot at request time; nothing does that on Pages,
        so an un-baked export would publish the page's own absence state forever."""
        text = self.pages["index.html"]
        self.assertIn('href="buckets.html"', text)
        self.assertIn("Low P/E", text)
        self.assertIn("__DRAFT_LIVE__", text)

    def _baked_payload(self):
        import json
        import re as _re
        m = _re.search(r"window\.__DRAFT_LIVE__ = (\{.*?\});</script>",
                       self.pages["index.html"], _re.S)
        self.assertIsNotNone(m, "no payload baked into index.html")
        return json.loads(m.group(1))

    def test_no_third_party_headline_text_is_republished(self):
        """Tone scores are ours and ship; the documents behind them are third-party copy and
        are not ours to publish on a public site, so the baked payload carries none."""
        payload = self._baked_payload()
        for source, by_ticker in (payload.get("headlines") or {}).items():
            self.assertEqual(
                [d for docs in by_ticker.values() for d in docs], [], source)

    def test_every_source_survives_the_withholding(self):
        """This is what the test above cannot see. It iterates whatever sources ARE in the
        exported dict, so a source dropped entirely passes it vacuously — which is exactly
        what happened: the withholding was `= {"bloomberg": {}, "reddit": {}}`, a whole-dict
        assignment, and Yahoo's 123 tickers of text vanished as COLLATERAL rather than by the
        stated policy. Withheld and never-fetched are different facts and the page renders
        them differently, so every source the server has must still be a key here."""
        live = research_ui._screener_combined_draft_payload()
        self.assertEqual(
            sorted((self._baked_payload().get("headlines") or {})),
            sorted((live.get("headlines") or {})),
            "the exported build dropped a whole headline source instead of emptying it")

    def test_the_withheld_notice_is_carried_and_rendered(self):
        """A promise the code does not keep is worse than no promise: `headlines_withheld`
        was written by this exporter and read by nothing, so a static reader saw empty tiles
        with no account of why. It has to reach the payload AND be rendered."""
        notice = self._baked_payload().get("headlines_withheld")
        self.assertTrue(notice, "no withheld notice in the baked payload")
        page = self.pages["index.html"]
        self.assertIn("HEADLINES_WITHHELD", page,
                      "the page does not read the notice it is shipped")
        self.assertIn("live.headlines_withheld", page,
                      "the notice is never ingested from the payload")
        self.assertIn("documents withheld", page,
                      "no rendered state distinguishes withheld from absent")

    def test_a_source_either_carries_documents_or_carries_the_notice(self):
        """Per source, and this is the contract the whole change exists to hold: a reader
        looking at a tone of +0.30 over 12 documents and an empty tile must be told which of
        the two reasons applies."""
        payload = self._baked_payload()
        notice = payload.get("headlines_withheld")
        for source, by_ticker in (payload.get("headlines") or {}).items():
            docs = [d for docs in by_ticker.values() for d in docs]
            self.assertTrue(
                docs or notice,
                "{} carries neither its documents nor an explanation of their "
                "absence".format(source))

    def test_no_headline_string_survives_anywhere_in_the_page(self):
        """The payload is not the only way text could reach the file — a rendered card, an
        aria-label or a title attribute would republish it just as publicly."""
        live = research_ui._screener_combined_draft_payload()
        page = self.pages["index.html"]
        leaked = []
        for source, by_ticker in (live.get("headlines") or {}).items():
            for ticker, docs in by_ticker.items():
                for doc in docs:
                    head = (doc.get("h") or "")[:40]
                    if len(head) > 20 and head in page:
                        leaked.append("{}/{}: {}".format(source, ticker, head))
        self.assertEqual(leaked[:5], [], "headline text reached the published page")

    def test_buckets_page_is_the_sovereign_html_wireframe(self):
        text = self.pages["buckets.html"]
        self.assertIn("bucketGrid", text)
        self.assertIn("Select top heat", text)

    def test_the_footer_tells_the_truth_about_being_a_snapshot(self):
        for name, text in self.pages.items():
            if name in ("map.html", "buckets.html"):
                continue  # map is self-contained; buckets is the standalone mock HTML
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

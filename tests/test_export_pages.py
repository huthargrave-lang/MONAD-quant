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
        # Derived from the list, not written out: a fourth Basics page added to the server
        # and not published would otherwise pass here and leave the rail advertising it.
        expected |= {n for n, _l, _k in export_pages._STATIC_BASICS}
        nodes = {n for n in self.written if n.startswith("node-")}
        self.assertTrue(nodes, "the research web must be drillable, not a contents page")
        self.assertEqual(set(self.written) - nodes, expected)

    def test_the_published_rail_matches_the_servers_views(self):
        """A published site that lists different views from the app it was built from
        reads as a different application. The one deliberate omission is Mounted data:
        those views need optional SQLite mounts that cannot exist on a static host."""
        import research_ui  # noqa: PLC0415 — test-local, keeps module import cheap
        # Server-only views are excluded on both sides from ONE list
        # (`research_ui.SERVER_ONLY_VIEWS`). /sweep runs backtests in a subprocess, which
        # a static host cannot do, so publishing it would be a rail item that goes nowhere.
        served = [label for _href, label in research_ui._nav_view_items(False)]
        published = [label for _href, label, _key in export_pages._STATIC_VIEWS]
        self.assertEqual(served, published)
        # Basics is a second list and needs its own comparison — the check above reads
        # `_nav_view_items`, which does not carry it, so adding the section without this
        # would have left a whole rail group unguarded on the side it is published from.
        self.assertEqual([label for _href, label, _f in research_ui.BASICS_VIEWS],
                         [label for _name, label, _k in export_pages._STATIC_BASICS])
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
        # The buckets link was asserted here incidentally, via the rail. It is gone from the
        # rail on purpose now and the page it pointed at is still published — that pair is
        # checked by test_the_buckets_page_is_published_but_no_longer_advertised, which is
        # where it belongs. This test is about the payload being baked in.
        self.assertIn("Low P/E", text)
        self.assertIn("__DRAFT_LIVE__", text)

    def test_the_buckets_page_is_published_but_no_longer_advertised(self):
        """The bucket workspace is the screener's context layer now, so the rail stops
        offering a second destination for choosing a thesis. The page itself stays published:
        an existing bookmark must not begin 404ing, which is the rule /screener and
        /sentiment were kept under when they left the rail."""
        self.assertIn("buckets.html", self.pages,
                      "buckets.html must still be published — a live link cannot start 404ing")
        for name in ("index.html", "overview.html", "web.html", "surfaces.html"):
            rail = re.search(r'<nav class="rail">.*?</nav>', self.pages[name], re.S)
            self.assertIsNotNone(rail, name)
            self.assertNotIn("buckets.html", rail.group(0),
                             "{} still advertises the buckets page in its rail".format(name))

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

    def test_a_lens_page_shows_its_definition_and_the_kept_local_state_not_a_table(self):
        """The lens pages no longer depend on a snapshot at all: they publish the lens's
        authored definition and say the vendor data is kept local, whatever is on disk."""
        page = self.pages["screen-low_pe_high_growth.html"]
        self.assertIn(sc.PRESETS["low_pe_high_growth"]["title"], page)
        self.assertIn("Data kept local", page)
        self.assertIn("Not evaluated on this public site", page)
        self.assertNotIn("No snapshot fetched", page)

    def test_a_lens_decided_by_authored_tags_lists_its_members(self):
        """`high_ai_exposure` is `ai == high`, an editorial tag: its membership is this
        repository's own and is published (by apply_preset, the one rule implementation)."""
        page = self.pages["screen-high_ai_exposure.html"]
        high = [tk for tk, _n, _s, ai, _b in sc.universe_rows() if ai == "high"]
        self.assertTrue(high)
        for tk in high:
            self.assertIn("<td>{}</td>".format(tk), page)
        self.assertIn("authored order", page)


class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(REPO, ".github", "workflows", "pages.yml"),
                  encoding="utf-8") as fh:
            cls.wf = fh.read()

    def test_it_runs_the_export_script_this_suite_tests(self):
        self.assertIn("python tools/export_pages.py --out _site", self.wf)
        self.assertIn("path: _site", self.wf)

    def test_the_workflow_fetches_no_yahoo_fundamentals_or_prices(self):
        """REPLACED the best-effort-fetch guard (docs/research/DATA_REDISTRIBUTION_AUDIT.md,
        option A). The site no longer publishes Yahoo fundamentals or closes, so the job
        that builds it has no reason to collect them: a fetch step here would only be a
        way for vendor data to reach a public artifact."""
        # What the job RUNS, not what its comments explain: the header names the retired
        # steps on purpose.
        executable = "\n".join(line for line in self.wf.splitlines()
                               if not line.lstrip().startswith("#"))
        for step in ("stock_screener.py fetch", "stock_screener.py prices", "yfinance"):
            self.assertNotIn(step, executable)
        self.assertIn("screener_lab.py refresh --tone-only", executable)

    def test_the_tone_fetch_is_best_effort_so_an_outage_cannot_block_publishing(self):
        fetch = self.wf.index("screener_lab.py refresh --tone-only")
        block = self.wf[max(0, fetch - 1400):fetch]
        self.assertIn("continue-on-error: true", block)

    def test_it_deploys_from_the_default_branch_and_refreshes_on_a_schedule(self):
        self.assertIn("branches: [development]", self.wf)
        self.assertIn("schedule:", self.wf)
        self.assertIn("workflow_dispatch:", self.wf)

    def test_contents_write_exists_for_the_ledger_and_nothing_else(self):
        """REWRITTEN when the tone ledger landed. The old guard pinned `contents: read` —
        least privilege while the workflow only published. The ledger deliberately widened
        it, so the claim this guard protects changed from "the workflow cannot write the
        repo" to "the workflow writes exactly one thing": daily tone rows, pushed to the
        dedicated tone-ledger branch. What must never appear is a push to any OTHER ref —
        a workflow that can commit to development is a self-trigger loop (both workflows
        fire on development pushes) and a supply-chain surface the read permission used to
        preclude."""
        self.assertIn("contents: write", self.wf)
        self.assertIn("pages: write", self.wf)
        self.assertIn("id-token: write", self.wf)
        pushes = re.findall(r"git push [^\n]*", self.wf)
        self.assertTrue(pushes, "contents:write with no push is a permission nothing uses")
        for push in pushes:
            self.assertIn("tone-ledger", push,
                          "the workflow pushes to a ref other than tone-ledger: %r" % push)
        self.assertNotIn("push origin development", self.wf)
        # Every ledger step must be unable to fail the deploy.
        for step in ("Check out the tone ledger", "Push the ledger rows"):
            block = self.wf.split(step, 1)[1][:400]
            self.assertIn("continue-on-error: true", block,
                          "%s can fail the deploy; the ledger must be additive or absent"
                          % step)


if __name__ == "__main__":
    unittest.main()


class ThePublishedRailIsShapedLikeTheServersTests(unittest.TestCase):
    """The parity test above compares LIST MEMBERSHIP — the views, and the Basics sequence.
    That is blind to STRUCTURE: both rails could carry the same items and disagree about which
    of them sit inside the Quant dropdown, which is exactly the drift that happened when
    Contribute was lifted out of the group on the server and left inside on the published side.

    Compared by LABEL, because the two rails address different things — the server uses routes
    and the static build uses filenames — so hrefs are two vocabularies and only the words a
    reader sees are common to both."""

    @staticmethod
    def _split(nav):
        head, _sep, rest = nav.partition("<details")
        inside = rest.partition("</details>")[2]
        outside = head + inside
        grab = lambda t: [m.group(1) or m.group(2) for m in
                          re.finditer(r"<h4>([^<]+)</h4>|<a[^>]*>([^<]+?)(?:<span|</a>)", t)]
        return ([x.strip() for x in grab(outside) if x],
                [x.strip() for x in grab(rest.partition("</details>")[0]) if x])

    def test_the_same_things_sit_outside_the_dropdown_on_both(self):
        import research_ui  # noqa: PLC0415
        served_out, _served_in = self._split(
            research_ui._nav(research_ui.SCREENER_HREF, []))
        published_out, _pub_in = self._split(export_pages._static_nav("screener"))
        # Normalised: the server escapes & in "Theses & fails"; the static rail does not.
        norm = lambda xs: [x.replace("&amp;", "&") for x in xs]
        self.assertEqual(norm(served_out), norm(published_out),
                         "the two rails disagree about what is outside the Quant group")

    def test_contribute_is_outside_it_on_both(self):
        import research_ui  # noqa: PLC0415
        for label, nav in (("served", research_ui._nav(research_ui.SCREENER_HREF, [])),
                           ("published", export_pages._static_nav("screener"))):
            with self.subTest(rail=label):
                outside, inside = self._split(nav)
                self.assertIn("Contribute", outside)
                self.assertNotIn("Contribute", inside)


# ── The public site carries no vendor data (DATA_REDISTRIBUTION_AUDIT.md, option A) ─────────
import contextlib  # noqa: E402
import json  # noqa: E402

import screener_lab  # noqa: E402

#: Distinctive values planted in every vendor cache the export could read. None may appear
#: in any published file; the tone reading (this repository's own number) must.
VENDOR_SENTINELS = ("73.9137", "0.4321987", "58.2713", "1.98765", "9876543210123",
                    "1234567891.5", "4321.987", "0.31415", "777.123", "778.456",
                    "Vendorname Sentinel Holdings", "Vendor Sentinel Sector",
                    "66.6123", "5555.123", "SENTINEL HEADLINE do not publish")
OWN_TONE = 0.4242


@contextlib.contextmanager
def planted_vendor_caches():
    """Every cache the screener reads, filled with sentinel vendor values and one tone
    snapshot whose headline is a sentinel too; restored afterwards."""
    fund_row = {"ticker": "META", "name": "Vendorname Sentinel Holdings",
                "sector": "Vendor Sentinel Sector", "pe": 73.9137, "growth": 0.4321987,
                "earnings_growth": 0.4321987, "revenue_growth": 0.2, "dividend_yield": 0.0917,
                "debt_to_equity": 58.2713, "beta": 1.98765, "market_cap": 9876543210123,
                "dollar_volume": 1234567891.5, "price": 4321.987, "profit_margin": 0.31415,
                "range_52w_pct": 0.5, "ai": "high", "bucket": "ai"}
    tone_row = {"ticker": "META", "name": "Vendorname Sentinel Holdings",
                "trailing_pe": 66.6123, "price": 5555.123,
                "bloomberg_tone": OWN_TONE, "bloomberg_coverage": 3, "bloomberg_toned": 2,
                "bloomberg_docs": [{"title": "SENTINEL HEADLINE do not publish", "tone": 0.5,
                                    "published": "Thu, 06 Aug 2026 14:22:00 GMT",
                                    "rule": "lexicon", "terms": ["beat"]}]}
    tone = {"built_at": "2026-10-09T00:00:00+00:00", "rows": [tone_row], "providers": []}
    real = (sc.SNAPSHOT_PATH, sc.PRICES_PATH, screener_lab.load_snapshot)
    with tempfile.TemporaryDirectory() as tmp:
        fund_path, price_path = os.path.join(tmp, "f.json"), os.path.join(tmp, "p.json")
        with open(fund_path, "w", encoding="utf-8") as fh:
            json.dump({"as_of": "2026-10-08T00:00:00Z", "source": "yfinance Ticker.info",
                       "universe_size": 1, "errors": [], "rows": [fund_row]}, fh)
        with open(price_path, "w", encoding="utf-8") as fh:
            json.dump({"as_of": "2026-10-08T00:00:00Z", "source": "yfinance", "bars": 2,
                       "delisted": {}, "errors": [], "series": {"META": [777.123, 778.456]}}, fh)
        sc.SNAPSHOT_PATH, sc.PRICES_PATH = fund_path, price_path
        screener_lab.load_snapshot = lambda *a, **k: json.loads(json.dumps(tone))
        try:
            yield
        finally:
            sc.SNAPSHOT_PATH, sc.PRICES_PATH, screener_lab.load_snapshot = real


class ThePublicSiteCarriesNoVendorData(unittest.TestCase):
    """With every vendor cache full of sentinels, no published file holds one of them,
    while this repository's own tone reading is published."""

    @classmethod
    def setUpClass(cls):
        cls.td = tempfile.TemporaryDirectory()
        with planted_vendor_caches():
            # The planting is real: the LOCAL server would render these values.
            served = research_ui._screener_combined_draft_payload()
            assert any(r.get("pe") == 73.9137 for r in served["rows"]), "plant failed"
            cls.full_public = research_ui.public_screener_payload(served)
            cls.written = export_pages.export(cls.td.name)
        cls.files = {}
        for name in cls.written:
            with open(os.path.join(cls.td.name, name), encoding="utf-8") as fh:
                cls.files[name] = fh.read()

    @classmethod
    def tearDownClass(cls):
        cls.td.cleanup()

    def test_no_vendor_value_or_headline_appears_in_any_published_file(self):
        for name, text in self.files.items():
            for sentinel in VENDOR_SENTINELS:
                with self.subTest(file=name, sentinel=sentinel):
                    self.assertNotIn(sentinel, text)

    def test_the_repositorys_own_tone_reading_is_published(self):
        payload = json.loads(re.search(r"window\.__DRAFT_LIVE__ = (\{.*?\});</script>",
                                       self.files["index.html"], re.S).group(1))
        meta = next(r for r in payload["rows"] if r["tk"] == "META")
        self.assertEqual(meta["bb"], OWN_TONE)
        self.assertEqual((meta["bb_c"], meta["bb_t"]), (3, 2))
        for field in research_ui.VENDOR_ROW_FIELDS:
            self.assertIn(meta[field], (None, "—"), field)
        self.assertEqual(meta["absent"]["pe"], "withheld")
        self.assertEqual(payload["vendor_withheld"], research_ui.VENDOR_WITHHELD_NOTICE)
        self.assertEqual((payload["price_history"], payload["concentration"]), ({}, None))

    def test_the_policy_function_strips_a_full_local_payload_too(self):
        """Defence in depth: the export never reads the vendor caches, and even a payload
        that DID (the local server's) comes out of public_screener_payload clean."""
        text = json.dumps(self.full_public)
        for sentinel in VENDOR_SENTINELS:
            with self.subTest(sentinel=sentinel):
                self.assertNotIn(sentinel, text)

    def test_the_public_rows_are_the_authored_universe(self):
        payload = json.loads(re.search(r"window\.__DRAFT_LIVE__ = (\{.*?\});</script>",
                                       self.files["index.html"], re.S).group(1))
        self.assertEqual([r["tk"] for r in payload["rows"]],
                         [tk for tk, *_rest in sc.universe_rows()])


class ThePublicPolicyFailsClosed(unittest.TestCase):
    def test_an_unclassified_payload_key_is_refused(self):
        with self.assertRaises(ValueError):
            research_ui.public_screener_payload({"rows": [], "new_vendor_series": {}})

    def test_an_unclassified_row_field_is_refused(self):
        with self.assertRaises(ValueError):
            research_ui.public_screener_payload({"rows": [{"tk": "META", "ev_ebitda": 9.1}]})

    def test_every_field_the_draft_payload_emits_is_classified(self):
        """The served payload's own keys and row fields, from authored snapshots: a new one
        must be classified before the export can run, and this names it first."""
        from tests import screener_payload_fixture
        payload = screener_payload_fixture.authored_payload()
        research_ui.public_screener_payload(payload)          # raises on an unclassified one
        rows = {k for r in payload["rows"] for k in r}
        classified = (set(research_ui.AUTHORED_ROW_FIELDS) | set(research_ui.TONE_ROW_FIELDS)
                      | set(research_ui.VENDOR_ROW_FIELDS) | set(research_ui.DERIVED_ROW_FIELDS))
        self.assertLessEqual(rows, classified)

    def test_the_lists_do_not_overlap(self):
        lists = (research_ui.AUTHORED_ROW_FIELDS, research_ui.TONE_ROW_FIELDS,
                 research_ui.VENDOR_ROW_FIELDS, research_ui.DERIVED_ROW_FIELDS)
        flat = [f for lst in lists for f in lst]
        self.assertEqual(len(flat), len(set(flat)))
        keys = (research_ui.PUBLIC_PAYLOAD_KEYS + research_ui.REBUILT_PAYLOAD_KEYS
                + research_ui.VENDOR_PAYLOAD_KEYS)
        self.assertEqual(len(keys), len(set(keys)))

    def test_a_lens_is_not_evaluated_on_withheld_fields_and_a_capped_one_not_on_its_rank(self):
        P = sc.PRESETS
        self.assertEqual(research_ui.preset_withheld_metrics(P["low_pe_high_growth"]), ["pe", "growth"])
        self.assertEqual(research_ui.preset_withheld_metrics(P["high_ai_exposure"]), [])
        self.assertEqual(research_ui.preset_withheld_metrics(P["sovereign_ledger"]), [])
        self.assertEqual(research_ui.preset_withheld_metrics(P["most_active"]), ["dollar_volume"])
        self.assertNotIn("shadow_severity_rank",
                         research_ui.preset_withheld_metrics(P["safety_low_debt"]))

    def test_the_metric_map_is_the_pages_canon_field(self):
        with open(research_ui.SCREENER_COMBINED_DRAFT_HTML, encoding="utf-8") as fh:
            html = fh.read()
        page = dict(re.findall(r'(\w+):"(\w+)"',
                               re.search(r"const CANON_FIELD = \{(.*?)\};", html, re.S).group(1)))
        self.assertEqual(page, research_ui.PRESET_METRIC_FIELD)

    def test_the_withheld_code_is_registered_and_the_page_reads_the_notice_from_the_payload(self):
        self.assertIn("withheld", research_ui.ABSENCE_REASONS)
        with open(research_ui.SCREENER_COMBINED_DRAFT_HTML, encoding="utf-8") as fh:
            html = fh.read()
        self.assertIn("VENDOR_WITHHELD = live.vendor_withheld", html)
        self.assertNotIn(research_ui.VENDOR_WITHHELD_NOTICE, html,
                         "the page restates the notice instead of reading it")


class ThePublicRenderersReadNoVendorCache(unittest.TestCase):
    """The lens pages, the buckets page and the screener payload are built without opening
    the Yahoo caches, so the site cannot depend on what the building machine holds."""

    def test_export_succeeds_with_the_vendor_loaders_booby_trapped(self):
        def trap(*a, **k):
            raise AssertionError("the public export read a vendor cache")
        real = (sc.load_snapshot, sc.load_prices)
        sc.load_snapshot, sc.load_prices = trap, trap
        try:
            with tempfile.TemporaryDirectory() as td:
                written = export_pages.export(td)
                self.assertIn("buckets.html", written)
                with open(os.path.join(td, "buckets.html"), encoding="utf-8") as fh:
                    self.assertNotRegex(fh.read(), r"const PRICES = \{\"")
        finally:
            sc.load_snapshot, sc.load_prices = real

    def test_the_local_server_still_reads_them(self):
        """Unchanged locally: the served lens page and payload read the caches."""
        with planted_vendor_caches():
            code, body, _ct = research_ui.route("/screener", {"preset": "low_pe_high_growth"}, {})
            self.assertEqual(code, 200)
            self.assertIn("Vendor Sentinel Sector", body)
            self.assertIn("777.123", json.dumps(research_ui._screener_combined_draft_payload()))

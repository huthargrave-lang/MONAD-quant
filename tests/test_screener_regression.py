"""What the Screener does today, pinned before the scenario layer starts moving it.

Phase 0b of the probabilistic scenario layer. Everything after this phase adds an optional
derived path from a selected shock through to securities, and the promise attached to it is
that the existing surface is *behaviourally identical* wherever no scenario model exists.
A promise like that is worth exactly as much as the harness that can contradict it.

TWO DESIGN CONSTRAINTS SHAPED THIS FILE, and both are load-bearing:

**It must be green in CI, so it must not need a snapshot.** `data/screener/fundamentals.json`,
`data/screener/prices.json` and `data/cache/screener_snapshot.json` are all gitignored
(.gitignore:52-57), so none of them exists on a runner. Three tests in the existing suite
already depend on them and are red in CI for that reason. A regression harness that joined
them would be red too — and a permanently-red guard is one everybody learns to scroll past,
which is the same failure as a guard that skips. So every pin here is computed from data that
is *tracked*: the authored bucket ledger, the canonical preset rules, the constituent list,
and the page file itself. Where row data is needed it is SYNTHESISED in the test, which is
this repo's existing convention (tests/test_research_web.py builds a synthetic web;
screener_lab's tests inject `get=`).

**It must pin behaviour, not spelling, wherever behaviour is reachable.** The Python side —
`apply_preset`, the bucket derivations, the heat table — is executed. The page's JavaScript is
not reachable from Python (no JS engine in CI; `node --check` is syntax-only and skips), so
for that layer this file pins the COMPOSITION — the exact expressions through which the three
constraints combine — because that is the thing the scenario layer will be tempted to edit,
and a changed composition is a changed screener whatever the lens rules say.

What is deliberately NOT here: anything asserting a particular ticker is or is not in a lens
under the live snapshot. That is a property of a fetch, it changes every night, and pinning it
would make this file a tripwire on the market rather than on the code.
"""
import inspect
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (REPO, os.path.join(REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import research_ui  # noqa: E402
import sovereign_buckets as sb  # noqa: E402
import stock_screener as sc  # noqa: E402

PAGE = os.path.join(REPO, "docs", "research", "SCREENER_COMBINED_DRAFT.html")


def _page():
    with open(PAGE, encoding="utf-8") as fh:
        return fh.read()


def _synthetic_rows():
    """A universe with a known answer for every rule, built rather than fetched.

    Every metric any preset requires appears here at a value that clearly passes and one that
    clearly fails, plus a row that reports NOTHING — because "absent" is a third outcome the
    screener is careful about and a fixture with no nulls in it cannot catch a regression that
    starts treating absent as zero.
    """
    def row(tk, **kw):
        base = {"ticker": tk, "name": tk + " Inc", "sector": "Test",
                "pe": None, "growth": None, "dividend_yield": None,
                "debt_to_equity": None, "beta": None, "profit_margin": None,
                "dollar_volume": None, "market_cap": None, "range_52w_pct": None,
                "ai": "low", "bucket": None,
                "shadow_debt": None, "shadow_severity": None, "shadow_severity_rank": 0}
        base.update(kw)
        return base

    return [
        # Clears the value/growth screens comfortably.
        row("AAA", pe=8.0, growth=0.40, dividend_yield=0.05, debt_to_equity=10.0,
            beta=0.5, profit_margin=0.30, dollar_volume=5e8, market_cap=1e10, ai="high"),
        # Fails them just as comfortably.
        row("BBB", pe=90.0, growth=-0.10, dividend_yield=0.0, debt_to_equity=400.0,
            beta=2.4, profit_margin=-0.05, dollar_volume=1e6, market_cap=1e8, ai="low"),
        # Middling — the row that moves if a threshold moves.
        row("CCC", pe=18.0, growth=0.12, dividend_yield=0.02, debt_to_equity=70.0,
            beta=0.85, profit_margin=0.09, dollar_volume=2e8, market_cap=5e9, ai="medium"),
        # Reports nothing at all. Must land in no_data, never in matches, and never be
        # treated as a zero that happens to clear a `<=` gate.
        row("ZZZ"),
    ]


class TheLensRulesStillScreenTheSameWay(unittest.TestCase):
    """`apply_preset` is the canonical lens engine — the page consumes the same rules through
    `PRESET_RULES`. Pinned against a synthetic universe so the answer is a property of the
    RULES and not of last night's fetch."""

    def setUp(self):
        self.rows = [sc.enrich_row(dict(r)) for r in _synthetic_rows()]

    def _screen(self, key):
        """(matched tickers in rank order, unscreenable tickers).

        `no_data` is a list of `(row, missing)` TUPLES, not rows — the missing-metric names
        travel with the row so the page can say which reading was absent.
        """
        matches, no_data = sc.apply_preset(self.rows, key)
        return ([r["ticker"] for r in matches],
                sorted(row["ticker"] for row, _missing in no_data))

    def test_every_preset_screens_the_synthetic_universe_identically(self):
        """The whole point of the harness. If a threshold, an operator or a rank direction
        moves, exactly one row of this table changes and the diff names the lens.

        Every value here was MEASURED from `apply_preset`, not predicted. Two of them are
        worth reading twice, because they look wrong and are not:

          `low_ai_exposure` matches ZZZ — the row that reports no numbers at all — because its
          only requirement is `ai == "low"`, and `ai` is CATEGORICAL, where absence is a value
          rather than missing data. ZZZ genuinely carries a low-AI tag.

          `most_active` matches ZZZ for a blunter reason: it requires nothing. It ranks on
          dollar volume, and a null rank value sinks to the end rather than excluding the row.
        """
        got = {key: self._screen(key) for key in sorted(sc.PRESETS)}
        expected = {
            "ai_shadow_debt":       ([], []),
            "chaos_hedges":         ([], []),
            "high_ai_exposure":     (["AAA"], []),
            "low_ai_exposure":      (["BBB", "ZZZ"], []),
            "low_pe_high_dividend": (["AAA"], ["ZZZ"]),
            "low_pe_high_growth":   (["AAA", "CCC"], ["ZZZ"]),
            "most_active":          (["AAA", "CCC", "BBB", "ZZZ"], []),
            "most_volatile":        (["BBB"], ["ZZZ"]),
            "safety_low_debt":      (["AAA", "CCC"], ["ZZZ"]),
            "sovereign_ledger":     ([], []),
        }
        for key in sorted(expected):
            self.assertEqual(got[key], expected[key], "{} screens differently".format(key))

    def test_the_rule_table_itself_is_written_down(self):
        """The actual regression pin, and the one thing here that cannot be derived.

        Every other test in this class computes its expectation FROM `PRESETS`, which makes
        them tests of the engine: they prove `apply_preset` honours whatever the rules say.
        None of them can see the rules themselves change — move `debt_to_equity <= 80` to
        `<= 200` and the boundary probes simply re-derive, build a row at 199, and pass. A
        test that takes its expectations from the thing it is testing can only ever prove
        self-consistency.

        So the rules are transcribed. This is the copy that makes a threshold change a diff
        with a lens name on it rather than a silent widening of what the screener claims."""
        got = {k: {"require": sorted(p["require"], key=lambda t: t[0]),
                   "rank": p["rank"], "top": p.get("top")}
               for k, p in sc.PRESETS.items()}
        expected = {
            "low_pe_high_growth": {
                "require": [("growth", ">=", 0.10), ("pe", "<=", 25.0)],
                "rank": ("growth", "desc"), "top": None},
            "low_pe_high_dividend": {
                "require": [("dividend_yield", ">=", 0.03), ("pe", "<=", 18.0)],
                "rank": ("dividend_yield", "desc"), "top": None},
            "safety_low_debt": {
                "require": [("beta", "<=", 0.9), ("debt_to_equity", "<=", 80.0),
                            ("profit_margin", ">=", 0.08),
                            ("shadow_severity_rank", "<=", 2)],
                "rank": ("debt_to_equity", "asc"), "top": None},
            "high_ai_exposure": {
                "require": [("ai", "==", "high")],
                "rank": ("growth", "desc"), "top": None},
            "ai_shadow_debt": {
                "require": [("shadow_debt", "!=", None)],
                "rank": ("debt_to_equity", "desc"), "top": None},
            "low_ai_exposure": {
                "require": [("ai", "==", "low")],
                "rank": ("dividend_yield", "desc"), "top": None},
            "most_volatile": {
                "require": [("beta", ">=", 1.3)],
                "rank": ("beta", "desc"), "top": None},
            "most_active": {
                "require": [],
                "rank": ("dollar_volume", "desc"), "top": 15},
            "sovereign_ledger": {
                "require": [("bucket", "==", "wartime elements")],
                "rank": ("dollar_volume", "desc"), "top": None},
            "chaos_hedges": {
                "require": [("bucket", "!=", None)],
                "rank": ("dollar_volume", "desc"), "top": None},
        }
        self.assertEqual(sorted(got), sorted(expected),
                         "the set of lenses changed")
        for key in sorted(expected):
            self.assertEqual(got[key], expected[key],
                             "the {} lens screens or ranks differently".format(key))

    def test_every_numeric_threshold_is_pinned_at_its_own_boundary(self):
        """Proves the ENGINE honours the rule table — a different property from the pin above,
        and it auto-covers any threshold a future preset adds.

        Those synthetic rows are deliberately unambiguous — clearly passing or clearly
        failing — and that is exactly why moving `pe <= 25.0` to `30.0` changed nothing: no
        row sat between 25 and 30, so the harness watched the thresholds and could not see
        them move. A fixture with no row near a boundary cannot detect a boundary moving.

        So the boundaries are DERIVED from `PRESETS` rather than transcribed, and each is
        probed from both sides with a row built for it. A threshold added by a future preset
        is covered the day it is added; one that moves in either direction flips a row here.
        """
        thresholds = {(f, op, v)
                      for p in sc.PRESETS.values()
                      for f, op, v in p["require"] if f not in sc.CATEGORICAL}
        self.assertTrue(thresholds, "no numeric thresholds found — PRESETS changed shape")

        def probe(field, value):
            """One row reporting only `field`, at `value`, plus everything else absent."""
            row = dict(_synthetic_rows()[-1])          # ZZZ: all metrics None
            row["ticker"] = "PROBE"
            row[field] = value
            return sc.enrich_row(row)

        def comfortably(op, limit):
            """A value that clears `op limit` by a wide margin, so a probe isolates the ONE
            threshold under test rather than tripping over a sibling requirement."""
            margin = max(1.0, abs(limit))
            return limit - margin if op.startswith("<") else limit + margin

        # `shadow_severity_rank` is DERIVED by enrich_row from the editorial tag table, not
        # reported by a row, so a synthetic ticker cannot be positioned against it — it is
        # always 0 for a name nobody tagged. Probing it would assert enrich_row's default,
        # not the threshold.
        derived = {"shadow_severity_rank"}
        checked = []
        for field, op, limit in sorted(thresholds, key=lambda t: (t[0], t[1], str(t[2]))):
            if field in derived:
                continue
            step = 0.01 if isinstance(limit, float) and abs(limit) < 10 else 1
            inside, outside = ((limit - step, limit + step) if op.startswith("<")
                               else (limit + step, limit - step))
            for key, p in sc.PRESETS.items():
                if (field, op, limit) not in p["require"]:
                    continue

                def row_at(value):
                    r = probe(field, value)
                    for f, o, v in p["require"]:
                        if f == field:
                            continue
                        if f in sc.CATEGORICAL:
                            r[f] = v if o == "==" else (
                                "wartime elements" if f == "bucket" else "tagged")
                        elif f not in derived:
                            r[f] = comfortably(o, v)
                    return r

                matched_in = [r["ticker"] for r in sc.apply_preset([row_at(inside)], key)[0]]
                matched_out = [r["ticker"] for r in sc.apply_preset([row_at(outside)], key)[0]]
                self.assertIn("PROBE", matched_in,
                              "{}: a row at {}={} does not clear {} {} {}".format(
                                  key, field, inside, field, op, limit))
                self.assertNotIn("PROBE", matched_out,
                                 "{}: a row at {}={} clears {} {} {} — the threshold has "
                                 "moved".format(key, field, outside, field, op, limit))
                checked.append((key, field, op, limit))
        self.assertGreaterEqual(
            len(checked), 8,
            "only {} thresholds were probed; the boundaries are not actually pinned".format(
                len(checked)))

    def test_a_missing_numeric_metric_is_never_read_as_zero(self):
        """The invariant, stated over each preset's OWN requirements rather than guessed.

        A `<=` gate is exactly where absent-as-zero goes wrong quietly: a missing debt/equity
        read as 0 clears "debt under 80%" and lands a company the screener knows nothing
        about at the top of the safety screen. So for every preset that requires a numeric
        metric, the row reporting none of them must be unscreenable — and must not appear in
        matches under any reading."""
        for key, p in sc.PRESETS.items():
            required = [f for f, _op, _v in p["require"] if f not in sc.CATEGORICAL]
            matched, unscreenable = self._screen(key)
            if not required:
                continue
            self.assertIn("ZZZ", unscreenable,
                          "{} requires {} but did not report the row that reports none of "
                          "them as unscreenable".format(key, required))
            self.assertNotIn("ZZZ", matched,
                             "{} matched a row missing {}".format(key, required))


class TheContextCompositionIsUnchanged(unittest.TestCase):
    """Three constraints — filters, buckets, lens — combine at one point, in one order, and
    the order is load-bearing: the filter row bites BEFORE the lens so that a preset carrying
    a `top` cap ranks what survived rather than capping first and filtering the cap.

    The scenario layer adds a fourth constraint. These pin what it must not disturb."""

    def setUp(self):
        self.html = _page()

    def test_the_universe_is_filters_and_buckets_and_nothing_else(self):
        body = re.search(r"function contextUniverse\(\)\{(.*?)\n\}", self.html, re.S)
        self.assertIsNotNone(body, "contextUniverse is gone")
        self.assertIn("ROWS.filter(r => passesFilters(r) && inSelectedBuckets(r))",
                      body.group(1),
                      "the context universe is no longer exactly filters AND buckets")

    def test_the_lens_is_applied_over_the_universe_and_not_beside_it(self):
        self.assertIn("function matchedRows(){ return lensRows(contextUniverse()); }",
                      self.html,
                      "matchedRows is no longer the lens applied to the context universe")

    def test_bucket_membership_narrows_and_values_nothing(self):
        """A bucket names companies; it asserts nothing about their P/E. If bucket selection
        ever reached a metric, a shock would be scoring companies through the back door —
        which is the invariant the whole scenario layer is built around."""
        body = re.search(r"function inSelectedBuckets\(r\)\{(.*?)\n\}", self.html, re.S)
        self.assertIsNotNone(body, "inSelectedBuckets is gone")
        code = body.group(1)
        self.assertIn("if(!BUCKET_SEL.size) return true;", code,
                      "an empty bucket selection must not narrow anything")
        self.assertIn("bucketNameSet().has(r.tk)", code)
        for metric in ("r.pe", "r.g", "r.de", "r.beta", "r.score", "r.dy"):
            self.assertNotIn(metric, code,
                             "bucket membership reads {} — it may name companies, not "
                             "value them".format(metric))

    def test_the_shock_and_clock_still_reach_no_security(self):
        """Today the shock orders bucket cards and colours their heat, and stops there. Phase
        C changes that deliberately, through SecurityExposure. Until then, and afterwards for
        editorial heat, a heat may not be multiplied into a company's number."""
        self.assertNotRegex(
            self.html, r"heatOf\([^)]*\)\s*[*/+-]\s*(?:r\.|score|rank|pe|beta)",
            "a heat is being combined with a company metric")
        self.assertNotRegex(
            self.html, r"(?:score|rank|pe|beta)\s*[*/+-]\s*heatOf\(",
            "a company metric is being combined with a heat")


class TheAbsenceSurfacesStillExist(unittest.TestCase):
    """The screener distinguishes at least four things an empty cell can mean, and each has a
    surface that says which. They are the first casualty of a feature that adds a new way for
    data to be missing, so each is pinned by the DISTINCTION it draws rather than by its
    wording."""

    def setUp(self):
        self.html = _page()

    def test_an_empty_lens_and_an_empty_page_read_differently(self):
        body = re.search(r"function lensEmptyMsg\(\)\{(.*?)\n\}", self.html, re.S)
        self.assertIsNotNone(body, "lensEmptyMsg is gone")
        code = body.group(1)
        self.assertIn("ROWS.length", code,
                      "the empty message no longer distinguishes 'this lens excluded "
                      "everything' from 'nothing is loaded'")
        self.assertIn("muted-cell", code, "a real-but-empty result must not read as absence")
        self.assertIn("absent", code, "a missing snapshot must not read as a result")

    def test_the_unscreenable_are_named_on_the_page(self):
        self.assertRegex(self.html, r"function lensNoData\(",
                         "the unscreenable bin is gone")
        self.assertRegex(self.html, r"could not be",
                         "the unscreenable are computed but never rendered")

    def test_the_way_out_measures_each_constraint_rather_than_guessing(self):
        """`emptyWayOut` re-runs the query with each constraint dropped — lens, buckets,
        filters. Each has to be measured against a FRESH universe: a memo built from the
        original constraints answers the original question every time, which is how two of
        the three counterfactuals silently became 0.

        COUNTED, not `assertIn`. There are three counterfactuals and the first version of this
        test asserted only that the name appeared somewhere in the body — so removing it from
        one call site left the test green while that constraint reported a number it had not
        measured. All three, or the reader is told to drop a constraint on the strength of a
        stale answer."""
        body = re.search(r"function emptyWayOut\(\)\{(.*?)\n\}", self.html, re.S)
        self.assertIsNotNone(body, "emptyWayOut is gone")
        code = body.group(1)
        self.assertEqual(
            code.count("matchedRows()"), code.count("withFreshUniverse("),
            "emptyWayOut re-runs the query {} times but only {} of them escape the memo — "
            "the rest report the number they were trying to change".format(
                code.count("matchedRows()"), code.count("withFreshUniverse(")))
        self.assertEqual(code.count("withFreshUniverse("), 3,
                         "there are three constraints a reader can drop; each needs its own "
                         "measured counterfactual")

    def test_a_gate_that_judged_nothing_still_says_so(self):
        """`shadow_severity_rank <= 2` is cleared by every untagged name, because untagged
        ranks 0. Without the note the lens claims a filter it did not apply — and this is the
        exact pattern the scenario layer's exposure gate has to copy."""
        self.assertRegex(self.html, r"function shadowGateNote\(rows\)\{",
                         "the note that reports a gate judging nothing is gone")
        self.assertIn("Absence of a tag is not evidence of no exposure.", self.html)

    def test_three_reasons_a_constituent_is_unscreened_stay_three(self):
        body = re.search(r"function listedNote\(rows\)\{(.*?)\n\}", self.html, re.S)
        self.assertIsNotNone(body, "listedNote is gone")
        code = body.group(1)
        self.assertIn("NOT_COMPANIES", code, "the fund/futures reason is gone")
        self.assertIn("DELISTED", code, "the no-longer-trades reason is gone")
        self.assertRegex(code, r"\bgap\b",
                         "the genuinely-missing reason is gone, so three situations are "
                         "back to sharing one sentence")


class TheBucketDerivationsAreUnchanged(unittest.TestCase):
    """Membership is the relationship Phase C reaches a security through, so it is pinned in
    full — from tracked authored data, so it holds with no snapshot on disk."""

    def test_the_membership_map_is_stable(self):
        """Slots and distinct names are two different counts, and the gap between them is
        the dual-bucket population Phase C has to keep every path to: 206 slots, 202 names,
        four names listed twice."""
        by_id = {b["id"]: b for b in sb.BUCKETS}
        self.assertEqual(len(by_id), 20, "the ledger no longer has twenty buckets")
        slots = sum(len(b["liquid"]) + len(b["satellite"]) for b in sb.BUCKETS)
        distinct = len({t for b in sb.BUCKETS for t in b["liquid"] + b["satellite"]})
        self.assertEqual((slots, distinct), (206, 202),
                         "membership moved; it is what Phase C reaches a security through, "
                         "so this is a deliberate change or a mistake, never a nudge")
        # Names, not just counts: a swap keeps every count identical.
        self.assertEqual(by_id["02"]["liquid"],
                         ["XLE", "XOP", "XOM", "CVX", "COP", "EOG", "FANG", "OXY", "CL=F"])
        self.assertEqual(by_id["04"]["liquid"],
                         ["FRO", "DHT", "STNG", "EURN", "INSW", "TNK", "ASC"])

    def test_the_dual_bucket_names_are_still_dual(self):
        """GD, CW and MRC are in 05 and 16; UUUU in 09 and 11. Phase C keeps every path to a
        security rather than collapsing them, so these four are the fixture that proves it —
        if they stop being dual, that test starts passing vacuously."""
        homes = {}
        for b in sb.BUCKETS:
            for tk in b["liquid"] + b["satellite"]:
                homes.setdefault(tk, []).append(b["id"])
        for tk, expected in (("GD", ["05", "16"]), ("CW", ["05", "16"]),
                             ("MRC", ["05", "16"]), ("UUUU", ["09", "11"])):
            self.assertEqual(homes.get(tk), expected,
                             "{} is no longer in exactly {}".format(tk, expected))

    def test_screen_tag_for_is_still_first_match_wins(self):
        """Not an endorsement — a pin. The drawer must name the bucket it actually traversed,
        and it can only know to do that while this stays true and documented."""
        self.assertEqual(sb.screen_tag_for("GD"), "defense US")
        self.assertEqual(sb.screen_tag_for("UUUU"), "uranium")
        self.assertIsNone(sb.screen_tag_for("SGOV"),
                          "a bucket with no screen_tag must yield None, not a guess")
        self.assertIsNone(sb.screen_tag_for("NOSUCHTICKER"))

    def test_the_reachable_but_unscreenable_are_a_known_population(self):
        """47 of the 202 reachable names can never appear in the results table. Phase C will
        mint exposures for them, and they have to be counted and named rather than silently
        dropped — which is what `listedNote` exists to do.

        The screenable set is `universe_rows()`, NOT `BUCKET_CONSTITUENTS`: the fundamentals
        universe is wider than the bucket list, so a constituent absent from
        `BUCKET_CONSTITUENTS` may still be screened via the base universe. Measuring against
        the narrower list reported 100 unscreenable names, more than half of them ordinary
        companies like XOM and LMT that screen perfectly well."""
        constituents = {t for b in sb.BUCKETS for t in b["liquid"] + b["satellite"]}
        screened = {row[0] for row in sc.universe_rows()}
        unscreenable = constituents - screened
        kinds = {t for t in unscreenable if t in sb.NOT_COMPANIES}
        gone = {t for t in unscreenable if t in sb.DELISTED} - kinds
        self.assertEqual(
            (len(unscreenable), len(kinds), len(gone)), (47, 36, 11),
            "the unscreenable population moved")
        self.assertEqual(
            sorted(unscreenable - kinds - gone), [],
            "a reachable name is unscreenable for a reason the ledger cannot state, so "
            "listedNote would have to describe it as a plain gap")


class TheHeatReadingIsPinned(unittest.TestCase):
    """Phase 0a made the rule executable; this is the pin it exists for. Every state, by
    value, so a change to the authored table or the bump is a diff and not a discovery."""

    def test_the_whole_state_space_is_stable(self):
        table = sb.heat_table()
        n = sum(len(by_clock) for row in table.values() for by_clock in row.values())
        self.assertEqual(n, 420, "the heat state space changed size")
        # An aggregate rather than 420 literals: the per-state assertions live in
        # test_sovereign_buckets, and duplicating them here is the second copy this project
        # keeps paying for. Deliberately NOT a json string length — that moves with key
        # ordering and formatting, so it would fail on a change that alters no reading and
        # pass on one that swapped two equal values between buckets.
        self.assertEqual(sum(v for r in table.values() for c in r.values()
                             for v in c.values()), 786,
                         "the total authored+bumped heat moved")

    def test_a_shock_with_no_model_still_orders_the_grid(self):
        """The scenario layer must leave editorial ordering alone. `unknown` is the shock a
        reader lands on with no scenario selected, and it must keep producing a full,
        non-degenerate ordering."""
        table = sb.heat_table()
        vals = [table[b["id"]]["unknown"]["T1"] for b in sb.BUCKETS]
        self.assertEqual(len(vals), 20)
        self.assertTrue(any(v > 0 for v in vals),
                        "no bucket has heat under the default shock, so the grid has no "
                        "order to show")


class ThePublishedArtifactStillBuilds(unittest.TestCase):
    """The export is what a reader actually sees. Task #47 — a published page drawing invented
    prices — was found on the live site, not in a test, because the harness pinned the served
    route and the export was nobody's job. It is this file's job now.

    Built into a temporary directory with no snapshot present, which is exactly the state a
    runner is in, so this asserts the ABSENCE path renders rather than the data path."""

    @classmethod
    def setUpClass(cls):
        cls.out = tempfile.mkdtemp(prefix="monad-export-")
        proc = subprocess.run(
            [sys.executable, os.path.join(REPO, "tools", "export_pages.py"),
             "--out", cls.out],
            cwd=REPO, capture_output=True, text=True)
        cls.proc = proc

    def test_the_export_succeeds(self):
        self.assertEqual(self.proc.returncode, 0,
                         "export_pages failed:\n{}".format(self.proc.stderr[-2000:]))

    def test_every_declared_page_is_written(self):
        for name in ("index.html", "buckets.html", "lenses.html",
                     "overview.html", "web.html", "web-groups.html"):
            path = os.path.join(self.out, name)
            self.assertTrue(os.path.exists(path), "{} was not exported".format(name))
            self.assertGreater(os.path.getsize(path), 2000,
                               "{} exported but is suspiciously small".format(name))

    def test_the_screener_carries_the_ledger_and_its_heat_table(self):
        with open(os.path.join(self.out, "index.html"), encoding="utf-8") as fh:
            html = fh.read()
        self.assertIn("window.LEDGER", html, "the published screener has no ledger")
        m = re.search(r"const HEAT = (\{.*?\});", html)
        self.assertIsNotNone(m, "the published screener carries no heat table")
        self.assertEqual(json.loads(m.group(1)), sb.heat_table(),
                         "the published heat table is not the one this repo computes")

    def test_the_published_page_does_not_generate_what_it_should_fetch(self):
        """The rule the buckets page was fixed to obey, asserted on the artifact that goes to
        GitHub Pages rather than on the route that served it.

        Scoped to VALUE generation, not to the word `Math.random`. The screener uses it twice
        — `Date.now().toString(36) + Math.random().toString(36).slice(2, 7)` — to mint a
        custom-lens id and a proposal id, which is a name, not a number a reader could
        mistake for a measurement. A blanket ban failed on both and would have to be either
        deleted or worked around, and a guard that gets worked around is worse than none.
        What must never appear is a random number used AS a number."""
        for name in ("index.html", "buckets.html"):
            with open(os.path.join(self.out, name), encoding="utf-8") as fh:
                html = fh.read()
            self.assertNotRegex(html, r"function mulberry32\(",
                                "{} ships a seeded price generator".format(name))
            stray = [m.group(0) for m in re.finditer(r"Math\.random\(\)(?!\.toString\(36\))",
                                                     html)]
            self.assertEqual(stray, [],
                             "{} uses Math.random() as a value rather than to mint an "
                             "identifier".format(name))

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.out, ignore_errors=True)


class TheHarnessDoesNotDependOnASnapshot(unittest.TestCase):
    """This file's own contract, asserted rather than trusted.

    Three tests in the existing suite go red without the gitignored snapshots. If this harness
    ever joins them it stops being a gate — a permanently-red guard is one people learn to
    scroll past, which is the same failure as one that skips."""

    def test_no_test_here_loads_a_gitignored_snapshot(self):
        """Matched as a QUALIFIED call — `sc.load_snapshot(`, not the bare name.

        The first version scanned for `load_snapshot(` and failed on its own assertion list:
        the guard named the thing it forbade, so it found itself. That is the same shape as
        the buckets guard that had to match `function mulberry32(` rather than the word,
        because the comment recording the removal names it on purpose."""
        with open(__file__, encoding="utf-8") as fh:
            src = re.sub(r'"""[\s\S]*?"""', "", fh.read())
        for call in (r"sc\.load_snapshot\(", r"sc\.load_prices\(",
                     r"screener_lab\.load_snapshot\(",
                     r"research_ui\._screener_combined_draft_payload\("):
            self.assertNotRegex(
                src, call,
                "this harness calls {} — it would be red on any runner, because the "
                "snapshots are gitignored".format(call.replace("\\", "")))

    def test_the_harness_passes_with_every_snapshot_absent(self):
        """The claim, executed rather than inspected. Runs this module in a subprocess with
        the snapshot paths pointed at a directory that does not exist, which is the state of
        a fresh runner.

        The env flag is what stops this recursing: the child loads this same module, so
        without it this test would re-launch itself forever."""
        if os.environ.get("MONAD_TEST_NO_SNAPSHOT"):
            self.skipTest("running inside the no-snapshot child")
        env = dict(os.environ, MONAD_TEST_NO_SNAPSHOT="1")
        proc = subprocess.run(
            [sys.executable, "-c",
             "import os, sys, unittest;"
             "sys.path.insert(0, %r);" % os.path.join(REPO, "tools") +
             "sys.path.insert(0, %r);" % REPO +
             "import stock_screener as sc, screener_lab as sl;"
             "sc.SNAPSHOT_PATH = sc.PRICES_PATH = sl.SNAPSHOT_PATH = '/nonexistent/x.json';"
             "m = unittest.defaultTestLoader.loadTestsFromName("
             "'tests.test_screener_regression');"
             "r = unittest.TextTestRunner(verbosity=0).run(m);"
             "sys.exit(0 if r.wasSuccessful() else 1)"],
            cwd=REPO, capture_output=True, text=True, env=env)
        self.assertEqual(proc.returncode, 0,
                         "this harness depends on a snapshot:\n{}".format(
                             proc.stderr[-3000:]))


class EveryServedRouteActuallyServes(unittest.TestCase):
    """A route that returns 500 must not be green.

    Found the hard way: `/screener/draft` — the main surface, the one exported to GitHub
    Pages — raised `NameError` on every request while the entire suite passed, because no test
    called `route()` for it. `test_research_ui` covers many routes and not that one; the
    contract tests read the HTML FILE, which is intact whether or not the server can render
    it; and `test_export_pages` builds through a different entry point.

    So this walks the route table itself rather than a list someone maintains: a route added
    tomorrow is covered tomorrow.
    """

    #: Routes that legitimately do not return 200 without state this repo does not ship.
    #: Each is named with the reason, so "expected failure" can never quietly grow.
    EXPECTED_NON_200 = {
        "/api/sentiment": "503 without a tone snapshot, which is gitignored",
        "/api/screen": "503 without a fundamentals snapshot, which is gitignored",
    }

    def _routes(self):
        """Read the literal paths out of `route()` rather than restating them."""
        src = inspect.getsource(research_ui.route)
        found = set(re.findall(r'path (?:==|in \()\s*"([^"]+)"', src))
        found |= set(re.findall(r'"(/[a-z/]+)"[,)]', src))
        return sorted(p for p in found
                      if p.startswith("/") and "<" not in p and not p.startswith("/static"))

    def test_the_route_table_is_discoverable(self):
        routes = self._routes()
        self.assertIn("/screener/draft", routes,
                      "the main surface is not discoverable from route(), so this guard "
                      "cannot cover it")
        self.assertGreater(len(routes), 8, "the route scan found suspiciously few routes")

    def test_no_route_raises(self):
        """Raising is worse than 503: it is an unhandled defect, and the server turns it into
        an opaque 500 with nothing in the log."""
        for path in self._routes():
            try:
                research_ui.route(path, {}, {})
            except Exception as exc:                       # noqa: BLE001 — that is the point
                self.fail("route({!r}) raised {}: {}".format(path, type(exc).__name__, exc))

    def test_the_screener_surfaces_return_200_and_carry_their_data(self):
        for path, marker in (("/screener/draft", "window.SCENARIOS"),
                             ("/screener/buckets", "window.LEDGER"),
                             ("/screen", "window.LEDGER")):
            code, body, _ct = research_ui.route(path, {}, {})
            self.assertEqual(code, 200, "{} did not serve".format(path))
            self.assertIn(marker, body, "{} lost {}".format(path, marker))

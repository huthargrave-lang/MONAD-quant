"""Guards for `tools/sweep_runner` — mostly one guard, restated from several directions.

`sweep.py --apply` REWRITES `config.py`, which the manifest denies as an armed-trader path.
The research UI now has a button that runs `sweep.py`. Everything below exists so that button
cannot become a remote control for the live strategy's parameters, and so the failure is
visible if someone later adds a passthrough that would let it.

The rest guard the honesty of the surface: that train and holdout stay separate, and that a
machine which cannot run the engine says so instead of offering a control that errors.
"""
import os
import re
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (REPO, os.path.join(REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import research_ui  # noqa: E402
import sweep_runner  # noqa: E402


class TheUiCannotArmTheTrader(unittest.TestCase):
    """`config.py` is deny-listed: changing it needs the trader stopped and explicit approval.
    A GET that could reach `--apply` would route around both."""

    def test_apply_is_absent_from_every_argv_it_can_build(self):
        """Not "we do not pass it" — it is unreachable. `build_argv` takes no flag that could
        become it, so no caller can opt in."""
        for ticker in ("QQQ", "TQQQ", "GC=F", "BRK.B"):
            for phase in sweep_runner.PHASES:
                for mode in ("optimistic", "realistic", "harsh"):
                    argv = sweep_runner.build_argv("/usr/bin/python3", ticker, phase, mode)
                    with self.subTest(ticker=ticker, phase=phase, mode=mode):
                        self.assertNotIn("--apply", argv)
                        self.assertFalse([a for a in argv if "apply" in a.lower()])

    def test_the_module_never_mentions_the_flag_at_all(self):
        """A string that is not there cannot be interpolated into an argument list by a later
        edit that looks harmless."""
        with open(os.path.join(REPO, "tools", "sweep_runner.py"), encoding="utf-8") as fh:
            src = fh.read()
        code = re.sub(r'"""[\s\S]*?"""', "", src)          # drop the docstrings that explain it
        code = re.sub(r"#[^\n]*", "", code)
        self.assertNotIn("--apply", code,
                         "the runner's code names the flag that rewrites config.py")

    def test_stdin_is_closed_so_the_config_prompt_cannot_be_answered_yes(self):
        """Without `--apply`, sweep.py STILL asks `Apply best_overall params to config.py?` and
        only a caught EOFError makes that a "n" (sweep.py:1702-1708). Inheriting the server's
        stdin would leave that answer to chance."""
        with open(os.path.join(REPO, "tools", "sweep_runner.py"), encoding="utf-8") as fh:
            src = fh.read()
        run_body = src[src.index("def _run("):src.index("def start(")]
        self.assertIn("stdin=subprocess.DEVNULL", run_body,
                      "the sweep subprocess inherits stdin, so the config.py prompt is live")

    def test_the_prompt_this_relies_on_is_still_shaped_that_way(self):
        """The guard above is only worth having while sweep.py still turns EOF into "n". If
        that changes, this fails rather than the protection silently evaporating."""
        with open(os.path.join(REPO, "sweep.py"), encoding="utf-8") as fh:
            src = fh.read()
        block = src[src.index("# ── Apply params to config.py?"):]
        block = block[:block.index("if answer in")]
        self.assertIn("except (EOFError, KeyboardInterrupt)", block,
                      "sweep.py no longer treats a closed stdin as declining to apply")
        self.assertIn('answer = "n"', block)

    def test_a_ticker_is_matched_not_interpolated(self):
        """The value arrives from a URL. Anything that is not a ticker never becomes an
        argument, and no shell is involved at any point."""
        for bad in ("QQQ; rm -rf /", "--apply", "$(id)", "`id`", "", "qqq", "../../etc/passwd",
                    "QQQ --apply", "A" * 40, "QQQ\nTQQQ"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    sweep_runner.build_argv("/usr/bin/python3", bad)
        with open(os.path.join(REPO, "tools", "sweep_runner.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertNotIn("shell=True", src)

    def test_a_bad_request_is_refused_by_the_route_before_anything_spawns(self):
        for query in ({"ticker": "QQQ; rm -rf /"}, {"ticker": "QQQ", "phase": "evil"},
                      {"ticker": ""}, {"ticker": "QQQ", "mode": "free-money"}):
            status, body, _ct = research_ui.route("/api/sweep/start", query, {})
            with self.subTest(query=query):
                self.assertEqual(status, 400, body)


class TheSweepSurfaceDoesNotOverclaim(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        _s, cls.html, _c = research_ui.route("/sweep", {}, {})

    def test_train_and_holdout_are_never_merged(self):
        """They answer different questions and only one is even trying to be out-of-sample.
        A single blended figure would be a third number neither run produced."""
        self.assertIn("Train", self.html)
        self.assertIn("Holdout", self.html)
        body = research_ui.SWEEP_JS
        self.assertIn("t[r[0]]", body)
        self.assertIn("h[r[0]]", body)
        for merged in ("(t[r[0]]+h[r[0]])", "avg(", "blend"):
            self.assertNotIn(merged, body, "the two columns are being combined")

    def test_the_page_says_the_holdout_is_what_the_presets_were_chosen_with(self):
        """This is the one thing a reader must not miss: the holdout column is the score the
        selection was made on, so it is not an untouched test of the winner."""
        self.assertIn("selected on", research_ui.SWEEP_JS)
        self.assertIn("holdout_live_score", self.html)
        self.assertRegex(self.html, r"not an\s+untouched test")

    def test_the_page_separates_studying_the_engine_from_using_the_sweep(self):
        """The request was explicit: say that the engine has been studied without implying the
        sweep hands back parameters worth trading."""
        # The claim is a card heading now rather than a sentence in a paragraph. Both
        # phrasings are checked as substance, not as one literal that a re-layout breaks.
        self.assertIn("Not a recommendation", self.html)
        self.assertIn("not the same as an edge", self.html)
        self.assertIn("D6", self.html)
        self.assertIn("no risk-adjusted", self.html)

    def test_a_degenerate_oversold_threshold_is_called_out(self):
        """An `rsi_oversold` of 80 admits nearly every bar. Printing it beside a Sharpe with no
        comment is how a search artifact reads as a finding."""
        self.assertIn("rsi_oversold", research_ui.SWEEP_JS)
        self.assertRegex(research_ui.SWEEP_JS, r"rsi_oversold\s*>=\s*7[05]")

    def test_the_read_only_claim_was_corrected_rather_than_left_false(self):
        """Every page footer said this server never writes. One surface now runs backtests and
        writes their results, so the sentence had to change with the behaviour."""
        self.assertNotIn("<footer>read-only ·", self.html)
        self.assertIn("except", self.html)

    def test_a_machine_that_cannot_run_the_engine_says_so_instead_of_offering_a_button(self):
        real = sweep_runner.find_interpreter
        sweep_runner.find_interpreter = lambda: None
        try:
            _s, html, _c = research_ui.route("/sweep", {}, {})
        finally:
            sweep_runner.find_interpreter = real
        self.assertIn("Cannot run here", html)
        self.assertNotIn('id="swGo"', html, "a dead run button is still rendered")

    def test_the_interpreter_split_is_disclosed_when_it_exists(self):
        """The server usually runs a venv that cannot import the engine at all, so the sweep
        runs on a different Python than the page. A reader comparing numbers deserves to know
        two interpreters were involved."""
        avail = sweep_runner.availability()
        if avail["runnable"] and not avail["is_current_process"]:
            self.assertIn("cannot import the strategy engine", self.html)
            self.assertIn("cannot import the strategy engine", self.html)


class TheInterpreterProbeIsReal(unittest.TestCase):

    def test_it_probes_by_importing_the_engine_not_by_reading_a_version(self):
        """A version comparison goes stale the moment the syntax floor moves. Importing the
        module that actually fails keeps the check true by construction."""
        self.assertIn("src.strategy.sizing", sweep_runner._PROBE)

    def test_availability_reports_a_reason_when_it_finds_nothing(self):
        real = sweep_runner.find_interpreter
        sweep_runner.find_interpreter = lambda: None
        try:
            avail = sweep_runner.availability()
        finally:
            sweep_runner.find_interpreter = real
        self.assertFalse(avail["runnable"])
        self.assertTrue(avail["why_not"])
        self.assertIn("3.10", avail["why_not"])

    def test_start_refuses_before_spawning_when_nothing_can_run(self):
        real = sweep_runner.find_interpreter
        sweep_runner.find_interpreter = lambda: None
        try:
            with self.assertRaises(RuntimeError):
                sweep_runner.start("QQQ")
        finally:
            sweep_runner.find_interpreter = real
        self.assertEqual(sweep_runner.jobs(), [], "a job was registered for a run that cannot happen")


if __name__ == "__main__":
    unittest.main()

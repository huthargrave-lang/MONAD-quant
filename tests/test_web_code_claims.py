"""Executable verification of the research web's claims ABOUT THE CODE.

Most of the web's claims are about markets, and this environment cannot check them
(market-data hosts are network-blocked, and F139 shows the load-bearing arc is not
reproducible from the repo anyway). But a subset of nodes make claims about *this
codebase*, and those are decidable right now, with certainty.

EPI-00 (F133) found that the web is only ever re-examined when adjacent new work
happens to touch it. That makes code-claims uniquely dangerous: the code moves
continuously, so a finding can rot without anyone noticing. These guards are
therefore **bidirectional** — each fails if the claim stops being true, with a
message telling the maintainer to update the WEB, not to "fix the test". A silent
fix that leaves a stale finding behind is exactly as much of a defect as a
regression.

Checks use the AST rather than grep so that a rename or reformat cannot quietly
make a guard vacuous.

Covered today:
  H27 — `use_regime_filter` runs at its default True in the backtest runner despite
        `config.USE_REGIME_FILTER = False`, while walk-forward honours the config.
  F26 — the 6-state slope-regime gate is dead-wired: `runner.py` never passes
        `use_slope_regime`/`longs_only`, and inside `generate_trades` they only
        adjust a Kelly-multiplier column, never gate an entry.
"""
import ast
import importlib
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ENGINE = ROOT / "src" / "strategy" / "engine.py"
RUNNER = ROOT / "src" / "backtest" / "runner.py"
WALKFWD = ROOT / "src" / "optimization" / "walk_forward.py"


def _calls_to(path, func_name):
    """Every ast.Call to `func_name` in `path`."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            name = getattr(f, "id", None) or getattr(f, "attr", None)
            if name == func_name:
                out.append(node)
    return out


def _param_default(path, func_name, param):
    """Default value of `param` in `func_name`'s signature, or a sentinel."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            args = node.args
            names = [a.arg for a in args.args]
            defaults = list(args.defaults)
            # defaults align to the TAIL of args.args
            offset = len(names) - len(defaults)
            if param in names:
                i = names.index(param)
                if i >= offset:
                    return ast.literal_eval(defaults[i - offset])
            kwnames = [a.arg for a in args.kwonlyargs]
            if param in kwnames:
                d = args.kw_defaults[kwnames.index(param)]
                return ast.literal_eval(d) if d is not None else None
    raise AssertionError(f"{func_name}({param}=...) not found in {path.name}")


class H27RegimeFilterClaim(unittest.TestCase):
    """H27 — OPEN bug: the backtest runner ignores config.USE_REGIME_FILTER."""

    def test_signature_default_is_true(self):
        self.assertIs(
            _param_default(ENGINE, "generate_trades", "use_regime_filter"), True,
            "generate_trades(use_regime_filter=...) no longer defaults to True — H27's "
            "premise changed. Re-verify H27 and update the web node.",
        )

    def test_config_says_false(self):
        cfg = importlib.import_module("config")
        self.assertIs(
            cfg.USE_REGIME_FILTER, False,
            "config.USE_REGIME_FILTER is no longer False — H27's premise changed. "
            "Re-verify H27 and update the web node.",
        )

    def test_runner_still_omits_the_flag(self):
        """The bug itself. If this fails, H27 was FIXED — update the web."""
        calls = _calls_to(RUNNER, "generate_trades")
        self.assertTrue(calls, "no generate_trades call found in runner.py")
        passes_flag = any(
            kw.arg == "use_regime_filter" for c in calls for kw in c.keywords
        )
        self.assertFalse(
            passes_flag,
            "runner.py NOW passes use_regime_filter — H27 appears FIXED. This is good "
            "news, but it means the web is stale AND every backtest number changed: "
            "supersede H27 (note.py supersede H27 --by <new> --reason data-fixed) and "
            "re-baseline the affected findings before deleting this guard.",
        )

    def test_walk_forward_does_honour_the_flag(self):
        """The asymmetry is the substance of H27: the two evidence-producing paths
        apply different entry gates, so their numbers are not comparable."""
        calls = _calls_to(WALKFWD, "generate_trades")
        self.assertTrue(calls, "no generate_trades call found in walk_forward.py")
        self.assertTrue(
            any(kw.arg == "use_regime_filter" for c in calls for kw in c.keywords),
            "walk_forward.py no longer passes use_regime_filter — the runner/"
            "walk-forward asymmetry H27 describes has changed shape. Re-verify H27.",
        )


class F26SlopeRegimeClaim(unittest.TestCase):
    """F26 — the slope-regime 'core innovation' is dead-wired."""

    def test_runner_never_passes_the_slope_flags(self):
        calls = _calls_to(RUNNER, "generate_trades")
        self.assertTrue(calls, "no generate_trades call found in runner.py")
        passed = {
            kw.arg for c in calls for kw in c.keywords
            if kw.arg in {"use_slope_regime", "longs_only"}
        }
        self.assertEqual(
            passed, set(),
            "runner.py NOW passes slope-regime flags "
            f"({sorted(passed)}) — F26 appears FIXED/re-wired. Every backtest number "
            "changes if so: re-verify F26 and supersede it rather than editing it.",
        )

    def test_slope_flags_default_off(self):
        for flag in ("use_slope_regime", "longs_only"):
            with self.subTest(flag=flag):
                self.assertIs(
                    _param_default(ENGINE, "generate_trades", flag), False,
                    f"generate_trades({flag}=...) no longer defaults to False — "
                    "F26's premise changed.",
                )

    def test_slope_flags_only_touch_the_kelly_column_not_entries(self):
        """F26's substance: the flags exist but gate nothing. Inside generate_trades
        every block guarded by a slope flag may WRITE only `regime_kelly_mult`; it
        may read entry_signal to build a mask, but never assign to it.

        Only assignment TARGETS are inspected — `bear_long_mask = (df["entry_signal"]
        == 1) & ...` reads the column and is not a gate, whereas
        `df.loc[mask, "entry_signal"] = 0` is.
        """
        tree = ast.parse(ENGINE.read_text(encoding="utf-8"))
        fn = next(
            n for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "generate_trades"
        )
        entry_names = {"long_entry", "short_entry", "entry_signal"}
        offenders = []
        for node in ast.walk(fn):
            if not isinstance(node, ast.If):
                continue
            if not any(
                isinstance(n, ast.Name) and n.id in {"use_slope_regime", "longs_only"}
                for n in ast.walk(node.test)
            ):
                continue
            for stmt in ast.walk(ast.Module(body=node.body, type_ignores=[])):
                targets = []
                if isinstance(stmt, ast.Assign):
                    targets = stmt.targets
                elif isinstance(stmt, (ast.AugAssign, ast.AnnAssign)):
                    targets = [stmt.target]
                for tgt in targets:
                    written = {
                        n.value for n in ast.walk(tgt)
                        if isinstance(n, ast.Constant) and isinstance(n.value, str)
                    } | {
                        n.id for n in ast.walk(tgt) if isinstance(n, ast.Name)
                    }
                    if written & entry_names:
                        offenders.append(ast.unparse(stmt))
        self.assertEqual(
            offenders, [],
            "a slope-regime flag now guards a block that ASSIGNS to an entry signal "
            f"({offenders}) — F26 ('dead-wired, gates nothing') appears FIXED. "
            "Re-verify F26 and supersede it; backtest numbers will have changed.",
        )

    def test_the_detector_would_actually_catch_a_rewiring(self):
        """Negative control: a guard that cannot fail is worthless. Synthesise the
        code F26 says is absent and confirm the same logic flags it."""
        src = (
            "def generate_trades(df, use_slope_regime=False, longs_only=False):\n"
            "    if use_slope_regime and longs_only:\n"
            "        mask = df['regime'] == 'BEAR'\n"
            "        df.loc[mask, 'entry_signal'] = 0\n"
            "    return df\n"
        )
        fn = next(
            n for n in ast.walk(ast.parse(src))
            if isinstance(n, ast.FunctionDef) and n.name == "generate_trades"
        )
        found = []
        for node in ast.walk(fn):
            if not isinstance(node, ast.If):
                continue
            if not any(
                isinstance(n, ast.Name) and n.id in {"use_slope_regime", "longs_only"}
                for n in ast.walk(node.test)
            ):
                continue
            for stmt in ast.walk(ast.Module(body=node.body, type_ignores=[])):
                if isinstance(stmt, ast.Assign):
                    for tgt in stmt.targets:
                        strs = {
                            n.value for n in ast.walk(tgt)
                            if isinstance(n, ast.Constant) and isinstance(n.value, str)
                        }
                        if strs & {"entry_signal"}:
                            found.append(ast.unparse(stmt))
        self.assertTrue(found, "the F26 detector failed to flag a synthetic rewiring")


class F23PerModeWindowsClaim(unittest.TestCase):
    """F23 — per-mode RSI period + MACD windows never reach the entry signal.

    `ctx claims` reports this bridge as UNGUARDED and asks for a test that ASSERTS
    the claim rather than merely exercising the symbol. This is that test: it checks
    the mechanism structurally (AST) *and* reproduces F23's own stated empirical
    proof — `momentum_signal` byte-identical for period 7 vs 14 while the stored
    `rsi`/`macd_hist` columns differ.

    The live trader rides this path (`live/signals.py` -> `build_features` ->
    `add_momentum_features` -> `momentum_signal`), so the armed bot trades on
    RSI-14 / MACD-12-26-9 regardless of config. Per F23, fixing it changes live
    entries and invalidates every sweep tuned with the bug present — it needs a
    re-sweep and sign-off with the trader stopped, not a unilateral edit.
    """

    MOMENTUM = ROOT / "src" / "signals" / "momentum.py"

    def test_momentum_signal_recomputes_without_period_arguments(self):
        """Structural half: inside momentum_signal, compute_rsi/compute_macd are
        called with the close series only — no period is threaded through."""
        tree = ast.parse(self.MOMENTUM.read_text(encoding="utf-8"))
        fn = next(
            n for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "momentum_signal"
        )
        checked = 0
        for node in ast.walk(fn):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if name not in {"compute_rsi", "compute_macd"}:
                continue
            checked += 1
            extra = [a for a in node.args[1:]] + list(node.keywords)
            self.assertEqual(
                extra, [],
                f"{name}() inside momentum_signal now receives period arguments — "
                "F23 appears FIXED. Per F23 this changes LIVE entries and invalidates "
                "every sweep tuned with the bug present: supersede F23, re-sweep, and "
                "get sign-off with the trader stopped before relying on this.",
            )
        self.assertEqual(
            checked, 2,
            "expected exactly one compute_rsi and one compute_macd call inside "
            f"momentum_signal, found {checked} — F23's mechanism has changed shape.",
        )

    def test_empirical_proof_signal_invariant_to_periods(self):
        """Empirical half: F23's own reproduction, on synthetic data."""
        try:
            import numpy as np
            import pandas as pd
        except ImportError:  # pragma: no cover - bare env
            self.skipTest("numpy/pandas unavailable")
        from src.signals.momentum import add_momentum_features

        rng = np.random.default_rng(11)
        n = 1200
        idx = pd.date_range("2021-01-01", periods=n, freq="D", tz="UTC")
        close = 100 * np.exp(np.cumsum(rng.normal(0, 0.012, n)))
        df = pd.DataFrame(
            {
                "open": close * (1 + rng.normal(0, 0.001, n)),
                "high": close * (1 + abs(rng.normal(0, 0.004, n))),
                "low": close * (1 - abs(rng.normal(0, 0.004, n))),
                "close": close,
                "volume": rng.integers(1e5, 1e6, n),
            },
            index=idx,
        )
        fast = add_momentum_features(
            df.copy(), rsi_period=7, macd_fast=5, macd_slow=13, macd_signal_period=4
        )
        slow = add_momentum_features(
            df.copy(), rsi_period=14, macd_fast=12, macd_slow=26, macd_signal_period=9
        )
        # The config DOES reach the stored columns...
        self.assertFalse(
            fast["rsi"].fillna(-1).equals(slow["rsi"].fillna(-1)),
            "stored rsi no longer varies with rsi_period — F23's premise changed.",
        )
        self.assertFalse(
            fast["macd_hist"].fillna(-1).equals(slow["macd_hist"].fillna(-1)),
            "stored macd_hist no longer varies with the MACD windows — premise changed.",
        )
        # ...but never reaches the entry signal.
        self.assertTrue(
            fast["momentum_signal"].equals(slow["momentum_signal"]),
            "momentum_signal now VARIES with the per-mode windows — F23 appears "
            "FIXED. Supersede F23 and re-sweep (see the docstring): every prior "
            "sweep was tuned with the bug present.",
        )


LIVE_SIGNALS = ROOT / "live" / "signals.py"
GAP_STUDY = ROOT / "tools" / "overnight_gap_risk_study.py"


def _kwarg(call, name):
    """The keyword argument `name` on an ast.Call, or None if not passed."""
    for kw in call.keywords:
        if kw.arg == name:
            return kw
    return None


class FourSiteGateTests(unittest.TestCase):
    """H27 is not backtest-vs-walk-forward — the runner is the odd one out of FOUR.

    F140 framed the `use_regime_filter` divergence as two paths disagreeing. Counting
    every production call site of `generate_trades` shows the runner disagreeing with
    all three others *and* with its own stated intent two lines earlier:

        runner.py              not passed        -> signature default True
        walk_forward.py        _cfg.USE_REGIME_FILTER
        live/signals.py        hardcoded False
        overnight_gap_risk...  study parameter (varied deliberately)

    Two consequences the two-path framing hides. (1) walk-forward and live agree only
    COINCIDENTALLY, at today's config value: flipping `config.USE_REGIME_FILTER` to
    True moves the OOS selector and leaves the armed bot where it is. (2) the runner
    computes the correct per-timeframe gate, hands it to the diagnostics printer, and
    then never hands it to `generate_trades` — so with `VERBOSE_SIGNALS=True` every
    backtest prints a gate it did not trade.
    """

    def test_generate_trades_has_exactly_these_production_call_sites(self):
        """Bidirectional: a NEW caller must be classified here, not silently ignored."""
        sites = {}
        for path in (RUNNER, WALKFWD, LIVE_SIGNALS, GAP_STUDY):
            sites[path.name] = len(_calls_to(path, "generate_trades"))
        self.assertEqual(
            sites,
            {"runner.py": 1, "walk_forward.py": 1, "signals.py": 1,
             "overnight_gap_risk_study.py": 1},
            "the set of production generate_trades call sites changed — re-verify "
            "which ones pass use_regime_filter and supersede the web node.",
        )

    def test_runner_is_the_only_caller_that_omits_the_gate(self):
        self.assertIsNone(
            _kwarg(_calls_to(RUNNER, "generate_trades")[0], "use_regime_filter"),
            "runner.py now PASSES use_regime_filter — H27 appears fixed. Supersede "
            "the web node and re-baseline every backtest number, which was produced "
            "with the gate at its default True.",
        )
        for path in (WALKFWD, LIVE_SIGNALS, GAP_STUDY):
            self.assertIsNotNone(
                _kwarg(_calls_to(path, "generate_trades")[0], "use_regime_filter"),
                "{} stopped passing use_regime_filter — the divergence changed "
                "shape; re-verify the web node.".format(path.name),
            )

    def test_walkforward_and_live_agree_only_by_coincidence(self):
        """walk-forward reads the config; live hardcodes False. They match today
        because the config happens to be False. That is a latent divergence, not
        agreement — assert the MECHANISM, not the current value."""
        import config

        wf = _kwarg(_calls_to(WALKFWD, "generate_trades")[0], "use_regime_filter")
        self.assertIsInstance(
            wf.value, ast.Attribute,
            "walk_forward no longer reads the gate from config — re-verify.")
        self.assertEqual(wf.value.attr, "USE_REGIME_FILTER")

        live = _kwarg(_calls_to(LIVE_SIGNALS, "generate_trades")[0], "use_regime_filter")
        self.assertIsInstance(
            live.value, ast.Constant,
            "live/signals.py no longer hardcodes the gate — if it now reads config, "
            "the coincidence is resolved and the web node should be superseded.")
        self.assertIs(live.value.value, False)

        self.assertFalse(
            config.USE_REGIME_FILTER,
            "config.USE_REGIME_FILTER is now True, so walk-forward and live have "
            "ACTUALLY diverged: the OOS selector gates entries the armed bot does "
            "not. This is the latent bug firing — do not just update this test.",
        )

    def test_runner_diagnostics_describe_a_gate_the_trades_do_not_use(self):
        """The smoking gun: the correct value is computed, printed, and dropped."""
        import config

        printed = _calls_to(RUNNER, "_print_signal_diagnostics")
        self.assertEqual(len(printed), 1)
        # third positional arg is the computed `use_regime`
        self.assertEqual(
            getattr(printed[0].args[2], "id", None), "use_regime",
            "runner no longer prints the computed gate — re-verify the claim.")
        self.assertTrue(
            getattr(config, "VERBOSE_SIGNALS", False),
            "VERBOSE_SIGNALS is off, so the misleading diagnostic no longer prints; "
            "the wiring bug remains but its visible symptom is gone.",
        )
        gate_default = _param_default(ENGINE, "generate_trades", "use_regime_filter")
        self.assertNotEqual(
            bool(gate_default), bool(config.USE_REGIME_FILTER),
            "the printed gate and the traded gate now AGREE — the diagnostic is no "
            "longer misleading. Supersede the web node.",
        )


SIGNALS_DIR = ROOT / "src" / "signals"
SIZING = ROOT / "src" / "strategy" / "sizing.py"


def _first_party_sources():
    """Every first-party .py, excluding tests and vendored/venv trees."""
    for path in ROOT.rglob("*.py"):
        parts = set(path.parts)
        if parts & {"venv", ".git", "__pycache__", "tests"}:
            continue
        yield path


class DeadSizingKnobTests(unittest.TestCase):
    """Five sizing knobs are written or configured and read by NOTHING.

    Scope note, because the broader version of this claim does not survive: the
    executed sizing is NOT undocumented. `config_modules/base.py` sets
    POSITION_SIZING_MODE='fixed', `runner.py:351` PRINTS "Sizing: Fixed 10% per
    trade" in every result block, `sweep_sizing.py`'s docstring explains the fixed
    default as a deliberate live-alignment choice, and F28 records it. Kelly is also
    still reachable — `walk_forward.py` runs its own half-Kelly equity loop and
    `sweep.py --sizing kelly` exists.

    What IS defective is narrower and fully mechanical: these five knobs have no
    consumer on ANY path, so they read as live tuning surface while governing
    nothing. CLAUDE.md compounds it by documenting a multiplier chain
    (`kelly_trade = min(base_kelly x regime_mult x adx_mult, pos_cap)`) that exists
    in no code path, citing `volatility.py:133-135` in a 115-line file.
    """

    # Files that read a dead knob in order to DEMONSTRATE it is dead. The claim is
    # "no code path applies this to a position size"; a probe that hashes the column to
    # show the slope flags move it is evidence for that claim, not a counterexample.
    # Ratcheted below: this set must be exactly these files, and each must be shown to
    # never multiply anything by the knob.
    OBSERVERS = {"tools/entry_gate_probe.py"}

    def _read_sites(self, name, writers):
        """Files mentioning `name` that are not its declared writers or observers."""
        hits = []
        for path in _first_party_sources():
            rel = str(path.relative_to(ROOT))
            if rel in writers or rel in self.OBSERVERS:
                continue
            if name in path.read_text(encoding="utf-8"):
                hits.append(rel)
        return hits

    def test_the_observer_exemption_is_exactly_the_declared_files(self):
        """A ratchet: fails if the set grows (new debt) and if it shrinks (stale list)."""
        present = {rel for rel in self.OBSERVERS if (ROOT / rel).exists()}
        self.assertEqual(
            present, self.OBSERVERS,
            "an exempted observer no longer exists — drop it from OBSERVERS rather "
            "than leaving a dead exemption that could silently cover a real consumer")

    def test_no_observer_multiplies_anything_by_a_dead_knob(self):
        """The exemption is for reading, not for applying. This is what makes it safe."""
        knobs = ("regime_kelly_mult", "adx_kelly_mult")
        for rel in self.OBSERVERS:
            tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
                    text = ast.unparse(node)
                    for knob in knobs:
                        self.assertNotIn(
                            knob, text,
                            "{} multiplies by {} at line {} — that is applying the "
                            "knob, not observing it. The exemption does not cover it; "
                            "if the knob went live, supersede the web node.".format(
                                rel, knob, node.lineno))

    def test_adx_kelly_mult_is_computed_and_consumed_by_nothing(self):
        hits = self._read_sites("adx_kelly_mult", {"src/signals/volatility.py"})
        self.assertEqual(
            hits, [],
            "adx_kelly_mult now has a consumer ({}) — the ADX multiplier may be "
            "live again. Re-verify and supersede the web node.".format(hits),
        )

    def test_regime_kelly_mult_is_computed_and_consumed_by_nothing(self):
        hits = self._read_sites(
            "regime_kelly_mult",
            {"src/signals/momentum.py", "src/strategy/engine.py"},
        )
        self.assertEqual(
            hits, [],
            "regime_kelly_mult now has a consumer ({}) — the regime multiplier may "
            "be live again. Re-verify and supersede.".format(hits),
        )

    def test_use_adx_sizing_has_no_reader_at_all(self):
        hits = self._read_sites("USE_ADX_SIZING", {"config.py"})
        self.assertEqual(
            hits, [],
            "USE_ADX_SIZING is read somewhere now ({}) — it was pure dead "
            "config.".format(hits),
        )

    def test_max_position_pct_strong_bull_has_no_reader(self):
        """CLAUDE.md calls this the 'KEY FIX' worth 10.55%->11.05% and Sharpe
        4.844->4.924. Nothing reads it."""
        hits = self._read_sites("MAX_POSITION_PCT_STRONG_BULL", {"config.py"})
        self.assertEqual(
            hits, [],
            "MAX_POSITION_PCT_STRONG_BULL now has a reader ({}) — the STRONG_BULL "
            "cap may be live. Re-verify and re-baseline.".format(hits),
        )

    def test_bull_kelly_multiplier_is_born_dead(self):
        """Threaded main.py -> runner signature -> nowhere. It appears exactly once
        in runner.py: the parameter declaration itself."""
        source = RUNNER.read_text(encoding="utf-8")
        self.assertEqual(
            source.count("bull_kelly_multiplier"), 1,
            "bull_kelly_multiplier is now referenced more than once in runner.py — "
            "it may have acquired a consumer. Re-verify and supersede.",
        )

    def test_claude_md_cites_a_line_range_that_does_not_exist(self):
        """The doc's ADX cite points past the end of the file it names — evidence
        the claim was never re-verified after the code moved."""
        volatility = SIGNALS_DIR / "volatility.py"
        n_lines = len(volatility.read_text(encoding="utf-8").splitlines())
        claude = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        if "volatility.py:133-135" not in claude:
            self.skipTest("CLAUDE.md's stale ADX cite was corrected — good")
        self.assertLess(
            n_lines, 133,
            "volatility.py is now long enough for CLAUDE.md's cite to be valid — "
            "re-check whether the ADX claim became true.",
        )


if __name__ == "__main__":
    unittest.main()


class UtcGateLandsInsideTheCoarseEdgeRegimeTests(unittest.TestCase):
    """F148's timezone bug is not a random defect — it lands on F14's edge regime.

    F14 decomposed the hourly "edge" by BAR-SAMPLING FREQUENCY: QQQ AM (3 bars/day)
    Sharpe 3.72, PM (4 bars/day) 3.31, ALL-DAY (7 bars/day) **-0.75**. Its mechanism
    is arithmetic — RSI(7) over 3 bars/day spans ~2.3 trading days and captures
    multi-day mean reversion, while over 7 bars/day it spans ~1 day and captures
    intraday noise.

    F148 found `main.py` applies a (9,16) gate to a UTC-NAIVE index, keeping 2 of 7
    session bars in winter and 3 in summer. Those are the SAME coarse regimes F14
    credits with the edge. So an hourly backtest run through `main.py` is silently
    measuring F14's AM subsample, while the live bot trades all-day.

    That gives the backtest-vs-live gap a second, independent mechanism. F12/F13
    attributed it to the DATA path (a 710-day fetch returning morning-only bars);
    this shows the ENTRY GATE reproduces the same artifact on correct full-session
    data. Fixing the fetch would not have removed it.

    The arithmetic is pinned here because it is decidable offline; the Sharpe figures
    are F14's and are not re-measured (market data is unavailable).
    """

    SESSION_BARS = 7          # 09:30..15:30 ET hourly
    RSI_PERIOD = 7

    def _bars_kept(self, utc_offset_hours):
        """Session bars surviving a (9,16) filter applied to a UTC-naive index."""
        return sum(1 for hour_et in range(9, 16)
                   if 9 <= (hour_et + utc_offset_hours) < 16)

    def test_the_gate_keeps_two_to_three_of_seven_session_bars(self):
        winter, summer = self._bars_kept(5), self._bars_kept(4)
        self.assertEqual((winter, summer), (2, 3),
                         "the UTC-gate retention changed — re-verify F148 and the "
                         "regime mapping below before citing either")

    def test_those_retentions_are_F14s_COARSE_regime_not_the_all_day_one(self):
        """The load-bearing claim: the bug lands where F14 says the edge lives."""
        for offset in (5, 4):
            kept = self._bars_kept(offset)
            self.assertLessEqual(
                kept, 3,
                "the gate now keeps {} bars/day, which is no longer F14's coarse "
                "regime — the mechanism linking F148 to F14 has changed".format(kept))
            self.assertLess(
                kept, self.SESSION_BARS,
                "the gate keeps the full session, so it no longer subsamples at all")

    def test_the_indicator_span_separates_the_two_regimes(self):
        """F14's stated mechanism, as arithmetic: ~2+ trading days vs ~1."""
        coarse = self.RSI_PERIOD / 3          # AM subsample and the summer gate
        all_day = self.RSI_PERIOD / self.SESSION_BARS
        self.assertGreater(coarse, 2.0, "the coarse regime no longer spans multi-day")
        self.assertLessEqual(all_day, 1.05, "the all-day regime no longer spans ~1 day")
        self.assertGreater(
            coarse / all_day, 2.0,
            "the two regimes' indicator spans have converged, so F14's "
            "coarse-vs-hourly distinction no longer holds arithmetically")

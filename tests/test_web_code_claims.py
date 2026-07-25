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


if __name__ == "__main__":
    unittest.main()

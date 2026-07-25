"""The live trader's mode/symbol coherence invariant (RESEARCH_WEB.md F157).

WHAT THIS GUARDS. The live path reads its instrument from two config keys:

  * `build_features()` resolves the per-mode signal thresholds — RSI_OVERSOLD, the
    VWAP z-score threshold, the MACD windows — from `config.ACTIVE_MODE`
    (src/strategy/engine.py:31-32), which is a *backtest* selector.
  * everything else keys on `config.LIVE_SYMBOL`: the bars, `require_signals`, and
    the target/stop through `live/trader.py::_get_asset_config`, which builds
    `f"{LIVE_SYMBOL}_HOURLY"`.

Nothing required them to agree, and `--symbol` sets only `LIVE_SYMBOL` — so
`--symbol GDXU` would have armed the trader on GDXU using TQQQ's entry thresholds.

HOW THIS TEST LOADS THE CODE. It extracts the function's source with `ast` and
execs it against a stub config, rather than importing `live.trader`. Two reasons:
the module imports `dotenv`, which is not installed in every environment (the same
gap that makes two other test modules error out); and more importantly, this is the
armed-trader module — a unit test should not import it as a side effect. The
extraction is by function NAME, so if the function is renamed or deleted this test
fails loudly instead of silently passing on nothing.
"""
import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRADER = ROOT / "live" / "trader.py"
FUNC = "_assert_mode_symbol_coherent"


def _load_check():
    """Return the invariant function, exec'd in isolation with no `config` bound."""
    source = TRADER.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == FUNC:
            namespace = {}
            exec(ast.get_source_segment(source, node), namespace)
            return namespace[FUNC], namespace
    raise AssertionError(
        "{} is gone from live/trader.py. If it was removed deliberately, the F157 "
        "divergence is unguarded again: --symbol would arm the trader on one "
        "instrument using another's signal thresholds.".format(FUNC))


class _Config:
    def __init__(self, symbol, mode=...):
        self.LIVE_SYMBOL = symbol
        if mode is not ...:
            self.ACTIVE_MODE = mode


class ModeSymbolInvariantTests(unittest.TestCase):
    def setUp(self):
        self.check, self.namespace = _load_check()

    def _run(self, cfg):
        self.namespace["config"] = cfg
        return self.check()

    def test_the_shipped_config_passes(self):
        """The invariant must not change behaviour today. If this fails, the repo's
        own config is incoherent and the trader would refuse to start."""
        import config as real

        self._run(real)  # must not raise

    def test_symbol_override_without_a_matching_mode_is_REFUSED(self):
        """The exact scenario: `--symbol GDXU` sets LIVE_SYMBOL alone."""
        with self.assertRaises(SystemExit) as ctx:
            self._run(_Config("GDXU", "TQQQ_HOURLY"))
        message = str(ctx.exception)
        self.assertIn("REFUSING TO START", message)
        self.assertIn("GDXU_HOURLY", message, "must name the value to set")
        self.assertIn("F157", message, "must cite the finding for the operator")

    def test_a_coherent_override_is_allowed(self):
        """Not merely strict — a properly-paired override must still work, or the
        invariant would break the supported workflow instead of protecting it."""
        self._run(_Config("QQQ", "QQQ_HOURLY"))

    def test_a_missing_ACTIVE_MODE_is_refused_not_crashed(self):
        """`getattr(..., None)` must yield a clean refusal, not AttributeError."""
        with self.assertRaises(SystemExit):
            self._run(_Config("TQQQ"))

    def test_it_refuses_rather_than_silently_auto_correcting(self):
        """Rewriting ACTIVE_MODE would change which thresholds fire — an operator
        decision. Assert the function never mutates the config it was given."""
        cfg = _Config("GDXU", "TQQQ_HOURLY")
        with self.assertRaises(SystemExit):
            self._run(cfg)
        self.assertEqual(cfg.ACTIVE_MODE, "TQQQ_HOURLY", "invariant mutated config")
        self.assertEqual(cfg.LIVE_SYMBOL, "GDXU")


class WiringTests(unittest.TestCase):
    """A guard that is never called is not a guard."""

    def setUp(self):
        self.source = TRADER.read_text(encoding="utf-8")
        self.tree = ast.parse(self.source)

    def test_the_invariant_is_actually_called(self):
        called = any(
            isinstance(n, ast.Call) and getattr(n.func, "id", None) == FUNC
            for n in ast.walk(self.tree))
        self.assertTrue(called, "{} is defined but never called".format(FUNC))

    def test_it_runs_AFTER_the_symbol_override_and_before_connecting(self):
        """Order is the whole point: checking before `--symbol` is applied would
        validate the default and let the override through unchecked.

        Located by AST line number, not by string search — `str.index(FUNC + "()")`
        matches the `def` line first, which made an earlier version of this test
        compare the definition's position instead of the call's.
        """
        call_lines = [
            n.lineno for n in ast.walk(self.tree)
            if isinstance(n, ast.Call) and getattr(n.func, "id", None) == FUNC]
        self.assertTrue(call_lines, "{} is never called".format(FUNC))
        call = min(call_lines)

        lines = self.source.splitlines()
        override = next(
            i + 1 for i, l in enumerate(lines)
            if "config.LIVE_SYMBOL = args.symbol.upper()" in l)
        self.assertGreater(
            call, override,
            "the invariant runs BEFORE --symbol is applied (line {} vs {}), so it "
            "would check the default config and let the override through "
            "unvalidated".format(call, override))

        # The first thing main() does with the broker is fetch the account, which is
        # what actually exercises the connection. Matched on any `broker.*` call
        # rather than on "broker.connect(" — that string does not appear anywhere, so
        # an earlier version of this assertion could never have failed, and a guard
        # that cannot fail is not a guard.
        #
        # Scoped to main()'s own body: `broker.*` calls inside on_bar() and other
        # helpers are defined earlier in the file but run later, so walking the whole
        # module compares against a line number that is not a startup ordering at all.
        main_fn = next(
            (n for n in ast.walk(self.tree)
             if isinstance(n, ast.FunctionDef) and n.name == "main"), None)
        self.assertIsNotNone(main_fn, "live/trader.py has no main() — re-check wiring")
        broker_uses = [
            n.lineno for n in ast.walk(main_fn)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and getattr(n.func.value, "id", None) == "broker"
        ]
        self.assertTrue(
            broker_uses,
            "no broker.* call found in live/trader.py — the module changed shape; "
            "re-check that the invariant still precedes broker contact")
        self.assertLess(
            call, min(broker_uses),
            "the invariant runs AFTER the first broker call (line {} vs {}), so a "
            "mismatched config could reach the broker before being "
            "rejected".format(call, min(broker_uses)))


if __name__ == "__main__":
    unittest.main()

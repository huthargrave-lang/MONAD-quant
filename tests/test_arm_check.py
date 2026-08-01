"""tools/arm_check.py — "would this tree arm?", and the ways that question lies.

The failure being guarded is specific. Origin's live/trader.py refuses to start
when config.ACTIVE_MODE and config.LIVE_SYMBOL disagree, and NOTHING in this repo
notices: the tree imports, the unit tests pass, deploy/smoke-test.sh passes, and
then the bot does not arm. So a checker for it is worth having.

But a checker for it is only worth having if it cannot say OK when it is wrong.
A false all-clear is worse than no checker at all — it converts an unknown into a
confident wrong answer, and an operator who trusts it stops looking. So most of
these tests are about the INDETERMINATE verdict: every shape of refusal the tool
does not recognise must land on 3, never 0.

Fixtures are synthetic trees rather than the real one. The real live/trader.py is
DENY-fenced and must never be mutated to test a checker, and a fixture can express
refusal shapes that do not exist in the repo yet — which is the point, since the
next refusal to be added will not look like the last one.
"""

import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TOOL = REPO / "tools" / "arm_check.py"

OK, REFUSES, INDETERMINATE, USAGE = 0, 2, 3, 4


def tree(trader_body: str, config_body: str = "LIVE_SYMBOL='TQQQ'\nACTIVE_MODE='TQQQ_HOURLY'\n"):
    """Materialise a minimal MONAD-shaped checkout."""
    d = Path(tempfile.mkdtemp())
    (d / "live").mkdir()
    (d / "live" / "trader.py").write_text(textwrap.dedent(trader_body))
    (d / "config.py").write_text(textwrap.dedent(config_body))
    return d


def run(root: Path):
    p = subprocess.run([sys.executable, str(TOOL), "--tree", str(root)],
                       capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr)


class ArmsCleanly(unittest.TestCase):
    def test_a_passing_guard_reports_would_arm(self):
        rc, out = run(tree("""
            import config
            def _assert_mode_symbol_coherent():
                if config.ACTIVE_MODE != f"{config.LIVE_SYMBOL}_HOURLY":
                    raise SystemExit("mismatch")
            def main():
                _assert_mode_symbol_coherent()
                broker.connect()
        """))
        self.assertEqual(rc, OK, out)
        self.assertIn("WOULD_ARM", out)


class RefusesIsDefinite(unittest.TestCase):
    def test_incoherent_config_is_a_definite_refusal(self):
        rc, out = run(tree("""
            import config
            def _assert_mode_symbol_coherent():
                if config.ACTIVE_MODE != f"{config.LIVE_SYMBOL}_HOURLY":
                    raise SystemExit(
                        f"REFUSING: {config.LIVE_SYMBOL!r} vs {config.ACTIVE_MODE!r}")
            def main():
                _assert_mode_symbol_coherent()
                broker.connect()
        """, config_body="LIVE_SYMBOL='GDXU'\nACTIVE_MODE='TQQQ_HOURLY'\n"))
        self.assertEqual(rc, REFUSES, out)
        self.assertIn("REFUSES", out)
        self.assertIn("GDXU", out, "the refusal message must name the offending values")

    def test_refusal_exit_code_is_not_one(self):
        """A caller doing `if rc:` must not read an unexpected crash as REFUSES."""
        self.assertNotEqual(REFUSES, 1)


class NoFalseAllClear(unittest.TestCase):
    """Every unrecognised refusal shape must be INDETERMINATE, never OK."""

    def test_no_guard_at_all_is_indeterminate_not_ok(self):
        rc, out = run(tree("""
            def main():
                broker.connect()
        """))
        self.assertEqual(rc, INDETERMINATE, out)

    def test_a_bare_system_exit_beside_a_healthy_guard_is_indeterminate(self):
        """The exact false-all-clear: a real guard passes, but a DIFFERENTLY shaped
        refusal sits next to it. Counting only the guard would exit 0 on a tree that
        cannot arm."""
        rc, out = run(tree("""
            import config
            def _assert_mode_symbol_coherent():
                return
            def main():
                _assert_mode_symbol_coherent()
                if config.LIVE_SYMBOL == 'TQQQ':
                    raise SystemExit("some other refusal entirely")
                broker.connect()
        """))
        self.assertEqual(rc, INDETERMINATE, out)
        self.assertIn("SystemExit", out)

    def test_sys_exit_in_the_slice_is_indeterminate(self):
        rc, out = run(tree("""
            import sys, config
            def _check_thing(): return
            def main():
                _check_thing()
                sys.exit(2)
                broker.connect()
        """))
        self.assertEqual(rc, INDETERMINATE, out)

    def test_unrecognised_module_level_call_is_indeterminate(self):
        """A refusal hiding behind a name that does not match the guard convention."""
        rc, out = run(tree("""
            import config
            def validate_live_config():
                raise SystemExit("refused")
            def main():
                validate_live_config()
                broker.connect()
        """))
        self.assertEqual(rc, INDETERMINATE, out)
        self.assertIn("validate_live_config", out)

    def test_a_guard_that_errors_is_indeterminate_not_pass(self):
        rc, out = run(tree("""
            def _assert_something():
                return UNDEFINED_GLOBAL
            def main():
                _assert_something()
                broker.connect()
        """))
        self.assertEqual(rc, INDETERMINATE, out)

    def test_unparseable_trader_is_indeterminate(self):
        rc, out = run(tree("def main(:\n"))
        self.assertEqual(rc, INDETERMINATE, out)

    def test_missing_main_is_indeterminate(self):
        rc, out = run(tree("def something_else():\n    pass\n"))
        self.assertEqual(rc, INDETERMINATE, out)


class SliceBoundary(unittest.TestCase):
    def test_a_guard_after_the_first_broker_call_does_not_count(self):
        """Only refusals BEFORE any broker contact are free. One after it has already
        touched the outside world, so it is not what 'would it arm' asks about."""
        rc, out = run(tree("""
            def _assert_late(): return
            def main():
                broker.connect()
                _assert_late()
        """))
        self.assertEqual(rc, INDETERMINATE, out)


class Usage(unittest.TestCase):
    def test_a_non_monad_directory_is_usage_not_a_verdict(self):
        d = Path(tempfile.mkdtemp())
        rc, _ = run(d)
        self.assertEqual(rc, USAGE)


class AgainstTheRealTree(unittest.TestCase):
    def test_this_repo_returns_a_valid_verdict_without_crashing(self):
        rc, out = run(REPO)
        self.assertIn(rc, (OK, REFUSES, INDETERMINATE), out)

    def test_it_never_imports_live_trader(self):
        """Importing would pull dotenv/ib_insync and side-effect the armed module.
        A safety check that touches what it inspects is a hazard, not a guard."""
        src = TOOL.read_text()
        self.assertNotIn("import live.trader", src)
        self.assertNotIn("from live import trader", src)
        self.assertIn("ast.parse", src)


if __name__ == "__main__":
    unittest.main()

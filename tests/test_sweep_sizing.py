"""
Tests for sweep position-sizing resolution (src/optimization/sweep_sizing.py) — C1.

The default must be the live trader's fixed 10% (so sweep numbers are comparable
to live), while --sizing/--adaptive flags must actually override that default.
The prior sweep.py applied the flags and THEN force-set fixed 10%, silently
ignoring them — these pin the corrected precedence and the comparability banner.
"""
import unittest

from src.optimization.sweep_sizing import resolve_sizing, LIVE_FIXED_PCT


class TestResolveSizing(unittest.TestCase):
    def test_default_is_live_fixed_ten_percent(self):
        p = resolve_sizing()
        self.assertEqual(p.mode, "fixed")
        self.assertEqual(p.fixed_pct, LIVE_FIXED_PCT)
        self.assertFalse(p.use_adaptive)
        self.assertTrue(p.is_live_aligned)
        self.assertIn("matches the live trader", p.banner)

    def test_sizing_flag_overrides_default(self):
        # Regression: --sizing kelly used to be clobbered back to fixed 10%.
        p = resolve_sizing(sizing="kelly")
        self.assertEqual(p.mode, "kelly")
        self.assertFalse(p.is_live_aligned)
        self.assertIn("NOT directly comparable", p.banner)

    def test_kelly_clamped_override(self):
        p = resolve_sizing(sizing="kelly_clamped")
        self.assertEqual(p.mode, "kelly_clamped")
        self.assertFalse(p.is_live_aligned)

    def test_fixed_custom_pct_not_live_aligned(self):
        p = resolve_sizing(sizing="fixed", fixed_pct=0.05)
        self.assertEqual(p.mode, "fixed")
        self.assertEqual(p.fixed_pct, 0.05)
        self.assertFalse(p.is_live_aligned)   # 5% != live 10%

    def test_fixed_ten_percent_explicit_is_live_aligned(self):
        p = resolve_sizing(sizing="fixed", fixed_pct=0.10)
        self.assertTrue(p.is_live_aligned)

    def test_adaptive_on_breaks_alignment(self):
        p = resolve_sizing(adaptive="on")
        self.assertTrue(p.use_adaptive)
        self.assertFalse(p.is_live_aligned)   # live has adaptive off

    def test_adaptive_off_explicit_stays_aligned(self):
        p = resolve_sizing(adaptive="off")
        self.assertFalse(p.use_adaptive)
        self.assertTrue(p.is_live_aligned)

    def test_fixed_pct_ignored_for_non_fixed_modes(self):
        # --fixed-pct only applies to fixed mode; kelly keeps the live default pct.
        p = resolve_sizing(sizing="kelly", fixed_pct=0.25)
        self.assertEqual(p.fixed_pct, LIVE_FIXED_PCT)


if __name__ == "__main__":
    unittest.main()

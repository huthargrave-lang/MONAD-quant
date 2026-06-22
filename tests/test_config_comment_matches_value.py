"""
Content anti-drift for config.py percent params (Context Web v2, Layer 2).

The structure guards (test_context_map.py) verify that files/tests exist and that
manifest invariants match config — but nothing verified the *numbers in prose*.
That is exactly where this repo rots: a param like

    STOP_LOSS_PCT_TQQQ_HOURLY = 0.0050  # 1.50% stop

silently lies (the value is 0.50%, the comment says 1.50%). This guard parses the
target/stop/PCT family and fails when a comment's leading percent disagrees with
value×100, so an agent reading config.py comments can trust them.

config.py is on the edit deny-fence (armed-trader path) — fixing a comment needs
sign-off + the trader stopped. Until then, the two KNOWN live mismatches are
baselined below: this suite fails on any *new* drift, and self-cleans (the
baseline assertion fails) the moment a known one is corrected.
"""
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
import ctx  # noqa: E402  (reuse the canonical drift detector)

# Known, deny-fenced drift: key -> (value, stated_comment_pct). Fixing these needs
# sign-off (config.py is the armed-trader path). Remove an entry once its comment
# in config.py is corrected — test_known_drift_still_present will flag the change.
KNOWN_COMMENT_DRIFT = {}


class TestConfigCommentMatchesValue(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.drift = ctx.config_comment_drift()
        cls.by_key = {d["key"]: d for d in cls.drift}

    def test_no_unbaselined_comment_drift(self):
        """Every percent-comment mismatch must be a known, baselined one. A NEW
        one (a fresh `# 2.80%` on a 1.00% value) fails CI here."""
        new = [d for d in self.drift if d["key"] not in KNOWN_COMMENT_DRIFT]
        self.assertEqual(
            new, [],
            "new config.py comment-vs-value drift (comment % ≠ value×100): "
            + "; ".join(f"{d['key']} @ L{d['line']} value={d['value_pct']:.2f}% "
                        f"comment={d['comment_pct']:.2f}%" for d in new)
            + " — fix the comment (needs sign-off; config.py is deny-fenced) or, if "
              "intentional, add it to KNOWN_COMMENT_DRIFT with a reason.",
        )

    def test_known_drift_still_present(self):
        """Self-cleaning baseline: if a known mismatch is no longer detected, the
        comment was (good!) fixed — remove it from KNOWN_COMMENT_DRIFT."""
        for key, (value, comment_pct) in KNOWN_COMMENT_DRIFT.items():
            with self.subTest(key=key):
                d = self.by_key.get(key)
                self.assertIsNotNone(
                    d, f"{key} no longer drifts — its config.py comment was fixed; "
                       f"remove it from KNOWN_COMMENT_DRIFT")
                self.assertAlmostEqual(d["value"], value, places=6,
                                       msg=f"{key} value changed from baseline {value}")
                self.assertAlmostEqual(d["comment_pct"], comment_pct, places=4,
                                       msg=f"{key} comment % changed from baseline {comment_pct}")

    def test_clean_params_not_flagged(self):
        """Sanity: params whose comment matches the value are NOT flagged (guards
        against the detector becoming a false-positive machine — e.g. GDXU's
        0.0280 # 2.80% must pass)."""
        for ok in ("TARGET_GAIN_PCT_GDXU_HOURLY", "STOP_LOSS_PCT_GDXU_HOURLY",
                   "TARGET_GAIN_PCT_QQQ_HOURLY", "STOP_LOSS_PCT_QQQ_HOURLY",
                   "TARGET_GAIN_PCT", "STOP_LOSS_PCT", "MAX_POSITION_PCT_STRONG_BULL"):
            with self.subTest(key=ok):
                self.assertNotIn(ok, self.by_key, f"{ok} false-flagged as drifted")

    def test_config_modules_are_scanned(self):
        """Finding #1: the default scan must follow the config split and include
        config_modules/*.py (where MAX_POSITION_PCT / MIN_POSITION_PCT live), not
        just config.py — else those risk-param comments are silently unguarded."""
        scanned = [os.path.relpath(p, REPO) for p in ctx._config_files()]
        self.assertIn("config.py", scanned)
        self.assertIn(os.path.join("config_modules", "base.py"), scanned)

    def test_detector_flags_synthetic_drift_in_any_file(self):
        """The engine works on an arbitrary file (the multi-file generalization):
        a crafted drifted line is flagged, a matching one is not."""
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tf:
            tf.write("STOP_LOSS_PCT_FAKE = 0.0050  # 1.50% stop\n"
                     "TARGET_GAIN_PCT_FAKE = 0.0090  # 0.90% target\n")
            name = tf.name
        try:
            d = ctx.config_comment_drift(paths=[name])
            keys = {x["key"] for x in d}
            self.assertIn("STOP_LOSS_PCT_FAKE", keys)        # 0.50% value vs 1.50% comment
            self.assertNotIn("TARGET_GAIN_PCT_FAKE", keys)   # 0.90% == 0.90% — clean
        finally:
            os.unlink(name)


if __name__ == "__main__":
    unittest.main()

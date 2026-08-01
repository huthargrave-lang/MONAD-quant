"""The live-safety audits must be able to notice their own fix (RESEARCH_WEB.md F155).

The audits in `tools/overnight_gap_risk_study.py` conclude that various live-safety
controls are ABSENT, and they guard those conclusions with substring tokens citing
the *buggy* code. That makes the tripwires one-directional: they fire when the
evidence is deleted, and stay silent when the bug is REPAIRED. Measured previously:
implementing three remediations the audits' own `falsification_gate` fields demand
changed 18 of 4,470 output leaves — 15 of them an echoed sha256 — and flipped none
of the 313 `False` absence claims.

So the property under test is not "the flag is False today". It is **"the flag would
become True if someone implemented the control"** — a negative control, without which
a derived check is indistinguishable from the hard-coded literal it replaced.

Each test therefore does the same thing: run the helper against the real
`live/state.py` (expecting absent, which is the true state today), then against a
copy with the control implemented, and require the answer to change.
"""
import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "live" / "state.py"

_SPEC = importlib.util.spec_from_file_location(
    "overnight_gap_risk_study", ROOT / "tools" / "overnight_gap_risk_study.py")
GAP = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = GAP
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))
_SPEC.loader.exec_module(GAP)


CONTROLS = {
    "position_uniqueness": (
        ("CREATE UNIQUE INDEX", "UNIQUE (", "UNIQUE("),
        "CREATE UNIQUE INDEX idx_position_one ON position(id);",
    ),
    "begin_immediate": (
        ("BEGIN IMMEDIATE", "begin immediate", "isolation_level='IMMEDIATE'"),
        'conn.execute("BEGIN IMMEDIATE")',
    ),
    "generation_conditional_delete": (
        ("DELETE FROM position WHERE generation", "WHERE generation = ?",
         "AND generation = ?"),
        'cur.execute("DELETE FROM position WHERE generation = ?", (gen,))',
    ),
    "delete_rowcount_checked": (
        (".rowcount", "rowcount ==", "rowcount !="),
        "if cur.rowcount != 1: raise RuntimeError('stale generation')",
    ),
}


class DerivedControlTests(unittest.TestCase):
    def setUp(self):
        self.source = STATE.read_text(encoding="utf-8")

    def test_all_four_controls_read_ABSENT_from_the_real_source(self):
        """Today's true state. If one of these flips, the control was implemented —
        good news, but the corresponding web node must then be superseded."""
        for name, (tokens, _fix) in CONTROLS.items():
            result = GAP._derived_control(self.source, tokens)
            self.assertFalse(
                result["present"],
                "{} now reads PRESENT in live/state.py (matched {}). If the control "
                "was genuinely implemented, supersede the F86-F104 node that claims "
                "it is absent.".format(name, result["matched_tokens"]),
            )

    def test_each_control_FLIPS_when_implemented(self):
        """The negative control, and the whole point of the change.

        Without this, a derived check is indistinguishable from the hard-coded
        `False` it replaced — which is precisely how the original literals passed
        unnoticed."""
        for name, (tokens, fix) in CONTROLS.items():
            patched = self.source + "\n" + fix + "\n"
            result = GAP._derived_control(patched, tokens)
            self.assertTrue(
                result["present"],
                "{}: implementing the control did NOT flip the flag — the tripwire "
                "is still one-directional and F155 is unfixed for this "
                "control.".format(name),
            )
            self.assertTrue(result["matched_tokens"], "must report what it matched")

    def test_the_helper_reports_WHICH_token_matched(self):
        """A bare boolean cannot be audited; the matched token is the evidence."""
        result = GAP._derived_control("xx BEGIN IMMEDIATE yy", ("BEGIN IMMEDIATE",))
        self.assertEqual(result["matched_tokens"], ["BEGIN IMMEDIATE"])

    def test_no_tokens_means_absent_not_present(self):
        """Direction check: an empty match must not read as 'present'."""
        self.assertFalse(GAP._derived_control("nothing here", ("zzz",))["present"])

    def test_the_helper_documents_its_error_direction(self):
        """Whole-file matching over-approximates presence. That must be stated, and
        it must err toward invalidating the absence finding — a false 'present'
        prompts review, a false 'absent' perpetuates a stale claim."""
        doc = GAP._derived_control.__doc__ or ""
        self.assertIn("over-approximation", doc)
        self.assertIn("F155", doc)


class NoLiteralAbsenceFlagsLeftBehindTests(unittest.TestCase):
    """Bidirectional: re-introducing a hard-coded absence flag should be noticed."""

    CONVERTED = (
        "position_uniqueness_constraint",
        "begin_immediate_present",
        "close_delete_is_generation_conditional",
        "close_checks_delete_rowcount",
    )

    def test_the_converted_flags_are_no_longer_hard_coded_False(self):
        source = (ROOT / "tools" / "overnight_gap_risk_study.py").read_text(
            encoding="utf-8")
        for flag in self.CONVERTED:
            self.assertNotIn(
                "{}=False".format(flag), source,
                "{} was reverted to a hard-coded False — it can no longer notice "
                "the control being implemented (F155).".format(flag),
            )
            self.assertIn(
                "{}=_derived_control(".format(flag), source,
                "{} is no longer derived from source".format(flag),
            )


if __name__ == "__main__":
    unittest.main()

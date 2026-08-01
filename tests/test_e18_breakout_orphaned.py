"""E18's `BULL_BREAKOUT_ENABLED` gates a computation, not a feature.

Study: `docs/research/E18_breakout_signal_is_orphaned.md`.

E18 records the Phase-B result — breakout entries dropped win rate 49.4% → 39.6% — and
ends `BULL_BREAKOUT_ENABLED=False`. CLAUDE.md §3 lists the signal as "BUILT BUT DISABLED".
Both read as: switched off, and flipping the switch brings it back.

It does not. The flag decides only whether a **column is computed**. The two references to
`bull_breakout_signal` in the whole codebase are both writes, inside `build_features`;
`generate_trades` votes on `momentum_signal + volume_signal` and nothing else.

Measured on four seeded daily panels: `entry_signal` is byte-identical with the flag off
and on. Non-vacuously — on a panel where the breakout condition **fires 40 times** while
the strategy takes **30 entries**, the entry hash does not move.

The consequence is a trap for whoever re-tests E18: flip the flag, see nothing change,
conclude the finding was overstated. They would be measuring an orphaned column. The
node's real status is "built, disabled, and disconnected"; reviving it is a routing change
in `generate_trades`, not a config flip.

E18's own figures are NOT recoverable here — they need multi-year BTC daily history, the
providers 403 at this environment's proxy, and the run wrote no artifact. That is stated
in the study rather than papered over; this file guards what is decidable.

Third member of the family: F145 (`adx_kelly_mult`, `regime_kelly_mult` computed, never
read), F26 (slope gate stripped from the entry path), and now a signal whose flag governs
only its own computation.
"""
import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import config  # noqa: E402
import entry_gate_probe as probe  # noqa: E402
from src.strategy.engine import build_features, generate_trades  # noqa: E402

ENGINE = (ROOT / "src" / "strategy" / "engine.py").read_text(encoding="utf-8")
COMMON = dict(require_signals=1, target_gain_pct=0.01, stop_loss_pct=0.006)
# Chosen so the breakout condition fires often AND the strategy takes entries; a panel
# with zero of either would make the equality below true for a trivial reason.
LOUD = dict(seed=26, drift=0.0005, bars=900, sigma=0.014)


def features(flag, **panel):
    df = probe.synth_panel(panel["seed"], panel["drift"], panel["bars"], "1D",
                           panel["sigma"])
    prior = getattr(config, "BULL_BREAKOUT_ENABLED", False)
    try:
        config.BULL_BREAKOUT_ENABLED = flag
        return build_features(df, timeframe="daily")
    finally:
        config.BULL_BREAKOUT_ENABLED = prior


class TheColumnHasNoReaderTests(unittest.TestCase):
    def test_every_reference_in_the_engine_is_a_write(self):
        """A read is a subscript that is not inside an assignment TARGET.

        Counting every subscript mentioning the name reported 2 reads — they were the
        two writes, `df["bull_breakout_signal"] = 0` and the `df.loc[mask, "..."] = 1`,
        whose targets are themselves subscripts. Third time this session that matching
        on text instead of on the target has turned a write into a read.
        """
        tree = ast.parse(ENGINE)
        in_target = set()
        writes = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if "bull_breakout_signal" in ast.unparse(target):
                        writes += 1
                    for sub in ast.walk(target):
                        in_target.add(id(sub))
        reads = sum(1 for node in ast.walk(tree)
                    if isinstance(node, ast.Subscript)
                    and id(node) not in in_target
                    and "bull_breakout_signal" in ast.unparse(node))
        self.assertGreaterEqual(writes, 1, "the signal is no longer written at all")
        self.assertEqual(
            reads, 0,
            "bull_breakout_signal is READ somewhere in engine.py now — the signal may "
            "have been wired into entries; re-measure and supersede E18's status")

    def test_no_other_module_mentions_it(self):
        hits = []
        for area in ("src", "tools", "live"):
            for path in (ROOT / area).rglob("*.py"):
                if path.name == "engine.py":
                    continue
                if "bull_breakout_signal" in path.read_text(encoding="utf-8"):
                    hits.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(
            hits, [],
            "bull_breakout_signal is referenced outside engine.py ({}) — it may have a "
            "consumer now".format(hits))

    def test_the_vote_is_built_from_two_signals_only(self):
        self.assertIn(
            'df["signal_vote"] = (\n        df["momentum_signal"] +\n'
            '        df["volume_signal"]\n    )', ENGINE,
            "the signal_vote composition changed — check whether the breakout signal "
            "joined it")


class FlippingTheFlagChangesNothingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.off = features(False, **LOUD)
        cls.on = features(True, **LOUD)

    def test_the_flag_is_currently_off(self):
        self.assertFalse(
            getattr(config, "BULL_BREAKOUT_ENABLED", False),
            "BULL_BREAKOUT_ENABLED is True now — if the signal was also wired in, "
            "supersede E18; if not, entries still will not change")

    def test_the_flag_controls_only_whether_the_column_exists(self):
        self.assertNotIn("bull_breakout_signal", self.off.columns)
        self.assertIn("bull_breakout_signal", self.on.columns)

    def test_the_breakout_condition_actually_fires_on_this_panel(self):
        """Non-vacuity, half one: a signal that never fires proves nothing."""
        fires = int(self.on["bull_breakout_signal"].sum())
        self.assertGreater(
            fires, 20,
            "the breakout condition fires only {} times on the tuned panel — pick a "
            "louder one before trusting the equality below".format(fires))

    def test_the_strategy_takes_entries_on_this_panel(self):
        """Non-vacuity, half two: identical empty vectors are identical for free."""
        entries = int((generate_trades(self.off, **COMMON)["entry_signal"] != 0).sum())
        self.assertGreater(entries, 20,
                           "only {} entries on this panel".format(entries))

    def test_the_entry_vector_is_identical_with_the_flag_on(self):
        off = generate_trades(self.off, **COMMON)
        on = generate_trades(self.on, **COMMON)
        self.assertEqual(
            probe.entry_hash(off), probe.entry_hash(on),
            "flipping BULL_BREAKOUT_ENABLED now changes entries — the signal was "
            "wired in. Re-measure E18's 49.4%/39.6% comparison and supersede the node.")

    def test_it_holds_across_the_standard_panels(self):
        for name, seed, drift in probe.PANELS:
            off = generate_trades(features(False, seed=seed, drift=drift, bars=600,
                                           sigma=0.006), **COMMON)
            on = generate_trades(features(True, seed=seed, drift=drift, bars=600,
                                          sigma=0.006), **COMMON)
            self.assertEqual(probe.entry_hash(off), probe.entry_hash(on),
                             "panel {} now differs with the flag on".format(name))


class TheDocumentedStatusUnderstatesItTests(unittest.TestCase):
    def test_claude_md_still_calls_it_built_but_disabled(self):
        text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertIn(
            "BUILT BUT DISABLED", text,
            "CLAUDE.md's description of the breakout signal changed — if it now says "
            "'unwired', drop this assertion and the corresponding line in the study")
        self.assertIn("BULL_BREAKOUT_ENABLED = False", text)

    def test_the_node_records_the_flag_as_the_off_switch(self):
        web = (ROOT / "RESEARCH_WEB.md").read_text(encoding="utf-8")
        start = web.index("### E18 ")
        body = web[start:web.index("\n### ", start + 5)]
        self.assertIn("BULL_BREAKOUT_ENABLED=False", body)

    def test_the_study_states_the_figures_are_unrecoverable(self):
        doc = (ROOT / "docs/research/E18_breakout_signal_is_orphaned.md").read_text(
            encoding="utf-8")
        for figure in ("49.4", "39.6", "83", "141"):
            self.assertIn(figure, doc)
        self.assertIn("unverifiable", doc.lower())


if __name__ == "__main__":
    unittest.main()

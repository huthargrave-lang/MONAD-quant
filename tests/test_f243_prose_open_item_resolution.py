"""A prose open item had no way to ever be closed — F243.

`_nodes_resolved_since` (F200) drops a handoff open item once every research node it
NAMES has been closed by a `resolves` edge. F200 also, correctly, kept every item that
names no node: most open items are prose tasks, and dropping those by default would
silently empty the queue's highest-leverage source.

That left F200's own item pinned to the top forever. Item 7 of
`docs/research/HANDOFF_2026-07-25.md` reads:

    **`config.py:120` cites `EXIT_ON_OPPOSING_SIGNAL`**, an identifier existing nowhere
    else. `config.py` is fenced.

It names no node, so no `resolves` edge can reach it — even though F200 corrected that
comment in the same cycle that recorded the item. The backlog surfaced it as the top-ranked
task again, which is the exact failure F200's title claims to have fixed, arriving through
the door F200 knowingly left open.

**Why a grep is the wrong predicate.** The obvious check — "is `EXIT_ON_OPPOSING_SIGNAL`
still in `config.py`?" — returns the opposite of the truth. F200 fixed the comment by
*quoting the dead identifier inside a disclaimer*:

    # (An earlier comment here pointed at `EXIT_ON_OPPOSING_SIGNAL` in live/trader.py;
    #  no such flag or behaviour exists.)

So the symbol is still there, in the very sentence that resolves the concern. Existence is
not the question; whether the citation *asserts* or *disclaims* is. `PROSE_RESOLVED` pairs
each prose item with a predicate over the repository, evaluated on every run, so the item
must keep re-earning its closure — reverting the comment, or adding the flag to `live/`,
brings it straight back. Same design as `BLOCKED_ON_DATA`'s live `--recheck`.

Guards are bidirectional: they fail if the item stops being resolved, if the predicate
becomes a constant (a resolution that cannot be revoked is not a predicate), if untracked
prose items start being dropped (F200's invariant), and if the registry stops matching any
real handoff item — a fingerprint that matches nothing is a dead lever, the F145 family.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import research_backlog as rb  # noqa: E402


def _write_repo(tmp, disclaimed=True, live_has_flag=False):
    """A synthetic repo root exercising the real predicate."""
    tmp = Path(tmp)
    comment = ("# (An earlier comment pointed at `EXIT_ON_OPPOSING_SIGNAL`; "
               "no such flag or behaviour exists.)\n" if disclaimed
               else "# Live equivalent lives in live/trader.py behind "
                    "EXIT_ON_OPPOSING_SIGNAL.\n")
    (tmp / "config.py").write_text(comment, encoding="utf-8")
    live = tmp / "live"
    live.mkdir(exist_ok=True)
    (live / "trader.py").write_text(
        "EXIT_ON_OPPOSING_SIGNAL = True\n" if live_has_flag else "pass\n",
        encoding="utf-8")
    return tmp


class ThePredicateIsRealTests(unittest.TestCase):
    """It must be able to say no, or it is a resolved-flag wearing a function's clothes."""

    def _with_repo(self, **kw):
        import tempfile
        original = rb.REPO
        tmpdir = tempfile.mkdtemp()
        try:
            rb.REPO = _write_repo(tmpdir, **kw)
            return rb._config_opposing_citation_is_disclaimed()
        finally:
            rb.REPO = original

    def test_a_disclaimed_citation_resolves_the_item(self):
        self.assertTrue(self._with_repo(disclaimed=True, live_has_flag=False))

    def test_an_asserting_citation_does_not(self):
        """Non-vacuity. Revert F200's comment and the item must come back."""
        self.assertFalse(
            self._with_repo(disclaimed=False, live_has_flag=False),
            "the predicate accepts a comment that asserts a live flag again — the "
            "resolution can no longer be revoked, so it is not a predicate")

    def test_a_live_flag_reopens_it_even_when_disclaimed(self):
        """The other half: the disclaimer says 'no such flag exists'. If one appears,
        the disclaimer is false and the item is live again."""
        self.assertFalse(
            self._with_repo(disclaimed=True, live_has_flag=True),
            "live/ gained EXIT_ON_OPPOSING_SIGNAL and the item still counts as "
            "resolved — the disclaimer it rests on is now untrue")


class TheNaiveCheckWouldBeWrongTests(unittest.TestCase):
    """The reason this needed a predicate at all. If this ever flips, the simpler
    check becomes correct and PROSE_RESOLVED's entry can be simplified."""

    def test_the_dead_identifier_is_still_present_in_config(self):
        src = (ROOT / "config.py").read_text(encoding="utf-8")
        self.assertIn(
            "EXIT_ON_OPPOSING_SIGNAL", src,
            "config.py no longer mentions the identifier at all, so a plain "
            "absence check would now answer correctly — simplify the predicate")
        self.assertIn(
            "no such flag or behaviour exists", src,
            "the disclaimer that resolves the item is gone from config.py")

    def test_and_it_is_absent_from_live(self):
        hits = [p for p in (ROOT / "live").rglob("*.py")
                if "EXIT_ON_OPPOSING_SIGNAL" in p.read_text(encoding="utf-8",
                                                            errors="ignore")]
        self.assertEqual(hits, [], "live/ now defines the flag the disclaimer denies")


class TheRegistryIsWiredToRealItemsTests(unittest.TestCase):
    """A fingerprint matching nothing is a dead lever (F145 family)."""

    @classmethod
    def setUpClass(cls):
        cls.heads = cls._open_heads()

    @staticmethod
    def _open_heads():
        import re
        handoffs = sorted((ROOT / "docs" / "research").glob("HANDOFF_*.md"))
        text = handoffs[-1].read_text(encoding="utf-8")
        section = re.search(r"\n##+\s*\d*\.?\s*Open[^\n]*\n(.*?)(?=\n##\s|\Z)", text, re.S)
        return [m.group(1).strip() for m in
                re.finditer(r"^\s*\d+\.\s+\*\*(.+?)\*\*", section.group(1), re.M)]

    def test_every_fingerprint_matches_a_real_open_item(self):
        for fingerprint in rb.PROSE_RESOLVED:
            with self.subTest(fingerprint=fingerprint):
                self.assertTrue(
                    any(fingerprint in h for h in self.heads),
                    "PROSE_RESOLVED carries '{}' which matches no item in the newest "
                    "handoff — it governs nothing".format(fingerprint))

    def test_the_opposing_signal_item_is_reported_resolved(self):
        head = next(h for h in self.heads if "EXIT_ON_OPPOSING_SIGNAL" in h)
        resolved, why = rb.prose_resolution(head)
        self.assertTrue(resolved, "the handoff item is open again")
        self.assertTrue(why, "a resolution with no stated reason is not auditable")

    def test_untracked_prose_items_are_left_alone(self):
        """F200's invariant: prose items are the queue's richest source and must not
        be dropped by default."""
        untracked = [h for h in self.heads if rb.prose_resolution(h)[1] is None]
        self.assertTrue(untracked, "every open item is now registry-tracked, which is "
                                   "suspicious — the source can silently empty")
        for h in untracked:
            self.assertFalse(rb.prose_resolution(h)[0],
                             "untracked item {!r} reports resolved".format(h[:50]))


class TheQueueNoLongerSurfacesItTests(unittest.TestCase):

    def test_the_resolved_item_is_absent_from_the_open_list(self):
        titles = [t["title"] for t in rb.source_open_items(limit=20)]
        self.assertFalse(
            any("EXIT_ON_OPPOSING_SIGNAL" in t for t in titles),
            "the resolved item is ranking again")

    def test_but_the_open_list_is_not_empty(self):
        """Non-vacuity: 'absent' must not be because everything was dropped."""
        self.assertGreaterEqual(
            len(rb.source_open_items(limit=20)), 3,
            "the open list collapsed — the prose-resolution path is over-matching")


if __name__ == "__main__":
    unittest.main()

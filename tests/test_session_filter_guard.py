"""
The regular session is applied in ONE place: src/data/fetcher.py (decision-debate Q1).

Morning-only data was manufactured twice by session filters written at call sites: a UTC
``between_time`` in sweep.py and equity_curve.py (F404700), and a UTC (9, 16) hour gate in
main.py (F148). Both compared New York session times with a naive-UTC index. This guard
fails CI on any new call-site session filter in research/backtest code: a
``between_time`` call, or a comparison against an index's ``.hour``, outside the fetcher.
Files that filter hours for a stated, correct reason are listed with it.
"""
import ast
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import ctx  # noqa: E402

CANONICAL = "src/data/fetcher.py"

#: Hour filtering that is correct where it is, and why.
ALLOWED = {
    "src/strategy/engine.py":
        "the engine's trade_hours gate; the loader has already applied the session, and "
        "run_backtest's default gate passes every session bar (census: acted-on bars agree)",
    "tools/overnight_gap_risk_study.py":
        "converts to US/Eastern before filtering, on 5-minute data the hourly loader does not serve",
    "tools/live_backtest_reconciliation_study.py":
        "samples morning bars ON PURPOSE to measure the bar-frequency effect (F14)",
}

#: live/ is fenced and is the loader's twin (live/signals.py); not research code.
SCOPE_EXCLUDE = ("live/", "tests/")


def _reads_index_hour(expr):
    return any(isinstance(sub, ast.Attribute) and sub.attr == "hour"
               and isinstance(sub.value, ast.Attribute) and sub.value.attr == "index"
               for sub in ast.walk(expr))


def _hour_names(tree):
    """Names assigned from an index's .hour (``hour = df.index.hour``), so the two-step
    form is caught as well as the direct comparison."""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and _reads_index_hour(node.value):
            names |= {t.id for t in node.targets if isinstance(t, ast.Name)}
    return names


def _index_hour_compare(node, names=frozenset()):
    """A Compare that reads ``<x>.index.hour``, directly or through a name bound to it."""
    if not isinstance(node, ast.Compare):
        return False
    for side in [node.left, *node.comparators]:
        if _reads_index_hour(side):
            return True
        if any(isinstance(sub, ast.Name) and sub.id in names for sub in ast.walk(side)):
            return True
    return False


def offenders():
    out = []
    for rel in ctx._first_party_modules():
        if rel == CANONICAL or rel in ALLOWED or rel.startswith(SCOPE_EXCLUDE):
            continue
        with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        names = _hour_names(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "between_time":
                out.append(f"{rel}:{node.lineno} between_time")
            elif _index_hour_compare(node, names):
                out.append(f"{rel}:{node.lineno} compares an index's .hour")
    return out


class TheSessionIsFilteredInOnePlace(unittest.TestCase):
    def test_no_call_site_session_filters(self):
        found = offenders()
        self.assertEqual(found, [], "\n".join(
            ["session/hour filtering outside src/data/fetcher.py; use "
             "fetcher.load_session_bars / regular_session, or list the file in ALLOWED "
             "with the reason it is correct:"] + found))

    def test_the_allowed_files_still_filter_hours(self):
        """An allowance that no longer covers anything is stale: remove it."""
        for rel in ALLOWED:
            with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
                tree = ast.parse(fh.read())
            names = _hour_names(tree)
            hit = any(_index_hour_compare(n, names) or (isinstance(n, ast.Call) and
                      getattr(n.func, "attr", None) == "between_time") for n in ast.walk(tree))
            self.assertTrue(hit, f"{rel} no longer filters hours; drop its allowance")

    def test_the_detector_catches_the_two_original_bugs(self):
        for src in ('df = df.between_time("09:30", "16:00")\n',
                    'x = df[(df.index.hour >= 9) & (df.index.hour < 16)]\n',
                    'hour = df.index.hour\nok = (hour >= 9) & (hour < 16)\n'):
            tree = ast.parse(src)
            names = _hour_names(tree)
            self.assertTrue(any(
                (isinstance(n, ast.Call) and getattr(n.func, "attr", None) == "between_time")
                or _index_hour_compare(n, names) for n in ast.walk(tree)), src)


if __name__ == "__main__":
    unittest.main()

"""D2's code bridge: is rolling-origin OOS the sweep's primary selector yet?

D2 is an OPEN decision, not an implemented claim: *"Make the sweep select on
rolling-origin OOS, not single-split holdout. Needs a design pass."* Its bridge to
`src/optimization/walk_forward.py::walk_forward_optimize` carried no `guarded_by`
test.

That makes it a different guarding problem from a finding. There is no result to
protect — the useful thing is to make the decision **announce its own completion**.
So this file pins the current state D2 describes as needing change, and fails when
that state changes:

* `walk_forward_optimize` really is **rolling-origin** — repeated train→test windows,
  not one split. This is D2's premise; if it stopped being true, D2 would be proposing
  something the code cannot do.
* `sweep.py` **does not** select on it. The moment someone wires walk-forward into the
  sweep's selection path, the second test fails and says D2 looks DONE — supersede it.

This matters beyond D2. The web carries ~50 hypotheses and decisions that no Finding
ever closed (F151), which biases the project's self-measured error rate toward looking
stable. A decision that fails a test when it is satisfied cannot quietly stay open.
"""
import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

WALKFWD = ROOT / "src" / "optimization" / "walk_forward.py"
SWEEP = ROOT / "sweep.py"
SCORING = ROOT / "src" / "optimization" / "sweep_scoring.py"


class RollingOriginPremiseTests(unittest.TestCase):
    """D2 presumes the walk-forward lens exists and is rolling-origin."""

    def setUp(self):
        self.source = WALKFWD.read_text(encoding="utf-8")
        self.tree = ast.parse(self.source)

    def _fn(self, name):
        for node in ast.walk(self.tree):
            if isinstance(node, ast.FunctionDef) and node.name == name:
                return node
        return None

    def test_the_optimizer_exists(self):
        self.assertIsNotNone(
            self._fn("walk_forward_optimize"),
            "walk_forward_optimize is gone — D2's premise no longer holds, and its "
            "bridge in context_map.json points at nothing. Supersede D2.")

    def test_it_takes_separate_train_and_test_horizons(self):
        """A single-split holdout would not need both."""
        fn = self._fn("walk_forward_optimize")
        args = [a.arg for a in fn.args.args]
        self.assertIn("train_months", args)
        self.assertIn("test_months", args)

    def test_it_iterates_windows_rather_than_splitting_once(self):
        """Rolling origin means a LOOP over windows. One split would not have one."""
        fn = self._fn("walk_forward_optimize")
        loops = [n for n in ast.walk(fn) if isinstance(n, (ast.For, ast.While))]
        self.assertTrue(
            loops,
            "walk_forward_optimize no longer loops — it may have become a single-split "
            "holdout, which is exactly what D2 argues against. Re-verify before citing "
            "D2 or E4.")

    def test_the_docstring_still_describes_train_then_out_of_sample(self):
        doc = (ast.get_docstring(self._fn("walk_forward_optimize")) or "").lower()
        self.assertIn("rolling window", doc)
        self.assertIn("out-of-sample", doc)


class D2IsStillOpenTests(unittest.TestCase):
    """The self-announcing half. These FAIL when D2 gets implemented."""

    def _selects_on_walkforward(self, path):
        if not path.exists():
            return False
        return "walk_forward" in path.read_text(encoding="utf-8")

    def test_the_sweep_does_not_yet_select_on_walk_forward(self):
        self.assertFalse(
            self._selects_on_walkforward(SWEEP),
            "sweep.py now references walk_forward — D2 ('promote walk-forward to the "
            "sweep's primary selector') appears IMPLEMENTED. Supersede D2 with a "
            "Finding recording what was wired and re-baseline every stored sweep "
            "result, which was selected under the old single-split lens. Do not "
            "simply delete this test.")

    def test_the_scoring_path_does_not_either(self):
        self.assertFalse(
            self._selects_on_walkforward(SCORING),
            "sweep_scoring.py now references walk_forward — see the message above; "
            "D2 may be satisfied.")

    def test_walk_forward_is_reachable_on_its_own_entrypoint(self):
        """D2 is 'promote', not 'build' — the lens must already be runnable, or the
        decision is mis-stated."""
        main = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn(
            "walk-forward", main,
            "main.py no longer exposes the walk-forward mode, so the lens D2 wants "
            "promoted is not reachable at all — D2 is mis-stated, not merely open.")


class BridgeRegistrationTests(unittest.TestCase):
    def test_the_bridge_exists_and_names_this_guard(self):
        import json
        bridges = json.loads((ROOT / "context_map.json").read_text(
            encoding="utf-8"))["graph_bridges"]["bridges"]
        d2 = [b for b in bridges if b.get("node") == "D2"]
        self.assertTrue(d2, "the D2 code bridge disappeared from context_map.json")
        self.assertIn("src/optimization/walk_forward.py::walk_forward_optimize",
                      d2[0]["code"])


if __name__ == "__main__":
    unittest.main()

"""
Every strategy evaluation in the repo is counted in the trial ledger, or says why not.

The ledger (src/research/trials.py) makes a trial count honest only if nothing can
evaluate a strategy without writing to it. This guard makes that structural: it
finds every call to the engine's two evaluation entry points (``run_backtest`` and
``compute_trade_returns``) in first-party code and requires each to be

  * **counted** — its enclosing function (or module) calls ``.begin(`` / ``.trial(``
    on a ledger run at an earlier line; or
  * **delegated** — it sits in a helper whose every caller in the file is counted; or
  * **exempt** — its file is listed below with the reason it cannot evidence an edge.

A new tool that backtests without counting fails here, in CI, before it produces a
number anyone can quote. It also checks that no producer diverts its trials to a
private ledger directory, and that the library producers cannot be called uncounted.
"""
import ast
import inspect
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import ctx  # noqa: E402

EVALUATORS = {"run_backtest", "compute_trade_returns"}

#: Where the evaluators are defined (and call each other). Not producers.
DEFINING = {"src/backtest/runner.py", "src/strategy/engine.py"}

#: (file, helper) -> the counted wrapper that is its only permitted caller.
DELEGATED = {
    ("src/optimization/walk_forward.py", "_run_slice"): "_counted_slice",
}

#: Files that call an evaluator without counting, and why that cannot inflate a result.
EXEMPT = {
    "tools/live_backtest_parity.py":
        "time_exit_bind_rate runs the engine on seeded SYNTHETIC panels to state a "
        "mechanism (how often the clock ends a trade); it measures no instrument and "
        "cannot evidence an edge.",
    "tools/overnight_gap_risk_study.py":
        "engine_crosscheck proves the study's own replay equals the engine byte-for-byte; "
        "the study's measurements come from its replay, not from this call. (Labs that "
        "measure with their own replay code are outside this guard; see the ledger README.)",
}

COUNTING_METHODS = {"begin", "trial"}


def _name(call):
    f = call.func
    return getattr(f, "attr", None) or getattr(f, "id", None)


def _scopes(tree):
    """Yield (scope_name, scope_node) for the module and every function in it."""
    yield "<module>", tree
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node.name, node


def _own_calls(scope):
    """Calls lexically in ``scope`` but not inside a nested function."""
    out, stack = [], list(ast.iter_child_nodes(scope))
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        if isinstance(node, ast.Call):
            out.append(node)
        stack.extend(ast.iter_child_nodes(node))
    return out


def _is_counted(calls, before_line):
    return any(_name(c) in COUNTING_METHODS and isinstance(c.func, ast.Attribute)
               and c.lineno < before_line for c in calls)


def _audit(rel):
    """Offender strings for one file."""
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    scopes = dict()
    for name, node in _scopes(tree):
        scopes.setdefault(name, node)
    offenders = []
    for name, node in _scopes(tree):
        calls = _own_calls(node)
        for call in calls:
            if _name(call) not in EVALUATORS:
                continue
            if _is_counted(calls, call.lineno):
                continue
            wrapper = DELEGATED.get((rel, name))
            if wrapper is not None:
                offenders.extend(_audit_delegation(rel, tree, name, wrapper, scopes))
                continue
            offenders.append(f"{rel}:{call.lineno} {name}() calls {_name(call)} uncounted")
    return offenders


def _audit_delegation(rel, tree, helper, wrapper, scopes):
    problems = []
    if wrapper not in scopes:
        return [f"{rel}: delegated wrapper {wrapper}() for {helper}() no longer exists"]
    for name, node in _scopes(tree):
        calls = _own_calls(node)
        for call in calls:
            if _name(call) != helper:
                continue
            if name != wrapper:
                problems.append(f"{rel}:{call.lineno} {name}() calls {helper}() directly; "
                                f"only {wrapper}() may")
            elif not _is_counted(calls, call.lineno):
                problems.append(f"{rel}:{call.lineno} {wrapper}() calls {helper}() before counting")
    return problems


def _first_party():
    return [m for m in ctx._first_party_modules() if not m.startswith("tests/")]


class EveryEvaluationIsCounted(unittest.TestCase):
    def test_no_uncounted_evaluation_outside_the_exemptions(self):
        offenders = []
        for rel in _first_party():
            if rel in DEFINING or rel in EXEMPT:
                continue
            offenders.extend(_audit(rel))
        self.assertEqual(offenders, [], "\n".join(
            ["strategy evaluations that the trial ledger never sees — count them with "
             "src/research/trials.open_run + Run.begin/trial (see backtest_trials.record_backtest), "
             "or add the file to EXEMPT with the reason it cannot evidence an edge:"] + offenders))

    def test_exemptions_are_still_needed(self):
        """An exemption that no longer covers an uncounted call is stale: remove it,
        or it quietly licenses the next uncounted call added to that file."""
        stale = [rel for rel in EXEMPT if not _audit(rel)]
        self.assertEqual(stale, [], f"stale exemptions: {stale}")

    def test_the_guard_sees_the_producers_it_was_written_for(self):
        """If the AST walk stopped finding evaluator calls, every check above would pass
        vacuously. These files are known to evaluate strategies."""
        for rel in ("sweep.py", "main.py", "tools/walkforward_eval.py",
                    "tools/strategy_funnel.py", "tools/equity_curve.py", "fee_analysis.py",
                    "src/optimization/walk_forward.py"):
            with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
                tree = ast.parse(fh.read())
            found = [c for c in ast.walk(tree) if isinstance(c, ast.Call) and _name(c) in EVALUATORS]
            self.assertTrue(found, f"{rel} no longer calls an evaluator; update this guard")

    def test_an_uncounted_call_is_caught(self):
        """The detector itself, on a planted offender."""
        tree = ast.parse("def f(df):\n    return run_backtest(df)\n"
                         "def g(df, run):\n    t = run.begin(params={})\n    return run_backtest(df)\n")
        results = {}
        for name, node in _scopes(tree):
            calls = _own_calls(node)
            for c in calls:
                if _name(c) in EVALUATORS:
                    results[name] = _is_counted(calls, c.lineno)
        self.assertEqual(results, {"f": False, "g": True})


class ProducersWriteTheCanonicalLedger(unittest.TestCase):
    def test_no_producer_diverts_its_trials(self):
        """``ledger_dir=`` exists for tests. A producer passing it would count its trials
        somewhere CI never verifies, which is an undercount with extra steps."""
        offenders = []
        for rel in _first_party():
            if rel.startswith("src/research/"):
                continue
            with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
                tree = ast.parse(fh.read())
            for c in ast.walk(tree):
                if isinstance(c, ast.Call) and _name(c) in {"open_run", "open_process_run"}:
                    if any(kw.arg == "ledger_dir" for kw in c.keywords):
                        offenders.append(f"{rel}:{c.lineno}")
        self.assertEqual(offenders, [])

    def test_library_producers_cannot_be_called_uncounted(self):
        import walkforward_eval
        from src.optimization import walk_forward
        for fn in (walkforward_eval.walkforward, walk_forward.walk_forward_optimize):
            param = inspect.signature(fn).parameters["run"]
            self.assertEqual(param.kind, inspect.Parameter.KEYWORD_ONLY, fn.__name__)
            self.assertIs(param.default, inspect.Parameter.empty,
                          f"{fn.__name__}(run=...) must be required, not defaulted")


if __name__ == "__main__":
    unittest.main()

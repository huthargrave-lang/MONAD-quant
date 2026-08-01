#!/usr/bin/env python3
"""arm_check.py — "Would THIS tree arm?", answered against an arbitrary checkout.

WHY THIS EXISTS
    Origin's live/trader.py gained `_assert_mode_symbol_coherent()`, which raises
    SystemExit in main() when config.ACTIVE_MODE != f"{LIVE_SYMBOL}_HOURLY". A tree
    carrying a mismatch imports fine, passes the unit tests, and passes
    deploy/smoke-test.sh — and then refuses to start. Nothing in this repo answers
    "would the bot actually arm from this tree?":

      * smoke-test step 5 compares f"{LIVE_SYMBOL}_HOURLY" to config.ASSETS and
        never to ACTIVE_MODE — one identifier away from the real predicate
      * step 2 never imports live.trader at all
      * CI tests the branch, not the tree that is about to become the live tree

    The question is only answerable ABOUT A SPECIFIC TREE, which is why this takes
    --tree and can be pointed at a candidate merge result before it is landed.

WHY IT READS RATHER THAN IMPORTS
    It parses live/trader.py with `ast` and never imports it. Importing pulls
    dotenv, ib_insync and the broker module; a safety check that side-effects the
    armed module is a new hazard, not a guard. Guard functions are extracted and
    executed in an isolated namespace with the real `config` bound.

THE FALSE ALL-CLEAR IS THE WORST FAILURE SHAPE
    A checker that exits 0 on a tree that refuses to arm is worse than no checker,
    because it converts an unknown into a confident wrong answer. So this reports
    INDETERMINATE — never OK — whenever it finds anything in the pre-broker slice
    it cannot evaluate: an unrecognised refusal path (`raise SystemExit`,
    `sys.exit`, `os._exit`), a call to a module-level function it does not
    recognise as a guard, a guard whose execution raises anything other than
    SystemExit, or no guards at all. "I found nothing" is not "there is nothing".

EXIT CODES
    0  WOULD_ARM      guards found, all executed, none refused
    2  REFUSES        a guard raised SystemExit — the tree will not arm
    3  INDETERMINATE  cannot prove either way (see above); treat as "stop and look"
    4  USAGE          bad invocation / unreadable tree

    Never 1: a plain non-zero from an unexpected crash must not be mistaken for a
    definite REFUSES verdict by a caller doing `if rc:`.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

OK, REFUSES, INDETERMINATE, USAGE = 0, 2, 3, 4

# A guard is a module-level predicate called for its side effect of refusing.
# The naming convention is the contract; anything else in the slice is a hazard.
GUARD_NAME = __import__("re").compile(r"^_(assert|require|check)_[a-z_][a-z0-9_]*$")


def _first_broker_index(body: list[ast.stmt]) -> int:
    """Index of the first statement that touches `broker`. Everything before it is
    the pre-broker slice: the window in which a refusal costs nothing external."""
    for i, stmt in enumerate(body):
        for node in ast.walk(stmt):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                if node.value.id == "broker":
                    return i
    return len(body)


def _module_level_functions(tree: ast.Module) -> set[str]:
    return {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def analyse(trader_src: str) -> dict:
    """Static half: find the guards, and find anything that makes the slice unsafe
    to reason about. Pure — no execution here."""
    tree = ast.parse(trader_src)
    fns = _module_level_functions(tree)
    main = next((n for n in tree.body
                 if isinstance(n, ast.FunctionDef) and n.name == "main"), None)
    if main is None:
        return {"guards": [], "hazards": ["live/trader.py defines no main()"]}

    slice_ = main.body[: _first_broker_index(main.body)]
    guards: list[tuple[str, int]] = []
    hazards: list[str] = []

    for stmt in slice_:
        for node in ast.walk(stmt):
            # An unrecognised way to refuse. We cannot evaluate it, so we must not
            # claim the tree arms.
            if isinstance(node, ast.Raise):
                exc = node.exc
                name = getattr(exc, "id", None) or getattr(getattr(exc, "func", None), "id", None)
                if name == "SystemExit":
                    hazards.append(f"bare `raise SystemExit` at line {node.lineno}, outside a named guard")
            if isinstance(node, ast.Call):
                f = node.func
                if isinstance(f, ast.Name):
                    if GUARD_NAME.match(f.id):
                        guards.append((f.id, node.lineno))
                    elif f.id in fns:
                        hazards.append(
                            f"call to module-level `{f.id}()` at line {node.lineno} "
                            f"is not a recognised guard name")
                    elif f.id in ("exit", "quit"):
                        hazards.append(f"`{f.id}()` at line {node.lineno}")
                elif isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
                    if (f.value.id, f.attr) in (("sys", "exit"), ("os", "_exit")):
                        hazards.append(f"`{f.value.id}.{f.attr}()` at line {node.lineno}")

    # de-dup, preserve order
    seen = set()
    guards = [g for g in guards if not (g in seen or seen.add(g))]
    return {"guards": guards, "hazards": hazards}


def run_guards(trader_src: str, guards: list[tuple[str, int]], config_mod) -> dict:
    """Dynamic half: execute each guard against the real config, isolated.

    Only SystemExit is a verdict. Any other exception means the guard could not be
    evaluated here (a module-level dependency we did not bind, say) — which is
    INDETERMINATE, never OK.
    """
    tree = ast.parse(trader_src)
    defs = {n.name: n for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    results = []
    for name, lineno in guards:
        node = defs.get(name)
        if node is None:
            results.append({"guard": name, "line": lineno, "result": "missing_def"})
            continue
        ns: dict = {"config": config_mod, "__name__": "arm_check_sandbox"}
        try:
            exec(compile(ast.Module(body=[node], type_ignores=[]), "<guard>", "exec"), ns)
            ns[name]()
            results.append({"guard": name, "line": lineno, "result": "pass"})
        except SystemExit as exc:
            results.append({"guard": name, "line": lineno, "result": "refuse",
                            "message": str(exc)})
        except BaseException as exc:                      # noqa: BLE001 — deliberate
            results.append({"guard": name, "line": lineno, "result": "unevaluable",
                            "message": f"{type(exc).__name__}: {exc}"})
    return {"results": results}


def verdict(analysis: dict, execution: dict | None) -> tuple[int, str]:
    if analysis["hazards"]:
        return INDETERMINATE, "unevaluable refusal path in the pre-broker slice: " + \
                              "; ".join(analysis["hazards"])
    if not analysis["guards"]:
        # Absence of a detected guard is not proof there is none — it may simply be
        # shaped differently. Refusing to say OK here is the anti-false-all-clear rule.
        return INDETERMINATE, "no arming guard found in main()'s pre-broker slice"
    res = execution["results"] if execution else []
    refused = [r for r in res if r["result"] == "refuse"]
    if refused:
        return REFUSES, refused[0].get("message", "").strip().splitlines()[0] if \
            refused[0].get("message") else f"{refused[0]['guard']} refused"
    bad = [r for r in res if r["result"] != "pass"]
    if bad:
        return INDETERMINATE, f"{bad[0]['guard']}: {bad[0].get('message', bad[0]['result'])}"
    return OK, f"{len(res)} guard(s) passed: " + ", ".join(r["guard"] for r in res)


def load_config(tree_root: Path):
    """Import the CANDIDATE tree's config, not the running process's."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "arm_check_config", tree_root / "config.py")
    if spec is None or spec.loader is None:
        raise ImportError("cannot load config.py")
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(tree_root))
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path.pop(0)
    return mod


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Would this tree arm the live trader?")
    ap.add_argument("--tree", default=".", help="checkout to inspect (default: cwd)")
    ap.add_argument("--json", action="store_true", help="machine-readable report")
    args = ap.parse_args(argv)

    root = Path(args.tree).resolve()
    trader = root / "live" / "trader.py"
    if not trader.is_file() or not (root / "config.py").is_file():
        print(f"arm_check: not a MONAD tree: {root}", file=sys.stderr)
        return USAGE

    try:
        src = trader.read_text()
        analysis = analyse(src)
    except SyntaxError as exc:
        code, why = INDETERMINATE, f"live/trader.py does not parse: {exc}"
        analysis, execution = {"guards": [], "hazards": [why]}, None
    else:
        execution = None
        if analysis["guards"] and not analysis["hazards"]:
            try:
                execution = run_guards(src, analysis["guards"], load_config(root))
            except BaseException as exc:                  # noqa: BLE001
                analysis["hazards"].append(f"config load failed: {type(exc).__name__}: {exc}")
        code, why = verdict(analysis, execution)

    label = {OK: "WOULD_ARM", REFUSES: "REFUSES", INDETERMINATE: "INDETERMINATE"}[code]
    if args.json:
        print(json.dumps({"tree": str(root), "verdict": label, "exit": code,
                          "why": why, "guards": [g[0] for g in analysis["guards"]],
                          "hazards": analysis["hazards"],
                          "results": (execution or {}).get("results", [])}, indent=2))
    else:
        print(f"arm_check: {label} — {why}")
    return code


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Find quantities that are computed twice, with different parameters — F260.

The dead-lever census (F145) asks *"is this knob read?"*. That question misses the most
expensive defects in this repository, because the knobs it misses **are** read. `engine.py`
passes `rsi_period` to `add_momentum_features`, which honours it and writes a correct
`df["rsi"]`. Everything a reader would inspect is right. And the entry gate still ignores
it, because `momentum_signal()` calls `compute_rsi(close)` again — with the function's
default period — instead of reading the column that was just built.

So this asks a different question: **does the value that is displayed equal the value that
governs?** The mechanical signature of a No is a *recomputation that drops parameters*:

    df["rsi"] = compute_rsi(df["close"], period=rsi_period)   # canonical: forwards the knob
    ...
    rsi = compute_rsi(close)                                  # divergent: silently defaults

Two call sites, one quantity, different parameters. The first is what gets logged, charted
and swept; the second is what decides trades.

Severities:

* ``divergent``  — the recomputation supplies strictly fewer PARAMETERS than the canonical
  assignment, so it takes defaults the canonical call deliberately overrides. This is a
  real behavioural split whenever the config value differs from the default.
* ``duplicate``  — same parameters, so the values agree. Wasteful, not wrong. Reported
  separately and never counted as a finding, because promoting it would bury the real ones.

"Parameters", not "keywords", is load-bearing: `volume_signal()` recomputes its inputs
exactly as `momentum_signal()` does, but forwards `window` POSITIONALLY, so the values
agree. A keyword-only reading flagged that as a third finding — the detector's own first
false positive, and the reason it binds positional arguments against the callee signature.
`momentum.py` is the outlier precisely because it forwards nothing.

What this deliberately does NOT flag: a helper called once, a `compute_*` used outside any
feature builder, or a recomputation whose parameters match. Precision matters more than
recall here — a census that cries wolf gets ignored, which is how F145's five dead knobs
sat unexamined.

Usage::

    python3 tools/recompute_audit.py [--json] [PATH ...]
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from typing import Dict, List, Optional, Sequence

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_PATHS = ("src", "live")


def _param_names(fn: ast.FunctionDef) -> List[str]:
    a = fn.args
    return [p.arg for p in list(a.posonlyargs) + list(a.args)]


def _supplied(call: ast.Call, params: Sequence[str]) -> frozenset:
    """Parameters this call actually supplies, positional AND keyword.

    Counting keywords alone was the detector's first bug: `compute_bb_width(df["close"],
    window)` forwards the knob POSITIONALLY, and a keyword-only reading called that a
    divergence. Binding positional args against the callee's signature is what makes the
    difference between a finding and a false alarm.
    """
    names = set(p.arg for p in call.keywords if p.arg is not None)
    names.update(params[:len(call.args)])
    return frozenset(names)


def _call_name(node: ast.AST) -> Optional[str]:
    """`compute_rsi(...)` -> 'compute_rsi'; `mod.compute_rsi(...)` -> 'compute_rsi'."""
    if not isinstance(node, ast.Call):
        return None
    fn = node.func
    if isinstance(fn, ast.Name):
        return fn.id
    if isinstance(fn, ast.Attribute):
        return fn.attr
    return None


def _subscript_columns(target: ast.AST) -> List[str]:
    """Column names from `df["x"]` or `df["a"], df["b"] = ...`."""
    targets = target.elts if isinstance(target, ast.Tuple) else [target]
    out = []
    for t in targets:
        if isinstance(t, ast.Subscript):
            key = t.slice
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                out.append(key.value)
    return out


class _Collector(ast.NodeVisitor):
    """One pass: canonical `df[col] = compute_X(...)` assignments, and every call site."""

    def __init__(self, path: str):
        self.path = path
        self.canonical: Dict[str, dict] = {}
        self.calls: List[dict] = []
        self.signatures: Dict[str, List[str]] = {}
        self._func: List[str] = []

    def visit_FunctionDef(self, node):                       # noqa: N802
        if node.name.startswith("compute_"):
            self.signatures[node.name] = _param_names(node)
        self._func.append(node.name)
        self.generic_visit(node)
        self._func.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Assign(self, node):                            # noqa: N802
        name = _call_name(node.value)
        if name and name.startswith("compute_"):
            cols = []
            for tgt in node.targets:
                cols.extend(_subscript_columns(tgt))
            if cols:
                self.canonical.setdefault(name, []).append({
                    "producer": name, "columns": cols, "node": node.value,
                    "line": node.lineno, "func": self._func[-1] if self._func else None,
                    "path": self.path,
                })
        self.generic_visit(node)

    def visit_Call(self, node):                              # noqa: N802
        name = _call_name(node)
        if name and name.startswith("compute_"):
            self.calls.append({
                "producer": name, "node": node, "line": node.lineno,
                "func": self._func[-1] if self._func else None, "path": self.path,
            })
        self.generic_visit(node)


def _python_files(paths: Sequence[str]) -> List[str]:
    out = []
    for p in paths:
        full = p if os.path.isabs(p) else os.path.join(REPO, p)
        if os.path.isfile(full) and full.endswith(".py"):
            out.append(full)
        for root, dirs, files in os.walk(full):
            dirs[:] = [d for d in dirs if d not in {"__pycache__", ".git", "node_modules"}]
            out.extend(os.path.join(root, f) for f in sorted(files) if f.endswith(".py"))
    return sorted(set(out))


def scan(paths: Sequence[str] = DEFAULT_PATHS) -> List[dict]:
    """Every recomputation of a quantity that also has a canonical column assignment."""
    signatures: Dict[str, List[str]] = {}
    candidates: Dict[str, list] = {}
    calls: List[dict] = []
    for path in _python_files(paths):
        try:
            with open(path, encoding="utf-8") as fh:
                tree = ast.parse(fh.read(), filename=path)
        except (SyntaxError, UnicodeDecodeError):
            continue
        c = _Collector(os.path.relpath(path, REPO))
        c.visit(tree)
        signatures.update(c.signatures)
        for name, infos in c.canonical.items():
            candidates.setdefault(name, []).extend(infos)
        calls.extend(c.calls)

    # Signatures are known only after every file is parsed, so bind arguments now.
    canonical: Dict[str, dict] = {}
    for name, infos in candidates.items():
        params = signatures.get(name, [])
        for info in infos:
            info["supplied"] = _supplied(info["node"], params)
        # Keep the RICHEST canonical assignment — the one forwarding most knobs.
        canonical[name] = max(infos, key=lambda i: len(i["supplied"]))
    for call in calls:
        call["supplied"] = _supplied(call["node"], signatures.get(call["producer"], []))

    findings = []
    for call in calls:
        canon = canonical.get(call["producer"])
        if canon is None:
            continue                                  # no column is built from it
        if call["line"] == canon["line"] and call["path"] == canon["path"]:
            continue                                  # this IS the canonical assignment
        missing = canon["supplied"] - call["supplied"]
        findings.append({
            "producer": call["producer"],
            "columns": canon["columns"],
            "canonical": "{}:{}".format(canon["path"], canon["line"]),
            "canonical_func": canon["func"],
            "recomputed_at": "{}:{}".format(call["path"], call["line"]),
            "recomputed_in": call["func"],
            "missing_kwargs": sorted(missing),
            "severity": "divergent" if missing else "duplicate",
        })
    findings.sort(key=lambda f: (f["severity"] != "divergent", f["recomputed_at"]))
    return findings


def divergent(paths: Sequence[str] = DEFAULT_PATHS) -> List[dict]:
    return [f for f in scan(paths) if f["severity"] == "divergent"]


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("paths", nargs="*", default=list(DEFAULT_PATHS))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    found = scan(args.paths or DEFAULT_PATHS)
    if args.json:
        print(json.dumps(found, indent=2))
        return 0

    div = [f for f in found if f["severity"] == "divergent"]
    dup = [f for f in found if f["severity"] == "duplicate"]
    print("RECOMPUTATION AUDIT — does the displayed value equal the governing one?\n")
    if not div:
        print("  no divergent recomputations")
    for f in div:
        print("  DIVERGENT  {}()  ->  column(s) {}".format(
            f["producer"], ", ".join(repr(c) for c in f["columns"])))
        print("     canonical   {}  in {}()".format(f["canonical"], f["canonical_func"]))
        print("     recomputed  {}  in {}()".format(f["recomputed_at"], f["recomputed_in"]))
        print("     drops       {}  -> silently takes the function defaults\n".format(
            ", ".join(f["missing_kwargs"])))
    print("  {} divergent, {} benign duplicate(s)".format(len(div), len(dup)))
    return 1 if div else 0


if __name__ == "__main__":
    sys.exit(main())

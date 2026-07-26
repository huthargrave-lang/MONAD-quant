#!/usr/bin/env python3
"""Census: which feature columns does any code actually read?

The companion to `config_reachability.py`. That one counts config constants; this counts
the DataFrame columns the signal/strategy layer writes. Two findings already name single
instances — F145 (two Kelly-multiplier columns computed and consumed by nothing) and F224
(a signal column whose flag gates only its own computation). This supplies the denominator.

**Write vs read is the whole difficulty**, and getting it wrong is the recurring bug in
this repo's own tooling: `df.loc[(df["regime"] == "BEAR") & …, "bear_short_signal"] = 1`
is a WRITE to `bear_short_signal` and a READ of `regime`, but a text match calls it a
write to both. So writes are identified by the **subscript key of an assignment target**,
and reads by any other mention of the column name — with the target subtrees excluded by
node identity.

Classes:

    read        written by the feature layer and read somewhere else in shipping code
    write_only  written, never read outside its own assignment targets
    external    read but not written here (e.g. raw OHLCV: open/high/low/close/volume)

`write_only` is not automatically a defect. An indicator can be written for a human
reading a diagnostic dump, and several here are. It IS the set worth looking at, because
every dead lever this project has found lives in it.

Usage::

    python3 tools/column_reachability.py [--json out.json] [--show write_only]
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from collections import Counter

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SELF = os.path.abspath(__file__)
if REPO not in sys.path:
    sys.path.insert(0, REPO)

# Where feature columns are produced. Kept explicit rather than "anything under src/":
# the question is what the FEATURE LAYER offers, and a study tool writing its own
# scratch column is not part of that contract.
PRODUCERS = (
    "src/signals/momentum.py",
    "src/signals/volume.py",
    "src/signals/volatility.py",
    "src/strategy/engine.py",
)
CONSUMERS = ("src", "tools", "live", "main.py", "sweep.py")
CLASSES = ("read", "write_only", "external")
# Columns that arrive with the data rather than being produced here.
RAW = {"open", "high", "low", "close", "volume"}


def _py_files(*roots):
    out = []
    for root in roots:
        path = os.path.join(REPO, root)
        if os.path.isfile(path):
            out.append(path)
            continue
        for base, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            out += [os.path.join(base, f) for f in files
                    if f.endswith(".py") and os.path.join(base, f) != SELF]
    return out


def _assigned_key(target):
    """The column an assignment target writes, or None.

    `df["x"] = …` writes x. `df.loc[mask, "x"] = …` writes x — the LAST element of the
    subscript tuple. Anything the mask mentions is read, not written.
    """
    if not isinstance(target, ast.Subscript):
        return None
    key = target.slice
    if isinstance(key, ast.Tuple):
        key = key.elts[-1] if key.elts else None
    if isinstance(key, ast.Constant) and isinstance(key.value, str):
        return key.value
    return None


def written_columns():
    """{column: [producer files]} for every column the feature layer assigns."""
    out = {}
    for rel in PRODUCERS:
        path = os.path.join(REPO, rel)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        for node in ast.walk(tree):
            targets = (node.targets if isinstance(node, ast.Assign)
                       else [node.target] if isinstance(node, ast.AugAssign) else [])
            for target in targets:
                col = _assigned_key(target)
                if col:
                    out.setdefault(col, set()).add(rel)
    return {k: sorted(v) for k, v in out.items()}


def _write_key_nodes(tree):
    """Node ids that sit in WRITE position: the key of an assignment target.

    Only the key. In `df.loc[df["adx"] < 20, "adx_kelly_mult"] = 0.8` the target subtree
    also contains `df["adx"]`, which is a READ used to build the mask. Excluding the whole
    target subtree — the first version of this — hid every mask read, and made `adx` look
    like it was only ever tested for existence.
    """
    keys = set()
    for node in ast.walk(tree):
        targets = (node.targets if isinstance(node, ast.Assign)
                   else [node.target] if isinstance(node, ast.AugAssign) else [])
        for target in targets:
            if not isinstance(target, ast.Subscript):
                continue
            key = target.slice
            if isinstance(key, ast.Tuple):
                key = key.elts[-1] if key.elts else None
            if isinstance(key, ast.Constant):
                keys.add(id(key))
    return keys


def read_sites(column):
    """Files that mention `column` somewhere OTHER than in write position."""
    pattern = re.compile(r"""["']""" + re.escape(column) + r"""["']""")
    hits = []
    for path in _py_files(*CONSUMERS):
        with open(path, encoding="utf-8") as fh:
            source = fh.read()
        if not pattern.search(source):
            continue
        try:
            tree = ast.parse(source)
        except SyntaxError:                      # not our problem here
            continue
        in_target = _write_key_nodes(tree)
        for node in ast.walk(tree):
            if id(node) in in_target:
                continue
            if isinstance(node, ast.Constant) and node.value == column:
                hits.append(os.path.relpath(path, REPO))
                break
    return sorted(set(hits))


def census():
    written = written_columns()
    result = {}
    for column, producers in written.items():
        readers = [r for r in read_sites(column) if r not in producers] or []
        # A producer file may legitimately read its own column downstream; count that too,
        # but separately, so "only its own module uses it" stays visible.
        own = [r for r in read_sites(column) if r in producers]
        result[column] = {
            "kind": "read" if readers or own else "write_only",
            "written_by": producers,
            "read_by": readers,
            "read_within_producer": own,
        }
    for column in sorted(RAW):
        result.setdefault(column, {"kind": "external", "written_by": [],
                                   "read_by": read_sites(column),
                                   "read_within_producer": []})
    return {"columns": result,
            "counts": dict(Counter(v["kind"] for v in result.values()))}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", default=None)
    ap.add_argument("--show", choices=CLASSES, default=None)
    args = ap.parse_args(argv)

    report = census()
    produced = [c for c, v in report["columns"].items() if v["kind"] != "external"]
    print("{} columns produced by the feature layer".format(len(produced)))
    for kind in CLASSES:
        n = report["counts"].get(kind, 0)
        print("  {:<12} {:>3}".format(kind, n))

    if args.show:
        print("\n{}:".format(args.show))
        for column, meta in sorted(report["columns"].items()):
            if meta["kind"] != args.show:
                continue
            where = ", ".join(meta["read_by"] + meta["read_within_producer"]) or "—"
            print("  {:<24} written by {:<44} read by {}".format(
                column, ", ".join(meta["written_by"]) or "—", where))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, sort_keys=True)
            fh.write("\n")
        print("\nwrote {}".format(args.json))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

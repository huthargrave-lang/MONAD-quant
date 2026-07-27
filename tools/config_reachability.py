#!/usr/bin/env python3
"""Census: which config constants can any code actually read?

Three findings in this repo say the same thing about single knobs: F145 (a sizing flag
with no reader anywhere), F224 (a signal flag that gates only its own computation), F225
(a filter reading a key its parser never emits). Nobody had counted, so this does.

The flag names are cited by NODE ID rather than spelled out, deliberately: F145's guard
asserts its flag has no reader outside config, and a census tool that named it in prose
would itself become the reader. Seventh instance in this codebase of a detector that
changes what it measures by describing it.

**The measurement that makes it honest is the dynamic one.** `build_features` dispatches
per mode with `getattr(config, f"RSI_PERIOD_{suffix}")`, and several tools do the same, so
a literal-name grep calls 108 constants dead when most are reached through a template. The
census therefore classifies each constant as:

    static        a first-party module names it literally
    dynamic       no literal reference, but its name matches a `getattr(config, f"P_{..}")`
                  template used somewhere (P_ is the prefix; the suffix is a mode name)
    tests-only    named only under tests/ — nothing in the shipping path reads it
    unreferenced  named nowhere outside config itself

`dynamic` is a REACHABILITY claim, not proof any run reads it: a per-mode constant for a
mode nobody selects is reachable and unread. It is reported separately for that reason
rather than merged into `static`.

Usage::

    python3 tools/config_reachability.py [--json out.json] [--show unreferenced]
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
SHIPPING = ("src", "tools", "live", "main.py", "sweep.py")
CLASSES = ("static", "dynamic", "tests-only", "unreferenced")


SELF = os.path.abspath(__file__)


def _py_files(*roots):
    """Every first-party .py under `roots`, EXCLUDING this file.

    This module's own docstring shows `getattr(config, f"PREFIX_{..}")` as an example,
    and scanning itself turned `P` and `PREFIX` into dispatch prefixes — a detector that
    reads its own explanation as data. Sixth instance of that class in this codebase.
    """
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


def config_constants():
    """{NAME: defining file} for module-level UPPER_CASE assignments in the config layer."""
    consts = {}
    sources = [os.path.join(REPO, "config.py")]
    mod_dir = os.path.join(REPO, "config_modules")
    if os.path.isdir(mod_dir):
        sources += sorted(os.path.join(mod_dir, f) for f in os.listdir(mod_dir)
                          if f.endswith(".py"))
    for path in sources:
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id.isupper():
                        consts.setdefault(target.id,
                                          os.path.relpath(path, REPO))
    return consts


def known_suffixes():
    """Mode names a dispatch template can actually resolve to.

    A prefix match is NOT a reachability proof. `TARGET_GAIN_PCT_STRONG_BULL` matches the
    `TARGET_GAIN_PCT_` template, but STRONG_BULL is a REGIME, not a mode — no code builds
    that name, and the constant is unreachable. Same for `RSI_OVERSOLD_BEAR`. The suffix
    must be a configured mode (or the legacy bare `HOURLY` used by BTC_HOURLY).
    """
    sys.path.insert(0, REPO)
    import config  # noqa: PLC0415 — deliberately late; this tool exists to inspect it
    return set(getattr(config, "ASSETS", {})) | {"HOURLY"}


def dynamic_prefixes(blob):
    """Prefixes of `getattr(config, f"PREFIX_{...}")`, plus the `{k}_{mode}` key lists.

    Two shapes are in use: a literal prefix in the f-string, and a loop over a tuple of
    key names formatted as `f"{k}_{mode}"`. Both make a whole family of per-mode
    constants reachable without any of them appearing literally.
    """
    prefixes = set(re.findall(r'getattr\(config,\s*f"([A-Z_]+)_\{', blob))
    for keylist in re.findall(r"for k in \(([^)]*)\)", blob):
        prefixes |= set(re.findall(r'"([A-Z_]+)"', keylist))
    return prefixes


def census():
    consts = config_constants()
    ship_blob = "\n".join(open(p, encoding="utf-8").read() for p in _py_files(*SHIPPING))
    test_blob = "\n".join(open(p, encoding="utf-8").read() for p in _py_files("tests"))
    prefixes = dynamic_prefixes(ship_blob)
    suffixes = known_suffixes()

    def resolvable(name):
        for prefix in prefixes:
            if name.startswith(prefix + "_"):
                return name[len(prefix) + 1:] in suffixes
        return False

    result = {}
    for name in consts:
        word = re.compile(r"\b" + re.escape(name) + r"\b")
        if word.search(ship_blob):
            kind = "static"
        elif resolvable(name):
            kind = "dynamic"
        elif word.search(test_blob):
            kind = "tests-only"
        else:
            kind = "unreferenced"
        result[name] = {"kind": kind, "defined_in": consts[name]}
    counts = dict(Counter(v["kind"] for v in result.values()))
    # The headline quantity is "does SHIPPING code read this?", which is stable under
    # observation. `unreferenced` alone is not: naming a dead constant in a guard moves
    # it to `tests-only`, so a test that pins the dead set changes the dead set. Report
    # the union, and let the two sub-classes float.
    counts["dead_to_shipping"] = (counts.get("unreferenced", 0)
                                  + counts.get("tests-only", 0))
    return {"subject": "repository",  # not an observation of the world; see F230
            "prefixes": sorted(prefixes), "suffixes": sorted(suffixes),
            "constants": result, "counts": counts}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", default=None)
    ap.add_argument("--show", choices=CLASSES, default=None,
                    help="list the constants in one class")
    args = ap.parse_args(argv)

    report = census()
    total = len(report["constants"])
    print("{} config constants".format(total))
    for kind in CLASSES:
        n = report["counts"].get(kind, 0)
        print("  {:<14} {:>4}  ({:.0%})".format(kind, n, n / total if total else 0))
    dead = report["counts"]["dead_to_shipping"]
    print("  {:<14} {:>4}  ({:.0%})   <- unreferenced + tests-only".format(
        "DEAD to src", dead, dead / total if total else 0))
    print("\ndynamic dispatch prefixes: {}".format(", ".join(report["prefixes"])))
    naive = report["counts"].get("dynamic", 0) + dead
    print("a literal-name census would call {} dead; {} actually are".format(naive, dead))

    if args.show:
        print("\n{}:".format(args.show))
        for name, meta in sorted(report["constants"].items()):
            if meta["kind"] == args.show:
                print("  {:<32} {}".format(name, meta["defined_in"]))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, sort_keys=True)
            fh.write("\n")
        print("\nwrote {}".format(args.json))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

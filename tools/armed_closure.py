#!/usr/bin/env python3
"""armed_closure.py — which files can change how the bot trades, computed not guessed.

THE FINDING THIS ENCODES
    context_map.json's edit_policy denies writes to `live/`, `config.py` and
    `config_modules/`. That list is hand-maintained, and it is already wrong:

        live/trader.py  ->  live/signals.py  ->  src/data/fetcher.py
                                             ->  src/strategy/engine.py
                                                     ->  src/signals/{momentum,volume,volatility}.py

    Those src/ modules are imported at arming time and decide when the bot buys.
    They are armed in effect while unfenced on paper. A hand-maintained danger
    list drifts from reality silently — which is the same class of failure as a
    hand-maintained "are we up to date?" belief.

    So: seed at live/trader.py, follow first-party imports transitively, and let
    the import graph state the boundary.

WHAT THIS DOES NOT DO
    It does not edit context_map.json to widen the fence. That file is itself
    DENY-fenced (deliberately, so an agent cannot neuter the guard by editing the
    deny list), and widening the fence to cover src/ would fence this repo's
    primary research surface — an operability regression that would push agents
    into bypassing the guard entirely. Reporting the gap is the useful act;
    closing it is a decision with tradeoffs that belongs to the owner.

USAGE
    python tools/armed_closure.py                # sorted closure, one path per line
    python tools/armed_closure.py --json         # closure + which members are unfenced
    python tools/armed_closure.py --unfenced     # only the gap, exit 1 if non-empty
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SEED = "live/trader.py"

# Import roots that belong to this project. Anything else (pandas, ib_insync,
# apscheduler) is third-party: real dependencies, but not files whose EDITS in
# this repo can change trading behaviour, which is what the closure is about.
FIRST_PARTY = ("live", "config", "config_modules", "src", "tools")


def _module_to_paths(mod: str, root: Path) -> list[Path]:
    """Resolve a dotted module name to the file(s) that provide it."""
    rel = mod.replace(".", "/")
    out = []
    for cand in (root / f"{rel}.py", root / rel / "__init__.py"):
        if cand.is_file():
            out.append(cand)
    return out


def _imports_of(path: Path) -> set[str]:
    """Every first-party dotted module this file imports."""
    try:
        tree = ast.parse(path.read_text())
    except (OSError, SyntaxError):
        return set()
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                found.add(a.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:            # relative import
                continue
            if not node.module:
                continue
            found.add(node.module)
            # `from live import alerts, broker` -> live.alerts, live.broker
            for a in node.names:
                found.add(f"{node.module}.{a.name}")
    return {m for m in found if m.split(".")[0] in FIRST_PARTY}


def closure(root: Path = REPO, seed: str = SEED) -> list[str]:
    """Transitive first-party import closure, as repo-relative sorted paths."""
    start = root / seed
    if not start.is_file():
        return []
    seen: set[Path] = {start}
    queue = [start]
    while queue:
        cur = queue.pop()
        for mod in _imports_of(cur):
            for p in _module_to_paths(mod, root):
                if p not in seen:
                    seen.add(p)
                    queue.append(p)
    return sorted(str(p.relative_to(root)) for p in seen)


def deny_patterns(root: Path = REPO) -> list[str]:
    try:
        m = json.loads((root / "context_map.json").read_text())
    except (OSError, ValueError):
        return []
    return list(m.get("edit_policy", {}).get("deny", []))


def is_fenced(relpath: str, patterns: list[str]) -> bool:
    for pat in patterns:
        if pat.endswith("/"):
            if relpath.startswith(pat):
                return True
        elif pat.startswith("*."):
            if relpath.endswith(pat[1:]):
                return True
        elif relpath == pat:
            return True
    return False


def unfenced(root: Path = REPO) -> list[str]:
    pats = deny_patterns(root)
    return [p for p in closure(root) if not is_fenced(p, pats)]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Files that can change trading behaviour.")
    ap.add_argument("--root", default=str(REPO))
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--unfenced", action="store_true",
                    help="print only closure members the deny fence misses; exit 1 if any")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()

    members = closure(root)
    gap = unfenced(root)

    if args.json:
        print(json.dumps({"seed": SEED, "closure": members,
                          "deny_patterns": deny_patterns(root), "unfenced": gap}, indent=2))
    elif args.unfenced:
        for p in gap:
            print(p)
        return 1 if gap else 0
    else:
        for p in members:
            print(p)
    return 0


if __name__ == "__main__":
    sys.exit(main())

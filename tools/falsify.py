"""Which guards can actually fail?

THE QUESTION
------------
This repo's discipline is that every guard gets mutation-checked when it is written. Nothing
re-checks the ones written last month. A guard that cannot fail is worse than no guard: it
manufactures confidence nobody earned, and 800 green tests are worth exactly as much as their
ability to go red.

This derives the mutation from the assertion itself. For every `assertIn("literal", ...)` in a
suite, find that literal in the source the guard reads, corrupt it, and run that one test.
Still green means the guard did not notice its own subject being destroyed.

WHAT IT COVERS, AND WHAT IT DOES NOT
-------------------------------------
Only `assertIn(<string literal>, ...)` where the literal appears in a tracked source. That is
deliberately the most suspicious shape in this suite — "assert this sentence is present" is
the guard form this codebase has been burned by repeatedly — and it is a small fraction of the
tests. A clean run says nothing about guards that assert computed values, `assertNotIn`,
`assertEqual`, or behaviour. Do not read a zero here as the suite being sound.

It also cannot find the OTHER failure mode: a guard whose extraction is broken, so it cannot
see text that IS present. That one shows up as red the moment it is written.

THE BUG THIS TOOL HAD, WHICH IS THE CLASS IT EXISTS TO FIND
------------------------------------------------------------
LOCAL UNIQUENESS IS NOT UNIQUENESS. `find_home` picked the file where a literal appeared
exactly once while it appeared forty times elsewhere, so it mutated a copy the guard never
reads and the guard "survived" a mutation that never touched it. That alone produced 36
confident false positives, every one of which evaporated on inspection.

Two further "bugs" were written up here and were WRONG, which is worth more than the fix was:
a test path that does not resolve was said to run zero tests and exit 0, and two test files
were said to share a class name. Neither is true — unittest reports an unresolvable path as
one errored test with a non-zero status, and the class in question exists once. The first
claim came from reading `rc=$?` after a pipe, which returns the exit status of `tail`.

WHY A SURVIVOR IS A QUESTION, NOT A VERDICT
--------------------------------------------
Even with a globally unique literal, the file holding it may not be the file the guard reads:
a guard over the buckets page can name a string that lives in the screener's renderer. The
only decisive confirmation is to destroy the string and run the WHOLE suite. If nothing
anywhere goes red, the string is genuinely unguarded. Every survivor this tool has reported
so far has been caught that way — 14 of 14.

    venv/bin/python tools/falsify.py --tests tests.test_screener_ui tests.test_scenarios
"""
import argparse
import ast
import json
import os
import re
import shutil
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = os.path.join(REPO, "venv/bin/python")

#: Sources a guard might read. A literal is mutated in whichever of these holds it uniquely.
SOURCES = [
    "docs/research/SCREENER_COMBINED_DRAFT.html",
    "tools/research_ui.py", "tools/sovereign_buckets.py", "tools/scenarios.py",
    "tools/concentration.py", "tools/channel_stats.py", "tools/bucket_lab.py",
    "tools/screener_lab.py", "tools/stock_screener.py", "tools/export_pages.py",
    "tools/ctx.py",
]

ASSERTS = {"assertIn", "assertRegex"}       # "this must be present" — the falsifiable shape


def literals(path):
    """(class, method, literal) for every presence-assertion carrying a plain string."""
    tree = ast.parse(open(path, encoding="utf-8").read())
    out = []
    for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
        for fn in [n for n in cls.body if isinstance(n, ast.FunctionDef)]:
            if not fn.name.startswith("test"):
                continue
            for node in ast.walk(fn):
                if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                    continue
                if node.func.attr not in ASSERTS or not node.args:
                    continue
                a = node.args[0]
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    out.append((cls.name, fn.name, a.value, node.func.attr))
    return out


def find_home(lit, cache):
    """The one source file holding this literal exactly once, or None."""
    homes = []
    for rel in SOURCES:
        if rel not in cache:
            p = os.path.join(REPO, rel)
            cache[rel] = open(p, encoding="utf-8").read() if os.path.exists(p) else ""
        n = cache[rel].count(lit)
        if n:
            homes.append((rel, n))
    # GLOBALLY unique, not locally. Picking the file where a literal appears once while it
    # appears forty times elsewhere mutates a copy the test never reads, and the guard then
    # "survives" a mutation that never touched it — the same false-confidence shape this
    # audit exists to find, in the audit.
    total = sum(n for _r, n in homes)
    if total != 1:
        return None
    return homes[0][0]


def corrupt(lit):
    """Alter the literal so a presence check fails, keeping length and shape.

    Letters are rotated rather than the string deleted: deleting can break syntax (an unclosed
    brace), and a guard going red because the file stopped parsing is not the guard working.
    """
    out = []
    for ch in lit:
        if ch.isalpha():
            out.append("q" if ch.lower() != "q" else "z")
        else:
            out.append(ch)
    return "".join(out)


def run(mod, cls, fn, timeout=180):
    """True if the test ran and passed, False if it ran and failed, None if it did not run.

    The None arm is DEFENSIVE and has never fired: unittest reports an unresolvable path as
    one errored test with a non-zero status, so the "zero tests, exit 0" case this was written
    for does not exist. Kept because reading "no tests ran" as "the guard survived" would be a
    check that cannot fail because it never ran, and that failure would be silent — but it is
    documented here as insurance rather than as a fixed bug, because it never was one.
    """
    r = subprocess.run([PY, "-m", "unittest", "%s.%s.%s" % (mod, cls, fn)],
                       capture_output=True, text=True, cwd=REPO, timeout=timeout)
    m = re.search(r"^Ran (\d+) test", r.stderr or "", re.M)
    if not m or int(m.group(1)) < 1:
        return None                      # did not run — not evidence either way
    return r.returncode == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tests", nargs="+", required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default="falsify_results.json")
    args = ap.parse_args()

    cache, jobs = {}, []
    for mod in args.tests:
        path = os.path.join(REPO, "tests", mod.split(".")[-1] + ".py")
        for cls, fn, lit, kind in literals(path):
            if kind == "assertRegex" or len(lit) < 8:
                continue                                  # regexes are not literal source text
            home = find_home(lit, cache)
            if home:
                jobs.append({"mod": mod, "cls": cls, "fn": fn, "lit": lit, "src": home})
    # One job per (test, source): breaking any one literal should be enough to fail the test,
    # so a test with five literals is asked once — the cheapest question that answers it.
    seen, uniq = set(), []
    for j in jobs:
        k = (j["mod"], j["cls"], j["fn"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(j)
    uniq = uniq[:args.limit]
    print("candidate guards with a source literal: %d" % len(uniq), flush=True)

    results = []
    for i, j in enumerate(uniq, 1):
        p = os.path.join(REPO, j["src"])
        src = open(p, encoding="utf-8").read()
        if src.count(j["lit"]) != 1:
            continue
        shutil.copy(p, p + ".falsify")
        try:
            open(p, "w", encoding="utf-8").write(src.replace(j["lit"], corrupt(j["lit"]), 1))
            green = run(j["mod"], j["cls"], j["fn"])
        except Exception as e:                                          # noqa: BLE001
            green = None
            j["error"] = str(e)[:120]
        finally:
            shutil.move(p + ".falsify", p)
        j["survived_mutation"] = green
        results.append(j)
        if green:
            print("  VACUOUS  %s.%s\n           literal: %r\n           in: %s"
                  % (j["cls"], j["fn"], j["lit"][:70], j["src"]), flush=True)
        if i % 25 == 0:
            print("  ... %d/%d" % (i, len(uniq)), flush=True)

    bad = [r for r in results if r["survived_mutation"]]
    json.dump(results, open(args.out, "w"), indent=1)
    print("\n%d guards probed, %d SURVIVED their own literal being destroyed" % (len(results), len(bad)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

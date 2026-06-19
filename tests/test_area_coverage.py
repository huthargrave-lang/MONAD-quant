"""
KA5 CI guard: the agent context map must *cover* the codebase.

Every first-party Python module must be claimed by some `context_map.json` area
(via its `files` list, directly or through a dir-prefix entry like `ops/`) OR be
named in `coverage_allowlist.modules` with a documented reason. This makes the
repomap (`ctx tree` / `ctx summary`) and the area model trustworthy: a NEW module
that nobody mapped fails CI and gets triaged, instead of silently going un-routed.

Also here (KA6-adjacent): every area's `tests` list must reference files that
exist, and `ctx covers` must be able to resolve a known symbol → its tests.

Stdlib + the `ctx` helpers only (no third-party deps).
"""
import ast
import json
import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(REPO, "context_map.json")
sys.path.insert(0, os.path.join(REPO, "tools"))
import ctx  # noqa: E402  (reuse the repomap + manifest helpers)


def _load():
    with open(MANIFEST) as f:
        return json.load(f)


def _claimed_modules(m):
    """All .py modules claimed by some area's `files` (direct or dir-prefix)."""
    mods = ctx._first_party_modules()
    claimed = set()
    for spec in m["areas"].values():
        for f in spec["files"]:
            if f.endswith(".py"):
                claimed.add(f)
            elif f.endswith("/"):
                claimed.update(mm for mm in mods if mm.startswith(f))
    return claimed


class TestAreaCoverage(unittest.TestCase):
    """Every first-party module is claimed by an area or explicitly allow-listed."""

    def setUp(self):
        self.m = _load()
        self.mods = ctx._first_party_modules()
        self.allow = set(self.m.get("coverage_allowlist", {}).get("modules", []))

    def test_every_module_is_claimed_or_allowlisted(self):
        claimed = _claimed_modules(self.m)
        orphans = [x for x in self.mods if x not in claimed and x not in self.allow]
        self.assertEqual(
            orphans, [],
            "first-party module(s) not claimed by any context_map.json area and not in "
            "coverage_allowlist.modules — add them to an area's `files` or to the "
            f"allow-list with a reason: {orphans}",
        )

    def test_allowlist_entries_exist_and_arent_already_claimed(self):
        """Anti-drift: an allow-list entry must be a real module, and must NOT
        duplicate an area claim (which would mean it should just be in the area)."""
        claimed = _claimed_modules(self.m)
        for mod in sorted(self.allow):
            with self.subTest(module=mod):
                self.assertTrue(os.path.exists(os.path.join(REPO, mod)),
                                f"coverage_allowlist references missing module: {mod}")
                self.assertNotIn(mod, claimed,
                                 f"{mod} is both allow-listed AND claimed by an area — "
                                 "remove it from the allow-list")

    def test_allowlist_has_a_reason(self):
        """The allow-list must carry a human-readable rationale (so it can't become
        a silent dumping ground)."""
        al = self.m.get("coverage_allowlist", {})
        self.assertIn("_README", al, "coverage_allowlist needs a _README explaining the policy")
        self.assertTrue(al["_README"].strip())


class TestDocstringAdvisory(unittest.TestCase):
    """Lightweight 'module has a docstring' check. Package markers (__init__.py)
    are exempt. Advisory in spirit, but enforced for the substantive modules we
    have today (they all currently have one) so a new undocumented module is caught."""

    def test_substantive_modules_have_a_module_docstring(self):
        missing = []
        for rel in ctx._first_party_modules():
            if os.path.basename(rel) == "__init__.py":
                continue
            try:
                with open(os.path.join(REPO, rel), errors="ignore") as fh:
                    doc = ast.get_docstring(ast.parse(fh.read()))
            except (OSError, SyntaxError):
                continue
            if not (doc and doc.strip()):
                missing.append(rel)
        self.assertEqual(
            missing, [],
            f"module(s) missing a top-level docstring (ctx tree/summary show it as "
            f"the one-line description — please add one): {missing}",
        )


class TestAreaTestsResolve(unittest.TestCase):
    """KA6: every area's `tests` list points at files that exist, and the symbol→
    test mapping that `ctx covers` relies on actually resolves."""

    def setUp(self):
        self.m = _load()

    def test_area_tests_exist(self):
        for area, spec in self.m["areas"].items():
            for t in spec.get("tests", []):
                with self.subTest(area=area, test=t):
                    self.assertTrue(os.path.exists(os.path.join(REPO, t)),
                                    f"area '{area}' lists a missing test file: {t}")

    def test_covers_resolves_known_symbol_to_its_area_tests(self):
        """`ctx covers classify_regime` must find its module, its area, and that
        area's tests — the core symbol→file→area→tests chain."""
        rel = ctx._symbol_module("classify_regime")
        self.assertEqual(rel, "src/signals/momentum.py")
        areas = ctx._areas_for_module(rel)
        self.assertIn("signals", areas)
        # signals area lists tests/test_signals.py, and it does mention the symbol.
        self.assertIn("tests/test_signals.py", ctx._tests_grepping("classify_regime"))

    def test_covers_handles_unknown_symbol(self):
        # Build the bogus name at runtime so this file doesn't grep-match itself.
        bogus = "Zz" + "NoSuchSymbol" + "Qq" + "9182"
        self.assertIsNone(ctx._symbol_module(bogus))
        self.assertEqual(ctx._tests_grepping(bogus), [])


if __name__ == "__main__":
    unittest.main()

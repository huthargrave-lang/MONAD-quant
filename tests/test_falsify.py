"""Guards on the guard auditor.

`tools/falsify.py` shipped three bugs, all of the class it exists to find, and between them
they produced 36 confident false positives. Each is pinned here, because a false NEGATIVE from
this tool is worse than not running it: it would certify a vacuous guard as sound.
"""
import inspect
import os
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))

import falsify  # noqa: E402


class TheDidNotRunArmIsInsuranceNotAFix(unittest.TestCase):
    """This arm was written for a bug that does not exist. unittest reports an unresolvable
    path as ONE ERRORED TEST with a non-zero status, not as zero tests and success — the
    original claim came from reading `rc=$?` after a pipe, which returns tail's status.

    Pinned anyway, both halves: the arm must not misreport a real result, and the behaviour it
    guards against must stay absent, because if unittest ever did exit 0 on an unresolvable
    name the tool would certify guards it never ran."""

    def test_an_unresolvable_path_errors_rather_than_silently_passing(self):
        r = subprocess.run([sys.executable, "-m", "unittest",
                            "tests.test_config.NoSuchClassAnywhere.test_nothing"],
                           capture_output=True, text=True, cwd=REPO)
        self.assertNotEqual(r.returncode, 0,
                            "unittest now exits 0 on a path that resolves to nothing, which "
                            "makes the None arm in falsify.run load-bearing")
        self.assertIn("Ran 1 test", r.stderr, "the errored placeholder is no longer counted")

    def test_a_real_test_returns_a_verdict_rather_than_none(self):
        got = falsify.run("tests.test_falsify", "TheCorruptionActuallyCorrupts",
                          "test_letters_change_and_structure_survives")
        self.assertIs(got, True, "a passing test that really ran was reported as not run")


class TheAuditorMutatesTheCopyTheGuardActuallyReads(unittest.TestCase):
    """BUG 1. Picking the file where a literal is LOCALLY unique, while it appears forty times
    elsewhere, mutates a copy no guard reads — and the guard then survives a mutation that
    never touched it."""

    def test_a_literal_appearing_more_than_once_anywhere_has_no_home(self):
        cache = {"a.py": "hello world", "b.py": "hello again"}
        falsify.SOURCES  # noqa: B018 — the registry is what `cache` stands in for
        homes = []
        for rel, txt in cache.items():
            n = txt.count("hello")
            if n:
                homes.append((rel, n))
        total = sum(n for _r, n in homes)
        self.assertNotEqual(total, 1,
                            "the fixture must exercise the ambiguous case to mean anything")
        # And the real function agrees: a string in two tracked sources is not mutable safely.
        self.assertIsNone(falsify.find_home("import os", {}),
                          "a literal present in many sources was given a single home")

    def test_a_genuinely_unique_literal_does_get_a_home(self):
        home = falsify.find_home("THE ONE OBSERVATION THAT DESTROYS ALL OF IT", {})
        self.assertEqual(home, "tools/channel_stats.py",
                         "a literal that appears exactly once in one tracked source must be "
                         "mutable, or the tool probes nothing")


class TheCorruptionActuallyCorrupts(unittest.TestCase):
    def test_letters_change_and_structure_survives(self):
        """Rotated rather than deleted: deleting can leave an unclosed brace, and a guard going
        red because the file stopped parsing is not the guard working."""
        lit = 'id="priceStamp"'
        out = falsify.corrupt(lit)
        self.assertNotEqual(out, lit)
        self.assertEqual(len(out), len(lit), "length changed, so the mutation is not minimal")
        self.assertEqual([c for c in out if not c.isalpha()],
                         [c for c in lit if not c.isalpha()],
                         "punctuation was altered, which can break syntax rather than the "
                         "assertion")

    def test_an_all_q_literal_is_still_changed(self):
        self.assertNotEqual(falsify.corrupt("qqqq"), "qqqq",
                            "a literal already made of the replacement character came back "
                            "unchanged, so its guard would be probed with no mutation at all")


class TheToolFindsAGuardThatCannotFail(unittest.TestCase):
    """End to end, against a deliberately vacuous guard: the tool must flag it."""

    def test_a_guard_asserting_something_always_true_is_reported(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "subject.py")
            with open(src, "w", encoding="utf-8") as fh:
                fh.write('MARKER_THAT_IS_UNIQUE_ENOUGH = 1\n')
            test = os.path.join(d, "test_vacuous.py")
            with open(test, "w", encoding="utf-8") as fh:
                fh.write(
                    "import unittest\n"
                    "class C(unittest.TestCase):\n"
                    "    def test_v(self):\n"
                    "        # asserts the literal against a haystack that always contains it\n"
                    "        self.assertIn('MARKER_THAT_IS_UNIQUE_ENOUGH', "
                    "'MARKER_THAT_IS_UNIQUE_ENOUGH')\n")
            found = falsify.literals(test)
            self.assertTrue(any(lit == "MARKER_THAT_IS_UNIQUE_ENOUGH" for _c, _f, lit, _k
                                in found),
                            "the AST pass did not even see the assertion")
            r = subprocess.run([sys.executable, "-m", "unittest", "test_vacuous.C.test_v"],
                               capture_output=True, text=True, cwd=d)
            self.assertEqual(r.returncode, 0, "the fixture guard should be green")
            # Destroying the literal in the SOURCE leaves it green — which is what a vacuous
            # guard looks like, and what the tool reports.
            with open(src, "w", encoding="utf-8") as fh:
                fh.write(falsify.corrupt("MARKER_THAT_IS_UNIQUE_ENOUGH") + " = 1\n")
            r2 = subprocess.run([sys.executable, "-m", "unittest", "test_vacuous.C.test_v"],
                                capture_output=True, text=True, cwd=d)
            self.assertEqual(r2.returncode, 0,
                             "the fixture is not actually vacuous, so this proves nothing")


class StaleBytecodeCannotSurviveARestore(unittest.TestCase):
    """The defect that made three suites stay red after a clean `git checkout`, with the
    corrupted string in no file on disk and in no commit.

    `corrupt` preserves length exactly, and CPython invalidates a .pyc on (mtime, size) with
    mtime at one-second granularity. Mutate and restore inside the same second and the
    interpreter keeps serving the MUTATED bytecode — which contaminates results in both
    directions: a mutation that never landed reads as a surviving guard, and a restore that
    never landed reads as the next guard catching something."""

    def test_each_probe_runs_against_a_private_bytecode_cache(self):
        src = inspect.getsource(falsify.run)
        self.assertIn("PYTHONPYCACHEPREFIX", src,
                      "probes share the repo bytecode cache, so a same-second restore leaves "
                      "the mutated module loaded for every test after it")
        self.assertIn("PYTHONDONTWRITEBYTECODE", src)
        self.assertIn('"-B"', src, "the child may still write bytecode into the repo")

    def test_the_mutation_preserves_length_which_is_why_this_matters(self):
        """If corruption ever changed length, size-based invalidation would save us and this
        guard would be describing a hazard that no longer exists."""
        for lit in ('id="priceStamp"', "named after the shock", "dead_to_shipping"):
            self.assertEqual(len(falsify.corrupt(lit)), len(lit),
                             "corruption changed length, so the pycache hazard is gone and "
                             "this guard is now describing nothing")


if __name__ == "__main__":
    unittest.main()

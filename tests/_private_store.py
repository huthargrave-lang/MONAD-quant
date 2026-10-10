"""The rule for a test that needs REAL private observations (docs/research/data/README.md,
section 4).

Restricted vendor data is never committed, so continuous integration has no private store
and a test that replays real observations cannot run there. One rule decides, so no test
improvises its own (and none passes silently):

  * the private file is ABSENT  -> the test skips, and the reason names the file and the
                                   command that restores the store;
  * the file is PRESENT         -> it must hash to its name: an altered file FAILS, it never
                                   skips;
  * ``MONAD_REQUIRE_PRIVATE_STORE=1`` -> an absent file FAILS too (a machine, or a CI job
                                   given the store, that is meant to hold it).

Guarded by tests/test_private_store.py::TheSkipRule.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.research import data_store  # noqa: E402

REQUIRE_ENV = "MONAD_REQUIRE_PRIVATE_STORE"
RESTORE_CMD = "venv/bin/python tools/data_inventory.py import <archive>"


def status(prefix: str, sha: str, store: Path | None = None) -> tuple[str, str]:
    """("present", path) | ("absent", why) | ("altered", why) for one private file."""
    store = Path(store) if store is not None else data_store.PRIVATE_DATA_DIR
    path = store / data_store.observations_name(prefix, sha)
    if not path.is_file():
        return "absent", f"{path.name} is not in {store}"
    problem = data_store.verify_file(path)
    return ("altered", problem) if problem else ("present", str(path))


def require(testcase, prefix: str, sha: str, *, store: Path | None = None, env=None) -> Path:
    """Apply the rule inside ``testcase``: return the verified file's path, or skip/fail."""
    env = os.environ if env is None else env
    state, detail = status(prefix, sha, store)
    if state == "altered":
        testcase.fail(f"private store: {detail}")
    if state == "absent":
        why = f"private observations absent ({detail}); restore with `{RESTORE_CMD}`"
        if env.get(REQUIRE_ENV) == "1":
            testcase.fail(f"{why} [{REQUIRE_ENV}=1]")
        testcase.skipTest(why)
    return Path(detail)

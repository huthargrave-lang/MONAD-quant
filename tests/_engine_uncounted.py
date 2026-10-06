"""
Module-scoped ``uncounted`` for tests that exercise the engine's own arithmetic.

src/strategy/counted.py refuses any engine evaluation without a begun trial, and allows
the explicit bypass ``uncounted(reason)`` only when called from tests/ or a listed exempt
tool. A test of how ``compute_trade_returns`` prices a gap is not a strategy evaluation,
so it runs uncounted, with the reason stated once per module:

    from tests._engine_uncounted import uncounted_module
    setUpModule, tearDownModule = uncounted_module("fill-model arithmetic on hand-built bars")

The bypass is entered HERE (inside tests/), which is what the runtime caller check reads.
unittest's ``enterContext`` would make unittest itself the caller, and is refused.
"""
from __future__ import annotations

from src.strategy.counted import uncounted


def uncounted_module(reason: str):
    """(setUpModule, tearDownModule) that hold ``uncounted(reason)`` for the module."""
    held = []

    def setUpModule():
        cm = uncounted(reason)
        cm.__enter__()
        held.append(cm)

    def tearDownModule():
        while held:
            held.pop().__exit__(None, None, None)

    return setUpModule, tearDownModule

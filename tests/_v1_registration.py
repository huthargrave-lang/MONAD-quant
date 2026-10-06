"""
Freeze a gate-rules-v1 registration for a test, as the real v1 registrations exist: an old
frozen file whose spec hash is on prereg.GATE_RULES_V1_ALLOWLIST. ``register()`` itself
refuses v1 (decision debate 2026-10-06), so tests of the v1 chains use this; the allowlist
entry is removed when the test ends.
"""
from src.research import prereg


def register_v1(testcase, spec, **kwargs):
    path, spec_hash = prereg._freeze(spec, **kwargs)
    hyp = spec["hypothesis"]
    previous = prereg.GATE_RULES_V1_ALLOWLIST.get(hyp)
    prereg.GATE_RULES_V1_ALLOWLIST[hyp] = spec_hash

    def restore():
        if previous is None:
            prereg.GATE_RULES_V1_ALLOWLIST.pop(hyp, None)
        else:
            prereg.GATE_RULES_V1_ALLOWLIST[hyp] = previous

    testcase.addCleanup(restore)
    return path, spec_hash

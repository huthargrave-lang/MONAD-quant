"""F110's dual-hash discipline: is it implemented, and does it show what it claims?

F110 concluded that free historical price refreshes are **not byte-stable** — the same
vendor panel re-fetched the same day hashes differently — while the *decision-level*
result, hashed at a preregistered 0.001pp precision, reproduces exactly. Its
prescription was operational: *"Preserve every exact snapshot hash, report a separate
precision-declared result hash."*

Two things are checkable offline, and both hold.

**The prescription is implemented.** Four IX-00 artifacts carry
`normalized_input_sha256` and `derived_result_sha256` side by side, plus a
`fingerprint_contract` and a `refresh_audit` recording the observed refreshes.

**The audit demonstrates the claim.** Every batch records 3–4 *distinct* exact input
hashes against *identical* paired derived hashes. Vendor bytes moved; the decision did
not.

**But the coverage is narrower than the artifact invites.** Each `refresh_audit` pairs
only **2** derived hashes against **3–4** observed inputs. F110's own wording is careful
— it says "reproduce exactly in *paired* refreshes" — but a reader skimming the artifact
could take it as all observed refreshes agreeing, which is not what was measured. That
gap is asserted here so the artifact cannot be over-read.

Two of the six IX-00 artifacts carry no hash block at all
(`ix00_ndx_2023_revision_fixture.json`, `ix00_ndx_recent_complete_panel.json`); they are
a fixture and a panel rather than event batches, so they are identified rather than
failed.
"""
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs" / "research" / "data"
NO_HASH_BLOCK = {
    "ix00_ndx_2023_revision_fixture.json",
    "ix00_ndx_recent_complete_panel.json",
}


def _batches():
    out = []
    for path in sorted(DATA.glob("ix00_*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and "refresh_audit" in payload:
            out.append((path.name, payload))
    return out


class DisciplineIsImplementedTests(unittest.TestCase):
    def test_every_event_batch_carries_both_hashes(self):
        batches = _batches()
        self.assertGreaterEqual(len(batches), 4, "IX-00 event batches disappeared")
        for name, payload in batches:
            self.assertIn("normalized_input_sha256", payload, name)
            self.assertIn("derived_result_sha256", payload, name)
            self.assertIn("fingerprint_contract", payload, name)

    def test_the_artifacts_without_hashes_are_the_known_two(self):
        """Identify them rather than fail: a fixture and a panel are not batches."""
        missing = {p.name for p in DATA.glob("ix00_*.json")
                   if "refresh_audit" not in json.loads(p.read_text(encoding="utf-8"))}
        self.assertEqual(
            missing, NO_HASH_BLOCK,
            "the set of IX-00 artifacts without a hash block changed — a new event "
            "batch may be missing the F110 discipline")


class TheAuditDemonstratesTheClaimTests(unittest.TestCase):
    def test_exact_input_hashes_differ_across_refreshes(self):
        """F110's first half: vendor bytes are not stable."""
        for name, payload in _batches():
            inputs = payload["refresh_audit"]["observed_exact_input_sha256"]
            self.assertGreaterEqual(len(inputs), 2, name)
            self.assertEqual(
                len(set(inputs)), len(inputs),
                "{}: exact input hashes are now identical across refreshes — the "
                "vendor may have become byte-stable, which would make F110 stale "
                "(good news; supersede it rather than editing this test)".format(name))

    def test_paired_derived_hashes_are_identical(self):
        """F110's second half: the decision reproduces."""
        for name, payload in _batches():
            derived = payload["refresh_audit"]["paired_derived_result_sha256"]
            self.assertGreaterEqual(len(derived), 2, name)
            self.assertEqual(
                len(set(derived)), 1,
                "{}: paired derived result hashes now DIFFER — decision-level "
                "reproducibility has broken, which is the load-bearing half of "
                "F110".format(name))

    def test_the_pairing_covers_FEWER_refreshes_than_were_observed(self):
        """The scope caveat. Stated so the artifact cannot be over-read as showing
        that every observed refresh produced the same decision."""
        for name, payload in _batches():
            audit = payload["refresh_audit"]
            inputs = len(audit["observed_exact_input_sha256"])
            paired = len(audit["paired_derived_result_sha256"])
            self.assertLess(
                paired, inputs,
                "{}: the derived pairing now covers every observed refresh, so the "
                "coverage caveat in F110's reading no longer applies — update the "
                "note".format(name))
            self.assertEqual(
                paired, 2,
                "{}: the pairing size changed from 2; re-read what was actually "
                "compared".format(name))


if __name__ == "__main__":
    unittest.main()

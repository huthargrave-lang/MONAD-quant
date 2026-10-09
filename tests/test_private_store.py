"""
The committed research data after option A (docs/research/DATA_REDISTRIBUTION_AUDIT.md):
no restricted vendor observations are committed, every restricted manifest records where
its private observations are, every sha a trial cites still has its committed manifest,
and, where the private store is present, every private data set loads through its normal
loader and every recorded (domain, data) pair loads through its domain.

The replay checks need the real private store, which CI does not have; they follow the one
rule in tests/_private_store.py (absent: skip with a reason; altered: fail; with
MONAD_REQUIRE_PRIVATE_STORE=1, absent: fail). The policy checks need only the committed
tree and always run.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

import data_inventory as inv  # noqa: E402

from src.research import bdc_data, cef_data, cef_etf_tilt, daily_data, data_store  # noqa: E402
from src.research import deletion_classes, earnings_data, futures_panel, insider_data  # noqa: E402
from src.research import spinoff_classes, trials  # noqa: E402
from tests import _private_store as ps  # noqa: E402

#: The normal loader for every prefix the committed store holds. A new prefix fails
#: test_every_prefix_has_a_loader until it is added here, so no data set escapes replay.
LOADERS = {
    "DS": lambda sha: daily_data.load_snapshot(sha).sha,
    "CEFNAV": lambda sha: cef_data.load_panel(sha).sha,
    "FUT": lambda sha: futures_panel.load(sha).sha,
    "BDCNAV": lambda sha: bdc_data.load_panel(sha).sha,
    "MREITBV": lambda sha: bdc_data.load_panel(sha, prefix="MREITBV").sha,
    "EARNDATES": lambda sha: earnings_data.load(sha).sha,
    "INSIDER": lambda sha: sha if len(insider_data.load(sha)) else None,
    "SPINEVENTS": lambda sha: spinoff_classes.load_events(sha).sha,
    "IDXDEL": lambda sha: deletion_classes.load_events(sha).sha,
    # Self-contained: the JSON is the data set. Its NAV panel is a CEFNAV data set of its own.
    "CEFETF": lambda sha: cef_etf_tilt.load_inputs(sha, panel_loader=lambda _panel: None).sha,
}


def _manifests():
    out = []
    for prefix, sha, path in inv._manifests(data_store.DATA_DIR):
        out.append((prefix, sha, json.loads(path.read_text(encoding="utf-8"))))
    return out


class CommittedTreePolicy(unittest.TestCase):
    """Runs everywhere, CI included: it reads only what is committed."""

    @classmethod
    def setUpClass(cls):
        cls.manifests = _manifests()

    def test_a_manifest_naming_a_restricted_vendor_records_private_observations(self):
        restricted = [(p, s, m) for p, s, m in self.manifests
                      if data_store.manifest_restricted_vendors(m)]
        self.assertTrue(restricted, "the committed store should hold restricted data sets")
        for prefix, sha, m in restricted:
            with self.subTest(data_set=f"{prefix}-{sha[:12]}"):
                self.assertEqual(data_store.private_record_problems(m, sha), [])
                self.assertFalse((data_store.DATA_DIR / data_store.observations_name(prefix, sha)).exists(),
                                 "restricted observations are committed")

    def test_the_inventory_reports_nothing_public_and_restricted(self):
        s = inv.summary(inv.inventory(records=[]))
        self.assertEqual(s["restricted_public_data_sets"], 0)
        self.assertEqual(s["private_but_committed"], 0)

    def test_every_public_data_set_keeps_its_committed_observations(self):
        for prefix, sha, m in self.manifests:
            if data_store.records_private(m):
                continue
            with self.subTest(data_set=f"{prefix}-{sha[:12]}"):
                self.assertIsNone(data_store.verify_committed(prefix, sha))

    def test_every_sha_a_trial_cites_has_its_committed_manifest(self):
        """The ledger names data by sha; a manifest must say what that sha is and, for a
        private one, where its bytes live. Needs no observations."""
        names = {sha for _p, sha, _m in self.manifests}
        for r in trials.iter_trials():
            d = (r.spec or {}).get("data") or {}
            for key in ("snapshot", "nav_panel"):
                if d.get(key):
                    self.assertIn(d[key], names, f"{r.key} cites {key} {d[key][:12]} with no manifest")

    def test_every_prefix_has_a_loader(self):
        self.assertLessEqual({p for p, _s, _m in self.manifests}, set(LOADERS))

    def test_every_self_contained_data_set_loads_through_its_loader(self):
        """Self-contained data sets are committed whole, so they replay everywhere."""
        for prefix, sha, _m in self.manifests:
            if data_store.is_self_contained(prefix):
                with self.subTest(data_set=f"{prefix}-{sha[:12]}"):
                    self.assertEqual(LOADERS[prefix](sha), sha)


class TheSkipRule(unittest.TestCase):
    """The rule itself: absent skips with a reason, altered fails, and the environment
    switch turns absence into a failure."""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.store = Path(self._td.name)
        self.data = b"date,symbol,close\n2020-01-02,CL=F,1.0\n"
        self.sha, self.path = data_store.write("FUT", self.data, private=False, data_dir=self.store)

    def tearDown(self):
        self._td.cleanup()

    def test_present_returns_the_verified_path(self):
        self.assertEqual(ps.require(self, "FUT", self.sha, store=self.store, env={}), self.path)

    def test_absent_skips_and_says_how_to_restore(self):
        with self.assertRaises(unittest.SkipTest) as err:
            ps.require(self, "FUT", "0" * 64, store=self.store, env={})
        self.assertIn("data_inventory.py import", str(err.exception))

    def test_absent_fails_when_the_store_is_required(self):
        with self.assertRaises(self.failureException):
            ps.require(self, "FUT", "0" * 64, store=self.store, env={ps.REQUIRE_ENV: "1"})

    def test_altered_fails_and_never_skips(self):
        import gzip
        self.path.write_bytes(gzip.compress(b"altered\n"))
        with self.assertRaises(self.failureException):
            ps.require(self, "FUT", self.sha, store=self.store, env={})


class Replay(unittest.TestCase):
    """Needs the private store (skips per data set without it, by the rule above)."""

    def test_every_private_data_set_loads_through_its_normal_loader(self):
        private = [(p, s) for p, s, m in _manifests() if data_store.records_private(m)]
        for prefix, sha in private:
            with self.subTest(data_set=f"{prefix}-{sha[:12]}"):
                ps.require(self, prefix, sha)
                self.assertEqual(LOADERS[prefix](sha), sha)

    def test_every_recorded_domain_and_data_pair_loads_through_its_domain(self):
        """What a trial actually ran on: its domain's own loader over its recorded data
        (snapshot and panel together, with each domain's load-time checks)."""
        from src.research.daily_domains import DOMAINS
        from src.research.daily_trials import DEFAULT_DOMAIN
        pairs = {}
        for r in trials.iter_trials():
            d = (r.spec or {}).get("data") or {}
            p = (r.spec or {}).get("params")
            if not d.get("snapshot") or not isinstance(p, dict) or "class" not in p:
                continue
            dom = p.get("domain", DEFAULT_DOMAIN)
            pairs[(dom, d["snapshot"], d.get("nav_panel"))] = d
        self.assertTrue(pairs)
        panel_prefix = {name: DOMAINS[name].panel_prefix for name in DOMAINS}
        for (dom, snap, panel), data in sorted(pairs.items(), key=lambda kv: (kv[0][0], kv[0][1])):
            with self.subTest(domain=dom, snapshot=snap[:12]):
                self.assertIn(dom, DOMAINS)
                for prefix, sha in (("DS", snap), (panel_prefix.get(dom), panel)):
                    if sha and data_store.records_private(data_store.read_manifest(prefix, sha)):
                        ps.require(self, prefix, sha)
                ctx = DOMAINS[dom].load(data)
                self.assertEqual(ctx.snap.sha, snap)


if __name__ == "__main__":
    unittest.main()

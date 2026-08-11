"""The scenario layer refuses what it cannot honestly represent.

`tools/scenarios.py` exists to make one specific failure unrepresentable: an author who knows
FRO benefits from a Hormuz closure writing that down directly, giving the system a
shock -> ticker map in the vocabulary of a causal model, after which every number downstream
looks derived and is asserted.

So most of this file is malformations. Each test builds a record that a careless author might
plausibly write, and asserts the module refuses it — because a validator is only worth the
inputs it rejects, and one that has never been shown a bad input is a comment.

Scenario records are constructed inline rather than read from `data/scenarios/`. That keeps
these tests true of the SCHEMA rather than of whatever fixture happens to be on disk, and it
means they do not go red the day a fixture is edited for an unrelated reason.
"""
import copy
import json
import os
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (REPO, os.path.join(REPO, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import scenarios as sn  # noqa: E402
import sovereign_buckets as sb  # noqa: E402
import stock_screener as sc  # noqa: E402


def _prov(**kw):
    base = {"basis": "fixture",
            "method": "illustrative — not calibrated against history or any model",
            "as_of": "2026-08-10T00:00:00Z",
            "provenance": ["tests/test_scenarios.py"]}
    base.update(kw)
    return base


def _scenario(**kw):
    base = dict(_prov(), id="hormuz", label="Strait of Hormuz",
                shock_id="hormuz", description="Transit disruption in the Strait of Hormuz.")
    base.update(kw)
    return base


def _branches(*probs, horizon="30d"):
    return [dict(_prov(), id="b{}".format(i), label="state {}".format(i),
                 probability=p, horizon=horizon)
            for i, p in enumerate(probs)]


def _with_branches(*probs, **kw):
    """A scenario carrying branches, and therefore a partition — the two travel together, so
    a helper that produced one without the other would make every branch test fail on the
    partition check before reaching what it meant to assert."""
    horizon = kw.pop("horizon", "30d")
    return _scenario(branches=_branches(*probs, horizon=horizon),
                     partition="illustrative bands on one measured quantity", **kw)


def _observation(**kw):
    base = dict(_prov(), target_id="hormuz_material_disruption",
                timestamp="2026-08-01T00:00:00Z", horizon="30d", probability=0.2)
    base.update(kw)
    return base


class TheShortcutIsUnrepresentable(unittest.TestCase):
    """The invariants that make a shock -> ticker map impossible to write, rather than merely
    discouraged. Each is checked by the thing it forbids."""

    def _bad(self, record, fragment):
        with self.assertRaises(ValueError) as cm:
            sn._validate_scenario(record["id"], record)
        self.assertIn(fragment, str(cm.exception))

    def test_a_scenario_cannot_name_a_security(self):
        """Invariant 4. The schema has nowhere to put a ticker, and the fields an author would
        reach for are refused by name so the failure says why rather than 'unknown key'."""
        for field in ("securities", "tickers", "ticker_impacts", "sensitivities", "exposures"):
            self._bad(_scenario(**{field: ["FRO"]}), "may not name a security")

    def test_a_record_missing_a_required_field_is_refused(self):
        """The other half of a closed schema, and the half nothing tested until a mutation
        removed the check and every test still passed. Rejecting unknown keys is worthless if
        a record can simply omit the ones that carry its meaning — a scenario with no
        `shock_id` reaches nothing, and a branch with no `probability` is not a branch."""
        for field in ("id", "label", "shock_id", "description"):
            record = _scenario()
            del record[field]
            with self.assertRaises(ValueError, msg="a scenario without {} was accepted".format(
                    field)) as cm:
                sn._validate_scenario("hormuz", record)
            self.assertIn("missing", str(cm.exception))
        for field in ("id", "label", "probability", "horizon"):
            branch = _branches(1.0)[0]
            del branch[field]
            with self.assertRaises(ValueError, msg="a branch without {} was accepted".format(
                    field)):
                sn._validate_scenario("hormuz", _scenario(branches=[branch]))
        for field in ("target_id", "timestamp", "horizon", "probability"):
            obs = _observation()
            del obs[field]
            with self.assertRaises(ValueError,
                                   msg="an observation without {} was accepted".format(field)):
                sn._validate_scenario("hormuz", _scenario(observations=[obs]))
        for field in ("magnitude", "sign"):
            saved = dict(sn.CHANNEL_SENSITIVITIES)
            try:
                rec = dict(_prov(), magnitude=0.5, sign=1)
                del rec[field]
                sn.CHANNEL_SENSITIVITIES[("FRO", "crude_freight_rate_ws")] = rec
                with self.assertRaises(
                        ValueError,
                        msg="a sensitivity without {} was accepted".format(field)):
                    sn._validate_sensitivities()
            finally:
                sn.CHANNEL_SENSITIVITIES.clear()
                sn.CHANNEL_SENSITIVITIES.update(saved)

    def test_a_scenario_schema_is_closed(self):
        """Invariant 7. An unknown key is a typo or a field smuggled in from another layer;
        ignoring it is how a scenario acquires data nothing validates."""
        self._bad(_scenario(exposure_table={"FRO": 0.8}), "unknown key")

    def test_a_sensitivity_cannot_name_a_scenario(self):
        """Invariant 3. A sensitivity is a relationship between a security and a QUANTITY. The
        moment it knows which scenario it is for, it is the shortcut with more steps."""
        for banned in ("shock_id", "scenario_id", "shock", "scenario"):
            saved = dict(sn.CHANNEL_SENSITIVITIES)
            try:
                sn.CHANNEL_SENSITIVITIES[("FRO", "crude_freight_rate_ws")] = dict(
                    _prov(), magnitude=0.8, sign=1, **{banned: "hormuz"})
                with self.assertRaises(ValueError) as cm:
                    sn._validate_sensitivities()
                self.assertIn("is a shortcut", str(cm.exception))
            finally:
                sn.CHANNEL_SENSITIVITIES.clear()
                sn.CHANNEL_SENSITIVITIES.update(saved)

    def test_a_channel_cannot_be_named_after_a_shock(self):
        """Invariant 6, and the hole the other six leave open on their own.

        `hormuz_closure` satisfies every structural rule — it lives in the registry outside
        `data/scenarios/`, sensitivities keyed to it carry no scenario field, the join is by
        channel_id — and it is a shock -> ticker map with an alias. A channel must name a
        measurable quantity, not an event."""
        for bad_id in ("hormuz", "hormuz_closure", "disruption_hormuz", "taiwan_blockade"):
            saved = dict(sn.CHANNELS)
            try:
                sn.CHANNELS[bad_id] = {"label": "x", "unit": "y", "sign": "z"}
                with self.assertRaises(ValueError) as cm:
                    sn._validate_channels()
                self.assertIn("named after the shock", str(cm.exception))
            finally:
                sn.CHANNELS.clear()
                sn.CHANNELS.update(saved)

    def test_a_channel_must_declare_a_unit_and_a_sign_convention(self):
        """Without them a "channel" is a label, and a sensitivity to a label is uninterpretable
        — the reader cannot tell which way +0.8 points or what it is 0.8 of."""
        for missing in ("label", "unit", "sign"):
            entry = {"label": "Crude", "unit": "USD/bbl", "sign": "positive = up"}
            entry[missing] = ""
            saved = dict(sn.CHANNELS)
            try:
                sn.CHANNELS["probe_quantity"] = entry
                with self.assertRaises(ValueError) as cm:
                    sn._validate_channels()
                self.assertIn("observable quantity", str(cm.exception))
            finally:
                sn.CHANNELS.clear()
                sn.CHANNELS.update(saved)

    def test_a_sensitivity_must_reach_a_real_channel_and_a_reachable_security(self):
        cases = [
            (("FRO", "no_such_channel"), "unknown channel_id"),
            (("NOSUCHTICKER", "crude_freight_rate_ws"), "is in no bucket"),
        ]
        for key, fragment in cases:
            saved = dict(sn.CHANNEL_SENSITIVITIES)
            try:
                sn.CHANNEL_SENSITIVITIES[key] = dict(_prov(), magnitude=0.5, sign=1)
                with self.assertRaises(ValueError) as cm:
                    sn._validate_sensitivities()
                self.assertIn(fragment, str(cm.exception))
            finally:
                sn.CHANNEL_SENSITIVITIES.clear()
                sn.CHANNEL_SENSITIVITIES.update(saved)

    def test_direction_lives_in_sign_not_in_a_negative_magnitude(self):
        """"How much" and "which way" are separate claims with separate evidence. A signed
        magnitude collapses them, and then a magnitude of -0.0 means nothing at all."""
        saved = dict(sn.CHANNEL_SENSITIVITIES)
        try:
            sn.CHANNEL_SENSITIVITIES[("STNG", "crude_freight_rate_ws")] = dict(
                _prov(), magnitude=-0.6, sign=-1)
            with self.assertRaises(ValueError) as cm:
                sn._validate_sensitivities()
            self.assertIn("Direction belongs in `sign`", str(cm.exception))
        finally:
            sn.CHANNEL_SENSITIVITIES.clear()
            sn.CHANNEL_SENSITIVITIES.update(saved)


class EveryNumberSaysWhereItCameFrom(unittest.TestCase):
    def _bad(self, record, fragment):
        with self.assertRaises(ValueError) as cm:
            sn._validate_scenario(record["id"], record)
        self.assertIn(fragment, str(cm.exception))

    def test_basis_is_required_and_closed(self):
        self._bad(_scenario(basis="probably"), "is not one of")

    def test_a_modelled_record_must_name_its_model(self):
        """"A model said so" is not provenance unless the model is named — otherwise a
        fixture relabelled `modelled` is indistinguishable from a forecast."""
        self._bad(_scenario(basis="modelled", model_id=None), "unless the model is named")

    def test_a_method_is_required(self):
        self._bad(_scenario(method="  "), "no method")

    def test_provenance_must_be_a_non_empty_list(self):
        for value in (None, [], "a paper"):
            self._bad(_scenario(provenance=value), "non-empty list")

    def test_confidence_is_bounded_and_absence_is_allowed(self):
        self._bad(_scenario(confidence=1.4), "outside 0..1")
        # None is a real state — "not assessed" — and must not be refused.
        sn._validate_scenario("hormuz", _scenario(confidence=None))


class ProbabilitiesMeanSomethingSpecific(unittest.TestCase):
    def _bad(self, record, fragment):
        with self.assertRaises(ValueError) as cm:
            sn._validate_scenario(record["id"], record)
        self.assertIn(fragment, str(cm.exception))

    def test_branches_are_an_exhaustive_partition(self):
        """A leftover is a state nobody described, and an expected value over a partial tree
        is not an expected value."""
        self._bad(_with_branches(0.5, 0.2), "sum to")
        self._bad(_with_branches(0.6, 0.6), "sum to")
        sn._validate_scenario("hormuz", _with_branches(0.6, 0.25, 0.15))

    def test_branches_require_a_partition(self):
        """Probabilities summing to 1 prove nothing about whether two states overlap. Naming
        the one dimension they divide is what makes disjointness a claim a person can check —
        and until a mutation disabled the requirement, nothing asserted it, because every
        helper in this file supplied one."""
        record = _scenario(branches=_branches(0.6, 0.4))
        record.pop("partition", None)
        self._bad(record, "no `partition`")
        blank = _with_branches(0.6, 0.4)
        blank["partition"] = "   "
        self._bad(blank, "no `partition`")

    def test_the_branch_tree_and_the_observation_series_must_agree(self):
        """A scenario states a target's probability twice — as a slice of the tree and as the
        newest point of the series. They are the second and third places a probability lives
        (state is derived, so it cannot disagree), and a tree reading 10% under a strip
        reading 30% is this repo's oldest failure arriving in its newest layer.

        Not covered by asserting the real fixture is consistent: that passes whether or not
        anything enforces it."""
        counting = _branches(0.7, 0.2, 0.08, 0.02)
        for b in counting[1:]:
            b["counts_toward"] = ["hormuz_material_disruption"]
        # The partition must state the target's threshold_pct and min_days, because these
        # branches count toward it — so a generic partition string is correctly refused.
        good = _scenario(branches=counting,
                         partition="bands on one measured quantity: at least 5% sustained "
                                   "for 7 days",
                         observations=[_observation(probability=0.30)])
        sn._validate_scenario("hormuz", good)          # 0.20 + 0.08 + 0.02 == 0.30

        bad = copy.deepcopy(good)
        bad["observations"][0]["probability"] = 0.45
        self._bad(bad, "publish two answers")

    def test_branch_ids_are_unique(self):
        """Two branches with one id are two states the tree cannot tell apart, and any later
        per-branch record — a conditional impact, an expected value — silently attaches to
        whichever was read last."""
        record = _with_branches(0.5, 0.5)
        record["branches"][1]["id"] = record["branches"][0]["id"]
        self._bad(record, "duplicate branch id")

    def test_branches_share_one_horizon(self):
        record = _with_branches(0.5, 0.5)
        record["branches"][1]["horizon"] = "90d"
        self._bad(record, "span horizons")

    def test_a_probability_is_of_a_registered_target(self):
        """As free text, "Hormuz closure" and "Strait of Hormuz closed" are one series or two
        depending on spelling."""
        self._bad(_scenario(observations=[_observation(target_id="hormuz closure")]),
                  "unknown target_id")

    def test_a_series_may_not_mix_fixture_and_modelled_points(self):
        """A surface marks a whole chart. A series that is mostly modelled with one
        illustrative point has no honest marking."""
        mixed = [_observation(timestamp="2026-08-01T00:00:00Z"),
                 _observation(timestamp="2026-08-02T00:00:00Z",
                              basis="modelled", model_id="m", model_version="1")]
        self._bad(_scenario(observations=mixed), "mixes bases")

    def test_the_observation_key_makes_newest_well_defined(self):
        dup = [_observation(), _observation()]
        self._bad(_scenario(observations=dup), "duplicate observation")

    def test_probabilities_are_bounded(self):
        self._bad(_scenario(observations=[_observation(probability=1.2)]), "outside 0..1")
        self._bad(_with_branches(1.4, -0.4), "outside 0..1")


class TheStateIsDerivedFromTheSeries(unittest.TestCase):
    """One number, one source. Authoring a current probability beside a history is how the
    strip and the chart end up disagreeing — the failure `sovereign_buckets` records as "the
    same number, two answers, both published"."""

    def test_the_state_is_the_newest_point(self):
        s = _scenario(observations=[
            _observation(timestamp="2026-08-01T00:00:00Z", probability=0.20),
            _observation(timestamp="2026-08-09T00:00:00Z", probability=0.37),
            _observation(timestamp="2026-08-05T00:00:00Z", probability=0.29),
        ])
        state = sn.scenario_state(s)
        self.assertEqual(state["probability"], 0.37)
        self.assertEqual(state["as_of"], "2026-08-09T00:00:00Z")
        self.assertEqual(state["basis"], "fixture")

    def test_a_scenario_with_no_observations_has_no_state(self):
        """`None`, not 0.0. "We have not modelled this" and "the probability is nil" are
        different claims and the second one is a forecast."""
        self.assertIsNone(sn.scenario_state(_scenario()))
        self.assertIsNone(sn.newest_observation(_scenario()))

    def test_the_state_is_selected_per_target_and_horizon(self):
        s = _scenario(observations=[
            _observation(horizon="30d", probability=0.37,
                         timestamp="2026-08-09T00:00:00Z"),
            _observation(horizon="90d", probability=0.55,
                         timestamp="2026-08-09T00:00:00Z"),
        ])
        self.assertEqual(sn.scenario_state(s, horizon="30d")["probability"], 0.37)
        self.assertEqual(sn.scenario_state(s, horizon="90d")["probability"], 0.55)


class AbsenceIsNotZero(unittest.TestCase):
    def test_an_unassessed_sensitivity_is_none(self):
        """Reachable with no coefficient on record is *unassessed*, and is reported as such —
        the pattern the shadow-debt gate already uses rather than scoring 0 and clearing."""
        # COP is in bucket 02 and reachable; nobody has assessed it. That is the state
        # this asserts — not "the table is empty", which was true only before Phase B and
        # would have made this test pass for the wrong reason ever after.
        self.assertIsNotNone(sn.sensitivity("FRO", "crude_freight_rate_ws"),
                             "FRO is assessed; this test needs an UNassessed probe")
        self.assertIsNone(sn.sensitivity("COP", "crude_price_usd_bbl"))
        self.assertIsNone(sn.sensitivity("NOSUCHTICKER", "crude_price_usd_bbl"))
        self.assertEqual(sn.channels_for("COP"), [])


class TheLoaderIsARealSeam(unittest.TestCase):
    """Replacing a fixture with a model's output is writing a file, and no consumer changes."""

    def test_it_reads_a_directory_of_scenarios(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "hormuz.json"), "w", encoding="utf-8") as fh:
                json.dump(_scenario(), fh)
            loaded = sn.load(d)
            self.assertEqual(sorted(loaded), ["hormuz"])
            sn.validate_scenarios(loaded)

    def test_underscore_files_are_notes_not_scenarios(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "_README.json"), "w", encoding="utf-8") as fh:
                json.dump({"note": "not a scenario"}, fh)
            self.assertEqual(sn.load(d), {})

    def test_a_scenario_with_no_id_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "x.json"), "w", encoding="utf-8") as fh:
                json.dump({"label": "no id"}, fh)
            with self.assertRaises(ValueError):
                sn.load(d)

    def test_an_empty_directory_is_not_an_error(self):
        """Scenario files are AUTHORED and tracked, unlike the fetched snapshots. An empty
        directory means none is written yet, which is a state, not a failure."""
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(sn.load(d), {})

    def test_the_scenario_directory_is_tracked_not_gitignored(self):
        """The fetched snapshots are gitignored and absent on a runner. Scenario data must not
        be, or the layer that reads it is untestable in CI for the same reason."""
        import subprocess
        probe = os.path.join(sn.SCENARIO_DIR, "_gitignore_probe.json")
        os.makedirs(sn.SCENARIO_DIR, exist_ok=True)
        with open(probe, "w", encoding="utf-8") as fh:
            fh.write("{}")
        try:
            r = subprocess.run(["git", "check-ignore", probe], cwd=REPO,
                               capture_output=True, text=True)
            self.assertNotEqual(
                r.returncode, 0,
                "data/scenarios is gitignored, so scenario data would be absent in CI")
        finally:
            os.remove(probe)


class TheVocabulariesAreCoherent(unittest.TestCase):
    def test_every_shock_a_scenario_names_is_a_real_shock(self):
        with self.assertRaises(ValueError) as cm:
            sn._validate_scenario("hormuz", _scenario(shock_id="not_a_shock"))
        self.assertIn("unknown shock_id", str(cm.exception))

    def test_the_shock_vocabulary_is_the_ledger_s_own(self):
        """Not a second list. A scenario's shock_id is checked against
        sovereign_buckets.SHOCK_HINTS, which is where the shock menu, the heat table and the
        hints are already reconciled."""
        for shock in sb.SHOCK_HINTS:
            sn._validate_scenario("s", _scenario(id="s", shock_id=shock))

    def test_the_registries_validate_at_import(self):
        """`validate_scenarios()` runs at module import, like validate_presets, so a malformed
        registry fails when anything imports this rather than at the surface that draws it."""
        with open(os.path.join(REPO, "tools", "scenarios.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertRegex(src, r"(?m)^validate_scenarios\(\)$",
                         "validation does not run at import")

    def test_editorial_heat_is_untouched(self):
        """This module is the modelled sibling of editorial heat, not a replacement. Nothing
        here may read or write the heat table."""
        with open(os.path.join(REPO, "tools", "scenarios.py"), encoding="utf-8") as fh:
            src = fh.read()
        for token in ("bucket_heat", "heat_table", "HEAT_MAX", "CLOCK_LEADS"):
            self.assertNotIn(
                token, src.replace("bucket_heat`", "").replace("`bucket_heat", ""),
                "scenarios.py touches {} — editorial heat and modelled activation are two "
                "records and this module owns only the second".format(token))


class TheRegistryCarriesNothingUnusable(unittest.TestCase):
    """A vocabulary may legitimately have terms no scenario has used yet. It may not have
    terms that no scenario COULD use — that is the `adx_kelly_mult` shape, a declaration with
    no reachable consumer, and this repo has paid for it twice."""

    def test_every_channel_has_at_least_one_security_that_could_reach_it(self):
        """`_validate_sensitivities` refuses a coefficient on a security that is in no bucket,
        so a channel whose only plausible securities are outside the ledger can never be
        authored against. It would sit in the registry forever, looking like capability.

        The concrete case this was written from: a `jet_fuel_usd_gal` channel is the natural
        way to say "airlines are hurt by a Hormuz disruption", and the Sovereign Ledger holds
        no airline at all — no DAL, UAL, AAL, LUV, ALK or JBLU in any bucket. Expressing that
        leg needs bucket membership to change first, which is a ledger decision."""
        universe = set(sb.all_tickers())
        self.assertEqual(
            sorted(t for t in ("DAL", "UAL", "AAL", "LUV", "ALK", "JBLU") if t in universe),
            [],
            "an airline has entered the ledger — a jet-fuel channel is now authorable, and "
            "the comment in scenarios.CHANNELS explaining its absence is stale")
        self.assertNotIn(
            "jet_fuel_usd_gal", sn.CHANNELS,
            "a jet-fuel channel is registered but no airline is in any bucket, so no "
            "sensitivity to it can pass validation")

    def test_the_channels_that_are_registered_are_reachable(self):
        """Each remaining channel names a quantity that securities IN the ledger respond to —
        tankers and refiners are all present — so a Phase B fixture can author against every
        one of them."""
        universe = set(sb.all_tickers())
        for probe in ("FRO", "STNG", "VLO", "XOM"):
            self.assertIn(probe, universe,
                          "{} left the ledger; the registered channels assume oil, refining "
                          "and tanker names are reachable".format(probe))
        self.assertEqual(len(sn.CHANNELS), 4)


class TheHormuzFixtureIsHonestAboutItself(unittest.TestCase):
    """The fixture on disk, checked as data rather than as prose.

    It exists so the strip, the drawer and the bay modules have a shaped, self-consistent
    scenario to render while the modelling that would replace it is done. The danger is not
    that it is wrong — it is illustrative and says so — but that it stops LOOKING illustrative
    once a surface draws it. These assert the properties a reader would need in order to tell.
    """

    @classmethod
    def setUpClass(cls):
        cls.all = sn.load()
        cls.s = cls.all["hormuz"]

    def _every_record(self):
        """EVERY scenario on disk, not just Hormuz.

        This iterated `self.s` alone, so the honesty assertions covered exactly one file —
        and `load()` is documented as a real seam whose whole point is that another scenario
        can be dropped in. A second file would have inherited every guarantee in the module
        docstring and none of the checks that make them true."""
        for sid, rec in sorted(self.all.items()):
            yield "scenario " + sid, rec
            for kind in ("branches", "observations", "developments"):
                for r in rec.get(kind) or []:
                    yield "{} {}".format(sid, kind[:-1]), r

    def test_every_record_is_marked_fixture(self):
        """Not the file, not a header — every record. A surface renders one branch or one
        point at a time, and a marking that lives only at the top is one the reader never
        sees beside the number."""
        for kind, r in self._every_record():
            self.assertEqual(r.get("basis"), "fixture",
                             "{} {} is not marked fixture".format(kind, r.get("id", "")))

    def test_every_method_says_it_is_not_calibrated(self):
        """`basis: fixture` is a machine word. `method` is the sentence a person reads, and it
        has to say the thing outright rather than implying it."""
        for kind, r in self._every_record():
            method = (r.get("method") or "").lower()
            self.assertTrue(
                "illustrative" in method,
                "{} {}: method does not call itself illustrative".format(kind, r.get("id", "")))

    def test_no_record_claims_a_model(self):
        for kind, r in self._every_record():
            self.assertIsNone(r.get("model_id"),
                              "{} {} names a model".format(kind, r.get("id", "")))
            self.assertIsNone(r.get("model_version"))

    def test_the_scenario_confidence_is_absent_rather_than_invented(self):
        """A confidence on an uncalibrated scenario would be a number about a number, and the
        outer one has no more basis than the inner. None is the honest reading."""
        self.assertIsNone(self.s.get("confidence"))

    def test_the_bands_are_numeric_half_open_intervals(self):
        """The first draft read "no material shortfall" / "limited — under a fifth", and a 1%
        shortfall satisfies both. Overlapping English sums to 1 while double-counting, which
        is exactly the flaw the partition field exists to expose. Every boundary is a number
        now, and the labels carry them so a reader sees the band and not just its name."""
        labels = {b["id"]: b["label"] for b in self.s["branches"]}
        self.assertRegex(labels["none"], r"under 5%")
        self.assertRegex(labels["limited"], r"5% to 20%")
        self.assertRegex(labels["sustained"], r"20% to 50%")
        self.assertRegex(labels["severe"], r"50% or more")
        self.assertRegex(self.s["partition"], r"\[0,5\).*\[5,20\).*\[20,50\).*\[50,100\]")

    def test_material_means_one_thing(self):
        """The target and the scenario both define "material", and the definition is now
        STRUCTURED so the coupling is enforced rather than promised.

        The first version of this test was a substring scan for "5%" anywhere in the
        partition — it passed on a partition whose bands started at 10%, and it contained
        `token.replace("seven consecutive days", "seven consecutive days")`, a no-op shaped
        like a vocabulary translation that was never written. The fixture meanwhile claimed of
        itself that the two numbers "cannot drift", which nothing checked and which was false.
        Both numbers are fields on the target now, `_validate_partition_matches_targets`
        enforces that a scenario states them, and this asserts the fields exist to enforce."""
        target = sn.TARGETS["hormuz_material_disruption"]
        self.assertEqual(target["threshold_pct"], 5)
        self.assertEqual(target["min_days"], 7)
        for field in ("threshold_pct", "min_days"):
            self.assertIn(str(target[field]), target["question"],
                          "the question and the checkable field state different thresholds")
            self.assertIn(str(target[field]), self.s["partition"],
                          "the partition does not state the target's {}".format(field))

    def test_the_tree_and_the_series_agree(self):
        """Enforced by the validator; asserted here on the real fixture so the fixture itself
        is known to satisfy it rather than merely being permitted to."""
        counting = [b for b in self.s["branches"]
                    if "hormuz_material_disruption" in b["counts_toward"]]
        self.assertEqual(sorted(b["id"] for b in counting),
                         ["limited", "severe", "sustained"])
        self.assertAlmostEqual(sum(b["probability"] for b in counting),
                               sn.scenario_state(self.s)["probability"], places=9)

    def test_no_development_carries_a_probability_contribution(self):
        """Attributing +4.1pp to one event is a modelling claim and no model here makes it.
        The schema has no field for it; this asserts the fixture did not find another way."""
        for d in self.s["developments"]:
            for key in d:
                self.assertNotIn(key, ("contribution", "impact", "delta", "pp", "points"),
                                 "development {} attributes a probability change".format(
                                     d["id"]))

    def test_a_direction_the_fixture_will_not_call_is_recorded_as_unclear(self):
        """`unclear` is a reading, not a gap — and a fixture with no unclear development would
        quietly suggest every event has a legible sign."""
        self.assertIn("unclear", [d["direction"] for d in self.s["developments"]])

    def test_a_sensitivity_with_no_number_is_none_not_zero(self):
        """XOM and CVX have a stated sign and no magnitude: the relationship exists and this
        table declines to invent an elasticity for it. That has to survive as None."""
        for tk in ("XOM", "CVX"):
            rec = sn.sensitivity(tk, "crude_price_usd_bbl")
            self.assertIsNotNone(rec)
            self.assertIsNone(rec["magnitude"], "{} was given an invented magnitude".format(tk))
            self.assertEqual(rec["sign"], 1)

    def test_one_security_can_face_two_channels_in_opposite_directions(self):
        """The reason sign lives per (security, channel) and never per security: a crude spike
        squeezes a refiner's input cost while a widening crack helps it. A per-security sign
        cannot express that, and would have to pick one and be wrong half the time."""
        self.assertEqual(sn.sensitivity("VLO", "crude_price_usd_bbl")["sign"], -1)
        self.assertEqual(sn.sensitivity("VLO", "refining_crack_usd_bbl")["sign"], 1)
        self.assertEqual(sn.sensitivity("MPC", "crude_price_usd_bbl")["sign"], -1)
        self.assertEqual(sn.sensitivity("MPC", "refining_crack_usd_bbl")["sign"], 1)

    def test_every_sensitivity_is_marked_fixture(self):
        for key, rec in sn.CHANNEL_SENSITIVITIES.items():
            self.assertEqual(rec["basis"], "fixture", "{} is not marked fixture".format(key))
            self.assertIn("illustrative", rec["method"].lower())


class TheGuardsTheReviewFound(unittest.TestCase):
    """Five defects an adversarial pass reproduced by execution rather than argued.

    Each was accepted by `validate_scenarios` at the time it was found, and each is the same
    shape: a property the module states about itself that nothing enforced."""

    def _bad(self, record, fragment):
        with self.assertRaises(ValueError) as cm:
            sn._validate_scenario(record["id"], record)
        self.assertIn(fragment, str(cm.exception))

    def test_a_horizon_is_registry_closed(self):
        """`horizon` is half the observation primary key AND the join key the tree/series
        agreement check runs on. As free text, rewriting `30d` to `30D` did not fail — it made
        the coherence check silently not run, after which the tree could read 30% while the
        series read 90%, both marked fixture and both "validated". `30 d`, `1m`, `P30D`,
        `thirty days` and `""` all validated too."""
        for bad in ("30D", "30 d", "1m", "P30D", "thirty days", ""):
            self._bad(_scenario(observations=[_observation(horizon=bad)]), "unknown horizon")
            self._bad(_with_branches(1.0, horizon=bad), "unknown horizon")

    def test_the_coherence_check_cannot_be_dodged_by_respelling_a_horizon(self):
        """The exploit, end to end: a tree and a series that disagree, hidden behind a
        horizon spelling. It must fail on the horizon rather than pass."""
        counting = _branches(0.7, 0.3)
        counting[1]["counts_toward"] = ["hormuz_material_disruption"]
        record = _scenario(branches=counting,
                           partition="bands: at least 5% sustained for 7 days",
                           observations=[_observation(horizon="30D", probability=0.90)])
        self._bad(record, "unknown horizon")

    def test_a_branch_cannot_count_toward_a_target_that_does_not_exist(self):
        """`counts_toward` was admitted as a key and its VALUES were never checked, so a
        branch could count toward a typo and the coherence check would skip it in silence."""
        counting = _branches(1.0)
        counting[0]["counts_toward"] = ["hormuz_matrial_disruption"]
        self._bad(_scenario(branches=counting, partition="bands: 5% over 7 days"),
                  "unknown target")

    def test_a_partition_must_state_the_numbers_its_target_defines(self):
        """The fixture claimed of itself that its band edge and the target's threshold were
        "the same number ... so the two cannot drift". Nothing read the partition prose, so
        moving the bands while the target stood still validated cleanly, leaving a probability
        answering a question nobody asked."""
        counting = _branches(1.0)
        counting[0]["counts_toward"] = ["hormuz_material_disruption"]
        self._bad(_scenario(branches=counting,
                            partition="bands on one quantity, edges at 25% and 40%"),
                  "the partition never states that number")

    def test_a_fixture_cannot_describe_itself_as_calibrated(self):
        """`basis: "fixture"` with method "Illustrative shape, calibrated against 20 years of
        AIS transit data and validated out of sample" was ACCEPTED. That sentence is the one
        thing that would make a reader trust an authored number."""
        for claim in ("calibrated against 20 years of AIS data",
                      "backtested out of sample",
                      "estimated from returns",
                      "fitted by regression"):
            self._bad(_scenario(method="Illustrative shape, " + claim), "claims")

    def test_an_honest_denial_of_calibration_is_not_mistaken_for_a_claim(self):
        """The other direction, and the one the first version of the check got wrong: it
        refused the fixture's own method, which reads "None of it is calibrated against
        history". Matching the word instead of the claim rejects exactly the text this check
        exists to encourage — the same reason the buckets guard matches `function mulberry32(`
        rather than the bare name."""
        for honest in ("Illustrative. None of it is calibrated against history.",
                       "Illustrative, not calibrated, not a MONAD estimate.",
                       "Illustrative — never backtested.",
                       "Illustrative; no regression was fitted."):
            sn._validate_scenario("hormuz", _scenario(method=honest))
            self.assertIsNone(sn._calibration_claim(honest.lower()))

    def test_a_fixture_method_must_say_it_is_illustrative(self):
        self._bad(_scenario(method="Authored for the scenario layer."), "never says so")

    def test_a_target_states_its_threshold_as_a_checkable_field(self):
        """Prose alone cannot be compared to a partition. The threshold and the duration are
        fields, and the question must state the same numbers or the target says two things."""
        saved = dict(sn.TARGETS["hormuz_material_disruption"])
        try:
            sn.TARGETS["hormuz_material_disruption"]["threshold_pct"] = 25
            with self.assertRaises(ValueError) as cm:
                sn._validate_targets()
            self.assertIn("does not appear in its own question", str(cm.exception))
        finally:
            sn.TARGETS["hormuz_material_disruption"] = saved


def _edge(**kw):
    base = dict(_prov(), channel_id="crude_freight_rate_ws", bucket_id="04", sign=1,
                strength="high", horizon="30d", branches=["limited"],
                mechanism="Longer voyages tighten effective fleet supply.")
    base.update(kw)
    return base


class ATransmissionEdgeIsCheckable(unittest.TestCase):
    """An edge names a CHANNEL and a BUCKET — never a security. That is invariant 4 holding at
    the one place it is most tempting to break, because the author writing "this reaches
    tankers" knows exactly which tankers they mean."""

    def _bad(self, edges, fragment, branches=None):
        record = _scenario(
            transmission=edges,
            branches=branches or _branches(0.6, 0.4),
            partition="bands: at least 5% sustained for 7 days")
        record["branches"][0]["id"] = "limited"
        record["branches"][1]["id"] = "other"
        with self.assertRaises(ValueError) as cm:
            sn._validate_scenario("hormuz", record)
        self.assertIn(fragment, str(cm.exception))

    def test_an_edge_cannot_name_an_unknown_channel_or_bucket(self):
        self._bad([_edge(channel_id="nope")], "unknown channel_id")
        self._bad([_edge(bucket_id="99")], "unknown bucket_id")

    def test_an_edge_must_assert_a_direction(self):
        """Unlike a sensitivity, where `None` is a real state — the relationship exists and
        nobody has called its direction — an edge with no sign is not a mechanism."""
        self._bad([_edge(sign=None)], "not a mechanism")
        self._bad([_edge(sign=0)], "not a mechanism")

    def test_strength_is_ordinal_and_closed(self):
        """A 0-1 coefficient would be multiplied by a probability within a week, producing a
        number with no unit that looks like an expected value. `SHADOW_DEBT_SEVERITY` is
        ordinal for the same reason."""
        self._bad([_edge(strength=0.9)], "not one of")
        self._bad([_edge(strength="extreme")], "not one of")

    def test_an_edge_must_carry_its_mechanism(self):
        """This is the hop where the causal claim lives. A path the reader cannot read is not
        an explanation, which is the entire point of storing paths."""
        self._bad([_edge(mechanism="   ")], "no mechanism")

    def test_an_edge_must_be_engaged_by_real_branches(self):
        self._bad([_edge(branches=[])], "engages no branches")
        self._bad([_edge(branches=["nosuchbranch"])], "unknown branch")

    def test_one_channel_cannot_move_one_bucket_both_ways(self):
        self._bad([_edge(sign=1), _edge(sign=-1)], "opposite signs")

    def test_two_channels_into_one_bucket_are_legal(self):
        """The multi-channel case the registry exists for — and the earlier draft of this rule
        wrongly refused it."""
        record = _scenario(
            transmission=[_edge(channel_id="crude_freight_rate_ws"),
                          _edge(channel_id="marine_war_risk_premium_pct", sign=-1)],
            branches=_branches(1.0), partition="bands: at least 5% sustained for 7 days")
        record["branches"][0]["id"] = "limited"
        sn._validate_scenario("hormuz", record)


class TheChainIsStoredNotRecomputed(unittest.TestCase):
    """Phase C's contract: a surface answers "why did this security move into this scenario
    set" by READING what it was handed.

    Recomputing in the UI would be a second implementation of the join — the defect this repo
    has paid for repeatedly. Narrating it would be an explanation free to disagree with the
    arithmetic it claims to describe."""

    @classmethod
    def setUpClass(cls):
        cls.s = sn.load()["hormuz"]
        cls.ex = sn.security_exposures(cls.s)

    def test_activation_is_a_probability_and_touches_no_company(self):
        """Decision 5: activation is mechanism-level. It returns bucket ids, never tickers,
        and its value is P(the mechanism is engaged) — a quantity a reader can check — rather
        than a score."""
        acts = sn.bucket_activations(self.s)
        self.assertTrue(acts)
        for bid, a in acts.items():
            self.assertIn(bid, {b["id"] for b in sb.BUCKETS})
            self.assertTrue(0.0 <= a["activation"] <= 1.0)
            self.assertNotIn("security", a)
            self.assertNotIn("securities", a)
            for d in a["drivers"]:
                self.assertIn(d["channel_id"], sn.CHANNELS)

    def test_strength_is_never_multiplied_into_activation(self):
        """An ordinal times a probability is a number with no unit that looks like an expected
        value. Both travel; neither is folded into the other."""
        for a in sn.bucket_activations(self.s).values():
            self.assertIn(a["strength"], sn.STRENGTHS)
            engaged = {d["engaged_probability"] for d in a["drivers"]}
            self.assertIn(a["activation"], engaged,
                          "activation is not one of its drivers' probabilities, so something "
                          "has been combined into it")

    def test_the_requested_chain_is_walkable_for_fro(self):
        """The example from the brief, end to end:
        Hormuz branch -> crude_freight_rate_ws up -> Tankers activation -> FRO sensitivity +
        -> derived exposure. Every hop present, every hop carrying its own evidence."""
        hits = sn.explain(self.s, "FRO", "crude_freight_rate_ws")
        self.assertEqual(len(hits), 1)
        rec = hits[0]
        self.assertEqual(rec["status"], "exposed")
        self.assertEqual(rec["sign"], 1)
        self.assertEqual(len(rec["paths"]), 1)
        p = rec["paths"][0]
        # Hop 1 — the scenario and the branches that engage this mechanism.
        self.assertEqual(rec["scenario_id"], "hormuz")
        self.assertEqual([b["id"] for b in p["branches"]],
                         ["limited", "sustained", "severe"])
        self.assertAlmostEqual(p["engaged_probability"], 0.30, places=9)
        # Hop 2 — the channel, named, with its unit and its direction.
        self.assertEqual(p["channel_id"], "crude_freight_rate_ws")
        self.assertEqual(p["channel_unit"], "Worldscale points")
        self.assertEqual(p["edge_sign"], 1)
        self.assertIn("ton-miles", p["mechanism"])
        # Hop 3 — the bucket, by id AND name, with membership tier.
        self.assertEqual((p["bucket_id"], p["bucket_name"]), ("04", "Tankers"))
        self.assertEqual(p["membership_tier"], "liquid")
        # Hop 4 — the security's own sensitivity to that channel.
        self.assertEqual((p["sensitivity_sign"], p["sensitivity_magnitude"]), (1, 0.85))
        # And every hop says what kind of number it is.
        for field in ("basis", "horizon"):
            self.assertTrue(p[field])

    def test_nothing_in_a_path_needs_recomputing_to_be_rendered(self):
        """The concrete form of the contract: a renderer holding one path can name the
        scenario, the branches, the channel, the mechanism, the bucket, the tier, the
        sensitivity and the horizon without reaching back into any registry."""
        expected = {"scenario_id", "branches", "engaged_probability", "channel_id",
                    "channel_label", "channel_unit", "edge_sign", "edge_strength",
                    "edge_confidence", "mechanism", "bucket_id", "bucket_name",
                    "membership_tier", "sensitivity_sign", "sensitivity_magnitude",
                    "sensitivity_confidence", "sensitivity_basis", "horizon", "basis",
                    "provenance"}
        for rec in self.ex.values():
            for p in rec["paths"]:
                # EXACT, not a superset. A missing field means the UI has to look something
                # up — the recomputation this phase exists to prevent. An EXTRA field is the
                # more dangerous direction: it is where a derived quantity gets smuggled in,
                # and the one that escaped first was `exposure_from_tier`, turning membership
                # strength into a number a surface would read as exposure.
                self.assertEqual(set(p), expected,
                                 "path shape drifted: missing {}, extra {}".format(
                                     sorted(expected - set(p)), sorted(set(p) - expected)))

    def test_membership_tier_is_never_a_number(self):
        """Tier is membership STRENGTH — whether a name is a core or a satellite holding of a
        bucket — and it says nothing about how that name responds to a channel. Read as
        exposure it would rank a large liquid holding above a small one that the mechanism
        actually moves."""
        for rec in self.ex.values():
            for p in rec["paths"]:
                self.assertIn(p["membership_tier"], ("liquid", "satellite"))
                self.assertIsInstance(p["membership_tier"], str)

    def test_a_negative_exposure_is_expressible(self):
        """The thing unsigned editorial heat structurally cannot say. A crude spike lifts the
        barrel (edge +1) and squeezes a refiner's input cost (sensitivity -1), so the derived
        exposure is negative — and the path shows both halves of why."""
        rec = sn.explain(self.s, "VLO", "crude_price_usd_bbl")[0]
        self.assertEqual(rec["status"], "exposed")
        self.assertEqual(rec["sign"], -1)
        p = rec["paths"][0]
        self.assertEqual((p["edge_sign"], p["sensitivity_sign"]), (1, -1))
        # And the same security is positive on another channel, which is why sign lives per
        # (security, channel) and never per security.
        self.assertEqual(sn.explain(self.s, "VLO", "refining_crack_usd_bbl")[0]["sign"], 1)

    def test_paths_that_disagree_are_unresolved_and_never_decided(self):
        """One channel reaching one security through two buckets with opposite edge signs.
        Legal to author — a channel may move two buckets different ways — and impossible to
        net, so the exposure refuses rather than picking.

        Not reachable from the Hormuz fixture, which has no conflict; disabling the
        `unresolved` branch left every test green until this existed."""
        sens_key = ("GD", "crude_price_usd_bbl")
        saved = dict(sn.CHANNEL_SENSITIVITIES)
        try:
            sn.CHANNEL_SENSITIVITIES[sens_key] = dict(
                _prov(), magnitude=0.5, sign=1, confidence=0.4)
            # GD sits in buckets 05 and 16; one channel, opposite directions into each.
            record = _scenario(
                branches=_branches(1.0),
                partition="bands: at least 5% sustained for 7 days",
                transmission=[
                    _edge(channel_id="crude_price_usd_bbl", bucket_id="05", sign=1),
                    _edge(channel_id="crude_price_usd_bbl", bucket_id="16", sign=-1),
                ])
            record["branches"][0]["id"] = "limited"
            sn._validate_scenario("hormuz", record)      # authoring this is legal
            rec = sn.explain(record, "GD", "crude_price_usd_bbl")[0]
            self.assertEqual(len(rec["paths"]), 2, "both routes must be kept")
            self.assertEqual(rec["status"], "unresolved")
            self.assertIsNone(rec["sign"], "a disagreement was silently decided")
            self.assertIn("disagree", rec["why"])
        finally:
            sn.CHANNEL_SENSITIVITIES.clear()
            sn.CHANNEL_SENSITIVITIES.update(saved)

    def test_a_sensitivity_with_no_direction_is_undirected_not_unassessed(self):
        """Four absences, not three, and this test found the fourth by asserting the wrong
        one. A record that EXISTS with `sign: None` says "we know it responds and cannot call
        which way"; no record at all says "nobody looked". Collapsing them is the module's own
        absent-is-not-zero rule broken one level up — and the derivation was collapsing them.

        The magnitude survives, because it was assessed: only the direction is missing."""
        saved = dict(sn.CHANNEL_SENSITIVITIES)
        try:
            sn.CHANNEL_SENSITIVITIES[("GD", "crude_price_usd_bbl")] = dict(
                _prov(), magnitude=0.5, sign=None, confidence=None)
            record = _scenario(
                branches=_branches(1.0),
                partition="bands: at least 5% sustained for 7 days",
                transmission=[_edge(channel_id="crude_price_usd_bbl", bucket_id="05", sign=1)])
            record["branches"][0]["id"] = "limited"
            rec = sn.explain(record, "GD", "crude_price_usd_bbl")[0]
            self.assertEqual(rec["status"], "undirected")
            self.assertIsNone(rec["sign"])
            self.assertEqual(rec["magnitude"], 0.5)
            self.assertIn("its sign is not", rec["why"])
        finally:
            sn.CHANNEL_SENSITIVITIES.clear()
            sn.CHANNEL_SENSITIVITIES.update(saved)

        # And with no record at all, the other absence.
        record = _scenario(
            branches=_branches(1.0),
            partition="bands: at least 5% sustained for 7 days",
            transmission=[_edge(channel_id="crude_price_usd_bbl", bucket_id="05", sign=1)])
        record["branches"][0]["id"] = "limited"
        rec = sn.explain(record, "GD", "crude_price_usd_bbl")[0]
        self.assertEqual(rec["status"], "unassessed")
        self.assertIsNone(rec["magnitude"])

    def test_reached_but_unassessed_is_a_status_not_a_zero(self):
        """The largest population by far — 46 of 58 records. Reporting these as 0 would put
        names the model knows nothing about beside names it has assessed, which is the
        shadow-debt gate's failure in a new place."""
        un = [r for r in self.ex.values() if r["status"] == "unassessed"]
        self.assertTrue(un)
        for r in un:
            self.assertIsNone(r["sign"])
            self.assertIsNone(r["magnitude"])
            self.assertIn("no sensitivity", r["why"])
            self.assertTrue(r["paths"], "an unassessed name still knows how it was reached")

    def test_a_relationship_with_no_magnitude_still_carries_its_sign(self):
        """XOM and CVX: the relationship exists, the direction is known, and the coefficient
        was deliberately not invented. `exposed` with `magnitude=None` is a fourth state and
        it must survive the derivation."""
        rec = sn.explain(self.s, "XOM", "crude_price_usd_bbl")[0]
        self.assertEqual(rec["status"], "exposed")
        self.assertEqual(rec["sign"], 1)
        self.assertIsNone(rec["magnitude"])

    def test_confidence_is_the_weakest_hop_not_an_average(self):
        """An exposure is no more certain than the least certain link that produced it.
        Averaging would let a confident edge launder an unconfident coefficient."""
        rec = sn.explain(self.s, "FRO", "marine_war_risk_premium_pct")[0]
        p = rec["paths"][0]
        self.assertEqual(rec["confidence"],
                         min(p["edge_confidence"], p["sensitivity_confidence"]))

    def test_a_sensitivity_without_a_path_produces_no_exposure(self):
        """A coefficient is not a claim that a scenario reaches a security. STNG has a
        freight-rate sensitivity and is in bucket 04, so it IS reached; a security with a
        sensitivity to a channel no edge routes into its bucket is not."""
        reached = {tk for tk, _cid in self.ex}
        self.assertIn("STNG", reached)
        # Every exposure traces to an edge — none is asserted.
        edges = {(e["channel_id"], e["bucket_id"]) for e in self.s["transmission"]}
        for (tk, cid), rec in self.ex.items():
            for p in rec["paths"]:
                self.assertIn((p["channel_id"], p["bucket_id"]), edges,
                              "{} reached on a path with no edge behind it".format(tk))

    def test_the_unscreenable_reached_are_named_not_dropped(self):
        """Funds, futures and the delisted are reached by the same edges as everything else.
        Dropping them silently is the defect `listedNote` exists to prevent."""
        screened = {row[0] for row in sc.universe_rows()}
        named = dict(sn.unscreenable_reached(self.s, screened))
        self.assertIn("XLE", named)
        self.assertEqual(named["XLE"], "fund")
        self.assertIn("CL=F", named)
        self.assertTrue(named["MRO"].startswith("delisted"))
        for tk in named:
            self.assertNotIn(tk, screened)


class TheAcceptanceGate(unittest.TestCase):
    """Phase C's gate, and the plan's: for one named Hormuz security the full chain is
    inspectable — security <- exposure <- bucket <- transmission mechanism <- scenario — with
    sign, confidence, horizon and basis non-null at each hop.

    No UI phase merges while this is red."""

    def test_one_security_is_explicable_end_to_end(self):
        s = sn.load()["hormuz"]
        rec = sn.explain(s, "FRO", "crude_freight_rate_ws")[0]
        self.assertEqual(rec["status"], "exposed")
        for field in ("sign", "confidence"):
            self.assertIsNotNone(rec[field], "the exposure has no {}".format(field))
        for p in rec["paths"]:
            for field in ("horizon", "basis", "mechanism", "bucket_id", "channel_id",
                          "edge_sign", "sensitivity_sign", "engaged_probability"):
                self.assertIsNotNone(p[field], "hop field {} is null".format(field))
            self.assertIn(p["basis"], sn.BASIS_VALUES)
            self.assertIn(p["horizon"], sn.HORIZONS)
            self.assertTrue(p["provenance"], "a hop with no provenance")
        # The scenario end of the chain resolves to a state and a set of developments.
        self.assertIsNotNone(sn.scenario_state(s))
        self.assertTrue(s["developments"])


class OrderingAuthorityIsGranted(unittest.TestCase):
    """Phase F. Whatever sits at the top of a screen is read as "the one this most affects",
    so ordering securities is a claim and this module decides who may make it.

    Two conditions, and each closes a different hole. A registered `rank_metric` means the
    quantity is one the derivation actually produces and one somebody chose on purpose — a
    free string here would let a scenario sort a screen by anything and call it a ranking. A
    `modelled` basis means the numbers behind that quantity were estimated: a fixture
    magnitude is an author's illustration, and sorting real securities by it publishes an
    order nobody produced.

    V1's only scenario satisfies neither, and the gate is still written as the condition
    rather than as `False` — with both branches exercised here, so the day a model arrives the
    switch is a data change with a validator behind it, not an untested code path."""

    def setUp(self):
        self.s = copy.deepcopy(sn.load()["hormuz"])

    def _modelled(self, s):
        for o in s["observations"]:
            o["basis"] = "modelled"
            o["model_id"] = "test-model"
            o["model_version"] = "1.0.0"
        return s

    def test_the_shipped_fixture_may_not_rank(self):
        r = sn.ranking_authority(sn.load()["hormuz"])
        self.assertFalse(r["quantitative"])
        self.assertTrue(r["why"], "the refusal carries no reason, so a surface has to write "
                                  "its own and two wordings of one rule start drifting")

    def test_a_modelled_scenario_with_a_registered_metric_may_rank(self):
        """The true branch. Without this the gate is `False` for every input it has ever been
        given, which is indistinguishable from a gate that is broken shut."""
        s = self._modelled(self.s)
        s["rank_metric"] = "exposure_magnitude"
        r = sn.ranking_authority(s)
        self.assertTrue(r["quantitative"])
        # The sentence names the metric, because the surfaces that need the name need the
        # sentence too — returning both was two fields where one was read.
        self.assertIn(sn.RANK_METRICS["exposure_magnitude"]["label"], r["why"])

    def test_a_metric_alone_does_not_grant_it(self):
        """A fixture may name the metric it WOULD rank by and still not rank by it."""
        self.s["rank_metric"] = "exposure_magnitude"
        r = sn.ranking_authority(self.s)
        self.assertFalse(r["quantitative"])
        self.assertIn("fixture", r["why"])
        # "Declared but not honoured" is a different state from "never declared", and the
        # refusal has to be able to say which: the sentence names the metric it WOULD rank by.
        self.assertIn(sn.RANK_METRICS["exposure_magnitude"]["label"], r["why"])

    def test_a_modelled_basis_alone_does_not_grant_it(self):
        r = sn.ranking_authority(self._modelled(self.s))
        self.assertFalse(r["quantitative"])
        self.assertIn("no ranking metric is declared", r["why"])

    def test_a_scenario_with_nothing_observed_says_so_rather_than_refusing_vaguely(self):
        self.s["observations"] = []
        self.s["rank_metric"] = "exposure_magnitude"
        r = sn.ranking_authority(self.s)
        self.assertFalse(r["quantitative"])
        self.assertIn("nothing has been observed", r["why"])

    def test_an_unregistered_metric_raises(self):
        """The registry is the whole mechanism. As a free string, `rank_metric: "impact"`
        validates cleanly and grants ordering authority over a quantity that does not exist."""
        self.s["rank_metric"] = "impact"
        with self.assertRaises(ValueError) as cm:
            sn.validate_scenarios({"hormuz": self.s})
        self.assertIn("rank_metric", str(cm.exception))

    def test_every_registered_metric_reaches_a_reader(self):
        """Every field a registered metric carries has to end up in front of somebody, or it is
        the `adx_kelly_mult` shape — a knob with no wiring, believed by the next reader because
        it is written down. Both of these are the words the refusal sentence is built from,
        which is what the drawer and the ranked chart print."""
        s = copy.deepcopy(sn.load()["hormuz"])
        for name, spec in sn.RANK_METRICS.items():
            self.assertEqual(set(spec), {"label", "of"},
                             "{} carries a field nothing reads".format(name))
            s["rank_metric"] = name
            why = sn.ranking_authority(s)["why"]
            for field, text in spec.items():
                self.assertIn(text, why,
                              "{}'s {} never reaches a surface".format(name, field))

    def test_the_verdict_travels_with_the_scenario(self):
        """Decided in Python and shipped, not re-decided by a surface."""
        p = sn.as_payload()["hormuz"]
        self.assertIn("ranking", p)
        self.assertFalse(p["ranking"]["quantitative"])
        self.assertTrue(p["ranking"]["why"])
        # And nothing rides along that no surface reads. The registries reaching the browser
        # are the ones the page actually looks things up in.
        js = sn.runtime_js()
        for dead in ("RANK_METRICS", "STRENGTHS"):
            self.assertNotIn(dead, js,
                             dead + " is emitted to a page that never reads it")


class TheUnconditionalExpectedImpactRefusesAPartialTree(unittest.TestCase):
    """Research-honesty review. The fourth quantity this module keeps apart, and the easiest of
    them to produce by accident.

    Everything needed is already on screen: branch probabilities in one tile, a conditional mean
    per branch the moment anyone writes one. Multiply and sum and there it is — a number that
    looks like an expected return and, over a tree missing one branch's mean, is an expected
    value of nothing in particular. The gate is on the MEAN, per branch: a branch carrying
    quantiles and no mean passes a presence check and then needs a mean that does not exist,
    and substituting p50 under skew is an invented number three surfaces from where it shows."""

    def setUp(self):
        self.s = copy.deepcopy(sn.load()["hormuz"])

    def test_the_shipped_fixture_produces_nothing_and_names_the_branches(self):
        r = sn.expected_scenario_impact(self.s)
        self.assertIsNone(r["value"])
        # Named, not counted: "some branches" leaves the reader unable to check.
        for b in self.s["branches"]:
            self.assertIn(b["id"], r["why"])

    def test_a_complete_tree_produces_the_probability_weighted_mean(self):
        """The true branch. Without it the gate has only ever returned None, which is
        indistinguishable from a gate broken shut."""
        for b in self.s["branches"]:
            b["expected_return"] = {"none": 0.0, "limited": -0.02,
                                    "sustained": -0.06, "severe": -0.15}[b["id"]]
        r = sn.expected_scenario_impact(self.s)
        want = sum(b["probability"] * b["expected_return"] for b in self.s["branches"])
        self.assertAlmostEqual(r["value"], want, places=9)
        self.assertEqual(r["horizon"], self.s["branches"][0]["horizon"])
        self.assertIsNone(r["why"])

    def test_one_missing_mean_is_enough_to_refuse(self):
        """The whole point. A tree that is 98% covered by probability mass and missing one
        branch's mean still cannot produce an expectation."""
        for b in self.s["branches"]:
            b["expected_return"] = 0.0
        gone = self.s["branches"][-1]          # 2% of the mass
        del gone["expected_return"]
        r = sn.expected_scenario_impact(self.s)
        self.assertIsNone(r["value"],
                          "an expectation was computed over the branches that had a mean")
        self.assertIn(gone["id"], r["why"])

    def test_a_scenario_with_no_branches_says_that_rather_than_returning_zero(self):
        self.s["branches"] = []
        self.s["observations"] = []            # branch/observation coherence
        r = sn.expected_scenario_impact(self.s)
        self.assertIsNone(r["value"])
        self.assertIn("no branch tree", r["why"])

    def test_it_travels_in_the_payload_so_a_surface_can_say_it_is_absent(self):
        """Shipped even though it is null for every scenario that exists. A quantity a surface
        cannot get is worth saying out loud: the gap between "30% chance" and "what is this
        worth" is where a reader supplies their own arithmetic if nothing says the system has
        not."""
        p = sn.as_payload()["hormuz"]
        self.assertIn("expected_impact", p)
        self.assertIsNone(p["expected_impact"]["value"])
        self.assertTrue(p["expected_impact"]["why"])

    def test_an_expected_return_is_never_multiplied_into_an_exposure(self):
        """Two different quantities about two different things. Exposure is dimensionless and
        per (security, channel); this is a portfolio-level mean over the branch tree. Nothing
        joins them, and the exposure records carry no trace of one."""
        for b in self.s["branches"]:
            b["expected_return"] = -0.05
        for rec in sn.security_exposures(self.s).values():
            self.assertNotIn("expected_return", rec)
            for p in rec["paths"]:
                self.assertNotIn("expected_return", p)


class TheAbsenceStatesHaveAnOrderOfPrecedence(unittest.TestCase):
    """Derivation review. Two of the four statuses can be true of one exposure at once, and
    nothing said which wins.

    A security reached by paths that disagree on horizon, on a channel nobody has assessed it
    for, is both `unassessed` and — structurally — `unresolved`. `unassessed` wins, and that is
    the right way round: `unresolved` means "we have conflicting assessments", which would be a
    claim about work nobody has done. With no coefficient there is no sign to net and no
    magnitude to report, so there is nothing to resolve; the disagreement becomes actionable at
    exactly the moment somebody writes the sensitivity, and the status flips then.

    The disagreement is not lost meanwhile — every path keeps its own horizon in `paths[]`, so
    a surface can show both routes. What it may not do is call them unresolved."""

    def setUp(self):
        self.s = copy.deepcopy(sn.load()["hormuz"])

    def _fork(self, security_bucket, horizon):
        """Two edges on ONE channel into one bucket, disagreeing on horizon."""
        e = copy.deepcopy(self.s["transmission"][0])
        e["bucket_id"] = security_bucket
        e["horizon"] = horizon
        self.s["transmission"].append(e)

    def test_an_assessed_security_reached_by_disagreeing_paths_is_unresolved(self):
        self._fork("04", "90d")                      # FRO has a sensitivity on this channel
        rec = sn.security_exposures(self.s)[("FRO", "crude_freight_rate_ws")]
        self.assertEqual(rec["status"], "unresolved")
        self.assertIsNone(rec["sign"], "a disagreement was silently decided")
        self.assertIsNone(rec["magnitude"])
        self.assertEqual(len(rec["paths"]), 2, "a disagreeing path was dropped")
        self.assertIn("horizons", rec["why"])

    def test_an_unassessed_security_reached_by_disagreeing_paths_stays_unassessed(self):
        """The precedence. Nothing stated it before this test, so either order would have
        looked deliberate to the next reader."""
        self._fork("04", "90d")
        ex = sn.security_exposures(self.s)
        # A bucket-04 member with no sensitivity on this channel — reached by both edges.
        unassessed = [(k, v) for k, v in ex.items()
                      if k[1] == "crude_freight_rate_ws" and len(v["paths"]) == 2
                      and all(p["sensitivity_basis"] is None for p in v["paths"])]
        self.assertTrue(unassessed, "the fixture no longer reaches an unassessed name twice")
        for key, rec in unassessed:
            self.assertEqual(rec["status"], "unassessed",
                             "%s is reported as unresolved, which claims conflicting "
                             "assessments where nobody has assessed anything" % key[0])
            self.assertIn("no sensitivity", rec["why"])
            # And the disagreement survives for a surface that wants to show it.
            self.assertEqual({p["horizon"] for p in rec["paths"]}, {"30d", "90d"},
                             "the paths' own horizons were collapsed")


class ThePathIsOneSeriesAndNotTheirUnion(unittest.TestCase):
    """Bug Bot, round 1. A scenario may carry more than one probability series and the schema
    is right to allow it: the same question at 30 and 90 days, or two different resolvable
    questions, are genuinely different quantities.

    `scenario_state` already picks ONE of them — that is what the strip prints. The chart read
    `scenario["observations"]`, which is their UNION, so two questions would have been drawn as
    a single line and labelled with whichever point happened to sort first. That is the failure
    `sovereign_buckets` records in its own docstring — the same number, two answers, both
    published — arriving by a different route.

    The filter lives beside the state it has to agree with, so a surface cannot resolve the
    scenario one way and its series another."""

    def setUp(self):
        self.s = copy.deepcopy(sn.load()["hormuz"])

    def test_the_shipped_fixture_is_its_whole_series(self):
        s = sn.load()["hormuz"]
        series = sn.probability_series(s)
        self.assertEqual(len(series), len(s["observations"]))
        self.assertEqual([o["timestamp"] for o in series],
                         sorted(o["timestamp"] for o in s["observations"]),
                         "the series is not in chronological order")

    def test_a_second_horizon_is_not_drawn_into_the_same_line(self):
        other = copy.deepcopy(self.s["observations"][-1])
        other["horizon"] = "90d"
        other["probability"] = 0.55
        self.s["observations"].append(other)
        sn.validate_scenarios({"hormuz": self.s})     # legal data, not a malformation
        state = sn.scenario_state(self.s)
        series = sn.probability_series(self.s, state)
        self.assertTrue(all(o["horizon"] == state["horizon"] for o in series),
                        "a 90-day probability was drawn onto the 30-day path")
        self.assertNotIn(0.55, [o["probability"] for o in series])

    def test_a_second_target_is_not_drawn_into_the_same_line(self):
        sn.TARGETS["bugbot_second_target"] = {
            "label": "A second resolvable question",
            "threshold_pct": 5, "min_days": 7,
            "question": "Do transits fall at least 5% below baseline for at least 7 days?"}
        try:
            other = copy.deepcopy(self.s["observations"][-1])
            other["target_id"] = "bugbot_second_target"
            other["probability"] = 0.90
            self.s["observations"].append(other)
            sn.validate_scenarios({"hormuz": self.s})
            state = sn.scenario_state(self.s)
            series = sn.probability_series(self.s, state)
            self.assertTrue(all(o["target_id"] == state["target_id"] for o in series),
                            "two different questions were drawn as one line")
            self.assertNotIn(0.90, [o["probability"] for o in series])
        finally:
            del sn.TARGETS["bugbot_second_target"]

    def test_the_series_and_the_state_are_resolved_together(self):
        """Passing the state in is what stops the chart and the strip resolving the same
        scenario twice and disagreeing about which series they are showing."""
        state = sn.scenario_state(self.s)
        series = sn.probability_series(self.s, state)
        self.assertEqual(series[-1]["probability"], state["probability"],
                         "the newest point of the series is not the reading the strip prints")
        self.assertEqual(series[-1]["timestamp"], state["as_of"])

    def test_a_scenario_with_nothing_observed_has_no_series_rather_than_an_empty_line(self):
        self.s["observations"] = []
        self.s["branches"] = []          # branch/observation coherence
        self.assertEqual(sn.probability_series(self.s), [])

    def test_the_resolved_series_travels_so_no_surface_picks_its_own(self):
        p = sn.as_payload()["hormuz"]
        self.assertIn("series", p)
        self.assertEqual([o["probability"] for o in p["series"]],
                         [o["probability"] for o in sn.probability_series(
                             sn.load()["hormuz"])])

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
        self._bad(_scenario(branches=_branches(0.5, 0.2)), "sum to")
        self._bad(_scenario(branches=_branches(0.6, 0.6)), "sum to")
        sn._validate_scenario("hormuz", _scenario(branches=_branches(0.6, 0.25, 0.15)))

    def test_branch_ids_are_unique(self):
        """Two branches with one id are two states the tree cannot tell apart, and any later
        per-branch record — a conditional impact, an expected value — silently attaches to
        whichever was read last."""
        dup = _branches(0.5, 0.5)
        dup[1]["id"] = dup[0]["id"]
        self._bad(_scenario(branches=dup), "duplicate branch id")

    def test_branches_share_one_horizon(self):
        mixed = _branches(0.5, 0.5)
        mixed[1]["horizon"] = "90d"
        self._bad(_scenario(branches=mixed), "span horizons")

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
        self._bad(_scenario(branches=_branches(1.4, -0.4)), "outside 0..1")


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
        self.assertIsNone(sn.sensitivity("FRO", "crude_freight_rate_ws"))
        self.assertIsNone(sn.sensitivity("NOSUCHTICKER", "crude_price_usd_bbl"))
        self.assertEqual(sn.channels_for("FRO"), [])


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
